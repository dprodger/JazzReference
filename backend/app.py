"""
Jazz Reference API Backend - Improved Version
A Flask API with robust database connection handling
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import logging
import time
from api_doc import api_docs
import sys
import os

# Import database tools
import db_tools


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
app.register_blueprint(api_docs)


@app.route('/api/health', methods=['GET'])
def health_check():
    """Enhanced health check endpoint with detailed diagnostics"""
    health_status = {
        'status': 'unknown',
        'database': 'unknown',
        'pool_stats': None,
        'timestamp': time.time()
    }
    
    try:
        # Check if db_tools.pool exists
        if db_tools.pool is None:
            health_status['status'] = 'unhealthy'
            health_status['database'] = 'db_tools.pool not initialized'
            return jsonify(health_status), 503
        
        # Get db_tools.pool statistics
        pool_stats = db_tools.pool.get_stats()
        health_status['pool_stats'] = {
            'pool_size': pool_stats.get('pool_size', 0),
            'pool_available': pool_stats.get('pool_available', 0),
            'requests_waiting': pool_stats.get('requests_waiting', 0)
        }
        
        # Test database connection
        result = db_tools.execute_query("SELECT version(), current_timestamp", fetch_one=True)
        
        health_status['status'] = 'healthy'
        health_status['database'] = 'connected'
        health_status['db_version'] = result['version'] if result else 'unknown'
        health_status['db_time'] = str(result['current_timestamp']) if result else 'unknown'
        
        return jsonify(health_status), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        health_status['status'] = 'unhealthy'
        health_status['database'] = f'error: {str(e)}'
        return jsonify(health_status), 503

"""
MINIMAL TEST ENDPOINT
Add this to app.py first to verify routing works, then add the full endpoints.
Paste this right after the /api/health endpoint.
"""

@app.route('/api/test-content-reports', methods=['POST', 'GET'])
def test_content_reports():
    """Test endpoint to verify routing works"""
    if request.method == 'POST':
        return jsonify({
            'success': True,
            'message': 'POST endpoint works!',
            'received_data': request.get_json()
        }), 201
    else:
        return jsonify({
            'success': True,
            'message': 'GET endpoint works!'
        })


# After this works, replace with the full endpoints from app_py_additions.py
@app.route('/api/songs', methods=['GET'])
def get_songs():
    """Get all songs or search songs by title"""
    search_query = request.args.get('search', '')
    
    try:
        if search_query:
            query = """
                SELECT id, title, composer, structure, musicbrainz_id, song_reference, external_references, 
                       created_at, updated_at
                FROM songs
                WHERE title ILIKE %s OR composer ILIKE %s
                ORDER BY title
            """
            params = (f'%{search_query}%', f'%{search_query}%')
        else:
            query = """
                SELECT id, title, composer, structure, musicbrainz_id, song_reference, external_references,
                       created_at, updated_at
                FROM songs
                ORDER BY title
            """
            params = None
        
        songs = db_tools.execute_query(query, params)
        return jsonify(songs)
        
    except Exception as e:
        logger.error(f"Error fetching songs: {e}")
        return jsonify({'error': 'Failed to fetch songs', 'detail': str(e)}), 500

@app.route('/api/songs/<song_id>', methods=['GET'])
def get_song_detail(song_id):
    """Get detailed information about a specific song - OPTIMIZED VERSION"""
    try:
        # Get song information
        song_query = """
            SELECT id, title, composer, structure, song_reference, musicbrainz_id, 
                   external_references, created_at, updated_at
            FROM songs
            WHERE id = %s
        """
        song = db_tools.execute_query(song_query, (song_id,), fetch_one=True)
        
        if not song:
            return jsonify({'error': 'Song not found'}), 404
        
        # Get ALL recordings with their performers in ONE query using JSON aggregation
        recordings_query = """
            SELECT 
                r.id,
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
                COALESCE(
                    json_agg(
                        json_build_object(
                            'id', p.id,
                            'name', p.name,
                            'instrument', i.name,
                            'role', rp.role
                        ) ORDER BY 
                            CASE rp.role 
                                WHEN 'leader' THEN 1 
                                WHEN 'sideman' THEN 2 
                                ELSE 3 
                            END,
                            p.name
                    ) FILTER (WHERE p.id IS NOT NULL),
                    '[]'::json
                ) as performers
            FROM recordings r
            LEFT JOIN recording_performers rp ON r.id = rp.recording_id
            LEFT JOIN performers p ON rp.performer_id = p.id
            LEFT JOIN instruments i ON rp.instrument_id = i.id
            WHERE r.song_id = %s
            GROUP BY r.id, r.album_title, r.recording_date, r.recording_year,
                     r.label, r.spotify_url, r.spotify_track_id,
                     r.album_art_small, r.album_art_medium, r.album_art_large,
                     r.youtube_url, r.apple_music_url,
                     r.is_canonical, r.notes
            ORDER BY r.is_canonical DESC, r.recording_year DESC
        """
        recordings = db_tools.execute_query(recordings_query, (song_id,))
        
        # Add recording info to song
        song['recordings'] = recordings
        song['recording_count'] = len(recordings)
        
        return jsonify(song)
        
    except Exception as e:
        logger.error(f"Error fetching song detail: {e}")
        return jsonify({'error': 'Failed to fetch song detail', 'detail': str(e)}), 500
        
@app.route('/api/recordings/<recording_id>', methods=['GET'])
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

@app.route('/api/performers', methods=['GET'])
def get_performers():
    """Get all performers or search performers by name"""
    search_query = request.args.get('search', '')
    
    try:
        if search_query:
            query = """
                SELECT id, name, biography, birth_date, death_date, 
                    external_links, wikipedia_url, musicbrainz_id
                FROM performers
                WHERE name ILIKE %s
                ORDER BY name
            """
            params = (f'%{search_query}%',)
        else:
            query = """
                SELECT id, name, biography, birth_date, death_date, external_links, wikipedia_url, musicbrainz_id
                FROM performers
                ORDER BY name
            """
            params = None
        
        performers = db_tools.execute_query(query, params)
        return jsonify(performers)
        
    except Exception as e:
        logger.error(f"Error fetching performers: {e}")
        return jsonify({'error': 'Failed to fetch performers', 'detail': str(e)}), 500

# Add these new routes to your existing backend/app.py file
# Add them before the if __name__ == '__main__' block

@app.route('/api/performers/<performer_id>/images', methods=['GET'])
def get_performer_images(performer_id):
    """Get all images for a specific performer"""
    try:
        # Get all images for this performer with join data
        query = """
            SELECT 
                i.id,
                i.url,
                i.source,
                i.source_identifier,
                i.license_type,
                i.license_url,
                i.attribution,
                i.width,
                i.height,
                i.thumbnail_url,
                i.source_page_url,
                ai.is_primary,
                ai.display_order
            FROM images i
            JOIN artist_images ai ON i.id = ai.image_id
            WHERE ai.performer_id = %s
            ORDER BY ai.is_primary DESC, ai.display_order, i.created_at
        """
        
        images = db_tools.execute_query(query, (performer_id,), fetch_all=True)
        
        if not images:
            return jsonify([])
        
        return jsonify(images)
        
    except Exception as e:
        logger.error(f"Error fetching performer images: {e}")
        return jsonify({'error': 'Failed to fetch performer images', 'detail': str(e)}), 500


@app.route('/api/images/<image_id>', methods=['GET'])
def get_image_detail(image_id):
    """Get detailed information about a specific image"""
    try:
        query = """
            SELECT 
                i.*,
                COALESCE(
                    json_agg(
                        json_build_object(
                            'performer_id', p.id,
                            'performer_name', p.name,
                            'is_primary', ai.is_primary,
                            'display_order', ai.display_order
                        ) ORDER BY ai.is_primary DESC, ai.display_order
                    ) FILTER (WHERE p.id IS NOT NULL),
                    '[]'::json
                ) as performers
            FROM images i
            LEFT JOIN artist_images ai ON i.id = ai.image_id
            LEFT JOIN performers p ON ai.performer_id = p.id
            WHERE i.id = %s
            GROUP BY i.id
        """
        
        image = db_tools.execute_query(query, (image_id,), fetch_one=True)
        
        if not image:
            return jsonify({'error': 'Image not found'}), 404
        
        return jsonify(image)
        
    except Exception as e:
        logger.error(f"Error fetching image detail: {e}")
        return jsonify({'error': 'Failed to fetch image detail', 'detail': str(e)}), 500


# Also update the get_performer_detail function to include images
# Replace the existing function with this updated version:

@app.route('/api/performers/<performer_id>', methods=['GET'])
def get_performer_detail(performer_id):
    """Get detailed information about a specific performer - WITH IMAGES"""
    try:
        # Get performer information
        performer_query = """
            SELECT id, name, biography, birth_date, death_date, external_links, wikipedia_url, musicbrainz_id 
            FROM performers
            WHERE id = %s
        """
        performer = db_tools.execute_query(performer_query, (performer_id,), fetch_one=True)
        
        if not performer:
            return jsonify({'error': 'Performer not found'}), 404
        
        # Get instruments
        instruments_query = """
            SELECT i.name, pi.is_primary
            FROM performer_instruments pi
            JOIN instruments i ON pi.instrument_id = i.id
            WHERE pi.performer_id = %s
            ORDER BY pi.is_primary DESC, i.name
        """
        performer['instruments'] = db_tools.execute_query(instruments_query, (performer_id,))
        
        # Get recordings
        recordings_query = """
            SELECT DISTINCT s.id as song_id, s.title as song_title, 
                   r.id as recording_id, r.album_title, r.recording_year, 
                   r.is_canonical, rp.role
            FROM recording_performers rp
            JOIN recordings r ON rp.recording_id = r.id
            JOIN songs s ON r.song_id = s.id
            WHERE rp.performer_id = %s
            ORDER BY r.recording_year DESC NULLS LAST, s.title
        """
        performer['recordings'] = db_tools.execute_query(recordings_query, (performer_id,))
        
        # Get images
        images_query = """
            SELECT 
                i.id,
                i.url,
                i.source,
                i.source_identifier,
                i.license_type,
                i.license_url,
                i.attribution,
                i.width,
                i.height,
                i.thumbnail_url,
                i.source_page_url,
                ai.is_primary,
                ai.display_order
            FROM images i
            JOIN artist_images ai ON i.id = ai.image_id
            WHERE ai.performer_id = %s
            ORDER BY ai.is_primary DESC, ai.display_order, i.created_at
        """
        performer['images'] = db_tools.execute_query(images_query, (performer_id,))
        
        return jsonify(performer)
        
    except Exception as e:
        logger.error(f"Error fetching performer detail: {e}")
        return jsonify({'error': 'Failed to fetch performer detail', 'detail': str(e)}), 500


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




#!/usr/bin/env python3
@app.route('/api/performers/search', methods=['GET'])
def search_performers():
    """
    Search for performers by name
    
    Query Parameters:
        name: Performer name to search for (case-insensitive partial match)
        
    Returns:
        List of matching performers with their details
    """
    name = request.args.get('name', '').strip()
    
    if not name:
        return jsonify({'error': 'Name parameter is required'}), 400
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Search for performers with names containing the search term (case-insensitive)
        # Use ILIKE for case-insensitive matching
        cur.execute("""
            SELECT 
                id,
                name,
                biography,
                birth_date,
                death_date,
                musicbrainz_id
            FROM performers
            WHERE LOWER(name) LIKE LOWER(%s)
            ORDER BY 
                -- Exact matches first
                CASE WHEN LOWER(name) = LOWER(%s) THEN 0 ELSE 1 END,
                -- Then by name
                name
            LIMIT 10
        """, (f'%{name}%', name))
        
        performers = cur.fetchall()
        
        cur.close()
        conn.close()
        
        if not performers:
            return jsonify([]), 404
        
        # Format the results
        results = []
        for performer in performers:
            results.append({
                'id': str(performer['id']),
                'name': performer['name'],
                'biography': performer['biography'],
                'birth_date': performer['birth_date'].isoformat() if performer['birth_date'] else None,
                'death_date': performer['death_date'].isoformat() if performer['death_date'] else None,
                'musicbrainz_id': performer['musicbrainz_id']
            })
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error searching performers: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500




if __name__ == '__main__':
    # Don't initialize pool at startup - let it initialize on first request
    # This prevents deployment failures if DB is temporarily unavailable
    logger.info("Starting Flask application...")
    logger.info("Database connection pool will initialize on first request")
    
    # Start keepalive thread
    db_tools.start_keepalive_thread()
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5001)
    finally:
        # Stop keepalive thread and close pool
        db_tools.stop_keepalive_thread()
        db_tools.close_connection_pool()
