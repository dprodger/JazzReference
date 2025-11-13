"""
Jazz Reference API Backend - Improved Version
A Flask API with robust database connection handling
"""

from flask import Flask, render_template, request
from flask_cors import CORS
import logging
import os

# Configuration
from config import configure_logging, init_app_config

# Set pooling mode BEFORE importing db_utils
os.environ['DB_USE_POOLING'] = 'true'

# Import database tools
import db_utils as db_tools
import research_queue
import song_research

logger = configure_logging()

# Create Flask app
app = Flask(__name__)
CORS(app)
init_app_config(app)

logger.info(f"Spotify credentials present: {bool(os.environ.get('SPOTIFY_CLIENT_ID'))}")
logger.info(f"Flask app initialized in PID {os.getpid()}")

# Register all route blueprints
from routes import register_blueprints
register_blueprints(app)


# ============================================================================
# LANDING PAGE
# ============================================================================

@app.route('/')
def landing_page():
    """Serve the main landing page"""
    return render_template('index.html')

# Request/response logging
@app.before_request
def log_request():
    """Log incoming requests"""
    logger.info(f"{request.method} {request.path}")

@app.after_request
def log_response(response):
    """Log response status"""
    logger.info(f"{request.method} {request.path} - {response.status_code}")
    return response



if __name__ == '__main__':
    # Running directly with 'python app.py' (not gunicorn)
    logger.info("Starting Flask application directly (not gunicorn)...")
    logger.info("Database connection pool will initialize on first request")
    
    # Start keepalive thread
    db_tools.start_keepalive_thread()
    
    # Start research worker thread (only when running directly)
    if not research_queue._worker_running:
        research_queue.start_worker(song_research.research_song)
        logger.info("Research worker thread initialized")
        
    try:
        app.run(debug=True, host='0.0.0.0', port=5001)
    finally:
        # Cleanup
        logger.info("Shutting down...")
        research_queue.stop_worker()
        db_tools.stop_keepalive_thread()
        db_tools.close_connection_pool()
        logger.info("Shutdown complete")
        
import atexit

def cleanup_connections():
    """Close the connection pool on shutdown"""
    logger.info("Shutting down connection pool...")
    db_tools.close_connection_pool()
    logger.info("Connection pool closed")

atexit.register(cleanup_connections)