from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
import math
import re
import secrets
import time
import uuid
from collections import defaultdict, deque
from threading import Lock
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, SessionLocal, engine, get_db
from .models import Account, ActivationCode, BrowserSession, GroupMember, LocalMute, PairingCode, Player, Server, VoiceGroup
from .voice_media import (
    can_hear, create_participant_token, force_media_mute, livekit_is_configured,
    room_name, synchronize_room, remove_media_participant,
)
from .security import (
    create_access_token, get_browser_session, hash_password, hash_value, new_id,
    new_secret, require_account, server_auth, verify_password,
)

app = FastAPI(title=settings.app_name, version="0.1.0", docs_url="/docs" if settings.environment != "production" else None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_origin_regex=r"^https://([a-z0-9-]+\.)?voice-horizon\.online$|^http://localhost(:[0-9]+)?$",
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Server-Key", "X-Tenant-Slug"],
)

if settings.auto_create_schema:
    Base.metadata.create_all(bind=engine)


class RegisterIn(BaseModel):
    email: str = Field(min_length=6, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("E-mail inválido")
        return value


class LoginIn(BaseModel):
    email: str
    password: str


class ServerCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    slug: str = Field(min_length=3, max_length=50)
    description: str = Field(default="", max_length=240)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        value = value.strip().lower()
        reserved = {"www", "api", "dashboard", "docs", "status", "admin", "mail", "ftp", "voice", "media", "turn", "livekit"}
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{1,48}[a-z0-9])", value):
            raise ValueError("Subdomínio deve usar letras minúsculas, números e hífen")
        if value in reserved:
            raise ValueError("Este subdomínio é reservado")
        return value


class ActivateIn(BaseModel):
    code: str = Field(min_length=10, max_length=40)


class PairClaimIn(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")
    identity_key: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=64)
    dimension: str = Field(default="minecraft:overworld", max_length=80)
    x: float
    y: float
    z: float

    @field_validator("x", "y", "z")
    @classmethod
    def finite_coordinate(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Coordenada inválida")
        return value


class PositionItem(BaseModel):
    identity_key: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=64)
    dimension: str = Field(max_length=80)
    x: float
    y: float
    z: float

    @field_validator("x", "y", "z")
    @classmethod
    def finite_coordinate(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Coordenada inválida")
        return value


class PositionBatchIn(BaseModel):
    players: list[PositionItem] = Field(max_length=200)


class SelfMuteIn(BaseModel):
    muted: bool


class ServerSelfMuteIn(BaseModel):
    identity_key: str = Field(min_length=1, max_length=100)
    muted: bool


class PlayerLeaveIn(BaseModel):
    identity_key: str = Field(min_length=1, max_length=100)


class GroupCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=48)
    is_private: bool = False
    password: str | None = Field(default=None, min_length=8, max_length=128)
    max_members: int = Field(default=8, ge=2, le=32)


class GroupJoinIn(BaseModel):
    code: str = Field(min_length=6, max_length=12)
    password: str | None = Field(default=None, max_length=128)


class ServerGroupCreateIn(BaseModel):
    identity_key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=2, max_length=48)
    is_private: bool = False
    password: str | None = Field(default=None, min_length=8, max_length=128)
    max_members: int = Field(default=8, ge=2, le=32)


class ServerGroupJoinIn(BaseModel):
    identity_key: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=6, max_length=12)
    password: str | None = Field(default=None, max_length=128)


class ServerGroupLeaveIn(BaseModel):
    identity_key: str = Field(min_length=1, max_length=100)


class DashboardSettingsIn(BaseModel):
    max_distance: float = Field(ge=5, le=100)
    voice_enabled: bool


class DeafenIn(BaseModel):
    deafened: bool


class LocalMuteIn(BaseModel):
    muted: bool


class SpeakingIn(BaseModel):
    speaking: bool


class ConnectionHub:
    """Single-process websocket fanout. Use Redis pub/sub before running multiple API workers."""
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = {}

    async def connect(self, server_id: str, socket: WebSocket) -> None:
        await socket.accept()
        self.connections.setdefault(server_id, set()).add(socket)

    def disconnect(self, server_id: str, socket: WebSocket) -> None:
        self.connections.get(server_id, set()).discard(socket)

    async def publish(self, server_id: str, event: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for socket in list(self.connections.get(server_id, set())):
            try:
                await socket.send_json(event)
            except Exception:
                stale.append(socket)
        for socket in stale:
            self.disconnect(server_id, socket)


hub = ConnectionHub()
_rate_limit_lock = Lock()
_rate_limit_hits: dict[str, deque[float]] = defaultdict(deque)
_media_sync_tasks: dict[str, asyncio.Task] = {}
_media_sync_pending: set[str] = set()


def schedule_media_sync(server_id: str) -> None:
    """Coalesce frequent movement/track events into one LiveKit reconciliation."""
    current = _media_sync_tasks.get(server_id)
    if current is not None and not current.done():
        _media_sync_pending.add(server_id)
        return

    async def worker() -> None:
        try:
            while True:
                await asyncio.sleep(0.2)
                _media_sync_pending.discard(server_id)
                db = SessionLocal()
                try:
                    server = db.get(Server, server_id)
                    if server is not None:
                        await synchronize_room(server, db)
                except Exception:
                    # Never let a media-control failure interrupt BDS gameplay/API flows.
                    import logging
                    logging.getLogger("horizon_voice.media").exception("LiveKit reconciliation failed for %s", server_id)
                finally:
                    db.close()
                if server_id not in _media_sync_pending:
                    break
        finally:
            _media_sync_tasks.pop(server_id, None)

    _media_sync_tasks[server_id] = asyncio.create_task(worker())


def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Process-local limiter for the single-worker preview deployment.

    This is deliberately not described as distributed protection; Redis-backed
    limits are a required production hardening task before scaling out.
    """
    now = time.monotonic()
    with _rate_limit_lock:
        hits = _rate_limit_hits[key]
        while hits and now - hits[0] >= window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = max(1, int(window_seconds - (now - hits[0])))
            raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde e tente novamente.",
                                headers={"Retry-After": str(retry_after)})
        hits.append(now)


def request_fingerprint(request: Request) -> str:
    # Nginx overwrites X-Real-IP and the API container is private to that proxy.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def resolve_tenant(request: Request, db: Session = Depends(get_db)) -> Server:
    slug = request.headers.get("x-tenant-slug", "").strip().lower()
    if not slug:
        host = request.headers.get("host", "").split(":", 1)[0].lower()
        suffix = "." + settings.public_base_domain.lower()
        if host.endswith(suffix):
            slug = host[:-len(suffix)]
    if not slug:
        raise HTTPException(status_code=400, detail="Não foi possível identificar o servidor pelo domínio")
    tenant = db.query(Server).filter(Server.slug == slug, Server.status == "active").first()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Servidor Horizon Voice não encontrado")
    return tenant


def require_browser(request: Request, db: Session = Depends(get_db)) -> BrowserSession:
    return get_browser_session(request.cookies.get("hv_session"), db)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "horizon-voice-api", "environment": settings.environment}


@app.post("/api/v1/auth/register", status_code=201)
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(f"register:{request_fingerprint(request)}", 5, 3600)
    if db.query(Account).filter(Account.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Este e-mail já está cadastrado")
    account = Account(id=new_id(), email=payload.email, password_hash=hash_password(payload.password))
    db.add(account)
    db.commit()
    return {"id": account.id, "email": account.email, "access_token": create_access_token(account.id), "token_type": "bearer"}


@app.post("/api/v1/auth/login")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(f"login:{request_fingerprint(request)}", 10, 300)
    account = db.query(Account).filter(Account.email == payload.email.strip().lower()).first()
    if account is None or not verify_password(payload.password, account.password_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")
    return {"id": account.id, "email": account.email, "access_token": create_access_token(account.id), "token_type": "bearer"}


@app.get("/api/v1/auth/me")
def me(account: Account = Depends(require_account)):
    return {"id": account.id, "email": account.email, "created_at": account.created_at.isoformat()}


@app.post("/api/v1/servers", status_code=201)
def create_server(payload: ServerCreateIn, account: Account = Depends(require_account), db: Session = Depends(get_db)):
    if db.query(Server).filter(Server.slug == payload.slug).first():
        raise HTTPException(status_code=409, detail="Este subdomínio já está em uso")
    server = Server(
        id=new_id(), owner_id=account.id, name=payload.name.strip(), slug=payload.slug,
        description=payload.description.strip(), status="pending", max_distance=settings.default_proximity_blocks,
    )
    activation = "HV-" + secrets.token_hex(4).upper() + "-" + secrets.token_hex(2).upper()
    db.add(server)
    db.flush()
    db.add(ActivationCode(
        id=new_id(), server_id=server.id, code_hash=hash_value(activation),
        expires_at=now_utc() + timedelta(minutes=15),
    ))
    db.commit()
    return {
        "server_id": server.id,
        "name": server.name,
        "subdomain": f"https://{server.slug}.{settings.public_base_domain}",
        "status": "pending",
        "activation_code": activation,
        "activation_expires_in_seconds": 900,
    }


@app.post("/api/v1/registration/activate")
def activate_server(payload: ActivateIn, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(f"activation:{request_fingerprint(request)}", 10, 60)
    activation = db.query(ActivationCode).filter(ActivationCode.code_hash == hash_value(payload.code.strip().upper())).with_for_update().first()
    if activation is None or activation.claimed_at is not None or ensure_aware(activation.expires_at) <= now_utc():
        raise HTTPException(status_code=400, detail="Código de ativação inválido, expirado ou já utilizado")
    server = db.get(Server, activation.server_id)
    if server is None or server.status != "pending":
        raise HTTPException(status_code=409, detail="Servidor não está aguardando ativação")
    server_secret = "hvs_" + new_secret(48)
    server.server_secret_hash = hash_value(server_secret)
    server.status = "active"
    activation.claimed_at = now_utc()
    db.commit()
    return {"server_id": server.id, "server_name": server.name, "subdomain": server.slug, "server_secret": server_secret, "message": "Guarde a credencial. Ela não será exibida novamente."}


@app.post("/api/v1/pairing/codes", status_code=201)
def create_pairing_code(request: Request, response: Response, tenant: Server = Depends(resolve_tenant), db: Session = Depends(get_db)):
    enforce_rate_limit(f"pairing:{tenant.id}:{request_fingerprint(request)}", settings.pairing_rate_per_minute, 60)
    raw_session = new_secret(32)
    browser_session = BrowserSession(
        id=new_id(), server_id=tenant.id, token_hash=hash_value(raw_session),
        expires_at=now_utc() + timedelta(minutes=settings.browser_session_minutes),
    )
    code = None
    code_hash = None
    for _ in range(10):
        candidate = f"{secrets.randbelow(1_000_000):06d}"
        candidate_hash = hash_value(candidate)
        if db.query(PairingCode).filter(PairingCode.code_hash == candidate_hash).first() is None:
            code, code_hash = candidate, candidate_hash
            break
    if code is None or code_hash is None:
        raise HTTPException(status_code=503, detail="Não foi possível gerar um código único. Tente novamente.")
    db.add(browser_session)
    db.flush()
    db.add(PairingCode(
        id=new_id(), server_id=tenant.id, browser_session_id=browser_session.id,
        code_hash=code_hash, expires_at=now_utc() + timedelta(seconds=settings.pairing_code_seconds),
    ))
    db.commit()
    response.set_cookie(
        key="hv_session", value=raw_session, httponly=True, secure=settings.cookie_secure,
        samesite="strict", max_age=settings.browser_session_minutes * 60, path="/api/v1",
    )
    return {"pairing_code": code, "expires_in_seconds": settings.pairing_code_seconds, "server_name": tenant.name, "subdomain": tenant.slug}


@app.post("/api/v1/pairing/claim")
def claim_pairing(payload: PairClaimIn, server: Server = Depends(server_auth), db: Session = Depends(get_db)):
    pairing = db.query(PairingCode).filter(
        PairingCode.server_id == server.id,
        PairingCode.code_hash == hash_value(payload.code),
    ).with_for_update().first()
    if pairing is None or pairing.consumed_at is not None or ensure_aware(pairing.expires_at) <= now_utc():
        raise HTTPException(status_code=400, detail="Código de pareamento inválido, expirado ou já utilizado")
    browser = db.get(BrowserSession, pairing.browser_session_id)
    if (browser is None or browser.server_id != server.id or browser.revoked_at is not None
            or ensure_aware(browser.expires_at) <= now_utc()):
        raise HTTPException(status_code=400, detail="Sessão do navegador não está mais disponível")
    player = db.query(Player).filter(Player.server_id == server.id, Player.identity_key == payload.identity_key).first()
    if player is None:
        player = Player(id=new_id(), server_id=server.id, identity_key=payload.identity_key, display_name=payload.display_name)
        db.add(player)
    player.display_name = payload.display_name
    player.dimension = payload.dimension
    player.x, player.y, player.z = payload.x, payload.y, payload.z
    player.online, player.last_seen = True, now_utc()
    browser.player_id = player.id
    prior_sessions = db.query(BrowserSession).filter(
        BrowserSession.player_id == player.id,
        BrowserSession.id != browser.id,
        BrowserSession.revoked_at.is_(None),
    ).all()
    for prior in prior_sessions:
        prior.revoked_at = now_utc()
    pairing.consumed_at = now_utc()
    db.commit()
    return {"paired": True, "player_id": player.id, "display_name": player.display_name}


@app.get("/api/v1/pairing/status")
def pairing_status(browser: BrowserSession = Depends(require_browser), db: Session = Depends(get_db)):
    player = db.get(Player, browser.player_id) if browser.player_id else None
    is_paired = bool(player is not None and player.online and player.server_id == browser.server_id)
    return {"paired": is_paired, "player": ({"id": player.id, "name": player.display_name} if is_paired and player else None)}


@app.post("/api/v1/pairing/revoke")
def revoke_pairing(browser: BrowserSession = Depends(require_browser), db: Session = Depends(get_db)):
    browser.revoked_at = now_utc()
    db.commit()
    return {"revoked": True}


@app.post("/api/v1/players/positions")
async def update_positions(payload: PositionBatchIn, server: Server = Depends(server_auth), db: Session = Depends(get_db)):
    now = now_utc()
    identity_keys = [item.identity_key for item in payload.players]
    existing_players = db.query(Player).filter(
        Player.server_id == server.id, Player.identity_key.in_(identity_keys)
    ).all() if identity_keys else []
    player_by_identity = {player.identity_key: player for player in existing_players}
    for item in payload.players:
        player = player_by_identity.get(item.identity_key)
        if player is None:
            player = Player(id=new_id(), server_id=server.id, identity_key=item.identity_key, display_name=item.display_name)
            db.add(player)
            player_by_identity[item.identity_key] = player
        player.display_name = item.display_name
        player.dimension = item.dimension
        player.x, player.y, player.z = item.x, item.y, item.z
        player.online, player.last_seen = True, now
    db.query(Player).filter(Player.server_id == server.id, Player.online.is_(True), Player.last_seen < now - timedelta(seconds=45)).update({Player.online: False, Player.speaking: False}, synchronize_session=False)
    db.commit()
    players = db.query(Player).filter(Player.server_id == server.id, Player.online.is_(True)).all()
    visibility: dict[str, list[str]] = {p.identity_key: [] for p in players}
    max_distance = max(1.0, float(server.max_distance))
    max_distance_sq = max_distance * max_distance
    cells: dict[tuple[str, int, int, int], list[Player]] = defaultdict(list)
    for player in players:
        cell = (player.dimension, math.floor(player.x / max_distance),
                math.floor(player.y / max_distance), math.floor(player.z / max_distance))
        cells[cell].append(player)
    offsets = [(dx, dy, dz) for dx in (-1, 0, 1)
               for dy in (-1, 0, 1) for dz in (-1, 0, 1)]
    for player in players:
        cx, cy, cz = math.floor(player.x / max_distance), math.floor(player.y / max_distance), math.floor(player.z / max_distance)
        for dx, dy, dz in offsets:
            candidates = cells.get((player.dimension, cx + dx, cy + dy, cz + dz), ())
            for other in candidates:
                if player.identity_key >= other.identity_key:
                    continue
                distance_sq = ((player.x - other.x) ** 2 + (player.y - other.y) ** 2 +
                               (player.z - other.z) ** 2)
                if distance_sq <= max_distance_sq:
                    visibility[player.identity_key].append(other.identity_key)
                    visibility[other.identity_key].append(player.identity_key)
    schedule_media_sync(server.id)
    await hub.publish(server.id, {"type": "player_snapshot", "nearby": visibility, "players": [
        {"identity": p.identity_key, "name": p.display_name, "dimension": p.dimension,
         "connected": True, "muted": p.self_muted or p.moderation_muted, "deafened": p.deafened, "speaking": p.speaking}
        for p in players
    ]})
    return {"updated": len(payload.players), "online": len(players), "nearby": visibility,
            "proximity_pairs": sum(len(value) for value in visibility.values()) // 2}


@app.post("/api/v1/players/leave")
async def player_leave(payload: PlayerLeaveIn, server: Server = Depends(server_auth), db: Session = Depends(get_db)):
    """Expire a BDS entity immediately instead of waiting for the presence timeout."""
    player = db.query(Player).filter(
        Player.server_id == server.id, Player.identity_key == payload.identity_key
    ).first()
    if player is None:
        return {"left": True, "known": False}
    player.online = False
    player.voice_connected = False
    player.speaking = False
    player.active_group_id = None
    db.query(GroupMember).filter(GroupMember.player_id == player.id).delete(synchronize_session=False)
    db.commit()
    try:
        await remove_media_participant(server, player.id)
    except Exception:
        import logging
        logging.getLogger("horizon_voice.media").exception("Could not disconnect media participant after BDS leave")
    schedule_media_sync(server.id)
    await hub.publish(server.id, {"type": "player_left", "player_id": player.id})
    return {"left": True, "known": True}


@app.post("/api/v1/players/self-mute")
async def server_self_mute(payload: ServerSelfMuteIn, server: Server = Depends(server_auth), db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.server_id == server.id, Player.identity_key == payload.identity_key).first()
    if player is None:
        raise HTTPException(status_code=404, detail="Jogador ainda não registrado no Horizon Voice")
    player.self_muted = payload.muted
    if payload.muted:
        player.speaking = False
    db.commit()
    try:
        await force_media_mute(server, player, player.self_muted or player.moderation_muted)
    except Exception:
        import logging
        logging.getLogger("horizon_voice.media").exception("Could not apply self-mute to LiveKit")
    schedule_media_sync(server.id)
    await hub.publish(server.id, {"type": "self_mute", "player_id": player.id, "muted": player.self_muted})
    return {"muted": player.self_muted or player.moderation_muted}


@app.get("/api/v1/players/voice-states")
def voice_states(server: Server = Depends(server_auth), db: Session = Depends(get_db)):
    players = db.query(Player).filter(Player.server_id == server.id, Player.online.is_(True)).all()
    return {"players": [{"identity": p.identity_key, "name": p.display_name,
             "connected": p.voice_connected,
             "muted": p.self_muted or p.moderation_muted, "speaking": p.speaking}
             for p in players]}


@app.post("/api/v1/voice/token")
async def voice_token(request: Request, browser: BrowserSession = Depends(require_browser), db: Session = Depends(get_db)):
    """Issue a short-lived, tenant-room token with client-side subscriptions denied."""
    enforce_rate_limit(f"voice-token:{browser.id}:{request_fingerprint(request)}", 12, 60)
    if not livekit_is_configured():
        raise HTTPException(status_code=503, detail="Servidor de voz indisponível. LiveKit não foi configurado.")
    if not browser.player_id:
        raise HTTPException(status_code=409, detail="Vincule seu jogador do Minecraft antes de entrar no áudio")
    player = db.get(Player, browser.player_id)
    server = db.get(Server, browser.server_id)
    if player is None or server is None or player.server_id != server.id:
        raise HTTPException(status_code=404, detail="Jogador ou servidor vinculado não encontrado")
    if not player.online or not server.voice_enabled:
        raise HTTPException(status_code=409, detail="O servidor ou o jogador não está disponível para voz")
    try:
        token = create_participant_token(player, server)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Não foi possível emitir o token de voz") from exc
    schedule_media_sync(server.id)
    return {
        "server_url": settings.livekit_public_url,
        "token": token,
        "room": room_name(server.id),
        "identity": player.id,
        "player_name": player.display_name,
        "muted": player.self_muted or player.moderation_muted,
        "deafened": player.deafened,
        "expires_in_minutes": max(5, min(settings.livekit_token_minutes, 120)),
        "subscription_mode": "server-authorized-proximity-and-groups",
    }


@app.post("/api/v1/voice/self-mute")
async def self_mute(payload: SelfMuteIn, browser: BrowserSession = Depends(require_browser), db: Session = Depends(get_db)):
    if not browser.player_id:
        raise HTTPException(status_code=409, detail="Jogador ainda não vinculado")
    player = db.get(Player, browser.player_id)
    if player is None or player.server_id != browser.server_id:
        raise HTTPException(status_code=404, detail="Jogador vinculado não encontrado")
    player.self_muted = payload.muted
    if payload.muted:
        player.speaking = False
    db.commit()
    server = db.get(Server, browser.server_id)
    if server is not None:
        try:
            await force_media_mute(server, player, player.self_muted or player.moderation_muted)
        except Exception:
            import logging
            logging.getLogger("horizon_voice.media").exception("Could not enforce browser mute in LiveKit")
        schedule_media_sync(server.id)
    await hub.publish(browser.server_id, {"type": "self_mute", "player_id": player.id, "muted": player.self_muted})
    return {"muted": player.self_muted or player.moderation_muted,
            "can_publish": not (player.self_muted or player.moderation_muted)}


@app.post("/api/v1/voice/moderation/{player_id}/mute")
async def moderation_mute(player_id: str, payload: SelfMuteIn, account: Account = Depends(require_account), db: Session = Depends(get_db)):
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Jogador não encontrado")
    server = db.get(Server, player.server_id)
    if server is None or server.owner_id != account.id:
        raise HTTPException(status_code=403, detail="Você não administra este servidor")
    player.moderation_muted = payload.muted
    if payload.muted:
        player.speaking = False
    db.commit()
    try:
        await force_media_mute(server, player, player.self_muted or player.moderation_muted)
    except Exception:
        import logging
        logging.getLogger("horizon_voice.media").exception("Could not enforce moderation mute in LiveKit")
    schedule_media_sync(server.id)
    await hub.publish(server.id, {"type": "moderation_mute", "player_id": player.id, "muted": payload.muted})
    return {"player_id": player.id, "muted": player.self_muted or player.moderation_muted}


@app.post("/api/v1/groups", status_code=201)
async def create_group(payload: GroupCreateIn, browser: BrowserSession = Depends(require_browser), db: Session = Depends(get_db)):
    if not browser.player_id:
        raise HTTPException(status_code=409, detail="Jogador ainda não vinculado")
    player = db.get(Player, browser.player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Jogador não encontrado")
    if payload.is_private and not payload.password:
        raise HTTPException(status_code=422, detail="Grupo privado exige senha")
    code = secrets.token_hex(4).upper()
    # One player can actively transmit in only one group at a time.
    db.query(GroupMember).filter(GroupMember.player_id == player.id).delete(synchronize_session=False)
    group = VoiceGroup(id=new_id(), server_id=browser.server_id, owner_player_id=player.id,
        name=payload.name.strip(), join_code=code, is_private=payload.is_private,
        password_hash=hash_password(payload.password) if payload.password else None, max_members=payload.max_members)
    db.add(group)
    db.add(GroupMember(id=new_id(), group_id=group.id, player_id=player.id))
    player.active_group_id = group.id
    db.commit()
    schedule_media_sync(browser.server_id)
    return {"id": group.id, "name": group.name, "code": group.join_code, "is_private": group.is_private,
            "room": f"hv-group-{group.id}"}


@app.post("/api/v1/groups/join")
async def join_group(payload: GroupJoinIn, request: Request, browser: BrowserSession = Depends(require_browser), db: Session = Depends(get_db)):
    enforce_rate_limit(f"group-join:{browser.id}:{request_fingerprint(request)}", 8, 60)
    if not browser.player_id:
        raise HTTPException(status_code=409, detail="Jogador ainda não vinculado")
    group = db.query(VoiceGroup).filter(
        VoiceGroup.server_id == browser.server_id, VoiceGroup.join_code == payload.code.upper()
    ).with_for_update().first()
    if group is None:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    if group.is_private:
        from .security import verify_password
        if not payload.password or not group.password_hash or not verify_password(payload.password, group.password_hash):
            raise HTTPException(status_code=403, detail="Senha do grupo incorreta")
    members = db.query(GroupMember).filter(GroupMember.group_id == group.id).count()
    existing = db.query(GroupMember).filter(GroupMember.group_id == group.id, GroupMember.player_id == browser.player_id).first()
    if not existing:
        if members >= group.max_members:
            raise HTTPException(status_code=409, detail="Grupo cheio")
        # Switch atomically to the selected group; old membership must not leak.
        db.query(GroupMember).filter(GroupMember.player_id == browser.player_id).delete(synchronize_session=False)
        db.add(GroupMember(id=new_id(), group_id=group.id, player_id=browser.player_id))
        player = db.get(Player, browser.player_id)
        player.active_group_id = group.id
        db.commit()
        schedule_media_sync(browser.server_id)
    else:
        player = db.get(Player, browser.player_id)
        player.active_group_id = group.id
        db.commit()
        schedule_media_sync(browser.server_id)
    return {"joined": True, "group_id": group.id, "room": room_name(browser.server_id)}


@app.post("/api/v1/groups/leave")
async def leave_group(browser: BrowserSession = Depends(require_browser), db: Session = Depends(get_db)):
    if not browser.player_id:
        raise HTTPException(status_code=409, detail="Jogador ainda não vinculado")
    player = db.get(Player, browser.player_id)
    db.query(GroupMember).filter(GroupMember.player_id == browser.player_id).delete(synchronize_session=False)
    if player is not None:
        player.active_group_id = None
    db.commit()
    schedule_media_sync(browser.server_id)
    return {"left": True, "mode": "proximity"}


@app.post("/api/v1/voice/refresh")
async def refresh_voice_subscriptions(request: Request, browser: BrowserSession = Depends(require_browser), db: Session = Depends(get_db)):
    if not browser.player_id:
        raise HTTPException(status_code=409, detail="Jogador ainda não vinculado")
    enforce_rate_limit(f"voice-refresh:{browser.id}:{request_fingerprint(request)}", 20, 60)
    schedule_media_sync(browser.server_id)
    return {"scheduled": True}


@app.post("/api/v1/voice/deafen")
async def set_deafen(payload: DeafenIn, browser: BrowserSession = Depends(require_browser), db: Session = Depends(get_db)):
    if not browser.player_id:
        raise HTTPException(status_code=409, detail="Jogador ainda não vinculado")
    player = db.get(Player, browser.player_id)
    if player is None or player.server_id != browser.server_id:
        raise HTTPException(status_code=404, detail="Jogador vinculado não encontrado")
    player.deafened = payload.deafened
    db.commit()
    schedule_media_sync(browser.server_id)
    await hub.publish(browser.server_id, {"type": "deafen", "player_id": player.id, "deafened": player.deafened})
    return {"deafened": player.deafened}


@app.post("/api/v1/voice/local-mute/{target_player_id}")
async def set_local_mute(target_player_id: str, payload: LocalMuteIn, browser: BrowserSession = Depends(require_browser), db: Session = Depends(get_db)):
    if not browser.player_id:
        raise HTTPException(status_code=409, detail="Jogador ainda não vinculado")
    if target_player_id == browser.player_id:
        raise HTTPException(status_code=422, detail="Não é possível silenciar a si mesmo nesta lista")
    target = db.get(Player, target_player_id)
    listener = db.get(Player, browser.player_id)
    if target is None or listener is None or target.server_id != browser.server_id or listener.server_id != browser.server_id:
        raise HTTPException(status_code=404, detail="Jogador não encontrado neste servidor")
    existing = db.query(LocalMute).filter(
        LocalMute.listener_player_id == listener.id, LocalMute.muted_player_id == target.id
    ).first()
    if payload.muted and existing is None:
        db.add(LocalMute(id=new_id(), listener_player_id=listener.id, muted_player_id=target.id))
    elif not payload.muted and existing is not None:
        db.delete(existing)
    db.commit()
    schedule_media_sync(browser.server_id)
    return {"player_id": target.id, "muted_locally": payload.muted}


@app.post("/api/v1/voice/speaking")
async def update_speaking(payload: SpeakingIn, browser: BrowserSession = Depends(require_browser), db: Session = Depends(get_db)):
    if not browser.player_id:
        raise HTTPException(status_code=409, detail="Jogador ainda não vinculado")
    player = db.get(Player, browser.player_id)
    if player is None or player.server_id != browser.server_id:
        raise HTTPException(status_code=404, detail="Jogador vinculado não encontrado")
    # This flag is presentation only; voice authorization never trusts it.
    player.speaking = bool(payload.speaking and not player.self_muted and not player.moderation_muted)
    db.commit()
    await hub.publish(browser.server_id, {"type": "speaking", "player_id": player.id, "speaking": player.speaking})
    return {"speaking": player.speaking}


@app.get("/api/v1/voice/nearby")
def nearby_players(browser: BrowserSession = Depends(require_browser), db: Session = Depends(get_db)):
    if not browser.player_id:
        raise HTTPException(status_code=409, detail="Jogador ainda não vinculado")
    listener = db.get(Player, browser.player_id)
    server = db.get(Server, browser.server_id)
    if listener is None or server is None or listener.server_id != server.id:
        raise HTTPException(status_code=404, detail="Jogador vinculado não encontrado")
    players = db.query(Player).filter(Player.server_id == server.id, Player.online.is_(True)).all()
    my_groups = {row[0] for row in db.query(GroupMember.group_id).filter(GroupMember.player_id == listener.id).all()}
    my_mutes = {row[0] for row in db.query(LocalMute.muted_player_id).filter(LocalMute.listener_player_id == listener.id).all()}
    rows = []
    for player in players:
        if player.id == listener.id:
            continue
        their_groups = {row[0] for row in db.query(GroupMember.group_id).filter(GroupMember.player_id == player.id).all()}
        in_group = bool(listener.active_group_id and listener.active_group_id == player.active_group_id
                        and listener.active_group_id in my_groups and listener.active_group_id in their_groups)
        distance = None
        same_dimension = listener.dimension == player.dimension
        if same_dimension:
            distance = math.sqrt((listener.x-player.x)**2 + (listener.y-player.y)**2 + (listener.z-player.z)**2)
        in_range = bool(same_dimension and distance is not None and distance <= server.max_distance)
        proximity_allowed = not listener.active_group_id and not player.active_group_id and in_range
        authorized = bool((proximity_allowed or in_group) and player.id not in my_mutes
                          and not (player.self_muted or player.moderation_muted) and not listener.deafened)
        rows.append({
            "id": player.id, "name": player.display_name,
            "connected": player.voice_connected,
            "speaking": player.speaking,
            "muted": player.self_muted or player.moderation_muted,
            "locally_muted": player.id in my_mutes,
            "distance": round(distance, 1) if distance is not None else None,
            "same_dimension": same_dimension,
            "in_group": in_group,
            "can_hear": authorized,
        })
    rows.sort(key=lambda item: (not item["can_hear"], item["distance"] is None, item["distance"] or 0, item["name"].lower()))
    return {"players": rows, "deafened": listener.deafened, "max_distance": server.max_distance,
            "active_group_id": listener.active_group_id, "voice_enabled": server.voice_enabled}


@app.get("/api/v1/groups")
def list_groups(browser: BrowserSession = Depends(require_browser), db: Session = Depends(get_db)):
    if not browser.player_id:
        raise HTTPException(status_code=409, detail="Jogador ainda não vinculado")
    player = db.get(Player, browser.player_id)
    if player is None or player.server_id != browser.server_id:
        raise HTTPException(status_code=404, detail="Jogador vinculado não encontrado")
    groups = db.query(VoiceGroup).filter(
        VoiceGroup.server_id == browser.server_id,
        (VoiceGroup.is_private.is_(False) | (VoiceGroup.id == player.active_group_id)),
    ).order_by(VoiceGroup.created_at.desc()).all()
    memberships = {row[0] for row in db.query(GroupMember.group_id).filter(GroupMember.player_id == browser.player_id).all()}
    return {"groups": [{
        "id": group.id, "name": group.name, "code": group.join_code,
        "members": db.query(GroupMember).filter(GroupMember.group_id == group.id).count(),
        "max_members": group.max_members, "is_private": group.is_private,
        "joined": group.id in memberships, "active": group.id == player.active_group_id,
        "is_owner": group.owner_player_id == player.id,
    } for group in groups]}


@app.delete("/api/v1/groups/{group_id}")
async def delete_owned_group(group_id: str, browser: BrowserSession = Depends(require_browser), db: Session = Depends(get_db)):
    if not browser.player_id:
        raise HTTPException(status_code=409, detail="Jogador ainda não vinculado")
    group = db.get(VoiceGroup, group_id)
    if group is None or group.server_id != browser.server_id:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    if group.owner_player_id != browser.player_id:
        raise HTTPException(status_code=403, detail="Somente o criador pode excluir este grupo")
    members = db.query(GroupMember).filter(GroupMember.group_id == group.id).all()
    member_ids = [member.player_id for member in members]
    if member_ids:
        db.query(Player).filter(Player.id.in_(member_ids)).update(
            {Player.active_group_id: None}, synchronize_session=False
        )
    db.query(GroupMember).filter(GroupMember.group_id == group.id).delete(synchronize_session=False)
    db.delete(group)
    db.commit()
    schedule_media_sync(browser.server_id)
    return {"deleted": True, "mode": "proximity"}


@app.get("/api/v1/players/groups")
def list_server_groups(identity_key: str, server: Server = Depends(server_auth), db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.server_id == server.id, Player.identity_key == identity_key).first()
    if player is None or not player.online:
        raise HTTPException(status_code=404, detail="Jogador não está online")
    groups = db.query(VoiceGroup).filter(
        VoiceGroup.server_id == server.id,
        (VoiceGroup.is_private.is_(False) | (VoiceGroup.id == player.active_group_id)),
    ).order_by(VoiceGroup.created_at.desc()).all()
    return {"active_group_id": player.active_group_id, "groups": [{
        "id": group.id, "name": group.name, "code": group.join_code,
        "members": db.query(GroupMember).filter(GroupMember.group_id == group.id).count(),
        "max_members": group.max_members, "is_private": group.is_private,
        "active": group.id == player.active_group_id,
    } for group in groups]}


@app.post("/api/v1/players/groups/create", status_code=201)
async def create_server_group(payload: ServerGroupCreateIn, server: Server = Depends(server_auth), db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.server_id == server.id, Player.identity_key == payload.identity_key).first()
    if player is None or not player.online:
        raise HTTPException(status_code=404, detail="Jogador não está online")
    if payload.is_private and not payload.password:
        raise HTTPException(status_code=422, detail="Grupo privado exige senha")
    code = secrets.token_hex(4).upper()
    db.query(GroupMember).filter(GroupMember.player_id == player.id).delete(synchronize_session=False)
    group = VoiceGroup(
        id=new_id(), server_id=server.id, owner_player_id=player.id, name=payload.name.strip(),
        join_code=code, is_private=payload.is_private,
        password_hash=hash_password(payload.password) if payload.password else None,
        max_members=payload.max_members,
    )
    db.add(group)
    db.add(GroupMember(id=new_id(), group_id=group.id, player_id=player.id))
    player.active_group_id = group.id
    db.commit()
    schedule_media_sync(server.id)
    return {"id": group.id, "name": group.name, "code": group.join_code, "is_private": group.is_private}


@app.post("/api/v1/players/groups/join")
async def join_server_group(payload: ServerGroupJoinIn, server: Server = Depends(server_auth), db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.server_id == server.id, Player.identity_key == payload.identity_key).first()
    if player is None or not player.online:
        raise HTTPException(status_code=404, detail="Jogador não está online")
    group = db.query(VoiceGroup).filter(
        VoiceGroup.server_id == server.id, VoiceGroup.join_code == payload.code.upper()
    ).with_for_update().first()
    if group is None:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    if group.is_private and (not payload.password or not group.password_hash or not verify_password(payload.password, group.password_hash)):
        raise HTTPException(status_code=403, detail="Senha do grupo incorreta")
    already_member = db.query(GroupMember).filter(
        GroupMember.group_id == group.id, GroupMember.player_id == player.id
    ).first()
    member_count = db.query(GroupMember).filter(GroupMember.group_id == group.id).count()
    if not already_member and member_count >= group.max_members:
        raise HTTPException(status_code=409, detail="Grupo cheio")
    if not already_member:
        db.query(GroupMember).filter(GroupMember.player_id == player.id).delete(synchronize_session=False)
        db.add(GroupMember(id=new_id(), group_id=group.id, player_id=player.id))
    player.active_group_id = group.id
    db.commit()
    schedule_media_sync(server.id)
    return {"joined": True, "group_id": group.id, "name": group.name, "code": group.join_code}


@app.post("/api/v1/players/groups/leave")
async def leave_server_group(payload: ServerGroupLeaveIn, server: Server = Depends(server_auth), db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.server_id == server.id, Player.identity_key == payload.identity_key).first()
    if player is None or not player.online:
        raise HTTPException(status_code=404, detail="Jogador não está online")
    db.query(GroupMember).filter(GroupMember.player_id == player.id).delete(synchronize_session=False)
    player.active_group_id = None
    db.commit()
    schedule_media_sync(server.id)
    return {"left": True, "mode": "proximity"}


@app.get("/api/v1/dashboard/servers")
def list_servers(account: Account = Depends(require_account), db: Session = Depends(get_db)):
    servers = db.query(Server).filter(Server.owner_id == account.id).order_by(Server.created_at.desc()).all()
    return {"servers": [{"id": s.id, "name": s.name, "slug": s.slug, "status": s.status,
             "subdomain": f"https://{s.slug}.{settings.public_base_domain}"} for s in servers]}


@app.get("/api/v1/dashboard/servers/{server_id}")
def server_dashboard(server_id: str, account: Account = Depends(require_account), db: Session = Depends(get_db)):
    server = db.get(Server, server_id)
    if server is None or server.owner_id != account.id:
        raise HTTPException(status_code=404, detail="Servidor não encontrado")
    online = db.query(Player).filter(Player.server_id == server.id, Player.online.is_(True)).all()
    connected = sum(1 for player in online if player.voice_connected)
    return {"server": {"id": server.id, "name": server.name, "slug": server.slug, "status": server.status,
                        "max_distance": server.max_distance, "voice_enabled": server.voice_enabled},
            "metrics": {"minecraft_online": len(online), "voice_connected": connected,
                        "speaking": sum(1 for p in online if p.speaking),
                        "moderation_muted": sum(1 for p in online if p.moderation_muted)}}


@app.patch("/api/v1/dashboard/servers/{server_id}/settings")
async def update_server_settings(server_id: str, payload: DashboardSettingsIn, account: Account = Depends(require_account), db: Session = Depends(get_db)):
    server = db.get(Server, server_id)
    if server is None or server.owner_id != account.id:
        raise HTTPException(status_code=404, detail="Servidor não encontrado")
    server.max_distance = payload.max_distance
    server.voice_enabled = payload.voice_enabled
    db.commit()
    schedule_media_sync(server.id)
    return {"saved": True, "max_distance": server.max_distance, "voice_enabled": server.voice_enabled}


@app.post("/api/v1/livekit/webhook")
async def livekit_webhook(request: Request, db: Session = Depends(get_db)):
    """Verify the raw LiveKit webhook signature before changing media presence."""
    if not livekit_is_configured():
        raise HTTPException(status_code=503, detail="LiveKit não configurado")
    authorization = request.headers.get("Authorization", "")
    if not authorization:
        raise HTTPException(status_code=401, detail="Assinatura LiveKit ausente")
    raw_body = (await request.body()).decode("utf-8")
    try:
        from livekit import api  # type: ignore[import-not-found]
        receiver = api.WebhookReceiver(api.TokenVerifier(settings.livekit_api_key, settings.livekit_api_secret))
        event = receiver.receive(raw_body, authorization)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Webhook LiveKit inválido") from exc

    room_value = getattr(getattr(event, "room", None), "name", "") or ""
    if not room_value.startswith("horizon-"):
        return {"ignored": True}
    try:
        server_id = str(uuid.UUID(hex=room_value.removeprefix("horizon-")))
    except ValueError:
        return {"ignored": True}
    server = db.get(Server, server_id)
    if server is None:
        return {"ignored": True}
    participant = getattr(event, "participant", None)
    identity = str(getattr(participant, "identity", "") or "")
    if not identity:
        return {"ignored": True}
    player = db.get(Player, identity)
    if player is None or player.server_id != server.id:
        return {"ignored": True}

    event_type = str(getattr(event, "event", ""))
    if event_type == "participant_joined":
        player.voice_connected = True
    elif event_type in {"participant_left", "participant_connection_aborted"}:
        player.voice_connected = False
        player.speaking = False
    elif event_type in {"track_published", "track_unpublished", "track_muted", "track_unmuted"}:
        # Track changes can alter the subscription set, but never grant access here.
        pass
    else:
        return {"ignored": True}
    db.commit()
    schedule_media_sync(server.id)
    await hub.publish(server.id, {"type": "media_presence", "player_id": player.id,
                                  "connected": player.voice_connected, "event": event_type})
    return {"received": True, "event": event_type}


@app.websocket("/api/v1/voice/events")
async def voice_events(socket: WebSocket):
    token = socket.cookies.get("hv_session")
    db = SessionLocal()
    try:
        browser = None
        if token:
            from .models import BrowserSession
            browser = db.query(BrowserSession).filter(BrowserSession.token_hash == hash_value(token)).first()
        if browser is None or browser.revoked_at is not None or ensure_aware(browser.expires_at) <= now_utc():
            await socket.close(code=1008)
            return
        await hub.connect(browser.server_id, socket)
        await socket.send_json({"type": "ready"})
        while True:
            try:
                # Browser input is only a keepalive; it is never trusted as position/state authority.
                await asyncio.wait_for(socket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                try:
                    db.refresh(browser)
                except Exception:
                    await socket.close(code=1008)
                    break
                if browser.revoked_at is not None or ensure_aware(browser.expires_at) <= now_utc():
                    await socket.close(code=1008)
                    break
                await socket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        pass
    finally:
        if browser is not None:
            hub.disconnect(browser.server_id, socket)
        db.close()
