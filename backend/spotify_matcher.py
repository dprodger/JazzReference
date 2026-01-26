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
"""

import re
import logging
from typing import Dict, Any, Optional, List
import requests

from db_utils import get_db_connection

from spotify_client import SpotifyClient, SpotifyRateLimitError, _CACHE_MISS
from spotify_matching import (
    strip_ensemble_suffix,
    strip_live_suffix,
    normalize_for_comparison,
    normalize_for_search,
    calculate_similarity,
    is_substring_title_match,
    extract_primary_artist,
    validate_track_match,
    validate_album_match,
)
from spotify_db import (
    find_song_by_name,
    find_song_by_id,
    get_recordings_for_song,
    get_releases_for_song,
    get_releases_without_artwork,
    get_recordings_for_release,
    update_release_spotify_data,
    update_release_artwork,
    update_recording_release_track_id,
    update_recording_default_release,
    is_track_blocked,
    is_album_blocked,
)

logger = logging.getLogger(__name__)


class SpotifyMatcher:
    """
    Handles matching recordings to Spotify tracks with fuzzy validation and caching
    """
    
    def __init__(self, dry_run=False, strict_mode=False, force_refresh=False,
                 artist_filter=False, cache_days=30, logger=None,
                 rate_limit_delay=0.2, max_retries=3,
                 progress_callback=None, rematch=False, rematch_tracks=False,
                 rematch_all=False):
        """
        Initialize Spotify Matcher

        Args:
            dry_run: If True, show what would be matched without making changes
            artist_filter: Filter to recordings by specific artist
            strict_mode: If True, use stricter validation thresholds (recommended)
            logger: Optional logger instance (uses module logger if not provided)
            cache_days: Number of days before cache is considered stale
            force_refresh: If True, always fetch fresh data ignoring cache
            rate_limit_delay: Base delay between API calls (seconds)
            max_retries: Maximum number of retries for rate-limited requests
            progress_callback: Optional callback(phase, current, total) for progress tracking
            rematch: If True, re-evaluate releases that already have Spotify URLs
            rematch_tracks: If True, re-run track matching for releases with album IDs
            rematch_all: If True, full re-match from scratch - ignores existing track IDs too
        """
        self.dry_run = dry_run
        self.artist_filter = artist_filter
        self.strict_mode = strict_mode
        self.rematch = rematch
        self.rematch_tracks = rematch_tracks
        self.rematch_all = rematch_all
        self.logger = logger or logging.getLogger(__name__)
        self.progress_callback = progress_callback
        
        # Initialize the API client
        self.client = SpotifyClient(
            cache_days=cache_days,
            force_refresh=force_refresh,
            rate_limit_delay=rate_limit_delay,
            max_retries=max_retries,
            logger=self.logger
        )
        
        # Stats - updated for releases and tracks
        self.stats = {
            'recordings_processed': 0,
            'recordings_with_spotify': 0,
            'recordings_updated': 0,
            'recordings_no_match': 0,
            'recordings_skipped': 0,
            'recordings_rejected': 0,
            'releases_processed': 0,
            'releases_with_spotify': 0,
            'releases_updated': 0,
            'releases_no_match': 0,
            'releases_skipped': 0,
            'releases_blocked': 0,  # Albums blocked via bad_streaming_matches
            'tracks_matched': 0,
            'tracks_skipped': 0,
            'tracks_no_match': 0,
            'tracks_had_previous': 0,  # Tracks that had a match before but failed rematch
            'tracks_blocked': 0,  # Tracks blocked via bad_streaming_matches
            'errors': 0,
            'cache_hits': 0,
            'api_calls': 0,
            'rate_limit_hits': 0,
            'rate_limit_waits': 0
        }
        
        # Validation thresholds
        if strict_mode:
            self.min_artist_similarity = 75
            self.min_album_similarity = 65
            self.min_track_similarity = 85
        else:
            self.min_artist_similarity = 65
            self.min_album_similarity = 55
            self.min_track_similarity = 75
    
    def _aggregate_client_stats(self):
        """
        Aggregate statistics from the SpotifyClient into the matcher's stats.
        
        The client tracks cache_hits internally when loading from cache.
        This method synchronizes those stats before returning results.
        """
        self.stats['cache_hits'] = self.client.stats.get('cache_hits', 0)
        self.stats['rate_limit_hits'] = self.client.stats.get('rate_limit_hits', 0)
        self.stats['rate_limit_waits'] = self.client.stats.get('rate_limit_waits', 0)
    
    def _get_track_match_failure_cache_path(self, song_id: str, release_id: str, 
                                            spotify_album_id: str) -> 'Path':
        """
        Get cache path for track match failure results.
        
        This caches the result of "album matched but track not found" to avoid
        repeated DB queries on subsequent runs.
        """
        from pathlib import Path
        # Use the client's cache directory structure
        failure_cache_dir = self.client.cache_dir / 'track_failures'
        failure_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a deterministic filename from the three IDs (convert UUIDs to strings)
        filename = f"fail_{str(song_id)}_{str(release_id)}_{str(spotify_album_id)}.json"
        return failure_cache_dir / filename
    
    def _is_track_match_cached_failure(self, song_id: str, release_id: str,
                                       spotify_album_id: str) -> bool:
        """
        Check if we've already determined that track matching fails for this combination.
        
        Returns True if we have a cached "no match" result, False otherwise.
        """
        cache_path = self._get_track_match_failure_cache_path(song_id, release_id, spotify_album_id)
        
        if self.client.force_refresh:
            return False
        
        if not cache_path.exists():
            return False
        
        # Check if cache is still valid
        if self.client._is_cache_valid(cache_path):
            self.client.stats['cache_hits'] = self.client.stats.get('cache_hits', 0) + 1
            self.logger.debug(f"    Track match failure cache hit")
            return True
        
        return False
    
    def _cache_track_match_failure(self, song_id: str, release_id: str,
                                   spotify_album_id: str, song_title: str) -> None:
        """
        Cache the fact that track matching failed for this song/release/album combination.
        """
        import json
        cache_path = self._get_track_match_failure_cache_path(song_id, release_id, spotify_album_id)
        
        try:
            with open(cache_path, 'w') as f:
                json.dump({
                    'song_id': str(song_id),
                    'release_id': str(release_id),
                    'spotify_album_id': str(spotify_album_id),
                    'song_title': song_title,
                    'result': 'no_track_match'
                }, f)
            self.logger.debug(f"    Cached track match failure")
        except Exception as e:
            self.logger.warning(f"    Failed to cache track match failure: {e}")

    def _log_orphaned_track(self, release_id: str, recording_id: str, spotify_track_url: str):
        """
        Log details of a track that had a previous Spotify match but failed rematch.
        Appends to a CSV file in the current working directory for later investigation.
        """
        from datetime import datetime
        from pathlib import Path
        import csv

        log_file = Path('spotify_orphaned_tracks.csv')
        file_exists = log_file.exists()

        try:
            with open(log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                # Write header if file is new
                if not file_exists:
                    writer.writerow(['timestamp', 'release_id', 'recording_id', 'spotify_track_url'])
                writer.writerow([
                    datetime.now().isoformat(),
                    str(release_id),
                    str(recording_id),
                    spotify_track_url
                ])
        except Exception as e:
            self.logger.warning(f"    Failed to log orphaned track: {e}")

    # ========================================================================
    # DELEGATED PROPERTIES (for backwards compatibility)
    # ========================================================================
    
    @property
    def last_made_api_call(self):
        return self.client.last_made_api_call
    
    @last_made_api_call.setter
    def last_made_api_call(self, value):
        self.client.last_made_api_call = value
    
    # ========================================================================
    # MATCHING HELPER METHODS
    # ========================================================================
    
    def normalize_for_comparison(self, text: str) -> str:
        """Normalize text for fuzzy comparison"""
        return normalize_for_comparison(text)
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two strings"""
        return calculate_similarity(text1, text2)
    
    def is_substring_title_match(self, title1: str, title2: str) -> bool:
        """Check if one normalized title is a complete substring of the other"""
        return is_substring_title_match(title1, title2)
    
    def extract_primary_artist(self, artist_credit: str) -> str:
        """Extract the primary artist from a MusicBrainz artist_credit string"""
        return extract_primary_artist(artist_credit)
    
    def validate_match(self, spotify_track: dict, expected_song: str, 
                      expected_artist: str, expected_album: str) -> tuple:
        """Validate that a Spotify track result actually matches what we're looking for"""
        return validate_track_match(
            spotify_track, expected_song, expected_artist, expected_album,
            self.min_track_similarity, self.min_artist_similarity, self.min_album_similarity
        )
    
    def validate_album_match(self, spotify_album: dict, expected_album: str, 
                            expected_artist: str, song_title: str = None) -> tuple:
        """Validate that a Spotify album result actually matches what we're looking for"""
        return validate_album_match(
            spotify_album, expected_album, expected_artist,
            self.min_album_similarity, self.min_artist_similarity,
            song_title=song_title,
            verify_track_callback=self.verify_album_contains_track
        )
    
    def verify_album_contains_track(self, album_id: str, song_title: str) -> bool:
        """
        Verify that a Spotify album contains a track matching the song title.
        
        Used as a fallback validation when artist matching fails but album
        similarity is high. This handles compilation albums, "Various Artists",
        and artist name variations.
        
        Args:
            album_id: Spotify album ID
            song_title: Song title to search for in the album
            
        Returns:
            True if a matching track was found, False otherwise
        """
        tracks = self.get_album_tracks(album_id)
        if not tracks:
            return False
        
        for track in tracks:
            similarity = self.calculate_similarity(song_title, track['name'])
            if similarity >= self.min_track_similarity:
                self.logger.debug(f"      Track verification passed: '{track['name']}' ({similarity}%)")
                return True
        
        return False
    
    # ========================================================================
    # DATABASE METHODS (delegated)
    # ========================================================================
    
    def find_song_by_name(self, song_name: str) -> Optional[dict]:
        """Look up song by name"""
        return find_song_by_name(song_name)
    
    def find_song_by_id(self, song_id: str) -> Optional[dict]:
        """Look up song by ID"""
        return find_song_by_id(song_id)
    
    def get_recordings_for_song(self, song_id: str) -> List[dict]:
        """Get all recordings for a song, optionally filtered by artist"""
        return get_recordings_for_song(song_id, self.artist_filter)
    
    def get_releases_for_song(self, song_id: str) -> List[dict]:
        """Get all releases for a song, optionally filtered by artist"""
        return get_releases_for_song(song_id, self.artist_filter)
    
    def get_releases_without_artwork(self) -> List[dict]:
        """Get releases with Spotify URL but no cover artwork"""
        return get_releases_without_artwork()
    
    def get_recordings_for_release(self, song_id: str, release_id: str, conn=None) -> List[dict]:
        """Get recordings linked to a specific release for a specific song"""
        return get_recordings_for_release(song_id, release_id, conn=conn)
    
    def update_release_spotify_data(self, conn, release_id: str, spotify_data: dict,
                                    release_title: str = None, artist: str = None,
                                    year: int = None, index: int = None, total: int = None):
        """Update release with Spotify album URL, ID, and cover artwork"""
        update_release_spotify_data(conn, release_id, spotify_data, 
                                   dry_run=self.dry_run, log=self.logger)
        
        if not self.dry_run:
            if index and total and release_title:
                self.logger.info(f"[{index}/{total}] {release_title} ({artist or 'Unknown'}, {year or 'Unknown'}) - ✓ Updated with Spotify URL and cover artwork")
            else:
                self.logger.info(f"    ✓ Updated with Spotify URL and cover artwork")
            
            self.stats['releases_updated'] += 1
    
    def update_release_artwork(self, conn, release_id: str, album_art: dict):
        """Update release with cover artwork only"""
        update_release_artwork(conn, release_id, album_art, 
                              dry_run=self.dry_run, log=self.logger)
        if not self.dry_run:
            self.logger.info(f"    ✓ Updated with cover artwork")
            self.stats['releases_updated'] += 1
    
    def update_recording_release_track_id(self, conn, recording_id: str, release_id: str,
                                          track_id: str, track_url: str,
                                          disc_number: int = None, track_number: int = None,
                                          track_title: str = None):
        """Update the recording_releases junction table with Spotify track info"""
        update_recording_release_track_id(conn, recording_id, release_id, track_id, track_url,
                                         disc_number=disc_number, track_number=track_number,
                                         track_title=track_title,
                                         dry_run=self.dry_run, log=self.logger)
    
    def update_recording_default_release(self, conn, song_id: str, release_id: str):
        """Update recordings linked to a release to set it as their default_release"""
        update_recording_default_release(conn, song_id, release_id,
                                        dry_run=self.dry_run, log=self.logger)
    
    # ========================================================================
    # DEPRECATED METHODS (kept for backwards compatibility)
    # ========================================================================
    
    def get_recordings_without_images(self) -> List[dict]:
        """
        DEPRECATED: Album artwork is now stored on releases, not recordings.
        
        Use get_releases_without_artwork() instead.
        """
        self.logger.warning("get_recordings_without_images() is deprecated - artwork now stored on releases")
        return []
    
    def update_recording_artwork(self, conn, recording_id: str, album_art: dict):
        """
        DEPRECATED: Album artwork is now stored on releases, not recordings.
        
        This method is kept for backwards compatibility but does nothing.
        Use update_release_spotify_data() instead.
        """
        self.logger.warning("update_recording_artwork() is deprecated - artwork now stored on releases")
    
    def update_recording_spotify_url(self, conn, recording_id: str, spotify_data: dict, 
                                     album: str = None, artist: str = None, year: int = None,
                                     index: int = None, total: int = None):
        """
        DEPRECATED: Spotify URL and artwork are now stored on releases, not recordings.
        
        This method is kept for backwards compatibility but does nothing.
        Use update_release_spotify_data() and match_releases() instead.
        """
        self.logger.warning("update_recording_spotify_url() is deprecated - use match_releases() instead")
    
    def match_recordings(self, song_identifier: str) -> Dict[str, Any]:
        """
        Main method to match Spotify tracks for a song's recordings
        
        Args:
            song_identifier: Song name or database ID
            
        Returns:
            dict: {
                'success': bool,
                'song': dict (if found),
                'stats': dict,
                'error': str (if failed)
            }
        """
        # DEPRECATED: Redirect to match_releases
        self.logger.warning("match_recordings() is deprecated - redirecting to match_releases()")
        self.logger.info("Spotify data is now stored on releases, not recordings.")
        self.logger.info("Use match_releases() directly for better results.")
        self.logger.info("")
        
        return self.match_releases(song_identifier)
    
    # ========================================================================
    # SPOTIFY API METHODS
    # ========================================================================
    
    def get_spotify_auth_token(self) -> Optional[str]:
        """Get a valid Spotify access token"""
        return self.client.get_spotify_auth_token()
    
    def extract_track_id_from_url(self, spotify_url: str) -> Optional[str]:
        """Extract Spotify track ID from URL"""
        if not spotify_url:
            return None
        
        # Spotify URL format: https://open.spotify.com/track/{track_id}
        match = re.search(r'spotify\.com/track/([a-zA-Z0-9]+)', spotify_url)
        if match:
            return match.group(1)
        
        return None
    
    def get_track_details(self, track_id: str) -> Optional[dict]:
        """
        Get detailed information about a Spotify track by ID with caching
        
        Args:
            track_id: Spotify track ID
            
        Returns:
            Track data dict or None if not found
        """
        # Check cache first
        cache_path = self.client._get_track_cache_path(track_id)
        cached_data = self.client._load_from_cache(cache_path)
        
        if cached_data is not _CACHE_MISS:
            # Cache hit - return cached data (which might be None for "not found")
            return cached_data
        
        # Not in cache or cache expired - fetch from API
        token = self.client.get_spotify_auth_token()
        if not token:
            return None
        
        try:
            response = self.client._make_api_request(
                'get',
                f'https://api.spotify.com/v1/tracks/{track_id}',
                headers={'Authorization': f'Bearer {token}'},
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Track API call
            self.stats['api_calls'] += 1
            self.client.last_made_api_call = True
            
            # Save to cache
            self.client._save_to_cache(cache_path, data)
            
            return data
            
        except SpotifyRateLimitError as e:
            self.logger.error(f"Rate limit exceeded fetching track details: {e}")
            return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # Cache the "not found" result
                self.client._save_to_cache(cache_path, None)
                return None
            self.logger.error(f"Spotify API error: {e}")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch track details: {e}")
            return None
    
    def get_album_details(self, album_id: str) -> Optional[dict]:
        """
        Fetch album details from Spotify
        
        Args:
            album_id: Spotify album ID
            
        Returns:
            Album dict or None if failed
        """
        # Check cache first
        cache_path = self.client._get_album_cache_path(f"{album_id}_details")
        cached_result = self.client._load_from_cache(cache_path)
        
        if cached_result is not _CACHE_MISS:
            return cached_result
        
        token = self.client.get_spotify_auth_token()
        if not token:
            return None
        
        try:
            response = self.client._make_api_request(
                'get',
                f'https://api.spotify.com/v1/albums/{album_id}',
                headers={'Authorization': f'Bearer {token}'},
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()
            
            self.stats['api_calls'] += 1
            self.client.last_made_api_call = True
            
            self.client._save_to_cache(cache_path, data)
            return data
            
        except SpotifyRateLimitError as e:
            self.logger.error(f"Rate limit exceeded fetching album: {e}")
            return None
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"Spotify API error fetching album: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching album: {e}")
            return None
    
    def get_album_tracks(self, album_id: str) -> Optional[List[dict]]:
        """
        Fetch all tracks from a Spotify album, handling pagination for large albums.

        Args:
            album_id: Spotify album ID

        Returns:
            List of track dicts with 'id', 'name', 'track_number', 'disc_number', 'url'
            or None if failed
        """
        # Check cache first
        cache_path = self.client._get_album_cache_path(album_id)
        cached_result = self.client._load_from_cache(cache_path)

        if cached_result is not _CACHE_MISS:
            return cached_result

        token = self.client.get_spotify_auth_token()
        if not token:
            return None

        try:
            tracks = []
            url = f'https://api.spotify.com/v1/albums/{album_id}/tracks'
            params = {'limit': 50}

            # Paginate through all tracks
            while url:
                response = self.client._make_api_request(
                    'get',
                    url,
                    headers={'Authorization': f'Bearer {token}'},
                    params=params if 'offset' not in url else None,  # params only for first request
                    timeout=10
                )

                response.raise_for_status()
                data = response.json()

                self.stats['api_calls'] += 1
                self.client.last_made_api_call = True

                for item in data.get('items', []):
                    tracks.append({
                        'id': item['id'],
                        'name': item['name'],
                        'track_number': item['track_number'],
                        'disc_number': item['disc_number'],
                        'url': item['external_urls']['spotify']
                    })

                # Get next page URL (None if no more pages)
                url = data.get('next')

            self.logger.debug(f"    Fetched {len(tracks)} total tracks from album")
            self.client._save_to_cache(cache_path, tracks)
            return tracks

        except SpotifyRateLimitError as e:
            self.logger.error(f"Rate limit exceeded fetching album tracks: {e}")
            return None
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"Spotify API error fetching album tracks: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching album tracks: {e}")
            return None
    
    def search_spotify_track(self, song_title: str, album_title: str, 
                            artist_name: str = None, year: int = None) -> Optional[dict]:
        """
        Search Spotify for a track with fuzzy validation and progressive search strategy.
        Uses caching to minimize API calls.
        
        Args:
            song_title: Song title to search for
            album_title: Album title
            artist_name: Artist name (optional, but recommended)
            year: Recording year (optional)
            
        Returns:
            dict with 'url', 'id', 'artists', 'album', 'album_art', 'similarity_scores'
            or None if no valid match found
        """
        # Check cache first
        cache_path = self.client._get_search_cache_path(song_title, album_title, artist_name, year)
        cached_result = self.client._load_from_cache(cache_path)
        
        if cached_result is not _CACHE_MISS:
            # Cache hit - return cached result (which might be None for "no match found")
            return cached_result
        
        # Not in cache - perform search
        token = self.client.get_spotify_auth_token()
        if not token:
            self.client._save_to_cache(cache_path, None)
            return None
        
        # Progressive search strategy
        # Start with specific queries, fall back to broader searches
        search_strategies = []

        # Normalize search terms (convert en-dashes to hyphens, etc.)
        search_song = normalize_for_search(song_title)
        search_album = normalize_for_search(album_title)
        search_artist = normalize_for_search(artist_name) if artist_name else None

        # Check if we should try a stripped artist name as fallback
        stripped_artist = strip_ensemble_suffix(search_artist) if search_artist else None
        has_stripped_fallback = stripped_artist and stripped_artist != search_artist

        if search_artist and year:
            search_strategies.append({
                'query': f'track:"{search_song}" artist:"{search_artist}" album:"{search_album}" year:{year}',
                'description': 'exact track, artist, album, and year'
            })

        if search_artist:
            search_strategies.append({
                'query': f'track:"{search_song}" artist:"{search_artist}" album:"{search_album}"',
                'description': 'exact track, artist, and album'
            })
            search_strategies.append({
                'query': f'track:"{search_song}" artist:"{search_artist}"',
                'description': 'exact track and artist'
            })

        # Fallback: try with ensemble suffix stripped (e.g., "Bill Evans Trio" -> "Bill Evans")
        if has_stripped_fallback:
            search_strategies.append({
                'query': f'track:"{search_song}" artist:"{stripped_artist}" album:"{search_album}"',
                'description': f'exact track, stripped artist ({stripped_artist}), and album'
            })
            search_strategies.append({
                'query': f'track:"{search_song}" artist:"{stripped_artist}"',
                'description': f'exact track and stripped artist ({stripped_artist})'
            })

        search_strategies.append({
            'query': f'track:"{search_song}" album:"{search_album}"',
            'description': 'exact track and album'
        })

        search_strategies.append({
            'query': f'track:"{search_song}"',
            'description': 'exact track only'
        })
        
        # Try each search strategy until we get a valid match
        for strategy in search_strategies:
            try:
                self.logger.debug(f"  → Trying: {strategy['description']}")
                
                response = self.client._make_api_request(
                    'get',
                    'https://api.spotify.com/v1/search',
                    headers={'Authorization': f'Bearer {token}'},
                    params={
                        'q': strategy['query'],
                        'type': 'track',
                        'limit': 5  # Get top 5 results for validation
                    },
                    timeout=10
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Track API call
                self.stats['api_calls'] += 1
                self.client.last_made_api_call = True
                
                tracks = data.get('tracks', {}).get('items', [])
                
                if tracks:
                    self.logger.debug(f"    Found {len(tracks)} candidates")
                    
                    # Try to validate each candidate
                    for i, track in enumerate(tracks):
                        is_valid, reason, scores = self.validate_match(
                            track, song_title, artist_name or '', album_title
                        )
                        
                        if is_valid:
                            # Extract album artwork URLs
                            album_art = {}
                            images = track['album'].get('images', [])
                            
                            for image in images:
                                height = image.get('height', 0)
                                if height >= 600:
                                    album_art['large'] = image['url']
                                elif height >= 300:
                                    album_art['medium'] = image['url']
                                elif height >= 64:
                                    album_art['small'] = image['url']
                            
                            # Build result
                            track_artists = [a['name'] for a in track['artists']]
                            track_album = track['album']['name']
                            
                            result = {
                                'url': track['external_urls']['spotify'],
                                'id': track['id'],
                                'artists': track_artists,
                                'album': track_album,
                                'album_art': album_art,
                                'similarity_scores': scores
                            }
                            
                            # Cache successful result
                            self.client._save_to_cache(cache_path, result)
                            
                            self.logger.debug(f"    ✓ Valid match found (candidate #{i+1})")
                            return result
                        else:
                            self.logger.debug(f"    ✗ Candidate #{i+1} rejected: {reason}")
                            self.logger.debug(f"       Expected: '{song_title}' by {artist_name} on '{album_title}'")
                            self.logger.debug(f"       Found: '{scores['spotify_song']}' by {scores['spotify_artist']} on '{scores['spotify_album']}'")
                            if scores.get('artist_best_individual'):
                                self.logger.debug(f"       Artist match scores - Individual: {scores['artist_best_individual']}%, Full string: {scores['artist_full_string']}%")
                            if scores['album']:
                                self.logger.debug(f"       Album similarity: {scores['album']}%")
                    
                    self.logger.debug(f"    ✗ No valid matches with {strategy['description']}")
                else:
                    self.logger.debug(f"    ✗ No results with {strategy['description']}")
                    
            except SpotifyRateLimitError as e:
                self.logger.error(f"Rate limit exceeded during search: {e}")
                # Don't cache rate limit errors - might succeed later
                return None
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    self.client.access_token = None
                    self.logger.warning("Spotify token expired, will refresh on next request")
                    # Don't cache auth failures
                    return None
                self.logger.error(f"Spotify search failed: {e}")
                # Don't cache errors
                return None
            except Exception as e:
                self.logger.error(f"Error searching Spotify: {e}")
                # Don't cache errors
                return None
        
        self.logger.debug(f"    ✗ No valid Spotify matches found after trying all strategies")
        
        # Cache the "no match" result
        self.client._save_to_cache(cache_path, None)
        
        return None
    
    def search_spotify_album(self, album_title: str, artist_name: str = None, 
                              song_title: str = None) -> Optional[dict]:
        """
        Search Spotify for an album with fuzzy validation.
        
        Args:
            album_title: Album title to search for
            artist_name: Artist name (optional, but recommended)
            song_title: Song title for track verification fallback (optional).
                       When provided, albums with high similarity but low artist
                       match can still be accepted if they contain this track.
            
        Returns:
            dict with 'url', 'id', 'artists', 'name', 'album_art', 'similarity_scores'
            or None if no valid match found
        """
        # Check cache first (reuse search cache with 'album' prefix)
        cache_path = self.client._get_search_cache_path('album', album_title, artist_name)
        cached_result = self.client._load_from_cache(cache_path)
        
        if cached_result is not _CACHE_MISS:
            return cached_result
        
        token = self.client.get_spotify_auth_token()
        if not token:
            self.client._save_to_cache(cache_path, None)
            return None
        
        # Progressive search strategy
        search_strategies = []

        # Normalize album title for search (convert en-dashes to hyphens, etc.)
        search_album = normalize_for_search(album_title)
        search_artist = normalize_for_search(artist_name) if artist_name else None

        # Truncate very long artist names to avoid Spotify API 400 errors
        # (Some releases have absurdly long artist credits with full orchestra rosters)
        MAX_ARTIST_LENGTH = 100
        if search_artist and len(search_artist) > MAX_ARTIST_LENGTH:
            # Try to truncate at a natural break point (comma, hyphen, etc.)
            truncated = search_artist[:MAX_ARTIST_LENGTH]
            for sep in [', ', ' - ', ' & ', ' and ']:
                if sep in truncated:
                    truncated = truncated.rsplit(sep, 1)[0]
                    break
            self.logger.debug(f"  Truncated long artist name: '{search_artist[:50]}...' -> '{truncated}'")
            search_artist = truncated

        # Check if album title has a live suffix we can strip (e.g., "Solo: Live" -> "Solo")
        stripped_album = strip_live_suffix(search_album)
        has_stripped_album = stripped_album != search_album

        if search_artist:
            search_strategies.append({
                'query': f'album:"{search_album}" artist:"{search_artist}"',
                'description': 'exact album and artist'
            })
            search_strategies.append({
                'query': f'"{search_album}" "{search_artist}"',
                'description': 'quoted album and artist'
            })

            # Try with ensemble suffix stripped (e.g., "Bill Evans Trio" -> "Bill Evans")
            stripped_artist = strip_ensemble_suffix(search_artist)
            if stripped_artist != search_artist:
                search_strategies.append({
                    'query': f'album:"{search_album}" artist:"{stripped_artist}"',
                    'description': f'exact album with stripped artist ({stripped_artist})'
                })
                search_strategies.append({
                    'query': f'"{search_album}" "{stripped_artist}"',
                    'description': f'quoted album with stripped artist ({stripped_artist})'
                })

            # Try with live suffix stripped from album (e.g., "Solo: Live" -> "Solo")
            if has_stripped_album:
                search_strategies.append({
                    'query': f'album:"{stripped_album}" artist:"{search_artist}"',
                    'description': f'stripped album ({stripped_album}) and artist'
                })
                search_strategies.append({
                    'query': f'"{stripped_album}" "{search_artist}"',
                    'description': f'quoted stripped album ({stripped_album}) and artist'
                })

        search_strategies.append({
            'query': f'album:"{search_album}"',
            'description': 'exact album only'
        })

        # Fallback: stripped album only
        if has_stripped_album:
            search_strategies.append({
                'query': f'album:"{stripped_album}"',
                'description': f'stripped album only ({stripped_album})'
            })
        
        for strategy in search_strategies:
            try:
                self.logger.debug(f"  → Trying: {strategy['description']}")
                
                response = self.client._make_api_request(
                    'get',
                    'https://api.spotify.com/v1/search',
                    headers={'Authorization': f'Bearer {token}'},
                    params={
                        'q': strategy['query'],
                        'type': 'album',
                        'limit': 10
                    },
                    timeout=10
                )

                response.raise_for_status()
                data = response.json()

                self.stats['api_calls'] += 1
                self.client.last_made_api_call = True

                albums = data.get('albums', {}).get('items', [])

                if albums:
                    self.logger.debug(f"    Found {len(albums)} candidates")

                    # Normalize expected album title for exact matching
                    expected_normalized = album_title.lower().strip()

                    # FIRST PASS: Look for exact album title matches
                    # This prioritizes "Julie" over "Julie Is Her Name" when searching for "Julie"
                    exact_matches = []
                    for i, album in enumerate(albums):
                        spotify_album_normalized = album['name'].lower().strip()
                        if spotify_album_normalized == expected_normalized:
                            # Validate artist match for this exact title match
                            is_valid, reason, scores = self.validate_album_match(
                                album, album_title, artist_name or '', song_title
                            )
                            exact_matches.append({
                                'index': i,
                                'album': album,
                                'is_valid': is_valid,
                                'reason': reason,
                                'scores': scores
                            })

                    if exact_matches:
                        self.logger.debug(f"    Found {len(exact_matches)} exact title match(es)")
                        # Check if any exact match also passes artist validation
                        for em in exact_matches:
                            if em['is_valid']:
                                self.logger.debug(f"    ✓ Exact match found: '{em['album']['name']}' (#{em['index']+1})")
                                album = em['album']
                                scores = em['scores']

                                # Extract album artwork
                                album_art = {}
                                images = album.get('images', [])
                                for image in images:
                                    height = image.get('height', 0)
                                    if height >= 600:
                                        album_art['large'] = image['url']
                                    elif height >= 300:
                                        album_art['medium'] = image['url']
                                    elif height >= 64:
                                        album_art['small'] = image['url']

                                album_artists = [a['name'] for a in album['artists']]
                                result = {
                                    'url': album['external_urls']['spotify'],
                                    'id': album['id'],
                                    'artists': album_artists,
                                    'name': album['name'],
                                    'album_art': album_art,
                                    'similarity_scores': scores
                                }
                                self.client._save_to_cache(cache_path, result)
                                return result

                        # Exact title matches exist but failed artist validation
                        self.logger.debug(f"    Exact matches failed artist validation, trying fuzzy matching...")

                    # SECOND PASS: Fuzzy matching (original logic)
                    # Evaluate ALL candidates, collect results
                    candidate_results = []
                    for i, album in enumerate(albums):
                        is_valid, reason, scores = self.validate_album_match(
                            album, album_title, artist_name or '', song_title
                        )
                        candidate_results.append({
                            'index': i,
                            'album': album,
                            'is_valid': is_valid,
                            'reason': reason,
                            'scores': scores
                        })

                    # Log summary of ALL candidates
                    self.logger.debug(f"    --- Candidate Summary ---")
                    for cr in candidate_results:
                        status = "✓" if cr['is_valid'] else "✗"
                        album_sim = cr['scores'].get('album', 0)
                        artist_sim = cr['scores'].get('artist', 0)
                        spotify_album = cr['scores'].get('spotify_album', '')
                        self.logger.debug(f"    {status} #{cr['index']+1}: '{spotify_album}' "
                                        f"(album: {album_sim:.0f}%, artist: {artist_sim:.0f}%)")
                    self.logger.debug(f"    -------------------------")

                    # Select first valid match from fuzzy results
                    for cr in candidate_results:
                        if cr['is_valid']:
                            album = cr['album']
                            scores = cr['scores']
                            
                            # Log the match details
                            self.logger.debug(f"       Matched: '{scores.get('spotify_album', '')}' by {scores.get('spotify_artist', '')}")
                            self.logger.debug(f"       Album similarity: {scores.get('album', 0):.1f}% (substring: {scores.get('album_is_substring', False)})")
                            self.logger.debug(f"       Artist similarity: {scores.get('artist', 0):.1f}% (substring: {scores.get('artist_is_substring', False)})")
                            
                            # Extract album artwork
                            album_art = {}
                            images = album.get('images', [])
                            
                            for image in images:
                                height = image.get('height', 0)
                                if height >= 600:
                                    album_art['large'] = image['url']
                                elif height >= 300:
                                    album_art['medium'] = image['url']
                                elif height >= 64:
                                    album_art['small'] = image['url']
                            
                            album_artists = [a['name'] for a in album['artists']]
                            
                            result = {
                                'url': album['external_urls']['spotify'],
                                'id': album['id'],
                                'artists': album_artists,
                                'name': album['name'],
                                'album_art': album_art,
                                'similarity_scores': scores
                            }
                            
                            self.client._save_to_cache(cache_path, result)
                            self.logger.debug(f"    ✓ Valid match found (candidate #{cr['index']+1})")
                            return result
                    
                    self.logger.debug(f"    ✗ No valid matches with {strategy['description']}")
                else:
                    self.logger.debug(f"    ✗ No results with {strategy['description']}")
                 
            except SpotifyRateLimitError as e:
                self.logger.error(f"Rate limit exceeded during search: {e}")
                return None
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    self.client.access_token = None
                    return None
                self.logger.error(f"Spotify search failed: {e}")
                return None
            except Exception as e:
                self.logger.error(f"Error searching Spotify: {e}")
                return None
        
        self.logger.debug(f"    ✗ No valid Spotify matches found after trying all strategies")
        self.client._save_to_cache(cache_path, None)
        return None
    
    # ========================================================================
    # MAIN ORCHESTRATION METHODS
    # ========================================================================
    
    def match_releases(self, song_identifier: str, start_from: int = 1) -> Dict[str, Any]:
        """
        Main method to match Spotify albums for a song's releases

        Args:
            song_identifier: Song name or database ID
            start_from: Release number to start from (1-indexed). Use this to resume
                       after a previous run was interrupted. Releases before this
                       number will be skipped.

        Returns:
            dict: {
                'success': bool,
                'song': dict (if found),
                'stats': dict,
                'error': str (if failed)
            }
        """
        try:
            # Find the song
            if song_identifier.startswith('song-') or len(song_identifier) == 36:
                song = self.find_song_by_id(song_identifier)
            else:
                song = self.find_song_by_name(song_identifier)
            
            if not song:
                return {
                    'success': False,
                    'error': 'Song not found'
                }
            
            self.logger.info(f"Song: {song['title']}")
            self.logger.info(f"Composer: {song['composer']}")
            self.logger.info(f"Database ID: {song['id']}")
            if song.get('alt_titles'):
                self.logger.info(f"Alt titles: {song['alt_titles']}")
            if self.artist_filter:
                self.logger.info(f"Filtering to releases by: {self.artist_filter}")
            self.logger.info("")
            
            # Get releases
            releases = self.get_releases_for_song(song['id'])
            
            if not releases:
                return {
                    'success': False,
                    'song': song,
                    'error': 'No releases found for this song'
                }
            
            self.logger.info(f"Found {len(releases)} releases to process")
            if start_from > 1:
                self.logger.info(f"Resuming from release #{start_from} (skipping first {start_from - 1})")
            self.logger.info("")

            # Process each release
            for i, release in enumerate(releases, 1):
                # Skip releases before start_from (for resuming interrupted runs)
                if i < start_from:
                    continue

                self.stats['releases_processed'] += 1

                # Report progress via callback
                if self.progress_callback:
                    self.progress_callback('spotify_track_match', i, len(releases))
                
                title = release['title'] or 'Unknown Album'
                year = release['release_year']
                
                # Get artist - prefer artist_credit (full credit from MusicBrainz release)
                # This preserves ensemble names like "Gene Krupa & His Orchestra"
                # which would otherwise be truncated by extract_primary_artist
                artist_credit = release.get('artist_credit')
                artist_name = artist_credit

                if not artist_name:
                    performers = release.get('performers') or []
                    leaders = [p['name'] for p in performers if p.get('role') == 'leader']
                    artist_name = leaders[0] if leaders else (
                        performers[0]['name'] if performers else None
                    )
                
                self.logger.debug(f"[{i}/{len(releases)}] {title}")
                self.logger.debug(f"    Artist: {artist_name or 'Unknown'}")
                self.logger.debug(f"    Year: {year or 'Unknown'}")
                
                # Check if already has Spotify ID (skip unless rematch or rematch_tracks mode)
                if release.get('spotify_album_id') and not self.rematch and not self.rematch_tracks:
                    self.logger.info(f"[{i}/{len(releases)}] {title} ({artist_name or 'Unknown'}, {year or 'Unknown'}) - ⊙ Already has Spotify ID, skipping")
                    self.stats['releases_skipped'] += 1
                    continue
                elif release.get('spotify_album_id') and self.rematch_tracks and not self.rematch_all:
                    # rematch_tracks mode (not rematch_all): Re-run track matching for releases with album IDs
                    # but only if there are recordings missing track IDs
                    existing_album_id = release.get('spotify_album_id')
                    recordings = self.get_recordings_for_release(song['id'], release['id'])
                    needs_track_match = any(not r.get('spotify_track_id') for r in recordings)

                    if not needs_track_match:
                        self.logger.debug(f"[{i}/{len(releases)}] {title} ({artist_name or 'Unknown'}, {year or 'Unknown'}) - ⊙ All tracks already matched, skipping")
                        self.stats['releases_skipped'] += 1
                        continue

                    self.logger.info(f"[{i}/{len(releases)}] {title} ({artist_name or 'Unknown'}, {year or 'Unknown'}) - ↻ Re-matching tracks...")
                    # Fetch Spotify tracks BEFORE opening DB connection
                    # to avoid holding the connection idle during API calls
                    spotify_tracks = self.get_album_tracks(existing_album_id)
                    if not spotify_tracks:
                        self.logger.info(f"[{i}/{len(releases)}] {title} ({artist_name or 'Unknown'}, {year or 'Unknown'}) - ✗ Could not fetch Spotify album tracks")
                        self.stats['releases_no_match'] += 1
                        continue

                    with get_db_connection() as conn:
                        track_matched = self.match_tracks_for_release(
                            conn,
                            song['id'],
                            release['id'],
                            existing_album_id,
                            song['title'],
                            alt_titles=song.get('alt_titles'),
                            spotify_tracks=spotify_tracks
                        )
                        if track_matched:
                            self.stats['releases_with_spotify'] += 1
                        else:
                            self.stats['releases_no_match'] += 1
                    continue
                elif release.get('spotify_album_id') and self.rematch_all:
                    # rematch_all mode: Re-search for album AND re-match all tracks
                    self.logger.info(f"[{i}/{len(releases)}] {title} ({artist_name or 'Unknown'}, {year or 'Unknown'}) - ↻ Full re-match...")
                    # Fall through to album search below
                elif release.get('spotify_album_id') and self.rematch:
                    self.logger.info(f"[{i}/{len(releases)}] {title} ({artist_name or 'Unknown'}, {year or 'Unknown'}) - ↻ Re-matching...")
                elif self.rematch_tracks and not self.rematch_all and not release.get('spotify_album_id'):
                    # In rematch_tracks mode (not rematch_all), skip releases without album IDs
                    self.logger.debug(f"[{i}/{len(releases)}] {title} ({artist_name or 'Unknown'}, {year or 'Unknown'}) - ⊙ No album ID, skipping (rematch-tracks mode)")
                    self.stats['releases_skipped'] += 1
                    continue

                # Search Spotify for album (with song title for track verification fallback)
                spotify_match = self.search_spotify_album(title, artist_name, song['title'])

                if spotify_match:
                    # Check if this album is blocked for this song
                    if is_album_blocked(song['id'], spotify_match['id']):
                        self.logger.info(f"[{i}/{len(releases)}] {title} ({artist_name or 'Unknown'}, {year or 'Unknown'}) - ⊘ Album blocked (in blocklist)")
                        self.stats['releases_blocked'] += 1
                        continue
                    # Check if we already know track matching fails for this combination
                    # This avoids opening a DB connection just to reach the same "no match" conclusion
                    # Skip this cache check in rematch_all mode
                    if not self.rematch_all and self._is_track_match_cached_failure(song['id'], release['id'], spotify_match['id']):
                        self.logger.info(f"[{i}/{len(releases)}] {title} ({artist_name or 'Unknown'}, {year or 'Unknown'}) - ✗ Album matched but track not found (cached)")
                        self.stats['releases_no_match'] += 1
                        continue
                    
                    # IMPORTANT: Fetch Spotify tracks BEFORE opening DB connection
                    # to avoid holding the connection idle during API calls
                    # (Supabase's PgBouncer has ~6 min idle timeout)
                    spotify_tracks = self.get_album_tracks(spotify_match['id'])
                    if not spotify_tracks:
                        self.logger.info(f"[{i}/{len(releases)}] {title} ({artist_name or 'Unknown'}, {year or 'Unknown'}) - ✗ Could not fetch Spotify album tracks")
                        self.stats['releases_no_match'] += 1
                        continue

                    with get_db_connection() as conn:
                        # Match tracks using pre-fetched data (no API calls inside DB transaction)
                        track_matched = self.match_tracks_for_release(
                            conn,
                            song['id'],
                            release['id'],
                            spotify_match['id'],
                            song['title'],
                            alt_titles=song.get('alt_titles'),
                            spotify_tracks=spotify_tracks
                        )

                        if track_matched:
                            # Only store album data if track was found (validates album match)
                            self.stats['releases_with_spotify'] += 1
                            self.update_release_spotify_data(
                                conn,
                                release['id'],
                                spotify_match,
                                title,
                                artist_name,
                                year,
                                i,
                                len(releases)
                            )
                            
                            # NEW: Set this as the default release for linked recordings
                            # (only if they don't already have a better default)
                            self.update_recording_default_release(
                                conn,
                                song['id'],
                                release['id']
                            )
                        else:
                            # Album matched but no track found - cache this for future runs
                            self._cache_track_match_failure(
                                song['id'], release['id'], spotify_match['id'], song['title']
                            )
                            self.logger.info(f"[{i}/{len(releases)}] {title} ({artist_name or 'Unknown'}, {year or 'Unknown'}) - ✗ Album matched but track not found (possible false positive)")
                            self.stats['releases_no_match'] += 1
                else:
                    self.logger.info(f"[{i}/{len(releases)}] {title} ({artist_name or 'Unknown'}, {year or 'Unknown'}) - ✗ No valid Spotify match found")
                    self.stats['releases_no_match'] += 1
            
            self._aggregate_client_stats()
            return {
                'success': True,
                'song': song,
                'stats': self.stats
            }
            
        except Exception as e:
            self.logger.error(f"Error matching releases: {e}", exc_info=True)
            self._aggregate_client_stats()
            return {
                'success': False,
                'error': str(e),
                'stats': self.stats
            }
    
    def match_track_to_recording(self, song_title: str, spotify_tracks: List[dict],
                                   expected_disc: int = None, expected_track: int = None,
                                   alt_titles: List[str] = None,
                                   song_id: str = None, conn=None) -> Optional[dict]:
        """
        Find the best matching Spotify track for a song title

        Args:
            song_title: The song title to match
            spotify_tracks: List of track dicts from get_album_tracks()
            expected_disc: Expected disc number (optional, for position-based fallback)
            expected_track: Expected track number (optional, for position-based fallback)
            alt_titles: Alternative titles to try if primary title doesn't match
            song_id: Our database song ID (for blocklist checking)
            conn: Optional existing database connection. If provided, uses it
                  instead of opening a new connection (avoids idle connection
                  timeout issues when called from within a transaction).

        Returns:
            Best matching track dict or None if no good match
        """
        best_match = None
        best_score = 0

        # Build set of blocked track IDs for this song (more efficient than per-track DB calls)
        blocked_track_ids = set()
        if song_id:
            from spotify_db import get_blocked_tracks_for_song
            blocked_track_ids = set(get_blocked_tracks_for_song(song_id, conn=conn))
            if blocked_track_ids:
                self.logger.debug(f"      Found {len(blocked_track_ids)} blocked track(s) for this song")

        # First pass: standard fuzzy matching with primary title
        for track in spotify_tracks:
            # Check if this track is blocked for this song
            if track['id'] in blocked_track_ids:
                self.logger.debug(f"      Skipping blocked track: {track['id']} ('{track['name']}')")
                self.stats['tracks_blocked'] += 1
                continue

            score = self.calculate_similarity(song_title, track['name'])

            if score > best_score and score >= self.min_track_similarity:
                best_score = score
                best_match = track

        if best_match:
            self.logger.debug(f"      Track match: '{song_title}' → '{best_match['name']}' ({best_score}%)")
            return best_match

        # Second pass: try alternative titles
        if alt_titles:
            for alt_title in alt_titles:
                for track in spotify_tracks:
                    # Check if this track is blocked for this song
                    if track['id'] in blocked_track_ids:
                        continue

                    score = self.calculate_similarity(alt_title, track['name'])

                    if score > best_score and score >= self.min_track_similarity:
                        best_score = score
                        best_match = track

                if best_match:
                    self.logger.debug(f"      Track match via alt title: '{alt_title}' → '{best_match['name']}' ({best_score}%)")
                    return best_match

        # Fallback: if positions provided and no fuzzy match, try position-based substring match
        # This handles cases like "An Affair to Remember" vs
        # "An Affair to Remember - From the 20th Century-Fox Film, An Affair To Remember"
        if expected_disc is not None and expected_track is not None:
            for track in spotify_tracks:
                # Check if this track is blocked for this song
                if track['id'] in blocked_track_ids:
                    continue

                # Check if track position matches exactly
                if track.get('disc_number') == expected_disc and track.get('track_number') == expected_track:
                    # Position matches - try substring matching with primary title
                    if self.is_substring_title_match(song_title, track['name']):
                        self.logger.debug(f"      Position+substring match: '{song_title}' → '{track['name']}' "
                                        f"(disc {expected_disc}, track {expected_track})")
                        return track

                    # Also try substring matching with alt titles
                    if alt_titles:
                        for alt_title in alt_titles:
                            if self.is_substring_title_match(alt_title, track['name']):
                                self.logger.debug(f"      Position+substring match via alt title: '{alt_title}' → '{track['name']}' "
                                                f"(disc {expected_disc}, track {expected_track})")
                                return track

        return best_match
    
    def match_tracks_for_release(self, conn, song_id: str, release_id: str,
                                  spotify_album_id: str, song_title: str,
                                  alt_titles: List[str] = None,
                                  spotify_tracks: List[dict] = None) -> bool:
        """
        Match Spotify tracks to recordings for a release

        After we've matched a release to a Spotify album, this method:
        1. Fetches all tracks from the Spotify album (or uses pre-fetched tracks)
        2. Gets our recordings linked to this release
        3. Fuzzy matches the song title to find the right track
        4. Updates the recording_releases junction table with the track ID

        Args:
            conn: Database connection
            song_id: Our song ID
            release_id: Our release ID
            spotify_album_id: Spotify album ID we matched to
            song_title: The song title to search for
            alt_titles: Alternative titles to try if primary doesn't match
            spotify_tracks: Pre-fetched Spotify tracks (optional). If provided, skips
                           the API call. IMPORTANT: Pass this when calling from within
                           a DB transaction to avoid holding the connection idle during
                           API calls (which can cause connection timeouts).

        Returns:
            bool: True if at least one track was matched, False otherwise
        """
        # Get tracks from Spotify album (use pre-fetched if provided)
        if spotify_tracks is None:
            spotify_tracks = self.get_album_tracks(spotify_album_id)
        if not spotify_tracks:
            self.logger.debug(f"    Could not fetch tracks for album {spotify_album_id}")
            return False
        
        self.logger.debug(f"    Matching tracks ({len(spotify_tracks)} tracks in album)...")
        
        # Get our recordings for this release (use existing connection to avoid idle timeout)
        recordings = self.get_recordings_for_release(song_id, release_id, conn=conn)

        any_matched = False
        for recording in recordings:
            # Skip if already has a track ID (unless rematch_all mode)
            if recording['spotify_track_id'] and not self.rematch_all:
                self.logger.debug(f"      Recording already has track ID, skipping")
                self.stats['tracks_skipped'] += 1
                any_matched = True  # Consider already-matched as success
                continue
            elif recording['spotify_track_id'] and self.rematch_all:
                self.logger.debug(f"      Recording has track ID but rematch_all mode, re-matching...")
            
            # Match song title to a track, passing position info for fallback matching
            # Pass conn to avoid nested connections and idle timeout issues
            matched_track = self.match_track_to_recording(
                song_title,
                spotify_tracks,
                expected_disc=recording.get('disc_number'),
                expected_track=recording.get('track_number'),
                alt_titles=alt_titles,
                song_id=song_id,
                conn=conn
            )
            
            if matched_track:
                self.update_recording_release_track_id(
                    conn,
                    recording['recording_id'],
                    release_id,
                    matched_track['id'],
                    matched_track['url'],
                    disc_number=matched_track.get('disc_number'),
                    track_number=matched_track.get('track_number'),
                    track_title=matched_track.get('name')
                )
                self.stats['tracks_matched'] += 1
                any_matched = True
            else:
                # Show what tracks are on the album to help debug
                track_names = [t['name'] for t in spotify_tracks[:8]]
                more = f"... (+{len(spotify_tracks) - 8} more)" if len(spotify_tracks) > 8 else ""
                self.logger.debug(f"      No track match for '{song_title}'")
                if alt_titles:
                    self.logger.debug(f"      Also tried alt titles: {alt_titles}")
                self.logger.debug(f"      Album tracks: {track_names}{more}")
                self.stats['tracks_no_match'] += 1

                # Check if this recording had a previous match that would now be lost
                if recording.get('spotify_track_id'):
                    self.stats['tracks_had_previous'] += 1
                    previous_track_id = recording['spotify_track_id']
                    previous_url = f"https://open.spotify.com/track/{previous_track_id}"
                    self.logger.warning(f"      ⚠ Had previous track ID: {previous_track_id} (would be orphaned)")

                    # Log to file for later investigation/cleanup
                    self._log_orphaned_track(
                        release_id=release_id,
                        recording_id=recording['recording_id'],
                        spotify_track_url=previous_url
                    )
        
        return any_matched
    
    def backfill_images(self):
        """
        UPDATED: Backfill cover artwork for releases (not recordings).
        
        Album artwork is now stored on releases, not recordings.
        This method fetches artwork for releases that have a Spotify album ID
        but are missing cover art.
        """
        self.logger.info("="*80)
        self.logger.info("Spotify Cover Artwork Backfill (Releases)")
        self.logger.info("="*80)
        
        if self.dry_run:
            self.logger.info("*** DRY RUN MODE - No database changes will be made ***")
        
        self.logger.info("")
        
        # Get releases without images
        releases = self.get_releases_without_artwork()
        
        if not releases:
            self.logger.info("No releases found that need cover artwork")
            return True
        
        self.logger.info(f"Found {len(releases)} releases to process")
        self.logger.info("")
        
        # Process each release
        with get_db_connection() as conn:
            for i, release in enumerate(releases, 1):
                self.stats['releases_processed'] += 1
                
                title = release['title'] or 'Unknown Album'
                album_id = release['spotify_album_id']
                
                self.logger.info(f"[{i}/{len(releases)}] {title}")
                self.logger.info(f"    Album ID: {album_id}")
                
                if not album_id:
                    self.logger.warning(f"    ✗ No Spotify album ID")
                    self.stats['errors'] += 1
                    continue
                
                # Get album details (with caching)
                album_data = self.get_album_details(album_id)
                
                if not album_data:
                    self.logger.warning(f"    ✗ Could not fetch album details from Spotify")
                    self.stats['errors'] += 1
                    continue
                
                # Extract album artwork
                album_art = {}
                images = album_data.get('images', [])
                
                for image in images:
                    height = image.get('height', 0)
                    if height >= 600:
                        album_art['large'] = image['url']
                    elif height >= 300:
                        album_art['medium'] = image['url']
                    elif height >= 64:
                        album_art['small'] = image['url']
                
                if not album_art:
                    self.logger.warning(f"    ✗ No cover artwork found in album data")
                    self.stats['errors'] += 1
                    continue
                
                # Update release
                self.update_release_artwork(conn, release['id'], album_art)
        
        # Aggregate client stats before printing summary
        self._aggregate_client_stats()
        
        # Print summary
        self.logger.info("")
        self.logger.info("="*80)
        self.logger.info("BACKFILL SUMMARY")
        self.logger.info("="*80)
        self.logger.info(f"Releases processed: {self.stats['releases_processed']}")
        self.logger.info(f"Releases updated:   {self.stats['releases_updated']}")
        self.logger.info(f"Errors:             {self.stats['errors']}")
        self.logger.info(f"Cache hits:         {self.stats['cache_hits']}")
        self.logger.info(f"API calls:          {self.stats['api_calls']}")
        self.logger.info("="*80)
        
        return True
    
    def print_summary(self):
        """Print summary of matching statistics"""
        # Aggregate client stats before printing
        self._aggregate_client_stats()

        self.logger.info("\n" + "=" * 70)
        self.logger.info("SPOTIFY MATCHING SUMMARY")
        self.logger.info("=" * 70)
        self.logger.info(f"Recordings processed:      {self.stats['recordings_processed']}")
        self.logger.info(f"Already had Spotify URL:   {self.stats['recordings_skipped']}")
        self.logger.info(f"Newly matched:             {self.stats['recordings_updated']}")
        self.logger.info(f"No match found:            {self.stats['recordings_no_match']}")
        self.logger.info(f"Errors:                    {self.stats['errors']}")
        self.logger.info("-" * 70)
        self.logger.info(f"Total with Spotify:        {self.stats['recordings_with_spotify']}")
        self.logger.info("-" * 70)
        # Show blocklist stats if any were encountered
        if self.stats['tracks_blocked'] > 0 or self.stats['releases_blocked'] > 0:
            self.logger.info(f"Tracks blocked:            {self.stats['tracks_blocked']}")
            self.logger.info(f"Albums blocked:            {self.stats['releases_blocked']}")
            self.logger.info("-" * 70)
        self.logger.info(f"API calls made:            {self.stats['api_calls']}")
        self.logger.info(f"Cache hits:                {self.stats['cache_hits']}")
        self.logger.info(f"Rate limit hits:           {self.stats['rate_limit_hits']}")
        self.logger.info(f"Rate limit waits:          {self.stats['rate_limit_waits']}")
        cache_hit_rate = (self.stats['cache_hits'] / (self.stats['api_calls'] + self.stats['cache_hits']) * 100) if (self.stats['api_calls'] + self.stats['cache_hits']) > 0 else 0
        self.logger.info(f"Cache hit rate:            {cache_hit_rate:.1f}%")
        self.logger.info("=" * 70)