"""
Jazz Reference API Backend - Improved Version
A Flask API with robust database connection handling
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import logging
import os

from dotenv import load_dotenv  # ADD THIS LINE

# Load environment variables from .env file
load_dotenv()  # ADD THIS LINE

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

# Import authentication blueprints
from routes.auth import auth_bp
from routes.password import password_bp

# Register authentication blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(password_bp)

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

# ============================================================================
# HOST-BASED ROUTING
# ============================================================================

# Define which hosts serve which content
API_HOSTS = ['api.approachnote.com', 'localhost:5001', '127.0.0.1:5001']
WEB_HOSTS = ['approachnote.com', 'www.approachnote.com']

# Routes that should only be served from the website (not API subdomain)
WEB_ONLY_PATHS = ['/', '/docs']

# Routes that should only be served from the API subdomain
# (everything except web-only paths and static files)

@app.before_request
def enforce_host_routing():
    """
    Enforce that API routes are only accessible via api.approachnote.com
    and website routes are only accessible via www/root domain.
    """
    host = request.host
    path = request.path

    # Allow static files from any host
    if path.startswith('/static/'):
        return None

    # Allow admin routes from any host (for now)
    if path.startswith('/admin'):
        return None

    # Check if this is an API host
    is_api_host = any(host == h or host.endswith('.' + h) for h in API_HOSTS)
    is_web_host = any(host == h or host.endswith('.' + h) for h in WEB_HOSTS)

    # On API host: block web-only paths
    if is_api_host and path in WEB_ONLY_PATHS:
        return jsonify({'error': 'Not found', 'message': 'Use approachnote.com for website'}), 404

    # On web host: only allow web-only paths and static files
    if is_web_host and path not in WEB_ONLY_PATHS:
        return jsonify({'error': 'Not found', 'message': 'Use api.approachnote.com for API'}), 404

    return None

# Request/response logging
@app.before_request
def log_request():
    """Log incoming requests"""
    logger.info(f"{request.method} {request.path} (Host: {request.host})")

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