"""LiveKit participant tokens and server-enforced proximity subscription control.

All participants in a tenant share one isolated LiveKit room. Participant tokens
explicitly deny client-side subscriptions; the API grants individual track
subscriptions with LiveKit's RoomService.UpdateSubscriptions after checking the
server-authoritative BDS positions, dimensions, mute state, deafen state and group
membership. Never replace this with a tenant-wide auto-subscribe room.
"""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import timedelta
from typing import Any, Iterable

from .config import settings
from .models import GroupMember, LocalMute, Player, Server, VoiceGroup

log = logging.getLogger("horizon_voice.media")
_subscription_cache: dict[tuple[str, str], set[str]] = {}
_permission_cache: dict[tuple[str, str], bool] = {}
_muted_track_cache: dict[tuple[str, str], set[str]] = {}
_server_sync_locks: dict[str, asyncio.Lock] = {}


def livekit_is_configured() -> bool:
    return bool(settings.livekit_api_key and settings.livekit_api_secret and settings.livekit_public_url)


def room_name(server_id: str) -> str:
    # UUID-like server IDs produce a safe, stable and tenant-isolated room name.
    safe = "".join(char for char in server_id.lower() if char.isalnum())
    return f"horizon-{safe}"


def can_hear(
    listener: Player,
    speaker: Player,
    max_distance: float,
    listener_groups: set[str],
    speaker_groups: set[str],
    locally_muted: bool,
) -> bool:
    """Pure authorization predicate; the server, not the browser, decides this."""
    if listener.id == speaker.id or not listener.online or not speaker.online:
        return False
    if listener.deafened or locally_muted or speaker.self_muted or speaker.moderation_muted:
        return False
    # Group mode is exclusive: if either participant selected a group channel,
    # proximity must not leak that participant's microphone to nearby players.
    listener_group = getattr(listener, "active_group_id", None)
    speaker_group = getattr(speaker, "active_group_id", None)
    if listener_group or speaker_group:
        return bool(listener_group and listener_group == speaker_group
                    and listener_group in listener_groups and listener_group in speaker_groups)
    if listener.dimension != speaker.dimension:
        return False
    distance_sq = (
        (listener.x - speaker.x) ** 2
        + (listener.y - speaker.y) ** 2
        + (listener.z - speaker.z) ** 2
    )
    return math.isfinite(distance_sq) and distance_sq <= max_distance * max_distance


def create_participant_token(player: Player, server: Server) -> str:
    """Mint a short-lived token; import SDK lazily so API tests do not need media."""
    if not livekit_is_configured():
        raise RuntimeError("LiveKit não está configurado no ambiente")
    from livekit import api  # type: ignore[import-not-found]

    can_publish = bool(server.voice_enabled and not player.self_muted and not player.moderation_muted)
    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(player.id)
        .with_name(player.display_name)
        .with_ttl(timedelta(minutes=max(5, min(settings.livekit_token_minutes, 120))))
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name(server.id),
                can_publish=can_publish,
                can_subscribe=False,
                can_publish_data=False,
                can_publish_sources=["microphone"],
            )
        )
    )
    return token.to_jwt()


async def synchronize_room(server: Server, db: Any) -> dict[str, int]:
    """Reconcile allowed LiveKit subscriptions with current authoritative DB state.

    It deliberately uses a single-worker in-memory diff cache. The deployment is
    configured for one API worker; Redis-backed coordination is required before
    horizontal API scaling. On first sync after a process restart, all discovered
    tracks are unsubscribed before the allowed set is restored.
    """
    if not livekit_is_configured():
        return {"participants": 0, "subscriptions_added": 0, "subscriptions_removed": 0}

    lock = _server_sync_locks.setdefault(server.id, asyncio.Lock())
    async with lock:
        from livekit import api  # type: ignore[import-not-found]

        room = room_name(server.id)
        players = db.query(Player).filter(Player.server_id == server.id).all()
        players_by_id = {player.id: player for player in players}
        group_members: dict[str, set[str]] = {}
        member_rows = (
            db.query(GroupMember.group_id, GroupMember.player_id)
            .join(VoiceGroup, VoiceGroup.id == GroupMember.group_id)
            .filter(VoiceGroup.server_id == server.id)
            .all()
        )
        for group_id, player_id in member_rows:
            group_members.setdefault(player_id, set()).add(group_id)
        local_mutes = {
            (row.listener_player_id, row.muted_player_id)
            for row in db.query(LocalMute).join(Player, Player.id == LocalMute.listener_player_id)
            .filter(Player.server_id == server.id).all()
        }

        added = 0
        removed = 0
        seen_listener_keys: set[tuple[str, str]] = set()
        async with api.LiveKitAPI(
            settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret
        ) as lk:
            participant_list = await lk.room.list_participants(
                api.proto_room.ListParticipantsRequest(room=room)
            )
            participants = list(participant_list.participants)
            published_tracks: dict[str, list[str]] = {}
            blocked_publishers: set[str] = set()
            for participant in participants:
                identity = str(participant.identity)
                player = players_by_id.get(identity)
                if player is None or not player.online or not server.voice_enabled:
                    # A stale/unpaired identity must not remain in the tenant's room.
                    try:
                        await lk.room.remove_participant(
                            api.proto_room.RoomParticipantIdentity(room=room, identity=identity)
                        )
                    except Exception:
                        log.exception("Could not remove stale LiveKit participant %s", identity)
                    continue
                track_sids = [str(track.sid) for track in participant.tracks if getattr(track, "sid", None)]
                published_tracks[identity] = track_sids
                if not player.voice_connected:
                    player.voice_connected = True

                muted = bool(player.self_muted or player.moderation_muted)
                permission_key = (server.id, identity)
                previous_permission = _permission_cache.get(permission_key)
                permission_changed = previous_permission is None or previous_permission != muted
                if permission_changed:
                    try:
                        permission = api.proto_room.ParticipantPermission(
                            can_publish=not muted,
                            can_subscribe=False,
                            can_publish_data=False,
                        )
                        await lk.room.update_participant(
                            api.proto_room.UpdateParticipantRequest(
                                room=room, identity=identity, permission=permission
                            )
                        )
                        _permission_cache[permission_key] = muted
                    except Exception:
                        # Fail closed and retry the permission update on the next
                        # reconciliation instead of caching a false success.
                        log.exception("Could not update media permissions for %s", identity)
                        _permission_cache.pop(permission_key, None)
                        blocked_publishers.add(identity)
                        muted = True

                muted_tracks = _muted_track_cache.setdefault(permission_key, set())
                for track_sid in track_sids:
                    needs_track_update = (
                        (muted and track_sid not in muted_tracks)
                        or (not muted and (track_sid in muted_tracks or previous_permission is None))
                    )
                    if not needs_track_update and not (identity in blocked_publishers and muted):
                        continue
                    try:
                        await lk.room.mute_published_track(
                            api.proto_room.MuteRoomTrackRequest(
                                room=room, identity=identity, track_sid=track_sid, muted=muted
                            )
                        )
                        if muted:
                            muted_tracks.add(track_sid)
                        else:
                            muted_tracks.discard(track_sid)
                    except Exception:
                        log.exception("Could not synchronize mute state for track %s", track_sid)
                        if muted:
                            blocked_publishers.add(identity)
                muted_tracks.intersection_update(track_sids)

            live_identities = set(published_tracks)
            for player in players:
                if player.voice_connected and player.id not in live_identities:
                    player.voice_connected = False
                    player.speaking = False
            db.commit()
            active_players = [players_by_id[identity] for identity in live_identities if identity in players_by_id]
            all_track_sids = {sid for sids in published_tracks.values() for sid in sids}

            for listener in active_players:
                identity = listener.id
                cache_key = (server.id, identity)
                seen_listener_keys.add(cache_key)
                desired: set[str] = set()
                if server.voice_enabled and not listener.deafened:
                    listener_groups = group_members.get(listener.id, set())
                    for speaker in active_players:
                        if speaker.id in blocked_publishers or not published_tracks.get(speaker.id):
                            continue
                        if can_hear(
                            listener,
                            speaker,
                            float(server.max_distance),
                            listener_groups,
                            group_members.get(speaker.id, set()),
                            (listener.id, speaker.id) in local_mutes,
                        ):
                            desired.update(published_tracks.get(speaker.id, []))

                previous = _subscription_cache.get(cache_key)
                # Rebuild from a known empty state after API restart, not trusting
                # subscriptions that may have been left by a previous process.
                removals = (all_track_sids - desired) if previous is None else (previous - desired)
                additions = desired - (previous or set())
                if removals:
                    await lk.room.update_subscriptions(
                        api.proto_room.UpdateSubscriptionsRequest(
                            room=room, identity=identity, track_sids=sorted(removals), subscribe=False
                        )
                    )
                    removed += len(removals)
                if additions:
                    await lk.room.update_subscriptions(
                        api.proto_room.UpdateSubscriptionsRequest(
                            room=room, identity=identity, track_sids=sorted(additions), subscribe=True
                        )
                    )
                    added += len(additions)
                _subscription_cache[cache_key] = desired

        for stale_key in [key for key in _subscription_cache if key[0] == server.id and key not in seen_listener_keys]:
            _subscription_cache.pop(stale_key, None)
            _permission_cache.pop(stale_key, None)
            _muted_track_cache.pop(stale_key, None)

        return {"participants": len(published_tracks), "subscriptions_added": added, "subscriptions_removed": removed}


async def force_media_mute(server: Server, player: Player, muted: bool) -> None:
    """Immediately revoke/restore publish permission and mute active tracks."""
    if not livekit_is_configured():
        return
    from livekit import api  # type: ignore[import-not-found]

    room = room_name(server.id)
    async with api.LiveKitAPI(settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret) as lk:
        permission = api.proto_room.ParticipantPermission(
            can_publish=not muted,
            can_subscribe=False,
            can_publish_data=False,
        )
        try:
            participant = await lk.room.get_participant(
                api.proto_room.RoomParticipantIdentity(room=room, identity=player.id)
            )
        except Exception:
            # Player may not currently have a media connection.
            return
        await lk.room.update_participant(
            api.proto_room.UpdateParticipantRequest(room=room, identity=player.id, permission=permission)
        )
        muted_tracks = _muted_track_cache.setdefault((server.id, player.id), set())
        for track in participant.tracks:
            track_sid = str(getattr(track, "sid", "") or "")
            if not track_sid:
                continue
            if muted or track_sid in muted_tracks:
                await lk.room.mute_published_track(
                    api.proto_room.MuteRoomTrackRequest(
                        room=room, identity=player.id, track_sid=track_sid, muted=muted
                    )
                )
                if muted:
                    muted_tracks.add(track_sid)
                else:
                    muted_tracks.discard(track_sid)
    _permission_cache[(server.id, player.id)] = muted


async def remove_media_participant(server: Server, player_id: str) -> None:
    """Remove the browser/media identity when its BDS entity leaves the world."""
    if not livekit_is_configured():
        return
    from livekit import api  # type: ignore[import-not-found]

    async with api.LiveKitAPI(settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret) as lk:
        try:
            await lk.room.remove_participant(
                api.proto_room.RoomParticipantIdentity(room=room_name(server.id), identity=player_id)
            )
        except Exception as exc:
            # A participant that is already gone needs no further action. The caller
            # still updates the authoritative database presence state.
            log.info("LiveKit participant %s was already disconnected: %s", player_id, exc)
    key = (server.id, player_id)
    _permission_cache.pop(key, None)
    _muted_track_cache.pop(key, None)
    _subscription_cache.pop(key, None)
