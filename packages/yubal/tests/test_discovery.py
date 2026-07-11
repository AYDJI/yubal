"""Tests for the Discovery service."""

from unittest.mock import MagicMock

import pytest
from yubal.lastfm import (
    LastFmArtist,
    LastFmClient,
    LastFmSimilarArtist,
    LastFmSimilarTrack,
    LastFmTrack,
)
from yubal.models.ytmusic import Artist, SearchResult
from yubal.services.discovery import (
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    DiscoveryService,
    _compute_confidence,
)


@pytest.fixture
def mock_lastfm() -> MagicMock:
    """Create a mock Last.fm client."""
    return MagicMock(spec=LastFmClient)


@pytest.fixture
def mock_ytmusic() -> MagicMock:
    """Create a mock YTMusic client (protocol)."""
    return MagicMock()


@pytest.fixture
def service(mock_lastfm: MagicMock, mock_ytmusic: MagicMock) -> DiscoveryService:
    """Create a DiscoveryService with mocked dependencies."""
    return DiscoveryService(lastfm=mock_lastfm, ytmusic=mock_ytmusic)


def _search_result(video_id: str, title: str, artist_names: list[str]) -> SearchResult:
    """Helper to create a SearchResult."""
    return SearchResult(
        videoId=video_id,
        title=title,
        artists=[Artist(name=n) for n in artist_names],
    )


class TestComputeConfidence:
    def test_exact_match(self) -> None:
        score = _compute_confidence(
            "Radiohead", "Karma Police", "Karma Police", ["Radiohead"]
        )
        assert score >= 95

    def test_partial_match(self) -> None:
        score = _compute_confidence(
            "Radiohead",
            "Karma Police",
            "Karma Police (Official Video)",
            ["Radiohead"],
        )
        assert 60 <= score <= 100

    def test_no_match(self) -> None:
        score = _compute_confidence(
            "Radiohead", "Karma Police", "Nothing Else Matters", ["Metallica"]
        )
        assert score < 50


class TestGetRecommendations:
    def test_basic_pipeline(
        self, service: DiscoveryService, mock_lastfm: MagicMock, mock_ytmusic: MagicMock
    ) -> None:
        mock_lastfm.get_top_artists.return_value = [
            LastFmArtist(name="Radiohead", playcount=100),
        ]
        mock_lastfm.get_similar_artists.return_value = [
            LastFmSimilarArtist(name="Thom Yorke", match_score=0.8),
        ]
        mock_lastfm.get_top_tracks.side_effect = [
            [LastFmTrack(artist="Radiohead", name="Karma Police")],
            [LastFmTrack(artist="Thom Yorke", name="Harrowdown Hill")],
        ]
        mock_ytmusic.search_songs.side_effect = [
            [_search_result("v1", "Karma Police", ["Radiohead"])],
            [_search_result("v2", "Harrowdown Hill", ["Thom Yorke"])],
        ]

        result = service.get_recommendations(
            "testuser",
            top_artists_limit=1,
            similar_artists_per_artist=1,
            top_tracks_per_artist=1,
            min_confidence=0,
        )

        assert len(result) == 2
        assert result[0].lastfm_track == "Karma Police"
        assert result[0].matched_video_id == "v1"
        assert result[1].lastfm_track == "Harrowdown Hill"
        assert result[1].matched_video_id == "v2"

    def test_deduplication(
        self, service: DiscoveryService, mock_lastfm: MagicMock, mock_ytmusic: MagicMock
    ) -> None:
        mock_lastfm.get_top_artists.return_value = [
            LastFmArtist(name="Radiohead"),
        ]
        mock_lastfm.get_similar_artists.return_value = [
            LastFmSimilarArtist(name="Radiohead", match_score=0.5),
        ]
        mock_lastfm.get_top_tracks.return_value = [
            LastFmTrack(artist="Radiohead", name="Karma Police"),
        ]
        mock_ytmusic.search_songs.return_value = [
            _search_result("v1", "Karma Police", ["Radiohead"]),
        ]

        result = service.get_recommendations(
            "testuser",
            top_artists_limit=1,
            similar_artists_per_artist=1,
            top_tracks_per_artist=1,
            min_confidence=0,
        )

        # Only one suggestion despite artist appearing twice
        assert len(result) == 1

    def test_confidence_filtering(
        self, service: DiscoveryService, mock_lastfm: MagicMock, mock_ytmusic: MagicMock
    ) -> None:
        mock_lastfm.get_top_artists.return_value = [
            LastFmArtist(name="Radiohead"),
        ]
        mock_lastfm.get_similar_artists.return_value = []
        mock_lastfm.get_top_tracks.return_value = [
            LastFmTrack(artist="Radiohead", name="Karma Police"),
        ]
        mock_ytmusic.search_songs.return_value = [
            _search_result("v1", "Karma Police", ["Radiohead"]),
        ]

        result = service.get_recommendations(
            "testuser",
            top_artists_limit=1,
            similar_artists_per_artist=0,
            top_tracks_per_artist=1,
            min_confidence=CONFIDENCE_HIGH,
        )

        assert len(result) == 1  # High-confidence match passes

    def test_no_search_results(
        self, service: DiscoveryService, mock_lastfm: MagicMock, mock_ytmusic: MagicMock
    ) -> None:
        mock_lastfm.get_top_artists.return_value = [
            LastFmArtist(name="Obscure Artist"),
        ]
        mock_lastfm.get_similar_artists.return_value = []
        mock_lastfm.get_top_tracks.return_value = [
            LastFmTrack(artist="Obscure Artist", name="Unknown Track"),
        ]
        mock_ytmusic.search_songs.return_value = []

        result = service.get_recommendations(
            "testuser",
            top_artists_limit=1,
            similar_artists_per_artist=0,
            top_tracks_per_artist=1,
            min_confidence=CONFIDENCE_MEDIUM,
        )

        assert len(result) == 0

    def test_search_error_handling(
        self, service: DiscoveryService, mock_lastfm: MagicMock, mock_ytmusic: MagicMock
    ) -> None:
        mock_lastfm.get_top_artists.return_value = [
            LastFmArtist(name="Radiohead"),
        ]
        mock_lastfm.get_similar_artists.return_value = []
        mock_lastfm.get_top_tracks.return_value = [
            LastFmTrack(artist="Radiohead", name="Karma Police"),
        ]
        mock_ytmusic.search_songs.side_effect = RuntimeError("API down")

        result = service.get_recommendations(
            "testuser",
            top_artists_limit=1,
            similar_artists_per_artist=0,
            top_tracks_per_artist=1,
            min_confidence=CONFIDENCE_MEDIUM,
        )

        assert len(result) == 0

    def test_top_tracks_error_handling(
        self, service: DiscoveryService, mock_lastfm: MagicMock, mock_ytmusic: MagicMock
    ) -> None:
        mock_lastfm.get_top_artists.return_value = [
            LastFmArtist(name="Radiohead"),
        ]
        mock_lastfm.get_similar_artists.return_value = []
        mock_lastfm.get_top_tracks.side_effect = RuntimeError("API down")

        result = service.get_recommendations(
            "testuser",
            top_artists_limit=1,
            similar_artists_per_artist=0,
            top_tracks_per_artist=1,
            min_confidence=CONFIDENCE_MEDIUM,
        )

        assert len(result) == 0

    def test_empty_top_artists(
        self, service: DiscoveryService, mock_lastfm: MagicMock, mock_ytmusic: MagicMock
    ) -> None:
        mock_lastfm.get_top_artists.return_value = []

        result = service.get_recommendations("testuser")

        assert result == []


class TestGetSimilarTrackRecommendations:
    def test_basic_pipeline(
        self, service: DiscoveryService, mock_lastfm: MagicMock, mock_ytmusic: MagicMock
    ) -> None:
        mock_lastfm.get_top_tracks_for_user.return_value = [
            LastFmTrack(artist="Radiohead", name="Karma Police"),
        ]
        mock_lastfm.get_similar_tracks.return_value = [
            LastFmSimilarTrack(
                artist="Radiohead", name="Fake Plastic Trees", match_score=0.9
            ),
        ]
        mock_ytmusic.search_songs.return_value = [
            _search_result("v1", "Fake Plastic Trees", ["Radiohead"]),
        ]

        result = service.get_similar_track_recommendations(
            "testuser",
            top_tracks_limit=1,
            similar_tracks_per_track=1,
            min_confidence=0,
        )

        assert len(result) == 1
        assert result[0].lastfm_track == "Fake Plastic Trees"
        assert result[0].matched_video_id == "v1"

    def test_deduplication(
        self, service: DiscoveryService, mock_lastfm: MagicMock, mock_ytmusic: MagicMock
    ) -> None:
        mock_lastfm.get_top_tracks_for_user.return_value = [
            LastFmTrack(artist="Radiohead", name="Karma Police"),
            LastFmTrack(artist="Radiohead", name="Karma Police"),
        ]
        mock_lastfm.get_similar_tracks.return_value = [
            LastFmSimilarTrack(
                artist="Radiohead", name="Fake Plastic Trees", match_score=0.9
            ),
        ]
        mock_ytmusic.search_songs.return_value = [
            _search_result("v1", "Fake Plastic Trees", ["Radiohead"]),
        ]

        result = service.get_similar_track_recommendations(
            "testuser",
            top_tracks_limit=2,
            similar_tracks_per_track=1,
            min_confidence=0,
        )

        assert len(result) == 1  # Same similar track deduped

    def test_confidence_filtering(
        self, service: DiscoveryService, mock_lastfm: MagicMock, mock_ytmusic: MagicMock
    ) -> None:
        mock_lastfm.get_top_tracks_for_user.return_value = [
            LastFmTrack(artist="Radiohead", name="Karma Police"),
        ]
        mock_lastfm.get_similar_tracks.return_value = [
            LastFmSimilarTrack(
                artist="Radiohead", name="Fake Plastic Trees", match_score=0.9
            ),
        ]
        mock_ytmusic.search_songs.return_value = [
            _search_result("v1", "Fake Plastic Trees", ["Radiohead"]),
        ]

        result = service.get_similar_track_recommendations(
            "testuser",
            top_tracks_limit=1,
            similar_tracks_per_track=1,
            min_confidence=CONFIDENCE_HIGH,
        )

        assert len(result) == 1  # High-confidence match passes

    def test_empty_top_tracks(
        self, service: DiscoveryService, mock_lastfm: MagicMock, mock_ytmusic: MagicMock
    ) -> None:
        mock_lastfm.get_top_tracks_for_user.return_value = []
        result = service.get_similar_track_recommendations("testuser")
        assert result == []

    def test_similar_tracks_error(
        self, service: DiscoveryService, mock_lastfm: MagicMock, mock_ytmusic: MagicMock
    ) -> None:
        mock_lastfm.get_top_tracks_for_user.return_value = [
            LastFmTrack(artist="Radiohead", name="Karma Police"),
        ]
        mock_lastfm.get_similar_tracks.side_effect = RuntimeError("API down")

        result = service.get_similar_track_recommendations(
            "testuser", top_tracks_limit=1, similar_tracks_per_track=1
        )

        assert result == []
