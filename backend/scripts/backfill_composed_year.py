#!/usr/bin/env python3
"""
Backfill composed_year for songs from MusicBrainz

This script populates the composed_year field for existing songs by:
1. Fetching work data from MusicBrainz using the song's musicbrainz_id
2. Extracting the earliest recording/release date as an approximation of composition year
3. Optionally checking Wikidata for more accurate composition dates

Usage:
    python scripts/backfill_composed_year.py [--dry-run] [--limit N] [--song-id UUID]
"""

import argparse
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_utils import get_db_connection
from mb_utils import MusicBrainzSearcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_year_from_date(date_str):
    """Extract year from a date string (YYYY, YYYY-MM, or YYYY-MM-DD)"""
    if not date_str:
        return None
    try:
        return int(date_str[:4])
    except (ValueError, TypeError):
        return None


def get_composed_year_from_musicbrainz(mb_searcher, work_id):
    """
    Get the composition year for a work from MusicBrainz.

    Strategy:
    1. Check composer/lyricist/writer relations for begin date (most accurate)
    2. Fall back to earliest recording date if no composer date found

    Args:
        mb_searcher: MusicBrainzSearcher instance
        work_id: MusicBrainz work ID

    Returns:
        int: Composition year, or None if not found
    """
    logger.debug(f"  Fetching work data for MB ID: {work_id}")
    work_data = mb_searcher.get_work_recordings(work_id)

    if not work_data:
        logger.debug(f"No work data found for {work_id}")
        return None

    # Log relation types found
    relation_types = set(r.get('type') for r in work_data.get('relations', []))
    logger.debug(f"  Relation types found: {relation_types}")

    # Strategy 1: Check composer/lyricist/writer relations for begin date (most accurate)
    composer_year = None
    for relation in work_data.get('relations', []):
        rel_type = relation.get('type')
        if rel_type in ('composer', 'lyricist', 'writer'):
            begin_date = relation.get('begin')
            artist_name = relation.get('artist', {}).get('name', 'Unknown')
            logger.debug(f"  Found {rel_type} relation: {artist_name}, begin={begin_date}")
            if begin_date:
                year = extract_year_from_date(begin_date)
                if year and (composer_year is None or year < composer_year):
                    composer_year = year
                    logger.debug(f"  -> Using {rel_type} date: {begin_date} -> year {year}")

    if composer_year:
        return composer_year

    # Strategy 2: Fall back to earliest recording date
    earliest_year = None
    for relation in work_data.get('relations', []):
        if relation.get('type') == 'performance':
            recording = relation.get('recording', {})
            first_release = recording.get('first-release-date')

            if first_release:
                year = extract_year_from_date(first_release)
                if year and (earliest_year is None or year < earliest_year):
                    earliest_year = year
                    logger.debug(f"  Found recording date: {first_release} -> year {year}")

            begin_date = relation.get('begin')
            if begin_date:
                year = extract_year_from_date(begin_date)
                if year and (earliest_year is None or year < earliest_year):
                    earliest_year = year
                    logger.debug(f"  Found relation begin date: {begin_date} -> year {year}")

    return earliest_year


def backfill_composed_year(dry_run=False, limit=None, song_id=None):
    """
    Backfill composed_year for songs missing this data.

    Args:
        dry_run: If True, show what would be done without making changes
        limit: Maximum number of songs to process (None for all)
        song_id: Specific song ID to process (None for all eligible songs)
    """
    mb_searcher = MusicBrainzSearcher(cache_days=30)

    # Get songs that have musicbrainz_id but no composed_year
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if song_id:
                cur.execute("""
                    SELECT id, title, composer, musicbrainz_id, second_mb_id, composed_year
                    FROM songs
                    WHERE id = %s AND musicbrainz_id IS NOT NULL
                """, (song_id,))
            else:
                query = """
                    SELECT id, title, composer, musicbrainz_id, second_mb_id, composed_year
                    FROM songs
                    WHERE musicbrainz_id IS NOT NULL
                      AND composed_year IS NULL
                    ORDER BY title
                """
                if limit:
                    query += f" LIMIT {limit}"
                cur.execute(query)

            songs = cur.fetchall()

    logger.info(f"Found {len(songs)} songs to process")

    updated_count = 0
    skipped_count = 0
    not_found_count = 0

    for i, song in enumerate(songs):
        song_id = song['id']
        title = song['title']
        composer = song['composer'] or 'Unknown'
        mb_id = song['musicbrainz_id']
        second_mb_id = song['second_mb_id']
        current_year = song['composed_year']

        logger.info(f"[{i+1}/{len(songs)}] Processing: {title} ({composer})")

        if current_year:
            logger.info(f"  Already has composed_year: {current_year}")
            skipped_count += 1
            continue

        # Get composition year from primary MusicBrainz ID
        composed_year = get_composed_year_from_musicbrainz(mb_searcher, mb_id)
        if composed_year:
            logger.debug(f"  Primary MB ID ({mb_id}): year {composed_year}")

        # Also check second_mb_id if present, use earlier year
        if second_mb_id:
            second_year = get_composed_year_from_musicbrainz(mb_searcher, second_mb_id)
            if second_year:
                logger.debug(f"  Second MB ID ({second_mb_id}): year {second_year}")
                if composed_year is None or second_year < composed_year:
                    composed_year = second_year

        if not composed_year:
            logger.info(f"  No composition year found in MusicBrainz")
            not_found_count += 1
            continue

        logger.info(f"  Found composition year: {composed_year}")

        if dry_run:
            logger.info(f"  [DRY RUN] Would update composed_year to {composed_year}")
            updated_count += 1
        else:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE songs
                        SET composed_year = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (composed_year, song_id))
                    conn.commit()
            logger.info(f"  Updated composed_year to {composed_year}")
            updated_count += 1

    # Summary
    logger.info("")
    logger.info("=" * 50)
    logger.info("SUMMARY")
    logger.info("=" * 50)
    logger.info(f"Total songs processed: {len(songs)}")
    logger.info(f"Updated: {updated_count}")
    logger.info(f"Skipped (already has year): {skipped_count}")
    logger.info(f"Not found in MusicBrainz: {not_found_count}")

    if dry_run:
        logger.info("")
        logger.info("(DRY RUN - no changes were made)")


def main():
    parser = argparse.ArgumentParser(
        description='Backfill composed_year for songs from MusicBrainz'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of songs to process'
    )
    parser.add_argument(
        '--song-id',
        help='Process a specific song by ID'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    backfill_composed_year(
        dry_run=args.dry_run,
        limit=args.limit,
        song_id=args.song_id
    )


if __name__ == '__main__':
    main()
