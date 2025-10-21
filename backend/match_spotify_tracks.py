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
import psycopg
from psycopg.rows import dict_row

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('spotify_match.log')
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': 'db.wxinjyotnrqxrwqrtvkp.supabase.co',
    'database': 'postgres',
    'user': 'postgres',
    'password': 'jovpeW-pukgu0-nifron',
    'port': '5432'
}

class SpotifyMatcher:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
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
    
    def get_db_connection(self):
        """Create database connection"""
        try:
            conn = psycopg.connect(
                host=DB_CONFIG['host'],
                dbname=DB_CONFIG['database'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                port=DB_CONFIG['port'],
                row_factory=dict_row
            )
            logger.debug("Database connection established")
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def get_spotify_token(self):
        """Get Spotify access token using client credentials flow"""
        # Check if we need credentials from environment
        client_id = os.environ.get('SPOTIFY_CLIENT_ID')
        client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            logger.error("Spotify credentials not found!")
            logger.error("Please set environment variables:")
            logger.error("  export SPOTIFY_CLIENT_ID='your_client_id'")
            logger.error("  export SPOTIFY_CLIENT_SECRET='your_client_secret'")
            logger.error("")
            logger.error("Get credentials at: https://developer.spotify.com/dashboard")
            raise ValueError("Missing Spotify credentials")
        
        # Check if token is still valid
        if self.access_token and time.time() < self.token_expires:
            return self.access_token
        
        logger.info("Fetching Spotify access token...")
        
        # Encode credentials
        auth_str = f"{client_id}:{client_secret}"
        auth_bytes = auth_str.encode('utf-8')
        auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
        
        # Request token
        url = "https://accounts.spotify.com/api/token"
        headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {'grant_type': 'client_credentials'}
        
        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            expires_in = token_data['expires_in']
            self.token_expires = time.time() + expires_in - 60  # Refresh 1 min early
            
            logger.info(f"✓ Spotify token obtained (expires in {expires_in}s)")
            return self.access_token
            
        except Exception as e:
            logger.error(f"Failed to get Spotify token: {e}")
            raise
    
    def find_song_by_name(self, song_name):
        """Find a song in the database by name"""
        logger.info(f"Searching for song: {song_name}")
        
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, composer
                    FROM songs
                    WHERE title ILIKE %s
                    ORDER BY title
                """, (f'%{song_name}%',))
                
                results = cur.fetchall()
                
                if not results:
                    logger.warning(f"No songs found matching: {song_name}")
                    return None
                
                if len(results) > 1:
                    logger.info(f"Found {len(results)} matching songs:")
                    for i, song in enumerate(results, 1):
                        logger.info(f"  {i}. {song['title']} by {song['composer']}")
                        logger.info(f"     ID: {song['id']}")
                    
                    logger.info(f"Using first result: {results[0]['title']}")
                
                return results[0]
    
    def find_song_by_id(self, song_id):
        """Find a song in the database by ID"""
        logger.info(f"Looking up song ID: {song_id}")
        
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, composer
                    FROM songs
                    WHERE id = %s
                """, (song_id,))
                
                result = cur.fetchone()
                
                if not result:
                    logger.error(f"Song not found with ID: {song_id}")
                    return None
                
                return result
    
    def get_recordings_for_song(self, song_id):
        """Get all recordings for a song with performer information"""
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        r.id,
                        r.album_title,
                        r.recording_year,
                        r.recording_date,
                        r.spotify_url,
                        r.notes,
                        s.title as song_title
                    FROM recordings r
                    JOIN songs s ON r.song_id = s.id
                    WHERE r.song_id = %s
                    ORDER BY r.recording_year DESC NULLS LAST
                """, (song_id,))
                
                recordings = cur.fetchall()
                
                # Get performers for each recording
                for recording in recordings:
                    cur.execute("""
                        SELECT p.name, rp.role
                        FROM recording_performers rp
                        JOIN performers p ON rp.performer_id = p.id
                        WHERE rp.recording_id = %s
                        ORDER BY 
                            CASE rp.role 
                                WHEN 'leader' THEN 1 
                                WHEN 'sideman' THEN 2 
                                ELSE 3 
                            END,
                            p.name
                    """, (recording['id'],))
                    
                    recording['performers'] = cur.fetchall()
                
                return recordings
    
    def search_spotify_track(self, song_title, album_title, artist_name, year=None):
        """Search Spotify for a track"""
        token = self.get_spotify_token()
        
        # Build search query
        # Format: track:song artist:artist album:album year:year
        query_parts = [f'track:"{song_title}"']
        
        if artist_name:
            query_parts.append(f'artist:"{artist_name}"')
        
        if album_title:
            query_parts.append(f'album:"{album_title}"')
        
        if year:
            query_parts.append(f'year:{year}')
        
        query = ' '.join(query_parts)
        
        url = "https://api.spotify.com/v1/search"
        headers = {
            'Authorization': f'Bearer {token}'
        }
        params = {
            'q': query,
            'type': 'track',
            'limit': 5
        }
        
        try:
            time.sleep(0.1)  # Rate limiting - be nice to Spotify
            logger.debug(f"    Searching Spotify: {query}")
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            tracks = data.get('tracks', {}).get('items', [])
            
            if not tracks:
                logger.debug(f"    ✗ No Spotify matches found")
                return None
            
            # Return the best match (first result)
            best_match = tracks[0]
            track_id = best_match['id']
            track_name = best_match['name']
            track_artists = ', '.join([a['name'] for a in best_match['artists']])
            track_album = best_match['album']['name']
            track_url = best_match['external_urls']['spotify']
            
            logger.debug(f"    ✓ Found: '{track_name}' by {track_artists}")
            logger.debug(f"       Album: '{track_album}'")
            logger.debug(f"       URL: {track_url}")
            
            return {
                'id': track_id,
                'url': track_url,
                'name': track_name,
                'artists': track_artists,
                'album': track_album
            }
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                # Token expired, clear it
                self.access_token = None
                logger.warning("Spotify token expired, will refresh on next request")
            else:
                logger.error(f"Spotify API error: {e}")
            self.stats['errors'] += 1
            return None
        except Exception as e:
            logger.error(f"Error searching Spotify: {e}")
            self.stats['errors'] += 1
            return None
    
    def update_recording_spotify_url(self, conn, recording_id, spotify_url):
        """Update a recording with Spotify URL"""
        if self.dry_run:
            logger.info(f"    [DRY RUN] Would update recording with Spotify URL")
            return True
        
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE recordings
                SET spotify_url = %s
                WHERE id = %s
            """, (spotify_url, recording_id))
            
            conn.commit()
            logger.info(f"    ✓ Updated recording with Spotify URL")
            self.stats['recordings_updated'] += 1
            return True
    
    def match_recordings_for_song(self, song_identifier):
        """Main method to match Spotify tracks for all recordings of a song"""
        logger.info("="*80)
        logger.info("Spotify Track Matcher")
        logger.info("="*80)
        
        if self.dry_run:
            logger.info("*** DRY RUN MODE - No database changes will be made ***")
            logger.info("")
        
        # Find the song
        if song_identifier.startswith('song-') or len(song_identifier) == 36:
            song = self.find_song_by_id(song_identifier)
        else:
            song = self.find_song_by_name(song_identifier)
        
        if not song:
            logger.error("Song not found. Exiting.")
            return False
        
        logger.info("")
        logger.info(f"Song: {song['title']}")
        logger.info(f"Composer: {song['composer']}")
        logger.info(f"Database ID: {song['id']}")
        logger.info("")
        
        # Get recordings
        recordings = self.get_recordings_for_song(song['id'])
        
        if not recordings:
            logger.warning("No recordings found for this song.")
            return False
        
        logger.info(f"Found {len(recordings)} recordings to process")
        logger.info("")
        
        # Process each recording
        with self.get_db_connection() as conn:
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
  python match_spotify_tracks.py "Take Five"
  
  # Match by song ID
  python match_spotify_tracks.py a1b2c3d4-e5f6-7890-abcd-ef1234567890
  
  # Dry run to see what would be matched
  python match_spotify_tracks.py "Blue in Green" --dry-run
  
  # Enable debug logging
  python match_spotify_tracks.py "Autumn Leaves" --debug
        """
    )
    
    parser.add_argument(
        'song',
        help='Song name or database ID'
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
    matcher = SpotifyMatcher(dry_run=args.dry_run)
    
    try:
        success = matcher.match_recordings_for_song(args.song)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nMatching cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()