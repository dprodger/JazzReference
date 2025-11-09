#!/usr/bin/env python3
"""
MusicBrainz Composer import
Identifies the composer via musicbrainz for a song, and updates if new

It handles argument parsing, logging configuration, and result presentation.
"""

import sys
import argparse
import logging
from pathlib import Path

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the core business logic
from mb_utils import update_song_composer
from db_utils import find_song_by_name_or_id

# Configure logging for CLI
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('log/mb_import.log')
    ]
)
logger = logging.getLogger(__name__)


def print_header(dry_run: bool):
    """Print CLI header"""
    logger.info("="*80)
    logger.info("MusicBrainz Composer Import")
    logger.info("="*80)
    if dry_run:
        logger.info("*** DRY RUN MODE - No database changes will be made ***")
    logger.info("")

# TODO
"""
def print_summary(result: dict):
    /"/""
    Print a CLI-friendly summary of the import operation
    
    Args:
        result: Result dict from MBReleaseImporter.import_releases()
    /"/""
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
        logger.info(f"Recordings found:    {stats['releases_found'] + stats['releases_imported']}")
        logger.info(f"Recordings imported: {stats['releases_imported']}")
        logger.info(f"Errors:              {stats['errors']}")
    else:
        logger.error(f"Import failed: {result.get('error', 'Unknown error')}")
        if 'song' in result:
            logger.info(f"Song: {result['song']['title']}")
    
    logger.info("="*80)
"""


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Import composer for a jazz song',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import by song name
  python import_composers.py --name "Take Five"
  
  # Import by song ID
  python import_composers.py --id a1b2c3d4-e5f6-7890-abcd-ef1234567890
  
  # Dry run to see what would be imported
  python import_composers.py --name "Blue in Green" --dry-run
  
  # Enable debug logging
  python import_composers.py --name "Autumn Leaves" --debug
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
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create log directory
    Path('log').mkdir(exist_ok=True)
    
    # Print header
    print_header(args.dry_run)
    
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
        result = update_song_composer(song_identifier)
        logger.info(f"\nUpdate_song_composer returned {result}")
        # Print summary
# TODO
#        print_summary(result)
        
        # Exit with appropriate code
        sys.exit(0 if result else 1)
        
    except KeyboardInterrupt:
        logger.info("\nImport cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()