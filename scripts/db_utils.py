#!/usr/bin/env python3
"""
Database Utilities
Shared database connection and configuration for Jazz Reference scripts
"""

import os
import logging
import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

# Database configuration - read from environment or use defaults
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'aws-1-us-east-2.pooler.supabase.com'),
    'database': os.environ.get('DB_NAME', 'postgres'),
    'user': os.environ.get('DB_USER', 'postgres.wxinjyotnrqxrwqrtvkp'),
    'password': os.environ.get('DB_PASSWORD', 'jovpeW-pukgu0-nifron'),
    'port': os.environ.get('DB_PORT', '6543')
}


def get_db_connection():
    """
    Create and return a database connection with automatic fallback handling.
    
    Tries connection pooler first (for IPv4 compatibility), then falls back
    to direct connection (requires IPv6).
    
    Returns:
        psycopg.Connection: Database connection with dict_row factory
        
    Raises:
        Exception: If connection fails after all attempts
    """
    try:
        # Supabase requires IPv6 for direct connections
        # Use connection pooler for IPv4 compatibility
        host = DB_CONFIG['host']
        
        # If using default Supabase host, try connection pooler for IPv4
        if 'supabase.co' in host and not host.startswith('aws-0-'):
            # Extract project reference from db.PROJECT_REF.supabase.co
            parts = host.split('.')
            if len(parts) >= 3 and parts[0] == 'db':
                project_ref = parts[1]
                # Supabase pooler format: aws-0-REGION.pooler.supabase.com
                # Most Supabase projects are in us-east-1
                pooler_host = f"aws-0-us-east-1.pooler.supabase.com"
                
                logger.debug(f"Detected Supabase host: {host}")
                logger.debug(f"Project reference: {project_ref}")
                logger.debug(f"Attempting connection via pooler: {pooler_host}")
                
                try:
                    conn = psycopg.connect(
                        host=pooler_host,
                        dbname=DB_CONFIG['database'],
                        user=f"postgres.{project_ref}",  # Pooler requires this format
                        password=DB_CONFIG['password'],
                        port='6543',  # Transaction mode pooler port
                        row_factory=dict_row,
                        options='-c statement_timeout=30000',
                        prepare_threshold=None  # cursor management
                    )
                    logger.debug("✓ Connection pooler connection established")
                    return conn
                except Exception as pooler_error:
                    logger.debug(f"✗ Pooler connection failed: {pooler_error}")
                    logger.debug("Falling back to direct connection (requires IPv6)...")
        
        # Try direct connection (requires IPv6)
        logger.debug(f"Attempting direct connection to: {DB_CONFIG['host']}")
        conn = psycopg.connect(
            host=DB_CONFIG['host'],
            dbname=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            port=DB_CONFIG['port'],
            row_factory=dict_row,
            prepare_threshold=None  # cursor management
        )
        logger.debug("✓ Direct database connection established")
        return conn
        
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        logger.error("")
        logger.error("Connection troubleshooting:")
        logger.error("  1. Verify your DB_HOST setting")
        logger.error(f"     Current: {DB_CONFIG.get('host', 'not set')}")
        logger.error("")
        logger.error("  2. If using Supabase, direct connections require IPv6")
        logger.error("     Check IPv6: curl -6 https://ifconfig.co")
        logger.error("")
        logger.error("  3. For IPv4-only machines, manually set pooler connection:")
        logger.error("     export DB_HOST='aws-0-us-east-1.pooler.supabase.com'")
        logger.error("     export DB_USER='postgres.YOUR_PROJECT_REF'")
        logger.error("     export DB_PORT='6543'")
        logger.error("")
        logger.error("  4. Find your project ref at: https://supabase.com/dashboard/project/_/settings/database")
        logger.error("")
        raise


def test_connection():
    """
    Test the database connection and print connection info.
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        logger.info("Testing database connection...")
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user, version()")
                db, user, version = cur.fetchone()
                logger.info(f"✓ Connected to database: {db}")
                logger.info(f"  User: {user}")
                logger.info(f"  PostgreSQL version: {version.split(',')[0]}")
        return True
    except Exception as e:
        logger.error(f"✗ Connection test failed: {e}")
        return False


if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Run connection test
    test_connection()