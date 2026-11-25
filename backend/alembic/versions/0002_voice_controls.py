"""Add per-listener audio controls and deafen state.

Revision ID: 0002_voice_controls
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002_voice_controls"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if "players" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("players")}
        if "deafened" not in columns:
            op.add_column("players", sa.Column("deafened", sa.Boolean(), nullable=False, server_default=sa.false()))
    inspector = inspect(bind)
    if "local_mutes" not in inspector.get_table_names():
        op.create_table(
            "local_mutes",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("listener_player_id", sa.String(length=36), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
            sa.Column("muted_player_id", sa.String(length=36), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("listener_player_id", "muted_player_id", name="uq_local_mute_pair"),
        )
        op.create_index("ix_local_mutes_listener_player_id", "local_mutes", ["listener_player_id"])
        op.create_index("ix_local_mutes_muted_player_id", "local_mutes", ["muted_player_id"])


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if "local_mutes" in inspector.get_table_names():
        op.drop_index("ix_local_mutes_muted_player_id", table_name="local_mutes")
        op.drop_index("ix_local_mutes_listener_player_id", table_name="local_mutes")
        op.drop_table("local_mutes")
    inspector = inspect(bind)
    if "players" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("players")}
        if "deafened" in columns:
            op.drop_column("players", "deafened")
