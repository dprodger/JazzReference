#!/usr/bin/env python3
"""
Backfill Apple Music Artwork

Fetches album artwork from iTunes API for releases that have Apple Music
streaming links but are missing artwork in the release_imagery table.

This addresses the issue where albums matched via local catalog (which doesn't
include artwork URLs) were saved without artwork.

Usage:
    # Dry run - see what would be updated
    python scripts/backfill_apple_artwork.py --dry-run

    # Process all missing artwork
    python scripts/backfill_apple_artwork.py

    # Process with limit
    python scripts/backfill_apple_artwork.py --limit 100

    # Debug mode with verbose output
    python scripts/backfill_apple_artwork.py --debug
"""

from script_base import ScriptBase, run_script

# Now we can import our modules
from db_utils import get_db_connection
from apple_music_client import AppleMusicClient
from apple_music_db import upsert_release_imagery


def get_releases_missing_artwork(limit: int = None):
    """
    Get releases that have Apple Music streaming links but no Apple Music artwork.

    Returns:
        List of dicts with release_id and apple_music_album_id
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT
                    rsl.release_id,
                    rsl.service_id as apple_music_album_id,
                    rel.title as release_title,
                    rel.artist_credit
                FROM release_streaming_links rsl
                JOIN releases rel ON rsl.release_id = rel.id
                -- Has Apple Music streaming link
                WHERE rsl.service = 'apple_music'
                -- But no Apple Music artwork
                AND NOT EXISTS (
                    SELECT 1 FROM release_imagery ri
                    WHERE ri.release_id = rsl.release_id
                    AND ri.source = 'Apple'
                )
                ORDER BY rel.title
            """
            if limit:
                query += f" LIMIT {limit}"

            cur.execute(query)
            return cur.fetchall()


def main():
    script = ScriptBase(
        name="backfill_apple_artwork",
        description="Fetch Apple Music artwork for releases missing it",
        epilog="""
Examples:
  python scripts/backfill_apple_artwork.py --dry-run
  python scripts/backfill_apple_artwork.py --limit 100
  python scripts/backfill_apple_artwork.py --debug
        """
    )

    script.add_dry_run_arg()
    script.add_debug_arg()
    script.add_limit_arg(default=None)

    args = script.parse_args()

    script.print_header({
        "DRY RUN": args.dry_run,
    })

    # Get releases missing artwork
    script.logger.info("Finding releases with Apple Music links but no artwork...")
    releases = get_releases_missing_artwork(args.limit)
    script.logger.info(f"Found {len(releases)} releases missing Apple Music artwork")

    if not releases:
        script.logger.info("Nothing to do!")
        return True

    # Initialize iTunes API client
    client = AppleMusicClient(
        cache_days=30,
        rate_limit_delay=0.5,  # Conservative rate limiting
        max_retries=3,
        logger=script.logger
    )

    # Stats tracking
    stats = {
        'releases_processed': 0,
        'artwork_added': 0,
        'artwork_not_found': 0,
        'errors': 0,
        'api_calls': 0,
        'cache_hits': 0,
    }

    # Process each release
    for i, release in enumerate(releases):
        release_id = str(release['release_id'])
        album_id = str(release['apple_music_album_id'])
        title = release['release_title']
        artist = release['artist_credit'] or 'Unknown Artist'

        stats['releases_processed'] += 1

        script.logger.info(f"[{i + 1}/{len(releases)}] {artist} - {title}")
        script.logger.debug(f"  Release ID: {release_id}, Apple Album ID: {album_id}")

        try:
            # Lookup album to get artwork
            album = client.lookup_album(album_id)

            if album and album.get('artwork'):
                artwork = album['artwork']

                # Check if we actually got valid URLs
                if artwork.get('medium') or artwork.get('large'):
                    if args.dry_run:
                        script.logger.info(f"  [DRY RUN] Would add artwork: {artwork.get('medium', artwork.get('large'))[:60]}...")
                        stats['artwork_added'] += 1
                    else:
                        with get_db_connection() as conn:
                            success = upsert_release_imagery(
                                conn,
                                release_id=release_id,
                                artwork=artwork,
                                source_id=album_id,
                                dry_run=False,
                                log=script.logger
                            )
                            if success:
                                stats['artwork_added'] += 1
                                script.logger.info(f"  Added artwork")
                            else:
                                stats['errors'] += 1
                                script.logger.warning(f"  Failed to save artwork")
                else:
                    stats['artwork_not_found'] += 1
                    script.logger.debug(f"  No valid artwork URLs in response")
            else:
                stats['artwork_not_found'] += 1
                script.logger.debug(f"  Album lookup returned no artwork")

        except Exception as e:
            stats['errors'] += 1
            script.logger.error(f"  Error: {e}")

    # Aggregate client stats
    stats['api_calls'] = client.stats.get('api_calls', 0)
    stats['cache_hits'] = client.stats.get('cache_hits', 0)

    # Print summary
    script.print_summary(stats)

    return stats['errors'] == 0 or stats['artwork_added'] > 0


if __name__ == "__main__":
    run_script(main)
