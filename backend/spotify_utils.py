"""
Spotify Track Matching Utilities
Core business logic for matching releases to Spotify albums

UPDATED: Recording-Centric Performer Architecture
- Spotify data (album art, URLs) is stored on RELEASES, not recordings
- Recordings have a default_release_id pointing to the best release for display
- The match_releases() method is the primary entry point

This module provides the SpotifyMatcher class which handles:
- Spotify API authentication and token management
- Fuzzy matching and validation of albums and tracks
- Album artwork extraction (stored on releases)
- Database updates for releases and recording_releases
- Setting default_release_id on recordings
- Caching of API responses to minimize rate limiting
- Intelligent rate limit handling with exponential backoff

Used by:
- scripts/match_spotify_releases.py (CLI interface)
- song_research.py (background worker)

REFACTORED: This module is now a facade that re-exports from:
- spotify_client.py: Authentication, rate limiting, caching
- spotify_matching.py: Text normalization and fuzzy matching
- spotify_db.py: Database operations
- spotify_matcher.py: Main SpotifyMatcher class
"""

# Re-export main class and exception
from spotify_matcher import SpotifyMatcher
from spotify_client import SpotifyRateLimitError

# Re-export commonly used utilities
from spotify_matching import (
    ENSEMBLE_SUFFIXES,
    strip_ensemble_suffix,
    normalize_for_comparison,
    calculate_similarity,
    is_substring_title_match,
    extract_primary_artist,
)

# For any code that imports the _CACHE_MISS sentinel
from spotify_client import _CACHE_MISS

__all__ = [
    'SpotifyMatcher',
    'SpotifyRateLimitError',
    'ENSEMBLE_SUFFIXES',
    'strip_ensemble_suffix',
    'normalize_for_comparison',
    'calculate_similarity',
    'is_substring_title_match',
    'extract_primary_artist',
    '_CACHE_MISS',
]