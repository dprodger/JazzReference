# routes/research.py
from flask import Blueprint, jsonify
import logging
import db_utils as db_tools
import research_queue

logger = logging.getLogger(__name__)
research_bp = Blueprint('research', __name__)

@research_bp.route('/api/songs/<song_id>/refresh', methods=['POST'])
def refresh_song_data(song_id):
    """
    Queue a song for background research and data refresh
    
    This endpoint accepts a song ID and adds it to the background processing
    queue. The actual research happens asynchronously in a worker thread.
    
    Args:
        song_id: UUID of the song to research
        
    Returns:
        JSON response with queue status
    """
    try:
        # First verify the song exists and get its name
        query = "SELECT id, title FROM songs WHERE id = %s"
        song = db_tools.execute_query(query, (song_id,), fetch_one=True)
        
        if not song:
            return jsonify({
                'error': 'Song not found',
                'song_id': song_id
            }), 404
        
        # Add to research queue
        success = research_queue.add_song_to_queue(song['id'], song['title'])
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Song queued for research',
                'song_id': song['id'],
                'song_title': song['title'],
                'queue_size': research_queue.get_queue_size()
            }), 202  # 202 Accepted - processing will happen asynchronously
        else:
            return jsonify({
                'error': 'Failed to queue song',
                'song_id': song_id
            }), 500
            
    except Exception as e:
        logger.error(f"Error queueing song {song_id} for research: {e}")
        return jsonify({
            'error': 'Internal server error',
            'detail': str(e)
        }), 500

@research_bp.route('/api/research/queue', methods=['GET'])
def get_queue_status():
    """Get the current status of the research queue"""
    return jsonify({
        'queue_size': research_queue.get_queue_size(),
        'worker_active': research_queue._worker_running
    })
    

