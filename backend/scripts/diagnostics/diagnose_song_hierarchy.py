#!/usr/bin/env python3
"""
Song Hierarchy Diagnostic Tool
Explores the MusicBrainz Song → Recording → Release hierarchy and Spotify matching

This diagnostic script helps understand:
- How MusicBrainz organizes Works, Recordings, and Releases
- Which recordings and releases exist for a given song
- How well we can match MusicBrainz data to Spotify tracks
- The effectiveness of different matching strategies (ISRC, exact title, substring)
"""

import sys
import argparse
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
import time
from rapidfuzz import fuzz

from dotenv import load_dotenv

load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mb_utils import MusicBrainzSearcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('log/diagnose_song_hierarchy.log')
    ]
)
logger = logging.getLogger(__name__)


class SongHierarchyDiagnostic:
    """Diagnostic tool for exploring MusicBrainz song hierarchy and Spotify matching"""
    
    def __init__(self, cache_dir='cache/musicbrainz', force_refresh=False):
        """
        Initialize diagnostic tool
        
        Args:
            cache_dir: Directory for MusicBrainz cache
            force_refresh: If True, bypass cache and fetch fresh data
        """
        self.mb = MusicBrainzSearcher(
            cache_dir=cache_dir,
            cache_days=30,
            force_refresh=force_refresh
        )
        
        self.spotify_client_id = os.environ.get('SPOTIFY_CLIENT_ID')
        self.spotify_client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
        self.spotify_token = None
        
        self.stats = {
            'works_found': 0,
            'recordings_found': 0,
            'recordings_matched_performer': 0,
            'releases_found': 0,
            'isrc_matches': 0,
            'exact_title_matches': 0,
            'substring_matches': 0,
            'spotify_checks': 0,
            'spotify_isrc_found': 0,
            'spotify_search_found': 0
        }
    
    def normalize_string(self, s: str) -> str:
        """
        Normalize string for comparison: lowercase, condense whitespace, normalize apostrophes
        
        Args:
            s: String to normalize
            
        Returns:
            Normalized string
        """
        if not s:
            return ""
        
        # Normalize apostrophes
        s = s.replace("'", "'").replace("'", "'").replace("`", "'")
        
        # Lowercase and condense whitespace
        s = ' '.join(s.lower().split())
        
        return s
    
    def calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity score between two strings"""
        norm1 = self.normalize_string(str1)
        norm2 = self.normalize_string(str2)
        return fuzz.ratio(norm1, norm2)
    
    def get_spotify_token(self) -> Optional[str]:
        """Get Spotify access token"""
        if not self.spotify_client_id or not self.spotify_client_secret:
            return None
        
        if self.spotify_token:
            return self.spotify_token
        
        import requests
        import base64
        
        auth_str = f"{self.spotify_client_id}:{self.spotify_client_secret}"
        auth_bytes = auth_str.encode('utf-8')
        auth_base64 = base64.b64encode(auth_bytes).decode('utf-8')
        
        url = 'https://accounts.spotify.com/api/token'
        headers = {
            'Authorization': f'Basic {auth_base64}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {'grant_type': 'client_credentials'}
        
        try:
            response = requests.post(url, headers=headers, data=data)
            if response.status_code == 200:
                self.spotify_token = response.json()['access_token']
                return self.spotify_token
        except Exception as e:
            logger.debug(f"Failed to get Spotify token: {e}")
        
        return None
    
    def search_spotify_by_isrc(self, isrc: str) -> Optional[Dict]:
        """
        Search Spotify by ISRC
        
        Args:
            isrc: International Standard Recording Code
            
        Returns:
            Track data if found, None otherwise
        """
        token = self.get_spotify_token()
        if not token:
            return None
        
        import requests
        
        headers = {'Authorization': f'Bearer {token}'}
        
        # Try ISRC search query (undocumented but sometimes works)
        url = 'https://api.spotify.com/v1/search'
        params = {
            'q': f'isrc:{isrc}',
            'type': 'track',
            'limit': 1
        }
        
        try:
            time.sleep(0.1)  # Rate limiting
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                tracks = data.get('tracks', {}).get('items', [])
                if tracks:
                    track = tracks[0]
                    # Verify ISRC matches in track details
                    track_url = track['href']
                    track_response = requests.get(track_url, headers=headers)
                    if track_response.status_code == 200:
                        track_details = track_response.json()
                        track_isrc = track_details.get('external_ids', {}).get('isrc')
                        if track_isrc and track_isrc.upper() == isrc.upper():
                            return {
                                'id': track['id'],
                                'name': track['name'],
                                'artists': [a['name'] for a in track['artists']],
                                'album': track['album']['name'],
                                'url': track['external_urls']['spotify'],
                                'isrc': track_isrc,
                                'method': 'isrc_search'
                            }
        except Exception as e:
            logger.debug(f"ISRC search error: {e}")
        
        return None
    
    def search_spotify_by_title(self, title: str, artist: str) -> Optional[Dict]:
        """
        Search Spotify by track title and artist
        
        Args:
            title: Track title
            artist: Artist name
            
        Returns:
            Track data if found, None otherwise
        """
        token = self.get_spotify_token()
        if not token:
            return None
        
        import requests
        
        headers = {'Authorization': f'Bearer {token}'}
        url = 'https://api.spotify.com/v1/search'
        
        # Try exact match first
        params = {
            'q': f'track:"{title}" artist:"{artist}"',
            'type': 'track',
            'limit': 5
        }
        
        try:
            time.sleep(0.1)  # Rate limiting
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                tracks = data.get('tracks', {}).get('items', [])
                
                # Look for best match
                best_match = None
                best_score = 0
                
                for track in tracks:
                    track_title = track['name']
                    track_artists = ', '.join([a['name'] for a in track['artists']])
                    
                    title_score = self.calculate_similarity(title, track_title)
                    artist_score = self.calculate_similarity(artist, track_artists)
                    combined_score = (title_score + artist_score) / 2
                    
                    if combined_score > best_score:
                        best_score = combined_score
                        best_match = {
                            'id': track['id'],
                            'name': track['name'],
                            'artists': [a['name'] for a in track['artists']],
                            'album': track['album']['name'],
                            'url': track['external_urls']['spotify'],
                            'title_similarity': title_score,
                            'artist_similarity': artist_score,
                            'combined_similarity': combined_score,
                            'method': 'title_search'
                        }
                        
                        # Get ISRC if available
                        track_url = track['href']
                        track_response = requests.get(track_url, headers=headers)
                        if track_response.status_code == 200:
                            track_details = track_response.json()
                            best_match['isrc'] = track_details.get('external_ids', {}).get('isrc')
                
                return best_match if best_score >= 70 else None
                
        except Exception as e:
            logger.debug(f"Title search error: {e}")
        
        return None
    
    def find_work(self, song_name: str) -> Optional[Dict]:
        """
        Search for MusicBrainz Work by song name
        
        Args:
            song_name: Name of the song/work
            
        Returns:
            Work data if found, None otherwise
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"Step 1: Searching for MusicBrainz Work: '{song_name}'")
        logger.info(f"{'='*80}\n")
        
        # search_musicbrainz_work returns just the work ID (not a list)
        work_id = self.mb.search_musicbrainz_work(song_name, composer=None)
        
        if not work_id:
            logger.warning("No work found in MusicBrainz")
            return None
        
        self.stats['works_found'] = 1
        
        logger.info(f"Found work ID: {work_id}")
        
        # Get full work details
        work_data = self.mb.get_work_recordings(work_id)
        
        if not work_data:
            logger.warning("Could not retrieve work details")
            return None
        
        # Extract title and composer info
        title = work_data.get('title', 'Unknown')
        work_type = work_data.get('type', 'Unknown')
        
        # Calculate similarity
        similarity = self.calculate_similarity(song_name, title)
        
        logger.info(f"\n  Work:")
        logger.info(f"    Title: {title}")
        logger.info(f"    MBID: {work_id}")
        logger.info(f"    Type: {work_type}")
        logger.info(f"    Similarity: {similarity:.1f}%")
        
        # Show composers if available
        composers = []
        for relation in work_data.get('relations', []):
            if relation.get('type') == 'composer':
                artist = relation.get('artist', {})
                composer_name = artist.get('name')
                if composer_name and composer_name not in composers:
                    composers.append(composer_name)
        
        if composers:
            logger.info(f"    Composers: {', '.join(composers)}")
        
        logger.info(f"\n✓ Using Work: '{title}' (similarity: {similarity:.1f}%)")
        
        # Return work data with ID included
        return {
            'id': work_id,
            'title': title,
            'type': work_type,
            'data': work_data
        }
    
    def _fetch_recordings_via_api(self, work_mbid: str, performer_name: str) -> List[Dict]:
        """
        Fallback method to fetch recordings via MusicBrainz search API
        
        Args:
            work_mbid: MusicBrainz Work ID
            performer_name: Name of performer to filter by
            
        Returns:
            List of recording dictionaries
        """
        import requests
        
        # Try using search with the work title instead
        logger.info("Note: MusicBrainz browse by work ID not working, using search instead")
        return []
    
    def find_recordings(self, work_dict: Dict, performer_name: str) -> List[Dict]:
        """
        Find all recordings of a work from the work data
        
        Args:
            work_dict: Work dictionary with 'id', 'title', 'data' fields
            performer_name: Name of performer to filter by
            
        Returns:
            List of recording dictionaries
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"Step 2: Finding Recordings from Work Relationships")
        logger.info(f"{'='*80}\n")
        
        work_data = work_dict.get('data', {})
        work_mbid = work_dict.get('id')
        
        # Debug: Show what relations we have
        relations = work_data.get('relations', [])
        logger.debug(f"Work has {len(relations)} total relations")
        relation_types = {}
        for rel in relations:
            rel_type = rel.get('type', 'unknown')
            relation_types[rel_type] = relation_types.get(rel_type, 0) + 1
        logger.debug(f"Relation types: {relation_types}")
        
        # Extract recordings from the work's relations
        # Work data includes recording-rels when fetched with inc=recording-rels
        recordings_data = []
        
        for relation in relations:
            rel_type = relation.get('type')
            # Check for different possible relationship types
            if 'recording' in relation:
                logger.debug(f"Found relation type '{rel_type}' with recording")
                recording = relation['recording']
                recordings_data.append(recording)
        
        logger.debug(f"Extracted {len(recordings_data)} recordings from relations")
        
        if not recordings_data:
            logger.warning("No recording relationships found in work data")
            logger.info("Fetching recordings via browse API instead...")
            return self._fetch_recordings_via_api(work_mbid, performer_name)
        
        self.stats['recordings_found'] = len(recordings_data)
        logger.info(f"Found {len(recordings_data)} recording(s) in work relationships")
        
        # Now we need to get full details for each recording to get artist credits, ISRCs, and releases
        # This requires individual API calls per recording
        matched_recordings = []
        
        for i, recording in enumerate(recordings_data[:20], 1):  # Limit to first 20 to avoid too many API calls
            rec_mbid = recording.get('id')
            rec_title = recording.get('title', 'Unknown')
            
            # Get full recording details
            rec_details = self.mb.get_recording_details(rec_mbid)
            
            if not rec_details:
                continue
            
            # Get artist credits
            artist_credits = rec_details.get('artist-credit', [])
            artists = []
            for credit in artist_credits:
                if isinstance(credit, dict) and 'artist' in credit:
                    artists.append(credit['artist'].get('name', ''))
                elif isinstance(credit, str):
                    artists.append(credit)
            artist_str = ', '.join(artists) if artists else 'Unknown'
            
            # Calculate artist similarity
            artist_similarity = self.calculate_similarity(performer_name, artist_str)
            
            # Debug: Show first 10 recordings
            if i <= 10:
                logger.debug(f"  Recording #{i}: '{rec_title}' by '{artist_str}' (similarity: {artist_similarity:.1f}%)")
            
            # Get ISRCs - MusicBrainz API doesn't include ISRCs by default
            # We need to add 'isrcs' to the inc parameter when fetching recording details
            isrcs = rec_details.get('isrcs', [])
            if not isrcs:
                # ISRCs might be in a different format
                isrcs = rec_details.get('isrc-list', [])
            
            # Get releases
            releases = rec_details.get('releases', [])[:10]
            
            recording_data = {
                'title': rec_title,
                'mbid': rec_mbid,
                'artists': artist_str,
                'artist_similarity': artist_similarity,
                'isrcs': isrcs,
                'releases': releases,
                'matched_performer': artist_similarity >= 70
            }
            
            if recording_data['matched_performer']:
                matched_recordings.append(recording_data)
                self.stats['recordings_matched_performer'] += 1
        
        logger.info(f"Found {len(matched_recordings)} recording(s) matching performer '{performer_name}' (≥70% similarity)\n")
        
        # Show sample if no matches
        if len(matched_recordings) == 0 and len(recordings_data) > 0:
            logger.info("Sample of recordings found (showing first 5 with similarity scores):")
            count = 0
            for i, recording in enumerate(recordings_data, 1):
                if count >= 5:
                    break
                rec_mbid = recording.get('id')
                rec_title = recording.get('title', 'Unknown')
                rec_details = self.mb.get_recording_details(rec_mbid)
                if rec_details:
                    artist_credits = rec_details.get('artist-credit', [])
                    artists = []
                    for credit in artist_credits:
                        if isinstance(credit, dict) and 'artist' in credit:
                            artists.append(credit['artist'].get('name', ''))
                    artist_str = ', '.join(artists) if artists else 'Unknown'
                    artist_similarity = self.calculate_similarity(performer_name, artist_str)
                    logger.info(f"  {count+1}. '{rec_title}' by '{artist_str}' (similarity: {artist_similarity:.1f}%)")
                    count += 1
            logger.info("")
        
        return matched_recordings
    
    def analyze_recording(self, recording: Dict, work_title: str) -> None:
        """
        Analyze a recording and try to match it to Spotify
        
        Args:
            recording: Recording dictionary
            work_title: Original work title for reference
        """
        rec_title = recording['title']
        rec_artists = recording['artists']
        isrcs = recording.get('isrcs', [])
        releases = recording.get('releases', [])
        
        logger.info(f"\n{'─'*80}")
        logger.info(f"Recording: {rec_title}")
        logger.info(f"{'─'*80}")
        logger.info(f"  MBID: {recording['mbid']}")
        logger.info(f"  Artists: {rec_artists}")
        logger.info(f"  Artist Similarity: {recording['artist_similarity']:.1f}%")
        
        if isrcs:
            logger.info(f"  ISRCs: {', '.join(isrcs)}")
        else:
            logger.info(f"  ISRCs: None")
        
        # Try to find on Spotify
        spotify_match = None
        if self.spotify_client_id and self.spotify_client_secret:
            self.stats['spotify_checks'] += 1
            logger.info(f"\n  Spotify Search:")
            
            # Try ISRC first
            if isrcs:
                for isrc in isrcs:
                    logger.info(f"    Trying ISRC: {isrc}")
                    spotify_match = self.search_spotify_by_isrc(isrc)
                    if spotify_match:
                        logger.info(f"      ✓ Found via ISRC!")
                        self.stats['spotify_isrc_found'] += 1
                        break
                    else:
                        logger.info(f"      ✗ Not found via ISRC")
            
            # If no ISRC match, try title+artist
            if not spotify_match:
                logger.info(f"    Trying title+artist: '{rec_title}' by '{rec_artists}'")
                spotify_match = self.search_spotify_by_title(rec_title, rec_artists)
                if spotify_match:
                    logger.info(f"      ✓ Found via title+artist search!")
                    logger.info(f"      Title Similarity: {spotify_match['title_similarity']:.1f}%")
                    logger.info(f"      Artist Similarity: {spotify_match['artist_similarity']:.1f}%")
                    self.stats['spotify_search_found'] += 1
                else:
                    logger.info(f"      ✗ No match found on Spotify")
        
        # Now analyze releases
        if not releases:
            logger.info(f"\n  Releases: None found in MusicBrainz")
            return
        
        self.stats['releases_found'] += len(releases)
        logger.info(f"\n  MusicBrainz Releases: {len(releases)} found")
        
        for j, release in enumerate(releases, 1):
            release_title = release.get('title', 'Unknown')
            release_mbid = release.get('id', 'Unknown')
            release_date = release.get('date', 'Unknown')
            
            logger.info(f"\n    Release #{j}:")
            logger.info(f"      Title: {release_title}")
            logger.info(f"      MBID: {release_mbid}")
            logger.info(f"      Date: {release_date}")
            
            # If we found a Spotify match, compare the albums
            if spotify_match:
                spotify_album = spotify_match['album']
                album_similarity = self.calculate_similarity(release_title, spotify_album)
                logger.info(f"      Spotify Album: {spotify_album}")
                logger.info(f"      Album Similarity: {album_similarity:.1f}%")
                
                # Check matching strategies
                matches = []
                
                # ISRC match (already confirmed if we got here via ISRC)
                if spotify_match.get('method') == 'isrc_search' and isrcs:
                    matches.append(f"✓ ISRC: {spotify_match.get('isrc')}")
                    self.stats['isrc_matches'] += 1
                
                # Exact title match (recording title)
                if self.normalize_string(rec_title) == self.normalize_string(spotify_match['name']):
                    matches.append("✓ Exact recording title match")
                    self.stats['exact_title_matches'] += 1
                
                # Exact album match
                if self.normalize_string(release_title) == self.normalize_string(spotify_album):
                    matches.append("✓ Exact album title match")
                
                # Starts-with match (work title is substring of release title)
                norm_work = self.normalize_string(work_title)
                norm_release = self.normalize_string(release_title)
                if norm_work in norm_release and norm_work != norm_release:
                    matches.append("✓ Work title in release title")
                    self.stats['substring_matches'] += 1
                
                if matches:
                    logger.info(f"      Matches: {', '.join(matches)}")
                
                # Show Spotify URL
                logger.info(f"      Spotify URL: {spotify_match['url']}")
            else:
                # No Spotify match, just show MB release info
                # Check if work title appears in release title
                norm_work = self.normalize_string(work_title)
                norm_release = self.normalize_string(release_title)
                
                if norm_work == norm_release:
                    logger.info(f"      Note: Exact match to work title")
                    self.stats['exact_title_matches'] += 1
                elif norm_work in norm_release:
                    logger.info(f"      Note: Work title appears in release title")
                    self.stats['substring_matches'] += 1
    
    def diagnose(self, song_name: str, performer_name: str) -> bool:
        """
        Run full diagnostic for a song and performer
        
        Args:
            song_name: Name of song/work
            performer_name: Name of performer
            
        Returns:
            True if successful, False otherwise
        """
        logger.info("="*80)
        logger.info("SONG HIERARCHY DIAGNOSTIC")
        logger.info("="*80)
        logger.info(f"Song: {song_name}")
        logger.info(f"Performer: {performer_name}")
        logger.info("="*80)
        
        # Step 1: Find the work
        work = self.find_work(song_name)
        if not work:
            logger.error("Could not find work in MusicBrainz")
            return False
        
        work_mbid = work.get('id')
        work_title = work.get('title')
        
        # Step 2: Find recordings (pass the whole work dict)
        recordings = self.find_recordings(work, performer_name)
        if not recordings:
            logger.warning("No recordings found matching the performer")
            return True  # Still a success, just no matches
        
        # Step 3: Analyze each recording
        logger.info(f"\n{'='*80}")
        logger.info(f"Step 3: Analyzing Recordings and Matching to Spotify")
        logger.info(f"{'='*80}")
        
        for i, recording in enumerate(recordings, 1):
            logger.info(f"\nRecording {i} of {len(recordings)}")
            self.analyze_recording(recording, work_title)
        
        return True
    
    def print_summary(self):
        """Print diagnostic summary"""
        logger.info(f"\n{'='*80}")
        logger.info("DIAGNOSTIC SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"Works found:                     {self.stats['works_found']}")
        logger.info(f"Recordings found (total):        {self.stats['recordings_found']}")
        logger.info(f"Recordings matched performer:    {self.stats['recordings_matched_performer']}")
        logger.info(f"Releases found:                  {self.stats['releases_found']}")
        logger.info(f"")
        logger.info(f"MusicBrainz Matching:")
        logger.info(f"  ISRC matches:                  {self.stats['isrc_matches']}")
        logger.info(f"  Exact title matches:           {self.stats['exact_title_matches']}")
        logger.info(f"  Substring matches:             {self.stats['substring_matches']}")
        logger.info(f"")
        logger.info(f"Spotify Matching:")
        logger.info(f"  Recordings checked:            {self.stats['spotify_checks']}")
        logger.info(f"  Found via ISRC:                {self.stats['spotify_isrc_found']}")
        logger.info(f"  Found via title/artist:        {self.stats['spotify_search_found']}")
        logger.info(f"{'='*80}\n")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Diagnose MusicBrainz Song→Recording→Release hierarchy and Spotify matching',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic diagnostic
  python diagnose_song_hierarchy.py --song-name "Take Five" --performer-name "Dave Brubeck"
  
  # With debug logging
  python diagnose_song_hierarchy.py --song-name "Blue in Green" --performer-name "Miles Davis" --debug
  
  # Force refresh (bypass cache)
  python diagnose_song_hierarchy.py --song-name "Round Midnight" --performer-name "Thelonious Monk" --force-refresh

Note: 
  - Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables for Spotify matching
  - Uses cache directory: cache/musicbrainz
  - Logs to: log/diagnose_song_hierarchy.log
        """
    )
    
    parser.add_argument(
        '--song-name',
        required=True,
        help='Name of the song/work to search for'
    )
    
    parser.add_argument(
        '--performer-name',
        required=True,
        help='Name of the performer to filter recordings by'
    )
    
    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Force refresh data from MusicBrainz (bypass cache)'
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
    
    # Create log directory
    Path('log').mkdir(exist_ok=True)
    
    # Create diagnostic tool
    diagnostic = SongHierarchyDiagnostic(
        cache_dir='cache/musicbrainz',
        force_refresh=args.force_refresh
    )
    
    try:
        success = diagnostic.diagnose(args.song_name, args.performer_name)
        diagnostic.print_summary()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n\nDiagnostic cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()