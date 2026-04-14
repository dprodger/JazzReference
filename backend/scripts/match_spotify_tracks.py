#!/usr/bin/env python3
"""
Spotify Release Matcher - Command Line Interface
Matches Spotify albums to existing releases and updates the database
"""

from script_base import ScriptBase, run_script
from integrations.spotify.utils import SpotifyMatcher
from integrations.spotify.db import get_songs_with_duration_mismatches
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

  # Resume from a specific release number (after interrupted run)
  python match_spotify_tracks.py --name "Take Five" --rematch-all --start-from 2972
        """
    )

    # Add arguments (song args optional — not needed for --duration-mismatches across all songs)
    script.add_song_args(required=False)
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
        '--rematch-tracks',
        action='store_true',
        help='Re-run track matching for releases that have album IDs but are missing track IDs'
    )

    script.parser.add_argument(
        '--rematch-all',
        action='store_true',
        help='Full re-match from scratch: ignore cache, re-match albums and all tracks regardless of existing IDs'
    )

    script.parser.add_argument(
        '--duration-mismatches',
        type=int,
        nargs='?',
        const=60,
        default=None,
        metavar='SECONDS',
        help='Only process releases with duration mismatches above this threshold (default: 60s). Implies --rematch-all.'
    )

    script.parser.add_argument(
        '--start-from',
        type=int,
        default=1,
        metavar='N',
        help='Resume from release number N (1-indexed). Use to continue after an interrupted run.'
    )

    script.parser.add_argument(
        '--audit-album-context',
        action='store_true',
        help='Evaluate album-context rescue for duration-rejected tracks and log results to album_context_audit.csv (no behavior change)'
    )

    script.parser.add_argument(
        '--album-context',
        action='store_true',
        help='Enable album-context rescue: accept duration-rejected tracks when the full MB/Spotify tracklists match well'
    )

    # Parse arguments
    args = script.parse_args()

    # Create matcher
    strict_mode = not args.no_strict

    # Convert duration-mismatches from seconds to milliseconds
    duration_mismatch_threshold = None
    if args.duration_mismatches is not None:
        duration_mismatch_threshold = args.duration_mismatches * 1000

    # --rematch-all and --duration-mismatches imply force_refresh, rematch, and rematch_tracks
    force_refresh = args.force_refresh or args.rematch_all or duration_mismatch_threshold is not None
    rematch = args.rematch_all
    rematch_tracks = args.rematch_tracks or args.rematch_all
    rematch_all = args.rematch_all

    # Album context mode
    album_context = None
    if args.album_context:
        album_context = 'rescue'
    elif args.audit_album_context:
        album_context = 'audit'

    matcher = SpotifyMatcher(
        dry_run=args.dry_run,
        artist_filter=args.artist,
        strict_mode=strict_mode,
        logger=script.logger,
        cache_days=args.cache_days,
        force_refresh=force_refresh,
        rematch=rematch,
        rematch_tracks=rematch_tracks,
        rematch_all=rematch_all,
        duration_mismatch_threshold=duration_mismatch_threshold,
        album_context=album_context,
    )

    # Print header with modes
    modes = {
        "DRY RUN": args.dry_run,
        "FORCE REFRESH": force_refresh,
        "REMATCH ALL": args.rematch_all or duration_mismatch_threshold is not None,
        "REMATCH TRACKS": rematch_tracks and not args.rematch_all and duration_mismatch_threshold is None,
        f"DURATION MISMATCHES (>{args.duration_mismatches}s)": duration_mismatch_threshold is not None,
        "ALBUM CONTEXT AUDIT": album_context == 'audit',
        "ALBUM CONTEXT RESCUE": album_context == 'rescue',
        f"START FROM #{args.start_from}": args.start_from > 1,
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

    if not song_identifier and duration_mismatch_threshold is not None:
        # Process all songs with duration mismatches
        songs = get_songs_with_duration_mismatches(duration_mismatch_threshold)
        script.logger.info(f"Found {len(songs)} songs with duration mismatches")
        script.logger.info("")
        for i, song in enumerate(songs, 1):
            script.logger.info(f"{'='*60}")
            script.logger.info(f"[{i}/{len(songs)}] {song['title']}")
            script.logger.info(f"{'='*60}")
            matcher.match_releases(str(song['id']), start_from=args.start_from)
        # Stats accumulate on the matcher instance across all songs
        result = {'success': True, 'stats': matcher.stats}
    elif not song_identifier:
        script.logger.error("Either --name/--id or --duration-mismatches is required")
        return False
    else:
        result = matcher.match_releases(song_identifier, start_from=args.start_from)

    # Print summary
    if result['success']:
        stats = result['stats']
        summary = {
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
        }
        # Only show rematch-specific stats if there were any
        if stats.get('tracks_had_previous', 0) > 0:
            summary["Tracks had previous match"] = stats['tracks_had_previous']
        if stats.get('releases_cleared', 0) > 0:
            summary["Stale matches cleared"] = stats['releases_cleared']
        if stats.get('tracks_album_context_rescued', 0) > 0:
            summary["Album context rescued"] = stats['tracks_album_context_rescued']
        if stats.get('tracks_album_context_would_rescue', 0) > 0:
            summary["Album context would rescue"] = stats['tracks_album_context_would_rescue']
        script.print_summary(summary, title="MATCHING SUMMARY")
    else:
        script.logger.error(f"Matching failed: {result.get('error', 'Unknown error')}")

    return result['success']


if __name__ == "__main__":
    run_script(main)
