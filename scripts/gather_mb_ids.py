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

# Import shared database utilities
sys.path.insert(0, '/mnt/project/scripts')
from db_utils import get_db_connection

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
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'JazzReference/1.0 (https://github.com/yourusername/jazzreference)',
            'Accept': 'application/json'
        })
        self.stats = {
            'songs_processed': 0,
            'songs_with_mb_id': 0,
            'mb_ids_found': 0,
            'songs_updated': 0,
            'no_match_found': 0,
            'errors': 0
        }
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # MusicBrainz requires 1 second between requests
    
    def rate_limit(self):
        """Enforce rate limiting for MusicBrainz API"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def normalize_title(self, title):
        """
        Normalize title for comparison by handling various punctuation differences
        
        Args:
            title: Title to normalize
        
        Returns:
            Normalized title string
        """
        normalized = title.lower()
        
        # Replace all types of apostrophes with standard apostrophe
        # Includes: ' (right single quotation), ʼ (modifier letter apostrophe), 
        # ` (grave accent), ´ (acute accent)
        apostrophe_variants = [''', ''', 'ʼ', '`', '´', '’']
        for variant in apostrophe_variants:
            normalized = normalized.replace(variant, "'")
        
        # Replace different types of dashes/hyphens
        dash_variants = ['–', '—', '−']  # en dash, em dash, minus
        for variant in dash_variants:
            normalized = normalized.replace(variant, '-')
        
        # Replace different types of quotes
        quote_variants = ['"', '"', '„', '«', '»']  # smart quotes, guillemets
        for variant in quote_variants:
            normalized = normalized.replace(variant, '"')
        
        return normalized
    
    def search_musicbrainz_work(self, title, composer):
        """
        Search MusicBrainz for a work by title and composer
        
        Args:
            title: Song title
            composer: Composer name(s)
        
        Returns:
            MusicBrainz Work ID if found, None otherwise
        """
        self.rate_limit()
        
        # Build search query
        # Search by title and optionally composer
        query_parts = [f'work:"{title}"']
        
        if composer:
            # Extract first composer if multiple
            first_composer = composer.split(',')[0].split(' and ')[0].strip()
            query_parts.append(f'artist:"{first_composer}"')
        
        query = ' AND '.join(query_parts)
        
        logger.debug(f"    Searching MusicBrainz: {query}")
        
        try:
            response = self.session.get(
                'https://musicbrainz.org/ws/2/work/',
                params={
                    'query': query,
                    'fmt': 'json',
                    'limit': 5
                },
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            works = data.get('works', [])
            
            if not works:
                logger.debug(f"    ✗ No MusicBrainz works found")
                return None
            
            # Normalize search title for comparison
            normalized_search_title = self.normalize_title(title)
            
            # Look for exact or very close title match
            for work in works:
                work_title = work.get('title', '')
                normalized_work_title = self.normalize_title(work_title)
                
                # Check for exact match after normalization
                if normalized_work_title == normalized_search_title:
                    mb_id = work['id']
                    logger.debug(f"    ✓ Found: '{work['title']}' (ID: {mb_id})")
                    
                    # Show composer if available
                    if 'artist-relation-list' in work:
                        composers = [r['artist']['name'] for r in work['artist-relation-list'] 
                                   if r['type'] == 'composer']
                        if composers:
                            logger.debug(f"       Composer(s): {', '.join(composers)}")
                    
                    return mb_id
            
            # If no exact match, show what was found
            logger.debug(f"    ⚠ Found {len(works)} works but no exact match:")
            for work in works[:3]:
                logger.debug(f"       - '{work['title']}'")
            
            return None
            
        except requests.exceptions.Timeout:
            logger.warning(f"    ⚠ MusicBrainz search timed out")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"    ✗ MusicBrainz search failed: {e}")
            return None
        except Exception as e:
            logger.error(f"    ✗ Error searching MusicBrainz: {e}")
            return None
    
    def get_songs_without_mb_id(self):
        """Get all songs that don't have a MusicBrainz ID"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
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
                
                # Search MusicBrainz
                mb_id = self.search_musicbrainz_work(
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
  # Run in normal mode
  python gather_mb_ids.py
  
  # Dry run to see what would be found
  python gather_mb_ids.py --dry-run
  
  # Enable debug logging
  python gather_mb_ids.py --debug

Notes:
  - MusicBrainz API requires 1 second between requests (enforced by rate limiting)
  - The script looks for exact or very close title matches
  - Results are logged to mb_gather.log
        """
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
    gatherer = MusicBrainzGatherer(dry_run=args.dry_run)
    
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
