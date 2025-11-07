"""
MusicBrainz Release Import Module - FIXED VERSION
Core business logic for importing releases - optimized for connection pooling

KEY FIXES:
1. Don't hold connections during MusicBrainz API calls
2. Use shorter transactions - one per recording
3. Minimize connection hold time
4. Properly release connections between operations
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List, Any

from db_utils import get_db_connection
from mb_performer_importer import PerformerImporter
from mb_utils import MusicBrainzSearcher


class MBReleaseImporter:
    """
    Handles MusicBrainz release import operations
    
    OPTIMIZED FOR CONNECTION POOLING:
    - Opens connections only when needed
    - Closes connections quickly
    - No connections held during API calls
    """
    
    def __init__(self, dry_run: bool = False, logger: Optional[logging.Logger] = None):
        """
        Initialize the importer
        
        Args:
            dry_run: If True, don't make database changes
            logger: Optional logger instance (creates one if not provided)
        """
        self.dry_run = dry_run
        self.logger = logger or logging.getLogger(__name__)
        self.mb_searcher = MusicBrainzSearcher()
        self.performer_importer = PerformerImporter(dry_run=dry_run)
        self.stats = {
            'releases_found': 0,
            'releases_imported': 0,
            'releases_skipped': 0,
            'credits_added': 0,
            'errors': 0
        }
        self.logger.info("MBReleaseImport::init completed")
    
    def find_song(self, song_identifier: str) -> Optional[Dict[str, Any]]:
        """
        Find a song by name or ID
        
        Args:
            song_identifier: Song name or UUID
            
        Returns:
            Song dict with keys: id, title, composer, musicbrainz_id
            Returns None if song not found
        """
        song_identifier = str(song_identifier)
        
        # Check if it looks like a UUID
        if song_identifier.startswith('song-') or len(song_identifier) == 36:
            return self._find_song_by_id(song_identifier)
        else:
            return self._find_song_by_name(song_identifier)
    
    def import_releases(self, song_identifier: str, limit: int = 100) -> Dict[str, Any]:
        """
        Main method to import releases for a song
        
        CRITICAL FIX: No longer holds a connection open for the entire operation.
        Instead, uses short-lived connections for each step.
        
        Args:
            song_identifier: Song name or database ID
            limit: Max recordings to fetch (default: 100)
            
        Returns:
            dict: {
                'success': bool,
                'song': dict (if found),
                'stats': dict with import statistics,
                'errors': list of error messages (if any),
                'error': string error message (if failed)
            }
        """
        self.logger.info(f"Starting release import for: {song_identifier}")
        
        # STEP 1: Find the song (opens and closes connection)
        song = self.find_song(song_identifier)
        if not song:
            self.logger.error("Song not found")
            return {
                'success': False,
                'error': 'Song not found',
                'stats': self.stats
            }
        
        self.logger.info(f"Found song: {song['title']} by {song['composer']}")
        self.logger.info(f"Database ID: {song['id']}")
        self.logger.info(f"MusicBrainz Work ID: {song['musicbrainz_id']}")
        
        # Check for MusicBrainz ID
        if not song['musicbrainz_id']:
            self.logger.error("Song has no MusicBrainz ID")
            return {
                'success': False,
                'error': 'Song has no MusicBrainz ID',
                'song': song,
                'stats': self.stats
            }
        
        # STEP 2: Fetch recordings from MusicBrainz (NO DATABASE CONNECTION)
        # This is a potentially slow operation, so we don't hold any DB connections
        recordings = self._fetch_musicbrainz_recordings(
            song['musicbrainz_id'], 
            limit
        )
        
        if not recordings:
            self.logger.warning("No recordings found in MusicBrainz for this work")
            return {
                'success': False,
                'error': 'No recordings found',
                'song': song,
                'stats': self.stats
            }
        
        self.logger.info(f"Processing {len(recordings)} recordings...")
        
        # OPTIMIZATION: Batch-check which recordings already exist
        # This replaces 200+ individual queries with a single query
        self.logger.info("Checking database for existing recordings...")
        existing_map = self._batch_check_existing_recordings(song['id'], recordings)
        
        existing_count = sum(1 for info in existing_map.values() if info['exists'])
        existing_with_credits = sum(1 for info in existing_map.values() 
                                   if info['exists'] and info['has_credits'])
        
        self.logger.info(f"Found {existing_count} recordings in database")
        self.logger.info(f"  - {existing_with_credits} have performer credits (will skip)")
        self.logger.info(f"  - {existing_count - existing_with_credits} need credits added")
        self.logger.info("")
        
        # STEP 3: Process each recording with its own short transaction
        # CRITICAL FIX: Each recording gets its own connection that is quickly released
        errors = []
        for i, recording in enumerate(recordings, 1):
            releases = recording.get('releases', [])
            if not releases:
                self.logger.debug(f"[{i}/{len(recordings)}] Skipping - no releases")
                continue
            
            album_title = releases[0].get('title', 'Unknown Album')
            self.logger.info(f"[{i}/{len(recordings)}] {album_title[:60]}")
            
            # Use pre-checked existence info from batch query
            existing_info = existing_map.get(album_title)
            
            try:
                # Open connection ONLY for this one recording
                with get_db_connection() as conn:
                    self._import_recording(conn, song['id'], recording, existing_info)
                    # Connection is automatically committed and closed here
                    
            except Exception as e:
                error_msg = f"Error importing recording: {e}"
                self.logger.error(error_msg)
                self.stats['errors'] += 1
                errors.append(error_msg)
                # Connection was already rolled back automatically
        
        return {
            'success': True,
            'song': song,
            'stats': self.stats,
            'errors': errors if errors else None
        }
    
    # ========================================================================
    # Private methods - implementation details
    # ========================================================================
    
    def _find_song_by_name(self, song_name: str) -> Optional[Dict[str, Any]]:
        """Find a song in the database by name"""
        self.logger.info(f"Searching for song: {song_name}")
        
        # Open connection only for this query
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, composer, musicbrainz_id
                    FROM songs
                    WHERE title ILIKE %s
                    ORDER BY title
                """, (f'%{song_name}%',))
                
                results = cur.fetchall()
                
                if not results:
                    self.logger.warning(f"No songs found matching: {song_name}")
                    return None
                
                if len(results) > 1:
                    self.logger.info(f"Found {len(results)} matching songs:")
                    for i, song in enumerate(results, 1):
                        mb_status = "✓ Has MusicBrainz ID" if song['musicbrainz_id'] else "✗ No MusicBrainz ID"
                        self.logger.info(f"  {i}. {song['title']} by {song['composer']} - {mb_status}")
                        self.logger.info(f"     ID: {song['id']}")
                    
                    # Return first one with MusicBrainz ID, or first result
                    for song in results:
                        if song['musicbrainz_id']:
                            self.logger.info(f"Using: {song['title']} (has MusicBrainz ID)")
                            return song
                    
                    self.logger.info(f"Using first result: {results[0]['title']} (no MusicBrainz ID)")
                    return results[0]
                
                return results[0]
    
    def _find_song_by_id(self, song_id: str) -> Optional[Dict[str, Any]]:
        """Find a song in the database by ID"""
        self.logger.info(f"Looking up song ID: {song_id}")
        
        # Open connection only for this query
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, composer, musicbrainz_id
                    FROM songs
                    WHERE id = %s
                """, (song_id,))
                
                result = cur.fetchone()
                
                if not result:
                    self.logger.error(f"Song not found with ID: {song_id}")
                    return None
                
                return result
    
    def _fetch_musicbrainz_recordings(self, work_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch recordings for a MusicBrainz work ID
        
        IMPORTANT: This method does NOT use any database connections.
        It only makes API calls to MusicBrainz.
        """
        self.logger.info(f"Fetching recordings for MusicBrainz work: {work_id}")
        
        try:
            # Use cached method from mb_utils
            data = self.mb_searcher.get_work_recordings(work_id)
            
            if not data:
                self.logger.error("Could not fetch work from MusicBrainz")
                self.stats['errors'] += 1
                return []
            
            # Extract recordings from relations
            recordings = []
            relations = data.get('relations', [])
            
            self.logger.info(f"Found {len(relations)} related recordings in work")
            
            for i, relation in enumerate(relations, 1):
                if relation.get('type') == 'performance' and 'recording' in relation:
                    recording = relation['recording']
                    recording_id = recording.get('id')
                    recording_title = recording.get('title', 'Unknown')

                    self.logger.info(f"[{i}/{len(relations)}] Fetching: {recording_title[:60]}")                    

                    # Fetch detailed recording information (API call, no DB)
                    self.logger.debug(f"[{i}/{len(relations)}] Fetching details for: {recording_title}")
                    recording_details = self.mb_searcher.get_recording_details(recording_id)
                    
                    if recording_details:
                        recordings.append(recording_details)
                        
                        if len(recordings) >= limit:
                            self.logger.info(f"Reached limit of {limit} recordings")
                            break
            
            self.logger.info(f"Successfully fetched {len(recordings)} recording details")
            return recordings
            
        except Exception as e:
            self.logger.error(f"Error fetching recordings: {e}", exc_info=True)
            self.stats['errors'] += 1
            return []
    
    def _import_recording(self, conn, song_id: str, recording_data: Dict[str, Any],
                         existing_info: Optional[Dict[str, Any]] = None) -> bool:
        """
        Import a single recording
        
        IMPORTANT: This method expects an active connection to be passed in.
        The connection is managed by the caller and should be committed by the caller.
        
        Args:
            conn: Database connection (must be managed by caller)
            song_id: ID of the song this recording belongs to
            recording_data: MusicBrainz recording data dict
            existing_info: Optional pre-checked existence info from batch query
                          Format: {'exists': bool, 'id': str, 'has_credits': bool}
            
        Returns:
            True if imported, False if skipped
        """
        # Extract release information
        releases = recording_data.get('releases', [])
        if not releases:
            self.logger.debug("  No releases found for this recording")
            return False
        
        # Use the first release
        release = releases[0]
        album_title = release.get('title', 'Unknown Album')
        release_date = release.get('date')
        
        # Parse date
        release_year = None
        formatted_date = None
        
        if release_date:
            try:
                # Try to parse as full date YYYY-MM-DD
                date_parts = release_date.split('-')
                if len(date_parts) >= 1:
                    release_year = int(date_parts[0])
                if len(date_parts) == 3:
                    formatted_date = datetime.strptime(release_date, '%Y-%m-%d').date()
                elif len(date_parts) == 2:
                    formatted_date = datetime.strptime(f"{release_date}-01", '%Y-%m-%d').date()
            except (ValueError, IndexError):
                self.logger.debug(f"Could not parse date: {release_date}")
                pass
        
        # Extract MusicBrainz recording ID
        mb_recording_id = recording_data.get('id')
        
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would import: {album_title} ({release_year or 'unknown year'})")
            self.logger.info(f"[DRY RUN]   Date: {formatted_date or 'None'}")
            # Show performer info that would be imported
            self.performer_importer.link_performers_to_recording(conn, None, recording_data)
            self.stats['releases_found'] += 1
            return True
        
        # Check if recording already exists
        # Use pre-checked info from batch query if available, otherwise do individual query
        if existing_info:
            # Use batch-checked existence info (FAST)
            recording_exists = existing_info['exists']
            recording_id = existing_info['id']
            has_credits = existing_info['has_credits']
        else:
            # Fall back to individual queries (SLOW - only happens if batch check wasn't done)
            existing_recording = self._find_existing_recording(conn, song_id, mb_recording_id, album_title)
            if existing_recording:
                recording_exists = True
                recording_id = existing_recording['id']
                has_credits = self._recording_has_credits(conn, recording_id)
            else:
                recording_exists = False
                recording_id = None
                has_credits = False
        
        if recording_exists:
            if has_credits:
                self.logger.info(f"⊘ Skipped: already exists with credits")
                self.stats['releases_skipped'] += 1
                return False
            else:
                self.logger.info(f"+ Adding credits to existing recording")
                # Add performer credits to existing recording
                self.performer_importer.link_performers_to_recording(conn, recording_id, recording_data)
                # Caller will commit
                self.stats['credits_added'] += 1
                return True
        
        # Insert new recording
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO recordings (
                    song_id, album_title, recording_year, recording_date,
                    is_canonical, musicbrainz_id
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                song_id,
                album_title,
                release_year,
                formatted_date,
                False,  # Not canonical by default
                mb_recording_id
            ))
            
            recording_id = cur.fetchone()['id']
            self.logger.info(f"✓ Imported new recording (ID: {recording_id})")
            
            # Link performers using shared importer
            self.performer_importer.link_performers_to_recording(conn, recording_id, recording_data)
            
            # Caller will commit
            self.stats['releases_imported'] += 1
            return True
    
    def _find_existing_recording(self, conn, song_id: str, mb_recording_id: Optional[str], 
                                 album_title: str) -> Optional[Dict[str, Any]]:
        """
        Check if a recording already exists
        
        Args:
            conn: Database connection
            song_id: Song ID to search within
            mb_recording_id: MusicBrainz recording ID (preferred)
            album_title: Album title (fallback)
            
        Returns:
            Recording dict with 'id' key, or None if not found
        """
        with conn.cursor() as cur:
            # First try to find by MusicBrainz ID (most reliable)
            if mb_recording_id:
                cur.execute("""
                    SELECT id
                    FROM recordings
                    WHERE song_id = %s AND musicbrainz_id = %s
                """, (song_id, mb_recording_id))
                
                result = cur.fetchone()
                if result:
                    return result
            
            # Fallback: find by song_id + album_title
            cur.execute("""
                SELECT id
                FROM recordings
                WHERE song_id = %s AND album_title = %s
            """, (song_id, album_title))
            
            return cur.fetchone()
    
    def _recording_has_credits(self, conn, recording_id: str) -> bool:
        """
        Check if a recording has any performer credits
        
        Args:
            conn: Database connection
            recording_id: Recording ID to check
            
        Returns:
            True if recording has performer credits, False otherwise
        """
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 
                    FROM recording_performers
                    WHERE recording_id = %s
                )
            """, (recording_id,))
            
            return cur.fetchone()['exists']
    
    def _batch_check_existing_recordings(self, song_id: str, 
                                         recording_data_list: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Batch check which recordings already exist in database
        
        This replaces 200+ individual queries with a single batch query,
        significantly improving performance on repeat runs.
        
        Args:
            song_id: Song ID to check recordings for
            recording_data_list: List of MusicBrainz recording data dicts
            
        Returns:
            Dict mapping album_title -> {
                'exists': bool,
                'id': str (UUID),
                'has_credits': bool,
                'mb_id': str (MusicBrainz ID)
            }
        """
        # Extract album titles and MusicBrainz IDs
        album_data = {}
        for rec_data in recording_data_list:
            releases = rec_data.get('releases', [])
            if releases:
                album_title = releases[0].get('title', 'Unknown Album')
                mb_recording_id = rec_data.get('id')
                album_data[album_title] = mb_recording_id
        
        if not album_data:
            return {}
        
        album_titles = list(album_data.keys())
        
        # Single batch query to check all recordings at once
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        r.album_title,
                        r.id,
                        r.musicbrainz_id,
                        (
                            SELECT COUNT(*) 
                            FROM recording_performers rp 
                            WHERE rp.recording_id = r.id
                        ) as credit_count
                    FROM recordings r
                    WHERE r.song_id = %s
                    AND r.album_title = ANY(%s)
                """, (song_id, album_titles))
                
                results = {}
                for row in cur.fetchall():
                    results[row['album_title']] = {
                        'exists': True,
                        'id': row['id'],
                        'has_credits': row['credit_count'] > 0,
                        'mb_id': row['musicbrainz_id']
                    }
                
                # Add entries for albums that don't exist
                for title, mb_id in album_data.items():
                    if title not in results:
                        results[title] = {
                            'exists': False,
                            'id': None,
                            'has_credits': False,
                            'mb_id': mb_id
                        }
                
                return results