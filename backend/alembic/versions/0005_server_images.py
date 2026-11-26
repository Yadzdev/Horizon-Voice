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
    # The initial migration builds tables from current ORM metadata. On a
    # fresh install these nullable fields may already exist; existing 0004
    # installations still need the ALTER TABLE operations below.
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("servers")}
    if "image_filename" not in columns:
        op.add_column("servers", sa.Column("image_filename", sa.String(length=160), nullable=True))
    if "image_content_type" not in columns:
        op.add_column("servers", sa.Column("image_content_type", sa.String(length=32), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("servers")}
    if "image_content_type" in columns:
        op.drop_column("servers", "image_content_type")
    if "image_filename" in columns:
        op.drop_column("servers", "image_filename")
