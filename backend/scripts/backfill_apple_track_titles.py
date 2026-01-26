#!/usr/bin/env python3
"""
Backfill Track Titles from Apple Music

Fetches track names from Apple Music/iTunes API for recording_releases that have
Apple Music track links but no track_title stored locally.

This fills in gaps for tracks that were matched via Apple Music but where
track_title wasn't saved at the time of matching.

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
        'recording_releases_found': 0,
        'tracks_updated': 0,
        'tracks_not_found_in_apple': 0,
        'api_calls': 0,
        'errors': 0,
    }

    # Query recording_releases that have Apple Music links but no track_title
    # We need to join with recording_release_streaming_links to find Apple Music tracks
    script.logger.info("Finding recording_releases with Apple Music links but no track_title...")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rr.id, rrsl.service_id as apple_music_track_id
                FROM recording_releases rr
                JOIN recording_release_streaming_links rrsl ON rr.id = rrsl.recording_release_id
                WHERE rrsl.service = 'apple_music'
                  AND rr.track_title IS NULL
                ORDER BY rr.created_at DESC
                LIMIT %s
            """, (args.limit,))

            recording_releases = cur.fetchall()

    stats['recording_releases_found'] = len(recording_releases)
    script.logger.info(f"Found {len(recording_releases)} recording_releases to process")
    script.logger.info("")

    if not recording_releases:
        script.print_summary(stats)
        return True

    # Initialize Apple Music client
    apple_client = AppleMusicClient(logger=script.logger)

    # Process each recording_release
    for i, rr in enumerate(recording_releases, 1):
        recording_release_id = rr['id']
        apple_track_id = rr['apple_music_track_id']

        script.logger.info(f"[{i}/{len(recording_releases)}] Looking up track {apple_track_id}...")

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

            if not args.dry_run:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE recording_releases
                            SET track_title = %s
                            WHERE id = %s
                        """, (track_name, recording_release_id))
                    conn.commit()

            stats['tracks_updated'] += 1

        except Exception as e:
            script.logger.error(f"  Error: {e}")
            stats['errors'] += 1

    script.print_summary(stats)
    return stats['errors'] == 0


if __name__ == "__main__":
    run_script(main)
