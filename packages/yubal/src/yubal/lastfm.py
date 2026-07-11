"""Last.fm API client for music discovery.

Provides methods to fetch a user's top artists, similar artists,
and top tracks from the Last.fm REST API.

Strategy note:
    Last.fm's user.getRecommendedTracks endpoint was a beta feature that
    never reached stable and required an authenticated session. Instead,
    this client uses the public API chain:
    user.getTopArtists -> artist.getSimilar -> artist.getTopTracks
    This works with just a username and API key (no session token),
    which is simpler to set up and sufficient for discovery purposes.
"""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

LASTFM_API_BASE = "https://ws.audioscrobbler.com/2.0/"


@dataclass(frozen=True)
class LastFmArtist:
    name: str
    playcount: int | None = None
    listeners: int | None = None
    url: str | None = None


@dataclass(frozen=True)
class LastFmTrack:
    artist: str
    name: str
    playcount: int | None = None
    url: str | None = None


@dataclass(frozen=True)
class LastFmSimilarArtist:
    name: str
    match_score: float
    url: str | None = None


@dataclass(frozen=True)
class LastFmSimilarTrack:
    artist: str
    name: str
    match_score: float
    url: str | None = None


class LastFmClient:
    """Client for the Last.fm REST API.

    Args:
        api_key: Last.fm API key. Get one at https://www.last.fm/api/account/create.
        http_client: Optional httpx client for dependency injection/testing.
    """

    def __init__(
        self,
        api_key: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._http = http_client or httpx.Client(timeout=30.0)

    def _get(self, method: str, **params: str) -> dict:
        """Make a GET request to the Last.fm API."""
        params = {
            "method": method,
            "api_key": self._api_key,
            "format": "json",
            **params,
        }
        response = self._http.get(LASTFM_API_BASE, params=params)
        response.raise_for_status()
        return response.json()

    def get_top_artists(
        self, username: str, period: str = "overall", limit: int = 10
    ) -> list[LastFmArtist]:
        """Fetch a user's top artists.

        Args:
            username: Last.fm username.
            period: Time period (overall, 7day, 1month, 3month, 6month, 12month).
            limit: Max results (default 10, max 1000).

        Returns:
            List of LastFmArtist.
        """
        data = self._get(
            "user.getTopArtists",
            user=username,
            period=period,
            limit=str(limit),
        )
        artists = []
        for a in (data.get("topartists") or {}).get("artist", []):
            artists.append(
                LastFmArtist(
                    name=a.get("name", ""),
                    playcount=int(a.get("playcount", 0)),
                    listeners=int(a.get("listeners", 0)),
                    url=a.get("url"),
                )
            )
        return artists

    def get_top_tracks_for_user(
        self, username: str, period: str = "overall", limit: int = 10
    ) -> list[LastFmTrack]:
        """Fetch a user's top tracks.

        Args:
            username: Last.fm username.
            period: Time period (overall, 7day, 1month, 3month, 6month, 12month).
            limit: Max results (default 10, max 1000).

        Returns:
            List of LastFmTrack.
        """
        data = self._get(
            "user.getTopTracks",
            user=username,
            period=period,
            limit=str(limit),
        )
        tracks = []
        for t in (data.get("toptracks") or {}).get("track", []):
            artist_info = t.get("artist", {}) or {}
            tracks.append(
                LastFmTrack(
                    artist=artist_info.get("name", ""),
                    name=t.get("name", ""),
                    playcount=int(t.get("playcount", 0)),
                    url=t.get("url"),
                )
            )
        return tracks

    def get_similar_artists(
        self, artist_name: str, limit: int = 10
    ) -> list[LastFmSimilarArtist]:
        """Fetch similar artists for a given artist.

        Args:
            artist_name: Name of the artist.
            limit: Max results (default 10, max 100).

        Returns:
            List of LastFmSimilarArtist with match scores.
        """
        data = self._get(
            "artist.getSimilar",
            artist=artist_name,
            limit=str(limit),
        )
        similar = []
        for a in (data.get("similarartists") or {}).get("artist", []):
            similar.append(
                LastFmSimilarArtist(
                    name=a.get("name", ""),
                    match_score=float(a.get("match", 0)),
                    url=a.get("url"),
                )
            )
        return similar

    def get_similar_tracks(
        self, track: str, artist: str, limit: int = 10
    ) -> list[LastFmSimilarTrack]:
        """Fetch tracks similar to a given track.

        Args:
            track: Name of the track.
            artist: Name of the artist.
            limit: Max results (default 10, max 100).

        Returns:
            List of LastFmSimilarTrack with match scores.
        """
        data = self._get(
            "track.getSimilar",
            track=track,
            artist=artist,
            limit=str(limit),
        )
        similar = []
        for t in (data.get("similartracks") or {}).get("track", []):
            artist_info = t.get("artist", {}) or {}
            similar.append(
                LastFmSimilarTrack(
                    artist=artist_info.get("name", ""),
                    name=t.get("name", ""),
                    match_score=float(t.get("match", 0)),
                    url=t.get("url"),
                )
            )
        return similar

    def get_top_tracks(self, artist_name: str, limit: int = 5) -> list[LastFmTrack]:
        """Fetch top tracks for an artist.

        Args:
            artist_name: Name of the artist.
            limit: Max results (default 5, max 100).

        Returns:
            List of LastFmTrack.
        """
        data = self._get(
            "artist.getTopTracks",
            artist=artist_name,
            limit=str(limit),
        )
        tracks = []
        for t in (data.get("toptracks") or {}).get("track", []):
            artist_info = t.get("artist", {}) or {}
            tracks.append(
                LastFmTrack(
                    artist=artist_info.get("name", artist_name),
                    name=t.get("name", ""),
                    playcount=int(t.get("playcount", 0)),
                    url=t.get("url"),
                )
            )
        return tracks
