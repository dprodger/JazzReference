"""
Jazz Reference API Backend
A Flask API to serve jazz database content to the iOS app
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg
from psycopg.rows import dict_row
import os

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

def get_db_connection():
    """Create and return a database connection with better error handling"""
    try:
        return psycopg.connect(
            host=DB_CONFIG['host'],
            dbname=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            port=DB_CONFIG['port'],
            row_factory=dict_row,
            connect_timeout=10,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5
        )
    except psycopg.OperationalError as e:
        print(f"Database connection failed: {e}")
        raise
        
@app.route('/api/songs', methods=['GET'])
def get_songs():
    """Get all songs or search songs by title"""
    search_query = request.args.get('search', '')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    if search_query:
        cur.execute("""
            SELECT id, title, composer, structure, song_reference, external_references, 
                   created_at, updated_at
            FROM songs
            WHERE title ILIKE %s OR composer ILIKE %s
            ORDER BY title
        """, (f'%{search_query}%', f'%{search_query}%'))
    else:
        cur.execute("""
            SELECT id, title, composer, structure, song_reference, external_references,
                   created_at, updated_at
            FROM songs
            ORDER BY title
        """)
    
    songs = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(songs)

@app.route('/api/songs/<song_id>', methods=['GET'])
def get_song_detail(song_id):
    """Get detailed information about a specific song"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get song information
    cur.execute("""
        SELECT id, title, composer, structure, external_references,
               created_at, updated_at
        FROM songs
        WHERE id = %s
    """, (song_id,))
    
    song = cur.fetchone()
    
    if not song:
        cur.close()
        conn.close()
        return jsonify({'error': 'Song not found'}), 404
    
    # Get recordings for this song
    cur.execute("""
        SELECT r.id, r.album_title, r.recording_date, r.recording_year,
               r.label, r.spotify_url, r.youtube_url, r.apple_music_url,
               r.is_canonical, r.notes
        FROM recordings r
        WHERE r.song_id = %s
        ORDER BY r.is_canonical DESC, r.recording_year DESC
    """, (song_id,))
    
    recordings = cur.fetchall()
    
    # For each recording, fetch the performers
    for recording in recordings:
        cur.execute("""
            SELECT p.id, p.name, i.name as instrument, rp.role
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
        """, (recording['id'],))
        
        recording['performers'] = cur.fetchall()
    
    # Add recording count to song
    song = dict(song)
    song['recordings'] = recordings
    song['recording_count'] = len(recordings)
    
    cur.close()
    conn.close()
    
    return jsonify(song)
    
@app.route('/api/recordings/<recording_id>', methods=['GET'])
def get_recording_detail(recording_id):
    """Get detailed information about a specific recording"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get recording information
    cur.execute("""
        SELECT r.id, r.song_id, r.album_title, r.recording_date, 
               r.recording_year, r.label, r.spotify_url, r.youtube_url,
               r.apple_music_url, r.is_canonical, r.notes,
               s.title as song_title, s.composer
        FROM recordings r
        JOIN songs s ON r.song_id = s.id
        WHERE r.id = %s
    """, (recording_id,))
    
    recording = cur.fetchone()
    
    if not recording:
        cur.close()
        conn.close()
        return jsonify({'error': 'Recording not found'}), 404
    
    # Get performers for this recording
    cur.execute("""
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
    """, (recording_id,))
    
    performers = cur.fetchall()
    
    # Add performers to recording
    recording = dict(recording)
    recording['performers'] = performers
    
    cur.close()
    conn.close()
    
    return jsonify(recording)

@app.route('/api/performers', methods=['GET'])
def get_performers():
    """Get all performers"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, name, biography, birth_date, death_date, external_links
        FROM performers
        ORDER BY name
    """)
    
    performers = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(performers)

@app.route('/api/performers/<performer_id>', methods=['GET'])
def get_performer_detail(performer_id):
    """Get detailed information about a specific performer"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get performer information
    cur.execute("""
        SELECT id, name, biography, birth_date, death_date, external_links
        FROM performers
        WHERE id = %s
    """, (performer_id,))
    
    performer = cur.fetchone()
    
    if not performer:
        cur.close()
        conn.close()
        return jsonify({'error': 'Performer not found'}), 404
    
    # Get instruments
    cur.execute("""
        SELECT i.name, pi.is_primary
        FROM performer_instruments pi
        JOIN instruments i ON pi.instrument_id = i.id
        WHERE pi.performer_id = %s
        ORDER BY pi.is_primary DESC, i.name
    """, (performer_id,))
    
    instruments = cur.fetchall()
    
    # Get discography
    cur.execute("""
        SELECT DISTINCT s.id, s.title, r.id as recording_id, 
               r.album_title, r.recording_year, r.is_canonical
        FROM recording_performers rp
        JOIN recordings r ON rp.recording_id = r.id
        JOIN songs s ON r.song_id = s.id
        WHERE rp.performer_id = %s
        ORDER BY r.recording_year DESC, s.title
    """, (performer_id,))
    
    discography = cur.fetchall()
    
    performer = dict(performer)
    performer['instruments'] = instruments
    performer['discography'] = discography
    
    cur.close()
    conn.close()
    
    return jsonify(performer)

@app.route('/api/performers', methods=['GET'])
def get_performers():
    """Get all performers or search performers by name"""
    search_query = request.args.get('search', '')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    if search_query:
        cur.execute("""
            SELECT id, name, biography, birth_date, death_date, external_links
            FROM performers
            WHERE name ILIKE %s
            ORDER BY name
        """, (f'%{search_query}%',))
    else:
        cur.execute("""
            SELECT id, name, biography, birth_date, death_date, external_links
            FROM performers
            ORDER BY name
        """)
    
    performers = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(performers)

@app.route('/api/performers/<performer_id>', methods=['GET'])
def get_performer_detail(performer_id):
    """Get detailed information about a specific performer"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get performer information
    cur.execute("""
        SELECT id, name, biography, birth_date, death_date, external_links
        FROM performers
        WHERE id = %s
    """, (performer_id,))
    
    performer = cur.fetchone()
    
    if not performer:
        cur.close()
        conn.close()
        return jsonify({'error': 'Performer not found'}), 404
    
    # Get instruments
    cur.execute("""
        SELECT i.name, pi.is_primary
        FROM performer_instruments pi
        JOIN instruments i ON pi.instrument_id = i.id
        WHERE pi.performer_id = %s
        ORDER BY pi.is_primary DESC, i.name
    """, (performer_id,))
    
    instruments = cur.fetchall()
    
    # Get recordings where performer is a leader
    cur.execute("""
        SELECT DISTINCT s.id as song_id, s.title as song_title, 
               r.id as recording_id, r.album_title, r.recording_year, 
               r.is_canonical, rp.role
        FROM recording_performers rp
        JOIN recordings r ON rp.recording_id = r.id
        JOIN songs s ON r.song_id = s.id
        WHERE rp.performer_id = %s
        ORDER BY r.recording_year DESC NULLS LAST, s.title
    """, (performer_id,))
    
    recordings = cur.fetchall()
    
    performer = dict(performer)
    performer['instruments'] = instruments
    performer['recordings'] = recordings
    
    cur.close()
    conn.close()
    
    return jsonify(performer)
    
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        conn.close()
        return jsonify({'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)