"""
MusicBrainz Release Import Module - OPTIMIZED VERSION

PERFORMANCE OPTIMIZATIONS:
1. Single database connection per recording (not per release)
2. Pre-check if releases exist BEFORE fetching from MusicBrainz API
3. Only fetch release details for releases that don't exist in DB
4. Batch all release operations for a recording in one transaction
5. Song-level pre-fetch of recordings with performers
   - Single query to get all recordings that already have performers
   - Skips add_performers_to_recording() entirely for these recordings
   - Reduces "everything cached" case from 4 queries/recording to 1 query total

KEY ARCHITECTURE:
- Recording = a specific sound recording (same audio across all releases)
- Release = a product (album, CD, digital release, etc.)
- A recording can appear on multiple releases
- Performers are associated with RECORDINGS (the audio), not releases
- Releases store Spotify/album art data and release-specific credits (producers, engineers)

COVER ART ARCHIVE INTEGRATION (2025-12):
- When import_cover_art=True (default), CAA is queried for each new release
- Uses shared save_release_imagery() function from caa_release_importer module
- CAA responses are cached to avoid repeated API calls
- Cover art import failures are non-fatal (logged as warnings)
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List, Any, Set, Tuple

from db_utils import get_db_connection
from mb_performer_importer import PerformerImporter
from mb_utils import MusicBrainzSearcher
from caa_utils import CoverArtArchiveClient
from caa_release_importer import save_release_imagery

# Module-level logger for helper functions
_logger = logging.getLogger(__name__)


def parse_mb_date(date_str: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """
    Parse a MusicBrainz date string (YYYY, YYYY-MM, or YYYY-MM-DD).

    MusicBrainz uses '??' for unknown parts, e.g.:
    - 2013-??-26 (year and day known, month unknown)
    - 2013-05-?? (year and month known, day unknown)

    Returns:
        Tuple of (formatted_date, year, precision)
        - formatted_date: Full date string for DB (YYYY-MM-DD, using 01 for unknown parts)
        - year: Integer year
        - precision: 'day', 'month', or 'year'
    """
    if not date_str:
        return (None, None, None)

    try:
        # Handle MusicBrainz '??' placeholders
        has_unknown_parts = '?' in date_str

        # Extract parts
        parts = date_str.split('-')
        year_str = parts[0] if len(parts) > 0 else None
        month_str = parts[1] if len(parts) > 1 else None
        day_str = parts[2] if len(parts) > 2 else None

        # Check if year is valid (not ????)
        if not year_str or '?' in year_str:
            return (None, None, None)

        year = int(year_str)

        # Determine precision and build formatted date
        if day_str and '?' not in day_str and month_str and '?' not in month_str:
            # Full date known: YYYY-MM-DD
            return (f"{year:04d}-{month_str}-{day_str}", year, 'day')
        elif month_str and '?' not in month_str:
            # Month known: YYYY-MM
            return (f"{year:04d}-{month_str}-01", year, 'month')
        else:
            # Year only
            return (f"{year:04d}-01-01", year, 'year')

    except (ValueError, TypeError, IndexError):
        pass

    return (None, None, None)


def extract_recording_date_from_mb(mb_recording: Dict[str, Any],
                                    logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """
    Extract the best recording date from MusicBrainz recording data.

    Priority:
    1. Performer relation dates (actual session dates when all/most match)
    2. MusicBrainz first-release-date (upper bound)

    Args:
        mb_recording: MusicBrainz recording data dict
        logger: Optional logger for detailed diagnostics

    Returns:
        Dict with keys:
        - recording_date: Formatted date string (YYYY-MM-DD)
        - recording_year: Integer year
        - recording_date_precision: 'day', 'month', or 'year'
        - recording_date_source: 'mb_performer_relation' or 'mb_first_release'
        - mb_first_release_date: Raw first-release-date from MB (for caching)
    """
    log = logger or _logger
    recording_id = mb_recording.get('id', 'unknown')
    recording_title = mb_recording.get('title', 'Unknown')

    result = {
        'recording_date': None,
        'recording_year': None,
        'recording_date_precision': None,
        'recording_date_source': None,
        'mb_first_release_date': None,
    }

    # Cache the first-release-date regardless of what we use
    first_release_date = mb_recording.get('first-release-date')
    if first_release_date:
        result['mb_first_release_date'] = first_release_date

    # Priority 1: Check performer relation dates
    relations = mb_recording.get('relations', [])

    # Count performers with and without dates
    performers_with_dates = []
    performers_without_dates = []

    for rel in relations:
        if rel.get('type') == 'instrument':
            artist_name = rel.get('artist', {}).get('name', 'Unknown')
            if rel.get('begin'):
                performers_with_dates.append({
                    'name': artist_name,
                    'date': rel['begin']
                })
            else:
                performers_without_dates.append(artist_name)

    total_performers = len(performers_with_dates) + len(performers_without_dates)

    if performers_with_dates:
        session_dates = set(p['date'] for p in performers_with_dates)
        session_years = set(d[:4] for d in session_dates if len(d) >= 4)

        # Case 1: All performers with dates have the same date
        if len(session_dates) == 1:
            date_str = session_dates.pop()
            formatted_date, year, precision = parse_mb_date(date_str)

            if formatted_date:
                # Log if some performers lack dates
                if performers_without_dates:
                    log.debug(
                        f"  PARTIAL_SESSION_DATES: {len(performers_with_dates)}/{total_performers} "
                        f"performers have date {date_str} for recording '{recording_title}' "
                        f"[{recording_id}]. Missing: {performers_without_dates[:3]}{'...' if len(performers_without_dates) > 3 else ''}"
                    )

                result['recording_date'] = formatted_date
                result['recording_year'] = year
                result['recording_date_precision'] = precision
                result['recording_date_source'] = 'mb_performer_relation'
                return result

        # Case 2: Multiple dates but all same year - use year only
        elif len(session_years) == 1 and len(session_dates) > 1:
            year = int(session_years.pop())
            log.info(
                f"  MULTI_SESSION_SAME_YEAR: Recording '{recording_title}' [{recording_id}] "
                f"has {len(session_dates)} different dates in {year}: {sorted(session_dates)}"
            )
            result['recording_date'] = f"{year}-01-01"
            result['recording_year'] = year
            result['recording_date_precision'] = 'year'
            result['recording_date_source'] = 'mb_performer_relation'
            return result

        # Case 3: Multiple dates across different years - log and use earliest
        elif len(session_years) > 1:
            log.warning(
                f"  MULTI_YEAR_SESSION_DATES: Recording '{recording_title}' [{recording_id}] "
                f"has dates spanning multiple years: {sorted(session_dates)}. Using earliest."
            )
            date_str = min(session_dates)
            formatted_date, year, precision = parse_mb_date(date_str)

            if formatted_date:
                result['recording_date'] = formatted_date
                result['recording_year'] = year
                result['recording_date_precision'] = precision
                result['recording_date_source'] = 'mb_performer_relation'
                return result

    # Priority 2: Use first-release-date as fallback
    if first_release_date:
        formatted_date, year, precision = parse_mb_date(first_release_date)

        if formatted_date:
            result['recording_date'] = formatted_date
            result['recording_year'] = year
            result['recording_date_precision'] = precision
            result['recording_date_source'] = 'mb_first_release'
            return result

    return result


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
    
    def __init__(self, dry_run: bool = False, force_refresh: bool = False,
                 logger: Optional[logging.Logger] = None,
                 progress_callback: Optional[callable] = None,
                 import_cover_art: bool = True):
        """
        Initialize the importer

        Args:
            dry_run: If True, don't make database changes
            force_refresh: If True, bypass MusicBrainz cache
            logger: Optional logger instance (creates one if not provided)
            progress_callback: Optional callback(phase, current, total) for progress tracking
            import_cover_art: If True, fetch cover art from CAA for new releases
        """
        self.dry_run = dry_run
        self.force_refresh = force_refresh
        self.logger = logger or logging.getLogger(__name__)
        self.progress_callback = progress_callback
        self.mb_searcher = MusicBrainzSearcher(force_refresh=force_refresh)
        self.performer_importer = PerformerImporter(dry_run=dry_run)

        # Cover Art Archive integration
        self.import_cover_art = import_cover_art
        if import_cover_art:
            self.caa_client = CoverArtArchiveClient(force_refresh=force_refresh)
        else:
            self.caa_client = None

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
            # Cover Art Archive stats
            'caa_releases_checked': 0,
            'caa_releases_with_art': 0,
            'caa_images_created': 0,
        }

        # Cache for lookup table IDs (populated once per import)
        self._format_cache = {}
        self._status_cache = {}
        self._packaging_cache = {}

        self.logger.info(f"MBReleaseImporter initialized (optimized version, force_refresh={force_refresh}, import_cover_art={import_cover_art})")
    
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
        2. Fetches recordings from MusicBrainz (via the work, and second_mb_id if present)
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

        # Get MusicBrainz work IDs (primary and optional secondary)
        mb_work_id = song.get('musicbrainz_id')
        second_mb_id = song.get('second_mb_id')

        if not mb_work_id:
            return {'success': False, 'error': 'Song has no MusicBrainz ID', 'stats': self.stats}

        # Fetch recordings from primary MusicBrainz work
        recordings = self._fetch_musicbrainz_recordings(mb_work_id, limit)

        # Tag recordings with their source work ID
        for rec in recordings:
            rec['_source_mb_work_id'] = mb_work_id

        # Fetch recordings from secondary MusicBrainz work if present
        if second_mb_id:
            self.logger.info(f"Song has secondary MusicBrainz work ID: {second_mb_id}")
            secondary_recordings = self._fetch_musicbrainz_recordings(second_mb_id, limit)

            # Tag secondary recordings with their source work ID
            for rec in secondary_recordings:
                rec['_source_mb_work_id'] = second_mb_id

            if secondary_recordings:
                self.logger.info(f"Found {len(secondary_recordings)} additional recordings from secondary MB work")
                recordings.extend(secondary_recordings)

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
            
            # 1. Batch fetch: recordings with performers for THIS song (skip performer import)
            recordings_with_performers = self._get_recordings_with_performers(
                conn, mb_recording_ids, song['id']
            )
            self.logger.debug(f"  Pre-fetched {len(recordings_with_performers)} recordings with performers")
            
            # 2. Batch fetch: existing recordings by MB ID for THIS song
            # NOTE: We filter by song_id to handle medley recordings correctly.
            # A medley in MusicBrainz is one recording linked to multiple works,
            # but we create separate recording entries for each song.
            existing_recordings = self._get_existing_recordings_batch(
                conn, mb_recording_ids, song['id']
            )
            self.logger.debug(f"  Pre-fetched {len(existing_recordings)} existing recordings for this song")
            
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
                source_work_id = mb_recording.get('_source_mb_work_id')
                is_secondary = source_work_id == second_mb_id if second_mb_id else False
                source_label = " [from secondary MB work]" if is_secondary else ""
                self.logger.info(f"\n[{i}/{len(recordings)}] Processing: {recording_title}{source_label}")

                # Report progress via callback
                if self.progress_callback:
                    self.progress_callback('musicbrainz_recording_import', i, len(recordings))

                try:
                    self._process_recording_fast(
                        conn, song['id'], mb_recording,
                        recordings_with_performers,
                        existing_recordings,
                        existing_releases_all,
                        all_existing_links,
                        source_mb_work_id=source_work_id
                    )
                    self.stats['recordings_found'] += 1
                except Exception as e:
                    self.logger.error(f"  Error processing recording: {e}", exc_info=True)
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
    
    def _get_recordings_with_performers(self, conn, mb_recording_ids: List[str],
                                         song_id: str) -> Set[str]:
        """
        Get set of MusicBrainz recording IDs that already have performers linked
        for a specific song.

        OPTIMIZATION: Single query to check all recordings at once.
        This allows us to skip add_performers_to_recording() entirely for
        recordings that already have performers, saving 4 DB queries each.

        NOTE: We filter by song_id because medley recordings may have performers
        linked for one song but not another.

        Args:
            conn: Database connection
            mb_recording_ids: List of MusicBrainz recording IDs to check
            song_id: The song ID to filter by

        Returns:
            Set of MB recording IDs that have at least one performer for this song
        """
        if not mb_recording_ids:
            return set()

        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT r.musicbrainz_id
                FROM recordings r
                INNER JOIN recording_performers rp ON r.id = rp.recording_id
                WHERE r.musicbrainz_id = ANY(%s)
                  AND r.song_id = %s
            """, (mb_recording_ids, song_id))

            return {row['musicbrainz_id'] for row in cur.fetchall()}
    
    def _get_existing_recordings_batch(self, conn, mb_recording_ids: List[str],
                                        song_id: str) -> Dict[str, str]:
        """
        Batch fetch existing recordings by MusicBrainz ID for a specific song.

        OPTIMIZATION: Single query for all recordings instead of one per recording.

        NOTE: We filter by song_id because medley recordings in MusicBrainz are
        linked to multiple works (songs). Each song should have its own recording
        entry in our database, even if they share the same MB recording ID.

        Args:
            conn: Database connection
            mb_recording_ids: List of MusicBrainz recording IDs
            song_id: The song ID to filter by

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
                  AND song_id = %s
            """, (mb_recording_ids, song_id))

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
                                 all_existing_links: Dict[str, Set[str]],
                                 source_mb_work_id: Optional[str] = None) -> None:
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
            source_mb_work_id: MusicBrainz work ID this recording was imported from (for tracking)
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

        # Extract recording date from MusicBrainz data (performer relations or first-release-date)
        date_info = extract_recording_date_from_mb(mb_recording, logger=self.logger)

        # STEP 1: Get or create the recording (use cache first - NO QUERY if exists)
        recording_id = existing_recordings.get(mb_recording_id)
        if recording_id:
            self.logger.debug(f"  Recording exists (by MB ID)")
            self.stats['recordings_existing'] += 1
        else:
            # Recording doesn't exist - need to create it
            recording_id = self._create_recording(
                conn, song_id, mb_recording_id, album_title, date_info,
                source_mb_work_id=source_mb_work_id
            )
            if recording_id:
                # Add to cache for future reference
                existing_recordings[mb_recording_id] = recording_id
        
        if not recording_id and not self.dry_run:
            self.logger.error("  Failed to get/create recording")
            return
        
        # STEP 2: Add performers
        # Check if we should skip, or if MusicBrainz has better data than what we have
        should_import_performers = True
        if mb_recording_id in recordings_with_performers:
            # Recording already has performers - check if MusicBrainz has better data
            if self.performer_importer.has_better_performer_data(conn, recording_id, mb_recording):
                # MusicBrainz has better data (instruments) - clear old and re-import
                self.performer_importer.clear_recording_performers(conn, recording_id)
                # Also update recording date if MB has better date info
                self._update_recording_date_if_better(conn, recording_id, date_info)
            else:
                self.logger.debug(f"  Skipping performer check - recording already has performers")
                self.stats['performers_skipped_existing'] += 1
                should_import_performers = False

        if should_import_performers:
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
                           album_title: str, date_info: Dict[str, Any],
                           source_mb_work_id: Optional[str] = None) -> Optional[str]:
        """
        Create a new recording in the database.

        Args:
            conn: Database connection
            song_id: Our database song ID
            mb_recording_id: MusicBrainz recording ID
            album_title: Album title for this recording
            date_info: Dict from extract_recording_date_from_mb() containing:
                - recording_date: Formatted date (YYYY-MM-DD)
                - recording_year: Integer year
                - recording_date_precision: 'day', 'month', or 'year'
                - recording_date_source: 'mb_performer_relation' or 'mb_first_release'
                - mb_first_release_date: Raw MB first-release-date
            source_mb_work_id: MusicBrainz work ID this recording was imported from

        Returns:
            Recording ID if created, None otherwise
        """
        if self.dry_run:
            source = date_info.get('recording_date_source', 'unknown')
            year = date_info.get('recording_year')
            self.logger.info(f"  [DRY RUN] Would create recording: {album_title} "
                           f"(year={year}, source={source})")
            return None

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO recordings (
                    song_id, album_title, recording_year, recording_date,
                    recording_date_source, recording_date_precision, mb_first_release_date,
                    is_canonical, musicbrainz_id, source_mb_work_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                song_id,
                album_title,
                date_info.get('recording_year'),
                date_info.get('recording_date'),
                date_info.get('recording_date_source'),
                date_info.get('recording_date_precision'),
                date_info.get('mb_first_release_date'),
                False,
                mb_recording_id,
                source_mb_work_id
            ))

            recording_id = cur.fetchone()['id']

            # Log with source info
            source = date_info.get('recording_date_source', 'none')
            year = date_info.get('recording_year', '?')
            self.logger.info(f"  ✓ Created recording: {album_title[:50]} (year={year}, source={source})")
            self.stats['recordings_created'] += 1

            return recording_id

    def _update_recording_date_if_better(self, conn, recording_id: str,
                                          date_info: Dict[str, Any]) -> bool:
        """
        Update recording date if MusicBrainz has better date info.

        "Better" means:
        - MusicBrainz has performer relation dates (actual session dates)
        - Our database only has mb_first_release dates

        Args:
            conn: Database connection
            recording_id: Our database recording ID
            date_info: Dict from extract_recording_date_from_mb()

        Returns:
            bool: True if date was updated
        """
        if not recording_id or not date_info:
            return False

        # Only update if MusicBrainz has performer relation dates
        new_source = date_info.get('recording_date_source')
        if new_source != 'mb_performer_relation':
            return False

        if self.dry_run:
            self.logger.info(f"  [DRY RUN] Would update recording date to {date_info.get('recording_date')}")
            return True

        with conn.cursor() as cur:
            # Check current date source
            cur.execute("""
                SELECT recording_date_source FROM recordings WHERE id = %s
            """, (recording_id,))
            row = cur.fetchone()

            if not row:
                return False

            current_source = row['recording_date_source']

            # Only update if we have a worse source (release date) or no date
            if current_source not in (None, 'mb_first_release'):
                return False

            # Update with better date info
            cur.execute("""
                UPDATE recordings
                SET recording_date = %s,
                    recording_year = %s,
                    recording_date_source = %s,
                    recording_date_precision = %s
                WHERE id = %s
            """, (
                date_info.get('recording_date'),
                date_info.get('recording_year'),
                date_info.get('recording_date_source'),
                date_info.get('recording_date_precision'),
                recording_id
            ))

            self.logger.info(f"  Updated recording date: {date_info.get('recording_date')} "
                           f"(source: {new_source})")
            return True

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

            # Import cover art from Cover Art Archive
            self._import_cover_art_for_release(conn, release_id, mb_release_id)
    
    def _get_release_id_by_mb_id(self, conn, mb_release_id: str) -> Optional[str]:
        """Get our database release ID by MusicBrainz release ID"""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM releases WHERE musicbrainz_release_id = %s
            """, (mb_release_id,))
            result = cur.fetchone()
            return result['id'] if result else None
    
    def _get_or_create_recording(self, conn, song_id: str, mb_recording_id: str,
                                  album_title: str, date_info: Dict[str, Any],
                                  source_mb_work_id: Optional[str] = None) -> Optional[str]:
        """
        Get existing recording or create new one.

        NOTE: This method is retained for backwards compatibility but the main import
        path now uses _create_recording() with pre-cached existence checks.

        IMPORTANT: For MusicBrainz imports, we ONLY match by MusicBrainz recording ID.
        Album title matching is NOT reliable because different artists can have
        albums with the same title (e.g., Grant Green's "Born to Be Blue" vs
        Freddie Hubbard's "Born to Be Blue").

        Args:
            conn: Database connection
            song_id: Song ID
            mb_recording_id: MusicBrainz recording ID (unique identifier)
            album_title: Album title (for display/storage only, NOT for matching)
            date_info: Dict from extract_recording_date_from_mb()
            source_mb_work_id: MusicBrainz work ID this recording was imported from

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
                    recording_date_source, recording_date_precision, mb_first_release_date,
                    is_canonical, musicbrainz_id, source_mb_work_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                song_id,
                album_title,
                date_info.get('recording_year'),
                date_info.get('recording_date'),
                date_info.get('recording_date_source'),
                date_info.get('recording_date_precision'),
                date_info.get('mb_first_release_date'),
                False,
                mb_recording_id,
                source_mb_work_id
            ))

            recording_id = cur.fetchone()['id']
            source = date_info.get('recording_date_source', 'none')
            year = date_info.get('recording_year', '?')
            self.logger.info(f"  ✓ Created recording: {album_title[:50]} (year={year}, source={source})")
            self.stats['recordings_created'] += 1

            return recording_id

    def _create_release(self, conn, release_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new release in the database, or return existing ID if duplicate
        
        Args:
            conn: Database connection
            release_data: Parsed release data dict
            
        Returns:
            Release ID (new or existing) or None
        """
        # Get foreign key IDs
        format_id = self._get_or_create_format(conn, release_data.get('format_name'))
        status_id = self._get_status_id(release_data.get('status_name'))
        packaging_id = self._get_or_create_packaging(conn, release_data.get('packaging_name'))
        
        mb_release_id = release_data.get('musicbrainz_release_id')
        
        with conn.cursor() as cur:
            # Use ON CONFLICT to handle race conditions where release was created
            # between our pre-fetch check and now
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
                ON CONFLICT (musicbrainz_release_id) DO UPDATE SET
                    musicbrainz_release_id = EXCLUDED.musicbrainz_release_id
                RETURNING id
            """, (
                mb_release_id,
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

    def _import_cover_art_for_release(self, conn, release_id: str,
                                       mb_release_id: str) -> None:
        """
        Import cover art for a newly created release from Cover Art Archive.

        Called automatically after release creation if import_cover_art=True.
        Uses the shared save_release_imagery() function for database operations.

        Args:
            conn: Database connection (caller manages transaction)
            release_id: Our database release UUID
            mb_release_id: MusicBrainz release ID
        """
        if not self.import_cover_art or not self.caa_client:
            return

        if self.dry_run:
            self.logger.debug(f"      [DRY RUN] Would check CAA for cover art")
            return

        try:
            # Get imagery data from CAA (uses cache)
            imagery_data = self.caa_client.extract_imagery_data(mb_release_id)

            # Dedupe to one Front, one Back (CAA may return multiple of each type)
            images_to_store = []
            stored_types = set()
            for img in (imagery_data or []):
                if img['type'] not in stored_types:
                    images_to_store.append(img)
                    stored_types.add(img['type'])

            # Save using shared function (doesn't commit - caller does)
            result = save_release_imagery(
                conn, release_id, images_to_store,
                logger=self.logger,
                update_checked_timestamp=True
            )

            # Update stats
            self.stats['caa_releases_checked'] += 1
            if images_to_store:
                self.stats['caa_releases_with_art'] += 1
                self.stats['caa_images_created'] += result.get('created', 0)
                front_count = sum(1 for img in images_to_store if img['type'] == 'Front')
                back_count = sum(1 for img in images_to_store if img['type'] == 'Back')
                self.logger.debug(f"      CAA: {front_count} front, {back_count} back image(s)")
            else:
                self.logger.debug(f"      CAA: no cover art available")

        except Exception as e:
            self.logger.warning(f"      CAA error (non-fatal): {e}")
            # Don't increment error count - CAA failures shouldn't fail the release import

    def _maybe_set_default_release(self, cur, recording_id: str, release_id: str) -> None:
        """
        Set default_release_id on recording if it doesn't have one.

        This ensures recordings always have a default release for display purposes,
        even when imported from MusicBrainz without Spotify matching.
        """
        cur.execute("""
            UPDATE recordings
            SET default_release_id = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
              AND default_release_id IS NULL
        """, (release_id, recording_id))

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

            # Set default_release_id if recording doesn't have one
            self._maybe_set_default_release(cur, recording_id, release_id)

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

            # Set default_release_id if recording doesn't have one
            self._maybe_set_default_release(cur, recording_id, release_id)
    
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
        # MusicBrainz returns dates in various formats: "2004-05-17", "2004-05", "2004"
        # Also can have unknown parts: "2017-??-29", "2004-??"
        # PostgreSQL DATE type requires full YYYY-MM-DD format with valid values
        release_date_raw = mb_release.get('date', '')
        release_date = None
        release_year = None
        
        if release_date_raw and len(release_date_raw) >= 4:
            try:
                # Check for unknown date markers (??) - if present, only use year
                if '?' in release_date_raw:
                    release_year = int(release_date_raw[:4])
                    release_date = f"{release_year}-01-01"
                elif len(release_date_raw) == 4:
                    # Year only: "2004" -> "2004-01-01"
                    release_year = int(release_date_raw)
                    release_date = f"{release_date_raw}-01-01"
                elif len(release_date_raw) == 7:
                    # Year-month: "2004-05" -> "2004-05-01"
                    release_year = int(release_date_raw[:4])
                    release_date = f"{release_date_raw}-01"
                elif len(release_date_raw) >= 10:
                    # Full date: "2004-05-17" (may have time component, truncate)
                    release_year = int(release_date_raw[:4])
                    release_date = release_date_raw[:10]
                else:
                    # Unknown format, just extract year if possible
                    release_year = int(release_date_raw[:4])
                    release_date = None
            except (ValueError, TypeError):
                pass
        
        # Get country (prefer release-events, fall back to country)
        country = None
        release_events = mb_release.get('release-events') or []
        if release_events:
            area = release_events[0].get('area') or {}  # Handle None explicitly
            country = area.get('iso-3166-1-codes', [None])[0] if area.get('iso-3166-1-codes') else area.get('name')
        if not country:
            country = mb_release.get('country')
        
        # Get label and catalog number
        label = None
        catalog_number = None
        label_info = mb_release.get('label-info') or []
        if label_info:
            label_entry = label_info[0]
            label_obj = label_entry.get('label') or {}  # Handle None explicitly
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
            'release_date': release_date,  # Already normalized to YYYY-MM-DD or None
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
                    SELECT id, title, composer, musicbrainz_id, second_mb_id
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
                    SELECT id, title, composer, musicbrainz_id, second_mb_id
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

            # Count performance relations for accurate progress tracking
            performance_relations = [r for r in relations if isinstance(r, dict) and r.get('type') == 'performance' and 'recording' in r]
            total_performances = min(len(performance_relations), limit)

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

                        # Report progress during fetch phase
                        if self.progress_callback:
                            self.progress_callback('musicbrainz_fetch', len(recordings), total_performances)

                        # Log progress every 25 recordings to show activity
                        if len(recordings) % 25 == 0:
                            self.logger.info(f"  Fetched {len(recordings)}/{total_performances} recording details...")

                        if len(recordings) >= limit:
                            self.logger.info(f"Reached limit of {limit} recordings")
                            break
            
            self.logger.info(f"Successfully fetched {len(recordings)} recording details")
            return recordings
            
        except Exception as e:
            self.logger.error(f"Error fetching recordings: {e}", exc_info=True)
            return []