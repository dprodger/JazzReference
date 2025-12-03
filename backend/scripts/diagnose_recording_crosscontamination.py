#!/usr/bin/env python3
"""
Diagnose Recording Cross-Contamination (Improved Version)

This script identifies recordings that may have been incorrectly merged due to 
album title matching instead of proper MusicBrainz ID matching.

IMPROVED DETECTION LOGIC:
- Ignores "Various Artists" compilations (normal for recordings to appear on these)
- Normalizes artist credits to detect the primary artist (e.g., "Stan Getz" vs "Stan Getz Quartet")
- Only flags as contaminated when genuinely different primary artists are found

Problem: When two different artists have albums with the same title (e.g., 
Grant Green's "Born to Be Blue" and Freddie Hubbard's "Born to Be Blue"),
the old fallback matching by album_title + song_id incorrectly merged them.

Usage:
  python diagnose_recording_crosscontamination.py --dry-run
  python diagnose_recording_crosscontamination.py --song "Born to be Blue" --dry-run
  python diagnose_recording_crosscontamination.py --song "Born to be Blue" --debug
"""

import sys
import argparse
import logging
import re
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from collections import defaultdict

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
        logging.FileHandler(LOG_DIR / 'diagnose_recording_crosscontamination.log')
    ]
)
logger = logging.getLogger(__name__)


# Artist credits to ignore when checking for contamination
# These are compilation/anthology credits that don't indicate the primary artist
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
    """
    Normalize an artist credit to extract the primary artist name.
    
    This handles cases like:
    - "Stan Getz Quartet" -> "stan getz"
    - "The Bobby Timmons Trio" -> "bobby timmons"
    - "Tommy Flanagan Trio" -> "tommy flanagan"
    - "Paul Motian Trio 2000 + One" -> "paul motian"
    
    Returns lowercase normalized name for comparison.
    """
    if not credit:
        return ''
    
    credit = credit.lower().strip()
    
    # Remove common suffixes
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
    
    # Remove leading "The "
    credit = re.sub(r'^the\s+', '', credit)
    
    return credit.strip()


def is_compilation_credit(credit: str) -> bool:
    """Check if an artist credit is a compilation/various artists credit."""
    if not credit:
        return False
    normalized = credit.lower().strip()
    return normalized in COMPILATION_CREDITS or 'various artist' in normalized


def extract_primary_artists(artist_credits: Set[str]) -> Set[str]:
    """
    Extract primary artists from a set of artist credits.
    
    Filters out compilation credits and normalizes remaining credits.
    Returns a set of normalized primary artist names.
    """
    primary_artists = set()
    
    for credit in artist_credits:
        if not credit or is_compilation_credit(credit):
            continue
        
        normalized = normalize_artist_credit(credit)
        if normalized:
            primary_artists.add(normalized)
    
    return primary_artists


def are_same_artist(artists: Set[str]) -> bool:
    """
    Check if a set of normalized artist names likely refers to the same artist.
    
    This handles cases where the same artist has slightly different credits.
    """
    if len(artists) <= 1:
        return True
    
    artists_list = list(artists)
    
    # Check if any artist name is a substring of another (common for "X" vs "X Trio")
    for i, artist1 in enumerate(artists_list):
        for artist2 in artists_list[i+1:]:
            # If one contains the other, they're likely the same
            if artist1 in artist2 or artist2 in artist1:
                continue
            # If they share a significant common prefix (first/last name)
            words1 = set(artist1.split())
            words2 = set(artist2.split())
            common_words = words1 & words2
            # If they share at least one significant word, might be same artist
            if common_words and any(len(w) > 3 for w in common_words):
                continue
            # Different artists
            return False
    
    return True


def is_collaboration(artist_credits: Set[str], primary_artists: Set[str]) -> bool:
    """
    Check if the artist credits indicate a legitimate collaboration.
    
    A collaboration is detected when:
    - One of the original credits contains multiple of the primary artists
    - Example: "The George Shearing Quintet with Nancy Wilson" contains both
      "george shearing" and "nancy wilson"
    
    This handles cases like:
    - "The Swingin's Mutual!" by George Shearing & Nancy Wilson
    - Joint albums where both artists are credited
    """
    if len(primary_artists) <= 1:
        return False
    
    # Check if any original credit contains multiple primary artists
    for credit in artist_credits:
        if not credit:
            continue
        credit_lower = credit.lower()
        
        # Count how many primary artists appear in this credit
        artists_in_credit = sum(1 for artist in primary_artists if artist in credit_lower)
        
        # If a credit contains 2+ of the primary artists, it's a collaboration
        if artists_in_credit >= 2:
            return True
    
    return False


def extract_composer_names(composer_field: str) -> Set[str]:
    """
    Extract individual composer names from a composer field.
    
    Handles formats like:
    - "George Gershwin" -> {"george gershwin"}
    - "George Gershwin, Ira Gershwin" -> {"george gershwin", "ira gershwin"}
    - "Rodgers and Hammerstein" -> {"rodgers", "hammerstein"}
    
    Returns normalized lowercase names.
    """
    if not composer_field:
        return set()
    
    composers = set()
    
    # Split on common separators
    parts = re.split(r'[,;&/]|\band\b', composer_field, flags=re.IGNORECASE)
    
    for part in parts:
        name = part.strip().lower()
        if name and len(name) > 2:
            composers.add(name)
    
    return composers


def filter_out_composers(primary_artists: Set[str], composer_names: Set[str]) -> Set[str]:
    """
    Remove composer names from the set of primary artists.
    
    This prevents false positives where a release is credited to the composer
    (e.g., "George Gershwin") instead of the performer.
    """
    if not composer_names:
        return primary_artists
    
    filtered = set()
    for artist in primary_artists:
        is_composer = False
        for composer in composer_names:
            # Check if artist matches or contains the composer name
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
    
    Returns True if performers likely belong to single artist (not contaminated).
    """
    if not performer_names or not primary_artists:
        return False
    
    if len(primary_artists) <= 1:
        return True  # Already single artist
    
    # Normalize performer names for comparison
    normalized_performers = [name.lower().strip() for name in performer_names]
    
    # For each primary artist, count how many performers match
    for artist in primary_artists:
        matches = 0
        for performer in normalized_performers:
            # Check various matching conditions
            if (artist in performer or 
                performer in artist or 
                # Check if performer's last name matches artist
                any(word in artist for word in performer.split() if len(word) > 3) or
                any(word in performer for word in artist.split() if len(word) > 3)):
                matches += 1
        
        # If this single artist accounts for a significant portion of performers,
        # the recording is probably legitimately theirs
        if matches > 0 and matches >= len(normalized_performers) * 0.5:
            # Check if any OTHER artist also has significant matches
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
                        break  # Found a match for this other artist
            
            # If no other artist has matching performers, it's not contamination
            if other_matches == 0:
                return True
    
    return False


class RecordingCrossContaminationDiagnoser:
    """Diagnoses recording cross-contamination issues with improved detection"""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.stats = {
            'songs_checked': 0,
            'recordings_checked': 0,
            'contaminated_recordings': 0,
            'false_positives_avoided': 0,
            'recordings_fixed': 0,
            'errors': 0
        }
    
    def diagnose_all_songs(self) -> Dict[str, Any]:
        """Check all songs for cross-contamination"""
        logger.info("="*80)
        logger.info("RECORDING CROSS-CONTAMINATION DIAGNOSIS (IMPROVED)")
        logger.info("="*80)
        
        if self.dry_run:
            logger.info("*** DRY RUN MODE ***")
        logger.info("")
        logger.info("Detection logic:")
        logger.info("  - Ignores 'Various Artists' compilation credits")
        logger.info("  - Normalizes credits (e.g., 'Stan Getz Quartet' -> 'Stan Getz')")
        logger.info("  - Only flags when genuinely different primary artists found")
        logger.info("")
        
        contaminated_recordings = []
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Find songs with multiple recordings having the same album title
                cur.execute("""
                    SELECT s.id, s.title as song_title, r.album_title, COUNT(*) as count
                    FROM songs s
                    JOIN recordings r ON r.song_id = s.id
                    GROUP BY s.id, s.title, r.album_title
                    HAVING COUNT(*) > 1
                    ORDER BY s.title, r.album_title
                """)
                
                potential_issues = cur.fetchall()
                logger.info(f"Found {len(potential_issues)} song/album combinations with multiple recordings")
                logger.info("")
                
                for issue in potential_issues:
                    self.stats['songs_checked'] += 1
                    result = self._check_recording_contamination(
                        conn, issue['id'], issue['song_title'], issue['album_title']
                    )
                    if result:
                        contaminated_recordings.extend(result)
        
        return {
            'contaminated_recordings': contaminated_recordings,
            'stats': self.stats
        }
    
    def diagnose_song(self, song_identifier: str) -> Dict[str, Any]:
        """Check a specific song for cross-contamination"""
        logger.info("="*80)
        logger.info("RECORDING CROSS-CONTAMINATION DIAGNOSIS (IMPROVED)")
        logger.info("="*80)
        
        if self.dry_run:
            logger.info("*** DRY RUN MODE ***")
        logger.info("")
        logger.info("Detection logic:")
        logger.info("  - Ignores 'Various Artists' compilation credits")
        logger.info("  - Normalizes credits (e.g., 'Stan Getz Quartet' -> 'Stan Getz')")
        logger.info("  - Ignores composer credits (normal for standards)")
        logger.info("  - Only flags when genuinely different primary artists found")
        logger.info("")
        
        contaminated_recordings = []
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Find the song
                if len(song_identifier) == 36 and '-' in song_identifier:
                    cur.execute("SELECT id, title, composer FROM songs WHERE id = %s", (song_identifier,))
                else:
                    cur.execute("SELECT id, title, composer FROM songs WHERE title ILIKE %s", (f'%{song_identifier}%',))
                
                song = cur.fetchone()
                if not song:
                    logger.error(f"Song not found: {song_identifier}")
                    return {'contaminated_recordings': [], 'stats': self.stats}
                
                # Extract composer name(s) for exclusion
                composer = song.get('composer', '')
                composer_names = extract_composer_names(composer) if composer else set()
                
                logger.info(f"Checking song: {song['title']} (ID: {song['id']})")
                if composer_names:
                    logger.info(f"Composer(s): {composer} -> will exclude from contamination check")
                logger.info("")
                
                # Get all recordings for this song
                cur.execute("""
                    SELECT r.id, r.album_title, r.musicbrainz_id, r.recording_year
                    FROM recordings r
                    WHERE r.song_id = %s
                    ORDER BY r.album_title
                """, (song['id'],))
                
                recordings = cur.fetchall()
                logger.info(f"Found {len(recordings)} recordings")
                logger.info("")
                
                for recording in recordings:
                    self.stats['recordings_checked'] += 1
                    result = self._analyze_recording(conn, recording, song['title'], composer_names)
                    if result.get('is_contaminated'):
                        contaminated_recordings.append(result)
                        self.stats['contaminated_recordings'] += 1
                    elif result.get('was_false_positive'):
                        self.stats['false_positives_avoided'] += 1
        
        return {
            'contaminated_recordings': contaminated_recordings,
            'stats': self.stats
        }
    
    def _check_recording_contamination(self, conn, song_id: str, song_title: str, 
                                        album_title: str) -> List[Dict]:
        """Check a specific song/album combination for contamination"""
        contaminated = []
        
        with conn.cursor() as cur:
            # First get the composer for this song
            cur.execute("SELECT composer FROM songs WHERE id = %s", (song_id,))
            song_row = cur.fetchone()
            composer = song_row.get('composer', '') if song_row else ''
            composer_names = extract_composer_names(composer) if composer else set()
            
            cur.execute("""
                SELECT r.id, r.musicbrainz_id, r.recording_year
                FROM recordings r
                WHERE r.song_id = %s AND r.album_title = %s
            """, (song_id, album_title))
            
            recordings = cur.fetchall()
            
            for recording in recordings:
                result = self._analyze_recording(conn, {
                    **dict(recording),
                    'album_title': album_title
                }, song_title, composer_names)
                
                if result.get('is_contaminated'):
                    contaminated.append(result)
                    self.stats['contaminated_recordings'] += 1
                elif result.get('was_false_positive'):
                    self.stats['false_positives_avoided'] += 1
                
                self.stats['recordings_checked'] += 1
        
        return contaminated
    
    def _analyze_recording(self, conn, recording: Dict, song_title: str, 
                           composer_names: Set[str] = None) -> Dict:
        """Analyze a single recording for cross-contamination with improved logic"""
        recording_id = recording['id']
        album_title = recording.get('album_title', 'Unknown')
        mb_id = recording.get('musicbrainz_id')
        composer_names = composer_names or set()
        
        with conn.cursor() as cur:
            # Get all performers linked to this recording
            cur.execute("""
                SELECT DISTINCT p.name, p.id as performer_id
                FROM recording_performers rp
                JOIN performers p ON p.id = rp.performer_id
                WHERE rp.recording_id = %s
                ORDER BY p.name
            """, (recording_id,))
            
            performers = [dict(row) for row in cur.fetchall()]
            
            # Get all releases linked to this recording
            cur.execute("""
                SELECT DISTINCT rel.id, rel.title, rel.artist_credit, rel.musicbrainz_release_id
                FROM recording_releases rr
                JOIN releases rel ON rel.id = rr.release_id
                WHERE rr.recording_id = %s
                ORDER BY rel.title
            """, (recording_id,))
            
            releases = [dict(row) for row in cur.fetchall()]
        
        # Collect all artist credits
        all_artist_credits = set()
        for release in releases:
            if release.get('artist_credit'):
                all_artist_credits.add(release['artist_credit'])
        
        # Extract primary artists (filtering out compilations)
        primary_artists = extract_primary_artists(all_artist_credits)
        
        # Filter out composers (it's normal for releases to be credited to the composer)
        primary_artists_filtered = filter_out_composers(primary_artists, composer_names)
        
        # Get performer names for additional check
        performer_names = [p['name'] for p in performers]
        
        # Check if this looks like contamination
        is_contaminated = False
        was_false_positive = False
        contamination_reason = None
        
        if len(all_artist_credits) > 1:
            # Multiple artist credits found
            if len(primary_artists) == 0:
                # All credits were compilations - not contaminated
                logger.debug(f"✓ OK (all compilations): {album_title}")
            elif len(primary_artists_filtered) == 0:
                # All non-compilation credits were composer credits - not contaminated
                was_false_positive = True
                logger.debug(f"✓ OK (composer credits only): {album_title} -> {primary_artists}")
            elif len(primary_artists_filtered) == 1:
                # Single primary artist (after filtering) + compilations/composer - not contaminated
                was_false_positive = True
                logger.debug(f"✓ OK (single artist + composer/compilations): {album_title} -> {primary_artists_filtered}")
            elif are_same_artist(primary_artists_filtered):
                # Different credits that normalize to same artist - not contaminated
                was_false_positive = True
                logger.debug(f"✓ OK (same artist variants): {album_title} -> {primary_artists_filtered}")
            elif is_collaboration(all_artist_credits, primary_artists_filtered):
                # Legitimate collaboration (one credit contains multiple artists) - not contaminated
                was_false_positive = True
                logger.debug(f"✓ OK (collaboration): {album_title} -> {primary_artists_filtered}")
            elif performers_match_single_artist(performer_names, primary_artists_filtered):
                # All performers belong to single artist, other credits are reissues - not contaminated
                was_false_positive = True
                logger.debug(f"✓ OK (performers match single artist): {album_title} -> {primary_artists_filtered}")
            else:
                # Genuinely different primary artists - contaminated!
                is_contaminated = True
                contamination_reason = f"Different primary artists found: {primary_artists_filtered}"
        
        result = {
            'recording_id': recording_id,
            'album_title': album_title,
            'song_title': song_title,
            'musicbrainz_id': mb_id,
            'performers': performers,
            'releases': releases,
            'all_artist_credits': list(all_artist_credits),
            'primary_artists': list(primary_artists_filtered),
            'is_contaminated': is_contaminated,
            'was_false_positive': was_false_positive,
            'contamination_reason': contamination_reason
        }
        
        if is_contaminated:
            logger.warning(f"⚠️  CONTAMINATED: {album_title}")
            logger.warning(f"   Recording ID: {recording_id}")
            logger.warning(f"   MB ID: {mb_id}")
            logger.warning(f"   Reason: {contamination_reason}")
            logger.warning(f"   All credits: {all_artist_credits}")
            logger.warning(f"   Primary artists (after filtering): {primary_artists_filtered}")
            logger.warning(f"   Performers: {[p['name'] for p in performers]}")
            logger.warning("")
        
        return result
    
    def print_summary(self):
        """Print diagnostic summary"""
        logger.info("")
        logger.info("="*80)
        logger.info("DIAGNOSIS SUMMARY")
        logger.info("="*80)
        logger.info(f"Songs checked:            {self.stats['songs_checked']}")
        logger.info(f"Recordings checked:       {self.stats['recordings_checked']}")
        logger.info(f"Contaminated recordings:  {self.stats['contaminated_recordings']}")
        logger.info(f"False positives avoided:  {self.stats['false_positives_avoided']}")
        logger.info(f"Recordings fixed:         {self.stats['recordings_fixed']}")
        logger.info(f"Errors:                   {self.stats['errors']}")
        logger.info("="*80)


def main():
    parser = argparse.ArgumentParser(
        description='Diagnose recording cross-contamination issues (improved detection)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check all songs (dry-run)
  python diagnose_recording_crosscontamination.py --dry-run
  
  # Check a specific song
  python diagnose_recording_crosscontamination.py --song "Born to be Blue" --dry-run
  
  # Enable debug logging to see all checks
  python diagnose_recording_crosscontamination.py --song "Born to be Blue" --debug

Improved detection logic:
  - Ignores "Various Artists" compilation credits (normal for recordings)
  - Normalizes credits like "Stan Getz Quartet" -> "Stan Getz"
  - Only flags when genuinely DIFFERENT primary artists are found
  
  Example of what's NOT contamination:
    - A Freddie Hubbard recording on his album AND a "Various Artists" compilation
    - Same recording credited to "Stan Getz" and "Stan Getz Quartet"
  
  Example of what IS contamination:
    - A recording with BOTH Grant Green AND Freddie Hubbard as performers
        """
    )
    
    parser.add_argument(
        '--song',
        help='Song name or ID to check (checks all songs if not specified)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show diagnosis without making changes (always true for diagnosis)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging to see all checks'
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    diagnoser = RecordingCrossContaminationDiagnoser(dry_run=True)
    
    try:
        if args.song:
            result = diagnoser.diagnose_song(args.song)
        else:
            result = diagnoser.diagnose_all_songs()
        
        diagnoser.print_summary()
        
        if result['contaminated_recordings']:
            logger.info("")
            logger.info("⚠️  Cross-contamination detected!")
            logger.info("   The recordings listed above have data from genuinely different artists.")
            logger.info("   This was caused by album title matching instead of MusicBrainz ID matching.")
            logger.info("")
            logger.info("To fix this:")
            logger.info("  1. Apply the fix to mb_release_importer.py (removes album title fallback)")
            logger.info("  2. Delete the contaminated recordings and re-import them")
            logger.info("  3. Or manually separate the recording data")
        else:
            logger.info("")
            logger.info("✓ No cross-contamination detected")
            if result['stats']['false_positives_avoided'] > 0:
                logger.info(f"  ({result['stats']['false_positives_avoided']} recordings had multiple credits but are correctly structured)")
        
        sys.exit(0 if not result['contaminated_recordings'] else 1)
        
    except KeyboardInterrupt:
        logger.info("\nDiagnosis cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()