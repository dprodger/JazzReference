#!/usr/bin/env python3
"""
Backfill MusicBrainz Recording Durations

Populates duration_ms on recordings from MusicBrainz data.

Phase 1: Reads from the local MusicBrainz cache (no API calls).
Phase 2: Fetches remaining recordings from the MusicBrainz API (rate-limited to 1/sec).

Usage:
    python backfill_mb_durations.py --limit 500
    python backfill_mb_durations.py --limit 500 --dry-run
    python backfill_mb_durations.py --cache-only              # Skip API calls
    python backfill_mb_durations.py --api-only --limit 1000   # Skip cache phase
    python backfill_mb_durations.py --debug
"""

import json
from pathlib import Path

from script_base import ScriptBase, run_script
from db_utils import get_db_connection
from core.cache_utils import get_cache_dir


def main():
    script = ScriptBase(
        name="backfill_mb_durations",
        description="Backfill duration_ms for recordings from MusicBrainz cache and API",
        epilog="""
Examples:
  python backfill_mb_durations.py --limit 500
  python backfill_mb_durations.py --cache-only
  python backfill_mb_durations.py --api-only --limit 5000
  python backfill_mb_durations.py --limit 100000 --dry-run
        """
    )

    script.add_dry_run_arg()
    script.add_debug_arg()
    script.add_limit_arg(default=100000)
    script.parser.add_argument(
        '--cache-only',
        action='store_true',
        help='Only read from local MB cache, skip API calls'
    )
    script.parser.add_argument(
        '--api-only',
        action='store_true',
        help='Skip cache phase, only fetch from MB API'
    )

    args = script.parse_args()

    script.print_header({
        "DRY RUN": args.dry_run,
        "CACHE ONLY": args.cache_only,
        "API ONLY": args.api_only,
    })

    stats = {
        'recordings_missing_duration': 0,
        'cache_hits': 0,
        'cache_misses': 0,
        'cache_no_duration': 0,
        'api_fetched': 0,
        'api_no_duration': 0,
        'api_errors': 0,
        'durations_updated': 0,
    }

    # Step 1: Find recordings without duration_ms that have a musicbrainz_id
    script.logger.info("Finding recordings without duration_ms...")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, musicbrainz_id
                FROM recordings
                WHERE duration_ms IS NULL
                  AND musicbrainz_id IS NOT NULL
                ORDER BY created_at DESC
                LIMIT %s
            """, (args.limit,))
            recordings = cur.fetchall()

    stats['recordings_missing_duration'] = len(recordings)
    script.logger.info(f"Found {len(recordings)} recordings without duration_ms")

    if not recordings:
        script.print_summary(stats)
        return True

    # Build lookup: musicbrainz_id -> recording db id
    mb_to_db = {r['musicbrainz_id']: r['id'] for r in recordings}
    remaining_mb_ids = set(mb_to_db.keys())

    # Phase 1: Read from local cache
    if not args.api_only:
        cache_dir = get_cache_dir('musicbrainz') / 'recordings'
        script.logger.info(f"Phase 1: Reading from MB cache ({cache_dir})...")

        updates = []  # (db_id, duration_ms) pairs

        for mb_id in list(remaining_mb_ids):
            cache_path = cache_dir / f"recording_{mb_id}.json"
            if not cache_path.exists():
                stats['cache_misses'] += 1
                continue

            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)

                data = cache_data.get('data')
                if not data:
                    stats['cache_misses'] += 1
                    continue

                length = data.get('length')
                if length is None:
                    stats['cache_no_duration'] += 1
                    # Keep in remaining_mb_ids so Phase 2 can re-fetch from API
                    continue

                stats['cache_hits'] += 1
                updates.append((int(length), mb_to_db[mb_id]))
                remaining_mb_ids.discard(mb_id)

            except (json.JSONDecodeError, KeyError) as e:
                script.logger.debug(f"  Cache read error for {mb_id}: {e}")
                stats['cache_misses'] += 1

        script.logger.info(f"  Cache: {stats['cache_hits']} hits, "
                          f"{stats['cache_misses']} misses, "
                          f"{stats['cache_no_duration']} had no duration")

        # Batch update from cache results (commit every 1000 to avoid long transactions)
        if updates and not args.dry_run:
            script.logger.info(f"  Updating {len(updates)} recordings from cache...")
            commit_batch_size = 1000
            for batch_start in range(0, len(updates), commit_batch_size):
                batch = updates[batch_start:batch_start + commit_batch_size]
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.executemany("""
                            UPDATE recordings
                            SET duration_ms = %s, updated_at = NOW()
                            WHERE id = %s
                        """, batch)
                    conn.commit()
                done = min(batch_start + commit_batch_size, len(updates))
                script.logger.info(f"    Committed {done}/{len(updates)}")
            stats['durations_updated'] += len(updates)
            script.logger.info(f"  Updated {len(updates)} recordings from cache")
        elif updates:
            stats['durations_updated'] += len(updates)
            script.logger.info(f"  [DRY RUN] Would update {len(updates)} recordings from cache")

    # Phase 2: Fetch from MusicBrainz API for remaining recordings
    if not args.cache_only and remaining_mb_ids:
        script.logger.info(f"Phase 2: Fetching {len(remaining_mb_ids)} recordings from MusicBrainz API...")

        from integrations.musicbrainz.utils import MusicBrainzSearcher
        mb_searcher = MusicBrainzSearcher(force_refresh=True)

        batch = []
        batch_size = 100  # Commit every 100 updates

        for i, mb_id in enumerate(sorted(remaining_mb_ids), 1):
            if i % 100 == 0:
                script.logger.info(f"  API progress: {i}/{len(remaining_mb_ids)}")

            try:
                details = mb_searcher.get_recording_details(mb_id)

                if details is None:
                    stats['api_errors'] += 1
                    continue

                length = details.get('length')
                if length is None:
                    stats['api_no_duration'] += 1
                    stats['api_fetched'] += 1
                    continue

                stats['api_fetched'] += 1
                batch.append((int(length), mb_to_db[mb_id]))

                # Commit in batches
                if len(batch) >= batch_size:
                    if not args.dry_run:
                        with get_db_connection() as conn:
                            with conn.cursor() as cur:
                                for duration_ms, db_id in batch:
                                    cur.execute("""
                                        UPDATE recordings
                                        SET duration_ms = %s, updated_at = NOW()
                                        WHERE id = %s
                                    """, (duration_ms, db_id))
                            conn.commit()
                    stats['durations_updated'] += len(batch)
                    batch = []

            except Exception as e:
                script.logger.error(f"  Error fetching {mb_id}: {e}")
                stats['api_errors'] += 1

        # Final batch
        if batch:
            if not args.dry_run:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        for duration_ms, db_id in batch:
                            cur.execute("""
                                UPDATE recordings
                                SET duration_ms = %s, updated_at = NOW()
                                WHERE id = %s
                            """, (duration_ms, db_id))
                    conn.commit()
            stats['durations_updated'] += len(batch)

        script.logger.info(f"  API: {stats['api_fetched']} fetched, "
                          f"{stats['api_no_duration']} had no duration, "
                          f"{stats['api_errors']} errors")
    elif remaining_mb_ids:
        script.logger.info(f"Skipping API phase ({len(remaining_mb_ids)} recordings remaining)")

    script.print_summary(stats)
    return stats['api_errors'] == 0


if __name__ == "__main__":
    run_script(main)
