#!/usr/bin/env python3
"""
Repair Recording Cross-Contamination (Improved Version)

This script repairs recordings that were incorrectly merged due to album title
matching. Uses the same improved detection logic as the diagnostic script.

IMPROVED DETECTION LOGIC:
- Ignores "Various Artists" compilations (normal for recordings to appear on these)
- Normalizes artist credits to detect the primary artist
- Only flags as contaminated when genuinely different primary artists are found

The repair strategy is:
1. Find recordings with cross-contamination (genuinely different artists)
2. Delete the contaminated recording and all its links
3. Re-run the MB release importer to create proper separate recordings

Usage:
  # Find what would be deleted (dry-run)
  python repair_contaminated_recordings.py --song "Born to be Blue" --dry-run
  
  # Actually delete and allow re-import
  python repair_contaminated_recordings.py --song "Born to be Blue"
"""

import sys
import argparse
import logging
import re
from pathlib import Path
from typing import Dict, List, Set, Optional, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_utils import get_db_connection

# Configure logging
LOG_DIR = Path(__file__).parent / 'log'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / 'repair_contaminated_recordings.log')
    ]
)
logger = logging.getLogger(__name__)


# Artist credits to ignore when checking for contamination
COMPILATION_CREDITS = {
    'various artists',
    'various',
    'va',
    'compilation',
    'soundtrack',
    'original soundtrack',
    'ost',
}


def normalize_artist_credit(credit: str) -> str:
    """Normalize an artist credit to extract the primary artist name."""
    if not credit:
        return ''
    
    credit = credit.lower().strip()
    
    suffixes_to_remove = [
        r'\s+trio\b.*$',
        r'\s+quartet\b.*$',
        r'\s+quintet\b.*$',
        r'\s+sextet\b.*$',
        r'\s+septet\b.*$',
        r'\s+octet\b.*$',
        r'\s+orchestra\b.*$',
        r'\s+big band\b.*$',
        r'\s+band\b.*$',
        r'\s+ensemble\b.*$',
        r'\s+group\b.*$',
        r'\s+and his\b.*$',
        r'\s+and her\b.*$',
        r'\s+with\b.*$',
        r'\s+featuring\b.*$',
        r'\s+feat\.?\b.*$',
        r'\s+&\b.*$',
        r'\s+\+\b.*$',
    ]
    
    for suffix in suffixes_to_remove:
        credit = re.sub(suffix, '', credit, flags=re.IGNORECASE)
    
    credit = re.sub(r'^the\s+', '', credit)
    return credit.strip()


def is_compilation_credit(credit: str) -> bool:
    """Check if an artist credit is a compilation/various artists credit."""
    if not credit:
        return False
    normalized = credit.lower().strip()
    return normalized in COMPILATION_CREDITS or 'various artist' in normalized


def extract_primary_artists(artist_credits: Set[str]) -> Set[str]:
    """Extract primary artists from a set of artist credits."""
    primary_artists = set()
    for credit in artist_credits:
        if not credit or is_compilation_credit(credit):
            continue
        normalized = normalize_artist_credit(credit)
        if normalized:
            primary_artists.add(normalized)
    return primary_artists


def are_same_artist(artists: Set[str]) -> bool:
    """Check if a set of normalized artist names likely refers to the same artist."""
    if len(artists) <= 1:
        return True
    
    artists_list = list(artists)
    for i, artist1 in enumerate(artists_list):
        for artist2 in artists_list[i+1:]:
            if artist1 in artist2 or artist2 in artist1:
                continue
            words1 = set(artist1.split())
            words2 = set(artist2.split())
            common_words = words1 & words2
            if common_words and any(len(w) > 3 for w in common_words):
                continue
            return False
    return True


def is_collaboration(artist_credits: Set[str], primary_artists: Set[str]) -> bool:
    """
    Check if the artist credits indicate a legitimate collaboration.
    
    A collaboration is detected when one of the original credits contains
    multiple of the primary artists (e.g., "George Shearing Quintet with Nancy Wilson").
    """
    if len(primary_artists) <= 1:
        return False
    
    for credit in artist_credits:
        if not credit:
            continue
        credit_lower = credit.lower()
        artists_in_credit = sum(1 for artist in primary_artists if artist in credit_lower)
        if artists_in_credit >= 2:
            return True
    
    return False


def extract_composer_names(composer_field: str) -> Set[str]:
    """
    Extract individual composer names from a composer field.
    
    Handles formats like:
    - "George Gershwin" -> {"george gershwin"}
    - "George Gershwin, Ira Gershwin" -> {"george gershwin", "ira gershwin"}
    """
    if not composer_field:
        return set()
    
    composers = set()
    parts = re.split(r'[,;&/]|\band\b', composer_field, flags=re.IGNORECASE)
    
    for part in parts:
        name = part.strip().lower()
        if name and len(name) > 2:
            composers.add(name)
    
    return composers


def filter_out_composers(primary_artists: Set[str], composer_names: Set[str]) -> Set[str]:
    """Remove composer names from the set of primary artists."""
    if not composer_names:
        return primary_artists
    
    filtered = set()
    for artist in primary_artists:
        is_composer = False
        for composer in composer_names:
            if artist == composer or composer in artist or artist in composer:
                is_composer = True
                break
        if not is_composer:
            filtered.add(artist)
    
    return filtered


def performers_match_single_artist(performer_names: List[str], primary_artists: Set[str]) -> bool:
    """
    Check if all performers can be attributed to a single primary artist.
    
    This handles cases where a recording appears on:
    - The original artist's album (credited to "Frank Sinatra")
    - A compilation (credited to "The Rat Pack")
    
    If all performers match just one artist, the other credits are probably
    just reissues/compilations, not contamination.
    """
    if not performer_names or not primary_artists:
        return False
    
    if len(primary_artists) <= 1:
        return True
    
    normalized_performers = [name.lower().strip() for name in performer_names]
    
    for artist in primary_artists:
        matches = 0
        for performer in normalized_performers:
            if (artist in performer or 
                performer in artist or 
                any(word in artist for word in performer.split() if len(word) > 3) or
                any(word in performer for word in artist.split() if len(word) > 3)):
                matches += 1
        
        if matches > 0 and matches >= len(normalized_performers) * 0.5:
            other_matches = 0
            for other_artist in primary_artists:
                if other_artist == artist:
                    continue
                for performer in normalized_performers:
                    if (other_artist in performer or 
                        performer in other_artist or
                        any(word in other_artist for word in performer.split() if len(word) > 3) or
                        any(word in performer for word in other_artist.split() if len(word) > 3)):
                        other_matches += 1
                        break
            
            if other_matches == 0:
                return True
    
    return False


class ContaminatedRecordingRepairer:
    """Repairs contaminated recordings with improved detection logic"""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.stats = {
            'songs_checked': 0,
            'recordings_checked': 0,
            'recordings_contaminated': 0,
            'false_positives_avoided': 0,
            'recordings_deleted': 0,
            'performer_links_deleted': 0,
            'release_links_deleted': 0,
            'errors': 0
        }
    
    def repair_song(self, song_identifier: str) -> Dict[str, Any]:
        """Find and repair contaminated recordings for a song"""
        logger.info(f"Checking song: {song_identifier}")
        
        song_id = None
        song_title = None
        composer_names = set()
        
        # First, look up the song
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Find the song (including composer)
                if len(song_identifier) == 36 and '-' in song_identifier:
                    cur.execute("SELECT id, title, composer FROM songs WHERE id = %s", (song_identifier,))
                else:
                    cur.execute("SELECT id, title, composer FROM songs WHERE title ILIKE %s", (f'%{song_identifier}%',))
                
                song = cur.fetchone()
                if not song:
                    logger.error(f"Song not found: {song_identifier}")
                    return {'contaminated_recordings': [], 'stats': self.stats}
                
                song_id = song['id']
                song_title = song['title']
                composer = song.get('composer', '')
                composer_names = extract_composer_names(composer) if composer else set()
                
                logger.info(f"  {song_title} (ID: {song_id})")
                if composer_names:
                    logger.debug(f"  Composer(s): {composer}")
        
        # Process the song using the batch approach
        contaminated_recordings = self._process_single_song(song_id, song_title, composer_names)
        
        return {
            'song': {'id': song_id, 'title': song_title},
            'contaminated_recordings': contaminated_recordings,
            'stats': self.stats
        }
    
    def repair_all_songs(self) -> Dict[str, Any]:
        """Find and repair contaminated recordings across ALL songs"""
        logger.info("="*80)
        logger.info("RECORDING CROSS-CONTAMINATION REPAIR (ALL SONGS)")
        logger.info("="*80)
        
        if self.dry_run:
            logger.info("*** DRY RUN MODE - No changes will be made ***")
        else:
            logger.info("*** LIVE MODE - Contaminated recordings will be DELETED ***")
        logger.info("")
        logger.info("Detection logic:")
        logger.info("  - Ignores 'Various Artists' compilation credits")
        logger.info("  - Normalizes credits (e.g., 'Stan Getz Quartet' -> 'Stan Getz')")
        logger.info("  - Ignores composer credits (normal for standards)")
        logger.info("  - Checks if performers match single artist (reissues)")
        logger.info("  - Only flags when genuinely different primary artists found")
        logger.info("")
        
        all_contaminated = []
        songs_with_issues = []
        
        # First, get list of all songs (quick query, close connection immediately)
        songs = []
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT s.id, s.title, s.composer
                    FROM songs s
                    JOIN recordings r ON r.song_id = s.id
                    ORDER BY s.title
                """)
                songs = cur.fetchall()
        
        total_songs = len(songs)
        logger.info(f"Found {total_songs} songs with recordings")
        logger.info("")
        
        # Process each song with its own short-lived connection
        for i, song in enumerate(songs, 1):
            song_id = song['id']
            song_title = song['title']
            composer = song.get('composer', '')
            composer_names = extract_composer_names(composer) if composer else set()
            
            logger.info(f"[{i}/{total_songs}] {song_title} Processing")
            self.stats['songs_checked'] += 1
            
            try:
                song_contaminated = self._process_single_song(
                    song_id, song_title, composer_names
                )
                
                if song_contaminated:
                    all_contaminated.extend(song_contaminated)
                    songs_with_issues.append({
                        'song': song_title,
                        'count': len(song_contaminated)
                    })
                    logger.info(f"[{i}/{total_songs}] {song_title}: {len(song_contaminated)} contaminated recording(s)")
                elif i % 50 == 0:
                    # Progress update every 50 songs
                    logger.info(f"[{i}/{total_songs}] Progress: checked {self.stats['recordings_checked']} recordings...")
                    
            except Exception as e:
                self.stats['errors'] += 1
                logger.error(f"[{i}/{total_songs}] Error processing {song_title}: {e}")
                continue
        
        return {
            'contaminated_recordings': all_contaminated,
            'songs_with_issues': songs_with_issues,
            'stats': self.stats
        }
    
    def _process_single_song(self, song_id: str, song_title: str, 
                              composer_names: Set[str]) -> List[Dict]:
        """Process a single song with its own database connection using batch queries"""
        song_contaminated = []
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Query 1: Get all recordings for this song
                cur.execute("""
                    SELECT r.id, r.album_title, r.musicbrainz_id, r.recording_year
                    FROM recordings r
                    WHERE r.song_id = %s
                """, (song_id,))
                recordings = cur.fetchall()
                
                if not recordings:
                    return []
                
                recording_ids = [r['id'] for r in recordings]
                
                # Query 2: Get all performers for all recordings in one query
                cur.execute("""
                    SELECT rp.recording_id, p.name
                    FROM recording_performers rp
                    JOIN performers p ON p.id = rp.performer_id
                    WHERE rp.recording_id = ANY(%s)
                """, (recording_ids,))
                
                # Group performers by recording_id
                performers_by_recording = {}
                for row in cur.fetchall():
                    rec_id = row['recording_id']
                    if rec_id not in performers_by_recording:
                        performers_by_recording[rec_id] = []
                    performers_by_recording[rec_id].append(row['name'])
                
                # Query 3: Get all releases for all recordings in one query
                cur.execute("""
                    SELECT DISTINCT rr.recording_id, rel.artist_credit
                    FROM recording_releases rr
                    JOIN releases rel ON rel.id = rr.release_id
                    WHERE rr.recording_id = ANY(%s)
                """, (recording_ids,))
                
                # Group artist credits by recording_id
                credits_by_recording = {}
                for row in cur.fetchall():
                    rec_id = row['recording_id']
                    if rec_id not in credits_by_recording:
                        credits_by_recording[rec_id] = set()
                    if row['artist_credit']:
                        credits_by_recording[rec_id].add(row['artist_credit'])
                
                # Now process each recording using the pre-fetched data
                for recording in recordings:
                    self.stats['recordings_checked'] += 1
                    recording_id = recording['id']
                    
                    performer_names = performers_by_recording.get(recording_id, [])
                    artist_credits = credits_by_recording.get(recording_id, set())
                    
                    result = self._check_recording_contamination(
                        recording, song_title, composer_names,
                        performer_names, artist_credits
                    )
                    
                    if result.get('is_contaminated'):
                        # Need to delete this recording
                        if not self.dry_run:
                            self._delete_recording(conn, recording_id, recording['album_title'])
                        else:
                            logger.info(f"   [DRY RUN] Would delete recording: {recording['album_title'][:50]}")
                        song_contaminated.append(result)
                    elif result.get('was_false_positive'):
                        self.stats['false_positives_avoided'] += 1
                
                if not self.dry_run and song_contaminated:
                    conn.commit()
        
        return song_contaminated
    
    def _check_recording_contamination(self, recording: Dict, song_title: str,
                                        composer_names: Set[str],
                                        performer_names: List[str],
                                        artist_credits: Set[str]) -> Dict:
        """Check a recording for contamination using pre-fetched data"""
        recording_id = recording['id']
        album_title = recording.get('album_title', 'Unknown')
        mb_id = recording.get('musicbrainz_id')
        
        # Extract primary artists (filtering out compilations)
        primary_artists = extract_primary_artists(artist_credits)
        
        # Filter out composers
        primary_artists_filtered = filter_out_composers(primary_artists, composer_names)
        
        # Check if this is actual contamination
        is_contaminated = False
        was_false_positive = False
        
        if len(artist_credits) > 1:
            if len(primary_artists) == 0:
                pass  # All compilations - OK
            elif len(primary_artists_filtered) == 0:
                was_false_positive = True
            elif len(primary_artists_filtered) == 1:
                was_false_positive = True
            elif are_same_artist(primary_artists_filtered):
                was_false_positive = True
            elif is_collaboration(artist_credits, primary_artists_filtered):
                was_false_positive = True
            elif performers_match_single_artist(performer_names, primary_artists_filtered):
                was_false_positive = True
            else:
                is_contaminated = True
        
        result = {
            'recording_id': recording_id,
            'album_title': album_title,
            'song_title': song_title,
            'musicbrainz_id': mb_id,
            'all_artist_credits': list(artist_credits),
            'primary_artists': list(primary_artists_filtered),
            'performers': performer_names,
            'is_contaminated': is_contaminated,
            'was_false_positive': was_false_positive
        }
        
        if is_contaminated:
            self.stats['recordings_contaminated'] += 1
            logger.warning(f"⚠️  CONTAMINATED: {album_title}")
            logger.warning(f"   Recording ID: {recording_id}")
            logger.warning(f"   MB ID: {mb_id}")
            logger.warning(f"   Primary artists: {primary_artists_filtered}")
            logger.warning(f"   All credits: {artist_credits}")
            logger.warning(f"   Performers: {performer_names[:5]}{'...' if len(performer_names) > 5 else ''}")
            logger.warning("")
        
        return result
    
    def _delete_recording(self, conn, recording_id: str, album_title: str):
        """Delete a contaminated recording and its links"""
        with conn.cursor() as cur:
            # Delete performer links
            cur.execute("""
                DELETE FROM recording_performers WHERE recording_id = %s
            """, (recording_id,))
            performer_links = cur.rowcount
            self.stats['performer_links_deleted'] += performer_links
            
            # Delete release links
            cur.execute("""
                DELETE FROM recording_releases WHERE recording_id = %s
            """, (recording_id,))
            release_links = cur.rowcount
            self.stats['release_links_deleted'] += release_links
            
            # Delete the recording itself
            cur.execute("""
                DELETE FROM recordings WHERE id = %s
            """, (recording_id,))
            
            self.stats['recordings_deleted'] += 1
            logger.info(f"   ✓ Deleted recording: {album_title[:50]}")
            logger.info(f"     - {performer_links} performer links removed")
            logger.info(f"     - {release_links} release links removed")
    
    def print_summary(self):
        """Print repair summary"""
        logger.info("")
        logger.info("="*80)
        logger.info("REPAIR SUMMARY")
        logger.info("="*80)
        if self.stats['songs_checked'] > 0:
            logger.info(f"Songs checked:            {self.stats['songs_checked']}")
        logger.info(f"Recordings checked:       {self.stats['recordings_checked']}")
        logger.info(f"Contaminated recordings:  {self.stats['recordings_contaminated']}")
        logger.info(f"False positives avoided:  {self.stats['false_positives_avoided']}")
        logger.info(f"Recordings deleted:       {self.stats['recordings_deleted']}")
        logger.info(f"Performer links deleted:  {self.stats['performer_links_deleted']}")
        logger.info(f"Release links deleted:    {self.stats['release_links_deleted']}")
        logger.info(f"Errors:                   {self.stats['errors']}")
        logger.info("="*80)


def main():
    parser = argparse.ArgumentParser(
        description='Repair contaminated recordings (improved detection)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check ALL songs (dry-run)
  python repair_contaminated_recordings.py --all --dry-run
  
  # Actually repair ALL songs
  python repair_contaminated_recordings.py --all
  
  # Check a specific song (dry-run)
  python repair_contaminated_recordings.py --song "Born to be Blue" --dry-run
  
  # Actually delete contaminated recordings for a song
  python repair_contaminated_recordings.py --song "Born to be Blue"
  
  # With debug logging
  python repair_contaminated_recordings.py --all --debug --dry-run

Improved detection logic:
  - Ignores "Various Artists" compilation credits
  - Normalizes credits like "Stan Getz Quartet" -> "Stan Getz"
  - Ignores composer credits (normal for standards)
  - Checks if performers match single artist (reissues)
  - Only repairs when genuinely DIFFERENT primary artists are found

After running this script (without --dry-run):
  1. Re-run the MB release importer with the updated mb_release_importer.py
  2. This will create proper separate recordings with correct MusicBrainz IDs
  
  Example:
    python import_mb_releases.py --name "Born to be Blue" --force-refresh
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--song',
        help='Song name or ID to repair'
    )
    group.add_argument(
        '--all',
        action='store_true',
        help='Process ALL songs in the database'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    repairer = ContaminatedRecordingRepairer(dry_run=args.dry_run)
    
    try:
        if args.all:
            result = repairer.repair_all_songs()
            repairer.print_summary()
            
            if result['contaminated_recordings'] and args.dry_run:
                logger.info("")
                logger.info(f"Found {len(result['contaminated_recordings'])} contaminated recordings across {len(result['songs_with_issues'])} songs")
                logger.info("")
                logger.info("Songs with contaminated recordings:")
                for song_info in result['songs_with_issues']:
                    logger.info(f"  - {song_info['song']}: {song_info['count']} recording(s)")
                logger.info("")
                logger.info("To actually delete these contaminated recordings, run without --dry-run:")
                logger.info("  python repair_contaminated_recordings.py --all")
            elif result['stats']['recordings_deleted'] > 0:
                logger.info("")
                logger.info("✓ Contaminated recordings deleted!")
                logger.info("")
                logger.info("Now re-import affected songs with the fixed importer.")
            else:
                logger.info("")
                logger.info("✓ No contamination found across all songs")
        else:
            result = repairer.repair_song(args.song)
            repairer.print_summary()
            
            if result['contaminated_recordings'] and args.dry_run:
                logger.info("")
                logger.info("To actually delete these contaminated recordings, run without --dry-run:")
                logger.info(f"  python repair_contaminated_recordings.py --song \"{args.song}\"")
                logger.info("")
                logger.info("Then re-import with the fixed importer:")
                logger.info(f"  python import_mb_releases.py --name \"{args.song}\" --force-refresh")
            elif result['stats']['recordings_deleted'] > 0:
                logger.info("")
                logger.info("✓ Contaminated recordings deleted!")
                logger.info("")
                logger.info("Now re-import with the fixed importer:")
                logger.info(f"  python import_mb_releases.py --name \"{args.song}\" --force-refresh")
            elif result['stats']['false_positives_avoided'] > 0:
                logger.info("")
                logger.info("✓ No actual contamination found")
                logger.info(f"  ({result['stats']['false_positives_avoided']} recordings had multiple credits but are correctly structured)")
        
        sys.exit(0)
        
    except KeyboardInterrupt:
        logger.info("\nRepair cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()