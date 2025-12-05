"""
Cover Art Archive Image Importer Module

Core business logic for importing cover art from the Cover Art Archive (CAA)
into the release_imagery table.

This module:
1. Finds releases for a song (or all unchecked releases)
2. Queries the Cover Art Archive API for each release
3. Creates/updates release_imagery records
4. Updates cover_art_checked_at timestamps to avoid repeated checks

Similar architecture to mb_release_importer.py - designed to be used by
CLI scripts or other modules.

SHARED FUNCTIONS:
- save_release_imagery(): Used by both CAAImageImporter (batch) and
  MBReleaseImporter (inline during release creation)
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List, Any, Set

from db_utils import get_db_connection
from caa_utils import CoverArtArchiveClient

# Module-level logger for shared functions
_logger = logging.getLogger(__name__)


def save_release_imagery(conn, release_id: str, images: List[Dict[str, Any]],
                         logger: Optional[logging.Logger] = None,
                         update_checked_timestamp: bool = True) -> Dict[str, int]:
    """
    Save imagery records and mark release as checked.

    This is the shared function used by:
    - MBReleaseImporter: For newly created releases during import
    - CAAImageImporter: For batch processing existing releases

    Args:
        conn: Database connection (caller manages transaction/commit)
        release_id: Database release UUID
        images: List of imagery dicts from CoverArtArchiveClient.extract_imagery_data()
        logger: Optional logger (uses module logger if not provided)
        update_checked_timestamp: If True, update cover_art_checked_at on the release

    Returns:
        Dict with counts: {'created': int, 'updated': int, 'existing': int}
    """
    log = logger or _logger
    result = {'created': 0, 'updated': 0, 'existing': 0}

    with conn.cursor() as cur:
        # Upsert each image
        for img in images:
            # Check if exists
            cur.execute("""
                SELECT id FROM release_imagery
                WHERE release_id = %s AND source = %s::imagery_source AND type = %s::imagery_type
            """, (release_id, img['source'], img['type']))

            existing = cur.fetchone()

            if existing:
                # Update existing record
                cur.execute("""
                    UPDATE release_imagery
                    SET source_id = %s,
                        source_url = %s,
                        image_url_small = %s,
                        image_url_medium = %s,
                        image_url_large = %s,
                        checksum = %s,
                        comment = %s,
                        approved = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE release_id = %s
                      AND source = %s::imagery_source
                      AND type = %s::imagery_type
                """, (
                    img['source_id'],
                    img['source_url'],
                    img['image_url_small'],
                    img['image_url_medium'],
                    img['image_url_large'],
                    img['checksum'],
                    img['comment'],
                    img['approved'],
                    release_id,
                    img['source'],
                    img['type']
                ))
                result['updated'] += 1
                log.debug(f"    Updated {img['type']} image")
            else:
                # Insert new record
                cur.execute("""
                    INSERT INTO release_imagery (
                        release_id, source, source_id, source_url, type,
                        image_url_small, image_url_medium, image_url_large,
                        checksum, comment, approved
                    ) VALUES (
                        %s, %s::imagery_source, %s, %s, %s::imagery_type,
                        %s, %s, %s, %s, %s, %s
                    )
                """, (
                    release_id,
                    img['source'],
                    img['source_id'],
                    img['source_url'],
                    img['type'],
                    img['image_url_small'],
                    img['image_url_medium'],
                    img['image_url_large'],
                    img['checksum'],
                    img['comment'],
                    img['approved']
                ))
                result['created'] += 1
                log.debug(f"    Created {img['type']} image")

        # Mark release as checked
        if update_checked_timestamp:
            cur.execute("""
                UPDATE releases
                SET cover_art_checked_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (release_id,))

    return result


class CAAImageImporter:
    """
    Handles Cover Art Archive image import operations.
    
    OPTIMIZATIONS:
    - Batch pre-fetch of existing imagery to skip API calls
    - Updates cover_art_checked_at even when no art found
    - Single database connection per batch operation
    """
    
    def __init__(self, dry_run: bool = False, force_refresh: bool = False,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the importer.
        
        Args:
            dry_run: If True, don't make database changes
            force_refresh: If True, bypass CAA cache and re-check releases
            logger: Optional logger instance (creates one if not provided)
        """
        self.dry_run = dry_run
        self.force_refresh = force_refresh
        self.logger = logger or logging.getLogger(__name__)
        self.caa_client = CoverArtArchiveClient(force_refresh=force_refresh)
        
        self.stats = {
            'releases_processed': 0,
            'releases_with_art': 0,
            'releases_no_art': 0,
            'images_created': 0,
            'images_existing': 0,
            'images_updated': 0,
            'api_calls': 0,
            'cache_hits': 0,
            'errors': 0,
        }
        
        self.logger.info(f"CAAImageImporter initialized (dry_run={dry_run}, force_refresh={force_refresh})")
    
    def import_for_song(self, song_identifier: str, limit: int = 500) -> Dict[str, Any]:
        """
        Import cover art for all releases of a song.
        
        Finds the song, retrieves all its releases, and fetches cover art
        from CAA for each release.
        
        Args:
            song_identifier: Song name or UUID
            limit: Maximum number of releases to process
            
        Returns:
            Dict with 'success', 'song', 'stats', and optionally 'error'
        """
        # Find the song
        song = self._find_song(song_identifier)
        
        if not song:
            return {
                'success': False,
                'error': f'Song not found: {song_identifier}',
                'stats': self.stats
            }
        
        self.logger.info(f"Found song: {song['title']} (ID: {song['id']})")
        
        # Get releases for this song
        # If force_refresh, include already-checked releases; otherwise skip them
        skip_checked = not self.force_refresh
        releases = self._get_releases_for_song(song['id'], limit, skip_checked=skip_checked)
        
        if not releases:
            if skip_checked:
                return {
                    'success': True,
                    'song': song,
                    'stats': self.stats,
                    'message': 'No unchecked releases found for this song (use --force-refresh to re-check)'
                }
            else:
                return {
                    'success': True,
                    'song': song,
                    'stats': self.stats,
                    'message': 'No releases found for this song'
                }
        
        self.logger.info(f"Found {len(releases)} releases to process")
        
        # Process releases
        self._process_releases(releases)
        
        # Update stats from CAA client
        caa_stats = self.caa_client.get_stats()
        self.stats['api_calls'] = caa_stats['api_calls']
        self.stats['cache_hits'] = caa_stats['cache_hits']
        
        return {
            'success': True,
            'song': song,
            'stats': self.stats
        }
    
    def import_all_unchecked(self, limit: int = 500) -> Dict[str, Any]:
        """
        Import cover art for all releases that haven't been checked yet.
        
        Finds releases where cover_art_checked_at IS NULL and processes them.
        
        Args:
            limit: Maximum number of releases to process
            
        Returns:
            Dict with 'success', 'stats', and optionally 'error'
        """
        # Get unchecked releases
        releases = self._get_unchecked_releases(limit)
        
        if not releases:
            return {
                'success': True,
                'stats': self.stats,
                'message': 'No unchecked releases found'
            }
        
        self.logger.info(f"Found {len(releases)} unchecked releases to process")
        
        # Process releases
        self._process_releases(releases)
        
        # Update stats from CAA client
        caa_stats = self.caa_client.get_stats()
        self.stats['api_calls'] = caa_stats['api_calls']
        self.stats['cache_hits'] = caa_stats['cache_hits']
        
        return {
            'success': True,
            'stats': self.stats
        }
    
    def _process_releases(self, releases: List[Dict[str, Any]]):
        """
        Process a list of releases, fetching and storing cover art.
        
        Args:
            releases: List of release dicts with 'id' and 'musicbrainz_release_id'
        """
        total = len(releases)
        
        for idx, release in enumerate(releases, 1):
            release_id = release['id']
            mb_release_id = release['musicbrainz_release_id']
            title = release.get('title', 'Unknown')
            
            self.logger.info(f"[{idx}/{total}] Processing: {title}")
            
            if not mb_release_id:
                self.logger.debug(f"  Skipping - no MusicBrainz ID")
                continue
            
            try:
                # Get cover art from CAA (this may hit cache or API)
                imagery_data = self.caa_client.extract_imagery_data(mb_release_id)
                
                if imagery_data:
                    # Count front vs back images
                    front_count = sum(1 for img in imagery_data if img['type'] == 'Front')
                    back_count = sum(1 for img in imagery_data if img['type'] == 'Back')
                    self.logger.info(f"  Found cover art: {front_count} front, {back_count} back")
                    self.stats['releases_with_art'] += 1
                    
                    # We only store one of each type due to unique constraint
                    # Collect the first front and first back image
                    images_to_store = []
                    stored_types = set()
                    for img in imagery_data:
                        if img['type'] not in stored_types:
                            images_to_store.append(img)
                            stored_types.add(img['type'])
                else:
                    self.logger.debug(f"  No cover art available")
                    self.stats['releases_no_art'] += 1
                    images_to_store = []
                
                # Single database connection for all operations on this release
                self._save_release_imagery(release_id, images_to_store)
                self.stats['releases_processed'] += 1
                
            except Exception as e:
                self.logger.error(f"  Error processing release: {e}")
                self.stats['errors'] += 1
    
    def _save_release_imagery(self, release_id: str, images: List[Dict[str, Any]]):
        """
        Save imagery records and mark release as checked in a single transaction.

        Uses the shared save_release_imagery() function for the actual database work.

        Args:
            release_id: Database release UUID
            images: List of imagery dicts to upsert (may be empty)
        """
        if self.dry_run:
            for img in images:
                self.logger.info(f"    [DRY RUN] Would create/update {img['type']} image")
                self.stats['images_created'] += 1
            self.logger.debug(f"    [DRY RUN] Would update cover_art_checked_at")
            return

        try:
            with get_db_connection() as conn:
                # Use shared function for database operations
                result = save_release_imagery(
                    conn, release_id, images,
                    logger=self.logger,
                    update_checked_timestamp=True
                )
                conn.commit()

                # Update stats from result
                self.stats['images_created'] += result['created']
                self.stats['images_updated'] += result['updated']

        except Exception as e:
            self.logger.error(f"    Error saving imagery: {e}")
            self.stats['errors'] += 1
    


    def _find_song(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Find a song by name or ID.
        
        Args:
            identifier: Song name or UUID
            
        Returns:
            Song dict with id, title, composer, or None if not found
        """
        identifier = str(identifier)
        
        # Check if it looks like a UUID
        if len(identifier) == 36 and '-' in identifier:
            return self._find_song_by_id(identifier)
        else:
            return self._find_song_by_name(identifier)
    
    def _find_song_by_name(self, song_name: str) -> Optional[Dict[str, Any]]:
        """Find a song in the database by name."""
        self.logger.debug(f"Searching for song: {song_name}")
        
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
                    self.logger.info(f"Found {len(results)} songs, using first match:")
                    for r in results[:5]:
                        self.logger.info(f"  - {r['title']}")
                
                return dict(results[0])
    
    def _find_song_by_id(self, song_id: str) -> Optional[Dict[str, Any]]:
        """Find a song in the database by ID."""
        self.logger.debug(f"Looking up song by ID: {song_id}")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, composer, musicbrainz_id
                    FROM songs
                    WHERE id = %s
                """, (song_id,))
                
                result = cur.fetchone()
                return dict(result) if result else None
    
    def _get_releases_for_song(self, song_id: str, limit: int, skip_checked: bool = True) -> List[Dict[str, Any]]:
        """
        Get all releases for a song via recordings.
        
        Args:
            song_id: Song UUID
            limit: Maximum releases to return
            skip_checked: If True, skip releases that have already been checked
            
        Returns:
            List of release dicts with id, musicbrainz_release_id, title
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Build query with optional filter for unchecked releases
                if skip_checked:
                    cur.execute("""
                        SELECT DISTINCT r.id, r.musicbrainz_release_id, r.title, r.artist_credit
                        FROM releases r
                        JOIN recording_releases rr ON r.id = rr.release_id
                        JOIN recordings rec ON rr.recording_id = rec.id
                        WHERE rec.song_id = %s
                          AND r.musicbrainz_release_id IS NOT NULL
                          AND r.cover_art_checked_at IS NULL
                        ORDER BY r.title
                        LIMIT %s
                    """, (song_id, limit))
                else:
                    cur.execute("""
                        SELECT DISTINCT r.id, r.musicbrainz_release_id, r.title, r.artist_credit
                        FROM releases r
                        JOIN recording_releases rr ON r.id = rr.release_id
                        JOIN recordings rec ON rr.recording_id = rec.id
                        WHERE rec.song_id = %s
                          AND r.musicbrainz_release_id IS NOT NULL
                        ORDER BY r.title
                        LIMIT %s
                    """, (song_id, limit))
                
                results = cur.fetchall()
                return [dict(r) for r in results]
    
    def _get_unchecked_releases(self, limit: int) -> List[Dict[str, Any]]:
        """
        Get releases that haven't been checked for cover art.
        
        Args:
            limit: Maximum releases to return
            
        Returns:
            List of release dicts with id, musicbrainz_release_id, title
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, musicbrainz_release_id, title, artist_credit
                    FROM releases
                    WHERE musicbrainz_release_id IS NOT NULL
                      AND cover_art_checked_at IS NULL
                    ORDER BY title
                    LIMIT %s
                """, (limit,))
                
                results = cur.fetchall()
                return [dict(r) for r in results]
    
    def get_imagery_for_release(self, release_id: str) -> List[Dict[str, Any]]:
        """
        Get existing imagery records for a release.
        
        Args:
            release_id: Release UUID
            
        Returns:
            List of imagery dicts
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, source, source_id, source_url, type,
                           image_url_small, image_url_medium, image_url_large,
                           checksum, comment, approved, created_at
                    FROM release_imagery
                    WHERE release_id = %s
                    ORDER BY type, source
                """, (release_id,))
                
                return [dict(r) for r in cur.fetchall()]