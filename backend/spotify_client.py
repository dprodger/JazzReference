"""
Spotify API Client Infrastructure

Handles low-level Spotify API concerns:
- OAuth token management
- Rate limiting with exponential backoff
- Response caching to minimize API calls

Used by SpotifyMatcher for all API interactions.
"""

import os
import re
import time
import base64
import logging
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import requests

from cache_utils import get_cache_dir

logger = logging.getLogger(__name__)

# Sentinel value to distinguish "no cache exists" from "cached None (no match found)"
_CACHE_MISS = object()


class SpotifyRateLimitError(Exception):
    """Raised when Spotify API rate limit is hit"""
    def __init__(self, retry_after: int = None):
        self.retry_after = retry_after
        super().__init__(f"Spotify rate limit exceeded. Retry after {retry_after} seconds." if retry_after else "Spotify rate limit exceeded.")


class SpotifyClient:
    """
    Low-level Spotify API client with authentication, rate limiting, and caching.
    """
    
    def __init__(self, cache_days=30, force_refresh=False, 
                 rate_limit_delay=0.2, max_retries=3, logger=None):
        """
        Initialize Spotify Client
        
        Args:
            cache_days: Number of days before cache is considered stale
            force_refresh: If True, always fetch fresh data ignoring cache
            rate_limit_delay: Base delay between API calls (seconds)
            max_retries: Maximum number of retries for rate-limited requests
            logger: Optional logger instance (uses module logger if not provided)
        """
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
        
        # Stats tracking - will be updated by SpotifyMatcher
        self.stats = {
            'cache_hits': 0,
            'api_calls': 0,
            'rate_limit_hits': 0,
            'rate_limit_waits': 0
        }
    
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
    # AUTHENTICATION
    # ========================================================================
    
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