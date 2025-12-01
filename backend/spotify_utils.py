"""
Spotify Track Matching Utilities
Core business logic for matching recordings to Spotify tracks

This module provides the SpotifyMatcher class which handles:
- Spotify API authentication and token management
- Fuzzy matching and validation of tracks
- Album artwork extraction
- Database updates for recordings
- Caching of API responses to minimize rate limiting
- Intelligent rate limit handling with exponential backoff

Used by:
- scripts/match_spotify_tracks.py (CLI interface)
- song_research.py (background worker)
"""

import os
import re
import time
import base64
import logging
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
import requests
from rapidfuzz import fuzz

from db_utils import get_db_connection

from cache_utils import get_cache_dir

logger = logging.getLogger(__name__)

# Sentinel value to distinguish "no cache exists" from "cached None (no match found)"
_CACHE_MISS = object()


class SpotifyRateLimitError(Exception):
    """Raised when Spotify API rate limit is hit"""
    def __init__(self, retry_after: int = None):
        self.retry_after = retry_after
        super().__init__(f"Spotify rate limit exceeded. Retry after {retry_after} seconds." if retry_after else "Spotify rate limit exceeded.")


class SpotifyMatcher:
    """
    Handles matching recordings to Spotify tracks with fuzzy validation and caching
    """
    
    def __init__(self, dry_run=False, strict_mode=False, force_refresh=False, 
                 artist_filter=False, cache_days=30, logger=None, 
                 rate_limit_delay=0.2, max_retries=3):
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
        """
        self.dry_run = dry_run
        self.artist_filter = artist_filter
        self.strict_mode = strict_mode
        self.logger = logger or logging.getLogger(__name__)
        self.access_token = None
        self.token_expires = 0
       
        # Cache configuration - use shared cache utility for persistent storage
        self.cache_days = cache_days
        self.force_refresh = force_refresh
        
        # Rate limiting configuration
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.rate_limit_hits = 0  # Track how many times we hit rate limits
        self.last_request_time = 0  # Track time of last request
        
        # Get cache directories using the shared utility
        # This ensures we use the persistent disk mount on Render
        self.cache_dir = get_cache_dir('spotify')
        self.search_cache_dir = self.cache_dir / 'searches'
        self.track_cache_dir = self.cache_dir / 'tracks'
        self.album_cache_dir = self.cache_dir / 'albums'
        
        # Create subdirectories
        self.search_cache_dir.mkdir(parents=True, exist_ok=True)
        self.track_cache_dir.mkdir(parents=True, exist_ok=True)
        self.album_cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.debug(f"Spotify cache directory: {self.cache_dir}")

        # Track whether last operation made an API call
        self.last_made_api_call = False
        
        self.logger.debug(f"Spotify cache: {self.cache_dir} (expires after {cache_days} days, force_refresh={force_refresh})")
        self.logger.debug(f"Rate limit: {rate_limit_delay}s delay, {max_retries} max retries")
        
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
            'tracks_matched': 0,
            'tracks_skipped': 0,
            'tracks_no_match': 0,
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
    
    # ========================================================================
    # RATE LIMITING METHODS
    # ========================================================================
    
    def _wait_for_rate_limit(self):
        """Enforce minimum delay between requests"""
        if self.rate_limit_delay > 0:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - elapsed
                time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def _handle_rate_limit_response(self, response: requests.Response) -> Optional[int]:
        """
        Extract rate limit information from response headers
        
        Args:
            response: Response object from requests
            
        Returns:
            Number of seconds to wait before retrying, or None if not rate limited
        """
        if response.status_code != 429:
            return None
        
        # Check for Retry-After header (number of seconds to wait)
        retry_after = response.headers.get('Retry-After')
        if retry_after:
            try:
                return int(retry_after)
            except ValueError:
                self.logger.warning(f"Invalid Retry-After header: {retry_after}")
        
        # Check for X-RateLimit-Reset (Unix timestamp)
        rate_limit_reset = response.headers.get('X-RateLimit-Reset')
        if rate_limit_reset:
            try:
                reset_time = int(rate_limit_reset)
                wait_time = max(0, reset_time - int(time.time()))
                return wait_time
            except ValueError:
                self.logger.warning(f"Invalid X-RateLimit-Reset header: {rate_limit_reset}")
        
        # Log all rate limit headers for debugging
        rate_limit_headers = {
            k: v for k, v in response.headers.items() 
            if 'rate' in k.lower() or k == 'Retry-After'
        }
        if rate_limit_headers:
            self.logger.debug(f"Rate limit headers: {rate_limit_headers}")
        
        # Default fallback if no headers available
        return None
    
    def _make_api_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make an API request with rate limit handling and retries
        
        Args:
            method: HTTP method ('get', 'post', etc.)
            url: URL to request
            **kwargs: Additional arguments to pass to requests
            
        Returns:
            Response object
            
        Raises:
            SpotifyRateLimitError: If rate limit exceeded after all retries
            requests.exceptions.RequestException: For other request failures
        """
        retry_count = 0
        base_delay = 1  # Start with 1 second for exponential backoff
        
        while retry_count <= self.max_retries:
            # Enforce minimum delay between requests
            self._wait_for_rate_limit()
            
            try:
                response = getattr(requests, method)(url, **kwargs)
                
                # Check for rate limiting
                if response.status_code == 429:
                    self.rate_limit_hits += 1
                    self.stats['rate_limit_hits'] += 1
                    
                    retry_after = self._handle_rate_limit_response(response)
                    
                    if retry_count >= self.max_retries:
                        # Out of retries
                        raise SpotifyRateLimitError(retry_after)
                    
                    # Calculate wait time
                    if retry_after is not None:
                        wait_time = retry_after
                        self.logger.warning(f"Rate limit hit (attempt {retry_count + 1}/{self.max_retries + 1}). "
                                          f"Waiting {wait_time}s as specified by Spotify.")
                    else:
                        # Use exponential backoff if no explicit retry time
                        wait_time = base_delay * (2 ** retry_count)
                        self.logger.warning(f"Rate limit hit (attempt {retry_count + 1}/{self.max_retries + 1}). "
                                          f"Using exponential backoff: {wait_time}s")
                    
                    self.stats['rate_limit_waits'] += 1
                    time.sleep(wait_time)
                    retry_count += 1
                    continue
                
                # Not rate limited - return response (caller will handle raise_for_status)
                return response
                
            except requests.exceptions.RequestException as e:
                # Network error or other request exception - don't retry
                raise
        
        # Should not reach here, but just in case
        raise SpotifyRateLimitError()
    
    # ========================================================================
    # CACHE METHODS
    # ========================================================================
    
    def _get_search_cache_path(self, song_title: str, album_title: str = None, 
                               artist_name: str = None, year: int = None) -> Path:
        """
        Get the cache file path for a search query
        
        Args:
            song_title: Song title to search for
            album_title: Album title (optional)
            artist_name: Artist name (optional)
            year: Recording year (optional)
            
        Returns:
            Path object for the cache file
        """
        # Create a unique identifier for this search combination
        query_parts = [song_title or '']
        if album_title:
            query_parts.append(album_title)
        if artist_name:
            query_parts.append(artist_name)
        if year:
            query_parts.append(str(year))
        
        query_string = '||'.join(query_parts)
        query_hash = hashlib.md5(query_string.encode()).hexdigest()
        
        # Create readable filename prefix
        safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', song_title.lower())[:50]
        filename = f"search_{safe_title}_{query_hash}.json"
        
        return self.search_cache_dir / filename
    
    def _get_track_cache_path(self, track_id: str) -> Path:
        """
        Get the cache file path for a track detail lookup
        
        Args:
            track_id: Spotify track ID
            
        Returns:
            Path object for the cache file
        """
        filename = f"track_{track_id}.json"
        return self.track_cache_dir / filename
    
    def _get_album_cache_path(self, album_id: str) -> Path:
        """
        Get the cache file path for an album detail lookup
        
        Args:
            album_id: Spotify album ID
            
        Returns:
            Path object for the cache file
        """
        filename = f"album_{album_id}.json"
        return self.album_cache_dir / filename
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """
        Check if a cache file exists and is still valid (not expired)
        
        Args:
            cache_path: Path to the cache file
            
        Returns:
            True if cache exists and is valid, False otherwise
        """
        if self.force_refresh:
            return False
        
        if not cache_path.exists():
            return False
        
        # Check file modification time
        file_mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age_days = (datetime.now() - file_mtime).days
        
        return age_days < self.cache_days
    
    def _load_from_cache(self, cache_path: Path) -> Any:
        """
        Load data from cache file if valid
        
        Args:
            cache_path: Path to the cache file
            
        Returns:
            Cached data if valid, _CACHE_MISS sentinel if no cache exists or is invalid
        """
        if not self._is_cache_valid(cache_path):
            return _CACHE_MISS
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.stats['cache_hits'] += 1
                self.last_made_api_call = False
                self.logger.debug(f"Cache hit: {cache_path.name}")
                return data
        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning(f"Failed to load cache file {cache_path}: {e}")
            # Delete corrupted cache file
            try:
                cache_path.unlink()
            except:
                pass
            return _CACHE_MISS
    
    def _save_to_cache(self, cache_path: Path, data: Any) -> None:
        """
        Save data to cache file
        
        Args:
            cache_path: Path to the cache file
            data: Data to cache (must be JSON serializable)
        """
        try:
            # Ensure directory exists
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
            self.logger.debug(f"Cached: {cache_path.name}")
        except (IOError, TypeError) as e:
            self.logger.warning(f"Failed to save cache file {cache_path}: {e}")
    
    # ========================================================================
    # SPOTIFY API METHODS
    # ========================================================================
    
    def normalize_for_comparison(self, text: str) -> str:
        """
        Normalize text for fuzzy comparison
        Removes common variations that shouldn't affect matching
        """
        if not text:
            return ""
        
        text = text.lower()
        
        # Remove live recording annotations
        text = re.sub(r'\s*-\s*live\s+(at|in|from)\s+.*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*\(live\s+(at|in|from)\s+[^)]*\).*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*-\s*live$', '', text, flags=re.IGNORECASE)  # Simple "- Live" suffix
        text = re.sub(r'\s*\(live\)$', '', text, flags=re.IGNORECASE)  # Simple "(Live)" suffix
        
        # Remove recorded at annotations
        text = re.sub(r'\s*-\s*recorded\s+(at|in)\s+.*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*\(recorded\s+(at|in)\s+[^)]*\).*$', '', text, flags=re.IGNORECASE)
        
        # Remove remastered annotations
        text = re.sub(r'\s*-\s*remastered(\s+\d{4})?.*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*\(remastered(\s+\d{4})?\).*$', '', text, flags=re.IGNORECASE)
        
        # Remove date/venue at end
        text = re.sub(r'\s*/\s+[a-z]+\s+\d+.*$', '', text, flags=re.IGNORECASE)
        
        # Remove tempo/arrangement annotations (common in jazz)
        text = re.sub(r'\s*-\s*(slow|fast|up tempo|medium|ballad)(\s+version)?.*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*\((slow|fast|up tempo|medium|ballad)(\s+version)?\).*$', '', text, flags=re.IGNORECASE)
        
        # Remove take numbers and alternate versions
        text = re.sub(r'\s*-\s*(take|version|alternate|alt\.?)\s*\d*.*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*\((take|version|alternate|alt\.?)\s*\d*\).*$', '', text, flags=re.IGNORECASE)
        
        # Remove ensemble suffixes
        text = text.replace(' trio', '')
        text = text.replace(' quartet', '')
        text = text.replace(' quintet', '')
        text = text.replace(' sextet', '')
        text = text.replace(' orchestra', '')
        text = text.replace(' band', '')
        text = text.replace(' ensemble', '')
        
        # Normalize "and" vs "&"
        text = text.replace(' & ', ' and ')

        # Normalize spacing around punctuation (e.g., "St. / Denis" → "St./Denis")
        text = re.sub(r'\s*/\s*', '/', text)
        text = re.sub(r'\s*-\s*', '-', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two strings using fuzzy matching.
        
        Handles common variations like parenthetical additions:
        - "Who Cares?" vs "Who Cares (As Long As You Care For Me)"
        - "Stella By Starlight" vs "Stella By Starlight (From 'The Uninvited')"
        
        Returns a score from 0-100
        """
        if not text1 or not text2:
            return 0
        
        norm1 = self.normalize_for_comparison(text1)
        norm2 = self.normalize_for_comparison(text2)
        
        # Primary comparison using token_sort_ratio
        score = fuzz.token_sort_ratio(norm1, norm2)
        
        # If score is below threshold, try comparing without parenthetical content
        # This handles cases like "Who Cares?" vs "Who Cares (As Long As You Care For Me)"
        if score < 80:
            # Strip parenthetical content from both
            stripped1 = re.sub(r'\s*\([^)]*\)\s*', ' ', norm1).strip()
            stripped2 = re.sub(r'\s*\([^)]*\)\s*', ' ', norm2).strip()
            
            # Only use stripped comparison if something was actually removed
            if stripped1 != norm1 or stripped2 != norm2:
                stripped_score = fuzz.token_sort_ratio(stripped1, stripped2)
                if stripped_score > score:
                    self.logger.debug(f"      Parenthetical fallback: {score}% → {stripped_score}%")
                    score = stripped_score
        
        return score
    
    def validate_match(self, spotify_track: dict, expected_song: str, 
                      expected_artist: str, expected_album: str) -> tuple:
        """
        Validate that a Spotify track result actually matches what we're looking for
        
        Args:
            spotify_track: Track dict from Spotify API
            expected_song: Song title we're searching for
            expected_artist: Artist name we're searching for
            expected_album: Album title we're searching for (can be None)
            
        Returns:
            tuple: (is_valid, reason, scores_dict)
        """
        # Extract Spotify track info
        spotify_song = spotify_track['name']
        spotify_artist_list = [a['name'] for a in spotify_track['artists']]
        spotify_artists = ', '.join(spotify_artist_list)
        spotify_album = spotify_track['album']['name']
        
        # Calculate track title similarity
        song_similarity = self.calculate_similarity(expected_song, spotify_song)
        
        # Debug: Show normalized versions if similarity is surprisingly low
        if song_similarity < 70:
            norm_expected = self.normalize_for_comparison(expected_song)
            norm_spotify = self.normalize_for_comparison(spotify_song)
            if norm_expected != expected_song.lower() or norm_spotify != spotify_song.lower():
                self.logger.debug(f"       [Normalization] Expected: '{expected_song}' → '{norm_expected}'")
                self.logger.debug(f"       [Normalization] Spotify:  '{spotify_song}' → '{norm_spotify}'")
        
        # Calculate artist similarity - handle multi-artist tracks
        individual_artist_scores = [
            self.calculate_similarity(expected_artist, spotify_artist)
            for spotify_artist in spotify_artist_list
        ]
        best_individual_match = max(individual_artist_scores) if individual_artist_scores else 0
        
        full_artist_similarity = self.calculate_similarity(expected_artist, spotify_artists)
        
        artist_similarity = max(best_individual_match, full_artist_similarity)
        
        # Calculate album similarity
        album_similarity = self.calculate_similarity(expected_album, spotify_album) if expected_album else None
        
        scores = {
            'song': song_similarity,
            'artist': artist_similarity,
            'artist_best_individual': best_individual_match,
            'artist_full_string': full_artist_similarity,
            'album': album_similarity,
            'spotify_song': spotify_song,
            'spotify_artist': spotify_artists,
            'spotify_album': spotify_album
        }
        
        # Validation logic
        if song_similarity < self.min_track_similarity:
            return False, f"Track title similarity too low ({song_similarity}% < {self.min_track_similarity}%)", scores
        
        if artist_similarity < self.min_artist_similarity:
            return False, f"Artist similarity too low ({artist_similarity}% < {self.min_artist_similarity}%)", scores
        
        if expected_album and album_similarity and album_similarity < self.min_album_similarity:
            return False, f"Album similarity too low ({album_similarity}% < {self.min_album_similarity}%)", scores
        
        # Passed all validation checks
        return True, "Valid match", scores
    
    def get_spotify_auth_token(self) -> Optional[str]:
        """
        Get a valid Spotify access token (reuses existing if still valid)
        Returns None if authentication fails
        """
        # Return cached token if still valid
        if self.access_token and time.time() < self.token_expires:
            return self.access_token
        
        # Get credentials from environment
        client_id = os.environ.get('SPOTIFY_CLIENT_ID')
        client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            self.logger.error("Spotify credentials not found in environment variables")
            self.logger.error("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET")
            return None
        
        try:
            # Encode credentials for basic auth
            credentials = f"{client_id}:{client_secret}"
            credentials_b64 = base64.b64encode(credentials.encode()).decode()
            
            # Request token (auth endpoint typically not rate limited, but use request wrapper anyway)
            response = self._make_api_request(
                'post',
                'https://accounts.spotify.com/api/token',
                headers={
                    'Authorization': f'Basic {credentials_b64}',
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                data={'grant_type': 'client_credentials'},
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Store token and expiration time (with 60 second buffer)
            self.access_token = data['access_token']
            self.token_expires = time.time() + data['expires_in'] - 60
            
            self.logger.debug("Spotify authentication successful")
            return self.access_token
            
        except SpotifyRateLimitError as e:
            self.logger.error(f"Rate limit exceeded during authentication: {e}")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to authenticate with Spotify: {e}")
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
        cache_path = self._get_track_cache_path(track_id)
        cached_data = self._load_from_cache(cache_path)
        
        if cached_data is not _CACHE_MISS:
            # Cache hit - return cached data (which might be None for "not found")
            return cached_data
        
        # Not in cache or cache expired - fetch from API
        token = self.get_spotify_auth_token()
        if not token:
            return None
        
        try:
            response = self._make_api_request(
                'get',
                f'https://api.spotify.com/v1/tracks/{track_id}',
                headers={'Authorization': f'Bearer {token}'},
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Track API call
            self.stats['api_calls'] += 1
            self.last_made_api_call = True
            
            # Save to cache
            self._save_to_cache(cache_path, data)
            
            return data
            
        except SpotifyRateLimitError as e:
            self.logger.error(f"Rate limit exceeded fetching track details: {e}")
            return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # Cache the "not found" result
                self._save_to_cache(cache_path, None)
                return None
            self.logger.error(f"Spotify API error: {e}")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch track details: {e}")
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
        cache_path = self._get_search_cache_path(song_title, album_title, artist_name, year)
        cached_result = self._load_from_cache(cache_path)
        
        if cached_result is not _CACHE_MISS:
            # Cache hit - return cached result (which might be None for "no match found")
            return cached_result
        
        # Not in cache - perform search
        token = self.get_spotify_auth_token()
        if not token:
            self._save_to_cache(cache_path, None)
            return None
        
        # Progressive search strategy
        # Start with specific queries, fall back to broader searches
        search_strategies = []
        
        if artist_name and year:
            search_strategies.append({
                'query': f'track:"{song_title}" artist:"{artist_name}" album:"{album_title}" year:{year}',
                'description': 'exact track, artist, album, and year'
            })
        
        if artist_name:
            search_strategies.append({
                'query': f'track:"{song_title}" artist:"{artist_name}" album:"{album_title}"',
                'description': 'exact track, artist, and album'
            })
            search_strategies.append({
                'query': f'track:"{song_title}" artist:"{artist_name}"',
                'description': 'exact track and artist'
            })
        
        search_strategies.append({
            'query': f'track:"{song_title}" album:"{album_title}"',
            'description': 'exact track and album'
        })
        
        search_strategies.append({
            'query': f'track:"{song_title}"',
            'description': 'exact track only'
        })
        
        # Try each search strategy until we get a valid match
        for strategy in search_strategies:
            try:
                self.logger.debug(f"  → Trying: {strategy['description']}")
                
                response = self._make_api_request(
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
                self.last_made_api_call = True
                
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
                            self._save_to_cache(cache_path, result)
                            
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
                    self.access_token = None
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
        self._save_to_cache(cache_path, None)
        
        return None
    
    # ========================================================================
    # DATABASE METHODS
    # ========================================================================
    
    def find_song_by_name(self, song_name: str) -> Optional[dict]:
        """Look up song by name"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, title, composer FROM songs WHERE LOWER(title) = LOWER(%s)",
                    (song_name,)
                )
                return cur.fetchone()
    
    def find_song_by_id(self, song_id: str) -> Optional[dict]:
        """Look up song by ID"""
        # Strip 'song-' prefix if present
        if song_id.startswith('song-'):
            song_id = song_id[5:]
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, title, composer FROM songs WHERE id = %s",
                    (song_id,)
                )
                return cur.fetchone()
    
    def get_recordings_for_song(self, song_id: str) -> List[dict]:
        """
        Get all recordings for a song, optionally filtered by artist
        
        Returns:
            List of recording dicts with 'id', 'album_title', 'recording_year',
            'spotify_url', 'performers' (list with 'name' and 'role')
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Base query
                query = """
                    SELECT 
                        r.id,
                        r.album_title,
                        r.recording_year,
                        r.spotify_url,
                        json_agg(
                            json_build_object(
                                'name', p.name,
                                'role', rp.role,
                                'instrument', i.name
                            ) ORDER BY 
                                CASE rp.role 
                                    WHEN 'leader' THEN 1 
                                    WHEN 'member' THEN 2 
                                    ELSE 3 
                                END,
                                p.name
                        ) FILTER (WHERE p.id IS NOT NULL) as performers
                    FROM recordings r
                    LEFT JOIN recording_performers rp ON r.id = rp.recording_id
                    LEFT JOIN performers p ON rp.performer_id = p.id
                    LEFT JOIN instruments i ON rp.instrument_id = i.id
                    WHERE r.song_id = %s
                """
                
                # Add artist filter if specified
                params = [song_id]
                if self.artist_filter:
                    query += """
                        AND EXISTS (
                            SELECT 1 
                            FROM recording_performers rp2
                            JOIN performers p2 ON rp2.performer_id = p2.id
                            WHERE rp2.recording_id = r.id
                            AND LOWER(p2.name) = LOWER(%s)
                        )
                    """
                    params.append(self.artist_filter)
                
                query += """
                    GROUP BY r.id, r.album_title, r.recording_year, r.spotify_url
                    ORDER BY r.recording_year
                """
                
                cur.execute(query, params)
                return cur.fetchall()
    
    def get_recordings_without_images(self) -> List[dict]:
        """Get recordings with Spotify URL but no album artwork"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, album_title, spotify_url
                    FROM recordings
                    WHERE spotify_url IS NOT NULL
                      AND album_art_medium IS NULL
                    ORDER BY album_title
                """)
                return cur.fetchall()
    
    def extract_track_id_from_url(self, spotify_url: str) -> Optional[str]:
        """Extract Spotify track ID from URL"""
        if not spotify_url:
            return None
        
        # Spotify URL format: https://open.spotify.com/track/{track_id}
        match = re.search(r'spotify\.com/track/([a-zA-Z0-9]+)', spotify_url)
        if match:
            return match.group(1)
        
        return None
    
    def update_recording_artwork(self, conn, recording_id: str, album_art: dict):
        """Update recording with album artwork only"""
        if self.dry_run:
            self.logger.info(f"    [DRY RUN] Would update with album artwork")
            return
        
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE recordings
                SET album_art_small = %s,
                    album_art_medium = %s,
                    album_art_large = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                album_art.get('small'),
                album_art.get('medium'),
                album_art.get('large'),
                recording_id
            ))
            
            conn.commit()
            self.logger.info(f"    ✓ Updated with album artwork")
            self.stats['recordings_updated'] += 1
    
    def update_recording_spotify_url(self, conn, recording_id: str, spotify_data: dict, 
                                     album: str = None, artist: str = None, year: int = None,
                                     index: int = None, total: int = None):
        """Update recording with Spotify URL, track ID, and album artwork"""
        if self.dry_run:
            self.logger.info(f"    [DRY RUN] Would update recording with: {spotify_data['url']}")
            if spotify_data.get('album_art', {}).get('medium'):
                self.logger.info(f"    [DRY RUN] Would add album artwork")
            return
        
        with conn.cursor() as cur:
            track_id = spotify_data.get('id')
            album_art = spotify_data.get('album_art', {})
            
            cur.execute("""
                UPDATE recordings
                SET spotify_url = %s,
                    spotify_track_id = %s,
                    album_art_small = %s,
                    album_art_medium = %s,
                    album_art_large = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                spotify_data['url'],
                track_id,
                album_art.get('small'),
                album_art.get('medium'),
                album_art.get('large'),
                recording_id
            ))
            
            conn.commit()
            
            # Consolidated INFO log with context if available
            if index and total and album:
                self.logger.info(f"[{index}/{total}] {album} ({artist or 'Unknown'}, {year or 'Unknown'}) - ✓ Updated with Spotify URL and album artwork")
            else:
                self.logger.info(f"    ✓ Updated with Spotify URL and album artwork")
            
            self.stats['recordings_updated'] += 1
    
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

        """
        self.logger.warning(f"TEMPORARILY BYPASSING SPOTIFY")
        return {
            'success': False,
            'error': "TEMPORARILY BYPASSING SPOTIFY",
            'stats': self.stats
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
            if self.artist_filter:
                self.logger.info(f"Filtering to recordings by: {self.artist_filter}")
            self.logger.info("")
            
            # Get recordings
            recordings = self.get_recordings_for_song(song['id'])
            
            if not recordings:
                return {
                    'success': False,
                    'song': song,
                    'error': 'No recordings found for this song'
                }
            
            self.logger.info(f"Found {len(recordings)} recordings to process")
            self.logger.info("")
            
            # Process each recording
            # CRITICAL: Open connection for EACH recording to avoid holding connections during Spotify API calls
            for i, recording in enumerate(recordings, 1):
                self.stats['recordings_processed'] += 1
                
                album = recording['album_title'] or 'Unknown Album'
                year = recording['recording_year']
                
                # Get primary artist
                performers = recording.get('performers') or []
                leaders = [p['name'] for p in performers if p['role'] == 'leader']
                artist_name = leaders[0] if leaders else (
                    performers[0]['name'] if performers else None
                )
                
                # Log details at DEBUG level
                self.logger.debug(f"[{i}/{len(recordings)}] {album}")
                self.logger.debug(f"    Artist: {artist_name or 'Unknown'}")
                self.logger.debug(f"    Year: {year or 'Unknown'}")
                
                # Check if already has Spotify URL
                if recording['spotify_url']:
                    self.logger.info(f"[{i}/{len(recordings)}] {album} ({artist_name or 'Unknown'}, {year or 'Unknown'}) - ⊙ Already has Spotify URL, skipping")
                    self.stats['recordings_skipped'] += 1
                    continue
                
                # Search Spotify WITHOUT holding a database connection
                spotify_match = self.search_spotify_track(
                    song['title'],
                    album,
                    artist_name,
                    year
                )
                
                if spotify_match:
                    self.stats['recordings_with_spotify'] += 1
                    # Open connection ONLY for this update, then close immediately
                    with get_db_connection() as conn:
                        self.update_recording_spotify_url(
                            conn,
                            recording['id'],
                            spotify_match,
                            album,
                            artist_name,
                            year,
                            i,
                            len(recordings)
                        )
                        # Connection automatically committed and closed here
                else:
                    self.logger.info(f"[{i}/{len(recordings)}] {album} ({artist_name or 'Unknown'}, {year or 'Unknown'}) - ✗ No valid Spotify match found")
                    self.stats['recordings_no_match'] += 1
            
            return {
                'success': True,
                'song': song,
                'stats': self.stats
            }
            
        except Exception as e:
            self.logger.error(f"Error matching recordings: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'stats': self.stats
            }
    
    def backfill_images(self):
        """Main method to backfill album artwork for existing recordings"""
        self.logger.info("="*80)
        self.logger.info("Spotify Album Artwork Backfill")
        self.logger.info("="*80)
        
        if self.dry_run:
            self.logger.info("*** DRY RUN MODE - No database changes will be made ***")
        
        self.logger.info("")
        
        # Get recordings without images
        recordings = self.get_recordings_without_images()
        
        if not recordings:
            self.logger.info("No recordings found that need album artwork")
            return True
        
        self.logger.info(f"Found {len(recordings)} recordings to process")
        self.logger.info("")
        
        # Process each recording
        with get_db_connection() as conn:
            for i, recording in enumerate(recordings, 1):
                self.stats['recordings_processed'] += 1
                
                album = recording['album_title'] or 'Unknown Album'
                spotify_url = recording['spotify_url']
                
                self.logger.info(f"[{i}/{len(recordings)}] {album}")
                self.logger.info(f"    URL: {spotify_url[:50]}...")
                
                # Extract track ID from URL
                track_id = self.extract_track_id_from_url(spotify_url)
                if not track_id:
                    self.logger.warning(f"    ✗ Could not extract track ID from URL")
                    self.stats['errors'] += 1
                    continue
                
                # Get track details (with caching)
                track_data = self.get_track_details(track_id)
                
                if not track_data:
                    self.logger.warning(f"    ✗ Could not fetch track details from Spotify")
                    self.stats['errors'] += 1
                    continue
                
                # Extract album artwork
                album_art = {}
                images = track_data.get('album', {}).get('images', [])
                
                for image in images:
                    height = image.get('height', 0)
                    if height >= 600:
                        album_art['large'] = image['url']
                    elif height >= 300:
                        album_art['medium'] = image['url']
                    elif height >= 64:
                        album_art['small'] = image['url']
                
                if not album_art:
                    self.logger.warning(f"    ✗ No album artwork found in track data")
                    self.stats['errors'] += 1
                    continue
                
                # Update recording
                self.update_recording_artwork(conn, recording['id'], album_art)
        
        # Print summary
        self.logger.info("")
        self.logger.info("="*80)
        self.logger.info("BACKFILL SUMMARY")
        self.logger.info("="*80)
        self.logger.info(f"Recordings processed: {self.stats['recordings_processed']}")
        self.logger.info(f"Recordings updated:   {self.stats['recordings_updated']}")
        self.logger.info(f"Errors:               {self.stats['errors']}")
        self.logger.info(f"Cache hits:           {self.stats['cache_hits']}")
        self.logger.info(f"API calls:            {self.stats['api_calls']}")
        self.logger.info("="*80)
        
        return True
    
    def print_summary(self):
        """Print summary of matching statistics"""
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
        self.logger.info(f"API calls made:            {self.stats['api_calls']}")
        self.logger.info(f"Cache hits:                {self.stats['cache_hits']}")
        self.logger.info(f"Rate limit hits:           {self.stats['rate_limit_hits']}")
        self.logger.info(f"Rate limit waits:          {self.stats['rate_limit_waits']}")
        cache_hit_rate = (self.stats['cache_hits'] / (self.stats['api_calls'] + self.stats['cache_hits']) * 100) if (self.stats['api_calls'] + self.stats['cache_hits']) > 0 else 0
        self.logger.info(f"Cache hit rate:            {cache_hit_rate:.1f}%")
        self.logger.info("=" * 70)
    
    # ========================================================================
    # RELEASE MATCHING METHODS (NEW)
    # ========================================================================
    
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
        cache_path = self._get_search_cache_path('album', album_title, artist_name)
        cached_result = self._load_from_cache(cache_path)
        
        if cached_result is not _CACHE_MISS:
            return cached_result
        
        token = self.get_spotify_auth_token()
        if not token:
            self._save_to_cache(cache_path, None)
            return None
        
        # Progressive search strategy
        search_strategies = []
        
        if artist_name:
            search_strategies.append({
                'query': f'album:"{album_title}" artist:"{artist_name}"',
                'description': 'exact album and artist'
            })
            search_strategies.append({
                'query': f'"{album_title}" "{artist_name}"',
                'description': 'quoted album and artist'
            })
        
        search_strategies.append({
            'query': f'album:"{album_title}"',
            'description': 'exact album only'
        })
        
        for strategy in search_strategies:
            try:
                self.logger.debug(f"  → Trying: {strategy['description']}")
                
                response = self._make_api_request(
                    'get',
                    'https://api.spotify.com/v1/search',
                    headers={'Authorization': f'Bearer {token}'},
                    params={
                        'q': strategy['query'],
                        'type': 'album',
                        'limit': 5
                    },
                    timeout=10
                )
                
                response.raise_for_status()
                data = response.json()
                
                self.stats['api_calls'] += 1
                self.last_made_api_call = True
                
                albums = data.get('albums', {}).get('items', [])
                
                if albums:
                    self.logger.debug(f"    Found {len(albums)} candidates")
                    
                    for i, album in enumerate(albums):
                        is_valid, reason, scores = self.validate_album_match(
                            album, album_title, artist_name or '', song_title
                        )
                        
                        if is_valid:
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
                            
                            self._save_to_cache(cache_path, result)
                            self.logger.debug(f"    ✓ Valid match found (candidate #{i+1})")
                            return result
                        else:
                            self.logger.debug(f"    ✗ Candidate #{i+1} rejected: {reason}")
                            self.logger.debug(f"       Expected: '{album_title}' by {artist_name}")
                            self.logger.debug(f"       Found: '{scores.get('spotify_album', '')}' by {scores.get('spotify_artist', '')}")
                    
                    self.logger.debug(f"    ✗ No valid matches with {strategy['description']}")
                else:
                    self.logger.debug(f"    ✗ No results with {strategy['description']}")
                    
            except SpotifyRateLimitError as e:
                self.logger.error(f"Rate limit exceeded during search: {e}")
                return None
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    self.access_token = None
                    return None
                self.logger.error(f"Spotify search failed: {e}")
                return None
            except Exception as e:
                self.logger.error(f"Error searching Spotify: {e}")
                return None
        
        self.logger.debug(f"    ✗ No valid Spotify matches found after trying all strategies")
        self._save_to_cache(cache_path, None)
        return None
    
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
    
    def validate_album_match(self, spotify_album: dict, expected_album: str, 
                            expected_artist: str, song_title: str = None) -> tuple:
        """
        Validate that a Spotify album result actually matches what we're looking for
        
        Args:
            spotify_album: Spotify album dict from search results
            expected_album: Album title we're searching for
            expected_artist: Artist name we're searching for
            song_title: Optional song title for track verification fallback.
                       When album similarity is high (>=80%) but artist fails,
                       we can still accept the match if the album contains
                       a track matching this title.
        
        Returns:
            tuple: (is_valid, reason, scores_dict)
        """
        spotify_album_name = spotify_album['name']
        spotify_artist_list = [a['name'] for a in spotify_album['artists']]
        spotify_artists = ', '.join(spotify_artist_list)
        
        # Calculate album similarity
        album_similarity = self.calculate_similarity(expected_album, spotify_album_name)
        
        # Calculate artist similarity
        individual_artist_scores = [
            self.calculate_similarity(expected_artist, spotify_artist)
            for spotify_artist in spotify_artist_list
        ]
        best_individual_match = max(individual_artist_scores) if individual_artist_scores else 0
        full_artist_similarity = self.calculate_similarity(expected_artist, spotify_artists)
        artist_similarity = max(best_individual_match, full_artist_similarity)
        
        scores = {
            'album': album_similarity,
            'artist': artist_similarity,
            'artist_best_individual': best_individual_match,
            'artist_full_string': full_artist_similarity,
            'spotify_album': spotify_album_name,
            'spotify_artist': spotify_artists
        }
        
        # Validation logic
        if album_similarity < self.min_album_similarity:
            return False, f"Album similarity too low ({album_similarity}% < {self.min_album_similarity}%)", scores
        
        if expected_artist and artist_similarity < self.min_artist_similarity:
            # Artist validation failed - try track verification fallback
            # This handles "Various Artists", ensemble name variations, etc.
            # Only attempt if album similarity is high (>=80%) and we have a song title
            if song_title and album_similarity >= 80:
                album_id = spotify_album.get('id')
                if album_id and self.verify_album_contains_track(album_id, song_title):
                    scores['verified_by_track'] = True
                    self.logger.debug(f"      Album accepted via track verification (artist {artist_similarity}% < {self.min_artist_similarity}%)")
                    return True, "Valid match (verified by track presence)", scores
            
            return False, f"Artist similarity too low ({artist_similarity}% < {self.min_artist_similarity}%)", scores
        
        return True, "Valid match", scores
    
    def get_releases_for_song(self, song_id: str) -> List[dict]:
        """
        Get all releases for a song (via recording_releases junction),
        optionally filtered by artist
        
        Returns:
            List of release dicts with 'id', 'title', 'artist_credit', 'release_year',
            'spotify_album_url', 'performers' (list with 'name' and 'role')
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT
                        rel.id,
                        rel.title,
                        rel.artist_credit,
                        rel.release_year,
                        rel.spotify_album_url,
                        json_agg(
                            json_build_object(
                                'name', p.name,
                                'role', rp.role,
                                'instrument', i.name
                            ) ORDER BY 
                                CASE rp.role 
                                    WHEN 'leader' THEN 1 
                                    WHEN 'sideman' THEN 2 
                                    ELSE 3 
                                END,
                                p.name
                        ) FILTER (WHERE p.id IS NOT NULL) as performers
                    FROM releases rel
                    JOIN recording_releases rr ON rel.id = rr.release_id
                    JOIN recordings rec ON rr.recording_id = rec.id
                    LEFT JOIN release_performers rp ON rel.id = rp.release_id
                    LEFT JOIN performers p ON rp.performer_id = p.id
                    LEFT JOIN instruments i ON rp.instrument_id = i.id
                    WHERE rec.song_id = %s
                """
                
                params = [song_id]
                if self.artist_filter:
                    query += """
                        AND EXISTS (
                            SELECT 1 
                            FROM release_performers rp2
                            JOIN performers p2 ON rp2.performer_id = p2.id
                            WHERE rp2.release_id = rel.id
                            AND LOWER(p2.name) = LOWER(%s)
                        )
                    """
                    params.append(self.artist_filter)
                
                query += """
                    GROUP BY rel.id, rel.title, rel.artist_credit, rel.release_year, rel.spotify_album_url
                    ORDER BY rel.release_year
                """
                
                cur.execute(query, params)
                return cur.fetchall()
    
    def update_release_spotify_data(self, conn, release_id: str, spotify_data: dict,
                                    release_title: str = None, artist: str = None,
                                    year: int = None, index: int = None, total: int = None):
        """Update release with Spotify album URL, ID, and cover artwork"""
        if self.dry_run:
            self.logger.info(f"    [DRY RUN] Would update release with: {spotify_data['url']}")
            if spotify_data.get('album_art', {}).get('medium'):
                self.logger.info(f"    [DRY RUN] Would add cover artwork")
            return
        
        with conn.cursor() as cur:
            album_id = spotify_data.get('id')
            album_art = spotify_data.get('album_art', {})
            
            cur.execute("""
                UPDATE releases
                SET spotify_album_url = %s,
                    spotify_album_id = %s,
                    cover_art_small = %s,
                    cover_art_medium = %s,
                    cover_art_large = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                spotify_data['url'],
                album_id,
                album_art.get('small'),
                album_art.get('medium'),
                album_art.get('large'),
                release_id
            ))
            
            conn.commit()
            
            if index and total and release_title:
                self.logger.info(f"[{index}/{total}] {release_title} ({artist or 'Unknown'}, {year or 'Unknown'}) - ✓ Updated with Spotify URL and cover artwork")
            else:
                self.logger.info(f"    ✓ Updated with Spotify URL and cover artwork")
            
            self.stats['releases_updated'] += 1
    
    def match_releases(self, song_identifier: str) -> Dict[str, Any]:
        """
        Main method to match Spotify albums for a song's releases
        
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
            self.logger.info("")
            
            # Process each release
            for i, release in enumerate(releases, 1):
                self.stats['releases_processed'] += 1
                
                title = release['title'] or 'Unknown Album'
                year = release['release_year']
                
                # Get artist - prefer artist_credit, fall back to performers
                artist_name = release.get('artist_credit')
                if not artist_name:
                    performers = release.get('performers') or []
                    leaders = [p['name'] for p in performers if p.get('role') == 'leader']
                    artist_name = leaders[0] if leaders else (
                        performers[0]['name'] if performers else None
                    )
                
                self.logger.debug(f"[{i}/{len(releases)}] {title}")
                self.logger.debug(f"    Artist: {artist_name or 'Unknown'}")
                self.logger.debug(f"    Year: {year or 'Unknown'}")
                
                # Check if already has Spotify URL
                if release['spotify_album_url']:
                    self.logger.info(f"[{i}/{len(releases)}] {title} ({artist_name or 'Unknown'}, {year or 'Unknown'}) - ⊙ Already has Spotify URL, skipping")
                    self.stats['releases_skipped'] += 1
                    continue
                
                # Search Spotify for album (with song title for track verification fallback)
                spotify_match = self.search_spotify_album(title, artist_name, song['title'])
                
                if spotify_match:
                    with get_db_connection() as conn:
                        # First try to match tracks - this validates the album match
                        track_matched = self.match_tracks_for_release(
                            conn,
                            song['id'],
                            release['id'],
                            spotify_match['id'],
                            song['title']
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
                        else:
                            # Album matched but no track found - likely false positive
                            self.logger.info(f"[{i}/{len(releases)}] {title} ({artist_name or 'Unknown'}, {year or 'Unknown'}) - ✗ Album matched but track not found (possible false positive)")
                            self.stats['releases_no_match'] += 1
                else:
                    self.logger.info(f"[{i}/{len(releases)}] {title} ({artist_name or 'Unknown'}, {year or 'Unknown'}) - ✗ No valid Spotify match found")
                    self.stats['releases_no_match'] += 1
            
            return {
                'success': True,
                'song': song,
                'stats': self.stats
            }
            
        except Exception as e:
            self.logger.error(f"Error matching releases: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'stats': self.stats
            }
    
    # ========================================================================
    # TRACK MATCHING METHODS (Match recordings to Spotify tracks within albums)
    # ========================================================================
    
    def get_album_tracks(self, album_id: str) -> Optional[List[dict]]:
        """
        Fetch tracks from a Spotify album
        
        Args:
            album_id: Spotify album ID
            
        Returns:
            List of track dicts with 'id', 'name', 'track_number', 'disc_number', 'url'
            or None if failed
        """
        # Check cache first
        cache_path = self._get_album_cache_path(album_id)
        cached_result = self._load_from_cache(cache_path)
        
        if cached_result is not _CACHE_MISS:
            return cached_result
        
        token = self.get_spotify_auth_token()
        if not token:
            return None
        
        try:
            response = self._make_api_request(
                'get',
                f'https://api.spotify.com/v1/albums/{album_id}/tracks',
                headers={'Authorization': f'Bearer {token}'},
                params={'limit': 50},
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()
            
            self.stats['api_calls'] += 1
            self.last_made_api_call = True
            
            tracks = []
            for item in data.get('items', []):
                tracks.append({
                    'id': item['id'],
                    'name': item['name'],
                    'track_number': item['track_number'],
                    'disc_number': item['disc_number'],
                    'url': item['external_urls']['spotify']
                })
            
            self._save_to_cache(cache_path, tracks)
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
    
    def get_recordings_for_release(self, song_id: str, release_id: str) -> List[dict]:
        """
        Get recordings linked to a specific release for a specific song
        
        Args:
            song_id: Our database song ID
            release_id: Our database release ID
            
        Returns:
            List of recording dicts with 'recording_id', 'song_title', 
            'track_number', 'spotify_track_id' (existing if any)
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        rr.recording_id,
                        s.title as song_title,
                        rr.track_number,
                        rr.spotify_track_id
                    FROM recording_releases rr
                    JOIN recordings rec ON rr.recording_id = rec.id
                    JOIN songs s ON rec.song_id = s.id
                    WHERE rr.release_id = %s
                      AND rec.song_id = %s
                    ORDER BY rr.track_number
                """, (release_id, song_id))
                return cur.fetchall()
    
    def match_track_to_recording(self, song_title: str, spotify_tracks: List[dict]) -> Optional[dict]:
        """
        Find the best matching Spotify track for a song title
        
        Args:
            song_title: The song title to match
            spotify_tracks: List of track dicts from get_album_tracks()
            
        Returns:
            Best matching track dict or None if no good match
        """
        best_match = None
        best_score = 0
        
        for track in spotify_tracks:
            score = self.calculate_similarity(song_title, track['name'])
            
            if score > best_score and score >= self.min_track_similarity:
                best_score = score
                best_match = track
        
        if best_match:
            self.logger.debug(f"      Track match: '{song_title}' → '{best_match['name']}' ({best_score}%)")
        
        return best_match
    
    def update_recording_release_track_id(self, conn, recording_id: str, release_id: str,
                                          track_id: str, track_url: str):
        """
        Update the recording_releases junction table with Spotify track info
        
        Args:
            conn: Database connection
            recording_id: Our recording ID
            release_id: Our release ID  
            track_id: Spotify track ID
            track_url: Spotify track URL
        """
        if self.dry_run:
            self.logger.debug(f"      [DRY RUN] Would update recording_releases with track: {track_id}")
            return
        
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE recording_releases
                SET spotify_track_id = %s,
                    spotify_track_url = %s
                WHERE recording_id = %s AND release_id = %s
            """, (track_id, track_url, recording_id, release_id))
            
            conn.commit()
    
    def match_tracks_for_release(self, conn, song_id: str, release_id: str, 
                                  spotify_album_id: str, song_title: str) -> bool:
        """
        Match Spotify tracks to recordings for a release
        
        After we've matched a release to a Spotify album, this method:
        1. Fetches all tracks from the Spotify album
        2. Gets our recordings linked to this release
        3. Fuzzy matches the song title to find the right track
        4. Updates the recording_releases junction table with the track ID
        
        Args:
            conn: Database connection
            song_id: Our song ID
            release_id: Our release ID
            spotify_album_id: Spotify album ID we matched to
            song_title: The song title to search for
            
        Returns:
            bool: True if at least one track was matched, False otherwise
        """
        # Get tracks from Spotify album
        spotify_tracks = self.get_album_tracks(spotify_album_id)
        if not spotify_tracks:
            self.logger.debug(f"    Could not fetch tracks for album {spotify_album_id}")
            return False
        
        self.logger.debug(f"    Matching tracks ({len(spotify_tracks)} tracks in album)...")
        
        # Get our recordings for this release
        recordings = self.get_recordings_for_release(song_id, release_id)
        
        any_matched = False
        for recording in recordings:
            # Skip if already has a track ID
            if recording['spotify_track_id']:
                self.logger.debug(f"      Recording already has track ID, skipping")
                self.stats['tracks_skipped'] += 1
                any_matched = True  # Consider already-matched as success
                continue
            
            # Match song title to a track
            matched_track = self.match_track_to_recording(song_title, spotify_tracks)
            
            if matched_track:
                self.update_recording_release_track_id(
                    conn,
                    recording['recording_id'],
                    release_id,
                    matched_track['id'],
                    matched_track['url']
                )
                self.stats['tracks_matched'] += 1
                any_matched = True
            else:
                # Show what tracks are on the album to help debug
                track_names = [t['name'] for t in spotify_tracks[:8]]
                more = f"... (+{len(spotify_tracks) - 8} more)" if len(spotify_tracks) > 8 else ""
                self.logger.debug(f"      No track match for '{song_title}'")
                self.logger.debug(f"      Album tracks: {track_names}{more}")
                self.stats['tracks_no_match'] += 1
        
        return any_matched