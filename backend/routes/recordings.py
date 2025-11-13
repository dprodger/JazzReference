# routes/recordings.py
from flask import Blueprint, jsonify
import logging
import db_utils as db_tools

logger = logging.getLogger(__name__)
recordings_bp = Blueprint('recordings', __name__)

# Recording endpoints:
# - GET /api/recordings/<recording_id>

@recordings_bp.route('/api/recordings/<recording_id>', methods=['GET'])
def get_recording_detail(recording_id):
    """Get detailed information about a specific recording"""
    try:
        # Get recording information
        recording_query = """
            SELECT r.id, r.song_id, r.album_title, r.recording_date, 
                   r.recording_year, r.label, r.spotify_url, r.spotify_track_id,
                   r.album_art_small, r.album_art_medium, r.album_art_large,
                   r.youtube_url, r.apple_music_url, r.musicbrainz_id, 
                   r.is_canonical, r.notes,
                   s.title as song_title, s.composer
            FROM recordings r
            JOIN songs s ON r.song_id = s.id
            WHERE r.id = %s
        """
        recording = db_tools.execute_query(recording_query, (recording_id,), fetch_one=True)
        
        if not recording:
            return jsonify({'error': 'Recording not found'}), 404
        
        # Get performers for this recording
        performers_query = """
            SELECT p.id, p.name, i.name as instrument, rp.role,
                   p.birth_date, p.death_date
            FROM recording_performers rp
            JOIN performers p ON rp.performer_id = p.id
            LEFT JOIN instruments i ON rp.instrument_id = i.id
            WHERE rp.recording_id = %s
            ORDER BY 
                CASE rp.role 
                    WHEN 'leader' THEN 1 
                    WHEN 'sideman' THEN 2 
                    ELSE 3 
                END,
                p.name
        """
        recording['performers'] = db_tools.execute_query(performers_query, (recording_id,))
        
        return jsonify(recording)
        
    except Exception as e:
        logger.error(f"Error fetching recording detail: {e}")
        return jsonify({'error': 'Failed to fetch recording detail', 'detail': str(e)}), 500
