#!/usr/bin/env python3
"""
One-Time Wikipedia URL Population Script
Populates Wikipedia URLs for songs that have MusicBrainz IDs but no Wikipedia URL

This is a one-time batch script to populate existing songs with Wikipedia URLs
from MusicBrainz data. It processes all songs that have a musicbrainz_id but
no wikipedia_url, using the cached MusicBrainz data where possible.
"""

import sys
import argparse
import logging
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_utils import get_db_connection
from mb_utils import MusicBrainzSearcher, update_song_wikipedia_url

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('log/one_time_song_wiki.log')
    ]
)
logger = logging.getLogger(__name__)


class SongWikipediaPopulator:
    """Populates Wikipedia URLs for songs from MusicBrainz data"""
    
    def __init__(self, dry_run=False, limit=None, force_refresh=False):
        """
        Initialize Wikipedia URL populator
        
        Args:
            dry_run: If True, show what would be done without making changes
            limit: Maximum number of songs to process (None for all)
            force_refresh: If True, ignore cache and fetch fresh data from MusicBrainz
        """
        self.dry_run = dry_run
        self.limit = limit
        
        # Create shared MusicBrainzSearcher to benefit from caching
        self.mb_searcher = MusicBrainzSearcher(force_refresh=force_refresh)
        
        self.stats = {
            'songs_processed': 0,
            'urls_added': 0,
            'urls_already_set': 0,
            'no_url_found': 0,
            'errors': 0
        }
    
    def get_songs_needing_wikipedia(self):
        """
        Get songs that have MusicBrainz ID but no Wikipedia URL
        
        Returns:
            List of song dicts with id, title, musicbrainz_id
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT id, title, musicbrainz_id
                    FROM songs
                    WHERE musicbrainz_id IS NOT NULL
                      AND wikipedia_url IS NULL
                    ORDER BY title
                """
                
                if self.limit:
                    query += f" LIMIT {self.limit}"
                
                cur.execute(query)
                return cur.fetchall()
    
    def process_song(self, song):
        """
        Process a single song to add Wikipedia URL
        
        Args:
            song: Song dict with id, title, musicbrainz_id
            
        Returns:
            True if URL was added, False otherwise
        """
        try:
            song_id = song['id']
            title = song['title']
            
            logger.info(f"Processing: {title}")
            
            # Use the update function from mb_utils
            # Pass the shared MusicBrainzSearcher to leverage cache
            updated = update_song_wikipedia_url(
                str(song_id), 
                self.mb_searcher, 
                dry_run=self.dry_run
            )
            
            if updated:
                self.stats['urls_added'] += 1
                return True
            else:
                # Check if it already had a URL or just no URL found
                # The function logs this, so we just track stats
                self.stats['no_url_found'] += 1
                return False
            
        except Exception as e:
            logger.error(f"Error processing {song['title']}: {e}", exc_info=True)
            self.stats['errors'] += 1
            return False
    
    def run(self):
        """Main processing method"""
        logger.info("="*80)
        logger.info("ONE-TIME WIKIPEDIA URL POPULATION")
        logger.info("="*80)
        
        if self.dry_run:
            logger.info("*** DRY RUN MODE - No database changes will be made ***")
            logger.info("")
        
        if self.mb_searcher.force_refresh:
            logger.info("*** FORCE REFRESH MODE - Ignoring cache and fetching fresh data ***")
            logger.info("")
        
        # Get songs to process
        songs = self.get_songs_needing_wikipedia()
        
        if not songs:
            logger.info("No songs need Wikipedia URL updates!")
            return True
        
        logger.info(f"Found {len(songs)} songs to process")
        if self.limit:
            logger.info(f"Limited to {self.limit} songs")
        logger.info("")
        
        # Process each song
        for song in songs:
            self.stats['songs_processed'] += 1
            
            self.process_song(song)
            
            # Add spacing between songs for readability
            if self.stats['songs_processed'] % 10 == 0:
                logger.info(f"Progress: {self.stats['songs_processed']}/{len(songs)} songs processed")
                logger.info("")
        
        # Print summary
        self.print_summary()
        
        return True
    
    def print_summary(self):
        """Print processing summary"""
        logger.info("")
        logger.info("="*80)
        logger.info("PROCESSING SUMMARY")
        logger.info("="*80)
        logger.info(f"Songs processed:          {self.stats['songs_processed']}")
        logger.info(f"Wikipedia URLs added:     {self.stats['urls_added']}")
        logger.info(f"Already had URL:          {self.stats['urls_already_set']}")
        logger.info(f"No URL found in MB:       {self.stats['no_url_found']}")
        logger.info(f"Errors:                   {self.stats['errors']}")
        logger.info("="*80)
        
        if self.stats['urls_added'] > 0:
            logger.info(f"✓ Successfully added {self.stats['urls_added']} Wikipedia URLs!")


def main():
    parser = argparse.ArgumentParser(
        description='Populate Wikipedia URLs for songs from MusicBrainz data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run in normal mode (process all songs)
  python one_time_song_wiki.py
  
  # Dry run to see what would be done
  python one_time_song_wiki.py --dry-run
  
  # Process only the first 10 songs
  python one_time_song_wiki.py --limit 10
  
  # Enable debug logging
  python one_time_song_wiki.py --debug
  
  # Combine flags
  python one_time_song_wiki.py --dry-run --debug --limit 5
  
  # Force refresh cache (use if cache doesn't have Wikipedia URL data)
  python one_time_song_wiki.py --force-refresh

Notes:
  - This script uses the MusicBrainz cache to minimize API calls
  - Only processes songs with musicbrainz_id but no wikipedia_url
  - Safe to run multiple times (skips songs that already have URLs)
  - Use --force-refresh if cached data is missing URL relationships
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of songs to process (default: process all)'
    )
    
    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Ignore cache and fetch fresh data from MusicBrainz (use if cache is missing URL data)'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create populator and run
    populator = SongWikipediaPopulator(
        dry_run=args.dry_run,
        limit=args.limit,
        force_refresh=args.force_refresh
    )
    
    try:
        success = populator.run()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nProcess cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()