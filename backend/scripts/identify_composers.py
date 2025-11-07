#!/usr/bin/env python3
"""
Identify Composers for Songs
One-time script to find and update composer information for songs that are missing it
but have MusicBrainz IDs. Uses MusicBrainz work data to extract composer information.
"""

import sys
import argparse
import logging
import time
from pathlib import Path

# Import shared utilities
from db_utils import get_db_connection
from mb_utils import MusicBrainzSearcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('log/identify_composers.log')
    ]
)
logger = logging.getLogger(__name__)


class ComposerIdentifier:
    """Identifies and updates composer information for songs"""
    
    def __init__(self, dry_run=False):
        """
        Initialize composer identifier
        
        Args:
            dry_run: If True, show what would be done without making changes
        """
        self.dry_run = dry_run
        self.mb_searcher = MusicBrainzSearcher(
            cache_dir='cache/musicbrainz',
            cache_days=30,
            force_refresh=False
        )
        self.stats = {
            'songs_processed': 0,
            'composers_found': 0,
            'composers_updated': 0,
            'no_composer_found': 0,
            'errors': 0
        }
    
    def get_songs_needing_composers(self):
        """
        Get songs that don't have a composer but do have a MusicBrainz ID
        
        Returns:
            List of song dicts with id, title, and musicbrainz_id
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, composer, musicbrainz_id
                    FROM songs
                    WHERE (composer IS NULL OR composer = '')
                      AND musicbrainz_id IS NOT NULL
                    ORDER BY title
                """)
                return cur.fetchall()
    
    def extract_composer_from_musicbrainz(self, song_title, musicbrainz_id):
        """
        Extract composer from MusicBrainz work data
        
        Args:
            song_title: Title of the song (for logging)
            musicbrainz_id: MusicBrainz work ID
            
        Returns:
            String with composer name(s), or None if not found
        """
        if not musicbrainz_id:
            return None
        
        # Get work details to extract composer relations
        logger.debug(f"  Fetching MusicBrainz work details: {musicbrainz_id}")
        work_data = self.mb_searcher.get_work_recordings(musicbrainz_id)
        made_api_call = self.mb_searcher.last_made_api_call
        
        if made_api_call:
            time.sleep(1.0)
        
        if not work_data:
            logger.debug(f"  Could not fetch work data")
            return None
        
        # Extract composers from relations
        composers = []
        relations = work_data.get('relations', [])
        
        for relation in relations:
            if relation.get('type') == 'composer':
                artist = relation.get('artist', {})
                composer_name = artist.get('name')
                if composer_name:
                    composers.append(composer_name)
        
        if composers:
            composer_string = ', '.join(composers)
            logger.debug(f"  Found composer(s) from MusicBrainz: {composer_string}")
            return composer_string
        
        return None
    
    def identify_composer(self, song):
        """
        Identify composer for a song using its MusicBrainz ID
        
        Args:
            song: Dict with id, title, and musicbrainz_id
            
        Returns:
            String with composer name(s), or None if not found
        """
        song_id = song['id']
        song_title = song['title']
        musicbrainz_id = song.get('musicbrainz_id')
        
        logger.info(f"Processing: {song_title}")
        
        if not musicbrainz_id:
            logger.warning(f"  No MusicBrainz ID found (this shouldn't happen)")
            return None
        
        # Extract composer from MusicBrainz
        logger.debug(f"  Using MusicBrainz ID: {musicbrainz_id}")
        composer = self.extract_composer_from_musicbrainz(song_title, musicbrainz_id)
        
        return composer
    
    def update_song_composer(self, song_id, composer):
        """
        Update the composer field for a song
        
        Args:
            song_id: UUID of the song
            composer: Composer name(s) to set
        """
        if self.dry_run:
            logger.info(f"  [DRY RUN] Would update composer to: {composer}")
            return
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE songs
                    SET composer = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (composer, song_id))
                conn.commit()
        
        logger.info(f"  ✓ Updated composer to: {composer}")
    
    def process_song(self, song):
        """
        Process a single song to identify and update its composer
        
        Args:
            song: Dict with song data
            
        Returns:
            True if composer was found and updated, False otherwise
        """
        try:
            composer = self.identify_composer(song)
            
            if composer:
                self.update_song_composer(song['id'], composer)
                self.stats['composers_found'] += 1
                if not self.dry_run:
                    self.stats['composers_updated'] += 1
                return True
            else:
                logger.info(f"  ✗ No composer found")
                self.stats['no_composer_found'] += 1
                return False
                
        except Exception as e:
            logger.error(f"Error processing {song['title']}: {e}", exc_info=True)
            self.stats['errors'] += 1
            return False
    
    def run(self):
        """Main processing method"""
        logger.info("="*80)
        logger.info("IDENTIFY COMPOSERS")
        logger.info("="*80)
        
        if self.dry_run:
            logger.info("*** DRY RUN MODE - No database changes will be made ***")
            logger.info("")
        
        # Get songs needing composers
        songs = self.get_songs_needing_composers()
        
        if not songs:
            logger.info("No songs need composer identification!")
            return True
        
        logger.info(f"Found {len(songs)} song(s) without composers but with MusicBrainz IDs")
        logger.info("")
        
        # Process each song
        for song in songs:
            self.stats['songs_processed'] += 1
            self.process_song(song)
            logger.info("")  # Blank line between songs
        
        # Print summary
        self.print_summary()
        
        return True
    
    def print_summary(self):
        """Print processing summary"""
        logger.info("")
        logger.info("="*80)
        logger.info("PROCESSING SUMMARY")
        logger.info("="*80)
        logger.info(f"Songs processed:      {self.stats['songs_processed']}")
        logger.info(f"Composers found:      {self.stats['composers_found']}")
        logger.info(f"Composers updated:    {self.stats['composers_updated']}")
        logger.info(f"No composer found:    {self.stats['no_composer_found']}")
        logger.info(f"Errors:               {self.stats['errors']}")
        logger.info("="*80)


def main():
    parser = argparse.ArgumentParser(
        description='Identify and update composer information for songs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run in normal mode
  python identify_composers.py
  
  # Dry run to see what would be done
  python identify_composers.py --dry-run
  
  # Enable debug logging
  python identify_composers.py --debug
  
  # Combine flags
  python identify_composers.py --dry-run --debug
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
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create log directory if needed
    Path('log').mkdir(exist_ok=True)
    
    # Create identifier and run
    identifier = ComposerIdentifier(dry_run=args.dry_run)
    
    try:
        success = identifier.run()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nProcess cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()