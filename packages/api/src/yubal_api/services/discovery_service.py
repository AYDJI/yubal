"""Discovery business logic service.

Coordinates Last.fm -> YT Music discovery with the database layer.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from yubal.client import YTMusicClient, YTMusicProtocol
from yubal.lastfm import LastFmClient
from yubal.lib.m3u import generate_m3u
from yubal.models.track import TrackMetadata
from yubal.services.discovery import DiscoveryService as CoreDiscoveryService

from yubal_api.db.discovery import (
    DiscoverySuggestion,
    LastFmSettings,
    SuggestionStatus,
)
from yubal_api.db.discovery_repository import (
    DiscoverySuggestionRepository,
    LastFmSettingsRepository,
)
from yubal_api.services.job_executor import JobExecutor

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".opus", ".mp3", ".m4a", ".flac", ".ogg", ".wav"}
DISCOVER_PLAYLIST_NAME = "Discover"
DISCOVER_PLAYLIST_ID = "lastfm"


class DiscoveryService:
    """API-level service for Last.fm discovery orchestration."""

    def __init__(
        self,
        settings_repo: LastFmSettingsRepository,
        suggestions_repo: DiscoverySuggestionRepository,
        job_executor: JobExecutor,
        base_path: Path | None = None,
        ytmusic: YTMusicProtocol | None = None,
        lastfm_api_key: str | None = None,
        cookies_path: str | None = None,
        core_discovery: CoreDiscoveryService | None = None,
    ) -> None:
        self._settings_repo = settings_repo
        self._suggestions_repo = suggestions_repo
        self._job_executor = job_executor
        self._base_path = base_path
        self._ytmusic = ytmusic
        self._lastfm_api_key = lastfm_api_key
        self._cookies_path = cookies_path
        self._core_discovery = core_discovery

    def get_settings(self) -> LastFmSettings | None:
        """Get Last.fm settings."""
        return self._settings_repo.get()

    def update_settings(self, fields: dict) -> LastFmSettings:
        """Create or update Last.fm settings."""
        existing = self._settings_repo.get()
        if existing:
            for key, value in fields.items():
                if value is not None:
                    setattr(existing, key, value)
            existing.updated_at = datetime.now(UTC)
            return self._settings_repo.upsert(existing)
        settings = LastFmSettings(**{k: v for k, v in fields.items() if v is not None})
        return self._settings_repo.upsert(settings)

    def connect(self, username: str, api_key: str) -> LastFmSettings:
        """Connect a Last.fm account."""
        existing = self._settings_repo.get()
        if existing:
            existing.username = username
            existing.api_key = api_key
            existing.updated_at = datetime.now(UTC)
            return self._settings_repo.upsert(existing)
        settings = LastFmSettings(
            username=username,
            api_key=api_key,
        )
        return self._settings_repo.upsert(settings)

    def disconnect(self) -> bool:
        """Remove Last.fm connection and clear suggestions."""
        self._suggestions_repo.clear()
        return self._settings_repo.delete()

    def get_suggestions(
        self, status: SuggestionStatus | None = None
    ) -> list[DiscoverySuggestion]:
        """List discovery suggestions."""
        return self._suggestions_repo.list_suggestions(status=status)

    def get_stats(self) -> dict[str, int]:
        """Get suggestion counts by status."""
        return {
            "pending": self._suggestions_repo.count(status=SuggestionStatus.PENDING),
            "approved": self._suggestions_repo.count(status=SuggestionStatus.APPROVED),
            "rejected": self._suggestions_repo.count(status=SuggestionStatus.REJECTED),
            "downloaded": self._suggestions_repo.count(
                status=SuggestionStatus.DOWNLOADED
            ),
        }

    def run_scan(self) -> int:
        """Run a discovery scan. Returns number of new suggestions."""
        settings = self._settings_repo.get()
        if not settings or not settings.enabled:
            logger.warning("Discovery scan requested but Last.fm is not configured")
            return 0

        if self._core_discovery is not None:
            core = self._core_discovery
        else:
            api_key = self._lastfm_api_key or settings.api_key
            lastfm = LastFmClient(api_key=api_key)
            ytmusic = self._ytmusic or YTMusicClient(
                cookies_path=Path(self._cookies_path) if self._cookies_path else None
            )
            core = CoreDiscoveryService(lastfm=lastfm, ytmusic=ytmusic)

        suggestions = core.get_recommendations(
            username=settings.username,
            min_confidence=settings.confidence_threshold,
        )

        if not suggestions:
            logger.info("Discovery scan returned no suggestions")
            return 0

        existing = {
            (s.lastfm_artist.lower(), s.lastfm_track.lower())
            for s in self._suggestions_repo.list_suggestions()
        }

        new_suggestions = []
        for s in suggestions:
            key = (s.lastfm_artist.lower(), s.lastfm_track.lower())
            if key in existing:
                continue
            new_suggestions.append(
                DiscoverySuggestion(
                    id=uuid4(),
                    lastfm_artist=s.lastfm_artist,
                    lastfm_track=s.lastfm_track,
                    matched_video_id=s.matched_video_id,
                    matched_title=s.matched_title,
                    matched_artist=s.matched_artist,
                    confidence=s.confidence,
                    artist_similarity=s.artist_similarity,
                    title_similarity=s.title_similarity,
                    status=SuggestionStatus.PENDING,
                    created_at=datetime.now(UTC),
                )
            )

        if new_suggestions:
            self._suggestions_repo.bulk_create(new_suggestions)

        logger.info(
            "Discovery scan added %d new suggestions (from %d candidates)",
            len(new_suggestions),
            len(suggestions),
        )
        return len(new_suggestions)

    def approve_suggestion(self, suggestion_id: UUID) -> DiscoverySuggestion | None:
        """Approve a suggestion and enqueue a download job."""
        suggestion = self._suggestions_repo.get(suggestion_id)
        if suggestion is None:
            return None

        if not suggestion.matched_video_id:
            suggestion.status = SuggestionStatus.REJECTED
            self._suggestions_repo.update(
                suggestion_id, {"status": SuggestionStatus.REJECTED}
            )
            return suggestion

        video_url = f"https://music.youtube.com/watch?v={suggestion.matched_video_id}"
        job = self._job_executor.create_and_start_job(
            url=video_url,
            max_items=1,
        )

        if job is None:
            logger.warning(
                "Could not create download job for suggestion %s", suggestion_id
            )
            return suggestion

        self._suggestions_repo.update(
            suggestion_id,
            {"status": SuggestionStatus.APPROVED, "job_id": job.id},
        )
        suggestion.status = SuggestionStatus.APPROVED
        suggestion.job_id = job.id
        return suggestion

    def reject_suggestion(self, suggestion_id: UUID) -> DiscoverySuggestion | None:
        """Reject a suggestion."""
        suggestion = self._suggestions_repo.get(suggestion_id)
        if suggestion is None:
            return None
        self._suggestions_repo.update(
            suggestion_id, {"status": SuggestionStatus.REJECTED}
        )
        suggestion.status = SuggestionStatus.REJECTED
        return suggestion

    def bulk_approve(self, suggestion_ids: list[UUID] | None = None) -> int:
        """Bulk approve suggestions. If no IDs given, approves all pending."""
        if suggestion_ids:
            count = 0
            for sid in suggestion_ids:
                if self.approve_suggestion(sid) is not None:
                    count += 1
            return count

        pending = self._suggestions_repo.list_suggestions(
            status=SuggestionStatus.PENDING
        )
        count = 0
        for s in pending:
            if self.approve_suggestion(s.id) is not None:
                count += 1
        return count

    def generate_similar_tracks_playlist(
        self,
        top_tracks_limit: int = 10,
        similar_tracks_per_track: int = 3,
        min_confidence: float | None = None,
    ) -> int:
        """Generate similar-track recommendations and save as pending suggestions.

        Uses track.getSimilar on the user's top tracks for a
        "Discover Weekly"-style playlist.

        Args:
            top_tracks_limit: Number of top tracks to seed from.
            similar_tracks_per_track: Similar tracks per seed track.
            min_confidence: Minimum confidence threshold (overrides settings).

        Returns:
            Number of new suggestions saved.
        """
        settings = self._settings_repo.get()
        if not settings or not settings.enabled:
            logger.warning(
                "Similar-tracks playlist requested but Last.fm is not configured"
            )
            return 0

        if self._core_discovery is not None:
            core = self._core_discovery
        else:
            api_key = self._lastfm_api_key or settings.api_key
            lastfm = LastFmClient(api_key=api_key)
            ytmusic = self._ytmusic or YTMusicClient(
                cookies_path=Path(self._cookies_path) if self._cookies_path else None
            )
            core = CoreDiscoveryService(lastfm=lastfm, ytmusic=ytmusic)

        threshold = (
            min_confidence
            if min_confidence is not None
            else settings.confidence_threshold
        )

        suggestions = core.get_similar_track_recommendations(
            username=settings.username,
            top_tracks_limit=top_tracks_limit,
            similar_tracks_per_track=similar_tracks_per_track,
            min_confidence=threshold,
        )

        if not suggestions:
            logger.info("Similar-tracks playlist returned no suggestions")
            return 0

        existing = {
            (s.lastfm_artist.lower(), s.lastfm_track.lower())
            for s in self._suggestions_repo.list_suggestions()
        }

        new_suggestions = []
        for s in suggestions:
            key = (s.lastfm_artist.lower(), s.lastfm_track.lower())
            if key in existing:
                continue
            new_suggestions.append(
                DiscoverySuggestion(
                    id=uuid4(),
                    lastfm_artist=s.lastfm_artist,
                    lastfm_track=s.lastfm_track,
                    matched_video_id=s.matched_video_id,
                    matched_title=s.matched_title,
                    matched_artist=s.matched_artist,
                    confidence=s.confidence,
                    artist_similarity=s.artist_similarity,
                    title_similarity=s.title_similarity,
                    status=SuggestionStatus.PENDING,
                    created_at=datetime.now(UTC),
                )
            )

        if new_suggestions:
            self._suggestions_repo.bulk_create(new_suggestions)

        logger.info(
            "Similar-tracks playlist: %d new suggestions (from %d candidates)",
            len(new_suggestions),
            len(suggestions),
        )
        return len(new_suggestions)

    def create_discover_playlist(self) -> dict:
        """Approve all pending suggestions and create a Discover playlist M3U.

        Approves all pending suggestions (enqueuing downloads), then scans
        the music library for already-downloaded files matching approved
        suggestions and writes an M3U playlist file for Navidrome.

        Returns:
            dict with approved count, playlist track count, and playlist path.
        """
        # Approve all pending
        pending = self._suggestions_repo.list_suggestions(
            status=SuggestionStatus.PENDING
        )
        approved_count = 0
        for s in pending:
            if self.approve_suggestion(s.id) is not None:
                approved_count += 1

        # Collect files for all approved or downloaded suggestions
        all_approved = self._suggestions_repo.list_suggestions(
            status=SuggestionStatus.APPROVED
        )
        all_downloaded = self._suggestions_repo.list_suggestions(
            status=SuggestionStatus.DOWNLOADED
        )

        if not self._base_path:
            logger.warning("Cannot create Discover playlist: base_path not configured")
            return {
                "approved": approved_count,
                "playlist_tracks": 0,
                "playlist_path": None,
            }

        track_files: list[tuple[TrackMetadata, Path]] = []
        for s in all_approved + all_downloaded:
            file_path = self._find_downloaded_file(s)
            if file_path is not None:
                artist_name = s.matched_artist or s.lastfm_artist
                title = s.matched_title or s.lastfm_track
                meta = TrackMetadata(
                    title=title,
                    artists=[artist_name],
                    album="Discover",
                    album_artists=[artist_name],
                    source_video_id=s.matched_video_id or "",
                )
                track_files.append((meta, file_path))

        from yubal.utils.filename import format_playlist_filename

        # Write M3U playlist (even if empty so Navidrome picks it up)
        playlists_dir = self._base_path / "_Playlists"
        playlists_dir.mkdir(parents=True, exist_ok=True)
        filename = format_playlist_filename(
            DISCOVER_PLAYLIST_NAME, DISCOVER_PLAYLIST_ID
        )
        m3u_path = playlists_dir / f"{filename}.m3u"
        content = generate_m3u(track_files, m3u_path)
        m3u_path.write_text(content, encoding="utf-8")

        logger.info(
            "Discover playlist created: %s (%d tracks)",
            m3u_path,
            len(track_files),
        )
        return {
            "approved": approved_count,
            "playlist_tracks": len(track_files),
            "playlist_path": str(m3u_path),
        }

    def _find_downloaded_file(self, suggestion: DiscoverySuggestion) -> Path | None:
        """Search the music library for a downloaded file matching the suggestion."""
        if not self._base_path or not self._base_path.exists():
            return None

        title = (suggestion.matched_title or suggestion.lastfm_track).lower()
        artist = (suggestion.matched_artist or suggestion.lastfm_artist).lower()

        # Build a set of candidate files once
        candidates: list[Path] = []
        audio_exts = AUDIO_EXTENSIONS
        try:
            for f in self._base_path.rglob("*"):
                if not f.is_file() or f.suffix not in audio_exts:
                    continue
                stem = f.stem.lower()
                if title in stem or artist in stem:
                    candidates.append(f)
        except (PermissionError, OSError) as e:
            logger.warning("Error scanning music library: %s", e)
            return None

        # Best match: file stem contains both title and artist
        for f in candidates:
            stem = f.stem.lower()
            if title in stem and artist in stem:
                return f

        # Fallback: file stem contains the title
        for f in candidates:
            stem = f.stem.lower()
            if title in stem:
                return f

        return None
