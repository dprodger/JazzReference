#!/usr/bin/env python3
"""
Jazz Song Information Gatherer - Enhanced Version
Searches for detailed information about a jazz standard including recordings and performers
"""

import sys
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
from datetime import datetime

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
                extract = page.get('extract', '')
                
                # Try to find canonical recording info in the extract
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
        
        # Look for patterns like "recorded by", "famous recording by", etc.
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
                
                # Filter out common false positives
                if len(artist) > 3 and not any(word in artist.lower() for word in ['the song', 'the tune', 'this']):
                    recordings.append({
                        'artist': artist,
                        'year': int(year) if year else None
                    })
        
        return recordings[:3] if recordings else None
    
    def search_musicbrainz_recordings(self, song_name):
        """Search MusicBrainz for actual recordings of the song"""
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
                    # Get album title from first release
                    album_title = None
                    if rec.get('releases'):
                        album_title = rec['releases'][0].get('title')
                    
                    recording_info = {
                        'musicbrainz_id': rec.get('id'), 
                        'title': album_title or rec.get('title'),
                        'artist': None,
                        'date': None,
                        'length': rec.get('length'),
                    }
                    
                    # Get artist info
                    if rec.get('artist-credit'):
                        artists = []
                        for artist in rec['artist-credit']:
                            if isinstance(artist, dict) and artist.get('artist'):
                                artists.append(artist['artist'].get('name'))
                        recording_info['artist'] = ', '.join(artists) if artists else None
                    
                    # Try to get date
                    if rec.get('releases'):
                        for release in rec['releases']:
                            if release.get('date'):
                                recording_info['date'] = release['date'][:4]  # Just year
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
        
        # Common patterns for composer attribution
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
                # Clean up common artifacts
                composer = re.sub(r'\s+and\s+.*$', '', composer, flags=re.IGNORECASE)
                return composer
        
        return None
    
    def extract_year(self, text):
        """Extract year from text"""
        if not text:
            return None
        
        # Look for year patterns near composition/written indicators
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
                # Sanity check - jazz standards range
                if 1900 <= year <= 2025:
                    return year
        
        return None
    
    def parse_performers_from_text(self, text, year=None):
        """Extract performer names and try to identify instruments"""
        performers = []
        
        # Common jazz instrument patterns
        instrument_patterns = [
            (r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:on |plays? )?(?:the )?(trumpet|piano|bass|drums|saxophone|sax|guitar|trombone|clarinet|vibraphone|organ)', 'instrument_explicit'),
            (r'([A-Z][a-z]+ [A-Z][a-z]+),?\s+(trumpet|piano|bass|drums|saxophone|sax|guitar|trombone|clarinet|vibraphone|organ)(?:ist)?', 'instrument_suffix'),
        ]
        
        for pattern, pattern_type in instrument_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                name = match.group(1).strip()
                instrument = match.group(2).strip().lower()
                
                # Normalize instrument names
                if 'sax' in instrument and instrument != 'saxophone':
                    instrument = 'saxophone'
                
                performers.append({
                    'name': name,
                    'instrument': instrument.capitalize(),
                    'year': year
                })
        
        return performers
    
    def research_song(self, song_name):
        """Main research function"""
        print(f"Researching: {song_name}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        
        result = {
            'song_name': song_name,
            'sources': {},
            'extracted_data': {},
            'recordings': [],
            'performers': []
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
            
            # Extract canonical recordings from Wikipedia
            if wiki_data.get('canonical_recording'):
                result['extracted_data']['canonical_recordings'] = wiki_data['canonical_recording']
            
            # Extract performers mentioned in the text
            performers = self.parse_performers_from_text(extract, result['extracted_data'].get('year'))
            result['performers'].extend(performers)
            
        else:
            print("✗ No Wikipedia article found", file=sys.stderr)
        
        # Search MusicBrainz for recordings
        print("Searching MusicBrainz for recordings...", file=sys.stderr)
        mb_recordings = self.search_musicbrainz_recordings(song_name)
        if mb_recordings:
            result['recordings'] = mb_recordings
            print(f"✓ Found {len(mb_recordings)} MusicBrainz recordings", file=sys.stderr)
            
            # Add artists as performers
            for rec in mb_recordings:
                if rec.get('artist'):
                    # Split multiple artists
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
        
        # Deduplicate performers
        performers_dict = {}
        for p in research_data.get('performers', []):
            name = p['name']
            if name not in performers_dict:
                performers_dict[name] = p
            elif p.get('instrument') and not performers_dict[name].get('instrument'):
                # Update with instrument info if we have it
                performers_dict[name] = p
        
        performers = list(performers_dict.values())
        
        # Build structured data
        structured = {
            'song': {
                'title': song_name,
                'composer': extracted.get('composer'),
                'structure': None,
                'external_references': external_refs,
                'notes': extracted.get('description'),
                'year': extracted.get('year')
            },
            'performers': performers[:10],  # Limit to top 10
            'recordings': research_data.get('recordings', [])[:5]  # Limit to top 5
        }
        
        return structured
    
    def generate_complete_sql(self, structured_data):
        """Generate complete SQL INSERT statements for all tables"""
        sql_parts = []
        song = structured_data['song']
        performers = structured_data.get('performers', [])
        recordings = structured_data.get('recordings', [])
        
        # Generate song insert
        title = song['title']
        composer = song.get('composer', '')
        structure = song.get('structure', '')
        ext_refs = json.dumps(song.get('external_references', {}))
        
        sql_parts.append(f"""
-- ============================================================================
-- Song: {title}
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
        
        # Generate performer inserts
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
                
                # If we have instrument info, link it
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
        
        # Generate recording inserts
        if recordings:
            sql_parts.append("\n-- Insert recordings")
            for i, recording in enumerate(recordings, 1):
                album = recording.get('title', f'Recording {i}')
                artist = recording.get('artist', '')
                year = recording.get('date')
                mb_id = recording.get('musicbrainz_id', '')
                
                is_canonical = 'true' if i == 1 else 'false'  # Mark first as canonical
                
                sql_parts.append(f"""
-- Recording: {album} by {artist}
DO $$
DECLARE
    v_song_id UUID;
    v_recording_id UUID;
BEGIN
    -- Get song ID
    SELECT id INTO v_song_id FROM songs WHERE title = '{title.replace("'", "''")}';
    
    IF v_song_id IS NOT NULL THEN
        -- Insert recording if not exists
        INSERT INTO recordings (song_id, album_title, recording_year, is_canonical, musicbrainz_id)
        SELECT v_song_id, '{album.replace("'", "''")}', 
                {year if year else "NULL"}, {is_canonical},
                {f"'{mb_id}'" if mb_id else "NULL"}
        WHERE NOT EXISTS (
            SELECT 1 FROM recordings 
            WHERE musicbrainz_id = {f"'{mb_id}'" if mb_id else "NULL"}
            {f"AND song_id = v_song_id AND album_title = '{album.replace("'", "''")}'" if not mb_id else ""}
        )
        RETURNING id INTO v_recording_id;
        
        -- Get recording ID if it already existed
        IF v_recording_id IS NULL THEN
            SELECT id INTO v_recording_id FROM recordings
            WHERE song_id = v_song_id 
            AND album_title = '{album.replace("'", "''")}';
        END IF;
""")
                
                # Link performer to recording if we have artist info
                if artist:
                    # Handle multiple artists
                    artists = [a.strip() for a in artist.split(',')]
                    for artist_name in artists[:3]:  # Limit to first 3
                        sql_parts.append(f"""
        -- Link {artist_name} to recording
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
    
    # Output results
    print("\n" + "=" * 60, file=sys.stderr)
    print("RESULTS", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    
    # Print JSON to stdout
    print(json.dumps(results, indent=2))
    
    # Print SQL to stderr for easy viewing
    print("\n" + "=" * 60, file=sys.stderr)
    print("COMPLETE SQL INSERT STATEMENTS", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    sql = researcher.generate_complete_sql(results['structured_output'])
    print(sql, file=sys.stderr)

if __name__ == "__main__":
    main()