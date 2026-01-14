#!/usr/bin/env python3
"""
Repair Apple Music Links

Validates and repairs stale Apple Music streaming links. For releases that have
Apple Music links but are missing artwork (likely stale), this script:

1. Checks if the stored album ID is still valid on Apple Music
2. If valid, fetches and saves the artwork
3. If stale, searches for the album again and updates the link
4. If found, saves the new link and artwork

Usage:
    # Dry run - see what would be updated
    python scripts/repair_apple_links.py --dry-run

    # Process all stale links
    python scripts/repair_apple_links.py

    # Process with limit
    python scripts/repair_apple_links.py --limit 100

    # Debug mode with verbose output
    python scripts/repair_apple_links.py --debug
"""

from script_base import ScriptBase, run_script

# Now we can import our modules
from db_utils import get_db_connection
from apple_music_client import AppleMusicClient, build_apple_music_album_url
from apple_music_db import upsert_release_imagery, upsert_release_streaming_link
from spotify_matching import (
    normalize_for_comparison,
    calculate_similarity,
    strip_ensemble_suffix,
    is_substring_title_match,
)


def get_releases_missing_artwork():
    """
    Get releases that have Apple Music streaming links but no Apple Music artwork.
    Groups by album ID to avoid redundant API calls for the same album.

    Returns:
        List of dicts with release info and Apple Music album details
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT
                    rsl.release_id,
                    rsl.service_id as apple_album_id,
                    rel.title as release_title,
                    rel.artist_credit,
                    rel.release_year
                FROM release_streaming_links rsl
                JOIN releases rel ON rsl.release_id = rel.id
                WHERE rsl.service = 'apple_music'
                AND NOT EXISTS (
                    SELECT 1 FROM release_imagery ri
                    WHERE ri.release_id = rsl.release_id
                    AND ri.source = 'Apple'
                )
                ORDER BY rsl.service_id, rel.title
            ''')
            return cur.fetchall()


def delete_streaming_link(conn, release_id: str, log):
    """Delete an Apple Music streaming link."""
    try:
        with conn.cursor() as cur:
            cur.execute('''
                DELETE FROM release_streaming_links
                WHERE release_id = %s AND service = 'apple_music'
            ''', (release_id,))
            conn.commit()
            return True
    except Exception as e:
        log.error(f"Failed to delete streaming link: {e}")
        conn.rollback()
        return False


def search_and_match_album(client, artist_credit: str, album_title: str, release_year: int, log):
    """
    Search Apple Music for an album and validate the match.

    Returns:
        Matched album dict or None
    """
    # Try different search strategies
    search_strategies = [
        (artist_credit, album_title),
        (strip_ensemble_suffix(artist_credit), album_title),
        (None, album_title),  # Album only
    ]

    for search_artist, search_album in search_strategies:
        try:
            if search_artist:
                albums = client.search_albums(search_artist, search_album, limit=10)
            else:
                albums = client.search_albums(search_album, limit=10)

            if not albums:
                continue

            # Validate each result
            for album in albums:
                am_artist = album.get('artist', '')
                am_album = album.get('name', '')

                # Calculate similarities
                artist_sim = calculate_similarity(
                    normalize_for_comparison(artist_credit or ''),
                    normalize_for_comparison(am_artist)
                )
                album_sim = calculate_similarity(
                    normalize_for_comparison(album_title),
                    normalize_for_comparison(am_album)
                )

                # Check for good match
                artist_ok = artist_sim >= 60 or is_substring_title_match(
                    normalize_for_comparison(artist_credit or ''),
                    normalize_for_comparison(am_artist)
                )
                album_ok = album_sim >= 60 or is_substring_title_match(
                    normalize_for_comparison(album_title),
                    normalize_for_comparison(am_album)
                )

                if artist_ok and album_ok:
                    log.debug(f"    Match found: {am_artist} - {am_album} "
                             f"(artist: {artist_sim:.0f}%, album: {album_sim:.0f}%)")
                    return album

        except Exception as e:
            log.debug(f"    Search error: {e}")
            continue

    return None


def main():
    script = ScriptBase(
        name="repair_apple_links",
        description="Validate and repair stale Apple Music streaming links",
        epilog="""
Examples:
  python scripts/repair_apple_links.py --dry-run
  python scripts/repair_apple_links.py --limit 100
  python scripts/repair_apple_links.py --debug
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
    all_releases = get_releases_missing_artwork()
    script.logger.info(f"Found {len(all_releases)} releases to check")

    if not all_releases:
        script.logger.info("Nothing to do!")
        return True

    # Apply limit if specified
    releases = all_releases[:args.limit] if args.limit else all_releases
    if args.limit and len(all_releases) > args.limit:
        script.logger.info(f"Processing first {args.limit} releases (of {len(all_releases)})")

    # Initialize iTunes API client
    client = AppleMusicClient(
        cache_days=30,
        force_refresh=False,  # Use cache for lookups
        rate_limit_delay=0.5,
        max_retries=3,
        logger=script.logger
    )

    # Stats tracking
    stats = {
        'releases_checked': 0,
        'links_valid': 0,
        'links_stale': 0,
        'artwork_added': 0,
        'links_repaired': 0,
        'links_removed': 0,
        'errors': 0,
    }

    # Group releases by album ID to avoid redundant lookups
    album_id_cache = {}  # album_id -> (is_valid, album_data)

    for i, release in enumerate(releases):
        release_id = str(release['release_id'])
        album_id = str(release['apple_album_id'])
        title = release['release_title']
        artist = release['artist_credit'] or 'Unknown Artist'
        year = release['release_year']

        stats['releases_checked'] += 1

        script.logger.info(f"[{i + 1}/{len(releases)}] {artist} - {title}")

        # Check cache first
        if album_id in album_id_cache:
            is_valid, album = album_id_cache[album_id]
            script.logger.debug(f"  Using cached result for album ID {album_id}")
        else:
            # Lookup album
            try:
                album = client.lookup_album(album_id)
                is_valid = album is not None
                album_id_cache[album_id] = (is_valid, album)
            except Exception as e:
                script.logger.error(f"  Lookup error: {e}")
                stats['errors'] += 1
                continue

        if is_valid and album:
            # Album still exists - just need to add artwork
            stats['links_valid'] += 1

            artwork = album.get('artwork')
            if artwork and (artwork.get('medium') or artwork.get('large')):
                if args.dry_run:
                    script.logger.info(f"  [DRY RUN] Would add artwork for valid album")
                    stats['artwork_added'] += 1
                else:
                    with get_db_connection() as conn:
                        if upsert_release_imagery(conn, release_id, artwork, album_id, log=script.logger):
                            stats['artwork_added'] += 1
                            script.logger.info(f"  Added artwork")
                        else:
                            stats['errors'] += 1
            else:
                script.logger.debug(f"  Album valid but no artwork available")
        else:
            # Album is stale - try to find a replacement
            stats['links_stale'] += 1
            script.logger.info(f"  Album ID {album_id} is stale, searching for replacement...")

            new_album = search_and_match_album(client, artist, title, year, script.logger)

            if new_album:
                new_album_id = str(new_album['id'])
                new_album_url = build_apple_music_album_url(new_album_id)
                artwork = new_album.get('artwork')

                script.logger.info(f"  Found replacement: {new_album.get('artist')} - {new_album.get('name')} (ID: {new_album_id})")

                if args.dry_run:
                    script.logger.info(f"  [DRY RUN] Would update link and add artwork")
                    stats['links_repaired'] += 1
                    if artwork:
                        stats['artwork_added'] += 1
                else:
                    with get_db_connection() as conn:
                        # Update the streaming link
                        if upsert_release_streaming_link(
                            conn,
                            release_id=release_id,
                            service_id=new_album_id,
                            service_url=new_album_url,
                            match_confidence=0.8,
                            match_method='repair_script',
                            log=script.logger
                        ):
                            stats['links_repaired'] += 1
                            script.logger.info(f"  Updated streaming link")

                            # Add artwork
                            if artwork and (artwork.get('medium') or artwork.get('large')):
                                if upsert_release_imagery(conn, release_id, artwork, new_album_id, log=script.logger):
                                    stats['artwork_added'] += 1
                                    script.logger.info(f"  Added artwork")
                        else:
                            stats['errors'] += 1
            else:
                # Couldn't find replacement - remove stale link
                script.logger.info(f"  No replacement found, removing stale link")

                if args.dry_run:
                    script.logger.info(f"  [DRY RUN] Would remove stale link")
                    stats['links_removed'] += 1
                else:
                    with get_db_connection() as conn:
                        if delete_streaming_link(conn, release_id, script.logger):
                            stats['links_removed'] += 1
                            script.logger.info(f"  Removed stale link")
                        else:
                            stats['errors'] += 1

    # Print summary
    script.print_summary(stats)

    return stats['errors'] == 0 or (stats['artwork_added'] + stats['links_repaired']) > 0


if __name__ == "__main__":
    run_script(main)
