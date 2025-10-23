#!/usr/bin/env python3
"""
Fetch Artist Images Script
Fetches images for jazz artists from Wikipedia and Discogs, storing them in the database.

Usage:
    python fetch_artist_images.py --name "Miles Davis"
    python fetch_artist_images.py --id <uuid>
    python fetch_artist_images.py --name "John Coltrane" --dry-run
    python fetch_artist_images.py --name "Thelonious Monk" --debug
"""

import sys
import argparse
import logging
import requests
import json
import re
from typing import Optional, Dict, Any, List
from urllib.parse import quote, urljoin, unquote
import time

# Import our database utilities
from db_utils import (
    get_db_connection,
    find_performer_by_name,
    find_performer_by_id,
    update_performer_external_references,
    get_performer_images
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ImageFetcher:
    """Handles fetching images from various sources."""
    
    def __init__(self, dry_run: bool = False, debug: bool = False):
        self.dry_run = dry_run
        self.debug = debug
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'JazzReferenceApp/1.0 (Educational; Contact: support@jazzreference.app)'
        })
        
        if debug:
            logger.setLevel(logging.DEBUG)
    
    def fetch_wikipedia_image(self, artist_name: str, wikipedia_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Fetch image from Wikipedia for an artist.
        
        Args:
            artist_name: Name of the artist to search for
            wikipedia_url: Optional Wikipedia URL from database (skips search if provided)
        
        Returns:
            Dictionary with image data or None
        """
        try:
            # If we have a Wikipedia URL from the database, extract the page title
            if wikipedia_url:
                logger.info(f"Using Wikipedia URL from database: {wikipedia_url}")
                # Extract page title from URL like https://en.wikipedia.org/wiki/Miles_Davis
                match = re.search(r'/wiki/(.+)$', wikipedia_url)
                if match:
                    page_title = unquote(match.group(1))
                    logger.debug(f"Extracted page title: {page_title}")
                else:
                    logger.warning(f"Could not extract page title from URL: {wikipedia_url}")
                    wikipedia_url = None  # Fall back to search
            
            # If no Wikipedia URL provided, search for the page
            if not wikipedia_url:
                logger.info(f"Searching Wikipedia for {artist_name}...")
                
                # Step 1: Search for the Wikipedia page
                search_url = "https://en.wikipedia.org/w/api.php"
                search_params = {
                    'action': 'query',
                    'format': 'json',
                    'list': 'search',
                    'srsearch': artist_name,
                    'srlimit': 1
                }
                
                response = self.session.get(search_url, params=search_params, timeout=10)
                response.raise_for_status()
                search_data = response.json()
                
                if not search_data.get('query', {}).get('search'):
                    logger.info(f"No Wikipedia page found for {artist_name}")
                    return None
                
                page_title = search_data['query']['search'][0]['title']
                logger.debug(f"Found Wikipedia page: {page_title}")
            
            # Step 2: Get the main image from the page
            search_url = "https://en.wikipedia.org/w/api.php"
            image_params = {
                'action': 'query',
                'format': 'json',
                'titles': page_title,
                'prop': 'pageimages|pageterms|info',
                'piprop': 'original|thumbnail',
                'pithumbsize': 500,
                'inprop': 'url'
            }
            
            response = self.session.get(search_url, params=image_params, timeout=10)
            response.raise_for_status()
            page_data = response.json()
            
            pages = page_data.get('query', {}).get('pages', {})
            if not pages:
                logger.info(f"No page data found for {page_title}")
                return None
            
            page = next(iter(pages.values()))
            
            # Get image URL
            if 'original' not in page:
                logger.info(f"No image found on Wikipedia page for {artist_name}")
                return None
            
            image_url = page['original']['source']
            thumbnail_url = page.get('thumbnail', {}).get('source')
            page_url = page.get('fullurl', f"https://en.wikipedia.org/wiki/{quote(page_title)}")
            
            # Get image details for licensing
            image_filename = image_url.split('/')[-1]
            license_params = {
                'action': 'query',
                'format': 'json',
                'titles': f'File:{image_filename}',
                'prop': 'imageinfo',
                'iiprop': 'extmetadata|size'
            }
            
            response = self.session.get(search_url, params=license_params, timeout=10)
            response.raise_for_status()
            license_data = response.json()
            
            # Extract license information
            license_type = 'unknown'
            license_url = None
            attribution = None
            width = page['original'].get('width')
            height = page['original'].get('height')
            
            if license_data.get('query', {}).get('pages'):
                file_page = next(iter(license_data['query']['pages'].values()))
                if 'imageinfo' in file_page and file_page['imageinfo']:
                    imageinfo = file_page['imageinfo'][0]
                    extmetadata = imageinfo.get('extmetadata', {})
                    
                    # Get license
                    if 'License' in extmetadata:
                        license_type = extmetadata['License'].get('value', 'unknown')
                    if 'LicenseUrl' in extmetadata:
                        license_url = extmetadata['LicenseUrl'].get('value')
                    
                    # Get attribution
                    if 'Artist' in extmetadata:
                        attribution = extmetadata['Artist'].get('value')
                    elif 'Credit' in extmetadata:
                        attribution = extmetadata['Credit'].get('value')
                    
                    # Get actual dimensions
                    if 'size' in imageinfo:
                        width = imageinfo.get('width', width)
                        height = imageinfo.get('height', height)
            
            # Normalize license type
            license_type_normalized = self._normalize_license(license_type)
            
            image_data = {
                'url': image_url,
                'thumbnail_url': thumbnail_url,
                'source': 'wikipedia',
                'source_identifier': page_title,
                'source_page_url': page_url,
                'license_type': license_type_normalized,
                'license_url': license_url,
                'attribution': attribution,
                'width': width,
                'height': height
            }
            
            logger.info(f"✓ Found Wikipedia image: {image_url}")
            logger.debug(f"Image details: {image_data}")
            
            return image_data
            
        except requests.RequestException as e:
            logger.error(f"Error fetching Wikipedia image: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching Wikipedia image: {e}")
            if self.debug:
                logger.exception(e)
            return None
    
    def fetch_discogs_image(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch image from Discogs for an artist.
        
        Note: Discogs requires API authentication. This is a placeholder
        that would need to be implemented with proper API credentials.
        
        Args:
            artist_name: Name of the artist to search for
        
        Returns:
            Dictionary with image data or None
        """
        try:
            logger.info(f"Searching Discogs for {artist_name}...")
            
            # Discogs requires authentication - this is simplified
            # In production, you'd need to:
            # 1. Register for Discogs API credentials
            # 2. Add them to environment variables
            # 3. Use OAuth or token authentication
            
            discogs_token = None  # Would read from environment
            
            if not discogs_token:
                logger.info("Discogs API token not configured, skipping Discogs search")
                return None
            
            # This would be the actual implementation:
            # search_url = "https://api.discogs.com/database/search"
            # params = {
            #     'q': artist_name,
            #     'type': 'artist',
            #     'token': discogs_token
            # }
            # response = self.session.get(search_url, params=params, timeout=10)
            # ... process response ...
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching Discogs image: {e}")
            if self.debug:
                logger.exception(e)
            return None
    
    def _normalize_license(self, license_str: str) -> str:
        """Normalize license strings to standard types."""
        if not license_str:
            return 'unknown'
        
        license_lower = license_str.lower()
        
        # Creative Commons licenses
        if 'cc-by-sa' in license_lower or 'cc by-sa' in license_lower:
            return 'cc-by-sa'
        elif 'cc-by' in license_lower or 'cc by' in license_lower:
            return 'cc-by'
        elif 'cc0' in license_lower or 'cc zero' in license_lower:
            return 'cc0'
        elif 'public domain' in license_lower or 'pd' in license_lower:
            return 'public-domain'
        elif 'fair use' in license_lower:
            return 'fair-use'
        else:
            return 'all-rights-reserved'
    
    def save_image_to_db(self, performer_id: str, image_data: Dict[str, Any], 
                        is_primary: bool = False, display_order: int = 0) -> bool:
        """
        Save an image to the database and link it to a performer.
        
        Args:
            performer_id: UUID of the performer
            image_data: Dictionary containing image information
            is_primary: Whether this is the primary/profile image
            display_order: Order for displaying in carousel
        
        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would save image to database:")
            logger.info(f"  URL: {image_data.get('url')}")
            logger.info(f"  Source: {image_data.get('source')}")
            logger.info(f"  License: {image_data.get('license_type')}")
            logger.info(f"  Primary: {is_primary}")
            return True
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # First, check if image already exists
                    check_query = """
                        SELECT id FROM images 
                        WHERE source = %s AND source_identifier = %s AND url = %s
                    """
                    cur.execute(check_query, (
                        image_data['source'],
                        image_data.get('source_identifier'),
                        image_data['url']
                    ))
                    existing = cur.fetchone()
                    
                    if existing:
                        image_id = existing['id']
                        logger.info(f"Image already exists in database: {image_id}")
                    else:
                        # Insert new image
                        insert_image_query = """
                            INSERT INTO images (
                                url, source, source_identifier, license_type, license_url,
                                attribution, width, height, thumbnail_url, source_page_url
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                            )
                            RETURNING id
                        """
                        cur.execute(insert_image_query, (
                            image_data['url'],
                            image_data['source'],
                            image_data.get('source_identifier'),
                            image_data.get('license_type'),
                            image_data.get('license_url'),
                            image_data.get('attribution'),
                            image_data.get('width'),
                            image_data.get('height'),
                            image_data.get('thumbnail_url'),
                            image_data.get('source_page_url')
                        ))
                        image_id = cur.fetchone()['id']
                        logger.info(f"✓ Inserted new image: {image_id}")
                    
                    # Check if relationship already exists
                    check_rel_query = """
                        SELECT 1 FROM artist_images 
                        WHERE performer_id = %s AND image_id = %s
                    """
                    cur.execute(check_rel_query, (performer_id, image_id))
                    
                    if cur.fetchone():
                        logger.info(f"Image already linked to performer")
                    else:
                        # Link image to performer
                        insert_rel_query = """
                            INSERT INTO artist_images (
                                performer_id, image_id, is_primary, display_order
                            ) VALUES (%s, %s, %s, %s)
                        """
                        cur.execute(insert_rel_query, (
                            performer_id, image_id, is_primary, display_order
                        ))
                        logger.info(f"✓ Linked image to performer")
                    
                    conn.commit()
                    return True
                    
        except Exception as e:
            logger.error(f"Error saving image to database: {e}")
            if self.debug:
                logger.exception(e)
            return False
    
    def fetch_and_save_images(self, performer: Dict[str, Any]) -> int:
        """
        Fetch images from all available sources and save them.
        
        Args:
            performer: Performer record from database
        
        Returns:
            Number of new images added
        """
        performer_id = str(performer['id'])
        performer_name = performer['name']
        images_added = 0
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Fetching images for: {performer_name}")
        logger.info(f"{'='*60}")
        
        # Check existing images
        existing_images = get_performer_images(performer_id)
        if existing_images:
            logger.info(f"Performer already has {len(existing_images)} image(s)")
            for img in existing_images:
                logger.info(f"  - {img['source']}: {img['url']}")
        
        # Get Wikipedia URL from external_links if available
        external_links = performer.get('external_links') or {}
        wikipedia_url = external_links.get('wikipedia')
        
        # Fetch from Wikipedia
        wiki_image = self.fetch_wikipedia_image(performer_name, wikipedia_url=wikipedia_url)
        if wiki_image:
            # Update external_references with Wikipedia page
            external_refs = {}
            if wiki_image.get('source_identifier'):
                external_refs['wikipedia_title'] = wiki_image['source_identifier']
            if wiki_image.get('source_page_url'):
                external_refs['wikipedia_url'] = wiki_image['source_page_url']
            
            if external_refs:
                update_performer_external_references(performer_id, external_refs, self.dry_run)
            
            # Save the image
            if self.save_image_to_db(performer_id, wiki_image, is_primary=not existing_images, display_order=0):
                images_added += 1
        
        # Fetch from Discogs (placeholder for now)
        discogs_image = self.fetch_discogs_image(performer_name)
        if discogs_image:
            if self.save_image_to_db(performer_id, discogs_image, is_primary=False, display_order=1):
                images_added += 1
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✓ Added {images_added} new image(s) for {performer_name}")
        logger.info(f"{'='*60}\n")
        
        return images_added


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Fetch images for jazz artists from Wikipedia and Discogs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Fetch images by artist name
    python fetch_artist_images.py --name "Miles Davis"
    
    # Fetch by performer ID
    python fetch_artist_images.py --id 123e4567-e89b-12d3-a456-426614174000
    
    # Dry run (don't save to database)
    python fetch_artist_images.py --name "John Coltrane" --dry-run
    
    # Enable debug logging
    python fetch_artist_images.py --name "Thelonious Monk" --debug
        """
    )
    
    # Required arguments (one of)
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--name', help='Artist name to search for')
    group.add_argument('--id', help='Performer UUID')
    
    # Optional arguments
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Fetch and save images
    fetcher = ImageFetcher(dry_run=args.dry_run, debug=args.debug)
    
    # Determine which performers to process
    performers = []
    
    if args.name:
        logger.info(f"Searching for performer: {args.name}")
        performer = find_performer_by_name(args.name)
        if not performer:
            logger.error(f"Performer not found: {args.name}")
            sys.exit(1)
        performers = [performer]
        logger.info(f"Found performer: {performer['name']} (ID: {performer['id']})")
    elif args.id:
        logger.info(f"Looking up performer ID: {args.id}")
        performer = find_performer_by_id(args.id)
        if not performer:
            logger.error(f"Performer not found with ID: {args.id}")
            sys.exit(1)
        performers = [performer]
        logger.info(f"Found performer: {performer['name']} (ID: {performer['id']})")
    else:
        # Process all performers
        logger.info("No specific performer specified - processing all performers")
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, biography, birth_date, death_date, external_links
                    FROM performers
                    ORDER BY name
                """)
                performers = cur.fetchall()
        logger.info(f"Found {len(performers)} performers to process")
    
    # Process each performer
    total_images_added = 0
    for performer in performers:
        images_added = fetcher.fetch_and_save_images(performer)
        total_images_added += images_added
        
        # Add delay between performers to be respectful to APIs
        if len(performers) > 1:
            time.sleep(2.0)
    
    if total_images_added > 0:
        logger.info(f"\n✓ Success! Added {total_images_added} image(s) across {len(performers)} performer(s)")
    else:
        logger.info(f"\n✓ No new images added")
    
    sys.exit(0)


if __name__ == '__main__':
    main()