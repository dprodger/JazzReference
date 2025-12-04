# routes/songs.py
"""
Song API Routes - Recording-Centric Performer Architecture

UPDATED: Recording-Centric Architecture
- Performers come from recording_performers table (not release_performers)
- Spotify URL and album art come from default_release or best release via subqueries
- Dropped columns (spotify_url, spotify_track_id, album_art_*) removed from recordings table

UPDATED: Release Imagery Support
- Album art now checks release_imagery table first (CAA images)
- Falls back to releases table (Spotify images) if no release_imagery exists

Provides endpoints for listing, searching, and creating songs.
"""
from flask import Blueprint, jsonify, request
import logging
import json
import db_utils as db_tools
from utils.helpers import safe_strip

logger = logging.getLogger(__name__)
songs_bp = Blueprint('songs', __name__)


# ============================================================================
# SQL FRAGMENTS FOR ALBUM ART (same as recordings.py)
# ============================================================================
# These fragments implement the priority: 
#   1. release_imagery (CAA) for default_release
#   2. releases table (Spotify) for default_release  
#   3. release_imagery (CAA) for any linked release
#   4. releases table (Spotify) for any linked release

ALBUM_ART_SMALL_SQL = """
    COALESCE(
        -- 1. release_imagery (Front) for default release
        (SELECT ri.image_url_small FROM release_imagery ri 
         WHERE ri.release_id = r.default_release_id AND ri.type = 'Front'),
        -- 2. releases table for default release
        (SELECT rel_sub.cover_art_small FROM releases rel_sub 
         WHERE rel_sub.id = r.default_release_id AND rel_sub.cover_art_small IS NOT NULL),
        -- 3. release_imagery (Front) for any linked release
        (SELECT ri.image_url_small 
         FROM recording_releases rr_sub 
         JOIN release_imagery ri ON rr_sub.release_id = ri.release_id
         WHERE rr_sub.recording_id = r.id AND ri.type = 'Front'
         LIMIT 1),
        -- 4. releases table for any linked release
        (SELECT rel_sub.cover_art_small 
         FROM recording_releases rr_sub 
         JOIN releases rel_sub ON rr_sub.release_id = rel_sub.id
         WHERE rr_sub.recording_id = r.id AND rel_sub.cover_art_small IS NOT NULL
         ORDER BY rel_sub.release_year DESC NULLS LAST LIMIT 1)
    ) as best_cover_art_small"""

ALBUM_ART_MEDIUM_SQL = """
    COALESCE(
        (SELECT ri.image_url_medium FROM release_imagery ri 
         WHERE ri.release_id = r.default_release_id AND ri.type = 'Front'),
        (SELECT rel_sub.cover_art_medium FROM releases rel_sub 
         WHERE rel_sub.id = r.default_release_id AND rel_sub.cover_art_medium IS NOT NULL),
        (SELECT ri.image_url_medium 
         FROM recording_releases rr_sub 
         JOIN release_imagery ri ON rr_sub.release_id = ri.release_id
         WHERE rr_sub.recording_id = r.id AND ri.type = 'Front'
         LIMIT 1),
        (SELECT rel_sub.cover_art_medium 
         FROM recording_releases rr_sub 
         JOIN releases rel_sub ON rr_sub.release_id = rel_sub.id
         WHERE rr_sub.recording_id = r.id AND rel_sub.cover_art_medium IS NOT NULL
         ORDER BY rel_sub.release_year DESC NULLS LAST LIMIT 1)
    ) as best_cover_art_medium"""

ALBUM_ART_LARGE_SQL = """
    COALESCE(
        (SELECT ri.image_url_large FROM release_imagery ri 
         WHERE ri.release_id = r.default_release_id AND ri.type = 'Front'),
        (SELECT rel_sub.cover_art_large FROM releases rel_sub 
         WHERE rel_sub.id = r.default_release_id AND rel_sub.cover_art_large IS NOT NULL),
        (SELECT ri.image_url_large 
         FROM recording_releases rr_sub 
         JOIN release_imagery ri ON rr_sub.release_id = ri.release_id
         WHERE rr_sub.recording_id = r.id AND ri.type = 'Front'
         LIMIT 1),
        (SELECT rel_sub.cover_art_large 
         FROM recording_releases rr_sub 
         JOIN releases rel_sub ON rr_sub.release_id = rel_sub.id
         WHERE rr_sub.recording_id = r.id AND rel_sub.cover_art_large IS NOT NULL
         ORDER BY rel_sub.release_year DESC NULLS LAST LIMIT 1)
    ) as best_cover_art_large"""

# For authority recommendations - uses 'r' alias for recordings
AUTHORITY_ALBUM_ART_SQL = """
    COALESCE(
        (SELECT ri.image_url_large FROM release_imagery ri 
         WHERE ri.release_id = r.default_release_id AND ri.type = 'Front'),
        (SELECT rel.cover_art_large FROM releases rel 
         WHERE rel.id = r.default_release_id AND rel.cover_art_large IS NOT NULL),
        (SELECT ri.image_url_large 
         FROM recording_releases rr
         JOIN release_imagery ri ON rr.release_id = ri.release_id
         WHERE rr.recording_id = r.id AND ri.type = 'Front'
         LIMIT 1),
        (SELECT rel.cover_art_large 
         FROM recording_releases rr
         JOIN releases rel ON rr.release_id = rel.id
         WHERE rr.recording_id = r.id AND rel.cover_art_large IS NOT NULL
         ORDER BY rel.release_year DESC NULLS LAST
         LIMIT 1)
    ) as matched_album_art"""


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
    
    UPDATED: Recording-Centric Architecture
    - Removed dropped columns (spotify_url, spotify_track_id, album_art_*) from recordings
    - Spotify/artwork data now comes entirely from releases via subqueries
    - Performers come from recording_performers table
    
    UPDATED: Release Imagery Support
    - Album art checks release_imagery table first (CAA images)
    - Falls back to releases table (Spotify images) if no release_imagery exists
    
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
                    ORDER BY p2.name
                    LIMIT 1
                ) ASC NULLS LAST,
                r.recording_year ASC NULLS LAST
            """
        else:  # 'year' - default
            # Sort by recording year, oldest first
            recordings_order = "r.recording_year ASC NULLS LAST"
        
        # ONE QUERY to get everything - song, recordings+performers+authority, transcriptions
        # UPDATED: Album art now uses release_imagery priority
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
                    r.default_release_id,
                    -- Spotify URL from default release or best available
                    COALESCE(
                        (SELECT COALESCE(rr_sub.spotify_track_url, rel_sub.spotify_album_url)
                         FROM releases rel_sub
                         LEFT JOIN recording_releases rr_sub ON rr_sub.release_id = rel_sub.id AND rr_sub.recording_id = r.id
                         WHERE rel_sub.id = r.default_release_id
                           AND (rel_sub.spotify_album_url IS NOT NULL OR rr_sub.spotify_track_url IS NOT NULL)
                        ),
                        (SELECT COALESCE(rr_sub.spotify_track_url, rel_sub.spotify_album_url)
                         FROM recording_releases rr_sub
                         JOIN releases rel_sub ON rr_sub.release_id = rel_sub.id
                         WHERE rr_sub.recording_id = r.id 
                           AND (rr_sub.spotify_track_url IS NOT NULL OR rel_sub.spotify_album_url IS NOT NULL)
                         ORDER BY 
                           CASE WHEN rr_sub.spotify_track_url IS NOT NULL THEN 0 ELSE 1 END,
                           rel_sub.release_year DESC NULLS LAST
                         LIMIT 1)
                    ) as best_spotify_url,
                    -- Album art with release_imagery priority
                    {ALBUM_ART_SMALL_SQL},
                    {ALBUM_ART_MEDIUM_SQL},
                    {ALBUM_ART_LARGE_SQL},
                    r.youtube_url,
                    r.apple_music_url,
                    r.musicbrainz_id,
                    r.is_canonical,
                    r.notes,
                    -- Performers aggregation from recording_performers
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
                         r.label, r.default_release_id,
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
# 2. RECORDINGS CTE - Recording-Centric Architecture Updates
#    - REMOVED: r.spotify_url, r.spotify_track_id, r.album_art_small/medium/large (dropped columns)
#    - ADDED: r.default_release_id to GROUP BY
#    - Spotify URL comes from best_spotify_url subquery (default release or best available)
#    - Cover art comes from best_cover_art_* subqueries with release_imagery priority
#    - Performers still from recording_performers (unchanged)
#
# 3. ORDER BY - Made dynamic based on sort parameter
#    - Default 'year' sorts by recording year
#    - 'name' sorts by leader's last name
#
# 4. RELEASE IMAGERY - Added priority for CAA images
#    - Checks release_imagery table first (type='Front')
#    - Falls back to releases table (Spotify images)


@songs_bp.route('/api/songs', methods=['POST'])
def create_song():
    """Create a new song"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        title = safe_strip(data.get('title'))
        composer = safe_strip(data.get('composer'))
        structure = safe_strip(data.get('structure'))
        song_reference = safe_strip(data.get('song_reference'))
        musicbrainz_id = safe_strip(data.get('musicbrainz_id'))
        wikipedia_url = safe_strip(data.get('wikipedia_url'))
        external_references = data.get('external_references')
        
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        
        # Build dynamic INSERT
        fields = ['title']
        values = [title]
        placeholders = ['%s']
        
        if composer:
            fields.append('composer')
            values.append(composer)
            placeholders.append('%s')
        
        if structure:
            fields.append('structure')
            values.append(structure)
            placeholders.append('%s')
        
        if song_reference:
            fields.append('song_reference')
            values.append(song_reference)
            placeholders.append('%s')
        
        if musicbrainz_id:
            fields.append('musicbrainz_id')
            values.append(musicbrainz_id)
            placeholders.append('%s')
        
        if wikipedia_url:
            fields.append('wikipedia_url')
            values.append(wikipedia_url)
            placeholders.append('%s')
        
        if external_references:
            fields.append('external_references')
            if isinstance(external_references, dict):
                values.append(json.dumps(external_references))
            else:
                values.append(external_references)
            placeholders.append('%s')
        
        query = f"""
            INSERT INTO songs ({', '.join(fields)})
            VALUES ({', '.join(placeholders)})
            RETURNING id, title, composer, structure, musicbrainz_id, wikipedia_url, 
                      song_reference, external_references, created_at, updated_at
        """
        
        result = db_tools.execute_query(query, values, fetch_one=True)
        
        logger.info(f"Created new song: {title} (ID: {result['id']})")
        
        return jsonify({
            'success': True,
            'message': 'Song created successfully',
            'song': result
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating song: {e}")
        return jsonify({'error': 'Failed to create song', 'detail': str(e)}), 500


@songs_bp.route('/api/songs/search', methods=['GET'])
def search_songs():
    """Search songs by title and optionally composer - returns first 20 matches"""
    search_query = request.args.get('q', '').strip()
    
    if not search_query:
        return jsonify([])
    
    try:
        query = """
            SELECT id, title, composer, musicbrainz_id
            FROM songs
            WHERE title ILIKE %s OR composer ILIKE %s
            ORDER BY 
                CASE WHEN title ILIKE %s THEN 0 ELSE 1 END,
                title
            LIMIT 20
        """
        params = (
            f'%{search_query}%', 
            f'%{search_query}%',
            f'{search_query}%'  # Exact prefix match ranked higher
        )
        
        songs = db_tools.execute_query(query, params)
        return jsonify(songs if songs else [])
        
    except Exception as e:
        logger.error(f"Error searching songs: {e}")
        return jsonify({'error': 'Search failed', 'detail': str(e)}), 500


# ============================================================================
# 2. UPDATE ENDPOINT: PATCH /api/songs/<song_id>
# ============================================================================

@songs_bp.route('/api/songs/<song_id>', methods=['PATCH'])
def update_song(song_id):
    """
    Update a song's MusicBrainz ID and/or Wikipedia URL
    
    This is a targeted update endpoint primarily for iOS app to set
    identifiers after manual research.
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        musicbrainz_id = safe_strip(data.get('musicbrainz_id'))
        wikipedia_url = safe_strip(data.get('wikipedia_url'))
        
        if not musicbrainz_id and not wikipedia_url:
            return jsonify({'error': 'At least one field (musicbrainz_id or wikipedia_url) must be provided'}), 400
        
        with db_tools.get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check song exists
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
    """
    Get all authority recommendations for a song (matched and unmatched)
    
    UPDATED: Recording-Centric Architecture
    - Spotify URL and album art now come from releases via subqueries
    - Dropped columns no longer exist on recordings table
    
    UPDATED: Release Imagery Support
    - Album art checks release_imagery table first (CAA images)
    - Falls back to releases table (Spotify images)
    """
    try:
        with db_tools.get_db_connection() as conn:
            with conn.cursor() as cur:
                # Verify song exists
                cur.execute("SELECT id FROM songs WHERE id = %s", (song_id,))
                if not cur.fetchone():
                    return jsonify({'error': 'Song not found'}), 404
                
                # Get all recommendations with optional recording details
                # UPDATED: Spotify URL and album art from releases with release_imagery priority
                cur.execute(f"""
                    SELECT sar.id, sar.source, sar.recommendation_text, sar.source_url,
                           sar.artist_name, sar.album_title, sar.recording_year,
                           sar.itunes_album_id, sar.itunes_track_id,
                           sar.recording_id,
                           r.album_title as matched_album_title,
                           r.recording_year as matched_year,
                           -- Get Spotify URL from default release or best available
                           COALESCE(
                               (SELECT COALESCE(rr.spotify_track_url, rel.spotify_album_url)
                                FROM releases rel
                                LEFT JOIN recording_releases rr ON rr.release_id = rel.id AND rr.recording_id = r.id
                                WHERE rel.id = r.default_release_id
                                  AND (rel.spotify_album_url IS NOT NULL OR rr.spotify_track_url IS NOT NULL)
                               ),
                               (SELECT COALESCE(rr.spotify_track_url, rel.spotify_album_url)
                                FROM recording_releases rr
                                JOIN releases rel ON rr.release_id = rel.id
                                WHERE rr.recording_id = r.id 
                                  AND (rr.spotify_track_url IS NOT NULL OR rel.spotify_album_url IS NOT NULL)
                                ORDER BY 
                                  CASE WHEN rr.spotify_track_url IS NOT NULL THEN 0 ELSE 1 END,
                                  rel.release_year DESC NULLS LAST
                                LIMIT 1)
                           ) as matched_spotify_url,
                           -- Album art with release_imagery priority
                           {AUTHORITY_ALBUM_ART_SQL}
                    FROM song_authority_recommendations sar
                    LEFT JOIN recordings r ON sar.recording_id = r.id
                    WHERE sar.song_id = %s
                    ORDER BY 
                        CASE WHEN sar.recording_id IS NOT NULL THEN 0 ELSE 1 END,
                        sar.source,
                        sar.artist_name
                """, (song_id,))
                
                recommendations = cur.fetchall()
                
                return jsonify({
                    'song_id': song_id,
                    'recommendations': recommendations,
                    'total_count': len(recommendations),
                    'matched_count': sum(1 for r in recommendations if r['recording_id']),
                    'unmatched_count': sum(1 for r in recommendations if not r['recording_id'])
                })
                
    except Exception as e:
        logger.error(f"Error fetching authority recommendations: {e}")
        return jsonify({'error': 'Failed to fetch recommendations', 'detail': str(e)}), 500


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