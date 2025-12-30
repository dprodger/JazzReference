"""
Recording Favorites Routes

This module handles user favorite recording operations:
- GET /favorites - List user's favorited recordings (requires auth)
- POST /recordings/<id>/favorite - Add recording to favorites (requires auth)
- DELETE /recordings/<id>/favorite - Remove recording from favorites (requires auth)
- GET /recordings/<id>/favorites - Get favorite count & users who favorited (optional auth)
"""

from flask import Blueprint, jsonify, g
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_utils import get_db_connection
from middleware.auth_middleware import require_auth, optional_auth

logger = logging.getLogger(__name__)
favorites_bp = Blueprint('favorites', __name__)


# =============================================================================
# USER'S FAVORITES
# =============================================================================

@favorites_bp.route('/favorites', methods=['GET'])
@require_auth
def get_user_favorites():
    """
    Get all favorite recordings for the authenticated user

    Returns:
        200: [
            {
                "id": "uuid",
                "song_title": "All The Things You Are",
                "album_title": "The Complete...",
                "recording_year": 1955,
                "best_album_art_small": "https://...",
                "favorited_at": "2025-01-15T10:30:00Z"
            },
            ...
        ]
        500: Server error
    """
    user_id = g.current_user['id']

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        r.id,
                        s.title as song_title,
                        rl.title as album_title,
                        r.recording_year,
                        COALESCE(
                            ri.image_url_small,
                            rl.cover_art_small
                        ) as best_album_art_small,
                        rf.created_at as favorited_at
                    FROM recording_favorites rf
                    INNER JOIN recordings r ON rf.recording_id = r.id
                    LEFT JOIN songs s ON r.song_id = s.id
                    LEFT JOIN releases rl ON r.default_release_id = rl.id
                    LEFT JOIN release_imagery ri ON rl.id = ri.release_id AND ri.type = 'Front'
                    WHERE rf.user_id = %s
                    ORDER BY rf.created_at DESC
                """, (user_id,))

                favorites = cur.fetchall()

                # Convert to JSON-serializable format
                result = []
                for fav in favorites:
                    result.append({
                        'id': str(fav['id']),
                        'song_title': fav['song_title'],
                        'album_title': fav['album_title'],
                        'recording_year': fav['recording_year'],
                        'best_album_art_small': fav['best_album_art_small'],
                        'favorited_at': fav['favorited_at'].isoformat() if fav['favorited_at'] else None
                    })

                return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error fetching favorites: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch favorites'}), 500


# =============================================================================
# FAVORITE/UNFAVORITE RECORDING
# =============================================================================

@favorites_bp.route('/recordings/<recording_id>/favorite', methods=['POST'])
@require_auth
def add_favorite(recording_id):
    """
    Add a recording to user's favorites

    Returns:
        201: {"message": "Recording added to favorites", "favorite_count": N}
        404: Recording not found
        409: Already favorited
        500: Server error
    """
    user_id = g.current_user['id']

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Verify recording exists
                cur.execute("SELECT id FROM recordings WHERE id = %s", (recording_id,))
                if not cur.fetchone():
                    return jsonify({'error': 'Recording not found'}), 404

                # Check if already favorited
                cur.execute("""
                    SELECT id FROM recording_favorites
                    WHERE recording_id = %s AND user_id = %s
                """, (recording_id, user_id))

                if cur.fetchone():
                    return jsonify({'error': 'Recording already favorited'}), 409

                # Add to favorites
                cur.execute("""
                    INSERT INTO recording_favorites (recording_id, user_id)
                    VALUES (%s, %s)
                """, (recording_id, user_id))

                # Get updated favorite count
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM recording_favorites
                    WHERE recording_id = %s
                """, (recording_id,))
                count = cur.fetchone()['count']

                conn.commit()

                logger.info(f"User {user_id} favorited recording {recording_id}")

                return jsonify({
                    'message': 'Recording added to favorites',
                    'favorite_count': count
                }), 201

    except Exception as e:
        logger.error(f"Error adding favorite: {e}", exc_info=True)
        return jsonify({'error': 'Failed to add favorite'}), 500


@favorites_bp.route('/recordings/<recording_id>/favorite', methods=['DELETE'])
@require_auth
def remove_favorite(recording_id):
    """
    Remove a recording from user's favorites

    Returns:
        200: {"message": "Recording removed from favorites", "favorite_count": N}
        404: Recording not found or not favorited
        500: Server error
    """
    user_id = g.current_user['id']

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Remove from favorites
                cur.execute("""
                    DELETE FROM recording_favorites
                    WHERE recording_id = %s AND user_id = %s
                    RETURNING id
                """, (recording_id, user_id))

                result = cur.fetchone()

                if not result:
                    return jsonify({'error': 'Recording not in favorites'}), 404

                # Get updated favorite count
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM recording_favorites
                    WHERE recording_id = %s
                """, (recording_id,))
                count = cur.fetchone()['count']

                conn.commit()

                logger.info(f"User {user_id} unfavorited recording {recording_id}")

                return jsonify({
                    'message': 'Recording removed from favorites',
                    'favorite_count': count
                }), 200

    except Exception as e:
        logger.error(f"Error removing favorite: {e}", exc_info=True)
        return jsonify({'error': 'Failed to remove favorite'}), 500


# =============================================================================
# GET FAVORITE INFO FOR A RECORDING
# =============================================================================

@favorites_bp.route('/recordings/<recording_id>/favorites', methods=['GET'])
@optional_auth
def get_recording_favorites(recording_id):
    """
    Get favorite count and users who favorited a recording

    For authenticated users, also includes is_favorited flag

    Returns:
        200: {
            "favorite_count": 12,
            "is_favorited": true,  // only if authenticated
            "favorited_by": [
                {"id": "uuid", "display_name": "John Doe"},
                ...
            ]
        }
        404: Recording not found
        500: Server error
    """
    current_user_id = g.current_user['id'] if hasattr(g, 'current_user') else None

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Verify recording exists
                cur.execute("SELECT id FROM recordings WHERE id = %s", (recording_id,))
                if not cur.fetchone():
                    return jsonify({'error': 'Recording not found'}), 404

                # Get favorite count
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM recording_favorites
                    WHERE recording_id = %s
                """, (recording_id,))
                count = cur.fetchone()['count']

                # Get users who favorited (limited to 50)
                cur.execute("""
                    SELECT
                        u.id,
                        u.display_name
                    FROM recording_favorites rf
                    INNER JOIN users u ON rf.user_id = u.id
                    WHERE rf.recording_id = %s
                    ORDER BY rf.created_at DESC
                    LIMIT 50
                """, (recording_id,))

                favorited_by = [dict(user) for user in cur.fetchall()]

                result = {
                    'favorite_count': count,
                    'favorited_by': favorited_by
                }

                # Check if current user has favorited (only if authenticated)
                if current_user_id:
                    cur.execute("""
                        SELECT id FROM recording_favorites
                        WHERE recording_id = %s AND user_id = %s
                    """, (recording_id, current_user_id))
                    result['is_favorited'] = cur.fetchone() is not None

                return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error fetching recording favorites: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch favorites'}), 500
