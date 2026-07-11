"""Tests for API-level DiscoveryService."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from yubal.services.discovery import DiscoverySuggestion as CoreSuggestion
from yubal_api.db.discovery import (
    DiscoverySuggestion,
    LastFmSettings,
    SuggestionStatus,
)
from yubal_api.services.discovery_service import DiscoveryService


@pytest.fixture
def mock_settings_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_suggestions_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_job_executor() -> MagicMock:
    executor = MagicMock()
    job = MagicMock()
    job.id = "job-001"
    executor.create_and_start_job.return_value = job
    return executor


@pytest.fixture
def mock_core_discovery() -> MagicMock:
    return MagicMock(spec=["get_recommendations", "get_similar_track_recommendations"])


@pytest.fixture
def service(
    mock_settings_repo: MagicMock,
    mock_suggestions_repo: MagicMock,
    mock_job_executor: MagicMock,
    mock_core_discovery: MagicMock,
) -> DiscoveryService:
    return DiscoveryService(
        settings_repo=mock_settings_repo,
        suggestions_repo=mock_suggestions_repo,
        job_executor=mock_job_executor,
        core_discovery=mock_core_discovery,
    )


@pytest.fixture
def sample_settings() -> LastFmSettings:
    return LastFmSettings(
        id=uuid4(),
        username="testuser",
        api_key="testkey",
        enabled=True,
        confidence_threshold=50,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_suggestion() -> DiscoverySuggestion:
    return DiscoverySuggestion(
        id=uuid4(),
        lastfm_artist="Radiohead",
        lastfm_track="Karma Police",
        matched_video_id="v123",
        matched_title="Karma Police",
        matched_artist="Radiohead",
        confidence=95.0,
        status=SuggestionStatus.PENDING,
        created_at=datetime.now(UTC),
    )


class TestGetSettings:
    def test_returns_settings(
        self,
        service: DiscoveryService,
        mock_settings_repo: MagicMock,
        sample_settings: LastFmSettings,
    ) -> None:
        mock_settings_repo.get.return_value = sample_settings
        result = service.get_settings()
        assert result is not None
        assert result.username == "testuser"

    def test_returns_none(
        self, service: DiscoveryService, mock_settings_repo: MagicMock
    ) -> None:
        mock_settings_repo.get.return_value = None
        assert service.get_settings() is None


class TestConnect:
    def test_connect_new(
        self, service: DiscoveryService, mock_settings_repo: MagicMock
    ) -> None:
        mock_settings_repo.get.return_value = None
        mock_settings_repo.upsert.side_effect = lambda s: s

        result = service.connect("newuser", "newkey")
        assert result.username == "newuser"
        assert result.api_key == "newkey"

    def test_connect_existing(
        self,
        service: DiscoveryService,
        mock_settings_repo: MagicMock,
        sample_settings: LastFmSettings,
    ) -> None:
        mock_settings_repo.get.return_value = sample_settings
        mock_settings_repo.upsert.side_effect = lambda s: s

        result = service.connect("updateduser", "updatedkey")
        assert result.username == "updateduser"
        assert result.api_key == "updatedkey"


class TestDisconnect:
    def test_disconnect(
        self,
        service: DiscoveryService,
        mock_settings_repo: MagicMock,
        mock_suggestions_repo: MagicMock,
    ) -> None:
        mock_settings_repo.delete.return_value = True
        assert service.disconnect() is True
        mock_suggestions_repo.clear.assert_called_once()


class TestRunScan:
    def test_scan_not_configured(
        self, service: DiscoveryService, mock_settings_repo: MagicMock
    ) -> None:
        mock_settings_repo.get.return_value = None
        assert service.run_scan() == 0

    def test_scan_disabled(
        self,
        service: DiscoveryService,
        mock_settings_repo: MagicMock,
        sample_settings: LastFmSettings,
    ) -> None:
        sample_settings.enabled = False
        mock_settings_repo.get.return_value = sample_settings
        assert service.run_scan() == 0

    def test_scan_with_results(
        self,
        service: DiscoveryService,
        mock_settings_repo: MagicMock,
        mock_suggestions_repo: MagicMock,
        mock_core_discovery: MagicMock,
        sample_settings: LastFmSettings,
    ) -> None:
        mock_settings_repo.get.return_value = sample_settings
        mock_suggestions_repo.list_suggestions.return_value = []
        mock_suggestions_repo.bulk_create.side_effect = lambda s: s
        mock_core_discovery.get_recommendations.return_value = [
            CoreSuggestion(
                lastfm_artist="Radiohead",
                lastfm_track="Karma Police",
                matched_video_id="v123",
                matched_title="Karma Police",
                matched_artist="Radiohead",
                confidence=95.0,
                artist_similarity=95.0,
                title_similarity=95.0,
            ),
        ]

        result = service.run_scan()
        assert result == 1
        mock_suggestions_repo.bulk_create.assert_called_once()

    def test_scan_deduplicates(
        self,
        service: DiscoveryService,
        mock_settings_repo: MagicMock,
        mock_suggestions_repo: MagicMock,
        mock_core_discovery: MagicMock,
        sample_settings: LastFmSettings,
    ) -> None:
        mock_settings_repo.get.return_value = sample_settings
        existing = DiscoverySuggestion(
            id=uuid4(),
            lastfm_artist="Radiohead",
            lastfm_track="Karma Police",
            status=SuggestionStatus.PENDING,
            created_at=datetime.now(UTC),
        )
        mock_suggestions_repo.list_suggestions.return_value = [existing]
        mock_core_discovery.get_recommendations.return_value = [
            CoreSuggestion(
                lastfm_artist="Radiohead",
                lastfm_track="Karma Police",
                matched_video_id="v123",
                matched_title="Karma Police",
                matched_artist="Radiohead",
                confidence=95.0,
                artist_similarity=95.0,
                title_similarity=95.0,
            ),
        ]

        result = service.run_scan()
        assert result == 0
        mock_suggestions_repo.bulk_create.assert_not_called()


class TestApproveSuggestion:
    def test_approve_not_found(
        self, service: DiscoveryService, mock_suggestions_repo: MagicMock
    ) -> None:
        mock_suggestions_repo.get.return_value = None
        result = service.approve_suggestion(uuid4())
        assert result is None

    def test_approve_no_video_id(
        self, service: DiscoveryService, mock_suggestions_repo: MagicMock
    ) -> None:
        suggestion = DiscoverySuggestion(
            id=uuid4(),
            lastfm_artist="Artist",
            lastfm_track="Track",
            matched_video_id=None,
            status=SuggestionStatus.PENDING,
            created_at=datetime.now(UTC),
        )
        mock_suggestions_repo.get.return_value = suggestion

        result = service.approve_suggestion(suggestion.id)
        assert result is not None
        assert result.status == SuggestionStatus.REJECTED

    def test_approve_success(
        self,
        service: DiscoveryService,
        mock_suggestions_repo: MagicMock,
        mock_job_executor: MagicMock,
        sample_suggestion: DiscoverySuggestion,
    ) -> None:
        mock_suggestions_repo.get.return_value = sample_suggestion
        job = MagicMock()
        job.id = "job-001"
        mock_job_executor.create_and_start_job.return_value = job

        result = service.approve_suggestion(sample_suggestion.id)
        assert result is not None
        assert result.status == SuggestionStatus.APPROVED
        assert result.job_id == "job-001"
        mock_job_executor.create_and_start_job.assert_called_once_with(
            url="https://music.youtube.com/watch?v=v123",
            max_items=1,
        )


class TestRejectSuggestion:
    def test_reject_not_found(
        self, service: DiscoveryService, mock_suggestions_repo: MagicMock
    ) -> None:
        mock_suggestions_repo.get.return_value = None
        assert service.reject_suggestion(uuid4()) is None

    def test_reject_success(
        self,
        service: DiscoveryService,
        mock_suggestions_repo: MagicMock,
        sample_suggestion: DiscoverySuggestion,
    ) -> None:
        mock_suggestions_repo.get.return_value = sample_suggestion

        result = service.reject_suggestion(sample_suggestion.id)
        assert result is not None
        assert result.status == SuggestionStatus.REJECTED


class TestBulkApprove:
    def test_bulk_approve_all_pending(
        self,
        service: DiscoveryService,
        mock_suggestions_repo: MagicMock,
        mock_job_executor: MagicMock,
    ) -> None:
        s1 = DiscoverySuggestion(
            id=uuid4(),
            lastfm_artist="A1",
            lastfm_track="T1",
            matched_video_id="v1",
            status=SuggestionStatus.PENDING,
            created_at=datetime.now(UTC),
        )
        s2 = DiscoverySuggestion(
            id=uuid4(),
            lastfm_artist="A2",
            lastfm_track="T2",
            matched_video_id="v2",
            status=SuggestionStatus.PENDING,
            created_at=datetime.now(UTC),
        )
        mock_suggestions_repo.list_suggestions.return_value = [s1, s2]
        job = MagicMock()
        job.id = "job-001"
        mock_job_executor.create_and_start_job.return_value = job

        count = service.bulk_approve()
        assert count == 2

    def test_bulk_approve_specific_ids(
        self,
        service: DiscoveryService,
        mock_suggestions_repo: MagicMock,
        mock_job_executor: MagicMock,
    ) -> None:
        s1 = DiscoverySuggestion(
            id=uuid4(),
            lastfm_artist="A1",
            lastfm_track="T1",
            matched_video_id="v1",
            status=SuggestionStatus.PENDING,
            created_at=datetime.now(UTC),
        )
        mock_suggestions_repo.get.return_value = s1
        job = MagicMock()
        job.id = "job-001"
        mock_job_executor.create_and_start_job.return_value = job

        count = service.bulk_approve([s1.id])
        assert count == 1


class TestGenerateSimilarTracksPlaylist:
    def test_generates_and_saves(
        self,
        service: DiscoveryService,
        mock_settings_repo: MagicMock,
        mock_suggestions_repo: MagicMock,
        mock_core_discovery: MagicMock,
        sample_settings: LastFmSettings,
    ) -> None:
        mock_settings_repo.get.return_value = sample_settings
        mock_suggestions_repo.list_suggestions.return_value = []
        from yubal.services.discovery import DiscoverySuggestion as CoreSuggestion

        mock_core_discovery.get_similar_track_recommendations.return_value = [
            CoreSuggestion(
                lastfm_artist="Radiohead",
                lastfm_track="Fake Plastic Trees",
                matched_video_id="v123",
                matched_title="Fake Plastic Trees",
                matched_artist="Radiohead",
                confidence=90.0,
                artist_similarity=100.0,
                title_similarity=100.0,
            ),
        ]

        result = service.generate_similar_tracks_playlist(
            top_tracks_limit=5, similar_tracks_per_track=2
        )

        assert result == 1
        mock_core_discovery.get_similar_track_recommendations.assert_called_once_with(
            username="testuser",
            top_tracks_limit=5,
            similar_tracks_per_track=2,
            min_confidence=50,
        )

    def test_not_configured(
        self,
        service: DiscoveryService,
        mock_settings_repo: MagicMock,
    ) -> None:
        mock_settings_repo.get.return_value = None
        assert service.generate_similar_tracks_playlist() == 0

    def test_disabled(
        self,
        service: DiscoveryService,
        mock_settings_repo: MagicMock,
        sample_settings: LastFmSettings,
    ) -> None:
        sample_settings.enabled = False
        mock_settings_repo.get.return_value = sample_settings
        assert service.generate_similar_tracks_playlist() == 0

    def test_no_suggestions(
        self,
        service: DiscoveryService,
        mock_settings_repo: MagicMock,
        mock_core_discovery: MagicMock,
        sample_settings: LastFmSettings,
    ) -> None:
        mock_settings_repo.get.return_value = sample_settings
        mock_core_discovery.get_similar_track_recommendations.return_value = []
        assert service.generate_similar_tracks_playlist() == 0
