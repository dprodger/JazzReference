"""
MusicBrainz Release Import Module
Core business logic for importing releases - can be used by CLI or background tasks

This module provides the MBReleaseImporter class which handles all the business logic
for importing MusicBrainz releases. It's designed to be reusable by both:
- Command-line scripts (import_mb_releases.py)
- Background workers (song_research.py via Flask app)

The module is decoupled from logging configuration and exit handling, allowing
callers to control these aspects.
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
    
    This class encapsulates all the business logic for importing releases from
    MusicBrainz, including finding songs, fetching recordings, and importing
    them with performer credits.
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
            'errors': 0
        }
    
    def find_song(self, song_identifier: str) -> Optional[Dict[str, Any]]:
        """
        Find a song by name or ID
        
        Args:
            song_identifier: Song name or UUID
            
        Returns:
            Song dict with keys: id, title, composer, musicbrainz_id
            Returns None if song not found
        """
        # Check if it looks like a UUID
        if song_identifier.startswith('song-') or len(song_identifier) == 36:
            return self._find_song_by_id(song_identifier)
        else:
            return self._find_song_by_name(song_identifier)
    
    def import_releases(self, song_identifier: str, limit: int = 100) -> Dict[str, Any]:
        """
        Main method to import releases for a song
        
        This is the primary entry point for importing releases. It handles:
        1. Finding the song in the database
        2. Verifying it has a MusicBrainz ID
        3. Fetching recordings from MusicBrainz
        4. Importing each recording with performer credits
        
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
        
        # Find the song
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
        
        # Fetch recordings from MusicBrainz
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
        
        # Process recordings
        errors = []
        with get_db_connection() as conn:
            for i, recording in enumerate(recordings, 1):
                self.logger.info(f"[{i}/{len(recordings)}] Processing: {recording.get('title', 'Unknown')}")
                try:
                    self._import_recording(conn, song['id'], recording)
                except Exception as e:
                    error_msg = f"Error importing recording: {e}"
                    self.logger.error(error_msg)
                    self.stats['errors'] += 1
                    errors.append(error_msg)
                    if not self.dry_run:
                        conn.rollback()
        
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
        """Fetch recordings for a MusicBrainz work ID"""
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
                    
                    # Fetch detailed recording information
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
    
    def _import_recording(self, conn, song_id: str, recording_data: Dict[str, Any]) -> bool:
        """
        Import a single recording
        
        Args:
            conn: Database connection (must be managed by caller)
            song_id: ID of the song this recording belongs to
            recording_data: MusicBrainz recording data dict
            
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
        
        # Insert recording
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
            self.logger.info(f"✓ Imported recording: {album_title} (ID: {recording_id})")
            
            # Link performers using shared importer
            self.performer_importer.link_performers_to_recording(conn, recording_id, recording_data)
            
            conn.commit()
            self.stats['releases_imported'] += 1
            return True