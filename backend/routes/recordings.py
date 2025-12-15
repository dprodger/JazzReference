# routes/recordings.py
"""
Recording API Routes - Recording-Centric Performer Architecture

UPDATED: Recording-Centric Architecture
- Performers come from recording_performers table (not release_performers)
- Spotify URL and album art come from default_release or best release
- Album title now comes from default release (releases.title via default_release_id)
- release_performers is now for release-specific credits (producers, engineers)

UPDATED: Release Imagery Support
- Album art now checks release_imagery table first (CAA images)
- Falls back to releases table (Spotify images) if no release_imagery exists

Provides endpoints for listing and searching recordings, including releases.
"""
from flask import Blueprint, jsonify, request
import logging
import db_utils as db_tools

logger = logging.getLogger(__name__)
recordings_bp = Blueprint('recordings', __name__)


# ============================================================================
# SQL FRAGMENTS FOR ALBUM ART
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
        (SELECT rel.cover_art_small FROM releases rel 
         WHERE rel.id = r.default_release_id AND rel.cover_art_small IS NOT NULL),
        -- 3. release_imagery (Front) for any linked release
        (SELECT ri.image_url_small 
         FROM recording_releases rr 
         JOIN release_imagery ri ON rr.release_id = ri.release_id
         WHERE rr.recording_id = r.id AND ri.type = 'Front'
         LIMIT 1),
        -- 4. releases table for any linked release
        (SELECT rel.cover_art_small 
         FROM recording_releases rr 
         JOIN releases rel ON rr.release_id = rel.id
         WHERE rr.recording_id = r.id AND rel.cover_art_small IS NOT NULL
         ORDER BY rel.release_year DESC NULLS LAST LIMIT 1)
    ) as album_art_small"""

ALBUM_ART_MEDIUM_SQL = """
    COALESCE(
        (SELECT ri.image_url_medium FROM release_imagery ri 
         WHERE ri.release_id = r.default_release_id AND ri.type = 'Front'),
        (SELECT rel.cover_art_medium FROM releases rel 
         WHERE rel.id = r.default_release_id AND rel.cover_art_medium IS NOT NULL),
        (SELECT ri.image_url_medium 
         FROM recording_releases rr 
         JOIN release_imagery ri ON rr.release_id = ri.release_id
         WHERE rr.recording_id = r.id AND ri.type = 'Front'
         LIMIT 1),
        (SELECT rel.cover_art_medium 
         FROM recording_releases rr 
         JOIN releases rel ON rr.release_id = rel.id
         WHERE rr.recording_id = r.id AND rel.cover_art_medium IS NOT NULL
         ORDER BY rel.release_year DESC NULLS LAST LIMIT 1)
    ) as album_art_medium"""

ALBUM_ART_LARGE_SQL = """
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
         ORDER BY rel.release_year DESC NULLS LAST LIMIT 1)
    ) as album_art_large"""

# ============================================================================
# SQL FRAGMENTS FOR BACK COVER ART
# ============================================================================
# Back covers only come from release_imagery (CAA) - no Spotify fallback
# Priority: default_release first, then any linked release

BACK_COVER_SMALL_SQL = """
    COALESCE(
        (SELECT ri.image_url_small FROM release_imagery ri
         WHERE ri.release_id = r.default_release_id AND ri.type = 'Back'),
        (SELECT ri.image_url_small
         FROM recording_releases rr
         JOIN release_imagery ri ON rr.release_id = ri.release_id
         WHERE rr.recording_id = r.id AND ri.type = 'Back'
         LIMIT 1)
    ) as back_cover_art_small"""

BACK_COVER_MEDIUM_SQL = """
    COALESCE(
        (SELECT ri.image_url_medium FROM release_imagery ri
         WHERE ri.release_id = r.default_release_id AND ri.type = 'Back'),
        (SELECT ri.image_url_medium
         FROM recording_releases rr
         JOIN release_imagery ri ON rr.release_id = ri.release_id
         WHERE rr.recording_id = r.id AND ri.type = 'Back'
         LIMIT 1)
    ) as back_cover_art_medium"""

BACK_COVER_LARGE_SQL = """
    COALESCE(
        (SELECT ri.image_url_large FROM release_imagery ri
         WHERE ri.release_id = r.default_release_id AND ri.type = 'Back'),
        (SELECT ri.image_url_large
         FROM recording_releases rr
         JOIN release_imagery ri ON rr.release_id = ri.release_id
         WHERE rr.recording_id = r.id AND ri.type = 'Back'
         LIMIT 1)
    ) as back_cover_art_large"""

HAS_BACK_COVER_SQL = """
    EXISTS(
        SELECT 1 FROM release_imagery ri
        WHERE ri.release_id = r.default_release_id AND ri.type = 'Back'
    ) OR EXISTS(
        SELECT 1 FROM recording_releases rr
        JOIN release_imagery ri ON rr.release_id = ri.release_id
        WHERE rr.recording_id = r.id AND ri.type = 'Back'
    ) as has_back_cover"""

# For release-level queries (get_recording_releases), we check imagery for specific release
RELEASE_ART_SMALL_SQL = """
    COALESCE(
        (SELECT ri.image_url_small FROM release_imagery ri 
         WHERE ri.release_id = rel.id AND ri.type = 'Front'),
        rel.cover_art_small
    ) as cover_art_small"""

RELEASE_ART_MEDIUM_SQL = """
    COALESCE(
        (SELECT ri.image_url_medium FROM release_imagery ri 
         WHERE ri.release_id = rel.id AND ri.type = 'Front'),
        rel.cover_art_medium
    ) as cover_art_medium"""

RELEASE_ART_LARGE_SQL = """
    COALESCE(
        (SELECT ri.image_url_large FROM release_imagery ri
         WHERE ri.release_id = rel.id AND ri.type = 'Front'),
        rel.cover_art_large
    ) as cover_art_large"""

# ============================================================================
# SQL FRAGMENTS FOR SPOTIFY URL CONSTRUCTION (from IDs)
# ============================================================================
# Spotify URLs are deterministic: https://open.spotify.com/{type}/{id}
# We store only IDs and construct URLs on-demand

SPOTIFY_URL_SQL = """
    COALESCE(
        -- 1. From default release (track preferred, then album)
        (SELECT CASE
             WHEN rr.spotify_track_id IS NOT NULL THEN 'https://open.spotify.com/track/' || rr.spotify_track_id
             WHEN rel.spotify_album_id IS NOT NULL THEN 'https://open.spotify.com/album/' || rel.spotify_album_id
         END
         FROM releases rel
         LEFT JOIN recording_releases rr ON rr.release_id = rel.id AND rr.recording_id = r.id
         WHERE rel.id = r.default_release_id
           AND (rel.spotify_album_id IS NOT NULL OR rr.spotify_track_id IS NOT NULL)
        ),
        -- 2. From any linked release (track preferred, then album)
        (SELECT CASE
             WHEN rr.spotify_track_id IS NOT NULL THEN 'https://open.spotify.com/track/' || rr.spotify_track_id
             WHEN rel.spotify_album_id IS NOT NULL THEN 'https://open.spotify.com/album/' || rel.spotify_album_id
         END
         FROM recording_releases rr
         JOIN releases rel ON rr.release_id = rel.id
         WHERE rr.recording_id = r.id
           AND (rr.spotify_track_id IS NOT NULL OR rel.spotify_album_id IS NOT NULL)
         ORDER BY
           CASE WHEN rr.spotify_track_id IS NOT NULL THEN 0 ELSE 1 END,
           rel.release_year DESC NULLS LAST
         LIMIT 1)
    ) as best_spotify_url"""


@recordings_bp.route('/recordings/count', methods=['GET'])
def get_recordings_count():
    """
    Get total count of recordings (lightweight endpoint for UI display)

    Returns:
        JSON with count field
    """
    try:
        result = db_tools.execute_query("SELECT COUNT(*) as count FROM recordings")
        return jsonify({"count": result[0]['count'] if result else 0})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@recordings_bp.route('/recordings', methods=['GET'])
def get_recordings():
    """
    Get all recordings with optional search

    Query Parameters:
        search: Search query to filter recordings by album title, artist name, or song title
        limit: Maximum number of results (default: 100, max: 500)

    Returns:
        List of recordings with basic info including performers
    """
    search_query = request.args.get('search', '').strip()
    limit = min(int(request.args.get('limit', 100)), 500)
    
    try:
        if search_query:
            # Search across album title (from default release), performer names, and song title
            query = f"""
                SELECT DISTINCT ON (r.id)
                    r.id,
                    r.song_id,
                    def_rel.title as album_title,
                    r.recording_date,
                    r.recording_year,
                    r.label,
                    r.default_release_id,
                    -- Get Spotify URL from default release or best available (constructed from IDs)
                    COALESCE(
                        (SELECT CASE WHEN rr.spotify_track_id IS NOT NULL
                                     THEN 'https://open.spotify.com/track/' || rr.spotify_track_id
                                     WHEN rel.spotify_album_id IS NOT NULL
                                     THEN 'https://open.spotify.com/album/' || rel.spotify_album_id END
                         FROM releases rel
                         LEFT JOIN recording_releases rr ON rr.release_id = rel.id AND rr.recording_id = r.id
                         WHERE rel.id = r.default_release_id
                           AND (rel.spotify_album_id IS NOT NULL OR rr.spotify_track_id IS NOT NULL)
                        ),
                        (SELECT CASE WHEN rr.spotify_track_id IS NOT NULL
                                     THEN 'https://open.spotify.com/track/' || rr.spotify_track_id
                                     WHEN rel.spotify_album_id IS NOT NULL
                                     THEN 'https://open.spotify.com/album/' || rel.spotify_album_id END
                         FROM recording_releases rr
                         JOIN releases rel ON rr.release_id = rel.id
                         WHERE rr.recording_id = r.id
                           AND (rr.spotify_track_id IS NOT NULL OR rel.spotify_album_id IS NOT NULL)
                         ORDER BY
                           CASE WHEN rr.spotify_track_id IS NOT NULL THEN 0 ELSE 1 END,
                           rel.release_year DESC NULLS LAST
                         LIMIT 1)
                    ) as spotify_url,
                    -- Album art with release_imagery priority
                    {ALBUM_ART_SMALL_SQL},
                    {ALBUM_ART_MEDIUM_SQL},
                    {ALBUM_ART_LARGE_SQL},
                    -- Back cover art (CAA only)
                    {BACK_COVER_SMALL_SQL},
                    {BACK_COVER_MEDIUM_SQL},
                    {BACK_COVER_LARGE_SQL},
                    {HAS_BACK_COVER_SQL},
                    r.youtube_url,
                    r.apple_music_url,
                    r.musicbrainz_id,
                    r.is_canonical,
                    r.notes,
                    s.title as song_title,
                    s.composer
                FROM recordings r
                JOIN songs s ON r.song_id = s.id
                LEFT JOIN releases def_rel ON r.default_release_id = def_rel.id
                LEFT JOIN recording_performers rp ON r.id = rp.recording_id
                LEFT JOIN performers p ON rp.performer_id = p.id
                WHERE (
                    def_rel.title ILIKE %s OR
                    p.name ILIKE %s OR
                    s.title ILIKE %s
                )
                ORDER BY r.id, r.recording_year DESC NULLS LAST
                LIMIT %s
            """
            search_pattern = f'%{search_query}%'
            recordings = db_tools.execute_query(
                query,
                (search_pattern, search_pattern, search_pattern, limit)
            )
        else:
            query = f"""
                SELECT
                    r.id,
                    r.song_id,
                    def_rel.title as album_title,
                    r.recording_date,
                    r.recording_year,
                    r.label,
                    r.default_release_id,
                    -- Get Spotify URL from default release or best available (constructed from IDs)
                    COALESCE(
                        (SELECT CASE WHEN rr.spotify_track_id IS NOT NULL
                                     THEN 'https://open.spotify.com/track/' || rr.spotify_track_id
                                     WHEN rel.spotify_album_id IS NOT NULL
                                     THEN 'https://open.spotify.com/album/' || rel.spotify_album_id END
                         FROM releases rel
                         LEFT JOIN recording_releases rr ON rr.release_id = rel.id AND rr.recording_id = r.id
                         WHERE rel.id = r.default_release_id
                           AND (rel.spotify_album_id IS NOT NULL OR rr.spotify_track_id IS NOT NULL)
                        ),
                        (SELECT CASE WHEN rr.spotify_track_id IS NOT NULL
                                     THEN 'https://open.spotify.com/track/' || rr.spotify_track_id
                                     WHEN rel.spotify_album_id IS NOT NULL
                                     THEN 'https://open.spotify.com/album/' || rel.spotify_album_id END
                         FROM recording_releases rr
                         JOIN releases rel ON rr.release_id = rel.id
                         WHERE rr.recording_id = r.id
                           AND (rr.spotify_track_id IS NOT NULL OR rel.spotify_album_id IS NOT NULL)
                         ORDER BY
                           CASE WHEN rr.spotify_track_id IS NOT NULL THEN 0 ELSE 1 END,
                           rel.release_year DESC NULLS LAST
                         LIMIT 1)
                    ) as spotify_url,
                    -- Album art with release_imagery priority
                    {ALBUM_ART_SMALL_SQL},
                    {ALBUM_ART_MEDIUM_SQL},
                    {ALBUM_ART_LARGE_SQL},
                    -- Back cover art (CAA only)
                    {BACK_COVER_SMALL_SQL},
                    {BACK_COVER_MEDIUM_SQL},
                    {BACK_COVER_LARGE_SQL},
                    {HAS_BACK_COVER_SQL},
                    r.youtube_url,
                    r.apple_music_url,
                    r.musicbrainz_id,
                    r.is_canonical,
                    r.notes,
                    s.title as song_title,
                    s.composer
                FROM recordings r
                JOIN songs s ON r.song_id = s.id
                LEFT JOIN releases def_rel ON r.default_release_id = def_rel.id
                ORDER BY r.recording_year DESC NULLS LAST
                LIMIT %s
            """
            recordings = db_tools.execute_query(query, (limit,))
        
        return jsonify(recordings if recordings else [])
        
    except Exception as e:
        logger.error(f"Error fetching recordings: {e}")
        return jsonify({'error': 'Failed to fetch recordings'}), 500


@recordings_bp.route('/recordings/<recording_id>', methods=['GET'])
def get_recording_detail(recording_id):
    """
    Get detailed information about a specific recording, including releases
    
    UPDATED: Recording-Centric Architecture
    - Performers come from recording_performers (not release_performers)
    - Spotify URL and album art come from default_release or best release
    
    UPDATED: Release Imagery Support
    - Album art checks release_imagery table first, falls back to releases table
    
    The response includes:
    - Recording metadata
    - Performers from recording_performers table
    - List of all releases this recording appears on
    - Authority recommendations for this recording
    
    Returns:
        Recording object with nested performers, releases, and recommendations
    """
    try:
        # Single optimized query using CTEs for recording, releases, and authority data
        combined_query = f"""
            WITH recording_data AS (
                SELECT
                    r.id,
                    r.song_id,
                    def_rel.title as album_title,
                    r.recording_date,
                    r.recording_year,
                    r.label,
                    r.default_release_id,
                    -- Get Spotify URL from default release or best available (constructed from IDs)
                    COALESCE(
                        (SELECT CASE WHEN rr_sub.spotify_track_id IS NOT NULL
                                     THEN 'https://open.spotify.com/track/' || rr_sub.spotify_track_id
                                     WHEN rel_sub.spotify_album_id IS NOT NULL
                                     THEN 'https://open.spotify.com/album/' || rel_sub.spotify_album_id END
                         FROM releases rel_sub
                         LEFT JOIN recording_releases rr_sub ON rr_sub.release_id = rel_sub.id AND rr_sub.recording_id = r.id
                         WHERE rel_sub.id = r.default_release_id
                           AND (rel_sub.spotify_album_id IS NOT NULL OR rr_sub.spotify_track_id IS NOT NULL)
                        ),
                        (SELECT CASE WHEN rr_sub.spotify_track_id IS NOT NULL
                                     THEN 'https://open.spotify.com/track/' || rr_sub.spotify_track_id
                                     WHEN rel_sub.spotify_album_id IS NOT NULL
                                     THEN 'https://open.spotify.com/album/' || rel_sub.spotify_album_id END
                         FROM recording_releases rr_sub
                         JOIN releases rel_sub ON rr_sub.release_id = rel_sub.id
                         WHERE rr_sub.recording_id = r.id
                           AND (rr_sub.spotify_track_id IS NOT NULL OR rel_sub.spotify_album_id IS NOT NULL)
                         ORDER BY
                           CASE WHEN rr_sub.spotify_track_id IS NOT NULL THEN 0 ELSE 1 END,
                           rel_sub.release_year DESC NULLS LAST
                         LIMIT 1)
                    ) as spotify_url,
                    -- Album art with release_imagery priority
                    {ALBUM_ART_SMALL_SQL},
                    {ALBUM_ART_MEDIUM_SQL},
                    {ALBUM_ART_LARGE_SQL},
                    -- Back cover art (CAA only)
                    {BACK_COVER_SMALL_SQL},
                    {BACK_COVER_MEDIUM_SQL},
                    {BACK_COVER_LARGE_SQL},
                    {HAS_BACK_COVER_SQL},
                    r.youtube_url,
                    r.apple_music_url,
                    r.musicbrainz_id,
                    r.is_canonical,
                    r.notes,
                    s.title as song_title,
                    s.composer
                FROM recordings r
                JOIN songs s ON r.song_id = s.id
                LEFT JOIN releases def_rel ON r.default_release_id = def_rel.id
                WHERE r.id = %s
            ),
            -- Get all releases for this recording with performer counts (from recording_performers)
            releases_data AS (
                SELECT 
                    rel.id,
                    rel.title,
                    rel.artist_credit,
                    rel.release_date,
                    rel.release_year,
                    rel.country,
                    rel.label,
                    rel.catalog_number,
                    rel.spotify_album_id,
                    CASE WHEN rel.spotify_album_id IS NOT NULL
                         THEN 'https://open.spotify.com/album/' || rel.spotify_album_id END as spotify_album_url,
                    -- Release-level cover art with imagery priority
                    {RELEASE_ART_SMALL_SQL},
                    {RELEASE_ART_MEDIUM_SQL},
                    {RELEASE_ART_LARGE_SQL},
                    rel.total_tracks,
                    rel.musicbrainz_release_id,
                    rr.disc_number,
                    rr.track_number,
                    rr.spotify_track_id,
                    CASE WHEN rr.spotify_track_id IS NOT NULL
                         THEN 'https://open.spotify.com/track/' || rr.spotify_track_id END as spotify_track_url,
                    rf.name as format_name,
                    rs.name as status_name,
                    CASE WHEN rel.spotify_album_id IS NOT NULL THEN 1 ELSE 0 END as has_spotify
                FROM recording_releases rr
                JOIN releases rel ON rr.release_id = rel.id
                LEFT JOIN release_formats rf ON rel.format_id = rf.id
                LEFT JOIN release_statuses rs ON rel.status_id = rs.id
                WHERE rr.recording_id = %s
                ORDER BY has_spotify DESC, rel.release_year ASC NULLS LAST
            ),
            -- Get performers from recording_performers (not release_performers)
            performers_data AS (
                SELECT 
                    p.id,
                    p.name,
                    i.name as instrument,
                    rp.role,
                    p.birth_date,
                    p.death_date
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
            ),
            -- Authority recommendations for this recording
            authority_data AS (
                SELECT
                    sar.id,
                    sar.source as source_name,
                    sar.source_url,
                    sar.recommendation_text,
                    sar.artist_name,
                    sar.album_title as rec_album_title
                FROM song_authority_recommendations sar
                WHERE sar.recording_id = %s
                ORDER BY sar.source
            ),
            -- Transcriptions for this recording
            transcriptions_data AS (
                SELECT
                    st.id,
                    st.song_id,
                    st.recording_id,
                    st.youtube_url,
                    st.created_at,
                    st.updated_at,
                    s.title as song_title,
                    s.composer
                FROM solo_transcriptions st
                JOIN songs s ON st.song_id = s.id
                WHERE st.recording_id = %s
                ORDER BY st.created_at DESC
            )
            SELECT
                (SELECT row_to_json(recording_data.*) FROM recording_data) as recording,
                (SELECT COALESCE(json_agg(performers_data.*), '[]'::json) FROM performers_data) as performers,
                (SELECT COALESCE(json_agg(releases_data.*), '[]'::json) FROM releases_data) as releases,
                (SELECT COALESCE(json_agg(authority_data.*), '[]'::json) FROM authority_data) as authority_recommendations,
                (SELECT COALESCE(json_agg(transcriptions_data.*), '[]'::json) FROM transcriptions_data) as transcriptions
        """

        # Execute the single query with recording_id passed 5 times (for each CTE)
        result = db_tools.execute_query(
            combined_query,
            (recording_id, recording_id, recording_id, recording_id, recording_id),
            fetch_one=True
        )
        
        if not result or not result['recording']:
            return jsonify({'error': 'Recording not found'}), 404
        
        # Build response from the single query result
        recording_dict = result['recording']
        recording_dict['performers'] = result['performers'] if result['performers'] else []
        recording_dict['releases'] = result['releases'] if result['releases'] else []
        recording_dict['authority_recommendations'] = result['authority_recommendations'] if result['authority_recommendations'] else []
        recording_dict['transcriptions'] = result['transcriptions'] if result['transcriptions'] else []

        return jsonify(recording_dict)
        
    except Exception as e:
        logger.error(f"Error fetching recording detail: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch recording details', 'detail': str(e)}), 500


@recordings_bp.route('/recordings/<recording_id>/releases', methods=['GET'])
def get_recording_releases(recording_id):
    """
    Get all releases that contain a specific recording
    
    UPDATED: Recording-Centric Architecture
    - Performers come from recording_performers (the recording's performers)
    - release_performers now contains only release-specific credits (producers, engineers)
    
    UPDATED: Release Imagery Support
    - Cover art checks release_imagery table first, falls back to releases table
    
    Returns:
        List of releases with recording's performers and Spotify info
    """
    try:
        query = f"""
            SELECT 
                rel.id,
                rel.title,
                rel.artist_credit,
                rel.release_date,
                rel.release_year,
                rel.country,
                rel.label,
                rel.catalog_number,
                rel.spotify_album_id,
                CASE WHEN rel.spotify_album_id IS NOT NULL
                     THEN 'https://open.spotify.com/album/' || rel.spotify_album_id END as spotify_album_url,
                -- Cover art with release_imagery priority
                {RELEASE_ART_SMALL_SQL},
                {RELEASE_ART_MEDIUM_SQL},
                {RELEASE_ART_LARGE_SQL},
                rel.total_tracks,
                rel.musicbrainz_release_id,
                rr.disc_number,
                rr.track_number,
                rr.spotify_track_id,
                CASE WHEN rr.spotify_track_id IS NOT NULL
                     THEN 'https://open.spotify.com/track/' || rr.spotify_track_id END as spotify_track_url,
                rf.name as format_name,
                rs.name as status_name,
                -- Performers from recording_performers (not release_performers)
                COALESCE(
                    (SELECT json_agg(
                        jsonb_build_object(
                            'id', p.id,
                            'name', p.name,
                            'sort_name', p.sort_name,
                            'instrument', i.name,
                            'role', rp.role
                        ) ORDER BY
                            CASE rp.role
                                WHEN 'leader' THEN 1
                                WHEN 'sideman' THEN 2
                                ELSE 3
                            END,
                            COALESCE(p.sort_name, p.name)
                    )
                    FROM recording_performers rp
                    JOIN performers p ON rp.performer_id = p.id
                    LEFT JOIN instruments i ON rp.instrument_id = i.id
                    WHERE rp.recording_id = rr.recording_id
                    ),
                    '[]'::json
                ) as performers,
                -- Release-specific credits (producers, engineers, etc.)
                COALESCE(
                    (SELECT json_agg(
                        jsonb_build_object(
                            'id', p.id,
                            'name', p.name,
                            'sort_name', p.sort_name,
                            'role', relp.role
                        ) ORDER BY relp.role, COALESCE(p.sort_name, p.name)
                    )
                    FROM release_performers relp
                    JOIN performers p ON relp.performer_id = p.id
                    WHERE relp.release_id = rel.id
                    ),
                    '[]'::json
                ) as release_credits
            FROM recording_releases rr
            JOIN releases rel ON rr.release_id = rel.id
            LEFT JOIN release_formats rf ON rel.format_id = rf.id
            LEFT JOIN release_statuses rs ON rel.status_id = rs.id
            WHERE rr.recording_id = %s
            ORDER BY 
                CASE WHEN rel.spotify_album_id IS NOT NULL THEN 0 ELSE 1 END,
                rel.release_year ASC NULLS LAST
        """
        
        releases = db_tools.execute_query(query, (recording_id,))
        return jsonify(releases if releases else [])
        
    except Exception as e:
        logger.error(f"Error fetching recording releases: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch releases', 'detail': str(e)}), 500