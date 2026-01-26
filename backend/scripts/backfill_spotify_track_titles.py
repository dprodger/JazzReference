#!/usr/bin/env python3
"""
Backfill Track Titles from Spotify

Fetches track names from Spotify API for recording_releases that have
a spotify_track_id but no track_title stored locally.

Uses Spotify's batch endpoint to fetch up to 50 tracks per API call,
making this much more efficient than individual lookups.

Usage:
    python backfill_spotify_track_titles.py --limit 500
    python backfill_spotify_track_titles.py --limit 500 --dry-run
    python backfill_spotify_track_titles.py --debug

Rate Limiting:
    Uses batch API (50 tracks/request) to minimize API calls.
"""

from script_base import ScriptBase, run_script
from db_utils import get_db_connection
from spotify_client import SpotifyClient


def main():
    script = ScriptBase(
        name="backfill_spotify_track_titles",
        description="Backfill track titles from Spotify batch API",
        epilog="""
Examples:
  python backfill_spotify_track_titles.py --limit 500
  python backfill_spotify_track_titles.py --limit 500 --dry-run
  python backfill_spotify_track_titles.py --limit 5000 --debug
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
        'recording_releases_found': 0,
        'batches_processed': 0,
        'tracks_updated': 0,
        'tracks_not_found_in_spotify': 0,
        'api_calls': 0,
        'errors': 0,
    }

    # Query recording_releases that have spotify_track_id but no track_title
    script.logger.info("Finding recording_releases without track_titles...")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, spotify_track_id
                FROM recording_releases
                WHERE spotify_track_id IS NOT NULL
                  AND track_title IS NULL
                ORDER BY created_at DESC
                LIMIT %s
            """, (args.limit,))

            recording_releases = cur.fetchall()

    stats['recording_releases_found'] = len(recording_releases)
    script.logger.info(f"Found {len(recording_releases)} recording_releases to process")

    if not recording_releases:
        script.print_summary(stats)
        return True

    # Initialize Spotify client
    spotify_client = SpotifyClient(logger=script.logger)

    # Batch track IDs into groups of 50
    batch_size = 50
    batches = []
    current_batch = []

    for rr in recording_releases:
        current_batch.append(rr)
        if len(current_batch) >= batch_size:
            batches.append(current_batch)
            current_batch = []

    if current_batch:
        batches.append(current_batch)

    script.logger.info(f"Processing in {len(batches)} batches of up to {batch_size} tracks")
    script.logger.info("")

    # Process each batch
    for batch_num, batch in enumerate(batches, 1):
        script.logger.info(f"[Batch {batch_num}/{len(batches)}] Fetching {len(batch)} tracks...")

        # Extract track IDs for this batch
        track_ids = [rr['spotify_track_id'] for rr in batch]

        try:
            # Fetch track data in batch
            tracks_data = spotify_client.get_tracks_batch(track_ids)
            stats['api_calls'] += 1

            if tracks_data is None:
                script.logger.error(f"  Failed to fetch batch from Spotify")
                stats['errors'] += 1
                continue

            stats['batches_processed'] += 1

            # Update each recording_release with track name
            for rr in batch:
                track_id = rr['spotify_track_id']
                recording_release_id = rr['id']

                track_data = tracks_data.get(track_id)
                if not track_data:
                    script.logger.debug(f"  Track not found in Spotify: {track_id}")
                    stats['tracks_not_found_in_spotify'] += 1
                    continue

                track_name = track_data.get('name')
                if not track_name:
                    script.logger.debug(f"  Track has no name: {track_id}")
                    stats['tracks_not_found_in_spotify'] += 1
                    continue

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

            script.logger.info(f"  Updated {sum(1 for rr in batch if tracks_data.get(rr['spotify_track_id']))} tracks")

        except Exception as e:
            script.logger.error(f"  Error processing batch: {e}")
            stats['errors'] += 1

    script.print_summary(stats)
    return stats['errors'] == 0


if __name__ == "__main__":
    run_script(main)
