"""Persist cover-image metadata for each public server portal.

Revision ID: 0005_server_images
Revises: 0004_livekit_presence
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_server_images"
down_revision = "0004_livekit_presence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("servers", sa.Column("image_filename", sa.String(length=160), nullable=True))
    op.add_column("servers", sa.Column("image_content_type", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("servers", "image_content_type")
    op.drop_column("servers", "image_filename")
