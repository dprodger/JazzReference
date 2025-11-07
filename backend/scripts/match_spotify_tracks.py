#!/usr/bin/env python3
"""
Spotify Track Matcher - Command Line Interface
Matches Spotify tracks to existing recordings and updates the database

This script provides a command-line interface to the SpotifyMatcher module.
It handles argument parsing, logging configuration, and result presentation.
"""

import sys
import argparse
import logging
from pathlib import Path

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from spotify_utils import SpotifyMatcher
from db_utils import normalize_apostrophes
from dotenv import load_dotenv

load_dotenv()

# Configure logging for CLI
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('log/spotify_match.log')
    ]
)
logger = logging.getLogger(__name__)


def print_header(dry_run: bool, strict_mode: bool, min_artist: int, min_album: int, min_track: int):
    """Print CLI header"""
    logger.info("="*80)
    logger.info("Spotify Track Matching")
    logger.info("="*80)
    
    if dry_run:
        logger.info("*** DRY RUN MODE - No database changes will be made ***")
        logger.info("")
    
    if strict_mode:
        logger.info("*** STRICT VALIDATION MODE - Using stricter matching thresholds ***")
        logger.info(f"    Minimum artist similarity: {min_artist}%")
        logger.info(f"    Minimum album similarity: {min_album}%")
        logger.info(f"    Minimum track similarity: {min_track}%")
        logger.info("")


def print_summary(result: dict):
    """
    Print a CLI-friendly summary of the matching operation
    
    Args:
        result: Result dict from SpotifyMatcher.match_recordings()
    """
    logger.info("")
    logger.info("="*80)
    logger.info("MATCHING SUMMARY")
    logger.info("="*80)
    
    if result['success']:
        stats = result['stats']
        
        logger.info(f"Recordings processed:       {stats['recordings_processed']}")
        logger.info(f"Recordings already had URL: {stats['recordings_skipped']}")
        logger.info(f"Spotify matches found:      {stats['recordings_with_spotify']}")
        logger.info(f"Recordings updated:         {stats['recordings_updated']}")
        logger.info(f"No match found:             {stats['recordings_no_match']}")
        logger.info(f"Errors:                     {stats['errors']}")
    else:
        logger.error(f"Matching failed: {result.get('error', 'Unknown error')}")
        if 'song' in result:
            logger.info(f"Song: {result['song']['title']}")
    
    logger.info("="*80)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Match Spotify tracks to existing recordings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
  
  # Filter to only recordings by a specific artist
  python match_spotify_tracks.py --name "Autumn Leaves" --artist "Bill Evans"
  
  # Use looser validation thresholds (not recommended)
  python match_spotify_tracks.py --name "Blue in Green" --no-strict
  
  # Dry run to see what would be matched
  python match_spotify_tracks.py --name "Blue in Green" --dry-run
  
  # Enable debug logging to see validation details
  python match_spotify_tracks.py --name "Autumn Leaves" --debug
        """
    )
    
    # Song selection arguments
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--name',
        help='Song name'
    )
    group.add_argument(
        '--id',
        help='Song database ID'
    )
    
    parser.add_argument(
        '--artist',
        help='Filter to recordings by this artist'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be matched without making changes'
    )
    
    parser.add_argument(
        '--no-strict',
        action='store_true',
        help='Use looser validation thresholds (not recommended - may cause false matches)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create log directory
    Path('log').mkdir(exist_ok=True)
    
    # Create matcher with CLI logger
    strict_mode = not args.no_strict
    matcher = SpotifyMatcher(
        dry_run=args.dry_run,
        artist_filter=args.artist,
        strict_mode=strict_mode,
        logger=logger
    )
    
    # Print header
    print_header(
        args.dry_run,
        strict_mode,
        matcher.min_artist_similarity,
        matcher.min_album_similarity,
        matcher.min_track_similarity
    )
    
    # Determine song identifier
    song_identifier = normalize_apostrophes(args.name) if args.name else args.id
    
    try:
        # Run the matching
        result = matcher.match_recordings(song_identifier)
        
        # Print summary
        print_summary(result)
        
        # Exit with appropriate code
        sys.exit(0 if result['success'] else 1)
        
    except KeyboardInterrupt:
        logger.info("\nMatching cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()