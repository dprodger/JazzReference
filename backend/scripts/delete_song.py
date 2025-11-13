#!/usr/bin/env python3
"""
Delete Song Script
Removes a song and all its associated data from the database.

Deletes in the following order:
1. solo_transcriptions
2. recording_performers
3. recordings
4. repertoire_songs (if exists)
5. songs

This script handles both deletion by song name (with disambiguation if multiple
matches exist) or by UUID.
"""

import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


from db_utils import get_db_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('log/delete_song.log')
    ]
)
logger = logging.getLogger(__name__)


class SongDeleter:
    """Handles deletion of songs and all associated data"""
    
    def __init__(self, dry_run=False):
        """
        Initialize the song deleter
        
        Args:
            dry_run: If True, show what would be deleted without making changes
        """
        self.dry_run = dry_run
        self.stats = {
            'solo_transcriptions_deleted': 0,
            'recording_performers_deleted': 0,
            'recordings_deleted': 0,
            'repertoire_songs_deleted': 0,
            'songs_deleted': 0
        }
    
    def find_song(self, identifier):
        """
        Find a song by name or UUID
        
        Args:
            identifier: Song name or UUID
            
        Returns:
            Song dict if found, None otherwise
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Try as UUID first
                try:
                    cur.execute("""
                        SELECT id, title, composer
                        FROM songs
                        WHERE id = %s
                    """, (identifier,))
                    
                    song = cur.fetchone()
                    if song:
                        return song
                except Exception:
                    # Not a valid UUID, rollback transaction and continue to name search
                    conn.rollback()
                
                # Search by name (case-insensitive)
                cur.execute("""
                    SELECT id, title, composer
                    FROM songs
                    WHERE LOWER(title) = LOWER(%s)
                """, (identifier,))
                
                songs = cur.fetchall()
                
                if not songs:
                    logger.warning(f"No song found matching: {identifier}")
                    return None
                
                if len(songs) == 1:
                    return songs[0]
                
                # Multiple matches - show options
                logger.info(f"\nFound {len(songs)} songs matching '{identifier}':")
                logger.info("")
                for i, song in enumerate(songs, 1):
                    composer = song['composer'] if song['composer'] else 'Unknown composer'
                    logger.info(f"{i}. {song['title']} - {composer}")
                    logger.info(f"   ID: {song['id']}")
                
                logger.info("")
                logger.info("Please re-run the script using the specific song ID:")
                logger.info(f"  python delete_song.py --id <song-id>")
                
                return None
    
    def get_deletion_info(self, song_id):
        """
        Get information about what will be deleted
        
        Args:
            song_id: UUID of the song
            
        Returns:
            Dictionary with counts of related records
        """
        info = {
            'solo_transcriptions': [],
            'recording_performers': [],
            'recordings': [],
            'repertoire_songs': []
        }
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get solo transcriptions
                cur.execute("""
                    SELECT st.id, st.youtube_url, r.album_title
                    FROM solo_transcriptions st
                    JOIN recordings r ON st.recording_id = r.id
                    WHERE st.song_id = %s
                    ORDER BY r.recording_year
                """, (song_id,))
                info['solo_transcriptions'] = cur.fetchall()
                
                # Get recordings and their performers
                cur.execute("""
                    SELECT r.id, r.album_title, r.recording_year,
                           COUNT(DISTINCT rp.id) as performer_count
                    FROM recordings r
                    LEFT JOIN recording_performers rp ON r.id = rp.recording_id
                    WHERE r.song_id = %s
                    GROUP BY r.id, r.album_title, r.recording_year
                    ORDER BY r.recording_year
                """, (song_id,))
                recordings = cur.fetchall()
                info['recordings'] = recordings
                
                # Get total recording_performers count
                cur.execute("""
                    SELECT COUNT(*)
                    FROM recording_performers rp
                    JOIN recordings r ON rp.recording_id = r.id
                    WHERE r.song_id = %s
                """, (song_id,))
                result = cur.fetchone()
                info['recording_performers_count'] = result['count']
                
                # Get repertoire_songs
                cur.execute("""
                    SELECT rs.repertoire_id, rep.name
                    FROM repertoire_songs rs
                    JOIN repertoires rep ON rs.repertoire_id = rep.id
                    WHERE rs.song_id = %s
                """, (song_id,))
                info['repertoire_songs'] = cur.fetchall()
        
        return info
    
    def display_deletion_plan(self, song, info):
        """
        Display what will be deleted
        
        Args:
            song: Song dict
            info: Dictionary with deletion info
        """
        logger.info("")
        logger.info("="*80)
        logger.info("DELETION PLAN")
        logger.info("="*80)
        logger.info(f"Song: {song['title']}")
        composer = song['composer'] if song['composer'] else 'Unknown composer'
        logger.info(f"Composer: {composer}")
        logger.info(f"ID: {song['id']}")
        logger.info("")
        
        # Solo transcriptions
        trans_count = len(info['solo_transcriptions'])
        logger.info(f"Solo Transcriptions to delete: {trans_count}")
        if trans_count > 0:
            for trans in info['solo_transcriptions']:
                album = trans['album_title'] if trans['album_title'] else 'Unknown album'
                logger.info(f"  - {album}")
                if trans['youtube_url']:
                    logger.info(f"    YouTube: {trans['youtube_url']}")
        
        # Recordings and performers
        rec_count = len(info['recordings'])
        logger.info(f"\nRecordings to delete: {rec_count}")
        if rec_count > 0:
            for rec in info['recordings']:
                album = rec['album_title'] if rec['album_title'] else 'Unknown album'
                year = rec['recording_year'] if rec['recording_year'] else 'Unknown year'
                logger.info(f"  - {album} ({year}) - {rec['performer_count']} performer(s)")
        
        perf_count = info['recording_performers_count']
        logger.info(f"\nRecording Performers to delete: {perf_count}")
        
        # Repertoire associations
        rep_count = len(info['repertoire_songs'])
        logger.info(f"\nRepertoire associations to delete: {rep_count}")
        if rep_count > 0:
            for rep in info['repertoire_songs']:
                logger.info(f"  - {rep['name']}")
        
        logger.info("="*80)
        logger.info("")
    
    def delete_song(self, song_id):
        """
        Delete the song and all associated data
        
        Args:
            song_id: UUID of the song to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Delete solo_transcriptions
                    if self.dry_run:
                        cur.execute("""
                            SELECT COUNT(*) FROM solo_transcriptions
                            WHERE song_id = %s
                        """, (song_id,))
                        count = cur.fetchone()['count']
                        self.stats['solo_transcriptions_deleted'] = count
                        logger.info(f"[DRY RUN] Would delete {count} solo transcription(s)")
                    else:
                        cur.execute("""
                            DELETE FROM solo_transcriptions
                            WHERE song_id = %s
                        """, (song_id,))
                        self.stats['solo_transcriptions_deleted'] = cur.rowcount
                        logger.info(f"✓ Deleted {cur.rowcount} solo transcription(s)")
                    
                    # Delete recording_performers (through recordings)
                    if self.dry_run:
                        cur.execute("""
                            SELECT COUNT(*) FROM recording_performers rp
                            JOIN recordings r ON rp.recording_id = r.id
                            WHERE r.song_id = %s
                        """, (song_id,))
                        count = cur.fetchone()['count']
                        self.stats['recording_performers_deleted'] = count
                        logger.info(f"[DRY RUN] Would delete {count} recording performer(s)")
                    else:
                        cur.execute("""
                            DELETE FROM recording_performers
                            WHERE recording_id IN (
                                SELECT id FROM recordings WHERE song_id = %s
                            )
                        """, (song_id,))
                        self.stats['recording_performers_deleted'] = cur.rowcount
                        logger.info(f"✓ Deleted {cur.rowcount} recording performer(s)")
                    
                    # Delete recordings
                    if self.dry_run:
                        cur.execute("""
                            SELECT COUNT(*) FROM recordings
                            WHERE song_id = %s
                        """, (song_id,))
                        count = cur.fetchone()['count']
                        self.stats['recordings_deleted'] = count
                        logger.info(f"[DRY RUN] Would delete {count} recording(s)")
                    else:
                        cur.execute("""
                            DELETE FROM recordings
                            WHERE song_id = %s
                        """, (song_id,))
                        self.stats['recordings_deleted'] = cur.rowcount
                        logger.info(f"✓ Deleted {cur.rowcount} recording(s)")
                    
                    # Delete repertoire_songs
                    if self.dry_run:
                        cur.execute("""
                            SELECT COUNT(*) FROM repertoire_songs
                            WHERE song_id = %s
                        """, (song_id,))
                        count = cur.fetchone()['count']
                        self.stats['repertoire_songs_deleted'] = count
                        logger.info(f"[DRY RUN] Would delete {count} repertoire association(s)")
                    else:
                        cur.execute("""
                            DELETE FROM repertoire_songs
                            WHERE song_id = %s
                        """, (song_id,))
                        self.stats['repertoire_songs_deleted'] = cur.rowcount
                        logger.info(f"✓ Deleted {cur.rowcount} repertoire association(s)")
                    
                    # Delete the song itself
                    if self.dry_run:
                        self.stats['songs_deleted'] = 1
                        logger.info(f"[DRY RUN] Would delete song")
                    else:
                        cur.execute("""
                            DELETE FROM songs
                            WHERE id = %s
                        """, (song_id,))
                        self.stats['songs_deleted'] = cur.rowcount
                        logger.info(f"✓ Deleted song")
                    
                    if not self.dry_run:
                        conn.commit()
                        logger.info("")
                        logger.info("✓ All changes committed successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Error during deletion: {e}", exc_info=True)
            return False
    
    def run(self, identifier):
        """
        Main execution method
        
        Args:
            identifier: Song name or UUID
            
        Returns:
            True if successful, False otherwise
        """
        logger.info("="*80)
        logger.info("DELETE SONG")
        logger.info("="*80)
        
        if self.dry_run:
            logger.info("*** DRY RUN MODE - No database changes will be made ***")
            logger.info("")
        
        # Find the song
        logger.info(f"Looking for song: {identifier}")
        song = self.find_song(identifier)
        
        if not song:
            return False
        
        logger.info(f"✓ Found: {song['title']}")
        
        # Get deletion information
        info = self.get_deletion_info(song['id'])
        
        # Display plan
        self.display_deletion_plan(song, info)
        
        # Confirm deletion if not dry run
        if not self.dry_run:
            logger.info("WARNING: This will permanently delete the song and all associated data!")
            response = input("Type 'DELETE' to confirm: ")
            
            if response != 'DELETE':
                logger.info("Deletion cancelled by user")
                return False
            
            logger.info("")
        
        # Perform deletion
        logger.info("Starting deletion process...")
        logger.info("")
        
        success = self.delete_song(song['id'])
        
        if success:
            self.print_summary()
        
        return success
    
    def print_summary(self):
        """Print deletion summary"""
        logger.info("")
        logger.info("="*80)
        logger.info("DELETION SUMMARY")
        logger.info("="*80)
        logger.info(f"Solo transcriptions:      {self.stats['solo_transcriptions_deleted']}")
        logger.info(f"Recording performers:     {self.stats['recording_performers_deleted']}")
        logger.info(f"Recordings:               {self.stats['recordings_deleted']}")
        logger.info(f"Repertoire associations:  {self.stats['repertoire_songs_deleted']}")
        logger.info(f"Songs:                    {self.stats['songs_deleted']}")
        logger.info("="*80)


def main():
    parser = argparse.ArgumentParser(
        description='Delete a song and all its associated data from the database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Delete by song name (will show matches if multiple found)
  python delete_song.py --name "Blue in Green"
  
  # Delete by UUID (no ambiguity)
  python delete_song.py --id "123e4567-e89b-12d3-a456-426614174000"
  
  # Dry run to see what would be deleted
  python delete_song.py --name "All Blues" --dry-run
  
  # Enable debug logging
  python delete_song.py --name "Autumn Leaves" --debug
  
  # Combine flags
  python delete_song.py --id "123e4567-e89b-12d3-a456-426614174000" --dry-run --debug
        """
    )
    
    # Mutually exclusive group for name or id
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--name',
        help='Song name to search for'
    )
    group.add_argument(
        '--id',
        help='Song UUID'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without making changes'
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
    
    # Get identifier (name or id)
    identifier = args.name if args.name else args.id
    
    # Create deleter and run
    deleter = SongDeleter(dry_run=args.dry_run)
    
    try:
        success = deleter.run(identifier)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nDeletion cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()