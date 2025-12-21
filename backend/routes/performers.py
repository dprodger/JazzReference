# routes/performers.py
from flask import Blueprint, jsonify, request
import logging
import db_utils as db_tools
from utils.helpers import safe_strip

logger = logging.getLogger(__name__)
performers_bp = Blueprint('performers', __name__)

# Performer endpoints:
# - GET /performers              - List performers (supports pagination via limit/offset)
# - GET /performers/index        - Lightweight list (id, name, sort_name only) for alphabet index
# - POST /performers             - Create a new performer
# - GET /performers/<performer_id> - Get performer details
# - GET /performers/search       - Search performers by name

@performers_bp.route('/performers', methods=['GET'])
def get_performers():
    """
    Get performers with optional search and pagination.

    Query Parameters:
        search: Filter performers by name (case-insensitive partial match)
        limit: Maximum number of results to return (default: no limit for backward compat)
        offset: Number of results to skip (default: 0)

    Response Headers:
        X-Total-Count: Total number of matching performers
        X-Has-More: "true" if more results available, "false" otherwise

    Returns:
        Array of performer objects (maintains backward compatibility)
    """
    search_query = request.args.get('search', '')

    # Pagination params - default to no limit for backward compatibility
    limit_param = request.args.get('limit')
    offset = int(request.args.get('offset', 0))

    # If limit specified, cap it at 1000
    limit = min(int(limit_param), 1000) if limit_param else None

    try:
        # Build WHERE clause
        where_clause = "WHERE name ILIKE %s" if search_query else ""
        base_params = (f'%{search_query}%',) if search_query else ()

        # Get total count first
        count_query = f"SELECT COUNT(*) as count FROM performers {where_clause}"
        count_result = db_tools.execute_query(count_query, base_params if base_params else None, fetch_one=True)
        total_count = count_result['count'] if count_result else 0

        # Build main query with pagination
        query = f"""
            SELECT id, name, sort_name, biography, birth_date, death_date,
                external_links, wikipedia_url, musicbrainz_id
            FROM performers
            {where_clause}
            ORDER BY COALESCE(sort_name, name)
        """

        # Add pagination if limit specified
        if limit is not None:
            query += f" LIMIT {limit} OFFSET {offset}"
            params = base_params if base_params else None
        else:
            params = base_params if base_params else None

        performers = db_tools.execute_query(query, params)

        # Build response with pagination headers
        response = jsonify(performers)
        response.headers['X-Total-Count'] = str(total_count)

        if limit is not None:
            has_more = (offset + len(performers)) < total_count
            response.headers['X-Has-More'] = 'true' if has_more else 'false'
        else:
            response.headers['X-Has-More'] = 'false'

        # Allow these headers to be read by JavaScript/iOS clients
        response.headers['Access-Control-Expose-Headers'] = 'X-Total-Count, X-Has-More'

        return response

    except Exception as e:
        logger.error(f"Error fetching performers: {e}")
        return jsonify({'error': 'Failed to fetch performers', 'detail': str(e)}), 500

@performers_bp.route('/performers', methods=['POST'])
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


@performers_bp.route('/performers/<performer_id>', methods=['GET'])
def get_performer_detail(performer_id):
    """Get detailed information about a specific performer - WITH IMAGES"""
    try:
        # Get performer information
        performer_query = """
            SELECT id, name, sort_name, biography, birth_date, death_date,
                external_links, wikipedia_url, musicbrainz_id
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
        
        # Get recordings (album_title, artist_credit, and album art from default release)
        # Support sort parameter: 'year' (default) or 'name' (by song title)
        sort_by = request.args.get('sort', 'year')

        if sort_by == 'name':
            order_clause = "s.title ASC, r.recording_year DESC NULLS LAST"
        else:
            order_clause = "r.recording_year DESC NULLS LAST, s.title ASC"

        recordings_query = f"""
            SELECT DISTINCT s.id as song_id, s.title as song_title,
                   r.id as recording_id, def_rel.title as album_title,
                   def_rel.artist_credit as artist_credit,
                   r.recording_year,
                   r.is_canonical, rp.role,
                   COALESCE(
                       (SELECT ri.image_url_small FROM release_imagery ri
                        WHERE ri.release_id = r.default_release_id AND ri.type = 'Front'),
                       (SELECT rel_sub.cover_art_small FROM releases rel_sub
                        WHERE rel_sub.id = r.default_release_id AND rel_sub.cover_art_small IS NOT NULL),
                       (SELECT ri.image_url_small
                        FROM recording_releases rr_sub
                        JOIN release_imagery ri ON rr_sub.release_id = ri.release_id
                        WHERE rr_sub.recording_id = r.id AND ri.type = 'Front'
                        LIMIT 1),
                       (SELECT rel_sub.cover_art_small
                        FROM recording_releases rr_sub
                        JOIN releases rel_sub ON rr_sub.release_id = rel_sub.id
                        WHERE rr_sub.recording_id = r.id AND rel_sub.cover_art_small IS NOT NULL
                        ORDER BY rel_sub.release_year DESC NULLS LAST LIMIT 1)
                   ) as best_cover_art_small,
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
                   ) as best_cover_art_medium
            FROM recording_performers rp
            JOIN recordings r ON rp.recording_id = r.id
            JOIN songs s ON r.song_id = s.id
            LEFT JOIN releases def_rel ON r.default_release_id = def_rel.id
            WHERE rp.performer_id = %s
            ORDER BY {order_clause}
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


@performers_bp.route('/performers/search', methods=['GET'])
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
                        sort_name,
                        biography,
                        birth_date,
                        death_date,
                        musicbrainz_id
                    FROM performers
                    WHERE LOWER(name) LIKE LOWER(%s)
                    ORDER BY
                        -- Exact matches first
                        CASE WHEN LOWER(name) = LOWER(%s) THEN 0 ELSE 1 END,
                        -- Then by sort_name (falling back to name)
                        COALESCE(sort_name, name)
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
                        'sort_name': performer['sort_name'],
                        'biography': performer['biography'],
                        'birth_date': performer['birth_date'].isoformat() if performer['birth_date'] else None,
                        'death_date': performer['death_date'].isoformat() if performer['death_date'] else None,
                        'musicbrainz_id': performer['musicbrainz_id']
                    })
                
                return jsonify(results)

    except Exception as e:
        logger.error(f"Error searching performers: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@performers_bp.route('/performers/index', methods=['GET'])
def get_performers_index():
    """
    Get lightweight list of all performers for building an alphabet index.

    Returns only id, name, and sort_name - minimal data for fast loading.
    This enables the iOS app to build the full alphabet navigation index
    while loading detailed data progressively.

    Query Parameters:
        search: Filter performers by name (case-insensitive partial match)

    Returns:
        Array of {id, name, sort_name} objects
    """
    search_query = request.args.get('search', '')

    try:
        if search_query:
            query = """
                SELECT id, name, sort_name
                FROM performers
                WHERE name ILIKE %s
                ORDER BY COALESCE(sort_name, name)
            """
            params = (f'%{search_query}%',)
        else:
            query = """
                SELECT id, name, sort_name
                FROM performers
                ORDER BY COALESCE(sort_name, name)
            """
            params = None

        performers = db_tools.execute_query(query, params)

        response = jsonify(performers)
        response.headers['X-Total-Count'] = str(len(performers))

        return response

    except Exception as e:
        logger.error(f"Error fetching performers index: {e}")
        return jsonify({'error': 'Failed to fetch performers index', 'detail': str(e)}), 500
