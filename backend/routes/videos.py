# routes/videos.py
from flask import Blueprint, jsonify, request
import logging
import db_utils as db_tools

logger = logging.getLogger(__name__)
videos_bp = Blueprint('videos', __name__)


@videos_bp.route('/videos', methods=['POST'])
def create_video():
    """Create a new video (backing track, performance, etc.)"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        song_id = data.get('song_id')
        recording_id = data.get('recording_id')  # Optional
        youtube_url = data.get('youtube_url')
        video_type = data.get('video_type')
        title = data.get('title')
        description = data.get('description')

        if not youtube_url:
            return jsonify({'error': 'youtube_url is required'}), 400
        if not video_type:
            return jsonify({'error': 'video_type is required'}), 400

        # Validate video_type
        valid_types = ['performance', 'transcription', 'educational', 'backing_track']
        if video_type not in valid_types:
            return jsonify({'error': f'video_type must be one of: {", ".join(valid_types)}'}), 400

        # At least one of song_id or recording_id must be provided
        if not song_id and not recording_id:
            return jsonify({'error': 'Either song_id or recording_id is required'}), 400

        # Validate song exists if provided
        if song_id:
            song_check = db_tools.execute_query(
                "SELECT id FROM songs WHERE id = %s",
                (song_id,),
                fetch_one=True
            )
            if not song_check:
                return jsonify({'error': 'Song not found'}), 404

        # Validate recording exists if provided
        if recording_id:
            recording_check = db_tools.execute_query(
                "SELECT id, song_id FROM recordings WHERE id = %s",
                (recording_id,),
                fetch_one=True
            )
            if not recording_check:
                return jsonify({'error': 'Recording not found'}), 404
            # If song_id not provided, get it from the recording
            if not song_id:
                song_id = recording_check['song_id']

        # Check for duplicate video (same youtube URL)
        duplicate_check = db_tools.execute_query(
            "SELECT id FROM videos WHERE youtube_url = %s",
            (youtube_url,),
            fetch_one=True
        )
        if duplicate_check:
            return jsonify({'error': 'A video with this YouTube URL already exists'}), 409

        # Create the video using direct connection for INSERT
        with db_tools.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO videos (song_id, recording_id, youtube_url, video_type, title, description)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, song_id, recording_id, youtube_url, video_type, title, description, created_at
                """, (song_id, recording_id, youtube_url, video_type, title, description))

                result = cur.fetchone()
                conn.commit()

        if not result:
            return jsonify({'error': 'Failed to create video'}), 500

        logger.info(f"Created video {result['id']} ({video_type}) for song {song_id}")

        return jsonify({
            'message': 'Video created successfully',
            'video': dict(result)
        }), 201

    except Exception as e:
        logger.error(f"Error creating video: {e}")
        return jsonify({'error': 'Failed to create video', 'detail': str(e)}), 500


@videos_bp.route('/songs/<song_id>/videos', methods=['GET'])
def get_song_videos(song_id):
    """Get all videos for a specific song"""
    try:
        video_type = request.args.get('type')  # Optional filter by type

        query = """
            SELECT
                v.id,
                v.song_id,
                v.recording_id,
                v.youtube_url,
                v.title,
                v.description,
                v.video_type,
                v.duration_seconds,
                v.created_at,
                v.updated_at
            FROM videos v
            WHERE v.song_id = %s
        """
        params = [song_id]

        if video_type:
            query += " AND v.video_type = %s"
            params.append(video_type)

        query += " ORDER BY v.created_at DESC"

        videos = db_tools.execute_query(query, tuple(params), fetch_all=True)

        if not videos:
            return jsonify([])

        return jsonify(videos)

    except Exception as e:
        logger.error(f"Error fetching song videos: {e}")
        return jsonify({'error': 'Failed to fetch videos', 'detail': str(e)}), 500
