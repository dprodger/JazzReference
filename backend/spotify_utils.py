"""
Spotify Track Matching Utilities
Core business logic for matching recordings to Spotify tracks

This module provides the SpotifyMatcher class which handles:
- Spotify API authentication and token management
- Fuzzy matching and validation of tracks
- Album artwork extraction
- Database updates for recordings

Used by:
- scripts/match_spotify_tracks.py (CLI interface)
- song_research.py (background worker)
"""

import os
import re
import time
import base64
import logging
from typing import Dict, Any, Optional, List
import requests
from rapidfuzz import fuzz

from db_utils import get_db_connection

logger = logging.getLogger(__name__)


class SpotifyMatcher:
    """
    Handles matching recordings to Spotify tracks with fuzzy validation
    """
    
    def __init__(self, dry_run=False, artist_filter=None, strict_mode=True, logger=None):
        """
        Initialize Spotify Matcher
        
        Args:
            dry_run: If True, show what would be matched without making changes
            artist_filter: Filter to recordings by specific artist
            strict_mode: If True, use stricter validation thresholds (recommended)
            logger: Optional logger instance (uses module logger if not provided)
        """
        self.dry_run = dry_run
        self.artist_filter = artist_filter
        self.strict_mode = strict_mode
        self.logger = logger or logging.getLogger(__name__)
        self.access_token = None
        self.token_expires = 0
        self.stats = {
            'recordings_processed': 0,
            'recordings_with_spotify': 0,
            'recordings_updated': 0,
            'recordings_no_match': 0,
            'recordings_skipped': 0,
            'recordings_rejected': 0,
            'errors': 0
        }
        
        # Validation thresholds
        if strict_mode:
            self.min_artist_similarity = 75
            self.min_album_similarity = 65
            self.min_track_similarity = 85
        else:
            self.min_artist_similarity = 65
            self.min_album_similarity = 55
            self.min_track_similarity = 75
    
    def normalize_for_comparison(self, text: str) -> str:
        """
        Normalize text for fuzzy comparison
        Removes common variations that shouldn't affect matching
        """
        if not text:
            return ""
        
        text = text.lower()
        
        # Remove live recording annotations
        text = re.sub(r'\s*-\s*live\s+(at|in|from)\s+.*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*\(live\s+(at|in|from)\s+[^)]*\).*$', '', text, flags=re.IGNORECASE)
        
        # Remove recorded at annotations
        text = re.sub(r'\s*-\s*recorded\s+(at|in)\s+.*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*\(recorded\s+(at|in)\s+[^)]*\).*$', '', text, flags=re.IGNORECASE)
        
        # Remove remastered annotations
        text = re.sub(r'\s*-\s*remastered(\s+\d{4})?.*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*\(remastered(\s+\d{4})?\).*$', '', text, flags=re.IGNORECASE)
        
        # Remove date/venue at end
        text = re.sub(r'\s*/\s+[a-z]+\s+\d+.*$', '', text, flags=re.IGNORECASE)
        
        # Remove ensemble suffixes
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
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two strings using fuzzy matching
        Returns a score from 0-100
        """
        if not text1 or not text2:
            return 0
        
        norm1 = self.normalize_for_comparison(text1)
        norm2 = self.normalize_for_comparison(text2)
        
        return fuzz.token_sort_ratio(norm1, norm2)
    
    def validate_match(self, spotify_track: dict, expected_song: str, 
                      expected_artist: str, expected_album: str) -> tuple:
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
        if song_similarity < 70:
            norm_expected = self.normalize_for_comparison(expected_song)
            norm_spotify = self.normalize_for_comparison(spotify_song)
            if norm_expected != expected_song.lower() or norm_spotify != spotify_song.lower():
                self.logger.debug(f"       [Normalization] Expected: '{expected_song}' → '{norm_expected}'")
                self.logger.debug(f"       [Normalization] Spotify:  '{spotify_song}' → '{norm_spotify}'")
        
        # Calculate artist similarity - handle multi-artist tracks
        individual_artist_scores = [
            self.calculate_similarity(expected_artist, spotify_artist)
            for spotify_artist in spotify_artist_list
        ]
        best_individual_match = max(individual_artist_scores) if individual_artist_scores else 0
        
        full_artist_similarity = self.calculate_similarity(expected_artist, spotify_artists)
        
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
        if expected_album and expected_album.lower() != 'unknown album':
            has_strong_match = song_similarity >= 90 and artist_similarity >= 90
            
            if has_strong_match:
                relaxed_album_threshold = 40
                if album_similarity < relaxed_album_threshold:
                    return False, f"Album mismatch even with strong track+artist match (similarity: {album_similarity}%)", scores
            else:
                if album_similarity < self.min_album_similarity:
                    return False, f"Album mismatch (similarity: {album_similarity}%)", scores
        
        return True, "Valid match", scores
    
    def get_spotify_token(self) -> str:
        """Get Spotify access token using client credentials flow"""
        client_id = os.environ.get('SPOTIFY_CLIENT_ID')
        client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            self.logger.error("Spotify credentials not found!")
            self.logger.error("")
            self.logger.error("Please set the following environment variables:")
            self.logger.error("  export SPOTIFY_CLIENT_ID='your_client_id'")
            self.logger.error("  export SPOTIFY_CLIENT_SECRET='your_client_secret'")
            self.logger.error("")
            self.logger.error("Get credentials at: https://developer.spotify.com/dashboard")
            raise ValueError("Missing Spotify credentials")
        
        # Check if token is still valid
        if self.access_token and time.time() < self.token_expires:
            return self.access_token
        
        # Get new token
        self.logger.info("Fetching Spotify access token...")
        
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
            
            self.logger.info(f"✓ Spotify token obtained (expires in {expires_in}s)")
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to get Spotify token: {e}")
            raise
    
    def find_song_by_name(self, song_name: str) -> Optional[dict]:
        """Find a song by name in the database"""
        self.logger.info(f"Searching for song: {song_name}")
        
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
                    self.logger.warning(f"No songs found matching: {song_name}")
                    return None
                
                if len(results) == 1:
                    return results[0]
                
                # Multiple matches - show options
                self.logger.info(f"Found {len(results)} songs matching '{song_name}':")
                for i, song in enumerate(results, 1):
                    self.logger.info(f"  {i}. {song['title']} - {song['composer']}")
                
                choice = input("\nSelect song number (or 0 to cancel): ")
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(results):
                        return results[idx]
                except ValueError:
                    pass
                
                return None
    
    def find_song_by_id(self, song_id: str) -> Optional[dict]:
        """Find a song by ID in the database"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, composer
                    FROM songs
                    WHERE id = %s
                """, (song_id,))
                
                return cur.fetchone()
    
    def get_recordings_for_song(self, song_id: str) -> List[dict]:
        """Get all recordings for a song with performer information"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
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
    
    def search_spotify_track(self, song_title: str, album_title: str, 
                           artist_name: str, year: Optional[int] = None) -> Optional[dict]:
        """
        Search Spotify for a track using progressive search strategy with validation
        """
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
        
        # Strategy 3: Track and artist with exact track matching
        if artist_name:
            search_strategies.append({
                'query': f'track:"{song_title}" artist:"{artist_name}"',
                'description': 'exact track + artist'
            })
        
        # Strategy 4: Just track and artist, both with quotes
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
                'limit': 10
            }
            
            try:
                time.sleep(0.1)
                self.logger.debug(f"    Trying: {strategy['description']}")
                self.logger.debug(f"    Query: {strategy['query']}")
                
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                tracks = data.get('tracks', {}).get('items', [])
                
                if tracks:
                    self.logger.debug(f"    Found {len(tracks)} candidate tracks, validating...")
                    
                    for i, track in enumerate(tracks):
                        is_valid, reason, scores = self.validate_match(
                            track, 
                            song_title, 
                            artist_name, 
                            album_title
                        )
                        
                        if is_valid:
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
                            
                            self.logger.debug(f"    ✓ Found valid match (candidate #{i+1})")
                            self.logger.debug(f"       Track: '{track_name}' by {track_artists}")
                            self.logger.debug(f"       Album: '{track_album}'")
                            
                            has_strong_match = scores['song'] >= 90 and scores['artist'] >= 90
                            if has_strong_match and scores.get('album'):
                                self.logger.debug(f"       ⚠ Used relaxed album matching (strong track+artist match)")
                            
                            self.logger.debug(f"       Similarity scores - Track: {scores['song']}%, Artist: {scores['artist']}% (individual: {scores['artist_best_individual']}%, full: {scores['artist_full_string']}%), Album: {scores['album'] or 'N/A'}%")
                            self.logger.debug(f"       URL: {track_url}")
                            if album_art['medium']:
                                self.logger.debug(f"       Album Art: ✓")
                            
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
                            self.logger.debug(f"    ✗ Candidate #{i+1} rejected: {reason}")
                            self.logger.debug(f"       Expected: '{song_title}' by {artist_name} on '{album_title}'")
                            self.logger.debug(f"       Found: '{scores['spotify_song']}' by {scores['spotify_artist']} on '{scores['spotify_album']}'")
                            if scores.get('artist_best_individual'):
                                self.logger.debug(f"       Artist match scores - Individual: {scores['artist_best_individual']}%, Full string: {scores['artist_full_string']}%")
                            if scores['album']:
                                self.logger.debug(f"       Album similarity: {scores['album']}%")
                    
                    self.logger.debug(f"    ✗ No valid matches with {strategy['description']}")
                else:
                    self.logger.debug(f"    ✗ No results with {strategy['description']}")
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:
                    self.access_token = None
                    self.logger.warning("Spotify token expired, will refresh on next request")
                    return None
                self.logger.error(f"Spotify search failed: {e}")
                return None
            except Exception as e:
                self.logger.error(f"Error searching Spotify: {e}")
                return None
        
        self.logger.debug(f"    ✗ No valid Spotify matches found after trying all strategies")
        return None
    
    def update_recording_spotify_url(self, conn, recording_id: str, spotify_data: dict):
        """Update recording with Spotify URL, track ID, and album artwork"""
        if self.dry_run:
            self.logger.info(f"    [DRY RUN] Would update recording with: {spotify_data['url']}")
            if spotify_data.get('album_art', {}).get('medium'):
                self.logger.info(f"    [DRY RUN] Would add album artwork")
            return
        
        with conn.cursor() as cur:
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
            self.logger.info(f"    ✓ Updated with Spotify URL and album artwork")
            self.stats['recordings_updated'] += 1
    
    def match_recordings(self, song_identifier: str) -> Dict[str, Any]:
        """
        Main method to match Spotify tracks for a song's recordings
        
        Args:
            song_identifier: Song name or database ID
            
        Returns:
            dict: {
                'success': bool,
                'song': dict (if found),
                'stats': dict,
                'error': str (if failed)
            }
        """
        try:
            # Find the song
            if song_identifier.startswith('song-') or len(song_identifier) == 36:
                song = self.find_song_by_id(song_identifier)
            else:
                song = self.find_song_by_name(song_identifier)
            
            if not song:
                return {
                    'success': False,
                    'error': 'Song not found'
                }
            
            self.logger.info(f"Song: {song['title']}")
            self.logger.info(f"Composer: {song['composer']}")
            self.logger.info(f"Database ID: {song['id']}")
            if self.artist_filter:
                self.logger.info(f"Filtering to recordings by: {self.artist_filter}")
            self.logger.info("")
            
            # Get recordings
            recordings = self.get_recordings_for_song(song['id'])
            
            if not recordings:
                return {
                    'success': False,
                    'song': song,
                    'error': 'No recordings found for this song'
                }
            
            self.logger.info(f"Found {len(recordings)} recordings to process")
            self.logger.info("")
            
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
                    
                    self.logger.info(f"[{i}/{len(recordings)}] {album}")
                    self.logger.info(f"    Artist: {artist_name or 'Unknown'}")
                    self.logger.info(f"    Year: {year or 'Unknown'}")
                    
                    # Check if already has Spotify URL
                    if recording['spotify_url']:
                        self.logger.info(f"    ⊙ Already has Spotify URL, skipping")
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
                        self.logger.info(f"    ✗ No valid Spotify match found")
                        self.stats['recordings_no_match'] += 1
                    
                    self.logger.info("")
            
            return {
                'success': True,
                'song': song,
                'stats': self.stats
            }
            
        except Exception as e:
            self.logger.error(f"Error matching recordings: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'stats': self.stats
            }