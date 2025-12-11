#!/usr/bin/env python3
"""
Backfill Performer Sort Names from MusicBrainz

Fetches sort_name, artist_type, and disambiguation from MusicBrainz for
performers that have a musicbrainz_id but are missing these fields.

This script uses a two-phase approach:
1. First, extract artist data from cached release files (no API calls needed)
2. Then, for any remaining performers, fetch from MusicBrainz API

This is a one-time migration script to populate the new fields added to
the performers table.

Run after applying the migration in jazz-db-schema.sql that adds:
- sort_name VARCHAR(255)
- artist_type VARCHAR(50)
- disambiguation VARCHAR(500)
"""

import json
import time
from pathlib import Path
from script_base import ScriptBase, run_script
from db_utils import get_db_connection
from mb_utils import MusicBrainzSearcher
from cache_utils import get_cache_dir


def extract_artists_from_release_cache():
    """
    Extract artist metadata from all cached release files.

    Returns:
        dict: Mapping of artist MBID -> {sort_name, artist_type, disambiguation}
    """
    release_cache_dir = get_cache_dir('musicbrainz') / 'releases'
    artists = {}

    if not release_cache_dir.exists():
        return artists

    for cache_file in release_cache_dir.glob('release_*.json'):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            release_data = cache_data.get('data')
            if not release_data:
                continue

            # Extract from media/tracks/artist-credit
            for medium in release_data.get('media') or []:
                for track in medium.get('tracks') or []:
                    # Track-level artist credits
                    for credit in track.get('artist-credit') or []:
                        artist = credit.get('artist')
                        if artist and artist.get('id'):
                            mbid = artist['id']
                            if mbid not in artists:
                                artists[mbid] = {
                                    'sort_name': artist.get('sort-name'),
                                    'artist_type': artist.get('type'),
                                    'disambiguation': artist.get('disambiguation'),
                                    'name': artist.get('name')
                                }

                    # Recording-level artist credits
                    recording = track.get('recording') or {}
                    for credit in recording.get('artist-credit') or []:
                        artist = credit.get('artist')
                        if artist and artist.get('id'):
                            mbid = artist['id']
                            if mbid not in artists:
                                artists[mbid] = {
                                    'sort_name': artist.get('sort-name'),
                                    'artist_type': artist.get('type'),
                                    'disambiguation': artist.get('disambiguation'),
                                    'name': artist.get('name')
                                }

                    # Recording relations (performers with instruments)
                    for relation in recording.get('relations') or []:
                        if relation.get('target-type') == 'artist':
                            artist = relation.get('artist')
                            if artist and artist.get('id'):
                                mbid = artist['id']
                                if mbid not in artists:
                                    artists[mbid] = {
                                        'sort_name': artist.get('sort-name'),
                                        'artist_type': artist.get('type'),
                                        'disambiguation': artist.get('disambiguation'),
                                        'name': artist.get('name')
                                    }

            # Release-level artist credits
            for credit in release_data.get('artist-credit') or []:
                artist = credit.get('artist')
                if artist and artist.get('id'):
                    mbid = artist['id']
                    if mbid not in artists:
                        artists[mbid] = {
                            'sort_name': artist.get('sort-name'),
                            'artist_type': artist.get('type'),
                            'disambiguation': artist.get('disambiguation'),
                            'name': artist.get('name')
                        }

        except Exception as e:
            # Skip files we can't parse
            continue

    return artists


def main() -> bool:
    script = ScriptBase(
        name="backfill_performer_sort_names",
        description="Backfill performer sort_name, artist_type, disambiguation from MusicBrainz",
        epilog="""
Examples:
  # Dry run to see what would be updated
  python backfill_performer_sort_names.py --dry-run

  # Actually update performers
  python backfill_performer_sort_names.py

  # Limit to first 50 performers
  python backfill_performer_sort_names.py --limit 50 --dry-run

  # Force update even if sort_name already exists
  python backfill_performer_sort_names.py --force

  # Debug mode for verbose output
  python backfill_performer_sort_names.py --debug --limit 10
        """
    )

    script.add_dry_run_arg()
    script.add_debug_arg()
    script.add_limit_arg(default=10000)

    script.parser.add_argument(
        '--force',
        action='store_true',
        help='Update performers even if they already have a sort_name'
    )

    script.parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Commit after this many updates (default: 50)'
    )

    script.parser.add_argument(
        '--delay',
        type=float,
        default=1.1,
        help='Delay between MusicBrainz API calls in seconds (default: 1.1)'
    )

    args = script.parse_args()

    script.print_header({
        "DRY RUN": args.dry_run,
        "FORCE": args.force,
        "LIMIT": args.limit,
        "BATCH SIZE": args.batch_size,
        "API DELAY": f"{args.delay}s",
    })

    # Initialize MusicBrainz searcher
    mb_searcher = MusicBrainzSearcher()

    # Stats tracking
    stats = {
        'total_candidates': 0,
        'already_has_sort_name': 0,
        'no_mbid': 0,
        'from_release_cache': 0,
        'from_artist_cache': 0,
        'api_fetched': 0,
        'api_errors': 0,
        'updated': 0,
        'no_change': 0,
    }

    # Phase 1: Extract artist data from release cache files
    script.logger.info("Phase 1: Extracting artist data from release cache files...")
    release_cache_artists = extract_artists_from_release_cache()
    script.logger.info(f"Found {len(release_cache_artists)} unique artists in release cache")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Build query based on force mode
            if args.force:
                # Get all performers with musicbrainz_id
                cur.execute("""
                    SELECT id, name, musicbrainz_id, sort_name, artist_type, disambiguation
                    FROM performers
                    WHERE musicbrainz_id IS NOT NULL
                    ORDER BY name
                    LIMIT %s
                """, (args.limit,))
            else:
                # Get only performers missing sort_name
                cur.execute("""
                    SELECT id, name, musicbrainz_id, sort_name, artist_type, disambiguation
                    FROM performers
                    WHERE musicbrainz_id IS NOT NULL
                      AND sort_name IS NULL
                    ORDER BY name
                    LIMIT %s
                """, (args.limit,))

            performers = cur.fetchall()
            stats['total_candidates'] = len(performers)

            script.logger.info(f"Phase 2: Processing {len(performers)} performers...")

            batch_count = 0

            for performer in performers:
                performer_id = performer['id']
                name = performer['name']
                mbid = performer['musicbrainz_id']
                current_sort_name = performer['sort_name']

                if not args.force and current_sort_name:
                    stats['already_has_sort_name'] += 1
                    continue

                if not mbid:
                    stats['no_mbid'] += 1
                    continue

                script.logger.debug(f"Processing: {name} ({mbid})")

                # Try sources in order: release cache -> artist cache -> API
                artist_data = None
                source = None

                # 1. Check release cache (extracted in Phase 1)
                if mbid in release_cache_artists:
                    artist_data = release_cache_artists[mbid]
                    source = 'release_cache'
                    stats['from_release_cache'] += 1
                    script.logger.debug(f"  Found in release cache")
                else:
                    # 2. Try artist cache / API (get_artist_details handles both)
                    try:
                        api_data = mb_searcher.get_artist_details(mbid)

                        if api_data:
                            artist_data = {
                                'sort_name': api_data.get('sort-name'),
                                'artist_type': api_data.get('type'),
                                'disambiguation': api_data.get('disambiguation')
                            }

                            # Check if API call was made (vs artist cache hit)
                            if mb_searcher.last_made_api_call:
                                source = 'api'
                                stats['api_fetched'] += 1
                                # Additional delay after API calls
                                time.sleep(args.delay)
                            else:
                                source = 'artist_cache'
                                stats['from_artist_cache'] += 1

                    except Exception as e:
                        script.logger.warning(f"  Error fetching {name} ({mbid}): {e}")
                        stats['api_errors'] += 1
                        continue

                if not artist_data:
                    script.logger.debug(f"  No data found for {name}")
                    stats['api_errors'] += 1
                    continue

                # Extract the fields we want
                new_sort_name = artist_data.get('sort_name')
                new_artist_type = artist_data.get('artist_type')
                new_disambiguation = artist_data.get('disambiguation')

                # Check if there's anything to update
                if (new_sort_name == current_sort_name and
                    new_artist_type == performer['artist_type'] and
                    new_disambiguation == performer['disambiguation']):
                    stats['no_change'] += 1
                    script.logger.debug(f"  No change needed for {name}")
                    continue

                # Log what we're updating
                script.logger.info(
                    f"  {name}: sort_name='{new_sort_name}', "
                    f"type='{new_artist_type}', "
                    f"disambiguation='{new_disambiguation[:50] if new_disambiguation else None}...' "
                    f"[{source}]"
                )

                if not args.dry_run:
                    cur.execute("""
                        UPDATE performers
                        SET sort_name = %s,
                            artist_type = %s,
                            disambiguation = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (new_sort_name, new_artist_type, new_disambiguation, performer_id))

                    batch_count += 1

                    # Commit in batches
                    if batch_count >= args.batch_size:
                        conn.commit()
                        script.logger.info(f"  Committed batch of {batch_count} updates")
                        batch_count = 0

                stats['updated'] += 1

            # Final commit
            if not args.dry_run and batch_count > 0:
                conn.commit()
                script.logger.info(f"  Committed final batch of {batch_count} updates")

    # Print summary
    script.print_summary(stats)

    return True


if __name__ == "__main__":
    run_script(main)
