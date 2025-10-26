#!/usr/bin/env python3
"""
Load Artist Information from Wikipedia
Extracts birth date, death date, and biography from Wikipedia for artists in the database
"""

import sys
import argparse
import logging
import os
import json
import re
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

# Local imports
from db_utils import get_db_connection
from wiki_utils import WikipediaSearcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('log/load_artist_from_wikipedia.log')
    ]
)
logger = logging.getLogger(__name__)


class WikipediaArtistLoader:
    """Load artist biographical information from Wikipedia"""
    
    def __init__(self, dry_run=False):
        """
        Initialize loader
        
        Args:
            dry_run: If True, show what would be done without making changes
        """
        self.dry_run = dry_run
        self.wiki_searcher = WikipediaSearcher()
        self.stats = {
            'artists_processed': 0,
            'artists_updated': 0,
            'artists_skipped': 0,
            'errors': 0,
            'net_new': 0,
            'exact_matches': 0,
            'overwrites': 0
        }
        
        # For tracking overwrites in dry-run mode
        self.overwrites = []
        
    def get_artist_by_id(self, artist_id):
        """Get artist by database ID"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, birth_date, death_date, biography, external_links
                    FROM performers
                    WHERE id = %s
                """, (artist_id,))
                
                return cur.fetchone()
    
    def get_artist_by_name(self, artist_name):
        """Get artist by name"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, birth_date, death_date, biography, external_links
                    FROM performers
                    WHERE LOWER(name) = LOWER(%s)
                """, (artist_name,))
                
                return cur.fetchone()
    
    def get_all_artists_with_wikipedia(self):
        """Get all artists that have a Wikipedia URL"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, birth_date, death_date, biography, external_links
                    FROM performers
                    WHERE external_links->>'wikipedia' IS NOT NULL
                    AND external_links->>'wikipedia' != ''
                    ORDER BY name
                """)
                
                return cur.fetchall()
    
    def extract_wikipedia_url(self, external_links):
        """Extract Wikipedia URL from external_links JSON"""
        if not external_links:
            return None
        
        # external_links is already a dict if using dict_row
        if isinstance(external_links, dict):
            return external_links.get('wikipedia')
        
        return None
    
    def extract_birth_death_dates(self, soup):
        """
        Extract birth and death dates from Wikipedia infobox
        
        Args:
            soup: BeautifulSoup object of Wikipedia page
            
        Returns:
            tuple: (birth_date, death_date) as strings in YYYY-MM-DD format or None
        """
        birth_date = None
        death_date = None
        
        # Find the infobox
        infobox = soup.find('table', {'class': 'infobox'})
        if not infobox:
            logger.debug("  No infobox found")
            return (None, None)
        
        # Look for birth date
        born_row = infobox.find('th', string=re.compile(r'Born', re.IGNORECASE))
        if born_row:
            born_cell = born_row.find_next_sibling('td')
            if born_cell:
                born_text = born_cell.get_text()
                logger.debug(f"  Found 'Born' text: {born_text[:100]}")
                birth_date = self.parse_date(born_text)
        
        # Look for death date
        died_row = infobox.find('th', string=re.compile(r'Died', re.IGNORECASE))
        if died_row:
            died_cell = died_row.find_next_sibling('td')
            if died_cell:
                died_text = died_cell.get_text()
                logger.debug(f"  Found 'Died' text: {died_text[:100]}")
                death_date = self.parse_date(died_text)
        
        return (birth_date, death_date)
    
    def parse_date(self, date_text):
        """
        Parse a date string from Wikipedia into YYYY-MM-DD format
        
        Args:
            date_text: Date text from Wikipedia (e.g., "May 26, 1926" or "1926-05-26")
            
        Returns:
            String in YYYY-MM-DD format, or None if parsing fails
        """
        original_text = date_text
        
        logger.debug(f"  Date parsing original: '{original_text[:200]}'")
        
        # FIRST: Try to find ISO format date in parentheses (Wikipedia often has this)
        # Example: "(1941-06-12)June 12, 1941"
        paren_iso_match = re.search(r'\((\d{4})-(\d{2})-(\d{2})\)', date_text)
        if paren_iso_match:
            result = f"{paren_iso_match.group(1)}-{paren_iso_match.group(2)}-{paren_iso_match.group(3)}"
            logger.debug(f"  Found ISO date in parentheses: '{result}'")
            return result
        
        # Remove parenthetical information and extra whitespace
        date_text = re.sub(r'\([^)]*\)', '', date_text)
        date_text = date_text.strip()
        
        logger.debug(f"  After removing parens: '{date_text[:200]}'")
        
        # Common patterns to try
        patterns = [
            # ISO format: "1926-05-26"
            (r'(\d{4})-(\d{2})-(\d{2})', lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}"),
            # Full date: "May 26, 1926" or "26 May 1926"
            (r'(\w+)\s+(\d{1,2}),?\s+(\d{4})', lambda m: f"{m.group(3)}-{self.month_to_num(m.group(1))}-{int(m.group(2)):02d}"),
            (r'(\d{1,2})\s+(\w+)\s+(\d{4})', lambda m: f"{m.group(3)}-{self.month_to_num(m.group(2))}-{int(m.group(1)):02d}"),
            # Year and month: "May 1926"
            (r'(\w+)\s+(\d{4})', lambda m: f"{m.group(2)}-{self.month_to_num(m.group(1))}-01"),
            # Just year: "1926"
            (r'^(\d{4})$', lambda m: f"{m.group(1)}-01-01"),
        ]
        
        for pattern, formatter in patterns:
            match = re.search(pattern, date_text)
            if match:
                try:
                    result = formatter(match)
                    logger.debug(f"  Matched pattern '{pattern}': groups={match.groups()}, result='{result}'")
                    return result
                except Exception as e:
                    logger.debug(f"  Failed to format date match: {e}")
                    continue
        
        logger.debug(f"  Could not parse date: '{date_text}'")
        return None
    
    def month_to_num(self, month_str):
        """Convert month name to number string"""
        months = {
            'january': '01', 'jan': '01',
            'february': '02', 'feb': '02',
            'march': '03', 'mar': '03',
            'april': '04', 'apr': '04',
            'may': '05',
            'june': '06', 'jun': '06',
            'july': '07', 'jul': '07',
            'august': '08', 'aug': '08',
            'september': '09', 'sep': '09', 'sept': '09',
            'october': '10', 'oct': '10',
            'november': '11', 'nov': '11',
            'december': '12', 'dec': '12'
        }
        return months.get(month_str.lower(), '01')
    
    def extract_biography(self, soup):
        """
        Extract biography from Wikipedia page (first few paragraphs)
        
        Args:
            soup: BeautifulSoup object of Wikipedia page
            
        Returns:
            String with biography text, or None
        """
        # Find the main content area - prefer mw-parser-output
        content_div = soup.find('div', {'class': 'mw-parser-output'})
        if not content_div:
            content_div = soup.find('div', {'id': 'mw-content-text'})
        
        if not content_div:
            logger.debug("  No content div found")
            return None
        
        logger.debug(f"  Found content div: {content_div.name}")
        
        # Get all paragraphs in the content area
        all_paragraphs = content_div.find_all('p')
        logger.debug(f"  Found {len(all_paragraphs)} total paragraph tags")
        
        # Get the first few substantial paragraphs
        paragraphs = []
        for i, p in enumerate(all_paragraphs):
            text = p.get_text().strip()
            
            # Debug first few paragraphs
            if i < 5:
                logger.debug(f"  P[{i}] length={len(text)}, text={text[:100]}...")
            
            # Skip very short paragraphs, coordinates, disambiguation notices, and empty paragraphs
            if (len(text) > 50 and 
                'coordinates' not in text.lower() and 
                'disambiguation' not in text.lower() and
                not text.startswith('This article') and
                not text.startswith('For other uses')):
                
                paragraphs.append(text)
                logger.debug(f"  Accepted paragraph {i}: {len(text)} chars")
                
                if len(paragraphs) >= 3:  # Get first 3 substantial paragraphs
                    break
        
        if not paragraphs:
            logger.debug("  No substantial paragraphs found after filtering")
            return None
        
        biography = '\n\n'.join(paragraphs)
        
        # Clean up the text
        biography = re.sub(r'\[\d+\]', '', biography)  # Remove citation numbers
        biography = re.sub(r'\s+', ' ', biography)  # Normalize whitespace
        biography = biography.strip()
        
        logger.debug(f"  Extracted biography ({len(biography)} chars, {len(paragraphs)} paragraphs)")
        return biography if biography else None
    
    def compare_values(self, old_val, new_val):
        """
        Compare old and new values
        
        Returns:
            'net-new': new value, no old value
            'match': values are the same
            'overwrite': values are different
        """
        if old_val is None and new_val is None:
            return 'match'
        elif old_val is None and new_val is not None:
            return 'net-new'
        elif old_val is not None and new_val is None:
            return 'match'  # Keep existing value
        else:
            # Convert to strings for comparison
            old_str = str(old_val).strip() if old_val else ''
            new_str = str(new_val).strip() if new_val else ''
            return 'match' if old_str == new_str else 'overwrite'
    
    def process_artist(self, artist):
        """
        Process a single artist
        
        Args:
            artist: Artist dict with id, name, birth_date, death_date, biography, external_links
            
        Returns:
            True if successful, False otherwise
        """
        try:
            artist_name = artist['name']
            artist_id = artist['id']
            
            logger.info(f"Processing: {artist_name}")
            self.stats['artists_processed'] += 1
            
            # Extract Wikipedia URL
            wiki_url = self.extract_wikipedia_url(artist['external_links'])
            if not wiki_url:
                logger.debug("  No Wikipedia URL found")
                self.stats['artists_skipped'] += 1
                return False
            
            logger.debug(f"  Wikipedia URL: {wiki_url}")
            
            # Fetch Wikipedia page
            html_content = self.wiki_searcher._fetch_wikipedia_page(wiki_url)
            if not html_content:
                logger.warning(f"  Failed to fetch Wikipedia page")
                self.stats['errors'] += 1
                return False
            
            # Parse the page
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract information
            logger.debug("  Extracting dates...")
            birth_date, death_date = self.extract_birth_death_dates(soup)
            
            logger.debug("  Extracting biography...")
            biography = self.extract_biography(soup)
            
            # Compare with existing values
            birth_status = self.compare_values(artist['birth_date'], birth_date)
            death_status = self.compare_values(artist['death_date'], death_date)
            bio_status = self.compare_values(artist['biography'], biography)
            
            logger.debug(f"  Birth date: {birth_status} ({artist['birth_date']} -> {birth_date})")
            logger.debug(f"  Death date: {death_status} ({artist['death_date']} -> {death_date})")
            logger.debug(f"  Biography: {bio_status}")
            
            # Track statistics
            if birth_status == 'net-new' or death_status == 'net-new' or bio_status == 'net-new':
                self.stats['net_new'] += 1
            if birth_status == 'match' and death_status == 'match' and bio_status == 'match':
                self.stats['exact_matches'] += 1
            if birth_status == 'overwrite' or death_status == 'overwrite' or bio_status == 'overwrite':
                self.stats['overwrites'] += 1
                
                # Log overwrite details
                overwrite_info = {
                    'artist_id': str(artist_id),
                    'artist_name': artist_name,
                    'wikipedia_url': wiki_url,
                    'birth_date': {
                        'old': str(artist['birth_date']) if artist['birth_date'] else None,
                        'new': birth_date
                    } if birth_status == 'overwrite' else None,
                    'death_date': {
                        'old': str(artist['death_date']) if artist['death_date'] else None,
                        'new': death_date
                    } if death_status == 'overwrite' else None,
                    'biography': {
                        'old': artist['biography'],
                        'new': biography
                    } if bio_status == 'overwrite' else None
                }
                self.overwrites.append(overwrite_info)
                
                if self.dry_run:
                    logger.debug(f"  [DRY RUN] Would overwrite data")
            
            # Update database if not in dry-run mode
            if not self.dry_run:
                self.update_artist(artist_id, birth_date, death_date, biography)
                self.stats['artists_updated'] += 1
            else:
                if birth_status != 'match' or death_status != 'match' or bio_status != 'match':
                    self.stats['artists_updated'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing {artist.get('name', 'unknown')}: {e}", exc_info=True)
            self.stats['errors'] += 1
            return False
    
    def update_artist(self, artist_id, birth_date, death_date, biography):
        """Update artist information in database"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Build update query dynamically based on what we have
                updates = []
                params = []
                
                if birth_date is not None:
                    updates.append("birth_date = %s")
                    params.append(birth_date)
                
                if death_date is not None:
                    updates.append("death_date = %s")
                    params.append(death_date)
                
                if biography is not None:
                    updates.append("biography = %s")
                    params.append(biography)
                
                if not updates:
                    logger.debug(f"  No updates to make for artist {artist_id}")
                    return
                
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(artist_id)
                
                query = f"""
                    UPDATE performers
                    SET {', '.join(updates)}
                    WHERE id = %s
                """
                
                logger.debug(f"  Executing update for artist {artist_id}")
                cur.execute(query, params)
                conn.commit()
    
    def save_overwrites_log(self):
        """Save overwrites to JSON log file"""
        if not self.overwrites:
            return
        
        log_dir = Path('log')
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f'wikipedia_overwrites_{timestamp}.json'
        
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'total_overwrites': len(self.overwrites),
                    'overwrites': self.overwrites
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Overwrites logged to: {log_file}")
        except Exception as e:
            logger.error(f"Failed to save overwrites log: {e}")
    
    def run(self, artist_name=None, artist_id=None):
        """
        Main processing method
        
        Args:
            artist_name: Optional specific artist name to process
            artist_id: Optional specific artist ID to process
        """
        logger.info("="*80)
        logger.info("LOAD ARTIST INFORMATION FROM WIKIPEDIA")
        logger.info("="*80)
        
        if self.dry_run:
            logger.info("*** DRY RUN MODE - No database changes will be made ***")
            logger.info("")
        
        # Get artists to process
        if artist_id:
            artist = self.get_artist_by_id(artist_id)
            if not artist:
                logger.error(f"Artist with ID {artist_id} not found")
                return False
            artists = [artist]
        elif artist_name:
            artist = self.get_artist_by_name(artist_name)
            if not artist:
                logger.error(f"Artist '{artist_name}' not found")
                return False
            artists = [artist]
        else:
            artists = self.get_all_artists_with_wikipedia()
        
        if not artists:
            logger.info("No artists to process!")
            return True
        
        logger.info(f"Found {len(artists)} artist(s) to process")
        logger.info("")
        
        # Process each artist
        for artist in artists:
            self.process_artist(artist)
        
        # Save overwrites log if in dry-run mode
        if self.dry_run and self.overwrites:
            self.save_overwrites_log()
        
        # Print summary
        self.print_summary()
        
        return True
    
    def print_summary(self):
        """Print processing summary"""
        logger.info("")
        logger.info("="*80)
        logger.info("PROCESSING SUMMARY")
        logger.info("="*80)
        logger.info(f"Artists processed:  {self.stats['artists_processed']}")
        logger.info(f"Artists updated:    {self.stats['artists_updated']}")
        logger.info(f"Artists skipped:    {self.stats['artists_skipped']}")
        logger.info(f"  - Net-new data:   {self.stats['net_new']}")
        logger.info(f"  - Exact matches:  {self.stats['exact_matches']}")
        logger.info(f"  - Overwrites:     {self.stats['overwrites']}")
        logger.info(f"Errors:             {self.stats['errors']}")
        logger.info("="*80)


def main():
    parser = argparse.ArgumentParser(
        description='Load artist biographical information from Wikipedia',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all artists with Wikipedia URLs
  python load_artist_from_wikipedia.py
  
  # Process a specific artist by name
  python load_artist_from_wikipedia.py --name "Miles Davis"
  
  # Process a specific artist by ID
  python load_artist_from_wikipedia.py --id "123e4567-e89b-12d3-a456-426614174000"
  
  # Dry run to see what would be changed
  python load_artist_from_wikipedia.py --dry-run
  
  # Enable debug logging
  python load_artist_from_wikipedia.py --debug
  
  # Combination
  python load_artist_from_wikipedia.py --name "John Coltrane" --dry-run --debug
        """
    )
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--name',
        help='Process a specific artist by name'
    )
    group.add_argument(
        '--id',
        help='Process a specific artist by database ID (UUID)'
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
    
    # Create loader and run
    loader = WikipediaArtistLoader(dry_run=args.dry_run)
    
    try:
        success = loader.run(artist_name=args.name, artist_id=args.id)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nProcess cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()