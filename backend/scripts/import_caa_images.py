#!/usr/bin/env python3
"""
Cover Art Archive Image Importer - Command Line Interface

Fetches cover art from the Cover Art Archive (CAA) for releases and imports
them into the release_imagery table.

This script provides a command-line interface to the CAAImageImporter module.
It handles argument parsing, logging configuration, and result presentation.

Usage:
  # Import images for all releases of a song
  python import_caa_images.py --name "Take Five"
  
  # Import images for all unchecked releases
  python import_caa_images.py --all
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the core business logic
from caa_release_importer import CAAImageImporter

# Configure logging
LOG_DIR = Path(__file__).parent / 'log'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / 'import_caa_images.log')
    ]
)
logger = logging.getLogger(__name__)


def print_header(dry_run: bool, force_refresh: bool = False, batch_mode: bool = False):
    """Print CLI header."""
    logger.info("="*80)
    logger.info("Cover Art Archive Image Import")
    logger.info("="*80)
    if dry_run:
        logger.info("*** DRY RUN MODE - No database changes will be made ***")
    if force_refresh:
        logger.info("*** FORCE REFRESH MODE - Bypassing CAA cache ***")
    if batch_mode:
        logger.info("*** BATCH MODE - Processing all unchecked releases ***")
    logger.info("")


def print_summary(result: dict, batch_mode: bool = False):
    """
    Print a CLI-friendly summary of the import operation.
    
    Args:
        result: Result dict from CAAImageImporter
        batch_mode: Whether this was a batch import
    """
    logger.info("")
    logger.info("="*80)
    logger.info("IMPORT SUMMARY")
    logger.info("="*80)
    
    if result['success']:
        stats = result['stats']
        
        if not batch_mode and 'song' in result:
            song = result['song']
            logger.info(f"Song: {song['title']}")
            if song.get('composer'):
                logger.info(f"Composer: {song['composer']}")
            logger.info("")
        
        if result.get('message'):
            logger.info(f"Note: {result['message']}")
            logger.info("")
        
        logger.info("Releases:")
        logger.info(f"  Processed:     {stats['releases_processed']}")
        logger.info(f"  With art:      {stats['releases_with_art']}")
        logger.info(f"  No art:        {stats['releases_no_art']}")
        logger.info("")
        logger.info("Images:")
        logger.info(f"  Created:       {stats['images_created']}")
        logger.info(f"  Updated:       {stats['images_updated']}")
        logger.info(f"  Already exist: {stats['images_existing']}")
        logger.info("")
        logger.info("API Performance:")
        logger.info(f"  API calls:     {stats['api_calls']}")
        logger.info(f"  Cache hits:    {stats['cache_hits']}")
        logger.info("")
        logger.info(f"Errors:          {stats['errors']}")
    else:
        logger.error(f"Import failed: {result.get('error', 'Unknown error')}")
    
    logger.info("="*80)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Import cover art from Cover Art Archive for jazz releases',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import cover art for all releases of a song (by name)
  python import_caa_images.py --name "Take Five"
  
  # Import cover art for all releases of a song (by ID)
  python import_caa_images.py --id a1b2c3d4-e5f6-7890-abcd-ef1234567890
  
  # Import cover art for ALL unchecked releases (batch mode)
  python import_caa_images.py --all
  
  # Dry run to see what would be imported
  python import_caa_images.py --name "Blue in Green" --dry-run
  
  # Enable debug logging
  python import_caa_images.py --name "Autumn Leaves" --debug
  
  # Force refresh from CAA API (bypass cache)
  python import_caa_images.py --name "Autumn Leaves" --force-refresh
  
  # Limit number of releases to process
  python import_caa_images.py --all --limit 50

What this script does:
  1. Finds releases for a song (or all unchecked releases in batch mode)
  2. Queries the Cover Art Archive for each release
  3. Downloads image metadata (URLs for different sizes)
  4. Creates release_imagery records in the database
  5. Marks releases as checked (cover_art_checked_at)

Notes:
  - By default, releases that have already been checked are SKIPPED
  - Use --force-refresh to re-check already processed releases
  - The CAA API has no rate limiting, but we use conservative delays
  - Results are cached locally to avoid repeated API calls
  - Only Front and Back cover types are imported
  - Releases without MusicBrainz IDs are skipped
        """
    )
    
    # Song selection arguments (mutually exclusive with --all)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--name',
        help='Song name to find releases for'
    )
    group.add_argument(
        '--id',
        help='Song database ID (UUID)'
    )
    group.add_argument(
        '--all',
        action='store_true',
        help='Process all releases that have not been checked for cover art'
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
        default=500,
        help='Maximum number of releases to process (default: 500)'
    )
    
    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Force refresh from CAA API (bypass cache) and re-check already processed releases'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine mode
    batch_mode = args.all
    
    # Print header
    print_header(args.dry_run, args.force_refresh, batch_mode)
    
    # Create importer with CLI logger
    importer = CAAImageImporter(
        dry_run=args.dry_run,
        force_refresh=args.force_refresh,
        logger=logger
    )
    
    try:
        if batch_mode:
            # Process all unchecked releases
            logger.info(f"Processing unchecked releases (limit: {args.limit})...")
            result = importer.import_all_unchecked(limit=args.limit)
        else:
            # Process releases for a specific song
            song_identifier = args.name if args.name else args.id
            logger.info(f"Finding song: {song_identifier}")
            result = importer.import_for_song(song_identifier, limit=args.limit)
        
        # Print summary
        print_summary(result, batch_mode)
        
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