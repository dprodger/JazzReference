#!/usr/bin/env python3
"""
MusicBrainz Release Importer
Fetches releases for songs with MusicBrainz IDs and imports them into the database
"""

import sys
import json
import time
import argparse
import logging
import os
from datetime import datetime
import requests

# Import shared database utilities
sys.path.insert(0, '/mnt/project/scripts')
from db_utils import get_db_connection
from mb_performer_importer import PerformerImporter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('log/mb_import.log')
    ]
)
logger = logging.getLogger(__name__)

class MusicBrainzImporter:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'JazzReference/1.0 (https://github.com/yourusername/jazzreference)',
            'Accept': 'application/json'
        })
        self.performer_importer = PerformerImporter(dry_run=dry_run)
        self.stats = {
            'releases_found': 0,
            'releases_imported': 0,
            'releases_skipped': 0,
            'errors': 0
        }
   
    def find_song_by_name(self, song_name):
        """Find a song in the database by name"""
        logger.info(f"Searching for song: {song_name}")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, composer, musicbrainz_id
                    FROM songs
                    WHERE title ILIKE %s
                    ORDER BY title
                """, (f'%{song_name}%',))
                
                results = cur.fetchall()
                
                if not results:
                    logger.warning(f"No songs found matching: {song_name}")
                    return None
                
                logger.info(f"Results is {results}")
                if len(results) > 1:
                    logger.info(f"Found {len(results)} matching songs:")
                    for i, song in enumerate(results, 1):
                        mb_status = "✓ Has MusicBrainz ID" if song['musicbrainz_id'] else "✗ No MusicBrainz ID"
                        logger.info(f"  {i}. {song['title']} by {song['composer']} - {mb_status}")
                        logger.info(f"     ID: {song['id']}")
                    
                    # Return first one with MusicBrainz ID, or first result
                    for song in results:
                        if song['musicbrainz_id']:
                            logger.info(f"Using: {song['title']} (has MusicBrainz ID)")
                            return song
                    
                    logger.info(f"Using first result: {results[0]['title']} (no MusicBrainz ID)")
                    return results[0]
                
                return results[0]
    
    def find_song_by_id(self, song_id):
        """Find a song in the database by ID"""
        logger.info(f"Looking up song ID: {song_id}")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, composer, musicbrainz_id
                    FROM songs
                    WHERE id = %s
                """, (song_id,))
                
                result = cur.fetchone()
                
                if not result:
                    logger.error(f"Song not found with ID: {song_id}")
                    return None
                
                return result
    
    def fetch_musicbrainz_recordings(self, work_id, limit=100, offset=0):
        """Fetch recordings for a MusicBrainz work ID"""
        logger.info(f"Fetching recordings for MusicBrainz work: {work_id}")
        
        # Use the work endpoint to get recordings, not the recording endpoint
        url = f"https://musicbrainz.org/ws/2/work/{work_id}"
        params = {
            'inc': 'recording-rels',
            'fmt': 'json'
        }
        
        try:
            time.sleep(1.0)  # Rate limiting - MusicBrainz requires 1 req/sec
            logger.debug(f"Requesting: {url} with params: {params}")
            response = self.session.get(url, params=params)
            
            # Log response for debugging
            logger.debug(f"Response status: {response.status_code}")
            
            response.raise_for_status()
            
            data = response.json()
            
            # Extract recordings from relations
            recordings = []
            relations = data.get('relations', [])
            
            logger.info(f"Found {len(relations)} related recordings in work")
            
            for i, relation in enumerate(relations, 1):
                if relation.get('type') == 'performance' and 'recording' in relation:
                    recording = relation['recording']
                    recording_id = recording.get('id')
                    recording_title = recording.get('title', 'Unknown')
                    
                    logger.debug(f"  [{i}/{len(relations)}] Found recording: {recording_title} (ID: {recording_id})")
                    
                    if recording_id:
                        # Fetch full recording details
                        full_recording = self.fetch_recording_detail(recording_id)
                        if full_recording:
                            recordings.append(full_recording)
                            if len(recordings) >= limit:
                                logger.info(f"Reached limit of {limit} recordings")
                                break
            
            logger.info(f"Successfully fetched details for {len(recordings)} recordings")
            
            return recordings
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error fetching MusicBrainz work: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_text = e.response.text
                    logger.error(f"Response content: {error_text}")
                except:
                    logger.error("Could not decode response content")
            self.stats['errors'] += 1
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching MusicBrainz work: {e}")
            self.stats['errors'] += 1
            return []
    
    def fetch_recording_detail(self, recording_id):
        """Fetch detailed information about a specific recording including artist relationships"""
        url = f"https://musicbrainz.org/ws/2/recording/{recording_id}"
        params = {
            'inc': 'releases+artist-credits+artist-rels',
            'fmt': 'json'
        }
        
        try:
            time.sleep(1.0)  # Rate limiting
            logger.debug(f"    Fetching full details for recording: {recording_id}")
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Log key information about the recording
            title = data.get('title', 'Unknown')
            
            # Get artist names
            artist_credits = data.get('artist-credit', [])
            artists = [ac.get('artist', {}).get('name', 'Unknown') for ac in artist_credits]
            artist_str = ', '.join(artists) if artists else 'Unknown'
            
            # Get releases
            releases = data.get('releases', [])
            release_count = len(releases)
            
            if releases:
                first_release = releases[0]
                release_title = first_release.get('title', 'Unknown')
                release_date = first_release.get('date', 'Unknown date')
                
                logger.debug(f"    ✓ Recording: '{title}' by {artist_str}")
                logger.debug(f"       First release: '{release_title}' ({release_date})")
                logger.debug(f"       Total releases: {release_count}")
            else:
                logger.debug(f"    ⚠ Recording: '{title}' by {artist_str} - No releases found")
            
            return data
            
        except Exception as e:
            logger.warning(f"    ✗ Error fetching recording {recording_id}: {e}")
            return None
    
    def check_recording_exists(self, conn, song_id, album_title):
        """Check if a recording already exists"""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM recordings
                WHERE song_id = %s AND album_title = %s
            """, (song_id, album_title))
            
            result = cur.fetchone()
            return result is not None
    
    def import_recording(self, conn, song_id, recording_data):
        """Import a single recording into the database"""
        # Extract release information
        releases = recording_data.get('releases', [])
        if not releases:
            logger.debug("Recording has no releases, skipping")
            return False
        
        # Use the first release
        release = releases[0]
        album_title = release.get('title', 'Unknown Album')
        
        # Check if already exists
        if self.check_recording_exists(conn, song_id, album_title):
            logger.debug(f"Recording already exists: {album_title}")
            self.stats['releases_skipped'] += 1
            return False
        
        # Extract date - handle various formats
        release_date = release.get('date', '')
        release_year = None
        formatted_date = None
        
        if release_date:
            try:
                # Try to extract year
                release_year = int(release_date.split('-')[0])
                
                # Format the date properly for PostgreSQL
                parts = release_date.split('-')
                if len(parts) == 3:
                    # Full date: YYYY-MM-DD
                    formatted_date = release_date
                elif len(parts) == 2:
                    # Year and month: YYYY-MM, use first day of month
                    formatted_date = f"{parts[0]}-{parts[1]}-01"
                elif len(parts) == 1:
                    # Year only: YYYY, use January 1st
                    formatted_date = f"{parts[0]}-01-01"
                else:
                    # Invalid format, just use year
                    formatted_date = None
                    
            except (ValueError, IndexError):
                logger.debug(f"Could not parse date: {release_date}")
                pass
        
        if self.dry_run:
            logger.info(f"[DRY RUN] Would import: {album_title} ({release_year or 'unknown year'})")
            logger.info(f"[DRY RUN]   Date: {formatted_date or 'None'}")
            # Show performer info that would be imported
            self.performer_importer.link_performers_to_recording(conn, None, recording_data)
            self.stats['releases_found'] += 1
            return True
        
        # Insert recording
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO recordings (
                    song_id, album_title, recording_year, recording_date,
                    is_canonical, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                song_id,
                album_title,
                release_year,
                formatted_date,
                False,  # Not canonical by default
                f"Imported from MusicBrainz - Recording ID: {recording_data.get('id')}"
            ))
            
            recording_id = cur.fetchone()['id']
            logger.info(f"✓ Imported recording: {album_title} (ID: {recording_id})")
            
            # Link performers using shared importer
            self.performer_importer.link_performers_to_recording(conn, recording_id, recording_data)
            
            conn.commit()
            self.stats['releases_imported'] += 1
            return True
    
    def import_releases_for_song(self, song_identifier):
        """Main method to import releases for a song"""
        logger.info("="*80)
        logger.info("MusicBrainz Release Import")
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
        logger.info(f"MusicBrainz Work ID: {song['musicbrainz_id']}")
        logger.info("")
        
        # Check for MusicBrainz ID
        if not song['musicbrainz_id']:
            logger.error("This song does not have a MusicBrainz ID. Cannot import releases.")
            logger.info("You need to add a MusicBrainz Work ID to this song first.")
            return False
        
        # Fetch recordings from MusicBrainz
        recordings = self.fetch_musicbrainz_recordings(song['musicbrainz_id'])
        
        if not recordings:
            logger.warning("No recordings found in MusicBrainz for this work.")
            return False
        
        logger.info(f"Processing {len(recordings)} recordings...")
        logger.info("")
        
        # Import each recording
        with get_db_connection() as conn:
            for i, recording in enumerate(recordings, 1):
                logger.info(f"[{i}/{len(recordings)}] Processing: {recording.get('title', 'Unknown')}")
                try:
                    self.import_recording(conn, song['id'], recording)
                except Exception as e:
                    logger.error(f"Error importing recording: {e}")
                    self.stats['errors'] += 1
                    if not self.dry_run:
                        conn.rollback()
        
        # Print summary
        logger.info("")
        logger.info("="*80)
        logger.info("IMPORT SUMMARY")
        logger.info("="*80)
        logger.info(f"Recordings found:    {self.stats['releases_found'] + self.stats['releases_imported']}")
        logger.info(f"Recordings imported: {self.stats['releases_imported']}")
        logger.info(f"Recordings skipped:  {self.stats['releases_skipped']} (already exist)")
        logger.info(f"Performers created:  {self.performer_importer.stats['performers_created']}")
        logger.info(f"Instruments created: {self.performer_importer.stats['instruments_created']}")
        logger.info(f"Errors:              {self.stats['errors']}")
        logger.info("="*80)
        
        return True

def main():
    parser = argparse.ArgumentParser(
        description='Import MusicBrainz releases for a jazz song',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import by song name
  python import_mb_releases.py --name "Take Five"
  
  # Import by song ID
  python import_mb_releases.py --id a1b2c3d4-e5f6-7890-abcd-ef1234567890
  
  # Dry run to see what would be imported
  python import_mb_releases.py --name "Blue in Green" --dry-run
  
  # Enable debug logging
  python import_mb_releases.py --name "Autumn Leaves" --debug
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
        '--dry-run',
        action='store_true',
        help='Show what would be imported without making changes'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Maximum number of recordings to fetch (default: 100)'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create importer and run
    importer = MusicBrainzImporter(dry_run=args.dry_run)

    # Determine song identifier
    song_identifier = args.name if args.name else args.id
    
    try:
        success = importer.import_releases_for_song(song_identifier)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nImport cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()