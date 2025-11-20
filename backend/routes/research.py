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
  
# Add this route to routes/research.py

@research_bp.route('/api/admin/research/queue-all-songs', methods=['POST'])
def queue_all_songs_for_research():
    """
    Admin endpoint to queue all songs in the database for research
    
    This endpoint queries all songs from the database and adds each one
    to the background research queue for data refresh.
    
    Returns:
        JSON response with summary statistics
    """
    try:
        # Query all songs from database
        query = """
            SELECT id, title 
            FROM songs 
            ORDER BY title
        """
        songs = db_tools.execute_query(query)
        
        if not songs:
            return jsonify({
                'success': True,
                'message': 'No songs found in database',
                'songs_queued': 0,
                'queue_size': research_queue.get_queue_size()
            }), 200
        
        # Queue each song for research
        queued_count = 0
        failed_songs = []
        
        for song in songs:
            success = research_queue.add_song_to_queue(song['id'], song['title'])
            if success:
                queued_count += 1
            else:
                failed_songs.append({
                    'id': song['id'],
                    'title': song['title']
                })
        
        # Prepare response
        response_data = {
            'success': True,
            'message': f'Queued {queued_count} songs for research',
            'total_songs': len(songs),
            'songs_queued': queued_count,
            'songs_failed': len(failed_songs),
            'queue_size': research_queue.get_queue_size()
        }
        
        # Include failed songs if any
        if failed_songs:
            response_data['failed_songs'] = failed_songs
            logger.warning(f"Failed to queue {len(failed_songs)} songs")
        
        logger.info(f"Admin: Queued {queued_count}/{len(songs)} songs for research")
        
        return jsonify(response_data), 202  # 202 Accepted - processing will happen asynchronously
        
    except Exception as e:
        logger.error(f"Error queuing all songs for research: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'detail': str(e)
        }), 500    

