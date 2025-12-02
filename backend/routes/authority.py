"""
Song Authority Recommendations Routes

Manages authority recommendations for recordings:
- GET /api/recordings/<recording_id>/authorities - Get authorities for a recording
- POST /api/recordings/<recording_id>/authorities - Add new authority recommendation
- DELETE /api/authorities/<authority_id> - Delete authority recommendation
"""

from flask import Blueprint, jsonify, request
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_utils import get_db_connection

logger = logging.getLogger(__name__)
authorities_bp = Blueprint('authorities', __name__)


# =============================================================================
# GET /api/recordings/<recording_id>/authorities
# =============================================================================

@authorities_bp.route('/api/recordings/<recording_id>/authorities', methods=['GET'])
def get_recording_authorities(recording_id):
    """Get all authority recommendations linked to a recording"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Verify recording exists
                cur.execute("SELECT id, song_id FROM recordings WHERE id = %s", (recording_id,))
                recording = cur.fetchone()
                
                if not recording:
                    return jsonify({'error': 'Recording not found'}), 404
                
                # Get authority recommendations for this recording
                cur.execute("""
                    SELECT 
                        sar.id,
                        sar.song_id,
                        sar.recording_id,
                        sar.source,
                        sar.recommendation_text,
                        sar.source_url,
                        sar.artist_name,
                        sar.album_title,
                        sar.recording_year,
                        sar.itunes_album_id,
                        sar.itunes_track_id,
                        sar.captured_at,
                        sar.created_at,
                        sar.updated_at
                    FROM song_authority_recommendations sar
                    WHERE sar.recording_id = %s
                    ORDER BY sar.source, sar.artist_name
                """, (recording_id,))
                
                authorities = cur.fetchall()
                
                return jsonify({
                    'recording_id': recording_id,
                    'song_id': str(recording['song_id']),
                    'authorities': authorities,
                    'count': len(authorities)
                })
                
    except Exception as e:
        logger.error(f"Error fetching recording authorities: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch authorities', 'detail': str(e)}), 500


# =============================================================================
# POST /api/recordings/<recording_id>/authorities
# =============================================================================

@authorities_bp.route('/api/recordings/<recording_id>/authorities', methods=['POST'])
def add_recording_authority(recording_id):
    """
    Add a new authority recommendation linked to a recording
    
    Request body:
    {
        "source": "jazzstandards.com",  // Required
        "source_url": "https://...",     // Required
        "recommendation_text": "...",    // Optional
        "artist_name": "...",            // Optional
        "album_title": "...",            // Optional
        "recording_year": 1959           // Optional
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        # Validate required fields
        if not data.get('source'):
            return jsonify({'error': 'source is required'}), 400
        if not data.get('source_url'):
            return jsonify({'error': 'source_url is required'}), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Verify recording exists and get song_id
                cur.execute("SELECT id, song_id FROM recordings WHERE id = %s", (recording_id,))
                recording = cur.fetchone()
                
                if not recording:
                    return jsonify({'error': 'Recording not found'}), 404
                
                song_id = recording['song_id']
                
                # Check for duplicate (same source + recording)
                cur.execute("""
                    SELECT id FROM song_authority_recommendations
                    WHERE recording_id = %s AND source = %s AND source_url = %s
                """, (recording_id, data['source'], data['source_url']))
                
                if cur.fetchone():
                    return jsonify({'error': 'Authority recommendation already exists for this recording'}), 409
                
                # Insert new authority recommendation
                cur.execute("""
                    INSERT INTO song_authority_recommendations (
                        song_id,
                        recording_id,
                        source,
                        source_url,
                        recommendation_text,
                        artist_name,
                        album_title,
                        recording_year,
                        captured_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    RETURNING id, song_id, recording_id, source, source_url,
                              recommendation_text, artist_name, album_title,
                              recording_year, created_at
                """, (
                    song_id,
                    recording_id,
                    data['source'],
                    data['source_url'],
                    data.get('recommendation_text'),
                    data.get('artist_name'),
                    data.get('album_title'),
                    data.get('recording_year')
                ))
                
                authority = cur.fetchone()
                conn.commit()
                
                logger.info(f"Created authority recommendation {authority['id']} for recording {recording_id}")
                
                return jsonify(authority), 201
                
    except Exception as e:
        logger.error(f"Error creating authority recommendation: {e}", exc_info=True)
        return jsonify({'error': 'Failed to create authority', 'detail': str(e)}), 500


# =============================================================================
# DELETE /api/authorities/<authority_id>
# =============================================================================

@authorities_bp.route('/api/authorities/<authority_id>', methods=['DELETE'])
def delete_authority(authority_id):
    """Delete an authority recommendation"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Verify authority exists
                cur.execute("""
                    SELECT id, recording_id, source 
                    FROM song_authority_recommendations 
                    WHERE id = %s
                """, (authority_id,))
                
                authority = cur.fetchone()
                
                if not authority:
                    return jsonify({'error': 'Authority recommendation not found'}), 404
                
                # Delete the authority
                cur.execute("""
                    DELETE FROM song_authority_recommendations
                    WHERE id = %s
                """, (authority_id,))
                
                conn.commit()
                
                logger.info(f"Deleted authority recommendation {authority_id}")
                
                return jsonify({
                    'message': 'Authority recommendation deleted',
                    'id': authority_id
                }), 200
                
    except Exception as e:
        logger.error(f"Error deleting authority recommendation: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete authority', 'detail': str(e)}), 500


# =============================================================================
# GET /api/songs/<song_id>/authorities
# =============================================================================

@authorities_bp.route('/api/songs/<song_id>/authorities', methods=['GET'])
def get_song_authorities(song_id):
    """
    Get all authority recommendations for a song
    Includes both matched (have recording_id) and unmatched recommendations
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Verify song exists
                cur.execute("SELECT id, title FROM songs WHERE id = %s", (song_id,))
                song = cur.fetchone()
                
                if not song:
                    return jsonify({'error': 'Song not found'}), 404
                
                # Get all authority recommendations for this song
                cur.execute("""
                    SELECT 
                        sar.id,
                        sar.song_id,
                        sar.recording_id,
                        sar.source,
                        sar.recommendation_text,
                        sar.source_url,
                        sar.artist_name,
                        sar.album_title,
                        sar.recording_year,
                        sar.itunes_album_id,
                        sar.itunes_track_id,
                        sar.captured_at,
                        sar.created_at,
                        r.album_title as matched_album_title,
                        r.recording_year as matched_year
                    FROM song_authority_recommendations sar
                    LEFT JOIN recordings r ON sar.recording_id = r.id
                    WHERE sar.song_id = %s
                    ORDER BY 
                        CASE WHEN sar.recording_id IS NOT NULL THEN 0 ELSE 1 END,
                        sar.source,
                        sar.artist_name
                """, (song_id,))
                
                authorities = cur.fetchall()
                
                matched_count = sum(1 for a in authorities if a['recording_id'])
                unmatched_count = len(authorities) - matched_count
                
                return jsonify({
                    'song_id': song_id,
                    'song_title': song['title'],
                    'authorities': authorities,
                    'total_count': len(authorities),
                    'matched_count': matched_count,
                    'unmatched_count': unmatched_count
                })
                
    except Exception as e:
        logger.error(f"Error fetching song authorities: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch authorities', 'detail': str(e)}), 500
        
        
# Add this endpoint to backend/routes/authority.py
# Place after the DELETE /api/authorities/<authority_id> endpoint

# =============================================================================
# PATCH /api/authorities/<authority_id>/link
# =============================================================================

@authorities_bp.route('/api/authorities/<authority_id>/link', methods=['PATCH'])
def link_authority_to_recording(authority_id):
    """
    Link an unmatched authority recommendation to a recording
    
    Request body:
    {
        "recording_id": "uuid-of-recording"
    }
    
    Returns the updated authority recommendation
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        recording_id = data.get('recording_id')
        if not recording_id:
            return jsonify({'error': 'recording_id is required'}), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Verify authority exists
                cur.execute("""
                    SELECT id, song_id, recording_id, source
                    FROM song_authority_recommendations
                    WHERE id = %s
                """, (authority_id,))
                
                authority = cur.fetchone()
                
                if not authority:
                    return jsonify({'error': 'Authority recommendation not found'}), 404
                
                # Verify recording exists and belongs to the same song
                cur.execute("""
                    SELECT id, song_id, album_title
                    FROM recordings
                    WHERE id = %s
                """, (recording_id,))
                
                recording = cur.fetchone()
                
                if not recording:
                    return jsonify({'error': 'Recording not found'}), 404
                
                # Verify the recording belongs to the same song
                if str(recording['song_id']) != str(authority['song_id']):
                    return jsonify({
                        'error': 'Recording does not belong to the same song as the authority recommendation'
                    }), 400
                
                # Check if already linked to a different recording
                if authority['recording_id'] and str(authority['recording_id']) != recording_id:
                    return jsonify({
                        'error': 'Authority is already linked to a different recording',
                        'current_recording_id': str(authority['recording_id'])
                    }), 409
                
                # Update the authority with the recording_id
                cur.execute("""
                    UPDATE song_authority_recommendations
                    SET recording_id = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING 
                        id,
                        song_id,
                        recording_id,
                        source,
                        recommendation_text,
                        source_url,
                        artist_name,
                        album_title,
                        recording_year,
                        itunes_album_id,
                        itunes_track_id,
                        captured_at,
                        created_at,
                        updated_at
                """, (recording_id, authority_id))
                
                updated_authority = cur.fetchone()
                conn.commit()
                
                logger.info(f"Linked authority {authority_id} to recording {recording_id}")
                
                return jsonify(updated_authority), 200
                
    except Exception as e:
        logger.error(f"Error linking authority to recording: {e}", exc_info=True)
        return jsonify({'error': 'Failed to link authority', 'detail': str(e)}), 500


# =============================================================================
# PATCH /api/authorities/<authority_id>/unlink
# =============================================================================

@authorities_bp.route('/api/authorities/<authority_id>/unlink', methods=['PATCH'])
def unlink_authority_from_recording(authority_id):
    """
    Unlink an authority recommendation from its recording
    Sets recording_id to NULL
    
    Returns the updated authority recommendation
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Verify authority exists
                cur.execute("""
                    SELECT id, recording_id
                    FROM song_authority_recommendations
                    WHERE id = %s
                """, (authority_id,))
                
                authority = cur.fetchone()
                
                if not authority:
                    return jsonify({'error': 'Authority recommendation not found'}), 404
                
                if not authority['recording_id']:
                    return jsonify({'error': 'Authority is not linked to any recording'}), 400
                
                # Update the authority to remove the recording_id
                cur.execute("""
                    UPDATE song_authority_recommendations
                    SET recording_id = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING 
                        id,
                        song_id,
                        recording_id,
                        source,
                        recommendation_text,
                        source_url,
                        artist_name,
                        album_title,
                        recording_year,
                        itunes_album_id,
                        itunes_track_id,
                        captured_at,
                        created_at,
                        updated_at
                """, (authority_id,))
                
                updated_authority = cur.fetchone()
                conn.commit()
                
                logger.info(f"Unlinked authority {authority_id} from recording")
                
                return jsonify(updated_authority), 200
                
    except Exception as e:
        logger.error(f"Error unlinking authority from recording: {e}", exc_info=True)
        return jsonify({'error': 'Failed to unlink authority', 'detail': str(e)}), 500        