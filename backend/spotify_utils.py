"""
Spotify Track Matching Utilities
Core business logic for matching recordings to Spotify tracks

This module provides the SpotifyMatcher class which handles:
- Spotify API authentication and token management
- Fuzzy matching and validation of tracks
- Album artwork extraction
- Database updates for recordings
- Caching of API responses to minimize rate limiting

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

logger = logging.getLogger(__name__)

# Sentinel value to distinguish "no cache exists" from "cached None (no match found)"
_CACHE_MISS = object()


class SpotifyMatcher:
    """
    Handles matching recordings to Spotify tracks with fuzzy validation and caching
    """
    
    def __init__(self, dry_run=False, artist_filter=None, strict_mode=True, logger=None,
                 cache_dir='cache/spotify', cache_days=30, force_refresh=False):
        """
        Initialize Spotify Matcher
        
        Args:
            dry_run: If True, show what would be matched without making changes
            artist_filter: Filter to recordings by specific artist
            strict_mode: If True, use stricter validation thresholds (recommended)
            logger: Optional logger instance (uses module logger if not provided)
            cache_dir: Directory to store cached Spotify data
            cache_days: Number of days before cache is considered stale
            force_refresh: If True, always fetch fresh data ignoring cache
        """
        self.dry_run = dry_run
        self.artist_filter = artist_filter
        self.strict_mode = strict_mode
        self.logger = logger or logging.getLogger(__name__)
        self.access_token = None
        self.token_expires = 0
        
        # Cache configuration
        self.cache_dir = Path(cache_dir)
        self.cache_days = cache_days
        self.force_refresh = force_refresh
        
        # Track whether last operation made an API call
        self.last_made_api_call = False
        
        # Create cache directories if they don't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.search_cache_dir = self.cache_dir / 'searches'
        self.search_cache_dir.mkdir(parents=True, exist_ok=True)
        self.track_cache_dir = self.cache_dir / 'tracks'
        self.track_cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.debug(f"Spotify cache: {self.cache_dir} (expires after {cache_days} days, force_refresh={force_refresh})")
        
        self.stats = {
            'recordings_processed': 0,
            'recordings_with_spotify': 0,
            'recordings_updated': 0,
            'recordings_no_match': 0,
            'recordings_skipped': 0,
            'recordings_rejected': 0,
            'errors': 0,
            'cache_hits': 0,
            'api_calls': 0
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
        Calculate similarity between two strings using fuzzy matching
        Returns a score from 0-100
        """
        if not text1 or not text2:
            return 0
        
        norm1 = self.normalize_for_comparison(text1)
        norm2 = self.normalize_for_comparison(text2)
        
        return fuzz.token_sort_ratio(norm1, norm2)
    
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
            
            # Request token
            response = requests.post(
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
            response = requests.get(
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
                
                response = requests.get(
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
                
                # Rate limiting - be nice to Spotify's API
                time.sleep(0.1)
                
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
                
                params = [song_id]
                
                # Add artist filter if specified
                if self.artist_filter:
                    query += """
                        AND EXISTS (
                            SELECT 1 
                            FROM recording_performers rp2
                            JOIN performers p2 ON rp2.performer_id = p2.id
                            WHERE rp2.recording_id = r.id
                            AND LOWER(p2.name) LIKE LOWER(%s)
                        )
                    """
                    params.append(f"%{self.artist_filter}%")
                
                query += """
                    GROUP BY r.id, r.album_title, r.recording_year, r.spotify_url
                    ORDER BY r.recording_year DESC
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
            ), prepare=False)
            
            conn.commit()
            
            # Consolidated INFO log with context if available
            if index and total and album:
                self.logger.info(f"[{index}/{total}] {album} ({artist or 'Unknown'}, {year or 'Unknown'}) - ✓ Updated with Spotify URL and album artwork")
            else:
                self.logger.info(f"    ✓ Updated with Spotify URL and album artwork")
            
            self.stats['recordings_updated'] += 1
    
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
            ), prepare=False)
            
            conn.commit()
            self.logger.info(f"    ✓ Updated with album artwork")
            self.stats['recordings_updated'] += 1
    
    # ========================================================================
    # MAIN PROCESSING METHODS
    # ========================================================================
    
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
                performers = recording.get('performers', [])
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