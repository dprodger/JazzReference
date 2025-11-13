"""
Jazz Reference API Backend - Improved Version
A Flask API with robust database connection handling
"""

import logging
import time
import sys
import os
import json

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from datetime import date

from api_doc import api_docs
from routes.health import health_bp
from routes.research import research_bp
from routes.songs import songs_bp
from routes.recordings import recordings_bp
from routes.performers import performers_bp
from routes.images import images_bp
from routes.repertoires import repertoires_bp


# Set pooling mode BEFORE importing db_utils
os.environ['DB_USE_POOLING'] = 'true'

# Import database tools
import db_utils as db_tools

# Import research tools
import research_queue
import song_research

# Custom JSON encoder to format dates without timestamps
from flask.json.provider import DefaultJSONProvider
from utils import CustomJSONProvider
from utils.helpers import safe_strip

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

app.json = CustomJSONProvider(app)
app.register_blueprint(api_docs)
app.register_blueprint(health_bp)
app.register_blueprint(research_bp)
app.register_blueprint(songs_bp)
app.register_blueprint(recordings_bp)
app.register_blueprint(performers_bp)
app.register_blueprint(images_bp)
app.register_blueprint(repertoires_bp)

logger.info(f"Spotify credentials present: {bool(os.environ.get('SPOTIFY_CLIENT_ID'))}")

# Worker thread initialization:
# - When running under gunicorn: Initialized via post_worker_init hook in gunicorn.conf.py
# - When running directly (python app.py): Initialized in __main__ block at bottom
# This ensures the worker runs in the process that handles HTTP requests

logger.info(f"Flask app initialized in PID {os.getpid()}")



# ============================================================================
# LANDING PAGE
# ============================================================================

@app.route('/')
def landing_page():
    """Serve the main landing page"""
    return render_template('index.html')

# ============================================================================
# API ENDPOINTS
# ============================================================================

        


@app.before_request
def log_request():
    """Log incoming requests"""
    logger.info(f"{request.method} {request.path}")

@app.after_request
def log_response(response):
    """Log response status"""
    logger.info(f"{request.method} {request.path} - {response.status_code}")
    return response


"""
Add this endpoint to your backend/app.py file
Insert after the existing endpoints (e.g., after /api/health)
"""

@app.route('/api/content-reports', methods=['POST'])
def submit_content_report():
    """Submit a content error report"""
    try:
        # Get JSON data from request
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['entity_type', 'entity_id', 'entity_name', 
                          'external_source', 'external_url', 'explanation']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        # Validate entity_type
        valid_entity_types = ['song', 'performer', 'recording']
        if data['entity_type'].lower() not in valid_entity_types:
            return jsonify({
                'success': False,
                'error': f'Invalid entity_type. Must be one of: {", ".join(valid_entity_types)}'
            }), 400
        
        # Get optional fields with defaults
        report_category = data.get('report_category', 'link_issue')
        reporter_platform = data.get('reporter_platform')
        reporter_app_version = data.get('reporter_app_version')
        
        # Get client IP and user agent
        reporter_ip = request.remote_addr
        reporter_user_agent = request.headers.get('User-Agent')
        
        # Insert into database
        with db_tools.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO content_reports (
                        entity_type,
                        entity_id,
                        entity_name,
                        report_category,
                        external_source,
                        external_url,
                        explanation,
                        reporter_ip,
                        reporter_user_agent,
                        reporter_platform,
                        reporter_app_version
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING id, created_at
                """, (
                    data['entity_type'].lower(),
                    data['entity_id'],
                    data['entity_name'],
                    report_category,
                    data['external_source'],
                    data['external_url'],
                    data['explanation'],
                    reporter_ip,
                    reporter_user_agent,
                    reporter_platform,
                    reporter_app_version
                ))
                
                result = cur.fetchone()
                report_id = result['id']
                created_at = result['created_at'].isoformat()
        
        logger.info(f"Content report created: {report_id} for {data['entity_type']} {data['entity_id']}")
        
        return jsonify({
            'success': True,
            'report_id': str(report_id),
            'created_at': created_at,
            'message': 'Thank you for your report. We will review it shortly.'
        }), 201
        
    except KeyError as e:
        logger.error(f"Missing data field: {e}")
        return jsonify({
            'success': False,
            'error': f'Invalid request data: {str(e)}'
        }), 400
        
    except Exception as e:
        logger.error(f"Error submitting content report: {e}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while submitting your report. Please try again later.'
        }), 500


@app.route('/api/content-reports', methods=['GET'])
def get_content_reports():
    """
    Get content reports (for admin use)
    Query parameters:
    - status: Filter by status (pending, reviewing, resolved, dismissed, duplicate)
    - entity_type: Filter by entity type (song, performer, recording)
    - entity_id: Filter by specific entity ID
    - limit: Number of results (default 50)
    """
    try:
        # Get query parameters
        status = request.args.get('status', 'pending')
        entity_type = request.args.get('entity_type')
        entity_id = request.args.get('entity_id')
        limit = min(int(request.args.get('limit', 50)), 200)  # Max 200
        
        # Build query
        query = """
            SELECT 
                id,
                entity_type,
                entity_id,
                entity_name,
                report_category,
                external_source,
                external_url,
                explanation,
                status,
                priority,
                resolution_notes,
                resolution_action,
                created_at,
                updated_at,
                reviewed_at,
                resolved_at
            FROM content_reports
            WHERE 1=1
        """
        params = []
        
        if status:
            query += " AND status = %s"
            params.append(status)
        
        if entity_type:
            query += " AND entity_type = %s"
            params.append(entity_type.lower())
        
        if entity_id:
            query += " AND entity_id = %s"
            params.append(entity_id)
        
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        
        # Execute query
        with db_tools.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                reports = cur.fetchall()
        
        # Convert datetime objects to ISO format
        for report in reports:
            if report['created_at']:
                report['created_at'] = report['created_at'].isoformat()
            if report['updated_at']:
                report['updated_at'] = report['updated_at'].isoformat()
            if report['reviewed_at']:
                report['reviewed_at'] = report['reviewed_at'].isoformat()
            if report['resolved_at']:
                report['resolved_at'] = report['resolved_at'].isoformat()
        
        return jsonify({
            'success': True,
            'count': len(reports),
            'reports': reports
        })
        
    except Exception as e:
        logger.error(f"Error fetching content reports: {e}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while fetching reports.'
        }), 500







# Solo Transcriptions API Endpoints
# Add these to backend/app.py

@app.route('/api/songs/<song_id>/transcriptions', methods=['GET'])
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
                r.album_title,
                r.recording_year,
                s.title as song_title
            FROM solo_transcriptions st
            JOIN songs s ON st.song_id = s.id
            JOIN recordings r ON st.recording_id = r.id
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


@app.route('/api/recordings/<recording_id>/transcriptions', methods=['GET'])
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
                r.album_title,
                r.recording_year
            FROM solo_transcriptions st
            JOIN songs s ON st.song_id = s.id
            JOIN recordings r ON st.recording_id = r.id
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


@app.route('/api/transcriptions/<transcription_id>', methods=['GET'])
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
                r.album_title,
                r.recording_year,
                r.label
            FROM solo_transcriptions st
            JOIN songs s ON st.song_id = s.id
            JOIN recordings r ON st.recording_id = r.id
            WHERE st.id = %s
        """
        
        transcription = db_tools.execute_query(query, (transcription_id,), fetch_one=True)
        
        if not transcription:
            return jsonify({'error': 'Transcription not found'}), 404
        
        return jsonify(transcription)
        
    except Exception as e:
        logger.error(f"Error fetching transcription detail: {e}")
        return jsonify({'error': 'Failed to fetch transcription detail', 'detail': str(e)}), 500

if __name__ == '__main__':
    # Running directly with 'python app.py' (not gunicorn)
    logger.info("Starting Flask application directly (not gunicorn)...")
    logger.info("Database connection pool will initialize on first request")
    
    # Start keepalive thread
    db_tools.start_keepalive_thread()
    
    # Start research worker thread (only when running directly)
    if not research_queue._worker_running:
        research_queue.start_worker(song_research.research_song)
        logger.info("Research worker thread initialized")
        
    try:
        app.run(debug=True, host='0.0.0.0', port=5001)
    finally:
        # Cleanup
        logger.info("Shutting down...")
        research_queue.stop_worker()
        db_tools.stop_keepalive_thread()
        db_tools.close_connection_pool()
        logger.info("Shutdown complete")
        
        # In app.py, add this at the bottom:
import atexit

def cleanup_connections():
    """Close the connection pool on shutdown"""
    logger.info("Shutting down connection pool...")
    db_tools.close_connection_pool()
    logger.info("Connection pool closed")

atexit.register(cleanup_connections)