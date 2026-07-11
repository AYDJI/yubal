"""Database models for Last.fm discovery."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import TypedDict
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class SuggestionStatus(StrEnum):
    """Status of a discovery suggestion."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DOWNLOADED = "downloaded"


class SuggestionFields(TypedDict, total=False):
    """Partial update fields for a discovery suggestion."""

    status: SuggestionStatus
    job_id: str | None


class LastFmSettings(SQLModel, table=True):
    """Last.fm connection settings and discovery configuration."""

    __tablename__ = "lastfm_settings"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    username: str = Field(max_length=200)
    api_key: str = Field(max_length=200)
    enabled: bool = Field(default=False)
    auto_download: bool = Field(default=False)
    confidence_threshold: int = Field(default=80, ge=0, le=100)
    schedule_cron: str = Field(default="0 0 * * 0", max_length=100)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DiscoverySuggestion(SQLModel, table=True):
    """A track suggestion from Last.fm-based discovery."""

    __tablename__ = "discovery_suggestions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    lastfm_artist: str = Field(max_length=500)
    lastfm_track: str = Field(max_length=500)
    matched_video_id: str | None = Field(default=None, max_length=100)
    matched_title: str | None = Field(default=None, max_length=500)
    matched_artist: str | None = Field(default=None, max_length=500)
    confidence: float = Field(default=0.0)
    artist_similarity: float = Field(default=0.0)
    title_similarity: float = Field(default=0.0)
    status: SuggestionStatus = Field(default=SuggestionStatus.PENDING, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    job_id: str | None = Field(default=None, max_length=100)
