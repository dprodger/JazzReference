#!/usr/bin/env python3
"""
Jazz Song Information Gatherer
Searches for detailed information about a jazz standard and outputs JSON
"""

import sys
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin

class JazzSongResearcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
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
                # Get the first result
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
                return {
                    'title': page.get('title'),
                    'extract': page.get('extract'),
                    'url': page.get('fullurl')
                }
        except Exception as e:
            print(f"Wikipedia page error: {e}", file=sys.stderr)
        
        return None
    
    def search_musicbrainz(self, song_name):
        """Search MusicBrainz for recording information"""
        search_url = "https://musicbrainz.org/ws/2/work/"
        params = {
            'query': f'work:"{song_name}" AND type:song',
            'fmt': 'json',
            'limit': 5
        }
        
        try:
            response = self.session.get(search_url, params=params)
            if response.status_code == 200:
                data = response.json()
                if data.get('works'):
                    return data['works']
        except Exception as e:
            print(f"MusicBrainz error: {e}", file=sys.stderr)
        
        return []
    
    def extract_composer_info(self, text):
        """Extract composer information from text"""
        if not text:
            return None
        
        # Common patterns for composer attribution
        patterns = [
            r'composed by ([^,.\n]+)',
            r'music by ([^,.\n]+)',
            r'written by ([^,.\n]+)',
            r'([^,.\n]+) \(music\)',
            r'lyrics? by ([^,.\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def extract_year(self, text):
        """Extract year from text"""
        if not text:
            return None
        
        # Look for year patterns
        patterns = [
            r'\b(19\d{2})\b',
            r'\b(20\d{2})\b',
            r'written in (\d{4})',
            r'composed in (\d{4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))
        
        return None
    
    def search_jazzstandards_com(self, song_name):
        """Search JazzStandards.com for detailed information"""
        # Clean song name for URL
        clean_name = re.sub(r'[^\w\s-]', '', song_name.lower())
        clean_name = re.sub(r'\s+', '', clean_name)
        
        url = f"https://www.jazzstandards.com/compositions-0/{clean_name}.htm"
        
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract text content
                content = soup.get_text()
                
                return {
                    'url': url,
                    'found': True,
                    'content': content[:1000]  # First 1000 chars
                }
        except Exception as e:
            print(f"JazzStandards.com error: {e}", file=sys.stderr)
        
        return {'found': False}
    
    def research_song(self, song_name):
        """Main research function"""
        print(f"Researching: {song_name}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        
        result = {
            'song_name': song_name,
            'sources': {},
            'extracted_data': {}
        }
        
        # Search Wikipedia
        print("Searching Wikipedia...", file=sys.stderr)
        wiki_data = self.search_wikipedia(song_name)
        if wiki_data:
            result['sources']['wikipedia'] = wiki_data
            print(f"✓ Found Wikipedia article: {wiki_data.get('title')}", file=sys.stderr)
            
            # Extract data
            extract = wiki_data.get('extract', '')
            result['extracted_data']['composer'] = self.extract_composer_info(extract)
            result['extracted_data']['year'] = self.extract_year(extract)
            result['extracted_data']['description'] = extract[:500] if extract else None
        else:
            print("✗ No Wikipedia article found", file=sys.stderr)
        
        # Search MusicBrainz
        print("Searching MusicBrainz...", file=sys.stderr)
        mb_data = self.search_musicbrainz(song_name)
        if mb_data:
            result['sources']['musicbrainz'] = mb_data
            print(f"✓ Found {len(mb_data)} MusicBrainz entries", file=sys.stderr)
        else:
            print("✗ No MusicBrainz data found", file=sys.stderr)
        
        # Search JazzStandards.com
        print("Searching JazzStandards.com...", file=sys.stderr)
        jazz_data = self.search_jazzstandards_com(song_name)
        if jazz_data.get('found'):
            result['sources']['jazzstandards'] = jazz_data
            print(f"✓ Found JazzStandards.com entry", file=sys.stderr)
        else:
            print("✗ No JazzStandards.com entry found", file=sys.stderr)
        
        # Generate structured output
        result['structured_output'] = self.format_for_database(result)
        
        return result
    
    def format_for_database(self, research_data):
        """Format research data for database insertion"""
        song_name = research_data['song_name']
        extracted = research_data.get('extracted_data', {})
        sources = research_data.get('sources', {})
        
        # Build external references
        external_refs = {}
        if 'wikipedia' in sources:
            external_refs['wikipedia'] = sources['wikipedia'].get('url')
        if 'jazzstandards' in sources:
            external_refs['jazzstandards'] = sources['jazzstandards'].get('url')
        
        # Build structured data
        structured = {
            'title': song_name,
            'composer': extracted.get('composer'),
            'structure': None,  # Would need more detailed analysis
            'external_references': external_refs,
            'notes': extracted.get('description'),
            'year': extracted.get('year')
        }
        
        return structured
    
    def generate_sql_insert(self, structured_data):
        """Generate SQL INSERT statement"""
        title = structured_data['title']
        composer = structured_data.get('composer', '')
        structure = structured_data.get('structure', '')
        ext_refs = json.dumps(structured_data.get('external_references', {}))
        notes = structured_data.get('notes', '')
        
        sql = f"""
-- Insert for: {title}
INSERT INTO songs (title, composer, structure, external_references)
VALUES (
    '{title.replace("'", "''")}',
    '{composer.replace("'", "''") if composer else "NULL"}',
    {f"'{structure.replace("'", "''")}'" if structure else "NULL"},
    '{ext_refs}'::jsonb
);
"""
        return sql

def main():
    if len(sys.argv) < 2:
        print("Usage: python jazz_song_research.py 'Song Name'")
        print("Example: python jazz_song_research.py 'Take Five'")
        sys.exit(1)
    
    song_name = sys.argv[1]
    
    researcher = JazzSongResearcher()
    results = researcher.research_song(song_name)
    
    # Output results
    print("\n" + "=" * 60, file=sys.stderr)
    print("RESULTS", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    
    # Print JSON to stdout
    print(json.dumps(results, indent=2))
    
    # Print SQL to stderr for easy viewing
    print("\n" + "=" * 60, file=sys.stderr)
    print("SQL INSERT STATEMENT", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    sql = researcher.generate_sql_insert(results['structured_output'])
    print(sql, file=sys.stderr)

if __name__ == "__main__":
    main()