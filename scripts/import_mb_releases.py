#!/usr/bin/env python3
"""
MusicBrainz Release Importer
Fetches releases for songs with MusicBrainz IDs and imports them into the database
"""

import sys
import json
import argparse
import logging
import os
from datetime import datetime

# Import shared database utilities
sys.path.insert(0, '/mnt/project/scripts')
from db_utils import get_db_connection
from db_utils import normalize_apostrophes
from mb_performer_importer import PerformerImporter
from mb_utils import MusicBrainzSearcher

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
        self.mb_searcher = MusicBrainzSearcher()
        self.performer_importer = PerformerImporter(dry_run=dry_run)
        self.stats = {
            'releases_found': 0,
            'releases_imported': 0,
            'releases_skipped': 0,
            'credits_added': 0,
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
        
        try:
            # Use cached method from mb_utils
            data = self.mb_searcher.get_work_recordings(work_id)
            
            if not data:
                logger.error(f"Could not fetch work from MusicBrainz")
                self.stats['errors'] += 1
                return []
            
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
            
        except Exception as e:
            logger.error(f"Error fetching MusicBrainz work: {e}")
            self.stats['errors'] += 1
            return []
    
    def fetch_recording_detail(self, recording_id):
        """Fetch detailed information about a specific recording including artist relationships"""
        try:
            # Use cached method from mb_utils
            data = self.mb_searcher.get_recording_details(recording_id)
            
            if not data:
                logger.debug(f"    Could not fetch recording details")
                return None
            
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
        """
        Check if a recording already exists
        
        Returns:
            tuple: (exists: bool, recording_id: str or None)
        """
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM recordings
                WHERE song_id = %s AND album_title = %s
            """, (song_id, album_title))
            
            result = cur.fetchone()
            if result:
                return (True, result['id'])
            return (False, None)
    
    def get_existing_credits(self, conn, recording_id):
        """
        Fetch existing performer credits for a recording
        
        Returns:
            List of dicts with keys: performer_name, performer_mbid, instrument_name, role
        """
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    p.name as performer_name,
                    p.musicbrainz_id as performer_mbid,
                    i.name as instrument_name,
                    rp.role
                FROM recording_performers rp
                JOIN performers p ON rp.performer_id = p.id
                LEFT JOIN instruments i ON rp.instrument_id = i.id
                WHERE rp.recording_id = %s
            """, (recording_id,))
            
            return cur.fetchall()
    
    def should_update_credits(self, existing_credits, new_performers):
        """
        Determine if we should update credits based on comparing existing vs new
        
        Args:
            existing_credits: List of existing credit dicts from database
            new_performers: List of new performer dicts to potentially import
            
        Returns:
            tuple: (should_update: bool, reason: str)
        """
        if not existing_credits:
            return (True, "no existing credits")
        
        # Count instruments in existing vs new
        existing_with_instruments = sum(1 for c in existing_credits if c['instrument_name'])
        new_with_instruments = sum(1 for p in new_performers if p.get('instruments'))
        
        # If existing credits have no instruments but new ones do, update
        if existing_with_instruments == 0 and new_with_instruments > 0:
            return (True, f"existing has no instruments, new has {new_with_instruments}")
        
        # If new credits have significantly more detail, update
        if len(new_performers) > len(existing_credits) * 1.5:
            return (True, f"new has significantly more performers ({len(new_performers)} vs {len(existing_credits)})")
        
        # Check if new credits add performers not in existing
        existing_names = {c['performer_name'].lower() for c in existing_credits}
        existing_mbids = {c['performer_mbid'] for c in existing_credits if c['performer_mbid']}
        
        new_names = {p['name'].lower() for p in new_performers if p.get('name')}
        new_mbids = {p['mbid'] for p in new_performers if p.get('mbid')}
        
        # Find performers in new that aren't in existing
        new_unique_names = new_names - existing_names
        new_unique_mbids = new_mbids - existing_mbids
        
        if new_unique_names or new_unique_mbids:
            return (True, f"new credits add {len(new_unique_names)} new performers")
        
        # Otherwise, skip - existing credits are good enough
        return (False, "existing credits are sufficient")
    
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
        exists, existing_recording_id = self.check_recording_exists(conn, song_id, album_title)
        
        if exists:
            logger.debug(f"Recording already exists: {album_title}")
            
            # Get existing credits to compare
            existing_credits = self.get_existing_credits(conn, existing_recording_id)
            
            if existing_credits:
                logger.debug(f"  Recording has {len(existing_credits)} existing credit(s)")
                
                # Parse what we would import to compare
                # First, parse the relationships to see what performers we'd add
                relations = recording_data.get('relations', [])
                new_performers = self.performer_importer.parse_artist_relationships(relations)
                
                # If no relationships, try the first release
                if not new_performers:
                    releases_list = recording_data.get('releases', [])
                    if releases_list:
                        first_release_id = releases_list[0].get('id')
                        release_data = self.performer_importer.fetch_release_credits(first_release_id)
                        if release_data:
                            mb_recording_id = recording_data.get('id')
                            new_performers = self.performer_importer.parse_release_artist_credits(release_data, mb_recording_id)
                
                # If still no performers, fall back to artist credits
                if not new_performers:
                    artist_credits = recording_data.get('artist-credit', [])
                    artists = self.performer_importer.parse_artist_credits(artist_credits)
                    new_performers = [
                        {'name': a['name'], 'mbid': a['mbid'], 'instruments': [], 'role': 'performer'}
                        for a in artists
                    ]
                
                # Decide if we should update
                should_update, reason = self.should_update_credits(existing_credits, new_performers)
                
                if not should_update:
                    logger.info(f"  Skipping - {reason}")
                    self.stats['releases_skipped'] += 1
                    return False
                else:
                    logger.info(f"  Updating credits - {reason}")
                    
                    if self.dry_run:
                        logger.info(f"[DRY RUN]   Would update existing recording with new credits")
                        self.performer_importer.link_performers_to_recording(conn, None, recording_data)
                        self.stats['credits_added'] += 1
                        return True
                    
                    # Add new performers to existing recording
                    performers_linked = self.performer_importer.link_performers_to_recording(
                        conn, existing_recording_id, recording_data
                    )
                    
                    if performers_linked > 0:
                        conn.commit()
                        logger.info(f"  ✓ Added {performers_linked} performer credit(s) to existing recording")
                        self.stats['credits_added'] += 1
                    else:
                        logger.debug(f"  No new performer credits to add")
                    
                    return True
            else:
                # No existing credits, add them
                logger.info(f"  Recording exists but has no credits, adding them...")
                
                if self.dry_run:
                    logger.info(f"[DRY RUN]   Would add credits to existing recording")
                    self.performer_importer.link_performers_to_recording(conn, None, recording_data)
                    self.stats['credits_added'] += 1
                    return True
                
                # Add performers to existing recording
                performers_linked = self.performer_importer.link_performers_to_recording(
                    conn, existing_recording_id, recording_data
                )
                
                if performers_linked > 0:
                    conn.commit()
                    logger.info(f"  ✓ Added {performers_linked} performer credit(s) to existing recording")
                    self.stats['credits_added'] += 1
                else:
                    logger.debug(f"  No performer credits to add")
                
                return True
        
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
        
        # Extract MusicBrainz recording ID
        mb_recording_id = recording_data.get('id')
        
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
                    is_canonical, musicbrainz_id
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                song_id,
                album_title,
                release_year,
                formatted_date,
                False,  # Not canonical by default
                mb_recording_id
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
        logger.info(f"Recordings skipped:  {self.stats['releases_skipped']} (already exist with credits)")
        logger.info(f"Credits added:       {self.stats['credits_added']} (to existing recordings)")
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
    song_identifier = normalize_apostrophes(args.name) if args.name else args.id
    
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