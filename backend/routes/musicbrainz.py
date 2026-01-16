# routes/musicbrainz.py
"""
MusicBrainz API routes for searching and importing works
"""

from flask import Blueprint, jsonify, request
import logging
import db_utils as db_tools
import research_queue
from mb_utils import MusicBrainzSearcher

logger = logging.getLogger(__name__)
musicbrainz_bp = Blueprint('musicbrainz', __name__)

# Shared MusicBrainz searcher instance
_mb_searcher = None


def get_mb_searcher():
    """Get or create a shared MusicBrainzSearcher instance"""
    global _mb_searcher
    if _mb_searcher is None:
        _mb_searcher = MusicBrainzSearcher()
    return _mb_searcher


@musicbrainz_bp.route('/musicbrainz/works/search', methods=['GET'])
def search_musicbrainz_works():
    """
    Search MusicBrainz for works (songs) by title.

    Query Parameters:
        q (str, required): Search query (song title)
        limit (int, optional): Maximum results to return (default 5, max 10)

    Returns:
        JSON with results array containing:
        - id: MusicBrainz work UUID
        - title: Work title
        - composers: Array of composer names (may be null)
        - score: Match score (0-100)
        - type: Work type (e.g., "Song")
        - musicbrainz_url: URL to MusicBrainz page
    """
    query = request.args.get('q', '').strip()

    if not query:
        return jsonify({
            'error': 'Missing required parameter: q',
            'results': []
        }), 400

    # Get and validate limit
    limit = request.args.get('limit', 5, type=int)
    limit = max(1, min(limit, 10))  # Clamp between 1 and 10

    try:
        searcher = get_mb_searcher()
        results = searcher.search_works_multi(query, limit=limit)

        return jsonify({
            'query': query,
            'results': results
        }), 200

    except Exception as e:
        logger.error(f"Error searching MusicBrainz: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to search MusicBrainz',
            'detail': str(e),
            'results': []
        }), 500


@musicbrainz_bp.route('/musicbrainz/import', methods=['POST'])
def import_from_musicbrainz():
    """
    Import a song from MusicBrainz into the database and queue for research.

    Request Body (JSON):
        musicbrainz_id (str, required): MusicBrainz work UUID
        title (str, required): Song title
        composer (str, optional): Composer name(s)

    Returns:
        JSON with created song data and queue status
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        musicbrainz_id = data.get('musicbrainz_id', '').strip()
        title = data.get('title', '').strip()
        composer = data.get('composer', '').strip() if data.get('composer') else None

        if not musicbrainz_id:
            return jsonify({'error': 'musicbrainz_id is required'}), 400

        if not title:
            return jsonify({'error': 'title is required'}), 400

        # Check if song with this MusicBrainz ID already exists
        existing_query = "SELECT id, title FROM songs WHERE musicbrainz_id = %s"
        existing = db_tools.execute_query(existing_query, (musicbrainz_id,), fetch_one=True)

        if existing:
            return jsonify({
                'error': 'Song with this MusicBrainz ID already exists',
                'existing_song': {
                    'id': str(existing['id']),
                    'title': existing['title']
                }
            }), 409  # Conflict

        # Build INSERT query
        fields = ['title', 'musicbrainz_id']
        values = [title, musicbrainz_id]
        placeholders = ['%s', '%s']

        if composer:
            fields.append('composer')
            values.append(composer)
            placeholders.append('%s')

        query = f"""
            INSERT INTO songs ({', '.join(fields)})
            VALUES ({', '.join(placeholders)})
            RETURNING id, title, composer, musicbrainz_id, created_at, updated_at
        """

        result = db_tools.execute_query(query, values, fetch_one=True)
        song_id = str(result['id'])

        logger.info(f"Created song from MusicBrainz: {title} (ID: {song_id}, MB: {musicbrainz_id})")

        # Queue for background research
        queued = research_queue.add_song_to_queue(song_id, title)

        return jsonify({
            'success': True,
            'message': 'Song imported and queued for research',
            'song': {
                'id': song_id,
                'title': result['title'],
                'composer': result['composer'],
                'musicbrainz_id': result['musicbrainz_id'],
                'created_at': result['created_at'].isoformat() if result['created_at'] else None,
                'updated_at': result['updated_at'].isoformat() if result['updated_at'] else None
            },
            'research_queued': queued,
            'queue_size': research_queue.get_queue_size()
        }), 201

    except Exception as e:
        logger.error(f"Error importing from MusicBrainz: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to import song',
            'detail': str(e)
        }), 500
