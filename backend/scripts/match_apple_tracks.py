#!/usr/bin/env python3
"""
Apple Music Release Matcher - Command Line Interface

Matches Apple Music albums to existing releases and updates the database
using the normalized streaming_links tables.

Unlike Spotify, Apple Music (iTunes) API requires no authentication -
it's a free public API.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from script_base import ScriptBase, run_script
from apple_music_matcher import AppleMusicMatcher


def main() -> bool:
    # Set up script with arguments
    script = ScriptBase(
        name="match_apple_tracks",
        description="Match Apple Music albums to existing releases",
        epilog="""
Apple Music API:
  The iTunes Search API is free and requires no authentication.
  Rate limiting is handled automatically with exponential backoff.

Examples:
  # Match by song name with strict validation (recommended)
  python match_apple_tracks.py --name "Take Five"

  # Match by song ID
  python match_apple_tracks.py --id a1b2c3d4-e5f6-7890-abcd-ef1234567890

  # Filter to only releases by a specific artist
  python match_apple_tracks.py --name "Autumn Leaves" --artist "Bill Evans"

  # Force refresh from API (bypass cache)
  python match_apple_tracks.py --name "Blue in Green" --force-refresh

  # Re-match releases that already have Apple Music links
  python match_apple_tracks.py --name "Blue in Green" --rematch

  # Use looser validation thresholds (not recommended)
  python match_apple_tracks.py --name "Blue in Green" --no-strict

  # Dry run to see what would be matched
  python match_apple_tracks.py --name "Blue in Green" --dry-run

  # Enable debug logging to see validation details and cache operations
  python match_apple_tracks.py --name "Autumn Leaves" --debug
        """
    )

    # Add arguments
    script.add_song_args()
    script.add_common_args()

    script.parser.add_argument(
        '--artist',
        help='Filter to releases by this artist'
    )

    script.parser.add_argument(
        '--no-strict',
        action='store_true',
        help='Use looser validation thresholds (not recommended - may cause false matches)'
    )

    script.parser.add_argument(
        '--cache-days',
        type=int,
        default=30,
        help='Number of days before cache expires (default: 30)'
    )

    script.parser.add_argument(
        '--rematch',
        action='store_true',
        help='Re-evaluate releases that already have Apple Music links'
    )

    script.parser.add_argument(
        '--rate-limit-delay',
        type=float,
        default=0.5,
        help='Delay between API calls in seconds (default: 0.5). Increase if hitting rate limits.'
    )

    script.parser.add_argument(
        '--slow',
        action='store_true',
        help='Use very conservative rate limiting (2s between requests). Recommended for batch processing.'
    )

    script.parser.add_argument(
        '--no-local-catalog',
        action='store_true',
        help='Skip local catalog and use iTunes API directly (slower, may hit rate limits)'
    )

    script.parser.add_argument(
        '--local-only',
        action='store_true',
        help='Only use local catalog, never fall back to iTunes API (avoids rate limits entirely)'
    )

    # Parse arguments
    args = script.parse_args()

    # Create matcher
    strict_mode = not args.no_strict
    # Use 2 second delay in slow mode
    rate_delay = 2.0 if args.slow else args.rate_limit_delay
    use_local_catalog = not args.no_local_catalog
    local_catalog_only = args.local_only
    matcher = AppleMusicMatcher(
        dry_run=args.dry_run,
        artist_filter=args.artist,
        strict_mode=strict_mode,
        logger=script.logger,
        cache_days=args.cache_days,
        force_refresh=args.force_refresh,
        rematch=args.rematch,
        rate_limit_delay=rate_delay,
        use_local_catalog=use_local_catalog,
        local_catalog_only=local_catalog_only,
    )

    # Print header with modes
    modes = {
        "DRY RUN": args.dry_run,
        "FORCE REFRESH": args.force_refresh,
        "REMATCH": args.rematch,
        "SLOW MODE": args.slow,
        "LOCAL CATALOG": use_local_catalog,
        "LOCAL ONLY": local_catalog_only,
    }
    script.print_header(modes)

    if strict_mode:
        script.logger.info("STRICT VALIDATION MODE")
        script.logger.info(f"  Minimum artist similarity: {matcher.min_artist_similarity}%")
        script.logger.info(f"  Minimum album similarity: {matcher.min_album_similarity}%")
        script.logger.info(f"  Minimum track similarity: {matcher.min_track_similarity}%")
        script.logger.info("")

    # Get song identifier and run matcher
    song_identifier = args.name or args.id
    result = matcher.match_releases(song_identifier)

    # Print summary
    if result['success']:
        stats = result['stats']
        script.print_summary({
            "Releases processed": stats['releases_processed'],
            "Already had Apple Music": stats['releases_with_apple_music'],
            "Releases matched": stats['releases_matched'],
            "Releases skipped": stats['releases_skipped'],
            "No match found": stats['releases_no_match'],
            "Tracks matched": stats['tracks_matched'],
            "Tracks no match": stats['tracks_no_match'],
            "Artwork added": stats['artwork_added'],
            "Errors": stats['errors'],
            "Local catalog hits": stats['local_catalog_hits'],
            "Cache hits": stats['cache_hits'],
            "API calls": stats['api_calls'],
        }, title="APPLE MUSIC MATCHING SUMMARY")
    else:
        script.logger.error(f"Matching failed: {result.get('message', 'Unknown error')}")

    return result['success']


if __name__ == "__main__":
    run_script(main)
