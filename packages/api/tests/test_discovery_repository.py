"""Tests for discovery database repositories."""

from uuid import uuid4

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine
from yubal_api.db.discovery import (
    DiscoverySuggestion,
    LastFmSettings,
    SuggestionStatus,
)
from yubal_api.db.discovery_repository import (
    DiscoverySuggestionRepository,
    LastFmSettingsRepository,
)


@pytest.fixture
def engine() -> Engine:
    """Create in-memory SQLite engine for tests."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def settings_repo(engine: Engine) -> LastFmSettingsRepository:
    return LastFmSettingsRepository(engine)


@pytest.fixture
def suggestions_repo(engine: Engine) -> DiscoverySuggestionRepository:
    return DiscoverySuggestionRepository(engine)


class TestLastFmSettingsRepository:
    def test_get_empty(self, settings_repo: LastFmSettingsRepository) -> None:
        assert settings_repo.get() is None

    def test_upsert_create(self, settings_repo: LastFmSettingsRepository) -> None:
        settings = LastFmSettings(
            username="testuser",
            api_key="key123",
            enabled=True,
        )
        result = settings_repo.upsert(settings)
        assert result.username == "testuser"
        assert result.api_key == "key123"
        assert result.enabled is True

    def test_upsert_update(self, settings_repo: LastFmSettingsRepository) -> None:
        original = LastFmSettings(username="testuser", api_key="key123")
        created = settings_repo.upsert(original)

        updated_settings = LastFmSettings(
            username="testuser", api_key="newkey", enabled=True
        )
        result = settings_repo.upsert(updated_settings)

        assert result.id == created.id
        assert result.api_key == "newkey"
        assert result.enabled is True

    def test_delete(self, settings_repo: LastFmSettingsRepository) -> None:
        settings_repo.upsert(LastFmSettings(username="testuser", api_key="key123"))
        assert settings_repo.delete() is True
        assert settings_repo.get() is None

    def test_delete_empty(self, settings_repo: LastFmSettingsRepository) -> None:
        assert settings_repo.delete() is False


class TestDiscoverySuggestionRepository:
    def test_list_empty(self, suggestions_repo: DiscoverySuggestionRepository) -> None:
        assert suggestions_repo.list_suggestions() == []

    def test_create_and_list(
        self, suggestions_repo: DiscoverySuggestionRepository
    ) -> None:
        suggestion = DiscoverySuggestion(
            lastfm_artist="Radiohead",
            lastfm_track="Karma Police",
            confidence=90.0,
        )
        created = suggestions_repo.create(suggestion)
        assert created.id is not None
        assert created.lastfm_artist == "Radiohead"

        all_items = suggestions_repo.list_suggestions()
        assert len(all_items) == 1

    def test_create_and_list_by_status(
        self, suggestions_repo: DiscoverySuggestionRepository
    ) -> None:
        s1 = DiscoverySuggestion(
            lastfm_artist="Artist1",
            lastfm_track="Track1",
            status=SuggestionStatus.PENDING,
        )
        s2 = DiscoverySuggestion(
            lastfm_artist="Artist2",
            lastfm_track="Track2",
            status=SuggestionStatus.APPROVED,
        )
        suggestions_repo.create(s1)
        suggestions_repo.create(s2)

        pending = suggestions_repo.list_suggestions(status=SuggestionStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].lastfm_artist == "Artist1"

    def test_get(self, suggestions_repo: DiscoverySuggestionRepository) -> None:
        s = DiscoverySuggestion(lastfm_artist="Radiohead", lastfm_track="Karma Police")
        created = suggestions_repo.create(s)
        fetched = suggestions_repo.get(created.id)
        assert fetched is not None
        assert fetched.lastfm_artist == "Radiohead"

    def test_get_not_found(
        self, suggestions_repo: DiscoverySuggestionRepository
    ) -> None:
        assert suggestions_repo.get(uuid4()) is None

    def test_update(self, suggestions_repo: DiscoverySuggestionRepository) -> None:
        s = DiscoverySuggestion(lastfm_artist="Radiohead", lastfm_track="Karma Police")
        created = suggestions_repo.create(s)

        updated = suggestions_repo.update(
            created.id, {"status": SuggestionStatus.APPROVED, "job_id": "job-001"}
        )
        assert updated is not None
        assert updated.status == SuggestionStatus.APPROVED
        assert updated.job_id == "job-001"

    def test_update_not_found(
        self, suggestions_repo: DiscoverySuggestionRepository
    ) -> None:
        assert (
            suggestions_repo.update(uuid4(), {"status": SuggestionStatus.APPROVED})
            is None
        )

    def test_bulk_create(self, suggestions_repo: DiscoverySuggestionRepository) -> None:
        suggestions = [
            DiscoverySuggestion(lastfm_artist="A1", lastfm_track="T1"),
            DiscoverySuggestion(lastfm_artist="A2", lastfm_track="T2"),
        ]
        results = suggestions_repo.bulk_create(suggestions)
        assert len(results) == 2
        assert len(suggestions_repo.list_suggestions()) == 2

    def test_count(self, suggestions_repo: DiscoverySuggestionRepository) -> None:
        assert suggestions_repo.count() == 0
        suggestions_repo.create(
            DiscoverySuggestion(lastfm_artist="A1", lastfm_track="T1")
        )
        suggestions_repo.create(
            DiscoverySuggestion(
                lastfm_artist="A2",
                lastfm_track="T2",
                status=SuggestionStatus.APPROVED,
            )
        )
        assert suggestions_repo.count() == 2
        assert suggestions_repo.count(status=SuggestionStatus.PENDING) == 1
        assert suggestions_repo.count(status=SuggestionStatus.APPROVED) == 1

    def test_clear_all(self, suggestions_repo: DiscoverySuggestionRepository) -> None:
        suggestions_repo.create(
            DiscoverySuggestion(lastfm_artist="A1", lastfm_track="T1")
        )
        suggestions_repo.create(
            DiscoverySuggestion(lastfm_artist="A2", lastfm_track="T2")
        )
        assert suggestions_repo.clear() == 2
        assert suggestions_repo.list_suggestions() == []

    def test_clear_by_status(
        self, suggestions_repo: DiscoverySuggestionRepository
    ) -> None:
        suggestions_repo.create(
            DiscoverySuggestion(lastfm_artist="A1", lastfm_track="T1")
        )
        suggestions_repo.create(
            DiscoverySuggestion(
                lastfm_artist="A2",
                lastfm_track="T2",
                status=SuggestionStatus.APPROVED,
            )
        )
        assert suggestions_repo.clear(status=SuggestionStatus.PENDING) == 1
        assert len(suggestions_repo.list_suggestions()) == 1
