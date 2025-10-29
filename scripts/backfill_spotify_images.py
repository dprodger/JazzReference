#!/usr/bin/env python3
"""
Spotify Album Artwork Backfill
Fetches album artwork for existing recordings that have Spotify URLs but no images
"""

import sys
import time
import argparse
import logging
import os
import base64
import requests
from dotenv import load_dotenv

# Import shared database utilities
from db_utils import get_db_connection

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('log/spotify_backfill.log')
    ]
)
logger = logging.getLogger(__name__)


class SpotifyImageBackfill:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.access_token = None
        self.token_expires = 0
        self.stats = {
            'recordings_processed': 0,
            'recordings_updated': 0,
            'recordings_skipped': 0,
            'errors': 0
        }
    
    def get_spotify_token(self):
        """Get Spotify access token using client credentials flow"""
        client_id = os.environ.get('SPOTIFY_CLIENT_ID')
        client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            logger.error("Spotify credentials not found!")
            logger.error("")
            logger.error("Please set the following environment variables:")
            logger.error("  export SPOTIFY_CLIENT_ID='your_client_id'")
            logger.error("  export SPOTIFY_CLIENT_SECRET='your_client_secret'")
            raise ValueError("Missing Spotify credentials")
        
        # Check if token is still valid
        if self.access_token and time.time() < self.token_expires:
            return self.access_token
        
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
            self.token_expires = time.time() + expires_in - 60
            
            logger.info(f"✓ Spotify token obtained (expires in {expires_in}s)")
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get Spotify token: {e}")
            raise
    
    def extract_track_id_from_url(self, spotify_url):
        """Extract Spotify track ID from URL"""
        # URLs are like: https://open.spotify.com/track/TRACK_ID or spotify:track:TRACK_ID
        if not spotify_url:
            return None
        
        if '/track/' in spotify_url:
            track_id = spotify_url.split('/track/')[-1].split('?')[0]
        elif ':track:' in spotify_url:
            track_id = spotify_url.split(':track:')[-1]
        else:
            return None
        
        return track_id
    
    def get_track_details(self, track_id):
        """Get track details including album artwork from Spotify"""
        token = self.get_spotify_token()
        
        headers = {
            'Authorization': f'Bearer {token}'
        }
        
        url = f'https://api.spotify.com/v1/tracks/{track_id}'
        
        try:
            time.sleep(0.1)  # Rate limiting
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract album artwork URLs
            images = data.get('album', {}).get('images', [])
            album_art = {
                'large': None,
                'medium': None,
                'small': None
            }
            
            # Spotify returns images in descending size order
            if len(images) >= 1:
                album_art['large'] = images[0].get('url')
            if len(images) >= 2:
                album_art['medium'] = images[1].get('url')
            if len(images) >= 3:
                album_art['small'] = images[2].get('url')
            
            return {
                'track_id': track_id,
                'album_art': album_art
            }
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                self.access_token = None
                logger.warning("Spotify token expired, will refresh on next request")
            logger.error(f"Failed to get track details: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting track details: {e}")
            return None
    
    def get_recordings_without_images(self):
        """Get recordings that have Spotify URLs but no album artwork"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, spotify_url, album_title
                    FROM recordings
                    WHERE spotify_url IS NOT NULL
                    AND (album_art_medium IS NULL OR album_art_medium = '')
                    ORDER BY recording_year DESC NULLS LAST
                """)
                return cur.fetchall()
    
    def update_recording_images(self, conn, recording_id, track_id, album_art):
        """Update recording with album artwork and track ID"""
        if self.dry_run:
            logger.info(f"    [DRY RUN] Would update with album artwork")
            return
        
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE recordings
                SET spotify_track_id = %s,
                    album_art_small = %s,
                    album_art_medium = %s,
                    album_art_large = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                track_id,
                album_art.get('small'),
                album_art.get('medium'),
                album_art.get('large'),
                recording_id
            ), prepare=False)
            
            conn.commit()
            logger.info(f"    ✓ Updated with album artwork")
            self.stats['recordings_updated'] += 1
    
    def backfill_images(self):
        """Main method to backfill album artwork for existing recordings"""
        logger.info("="*80)
        logger.info("Spotify Album Artwork Backfill")
        logger.info("="*80)
        
        if self.dry_run:
            logger.info("*** DRY RUN MODE - No database changes will be made ***")
        
        logger.info("")
        
        # Get recordings without images
        recordings = self.get_recordings_without_images()
        
        if not recordings:
            logger.info("No recordings found that need album artwork")
            return True
        
        logger.info(f"Found {len(recordings)} recordings to process")
        logger.info("")
        
        # Process each recording
        with get_db_connection() as conn:
            for i, recording in enumerate(recordings, 1):
                self.stats['recordings_processed'] += 1
                
                album = recording['album_title'] or 'Unknown Album'
                spotify_url = recording['spotify_url']
                
                logger.info(f"[{i}/{len(recordings)}] {album}")
                logger.info(f"    URL: {spotify_url[:50]}...")
                
                # Extract track ID from URL
                track_id = self.extract_track_id_from_url(spotify_url)
                if not track_id:
                    logger.warning(f"    ✗ Could not extract track ID from URL")
                    self.stats['errors'] += 1
                    continue
                
                # Get track details with album artwork
                track_details = self.get_track_details(track_id)
                
                if not track_details:
                    logger.warning(f"    ✗ Failed to get track details")
                    self.stats['errors'] += 1
                    continue
                
                album_art = track_details['album_art']
                if not album_art.get('medium'):
                    logger.warning(f"    ✗ No album artwork available")
                    self.stats['errors'] += 1
                    continue
                
                # Update database
                self.update_recording_images(
                    conn,
                    recording['id'],
                    track_id,
                    album_art
                )
                
                logger.info("")
        
        # Print summary
        logger.info("="*80)
        logger.info("BACKFILL SUMMARY")
        logger.info("="*80)
        logger.info(f"Recordings processed: {self.stats['recordings_processed']}")
        logger.info(f"Recordings updated:   {self.stats['recordings_updated']}")
        logger.info(f"Errors:               {self.stats['errors']}")
        logger.info("="*80)
        
        return True


def main():
    parser = argparse.ArgumentParser(
        description='Backfill album artwork for recordings with Spotify URLs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Setup:
  1. Get Spotify API credentials from https://developer.spotify.com/dashboard
  2. Set environment variables:
     export SPOTIFY_CLIENT_ID='your_client_id'
     export SPOTIFY_CLIENT_SECRET='your_client_secret'

Examples:
  # Backfill all recordings
  python backfill_spotify_images.py
  
  # Dry run to see what would be updated
  python backfill_spotify_images.py --dry-run
  
  # Enable debug logging
  python backfill_spotify_images.py --debug
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without making changes'
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
    
    # Create backfill instance and run
    backfill = SpotifyImageBackfill(dry_run=args.dry_run)
    
    try:
        success = backfill.backfill_images()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nBackfill cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()