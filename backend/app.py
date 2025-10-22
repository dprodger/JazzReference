"""
Jazz Reference API Backend - Improved Version
A Flask API with robust database connection handling
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
import os
import logging
from contextlib import contextmanager
import time
from typing import Optional
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'db.wxinjyotnrqxrwqrtvkp.supabase.co'),
    'database': os.environ.get('DB_NAME', 'postgres'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', 'jovpeW-pukgu0-nifron'),
    'port': os.environ.get('DB_PORT', '5432')
}

# Connection string for pooling
CONNECTION_STRING = (
    f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    f"?sslmode=require"
)

# Global connection pool
pool: Optional[ConnectionPool] = None
keepalive_thread: Optional[threading.Thread] = None
keepalive_stop = threading.Event()

def connection_keepalive():
    """Background thread to keep connections alive during idle periods"""
    logger.info("Starting connection keepalive thread...")
    
    while not keepalive_stop.is_set():
        try:
            # Wait 5 minutes between keepalive pings
            if keepalive_stop.wait(300):  # 300 seconds = 5 minutes
                break
            
            if pool is not None:
                logger.debug("Sending keepalive ping to database...")
                try:
                    with pool.connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT 1")
                    logger.debug("Keepalive ping successful")
                except Exception as e:
                    logger.warning(f"Keepalive ping failed: {e}")
                    
        except Exception as e:
            logger.error(f"Error in keepalive thread: {e}")
    
    logger.info("Connection keepalive thread stopped")

def init_connection_pool(max_retries=3, retry_delay=2):
    """Initialize the connection pool with retry logic optimized for port 6543"""
    global pool
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Initializing connection pool (attempt {attempt + 1}/{max_retries})...")
            
            # Use VERY conservative settings for Supabase free tier
            pool = ConnectionPool(
                CONNECTION_STRING,
                min_size=1,  # Only 1 connection
                max_size=2,  # Max 2 connections per worker
                open=True,
                timeout=10,  # Reduce timeout
                max_waiting=2,  # Fewer waiting requests
                kwargs={
                    'row_factory': dict_row,
                    'connect_timeout': 5,
                    'keepalives': 1,
                    'keepalives_idle': 30,
                    'keepalives_interval': 10,
                    'keepalives_count': 3,
                    'options': '-c statement_timeout=30000'
                }
            )
            
            # Test the connection
            logger.info("Testing connection pool...")
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 as test")
                    result = cur.fetchone()
                    logger.info(f"✓ Connection pool initialized successfully (test: {result})")
            
            return True
            
        except Exception as e:
            logger.error(f"✗ Connection pool initialization failed (attempt {attempt + 1}/{max_retries}): {e}")
            
            # Clean up failed pool
            if pool is not None:
                try:
                    pool.close()
                except:
                    pass
                pool = None
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 1.5  # Exponential backoff
            else:
                logger.error("Failed to initialize connection pool after all retries")
                return False
    
    return False

@contextmanager
def get_db_connection():
    """Get a database connection from the pool with explicit transaction management"""
    global pool
    
    # Lazy initialization - create pool on first request if not exists
    if pool is None:
        logger.info("Connection pool not initialized, initializing now...")
        if not init_connection_pool():
            raise RuntimeError("Failed to initialize connection pool")
    
    conn = None
    max_retries = 2
    retry_delay = 0.5
    
    for attempt in range(max_retries):
        try:
            conn = pool.getconn(timeout=10)  # 10 second timeout to get connection from pool
            
            # Yield the connection for use
            yield conn
            
            # If we get here, the code block succeeded
            # Explicitly commit the transaction
            conn.commit()
            return  # Success, exit the function
            
        except psycopg.OperationalError as e:
            logger.error(f"Database operational error (attempt {attempt + 1}/{max_retries}): {e}")
            
            # Rollback on error
            if conn:
                try:
                    conn.rollback()
                except Exception as rollback_error:
                    logger.error(f"Error rolling back transaction: {rollback_error}")
            
            # If this was a connection error and we have retries left, try again
            if attempt < max_retries - 1:
                logger.info(f"Retrying connection in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
                
                # Return the bad connection if we got one
                if conn:
                    try:
                        pool.putconn(conn)
                    except:
                        pass
                conn = None
            else:
                raise
                
        except Exception as e:
            # Rollback on any error
            if conn:
                try:
                    conn.rollback()
                    logger.debug("Transaction rolled back due to error")
                except Exception as rollback_error:
                    logger.error(f"Error rolling back transaction: {rollback_error}")
            
            logger.error(f"Unexpected database error: {e}")
            raise
            
        finally:
            # Always return connection to pool
            if conn:
                try:
                    pool.putconn(conn)
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")

def execute_query(query, params=None, fetch_one=False, fetch_all=True):
    """Execute a query with proper error handling and logging"""
    start_time = time.time()
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                
                if fetch_one:
                    result = cur.fetchone()
                elif fetch_all:
                    result = cur.fetchall()
                else:
                    result = None
                
                duration = time.time() - start_time
                logger.debug(f"Query executed in {duration:.3f}s")
                
                return result
                
    except psycopg.OperationalError as e:
        logger.error(f"Database operational error after {time.time() - start_time:.3f}s: {e}")
        raise
    except Exception as e:
        logger.error(f"Query error after {time.time() - start_time:.3f}s: {e}")
        raise

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
        # Check if pool exists
        if pool is None:
            health_status['status'] = 'unhealthy'
            health_status['database'] = 'pool not initialized'
            return jsonify(health_status), 503
        
        # Get pool statistics
        pool_stats = pool.get_stats()
        health_status['pool_stats'] = {
            'pool_size': pool_stats.get('pool_size', 0),
            'pool_available': pool_stats.get('pool_available', 0),
            'requests_waiting': pool_stats.get('requests_waiting', 0)
        }
        
        # Test database connection
        result = execute_query("SELECT version(), current_timestamp", fetch_one=True)
        
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
        
        songs = execute_query(query, params)
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
        song = execute_query(song_query, (song_id,), fetch_one=True)
        
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
                r.youtube_url,
                r.apple_music_url,
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
                     r.label, r.spotify_url, r.youtube_url, r.apple_music_url,
                     r.is_canonical, r.notes
            ORDER BY r.is_canonical DESC, r.recording_year DESC
        """
        recordings = execute_query(recordings_query, (song_id,))
        
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
                   r.recording_year, r.label, r.spotify_url, r.youtube_url,
                   r.apple_music_url, r.is_canonical, r.notes,
                   s.title as song_title, s.composer
            FROM recordings r
            JOIN songs s ON r.song_id = s.id
            WHERE r.id = %s
        """
        recording = execute_query(recording_query, (recording_id,), fetch_one=True)
        
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
        recording['performers'] = execute_query(performers_query, (recording_id,))
        
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
                SELECT id, name, biography, birth_date, death_date, external_links
                FROM performers
                WHERE name ILIKE %s
                ORDER BY name
            """
            params = (f'%{search_query}%',)
        else:
            query = """
                SELECT id, name, biography, birth_date, death_date, external_links
                FROM performers
                ORDER BY name
            """
            params = None
        
        performers = execute_query(query, params)
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
        
        images = execute_query(query, (performer_id,), fetch_all=True)
        
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
        
        image = execute_query(query, (image_id,), fetch_one=True)
        
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
            SELECT id, name, biography, birth_date, death_date, external_links, external_references
            FROM performers
            WHERE id = %s
        """
        performer = execute_query(performer_query, (performer_id,), fetch_one=True)
        
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
        performer['instruments'] = execute_query(instruments_query, (performer_id,))
        
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
        performer['recordings'] = execute_query(recordings_query, (performer_id,))
        
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
        performer['images'] = execute_query(images_query, (performer_id,))
        
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

if __name__ == '__main__':
    # Don't initialize pool at startup - let it initialize on first request
    # This prevents deployment failures if DB is temporarily unavailable
    logger.info("Starting Flask application...")
    logger.info("Database connection pool will initialize on first request")
    
    # Start keepalive thread
    keepalive_thread = threading.Thread(target=connection_keepalive, daemon=True)
    keepalive_thread.start()
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5001)
    finally:
        # Stop keepalive thread
        logger.info("Stopping keepalive thread...")
        keepalive_stop.set()
        if keepalive_thread:
            keepalive_thread.join(timeout=5)
        
        # Close the connection pool on shutdown
        if pool:
            logger.info("Closing connection pool...")
            pool.close()
            logger.info("Connection pool closed")
