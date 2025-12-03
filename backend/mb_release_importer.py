"""
MusicBrainz Release Import Module - OPTIMIZED VERSION

PERFORMANCE OPTIMIZATIONS:
1. Single database connection per recording (not per release)
2. Pre-check if releases exist BEFORE fetching from MusicBrainz API
3. Only fetch release details for releases that don't exist in DB
4. Batch all release operations for a recording in one transaction
5. NEW (2025-12): Song-level pre-fetch of recordings with performers
   - Single query to get all recordings that already have performers
   - Skips add_performers_to_recording() entirely for these recordings
   - Reduces "everything cached" case from 4 queries/recording to 1 query total

KEY ARCHITECTURE (UPDATED):
- Recording = a specific sound recording (same audio across all releases)
- Release = a product (album, CD, digital release, etc.)
- A recording can appear on multiple releases
- Performers are associated with RECORDINGS (the audio), not releases
- Releases store Spotify/album art data and release-specific credits (producers, engineers)
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List, Any, Set

from db_utils import get_db_connection
from mb_performer_importer import PerformerImporter
from mb_utils import MusicBrainzSearcher


class MBReleaseImporter:
    """
    Handles MusicBrainz recording and release import operations
    
    OPTIMIZED FOR:
    - Minimal database connections (one per recording batch)
    - Skip API calls for existing releases
    - Efficient lookup table caching
    - Song-level pre-fetch to skip performer checks for existing recordings
    
    UPDATED: Recording-Centric Performer Architecture
    - Performers are now added to recordings (aggregated from all releases)
    - Releases only get release-specific credits (producers, engineers)
    """
    
    def __init__(self, dry_run: bool = False, force_refresh: bool = False, logger: Optional[logging.Logger] = None):
        """
        Initialize the importer
        
        Args:
            dry_run: If True, don't make database changes
            force_refresh: If True, bypass MusicBrainz cache
            logger: Optional logger instance (creates one if not provided)
        """
        self.dry_run = dry_run
        self.force_refresh = force_refresh
        self.logger = logger or logging.getLogger(__name__)
        self.mb_searcher = MusicBrainzSearcher(force_refresh=force_refresh)
        self.performer_importer = PerformerImporter(dry_run=dry_run)
        self.stats = {
            'recordings_found': 0,
            'recordings_created': 0,
            'recordings_existing': 0,
            'releases_found': 0,
            'releases_created': 0,
            'releases_existing': 0,
            'releases_skipped_api': 0,  # Count of API calls skipped
            'links_created': 0,
            'performers_linked': 0,
            'performers_added_to_recordings': 0,  # NEW: Performers added to recordings
            'release_credits_linked': 0,  # NEW: Release-specific credits (producers, etc.)
            'performers_skipped_existing': 0,  # NEW: Recordings skipped because they already have performers
            'errors': 0,  # Error count
        }
        
        # Cache for lookup table IDs (populated once per import)
        self._format_cache = {}
        self._status_cache = {}
        self._packaging_cache = {}
        
        self.logger.info(f"MBReleaseImporter initialized (optimized version, force_refresh={force_refresh})")
    
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
        if len(song_identifier) == 36 and '-' in song_identifier:
            return self._find_song_by_id(song_identifier)
        else:
            return self._find_song_by_name(song_identifier)
    
    def import_releases(self, song_identifier: str, limit: int = 200) -> Dict[str, Any]:
        """
        Main method to import recordings and releases for a song
        
        This method:
        1. Finds the song by name or ID
        2. Fetches recordings from MusicBrainz (via the work)
        3. Pre-fetches which recordings already have performers (OPTIMIZATION)
        4. For each recording:
           - Creates the recording if it doesn't exist
           - Adds performers to the RECORDING (only if not already done)
           - Checks which releases already exist (OPTIMIZATION)
           - Only fetches details for NEW releases
           - Creates release-specific credits (producers, engineers)
        5. Links recordings to releases
        
        Args:
            song_identifier: Song name or UUID to find recordings for
            limit: Maximum number of recordings to process
            
        Returns:
            Dict with import statistics
        """
        # Find the song
        song = self.find_song(song_identifier)
        
        if not song:
            return {'success': False, 'error': 'Song not found', 'stats': self.stats}
        
        self.logger.info(f"Found song: {song['title']} (ID: {song['id']})")
        
        # Get MusicBrainz work ID
        mb_work_id = song.get('musicbrainz_id')
        
        if not mb_work_id:
            return {'success': False, 'error': 'Song has no MusicBrainz ID', 'stats': self.stats}
        
        # Fetch recordings from MusicBrainz
        recordings = self._fetch_musicbrainz_recordings(mb_work_id, limit)
        
        if not recordings:
            return {'success': False, 'error': 'No recordings found on MusicBrainz', 'stats': self.stats}
        
        self.logger.info(f"Found {len(recordings)} recordings to process")
        
        # Process each recording with a SINGLE connection
        with get_db_connection() as conn:
            # Pre-load lookup table caches (one-time cost)
            self._load_lookup_caches(conn)
            
            # =======================================================================
            # OPTIMIZATION: Song-level pre-fetch of ALL data needed
            # This replaces per-recording queries with batch queries upfront
            # =======================================================================
            
            # Collect all MB IDs from recordings
            mb_recording_ids = [r.get('id') for r in recordings if r.get('id')]
            
            # Collect all MB release IDs from all recordings
            all_mb_release_ids = []
            for rec in recordings:
                for rel in (rec.get('releases') or []):
                    if rel.get('id'):
                        all_mb_release_ids.append(rel.get('id'))
            
            # 1. Batch fetch: recordings with performers (skip performer import)
            recordings_with_performers = self._get_recordings_with_performers(
                conn, mb_recording_ids
            )
            self.logger.debug(f"  Pre-fetched {len(recordings_with_performers)} recordings with performers")
            
            # 2. Batch fetch: existing recordings by MB ID
            existing_recordings = self._get_existing_recordings_batch(
                conn, mb_recording_ids
            )
            self.logger.debug(f"  Pre-fetched {len(existing_recordings)} existing recordings")
            
            # 3. Batch fetch: existing releases by MB ID
            existing_releases_all = self._get_existing_release_ids(
                conn, all_mb_release_ids
            )
            self.logger.debug(f"  Pre-fetched {len(existing_releases_all)} existing releases")
            
            # 4. Batch fetch: all recording-release links for existing recordings
            existing_recording_db_ids = list(existing_recordings.values())
            all_existing_links = self._get_all_recording_release_links(
                conn, existing_recording_db_ids
            )
            self.logger.debug(f"  Pre-fetched {len(all_existing_links)} existing links")
            
            for i, mb_recording in enumerate(recordings, 1):
                recording_title = mb_recording.get('title', 'Unknown')
                self.logger.info(f"\n[{i}/{len(recordings)}] Processing: {recording_title}")
                
                try:
                    self._process_recording_fast(
                        conn, song['id'], mb_recording, 
                        recordings_with_performers,
                        existing_recordings,
                        existing_releases_all,
                        all_existing_links
                    )
                    self.stats['recordings_found'] += 1
                except Exception as e:
                    self.logger.error(f"  Error processing recording: {e}")
                    self.stats['errors'] += 1
                    # Rollback the failed transaction so subsequent operations can proceed
                    try:
                        conn.rollback()
                    except Exception:
                        pass  # Connection might already be closed
                    # Continue with next recording
                    continue
        return {
            'success': True,
            'song': song,
            'recordings_processed': len(recordings),
            'stats': self.stats
        }
    
    def _get_recordings_with_performers(self, conn, mb_recording_ids: List[str]) -> Set[str]:
        """
        Get set of MusicBrainz recording IDs that already have performers linked.
        
        OPTIMIZATION: Single query to check all recordings at once.
        This allows us to skip add_performers_to_recording() entirely for
        recordings that already have performers, saving 4 DB queries each.
        
        Args:
            conn: Database connection
            mb_recording_ids: List of MusicBrainz recording IDs to check
            
        Returns:
            Set of MB recording IDs that have at least one performer
        """
        if not mb_recording_ids:
            return set()
        
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT r.musicbrainz_id
                FROM recordings r
                INNER JOIN recording_performers rp ON r.id = rp.recording_id
                WHERE r.musicbrainz_id = ANY(%s)
            """, (mb_recording_ids,))
            
            return {row['musicbrainz_id'] for row in cur.fetchall()}
    
    def _get_existing_recordings_batch(self, conn, mb_recording_ids: List[str]) -> Dict[str, str]:
        """
        Batch fetch existing recordings by MusicBrainz ID.
        
        OPTIMIZATION: Single query for all recordings instead of one per recording.
        
        Args:
            conn: Database connection
            mb_recording_ids: List of MusicBrainz recording IDs
            
        Returns:
            Dict mapping MB recording ID -> our database recording ID
        """
        if not mb_recording_ids:
            return {}
        
        with conn.cursor() as cur:
            cur.execute("""
                SELECT musicbrainz_id, id
                FROM recordings
                WHERE musicbrainz_id = ANY(%s)
            """, (mb_recording_ids,))
            
            return {row['musicbrainz_id']: row['id'] for row in cur.fetchall()}
    
    def _get_all_recording_release_links(self, conn, recording_ids: List[str]) -> Dict[str, Set[str]]:
        """
        Batch fetch all recording-release links for multiple recordings.
        
        OPTIMIZATION: Single query for all recordings instead of one per recording.
        
        Args:
            conn: Database connection
            recording_ids: List of our recording IDs
            
        Returns:
            Dict mapping recording_id -> set of linked release_ids
        """
        if not recording_ids:
            return {}
        
        result = {}
        with conn.cursor() as cur:
            cur.execute("""
                SELECT recording_id, release_id
                FROM recording_releases
                WHERE recording_id = ANY(%s)
            """, (recording_ids,))
            
            for row in cur.fetchall():
                rec_id = row['recording_id']
                if rec_id not in result:
                    result[rec_id] = set()
                result[rec_id].add(row['release_id'])
        
        return result
    
    def _load_lookup_caches(self, conn) -> None:
        """
        Pre-load lookup table caches for efficient access
        
        OPTIMIZATION: Single query each for formats, statuses, packaging
        """
        self.logger.debug("Pre-loading lookup table caches...")
        
        with conn.cursor() as cur:
            # Load formats
            cur.execute("SELECT id, name FROM release_formats")
            for row in cur.fetchall():
                self._format_cache[row['name']] = row['id']
            
            # Load statuses (by lowercase name)
            cur.execute("SELECT id, LOWER(name) as name FROM release_statuses")
            for row in cur.fetchall():
                self._status_cache[row['name']] = row['id']
            
            # Load packaging
            cur.execute("SELECT id, name FROM release_packaging")
            for row in cur.fetchall():
                self._packaging_cache[row['name']] = row['id']
        
        self.logger.debug(f"  Loaded {len(self._format_cache)} formats, "
                         f"{len(self._status_cache)} statuses, "
                         f"{len(self._packaging_cache)} packaging types")
    
    def _process_recording(self, conn, song_id: str, mb_recording: Dict[str, Any],
                           recordings_with_performers: Set[str]) -> None:
        """
        Process a single MusicBrainz recording (ORIGINAL VERSION)
        
        Kept for backward compatibility. Use _process_recording_fast for better performance.
        """
        # Delegate to fast version with empty caches (will do per-recording queries)
        self._process_recording_fast(
            conn, song_id, mb_recording,
            recordings_with_performers,
            {},  # existing_recordings
            {},  # existing_releases_all
            {}   # all_existing_links
        )
    
    def _process_recording_fast(self, conn, song_id: str, mb_recording: Dict[str, Any],
                                 recordings_with_performers: Set[str],
                                 existing_recordings: Dict[str, str],
                                 existing_releases_all: Dict[str, str],
                                 all_existing_links: Dict[str, Set[str]]) -> None:
        """
        Process a single MusicBrainz recording (OPTIMIZED VERSION)
        
        FULLY OPTIMIZED: Uses pre-fetched data for ALL lookups.
        For "everything exists" case: ZERO database queries per recording.
        
        Args:
            conn: Database connection (reused from caller)
            song_id: Our database song ID
            mb_recording: MusicBrainz recording data
            recordings_with_performers: Set of MB recording IDs that already have performers
            existing_recordings: Dict of MB recording ID -> our recording ID
            existing_releases_all: Dict of MB release ID -> our release ID
            all_existing_links: Dict of our recording ID -> set of linked release IDs
        """
        mb_recording_id = mb_recording.get('id')
        
        # Get the releases from the recording data
        mb_releases = mb_recording.get('releases') or []
        if not mb_releases:
            self.logger.info("  No releases found for this recording")
            return
        
        # Use the first release for album title (for the recording)
        first_release = mb_releases[0]
        album_title = first_release.get('title', 'Unknown Album')
        
        # Extract recording date/year from first release
        release_date = first_release.get('date', '')
        release_year = None
        formatted_date = None
        
        if release_date:
            try:
                if len(release_date) >= 4:
                    release_year = int(release_date[:4])
                if len(release_date) >= 10:
                    formatted_date = release_date[:10]
            except (ValueError, TypeError):
                pass
        
        # STEP 1: Get or create the recording (use cache first - NO QUERY if exists)
        recording_id = existing_recordings.get(mb_recording_id)
        if recording_id:
            self.logger.debug(f"  Recording exists (by MB ID)")
            self.stats['recordings_existing'] += 1
        else:
            # Recording doesn't exist - need to create it
            recording_id = self._create_recording(
                conn, song_id, mb_recording_id, album_title, release_year, formatted_date
            )
            if recording_id:
                # Add to cache for future reference
                existing_recordings[mb_recording_id] = recording_id
        
        if not recording_id and not self.dry_run:
            self.logger.error("  Failed to get/create recording")
            return
        
        # STEP 2: Add performers (SKIP if already has performers - NO QUERY)
        if mb_recording_id in recordings_with_performers:
            self.logger.debug(f"  Skipping performer check - recording already has performers")
            self.stats['performers_skipped_existing'] += 1
        else:
            performers_added = self.performer_importer.add_performers_to_recording(
                conn, recording_id, mb_recording, 
                source_release_title=album_title
            )
            if performers_added > 0:
                self.stats['performers_added_to_recordings'] += performers_added
                self.logger.info(f"  Added {performers_added} performers to recording")
                recordings_with_performers.add(mb_recording_id)
        
        # STEP 3: Check releases using pre-fetched cache (NO QUERY)
        # Filter existing_releases_all to just this recording's releases
        existing_releases = {
            mb_id: db_id 
            for mb_id, db_id in existing_releases_all.items()
            if mb_id in {r.get('id') for r in mb_releases}
        }
        
        # STEP 4: Get existing links from pre-fetched cache (NO QUERY)
        existing_links = all_existing_links.get(recording_id, set()) if recording_id else set()
        
        # Count statistics
        fully_linked_count = len(existing_links & set(existing_releases.values()))
        new_releases_count = len(mb_releases) - len(existing_releases)
        needs_linking_count = len(existing_releases) - fully_linked_count
        
        self.logger.info(f"  Processing {len(mb_releases)} releases "
                       f"({len(existing_releases)} in DB, {fully_linked_count} already linked, "
                       f"{needs_linking_count} need linking, {new_releases_count} new)...")
        
        # STEP 5: Process each release (only does work for new/unlinked releases)
        for mb_release in mb_releases:
            self._process_release_in_transaction(
                conn, recording_id, mb_recording_id, mb_recording, 
                mb_release, existing_releases, existing_links
            )
    
    def _create_recording(self, conn, song_id: str, mb_recording_id: str,
                           album_title: str, release_year: Optional[int],
                           formatted_date: Optional[str]) -> Optional[str]:
        """
        Create a new recording in the database.
        
        Separated from get_or_create to allow cache-first lookup.
        """
        if self.dry_run:
            self.logger.info(f"  [DRY RUN] Would create recording: {album_title}")
            return None
        
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
                False,
                mb_recording_id
            ))
            
            recording_id = cur.fetchone()['id']
            self.logger.info(f"  ✓ Created recording: {album_title[:50]}")
            self.stats['recordings_created'] += 1
            
            return recording_id
    
    def _get_existing_release_ids(self, conn, mb_release_ids: List[str]) -> Dict[str, str]:
        """
        Check which MusicBrainz release IDs already exist in the database
        
        OPTIMIZATION: Single batch query instead of one per release
        Now returns mapping of MB ID -> our release ID for efficient lookup
        
        Args:
            conn: Database connection
            mb_release_ids: List of MusicBrainz release IDs to check
            
        Returns:
            Dict mapping MusicBrainz release ID -> our database release ID
        """
        if not mb_release_ids:
            return {}
        
        with conn.cursor() as cur:
            # Use ANY() for efficient batch lookup, return both IDs
            cur.execute("""
                SELECT musicbrainz_release_id, id 
                FROM releases 
                WHERE musicbrainz_release_id = ANY(%s)
            """, (mb_release_ids,))
            
            return {row['musicbrainz_release_id']: row['id'] for row in cur.fetchall()}
    
    def _get_existing_recording_release_links(self, conn, recording_id: str, 
                                               release_ids: List[str]) -> Set[str]:
        """
        Check which recording-release links already exist
        
        OPTIMIZATION: Single batch query for all releases
        
        Args:
            conn: Database connection
            recording_id: Our recording ID
            release_ids: List of our release IDs to check
            
        Returns:
            Set of release IDs that are already linked to this recording
        """
        if not release_ids or not recording_id:
            return set()
        
        with conn.cursor() as cur:
            cur.execute("""
                SELECT release_id 
                FROM recording_releases 
                WHERE recording_id = %s AND release_id = ANY(%s)
            """, (recording_id, release_ids))
            
            return {row['release_id'] for row in cur.fetchall()}
    
    def _process_release_in_transaction(
        self, conn, recording_id: Optional[str], mb_recording_id: str,
        mb_recording: Dict[str, Any], mb_release: Dict[str, Any],
        existing_releases: Dict[str, str], existing_links: Set[str]
    ) -> None:
        """
        Process a single release within an existing transaction
        
        OPTIMIZED:
        - Uses pre-fetched existing_releases mapping (MB ID -> our ID)
        - Uses pre-fetched existing_links set (our release IDs already linked)
        - Skips entirely for releases that are already fully linked
        - No individual DB queries for existing releases
        
        UPDATED: Recording-Centric Performer Architecture
        - Performers are added to RECORDINGS, not releases
        - Releases only get release-specific credits (producers, engineers)
        
        Args:
            conn: Database connection (reused)
            recording_id: Our database recording ID (may be None in dry-run)
            mb_recording_id: MusicBrainz recording ID
            mb_recording: MusicBrainz recording data
            mb_release: Basic MusicBrainz release data
            existing_releases: Dict mapping MB release ID -> our release ID
            existing_links: Set of our release IDs already linked to this recording
        """
        mb_release_id = mb_release.get('id')
        release_title = mb_release.get('title', 'Unknown')
        
        # OPTIMIZATION: Check if release exists using pre-fetched data
        if mb_release_id in existing_releases:
            release_id = existing_releases[mb_release_id]
            self.stats['releases_existing'] += 1
            self.stats['releases_skipped_api'] += 1
            
            # Check if already linked using pre-fetched data (no DB query!)
            if release_id in existing_links:
                self.logger.debug(f"    Skipping fully-linked release: {release_title[:40]}")
                return
            
            # Need to create link (but release exists)
            if recording_id:
                self.logger.debug(f"    Creating link for existing release: {release_title[:40]}")
                self._link_recording_to_release_fast(
                    conn, recording_id, release_id, mb_recording_id, mb_release
                )
            return
        
        # Release doesn't exist - fetch full details from MusicBrainz
        release_details = self.mb_searcher.get_release_details(mb_release_id)
        
        if not release_details:
            self.logger.warning(f"    Could not fetch details for release: {release_title[:40]}")
            return
        
        self.stats['releases_found'] += 1
        
        # Parse release data
        release_data = self._parse_release_data(release_details)
        
        if self.dry_run:
            self._log_release_info(release_data)
            return
        
        # Create the release
        release_id = self._create_release(conn, release_data)
        
        if release_id:
            self.stats['releases_created'] += 1
            self.logger.info(f"    ✓ Created release: {release_title[:40]}")
            
            # Link recording to release
            if recording_id:
                self._link_recording_to_release(conn, recording_id, release_id, mb_release)
            
            # Link release-specific credits (producers, engineers, etc.)
            # These go to the RELEASE, not the recording
            credits_linked = self.performer_importer.link_release_credits(
                conn, release_id, mb_recording, release_details
            )
            if credits_linked > 0:
                self.stats['release_credits_linked'] += credits_linked
    
    def _get_release_id_by_mb_id(self, conn, mb_release_id: str) -> Optional[str]:
        """Get our database release ID by MusicBrainz release ID"""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM releases WHERE musicbrainz_release_id = %s
            """, (mb_release_id,))
            result = cur.fetchone()
            return result['id'] if result else None
    
    def _get_or_create_recording(self, conn, song_id: str, mb_recording_id: str,
                                  album_title: str, release_year: Optional[int],
                                  formatted_date: Optional[str]) -> Optional[str]:
        """
        Get existing recording or create new one
        
        IMPORTANT: For MusicBrainz imports, we ONLY match by MusicBrainz recording ID.
        Album title matching is NOT reliable because different artists can have
        albums with the same title (e.g., Grant Green's "Born to Be Blue" vs 
        Freddie Hubbard's "Born to Be Blue").
        
        Args:
            conn: Database connection
            song_id: Song ID
            mb_recording_id: MusicBrainz recording ID (unique identifier)
            album_title: Album title (for display/storage only, NOT for matching)
            release_year: Year of release
            formatted_date: Formatted date string
            
        Returns:
            Recording ID or None
        """
        with conn.cursor() as cur:
            # Match ONLY by MusicBrainz ID - this is the unique identifier
            # DO NOT fall back to album title matching as it causes cross-artist contamination
            cur.execute("""
                SELECT id FROM recordings
                WHERE musicbrainz_id = %s
            """, (mb_recording_id,))
            result = cur.fetchone()
            
            if result:
                self.logger.debug(f"  Recording exists (by MB ID)")
                self.stats['recordings_existing'] += 1
                return result['id']
            
            # Create new recording
            if self.dry_run:
                self.logger.info(f"  [DRY RUN] Would create recording: {album_title}")
                return None
            
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
                False,
                mb_recording_id
            ))
            
            recording_id = cur.fetchone()['id']
            self.logger.info(f"  ✓ Created recording: {album_title[:50]}")
            self.stats['recordings_created'] += 1
            
            return recording_id
    
    def _create_release(self, conn, release_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new release in the database
        
        Args:
            conn: Database connection
            release_data: Parsed release data dict
            
        Returns:
            New release ID or None
        """
        # Get foreign key IDs
        format_id = self._get_or_create_format(conn, release_data.get('format_name'))
        status_id = self._get_status_id(release_data.get('status_name'))
        packaging_id = self._get_or_create_packaging(conn, release_data.get('packaging_name'))
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO releases (
                    musicbrainz_release_id, musicbrainz_release_group_id,
                    title, artist_credit, disambiguation,
                    release_date, release_year, country,
                    label, catalog_number, barcode,
                    format_id, packaging_id, status_id,
                    language, script, total_tracks, total_discs,
                    data_quality
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                release_data.get('musicbrainz_release_id'),
                release_data.get('musicbrainz_release_group_id'),
                release_data.get('title'),
                release_data.get('artist_credit'),
                release_data.get('disambiguation'),
                release_data.get('release_date'),
                release_data.get('release_year'),
                release_data.get('country'),
                release_data.get('label'),
                release_data.get('catalog_number'),
                release_data.get('barcode'),
                format_id,
                packaging_id,
                status_id,
                release_data.get('language'),
                release_data.get('script'),
                release_data.get('total_tracks'),
                release_data.get('total_discs'),
                release_data.get('data_quality'),
            ))
            
            result = cur.fetchone()
            return result['id'] if result else None
    
    def _link_recording_to_release(self, conn, recording_id: str, release_id: str,
                                    mb_release: Dict[str, Any]) -> None:
        """
        Link a recording to a release
        
        Args:
            conn: Database connection
            recording_id: Recording ID
            release_id: Release ID
            mb_release: MusicBrainz release data (for track info)
        """
        # Extract track number from release data
        track_number = None
        disc_number = None
        
        # Try to find track info in media
        media = mb_release.get('media') or []
        for disc_idx, medium in enumerate(media, 1):
            tracks = medium.get('tracks') or medium.get('track-list') or []
            for track_idx, track in enumerate(tracks, 1):
                # This is simplified - in practice we'd match by recording ID
                track_number = track_idx
                disc_number = disc_idx
                break
            if track_number:
                break
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO recording_releases (recording_id, release_id, track_number, disc_number)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (recording_id, release_id) DO NOTHING
            """, (recording_id, release_id, track_number, disc_number))
            
            self.stats['links_created'] += 1
    
    def _link_recording_to_release_fast(self, conn, recording_id: str, release_id: str,
                                         mb_recording_id: str, mb_release: Dict[str, Any]) -> None:
        """
        Fast version of link creation - just creates the link without track info
        
        Used when release already exists but link doesn't
        """
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO recording_releases (recording_id, release_id)
                VALUES (%s, %s)
                ON CONFLICT (recording_id, release_id) DO NOTHING
            """, (recording_id, release_id))
            
            self.stats['links_created'] += 1
    
    def _parse_release_data(self, mb_release: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse MusicBrainz release data into our database format
        
        Args:
            mb_release: Raw MusicBrainz release data
            
        Returns:
            Dict with parsed release data
        """
        # Extract artist credit
        artist_credit = ''
        artist_credits = mb_release.get('artist-credit') or []
        for credit in artist_credits:
            if isinstance(credit, dict):
                artist = credit.get('artist', {})
                artist_credit += artist.get('name', '')
                artist_credit += credit.get('joinphrase', '')
            elif isinstance(credit, str):
                artist_credit += credit
        
        # Extract release date
        release_date = mb_release.get('date', '')
        release_year = None
        if release_date and len(release_date) >= 4:
            try:
                release_year = int(release_date[:4])
            except (ValueError, TypeError):
                pass
        
        # Get country (prefer release-events, fall back to country)
        country = None
        release_events = mb_release.get('release-events') or []
        if release_events:
            area = release_events[0].get('area', {})
            country = area.get('iso-3166-1-codes', [None])[0] if area.get('iso-3166-1-codes') else area.get('name')
        if not country:
            country = mb_release.get('country')
        
        # Get label and catalog number
        label = None
        catalog_number = None
        label_info = mb_release.get('label-info') or []
        if label_info:
            label_entry = label_info[0]
            label_obj = label_entry.get('label', {})
            label = label_obj.get('name') if label_obj else None
            catalog_number = label_entry.get('catalog-number')
        
        # Get format from first medium
        format_name = None
        total_tracks = 0
        total_discs = 0
        media = mb_release.get('media') or []  # Handle None explicitly
        if media:
            format_name = media[0].get('format')
            total_discs = len(media)
            for medium in media:
                total_tracks += medium.get('track-count', 0) or 0  # Handle None
        
        return {
            'musicbrainz_release_id': mb_release.get('id'),
            'musicbrainz_release_group_id': mb_release.get('release-group', {}).get('id'),
            'title': mb_release.get('title'),
            'artist_credit': artist_credit.strip() or None,
            'disambiguation': mb_release.get('disambiguation') or None,
            'release_date': release_date or None,  # Convert empty string to None
            'release_year': release_year,
            'country': country or None,
            'label': label,
            'catalog_number': catalog_number,
            'barcode': mb_release.get('barcode') or None,
            'format_name': format_name,
            'packaging_name': mb_release.get('packaging'),
            'status_name': mb_release.get('status'),
            'language': mb_release.get('text-representation', {}).get('language'),
            'script': mb_release.get('text-representation', {}).get('script'),
            'total_tracks': total_tracks or None,
            'total_discs': total_discs or None,
            'data_quality': mb_release.get('quality'),
        }
    
    def _log_release_info(self, release_data: Dict[str, Any]) -> None:
        """Log release info for dry-run mode"""
        self.logger.info(f"    [DRY RUN] Release details:")
        self.logger.info(f"      Title: {release_data['title']}")
        self.logger.info(f"      Artist: {release_data.get('artist_credit', 'Unknown')}")
        self.logger.info(f"      Year: {release_data.get('release_year', 'Unknown')}")
        self.logger.info(f"      Country: {release_data.get('country', 'Unknown')}")
        self.logger.info(f"      Format: {release_data.get('format_name', 'Unknown')}")
        self.logger.info(f"      Label: {release_data.get('label', 'Unknown')}")
    
    # ========================================================================
    # Lookup table helpers
    # ========================================================================
    
    def _get_or_create_format(self, conn, format_name: str) -> Optional[int]:
        """Get format ID, creating if needed"""
        if not format_name:
            return None
        
        # Check cache first
        if format_name in self._format_cache:
            return self._format_cache[format_name]
        
        # Not in cache - need to create it
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO release_formats (name, category)
                VALUES (%s, 'other')
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
            """, (format_name,))
            result = cur.fetchone()
            self._format_cache[format_name] = result['id']
            return result['id']
    
    def _get_status_id(self, status_name: str) -> Optional[int]:
        """Get status ID (don't create - use predefined values only)"""
        if not status_name:
            return None
        
        status_name = status_name.lower()
        return self._status_cache.get(status_name)
    
    def _get_or_create_packaging(self, conn, packaging_name: str) -> Optional[int]:
        """Get packaging ID, creating if needed"""
        if not packaging_name:
            return None
        
        # Check cache first
        if packaging_name in self._packaging_cache:
            return self._packaging_cache[packaging_name]
        
        # Not in cache - need to create it
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO release_packaging (name)
                VALUES (%s)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
            """, (packaging_name,))
            result = cur.fetchone()
            self._packaging_cache[packaging_name] = result['id']
            return result['id']
    
    # ========================================================================
    # Private methods - Database queries
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
                    self.logger.info(f"Found {len(results)} songs, using first match:")
                    for r in results[:5]:
                        self.logger.info(f"  - {r['title']}")
                
                song = results[0]
                return dict(song)
    
    def _find_song_by_id(self, song_id: str) -> Optional[Dict[str, Any]]:
        """Find a song in the database by ID"""
        self.logger.info(f"Looking up song by ID: {song_id}")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, composer, musicbrainz_id
                    FROM songs
                    WHERE id = %s
                """, (song_id,))
                
                result = cur.fetchone()
                return dict(result) if result else None
    
    def _fetch_musicbrainz_recordings(self, work_id: str, limit: int) -> List[Dict[str, Any]]:
        """
        Fetch recordings for a MusicBrainz work
        
        Args:
            work_id: MusicBrainz work ID
            limit: Maximum recordings to fetch
            
        Returns:
            List of recording data dicts
        """
        self.logger.info(f"Fetching recordings for MusicBrainz work: {work_id}")
        
        try:
            # Get work with recording relationships
            data = self.mb_searcher.get_work_recordings(work_id)
            
            if not data:
                self.logger.error("Could not fetch work from MusicBrainz")
                return []
            
            # Extract recordings from relations
            recordings = []
            relations = data.get('relations') or []
            
            self.logger.info(f"Found {len(relations)} related items in work")
            
            for relation in relations:
                if not isinstance(relation, dict):
                    continue
                if relation.get('type') == 'performance' and 'recording' in relation:
                    recording = relation.get('recording')
                    if not isinstance(recording, dict):
                        continue
                    recording_id = recording.get('id')
                    
                    # Fetch detailed recording information (CACHED by mb_utils)
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
            return []