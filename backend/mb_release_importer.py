"""
MusicBrainz Release Import Module - OPTIMIZED VERSION
Core business logic for importing recordings AND releases

PERFORMANCE OPTIMIZATIONS:
1. Single database connection per recording (not per release)
2. Pre-check if releases exist BEFORE fetching from MusicBrainz API
3. Only fetch release details for releases that don't exist in DB
4. Batch all release operations for a recording in one transaction

KEY ARCHITECTURE:
- Recording = a specific sound recording (same audio across all releases)
- Release = a product (album, CD, digital release, etc.)
- A recording can appear on multiple releases
- Performers are now associated with releases, not recordings
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
            'releases_skipped_api': 0,  # NEW: Count of API calls skipped
            'links_created': 0,
            'performers_linked': 0,
            'errors': 0
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
        3. For each recording:
           - Creates the recording if it doesn't exist
           - Checks which releases already exist (OPTIMIZATION)
           - Only fetches details for NEW releases
           - Creates releases and links performers
        
        Args:
            song_identifier: Song name or database ID
            limit: Max recordings to fetch (default: 200)
            
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
        
        # STEP 1: Find the song
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
        mb_recordings = self._fetch_musicbrainz_recordings(
            song['musicbrainz_id'], 
            limit
        )
        
        if not mb_recordings:
            self.logger.warning("No recordings found in MusicBrainz for this work")
            return {
                'success': False,
                'error': 'No recordings found',
                'song': song,
                'stats': self.stats
            }
        
        self.stats['recordings_found'] = len(mb_recordings)
        self.logger.info(f"Found {len(mb_recordings)} recordings in MusicBrainz")
        self.logger.info("")
        
        # STEP 3: Process all recordings with a SINGLE database connection
        errors = []
        with get_db_connection() as conn:
            # Pre-populate lookup table caches (uses existing connection)
            self._preload_lookup_caches(conn)
            
            for i, mb_recording in enumerate(mb_recordings, 1):
                mb_recording_id = mb_recording.get('id')
                mb_recording_title = mb_recording.get('title', 'Unknown')
                
                self.logger.info(f"[{i}/{len(mb_recordings)}] Recording: {mb_recording_title[:60]}")
                
                try:
                    self._process_recording(conn, song['id'], mb_recording)
                    # Commit after each recording to avoid holding locks too long
                    conn.commit()
                except Exception as e:
                    error_msg = f"Error processing recording {mb_recording_title}: {e}"
                    self.logger.error(error_msg)
                    self.stats['errors'] += 1
                    errors.append(error_msg)
                    # Rollback this recording's changes, continue with next
                    conn.rollback()
        
        return {
            'success': True,
            'song': song,
            'stats': self.stats,
            'errors': errors if errors else None
        }
    
    def _preload_lookup_caches(self, conn) -> None:
        """
        Pre-load lookup table caches to avoid repeated queries
        
        OPTIMIZATION: Load all lookup values once at start
        
        Args:
            conn: Database connection to use
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
    
    def _process_recording(self, conn, song_id: str, mb_recording: Dict[str, Any]) -> None:
        """
        Process a single MusicBrainz recording
        
        OPTIMIZED: 
        - Uses the provided database connection (no new connections)
        - Batch checks existing releases AND links in 2 queries total
        - Skips all DB operations for fully-linked existing releases
        
        1. Create/find the recording in our database
        2. Check which releases already exist (batch query)
        3. Check which links already exist (batch query)  
        4. Only fetch details for NEW releases
        5. Only create links for releases not yet linked
        
        Args:
            conn: Database connection (reused from caller)
            song_id: Our database song ID
            mb_recording: MusicBrainz recording data
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
        
        # STEP 1: Create or find the recording
        recording_id = self._get_or_create_recording(
            conn, song_id, mb_recording_id, album_title, release_year, formatted_date
        )
        
        if not recording_id and not self.dry_run:
            self.logger.error("  Failed to get/create recording")
            return
        
        # STEP 2: Get mapping of MB release IDs to our release IDs (single query)
        existing_releases = self._get_existing_release_ids(
            conn, [r.get('id') for r in mb_releases if r.get('id')]
        )
        
        # STEP 3: Batch check which links already exist (single query)
        existing_release_db_ids = list(existing_releases.values())
        existing_links = set()
        if recording_id and existing_release_db_ids:
            existing_links = self._get_existing_recording_release_links(
                conn, recording_id, existing_release_db_ids
            )
        
        # Count how many existing releases are already fully linked
        fully_linked_count = len(existing_links)
        new_releases_count = len(mb_releases) - len(existing_releases)
        needs_linking_count = len(existing_releases) - fully_linked_count
        
        self.logger.info(f"  Processing {len(mb_releases)} releases "
                       f"({len(existing_releases)} in DB, {fully_linked_count} already linked, "
                       f"{needs_linking_count} need linking, {new_releases_count} new)...")
        
        # STEP 4: Process each release
        for mb_release in mb_releases:
            self._process_release_in_transaction(
                conn, recording_id, mb_recording_id, mb_recording, 
                mb_release, existing_releases, existing_links
            )
    
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
        
        # Extract release data
        release_data = self._extract_release_data(release_details)
        
        if self.dry_run:
            self.logger.info(f"    [DRY RUN] Would create release: {release_title[:50]}")
            self._log_release_info(release_data)
            # Show performers that would be linked
            self.performer_importer.link_performers_to_release(
                None, None, mb_recording, release_details
            )
            return
        
        # Create the release (it's new)
        release_id = self._create_release(conn, release_data)
        
        if release_id:
            self.stats['releases_created'] += 1
            
            # Link recording to release
            link_created = self._link_recording_to_release_fast(
                conn, recording_id, release_id, mb_recording_id, release_details
            )
            
            if link_created:
                self.stats['links_created'] += 1
            
            # Link performers to the release
            performers_linked = self.performer_importer.link_performers_to_release(
                conn, release_id, mb_recording, release_details
            )
            self.stats['performers_linked'] += performers_linked
    
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
        
        Args:
            conn: Database connection
            song_id: Song ID
            mb_recording_id: MusicBrainz recording ID
            album_title: Album title
            release_year: Year of release
            formatted_date: Formatted date string
            
        Returns:
            Recording ID or None
        """
        with conn.cursor() as cur:
            # Try to find by MusicBrainz ID first
            cur.execute("""
                SELECT id FROM recordings
                WHERE musicbrainz_id = %s
            """, (mb_recording_id,))
            result = cur.fetchone()
            
            if result:
                self.logger.debug(f"  Recording exists (by MB ID)")
                self.stats['recordings_existing'] += 1
                return result['id']
            
            # Try to find by song_id + album_title
            cur.execute("""
                SELECT id FROM recordings
                WHERE song_id = %s AND album_title = %s
            """, (song_id, album_title))
            result = cur.fetchone()
            
            if result:
                self.logger.debug(f"  Recording exists (by album title)")
                self.stats['recordings_existing'] += 1
                # Update with MusicBrainz ID if missing
                cur.execute("""
                    UPDATE recordings
                    SET musicbrainz_id = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND musicbrainz_id IS NULL
                """, (mb_recording_id, result['id']))
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
        Create a new release (assumes it doesn't exist)
        
        Args:
            conn: Database connection
            release_data: Extracted release data
            
        Returns:
            Release ID or None
        """
        # Get lookup table IDs
        format_id = self._get_or_create_format(conn, release_data.get('format_name'))
        status_id = self._get_status_id(release_data.get('status_name'))
        packaging_id = self._get_or_create_packaging(conn, release_data.get('packaging_name'))
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO releases (
                    musicbrainz_release_id,
                    musicbrainz_release_group_id,
                    title,
                    artist_credit,
                    disambiguation,
                    release_date,
                    release_year,
                    country,
                    label,
                    catalog_number,
                    barcode,
                    format_id,
                    packaging_id,
                    status_id,
                    language,
                    script,
                    total_tracks,
                    total_discs,
                    data_quality
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                release_data['musicbrainz_release_id'],
                release_data.get('musicbrainz_release_group_id'),
                release_data['title'],
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
                release_data.get('data_quality')
            ))
            
            release_id = cur.fetchone()['id']
            self.logger.info(f"    ✓ Created release: {release_data['title'][:50]}")
            
            return release_id
    
    def _link_recording_to_release(self, conn, recording_id: str, release_id: str,
                                   mb_recording_id: str, release_data: Dict[str, Any]) -> bool:
        """
        Link a recording to a release via the recording_releases junction table
        
        Args:
            conn: Database connection
            recording_id: Our recording ID
            release_id: Our release ID
            mb_recording_id: MusicBrainz recording ID
            release_data: MusicBrainz release data (for track position)
            
        Returns:
            True if link was created, False if already exists
        """
        # Find track position for this recording in the release
        disc_number, track_number, track_position = self._find_track_position(
            release_data, mb_recording_id
        )
        
        with conn.cursor() as cur:
            # Check if link already exists
            cur.execute("""
                SELECT 1 FROM recording_releases
                WHERE recording_id = %s AND release_id = %s
            """, (recording_id, release_id))
            
            if cur.fetchone():
                self.logger.debug(f"    Link already exists")
                return False
            
            # Create the link
            cur.execute("""
                INSERT INTO recording_releases (
                    recording_id, release_id, disc_number, track_number, track_position
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (recording_id, release_id, disc_number, track_number, track_position))
            
            self.logger.debug(f"    Linked recording to release (disc {disc_number}, track {track_number})")
            return True
    
    def _link_recording_to_release_fast(self, conn, recording_id: str, release_id: str,
                                         mb_recording_id: str, release_data: Dict[str, Any]) -> bool:
        """
        Link a recording to a release - FAST version that skips existence check
        
        OPTIMIZATION: Caller has already verified link doesn't exist via batch query.
        Uses INSERT ... ON CONFLICT DO NOTHING as safety net.
        
        Args:
            conn: Database connection
            recording_id: Our recording ID
            release_id: Our release ID
            mb_recording_id: MusicBrainz recording ID
            release_data: MusicBrainz release data (for track position)
            
        Returns:
            True (always, since we skip the check)
        """
        # Find track position for this recording in the release
        disc_number, track_number, track_position = self._find_track_position(
            release_data, mb_recording_id
        )
        
        with conn.cursor() as cur:
            # Insert directly - ON CONFLICT handles race conditions
            cur.execute("""
                INSERT INTO recording_releases (
                    recording_id, release_id, disc_number, track_number, track_position
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (recording_id, release_id, disc_number, track_number, track_position))
            
            self.logger.debug(f"    Linked recording to release (disc {disc_number}, track {track_number})")
            return True
    
    def _find_track_position(self, release_data: Dict[str, Any], 
                            target_recording_id: str) -> tuple:
        """
        Find the disc and track position of a recording within a release
        
        Args:
            release_data: MusicBrainz release data
            target_recording_id: Recording ID to find
            
        Returns:
            Tuple of (disc_number, track_number, track_position)
        """
        media = release_data.get('media') or []  # Handle None explicitly
        
        for disc_idx, medium in enumerate(media, 1):
            if not isinstance(medium, dict):
                continue
            tracks = medium.get('tracks') or []  # Handle None explicitly
            for track_idx, track in enumerate(tracks, 1):
                if not isinstance(track, dict):
                    continue
                recording = track.get('recording') or {}
                if isinstance(recording, dict) and recording.get('id') == target_recording_id:
                    position = track.get('position', track_idx)
                    return (disc_idx, position, str(position))
        
        # Default: disc 1, track 1
        return (1, 1, '1')
    
    def _extract_release_data(self, mb_release: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract normalized release data from MusicBrainz response
        
        Args:
            mb_release: MusicBrainz release data
            
        Returns:
            Dict with normalized release fields
        """
        # Extract artist credit
        artist_credit = ''
        artist_credit_list = mb_release.get('artist-credit') or []
        for credit in artist_credit_list:
            if isinstance(credit, dict):
                if 'artist' in credit:
                    artist = credit.get('artist')
                    if isinstance(artist, dict):
                        artist_credit += artist.get('name', '')
                if 'joinphrase' in credit:
                    artist_credit += credit['joinphrase']
        
        # Extract release date and year
        release_date = mb_release.get('date', '') or ''  # Handle None from API
        release_year = None
        
        if release_date:
            try:
                if len(release_date) >= 4:
                    release_year = int(release_date[:4])
                if len(release_date) == 10:
                    release_date = release_date  # Keep full date
                else:
                    release_date = None  # Only keep complete dates (YYYY-MM-DD)
            except (ValueError, TypeError):
                release_date = None
        else:
            release_date = None  # Ensure empty string becomes None
        
        # Extract country
        country = mb_release.get('country')
        if not country:
            release_events = mb_release.get('release-events') or []
            if release_events and isinstance(release_events[0], dict):
                area = release_events[0].get('area') or {}
                if isinstance(area, dict) and 'iso-3166-1-codes' in area:
                    codes = area.get('iso-3166-1-codes') or []
                    country = codes[0] if codes else None
        
        # Extract label info
        label = None
        catalog_number = None
        label_info = mb_release.get('label-info') or []
        if label_info and isinstance(label_info[0], dict):
            first_label = label_info[0]
            label_obj = first_label.get('label') or {}
            label = label_obj.get('name') if isinstance(label_obj, dict) else None
            catalog_number = first_label.get('catalog-number')
        
        # Extract format from media
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