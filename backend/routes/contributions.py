# routes/contributions.py
"""
Recording Contributions API Routes

CRUD operations for user-contributed recording metadata:
- Performance key (musical key of the recording)
- Tempo (BPM)
- Instrumental/Vocal flag

Contributions are aggregated using simple majority consensus.
"""
from flask import Blueprint, jsonify, request, g
import logging
import db_utils as db_tools
from middleware.auth_middleware import require_auth, optional_auth

logger = logging.getLogger(__name__)
contributions_bp = Blueprint('contributions', __name__)

# Valid performance keys (using flats for consistency)
# Major keys use root note only, minor keys use 'm' suffix
VALID_KEYS = [
    'C', 'Cm', 'Db', 'Dbm', 'D', 'Dm', 'Eb', 'Ebm', 'E', 'Em', 'F', 'Fm',
    'Gb', 'Gbm', 'G', 'Gm', 'Ab', 'Abm', 'A', 'Am', 'Bb', 'Bbm', 'B', 'Bm'
]

# Valid tempo markings (standard jazz terms)
VALID_TEMPO_MARKINGS = ['Ballad', 'Slow', 'Medium', 'Medium-Up', 'Up-Tempo', 'Fast', 'Burning']

# Tempo range constraints (kept for backward compatibility)
MIN_TEMPO = 40
MAX_TEMPO = 400


def get_consensus_data(recording_id):
    """
    Calculate consensus values for a recording's community-contributed metadata.

    Uses simple majority (mode) for key, tempo marking, and instrumental/vocal.
    Ties are broken by most recent update.

    Returns dict with consensus values and counts.
    """
    query = """
        SELECT
            -- Mode for performance_key (most common, ties broken by most recent)
            (SELECT performance_key
             FROM recording_contributions
             WHERE recording_id = %s AND performance_key IS NOT NULL
             GROUP BY performance_key
             ORDER BY COUNT(*) DESC, MAX(updated_at) DESC
             LIMIT 1) as consensus_key,

            -- Mode for tempo_marking (most common, ties broken by most recent)
            (SELECT tempo_marking
             FROM recording_contributions
             WHERE recording_id = %s AND tempo_marking IS NOT NULL
             GROUP BY tempo_marking
             ORDER BY COUNT(*) DESC, MAX(updated_at) DESC
             LIMIT 1) as consensus_tempo_marking,

            -- Mode for is_instrumental (most common, ties broken by most recent)
            (SELECT is_instrumental
             FROM recording_contributions
             WHERE recording_id = %s AND is_instrumental IS NOT NULL
             GROUP BY is_instrumental
             ORDER BY COUNT(*) DESC, MAX(updated_at) DESC
             LIMIT 1) as consensus_instrumental,

            -- Contribution counts per field
            (SELECT COUNT(*) FROM recording_contributions
             WHERE recording_id = %s AND performance_key IS NOT NULL) as key_count,
            (SELECT COUNT(*) FROM recording_contributions
             WHERE recording_id = %s AND tempo_marking IS NOT NULL) as tempo_count,
            (SELECT COUNT(*) FROM recording_contributions
             WHERE recording_id = %s AND is_instrumental IS NOT NULL) as instrumental_count
    """

    result = db_tools.execute_query(
        query,
        (recording_id, recording_id, recording_id, recording_id, recording_id, recording_id),
        fetch_one=True
    )

    if not result:
        return {
            'consensus': {
                'performance_key': None,
                'tempo_marking': None,
                'is_instrumental': None
            },
            'counts': {
                'key': 0,
                'tempo': 0,
                'instrumental': 0
            }
        }

    return {
        'consensus': {
            'performance_key': result['consensus_key'],
            'tempo_marking': result['consensus_tempo_marking'],
            'is_instrumental': result['consensus_instrumental']
        },
        'counts': {
            'key': result['key_count'] or 0,
            'tempo': result['tempo_count'] or 0,
            'instrumental': result['instrumental_count'] or 0
        }
    }


def get_user_contribution(recording_id, user_id):
    """Get a specific user's contribution for a recording."""
    query = """
        SELECT
            performance_key,
            tempo_marking,
            is_instrumental,
            updated_at
        FROM recording_contributions
        WHERE recording_id = %s AND user_id = %s
    """
    return db_tools.execute_query(query, (recording_id, user_id), fetch_one=True)


@contributions_bp.route('/recordings/<recording_id>/community-data', methods=['GET'])
@optional_auth
def get_community_data(recording_id):
    """
    Get community-contributed metadata for a recording.

    Returns consensus values calculated from all user contributions,
    plus contribution counts. If authenticated, also includes the
    current user's contribution.

    Response:
    {
        "consensus": {
            "performance_key": "Eb",
            "tempo_marking": "Medium-Up",
            "is_instrumental": true
        },
        "counts": {
            "key": 15,
            "tempo": 12,
            "instrumental": 18
        },
        "user_contribution": {  // Only if authenticated
            "performance_key": "Eb",
            "tempo_marking": "Medium-Up",
            "is_instrumental": true,
            "updated_at": "2025-01-10T14:30:00Z"
        }
    }
    """
    try:
        # Verify recording exists
        recording = db_tools.execute_query(
            "SELECT id FROM recordings WHERE id = %s",
            (recording_id,),
            fetch_one=True
        )
        if not recording:
            return jsonify({'error': 'Recording not found'}), 404

        # Get consensus data
        response = get_consensus_data(recording_id)

        # Add user's contribution if authenticated
        if hasattr(g, 'current_user') and g.current_user:
            user_contribution = get_user_contribution(recording_id, g.current_user['id'])
            if user_contribution:
                response['user_contribution'] = {
                    'performance_key': user_contribution['performance_key'],
                    'tempo_marking': user_contribution['tempo_marking'],
                    'is_instrumental': user_contribution['is_instrumental'],
                    'updated_at': user_contribution['updated_at'].isoformat() if user_contribution['updated_at'] else None
                }
            else:
                response['user_contribution'] = None

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error fetching community data for recording {recording_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch community data'}), 500


@contributions_bp.route('/recordings/<recording_id>/contribution', methods=['PUT'])
@require_auth
def upsert_contribution(recording_id):
    """
    Create or update the current user's contribution for a recording.

    Request body (all fields optional):
    {
        "performance_key": "Eb",      // Must be valid key (with optional 'm' for minor) or null
        "tempo_marking": "Medium-Up", // Must be valid tempo marking or null
        "is_instrumental": true       // Boolean or null
    }

    Response:
    {
        "user_contribution": { ... },
        "consensus": { ... },
        "counts": { ... }
    }
    """
    try:
        # Verify recording exists
        recording = db_tools.execute_query(
            "SELECT id FROM recordings WHERE id = %s",
            (recording_id,),
            fetch_one=True
        )
        if not recording:
            return jsonify({'error': 'Recording not found'}), 404

        data = request.get_json() or {}
        user_id = g.current_user['id']

        # Validate performance_key
        performance_key = data.get('performance_key')
        if performance_key is not None and performance_key not in VALID_KEYS:
            return jsonify({
                'error': f'Invalid performance_key. Must be one of: {", ".join(VALID_KEYS)}'
            }), 400

        # Validate tempo_marking
        tempo_marking = data.get('tempo_marking')
        if tempo_marking is not None and tempo_marking not in VALID_TEMPO_MARKINGS:
            return jsonify({
                'error': f'Invalid tempo_marking. Must be one of: {", ".join(VALID_TEMPO_MARKINGS)}'
            }), 400

        # Validate is_instrumental
        is_instrumental = data.get('is_instrumental')
        if is_instrumental is not None and not isinstance(is_instrumental, bool):
            return jsonify({'error': 'is_instrumental must be a boolean'}), 400

        # Upsert the contribution
        upsert_query = """
            INSERT INTO recording_contributions (recording_id, user_id, performance_key, tempo_marking, is_instrumental)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, recording_id)
            DO UPDATE SET
                performance_key = EXCLUDED.performance_key,
                tempo_marking = EXCLUDED.tempo_marking,
                is_instrumental = EXCLUDED.is_instrumental,
                updated_at = CURRENT_TIMESTAMP
            RETURNING performance_key, tempo_marking, is_instrumental, updated_at
        """

        result = db_tools.execute_query(
            upsert_query,
            (recording_id, user_id, performance_key, tempo_marking, is_instrumental),
            fetch_one=True
        )

        # Get updated consensus
        response = get_consensus_data(recording_id)
        response['user_contribution'] = {
            'performance_key': result['performance_key'],
            'tempo_marking': result['tempo_marking'],
            'is_instrumental': result['is_instrumental'],
            'updated_at': result['updated_at'].isoformat() if result['updated_at'] else None
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error saving contribution for recording {recording_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to save contribution'}), 500


@contributions_bp.route('/recordings/<recording_id>/contribution', methods=['DELETE'])
@require_auth
def delete_contribution(recording_id):
    """
    Delete the current user's entire contribution for a recording.

    Response:
    {
        "message": "Contribution deleted",
        "consensus": { ... },
        "counts": { ... }
    }
    """
    try:
        user_id = g.current_user['id']

        # Delete the contribution
        delete_query = """
            DELETE FROM recording_contributions
            WHERE recording_id = %s AND user_id = %s
            RETURNING id
        """

        result = db_tools.execute_query(
            delete_query,
            (recording_id, user_id),
            fetch_one=True
        )

        if not result:
            return jsonify({'error': 'No contribution found to delete'}), 404

        # Get updated consensus
        response = get_consensus_data(recording_id)
        response['message'] = 'Contribution deleted'

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error deleting contribution for recording {recording_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete contribution'}), 500


@contributions_bp.route('/users/me/contribution-stats', methods=['GET'])
@require_auth
def get_user_contribution_stats():
    """
    Get contribution statistics for the current authenticated user.

    Returns counts of all contributions made by the user:
    - transcriptions: Number of solo transcriptions submitted
    - backing_tracks: Number of backing track videos submitted
    - tempo_markings: Number of tempo marking contributions
    - instrumental_vocal: Number of instrumental/vocal contributions
    - keys: Number of performance key contributions

    Response:
    {
        "transcriptions": 5,
        "backing_tracks": 3,
        "tempo_markings": 12,
        "instrumental_vocal": 15,
        "keys": 10
    }
    """
    try:
        user_id = g.current_user['id']

        # Query all contribution counts for this user
        query = """
            SELECT
                -- Transcriptions submitted by this user
                (SELECT COUNT(*) FROM solo_transcriptions
                 WHERE created_by = %s) as transcription_count,

                -- Backing tracks submitted by this user
                (SELECT COUNT(*) FROM videos
                 WHERE created_by = %s AND video_type = 'backing_track') as backing_track_count,

                -- Recording contribution fields
                (SELECT COUNT(*) FROM recording_contributions
                 WHERE user_id = %s AND tempo_marking IS NOT NULL) as tempo_count,

                (SELECT COUNT(*) FROM recording_contributions
                 WHERE user_id = %s AND is_instrumental IS NOT NULL) as instrumental_count,

                (SELECT COUNT(*) FROM recording_contributions
                 WHERE user_id = %s AND performance_key IS NOT NULL) as key_count
        """

        result = db_tools.execute_query(
            query,
            (user_id, user_id, user_id, user_id, user_id),
            fetch_one=True
        )

        if not result:
            return jsonify({
                'transcriptions': 0,
                'backing_tracks': 0,
                'tempo_markings': 0,
                'instrumental_vocal': 0,
                'keys': 0
            })

        return jsonify({
            'transcriptions': result['transcription_count'] or 0,
            'backing_tracks': result['backing_track_count'] or 0,
            'tempo_markings': result['tempo_count'] or 0,
            'instrumental_vocal': result['instrumental_count'] or 0,
            'keys': result['key_count'] or 0
        })

    except Exception as e:
        logger.error(f"Error fetching user contribution stats: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch contribution stats'}), 500


@contributions_bp.route('/recordings/<recording_id>/contribution/<field>', methods=['DELETE'])
@require_auth
def delete_contribution_field(recording_id, field):
    """
    Clear a specific field from the current user's contribution.

    Path parameters:
        field: 'key', 'tempo', or 'instrumental'

    Response:
    {
        "user_contribution": { ... },
        "consensus": { ... },
        "counts": { ... }
    }
    """
    # Map field names to column names
    field_map = {
        'key': 'performance_key',
        'tempo': 'tempo_marking',
        'instrumental': 'is_instrumental'
    }

    if field not in field_map:
        return jsonify({
            'error': f'Invalid field. Must be one of: {", ".join(field_map.keys())}'
        }), 400

    column_name = field_map[field]

    try:
        user_id = g.current_user['id']

        # Update the specific field to NULL
        update_query = f"""
            UPDATE recording_contributions
            SET {column_name} = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE recording_id = %s AND user_id = %s
            RETURNING performance_key, tempo_marking, is_instrumental, updated_at
        """

        result = db_tools.execute_query(
            update_query,
            (recording_id, user_id),
            fetch_one=True
        )

        if not result:
            return jsonify({'error': 'No contribution found'}), 404

        # Check if all fields are now NULL - if so, delete the row entirely
        if result['performance_key'] is None and result['tempo_marking'] is None and result['is_instrumental'] is None:
            db_tools.execute_query(
                "DELETE FROM recording_contributions WHERE recording_id = %s AND user_id = %s",
                (recording_id, user_id)
            )
            user_contribution = None
        else:
            user_contribution = {
                'performance_key': result['performance_key'],
                'tempo_marking': result['tempo_marking'],
                'is_instrumental': result['is_instrumental'],
                'updated_at': result['updated_at'].isoformat() if result['updated_at'] else None
            }

        # Get updated consensus
        response = get_consensus_data(recording_id)
        response['user_contribution'] = user_contribution

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error clearing contribution field for recording {recording_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to clear contribution field'}), 500
