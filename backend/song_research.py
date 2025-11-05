"""
Song Research Module
Handles researching and updating song data from external sources
"""

import logging

logger = logging.getLogger(__name__)


def research_song(song_id: str, song_name: str):
    """
    Research a song and update its data
    
    This is the main entry point for song research. For now, it just logs
    the song information. In the future, this will call various research
    components to gather data from MusicBrainz, Wikipedia, etc.
    
    Args:
        song_id: UUID of the song to research
        song_name: Name of the song
    """
    logger.info(f"Researching song {song_id} / {song_name}")
    
    # TODO: Add actual research logic here
    # This will eventually include:
    # - MusicBrainz lookup
    # - Wikipedia lookup
    # - Recording information
    # - Performer information
    # - External references