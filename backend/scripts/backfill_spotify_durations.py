#!/usr/bin/env python3
"""
Backfill Spotify Track Durations

Fetches duration_ms from Spotify API for recording_release_streaming_links
entries where service='spotify' and duration_ms is NULL.

Uses Spotify's batch endpoint (50 tracks per API call) to minimize round-trips.

Usage:
    python backfill_spotify_durations.py --limit 500
    python backfill_spotify_durations.py --limit 500 --dry-run
    python backfill_spotify_durations.py --debug
"""

from script_base import ScriptBase, run_script
from db_utils import get_db_connection
from integrations.spotify.client import SpotifyClient


def main():
    script = ScriptBase(
        name="backfill_spotify_durations",
        description="Backfill duration_ms for Spotify tracks from batch API",
        epilog="""
Examples:
  python backfill_spotify_durations.py --limit 500
  python backfill_spotify_durations.py --limit 500 --dry-run
  python backfill_spotify_durations.py --limit 35000 --debug
        """
    )

    script.add_dry_run_arg()
    script.add_debug_arg()
    script.add_limit_arg(default=500)

    args = script.parse_args()

    script.print_header({
        "DRY RUN": args.dry_run,
    })

    stats = {
        'links_found': 0,
        'batches_processed': 0,
        'durations_updated': 0,
        'tracks_not_found': 0,
        'tracks_no_duration': 0,
        'api_calls': 0,
        'errors': 0,
    }

    script.logger.info("Finding Spotify streaming links without duration_ms...")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, service_id
                FROM recording_release_streaming_links
                WHERE service = 'spotify'
                  AND duration_ms IS NULL
                  AND service_id IS NOT NULL
                ORDER BY created_at DESC
                LIMIT %s
            """, (args.limit,))

            links = cur.fetchall()

    stats['links_found'] = len(links)
    script.logger.info(f"Found {len(links)} Spotify links without duration_ms")

    if not links:
        script.print_summary(stats)
        return True

    spotify_client = SpotifyClient(logger=script.logger)

    # Batch into groups of 50
    batch_size = 50
    batches = [links[i:i + batch_size] for i in range(0, len(links), batch_size)]

    script.logger.info(f"Processing in {len(batches)} batches of up to {batch_size} tracks")
    script.logger.info("")

    for batch_num, batch in enumerate(batches, 1):
        script.logger.info(f"[Batch {batch_num}/{len(batches)}] Fetching {len(batch)} tracks...")

        track_ids = [link['service_id'] for link in batch]

        try:
            tracks_data = spotify_client.get_tracks_batch(track_ids)
            stats['api_calls'] += 1

            if tracks_data is None:
                script.logger.error(f"  Failed to fetch batch from Spotify")
                stats['errors'] += 1
                continue

            stats['batches_processed'] += 1

            batch_updated = 0
            for link in batch:
                track_id = link['service_id']
                link_id = link['id']

                track_data = tracks_data.get(track_id)
                if not track_data:
                    script.logger.debug(f"  Track not found in Spotify: {track_id}")
                    stats['tracks_not_found'] += 1
                    continue

                duration_ms = track_data.get('duration_ms')
                if not duration_ms:
                    script.logger.debug(f"  Track has no duration_ms: {track_id}")
                    stats['tracks_no_duration'] += 1
                    continue

                if not args.dry_run:
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE recording_release_streaming_links
                                SET duration_ms = %s, updated_at = NOW()
                                WHERE id = %s
                            """, (duration_ms, link_id))
                        conn.commit()

                stats['durations_updated'] += 1
                batch_updated += 1

            script.logger.info(f"  Updated {batch_updated} durations")

        except Exception as e:
            script.logger.error(f"  Error processing batch: {e}")
            stats['errors'] += 1

    script.print_summary(stats)
    return stats['errors'] == 0


if __name__ == "__main__":
    run_script(main)
