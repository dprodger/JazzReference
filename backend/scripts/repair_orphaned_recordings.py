#!/usr/bin/env python3
"""
Repair Orphaned Recordings

This script repairs recordings that have no entries in the recording_releases
junction table. These "orphaned" recordings exist in the database but are not
linked to any releases.

The repair strategy is:
1. Find orphaned recordings (have musicbrainz_id but no recording_releases entries)
2. For each orphaned recording:
   - Look up the releases in our database that match the MB releases for that recording
   - Create missing recording_releases links
   - Set default_release_id if not already set

Usage:
  # Analyze orphaned recordings (dry-run)
  python repair_orphaned_recordings.py --dry-run

  # Repair all orphaned recordings
  python repair_orphaned_recordings.py

  # Repair orphaned recordings for a specific song
  python repair_orphaned_recordings.py --song "Satin Doll"

  # Limit to first N orphaned recordings
  python repair_orphaned_recordings.py --limit 10
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_utils import get_db_connection
from mb_utils import MusicBrainzSearcher

# Configure logging
LOG_DIR = Path(__file__).parent / 'log'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / 'repair_orphaned_recordings.log')
    ]
)
logger = logging.getLogger(__name__)


class OrphanedRecordingRepairer:
    """Repairs orphaned recordings by re-linking them to releases"""

    def __init__(self, dry_run: bool = False, force_refresh: bool = False):
        self.dry_run = dry_run
        self.force_refresh = force_refresh
        self.mb_searcher = MusicBrainzSearcher(force_refresh=force_refresh)
        self.stats = {
            'orphans_found': 0,
            'orphans_repaired': 0,
            'orphans_skipped_no_mb_id': 0,
            'orphans_skipped_no_releases': 0,
            'links_created': 0,
            'default_release_set': 0,
            'errors': 0
        }

    def find_orphaned_recordings(self, song_name: Optional[str] = None,
                                  limit: Optional[int] = None) -> List[Dict]:
        """
        Find recordings that have no entries in recording_releases.

        Args:
            song_name: Optional filter by song name
            limit: Optional limit on number of orphans to return

        Returns:
            List of orphaned recording dicts
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT
                        r.id,
                        r.song_id,
                        r.album_title,
                        r.musicbrainz_id,
                        r.recording_year,
                        r.default_release_id,
                        s.title as song_title
                    FROM recordings r
                    JOIN songs s ON r.song_id = s.id
                    LEFT JOIN recording_releases rr ON r.id = rr.recording_id
                    WHERE rr.id IS NULL
                """
                params = []

                if song_name:
                    query += " AND LOWER(s.title) LIKE LOWER(%s)"
                    params.append(f'%{song_name}%')

                query += " ORDER BY s.title, r.album_title"

                if limit:
                    query += f" LIMIT {limit}"

                cur.execute(query, params if params else None)
                return [dict(row) for row in cur.fetchall()]

    def get_mb_releases_for_recording(self, mb_recording_id: str) -> List[Dict]:
        """
        Get releases from MusicBrainz for a recording.

        Args:
            mb_recording_id: MusicBrainz recording ID

        Returns:
            List of release dicts with id and title
        """
        try:
            recording_details = self.mb_searcher.get_recording_details(mb_recording_id)
            if not recording_details:
                return []

            releases = recording_details.get('releases', [])
            return [
                {
                    'mb_release_id': r.get('id'),
                    'title': r.get('title'),
                    'date': r.get('date', ''),
                    'status': r.get('status', '')
                }
                for r in releases if r.get('id')
            ]
        except Exception as e:
            logger.error(f"Error fetching MB releases: {e}")
            return []

    def find_matching_db_releases(self, conn, mb_release_ids: List[str]) -> Dict[str, str]:
        """
        Find releases in our database that match MusicBrainz release IDs.

        Args:
            conn: Database connection
            mb_release_ids: List of MusicBrainz release IDs

        Returns:
            Dict mapping MB release ID -> our database release ID
        """
        if not mb_release_ids:
            return {}

        with conn.cursor() as cur:
            cur.execute("""
                SELECT musicbrainz_release_id, id
                FROM releases
                WHERE musicbrainz_release_id = ANY(%s)
            """, (mb_release_ids,))

            return {row['musicbrainz_release_id']: row['id'] for row in cur.fetchall()}

    def repair_recording(self, conn, recording: Dict) -> bool:
        """
        Repair a single orphaned recording by linking it to releases.

        Args:
            conn: Database connection
            recording: Recording dict

        Returns:
            True if repaired successfully, False otherwise
        """
        recording_id = recording['id']
        mb_recording_id = recording['musicbrainz_id']
        album_title = recording['album_title'] or 'Unknown'
        song_title = recording['song_title']

        logger.info(f"  Processing: {song_title} / {album_title}")
        logger.debug(f"    Recording ID: {recording_id}")
        logger.debug(f"    MB Recording ID: {mb_recording_id}")

        if not mb_recording_id:
            logger.warning(f"    Skipping: no MusicBrainz ID")
            self.stats['orphans_skipped_no_mb_id'] += 1
            return False

        # Get releases from MusicBrainz
        mb_releases = self.get_mb_releases_for_recording(mb_recording_id)

        if not mb_releases:
            logger.warning(f"    Skipping: no releases found in MusicBrainz")
            self.stats['orphans_skipped_no_releases'] += 1
            return False

        logger.info(f"    Found {len(mb_releases)} releases in MusicBrainz")

        # Find matching releases in our database
        mb_release_ids = [r['mb_release_id'] for r in mb_releases]
        db_releases = self.find_matching_db_releases(conn, mb_release_ids)

        if not db_releases:
            logger.warning(f"    Skipping: none of the MB releases exist in our database")
            self.stats['orphans_skipped_no_releases'] += 1
            return False

        logger.info(f"    Found {len(db_releases)} matching releases in database")

        if self.dry_run:
            logger.info(f"    [DRY RUN] Would create {len(db_releases)} links")
            for mb_id, db_id in list(db_releases.items())[:5]:
                mb_release = next((r for r in mb_releases if r['mb_release_id'] == mb_id), {})
                logger.info(f"      - {mb_release.get('title', 'Unknown')}")
            if len(db_releases) > 5:
                logger.info(f"      ... and {len(db_releases) - 5} more")
            return True

        # Create recording_releases links
        links_created = 0
        first_release_id = None

        with conn.cursor() as cur:
            for mb_release_id, db_release_id in db_releases.items():
                try:
                    cur.execute("""
                        INSERT INTO recording_releases (recording_id, release_id)
                        VALUES (%s, %s)
                        ON CONFLICT (recording_id, release_id) DO NOTHING
                        RETURNING id
                    """, (recording_id, db_release_id))

                    result = cur.fetchone()
                    if result:
                        links_created += 1
                        if first_release_id is None:
                            first_release_id = db_release_id

                except Exception as e:
                    logger.error(f"    Error creating link: {e}")
                    self.stats['errors'] += 1

            # Set default_release_id if not already set
            if first_release_id and not recording['default_release_id']:
                cur.execute("""
                    UPDATE recordings
                    SET default_release_id = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                      AND default_release_id IS NULL
                """, (first_release_id, recording_id))

                if cur.rowcount > 0:
                    self.stats['default_release_set'] += 1
                    logger.info(f"    Set default_release_id")

            conn.commit()

        self.stats['links_created'] += links_created
        logger.info(f"    Created {links_created} links")

        return links_created > 0

    def run(self, song_name: Optional[str] = None, limit: Optional[int] = None):
        """
        Run the repair process.

        Args:
            song_name: Optional filter by song name
            limit: Optional limit on number of orphans to process
        """
        mode = "[DRY RUN] " if self.dry_run else ""
        logger.info(f"{mode}Finding orphaned recordings...")

        orphans = self.find_orphaned_recordings(song_name=song_name, limit=limit)
        self.stats['orphans_found'] = len(orphans)

        if not orphans:
            logger.info("No orphaned recordings found")
            return

        logger.info(f"Found {len(orphans)} orphaned recordings")

        with get_db_connection() as conn:
            for i, recording in enumerate(orphans, 1):
                logger.info(f"\n[{i}/{len(orphans)}] {recording['song_title']}")

                try:
                    if self.repair_recording(conn, recording):
                        self.stats['orphans_repaired'] += 1
                except Exception as e:
                    logger.error(f"  Error repairing recording: {e}")
                    self.stats['errors'] += 1
                    try:
                        conn.rollback()
                    except:
                        pass

        self._print_stats()

    def _print_stats(self):
        """Print summary statistics"""
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Orphans found:              {self.stats['orphans_found']}")
        logger.info(f"Orphans repaired:           {self.stats['orphans_repaired']}")
        logger.info(f"Skipped (no MB ID):         {self.stats['orphans_skipped_no_mb_id']}")
        logger.info(f"Skipped (no releases):      {self.stats['orphans_skipped_no_releases']}")
        logger.info(f"Links created:              {self.stats['links_created']}")
        logger.info(f"Default release set:        {self.stats['default_release_set']}")
        logger.info(f"Errors:                     {self.stats['errors']}")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Repair orphaned recordings by re-linking them to releases'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without making changes')
    parser.add_argument('--song', type=str,
                        help='Filter by song name')
    parser.add_argument('--limit', type=int,
                        help='Limit number of orphans to process')
    parser.add_argument('--force-refresh', action='store_true',
                        help='Bypass MusicBrainz cache')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    repairer = OrphanedRecordingRepairer(
        dry_run=args.dry_run,
        force_refresh=args.force_refresh
    )

    repairer.run(song_name=args.song, limit=args.limit)


if __name__ == '__main__':
    main()
