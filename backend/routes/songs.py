# routes/songs.py
from flask import Blueprint, jsonify, request
import logging
import db_utils as db_tools
from utils.helpers import safe_strip

logger = logging.getLogger(__name__)
songs_bp = Blueprint('songs', __name__)

# All song-related endpoints:
# - GET /api/songs
# - POST /api/songs
# - GET /api/songs/<song_id>
# - GET /api/songs/search


@songs_bp.route('/api/songs', methods=['GET'])
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



@songs_bp.route('/api/songs/<song_id>', methods=['GET'])
def get_song_detail(song_id):
    """
    Get detailed information about a specific song with all recordings, performers, and transcriptions.
    
    ULTRA-OPTIMIZED VERSION: Uses a SINGLE query with CTEs instead of 3 separate queries.
    This eliminates 2 network round trips between Render and Supabase.
    """
    try:
        # ONE QUERY to get everything - song, recordings+performers, transcriptions
        combined_query = """
            WITH song_data AS (
                SELECT 
                    id, title, composer, structure, song_reference,
                    musicbrainz_id, wikipedia_url, external_references, 
                    created_at, updated_at
                FROM songs
                WHERE id = %s
            ),
            recordings_with_performers AS (
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
                         r.youtube_url, r.apple_music_url, r.musicbrainz_id,
                         r.is_canonical, r.notes
                ORDER BY r.is_canonical DESC, r.recording_year DESC
            ),
            transcriptions_data AS (
                SELECT 
                    st.id,
                    st.song_id,
                    st.recording_id,
                    st.youtube_url,
                    st.created_at,
                    st.updated_at,
                    r.album_title,
                    r.recording_year
                FROM solo_transcriptions st
                LEFT JOIN recordings r ON st.recording_id = r.id
                WHERE st.song_id = %s
                ORDER BY r.recording_year DESC
            )
            SELECT 
                (SELECT row_to_json(song_data.*) FROM song_data) as song,
                (SELECT json_agg(recordings_with_performers.*) FROM recordings_with_performers) as recordings,
                (SELECT json_agg(transcriptions_data.*) FROM transcriptions_data) as transcriptions
        """
        
        # Execute the single query with song_id passed 3 times (for each CTE)
        result = db_tools.execute_query(combined_query, (song_id, song_id, song_id), fetch_one=True)
        
        if not result or not result['song']:
            return jsonify({'error': 'Song not found'}), 404
        
        # Build response from the single query result
        song_dict = result['song']
        recordings = result['recordings'] if result['recordings'] else []
        transcriptions = result['transcriptions'] if result['transcriptions'] else []
        
        song_dict['recordings'] = recordings
        song_dict['recording_count'] = len(recordings)
        song_dict['transcriptions'] = transcriptions
        song_dict['transcription_count'] = len(transcriptions)
        
        return jsonify(song_dict)
        
    except Exception as e:
        logger.error(f"Error fetching song detail: {e}")
        return jsonify({'error': 'Failed to fetch song details', 'detail': str(e)}), 500



   
@songs_bp.route('/api/songs/search', methods=['GET'])
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


@songs_bp.route('/api/songs', methods=['POST'])
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


@songs_bp.route('/api/songs/<song_id>', methods=['PATCH'])
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

