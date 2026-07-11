"""Discovery endpoints for Last.fm-powered music discovery."""

from uuid import UUID

from fastapi import APIRouter, status

from yubal_api.api.deps import DiscoveryServiceDep
from yubal_api.db.discovery import SuggestionStatus
from yubal_api.schemas.discovery import (
    BulkApproveRequest,
    DiscoverPlaylistResponse,
    DiscoveryScanResponse,
    DiscoveryStatsResponse,
    DiscoverySuggestionListResponse,
    DiscoverySuggestionResponse,
    LastFmConnectRequest,
    LastFmSettingsResponse,
    LastFmSettingsUpdate,
)

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get("/settings", response_model=LastFmSettingsResponse | None)
def get_discovery_settings(
    service: DiscoveryServiceDep,
) -> LastFmSettingsResponse | None:
    """Get Last.fm discovery settings."""
    settings = service.get_settings()
    if settings is None:
        return None
    return LastFmSettingsResponse.model_validate(settings)


@router.put("/settings", response_model=LastFmSettingsResponse)
def update_discovery_settings(
    data: LastFmSettingsUpdate,
    service: DiscoveryServiceDep,
) -> LastFmSettingsResponse:
    """Update Last.fm discovery settings."""
    settings = service.update_settings(data.model_dump(exclude_unset=True))
    return LastFmSettingsResponse.model_validate(settings)


@router.post("/connect", response_model=LastFmSettingsResponse)
def connect_lastfm(
    data: LastFmConnectRequest,
    service: DiscoveryServiceDep,
) -> LastFmSettingsResponse:
    """Connect a Last.fm account."""
    settings = service.connect(data.username, data.api_key)
    return LastFmSettingsResponse.model_validate(settings)


@router.post("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_lastfm(
    service: DiscoveryServiceDep,
) -> None:
    """Disconnect Last.fm and clear suggestions."""
    service.disconnect()


@router.post("/scan", response_model=DiscoveryScanResponse)
async def run_discovery_scan(
    service: DiscoveryServiceDep,
) -> DiscoveryScanResponse:
    """Run a discovery scan."""
    new_count = service.run_scan()
    stats = service.get_stats()
    return DiscoveryScanResponse(
        new_suggestions=new_count,
        total_pending=stats["pending"],
    )


@router.get("/suggestions", response_model=DiscoverySuggestionListResponse)
def list_suggestions(
    service: DiscoveryServiceDep,
    status: SuggestionStatus | None = None,
) -> DiscoverySuggestionListResponse:
    """List discovery suggestions."""
    items = service.get_suggestions(status=status)
    return DiscoverySuggestionListResponse(
        items=[DiscoverySuggestionResponse.model_validate(s) for s in items]
    )


@router.get("/stats", response_model=DiscoveryStatsResponse)
def get_discovery_stats(
    service: DiscoveryServiceDep,
) -> DiscoveryStatsResponse:
    """Get discovery statistics."""
    return DiscoveryStatsResponse(**service.get_stats())


RESPONSE_MODEL = DiscoverySuggestionResponse


@router.post("/suggestions/{suggestion_id}/approve", response_model=RESPONSE_MODEL)
def approve_suggestion(
    suggestion_id: UUID,
    service: DiscoveryServiceDep,
) -> DiscoverySuggestionResponse:
    """Approve a suggestion and enqueue download."""
    suggestion = service.approve_suggestion(suggestion_id)
    if suggestion is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Suggestion not found")
    return DiscoverySuggestionResponse.model_validate(suggestion)


@router.post("/suggestions/{suggestion_id}/reject", response_model=RESPONSE_MODEL)
def reject_suggestion(
    suggestion_id: UUID,
    service: DiscoveryServiceDep,
) -> DiscoverySuggestionResponse:
    """Reject a suggestion."""
    suggestion = service.reject_suggestion(suggestion_id)
    if suggestion is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Suggestion not found")
    return DiscoverySuggestionResponse.model_validate(suggestion)


@router.post("/suggestions/bulk-approve", response_model=dict)
def bulk_approve_suggestions(
    data: BulkApproveRequest,
    service: DiscoveryServiceDep,
) -> dict:
    """Bulk approve suggestions."""
    count = service.bulk_approve(data.suggestion_ids)
    return {"approved": count}


@router.post("/suggestions/clear", response_model=dict)
def clear_suggestions(
    service: DiscoveryServiceDep,
) -> dict:
    """Delete all discovery suggestions."""
    count = service.clear_suggestions()
    return {"cleared": count}


@router.post("/playlists/similar-tracks", response_model=DiscoveryScanResponse)
def generate_similar_tracks_playlist(
    service: DiscoveryServiceDep,
    top_tracks_limit: int = 10,
    similar_tracks_per_track: int = 3,
) -> DiscoveryScanResponse:
    """Generate a similar-tracks playlist (Discover Weekly-style)."""
    new_count = service.generate_similar_tracks_playlist(
        top_tracks_limit=top_tracks_limit,
        similar_tracks_per_track=similar_tracks_per_track,
    )
    stats = service.get_stats()
    return DiscoveryScanResponse(
        new_suggestions=new_count,
        total_pending=stats["pending"],
    )


@router.post("/playlists/discover", response_model=DiscoverPlaylistResponse)
async def create_discover_playlist(
    service: DiscoveryServiceDep,
) -> DiscoverPlaylistResponse:
    """Approve all pending and create a Discover playlist M3U."""
    result = await service.create_discover_playlist()
    return DiscoverPlaylistResponse(**result)
