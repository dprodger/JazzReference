# routes/recordings.py
"""
Recording API Routes - Recording-Centric Performer Architecture

UPDATED: Recording-Centric Architecture
- Performers come from recording_performers table (not release_performers)
- Spotify URL and album art come from default_release or best release
- Album title now comes from default release (releases.title via default_release_id)
- release_performers is now for release-specific credits (producers, engineers)

UPDATED: Release Imagery Support
- Album art comes from release_imagery table (CAA, Spotify, Apple Music)

Provides endpoints for listing and searching recordings, including releases.
"""
from flask import Blueprint, jsonify, request, g
import logging
import db_utils as db_tools
from middleware.auth_middleware import optional_auth

logger = logging.getLogger(__name__)
recordings_bp = Blueprint('recordings', __name__)


# ============================================================================
# SQL FRAGMENTS FOR ALBUM ART
# ============================================================================
# All imagery now comes from release_imagery table (CAA, Spotify, Apple Music)
# Priority: default_release first, then any linked release

ALBUM_ART_SMALL_SQL = """
    COALESCE(
        -- 1. release_imagery (Front) for default release, prefer CAA for consistency with back covers
        (SELECT ri.image_url_small FROM release_imagery ri
         WHERE ri.release_id = r.default_release_id AND ri.type = 'Front'
         ORDER BY CASE WHEN ri.source = 'MusicBrainz' THEN 0 ELSE 1 END
         LIMIT 1),
        -- 2. release_imagery (Front) for any linked release
        (SELECT ri.image_url_small
         FROM recording_releases rr
         JOIN release_imagery ri ON rr.release_id = ri.release_id
         WHERE rr.recording_id = r.id AND ri.type = 'Front'
         ORDER BY CASE WHEN ri.source = 'MusicBrainz' THEN 0 ELSE 1 END
         LIMIT 1)
    ) as album_art_small"""

ALBUM_ART_MEDIUM_SQL = """
    COALESCE(
        (SELECT ri.image_url_medium FROM release_imagery ri
         WHERE ri.release_id = r.default_release_id AND ri.type = 'Front'
         ORDER BY CASE WHEN ri.source = 'MusicBrainz' THEN 0 ELSE 1 END
         LIMIT 1),
        (SELECT ri.image_url_medium
         FROM recording_releases rr
         JOIN release_imagery ri ON rr.release_id = ri.release_id
         WHERE rr.recording_id = r.id AND ri.type = 'Front'
         ORDER BY CASE WHEN ri.source = 'MusicBrainz' THEN 0 ELSE 1 END
         LIMIT 1)
    ) as album_art_medium"""

ALBUM_ART_LARGE_SQL = """
    COALESCE(
        (SELECT ri.image_url_large FROM release_imagery ri
         WHERE ri.release_id = r.default_release_id AND ri.type = 'Front'
         ORDER BY CASE WHEN ri.source = 'MusicBrainz' THEN 0 ELSE 1 END
         LIMIT 1),
        (SELECT ri.image_url_large
         FROM recording_releases rr
         JOIN release_imagery ri ON rr.release_id = ri.release_id
         WHERE rr.recording_id = r.id AND ri.type = 'Front'
         ORDER BY CASE WHEN ri.source = 'MusicBrainz' THEN 0 ELSE 1 END
         LIMIT 1)
    ) as album_art_large"""

# Source info for front cover (for watermark/attribution)
ALBUM_ART_SOURCE_SQL = """
    COALESCE(
        (SELECT ri.source::text FROM release_imagery ri
         WHERE ri.release_id = r.default_release_id AND ri.type = 'Front'
         ORDER BY CASE WHEN ri.source = 'MusicBrainz' THEN 0 ELSE 1 END
         LIMIT 1),
        (SELECT ri.source::text
         FROM recording_releases rr
         JOIN release_imagery ri ON rr.release_id = ri.release_id
         WHERE rr.recording_id = r.id AND ri.type = 'Front'
         ORDER BY CASE WHEN ri.source = 'MusicBrainz' THEN 0 ELSE 1 END
         LIMIT 1)
    ) as album_art_source"""

ALBUM_ART_SOURCE_URL_SQL = """
    COALESCE(
        (SELECT ri.source_url FROM release_imagery ri
         WHERE ri.release_id = r.default_release_id AND ri.type = 'Front'
         ORDER BY CASE WHEN ri.source = 'MusicBrainz' THEN 0 ELSE 1 END
         LIMIT 1),
        (SELECT ri.source_url
         FROM recording_releases rr
         JOIN release_imagery ri ON rr.release_id = ri.release_id
         WHERE rr.recording_id = r.id AND ri.type = 'Front'
         ORDER BY CASE WHEN ri.source = 'MusicBrainz' THEN 0 ELSE 1 END
         LIMIT 1)
    ) as album_art_source_url"""

# ============================================================================
# SQL FRAGMENTS FOR BACK COVER ART
# ============================================================================
# Back covers ONLY from the default release - ensures consistency with front cover
# (No fallback to linked releases to avoid showing mismatched front/back from different releases)

BACK_COVER_SMALL_SQL = """
    (SELECT ri.image_url_small FROM release_imagery ri
     WHERE ri.release_id = r.default_release_id AND ri.type = 'Back'
     LIMIT 1) as back_cover_art_small"""

BACK_COVER_MEDIUM_SQL = """
    (SELECT ri.image_url_medium FROM release_imagery ri
     WHERE ri.release_id = r.default_release_id AND ri.type = 'Back'
     LIMIT 1) as back_cover_art_medium"""

BACK_COVER_LARGE_SQL = """
    (SELECT ri.image_url_large FROM release_imagery ri
     WHERE ri.release_id = r.default_release_id AND ri.type = 'Back'
     LIMIT 1) as back_cover_art_large"""

HAS_BACK_COVER_SQL = """
    EXISTS(
        SELECT 1 FROM release_imagery ri
        WHERE ri.release_id = r.default_release_id AND ri.type = 'Back'
    ) as has_back_cover"""

# Source info for back cover (for watermark/attribution)
BACK_COVER_SOURCE_SQL = """
    (SELECT ri.source::text FROM release_imagery ri
     WHERE ri.release_id = r.default_release_id AND ri.type = 'Back'
     LIMIT 1) as back_cover_source"""

BACK_COVER_SOURCE_URL_SQL = """
    (SELECT ri.source_url FROM release_imagery ri
     WHERE ri.release_id = r.default_release_id AND ri.type = 'Back'
     LIMIT 1) as back_cover_source_url"""

# SQL fragment for favorite count (subquery)
FAVORITE_COUNT_SQL = """
    (SELECT COUNT(*) FROM recording_favorites rf WHERE rf.recording_id = r.id) as favorite_count"""

# For release-level queries (get_recording_releases), we check imagery for specific release
# Prefer CAA for consistency with back covers
RELEASE_ART_SMALL_SQL = """
    (SELECT ri.image_url_small FROM release_imagery ri
     WHERE ri.release_id = rel.id AND ri.type = 'Front'
     ORDER BY CASE WHEN ri.source = 'MusicBrainz' THEN 0 ELSE 1 END
     LIMIT 1) as cover_art_small"""

RELEASE_ART_MEDIUM_SQL = """
    (SELECT ri.image_url_medium FROM release_imagery ri
     WHERE ri.release_id = rel.id AND ri.type = 'Front'
     ORDER BY CASE WHEN ri.source = 'MusicBrainz' THEN 0 ELSE 1 END
     LIMIT 1) as cover_art_medium"""

RELEASE_ART_LARGE_SQL = """
    (SELECT ri.image_url_large FROM release_imagery ri
     WHERE ri.release_id = rel.id AND ri.type = 'Front'
     ORDER BY CASE WHEN ri.source = 'MusicBrainz' THEN 0 ELSE 1 END
     LIMIT 1) as cover_art_large"""

RELEASE_ART_SOURCE_SQL = """
    (SELECT ri.source::text FROM release_imagery ri
     WHERE ri.release_id = rel.id AND ri.type = 'Front'
     ORDER BY CASE WHEN ri.source = 'MusicBrainz' THEN 0 ELSE 1 END
     LIMIT 1) as cover_art_source"""

RELEASE_ART_SOURCE_URL_SQL = """
    (SELECT ri.source_url FROM release_imagery ri
     WHERE ri.release_id = rel.id AND ri.type = 'Front'
     ORDER BY CASE WHEN ri.source = 'MusicBrainz' THEN 0 ELSE 1 END
     LIMIT 1) as cover_art_source_url"""

# ============================================================================
# SQL FRAGMENTS FOR RELEASE-LEVEL BACK COVER ART
# ============================================================================
# Back covers for specific releases (used in releases array)

RELEASE_BACK_ART_SMALL_SQL = """
    (SELECT ri.image_url_small FROM release_imagery ri
     WHERE ri.release_id = rel.id AND ri.type = 'Back'
     LIMIT 1) as back_cover_art_small"""

RELEASE_BACK_ART_MEDIUM_SQL = """
    (SELECT ri.image_url_medium FROM release_imagery ri
     WHERE ri.release_id = rel.id AND ri.type = 'Back'
     LIMIT 1) as back_cover_art_medium"""

RELEASE_BACK_ART_LARGE_SQL = """
    (SELECT ri.image_url_large FROM release_imagery ri
     WHERE ri.release_id = rel.id AND ri.type = 'Back'
     LIMIT 1) as back_cover_art_large"""

RELEASE_HAS_BACK_COVER_SQL = """
    EXISTS(
        SELECT 1 FROM release_imagery ri
        WHERE ri.release_id = rel.id AND ri.type = 'Back'
    ) as has_back_cover"""

RELEASE_BACK_ART_SOURCE_SQL = """
    (SELECT ri.source::text FROM release_imagery ri
     WHERE ri.release_id = rel.id AND ri.type = 'Back'
     LIMIT 1) as back_cover_source"""

RELEASE_BACK_ART_SOURCE_URL_SQL = """
    (SELECT ri.source_url FROM release_imagery ri
     WHERE ri.release_id = rel.id AND ri.type = 'Back'
     LIMIT 1) as back_cover_source_url"""

# ============================================================================
# SQL FRAGMENTS FOR SPOTIFY URLS (Normalized Streaming Links)
# ============================================================================
# Spotify track URLs now come from recording_release_streaming_links table
# with fallback to legacy spotify_track_id column for backwards compatibility

SPOTIFY_URL_FROM_DEFAULT_RELEASE_SQL = """
    COALESCE(
        -- Check normalized streaming_links table first (default release)
        (SELECT rrsl.service_url
         FROM recording_releases rr
         JOIN recording_release_streaming_links rrsl
             ON rrsl.recording_release_id = rr.id AND rrsl.service = 'spotify'
         WHERE rr.release_id = r.default_release_id AND rr.recording_id = r.id
        ),
        -- Fall back to legacy column (default release)
        (SELECT 'https://open.spotify.com/track/' || rr.spotify_track_id
         FROM recording_releases rr
         WHERE rr.release_id = r.default_release_id
           AND rr.recording_id = r.id
           AND rr.spotify_track_id IS NOT NULL
        )
    )"""

SPOTIFY_URL_FROM_ANY_RELEASE_SQL = """
    COALESCE(
        -- Check normalized streaming_links table first
        (SELECT rrsl.service_url
         FROM recording_releases rr
         JOIN recording_release_streaming_links rrsl
             ON rrsl.recording_release_id = rr.id AND rrsl.service = 'spotify'
         WHERE rr.recording_id = r.id
         LIMIT 1
        ),
        -- Fall back to legacy column
        (SELECT 'https://open.spotify.com/track/' || rr.spotify_track_id
         FROM recording_releases rr
         WHERE rr.recording_id = r.id
           AND rr.spotify_track_id IS NOT NULL
         LIMIT 1
        )
    )"""

# For has_spotify availability check
HAS_SPOTIFY_SQL = """
    (
        EXISTS(SELECT 1 FROM recording_releases rr2
               JOIN recording_release_streaming_links rrsl ON rrsl.recording_release_id = rr2.id
               WHERE rr2.recording_id = r.id AND rrsl.service = 'spotify')
        OR EXISTS(SELECT 1 FROM recording_releases rr2
               WHERE rr2.recording_id = r.id AND rr2.spotify_track_id IS NOT NULL)
    )"""


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
        # Simplified query using JOINs instead of correlated subqueries
        # Gets album art and Spotify URL from default release only (no fallbacks)
        if search_query:
            # Search across album title (from default release), performer names, and song title
            query = f"""
                SELECT DISTINCT ON (r.id)
                    r.id,
                    r.title,
                    r.song_id,
                    def_rel.title as album_title,
                    def_rel.artist_credit,
                    r.recording_date,
                    r.recording_year,
                    r.label,
                    r.default_release_id,
                    -- Get Spotify track URL from default release or best available
                    COALESCE(
                        {SPOTIFY_URL_FROM_DEFAULT_RELEASE_SQL},
                        {SPOTIFY_URL_FROM_ANY_RELEASE_SQL}
                    ) as spotify_url,
                    -- Album art with release_imagery priority
                    {ALBUM_ART_SMALL_SQL},
                    {ALBUM_ART_MEDIUM_SQL},
                    {ALBUM_ART_LARGE_SQL},
                    {ALBUM_ART_SOURCE_SQL},
                    {ALBUM_ART_SOURCE_URL_SQL},
                    -- Back cover art (CAA only)
                    {BACK_COVER_SMALL_SQL},
                    {BACK_COVER_MEDIUM_SQL},
                    {BACK_COVER_LARGE_SQL},
                    {HAS_BACK_COVER_SQL},
                    {BACK_COVER_SOURCE_SQL},
                    {BACK_COVER_SOURCE_URL_SQL},
                    r.youtube_url,
                    r.apple_music_url,
                    r.musicbrainz_id,
                    r.is_canonical,
                    r.notes,
                    s.title as song_title,
                    s.composer,
                    -- Favorite count
                    (SELECT COUNT(*) FROM recording_favorites rf WHERE rf.recording_id = r.id) as favorite_count,
                    -- Streaming availability flags
                    {HAS_SPOTIFY_SQL} as has_spotify,
                    EXISTS(SELECT 1 FROM recording_releases rr2
                           JOIN recording_release_streaming_links rrsl ON rrsl.recording_release_id = rr2.id
                           WHERE rr2.recording_id = r.id AND rrsl.service = 'apple_music'
                    ) as has_apple_music,
                    (
                        EXISTS(SELECT 1 FROM recording_releases rr2
                               JOIN recording_release_streaming_links rrsl ON rrsl.recording_release_id = rr2.id
                               WHERE rr2.recording_id = r.id AND rrsl.service = 'youtube')
                        OR r.youtube_url IS NOT NULL
                    ) as has_youtube
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
            # Efficient query using JOINs with default release instead of correlated subqueries
            # Album art and Spotify URL come from default release only (no fallback scanning)
            query = f"""
                SELECT
                    r.id,
                    r.title,
                    r.song_id,
                    def_rel.title as album_title,
                    def_rel.artist_credit,
                    r.recording_date,
                    r.recording_year,
                    r.label,
                    r.default_release_id,
                    -- Spotify URL: check streaming links table first, then legacy column
                    COALESCE(
                        def_rrsl.service_url,
                        CASE WHEN def_rr.spotify_track_id IS NOT NULL
                             THEN 'https://open.spotify.com/track/' || def_rr.spotify_track_id
                        END
                    ) as spotify_url,
                    -- Album art from release_imagery table
                    def_ri.image_url_small as album_art_small,
                    def_ri.image_url_medium as album_art_medium,
                    def_ri.image_url_large as album_art_large,
                    def_ri.source::text as album_art_source,
                    def_ri.source_url as album_art_source_url,
                    -- Back cover (CAA only)
                    back_ri.image_url_small as back_cover_art_small,
                    back_ri.image_url_medium as back_cover_art_medium,
                    back_ri.image_url_large as back_cover_art_large,
                    back_ri.release_id IS NOT NULL as has_back_cover,
                    back_ri.source::text as back_cover_source,
                    back_ri.source_url as back_cover_source_url,
                    r.youtube_url,
                    r.apple_music_url,
                    r.musicbrainz_id,
                    r.is_canonical,
                    r.notes,
                    s.title as song_title,
                    s.composer,
                    -- Favorite count
                    (SELECT COUNT(*) FROM recording_favorites rf WHERE rf.recording_id = r.id) as favorite_count,
                    -- Streaming availability flags
                    {HAS_SPOTIFY_SQL} as has_spotify,
                    EXISTS(SELECT 1 FROM recording_releases rr2
                           JOIN recording_release_streaming_links rrsl ON rrsl.recording_release_id = rr2.id
                           WHERE rr2.recording_id = r.id AND rrsl.service = 'apple_music'
                    ) as has_apple_music,
                    (
                        EXISTS(SELECT 1 FROM recording_releases rr2
                               JOIN recording_release_streaming_links rrsl ON rrsl.recording_release_id = rr2.id
                               WHERE rr2.recording_id = r.id AND rrsl.service = 'youtube')
                        OR r.youtube_url IS NOT NULL
                    ) as has_youtube
                FROM recordings r
                JOIN songs s ON r.song_id = s.id
                LEFT JOIN releases def_rel ON r.default_release_id = def_rel.id
                LEFT JOIN recording_releases def_rr ON def_rr.release_id = def_rel.id AND def_rr.recording_id = r.id
                LEFT JOIN recording_release_streaming_links def_rrsl
                    ON def_rrsl.recording_release_id = def_rr.id AND def_rrsl.service = 'spotify'
                LEFT JOIN release_imagery def_ri ON def_ri.release_id = def_rel.id AND def_ri.type = 'Front'
                LEFT JOIN release_imagery back_ri ON back_ri.release_id = def_rel.id AND back_ri.type = 'Back'
                ORDER BY r.recording_year DESC NULLS LAST
                LIMIT %s
            """
            recordings = db_tools.execute_query(query, (limit,))
        
        return jsonify(recordings if recordings else [])
        
    except Exception as e:
        logger.error(f"Error fetching recordings: {e}")
        return jsonify({'error': 'Failed to fetch recordings'}), 500


@recordings_bp.route('/recordings/<recording_id>', methods=['GET'])
@optional_auth
def get_recording_detail(recording_id):
    """
    Get detailed information about a specific recording, including releases
    
    UPDATED: Recording-Centric Architecture
    - Performers come from recording_performers (not release_performers)
    - Spotify URL and album art come from default_release or best release
    
    UPDATED: Release Imagery Support
    - Album art comes from release_imagery table
    
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
                    r.title,
                    r.song_id,
                    def_rel.title as album_title,
                    r.recording_date,
                    r.recording_year,
                    r.label,
                    r.default_release_id,
                    -- Get Spotify track URL from default release or best available
                    -- Check normalized streaming_links first, then legacy column
                    COALESCE(
                        {SPOTIFY_URL_FROM_DEFAULT_RELEASE_SQL},
                        {SPOTIFY_URL_FROM_ANY_RELEASE_SQL}
                    ) as spotify_url,
                    -- Album art with release_imagery priority
                    {ALBUM_ART_SMALL_SQL},
                    {ALBUM_ART_MEDIUM_SQL},
                    {ALBUM_ART_LARGE_SQL},
                    {ALBUM_ART_SOURCE_SQL},
                    {ALBUM_ART_SOURCE_URL_SQL},
                    -- Back cover art (CAA only)
                    {BACK_COVER_SMALL_SQL},
                    {BACK_COVER_MEDIUM_SQL},
                    {BACK_COVER_LARGE_SQL},
                    {HAS_BACK_COVER_SQL},
                    {BACK_COVER_SOURCE_SQL},
                    {BACK_COVER_SOURCE_URL_SQL},
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
                    CASE WHEN rel.spotify_album_id IS NOT NULL THEN 'https://open.spotify.com/album/' || rel.spotify_album_id END as spotify_album_url,
                    -- Release-level cover art with imagery priority
                    {RELEASE_ART_SMALL_SQL},
                    {RELEASE_ART_MEDIUM_SQL},
                    {RELEASE_ART_LARGE_SQL},
                    {RELEASE_ART_SOURCE_SQL},
                    {RELEASE_ART_SOURCE_URL_SQL},
                    -- Release-level back cover art
                    {RELEASE_BACK_ART_SMALL_SQL},
                    {RELEASE_BACK_ART_MEDIUM_SQL},
                    {RELEASE_BACK_ART_LARGE_SQL},
                    {RELEASE_HAS_BACK_COVER_SQL},
                    {RELEASE_BACK_ART_SOURCE_SQL},
                    {RELEASE_BACK_ART_SOURCE_URL_SQL},
                    rel.total_tracks,
                    rel.musicbrainz_release_id,
                    rr.disc_number,
                    rr.track_number,
                    COALESCE(rrsl.service_id, rr.spotify_track_id) as spotify_track_id,
                    COALESCE(rrsl.service_url,
                        CASE WHEN rr.spotify_track_id IS NOT NULL
                             THEN 'https://open.spotify.com/track/' || rr.spotify_track_id END
                    ) as spotify_track_url,
                    rf.name as format_name,
                    rs.name as status_name,
                    CASE WHEN rrsl.service_id IS NOT NULL OR rr.spotify_track_id IS NOT NULL THEN 1 ELSE 0 END as has_spotify
                FROM recording_releases rr
                JOIN releases rel ON rr.release_id = rel.id
                LEFT JOIN recording_release_streaming_links rrsl
                    ON rrsl.recording_release_id = rr.id AND rrsl.service = 'spotify'
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
            ),
            -- Streaming links from normalized tables (best link per service)
            streaming_links_data AS (
                SELECT DISTINCT ON (service)
                    service,
                    service_url as track_url,
                    preview_url,
                    -- Get album URL from release_streaming_links for same release
                    (SELECT rsl.service_url
                     FROM release_streaming_links rsl
                     WHERE rsl.release_id = rr.release_id AND rsl.service = rrsl.service
                     LIMIT 1
                    ) as album_url
                FROM recording_releases rr
                JOIN recording_release_streaming_links rrsl ON rrsl.recording_release_id = rr.id
                WHERE rr.recording_id = %s
                ORDER BY service, rrsl.match_confidence DESC NULLS LAST
            ),
            -- Favorites data
            favorites_data AS (
                SELECT
                    COUNT(*) as favorite_count,
                    COALESCE(json_agg(
                        json_build_object('id', u.id::text, 'display_name', u.display_name)
                        ORDER BY rf.created_at DESC
                    ) FILTER (WHERE u.id IS NOT NULL), '[]'::json) as favorited_by
                FROM recording_favorites rf
                LEFT JOIN users u ON rf.user_id = u.id
                WHERE rf.recording_id = %s
            ),
            -- Community-contributed metadata consensus
            community_consensus AS (
                SELECT
                    (SELECT performance_key FROM recording_contributions
                     WHERE recording_id = %s AND performance_key IS NOT NULL
                     GROUP BY performance_key ORDER BY COUNT(*) DESC, MAX(updated_at) DESC LIMIT 1) as consensus_key,
                    (SELECT tempo_marking FROM recording_contributions
                     WHERE recording_id = %s AND tempo_marking IS NOT NULL
                     GROUP BY tempo_marking ORDER BY COUNT(*) DESC, MAX(updated_at) DESC LIMIT 1) as consensus_tempo_marking,
                    (SELECT is_instrumental FROM recording_contributions
                     WHERE recording_id = %s AND is_instrumental IS NOT NULL
                     GROUP BY is_instrumental ORDER BY COUNT(*) DESC, MAX(updated_at) DESC LIMIT 1) as consensus_instrumental,
                    (SELECT COUNT(*) FROM recording_contributions WHERE recording_id = %s AND performance_key IS NOT NULL) as key_count,
                    (SELECT COUNT(*) FROM recording_contributions WHERE recording_id = %s AND tempo_marking IS NOT NULL) as tempo_count,
                    (SELECT COUNT(*) FROM recording_contributions WHERE recording_id = %s AND is_instrumental IS NOT NULL) as instrumental_count
            )
            SELECT
                (SELECT row_to_json(recording_data.*) FROM recording_data) as recording,
                (SELECT COALESCE(json_agg(performers_data.*), '[]'::json) FROM performers_data) as performers,
                (SELECT COALESCE(json_agg(releases_data.*), '[]'::json) FROM releases_data) as releases,
                (SELECT COALESCE(json_agg(authority_data.*), '[]'::json) FROM authority_data) as authority_recommendations,
                (SELECT COALESCE(json_agg(transcriptions_data.*), '[]'::json) FROM transcriptions_data) as transcriptions,
                (SELECT COALESCE(json_agg(streaming_links_data.*), '[]'::json) FROM streaming_links_data) as streaming_links,
                (SELECT row_to_json(favorites_data.*) FROM favorites_data) as favorites,
                (SELECT row_to_json(community_consensus.*) FROM community_consensus) as community_consensus
        """

        # Execute the single query with recording_id passed 13 times (for each CTE)
        result = db_tools.execute_query(
            combined_query,
            (recording_id,) * 13,
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

        # Transform streaming_links from array to dict keyed by service
        streaming_links_array = result['streaming_links'] if result['streaming_links'] else []
        streaming_links_dict = {}
        for link in streaming_links_array:
            streaming_links_dict[link['service']] = {
                'track_url': link.get('track_url'),
                'album_url': link.get('album_url'),
                'preview_url': link.get('preview_url')
            }

        # Add YouTube from legacy recordings.youtube_url field
        if recording_dict.get('youtube_url'):
            streaming_links_dict['youtube'] = {
                'track_url': recording_dict.get('youtube_url'),
                'album_url': None,
                'preview_url': None
            }

        # Add legacy Spotify URL if not already in streaming_links
        if 'spotify' not in streaming_links_dict and recording_dict.get('spotify_url'):
            streaming_links_dict['spotify'] = {
                'track_url': recording_dict.get('spotify_url'),
                'album_url': None,
                'preview_url': None
            }

        recording_dict['streaming_links'] = streaming_links_dict

        # Add favorites data
        favorites_data = result.get('favorites') or {}
        recording_dict['favorite_count'] = favorites_data.get('favorite_count', 0)
        recording_dict['favorited_by'] = favorites_data.get('favorited_by', [])

        # Check if current user has favorited (only if authenticated)
        if hasattr(g, 'current_user') and g.current_user:
            current_user_id = str(g.current_user['id'])
            recording_dict['is_favorited'] = any(
                user.get('id') == current_user_id
                for user in recording_dict['favorited_by']
            )
        else:
            recording_dict['is_favorited'] = None

        # Add community-contributed metadata
        community_consensus = result.get('community_consensus') or {}
        recording_dict['community_data'] = {
            'consensus': {
                'performance_key': community_consensus.get('consensus_key'),
                'tempo_marking': community_consensus.get('consensus_tempo_marking'),
                'is_instrumental': community_consensus.get('consensus_instrumental')
            },
            'counts': {
                'key': community_consensus.get('key_count', 0) or 0,
                'tempo': community_consensus.get('tempo_count', 0) or 0,
                'instrumental': community_consensus.get('instrumental_count', 0) or 0
            }
        }

        # Add user's contribution if authenticated
        if hasattr(g, 'current_user') and g.current_user:
            user_contribution = db_tools.execute_query(
                """SELECT performance_key, tempo_marking, is_instrumental, updated_at
                   FROM recording_contributions
                   WHERE recording_id = %s AND user_id = %s""",
                (recording_id, g.current_user['id']),
                fetch_one=True
            )
            if user_contribution:
                recording_dict['user_contribution'] = {
                    'performance_key': user_contribution['performance_key'],
                    'tempo_marking': user_contribution['tempo_marking'],
                    'is_instrumental': user_contribution['is_instrumental'],
                    'updated_at': user_contribution['updated_at'].isoformat() if user_contribution['updated_at'] else None
                }
            else:
                recording_dict['user_contribution'] = None
        else:
            recording_dict['user_contribution'] = None

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
    - Cover art comes from release_imagery table
    
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
                CASE WHEN rel.spotify_album_id IS NOT NULL THEN 'https://open.spotify.com/album/' || rel.spotify_album_id END as spotify_album_url,
                -- Cover art with release_imagery priority
                {RELEASE_ART_SMALL_SQL},
                {RELEASE_ART_MEDIUM_SQL},
                {RELEASE_ART_LARGE_SQL},
                {RELEASE_ART_SOURCE_SQL},
                {RELEASE_ART_SOURCE_URL_SQL},
                -- Back cover art
                {RELEASE_BACK_ART_SMALL_SQL},
                {RELEASE_BACK_ART_MEDIUM_SQL},
                {RELEASE_BACK_ART_LARGE_SQL},
                {RELEASE_HAS_BACK_COVER_SQL},
                {RELEASE_BACK_ART_SOURCE_SQL},
                {RELEASE_BACK_ART_SOURCE_URL_SQL},
                rel.total_tracks,
                rel.musicbrainz_release_id,
                rr.disc_number,
                rr.track_number,
                COALESCE(rrsl.service_id, rr.spotify_track_id) as spotify_track_id,
                COALESCE(rrsl.service_url,
                    CASE WHEN rr.spotify_track_id IS NOT NULL
                         THEN 'https://open.spotify.com/track/' || rr.spotify_track_id END
                ) as spotify_track_url,
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
            LEFT JOIN recording_release_streaming_links rrsl
                ON rrsl.recording_release_id = rr.id AND rrsl.service = 'spotify'
            LEFT JOIN release_formats rf ON rel.format_id = rf.id
            LEFT JOIN release_statuses rs ON rel.status_id = rs.id
            WHERE rr.recording_id = %s
            ORDER BY
                CASE WHEN rrsl.service_id IS NOT NULL OR rr.spotify_track_id IS NOT NULL THEN 0 ELSE 1 END,
                rel.release_year ASC NULLS LAST
        """
        
        releases = db_tools.execute_query(query, (recording_id,))
        return jsonify(releases if releases else [])
        
    except Exception as e:
        logger.error(f"Error fetching recording releases: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch releases', 'detail': str(e)}), 500