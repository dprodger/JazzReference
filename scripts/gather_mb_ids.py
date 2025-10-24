#!/usr/bin/env python3
"""
MusicBrainz ID Gatherer
Finds and adds MusicBrainz Work IDs for songs that don't have them
"""

import sys
import json
import time
import argparse
import logging
from datetime import datetime
import requests

# Import shared database and MusicBrainz utilities
from db_utils import get_db_connection
from mb_utils import MusicBrainzSearcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('log/mb_gather.log')
    ]
)
logger = logging.getLogger(__name__)


class MusicBrainzGatherer:
    def __init__(self, dry_run=False, song_name=None, song_id=None):
        self.dry_run = dry_run
        self.song_name = song_name
        self.song_id = song_id
        self.mb_searcher = MusicBrainzSearcher()
        self.stats = {
            'songs_processed': 0,
            'songs_with_mb_id': 0,
            'mb_ids_found': 0,
            'songs_updated': 0,
            'no_match_found': 0,
            'errors': 0
        }
    
    def get_songs_without_mb_id(self):
        """Get all songs that don't have a MusicBrainz ID, optionally filtered by name or ID"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if self.song_id:
                    # Filter by specific song ID
                    cur.execute("""
                        SELECT id, title, composer
                        FROM songs
                        WHERE id = %s AND musicbrainz_id IS NULL
                    """, (self.song_id,))
                elif self.song_name:
                    # Filter by song name (case-insensitive partial match)
                    cur.execute("""
                        SELECT id, title, composer
                        FROM songs
                        WHERE title ILIKE %s AND musicbrainz_id IS NULL
                        ORDER BY title
                    """, (f'%{self.song_name}%',))
                else:
                    # Get all songs without MB IDs
                    cur.execute("""
                        SELECT id, title, composer
                        FROM songs
                        WHERE musicbrainz_id IS NULL
                        ORDER BY title
                    """)
                return cur.fetchall()
    
    def update_song_mb_id(self, conn, song_id, mb_id):
        """Update song with MusicBrainz ID"""
        if self.dry_run:
            logger.info(f"    [DRY RUN] Would update with MusicBrainz ID: {mb_id}")
            return
        
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE songs
                SET musicbrainz_id = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (mb_id, song_id))
            
            conn.commit()
            logger.info(f"    ✓ Updated with MusicBrainz ID: {mb_id}")
            self.stats['songs_updated'] += 1
    
    def gather_mb_ids(self):
        """Main method to gather MusicBrainz IDs for songs"""
        logger.info("="*80)
        logger.info("MusicBrainz ID Gathering")
        logger.info("="*80)
        
        if self.dry_run:
            logger.info("*** DRY RUN MODE - No database changes will be made ***")
            logger.info("")
        
        # Show any active filters
        if self.song_name:
            logger.info(f"Filter: Processing only songs matching '{self.song_name}'")
            logger.info("")
        elif self.song_id:
            logger.info(f"Filter: Processing only song with ID '{self.song_id}'")
            logger.info("")
        
        # Get songs without MB IDs
        songs = self.get_songs_without_mb_id()
        
        if not songs:
            logger.info("All songs already have MusicBrainz IDs!")
            return True
        
        logger.info(f"Found {len(songs)} songs without MusicBrainz IDs")
        logger.info("")
        
        # Process each song
        with get_db_connection() as conn:
            for i, song in enumerate(songs, 1):
                self.stats['songs_processed'] += 1
                
                logger.info(f"[{i}/{len(songs)}] {song['title']}")
                if song['composer']:
                    logger.info(f"    Composer: {song['composer']}")
                
                # Search MusicBrainz using shared searcher
                mb_id = self.mb_searcher.search_musicbrainz_work(
                    song['title'],
                    song['composer']
                )
                
                if mb_id:
                    self.stats['mb_ids_found'] += 1
                    self.update_song_mb_id(conn, song['id'], mb_id)
                else:
                    logger.info(f"    ✗ No MusicBrainz match found")
                    self.stats['no_match_found'] += 1
                
                logger.info("")
        
        # Print summary
        logger.info("="*80)
        logger.info("GATHERING SUMMARY")
        logger.info("="*80)
        logger.info(f"Songs processed:           {self.stats['songs_processed']}")
        logger.info(f"MusicBrainz IDs found:     {self.stats['mb_ids_found']}")
        logger.info(f"Songs updated:             {self.stats['songs_updated']}")
        logger.info(f"No match found:            {self.stats['no_match_found']}")
        logger.info(f"Errors:                    {self.stats['errors']}")
        logger.info("="*80)
        
        return True


def main():
    parser = argparse.ArgumentParser(
        description='Gather MusicBrainz IDs for songs without them',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script searches for MusicBrainz Work IDs for songs in the database that don't
have them. It uses the MusicBrainz API to search by song title and composer.

Examples:
  # Run in normal mode (process all songs)
  python gather_mb_ids.py
  
  # Process a specific song by name
  python gather_mb_ids.py --name "Take Five"
  
  # Process a specific song by ID
  python gather_mb_ids.py --id a1b2c3d4-e5f6-7890-abcd-ef1234567890
  
  # Dry run to see what would be found
  python gather_mb_ids.py --dry-run
  
  # Dry run for a specific song
  python gather_mb_ids.py --name "Blue in Green" --dry-run
  
  # Enable debug logging
  python gather_mb_ids.py --debug

Notes:
  - MusicBrainz API requires 1 second between requests (enforced by rate limiting)
  - The script looks for exact or very close title matches
  - Results are logged to mb_gather.log
        """
    )
    
    # Song selection arguments (optional)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--name',
        help='Process only the song with this name (partial match)'
    )
    group.add_argument(
        '--id',
        help='Process only the song with this ID'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be found without making changes'
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
    
    # Create gatherer and run
    gatherer = MusicBrainzGatherer(
        dry_run=args.dry_run,
        song_name=args.name if hasattr(args, 'name') and args.name else None,
        song_id=args.id if hasattr(args, 'id') and args.id else None
    )
    
    try:
        success = gatherer.gather_mb_ids()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nGathering cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()