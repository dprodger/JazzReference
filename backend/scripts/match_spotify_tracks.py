#!/usr/bin/env python3
"""
Spotify Track Matcher (Improved)
Finds Spotify track IDs for existing recordings and updates the database
Now with fuzzy matching validation to prevent false positives
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
from rapidfuzz import fuzz

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import shared database utilities
from db_utils import get_db_connection
from db_utils import normalize_apostrophes
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
    def __init__(self, dry_run=False, artist_filter=None, strict_mode=True):
        """
        Initialize Spotify Matcher
        
        Args:
            dry_run: If True, show what would be matched without making changes
            artist_filter: Filter to recordings by specific artist
            strict_mode: If True, use stricter validation thresholds (recommended)
        """
        self.dry_run = dry_run
        self.artist_filter = artist_filter
        self.strict_mode = strict_mode
        self.access_token = None
        self.token_expires = 0
        self.stats = {
            'recordings_processed': 0,
            'recordings_with_spotify': 0,
            'recordings_updated': 0,
            'recordings_no_match': 0,
            'recordings_skipped': 0,
            'recordings_rejected': 0,  # New: tracks rejected by validation
            'errors': 0
        }
        
        # Validation thresholds
        # In strict mode, we require higher similarity scores to accept a match
        if strict_mode:
            self.min_artist_similarity = 75  # Lowered from 80 to handle multi-artist tracks
            self.min_album_similarity = 65   # Lowered from 70 for more flexibility
            self.min_track_similarity = 85   # Keep track title strict
        else:
            self.min_artist_similarity = 65
            self.min_album_similarity = 55
            self.min_track_similarity = 75
    
    def normalize_for_comparison(self, text):
        """
        Normalize text for fuzzy comparison
        Removes common variations that shouldn't affect matching
        """
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove live recording annotations (common on Spotify)
        # Examples: "Track - Live at Venue" or "Track (Live at Venue)"
        import re
        
        # Pattern 1: " - Live at..." or " - Live At..." or " - live at..."
        text = re.sub(r'\s*-\s*live\s+(at|in|from)\s+.*$', '', text, flags=re.IGNORECASE)
        
        # Pattern 2: " (Live at...)" or " (Live in...)"
        text = re.sub(r'\s*\(live\s+(at|in|from)\s+[^)]*\).*$', '', text, flags=re.IGNORECASE)
        
        # Pattern 3: " - Recorded at..." or " (Recorded at...)"
        text = re.sub(r'\s*-\s*recorded\s+(at|in)\s+.*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*\(recorded\s+(at|in)\s+[^)]*\).*$', '', text, flags=re.IGNORECASE)
        
        # Pattern 4: " - Remastered YYYY" or " (Remastered YYYY)"
        text = re.sub(r'\s*-\s*remastered(\s+\d{4})?.*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*\(remastered(\s+\d{4})?\).*$', '', text, flags=re.IGNORECASE)
        
        # Pattern 5: Date/venue at the end in parentheses (e.g., "/ October 17-18, 1996")
        text = re.sub(r'\s*/\s+[a-z]+\s+\d+.*$', '', text, flags=re.IGNORECASE)
        
        # Remove common suffixes that create false negatives
        # e.g., "Bill Evans Trio" vs "Bill Evans"
        text = text.replace(' trio', '')
        text = text.replace(' quartet', '')
        text = text.replace(' quintet', '')
        text = text.replace(' sextet', '')
        text = text.replace(' orchestra', '')
        text = text.replace(' band', '')
        text = text.replace(' ensemble', '')
        
        # Normalize "and" vs "&"
        text = text.replace(' & ', ' and ')
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text
    
    def calculate_similarity(self, text1, text2):
        """
        Calculate similarity between two strings using fuzzy matching
        Returns a score from 0-100
        """
        if not text1 or not text2:
            return 0
        
        # Normalize both strings
        norm1 = self.normalize_for_comparison(text1)
        norm2 = self.normalize_for_comparison(text2)
        
        # Use token_sort_ratio which handles word order differences
        # e.g., "Evans Bill" vs "Bill Evans"
        return fuzz.token_sort_ratio(norm1, norm2)
    
    def validate_match(self, spotify_track, expected_song, expected_artist, expected_album):
        """
        Validate that a Spotify track result actually matches what we're looking for
        
        Args:
            spotify_track: Track dict from Spotify API
            expected_song: Song title we're searching for
            expected_artist: Artist name we're searching for
            expected_album: Album title we're searching for (can be None)
            
        Returns:
            tuple: (is_valid, reason, scores_dict)
        """
        # Extract Spotify track info
        spotify_song = spotify_track['name']
        spotify_artist_list = [a['name'] for a in spotify_track['artists']]
        spotify_artists = ', '.join(spotify_artist_list)
        spotify_album = spotify_track['album']['name']
        
        # Calculate track title similarity
        song_similarity = self.calculate_similarity(expected_song, spotify_song)
        
        # Debug: Show normalized versions if similarity is surprisingly low
        # This helps diagnose normalization issues
        if song_similarity < 70:
            norm_expected = self.normalize_for_comparison(expected_song)
            norm_spotify = self.normalize_for_comparison(spotify_song)
            if norm_expected != expected_song.lower() or norm_spotify != spotify_song.lower():
                logger.debug(f"       [Normalization] Expected: '{expected_song}' → '{norm_expected}'")
                logger.debug(f"       [Normalization] Spotify:  '{spotify_song}' → '{norm_spotify}'")
        
        # Calculate artist similarity - handle multi-artist tracks better
        # Strategy 1: Check if expected artist matches any individual artist in the list
        individual_artist_scores = [
            self.calculate_similarity(expected_artist, spotify_artist)
            for spotify_artist in spotify_artist_list
        ]
        best_individual_match = max(individual_artist_scores) if individual_artist_scores else 0
        
        # Strategy 2: Check similarity to the full concatenated string
        full_artist_similarity = self.calculate_similarity(expected_artist, spotify_artists)
        
        # Use the better of the two strategies
        # This ensures "Jerry Bergonzi" matches both "Jerry Bergonzi" 
        # and "Jerry Bergonzi, The Modern Jazz Trio"
        artist_similarity = max(best_individual_match, full_artist_similarity)
        
        # Calculate album similarity
        album_similarity = self.calculate_similarity(expected_album, spotify_album) if expected_album else None
        
        scores = {
            'song': song_similarity,
            'artist': artist_similarity,
            'artist_best_individual': best_individual_match,
            'artist_full_string': full_artist_similarity,
            'album': album_similarity,
            'spotify_song': spotify_song,
            'spotify_artist': spotify_artists,
            'spotify_album': spotify_album
        }
        
        # Check track title similarity
        if song_similarity < self.min_track_similarity:
            return False, f"Track title mismatch (similarity: {song_similarity}%)", scores
        
        # Check artist similarity
        if artist_similarity < self.min_artist_similarity:
            return False, f"Artist mismatch (similarity: {artist_similarity}%)", scores
        
        # Smart album matching: If track and artist both match very well,
        # be much more lenient on album matching
        # This handles reissues, compilations, and album title variations
        if expected_album and expected_album.lower() != 'unknown album':
            # Strong match threshold: both track and artist > 90%
            has_strong_match = song_similarity >= 90 and artist_similarity >= 90
            
            if has_strong_match:
                # With strong track+artist match, use lower album threshold
                # This catches reissues and compilations with the same recording
                relaxed_album_threshold = 40  # Much lower for strong matches
                if album_similarity < relaxed_album_threshold:
                    return False, f"Album mismatch even with strong track+artist match (similarity: {album_similarity}%)", scores
            else:
                # Normal case: require standard album similarity
                if album_similarity < self.min_album_similarity:
                    return False, f"Album mismatch (similarity: {album_similarity}%)", scores
        
        # Passed all checks
        return True, "Valid match", scores
    
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
        """
        Search Spotify for a track using progressive search strategy with validation
        """
        token = self.get_spotify_token()
        
        headers = {
            'Authorization': f'Bearer {token}'
        }
        
        url = 'https://api.spotify.com/v1/search'
        
        # Define search strategies in order of specificity
        # NOTE: We've removed the very loose strategies that caused false positives
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
        
        # Strategy 3: Track and artist with exact track matching
        if artist_name:
            search_strategies.append({
                'query': f'track:"{song_title}" artist:"{artist_name}"',
                'description': 'exact track + artist'
            })
        
        # Strategy 4: Just track and artist, both with quotes (tighter than before)
        if artist_name:
            search_strategies.append({
                'query': f'"{song_title}" "{artist_name}"',
                'description': 'quoted track + quoted artist'
            })
        
        # Try each strategy until we get valid results
        for strategy in search_strategies:
            params = {
                'q': strategy['query'],
                'type': 'track',
                'limit': 10  # Get more results to find best match
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
                    # We have results - now validate them
                    logger.debug(f"    Found {len(tracks)} candidate tracks, validating...")
                    
                    # Try to find a valid match among the results
                    for i, track in enumerate(tracks):
                        is_valid, reason, scores = self.validate_match(
                            track, 
                            song_title, 
                            artist_name, 
                            album_title
                        )
                        
                        if is_valid:
                            # Found a valid match!
                            track_id = track['id']
                            track_name = track['name']
                            track_artists = ', '.join([a['name'] for a in track['artists']])
                            track_album = track['album']['name']
                            track_url = track['external_urls']['spotify']
                            
                            # Extract album artwork URLs
                            images = track['album'].get('images', [])
                            album_art = {
                                'large': None,
                                'medium': None,
                                'small': None
                            }
                            
                            if len(images) >= 1:
                                album_art['large'] = images[0].get('url')
                            if len(images) >= 2:
                                album_art['medium'] = images[1].get('url')
                            if len(images) >= 3:
                                album_art['small'] = images[2].get('url')
                            
                            logger.debug(f"    ✓ Found valid match (candidate #{i+1})")
                            logger.debug(f"       Track: '{track_name}' by {track_artists}")
                            logger.debug(f"       Album: '{track_album}'")
                            
                            # Show if relaxed matching was used
                            has_strong_match = scores['song'] >= 90 and scores['artist'] >= 90
                            if has_strong_match and scores.get('album'):
                                logger.debug(f"       ⚠ Used relaxed album matching (strong track+artist match)")
                            
                            logger.debug(f"       Similarity scores - Track: {scores['song']}%, Artist: {scores['artist']}% (individual: {scores['artist_best_individual']}%, full: {scores['artist_full_string']}%), Album: {scores['album'] or 'N/A'}%")
                            logger.debug(f"       URL: {track_url}")
                            if album_art['medium']:
                                logger.debug(f"       Album Art: ✓")
                            
                            return {
                                'id': track_id,
                                'url': track_url,
                                'name': track_name,
                                'artists': track_artists,
                                'album': track_album,
                                'album_art': album_art,
                                'similarity_scores': scores
                            }
                        else:
                            # This candidate didn't pass validation
                            logger.debug(f"    ✗ Candidate #{i+1} rejected: {reason}")
                            logger.debug(f"       Expected: '{song_title}' by {artist_name} on '{album_title}'")
                            logger.debug(f"       Found: '{scores['spotify_song']}' by {scores['spotify_artist']} on '{scores['spotify_album']}'")
                            if scores.get('artist_best_individual'):
                                logger.debug(f"       Artist match scores - Individual: {scores['artist_best_individual']}%, Full string: {scores['artist_full_string']}%")
                            if scores['album']:
                                logger.debug(f"       Album similarity: {scores['album']}%")
                    
                    # No valid matches found in this result set
                    logger.debug(f"    ✗ No valid matches with {strategy['description']}")
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
        logger.debug(f"    ✗ No valid Spotify matches found after trying all strategies")
        return None
    
    def update_recording_spotify_url(self, conn, recording_id, spotify_data):
        """Update recording with Spotify URL, track ID, and album artwork"""
        if self.dry_run:
            logger.info(f"    [DRY RUN] Would update recording with: {spotify_data['url']}")
            if spotify_data.get('album_art', {}).get('medium'):
                logger.info(f"    [DRY RUN] Would add album artwork")
            return
        
        with conn.cursor() as cur:
            # Extract track ID from spotify_data
            track_id = spotify_data.get('id')
            album_art = spotify_data.get('album_art', {})
            
            cur.execute("""
                UPDATE recordings
                SET spotify_url = %s,
                    spotify_track_id = %s,
                    album_art_small = %s,
                    album_art_medium = %s,
                    album_art_large = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                spotify_data['url'],
                track_id,
                album_art.get('small'),
                album_art.get('medium'),
                album_art.get('large'),
                recording_id
            ), prepare=False)
            
            conn.commit()
            logger.info(f"    ✓ Updated with Spotify URL and album artwork")
            self.stats['recordings_updated'] += 1
    
    def match_recordings_for_song(self, song_identifier):
        """Main method to match Spotify tracks for a song's recordings"""
        logger.info("="*80)
        logger.info("Spotify Track Matching")
        logger.info("="*80)
        
        if self.dry_run:
            logger.info("*** DRY RUN MODE - No database changes will be made ***")
            logger.info("")
        
        if self.strict_mode:
            logger.info("*** STRICT VALIDATION MODE - Using stricter matching thresholds ***")
            logger.info(f"    Minimum artist similarity: {self.min_artist_similarity}%")
            logger.info(f"    Minimum album similarity: {self.min_album_similarity}%")
            logger.info(f"    Minimum track similarity: {self.min_track_similarity}%")
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
                        spotify_match
                    )
                else:
                    logger.info(f"    ✗ No valid Spotify match found")
                    self.stats['recordings_no_match'] += 1
                
                logger.info("")
        
        # Print summary
        logger.info("="*80)
        logger.info("MATCHING SUMMARY")
        logger.info("="*80)
        logger.info(f"Recordings processed:       {self.stats['recordings_processed']}")
        logger.info(f"Recordings already had URL: {self.stats['recordings_skipped']}")
        logger.info(f"Spotify matches found:      {self.stats['recordings_with_spotify']}")
        logger.info(f"Recordings updated:         {self.stats['recordings_updated']}")
        logger.info(f"No match found:             {self.stats['recordings_no_match']}")
        logger.info(f"Errors:                     {self.stats['errors']}")
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
  # Match by song name with strict validation (recommended)
  python match_spotify_tracks.py --name "Take Five"
  
  # Match by song ID
  python match_spotify_tracks.py --id a1b2c3d4-e5f6-7890-abcd-ef1234567890
  
  # Filter to only recordings by a specific artist
  python match_spotify_tracks.py --name "Autumn Leaves" --artist "Bill Evans"
  
  # Use looser validation thresholds (not recommended)
  python match_spotify_tracks.py --name "Blue in Green" --no-strict
  
  # Dry run to see what would be matched
  python match_spotify_tracks.py --name "Blue in Green" --dry-run
  
  # Enable debug logging to see validation details
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
        '--no-strict',
        action='store_true',
        help='Use looser validation thresholds (not recommended - may cause false matches)'
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
    matcher = SpotifyMatcher(
        dry_run=args.dry_run, 
        artist_filter=args.artist,
        strict_mode=not args.no_strict
    )
    
    # Determine song identifier
    song_identifier = normalize_apostrophes(args.name) if args.name else args.id
    
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