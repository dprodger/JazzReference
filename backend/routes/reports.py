# routes/reports.py
from flask import Blueprint, jsonify, request
import logging
import db_utils as db_tools

logger = logging.getLogger(__name__)
reports_bp = Blueprint('reports', __name__)

# Report endpoints:
# - POST /content-reports

@reports_bp.route('/content-reports', methods=['POST'])
def submit_content_report():
    """Submit a content error report"""
    try:
        # Get JSON data from request
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['entity_type', 'entity_id', 'entity_name', 
                          'external_source', 'external_url', 'explanation']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        # Validate entity_type
        valid_entity_types = ['song', 'performer', 'recording']
        if data['entity_type'].lower() not in valid_entity_types:
            return jsonify({
                'success': False,
                'error': f'Invalid entity_type. Must be one of: {", ".join(valid_entity_types)}'
            }), 400
        
        # Get optional fields with defaults
        report_category = data.get('report_category', 'link_issue')
        reporter_platform = data.get('reporter_platform')
        reporter_app_version = data.get('reporter_app_version')
        
        # Get client IP and user agent
        reporter_ip = request.remote_addr
        reporter_user_agent = request.headers.get('User-Agent')
        
        # Insert into database
        with db_tools.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO content_reports (
                        entity_type,
                        entity_id,
                        entity_name,
                        report_category,
                        external_source,
                        external_url,
                        explanation,
                        reporter_ip,
                        reporter_user_agent,
                        reporter_platform,
                        reporter_app_version
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING id, created_at
                """, (
                    data['entity_type'].lower(),
                    data['entity_id'],
                    data['entity_name'],
                    report_category,
                    data['external_source'],
                    data['external_url'],
                    data['explanation'],
                    reporter_ip,
                    reporter_user_agent,
                    reporter_platform,
                    reporter_app_version
                ))
                
                result = cur.fetchone()
                report_id = result['id']
                created_at = result['created_at'].isoformat()
        
        logger.info(f"Content report created: {report_id} for {data['entity_type']} {data['entity_id']}")
        
        return jsonify({
            'success': True,
            'report_id': str(report_id),
            'created_at': created_at,
            'message': 'Thank you for your report. We will review it shortly.'
        }), 201
        
    except KeyError as e:
        logger.error(f"Missing data field: {e}")
        return jsonify({
            'success': False,
            'error': f'Invalid request data: {str(e)}'
        }), 400
        
    except Exception as e:
        logger.error(f"Error submitting content report: {e}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while submitting your report. Please try again later.'
        }), 500


@reports_bp.route('/content-reports', methods=['GET'])
def get_content_reports():
    """
    Get content reports (for admin use)
    Query parameters:
    - status: Filter by status (pending, reviewing, resolved, dismissed, duplicate)
    - entity_type: Filter by entity type (song, performer, recording)
    - entity_id: Filter by specific entity ID
    - limit: Number of results (default 50)
    """
    try:
        # Get query parameters
        status = request.args.get('status', 'pending')
        entity_type = request.args.get('entity_type')
        entity_id = request.args.get('entity_id')
        limit = min(int(request.args.get('limit', 50)), 200)  # Max 200
        
        # Build query
        query = """
            SELECT 
                id,
                entity_type,
                entity_id,
                entity_name,
                report_category,
                external_source,
                external_url,
                explanation,
                status,
                priority,
                resolution_notes,
                resolution_action,
                created_at,
                updated_at,
                reviewed_at,
                resolved_at
            FROM content_reports
            WHERE 1=1
        """
        params = []
        
        if status:
            query += " AND status = %s"
            params.append(status)
        
        if entity_type:
            query += " AND entity_type = %s"
            params.append(entity_type.lower())
        
        if entity_id:
            query += " AND entity_id = %s"
            params.append(entity_id)
        
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        
        # Execute query
        with db_tools.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                reports = cur.fetchall()
        
        # Convert datetime objects to ISO format
        for report in reports:
            if report['created_at']:
                report['created_at'] = report['created_at'].isoformat()
            if report['updated_at']:
                report['updated_at'] = report['updated_at'].isoformat()
            if report['reviewed_at']:
                report['reviewed_at'] = report['reviewed_at'].isoformat()
            if report['resolved_at']:
                report['resolved_at'] = report['resolved_at'].isoformat()
        
        return jsonify({
            'success': True,
            'count': len(reports),
            'reports': reports
        })
        
    except Exception as e:
        logger.error(f"Error fetching content reports: {e}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while fetching reports.'
        }), 500



