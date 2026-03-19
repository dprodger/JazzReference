#!/usr/bin/env python3
"""
Deduplicate recordings that share the same (musicbrainz_id, song_id).

These duplicates were created by concurrent imports that raced past the
in-memory existence check. For each group the oldest recording is kept
("keeper") and the newer copies ("dups") are merged into it:

  1. Streaming links on shared releases are moved to the keeper's
     recording_release (skipping services the keeper already has)
  2. recording_releases that only the dup owns are reassigned to the keeper
  3. dup recordings are deleted (CASCADE removes remaining child rows)

Run with --dry-run first to preview changes.

Usage:
    python scripts/deduplicate_recordings.py --dry-run
    python scripts/deduplicate_recordings.py
"""

import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from db_utils import get_db_connection

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def deduplicate(dry_run=False):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # ── Step 0: Identify keepers and dups ──────────────────────
            # Keeper = oldest created_at per (musicbrainz_id, song_id)
            cur.execute("""
                CREATE TEMP TABLE dup_groups AS
                WITH ranked AS (
                    SELECT id, musicbrainz_id, song_id,
                           ROW_NUMBER() OVER (
                               PARTITION BY musicbrainz_id, song_id
                               ORDER BY created_at ASC
                           ) as rn
                    FROM recordings
                    WHERE musicbrainz_id IN (
                        SELECT musicbrainz_id FROM recordings
                        WHERE musicbrainz_id IS NOT NULL
                        GROUP BY musicbrainz_id, song_id
                        HAVING count(*) > 1
                    )
                )
                SELECT r.id as dup_id,
                       k.id as keeper_id,
                       r.musicbrainz_id,
                       r.song_id
                FROM ranked r
                JOIN ranked k ON r.musicbrainz_id = k.musicbrainz_id
                    AND r.song_id = k.song_id AND k.rn = 1
                WHERE r.rn > 1
            """)

            cur.execute("SELECT count(*) as cnt FROM dup_groups")
            dup_count = cur.fetchone()['cnt']
            cur.execute("SELECT count(DISTINCT keeper_id) as cnt FROM dup_groups")
            group_count = cur.fetchone()['cnt']
            logger.info(f"Found {dup_count} duplicate recordings across {group_count} groups")

            if dup_count == 0:
                logger.info("Nothing to do.")
                return

            # ── Step 1: Move streaming links from dup rr to keeper rr ─
            # Only where keeper has the same release but is missing that service
            cur.execute("""
                SELECT count(*) as cnt FROM recording_release_streaming_links rrsl
                JOIN recording_releases rr_dup ON rrsl.recording_release_id = rr_dup.id
                JOIN dup_groups dg ON rr_dup.recording_id = dg.dup_id
                JOIN recording_releases rr_keep ON rr_keep.recording_id = dg.keeper_id
                    AND rr_keep.release_id = rr_dup.release_id
                WHERE NOT EXISTS (
                    SELECT 1 FROM recording_release_streaming_links existing
                    WHERE existing.recording_release_id = rr_keep.id
                      AND existing.service = rrsl.service
                )
            """)
            links_to_move = cur.fetchone()['cnt']
            logger.info(f"Streaming links to move to keepers: {links_to_move}")

            if not dry_run and links_to_move > 0:
                cur.execute("""
                    UPDATE recording_release_streaming_links rrsl
                    SET recording_release_id = rr_keep.id
                    FROM recording_releases rr_dup
                    JOIN dup_groups dg ON rr_dup.recording_id = dg.dup_id
                    JOIN recording_releases rr_keep ON rr_keep.recording_id = dg.keeper_id
                        AND rr_keep.release_id = rr_dup.release_id
                    WHERE rrsl.recording_release_id = rr_dup.id
                      AND NOT EXISTS (
                          SELECT 1 FROM recording_release_streaming_links existing
                          WHERE existing.recording_release_id = rr_keep.id
                            AND existing.service = rrsl.service
                      )
                """)
                logger.info(f"  Moved {cur.rowcount} streaming links")

            # Count streaming links that will be dropped (keeper already has them)
            cur.execute("""
                SELECT count(*) as cnt FROM recording_release_streaming_links rrsl
                JOIN recording_releases rr_dup ON rrsl.recording_release_id = rr_dup.id
                JOIN dup_groups dg ON rr_dup.recording_id = dg.dup_id
            """)
            remaining_dup_links = cur.fetchone()['cnt']
            logger.info(f"Streaming links on dups to be dropped (keeper already has): {remaining_dup_links}")

            # ── Step 2: Reassign orphan recording_releases ────────────
            # Where dup has a release the keeper doesn't
            cur.execute("""
                SELECT count(*) as cnt FROM recording_releases rr_dup
                JOIN dup_groups dg ON rr_dup.recording_id = dg.dup_id
                WHERE NOT EXISTS (
                    SELECT 1 FROM recording_releases rr_keep
                    WHERE rr_keep.recording_id = dg.keeper_id
                      AND rr_keep.release_id = rr_dup.release_id
                )
            """)
            rr_to_move = cur.fetchone()['cnt']
            logger.info(f"Recording-releases to reassign to keepers: {rr_to_move}")

            if not dry_run and rr_to_move > 0:
                cur.execute("""
                    UPDATE recording_releases rr_dup
                    SET recording_id = dg.keeper_id
                    FROM dup_groups dg
                    WHERE rr_dup.recording_id = dg.dup_id
                      AND NOT EXISTS (
                          SELECT 1 FROM recording_releases rr_keep
                          WHERE rr_keep.recording_id = dg.keeper_id
                            AND rr_keep.release_id = rr_dup.release_id
                      )
                """)
                logger.info(f"  Reassigned {cur.rowcount} recording-releases")

            # ── Step 3: Delete duplicate recordings ───────────────────
            # CASCADE will remove their recording_releases (+ streaming links),
            # recording_performers, recording_contributions
            if not dry_run:
                cur.execute("""
                    DELETE FROM recordings
                    WHERE id IN (SELECT dup_id FROM dup_groups)
                """)
                logger.info(f"Deleted {cur.rowcount} duplicate recordings")
                conn.commit()
            else:
                logger.info(f"\n[DRY RUN] Would delete {dup_count} duplicate recordings")

            # ── Cleanup temp table ────────────────────────────────────
            cur.execute("DROP TABLE IF EXISTS dup_groups")

            logger.info("\nDone." if not dry_run else "\n[DRY RUN] No changes made.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Deduplicate recordings with same (musicbrainz_id, song_id)')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without modifying data')
    args = parser.parse_args()
    deduplicate(dry_run=args.dry_run)
