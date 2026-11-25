from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    servers: Mapped[list[Server]] = relationship(back_populates="owner")


class Server(Base):
    __tablename__ = "servers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(240), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    server_secret_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    max_distance: Mapped[float] = mapped_column(Float, default=30.0)
    voice_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    owner: Mapped[Account] = relationship(back_populates="servers")


class ActivationCode(Base):
    __tablename__ = "activation_codes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    server_id: Mapped[str] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("server_id", "identity_key", name="uq_player_server_identity"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    server_id: Mapped[str] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    identity_key: Mapped[str] = mapped_column(String(100))  # BDS Entity.id; session identity, not a claimed XUID
    display_name: Mapped[str] = mapped_column(String(64))
    dimension: Mapped[str] = mapped_column(String(80), default="minecraft:overworld")
    x: Mapped[float] = mapped_column(Float, default=0)
    y: Mapped[float] = mapped_column(Float, default=0)
    z: Mapped[float] = mapped_column(Float, default=0)
    online: Mapped[bool] = mapped_column(Boolean, default=True)
    self_muted: Mapped[bool] = mapped_column(Boolean, default=False)
    moderation_muted: Mapped[bool] = mapped_column(Boolean, default=False)
    deafened: Mapped[bool] = mapped_column(Boolean, default=False)
    # Current voice mode: NULL means proximity; otherwise the selected group ID.
    active_group_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    speaking: Mapped[bool] = mapped_column(Boolean, default=False)
    voice_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class BrowserSession(Base):
    __tablename__ = "browser_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    server_id: Mapped[str] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    player_id: Mapped[str | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PairingCode(Base):
    __tablename__ = "pairing_codes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    server_id: Mapped[str] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    browser_session_id: Mapped[str] = mapped_column(ForeignKey("browser_sessions.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VoiceGroup(Base):
    __tablename__ = "voice_groups"
    __table_args__ = (UniqueConstraint("server_id", "join_code", name="uq_group_server_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    server_id: Mapped[str] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    owner_player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(48))
    join_code: Mapped[str] = mapped_column(String(12))
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_members: Mapped[int] = mapped_column(Integer, default=8)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "player_id", name="uq_group_member"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("voice_groups.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


Index("ix_players_server_online_dimension", Player.server_id, Player.online, Player.dimension)


class LocalMute(Base):
    __tablename__ = "local_mutes"
    __table_args__ = (UniqueConstraint("listener_player_id", "muted_player_id", name="uq_local_mute_pair"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    listener_player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    muted_player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
