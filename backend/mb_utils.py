#!/usr/bin/env python3
"""
MusicBrainz Utilities
Shared utilities for searching and interacting with MusicBrainz API with caching support
"""

import time
import logging
import requests
import json
import hashlib
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class MusicBrainzSearcher:
    """Shared MusicBrainz search functionality with caching"""
    
    def __init__(self, cache_dir='cache/musicbrainz', cache_days=30, force_refresh=False):
        """
        Initialize MusicBrainz searcher with caching support
        
        Args:
            cache_dir: Directory to store cached MusicBrainz data
            cache_days: Number of days before cache is considered stale
            force_refresh: If True, always fetch fresh data ignoring cache
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'JazzReference/1.0 (https://github.com/yourusername/jazzreference)',
            'Accept': 'application/json'
        })
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # MusicBrainz requires 1 second between requests
        
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
        self.artist_cache_dir = self.cache_dir / 'artists'
        self.artist_cache_dir.mkdir(parents=True, exist_ok=True)
        self.work_cache_dir = self.cache_dir / 'works'
        self.work_cache_dir.mkdir(parents=True, exist_ok=True)
        self.recording_cache_dir = self.cache_dir / 'recordings'
        self.recording_cache_dir.mkdir(parents=True, exist_ok=True)
        self.release_cache_dir = self.cache_dir / 'releases'
        self.release_cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"MusicBrainz cache: {self.cache_dir} (expires after {cache_days} days, force_refresh={force_refresh})")

    def verify_musicbrainz_reference(self, artist_name, mb_id, context):
        """
        Verify that a MusicBrainz artist ID is valid
        
        Args:
            artist_name: Name of the artist
            mb_id: MusicBrainz artist ID (UUID)
            context: Dict with sample_songs for verification
            
        Returns:
            Dict with 'valid' (bool), 'confidence' (str), 'reason' (str)
        """
        try:
            logger.debug(f"Verifying MusicBrainz ID: {mb_id}")
            
            # Use the cached detail lookup
            data = self.get_artist_details(mb_id)
            
            if data is None:
                return {
                    'valid': False,
                    'confidence': 'certain',
                    'reason': 'MusicBrainz ID not found (404)'
                }
            
            # Check name similarity
            mb_name = data.get('name', '').lower()
            artist_name_lower = artist_name.lower()
            
            if mb_name != artist_name_lower:
                # Check if it's a close match
                if mb_name not in artist_name_lower and artist_name_lower not in mb_name:
                    return {
                        'valid': False,
                        'confidence': 'high',
                        'reason': f'Name mismatch: searched for "{artist_name}", MusicBrainz has "{data.get("name")}"'
                    }
            
            # Name matches, this is valid
            return {
                'valid': True,
                'confidence': 'high',
                'reason': f'Name matches: "{data.get("name")}"'
            }
            
        except requests.exceptions.Timeout:
            return {
                'valid': False,
                'confidence': 'uncertain',
                'reason': 'Request timed out'
            }
        except Exception as e:
            logger.error(f"Unexpected error verifying MusicBrainz: {e}", exc_info=True)
            return {
                'valid': False,
                'confidence': 'uncertain',
                'reason': f'Verification error: {str(e)}'
            }
    
    def _get_work_search_cache_path(self, title, composer):
        """
        Get the cache file path for a work search query
        
        Args:
            title: Song title
            composer: Composer name
            
        Returns:
            Path object for the cache file
        """
        query_string = f"{title}||{composer or ''}"
        query_hash = hashlib.md5(query_string.encode()).hexdigest()
        safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title.lower())[:50]
        filename = f"work_{safe_title}_{query_hash}.json"
        return self.search_cache_dir / filename
    
    def _get_artist_search_cache_path(self, artist_name):
        """
        Get the cache file path for an artist search query
        
        Args:
            artist_name: Artist name to search for
            
        Returns:
            Path object for the cache file
        """
        query_hash = hashlib.md5(artist_name.encode()).hexdigest()
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', artist_name.lower())[:50]
        filename = f"artist_search_{safe_name}_{query_hash}.json"
        return self.search_cache_dir / filename
    
    def _get_artist_detail_cache_path(self, mb_id):
        """
        Get the cache file path for an artist detail lookup
        
        Args:
            mb_id: MusicBrainz artist ID
            
        Returns:
            Path object for the cache file
        """
        filename = f"artist_{mb_id}.json"
        return self.artist_cache_dir / filename
    
    def _get_work_detail_cache_path(self, work_id):
        """
        Get the cache file path for a work detail lookup
        
        Args:
            work_id: MusicBrainz work ID
            
        Returns:
            Path object for the cache file
        """
        filename = f"work_{work_id}.json"
        return self.work_cache_dir / filename
    
    def _get_recording_detail_cache_path(self, recording_id):
        """
        Get the cache file path for a recording detail lookup
        
        Args:
            recording_id: MusicBrainz recording ID
            
        Returns:
            Path object for the cache file
        """
        filename = f"recording_{recording_id}.json"
        return self.recording_cache_dir / filename
    
    def _get_release_detail_cache_path(self, release_id):
        """
        Get the cache file path for a release detail lookup
        
        Args:
            release_id: MusicBrainz release ID
            
        Returns:
            Path object for the cache file
        """
        filename = f"release_{release_id}.json"
        return self.release_cache_dir / filename
    
    def _is_cache_valid(self, cache_path):
        """
        Check if cache file exists and is not expired
        
        Args:
            cache_path: Path to cache file
            
        Returns:
            bool: True if cache is valid and not expired
        """
        if not cache_path.exists():
            return False
        
        # Check file modification time
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - mtime
        
        is_valid = age.days < self.cache_days
        if is_valid:
            logger.debug(f"Cache valid (age: {age.days} days): {cache_path.name}")
        else:
            logger.debug(f"Cache expired (age: {age.days} days): {cache_path.name}")
        
        return is_valid
    
    def _load_from_cache(self, cache_path):
        """
        Load data from cache file
        
        Args:
            cache_path: Path to cache file
            
        Returns:
            Cached data dict, or None if not in cache
        """
        if not self._is_cache_valid(cache_path):
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                logger.debug(f"Loaded from cache: {cache_path.name}")
                return cache_data
        except Exception as e:
            logger.warning(f"Failed to load cache file {cache_path}: {e}")
            return None
    
    def _save_to_cache(self, cache_path, data):
        """
        Save data to cache file
        
        Args:
            cache_path: Path to cache file
            data: Data to cache (will be JSON serialized)
        """
        try:
            cache_data = {
                'data': data,
                'cached_at': datetime.now().isoformat()
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Saved to cache: {cache_path.name}")
        except Exception as e:
            logger.warning(f"Failed to save cache file {cache_path}: {e}")
    
    def rate_limit(self):
        """Enforce rate limiting for MusicBrainz API"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            logger.debug("rate_limit: sleep")
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def normalize_title(self, title):
        """
        Normalize title for comparison by handling various punctuation differences
        
        Args:
            title: Title to normalize
        
        Returns:
            Normalized title string
        """
        normalized = title.lower()
        
        # Replace all types of apostrophes with standard apostrophe
        # Includes: ' (right single quotation), ʼ (modifier letter apostrophe), 
        # ` (grave accent), ´ (acute accent)
        apostrophe_variants = [''', ''', 'ʼ', '`', '´']
        for variant in apostrophe_variants:
            normalized = normalized.replace(variant, "'")
        
        # Replace different types of dashes/hyphens
        dash_variants = ['–', '—', '−']  # en dash, em dash, minus
        for variant in dash_variants:
            normalized = normalized.replace(variant, '-')
        
        # Replace different types of quotes
        quote_variants = ['"', '"', '„', '«', '»']  # smart quotes, guillemets
        for variant in quote_variants:
            normalized = normalized.replace(variant, '"')
        
        return normalized
    
    def search_musicbrainz_work(self, title, composer):
        """
        Search MusicBrainz for a work by title and composer
        
        Uses multiple search strategies to maximize chances of finding a match:
        1. Try with exact phrase in quotes (most precise)
        2. Fall back to unquoted search if needed (broader)
        3. Don't over-constrain with composer (can filter results instead)
        
        Args:
            title: Song title
            composer: Composer name(s)
        
        Returns:
            MusicBrainz Work ID if found, None otherwise
        """
        # Check cache first (unless force_refresh is enabled)
        cache_path = self._get_work_search_cache_path(title, composer)
        if not self.force_refresh:
            cached = self._load_from_cache(cache_path)
            if cached:
                logger.debug(f"  Using cached work search result (cached: {cached['cached_at'][:10]})")
                self.last_made_api_call = False
                return cached.get('data')
        
        # Perform search
        self.last_made_api_call = True
        self.rate_limit()
        
        # Strategy 1: Search with exact title phrase (no composer constraint)
        # We don't add composer to query because it's often too restrictive
        # Better to get more results and filter by title match
        query = f'work:"{title}"'
        
        logger.debug(f"    Searching MusicBrainz: {query}")
        
        try:
            response = self.session.get(
                'https://musicbrainz.org/ws/2/work/',
                params={
                    'query': query,
                    'fmt': 'json',
                    'limit': 10  # Get more results since we're not filtering by composer
                },
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            works = data.get('works', [])
            
            # If no results with quoted search, try unquoted
            if not works:
                logger.debug(f"    No results with quoted search, trying unquoted...")
                self.rate_limit()
                
                query = title
                logger.debug(f"    Searching MusicBrainz: {query}")
                
                response = self.session.get(
                    'https://musicbrainz.org/ws/2/work/',
                    params={
                        'query': query,
                        'fmt': 'json',
                        'limit': 10
                    },
                    timeout=10
                )
                response.raise_for_status()
                data = response.json()
                works = data.get('works', [])
            
            if not works:
                logger.debug(f"    ✗ No MusicBrainz works found")
                # Cache the negative result too
                self._save_to_cache(cache_path, None)
                return None
            
            # Normalize search title for comparison
            normalized_search_title = self.normalize_title(title)
            
            # Look for exact or very close title match
            for work in works:
                work_title = work.get('title', '')
                normalized_work_title = self.normalize_title(work_title)
                
                # Check for exact match after normalization
                if normalized_work_title == normalized_search_title:
                    mb_id = work['id']
                    logger.debug(f"    ✓ Found: '{work['title']}' (ID: {mb_id})")
                    
                    # Show composer if available
                    if 'artist-relation-list' in work:
                        composers = [r['artist']['name'] for r in work['artist-relation-list'] 
                                   if r['type'] == 'composer']
                        if composers:
                            logger.debug(f"       Composer(s): {', '.join(composers)}")
                    
                    # Cache the result
                    self._save_to_cache(cache_path, mb_id)
                    return mb_id
            
            # If no exact match, show what was found
            logger.debug(f"    ⚠ Found {len(works)} works but no exact match:")
            for work in works[:3]:
                logger.debug(f"       - '{work['title']}'")
            
            # Cache the negative result
            self._save_to_cache(cache_path, None)
            return None
            
        except requests.exceptions.Timeout:
            logger.warning(f"    ⚠ MusicBrainz search timed out")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"    ✗ MusicBrainz search failed: {e}")
            return None
        except Exception as e:
            logger.error(f"    ✗ Error searching MusicBrainz: {e}")
            return None
    
    def _escape_lucene_query(self, text):
        """
        Escape special characters for Lucene query syntax
        
        Args:
            text: Text to escape
            
        Returns:
            Escaped text safe for Lucene queries
        """
        # Lucene special characters that need escaping
        special_chars = ['\\', '+', '-', '&', '|', '!', '(', ')', '{', '}', '[', ']', '^', '"', '~', '*', '?', ':']
        
        escaped = text
        for char in special_chars:
            escaped = escaped.replace(char, f'\\{char}')
        
        return escaped
    
    def search_musicbrainz_artist(self, artist_name):
        """
        Search MusicBrainz for an artist
        
        Args:
            artist_name: Name to search for
            
        Returns:
            List of matching artist dicts with 'id', 'name', 'score', etc.
        """
        # Check cache first (unless force_refresh is enabled)
        cache_path = self._get_artist_search_cache_path(artist_name)
        if not self.force_refresh:
            cached = self._load_from_cache(cache_path)
            if cached:
                logger.debug(f"  Using cached artist search result (cached: {cached['cached_at'][:10]})")
                self.last_made_api_call = False
                return cached.get('data', [])
        
        # Perform search
        self.last_made_api_call = True
        self.rate_limit()
        
        try:
            url = "https://musicbrainz.org/ws/2/artist/"
            # Escape special Lucene characters in the artist name
            escaped_name = self._escape_lucene_query(artist_name)
            params = {
                'query': f'artist:"{escaped_name}"',
                'fmt': 'json',
                'limit': 5
            }
            
            logger.debug(f"Searching MusicBrainz for artist: {artist_name}")
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.debug(f"MusicBrainz search failed (status {response.status_code})")
                return []
            
            data = response.json()
            artists = data.get('artists', [])
            
            # Cache the results
            self._save_to_cache(cache_path, artists)
            
            return artists
            
        except Exception as e:
            logger.error(f"Error searching MusicBrainz for {artist_name}: {e}")
            return []
    
    def get_artist_details(self, mb_id):
        """
        Get detailed information about a MusicBrainz artist
        
        Args:
            mb_id: MusicBrainz artist ID
            
        Returns:
            Dict with artist details, or None if not found
        """
        # Check cache first (unless force_refresh is enabled)
        cache_path = self._get_artist_detail_cache_path(mb_id)
        if not self.force_refresh:
            cached = self._load_from_cache(cache_path)
            if cached:
                logger.debug(f"  Using cached artist details (cached: {cached['cached_at'][:10]})")
                self.last_made_api_call = False
                return cached.get('data')
        
        # Fetch from API
        self.last_made_api_call = True
        self.rate_limit()
        
        try:
            url = f"https://musicbrainz.org/ws/2/artist/{mb_id}"
            params = {
                'fmt': 'json',
                'inc': 'recordings+tags'
            }
            
            logger.debug(f"Fetching MusicBrainz artist details: {mb_id}")
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 404:
                # Cache the negative result
                self._save_to_cache(cache_path, None)
                return None
            elif response.status_code != 200:
                return None
            
            data = response.json()
            
            # Cache the result
            self._save_to_cache(cache_path, data)
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching artist details from MusicBrainz: {e}")
            return None
    
    def get_work_recordings(self, work_id):
        """
        Get recordings for a MusicBrainz work
        
        Args:
            work_id: MusicBrainz work ID
            
        Returns:
            Dict with work data including recording relations, or None if not found
        """
        # Check cache first (unless force_refresh is enabled)
        cache_path = self._get_work_detail_cache_path(work_id)
        if not self.force_refresh:
            cached = self._load_from_cache(cache_path)
            if cached:
                logger.debug(f"  Using cached work recordings (cached: {cached['cached_at'][:10]})")
                self.last_made_api_call = False
                return cached.get('data')
        
        # Fetch from API
        self.last_made_api_call = True
        self.rate_limit()
        
        try:
            url = f"https://musicbrainz.org/ws/2/work/{work_id}"
            params = {
                'inc': 'artist-rels+recording-rels',
                'fmt': 'json'
            }
            
            logger.debug(f"Fetching MusicBrainz work recordings: {work_id}")
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 404:
                # Cache the negative result
                self._save_to_cache(cache_path, None)
                return None
            elif response.status_code != 200:
                return None
            
            data = response.json()
            
            # Cache the result
            self._save_to_cache(cache_path, data)
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching work recordings from MusicBrainz: {e}")
            return None
    
    def get_recording_details(self, recording_id):
        """
        Get detailed information about a MusicBrainz recording
        
        Args:
            recording_id: MusicBrainz recording ID
            
        Returns:
            Dict with recording details, or None if not found
        """
        # Check cache first (unless force_refresh is enabled)
        cache_path = self._get_recording_detail_cache_path(recording_id)
        if not self.force_refresh:
            cached = self._load_from_cache(cache_path)
            if cached:
                logger.debug(f"  Using cached recording details (cached: {cached['cached_at'][:10]})")
                self.last_made_api_call = False
                return cached.get('data')
        
        # Fetch from API
        self.last_made_api_call = True
        self.rate_limit()
        
        try:
            url = f"https://musicbrainz.org/ws/2/recording/{recording_id}"
            params = {
                'inc': 'releases+artist-credits+artist-rels',
                'fmt': 'json'
            }
            
            logger.debug(f"Fetching MusicBrainz recording details: {recording_id}")
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 404:
                # Cache the negative result
                self._save_to_cache(cache_path, None)
                return None
            elif response.status_code != 200:
                return None
            
            data = response.json()
            
            # Cache the result
            self._save_to_cache(cache_path, data)
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching recording details from MusicBrainz: {e}")
            return None
    
    def get_release_details(self, release_id):
        """
        Get detailed information about a MusicBrainz release
        
        Args:
            release_id: MusicBrainz release ID
            
        Returns:
            Dict with release details, or None if not found
        """
        # Check cache first (unless force_refresh is enabled)
        cache_path = self._get_release_detail_cache_path(release_id)
        if not self.force_refresh:
            cached = self._load_from_cache(cache_path)
            if cached:
                logger.debug(f"  Using cached release details (cached: {cached['cached_at'][:10]})")
                self.last_made_api_call = False
                return cached.get('data')
        
        # Fetch from API
        self.last_made_api_call = True
        self.rate_limit()
        
        try:
            url = f"https://musicbrainz.org/ws/2/release/{release_id}"
            params = {
                'inc': 'artist-credits+recordings+artist-rels',
                'fmt': 'json'
            }
            
            logger.debug(f"Fetching MusicBrainz release details: {release_id}")
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 404:
                # Cache the negative result
                self._save_to_cache(cache_path, None)
                return None
            elif response.status_code != 200:
                return None
            
            data = response.json()
            
            # Cache the result
            self._save_to_cache(cache_path, data)
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching release details from MusicBrainz: {e}")
            return None
    
    def clear_cache(self, search_only=False):
        """
        Clear the MusicBrainz cache
        
        Args:
            search_only: If True, only clear search cache (not artist details)
        """
        import shutil
        
        if search_only:
            if self.search_cache_dir.exists():
                shutil.rmtree(self.search_cache_dir)
                self.search_cache_dir.mkdir(parents=True, exist_ok=True)
                logger.info("Cleared MusicBrainz search cache")
        else:
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                self.search_cache_dir.mkdir(parents=True, exist_ok=True)
                self.artist_cache_dir.mkdir(parents=True, exist_ok=True)
                self.work_cache_dir.mkdir(parents=True, exist_ok=True)
                self.recording_cache_dir.mkdir(parents=True, exist_ok=True)
                self.release_cache_dir.mkdir(parents=True, exist_ok=True)
                logger.info("Cleared all MusicBrainz cache")


def update_song_composer(song_id: str, mb_searcher: MusicBrainzSearcher = None) -> bool:
    """
    Update song composer from MusicBrainz if not already set
    
    Checks for composer, writer, and lyricist relationships in MusicBrainz work data.
    
    Args:
        song_id: UUID of the song
        mb_searcher: Optional MusicBrainzSearcher instance (creates new one if not provided)
        
    Returns:
        bool: True if composer was updated, False otherwise
    """
    from db_utils import get_db_connection
    
    try:
        # Check if song has musicbrainz_id and no composer
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT musicbrainz_id, composer FROM songs WHERE id = %s",
                    (song_id,)
                )
                row = cur.fetchone()
                
                if not row:
                    return False
                
                mb_id = row['musicbrainz_id']
                composer = row['composer']                
                # Skip if no MusicBrainz ID or already has composer
                if not mb_id or composer:
                    return False
        
        # Create MusicBrainzSearcher if not provided
        if mb_searcher is None:
            mb_searcher = MusicBrainzSearcher()
        
        # Fetch work details from MusicBrainz
        work_data = mb_searcher.get_work_recordings(mb_id)
        
        if not work_data:
            logger.debug("No MusicBrainz work data found")
            return False
        
        # Extract composer/writer from artist relationships
        # Check multiple relationship types: composer, writer, lyricist
        creators = []
        creator_types_found = set()
        
        for relation in work_data.get('relations', []):
            rel_type = relation.get('type')
            
            # Check for any creator relationship type
            if rel_type in ['composer', 'writer', 'lyricist']:
                artist = relation.get('artist', {})
                creator_name = artist.get('name')
                
                if creator_name and creator_name not in creators:
                    creators.append(creator_name)
                    creator_types_found.add(rel_type)
        
        if not creators:
            logger.debug("No composer, writer, or lyricist found in MusicBrainz work data")
            return False
        
        # Join multiple creators with comma
        composer_name = ', '.join(creators)
        types_str = ', '.join(sorted(creator_types_found))
        
        # Update song with composer
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE songs SET composer = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (composer_name, song_id)
                )
                conn.commit()
        
        logger.info(f"✓ Updated composer to '{composer_name}' (from {types_str})")
        return True        

    except Exception as e:
        logger.error(f"Error updating composer: {e}")
        return False