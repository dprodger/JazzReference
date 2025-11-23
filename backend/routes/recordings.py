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
    """
    Get detailed information about a specific recording with performers and authority recommendations.
    
    OPTIMIZED VERSION: Uses a SINGLE query with CTEs to fetch everything at once.
    
    NEW: Includes authority recommendations that reference this recording.
    """
    try:
        # ONE QUERY to get recording + performers + authority recommendations
        combined_query = """
            WITH recording_data AS (
                SELECT 
                    r.id, r.song_id, r.album_title, r.recording_date, 
                    r.recording_year, r.label, r.spotify_url, r.youtube_url,
                    r.apple_music_url, r.spotify_track_id, 
                    r.album_art_small, r.album_art_medium, r.album_art_large,
                    r.musicbrainz_id, r.is_canonical, r.notes,
                    s.title as song_title, 
                    s.composer,
                    s.external_references
                FROM recordings r
                JOIN songs s ON r.song_id = s.id
                WHERE r.id = %s
            ),
            performers_data AS (
                SELECT 
                    p.id, 
                    p.name, 
                    i.name as instrument, 
                    rp.role,
                    p.birth_date, 
                    p.death_date
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
            ),
            authority_data AS (
                SELECT 
                    sar.id, 
                    sar.source, 
                    sar.recommendation_text, 
                    sar.source_url,
                    sar.artist_name, 
                    sar.album_title as recommended_album,
                    sar.recording_year as recommended_year
                FROM song_authority_recommendations sar
                WHERE sar.recording_id = %s
                ORDER BY sar.source, sar.artist_name
            )
            SELECT 
                (SELECT row_to_json(recording_data.*) FROM recording_data) as recording,
                (SELECT json_agg(performers_data.*) FROM performers_data) as performers,
                (SELECT json_agg(authority_data.*) FROM authority_data) as authority_recommendations
        """
        
        # Execute the single query with recording_id passed 3 times (for each CTE)
        result = db_tools.execute_query(
            combined_query, 
            (recording_id, recording_id, recording_id), 
            fetch_one=True
        )
        
        if not result or not result['recording']:
            return jsonify({'error': 'Recording not found'}), 404
        
        # Build response from the single query result
        recording_dict = result['recording']
        performers = result['performers'] if result['performers'] else []
        authority_recommendations = result['authority_recommendations'] if result['authority_recommendations'] else []
        
        recording_dict['performers'] = performers
        recording_dict['authority_recommendations'] = authority_recommendations
        
        return jsonify(recording_dict)
        
    except Exception as e:
        logger.error(f"Error fetching recording detail: {e}")
        return jsonify({'error': 'Failed to fetch recording details', 'detail': str(e)}), 500


# NOTES ON CHANGES:
#
# 1. RECORDING DATA CTE - Added external_references from parent song
#    - Includes s.external_references so frontend can show song references
#    - No performance impact, already joining to songs table
#
# 2. PERFORMERS CTE - Unchanged
#    - Kept existing structure and ordering
#
# 3. AUTHORITY DATA CTE - New CTE for authority recommendations
#    - Fetches all recommendations that reference this recording
#    - Ordered by source name for consistent display
#
# 4. PERFORMANCE CHARACTERISTICS:
#    - Still ONE database query (single network round trip)
#    - Uses index on song_authority_recommendations(recording_id)
#    - All CTEs execute in parallel
#
# 5. RESPONSE FORMAT:
#    Recording object now includes:
#    - authority_recommendations: array of recommendation objects
#    - external_references: from parent song (for showing song links)
#    - performers: array (unchanged)
#
# EXAMPLE RESPONSE:
# {
#   "id": "...",
#   "album_title": "Time Out",
#   "song_title": "Take Five",
#   "external_references": {
#     "wikipedia": "https://en.wikipedia.org/wiki/Take_Five",
#     "jazzstandards": "https://..."
#   },
#   "performers": [
#     {"id": "...", "name": "Dave Brubeck", "instrument": "Piano", "role": "leader"}
#   ],
#   "authority_recommendations": [
#     {
#       "id": "...",
#       "source": "jazzstandards.com",
#       "recommendation_text": "This is the definitive recording...",
#       "source_url": "https://...",
#       "artist_name": "Dave Brubeck Quartet",
#       "recommended_album": "Time Out",
#       "recommended_year": 1959
#     }
#   ]
# }