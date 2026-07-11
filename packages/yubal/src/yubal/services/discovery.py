"""Music discovery service using Last.fm recommendations.

Orchestrates the discovery pipeline:
1. Fetch a user's top artists from Last.fm
2. For each top artist, find similar artists
3. For each similar artist, get top tracks
4. Search YT Music for each track to find a match
5. Score each match by confidence
"""

import logging
from dataclasses import dataclass

from rapidfuzz import fuzz

from yubal.client import YTMusicProtocol
from yubal.lastfm import LastFmClient

logger = logging.getLogger(__name__)

# Confidence thresholds (0-100 scale)
CONFIDENCE_HIGH = 80
CONFIDENCE_MEDIUM = 50
CONFIDENCE_AUTO_DOWNLOAD = CONFIDENCE_HIGH


@dataclass(frozen=True)
class DiscoverySuggestion:
    """A discovered track suggestion with match details."""

    lastfm_artist: str
    lastfm_track: str
    matched_video_id: str | None
    matched_title: str | None
    matched_artist: str | None
    confidence: float
    artist_similarity: float
    title_similarity: float


def _compute_confidence(
    lastfm_artist: str,
    lastfm_track: str,
    search_title: str,
    search_artists: list[str],
) -> float:
    """Compute a confidence score for a Last.fm -> YT Music match.

    Uses normalized fuzzy matching on both artist and title.
    Returns a score from 0-100.
    """
    title_score = fuzz.token_sort_ratio(lastfm_track.lower(), search_title.lower())

    artist_scores = [
        fuzz.token_sort_ratio(lastfm_artist.lower(), a.lower()) for a in search_artists
    ]
    artist_score = max(artist_scores) if artist_scores else 0.0

    # Weight: title 60%, artist 40%
    confidence = title_score * 0.6 + artist_score * 0.4
    return confidence


class DiscoveryService:
    """Orchestrates Last.fm-based music discovery against YT Music.

    Args:
        lastfm: Configured LastFmClient instance.
        ytmusic: YTMusicProtocol instance for searching YT Music.
    """

    def __init__(
        self,
        lastfm: LastFmClient,
        ytmusic: YTMusicProtocol,
    ) -> None:
        self._lastfm = lastfm
        self._ytmusic = ytmusic

    def get_recommendations(
        self,
        username: str,
        top_artists_limit: int = 5,
        similar_artists_per_artist: int = 3,
        top_tracks_per_artist: int = 3,
        min_confidence: float = CONFIDENCE_MEDIUM,
    ) -> list[DiscoverySuggestion]:
        """Fetch music recommendations via Last.fm and match against YT Music.

        Pipeline:
        1. Get top artists for the user
        2. For each top artist, find similar artists (excluding the original)
        3. For each similar + original artist, get top tracks
        4. Search YT Music for each track
        5. Score and filter by confidence

        Args:
            username: Last.fm username.
            top_artists_limit: Number of top artists to fetch.
            similar_artists_per_artist: Similar artists per top artist.
            top_tracks_per_artist: Top tracks per (similar) artist.
            min_confidence: Minimum confidence threshold (0-100).

        Returns:
            List of DiscoverySuggestion sorted by confidence descending.
        """
        suggestions: list[DiscoverySuggestion] = []
        seen: set[tuple[str, str]] = set()

        top_artists = self._lastfm.get_top_artists(username, limit=top_artists_limit)
        logger.info("Fetched %d top artists for user '%s'", len(top_artists), username)

        for top_artist in top_artists:
            # Include some tracks from the top artist directly
            self._add_tracks_for_artist(
                top_artist.name, suggestions, seen, top_tracks_per_artist
            )

            # Find similar artists and get their top tracks
            similar = self._lastfm.get_similar_artists(
                top_artist.name, limit=similar_artists_per_artist
            )
            for similar_artist in similar:
                self._add_tracks_for_artist(
                    similar_artist.name, suggestions, seen, top_tracks_per_artist
                )

        # Filter by minimum confidence and sort
        filtered = [s for s in suggestions if s.confidence >= min_confidence]
        filtered.sort(key=lambda s: s.confidence, reverse=True)

        logger.info(
            "Discovery complete: %d suggestions (after filtering %d+ confidence)",
            len(filtered),
            min_confidence,
        )
        return filtered

    def get_similar_track_recommendations(
        self,
        username: str,
        top_tracks_limit: int = 10,
        similar_tracks_per_track: int = 3,
        min_confidence: float = CONFIDENCE_MEDIUM,
    ) -> list[DiscoverySuggestion]:
        """Fetch track-similarity recommendations via Last.fm.

        Pipeline:
        1. Get the user's top tracks
        2. For each top track, find similar tracks via track.getSimilar
        3. Search YT Music for each similar track
        4. Score and filter by confidence

        Args:
            username: Last.fm username.
            top_tracks_limit: Number of top tracks to seed from.
            similar_tracks_per_track: Similar tracks per seed track.
            min_confidence: Minimum confidence threshold (0-100).

        Returns:
            List of DiscoverySuggestion sorted by confidence descending.
        """
        suggestions: list[DiscoverySuggestion] = []
        seen: set[tuple[str, str]] = set()

        top_tracks = self._lastfm.get_top_tracks_for_user(
            username, period="overall", limit=top_tracks_limit
        )
        logger.info(
            "Fetched %d top tracks for user '%s'",
            len(top_tracks),
            username,
        )

        for top_track in top_tracks:
            try:
                similar = self._lastfm.get_similar_tracks(
                    top_track.name,
                    top_track.artist,
                    limit=similar_tracks_per_track,
                )
            except Exception:
                logger.warning(
                    "Failed to fetch similar tracks for '%s - %s'",
                    top_track.artist,
                    top_track.name,
                    exc_info=True,
                )
                continue

            for similar_track in similar:
                key = (similar_track.artist.lower(), similar_track.name.lower())
                if key in seen:
                    continue
                seen.add(key)

                match = self._search_and_score(similar_track.artist, similar_track.name)
                suggestions.append(match)

        filtered = [s for s in suggestions if s.confidence >= min_confidence]
        filtered.sort(key=lambda s: s.confidence, reverse=True)

        logger.info(
            "Similar-track discovery complete: %d suggestions "
            "(after filtering %d+ confidence)",
            len(filtered),
            min_confidence,
        )
        return filtered

    def _add_tracks_for_artist(
        self,
        artist_name: str,
        suggestions: list[DiscoverySuggestion],
        seen: set[tuple[str, str]],
        limit: int,
    ) -> None:
        """Fetch top tracks for an artist and match them against YT Music."""
        try:
            tracks = self._lastfm.get_top_tracks(artist_name, limit=limit)
        except Exception:
            logger.warning(
                "Failed to fetch top tracks for '%s'", artist_name, exc_info=True
            )
            return

        for track in tracks:
            key = (track.artist.lower(), track.name.lower())
            if key in seen:
                continue
            seen.add(key)

            match = self._search_and_score(track.artist, track.name)
            suggestions.append(match)

    def _search_and_score(self, artist: str, track_name: str) -> DiscoverySuggestion:
        """Search YT Music for a track and compute confidence."""
        query = f"{artist} - {track_name}"
        try:
            results = self._ytmusic.search_songs(query)
        except Exception:
            logger.warning("Search failed for '%s'", query, exc_info=True)
            return DiscoverySuggestion(
                lastfm_artist=artist,
                lastfm_track=track_name,
                matched_video_id=None,
                matched_title=None,
                matched_artist=None,
                confidence=0.0,
                artist_similarity=0.0,
                title_similarity=0.0,
            )

        if not results:
            return DiscoverySuggestion(
                lastfm_artist=artist,
                lastfm_track=track_name,
                matched_video_id=None,
                matched_title=None,
                matched_artist=None,
                confidence=0.0,
                artist_similarity=0.0,
                title_similarity=0.0,
            )

        best = results[0]
        search_artists = [a.name for a in best.artists]
        confidence = _compute_confidence(artist, track_name, best.title, search_artists)

        artist_sim = max(
            (fuzz.token_sort_ratio(artist.lower(), a.lower()) for a in search_artists),
            default=0.0,
        )
        title_sim = fuzz.token_sort_ratio(track_name.lower(), best.title.lower())

        return DiscoverySuggestion(
            lastfm_artist=artist,
            lastfm_track=track_name,
            matched_video_id=best.video_id,
            matched_title=best.title,
            matched_artist=search_artists[0] if search_artists else None,
            confidence=round(confidence, 1),
            artist_similarity=round(artist_sim, 1),
            title_similarity=round(title_sim, 1),
        )
