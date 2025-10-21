#!/usr/bin/env python3
"""
Jazz Song Information Gatherer - Enhanced Version with JazzStandards.com
Searches for detailed information about a jazz standard including recordings and performers
"""

import sys
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
from datetime import datetime
import time

class JazzSongResearcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def normalize_song_name_for_url(self, song_name):
        """Convert song name to JazzStandards.com URL format"""
        # Remove articles, apostrophes, and special characters
        name = song_name.lower()
        name = re.sub(r'^(a|an|the)\s+', '', name)
        name = re.sub(r'[\'"\(\),\.]', '', name)
        name = re.sub(r'\s+', '', name)
        name = re.sub(r'[^\w]', '', name)
        return name
    
    def search_jazzstandards_com(self, song_name):
        """
        Search JazzStandards.com for song information and recommended recordings
        """
        print(f"Searching JazzStandards.com for: {song_name}", file=sys.stderr)
        
        # Try to construct direct URL (JazzStandards.com uses lowercase, no spaces)
        normalized_name = self.normalize_song_name_for_url(song_name)
        
        # Try different directory patterns (they organize by first character)
        first_char = normalized_name[0] if normalized_name else 'a'
        # Map numbers to their word equivalents
        char_map = {
            '0': '0', '1': '1', '2': '2', '3': '3', '4': '4',
            '5': '5', '6': '6', '7': '7', '8': '8', '9': '9'
        }
        dir_num = char_map.get(first_char, first_char)
        
        possible_urls = [
            f"https://www.jazzstandards.com/compositions-{dir_num}/{normalized_name}.htm",
            f"https://www.jazzstandards.com/compositions/{normalized_name}.htm",
            f"https://www.jazzstandards.com/compositions-0/{normalized_name}.htm",
        ]
        
        for url in possible_urls:
            try:
                time.sleep(1)  # Be respectful
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    print(f"✓ Found page: {url}", file=sys.stderr)
                    return self.parse_jazzstandards_page(response.text, url)
                    
            except Exception as e:
                print(f"  Tried {url}: {e}", file=sys.stderr)
                continue
        
        print("✗ Could not find song on JazzStandards.com", file=sys.stderr)
        return None
    
    def parse_jazzstandards_page(self, html_content, url):
        """Parse JazzStandards.com page to extract information"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = {
            'url': url,
            'composer': None,
            'year': None,
            'description': None,
            'recommended_recordings': [],
            'musical_info': {}
        }
        
        # Extract composer information
        composer_patterns = [
            (r'Music by ([^,\n<]+)', 'composer'),
            (r'Lyrics by ([^,\n<]+)', 'lyricist'),
            (r'Composed by ([^,\n<]+)', 'composer'),
        ]
        
        text_content = soup.get_text()
        for pattern, role in composer_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                result[role] = match.group(1).strip()
        
        # Extract year
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', text_content)
        if year_match:
            result['year'] = int(year_match.group(1))
        
        # Look for "Recommendations for this Tune" section
        recommendations_section = soup.find(string=re.compile(r'Recommendations?\s+for\s+this\s+Tune', re.IGNORECASE))
        
        if recommendations_section:
            # Find the parent element and look for recording information
            parent = recommendations_section.find_parent()
            if parent:
                # Look for subsequent text or tables
                recordings = self.extract_recommendations(parent)
                result['recommended_recordings'] = recordings
        
        # Alternative: Look for any bold text followed by album/year info
        if not result['recommended_recordings']:
            result['recommended_recordings'] = self.extract_recordings_alternative(soup)
        
        # Extract key, tempo, form if available
        musical_terms = ['Key:', 'Form:', 'Tempo:', 'Time Signature:']
        for term in musical_terms:
            match = re.search(f'{term}\\s*([^\\n<]+)', text_content, re.IGNORECASE)
            if match:
                key = term.replace(':', '').lower().replace(' ', '_')
                result['musical_info'][key] = match.group(1).strip()
        
        # Get description (first substantial paragraph)
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            text = p.get_text().strip()
            if len(text) > 100:  # Substantial paragraph
                result['description'] = text[:500]
                break
        
        return result
    
    def extract_recommendations(self, parent_element):
        """Extract recommended recordings from JazzStandards.com recommendations section"""
        recordings = []
        
        # Look for patterns like: "Artist - Album (Year)"
        text = parent_element.get_text()
        
        # Pattern 1: Artist - Album (Year)
        pattern1 = r'([A-Z][^-\n]+?)\s*[-–]\s*([^(\n]+?)\s*\((\d{4})\)'
        matches = re.finditer(pattern1, text)
        for match in matches:
            artist = match.group(1).strip()
            album = match.group(2).strip()
            year = match.group(3).strip()
            
            if len(artist) > 2 and len(album) > 2:
                recordings.append({
                    'artist': artist,
                    'album': album,
                    'year': int(year) if year.isdigit() else None,
                    'source': 'jazzstandards.com',
                    'is_recommended': True
                })
        
        # Pattern 2: Look for table rows if structured differently
        if not recordings:
            # Try finding in lists or table structures
            for li in parent_element.find_all('li'):
                text = li.get_text()
                match = re.search(r'([^-\n]+?)\s*[-–]\s*([^(\n]+?)\s*\((\d{4})\)', text)
                if match:
                    recordings.append({
                        'artist': match.group(1).strip(),
                        'album': match.group(2).strip(),
                        'year': int(match.group(3)) if match.group(3).isdigit() else None,
                        'source': 'jazzstandards.com',
                        'is_recommended': True
                    })
        
        return recordings[:10]  # Limit to top 10
    
    def extract_recordings_alternative(self, soup):
        """Alternative method to extract recordings from page"""
        recordings = []
        
        # Look for bold text (artist names) followed by album info
        bold_elements = soup.find_all(['b', 'strong'])
        
        for bold in bold_elements:
            artist = bold.get_text().strip()
            
            # Get the next sibling text
            next_text = ''
            next_sibling = bold.next_sibling
            if next_sibling:
                if isinstance(next_sibling, str):
                    next_text = next_sibling
                else:
                    next_text = next_sibling.get_text()
            
            # Look for album and year in the next text
            album_match = re.search(r'[-–]\s*([^(\n]+?)\s*\((\d{4})\)', next_text)
            if album_match and len(artist) > 2:
                recordings.append({
                    'artist': artist,
                    'album': album_match.group(1).strip(),
                    'year': int(album_match.group(2)),
                    'source': 'jazzstandards.com',
                    'is_recommended': True
                })
        
        return recordings[:10]
    
    def search_wikipedia(self, song_name):
        """Search Wikipedia for song information"""
        search_url = f"https://en.wikipedia.org/w/api.php"
        params = {
            'action': 'query',
            'list': 'search',
            'srsearch': f'"{song_name}" jazz song',
            'format': 'json',
            'srlimit': 3
        }
        
        try:
            response = self.session.get(search_url, params=params)
            data = response.json()
            
            if data.get('query', {}).get('search'):
                page_title = data['query']['search'][0]['title']
                return self.get_wikipedia_page(page_title)
        except Exception as e:
            print(f"Wikipedia search error: {e}", file=sys.stderr)
        
        return None
    
    def get_wikipedia_page(self, page_title):
        """Get full Wikipedia page content"""
        url = f"https://en.wikipedia.org/w/api.php"
        params = {
            'action': 'query',
            'titles': page_title,
            'prop': 'extracts|info',
            'exintro': True,
            'explaintext': True,
            'inprop': 'url',
            'format': 'json'
        }
        
        try:
            response = self.session.get(url, params=params)
            data = response.json()
            pages = data.get('query', {}).get('pages', {})
            
            if pages:
                page = list(pages.values())[0]
                extract = page.get('extract', '')
                
                canonical_info = self.extract_canonical_recording(extract)
                
                return {
                    'title': page.get('title'),
                    'extract': extract,
                    'url': page.get('fullurl'),
                    'canonical_recording': canonical_info
                }
        except Exception as e:
            print(f"Wikipedia page error: {e}", file=sys.stderr)
        
        return None
    
    def extract_canonical_recording(self, text):
        """Extract information about canonical/famous recordings from text"""
        if not text:
            return None
        
        patterns = [
            r'(?:recorded|performed|version) by ([^,.\n]+?)(?:in|on|\(|,|\.)(\d{4})?',
            r'([A-Z][a-z]+ [A-Z][a-z]+)(?:\'s| (?:recorded|version|recording))',
            r'(?:album|recording) (?:by |with )?([^,.\n(]+)',
        ]
        
        recordings = []
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                artist = match.group(1).strip()
                year = match.group(2) if len(match.groups()) > 1 else None
                
                if len(artist) > 3 and not any(word in artist.lower() for word in ['the song', 'the tune', 'this']):
                    recordings.append({
                        'artist': artist,
                        'year': int(year) if year else None
                    })
        
        return recordings[:3] if recordings else None
    
    def search_musicbrainz_work(self, song_name, composer=None):
        """Search MusicBrainz for the work (composition) ID"""
        search_url = "https://musicbrainz.org/ws/2/work/"
        
        # Build query
        query_parts = [f'work:"{song_name}"']
        if composer:
            query_parts.append(f'artist:"{composer}"')
        
        params = {
            'query': ' AND '.join(query_parts),
            'fmt': 'json',
            'limit': 5
        }
        
        try:
            time.sleep(1)  # Be respectful with rate limiting
            response = self.session.get(search_url, params=params)
            if response.status_code == 200:
                data = response.json()
                works = data.get('works', [])
                
                if works:
                    # Return the first (best match) work
                    best_match = works[0]
                    return {
                        'work_id': best_match.get('id'),
                        'title': best_match.get('title'),
                        'type': best_match.get('type'),
                        'score': best_match.get('score', 0)
                    }
        except Exception as e:
            print(f"MusicBrainz work search error: {e}", file=sys.stderr)
        
        return None
        
    def search_musicbrainz_recordings(self, song_name):
        """Search MusicBrainz for actual recordings of the song (fallback)"""
        search_url = "https://musicbrainz.org/ws/2/recording/"
        params = {
            'query': f'recording:"{song_name}"',
            'fmt': 'json',
            'limit': 10
        }
        
        try:
            response = self.session.get(search_url, params=params)
            if response.status_code == 200:
                data = response.json()
                recordings = []
                
                for rec in data.get('recordings', [])[:5]:
                    album_title = None
                    if rec.get('releases'):
                        album_title = rec['releases'][0].get('title')
                    
                    recording_info = {
                        'musicbrainz_id': rec.get('id'), 
                        'title': album_title or rec.get('title'),
                        'artist': None,
                        'date': None,
                        'length': rec.get('length'),
                        'source': 'musicbrainz'
                    }
                    
                    if rec.get('artist-credit'):
                        artists = []
                        for artist in rec['artist-credit']:
                            if isinstance(artist, dict) and artist.get('artist'):
                                artists.append(artist['artist'].get('name'))
                        recording_info['artist'] = ', '.join(artists) if artists else None
                    
                    if rec.get('releases'):
                        for release in rec['releases']:
                            if release.get('date'):
                                recording_info['date'] = release['date'][:4]
                                break
                    
                    recordings.append(recording_info)
                
                return recordings
        except Exception as e:
            print(f"MusicBrainz recordings error: {e}", file=sys.stderr)
        
        return []
    
    def extract_composer_info(self, text):
        """Extract composer information from text"""
        if not text:
            return None
        
        patterns = [
            r'composed by ([^,.\n]+?)(?:\.|,|\n|and)',
            r'music by ([^,.\n]+?)(?:\.|,|\n|and)',
            r'written by ([^,.\n]+?)(?:\.|,|\n|and)',
            r'([^,.\n]+?) \(music\)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                composer = match.group(1).strip()
                composer = re.sub(r'\s+and\s+.*$', '', composer, flags=re.IGNORECASE)
                return composer
        
        return None
    
    def extract_year(self, text):
        """Extract year from text"""
        if not text:
            return None
        
        patterns = [
            r'(?:written|composed|recorded) in (\d{4})',
            r'\((\d{4})\)',
            r'\b(19\d{2})\b',
            r'\b(20\d{2})\b',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                year = int(match.group(1))
                if 1900 <= year <= 2025:
                    return year
        
        return None
    
    def parse_performers_from_text(self, text, year=None):
        """Extract performer names and try to identify instruments"""
        performers = []
        
        instrument_patterns = [
            (r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:on |plays? )?(?:the )?(trumpet|piano|bass|drums|saxophone|sax|guitar|trombone|clarinet|vibraphone|organ)', 'instrument_explicit'),
            (r'([A-Z][a-z]+ [A-Z][a-z]+),?\s+(trumpet|piano|bass|drums|saxophone|sax|guitar|trombone|clarinet|vibraphone|organ)(?:ist)?', 'instrument_suffix'),
        ]
        
        for pattern, pattern_type in instrument_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                name = match.group(1).strip()
                instrument = match.group(2).strip().lower()
                
                if 'sax' in instrument and instrument != 'saxophone':
                    instrument = 'saxophone'
                
                performers.append({
                    'name': name,
                    'instrument': instrument.capitalize(),
                    'year': year
                })
        
        return performers
    
    def research_song(self, song_name):
        """Main research function with JazzStandards.com priority"""
        print(f"Researching: {song_name}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        
        result = {
            'song_name': song_name,
            'sources': {},
            'extracted_data': {},
            'recordings': [],
            'performers': []
        }
        
        # PRIORITY: Search JazzStandards.com first
        print("Searching JazzStandards.com...", file=sys.stderr)
        js_data = self.search_jazzstandards_com(song_name)
        if js_data:
            result['sources']['jazzstandards'] = js_data
            print(f"✓ Found on JazzStandards.com", file=sys.stderr)
            
            # Prefer JazzStandards.com data
            if js_data.get('composer'):
                result['extracted_data']['composer'] = js_data['composer']
            if js_data.get('year'):
                result['extracted_data']['year'] = js_data['year']
            if js_data.get('description'):
                result['extracted_data']['description'] = js_data['description']
            if js_data.get('musical_info'):
                result['extracted_data']['musical_info'] = js_data['musical_info']
            
            # Add recommended recordings (these are canonical!)
            if js_data.get('recommended_recordings'):
                result['recordings'].extend(js_data['recommended_recordings'])
                print(f"✓ Found {len(js_data['recommended_recordings'])} recommended recordings", file=sys.stderr)
        else:
            print("✗ Not found on JazzStandards.com", file=sys.stderr)
        
        # Search Wikipedia as secondary source
        print("Searching Wikipedia...", file=sys.stderr)
        wiki_data = self.search_wikipedia(song_name)
        if wiki_data:
            result['sources']['wikipedia'] = wiki_data
            print(f"✓ Found Wikipedia article: {wiki_data.get('title')}", file=sys.stderr)
            
            extract = wiki_data.get('extract', '')
            
            # Only fill in missing data
            if not result['extracted_data'].get('composer'):
                result['extracted_data']['composer'] = self.extract_composer_info(extract)
            if not result['extracted_data'].get('year'):
                result['extracted_data']['year'] = self.extract_year(extract)
            if not result['extracted_data'].get('description'):
                result['extracted_data']['description'] = extract[:500] if extract else None
            
            if wiki_data.get('canonical_recording'):
                result['extracted_data']['canonical_recordings'] = wiki_data['canonical_recording']
            
            performers = self.parse_performers_from_text(extract, result['extracted_data'].get('year'))
            result['performers'].extend(performers)
        else:
            print("✗ No Wikipedia article found", file=sys.stderr)
        
        # Only use MusicBrainz if we don't have recordings from JazzStandards
        if not result['recordings']:
            print("Searching MusicBrainz for recordings (fallback)...", file=sys.stderr)
            mb_recordings = self.search_musicbrainz_recordings(song_name)
            if mb_recordings:
                result['recordings'] = mb_recordings
                print(f"✓ Found {len(mb_recordings)} MusicBrainz recordings", file=sys.stderr)
                
                for rec in mb_recordings:
                    if rec.get('artist'):
                        artists = [a.strip() for a in rec['artist'].split(',')]
                        for artist in artists:
                            if artist and len(artist) > 2:
                                result['performers'].append({
                                    'name': artist,
                                    'instrument': None,
                                    'year': rec.get('date')
                                })
            else:
                print("✗ No MusicBrainz recordings found", file=sys.stderr)
        
        # After searching other sources, add MusicBrainz work search
        print("Searching MusicBrainz for work ID...", file=sys.stderr)
        mb_work = self.search_musicbrainz_work(
            song_name, 
            result['extracted_data'].get('composer')
        )
        if mb_work:
            result['sources']['musicbrainz'] = mb_work
            print(f"✓ Found MusicBrainz Work: {mb_work['work_id']}", file=sys.stderr)

        result['structured_output'] = self.format_for_database(result)
        
        return result
    
    def format_for_database(self, research_data):
        """Format research data for database insertion"""
        song_name = research_data['song_name']
        extracted = research_data.get('extracted_data', {})
        sources = research_data.get('sources', {})
        
        external_refs = {}
        if 'jazzstandards' in sources:
            external_refs['jazzstandards'] = sources['jazzstandards'].get('url')
        if 'wikipedia' in sources:
            external_refs['wikipedia'] = sources['wikipedia'].get('url')
        
        performers_dict = {}
        for p in research_data.get('performers', []):
            name = p['name']
            if name not in performers_dict:
                performers_dict[name] = p
            elif p.get('instrument') and not performers_dict[name].get('instrument'):
                performers_dict[name] = p
        
        performers = list(performers_dict.values())
        
        # Extract MusicBrainz ID if available
        musicbrainz_id = None
        if 'musicbrainz' in sources:
            musicbrainz_id = sources['musicbrainz'].get('work_id')
        
        structured = {
            'song': {
                'title': song_name,
                'composer': extracted.get('composer'),
                'structure': None,
                'external_references': external_refs,
                'notes': extracted.get('description'),
                'year': extracted.get('year'),
                'musical_info': extracted.get('musical_info', {}),
                'musicbrainz_id': musicbrainz_id
            },
            'performers': performers[:10],
            'recordings': research_data.get('recordings', [])[:10]
        }
        
        return structured

    def generate_complete_sql(self, structured_data):
        """Generate complete SQL INSERT statements for all tables"""
        sql_parts = []
        song = structured_data['song']
        performers = structured_data.get('performers', [])
        recordings = structured_data.get('recordings', [])
        
        title = song['title']
        composer = song.get('composer', '')
        structure = song.get('structure', '')
        ext_refs = json.dumps(song.get('external_references', {}))
        
        sql_parts.append(f"""
-- ============================================================================
-- Song: {title}
-- Source: JazzStandards.com (priority) + Wikipedia + MusicBrainz
-- ============================================================================

-- Insert song (only if not exists)
INSERT INTO songs (title, composer, structure, external_references)
SELECT 
    '{title.replace("'", "''")}',
    {f"'{composer.replace("'", "''")}'" if composer else "NULL"},
    {f"'{structure.replace("'", "''")}'" if structure else "NULL"},
    '{ext_refs}'::jsonb
WHERE NOT EXISTS (
    SELECT 1 FROM songs WHERE title = '{title.replace("'", "''")}'
);
""")
        
        if performers:
            sql_parts.append("\n-- Insert performers (only if not exists)")
            for performer in performers:
                name = performer['name']
                instrument = performer.get('instrument', '')
                
                sql_parts.append(f"""
INSERT INTO performers (name)
SELECT '{name.replace("'", "''")}'
WHERE NOT EXISTS (
    SELECT 1 FROM performers WHERE name = '{name.replace("'", "''")}'
);
""")
                
                if instrument:
                    sql_parts.append(f"""
-- Link {name} to instrument (only if not exists)
INSERT INTO performer_instruments (performer_id, instrument_id, is_primary)
SELECT p.id, i.id, true
FROM performers p, instruments i
WHERE p.name = '{name.replace("'", "''")}' 
  AND i.name = '{instrument.replace("'", "''")}'
  AND NOT EXISTS (
      SELECT 1 FROM performer_instruments pi
      WHERE pi.performer_id = p.id AND pi.instrument_id = i.id
  );
""")
        
        if recordings:
            sql_parts.append("\n-- Insert recordings (JazzStandards.com recommendations marked as canonical)")
            for i, recording in enumerate(recordings, 1):
                album = recording.get('album') or recording.get('title', f'Recording {i}')
                artist = recording.get('artist', '')
                year = recording.get('year') or recording.get('date')
                
                # Mark JazzStandards.com recommendations as canonical
                is_recommended = recording.get('is_recommended', False)
                is_canonical = 'true' if is_recommended else 'false'
                source = recording.get('source', 'unknown')
                
                sql_parts.append(f"""
-- Recording: {album} by {artist} [Source: {source}]
DO $$
DECLARE
    v_song_id UUID;
    v_recording_id UUID;
BEGIN
    SELECT id INTO v_song_id FROM songs WHERE title = '{title.replace("'", "''")}';
    
    IF v_song_id IS NOT NULL THEN
        INSERT INTO recordings (song_id, album_title, recording_year, is_canonical)
        SELECT v_song_id, '{album.replace("'", "''")}', 
                {year if year else "NULL"}, {is_canonical}
        WHERE NOT EXISTS (
            SELECT 1 FROM recordings 
            WHERE song_id = v_song_id AND album_title = '{album.replace("'", "''")}'
        )
        RETURNING id INTO v_recording_id;
        
        IF v_recording_id IS NULL THEN
            SELECT id INTO v_recording_id FROM recordings
            WHERE song_id = v_song_id 
            AND album_title = '{album.replace("'", "''")}';
        END IF;
""")
                
                if artist:
                    artists = [a.strip() for a in artist.split(',')]
                    for artist_name in artists[:3]:
                        sql_parts.append(f"""
        IF v_recording_id IS NOT NULL THEN
            INSERT INTO recording_performers (recording_id, performer_id, role)
            SELECT v_recording_id, p.id, 'leader'
            FROM performers p
            WHERE p.name = '{artist_name.replace("'", "''")}'
            AND NOT EXISTS (
                SELECT 1 FROM recording_performers rp
                WHERE rp.recording_id = v_recording_id 
                AND rp.performer_id = p.id
            );
        END IF;
""")
                
                sql_parts.append("""    END IF;
END $$;
""")
        
        return '\n'.join(sql_parts)

def main():
    if len(sys.argv) < 2:
        print("Usage: python jazz_song_research.py 'Song Name'")
        print("Example: python jazz_song_research.py 'Take Five'")
        sys.exit(1)
    
    song_name = sys.argv[1]
    
    researcher = JazzSongResearcher()
    results = researcher.research_song(song_name)
    
    print("\n" + "=" * 60, file=sys.stderr)
    print("RESULTS", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    
    print(json.dumps(results, indent=2))
    
    print("\n" + "=" * 60, file=sys.stderr)
    print("COMPLETE SQL INSERT STATEMENTS", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    sql = researcher.generate_complete_sql(results['structured_output'])
    print(sql, file=sys.stderr)

if __name__ == "__main__":
    main()
