"""
Song Research Module
Handles researching and updating song data from external sources

This module is called by the Flask background worker thread (via research_queue.py)
to perform asynchronous song research tasks. It uses the MBReleaseImporter module
to import MusicBrainz releases and performer data.
"""

import logging
from typing import Dict, Any

from mb_release_importer import MBReleaseImporter

logger = logging.getLogger(__name__)


def research_song(song_id: str, song_name: str) -> Dict[str, Any]:
    """
    Research a song and update its data
    
    This is the main entry point called by the background worker thread.
    It imports MusicBrainz releases and performer credits for the song.
    
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
        # Create importer for background processing
        # Note: dry_run=False since this is actual processing
        # Pass in the logger so all output goes to Flask's logging
        importer = MBReleaseImporter(dry_run=False, logger=logger)
        
        logger.info("received the mbreleaseimporter")
        # Import releases for this song (using song_id for exact match)
        result = importer.import_releases(str(song_id))
        
        if result['success']:
            stats = result['stats']
            logger.info(f"✓ Successfully researched {song_name}")
            logger.info(f"  Imported: {stats['releases_imported']} releases")
            logger.info(f"  Skipped: {stats['releases_skipped']} (already exist with credits)")
            logger.info(f"  Credits added: {stats['credits_added']} (to existing recordings)")
            if stats['errors'] > 0:
                logger.info(f"  Errors: {stats['errors']}")
            
            # Return success with stats
            return {
                'success': True,
                'song_id': song_id,
                'song_name': song_name,
                'stats': stats
            }
        else:
            # Import failed for some reason
            error = result.get('error', 'Unknown error')
            logger.error(f"✗ Failed to research {song_name}: {error}")
            
            return {
                'success': False,
                'song_id': song_id,
                'song_name': song_name,
                'error': error
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
# - research_song_spotify(song_id, song_name)
# - update_song_images(song_id, song_name)