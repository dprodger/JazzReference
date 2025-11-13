"""
Configuration Module for Jazz Reference API
Handles logging setup and Flask app initialization
"""

import os
import logging


def configure_logging():
    """
    Configure application logging with standard format
    
    Returns:
        Logger instance for the config module
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def init_app_config(app):
    """
    Initialize Flask app configuration
    
    This sets up:
    - Custom JSON provider for date formatting
    
    Args:
        app: Flask application instance
    """
    from utils.json_provider import CustomJSONProvider
    app.json = CustomJSONProvider(app)


def set_db_pooling_mode():
    """
    Set database pooling mode environment variable
    
    This MUST be called before importing db_utils to ensure
    the connection pool is configured correctly.
    """
    os.environ['DB_USE_POOLING'] = 'true'