#!/usr/bin/env python3
"""
Backfill Track Titles from Spotify

Fetches track names from Spotify API for streaming links that have
a Spotify service_id but no service_title stored locally.

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
from integrations.spotify.client import SpotifyClient


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
        'streaming_links_found': 0,
        'batches_processed': 0,
        'tracks_updated': 0,
        'tracks_not_found_in_spotify': 0,
        'api_calls': 0,
        'errors': 0,
    }

    # Query Spotify streaming links missing service_title
    script.logger.info("Finding Spotify streaming links without service_title...")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, service_id
                FROM recording_release_streaming_links
                WHERE service = 'spotify'
                  AND service_id IS NOT NULL
                  AND service_title IS NULL
                ORDER BY created_at DESC
                LIMIT %s
            """, (args.limit,))

            streaming_links = cur.fetchall()

    stats['streaming_links_found'] = len(streaming_links)
    script.logger.info(f"Found {len(streaming_links)} streaming links to process")

    if not streaming_links:
        script.print_summary(stats)
        return True

    # Initialize Spotify client
    spotify_client = SpotifyClient(logger=script.logger)

    # Batch track IDs into groups of 50
    batch_size = 50
    batches = []
    current_batch = []

    for link in streaming_links:
        current_batch.append(link)
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
        track_ids = [link['service_id'] for link in batch]

        try:
            # Fetch track data in batch
            tracks_data = spotify_client.get_tracks_batch(track_ids)
            stats['api_calls'] += 1

            if tracks_data is None:
                script.logger.error(f"  Failed to fetch batch from Spotify")
                stats['errors'] += 1
                continue

            stats['batches_processed'] += 1

            # Collect updates for batch write
            updates = []
            for link in batch:
                track_id = link['service_id']
                streaming_link_id = link['id']

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

                updates.append((track_name, streaming_link_id))

            # Write all updates in a single connection/transaction
            if updates and not args.dry_run:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.executemany("""
                            UPDATE recording_release_streaming_links
                            SET service_title = %s, updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, updates)
                    conn.commit()

            stats['tracks_updated'] += len(updates)
            script.logger.info(f"  Updated {len(updates)} tracks")

        except Exception as e:
            script.logger.error(f"  Error processing batch: {e}")
            stats['errors'] += 1

    script.print_summary(stats)
    return stats['errors'] == 0


if __name__ == "__main__":
    run_script(main)
