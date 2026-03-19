#!/usr/bin/env python3
"""
Backfill Track Titles from Apple Music

Fetches track names from Apple Music/iTunes API for streaming links that have
an Apple Music service_id but no service_title stored locally.

This fills in gaps for tracks that were matched via Apple Music but where
service_title wasn't saved at the time of matching.

Usage:
    python backfill_apple_track_titles.py --limit 100
    python backfill_apple_track_titles.py --limit 100 --dry-run
    python backfill_apple_track_titles.py --debug

Rate Limiting:
    iTunes API has aggressive rate limiting. This script processes one track
    at a time with delays to avoid hitting rate limits.
"""

from script_base import ScriptBase, run_script
from db_utils import get_db_connection
from apple_music_client import AppleMusicClient


def main():
    script = ScriptBase(
        name="backfill_apple_track_titles",
        description="Backfill track titles from Apple Music/iTunes API",
        epilog="""
Examples:
  python backfill_apple_track_titles.py --limit 100
  python backfill_apple_track_titles.py --limit 100 --dry-run
  python backfill_apple_track_titles.py --limit 500 --debug
        """
    )

    script.add_dry_run_arg()
    script.add_debug_arg()
    script.add_limit_arg(default=100)

    args = script.parse_args()

    script.print_header({
        "DRY RUN": args.dry_run,
    })

    stats = {
        'streaming_links_found': 0,
        'tracks_updated': 0,
        'tracks_not_found_in_apple': 0,
        'api_calls': 0,
        'errors': 0,
    }

    # Query Apple Music streaming links missing service_title
    script.logger.info("Finding Apple Music streaming links without service_title...")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, service_id
                FROM recording_release_streaming_links
                WHERE service = 'apple_music'
                  AND service_id IS NOT NULL
                  AND service_title IS NULL
                ORDER BY created_at DESC
                LIMIT %s
            """, (args.limit,))

            streaming_links = cur.fetchall()

    stats['streaming_links_found'] = len(streaming_links)
    script.logger.info(f"Found {len(streaming_links)} streaming links to process")
    script.logger.info("")

    if not streaming_links:
        script.print_summary(stats)
        return True

    # Initialize Apple Music client
    apple_client = AppleMusicClient(logger=script.logger)

    # Process each streaming link, batching DB writes
    batch_size = 50
    updates = []

    for i, link in enumerate(streaming_links, 1):
        streaming_link_id = link['id']
        apple_track_id = link['service_id']

        script.logger.info(f"[{i}/{len(streaming_links)}] Looking up track {apple_track_id}...")

        try:
            # Look up track in Apple Music
            track_data = apple_client.lookup_track(apple_track_id)
            stats['api_calls'] += 1

            if not track_data:
                script.logger.warning(f"  Track not found in Apple Music")
                stats['tracks_not_found_in_apple'] += 1
                continue

            track_name = track_data.get('name')
            if not track_name:
                script.logger.warning(f"  Track has no name")
                stats['tracks_not_found_in_apple'] += 1
                continue

            script.logger.info(f"  Title: {track_name}")
            updates.append((track_name, streaming_link_id))
            stats['tracks_updated'] += 1

            # Flush writes in batches
            if len(updates) >= batch_size:
                if not args.dry_run:
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.executemany("""
                                UPDATE recording_release_streaming_links
                                SET service_title = %s, updated_at = CURRENT_TIMESTAMP
                                WHERE id = %s
                            """, updates)
                        conn.commit()
                script.logger.info(f"  Committed {len(updates)} updates")
                updates = []

        except Exception as e:
            script.logger.error(f"  Error: {e}")
            stats['errors'] += 1

    # Flush remaining updates
    if updates and not args.dry_run:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany("""
                    UPDATE recording_release_streaming_links
                    SET service_title = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, updates)
            conn.commit()
        script.logger.info(f"  Committed {len(updates)} updates")

    script.print_summary(stats)
    return stats['errors'] == 0


if __name__ == "__main__":
    run_script(main)
