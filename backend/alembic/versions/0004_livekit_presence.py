"""Track actual LiveKit participant presence from signed webhooks.

Revision ID: 0004_livekit_presence
Revises: 0003_exclusive_group_mode
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0004_livekit_presence"
down_revision = "0003_exclusive_group_mode"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if "players" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("players")}
        if "voice_connected" not in columns:
            op.add_column("players", sa.Column("voice_connected", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if "players" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("players")}
        if "voice_connected" in columns:
            op.drop_column("players", "voice_connected")
