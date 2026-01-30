#!/usr/bin/env python3
"""
Backfill Recording Titles from MusicBrainz

Fetches recording titles from MusicBrainz API for recordings that have
a musicbrainz_id but no title stored locally.

The recording title from MusicBrainz may differ from the song title
(e.g., different punctuation, "live" suffixes, etc.)

Usage:
    python backfill_recording_titles.py --limit 100
    python backfill_recording_titles.py --limit 100 --dry-run
    python backfill_recording_titles.py --debug

Rate Limiting:
    Respects MusicBrainz rate limit (~200 requests per minute).
"""

from script_base import ScriptBase, run_script
from db_utils import get_db_connection
from mb_utils import MusicBrainzSearcher


def main():
    script = ScriptBase(
        name="backfill_recording_titles",
        description="Backfill recording titles from MusicBrainz API",
        epilog="""
Examples:
  python backfill_recording_titles.py --limit 100
  python backfill_recording_titles.py --limit 100 --dry-run
  python backfill_recording_titles.py --limit 1000 --debug
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
        'recordings_found': 0,
        'recordings_updated': 0,
        'recordings_skipped': 0,
        'recordings_not_found_in_mb': 0,
        'errors': 0,
    }

    # Query recordings that have musicbrainz_id but no title
    script.logger.info("Finding recordings without titles...")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, musicbrainz_id, song_id
                FROM recordings
                WHERE musicbrainz_id IS NOT NULL
                  AND title IS NULL
                ORDER BY created_at DESC
                LIMIT %s
            """, (args.limit,))

            recordings = cur.fetchall()

    stats['recordings_found'] = len(recordings)
    script.logger.info(f"Found {len(recordings)} recordings to process")
    script.logger.info("")

    if not recordings:
        script.print_summary(stats)
        return True

    # Initialize MusicBrainz API client (handles rate limiting internally)
    mb_searcher = MusicBrainzSearcher()
    script.logger.info(f"MusicBrainz rate limit: {mb_searcher.min_request_interval}s between requests")

    # Process each recording
    for i, recording in enumerate(recordings, 1):
        recording_id = recording['id']
        mb_recording_id = recording['musicbrainz_id']

        script.logger.info(f"[{i}/{len(recordings)}] Processing MB:{mb_recording_id[:12]}...")

        # Fetch recording details from MusicBrainz
        try:
            mb_data = mb_searcher.get_recording_details(mb_recording_id)

            if not mb_data:
                script.logger.warning(f"  Recording not found in MusicBrainz")
                stats['recordings_not_found_in_mb'] += 1
                continue

            title = mb_data.get('title')
            if not title:
                script.logger.warning(f"  Recording has no title in MusicBrainz")
                stats['recordings_skipped'] += 1
                continue

            script.logger.info(f"  Title: {title}")

            if not args.dry_run:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE recordings
                            SET title = %s
                            WHERE id = %s
                        """, (title, recording_id))
                    conn.commit()

            stats['recordings_updated'] += 1

        except Exception as e:
            script.logger.error(f"  Error: {e}")
            stats['errors'] += 1

    script.print_summary(stats)
    return stats['errors'] == 0


if __name__ == "__main__":
    run_script(main)
