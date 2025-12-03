"""
Song Research Module
Coordinates background research tasks for songs

It uses:
- MBReleaseImporter for MusicBrainz releases and performer data
- SpotifyMatcher for Spotify release and track matching (with caching)
"""

import logging
import os
from typing import Dict, Any

from mb_release_importer import MBReleaseImporter
from spotify_utils import SpotifyMatcher
from db_utils import get_db_connection
from mb_utils import MusicBrainzSearcher, update_song_composer, update_song_wikipedia_url

logger = logging.getLogger(__name__)


def research_song(song_id: str, song_name: str) -> Dict[str, Any]:
    """
    Research a song and update its data
    
    This is the main entry point called by the background worker thread.
    It imports MusicBrainz releases and performer credits, then matches
    Spotify tracks for the song's recordings.
    
    The function is designed to be fault-tolerant and will not raise exceptions
    to the caller - all errors are logged and returned in the result dict.
    
    Note: This function uses caching for both MusicBrainz and Spotify API calls.
    By default, cache expires after 30 days. This helps minimize API rate limiting
    and speeds up repeated research operations.
    
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
        # MBReleaseImporter uses MusicBrainzSearcher internally which has caching
        importer = MBReleaseImporter(dry_run=False, logger=logger)
        
        # Get import limit from environment variable, default to 100
        mb_import_limit = int(os.environ.get('MB_IMPORT_LIMIT', 100))
        logger.info(f"Importing MusicBrainz releases...; limiting to {mb_import_limit}")
        mb_result = importer.import_releases(str(song_id), mb_import_limit)
        
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
        logger.info(f"  Recordings found: {mb_stats['recordings_found']}")
        logger.info(f"  Recordings created: {mb_stats['recordings_created']}")
        logger.info(f"  Releases created: {mb_stats['releases_created']}")
        logger.info(f"  Releases existing: {mb_stats['releases_existing']}")
        logger.info(f"  Performers linked: {mb_stats['performers_linked']}")
        if mb_stats['errors'] > 0:
            logger.info(f"  Errors: {mb_stats['errors']}")
        
        # Step 1.5: Update composer from MusicBrainz if needed
        logger.info("Checking for composer update...")
        composer_updated = update_song_composer(str(song_id))
        if not composer_updated:
            logger.debug("Composer not updated (already set or not found)")
        
        # Step 1.6: Update Wikipedia URL from MusicBrainz if needed
        logger.info("Checking for Wikipedia URL update...")
        wikipedia_updated = update_song_wikipedia_url(str(song_id))
        if not wikipedia_updated:
            logger.debug("Wikipedia URL not updated (already set or not found)")
        
        # Step 2: Match Spotify releases and tracks
        # SpotifyMatcher uses default cache settings: 30 days expiration, no force_refresh
        # This minimizes API calls and speeds up repeated research operations
        matcher = SpotifyMatcher(dry_run=False, strict_mode=True, logger=logger)
        
        logger.info("Matching Spotify releases...")
        spotify_result = matcher.match_releases(str(song_id))
        
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
        logger.info(f"  Releases processed: {spotify_stats['releases_processed']}")
        logger.info(f"  Spotify matches found: {spotify_stats['releases_with_spotify']}")
        logger.info(f"  Releases updated: {spotify_stats['releases_updated']}")
        logger.info(f"  No match found: {spotify_stats['releases_no_match']}")
        logger.info(f"  Already had URL: {spotify_stats['releases_skipped']}")
        logger.info(f"  Tracks matched: {spotify_stats['tracks_matched']}")
        logger.info(f"  Tracks skipped: {spotify_stats['tracks_skipped']}")
        logger.info(f"  Tracks no match: {spotify_stats['tracks_no_match']}")
        logger.info(f"  Cache hits: {spotify_stats['cache_hits']}")
        logger.info(f"  API calls: {spotify_stats['api_calls']}")
        
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