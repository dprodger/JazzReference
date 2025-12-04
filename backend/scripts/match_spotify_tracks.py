#!/usr/bin/env python3
"""
Spotify Release Matcher - Command Line Interface
Matches Spotify albums to existing releases and updates the database
"""

from script_base import ScriptBase, run_script
from spotify_utils import SpotifyMatcher
from dotenv import load_dotenv

load_dotenv()


def main() -> bool:
    # Set up script with arguments
    script = ScriptBase(
        name="match_spotify_tracks",
        description="Match Spotify albums to existing releases",
        epilog="""
Setup:
  1. Get Spotify API credentials from https://developer.spotify.com/dashboard
  2. Set environment variables:
     export SPOTIFY_CLIENT_ID='your_client_id'
     export SPOTIFY_CLIENT_SECRET='your_client_secret'

Examples:
  # Match by song name with strict validation (recommended)
  python match_spotify_tracks.py --name "Take Five"

  # Match by song ID
  python match_spotify_tracks.py --id a1b2c3d4-e5f6-7890-abcd-ef1234567890

  # Filter to only releases by a specific artist
  python match_spotify_tracks.py --name "Autumn Leaves" --artist "Bill Evans"

  # Force refresh from API (bypass cache)
  python match_spotify_tracks.py --name "Blue in Green" --force-refresh

  # Use looser validation thresholds (not recommended)
  python match_spotify_tracks.py --name "Blue in Green" --no-strict

  # Dry run to see what would be matched
  python match_spotify_tracks.py --name "Blue in Green" --dry-run

  # Enable debug logging to see validation details and cache operations
  python match_spotify_tracks.py --name "Autumn Leaves" --debug
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

    # Parse arguments
    args = script.parse_args()

    # Create matcher
    strict_mode = not args.no_strict
    matcher = SpotifyMatcher(
        dry_run=args.dry_run,
        artist_filter=args.artist,
        strict_mode=strict_mode,
        logger=script.logger,
        cache_days=args.cache_days,
        force_refresh=args.force_refresh
    )

    # Print header with modes
    modes = {
        "DRY RUN": args.dry_run,
        "FORCE REFRESH": args.force_refresh,
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
            "Releases already had URL": stats['releases_skipped'],
            "Spotify matches found": stats['releases_with_spotify'],
            "Releases updated": stats['releases_updated'],
            "No match found": stats['releases_no_match'],
            "Tracks matched": stats['tracks_matched'],
            "Tracks already matched": stats['tracks_skipped'],
            "Tracks no match": stats['tracks_no_match'],
            "Errors": stats['errors'],
            "Cache hits": stats['cache_hits'],
            "API calls": stats['api_calls'],
        }, title="MATCHING SUMMARY")
    else:
        script.logger.error(f"Matching failed: {result.get('error', 'Unknown error')}")

    return result['success']


if __name__ == "__main__":
    run_script(main)
