"""Tests for Last.fm API client."""

from unittest.mock import MagicMock

import httpx
import pytest
from yubal.lastfm import (
    LASTFM_API_BASE,
    LastFmArtist,
    LastFmClient,
    LastFmSimilarArtist,
    LastFmSimilarTrack,
    LastFmTrack,
)


@pytest.fixture
def mock_http() -> MagicMock:
    """Create a mock httpx client."""
    return MagicMock(spec=httpx.Client)


@pytest.fixture
def client(mock_http: MagicMock) -> LastFmClient:
    """Create a LastFmClient with mocked HTTP client."""
    return LastFmClient(api_key="test_key", http_client=mock_http)


def _mock_response(mock_http: MagicMock, json_data: dict) -> None:
    """Configure mock HTTP to return a JSON response."""
    response = MagicMock(spec=httpx.Response)
    response.json.return_value = json_data
    response.raise_for_status.return_value = None
    mock_http.get.return_value = response


class TestGetTopArtists:
    def test_success(self, client: LastFmClient, mock_http: MagicMock) -> None:
        _mock_response(
            mock_http,
            {
                "topartists": {
                    "artist": [
                        {
                            "name": "Radiohead",
                            "playcount": "150",
                            "listeners": "50000",
                            "url": "https://last.fm/music/Radiohead",
                        },
                        {
                            "name": "Pink Floyd",
                            "playcount": "200",
                            "listeners": "75000",
                            "url": "https://last.fm/music/Pink+Floyd",
                        },
                    ]
                }
            },
        )

        result = client.get_top_artists("testuser", period="7day", limit=5)

        assert len(result) == 2
        assert result[0] == LastFmArtist(
            name="Radiohead",
            playcount=150,
            listeners=50000,
            url="https://last.fm/music/Radiohead",
        )
        assert result[1] == LastFmArtist(
            name="Pink Floyd",
            playcount=200,
            listeners=75000,
            url="https://last.fm/music/Pink+Floyd",
        )

        mock_http.get.assert_called_once_with(
            LASTFM_API_BASE,
            params={
                "method": "user.getTopArtists",
                "api_key": "test_key",
                "format": "json",
                "user": "testuser",
                "period": "7day",
                "limit": "5",
            },
        )

    def test_empty_response(self, client: LastFmClient, mock_http: MagicMock) -> None:
        _mock_response(mock_http, {"topartists": {"artist": []}})
        result = client.get_top_artists("emptyuser")
        assert result == []

    def test_api_error(self, client: LastFmClient, mock_http: MagicMock) -> None:
        mock_http.get.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=MagicMock(), response=MagicMock()
        )
        with pytest.raises(httpx.HTTPStatusError):
            client.get_top_artists("testuser")


class TestGetTopTracksForUser:
    def test_success(self, client: LastFmClient, mock_http: MagicMock) -> None:
        _mock_response(
            mock_http,
            {
                "toptracks": {
                    "track": [
                        {
                            "name": "Karma Police",
                            "playcount": "150",
                            "url": "https://last.fm/music/Radiohead/Karma+Police",
                            "artist": {"name": "Radiohead"},
                        },
                    ]
                }
            },
        )

        result = client.get_top_tracks_for_user("testuser", period="7day", limit=5)

        assert len(result) == 1
        assert result[0] == LastFmTrack(
            artist="Radiohead",
            name="Karma Police",
            playcount=150,
            url="https://last.fm/music/Radiohead/Karma+Police",
        )

        mock_http.get.assert_called_once_with(
            LASTFM_API_BASE,
            params={
                "method": "user.getTopTracks",
                "api_key": "test_key",
                "format": "json",
                "user": "testuser",
                "period": "7day",
                "limit": "5",
            },
        )

    def test_empty_response(self, client: LastFmClient, mock_http: MagicMock) -> None:
        _mock_response(mock_http, {"toptracks": {"track": []}})
        result = client.get_top_tracks_for_user("emptyuser")
        assert result == []


class TestGetSimilarArtists:
    def test_success(self, client: LastFmClient, mock_http: MagicMock) -> None:
        _mock_response(
            mock_http,
            {
                "similarartists": {
                    "artist": [
                        {
                            "name": "Thom Yorke",
                            "match": "0.85",
                            "url": "https://last.fm/music/Thom+Yorke",
                        },
                        {
                            "name": "Atoms for Peace",
                            "match": "0.72",
                            "url": "https://last.fm/music/Atoms+for+Peace",
                        },
                    ]
                }
            },
        )

        result = client.get_similar_artists("Radiohead", limit=5)

        assert len(result) == 2
        assert result[0] == LastFmSimilarArtist(
            name="Thom Yorke",
            match_score=0.85,
            url="https://last.fm/music/Thom+Yorke",
        )
        assert result[1] == LastFmSimilarArtist(
            name="Atoms for Peace",
            match_score=0.72,
            url="https://last.fm/music/Atoms+for+Peace",
        )

        mock_http.get.assert_called_once_with(
            LASTFM_API_BASE,
            params={
                "method": "artist.getSimilar",
                "api_key": "test_key",
                "format": "json",
                "artist": "Radiohead",
                "limit": "5",
            },
        )

    def test_empty_response(self, client: LastFmClient, mock_http: MagicMock) -> None:
        _mock_response(mock_http, {"similarartists": {"artist": []}})
        result = client.get_similar_artists("UnknownArtist")
        assert result == []


class TestGetSimilarTracks:
    def test_success(self, client: LastFmClient, mock_http: MagicMock) -> None:
        _mock_response(
            mock_http,
            {
                "similartracks": {
                    "track": [
                        {
                            "name": "Fake Plastic Trees",
                            "match": "0.9",
                            "url": "https://last.fm/music/Radiohead/Fake+Plastic+Trees",
                            "artist": {"name": "Radiohead"},
                        },
                        {
                            "name": "Lucky",
                            "match": "0.75",
                            "url": "https://last.fm/music/Radiohead/Lucky",
                            "artist": {"name": "Radiohead"},
                        },
                    ]
                }
            },
        )

        result = client.get_similar_tracks("Creep", "Radiohead", limit=5)

        assert len(result) == 2
        assert result[0] == LastFmSimilarTrack(
            artist="Radiohead",
            name="Fake Plastic Trees",
            match_score=0.9,
            url="https://last.fm/music/Radiohead/Fake+Plastic+Trees",
        )
        assert result[1] == LastFmSimilarTrack(
            artist="Radiohead",
            name="Lucky",
            match_score=0.75,
            url="https://last.fm/music/Radiohead/Lucky",
        )

        mock_http.get.assert_called_once_with(
            LASTFM_API_BASE,
            params={
                "method": "track.getSimilar",
                "api_key": "test_key",
                "format": "json",
                "track": "Creep",
                "artist": "Radiohead",
                "limit": "5",
            },
        )

    def test_empty_response(self, client: LastFmClient, mock_http: MagicMock) -> None:
        _mock_response(mock_http, {"similartracks": {"track": []}})
        result = client.get_similar_tracks("Unknown", "Unknown")
        assert result == []


class TestGetTopTracks:
    def test_success(self, client: LastFmClient, mock_http: MagicMock) -> None:
        _mock_response(
            mock_http,
            {
                "toptracks": {
                    "track": [
                        {
                            "name": "Creep",
                            "playcount": "500000",
                            "url": "https://last.fm/music/Radiohead/Creep",
                            "artist": {"name": "Radiohead"},
                        },
                        {
                            "name": "Karma Police",
                            "playcount": "300000",
                            "url": "https://last.fm/music/Radiohead/Karma+Police",
                            "artist": {"name": "Radiohead"},
                        },
                    ]
                }
            },
        )

        result = client.get_top_tracks("Radiohead", limit=10)

        assert len(result) == 2
        assert result[0] == LastFmTrack(
            artist="Radiohead",
            name="Creep",
            playcount=500000,
            url="https://last.fm/music/Radiohead/Creep",
        )
        assert result[1] == LastFmTrack(
            artist="Radiohead",
            name="Karma Police",
            playcount=300000,
            url="https://last.fm/music/Radiohead/Karma+Police",
        )

    def test_empty_response(self, client: LastFmClient, mock_http: MagicMock) -> None:
        _mock_response(mock_http, {"toptracks": {"track": []}})
        result = client.get_top_tracks("UnknownArtist")
        assert result == []
