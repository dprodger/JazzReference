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

# Set pooling mode BEFORE importing db_utils
os.environ['DB_USE_POOLING'] = 'true'

# Import database tools
import db_utils as db_tools

# Import research tools
import research_queue
import song_research

# Custom JSON encoder to format dates without timestamps
from flask.json.provider import DefaultJSONProvider

class CustomJSONProvider(DefaultJSONProvider):
    """Custom JSON provider that formats dates as YYYY-MM-DD"""
    def default(self, obj):
        if isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')
        return super().default(obj)

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

















@app.route('/api/songs/<song_id>/refresh', methods=['POST'])
def refresh_song_data(song_id):
    """
    Queue a song for background research and data refresh
    
    This endpoint accepts a song ID and adds it to the background processing
    queue. The actual research happens asynchronously in a worker thread.
    
    Args:
        song_id: UUID of the song to research
        
    Returns:
        JSON response with queue status
    """
    try:
        # First verify the song exists and get its name
        query = "SELECT id, title FROM songs WHERE id = %s"
        song = db_tools.execute_query(query, (song_id,), fetch_one=True)
        
        if not song:
            return jsonify({
                'error': 'Song not found',
                'song_id': song_id
            }), 404
        
        # Add to research queue
        success = research_queue.add_song_to_queue(song['id'], song['title'])
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Song queued for research',
                'song_id': song['id'],
                'song_title': song['title'],
                'queue_size': research_queue.get_queue_size()
            }), 202  # 202 Accepted - processing will happen asynchronously
        else:
            return jsonify({
                'error': 'Failed to queue song',
                'song_id': song_id
            }), 500
            
    except Exception as e:
        logger.error(f"Error queueing song {song_id} for research: {e}")
        return jsonify({
            'error': 'Internal server error',
            'detail': str(e)
        }), 500


@app.route('/api/research/queue', methods=['GET'])
def get_queue_status():
    """Get the current status of the research queue"""
    return jsonify({
        'queue_size': research_queue.get_queue_size(),
        'worker_active': research_queue._worker_running
    })








@app.route('/api/songs', methods=['GET'])
def get_songs():
    """Get all songs or search songs by title"""
    search_query = request.args.get('search', '')
    
    try:
        if search_query:
            query = """
                SELECT id, title, composer, structure, musicbrainz_id, wikipedia_url, song_reference, external_references, 
                       created_at, updated_at
                FROM songs
                WHERE title ILIKE %s OR composer ILIKE %s
                ORDER BY title
            """
            params = (f'%{search_query}%', f'%{search_query}%')
        else:
            query = """
                SELECT id, title, composer, structure, musicbrainz_id, wikipedia_url, song_reference, external_references,
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
    """
    Get detailed information about a specific song with all recordings, performers, and transcriptions.
    
    OPTIMIZED VERSION: Uses JSON aggregation to fetch everything in 3 queries instead of 50+.
    """
    try:
        # Query 1: Get song information
        song_query = """
            SELECT 
                id, title, composer, structure, song_reference,
                musicbrainz_id, wikipedia_url, external_references, 
                created_at, updated_at
            FROM songs
            WHERE id = %s
        """
        song = db_tools.execute_query(song_query, (song_id,), fetch_one=True)
        
        if not song:
            return jsonify({'error': 'Song not found'}), 404
        
        # Query 2: Get ALL recordings with performers using json_agg
        recordings_query = """
            SELECT 
                r.id, r.album_title, r.recording_date, r.recording_year,
                r.label, r.spotify_url, r.spotify_track_id,
                r.album_art_small, r.album_art_medium, r.album_art_large,
                r.youtube_url, r.apple_music_url, r.musicbrainz_id,
                r.is_canonical, r.notes,
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
                     r.youtube_url, r.apple_music_url, r.musicbrainz_id,
                     r.is_canonical, r.notes
            ORDER BY r.is_canonical DESC, r.recording_year DESC
        """
        recordings = db_tools.execute_query(recordings_query, (song_id,), fetch_all=True)
        
        # Query 3: Get transcriptions
        transcriptions_query = """
            SELECT 
                st.id, st.song_id, st.recording_id, st.youtube_url,
                st.created_at, st.updated_at,
                r.album_title, r.recording_year
            FROM solo_transcriptions st
            LEFT JOIN recordings r ON st.recording_id = r.id
            WHERE st.song_id = %s
            ORDER BY r.recording_year DESC
        """
        transcriptions = db_tools.execute_query(transcriptions_query, (song_id,), fetch_all=True)
        
        # Build response
        song_dict = dict(song)
        song_dict['recordings'] = recordings if recordings else []
        song_dict['recording_count'] = len(recordings) if recordings else 0
        song_dict['transcriptions'] = transcriptions if transcriptions else []  # NEW
        song_dict['transcription_count'] = len(transcriptions) if transcriptions else 0  # NEW
        
        return jsonify(song_dict)
        
    except Exception as e:
        logger.error(f"Error fetching song detail: {e}")
        return jsonify({'error': 'Failed to fetch song details', 'detail': str(e)}), 500


   
@app.route('/api/songs/search', methods=['GET'])
def search_songs():
    """
    Search for songs by title
    
    Query Parameters:
        title: Song title to search for (case-insensitive partial match)
        
    Returns:
        List of matching songs with their details
    """
    title = request.args.get('title', '').strip()
    
    if not title:
        return jsonify({'error': 'Title parameter is required'}), 400
    
    try:
        with db_tools.get_db_connection() as conn:
            with conn.cursor() as cur:
            
                # Search for songs with titles containing the search term (case-insensitive)
                # Use ILIKE for case-insensitive matching
                cur.execute("""
                    SELECT 
                        id,
                        title,
                        composer,
                        structure,
                        musicbrainz_id,
                        wikipedia_url,
                        external_references
                    FROM songs
                    WHERE LOWER(title) LIKE LOWER(%s)
                    ORDER BY 
                        -- Exact matches first
                        CASE WHEN LOWER(title) = LOWER(%s) THEN 0 ELSE 1 END,
                        -- Then by title length (shorter = more likely to be what we want)
                        LENGTH(title),
                        title
                    LIMIT 10
                """, (f'%{title}%', title))
                
                songs = cur.fetchall()
                
                return jsonify(songs)
                
    except Exception as e:
        logger.error(f"Error searching songs: {e}")
        return jsonify({'error': 'Failed to search songs', 'detail': str(e)}), 500


@app.route('/api/songs', methods=['POST'])
def create_song():
    """Create a new song from iOS app (typically from MusicBrainz import)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        title = data.get('title')
        if not title or not title.strip():
            return jsonify({'error': 'Song title is required'}), 400
        
        title = title.strip()
        
        # Optional fields - safely handle None values
        composer = safe_strip(data.get('composer'))
        musicbrainz_id = safe_strip(data.get('musicbrainz_id'))
        wikipedia_url = safe_strip(data.get('wikipedia_url'))
        structure = safe_strip(data.get('structure'))
        
        # Handle external references (JSON field)
        external_refs = data.get('external_references', {})
        if not isinstance(external_refs, dict):
            external_refs = {}
        
        # Note: wikipedia_url is now stored in its own column, not in external_references
        
        # Start transaction
        with db_tools.get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if song already exists by title (case-insensitive)
                cur.execute("""
                    SELECT id, title, musicbrainz_id FROM songs 
                    WHERE LOWER(title) = LOWER(%s)
                """, (title,))
                
                existing = cur.fetchone()
                if existing:
                    return jsonify({
                        'error': 'Song already exists',
                        'existing_song': existing
                    }), 409
                
                # Check if song exists by MusicBrainz ID
                if musicbrainz_id:
                    cur.execute("""
                        SELECT id, title FROM songs 
                        WHERE musicbrainz_id = %s
                    """, (musicbrainz_id,))
                    
                    existing_by_mbid = cur.fetchone()
                    if existing_by_mbid:
                        return jsonify({
                            'error': 'Song with this MusicBrainz ID already exists',
                            'existing_song': existing_by_mbid
                        }), 409
                
                # Insert new song
                cur.execute("""
                    INSERT INTO songs (
                        title, 
                        composer, 
                        musicbrainz_id,
                        wikipedia_url,
                        structure,
                        external_references,
                        created_at,
                        updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    RETURNING id, title, composer, musicbrainz_id, wikipedia_url
                """, (
                    title,
                    composer,
                    musicbrainz_id,
                    wikipedia_url,
                    structure,
                    json.dumps(external_refs) if external_refs else None
                ))
                
                new_song = cur.fetchone()
                
        logger.info(f"Created new song: {new_song['title']} (ID: {new_song['id']})")
        
        return jsonify({
            'success': True,
            'message': 'Song created successfully',
            'song': new_song
        }), 201
        
    except KeyError as e:
        logger.error(f"Missing data field: {e}")
        return jsonify({
            'success': False,
            'error': f'Invalid request data: {str(e)}'
        }), 400
        
    except Exception as e:
        logger.error(f"Error creating song: {e}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while creating the song. Please try again later.'
        }), 500


@app.route('/api/songs/<song_id>', methods=['PATCH'])
def update_song_musicbrainz_id(song_id):
    """
    Update a song's metadata (MusicBrainz ID, Wikipedia URL, etc.)
    Used when associating an existing song with external references
    """
    try:
        data = request.get_json()
        musicbrainz_id = safe_strip(data.get('musicbrainz_id'))
        wikipedia_url = safe_strip(data.get('wikipedia_url'))
        
        # At least one field must be provided
        if not musicbrainz_id and not wikipedia_url:
            return jsonify({'error': 'At least one field (musicbrainz_id or wikipedia_url) is required'}), 400
        
        with db_tools.get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if song exists
                cur.execute("SELECT id, title FROM songs WHERE id = %s", (song_id,))
                song = cur.fetchone()
                
                if not song:
                    return jsonify({'error': 'Song not found'}), 404
                
                # Check if another song already has this MusicBrainz ID (if provided)
                if musicbrainz_id:
                    cur.execute("""
                        SELECT id, title FROM songs 
                        WHERE musicbrainz_id = %s AND id != %s
                    """, (musicbrainz_id, song_id))
                    
                    conflict = cur.fetchone()
                    if conflict:
                        return jsonify({
                            'error': 'Another song already has this MusicBrainz ID',
                            'conflicting_song': conflict
                        }), 409
                
                # Build dynamic UPDATE query based on provided fields
                update_fields = []
                params = []
                
                if musicbrainz_id:
                    update_fields.append("musicbrainz_id = %s")
                    params.append(musicbrainz_id)
                
                if wikipedia_url:
                    update_fields.append("wikipedia_url = %s")
                    params.append(wikipedia_url)
                
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                params.append(song_id)
                
                # Update the song
                cur.execute(f"""
                    UPDATE songs
                    SET {', '.join(update_fields)}
                    WHERE id = %s
                    RETURNING id, title, composer, musicbrainz_id, wikipedia_url
                """, params)
                
                updated_song = cur.fetchone()
                
        logger.info(f"Updated song {song_id} - MusicBrainz ID: {musicbrainz_id}, Wikipedia URL: {wikipedia_url}")
        
        return jsonify({
            'success': True,
            'message': 'Song updated successfully',
            'song': updated_song
        })
        
    except Exception as e:
        logger.error(f"Error updating song: {e}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while updating the song'
        }), 500

        
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

@app.route('/api/performers', methods=['POST'])
def create_performer():
    """Create a new performer from iOS app (typically from MusicBrainz import)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        name = data.get('name')
        if not name or not name.strip():
            return jsonify({'error': 'Performer name is required'}), 400
        
        name = name.strip()
        
        # Optional fields - safely handle None values
        musicbrainz_id = safe_strip(data.get('musicbrainz_id'))
        biography = safe_strip(data.get('biography'))
        birth_date = safe_strip(data.get('birth_date'))
        death_date = safe_strip(data.get('death_date'))
        wikipedia_url = safe_strip(data.get('wikipedia_url'))
        instruments = data.get('instruments', [])
        
        # Start transaction
        with db_tools.get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if performer already exists by name
                cur.execute("""
                    SELECT id, name FROM performers 
                    WHERE LOWER(name) = LOWER(%s)
                """, (name,))
                
                existing = cur.fetchone()
                if existing:
                    return jsonify({
                        'error': 'Performer already exists',
                        'existing_performer': existing
                    }), 409
                
                # Check if performer exists by MusicBrainz ID
                if musicbrainz_id:
                    cur.execute("""
                        SELECT id, name FROM performers 
                        WHERE musicbrainz_id = %s
                    """, (musicbrainz_id,))
                    
                    existing = cur.fetchone()
                    if existing:
                        return jsonify({
                            'error': 'Performer with this MusicBrainz ID already exists',
                            'existing_performer': existing
                        }), 409
                
                # Insert the new performer
                cur.execute("""
                    INSERT INTO performers 
                    (name, biography, birth_date, death_date, wikipedia_url, musicbrainz_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, name, biography, birth_date, death_date, 
                              wikipedia_url, musicbrainz_id
                """, (name, biography, birth_date, death_date, wikipedia_url, musicbrainz_id))
                
                new_performer = cur.fetchone()
                performer_id = new_performer['id']
                
                # Handle instruments if provided
                if instruments and len(instruments) > 0:
                    for instrument_name in instruments:
                        if not instrument_name or not instrument_name.strip():
                            continue
                        
                        instrument_name = instrument_name.strip()
                        
                        # Get or create instrument
                        cur.execute("""
                            SELECT id FROM instruments WHERE LOWER(name) = LOWER(%s)
                        """, (instrument_name,))
                        
                        instrument = cur.fetchone()
                        
                        if not instrument:
                            # Create new instrument
                            cur.execute("""
                                INSERT INTO instruments (name)
                                VALUES (%s)
                                RETURNING id
                            """, (instrument_name,))
                            instrument = cur.fetchone()
                        
                        instrument_id = instrument['id']
                        
                        # Link performer to instrument
                        cur.execute("""
                            INSERT INTO performer_instruments 
                            (performer_id, instrument_id, is_primary)
                            VALUES (%s, %s, %s)
                            ON CONFLICT DO NOTHING
                        """, (performer_id, instrument_id, True))
                
                conn.commit()
                
                logger.info(f"Created performer: {name} (ID: {performer_id})")
                
                # Return the created performer
                return jsonify({
                    'success': True,
                    'performer': new_performer,
                    'message': f'Successfully created performer: {name}'
                }), 201
                
    except Exception as e:
        logger.error(f"Error creating performer: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to create performer',
            'detail': str(e)
        }), 500        
        
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
        with db_tools.get_db_connection() as conn:
            with conn.cursor() as cur:
            
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