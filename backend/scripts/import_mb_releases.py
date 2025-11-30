#!/usr/bin/env python3
"""
MusicBrainz Release Importer - Command Line Interface

Fetches recordings and releases for songs with MusicBrainz IDs and imports them 
into the database. Creates recordings, releases, and links performers to releases.

This script provides a command-line interface to the MBReleaseImporter module.
It handles argument parsing, logging configuration, and result presentation.
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the core business logic
from mb_release_importer import MBReleaseImporter
from db_utils import find_song_by_name_or_id

# Configure logging
LOG_DIR = Path(__file__).parent / 'log'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / 'import_mb_releases.log')
    ]
)
logger = logging.getLogger(__name__)


def print_header(dry_run: bool):
    """Print CLI header"""
    logger.info("="*80)
    logger.info("MusicBrainz Recording & Release Import")
    logger.info("="*80)
    if dry_run:
        logger.info("*** DRY RUN MODE - No database changes will be made ***")
    logger.info("")


def print_summary(result: dict):
    """
    Print a CLI-friendly summary of the import operation
    
    Args:
        result: Result dict from MBReleaseImporter.import_releases()
    """
    logger.info("")
    logger.info("="*80)
    logger.info("IMPORT SUMMARY")
    logger.info("="*80)
    
    if result['success']:
        song = result['song']
        stats = result['stats']
        
        logger.info(f"Song: {song['title']}")
        logger.info(f"Composer: {song['composer']}")
        logger.info("")
        logger.info("Recordings:")
        logger.info(f"  Found:     {stats['recordings_found']}")
        logger.info(f"  Created:   {stats['recordings_created']}")
        logger.info(f"  Existing:  {stats['recordings_existing']}")
        logger.info("")
        logger.info("Releases:")
        logger.info(f"  Found (new):    {stats['releases_found']}")
        logger.info(f"  Created:        {stats['releases_created']}")
        logger.info(f"  Already exist:  {stats['releases_existing']}")
        if stats.get('releases_skipped_api', 0) > 0:
            logger.info(f"  API calls skipped: {stats['releases_skipped_api']}")
        logger.info("")
        logger.info(f"Links created:      {stats['links_created']}")
        logger.info(f"Performers linked:  {stats['performers_linked']}")
        logger.info(f"Errors:             {stats['errors']}")
    else:
        logger.error(f"Import failed: {result.get('error', 'Unknown error')}")
        if 'song' in result:
            logger.info(f"Song: {result['song']['title']}")
    
    logger.info("="*80)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Import MusicBrainz recordings and releases for a jazz song',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import by song name
  python import_mb_releases.py --name "Take Five"
  
  # Import by song ID
  python import_mb_releases.py --id a1b2c3d4-e5f6-7890-abcd-ef1234567890
  
  # Dry run to see what would be imported
  python import_mb_releases.py --name "Blue in Green" --dry-run
  
  # Enable debug logging
  python import_mb_releases.py --name "Autumn Leaves" --debug
  
  # Limit recordings to process
  python import_mb_releases.py --name "Body and Soul" --limit 10

What this script does:
  1. Finds the song by name or ID
  2. Fetches recordings from MusicBrainz (via the song's MusicBrainz Work ID)
  3. For each recording:
     - Creates the recording if it doesn't exist
     - Fetches all releases containing that recording
     - Creates releases if they don't exist
     - Links recordings to releases
     - Associates performers with releases

Performance optimizations:
  - Checks if releases exist BEFORE making API calls
  - Uses single database connection per recording (not per release)
  - Skips API calls for releases already in database
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
        '--dry-run',
        action='store_true',
        help='Show what would be imported without making changes'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Maximum number of recordings to fetch (default: 100)'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Print header
    print_header(args.dry_run)
    
    # Create importer with CLI logger
    importer = MBReleaseImporter(dry_run=args.dry_run, logger=logger)
    
    # Retrieve song from database
    try:
        song = find_song_by_name_or_id(name=args.name, song_id=args.id)
        if song is None:
            identifier = args.name if args.name else args.id
            logger.error(f"Song not found: {identifier}")
            sys.exit(1)
        
        song_identifier = song['id']
        logger.info(f"Found song: {song['title']} (ID: {song_identifier})")
        
    except ValueError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    
    try:
        # Run the import
        result = importer.import_releases(song_identifier, limit=args.limit)
        
        # Print summary
        print_summary(result)
        
        # Exit with appropriate code
        if result['success']:
            logger.info("✓ Import completed successfully")
            sys.exit(0)
        else:
            logger.error("✗ Import failed")
            sys.exit(1)
        
    except KeyboardInterrupt:
        logger.info("\nImport cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()