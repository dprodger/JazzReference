# routes/images.py
from flask import Blueprint, jsonify
import logging
import db_utils as db_tools

logger = logging.getLogger(__name__)
images_bp = Blueprint('images', __name__)

# Image endpoints:
# - GET /api/performers/<performer_id>/images
# - GET /api/images/<image_id>
@images_bp.route('/api/performers/<performer_id>/images', methods=['GET'])
def get_performer_images(performer_id):
    """Get all images for a specific performer"""
    try:
        # Get all images for this performer with join data
        query = """
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
        
        images = db_tools.execute_query(query, (performer_id,), fetch_all=True)
        
        if not images:
            return jsonify([])
        
        return jsonify(images)
        
    except Exception as e:
        logger.error(f"Error fetching performer images: {e}")
        return jsonify({'error': 'Failed to fetch performer images', 'detail': str(e)}), 500


@images_bp.route('/api/images/<image_id>', methods=['GET'])
def get_image_detail(image_id):
    """Get detailed information about a specific image"""
    try:
        query = """
            SELECT 
                i.*,
                COALESCE(
                    json_agg(
                        json_build_object(
                            'performer_id', p.id,
                            'performer_name', p.name,
                            'is_primary', ai.is_primary,
                            'display_order', ai.display_order
                        ) ORDER BY ai.is_primary DESC, ai.display_order
                    ) FILTER (WHERE p.id IS NOT NULL),
                    '[]'::json
                ) as performers
            FROM images i
            LEFT JOIN artist_images ai ON i.id = ai.image_id
            LEFT JOIN performers p ON ai.performer_id = p.id
            WHERE i.id = %s
            GROUP BY i.id
        """
        
        image = db_tools.execute_query(query, (image_id,), fetch_one=True)
        
        if not image:
            return jsonify({'error': 'Image not found'}), 404
        
        return jsonify(image)
        
    except Exception as e:
        logger.error(f"Error fetching image detail: {e}")
        return jsonify({'error': 'Failed to fetch image detail', 'detail': str(e)}), 500


