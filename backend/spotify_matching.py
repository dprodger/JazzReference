"""
Spotify Matching Utilities

Text normalization, fuzzy matching, and validation logic for matching
our database records to Spotify API results.

Functions in this module are stateless and can be used independently.
"""

import re
import logging
from typing import List, Optional
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


# Common jazz ensemble suffixes that may not appear in Spotify artist names
# e.g., "Bill Evans Trio" in our DB might be just "Bill Evans" on Spotify
ENSEMBLE_SUFFIXES = [
    'Trio', 'Quartet', 'Quintet', 'Sextet', 'Septet', 'Octet', 'Nonet',
    'Orchestra', 'Big Band', 'Band', 'Ensemble', 'Group'
]

# Artist names that indicate a compilation rather than a specific artist
# For these, we allow lenient track verification since artist matching is meaningless
COMPILATION_ARTIST_PATTERNS = [
    'various artists',
    'various',
    'va',
    'multiple artists',
    'compilation',
    'assorted artists',
    'diverse artists',
    'varios artistas',
    'artistes divers',
]


def is_compilation_artist(artist_name: str) -> bool:
    """
    Check if an artist name indicates a compilation/various artists release.

    Args:
        artist_name: The artist name to check

    Returns:
        True if the artist name suggests a compilation
    """
    if not artist_name:
        return False

    normalized = artist_name.lower().strip()
    return normalized in COMPILATION_ARTIST_PATTERNS


def strip_ensemble_suffix(artist_name: str) -> str:
    """
    Strip common ensemble suffixes from artist names.
    
    Examples:
        "Lynne Arriale Trio" -> "Lynne Arriale"
        "Bill Evans Trio" -> "Bill Evans"
        "Duke Ellington Orchestra" -> "Duke Ellington"
        "Miles Davis" -> "Miles Davis" (unchanged)
    
    Returns:
        Artist name with suffix stripped, or original if no suffix found
    """
    if not artist_name:
        return artist_name
    
    for suffix in ENSEMBLE_SUFFIXES:
        # Check for suffix at end of string (case-insensitive)
        pattern = rf'\s+{re.escape(suffix)}$'
        if re.search(pattern, artist_name, re.IGNORECASE):
            return re.sub(pattern, '', artist_name, flags=re.IGNORECASE).strip()
    
    return artist_name


def normalize_for_comparison(text: str) -> str:
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
    text = re.sub(r'\s*-\s*live$', '', text, flags=re.IGNORECASE)  # Simple "- Live" suffix
    text = re.sub(r'\s*\(live\)$', '', text, flags=re.IGNORECASE)  # Simple "(Live)" suffix
    
    # Remove recorded at annotations
    text = re.sub(r'\s*-\s*recorded\s+(at|in)\s+.*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*\(recorded\s+(at|in)\s+[^)]*\).*$', '', text, flags=re.IGNORECASE)
    
    # Remove remastered annotations
    text = re.sub(r'\s*-\s*remastered(\s+\d{4})?.*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*\(remastered(\s+\d{4})?\).*$', '', text, flags=re.IGNORECASE)
    
    # Remove date/venue at end
    text = re.sub(r'\s*/\s+[a-z]+\s+\d+.*$', '', text, flags=re.IGNORECASE)
    
    # Remove tempo/arrangement annotations (common in jazz)
    text = re.sub(r'\s*-\s*(slow|fast|up tempo|medium|ballad)(\s+version)?.*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*\((slow|fast|up tempo|medium|ballad)(\s+version)?\).*$', '', text, flags=re.IGNORECASE)
    
    # Remove take numbers and alternate versions
    text = re.sub(r'\s*-\s*(take|version|alternate|alt\.?)\s*\d*.*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*\((take|version|alternate|alt\.?)\s*\d*\).*$', '', text, flags=re.IGNORECASE)
    
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

    # Normalize spacing around punctuation (e.g., "St. / Denis" → "St./Denis")
    text = re.sub(r'\s*/\s*', '/', text)
    text = re.sub(r'\s*-\s*', '-', text)
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    return text


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two strings using fuzzy matching.
    
    Handles common variations like parenthetical additions:
    - "Who Cares?" vs "Who Cares (As Long As You Care For Me)"
    - "Stella By Starlight" vs "Stella By Starlight (From 'The Uninvited')"
    
    Returns a score from 0-100
    """
    if not text1 or not text2:
        return 0
    
    norm1 = normalize_for_comparison(text1)
    norm2 = normalize_for_comparison(text2)
    
    # Primary comparison using token_sort_ratio
    score = fuzz.token_sort_ratio(norm1, norm2)
    
    # If score is below threshold, try comparing without parenthetical content
    # This handles cases like "Who Cares?" vs "Who Cares (As Long As You Care For Me)"
    if score < 80:
        # Strip parenthetical content from both
        stripped1 = re.sub(r'\s*\([^)]*\)\s*', ' ', norm1).strip()
        stripped2 = re.sub(r'\s*\([^)]*\)\s*', ' ', norm2).strip()
        
        # Only use stripped comparison if something was actually removed
        if stripped1 != norm1 or stripped2 != norm2:
            stripped_score = fuzz.token_sort_ratio(stripped1, stripped2)
            if stripped_score > score:
                logger.debug(f"      Parenthetical fallback: {score}% → {stripped_score}%")
                score = stripped_score
    
    return score


def is_substring_title_match(title1: str, title2: str) -> bool:
    """
    Check if one normalized title is a complete substring of the other.
    
    This is a fallback matching strategy used when track positions match
    but fuzzy matching doesn't meet the threshold. This handles cases like:
    - "An Affair to Remember" vs "An Affair to Remember - From the 20th Century-Fox Film"
    - "Stella By Starlight" vs "Stella By Starlight (From 'The Uninvited')"
    
    To minimize false positives, we require:
    - The shorter title is at least 4 characters
    - The shorter title appears as a complete substring in the longer one
    
    Args:
        title1: First title
        title2: Second title
        
    Returns:
        True if one title is fully contained in the other
    """
    if not title1 or not title2:
        return False
    
    norm1 = normalize_for_comparison(title1)
    norm2 = normalize_for_comparison(title2)
    
    # Determine shorter and longer
    shorter = norm1 if len(norm1) <= len(norm2) else norm2
    longer = norm2 if len(norm1) <= len(norm2) else norm1
    
    # Require minimum length to avoid false positives with very short titles
    if len(shorter) < 4:
        return False
    
    # Check if shorter is a complete substring of longer
    return shorter in longer


def extract_primary_artist(artist_credit: str) -> str:
    """
    Extract the primary artist from a MusicBrainz artist_credit string.
    
    MusicBrainz artist_credit can contain multiple artists joined by various
    separators (', ', '; ', '/', ' & '). For Spotify searches, we typically
    only need the primary (first) artist to get a good match.
    
    This prevents issues with long artist strings like:
    "Dave Brubeck, Claude Debussy, João Donato/João Gilberto, Bill Evans..."
    
    Args:
        artist_credit: Full artist credit string from MusicBrainz
        
    Returns:
        Primary artist name (first artist in the credit)
    """
    if not artist_credit:
        return None
    
    # Common separators in MusicBrainz artist credits
    # Order matters - check multi-char separators first
    separators = [', ', '; ', ' / ', '/', ' & ']
    
    result = artist_credit
    for sep in separators:
        if sep in result:
            result = result.split(sep)[0]
            break
    
    return result.strip() if result else None


def validate_track_match(spotify_track: dict, expected_song: str, 
                         expected_artist: str, expected_album: str,
                         min_track_similarity: int, min_artist_similarity: int,
                         min_album_similarity: int) -> tuple:
    """
    Validate that a Spotify track result actually matches what we're looking for
    
    Args:
        spotify_track: Track dict from Spotify API
        expected_song: Song title we're searching for
        expected_artist: Artist name we're searching for
        expected_album: Album title we're searching for (can be None)
        min_track_similarity: Minimum track title similarity threshold
        min_artist_similarity: Minimum artist similarity threshold
        min_album_similarity: Minimum album similarity threshold
        
    Returns:
        tuple: (is_valid, reason, scores_dict)
    """
    # Extract Spotify track info
    spotify_song = spotify_track['name']
    spotify_artist_list = [a['name'] for a in spotify_track['artists']]
    spotify_artists = ', '.join(spotify_artist_list)
    spotify_album = spotify_track['album']['name']
    
    # Calculate track title similarity
    song_similarity = calculate_similarity(expected_song, spotify_song)
    
    # Debug: Show normalized versions if similarity is surprisingly low
    if song_similarity < 70:
        norm_expected = normalize_for_comparison(expected_song)
        norm_spotify = normalize_for_comparison(spotify_song)
        if norm_expected != expected_song.lower() or norm_spotify != spotify_song.lower():
            logger.debug(f"       [Normalization] Expected: '{expected_song}' → '{norm_expected}'")
            logger.debug(f"       [Normalization] Spotify:  '{spotify_song}' → '{norm_spotify}'")
    
    # Calculate artist similarity - handle multi-artist tracks
    individual_artist_scores = [
        calculate_similarity(expected_artist, spotify_artist)
        for spotify_artist in spotify_artist_list
    ]
    best_individual_match = max(individual_artist_scores) if individual_artist_scores else 0
    
    full_artist_similarity = calculate_similarity(expected_artist, spotify_artists)
    
    artist_similarity = max(best_individual_match, full_artist_similarity)
    
    # Calculate album similarity
    album_similarity = calculate_similarity(expected_album, spotify_album) if expected_album else None
    
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
    
    # Validation logic
    if song_similarity < min_track_similarity:
        return False, f"Track title similarity too low ({song_similarity}% < {min_track_similarity}%)", scores
    
    if artist_similarity < min_artist_similarity:
        return False, f"Artist similarity too low ({artist_similarity}% < {min_artist_similarity}%)", scores
    
    if expected_album and album_similarity and album_similarity < min_album_similarity:
        return False, f"Album similarity too low ({album_similarity}% < {min_album_similarity}%)", scores
    
    # Passed all validation checks
    return True, "Valid match", scores


def validate_album_match(spotify_album: dict, expected_album: str, 
                         expected_artist: str, min_album_similarity: int,
                         min_artist_similarity: int,
                         song_title: str = None,
                         verify_track_callback=None) -> tuple:
    """
    Validate that a Spotify album result actually matches what we're looking for
    
    Args:
        spotify_album: Spotify album dict from search results
        expected_album: Album title we're searching for
        expected_artist: Artist name we're searching for
        min_album_similarity: Minimum album similarity threshold
        min_artist_similarity: Minimum artist similarity threshold
        song_title: Optional song title for track verification fallback.
                   When album similarity is high (>=80%) but artist fails,
                   we can still accept the match if the album contains
                   a track matching this title.
        verify_track_callback: Optional callback function(album_id, song_title) -> bool
                              for verifying track presence
    
    Returns:
        tuple: (is_valid, reason, scores_dict)
    """
    spotify_album_name = spotify_album['name']
    spotify_artist_list = [a['name'] for a in spotify_album['artists']]
    spotify_artists = ', '.join(spotify_artist_list)
    
    # Calculate album similarity
    album_similarity = calculate_similarity(expected_album, spotify_album_name)
    
    # Check for substring containment (e.g., "Live at Montreux" in "Live At The Montreux Jazz Festival")
    # This is a strong signal even if fuzzy similarity is below threshold
    # Strip articles (the, a, an) for more flexible matching
    def strip_articles(text):
        return re.sub(r'\b(the|a|an)\b', '', text, flags=re.IGNORECASE).strip()
    
    normalized_expected = strip_articles(normalize_for_comparison(expected_album))
    normalized_spotify = strip_articles(normalize_for_comparison(spotify_album_name))
    # Also remove extra spaces that may result from stripping articles
    normalized_expected = ' '.join(normalized_expected.split())
    normalized_spotify = ' '.join(normalized_spotify.split())
    
    album_is_substring = (
        normalized_expected in normalized_spotify or 
        normalized_spotify in normalized_expected
    )
    
    # Calculate artist similarity
    individual_artist_scores = [
        calculate_similarity(expected_artist, spotify_artist)
        for spotify_artist in spotify_artist_list
    ]
    best_individual_match = max(individual_artist_scores) if individual_artist_scores else 0
    full_artist_similarity = calculate_similarity(expected_artist, spotify_artists)
    artist_similarity = max(best_individual_match, full_artist_similarity)
    
    # Check for artist substring containment (e.g., "Lynne Arriale" in "Lynne Arriale Trio")
    normalized_expected_artist = normalize_for_comparison(expected_artist)
    artist_is_substring = any(
        normalized_expected_artist in normalize_for_comparison(sa) or
        normalize_for_comparison(sa) in normalized_expected_artist
        for sa in spotify_artist_list
    )
    
    scores = {
        'album': album_similarity,
        'album_is_substring': album_is_substring,
        'artist': artist_similarity,
        'artist_is_substring': artist_is_substring,
        'artist_best_individual': best_individual_match,
        'artist_full_string': full_artist_similarity,
        'spotify_album': spotify_album_name,
        'spotify_artist': spotify_artists
    }
    
    # Validation logic
    # Accept if: fuzzy similarity meets threshold OR album title is a substring (with reasonable similarity)
    album_valid = (
        album_similarity >= min_album_similarity or
        (album_is_substring and album_similarity >= 50)  # Substring match with at least 50% similarity
    )
    
    if not album_valid:
        return False, f"Album similarity too low ({album_similarity}% < {min_album_similarity}%)", scores
    
    if album_is_substring and album_similarity < min_album_similarity:
        logger.debug(f"      Album accepted via substring containment ({album_similarity}%)")
    
    if expected_artist and artist_similarity < min_artist_similarity:
        # Check if artist is accepted via substring containment 
        # (e.g., "Lynne Arriale" contained in "Lynne Arriale Trio")
        artist_valid_by_substring = artist_is_substring and artist_similarity >= 50
        
        if artist_valid_by_substring:
            logger.debug(f"      Artist accepted via substring containment ({artist_similarity}%)")
        else:
            # Artist validation failed - try track verification fallback
            # This handles "Various Artists" compilations where artist matching is meaningless
            # Only attempt if album similarity is high (>=80%) and we have a song title
            if song_title and album_similarity >= 80 and verify_track_callback:
                # For compilation artists (Various Artists, etc.), allow lenient track verification
                # For real artists, require at least 40% artist similarity to use track verification
                # This prevents matching "Illinois Jacquet" to "Charles Bradley" just because
                # both have albums/tracks called "Black Velvet"
                is_compilation = is_compilation_artist(expected_artist)
                min_artist_for_track_verify = 0 if is_compilation else 40

                if artist_similarity >= min_artist_for_track_verify:
                    album_id = spotify_album.get('id')
                    if album_id and verify_track_callback(album_id, song_title):
                        scores['verified_by_track'] = True
                        if is_compilation:
                            logger.debug(f"      Album accepted via track verification (compilation artist)")
                        else:
                            logger.debug(f"      Album accepted via track verification (artist {artist_similarity}% >= {min_artist_for_track_verify}%)")
                        return True, "Valid match (verified by track presence)", scores
                else:
                    logger.debug(f"      Track verification skipped (artist {artist_similarity}% < {min_artist_for_track_verify}% minimum for non-compilation)")

            return False, f"Artist similarity too low ({artist_similarity}% < {min_artist_similarity}%)", scores
    
    return True, "Valid match", scores