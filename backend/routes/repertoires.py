# routes/repertoires.py
from flask import Blueprint, jsonify, request
import logging
import db_utils as db_tools

logger = logging.getLogger(__name__)
repertoires_bp = Blueprint('repertoires', __name__)

# Repertoire endpoints:
# - GET /api/repertoires
# - GET /api/repertoires/<repertoire_id>
# - GET /api/repertoires/<repertoire_id>/songs
# - POST /api/repertoires/<repertoire_id>/songs/<song_id>
# - DELETE /api/repertoires/<repertoire_id>/songs/<song_id>

"""
Repertoire API Endpoints
Add these endpoints to backend/app.py

These endpoints support viewing and managing repertoires (collections of songs).
In Phase 1, we implement GET endpoints for listing and viewing repertoires.
"""

# =============================================================================
# REPERTOIRE ENDPOINTS
# =============================================================================

@repertoires_bp.route('/api/repertoires', methods=['GET'])
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


@repertoires_bp.route('/api/repertoires/<repertoire_id>', methods=['GET'])
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


@repertoires_bp.route('/api/repertoires/<repertoire_id>/songs', methods=['GET'])
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

@repertoires_bp.route('/api/repertoires', methods=['POST'])
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


@repertoires_bp.route('/api/repertoires/<repertoire_id>', methods=['PUT'])
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


@repertoires_bp.route('/api/repertoires/<repertoire_id>', methods=['DELETE'])
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


@repertoires_bp.route('/api/repertoires/<repertoire_id>/songs', methods=['POST'])
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


@repertoires_bp.route('/api/repertoires/<repertoire_id>/songs/<song_id>', methods=['DELETE'])
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

