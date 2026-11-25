"""Add exclusive voice mode selection for group conversations.

Revision ID: 0003_exclusive_group_mode
Revises: 0002_voice_controls
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003_exclusive_group_mode"
down_revision = "0002_voice_controls"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if "players" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("players")}
        if "active_group_id" not in columns:
            op.add_column("players", sa.Column("active_group_id", sa.String(length=36), nullable=True))
            op.create_index("ix_players_active_group_id", "players", ["active_group_id"])


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if "players" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("players")}
        if "active_group_id" in columns:
            indexes = {index["name"] for index in inspector.get_indexes("players")}
            if "ix_players_active_group_id" in indexes:
                op.drop_index("ix_players_active_group_id", table_name="players")
            op.drop_column("players", "active_group_id")
