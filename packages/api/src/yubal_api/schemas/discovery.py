"""Discovery request/response schemas."""

from uuid import UUID

from pydantic import BaseModel, Field

from yubal_api.db.discovery import SuggestionStatus
from yubal_api.schemas.types import UTCDateTime


class LastFmSettingsResponse(BaseModel):
    """Last.fm settings response."""

    username: str
    enabled: bool
    auto_download: bool
    confidence_threshold: int
    schedule_cron: str

    model_config = {"from_attributes": True}


class LastFmSettingsUpdate(BaseModel):
    """Request to update Last.fm settings."""

    username: str | None = None
    api_key: str | None = None
    enabled: bool | None = None
    auto_download: bool | None = None
    confidence_threshold: int | None = Field(default=None, ge=0, le=100)
    schedule_cron: str | None = None


class LastFmConnectRequest(BaseModel):
    """Request to connect a Last.fm account."""

    username: str
    api_key: str


class DiscoverySuggestionResponse(BaseModel):
    """Discovery suggestion response."""

    id: UUID
    lastfm_artist: str
    lastfm_track: str
    matched_video_id: str | None
    matched_title: str | None
    matched_artist: str | None
    confidence: float
    artist_similarity: float
    title_similarity: float
    status: SuggestionStatus
    created_at: UTCDateTime
    job_id: str | None

    model_config = {"from_attributes": True}


class DiscoverySuggestionListResponse(BaseModel):
    """List of discovery suggestions."""

    items: list[DiscoverySuggestionResponse]


class DiscoverySuggestionAction(BaseModel):
    """Action to take on a suggestion."""

    suggestion_id: UUID


class BulkApproveRequest(BaseModel):
    """Request to bulk-approve suggestions."""

    suggestion_ids: list[UUID] | None = None


class DiscoveryScanResponse(BaseModel):
    """Response from a discovery scan."""

    new_suggestions: int
    total_pending: int


class DiscoveryStatsResponse(BaseModel):
    """Discovery statistics."""

    pending: int
    approved: int
    rejected: int
    downloaded: int
