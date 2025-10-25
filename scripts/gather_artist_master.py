#!/usr/bin/env python3
"""
Artist Gatherer
Looks for an artist by name at several key canonical sources
stores or verifies the canonical IDs
then gathers relevant information from those canonical ids
"""

import sys
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
from datetime import datetime
import time
import argparse
import logging
from pathlib import Path

# Import db_utils and mb_utils from same directory
from db_utils import get_db_connection
from mb_utils import MusicBrainzSearcher
from wiki_utils import WikipediaSearcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ArtistGatherer:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        
        self.mb_searcher = MusicBrainzSearcher()
        self.wiki_searcher = WikipediaSearcher()
    
    def gather_canonical_ids(self,artist_name):
        """Figure out if the artist exists"""
        """if artist exists, figure out if wikipedia and MB IDs exist"""
        """if wiki and mb ids exist, verify whether current searching logic would find the same ones"""

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:      
                    cur.execute("""
                        SELECT id, external_links FROM performers WHERE name = %s
                    """, (artist_name,))
                    
                    performer_result = cur.fetchone()
                    if performer_result:
                        performer_id = performer_result['id']
                        performer_external_links = performer_result['external_links']
    
                        logger.info(f"  Artist already exists: {performer_id}") 
                        logger.info(f"  External links is {performer_external_links}")  

                        cur_wiki=""
                        if "wikipedia" in performer_external_links:
                            cur_wiki = performer_external_links['wikipedia']
                            
                        context = {}
                        new_wiki = self.wiki_searcher.search_wikipedia(artist_name, context)
                        
                        if new_wiki == cur_wiki:
                            logger.info(f" the wikipedia reference matches & stays the same")
                        else:
                            logger.info(f" we would switch the wiki url from {cur_wiki} to {new_wiki}")
                            
                    else:
                        logger.info("  Artist doesn't already exist")
                        
                        context = {}
                        wiki = self.wiki_searcher.search_wikipedia(artist_name, context)
                                        
                    return True
                                
        except Exception as e:
            logger.error(f"Error importing to database: {e}", exc_info=True)
            return False

    def import_to_database(self, artist_name):
        """Research and import directly to database"""
        logger.info(f"{'='*60}")
        logger.info(f"Processing: {artist_name}")
        logger.info(f"{'='*60}\n")
        
        canonical_ids = self.gather_canonical_ids(artist_name)
        
        return True

def main():
    parser = argparse.ArgumentParser(
        description='Crawl data sources for a specific artist',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python gather_artist_master.py --name "Miles Davis"
  python gather_artist_master.py --name "Ella Fitzgerald" --dry-run
  python gather_artist_master.py --name "Grant Green" --debug
        """
    )
    
    parser.add_argument('--name', required=True, help='Performer name')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be gathered without making changes')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    researcher = ArtistGatherer(dry_run=args.dry_run)
    
    try:
        success = researcher.import_to_database(args.name)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nCancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()