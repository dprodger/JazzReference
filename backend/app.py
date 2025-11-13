"""
Jazz Reference API Backend - Improved Version
A Flask API with robust database connection handling
"""

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from datetime import date
import logging
import time
from api_doc import api_docs
import sys
import os
import json
from routes.health import health_bp
from routes.research import research_bp
from routes.songs import songs_bp
from routes.recordings import recordings_bp
from routes.performers import performers_bp
from routes.images import images_bp


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


logger.info(f"Spotify credentials present: {bool(os.environ.get('SPOTIFY_CLIENT_ID'))}")

# Worker thread initialization:
# - When running under gunicorn: Initialized via post_worker_init hook in gunicorn.conf.py
# - When running directly (python app.py): Initialized in __main__ block at bottom
# This ensures the worker runs in the process that handles HTTP requests

logger.info(f"Flask app initialized in PID {os.getpid()}")

def safe_strip(value):
    """Safely strip a string value, handling None"""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return value


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







"""
Repertoire API Endpoints
Add these endpoints to backend/app.py

These endpoints support viewing and managing repertoires (collections of songs).
In Phase 1, we implement GET endpoints for listing and viewing repertoires.
"""

# =============================================================================
# REPERTOIRE ENDPOINTS
# =============================================================================

@app.route('/api/repertoires', methods=['GET'])
def get_repertoires():
    """
    Get all repertoires with song counts
    
    Returns:
        List of all repertoires with metadata and song counts
        
    Example response:
        [
            {
                "id": "uuid",
                "name": "Gig Standards",
                "description": "Essential standards for typical jazz gigs",
                "song_count": 42,
                "created_at": "2025-01-15T10:30:00Z",
                "updated_at": "2025-01-20T14:22:00Z"
            },
            ...
        ]
    """
    try:
        query = """
            SELECT 
                r.id,
                r.name,
                r.description,
                r.created_at,
                r.updated_at,
                COUNT(rs.song_id) as song_count
            FROM repertoires r
            LEFT JOIN repertoire_songs rs ON r.id = rs.repertoire_id
            GROUP BY r.id, r.name, r.description, r.created_at, r.updated_at
            ORDER BY r.name
        """
        
        repertoires = db_tools.execute_query(query)
        return jsonify(repertoires)
        
    except Exception as e:
        logger.error(f"Error fetching repertoires: {e}")
        return jsonify({'error': 'Failed to fetch repertoires', 'detail': str(e)}), 500


@app.route('/api/repertoires/<repertoire_id>', methods=['GET'])
def get_repertoire_detail(repertoire_id):
    """
    Get detailed information about a specific repertoire
    
    Args:
        repertoire_id: UUID of the repertoire
        
    Returns:
        Repertoire with full song details
        
    Example response:
        {
            "id": "uuid",
            "name": "Gig Standards",
            "description": "Essential standards for typical jazz gigs",
            "created_at": "2025-01-15T10:30:00Z",
            "updated_at": "2025-01-20T14:22:00Z",
            "songs": [
                {
                    "id": 1,
                    "title": "Autumn Leaves",
                    "composer": "Joseph Kosma",
                    "structure": "AABA",
                    "added_to_repertoire_at": "2025-01-15T10:35:00Z"
                },
                ...
            ],
            "song_count": 42
        }
    """
    try:
        # Get repertoire information
        repertoire_query = """
            SELECT id, name, description, created_at, updated_at
            FROM repertoires
            WHERE id = %s
        """
        repertoire = db_tools.execute_query(repertoire_query, (repertoire_id,), fetch_one=True)
        
        if not repertoire:
            return jsonify({'error': 'Repertoire not found'}), 404
        
        # Get songs in this repertoire
        songs_query = """
            SELECT 
                s.id,
                s.title,
                s.composer,
                s.structure,
                s.musicbrainz_id,
                s.external_references,
                rs.created_at as added_to_repertoire_at
            FROM songs s
            INNER JOIN repertoire_songs rs ON s.id = rs.song_id
            WHERE rs.repertoire_id = %s
            ORDER BY s.title
        """
        songs = db_tools.execute_query(songs_query, (repertoire_id,))
        
        # Add songs to repertoire
        repertoire['songs'] = songs
        repertoire['song_count'] = len(songs)
        
        return jsonify(repertoire)
        
    except Exception as e:
        logger.error(f"Error fetching repertoire detail: {e}")
        return jsonify({'error': 'Failed to fetch repertoire detail', 'detail': str(e)}), 500


@app.route('/api/repertoires/<repertoire_id>/songs', methods=['GET'])
def get_repertoire_songs(repertoire_id):
    """
    Get just the songs in a specific repertoire (without full repertoire metadata)
    
    This is useful for the iOS app when it wants to filter the song list
    to just show songs in the current repertoire.
    
    Args:
        repertoire_id: UUID of the repertoire, or "all" for all songs
        
    Query Parameters:
        search: Optional search term to filter songs by title or composer
        
    Returns:
        List of songs in the repertoire
        
    Example response:
        [
            {
                "id": 1,
                "title": "Autumn Leaves",
                "composer": "Joseph Kosma",
                "structure": "AABA",
                "musicbrainz_id": "...",
                "external_references": {...},
                "added_to_repertoire_at": "2025-01-15T10:35:00Z"
            },
            ...
        ]
    """
    try:
        # Get search query parameter
        search_query = request.args.get('search', '').strip()
        
        # Special case: "all" means return all songs (no filtering by repertoire)
        if repertoire_id.lower() == 'all':
            if search_query:
                query = """
                    SELECT id, title, composer, structure, musicbrainz_id, wikipedia_url,
                           song_reference, external_references, created_at, updated_at
                    FROM songs
                    WHERE title ILIKE %s OR composer ILIKE %s
                    ORDER BY title
                """
                params = (f'%{search_query}%', f'%{search_query}%')
                songs = db_tools.execute_query(query, params)
            else:
                query = """
                    SELECT id, title, composer, structure, musicbrainz_id, wikipedia_url,
                           song_reference, external_references, created_at, updated_at
                    FROM songs
                    ORDER BY title
                """
                songs = db_tools.execute_query(query)
            
            return jsonify(songs)
        
        # Verify repertoire exists
        repertoire_check = """
            SELECT id FROM repertoires WHERE id = %s
        """
        repertoire = db_tools.execute_query(repertoire_check, (repertoire_id,), fetch_one=True)
        
        if not repertoire:
            return jsonify({'error': 'Repertoire not found'}), 404
        
        # Get songs in this repertoire
        if search_query:
            query = """
                SELECT 
                    s.id,
                    s.title,
                    s.composer,
                    s.structure,
                    s.musicbrainz_id,
                    s.wikipedia_url,
                    s.song_reference,
                    s.external_references,
                    s.created_at,
                    s.updated_at,
                    rs.created_at as added_to_repertoire_at
                FROM songs s
                INNER JOIN repertoire_songs rs ON s.id = rs.song_id
                WHERE rs.repertoire_id = %s
                  AND (s.title ILIKE %s OR s.composer ILIKE %s)
                ORDER BY s.title
            """
            params = (repertoire_id, f'%{search_query}%', f'%{search_query}%')
            songs = db_tools.execute_query(query, params)
        else:
            query = """
                SELECT 
                    s.id,
                    s.title,
                    s.composer,
                    s.structure,
                    s.musicbrainz_id,
                    s.wikipedia_url,
                    s.song_reference,
                    s.external_references,
                    s.created_at,
                    s.updated_at,
                    rs.created_at as added_to_repertoire_at
                FROM songs s
                INNER JOIN repertoire_songs rs ON s.id = rs.song_id
                WHERE rs.repertoire_id = %s
                ORDER BY s.title
            """
            songs = db_tools.execute_query(query, (repertoire_id,))
        
        return jsonify(songs)
        
    except Exception as e:
        logger.error(f"Error fetching repertoire songs: {e}")
        return jsonify({'error': 'Failed to fetch repertoire songs', 'detail': str(e)}), 500
# =============================================================================
# REPERTOIRE CRUD ENDPOINTS - Add these to app.py after the existing GET endpoints
# =============================================================================

@app.route('/api/repertoires', methods=['POST'])
def create_repertoire():
    """
    Create a new repertoire
    
    Request body:
        {
            "name": "My Gig List",
            "description": "Songs for Friday night gig"  # optional
        }
    
    Returns:
        Created repertoire with id
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or 'name' not in data:
            return jsonify({'error': 'Missing required field: name'}), 400
        
        name = safe_strip(data.get('name'))
        description = safe_strip(data.get('description'))
        
        if not name:
            return jsonify({'error': 'Name cannot be empty'}), 400
        
        # Insert new repertoire
        query = """
            INSERT INTO repertoires (name, description)
            VALUES (%s, %s)
            RETURNING id, name, description, created_at, updated_at
        """
        
        result = db_tools.execute_query(query, (name, description), fetch_one=True)
        
        if not result:
            return jsonify({'error': 'Failed to create repertoire'}), 500
        
        # Add song_count of 0 for new repertoire
        repertoire = dict(result)
        repertoire['song_count'] = 0
        
        logger.info(f"Created repertoire: {name} (ID: {result['id']})")
        return jsonify(repertoire), 201
        
    except Exception as e:
        logger.error(f"Error creating repertoire: {e}")
        return jsonify({'error': 'Failed to create repertoire', 'detail': str(e)}), 500


@app.route('/api/repertoires/<repertoire_id>', methods=['PUT'])
def update_repertoire(repertoire_id):
    """
    Update a repertoire's name and/or description
    
    Request body:
        {
            "name": "Updated Name",           # optional
            "description": "Updated desc"      # optional
        }
    
    Returns:
        Updated repertoire
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Check if repertoire exists
        check_query = "SELECT id FROM repertoires WHERE id = %s"
        exists = db_tools.execute_query(check_query, (repertoire_id,), fetch_one=True)
        
        if not exists:
            return jsonify({'error': 'Repertoire not found'}), 404
        
        # Build update query dynamically based on provided fields
        updates = []
        params = []
        
        if 'name' in data:
            name = safe_strip(data.get('name'))
            if not name:
                return jsonify({'error': 'Name cannot be empty'}), 400
            updates.append("name = %s")
            params.append(name)
        
        if 'description' in data:
            description = safe_strip(data.get('description'))
            updates.append("description = %s")
            params.append(description)
        
        if not updates:
            return jsonify({'error': 'No fields to update'}), 400
        
        # Always update the updated_at timestamp
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(repertoire_id)
        
        query = f"""
            UPDATE repertoires
            SET {', '.join(updates)}
            WHERE id = %s
            RETURNING id, name, description, created_at, updated_at
        """
        
        result = db_tools.execute_query(query, params, fetch_one=True)
        
        if not result:
            return jsonify({'error': 'Failed to update repertoire'}), 500
        
        # Get song count
        count_query = """
            SELECT COUNT(*) as count 
            FROM repertoire_songs 
            WHERE repertoire_id = %s
        """
        count_result = db_tools.execute_query(count_query, (repertoire_id,), fetch_one=True)
        
        repertoire = dict(result)
        repertoire['song_count'] = count_result['count'] if count_result else 0
        
        logger.info(f"Updated repertoire: {repertoire_id}")
        return jsonify(repertoire), 200
        
    except Exception as e:
        logger.error(f"Error updating repertoire: {e}")
        return jsonify({'error': 'Failed to update repertoire', 'detail': str(e)}), 500


@app.route('/api/repertoires/<repertoire_id>', methods=['DELETE'])
def delete_repertoire(repertoire_id):
    """
    Delete a repertoire
    
    Note: This will cascade delete all repertoire_songs entries
    
    Returns:
        Success message
    """
    try:
        # Check if repertoire exists
        check_query = "SELECT id, name FROM repertoires WHERE id = %s"
        exists = db_tools.execute_query(check_query, (repertoire_id,), fetch_one=True)
        
        if not exists:
            return jsonify({'error': 'Repertoire not found'}), 404
        
        # Delete the repertoire (cascade will delete repertoire_songs)
        delete_query = "DELETE FROM repertoires WHERE id = %s"
        db_tools.execute_query(delete_query, (repertoire_id,))
        
        logger.info(f"Deleted repertoire: {exists['name']} (ID: {repertoire_id})")
        return jsonify({
            'success': True,
            'message': 'Repertoire deleted successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting repertoire: {e}")
        return jsonify({'error': 'Failed to delete repertoire', 'detail': str(e)}), 500


@app.route('/api/repertoires/<repertoire_id>/songs', methods=['POST'])
def add_song_to_repertoire(repertoire_id):
    """
    Add a song to a repertoire
    
    Request body:
        {
            "song_id": 123
        }
    
    Returns:
        Success message with song details
    """
    try:
        data = request.get_json()
        
        if not data or 'song_id' not in data:
            return jsonify({'error': 'Missing required field: song_id'}), 400
        
        song_id = str(data.get('song_id'))
        
        # Verify repertoire exists
        rep_query = "SELECT id, name FROM repertoires WHERE id = %s"
        repertoire = db_tools.execute_query(rep_query, (repertoire_id,), fetch_one=True)
        
        if not repertoire:
            return jsonify({'error': 'Repertoire not found'}), 404
        
        # Verify song exists
        song_query = "SELECT id, title, composer FROM songs WHERE id = %s"
        song = db_tools.execute_query(song_query, (song_id,), fetch_one=True)
        
        if not song:
            return jsonify({'error': 'Song not found'}), 404
        
        # Check if song is already in repertoire
        check_query = """
            SELECT id FROM repertoire_songs 
            WHERE repertoire_id = %s AND song_id = %s
        """
        exists = db_tools.execute_query(
            check_query, 
            (repertoire_id, song_id), 
            fetch_one=True
        )
        
        if exists:
            return jsonify({
                'error': 'Song already in repertoire',
                'song': dict(song),
                'repertoire': dict(repertoire)
            }), 409
        
        # Add song to repertoire
        insert_query = """
            INSERT INTO repertoire_songs (repertoire_id, song_id)
            VALUES (%s, %s)
            RETURNING id, created_at
        """
        result = db_tools.execute_query(
            insert_query, 
            (repertoire_id, song_id), 
            fetch_one=True
        )
        
        logger.info(f"Added song '{song['title']}' to repertoire '{repertoire['name']}'")
        
        return jsonify({
            'success': True,
            'message': 'Song added to repertoire',
            'song': dict(song),
            'repertoire': dict(repertoire),
            'added_at': result['created_at']
        }), 201
        
    except Exception as e:
        logger.error(f"Error adding song to repertoire: {e}")
        return jsonify({'error': 'Failed to add song to repertoire', 'detail': str(e)}), 500


@app.route('/api/repertoires/<repertoire_id>/songs/<song_id>', methods=['DELETE'])
def remove_song_from_repertoire(repertoire_id, song_id):
    """
    Remove a song from a repertoire
    
    Returns:
        Success message
    """
    try:
        # Verify repertoire exists
        rep_query = "SELECT id, name FROM repertoires WHERE id = %s"
        repertoire = db_tools.execute_query(rep_query, (repertoire_id,), fetch_one=True)
        
        if not repertoire:
            return jsonify({'error': 'Repertoire not found'}), 404
        
        # Check if song is in repertoire
        check_query = """
            SELECT rs.id, s.title 
            FROM repertoire_songs rs
            JOIN songs s ON rs.song_id = s.id
            WHERE rs.repertoire_id = %s AND rs.song_id = %s
        """
        exists = db_tools.execute_query(
            check_query, 
            (repertoire_id, song_id), 
            fetch_one=True
        )
        
        if not exists:
            return jsonify({'error': 'Song not found in repertoire'}), 404
        
        # Delete the association
        delete_query = """
            DELETE FROM repertoire_songs 
            WHERE repertoire_id = %s AND song_id = %s
        """
        db_tools.execute_query(delete_query, (repertoire_id, song_id))
        
        logger.info(f"Removed song '{exists['title']}' from repertoire '{repertoire['name']}'")
        
        return jsonify({
            'success': True,
            'message': 'Song removed from repertoire'
        }), 200
        
    except Exception as e:
        logger.error(f"Error removing song from repertoire: {e}")
        return jsonify({'error': 'Failed to remove song from repertoire', 'detail': str(e)}), 500

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