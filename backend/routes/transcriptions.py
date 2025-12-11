# routes/transcriptions.py
from flask import Blueprint, jsonify
import logging
import db_utils as db_tools

logger = logging.getLogger(__name__)
transcriptions_bp = Blueprint('transcriptions', __name__)

# Transcription endpoints:
# - GET /songs/<song_id>/transcriptions
# - GET /recordings/<recording_id>/transcriptions
# - GET /transcriptions/<transcription_id>





# Solo Transcriptions API Endpoints
# Add these to backend/app.py

@transcriptions_bp.route('/songs/<song_id>/transcriptions', methods=['GET'])
def get_song_transcriptions(song_id):
    """Get all solo transcriptions for a specific song"""
    try:
        query = """
            SELECT
                st.id,
                st.song_id,
                st.recording_id,
                st.youtube_url,
                st.created_at,
                st.updated_at,
                def_rel.title as album_title,
                r.recording_year,
                s.title as song_title
            FROM solo_transcriptions st
            JOIN songs s ON st.song_id = s.id
            JOIN recordings r ON st.recording_id = r.id
            LEFT JOIN releases def_rel ON r.default_release_id = def_rel.id
            WHERE st.song_id = %s
            ORDER BY r.recording_year DESC
        """
        
        transcriptions = db_tools.execute_query(query, (song_id,), fetch_all=True)
        
        if not transcriptions:
            return jsonify([])
        
        return jsonify(transcriptions)
        
    except Exception as e:
        logger.error(f"Error fetching song transcriptions: {e}")
        return jsonify({'error': 'Failed to fetch transcriptions', 'detail': str(e)}), 500


@transcriptions_bp.route('/recordings/<recording_id>/transcriptions', methods=['GET'])
def get_recording_transcriptions(recording_id):
    """Get all solo transcriptions for a specific recording"""
    try:
        query = """
            SELECT
                st.id,
                st.song_id,
                st.recording_id,
                st.youtube_url,
                st.created_at,
                st.updated_at,
                s.title as song_title,
                def_rel.title as album_title,
                r.recording_year
            FROM solo_transcriptions st
            JOIN songs s ON st.song_id = s.id
            JOIN recordings r ON st.recording_id = r.id
            LEFT JOIN releases def_rel ON r.default_release_id = def_rel.id
            WHERE st.recording_id = %s
            ORDER BY st.created_at DESC
        """
        
        transcriptions = db_tools.execute_query(query, (recording_id,), fetch_all=True)
        
        if not transcriptions:
            return jsonify([])
        
        return jsonify(transcriptions)
        
    except Exception as e:
        logger.error(f"Error fetching recording transcriptions: {e}")
        return jsonify({'error': 'Failed to fetch transcriptions', 'detail': str(e)}), 500


@transcriptions_bp.route('/transcriptions/<transcription_id>', methods=['GET'])
def get_transcription_detail(transcription_id):
    """Get detailed information about a specific solo transcription"""
    try:
        query = """
            SELECT
                st.id,
                st.song_id,
                st.recording_id,
                st.youtube_url,
                st.created_at,
                st.updated_at,
                s.title as song_title,
                s.composer,
                def_rel.title as album_title,
                r.recording_year,
                r.label
            FROM solo_transcriptions st
            JOIN songs s ON st.song_id = s.id
            JOIN recordings r ON st.recording_id = r.id
            LEFT JOIN releases def_rel ON r.default_release_id = def_rel.id
            WHERE st.id = %s
        """
        
        transcription = db_tools.execute_query(query, (transcription_id,), fetch_one=True)
        
        if not transcription:
            return jsonify({'error': 'Transcription not found'}), 404
        
        return jsonify(transcription)
        
    except Exception as e:
        logger.error(f"Error fetching transcription detail: {e}")
        return jsonify({'error': 'Failed to fetch transcription detail', 'detail': str(e)}), 500
