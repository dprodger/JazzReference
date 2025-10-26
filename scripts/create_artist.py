#!/usr/bin/env python3
"""
Create Artist
Creates a new performer/artist in the database and optionally finds external references
"""

import sys
import argparse
import logging
import json
import time

# Third-party imports
import requests

# Local imports
from db_utils import get_db_connection
from wiki_utils import WikipediaSearcher
from mb_utils import MusicBrainzSearcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('log/create_artist.log')
    ]
)
logger = logging.getLogger(__name__)


class ArtistCreator:
    """Create new artists and find their external references"""
    
    def __init__(self, dry_run=False):
        """
        Initialize creator
        
        Args:
            dry_run: If True, show what would be done without making changes
        """
        self.dry_run = dry_run
        self.wiki_searcher = WikipediaSearcher()
        self.mb_searcher = MusicBrainzSearcher()
        
        # Set up session for API calls
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'JazzReference/1.0 (Educational; Contact: support@jazzreference.app)',
            'Accept': 'application/json'
        })
        
        self.stats = {
            'artists_checked': 0,
            'artists_created': 0,
            'artists_skipped': 0,
            'wikipedia_found': 0,
            'musicbrainz_found': 0,
            'errors': 0
        }
    
    def check_artist_exists(self, name):
        """
        Check if an artist with this name already exists
        
        Args:
            name: Artist name to check
            
        Returns:
            Dict with artist data if exists, None otherwise
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, name, external_links
                        FROM performers
                        WHERE LOWER(name) = LOWER(%s)
                    """, (name,))
                    
                    result = cur.fetchone()
                    return result
        except Exception as e:
            logger.error(f"Error checking if artist exists: {e}", exc_info=True)
            self.stats['errors'] += 1
            return None
    
    def create_artist(self, name):
        """
        Create a new artist in the database
        
        Args:
            name: Artist name
            
        Returns:
            UUID of created artist, or None on failure
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would create artist: {name}")
            return "dry-run-uuid"
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO performers (name, external_links)
                        VALUES (%s, '{}'::jsonb)
                        RETURNING id
                    """, (name,))
                    
                    result = cur.fetchone()
                    artist_id = result['id']
                    
                    conn.commit()
                    return artist_id
        except Exception as e:
            logger.error(f"Error creating artist: {e}", exc_info=True)
            self.stats['errors'] += 1
            return None
    
    def update_artist_references(self, artist_id, references):
        """
        Update external_links for an artist
        
        Args:
            artist_id: UUID of the artist
            references: Dict with keys like 'wikipedia', 'musicbrainz'
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update references: {json.dumps(references)}")
            return True
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE performers
                        SET external_links = COALESCE(external_links, '{}'::jsonb) || %s::jsonb,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (json.dumps(references), artist_id))
                    
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"Error updating artist references: {e}", exc_info=True)
            self.stats['errors'] += 1
            return False
    
    def search_wikipedia(self, artist_name):
        """
        Search Wikipedia for an artist
        
        Args:
            artist_name: Name to search for
            
        Returns:
            Wikipedia URL if found with reasonable confidence, None otherwise
        """
        try:
            logger.info(f"  Searching Wikipedia for: {artist_name}")
            
            # Build minimal context (we don't have sample songs yet)
            context = {
                'birth_date': None,
                'death_date': None,
                'sample_songs': []
            }
            
            # Use Wikipedia API to search
            search_url = "https://en.wikipedia.org/w/api.php"
            params = {
                'action': 'opensearch',
                'search': artist_name,
                'limit': 5,
                'namespace': 0,
                'format': 'json'
            }
            
            response = self.session.get(search_url, params=params, timeout=10)
            time.sleep(1.0)  # Rate limiting
            
            if response.status_code != 200:
                logger.info(f"  ✗ Wikipedia search failed (status {response.status_code})")
                return None
            
            data = response.json()
            if len(data) < 4 or not data[3]:
                logger.info(f"  ✗ No Wikipedia results found")
                return None
            
            # Get the URLs from the response
            urls = data[3]
            
            # Check top 5 results
            for url in urls[:5]:
                verification = self.wiki_searcher.verify_wikipedia_reference(artist_name, url, context)
                logger.debug(f"  Checked {url}: valid={verification['valid']}, confidence={verification['confidence']}, score={verification.get('score', 0)}")
                
                # Accept any valid result (low, medium, or high - not very_low)
                if verification['valid']:
                    logger.info(f"  ✓ Found Wikipedia: {url} (confidence: {verification['confidence']}, score: {verification.get('score', 0)})")
                    logger.info(f"    Reason: {verification['reason']}")
                    self.stats['wikipedia_found'] += 1
                    return url
            
            logger.info(f"  ✗ No valid Wikipedia match found")
            return None
            
        except Exception as e:
            logger.error(f"Error searching Wikipedia for {artist_name}: {e}")
            self.stats['errors'] += 1
            return None
    
    def search_musicbrainz(self, artist_name):
        """
        Search MusicBrainz for an artist
        
        Args:
            artist_name: Name to search for
            
        Returns:
            MusicBrainz artist ID if found with reasonable confidence, None otherwise
        """
        try:
            logger.info(f"  Searching MusicBrainz for: {artist_name}")
            
            # Build minimal context
            context = {
                'sample_songs': []
            }
            
            url = "https://musicbrainz.org/ws/2/artist/"
            params = {
                'query': f'artist:"{artist_name}" AND tag:jazz',
                'fmt': 'json',
                'limit': 5
            }
            
            response = self.session.get(url, params=params, timeout=10)
            time.sleep(1.0)  # MusicBrainz rate limiting
            
            if response.status_code != 200:
                logger.info(f"  ✗ MusicBrainz search failed (status {response.status_code})")
                return None
            
            data = response.json()
            artists = data.get('artists', [])
            
            if not artists:
                logger.info(f"  ✗ No MusicBrainz results found")
                return None
            
            # Look for exact or close name match
            for artist in artists:
                artist_name_mb = artist.get('name', '').lower()
                if artist_name_mb == artist_name.lower():
                    mb_id = artist.get('id')
                    # Verify this is the right artist
                    verification = self.verify_musicbrainz_reference(artist_name, mb_id, context)
                    if verification['valid']:
                        logger.info(f"  ✓ Found MusicBrainz: {mb_id} (confidence: {verification['confidence']})")
                        logger.info(f"    Reason: {verification['reason']}")
                        self.stats['musicbrainz_found'] += 1
                        return mb_id
            
            logger.info(f"  ✗ No valid MusicBrainz match found")
            return None
            
        except Exception as e:
            logger.error(f"Error searching MusicBrainz for {artist_name}: {e}")
            self.stats['errors'] += 1
            return None
    
    def verify_musicbrainz_reference(self, artist_name, mb_id, context):
        """
        Verify that a MusicBrainz artist ID is valid
        
        Args:
            artist_name: Name of the artist
            mb_id: MusicBrainz artist ID (UUID)
            context: Dict with sample_songs for verification
            
        Returns:
            Dict with 'valid' (bool), 'confidence' (str), 'reason' (str)
        """
        try:
            url = f"https://musicbrainz.org/ws/2/artist/{mb_id}"
            params = {
                'fmt': 'json',
                'inc': 'recordings+tags'
            }
            
            logger.debug(f"Verifying MusicBrainz ID: {mb_id}")
            
            response = self.session.get(url, params=params, timeout=10)
            time.sleep(1.0)  # MusicBrainz rate limiting
            
            if response.status_code == 404:
                return {
                    'valid': False,
                    'confidence': 'certain',
                    'reason': 'MusicBrainz ID not found (404)'
                }
            elif response.status_code != 200:
                return {
                    'valid': False,
                    'confidence': 'uncertain',
                    'reason': f'API returned status code {response.status_code}'
                }
            
            data = response.json()
            
            # Check name similarity
            mb_name = data.get('name', '').lower()
            artist_name_lower = artist_name.lower()
            
            if mb_name != artist_name_lower:
                # Check if it's a close match
                if mb_name not in artist_name_lower and artist_name_lower not in mb_name:
                    return {
                        'valid': False,
                        'confidence': 'high',
                        'reason': f'Name mismatch: searched for "{artist_name}", MusicBrainz has "{data.get("name")}"'
                    }
            
            # Name matches, this is valid
            return {
                'valid': True,
                'confidence': 'high',
                'reason': f'Name matches: "{data.get("name")}"'
            }
            
        except requests.exceptions.Timeout:
            return {
                'valid': False,
                'confidence': 'uncertain',
                'reason': 'Request timed out'
            }
        except Exception as e:
            logger.error(f"Unexpected error verifying MusicBrainz: {e}", exc_info=True)
            return {
                'valid': False,
                'confidence': 'uncertain',
                'reason': f'Verification error: {str(e)}'
            }
    
    def create_with_research(self, name, wikipedia_url=None, musicbrainz_id=None):
        """
        Create an artist and optionally find external references
        
        Args:
            name: Artist name
            wikipedia_url: Optional Wikipedia URL (skips search if provided)
            musicbrainz_id: Optional MusicBrainz ID (skips search if provided)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("="*80)
            logger.info(f"CREATING ARTIST: {name}")
            logger.info("="*80)
            logger.info("")
            
            self.stats['artists_checked'] += 1
            
            # Check if artist already exists
            existing = self.check_artist_exists(name)
            if existing:
                logger.info(f"✗ Artist already exists: {name}")
                logger.info(f"  ID: {existing['id']}")
                if existing['external_links']:
                    logger.info(f"  External links: {json.dumps(existing['external_links'], indent=2)}")
                self.stats['artists_skipped'] += 1
                return False
            
            # Create the artist
            logger.info(f"Creating artist: {name}")
            artist_id = self.create_artist(name)
            
            if not artist_id:
                logger.error(f"✗ Failed to create artist")
                return False
            
            logger.info(f"✓ Artist created with ID: {artist_id}")
            self.stats['artists_created'] += 1
            logger.info("")
            
            # Build external references
            external_refs = {}
            
            # Handle Wikipedia reference
            if wikipedia_url:
                logger.info(f"Using provided Wikipedia URL: {wikipedia_url}")
                external_refs['wikipedia'] = wikipedia_url
                self.stats['wikipedia_found'] += 1
            else:
                # Search for Wikipedia
                wiki_url = self.search_wikipedia(name)
                if wiki_url:
                    external_refs['wikipedia'] = wiki_url
            
            # Handle MusicBrainz reference
            if musicbrainz_id:
                logger.info(f"Using provided MusicBrainz ID: {musicbrainz_id}")
                external_refs['musicbrainz'] = musicbrainz_id
                self.stats['musicbrainz_found'] += 1
            else:
                # Search for MusicBrainz
                mb_id = self.search_musicbrainz(name)
                if mb_id:
                    external_refs['musicbrainz'] = mb_id
            
            # Update artist with references if any were found
            if external_refs:
                logger.info("")
                logger.info(f"Updating artist with external references...")
                success = self.update_artist_references(artist_id, external_refs)
                if success:
                    logger.info(f"✓ External references updated")
                    logger.info(f"  {json.dumps(external_refs, indent=2)}")
                else:
                    logger.error(f"✗ Failed to update external references")
            else:
                logger.info("")
                logger.info("⚠️  No external references found")
            
            logger.info("")
            logger.info("="*80)
            logger.info(f"✓ ARTIST CREATION COMPLETE: {name}")
            logger.info("="*80)
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating artist {name}: {e}", exc_info=True)
            self.stats['errors'] += 1
            return False
    
    def print_summary(self):
        """Print processing summary"""
        logger.info("")
        logger.info("="*80)
        logger.info("CREATION SUMMARY")
        logger.info("="*80)
        logger.info(f"Artists checked:       {self.stats['artists_checked']}")
        logger.info(f"Artists created:       {self.stats['artists_created']}")
        logger.info(f"Artists skipped:       {self.stats['artists_skipped']}")
        logger.info(f"Wikipedia found:       {self.stats['wikipedia_found']}")
        logger.info(f"MusicBrainz found:     {self.stats['musicbrainz_found']}")
        logger.info(f"Errors:                {self.stats['errors']}")
        logger.info("="*80)


def main():
    parser = argparse.ArgumentParser(
        description='Create a new artist and optionally find external references',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create artist and search for references
  python create_artist.py --name "Bill Evans"
  
  # Create with provided Wikipedia URL
  python create_artist.py --name "Bill Evans" --wiki "https://en.wikipedia.org/wiki/Bill_Evans"
  
  # Create with provided MusicBrainz ID
  python create_artist.py --name "Bill Evans" --mb "5d7f3dea-8e59-48d5-be59-9e58f0dc2d5f"
  
  # Create with both references provided
  python create_artist.py --name "Bill Evans" \\
    --wiki "https://en.wikipedia.org/wiki/Bill_Evans" \\
    --mb "5d7f3dea-8e59-48d5-be59-9e58f0dc2d5f"
  
  # Dry run to see what would be done
  python create_artist.py --name "Bill Evans" --dry-run
  
  # Enable debug logging
  python create_artist.py --name "Bill Evans" --debug

This script:
1. Checks if the artist already exists in the database
2. Creates the artist if they don't exist
3. Searches for external references (Wikipedia, MusicBrainz) unless provided
4. Updates the artist with the found references

Note: If --wiki or --mb arguments are provided, the script will use those values
instead of searching for them.
        """
    )
    
    parser.add_argument(
        '--name',
        required=True,
        help='Artist name to create'
    )
    
    parser.add_argument(
        '--wiki',
        help='Wikipedia URL (skips Wikipedia search if provided)'
    )
    
    parser.add_argument(
        '--mb',
        help='MusicBrainz artist ID (skips MusicBrainz search if provided)'
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
    
    # Create artist creator
    creator = ArtistCreator(dry_run=args.dry_run)
    
    if args.dry_run:
        logger.info("*** DRY RUN MODE - No database changes will be made ***")
        logger.info("")
    
    try:
        success = creator.create_with_research(
            args.name,
            wikipedia_url=args.wiki,
            musicbrainz_id=args.mb
        )
        
        # Print summary
        creator.print_summary()
        
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nProcess cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()