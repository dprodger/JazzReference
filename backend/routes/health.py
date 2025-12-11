# routes/health.py
from flask import Blueprint, jsonify
import logging
import time
import db_utils as db_tools

logger = logging.getLogger(__name__)
health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Enhanced health check endpoint with detailed diagnostics"""
    health_status = {
        'status': 'unknown',
        'database': 'unknown',
        'pool_stats': None,
        'timestamp': time.time()
    }
    
    try:
        # Check if db_tools.pool exists
        if db_tools.pool is None:
            health_status['status'] = 'unhealthy'
            health_status['database'] = 'db_tools.pool not initialized'
            return jsonify(health_status), 503
        
        # Get db_tools.pool statistics
        pool_stats = db_tools.pool.get_stats()
        health_status['pool_stats'] = {
            'pool_size': pool_stats.get('pool_size', 0),
            'pool_available': pool_stats.get('pool_available', 0),
            'requests_waiting': pool_stats.get('requests_waiting', 0)
        }
        
        # Test database connection
        result = db_tools.execute_query("SELECT version(), current_timestamp", fetch_one=True)
        
        health_status['status'] = 'healthy'
        health_status['database'] = 'connected'
        health_status['db_version'] = result['version'] if result else 'unknown'
        health_status['db_time'] = str(result['current_timestamp']) if result else 'unknown'
        
        return jsonify(health_status), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        health_status['status'] = 'unhealthy'
        health_status['database'] = f'error: {str(e)}'
        return jsonify(health_status), 503

