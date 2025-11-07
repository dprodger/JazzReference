"""
Song Research Module
Handles researching and updating song data from external sources

This module is called by the Flask background worker thread (via research_queue.py)
to perform asynchronous song research tasks. It uses:
- MBReleaseImporter for MusicBrainz releases and performer data
- SpotifyMatcher for Spotify track matching
"""

import logging
from typing import Dict, Any

from mb_release_importer import MBReleaseImporter
from spotify_utils import SpotifyMatcher
from db_utils import get_db_connection
from mb_utils import MusicBrainzSearcher

logger = logging.getLogger(__name__)


def update_song_composer(song_id: str) -> bool:
    """
    Update song composer from MusicBrainz if not already set
    
    Args:
        song_id: UUID of the song
        
    Returns:
        bool: True if composer was updated, False otherwise
    """
    try:
        # Check if song has musicbrainz_id and no composer
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT musicbrainz_id, composer FROM songs WHERE id = %s",
                    (song_id,)
                )
                row = cur.fetchone()
                
                if not row:
                    return False
                
                mb_id = row['musicbrainz_id']
                composer = row['composer']                
                # Skip if no MusicBrainz ID or already has composer
                if not mb_id or composer:
                    return False
        
        # Fetch work details from MusicBrainz
        mb = MusicBrainzSearcher()
        work_data = mb.get_work_recordings(mb_id)
        
        if not work_data:
            logger.debug("No MusicBrainz work data found")
            return False
        
        # Extract composer from artist relationships
        composer_name = None
        for relation in work_data.get('relations', []):
            if relation.get('type') == 'composer':
                artist = relation.get('artist', {})
                composer_name = artist.get('name')
                break
        
        if not composer_name:
            logger.debug("No composer found in MusicBrainz work data")
            return False
        
        # Update song with composer
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE songs SET composer = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (composer_name, song_id)
                )
                conn.commit()
        
        logger.info(f"✓ Updated composer to '{composer_name}'")
        return True
        
    except Exception as e:
        logger.error(f"Error updating composer: {e}")
        return False


def research_song(song_id: str, song_name: str) -> Dict[str, Any]:
    """
    Research a song and update its data
    
    This is the main entry point called by the background worker thread.
    It imports MusicBrainz releases and performer credits, then matches
    Spotify tracks for the song's recordings.
    
    The function is designed to be fault-tolerant and will not raise exceptions
    to the caller - all errors are logged and returned in the result dict.
    
    Args:
        song_id: UUID of the song to research
        song_name: Name of the song (for logging)
        
    Returns:
        dict: {
            'success': bool,
            'song_id': str,
            'song_name': str,
            'stats': dict (if successful),
            'error': str (if failed)
        }
    """
    logger.info(f"Starting research for song {song_id} / {song_name}")
    
    try:
        # Step 1: Import MusicBrainz releases
        importer = MBReleaseImporter(dry_run=False, logger=logger)
        
        logger.info("Importing MusicBrainz releases...")
        mb_result = importer.import_releases(str(song_id))
        
        if not mb_result['success']:
            error = mb_result.get('error', 'Unknown error')
            logger.error(f"✗ Failed to import MusicBrainz releases: {error}")
            return {
                'success': False,
                'song_id': song_id,
                'song_name': song_name,
                'error': f"MusicBrainz import failed: {error}"
            }
        
        mb_stats = mb_result['stats']
        logger.info(f"✓ MusicBrainz import complete")
        logger.info(f"  Imported: {mb_stats['releases_imported']} releases")
        logger.info(f"  Skipped: {mb_stats['releases_skipped']} (already exist with credits)")
        logger.info(f"  Credits added: {mb_stats['credits_added']} (to existing recordings)")
        if mb_stats['errors'] > 0:
            logger.info(f"  Errors: {mb_stats['errors']}")
        
        # Step 1.5: Update composer from MusicBrainz if needed
        logger.info("Checking for composer update...")
        composer_updated = update_song_composer(str(song_id))
        if not composer_updated:
            logger.debug("Composer not updated (already set or not found)")
        
        # Step 2: Match Spotify tracks
        matcher = SpotifyMatcher(dry_run=False, strict_mode=True, logger=logger)
        
        logger.info("Matching Spotify tracks...")
        spotify_result = matcher.match_recordings(str(song_id))
        
        if not spotify_result['success']:
            # Spotify matching failed, but MusicBrainz succeeded
            # This is a partial success - log warning but don't fail completely
            error = spotify_result.get('error', 'Unknown error')
            logger.warning(f"⚠ Spotify matching failed: {error}")
            logger.info(f"✓ Research partially complete (MusicBrainz only)")
            
            # Return success with combined stats
            combined_stats = {
                'musicbrainz': mb_stats,
                'spotify': {'error': error},
                'partial_success': True
            }
            
            return {
                'success': True,
                'song_id': song_id,
                'song_name': song_name,
                'stats': combined_stats
            }
        
        spotify_stats = spotify_result['stats']
        logger.info(f"✓ Spotify matching complete")
        logger.info(f"  Recordings processed: {spotify_stats['recordings_processed']}")
        logger.info(f"  Spotify matches found: {spotify_stats['recordings_with_spotify']}")
        logger.info(f"  Recordings updated: {spotify_stats['recordings_updated']}")
        logger.info(f"  No match found: {spotify_stats['recordings_no_match']}")
        logger.info(f"  Already had URL: {spotify_stats['recordings_skipped']}")
        
        # Combine stats from both operations
        combined_stats = {
            'musicbrainz': mb_stats,
            'spotify': spotify_stats
        }
        
        logger.info(f"✓ Successfully researched {song_name}")
        
        return {
            'success': True,
            'song_id': song_id,
            'song_name': song_name,
            'stats': combined_stats
        }
            
    except Exception as e:
        # Catch any unexpected errors so they don't crash the worker thread
        error_msg = f"Unexpected error researching song {song_id}: {e}"
        logger.error(error_msg, exc_info=True)
        
        return {
            'success': False,
            'song_id': song_id,
            'song_name': song_name,
            'error': error_msg
        }


# Future expansion: Additional research functions can be added here
# For example:
# - research_song_wikipedia(song_id, song_name)
# - update_song_images(song_id, song_name)