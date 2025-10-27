#!/usr/bin/env python3
"""
Spotify Track Matcher
Finds Spotify track IDs for existing recordings and updates the database
"""

import sys
import json
import time
import argparse
import logging
import os
import base64
from datetime import datetime
import requests

# Import shared database utilities
from db_utils import get_db_connection
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('log/spotify_match.log')
    ]
)
logger = logging.getLogger(__name__)


class SpotifyMatcher:
    def __init__(self, dry_run=False, artist_filter=None):
        self.dry_run = dry_run
        self.artist_filter = artist_filter
        self.access_token = None
        self.token_expires = 0
        self.stats = {
            'recordings_processed': 0,
            'recordings_with_spotify': 0,
            'recordings_updated': 0,
            'recordings_no_match': 0,
            'recordings_skipped': 0,
            'errors': 0
        }
    
    def get_spotify_token(self):
        """Get Spotify access token using client credentials flow"""
        # Check if we need credentials from environment
        client_id = os.environ.get('SPOTIFY_CLIENT_ID')
        client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            logger.error("Spotify credentials not found!")
            logger.error("")
            logger.error("Please set the following environment variables:")
            logger.error("  export SPOTIFY_CLIENT_ID='your_client_id'")
            logger.error("  export SPOTIFY_CLIENT_SECRET='your_client_secret'")
            logger.error("")
            logger.error("Get credentials at: https://developer.spotify.com/dashboard")
            raise ValueError("Missing Spotify credentials")
        
        # Check if token is still valid
        if self.access_token and time.time() < self.token_expires:
            return self.access_token
        
        # Get new token
        logger.info("Fetching Spotify access token...")
        
        auth_str = f"{client_id}:{client_secret}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {'grant_type': 'client_credentials'}
        
        try:
            response = requests.post(
                'https://accounts.spotify.com/api/token',
                headers=headers,
                data=data
            )
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            expires_in = token_data['expires_in']
            self.token_expires = time.time() + expires_in - 60  # Refresh 1 min early
            
            logger.info(f"✓ Spotify token obtained (expires in {expires_in}s)")
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get Spotify token: {e}")
            raise
    
    def find_song_by_name(self, song_name):
        """Find a song by name in the database"""
        logger.info(f"Searching for song: {song_name}")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, composer
                    FROM songs
                    WHERE title ILIKE %s
                    ORDER BY title
                    LIMIT 5
                """, (f'%{song_name}%',))
                
                results = cur.fetchall()
                
                if not results:
                    logger.warning(f"No songs found matching: {song_name}")
                    return None
                
                if len(results) == 1:
                    return results[0]
                
                # Multiple matches - show options
                logger.info(f"Found {len(results)} songs matching '{song_name}':")
                for i, song in enumerate(results, 1):
                    logger.info(f"  {i}. {song['title']} - {song['composer']}")
                
                choice = input("\nSelect song number (or 0 to cancel): ")
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(results):
                        return results[idx]
                except ValueError:
                    pass
                
                return None
    
    def find_song_by_id(self, song_id):
        """Find a song by ID in the database"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, composer
                    FROM songs
                    WHERE id = %s
                """, (song_id,))
                
                return cur.fetchone()
    
    def get_recordings_for_song(self, song_id):
        """Get all recordings for a song with performer information"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Build query with optional artist filter
                query = """
                    SELECT 
                        r.id,
                        r.album_title,
                        r.recording_year,
                        r.spotify_url,
                        COALESCE(
                            json_agg(
                                json_build_object(
                                    'name', p.name,
                                    'role', rp.role
                                )
                                ORDER BY 
                                    CASE rp.role 
                                        WHEN 'leader' THEN 1 
                                        ELSE 2 
                                    END
                            ) FILTER (WHERE p.id IS NOT NULL),
                            '[]'
                        ) as performers
                    FROM recordings r
                    LEFT JOIN recording_performers rp ON r.id = rp.recording_id
                    LEFT JOIN performers p ON rp.performer_id = p.id
                    WHERE r.song_id = %s
                """
                
                params = [song_id]
                
                # Add artist filter if specified
                if self.artist_filter:
                    query += """
                    AND EXISTS (
                        SELECT 1 
                        FROM recording_performers rp2
                        JOIN performers p2 ON rp2.performer_id = p2.id
                        WHERE rp2.recording_id = r.id
                        AND p2.name ILIKE %s
                    )
                    """
                    params.append(f'%{self.artist_filter}%')
                
                query += """
                    GROUP BY r.id, r.album_title, r.recording_year, r.spotify_url
                    ORDER BY r.recording_year DESC NULLS LAST, r.album_title
                """
                
                cur.execute(query, params)
                return cur.fetchall()
    
    def search_spotify_track(self, song_title, album_title, artist_name, year=None):
        """Search Spotify for a track using progressive search strategy"""
        token = self.get_spotify_token()
        
        headers = {
            'Authorization': f'Bearer {token}'
        }
        
        url = 'https://api.spotify.com/v1/search'
        
        # Define search strategies in order of specificity
        search_strategies = []
        
        # Strategy 1: All fields with exact track name
        if artist_name and album_title and year:
            search_strategies.append({
                'query': f'track:"{song_title}" artist:"{artist_name}" album:"{album_title}" year:{year}',
                'description': 'exact track + artist + album + year'
            })
        
        # Strategy 2: Track, artist, and album (no year)
        if artist_name and album_title:
            search_strategies.append({
                'query': f'track:"{song_title}" artist:"{artist_name}" album:"{album_title}"',
                'description': 'exact track + artist + album'
            })
        
        # Strategy 3: Track and artist with looser track matching
        if artist_name:
            search_strategies.append({
                'query': f'track:{song_title} artist:"{artist_name}"',
                'description': 'track + artist (loose match)'
            })
        
        # Strategy 4: Just track and artist, both loose
        if artist_name:
            search_strategies.append({
                'query': f'{song_title} {artist_name}',
                'description': 'track + artist (very loose)'
            })
        
        # Try each strategy until we get results
        for strategy in search_strategies:
            params = {
                'q': strategy['query'],
                'type': 'track',
                'limit': 10
            }
            
            try:
                time.sleep(0.1)  # Rate limiting
                logger.debug(f"    Trying: {strategy['description']}")
                logger.debug(f"    Query: {strategy['query']}")
                
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                tracks = data.get('tracks', {}).get('items', [])
                
                if tracks:
                    # Found results - return best match
                    best_match = tracks[0]
                    track_id = best_match['id']
                    track_name = best_match['name']
                    track_artists = ', '.join([a['name'] for a in best_match['artists']])
                    track_album = best_match['album']['name']
                    track_url = best_match['external_urls']['spotify']
                    
                    logger.debug(f"    ✓ Found with {strategy['description']}")
                    logger.debug(f"       Track: '{track_name}' by {track_artists}")
                    logger.debug(f"       Album: '{track_album}'")
                    logger.debug(f"       URL: {track_url}")
                    
                    return {
                        'id': track_id,
                        'url': track_url,
                        'name': track_name,
                        'artists': track_artists,
                        'album': track_album
                    }
                else:
                    logger.debug(f"    ✗ No results with {strategy['description']}")
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    # Token expired, clear it
                    self.access_token = None
                    logger.warning("Spotify token expired, will refresh on next request")
                    return None
                logger.error(f"Spotify search failed: {e}")
                return None
            except Exception as e:
                logger.error(f"Error searching Spotify: {e}")
                return None
        
        # No strategies worked
        logger.debug(f"    ✗ No Spotify matches found after trying all strategies")
        return None
    
    def update_recording_spotify_url(self, conn, recording_id, spotify_url):
        """Update recording with Spotify URL"""
        if self.dry_run:
            logger.info(f"    [DRY RUN] Would update recording with: {spotify_url}")
            return
        
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE recordings
                SET spotify_url = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (spotify_url, recording_id), prepare=False)
            
            conn.commit()
            logger.info(f"    ✓ Updated with Spotify URL")
            self.stats['recordings_updated'] += 1
    
    def match_recordings_for_song(self, song_identifier):
        """Main method to match Spotify tracks for a song's recordings"""
        logger.info("="*80)
        logger.info("Spotify Track Matching")
        logger.info("="*80)
        
        if self.dry_run:
            logger.info("*** DRY RUN MODE - No database changes will be made ***")
            logger.info("")
        
        # Find the song
        if song_identifier.startswith('song-') or len(song_identifier) == 36:
            # Looks like a UUID
            song = self.find_song_by_id(song_identifier)
        else:
            # Treat as song name
            song = self.find_song_by_name(song_identifier)
        
        if not song:
            logger.error("Song not found. Exiting.")
            return False
        
        logger.info("")
        logger.info(f"Song: {song['title']}")
        logger.info(f"Composer: {song['composer']}")
        logger.info(f"Database ID: {song['id']}")
        if self.artist_filter:
            logger.info(f"Filtering to recordings by: {self.artist_filter}")
        logger.info("")
        
        # Get recordings
        recordings = self.get_recordings_for_song(song['id'])
        
        if not recordings:
            logger.warning("No recordings found for this song.")
            return False
        
        logger.info(f"Found {len(recordings)} recordings to process")
        logger.info("")
        
        # Process each recording
        with get_db_connection() as conn:
            for i, recording in enumerate(recordings, 1):
                self.stats['recordings_processed'] += 1
                
                album = recording['album_title'] or 'Unknown Album'
                year = recording['recording_year']
                
                # Get primary artist
                performers = recording.get('performers', [])
                leaders = [p['name'] for p in performers if p['role'] == 'leader']
                artist_name = leaders[0] if leaders else (
                    performers[0]['name'] if performers else None
                )
                
                logger.info(f"[{i}/{len(recordings)}] {album}")
                logger.info(f"    Artist: {artist_name or 'Unknown'}")
                logger.info(f"    Year: {year or 'Unknown'}")
                
                # Check if already has Spotify URL
                if recording['spotify_url']:
                    logger.info(f"    ⊙ Already has Spotify URL, skipping")
                    self.stats['recordings_skipped'] += 1
                    continue
                
                # Search Spotify
                spotify_match = self.search_spotify_track(
                    song['title'],
                    album,
                    artist_name,
                    year
                )
                
                if spotify_match:
                    self.stats['recordings_with_spotify'] += 1
                    self.update_recording_spotify_url(
                        conn,
                        recording['id'],
                        spotify_match['url']
                    )
                else:
                    logger.info(f"    ✗ No Spotify match found")
                    self.stats['recordings_no_match'] += 1
                
                logger.info("")
        
        # Print summary
        logger.info("="*80)
        logger.info("MATCHING SUMMARY")
        logger.info("="*80)
        logger.info(f"Recordings processed:      {self.stats['recordings_processed']}")
        logger.info(f"Recordings already had URL: {self.stats['recordings_skipped']}")
        logger.info(f"Spotify matches found:     {self.stats['recordings_with_spotify']}")
        logger.info(f"Recordings updated:        {self.stats['recordings_updated']}")
        logger.info(f"No match found:            {self.stats['recordings_no_match']}")
        logger.info(f"Errors:                    {self.stats['errors']}")
        logger.info("="*80)
        
        return True


def main():
    parser = argparse.ArgumentParser(
        description='Match Spotify tracks to existing recordings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Setup:
  1. Get Spotify API credentials from https://developer.spotify.com/dashboard
  2. Set environment variables:
     export SPOTIFY_CLIENT_ID='your_client_id'
     export SPOTIFY_CLIENT_SECRET='your_client_secret'

Examples:
  # Match by song name
  python match_spotify_tracks.py --name "Take Five"
  
  # Match by song ID
  python match_spotify_tracks.py --id a1b2c3d4-e5f6-7890-abcd-ef1234567890
  
  # Filter to only recordings by a specific artist
  python match_spotify_tracks.py --name "Autumn Leaves" --artist "Bill Evans"
  
  # Dry run to see what would be matched
  python match_spotify_tracks.py --name "Blue in Green" --dry-run
  
  # Enable debug logging
  python match_spotify_tracks.py --name "Autumn Leaves" --debug
        """
    )
    
    # Song selection arguments
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--name',
        help='Song name'
    )
    group.add_argument(
        '--id',
        help='Song database ID'
    )
    
    parser.add_argument(
        '--artist',
        help='Filter to recordings by this artist'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be matched without making changes'
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
    
    # Create matcher and run
    matcher = SpotifyMatcher(dry_run=args.dry_run, artist_filter=args.artist)
    
    # Determine song identifier
    song_identifier = args.name if args.name else args.id
    
    try:
        success = matcher.match_recordings_for_song(song_identifier)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nMatching cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()