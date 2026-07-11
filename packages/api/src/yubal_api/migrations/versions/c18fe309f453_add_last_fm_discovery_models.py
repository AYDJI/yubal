"""Add Last.fm discovery models

Revision ID: c18fe309f453
Revises: 03132d5514f9
Create Date: 2026-07-11 10:47:56.288586

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c18fe309f453"
down_revision: str | Sequence[str] | None = "03132d5514f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "discovery_suggestions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lastfm_artist", sa.String(500), nullable=False),
        sa.Column("lastfm_track", sa.String(500), nullable=False),
        sa.Column("matched_video_id", sa.String(100), nullable=True),
        sa.Column("matched_title", sa.String(500), nullable=True),
        sa.Column("matched_artist", sa.String(500), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("artist_similarity", sa.Float(), nullable=False),
        sa.Column("title_similarity", sa.Float(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "APPROVED",
                "REJECTED",
                "DOWNLOADED",
                name="suggestionstatus",
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("job_id", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_discovery_suggestions_status"),
        "discovery_suggestions",
        ["status"],
        unique=False,
    )
    op.create_table(
        "lastfm_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(200), nullable=False),
        sa.Column("api_key", sa.String(200), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("auto_download", sa.Boolean(), nullable=False),
        sa.Column("confidence_threshold", sa.Integer(), nullable=False),
        sa.Column("schedule_cron", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("lastfm_settings")
    op.drop_index(
        op.f("ix_discovery_suggestions_status"),
        table_name="discovery_suggestions",
    )
    op.drop_table("discovery_suggestions")
