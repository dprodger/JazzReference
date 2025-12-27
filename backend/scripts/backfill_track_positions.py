#!/usr/bin/env python3
"""
Backfill track positions for recording_releases

The original import code was broken - it always set track_number=1, disc_number=1
for every recording. This script fetches the correct positions from MusicBrainz.

Usage:
    python scripts/backfill_track_positions.py [--dry-run] [--limit N]
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_utils import get_db_connection
from mb_utils import MusicBrainzSearcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_track_positions(release_data: dict) -> dict:
    """
    Extract track positions from MusicBrainz release data

    Returns dict mapping mb_recording_id -> (track_number, disc_number)
    """
    if not release_data:
        return {}

    positions = {}
    for medium in release_data.get('media', []):
        disc_number = medium.get('position', 1)
        for track in medium.get('tracks', []):
            recording = track.get('recording', {})
            recording_id = recording.get('id')
            track_number = track.get('position')

            if recording_id and track_number:
                positions[recording_id] = (track_number, disc_number)

    return positions


def get_recording_releases_to_update(conn, limit: int = None) -> list:
    """
    Get all recording_releases that need position updates

    Returns list of dicts with recording_release info plus MB IDs
    """
    query = """
        SELECT
            rr.recording_id,
            rr.release_id,
            rr.track_number as current_track,
            rr.disc_number as current_disc,
            rec.musicbrainz_id as musicbrainz_recording_id,
            rel.musicbrainz_release_id,
            rel.title as release_title
        FROM recording_releases rr
        JOIN recordings rec ON rec.id = rr.recording_id
        JOIN releases rel ON rel.id = rr.release_id
        WHERE rec.musicbrainz_id IS NOT NULL
          AND rel.musicbrainz_release_id IS NOT NULL
        ORDER BY rel.musicbrainz_release_id
    """

    if limit:
        query += f" LIMIT {limit}"

    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


def backfill_positions(dry_run: bool = False, limit: int = None, force_refresh: bool = False):
    """
    Main backfill function

    Args:
        dry_run: If True, show what would be updated without making changes
        limit: Maximum number of recording_releases to process
        force_refresh: If True, ignore cache and fetch fresh data from MusicBrainz
    """
    logger.info("=" * 70)
    logger.info("Track Position Backfill")
    logger.info("=" * 70)

    if dry_run:
        logger.info("*** DRY RUN - No changes will be made ***")

    # Initialize MusicBrainzSearcher with caching
    mb_searcher = MusicBrainzSearcher(cache_days=30, force_refresh=force_refresh)

    stats = {
        'rows_checked': 0,
        'rows_updated': 0,
        'rows_unchanged': 0,
        'rows_not_found': 0,
        'releases_fetched': 0,
        'cache_hits': 0,
        'api_errors': 0,
    }

    # Step 1: Fetch all data from DB, then close connection
    # This avoids holding DB connection open during long API calls
    with get_db_connection() as conn:
        rows = get_recording_releases_to_update(conn, limit)

    logger.info(f"Found {len(rows)} recording_releases to check")
    logger.info("")

    # Group by release to minimize API calls
    releases = {}
    for row in rows:
        mb_release_id = row['musicbrainz_release_id']
        if mb_release_id not in releases:
            releases[mb_release_id] = []
        releases[mb_release_id].append(row)

    logger.info(f"Grouped into {len(releases)} unique releases")
    logger.info("")

    # Step 2: Process each release - make API calls OUTSIDE of DB connection
    for i, (mb_release_id, release_rows) in enumerate(releases.items(), 1):
        release_title = release_rows[0]['release_title'][:40]
        logger.info(f"[{i}/{len(releases)}] {release_title}")
        logger.info(f"    MB Release: {mb_release_id}")
        logger.info(f"    Recordings: {len(release_rows)}")

        # Fetch release details using MBSearcher (with caching)
        # This is done OUTSIDE the DB connection context
        logger.info(f"    Fetching from MusicBrainz...")
        release_data = mb_searcher.get_release_details(mb_release_id)

        # Track cache hits vs API calls
        # MBSearcher sets last_made_api_call=True for API, False for cache
        if mb_searcher.last_made_api_call:
            stats['releases_fetched'] += 1
        elif release_data:
            stats['cache_hits'] += 1

        # Extract positions from release data
        positions = extract_track_positions(release_data)

        if not positions:
            logger.warning(f"    Could not fetch positions, skipping")
            stats['api_errors'] += 1
            continue

        logger.info(f"    Found {len(positions)} tracks in release")

        # Collect updates to apply
        updates_to_apply = []

        for row in release_rows:
            stats['rows_checked'] += 1
            mb_recording_id = row['musicbrainz_recording_id']

            if mb_recording_id not in positions:
                logger.debug(f"      Recording {mb_recording_id[:8]} not found in release")
                stats['rows_not_found'] += 1
                continue

            new_track, new_disc = positions[mb_recording_id]
            current_track = row['current_track']
            current_disc = row['current_disc']

            # Check if update needed
            if current_track == new_track and current_disc == new_disc:
                stats['rows_unchanged'] += 1
                continue

            logger.info(f"      Recording {mb_recording_id[:8]}: "
                      f"({current_disc}, {current_track}) -> ({new_disc}, {new_track})")

            updates_to_apply.append({
                'recording_id': row['recording_id'],
                'release_id': row['release_id'],
                'track_number': new_track,
                'disc_number': new_disc
            })
            stats['rows_updated'] += 1

        # Step 3: Apply updates with a fresh DB connection for each release
        # This prevents connection timeout from long API calls
        if updates_to_apply and not dry_run:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    for update in updates_to_apply:
                        cur.execute("""
                            UPDATE recording_releases
                            SET track_number = %s, disc_number = %s
                            WHERE recording_id = %s AND release_id = %s
                        """, (update['track_number'], update['disc_number'],
                              update['recording_id'], update['release_id']))
                conn.commit()

    # Print summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("BACKFILL SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Rows checked:     {stats['rows_checked']}")
    logger.info(f"Rows updated:     {stats['rows_updated']}")
    logger.info(f"Rows unchanged:   {stats['rows_unchanged']}")
    logger.info(f"Rows not found:   {stats['rows_not_found']}")
    logger.info("-" * 70)
    logger.info(f"Releases fetched: {stats['releases_fetched']} (API calls)")
    logger.info(f"Cache hits:       {stats['cache_hits']}")
    logger.info(f"API errors:       {stats['api_errors']}")
    logger.info("=" * 70)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Backfill track positions for recording_releases'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without making changes'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of recording_releases to process'
    )
    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Ignore cache and fetch fresh data from MusicBrainz'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    backfill_positions(
        dry_run=args.dry_run,
        limit=args.limit,
        force_refresh=args.force_refresh
    )


if __name__ == '__main__':
    main()
