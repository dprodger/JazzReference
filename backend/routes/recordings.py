# routes/recordings.py
"""
Recording API Routes - Updated with Releases Support
Provides endpoints for listing and searching recordings, now including releases
"""
from flask import Blueprint, jsonify, request
import logging
import db_utils as db_tools

logger = logging.getLogger(__name__)
recordings_bp = Blueprint('recordings', __name__)


@recordings_bp.route('/api/recordings', methods=['GET'])
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
            # Search across album title, performer names, and song title
            query = """
                SELECT DISTINCT ON (r.id)
                    r.id,
                    r.song_id,
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
                    s.title as song_title,
                    s.composer
                FROM recordings r
                JOIN songs s ON r.song_id = s.id
                LEFT JOIN recording_performers rp ON r.id = rp.recording_id
                LEFT JOIN performers p ON rp.performer_id = p.id
                WHERE (
                    r.album_title ILIKE %s OR
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
            query = """
                SELECT 
                    r.id,
                    r.song_id,
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
                    s.title as song_title,
                    s.composer
                FROM recordings r
                JOIN songs s ON r.song_id = s.id
                ORDER BY r.recording_year DESC NULLS LAST
                LIMIT %s
            """
            recordings = db_tools.execute_query(query, (limit,))
        
        return jsonify(recordings if recordings else [])
        
    except Exception as e:
        logger.error(f"Error fetching recordings: {e}")
        return jsonify({'error': 'Failed to fetch recordings'}), 500


@recordings_bp.route('/api/recordings/<recording_id>', methods=['GET'])
def get_recording_detail(recording_id):
    """
    Get detailed information about a specific recording, including releases
    
    The response includes:
    - Recording metadata
    - Performers from the "best" release (Spotify + most performers)
    - List of all releases this recording appears on
    - Authority recommendations for this recording
    
    Returns:
        Recording object with nested performers, releases, and recommendations
    """
    try:
        # Single optimized query using CTEs for recording, releases, and authority data
        combined_query = """
            WITH recording_data AS (
                SELECT 
                    r.id,
                    r.song_id,
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
                    s.title as song_title,
                    s.composer
                FROM recordings r
                JOIN songs s ON r.song_id = s.id
                WHERE r.id = %s
            ),
            -- Get all releases for this recording with performer counts
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
                    rel.spotify_album_url,
                    rel.cover_art_small,
                    rel.cover_art_medium,
                    rel.cover_art_large,
                    rel.total_tracks,
                    rel.musicbrainz_release_id,
                    rr.disc_number,
                    rr.track_number,
                    rr.spotify_track_id,
                    rr.spotify_track_url,
                    rf.name as format_name,
                    rs.name as status_name,
                    COUNT(DISTINCT rp.performer_id) as performer_count,
                    CASE WHEN rel.spotify_album_id IS NOT NULL THEN 1 ELSE 0 END as has_spotify
                FROM recording_releases rr
                JOIN releases rel ON rr.release_id = rel.id
                LEFT JOIN release_formats rf ON rel.format_id = rf.id
                LEFT JOIN release_statuses rs ON rel.status_id = rs.id
                LEFT JOIN release_performers rp ON rel.id = rp.release_id
                WHERE rr.recording_id = %s
                GROUP BY rel.id, rel.title, rel.artist_credit, rel.release_date, 
                         rel.release_year, rel.country, rel.label, rel.catalog_number,
                         rel.spotify_album_id, rel.spotify_album_url,
                         rel.cover_art_small, rel.cover_art_medium, rel.cover_art_large,
                         rel.total_tracks, rel.musicbrainz_release_id,
                         rr.disc_number, rr.track_number, rr.spotify_track_id, rr.spotify_track_url,
                         rf.name, rs.name
                ORDER BY has_spotify DESC, performer_count DESC, rel.release_year ASC NULLS LAST
            ),
            -- Get the "best" release ID (has Spotify + most performers)
            best_release AS (
                SELECT id FROM releases_data LIMIT 1
            ),
            -- Get performers from the best release
            performers_data AS (
                SELECT 
                    p.id,
                    p.name,
                    i.name as instrument,
                    rp.role,
                    p.birth_date,
                    p.death_date
                FROM release_performers rp
                JOIN performers p ON rp.performer_id = p.id
                LEFT JOIN instruments i ON rp.instrument_id = i.id
                WHERE rp.release_id = (SELECT id FROM best_release)
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
            )
            SELECT 
                (SELECT row_to_json(recording_data.*) FROM recording_data) as recording,
                (SELECT COALESCE(json_agg(performers_data.*), '[]'::json) FROM performers_data) as performers,
                (SELECT COALESCE(json_agg(releases_data.*), '[]'::json) FROM releases_data) as releases,
                (SELECT COALESCE(json_agg(authority_data.*), '[]'::json) FROM authority_data) as authority_recommendations
        """
        
        # Execute the single query with recording_id passed 3 times (for each CTE)
        result = db_tools.execute_query(
            combined_query, 
            (recording_id, recording_id, recording_id), 
            fetch_one=True
        )
        
        if not result or not result['recording']:
            return jsonify({'error': 'Recording not found'}), 404
        
        # Build response from the single query result
        recording_dict = result['recording']
        recording_dict['performers'] = result['performers'] if result['performers'] else []
        recording_dict['releases'] = result['releases'] if result['releases'] else []
        recording_dict['authority_recommendations'] = result['authority_recommendations'] if result['authority_recommendations'] else []
        
        return jsonify(recording_dict)
        
    except Exception as e:
        logger.error(f"Error fetching recording detail: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch recording details', 'detail': str(e)}), 500


@recordings_bp.route('/api/recordings/<recording_id>/releases', methods=['GET'])
def get_recording_releases(recording_id):
    """
    Get all releases that contain a specific recording
    
    Returns:
        List of releases with their performers and Spotify info
    """
    try:
        query = """
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
                rel.spotify_album_url,
                rel.cover_art_small,
                rel.cover_art_medium,
                rel.cover_art_large,
                rel.total_tracks,
                rel.musicbrainz_release_id,
                rr.disc_number,
                rr.track_number,
                rr.spotify_track_id,
                rr.spotify_track_url,
                rf.name as format_name,
                rs.name as status_name,
                COALESCE(
                    json_agg(
                        DISTINCT jsonb_build_object(
                            'id', p.id,
                            'name', p.name,
                            'instrument', i.name,
                            'role', rp.role
                        )
                    ) FILTER (WHERE p.id IS NOT NULL),
                    '[]'::json
                ) as performers
            FROM recording_releases rr
            JOIN releases rel ON rr.release_id = rel.id
            LEFT JOIN release_formats rf ON rel.format_id = rf.id
            LEFT JOIN release_statuses rs ON rel.status_id = rs.id
            LEFT JOIN release_performers rp ON rel.id = rp.release_id
            LEFT JOIN performers p ON rp.performer_id = p.id
            LEFT JOIN instruments i ON rp.instrument_id = i.id
            WHERE rr.recording_id = %s
            GROUP BY rel.id, rel.title, rel.artist_credit, rel.release_date, 
                     rel.release_year, rel.country, rel.label, rel.catalog_number,
                     rel.spotify_album_id, rel.spotify_album_url,
                     rel.cover_art_small, rel.cover_art_medium, rel.cover_art_large,
                     rel.total_tracks, rel.musicbrainz_release_id,
                     rr.disc_number, rr.track_number, rr.spotify_track_id, rr.spotify_track_url,
                     rf.name, rs.name
            ORDER BY 
                CASE WHEN rel.spotify_album_id IS NOT NULL THEN 0 ELSE 1 END,
                rel.release_year ASC NULLS LAST
        """
        
        releases = db_tools.execute_query(query, (recording_id,))
        return jsonify(releases if releases else [])
        
    except Exception as e:
        logger.error(f"Error fetching recording releases: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch releases', 'detail': str(e)}), 500
