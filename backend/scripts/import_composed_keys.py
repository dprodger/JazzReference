#!/usr/bin/env python3
"""
Import composed_key values from a JSON file into the songs table.

This script reads song_keys.json from the same directory and updates
the composed_key field for each song by ID.

Usage:
    python scripts/import_composed_keys.py [--dry-run]
"""

import argparse
import json
import logging
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_utils import get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def import_composed_keys(dry_run=False):
    """
    Import composed_key values from song_keys.json.

    Args:
        dry_run: If True, show what would be done without making changes
    """
    # Load JSON from same directory as script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, 'song_keys.json')

    if not os.path.exists(json_path):
        logger.error(f"File not found: {json_path}")
        return

    with open(json_path, 'r') as f:
        songs = json.load(f)

    logger.info(f"Loaded {len(songs)} songs from {json_path}")

    updated_count = 0
    skipped_count = 0
    not_found_count = 0

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for song in songs:
                song_id = song.get('id')
                composed_key = song.get('composed_key')
                title = song.get('title', 'Unknown')

                if not song_id:
                    logger.warning(f"Skipping entry without ID: {song}")
                    skipped_count += 1
                    continue

                if not composed_key:
                    logger.debug(f"Skipping {title} - no composed_key")
                    skipped_count += 1
                    continue

                # Check if song exists
                cur.execute("SELECT id, title FROM songs WHERE id = %s", (song_id,))
                existing = cur.fetchone()

                if not existing:
                    logger.warning(f"Song not found: {song_id} ({title})")
                    not_found_count += 1
                    continue

                if dry_run:
                    logger.info(f"[DRY RUN] Would update {title}: composed_key = {composed_key}")
                    updated_count += 1
                else:
                    cur.execute("""
                        UPDATE songs
                        SET composed_key = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (composed_key, song_id))
                    logger.info(f"Updated {title}: composed_key = {composed_key}")
                    updated_count += 1

            if not dry_run:
                conn.commit()

    # Summary
    logger.info("")
    logger.info("=" * 50)
    logger.info("SUMMARY")
    logger.info("=" * 50)
    logger.info(f"Total entries in file: {len(songs)}")
    logger.info(f"Updated: {updated_count}")
    logger.info(f"Skipped (no key): {skipped_count}")
    logger.info(f"Not found in DB: {not_found_count}")

    if dry_run:
        logger.info("")
        logger.info("(DRY RUN - no changes were made)")


def main():
    parser = argparse.ArgumentParser(
        description='Import composed_key values from song_keys.json'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )

    args = parser.parse_args()
    import_composed_keys(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
