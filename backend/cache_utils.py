#!/usr/bin/env python3
"""
Cache Utilities
Provides shared functionality for locating the persistent cache directory
"""

from pathlib import Path


def get_cache_root():
    """
    Get the absolute path to the cache root directory.
    
    The cache directory is located at the project root level:
    /opt/render/project/src/cache/
    
    This works in both local development and Render deployment:
    - Locally: Returns <project_root>/cache/
    - Render: Returns /opt/render/project/src/cache/ (persistent disk)
    
    Returns:
        Path: Absolute path to cache root directory
    """
    # This file is in backend/
    # We want to go up one level to project root, then into cache/
    backend_dir = Path(__file__).parent
    project_root = backend_dir.parent
    cache_root = project_root / 'cache'
    
    # Ensure the cache directory exists
    cache_root.mkdir(parents=True, exist_ok=True)
    
    return cache_root


def get_cache_dir(service_name):
    """
    Get the cache directory for a specific service (e.g., 'musicbrainz', 'spotify').
    
    Args:
        service_name: Name of the service (e.g., 'musicbrainz', 'spotify', 'wikipedia')
        
    Returns:
        Path: Absolute path to the service's cache directory
    """
    cache_dir = get_cache_root() / service_name
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir