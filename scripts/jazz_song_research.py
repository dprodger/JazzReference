#!/usr/bin/env python3
"""
Jazz Song Research Tool - Database Version
Searches for jazz song information and imports directly into the database

Same research logic as jazz_song_research.py, but writes directly to database
instead of generating JSON and SQL output.
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
sys.path.insert(0, str(Path(__file__).parent))
from db_utils import get_db_connection
from mb_utils import MusicBrainzSearcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def normalize_apostrophes(text):
    """
    Normalize various apostrophe characters to the correct Unicode apostrophe (').
    
    This function can be extracted to a utilities module for reuse across scripts.
    
    Args:
        text: String that may contain various apostrophe characters
        
    Returns:
        String with all apostrophes normalized to U+2019 (')
    """
    if not text:
        return text
    
    # Map of apostrophe variants to the correct Unicode apostrophe
    apostrophe_variants = {
        "'": "'",  # U+0027 (straight apostrophe) -> U+2019
        "`": "'",  # U+0060 (backtick/grave accent) -> U+2019
        "´": "'",  # U+00B4 (acute accent) -> U+2019
        "'": "'",  # U+2018 (left single quotation mark) -> U+2019
        "‛": "'",  # U+201B (single high-reversed-9 quotation mark) -> U+2019
    }
    
    result = text
    for variant, correct in apostrophe_variants.items():
        result = result.replace(variant, correct)
    
    return result


class JazzSongResearcher:
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
        # Initialize MusicBrainz searcher
        self.mb_searcher = MusicBrainzSearcher()
    
    def normalize_song_name_for_url(self, song_name):
        """Convert song name to JazzStandards.com URL format"""
        name = song_name.lower()
        name = re.sub(r'^(a|an|the)\s+', '', name)
        name = re.sub(r'[\'"\(\),\.]', '', name)
        name = re.sub(r'\s+', '', name)
        name = re.sub(r'[^\w]', '', name)
        return name
    
    def search_jazzstandards_com(self, song_name):
        """Search JazzStandards.com for song information"""
        logger.info(f"Searching JazzStandards.com for: {song_name}")
        
        normalized_name = self.normalize_song_name_for_url(song_name)
        first_char = normalized_name[0] if normalized_name else 'a'
        
        possible_urls = [
            f"https://www.jazzstandards.com/compositions-{first_char}/{normalized_name}.htm",
            f"https://www.jazzstandards.com/compositions/{normalized_name}.htm",
            f"https://www.jazzstandards.com/compositions-0/{normalized_name}.htm",
        ]
        
        for url in possible_urls:
            try:
                time.sleep(1)
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    logger.info(f"✓ Found page: {url}")
                    return self.parse_jazzstandards_page(response.text, url)
                    
            except Exception as e:
                logger.debug(f"Tried {url}: {e}")
                continue
        
        logger.warning("Could not find song on JazzStandards.com")
        return None
    
    def parse_jazzstandards_page(self, html_content, url):
        """Parse JazzStandards.com page"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = {
            'url': url,
            'composer': None,
            'year': None,
            'description': None,
            'recommended_recordings': []
        }
        
        text_content = soup.get_text()
        
        # Extract composer
        composer_patterns = [
            (r'Music by ([^,\n<]+)', 'composer'),
            (r'Composed by ([^,\n<]+)', 'composer'),
        ]
        
        for pattern, role in composer_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                result['composer'] = match.group(1).strip()
                break
        
        # Extract year
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', text_content)
        if year_match:
            result['year'] = int(year_match.group(1))
        
        # Look for recommendations
        recommendations_section = soup.find(
            string=re.compile(r'Recommendations?\s+for\s+this\s+Tune', re.IGNORECASE)
        )
        
        if recommendations_section:
            parent = recommendations_section.find_parent()
            if parent:
                recordings = self.extract_recommendations(parent)
                result['recommended_recordings'] = recordings
        
        # Alternative extraction
        if not result['recommended_recordings']:
            result['recommended_recordings'] = self.extract_recordings_alternative(soup)
        
        # Get description
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            text = p.get_text().strip()
            if len(text) > 100:
                result['description'] = text[:500]
                break
        
        return result
    
    def extract_recommendations(self, parent_element):
        """Extract recommended recordings"""
        recordings = []
        text = parent_element.get_text()
        
        pattern = r'([A-Z][^-\n]+?)\s*[-–]\s*([^(\n]+?)\s*\((\d{4})\)'
        matches = re.finditer(pattern, text)
        
        for match in matches:
            artist = match.group(1).strip()
            album = match.group(2).strip()
            year = match.group(3).strip()
            
            if len(artist) > 2 and len(album) > 2:
                recordings.append({
                    'artist': artist,
                    'album': album,
                    'year': int(year) if year.isdigit() else None,
                    'is_recommended': True
                })
        
        return recordings[:10]
    
    def extract_recordings_alternative(self, soup):
        """Alternative method to extract recordings"""
        recordings = []
        bold_elements = soup.find_all(['b', 'strong'])
        
        for bold in bold_elements:
            artist = bold.get_text().strip()
            next_text = ''
            next_sibling = bold.next_sibling
            
            if next_sibling:
                if isinstance(next_sibling, str):
                    next_text = next_sibling
                elif hasattr(next_sibling, 'get_text'):
                    next_text = next_sibling.get_text()
            
            if next_text:
                match = re.search(r'[–-]\s*([^(]+?)\s*\((\d{4})\)', next_text)
                if match:
                    album = match.group(1).strip()
                    year = match.group(2).strip()
                    
                    if len(artist) > 2 and len(album) > 2:
                        recordings.append({
                            'artist': artist,
                            'album': album,
                            'year': int(year) if year.isdigit() else None,
                            'is_recommended': True
                        })
        
        return recordings[:10]
    
    def research_song(self, song_name):
        """Main research function - same output as original"""
        web_data = self.search_jazzstandards_com(song_name)
        
        if not web_data:
            return {
                'song': {
                    'title': song_name,
                    'composer': None,
                    'structure': None,
                    'external_references': {},
                    'notes': None
                },
                'performers': [],
                'recordings': []
            }
        
        # Build external references
        external_refs = {}
        if web_data.get('url'):
            external_refs['jazzstandards_url'] = web_data['url']
        
        # Extract unique performers from recordings
        performers_dict = {}
        for recording in web_data.get('recommended_recordings', []):
            if recording.get('artist'):
                name = recording['artist']
                if name not in performers_dict:
                    performers_dict[name] = {
                        'name': name,
                        'instrument': None
                    }
        
        return {
            'song': {
                'title': song_name,
                'composer': web_data.get('composer'),
                'structure': None,
                'external_references': external_refs,
                'notes': web_data.get('description')
            },
            'performers': list(performers_dict.values())[:10],
            'recordings': web_data.get('recommended_recordings', [])[:5]
        }
    
    def import_to_database(self, song_name):
        """Research and import directly to database"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: {song_name}")
        logger.info(f"{'='*60}\n")
        
        # Do the research
        data = self.research_song(song_name)
        song = data['song']
        performers = data.get('performers', [])
        recordings = data.get('recordings', [])
        
        if self.dry_run:
            logger.info("[DRY RUN] Would import the following:")
            logger.info(f"Song: {song['title']}")
            logger.info(f"Composer: {song.get('composer', 'Unknown')}")
            logger.info(f"Performers: {len(performers)}")
            logger.info(f"Recordings: {len(recordings)}")
            
            if not recordings:
                logger.warning("No recordings found - only song metadata would be imported")
            
            return True
        
        # Warn if no data found
        if not recordings and not song.get('composer'):
            logger.warning(f"No data found on JazzStandards.com for: {song_name}")
            logger.warning("Song will be inserted with title only")
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Insert song
                    title = song['title']
                    composer = song.get('composer')
                    structure = song.get('structure')
                    ext_refs = json.dumps(song.get('external_references', {}))
                    
                    cur.execute("""
                        INSERT INTO songs (title, composer, structure, external_references)
                        SELECT %s, %s, %s, %s::jsonb
                        WHERE NOT EXISTS (
                            SELECT 1 FROM songs WHERE title = %s
                        )
                    """, (title, composer, structure, ext_refs, title))
                    
                    if cur.rowcount > 0:
                        logger.info(f"✓ Inserted song: {title}")
                    else:
                        logger.info(f"  Song already exists: {title}")
                    
                    # Get song ID
                    cur.execute("SELECT id FROM songs WHERE title = %s", (title,))
                    song_result = cur.fetchone()
                    if not song_result:
                        logger.error(f"Could not find song: {title}")
                        return False
                    song_id = song_result['id']
                    
                    # Always search for MusicBrainz ID
                    logger.info(f"Searching for MusicBrainz ID...")
                    mb_id = self.mb_searcher.search_musicbrainz_work(title, composer)
                    
                    if mb_id:
                        cur.execute("""
                            UPDATE songs
                            SET musicbrainz_id = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (mb_id, song_id))
                        conn.commit()
                        logger.info(f"✓ Added MusicBrainz ID: {mb_id}")
                    else:
                        logger.info(f"  No MusicBrainz match found")
                    
                    # Insert performers
                    for performer in performers:
                        name = performer['name']
                        
                        cur.execute("""
                            INSERT INTO performers (name)
                            SELECT %s
                            WHERE NOT EXISTS (
                                SELECT 1 FROM performers WHERE name = %s
                            )
                        """, (name, name))
                        
                        if cur.rowcount > 0:
                            logger.info(f"✓ Created performer: {name}")
                    
                    # Insert recordings
                    for recording in recordings:
                        album = recording.get('album')
                        artist = recording.get('artist')
                        year = recording.get('year')
                        is_canonical = recording.get('is_recommended', False)
                        
                        # Check if recording exists
                        cur.execute("""
                            SELECT id FROM recordings
                            WHERE song_id = %s AND album_title = %s
                        """, (song_id, album))
                        
                        if cur.fetchone():
                            logger.debug(f"  Recording already exists: {album}")
                            continue
                        
                        # Insert recording
                        cur.execute("""
                            INSERT INTO recordings 
                            (song_id, album_title, recording_year, is_canonical)
                            VALUES (%s, %s, %s, %s)
                            RETURNING id
                        """, (song_id, album, year, is_canonical))
                        
                        recording_result = cur.fetchone()
                        if recording_result:
                            recording_id = recording_result['id']
                            logger.info(f"✓ Added recording: {album}")
                            
                            # Link performer to recording
                            if artist:
                                cur.execute("""
                                    SELECT id FROM performers WHERE name = %s
                                """, (artist,))
                                
                                performer_result = cur.fetchone()
                                if performer_result:
                                    performer_id = performer_result['id']
                                    
                                    cur.execute("""
                                        INSERT INTO recording_performers 
                                        (recording_id, performer_id, role)
                                        SELECT %s, %s, 'leader'
                                        WHERE NOT EXISTS (
                                            SELECT 1 FROM recording_performers
                                            WHERE recording_id = %s 
                                            AND performer_id = %s
                                        )
                                    """, (recording_id, performer_id, recording_id, performer_id))
                                    
                                    logger.debug(f"  Linked performer: {artist}")
            
            logger.info(f"\n✓ Successfully imported: {song_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error importing to database: {e}", exc_info=True)
            return False


def main():
    parser = argparse.ArgumentParser(
        description='Research jazz songs and import to database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python jazz_song_research.py --name "Take Five"
  python jazz_song_research.py --name "Blue in Green" --dry-run
  python jazz_song_research.py --name "Autumn Leaves" --debug
        """
    )
    
    parser.add_argument('--name', required=True, help='Song name')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be imported without making changes')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Normalize apostrophes in song name
    song_name = normalize_apostrophes(args.name)
    
    researcher = JazzSongResearcher(dry_run=args.dry_run)
    
    try:
        success = researcher.import_to_database(song_name)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nCancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()