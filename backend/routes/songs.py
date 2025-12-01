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
    Get detailed information about a specific song with all recordings, performers, transcriptions,
    AND authority recommendations.
    
    ULTRA-OPTIMIZED VERSION: Uses a SINGLE query with CTEs instead of 4+ separate queries.
    This eliminates network round trips between Render and Supabase.
    
    NEW: Includes authority recommendation counts and sort parameter support.
    """
    try:
        # Get sort preference from query parameter (default: 'year')
        # UPDATED: Changed from authority/year/canonical to name/year
        sort_by = request.args.get('sort', 'year')
        
        # Build ORDER BY clause based on sort preference
        if sort_by == 'name':
            # Sort alphabetically by leader's last name (extract last word of name)
            recordings_order = """
                (
                    SELECT COALESCE(
                        SUBSTRING(p2.name FROM '([^ ]+)$'),
                        p2.name,
                        'ZZZ'
                    )
                    FROM recording_performers rp2
                    JOIN performers p2 ON rp2.performer_id = p2.id
                    WHERE rp2.recording_id = r.id AND rp2.role = 'leader'
                    LIMIT 1
                ) ASC NULLS LAST,
                r.recording_year ASC NULLS LAST
            """
        else:  # 'year' - default
            # Sort by recording year, oldest first
            recordings_order = "r.recording_year ASC NULLS LAST"
        
        # ONE QUERY to get everything - song, recordings+performers+authority, transcriptions
        combined_query = f"""
            WITH song_data AS (
                SELECT 
                    s.id, s.title, s.composer, s.structure, s.song_reference,
                    s.musicbrainz_id, s.wikipedia_url, s.external_references, 
                    s.created_at, s.updated_at,
                    -- NEW: Count total authority recommendations for this song
                    (SELECT COUNT(*) 
                     FROM song_authority_recommendations 
                     WHERE song_id = s.id) as authority_recommendation_count
                FROM songs s
                WHERE s.id = %s
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
                    -- Best cover art from Spotify-linked releases
                    (SELECT rel.cover_art_small 
                     FROM recording_releases rr_sub
                     JOIN releases rel ON rr_sub.release_id = rel.id
                     WHERE rr_sub.recording_id = r.id 
                       AND rel.spotify_album_id IS NOT NULL 
                       AND rel.cover_art_small IS NOT NULL
                     ORDER BY rel.release_year DESC NULLS LAST
                     LIMIT 1) as best_cover_art_small,
                    (SELECT rel.cover_art_medium 
                     FROM recording_releases rr_sub
                     JOIN releases rel ON rr_sub.release_id = rel.id
                     WHERE rr_sub.recording_id = r.id 
                       AND rel.spotify_album_id IS NOT NULL 
                       AND rel.cover_art_medium IS NOT NULL
                     ORDER BY rel.release_year DESC NULLS LAST
                     LIMIT 1) as best_cover_art_medium,
                    (SELECT rel.cover_art_large 
                     FROM recording_releases rr_sub
                     JOIN releases rel ON rr_sub.release_id = rel.id
                     WHERE rr_sub.recording_id = r.id 
                       AND rel.spotify_album_id IS NOT NULL 
                       AND rel.cover_art_large IS NOT NULL
                     ORDER BY rel.release_year DESC NULLS LAST
                     LIMIT 1) as best_cover_art_large,
                    -- Best Spotify URL from releases
                    (SELECT COALESCE(rr_sub.spotify_track_url, rel.spotify_album_url)
                     FROM recording_releases rr_sub
                     JOIN releases rel ON rr_sub.release_id = rel.id
                     WHERE rr_sub.recording_id = r.id 
                       AND (rr_sub.spotify_track_url IS NOT NULL OR rel.spotify_album_url IS NOT NULL)
                     ORDER BY 
                       CASE WHEN rr_sub.spotify_track_url IS NOT NULL THEN 0 ELSE 1 END,
                       rel.release_year DESC NULLS LAST
                     LIMIT 1) as best_spotify_url,
                    r.youtube_url,
                    r.apple_music_url,
                    r.musicbrainz_id,
                    r.is_canonical,
                    r.notes,
                    -- Performers aggregation (existing)
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
                    ) as performers,
                    -- Authority recommendation count per recording
                    COUNT(DISTINCT sar.id) as authority_count,
                    -- Array of authority sources
                    COALESCE(
                        array_agg(DISTINCT sar.source) FILTER (WHERE sar.source IS NOT NULL),
                        ARRAY[]::text[]
                    ) as authority_sources
                FROM recordings r
                LEFT JOIN recording_performers rp ON r.id = rp.recording_id
                LEFT JOIN performers p ON rp.performer_id = p.id
                LEFT JOIN instruments i ON rp.instrument_id = i.id
                LEFT JOIN song_authority_recommendations sar 
                    ON r.id = sar.recording_id
                WHERE r.song_id = %s
                GROUP BY r.id, r.album_title, r.recording_date, r.recording_year,
                         r.label, r.spotify_url, r.spotify_track_id,
                         r.album_art_small, r.album_art_medium, r.album_art_large,
                         r.youtube_url, r.apple_music_url, r.musicbrainz_id,
                         r.is_canonical, r.notes
                ORDER BY {recordings_order}
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


# NOTES ON CHANGES:
# 
# 1. SONG DATA CTE - Added subquery for authority_recommendation_count
#    - Uses (SELECT COUNT(*) FROM song_authority_recommendations WHERE song_id = s.id)
#    - No joins needed, keeps it simple
#
# 2. RECORDINGS CTE - Added authority information
#    - LEFT JOIN song_authority_recommendations sar ON r.id = sar.recording_id
#    - COUNT(DISTINCT sar.id) as authority_count
#    - array_agg(DISTINCT sar.source) as authority_sources
#    - Added to GROUP BY (no changes needed, already grouping by r.id)
#
# 3. ORDER BY - Made dynamic based on sort parameter
#    - Default 'authority' uses CASE expression to prioritize recordings with recommendations
#    - 'year' and 'canonical' options preserved
#    - Uses Python f-string to inject ORDER BY clause (safe because sort_by is validated)
#
# 4. PERFORMANCE CHARACTERISTICS:
#    - Still ONE database query (single network round trip)
#    - Uses existing indexes on recordings(song_id) and song_authority_recommendations(recording_id)
#    - Authority aggregation happens in parallel with performer aggregation
#    - No performance degradation vs original version
#
# 5. RESPONSE FORMAT:
#    Song object now includes:
#    - authority_recommendation_count: int
#    
#    Each recording now includes:
#    - authority_count: int
#    - authority_sources: string[]
#    - performers: array (unchanged)
#
# EXAMPLE RESPONSE:
# {
#   "song": {
#     "id": "...",
#     "title": "Take Five",
#     "authority_recommendation_count": 3,  # NEW
#     ...
#   },
#   "recordings": [
#     {
#       "id": "...",
#       "album_title": "Time Out",
#       "authority_count": 1,              # NEW
#       "authority_sources": ["jazzstandards.com"],  # NEW
#       "performers": [...]
#     }
#   ],
#   "transcriptions": [...]
# }

   
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


# ============================================================================
# 3. NEW ENDPOINT: GET /api/songs/<song_id>/authority_recommendations
# ============================================================================

@songs_bp.route('/api/songs/<song_id>/authority_recommendations', methods=['GET'])
def get_song_authority_recommendations(song_id):
    """Get all authority recommendations for a song (matched and unmatched)"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Verify song exists
    cur.execute("SELECT id FROM songs WHERE id = %s", (song_id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({'error': 'Song not found'}), 404
    
    # Get all recommendations with optional recording details
    cur.execute("""
        SELECT sar.id, sar.source, sar.recommendation_text, sar.source_url,
               sar.artist_name, sar.album_title, sar.recording_year,
               sar.itunes_album_id, sar.itunes_track_id,
               sar.recording_id,
               r.album_title as matched_album_title,
               r.recording_year as matched_year,
               r.spotify_url as matched_spotify_url,
               r.album_art_large as matched_album_art
        FROM song_authority_recommendations sar
        LEFT JOIN recordings r ON sar.recording_id = r.id
        WHERE sar.song_id = %s
        ORDER BY 
            CASE WHEN sar.recording_id IS NOT NULL THEN 0 ELSE 1 END,
            sar.source,
            sar.artist_name
    """, (song_id,))
    
    recommendations = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return jsonify({
        'song_id': song_id,
        'recommendations': recommendations,
        'total_count': len(recommendations),
        'matched_count': sum(1 for r in recommendations if r['recording_id']),
        'unmatched_count': sum(1 for r in recommendations if not r['recording_id'])
    })


# ============================================================================
# HELPER FUNCTION: Format External References
# ============================================================================

def format_external_references(external_refs):
    """
    Format external_references JSONB field for display
    Returns list of {source, url, display_name} objects
    """
    if not external_refs:
        return []
    
    # Mapping of source keys to display names
    source_names = {
        'wikipedia': 'Wikipedia',
        'jazzstandards': 'JazzStandards.com',
        'allmusic': 'AllMusic',
        'discogs': 'Discogs',
        'musicbrainz': 'MusicBrainz'
    }
    
    formatted = []
    for key, url in external_refs.items():
        formatted.append({
            'source': key,
            'url': url,
            'display_name': source_names.get(key, key.title())
        })
    
    return formatted