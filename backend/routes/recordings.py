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


# routes/recordings.py
"""
Recording API Routes
Provides endpoints for listing and searching recordings
"""
from flask import Blueprint, jsonify, request
import logging
import db_utils as db_tools

logger = logging.getLogger(__name__)
recordings_bp = Blueprint('recordings', __name__)

# Recording endpoints:
# - GET /api/recordings - List all recordings with optional search
# - GET /api/recordings/<recording_id> - Get recording detail


@recordings_bp.route('/api/recordings', methods=['GET'])
def get_recordings():
    """
    Get all recordings with optional search
    
    Query Parameters:
        search: Search query to filter recordings by album title, artist name, or song title
        limit: Maximum number of results (default: 100, max: 500)
        
    Returns:
        List of recordings with basic info including performers
    """
    search_query = request.args.get('search', '').strip()
    limit = min(int(request.args.get('limit', 100)), 500)
    
    try:
        if search_query:
            # Search across album title, performer names, and song title
            query = """
                SELECT DISTINCT ON (r.id)
                    r.id,
                    r.song_id,
                    r.album_title,
                    r.recording_date,
                    r.recording_year,
                    r.label,
                    r.spotify_url,
                    r.spotify_track_id,
                    r.album_art_small,
                    r.album_art_medium,
                    r.album_art_large,
                    r.youtube_url,
                    r.apple_music_url,
                    r.musicbrainz_id,
                    r.is_canonical,
                    r.notes,
                    s.title as song_title,
                    s.composer,
                    COALESCE(
                        json_agg(
                            DISTINCT jsonb_build_object(
                                'id', p.id,
                                'name', p.name,
                                'instrument', i.name,
                                'role', rp.role
                            )
                        ) FILTER (WHERE p.id IS NOT NULL),
                        '[]'::json
                    ) as performers
                FROM recordings r
                JOIN songs s ON r.song_id = s.id
                LEFT JOIN recording_performers rp ON r.id = rp.recording_id
                LEFT JOIN performers p ON rp.performer_id = p.id
                LEFT JOIN instruments i ON rp.instrument_id = i.id
                WHERE 
                    r.album_title ILIKE %s
                    OR s.title ILIKE %s
                    OR p.name ILIKE %s
                GROUP BY r.id, r.song_id, r.album_title, r.recording_date, 
                         r.recording_year, r.label, r.spotify_url, r.spotify_track_id,
                         r.album_art_small, r.album_art_medium, r.album_art_large,
                         r.youtube_url, r.apple_music_url, r.musicbrainz_id,
                         r.is_canonical, r.notes, s.title, s.composer
                ORDER BY r.id, r.is_canonical DESC, r.recording_year DESC NULLS LAST
                LIMIT %s
            """
            search_pattern = f'%{search_query}%'
            result = db_tools.execute_query(
                query, 
                (search_pattern, search_pattern, search_pattern, limit),
                fetch_one=False
            )
        else:
            # Get all recordings without search filter
            query = """
                SELECT 
                    r.id,
                    r.song_id,
                    r.album_title,
                    r.recording_date,
                    r.recording_year,
                    r.label,
                    r.spotify_url,
                    r.spotify_track_id,
                    r.album_art_small,
                    r.album_art_medium,
                    r.album_art_large,
                    r.youtube_url,
                    r.apple_music_url,
                    r.musicbrainz_id,
                    r.is_canonical,
                    r.notes,
                    s.title as song_title,
                    s.composer,
                    COALESCE(
                        json_agg(
                            DISTINCT jsonb_build_object(
                                'id', p.id,
                                'name', p.name,
                                'instrument', i.name,
                                'role', rp.role
                            )
                        ) FILTER (WHERE p.id IS NOT NULL),
                        '[]'::json
                    ) as performers
                FROM recordings r
                JOIN songs s ON r.song_id = s.id
                LEFT JOIN recording_performers rp ON r.id = rp.recording_id
                LEFT JOIN performers p ON rp.performer_id = p.id
                LEFT JOIN instruments i ON rp.instrument_id = i.id
                GROUP BY r.id, r.song_id, r.album_title, r.recording_date, 
                         r.recording_year, r.label, r.spotify_url, r.spotify_track_id,
                         r.album_art_small, r.album_art_medium, r.album_art_large,
                         r.youtube_url, r.apple_music_url, r.musicbrainz_id,
                         r.is_canonical, r.notes, s.title, s.composer
                ORDER BY r.is_canonical DESC, r.album_title, r.recording_year DESC NULLS LAST
                LIMIT %s
            """
            result = db_tools.execute_query(query, (limit,), fetch_one=False)
        
        if result is None:
            result = []
            
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error fetching recordings: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch recordings', 'detail': str(e)}), 500


@recordings_bp.route('/api/recordings/<recording_id>', methods=['GET'])
def get_recording_detail(recording_id):
    """
    Get detailed information about a specific recording
    
    Path Parameters:
        recording_id: UUID of the recording
        
    Returns:
        Recording details with full performer lineup
    """
    try:
        query = """
            SELECT 
                r.id,
                r.song_id,
                r.album_title,
                r.recording_date,
                r.recording_year,
                r.label,
                r.spotify_url,
                r.spotify_track_id,
                r.album_art_small,
                r.album_art_medium,
                r.album_art_large,
                r.youtube_url,
                r.apple_music_url,
                r.musicbrainz_id,
                r.is_canonical,
                r.notes,
                s.title as song_title,
                s.composer,
                COALESCE(
                    json_agg(
                        DISTINCT jsonb_build_object(
                            'id', p.id,
                            'name', p.name,
                            'instrument', i.name,
                            'role', rp.role,
                            'birth_date', p.birth_date,
                            'death_date', p.death_date
                        )
                    ) FILTER (WHERE p.id IS NOT NULL),
                    '[]'::json
                ) as performers
            FROM recordings r
            JOIN songs s ON r.song_id = s.id
            LEFT JOIN recording_performers rp ON r.id = rp.recording_id
            LEFT JOIN performers p ON rp.performer_id = p.id
            LEFT JOIN instruments i ON rp.instrument_id = i.id
            WHERE r.id = %s
            GROUP BY r.id, r.song_id, r.album_title, r.recording_date, 
                     r.recording_year, r.label, r.spotify_url, r.spotify_track_id,
                     r.album_art_small, r.album_art_medium, r.album_art_large,
                     r.youtube_url, r.apple_music_url, r.musicbrainz_id,
                     r.is_canonical, r.notes, s.title, s.composer
        """
        
        recording = db_tools.execute_query(query, (recording_id,), fetch_one=True)
        
        if not recording:
            return jsonify({'error': 'Recording not found'}), 404
        
        return jsonify(recording)
        
    except Exception as e:
        logger.error(f"Error fetching recording detail: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch recording detail', 'detail': str(e)}), 500