#!/usr/bin/env python3
"""
Fetch Artist Images Script
Fetches images for jazz artists from Wikipedia and Discogs, storing them in the database.

ARCHITECTURE:
This script separates database operations from slow API calls to prevent connection timeouts:
1. Fetch performer data (short DB connection)
2. Fetch images from external APIs (no DB connection)
3. Save results to database (short DB connection)

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
from dataclasses import dataclass
import time

# Third-party imports
from bs4 import BeautifulSoup

# Import our database utilities
from db_utils import (
    get_db_connection,
    find_performer_by_name,
    find_performer_by_id,
    update_performer_external_references,
    get_performer_images
)

# Import Wikipedia utilities with caching
from wiki_utils import WikipediaSearcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ImageData:
    """Data class for image information."""
    url: str
    source: str
    thumbnail_url: Optional[str] = None
    source_identifier: Optional[str] = None
    source_page_url: Optional[str] = None
    license_type: Optional[str] = None
    license_url: Optional[str] = None
    attribution: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class ImageFetcher:
    """Handles fetching images from various sources."""
    
    def __init__(self, dry_run: bool = False, debug: bool = False, force_refresh: bool = False):
        self.dry_run = dry_run
        self.debug = debug
        self.force_refresh = force_refresh
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'JazzReferenceApp/1.0 (Educational; Contact: support@jazzreference.app)'
        })
        
        # Initialize Wikipedia searcher with caching
        self.wiki_searcher = WikipediaSearcher(
            cache_dir='cache/wikipedia',
            cache_days=7,
            force_refresh=force_refresh
        )
        
        if debug:
            logger.setLevel(logging.DEBUG)
    
    def fetch_wikipedia_image(self, artist_name: str, wikipedia_url: Optional[str] = None) -> Optional[ImageData]:
        """
        Fetch image from Wikipedia for an artist.
        
        Args:
            artist_name: Name of the artist to search for
            wikipedia_url: Optional Wikipedia URL from database (skips search if provided)
        
        Returns:
            ImageData object or None
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
                # API didn't return image - try HTML scraping fallback
                logger.debug(f"No image from pageimages API, trying HTML scraping fallback...")
                page_url = page.get('fullurl', f"https://en.wikipedia.org/wiki/{quote(page_title)}")
                return self._scrape_wikipedia_page_for_image(page_title, page_url, artist_name)
            
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
            
            image_data = ImageData(
                url=image_url,
                thumbnail_url=thumbnail_url,
                source='wikipedia',
                source_identifier=page_title,
                source_page_url=page_url,
                license_type=license_type_normalized,
                license_url=license_url,
                attribution=attribution,
                width=width,
                height=height
            )
            
            logger.info(f"✓ Found Wikipedia image: {image_url}")
            logger.debug(f"Image details: {image_data}")
            
            return image_data
            
        except requests.RequestException as e:
            logger.error(f"Error fetching from Wikipedia: {e}")
            if self.debug:
                logger.exception(e)
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching Wikipedia image: {e}")
            if self.debug:
                logger.exception(e)
            return None
    
    def fetch_discogs_image(self, artist_name: str) -> Optional[ImageData]:
        """
        Fetch image from Discogs for an artist.
        
        Args:
            artist_name: Name of the artist to search for
        
        Returns:
            ImageData object or None
        """
        # Placeholder - Discogs requires authentication
        logger.debug(f"Discogs image fetch not yet implemented for {artist_name}")
        return None
    
    def _normalize_license(self, license_str: str) -> str:
        """
        Normalize license type to standard values.
        
        Args:
            license_str: Raw license string
        
        Returns:
            Normalized license type
        """
        if not license_str or license_str == 'unknown':
            return 'unknown'
        
        license_lower = license_str.lower()
        
        if 'public domain' in license_lower or 'pd' in license_lower:
            return 'public_domain'
        elif 'cc0' in license_lower:
            return 'cc0'
        elif 'cc-by-sa' in license_lower or 'cc by-sa' in license_lower:
            return 'cc_by_sa'
        elif 'cc-by' in license_lower or 'cc by' in license_lower:
            return 'cc_by'
        elif 'fair use' in license_lower:
            return 'fair_use'
        else:
            return 'other'
    
    def _scrape_wikipedia_page_for_image(self, page_title: str, page_url: str, 
                                         artist_name: str) -> Optional[ImageData]:
        """
        Scrape Wikipedia page HTML to find images in the infobox.
        This is a fallback when the pageimages API doesn't return an image.
        
        Args:
            page_title: Wikipedia page title
            page_url: Full Wikipedia page URL
            artist_name: Artist name (for logging)
        
        Returns:
            ImageData object or None
        """
        try:
            logger.debug(f"Scraping page HTML: {page_url}")
            
            # Fetch the page HTML (using cache if available)
            html_content = self.wiki_searcher._fetch_wikipedia_page(page_url)
            
            if not html_content:
                logger.info(f"Failed to fetch Wikipedia page for {artist_name}")
                return None
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for image in the infobox
            infobox = soup.find('table', {'class': 'infobox'})
            if not infobox:
                logger.debug("No infobox found on page")
                logger.info(f"No image found on Wikipedia page for {artist_name}")
                return None
            
            # Find the first image in the infobox
            img_tag = infobox.find('img')
            if not img_tag or not img_tag.get('src'):
                logger.debug("No image found in infobox")
                logger.info(f"No image found on Wikipedia page for {artist_name}")
                return None
            
            # Extract image URL
            img_src = img_tag.get('src')
            if img_src.startswith('//'):
                img_src = 'https:' + img_src
            elif img_src.startswith('/'):
                img_src = 'https://en.wikipedia.org' + img_src
            
            logger.debug(f"Found image in infobox: {img_src}")
            
            # Get the full-resolution image URL
            # Wikipedia thumbnail URLs: .../thumb/.../filename.jpg/220px-filename.jpg
            # We want the original: .../filename.jpg
            full_img_url = img_src
            if '/thumb/' in img_src:
                # Remove /thumb/ and size suffix to get original
                full_img_url = re.sub(r'/thumb/', '/', img_src)
                # Extract actual filename and rebuild URL
                match = re.search(r'/([^/]+)$', img_src)
                if match:
                    filename = match.group(1)
                    # Remove size prefix like "220px-"
                    filename = re.sub(r'^\d+px-', '', filename)
                    full_img_url = re.sub(r'/[^/]+$', '/' + filename, full_img_url)
            
            logger.debug(f"Full resolution URL: {full_img_url}")
            
            # Extract image filename for license lookup
            image_filename = full_img_url.split('/')[-1]
            
            # Try to get license information via API
            api_url = "https://en.wikipedia.org/w/api.php"
            license_params = {
                'action': 'query',
                'format': 'json',
                'titles': f'File:{image_filename}',
                'prop': 'imageinfo',
                'iiprop': 'extmetadata|size|url'
            }
            
            license_type = 'unknown'
            license_url = None
            attribution = None
            width = img_tag.get('width')
            height = img_tag.get('height')
            
            try:
                response = self.session.get(api_url, params=license_params, timeout=10)
                response.raise_for_status()
                license_data = response.json()
                
                if license_data.get('query', {}).get('pages'):
                    file_page = next(iter(license_data['query']['pages'].values()))
                    if 'imageinfo' in file_page and file_page['imageinfo']:
                        imageinfo = file_page['imageinfo'][0]
                        
                        # Use the full URL from the API if available
                        if 'url' in imageinfo:
                            full_img_url = imageinfo['url']
                            logger.debug(f"Updated to API URL: {full_img_url}")
                        
                        # Extract metadata
                        extmetadata = imageinfo.get('extmetadata', {})
                        
                        if 'License' in extmetadata:
                            license_type = extmetadata['License'].get('value', 'unknown')
                        if 'LicenseUrl' in extmetadata:
                            license_url = extmetadata['LicenseUrl'].get('value')
                        if 'Artist' in extmetadata:
                            attribution = extmetadata['Artist'].get('value')
                        elif 'Credit' in extmetadata:
                            attribution = extmetadata['Credit'].get('value')
                        
                        # Get dimensions
                        if 'width' in imageinfo:
                            width = imageinfo['width']
                        if 'height' in imageinfo:
                            height = imageinfo['height']
            except Exception as e:
                logger.debug(f"Could not fetch license info: {e}")
            
            # Normalize license type
            license_type_normalized = self._normalize_license(license_type)
            
            image_data = ImageData(
                url=full_img_url,
                thumbnail_url=img_src,
                source='wikipedia',
                source_identifier=page_title,
                source_page_url=page_url,
                license_type=license_type_normalized,
                license_url=license_url,
                attribution=attribution,
                width=width,
                height=height
            )
            
            logger.info(f"✓ Found Wikipedia image via HTML scraping: {full_img_url}")
            logger.debug(f"Image details: {image_data}")
            
            return image_data
            
        except Exception as e:
            logger.error(f"Error scraping Wikipedia page for image: {e}")
            if self.debug:
                logger.exception(e)
            logger.info(f"No image found on Wikipedia page for {artist_name}")
            return None


class ImageDatabaseManager:
    """Handles database operations for images - separated from API fetching."""
    
    def __init__(self, dry_run: bool = False, debug: bool = False):
        self.dry_run = dry_run
        self.debug = debug
    
    def get_existing_images(self, performer_id: str) -> List[Dict[str, Any]]:
        """
        Get existing images for a performer.
        Uses a short-lived database connection.
        
        Args:
            performer_id: UUID of the performer
        
        Returns:
            List of existing image records
        """
        try:
            existing_images = get_performer_images(performer_id)
            if existing_images:
                logger.info(f"Performer already has {len(existing_images)} image(s)")
                for img in existing_images:
                    logger.info(f"  - {img['source']}: {img['url']}")
            return existing_images or []
        except Exception as e:
            logger.error(f"Error getting existing images: {e}")
            if self.debug:
                logger.exception(e)
            return []
    
    def is_duplicate_image(self, performer_id: str, image_url: str) -> bool:
        """
        Check if an image URL is already associated with this performer.
        
        Args:
            performer_id: UUID of the performer
            image_url: URL of the image to check
        
        Returns:
            True if this image is already linked to this performer, False otherwise
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Check if this URL is already linked to this performer
                    query = """
                        SELECT 1 
                        FROM images i
                        JOIN artist_images ai ON i.id = ai.image_id
                        WHERE ai.performer_id = %s AND i.url = %s
                        LIMIT 1
                    """
                    cur.execute(query, (performer_id, image_url))
                    result = cur.fetchone()
                    return result is not None
        except Exception as e:
            logger.error(f"Error checking for duplicate image: {e}")
            if self.debug:
                logger.exception(e)
            # On error, assume it's not a duplicate to avoid blocking new images
            return False
    
    def save_image(self, performer_id: str, image_data: ImageData, 
                   is_primary: bool = False, display_order: int = 0) -> bool:
        """
        Save an image to the database with a short-lived connection.
        Skips saving if the image is already linked to this performer.
        
        Args:
            performer_id: UUID of the performer
            image_data: ImageData object containing image information
            is_primary: Whether this is the primary image
            display_order: Display order for the image
        
        Returns:
            True if saved successfully, False if duplicate or error
        """
        # First check if this is a duplicate
        if self.is_duplicate_image(performer_id, image_data.url):
            logger.info(f"⊘ Image already linked to performer, skipping: {image_data.url}")
            return False
        
        if self.dry_run:
            logger.info(f"[DRY RUN] Would save image: {image_data.url}")
            logger.info(f"  Source: {image_data.source}")
            logger.info(f"  Primary: {is_primary}, Order: {display_order}")
            return True
        
        try:
            # Use a short-lived connection just for this operation
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Check if image URL already exists in images table
                    check_query = "SELECT id FROM images WHERE url = %s"
                    cur.execute(check_query, (image_data.url,))
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
                            image_data.url,
                            image_data.source,
                            image_data.source_identifier,
                            image_data.license_type,
                            image_data.license_url,
                            image_data.attribution,
                            image_data.width,
                            image_data.height,
                            image_data.thumbnail_url,
                            image_data.source_page_url
                        ))
                        image_id = cur.fetchone()['id']
                        logger.info(f"✓ Inserted new image: {image_id}")
                    
                    # Check if relationship already exists (extra safety check)
                    check_rel_query = """
                        SELECT 1 FROM artist_images 
                        WHERE performer_id = %s AND image_id = %s
                    """
                    cur.execute(check_rel_query, (performer_id, image_id))
                    
                    if cur.fetchone():
                        logger.info(f"⊘ Image already linked to performer (shouldn't happen - duplicate check failed)")
                        return False
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
                    
                    # Commit happens automatically when exiting context
                    return True
            
            # Connection is now closed
                    
        except Exception as e:
            logger.error(f"Error saving image to database: {e}")
            if self.debug:
                logger.exception(e)
            return False
    
    def update_external_references(self, performer_id: str, 
                                   external_refs: Dict[str, str]) -> bool:
        """
        Update performer external references.
        Uses a short-lived database connection.
        
        Args:
            performer_id: UUID of the performer
            external_refs: Dictionary of external reference data
        
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            update_performer_external_references(performer_id, external_refs, self.dry_run)
            return True
        except Exception as e:
            logger.error(f"Error updating external references: {e}")
            if self.debug:
                logger.exception(e)
            return False


def process_performer(performer: Dict[str, Any], fetcher: ImageFetcher, 
                     db_manager: ImageDatabaseManager) -> int:
    """
    Process a single performer: fetch images and save to database.
    This function clearly separates API calls from database operations.
    
    Args:
        performer: Performer record from database
        fetcher: ImageFetcher instance for API calls
        db_manager: ImageDatabaseManager for database operations
    
    Returns:
        Number of new images added
    """
    performer_id = str(performer['id'])
    performer_name = performer['name']
    images_added = 0
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Fetching images for: {performer_name}")
    logger.info(f"{'='*60}")
    
    # STEP 1: Get existing images (short DB connection)
    existing_images = db_manager.get_existing_images(performer_id)
    
    # STEP 2: Fetch images from external APIs (NO database connection)
    external_links = performer.get('external_links') or {}
    wikipedia_url = external_links.get('wikipedia')
    
    # Fetch Wikipedia image
    wiki_image = fetcher.fetch_wikipedia_image(performer_name, wikipedia_url=wikipedia_url)
    
    # Fetch Discogs image
    discogs_image = fetcher.fetch_discogs_image(performer_name)
    
    # STEP 3: Save results to database (short DB connections for each operation)
    if wiki_image:
        # Update external references if we got Wikipedia data
        external_refs = {}
        if wiki_image.source_identifier:
            external_refs['wikipedia_title'] = wiki_image.source_identifier
        if wiki_image.source_page_url:
            external_refs['wikipedia_url'] = wiki_image.source_page_url
        
        if external_refs:
            db_manager.update_external_references(performer_id, external_refs)
        
        # Save the image (will skip if duplicate)
        if db_manager.save_image(performer_id, wiki_image, 
                                is_primary=not existing_images, display_order=0):
            images_added += 1
    
    if discogs_image:
        if db_manager.save_image(performer_id, discogs_image, 
                                is_primary=False, display_order=1):
            images_added += 1
    
    logger.info(f"\n{'='*60}")
    logger.info(f"✓ Added {images_added} new image(s) for {performer_name}")
    logger.info(f"{'='*60}\n")
    
    return images_added


def get_all_performers() -> List[Dict[str, Any]]:
    """
    Get all performers from the database.
    Uses a short-lived connection.
    
    Returns:
        List of performer records
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, biography, birth_date, death_date, external_links
                FROM performers
                ORDER BY name
            """)
            performers = cur.fetchall()
    # Connection is now closed
    return performers


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
    
    # Force refresh Wikipedia pages (bypass cache)
    python fetch_artist_images.py --name "Miles Davis" --force-refresh
    
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
    parser.add_argument('--force-refresh', action='store_true',
                       help='Bypass Wikipedia cache and fetch fresh data from Wikipedia')
    
    args = parser.parse_args()
    
    # Create fetcher and database manager
    fetcher = ImageFetcher(dry_run=args.dry_run, debug=args.debug, force_refresh=args.force_refresh)
    db_manager = ImageDatabaseManager(dry_run=args.dry_run, debug=args.debug)
    
    if args.force_refresh:
        logger.info("*** FORCE REFRESH MODE - Bypassing Wikipedia cache ***")
    
    # Determine which performers to process
    performers = []
    
    if args.name:
        logger.info(f"Searching for performer: {args.name}")
        # Short DB connection to find performer
        performer = find_performer_by_name(args.name)
        if not performer:
            logger.error(f"Performer not found: {args.name}")
            sys.exit(1)
        performers = [performer]
        logger.info(f"Found performer: {performer['name']} (ID: {performer['id']})")
    elif args.id:
        logger.info(f"Looking up performer ID: {args.id}")
        # Short DB connection to find performer
        performer = find_performer_by_id(args.id)
        if not performer:
            logger.error(f"Performer not found with ID: {args.id}")
            sys.exit(1)
        performers = [performer]
        logger.info(f"Found performer: {performer['name']} (ID: {performer['id']})")
    else:
        # Process all performers - short DB connection to get list
        logger.info("No specific performer specified - processing all performers")
        performers = get_all_performers()
        logger.info(f"Found {len(performers)} performers to process")
    
    # Process each performer
    # Note: Each call to process_performer() uses separate short-lived connections
    total_images_added = 0
    for i, performer in enumerate(performers, 1):
        logger.info(f"\nProcessing performer {i}/{len(performers)}")
        
        images_added = process_performer(performer, fetcher, db_manager)
        total_images_added += images_added
        
        # Add delay between performers to be respectful to APIs
        if len(performers) > 1 and i < len(performers):
            logger.debug(f"Waiting 2 seconds before next performer...")
            time.sleep(2.0)
    
    if total_images_added > 0:
        logger.info(f"\n✓ Success! Added {total_images_added} image(s) across {len(performers)} performer(s)")
    else:
        logger.info(f"\n✓ No new images added")
    
    sys.exit(0)


if __name__ == '__main__':
    main()