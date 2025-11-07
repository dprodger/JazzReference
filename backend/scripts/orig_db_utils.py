#!/usr/bin/env python3
"""
Database Utilities - Unified for Scripts and Backend
Supports both pooled (Flask backend) and non-pooled (scripts) modes

Configuration:
    Set DB_USE_POOLING=true environment variable to enable pooling (for Flask)
    Leave unset or false for simple connections (for scripts)
"""

import os
import logging
import time
import threading
from contextlib import contextmanager
from typing import Optional

import psycopg
from psycopg.rows import dict_row

# Try to import pooling support - optional for scripts
try:
    from psycopg_pool import ConnectionPool
    POOLING_AVAILABLE = True
except ImportError:
    POOLING_AVAILABLE = False
    ConnectionPool = None

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

# Determine mode: pooled (backend) or simple (scripts)
USE_POOLING = os.environ.get('DB_USE_POOLING', 'false').lower() == 'true'

# Validate pooling availability
if USE_POOLING and not POOLING_AVAILABLE:
    logger.warning("Pooling requested but psycopg_pool not available. Falling back to simple mode.")
    USE_POOLING = False

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'aws-1-us-east-2.pooler.supabase.com'),
    'database': os.environ.get('DB_NAME', 'postgres'),
    'user': os.environ.get('DB_USER', 'postgres.wxinjyotnrqxrwqrtvkp'),
    'password': os.environ.get('DB_PASSWORD', 'jovpeW-pukgu0-nifron'),
    'port': os.environ.get('DB_PORT', '6543')
}

# Connection string for pooling
CONNECTION_STRING = (
    f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    f"?sslmode=require"
)


# ============================================================================
# POOLING MODE (Backend) - Only active if USE_POOLING=true
# ============================================================================

# Global connection pool (only used if pooling enabled)
pool: Optional[ConnectionPool] = None
keepalive_thread: Optional[threading.Thread] = None
keepalive_stop = threading.Event()


def init_connection_pool(max_retries=3, retry_delay=2):
    """
    Initialize the connection pool (only used in pooling mode)
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not USE_POOLING:
        logger.debug("Pooling not enabled, skipping pool initialization")
        return True
    
    global pool
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Initializing connection pool (attempt {attempt + 1}/{max_retries})...")
            
            # Optimized settings for Supabase transaction pooler
            pool = ConnectionPool(
                CONNECTION_STRING,
                min_size=1,
                max_size=3,
                open=True,
                timeout=10,
                max_waiting=10,
                max_lifetime=1800,
                max_idle=600,
                kwargs={
                    'row_factory': dict_row,
                    'connect_timeout': 10,
                    'keepalives': 1,
                    'keepalives_idle': 30,
                    'keepalives_interval': 10,
                    'keepalives_count': 3,
                    'options': '-c statement_timeout=30000',
                    'autocommit': False,
                    'prepare_threshold': None  # CRITICAL: Disable prepared statements
                }
            )
            
            # Test the connection
            logger.info("Testing connection pool...")
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 as test")
                    result = cur.fetchone()
                    logger.info(f"✓ Connection pool initialized successfully (test: {result})")
            
            return True
            
        except Exception as e:
            logger.error(f"✗ Connection pool initialization failed (attempt {attempt + 1}/{max_retries}): {e}")
            
            if pool is not None:
                try:
                    pool.close()
                except:
                    pass
                pool = None
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 1.5
            else:
                logger.error("Failed to initialize connection pool after all retries")
                return False
    
    return False


def reset_connection_pool():
    """Reset the connection pool (only used in pooling mode)"""
    if not USE_POOLING:
        return True
    
    global pool
    
    logger.warning("Resetting connection pool...")
    
    if pool is not None:
        try:
            pool.close()
            logger.info("Old pool closed")
        except Exception as e:
            logger.error(f"Error closing old pool: {e}")
    
    pool = None
    time.sleep(2)
    success = init_connection_pool()
    
    if success:
        logger.info("✓ Connection pool reset successfully")
    else:
        logger.error("✗ Failed to reset connection pool")
    
    return success


def connection_keepalive():
    """Background thread to keep connections alive (only used in pooling mode)"""
    logger.info("Starting connection keepalive thread...")
    
    while not keepalive_stop.is_set():
        try:
            if keepalive_stop.wait(300):  # 5 minutes
                break
            
            if pool is not None:
                logger.debug("Sending keepalive ping to database...")
                try:
                    with pool.connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT 1")
                    logger.debug("Keepalive ping successful")
                except Exception as e:
                    logger.warning(f"Keepalive ping failed: {e}")
                    
        except Exception as e:
            logger.error(f"Error in keepalive thread: {e}")
    
    logger.info("Connection keepalive thread stopped")


def start_keepalive_thread():
    """Start the background keepalive thread (only used in pooling mode)"""
    if not USE_POOLING:
        return
    
    global keepalive_thread
    
    if keepalive_thread is None or not keepalive_thread.is_alive():
        keepalive_stop.clear()
        keepalive_thread = threading.Thread(target=connection_keepalive, daemon=True)
        keepalive_thread.start()
        logger.info("Keepalive thread started")


def stop_keepalive_thread():
    """Stop the background keepalive thread (only used in pooling mode)"""
    if not USE_POOLING:
        return
    
    global keepalive_thread
    
    logger.info("Stopping keepalive thread...")
    keepalive_stop.set()
    if keepalive_thread:
        keepalive_thread.join(timeout=5)
    logger.info("Keepalive thread stopped")


def close_connection_pool():
    """Close the connection pool (only used in pooling mode)"""
    if not USE_POOLING:
        return
    
    global pool
    
    if pool:
        logger.info("Closing connection pool...")
        try:
            pool.close()
            logger.info("Connection pool closed")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")
        pool = None


def get_pool_stats():
    """Get current connection pool statistics (only used in pooling mode)"""
    if not USE_POOLING or pool is None:
        return None
    
    try:
        stats = pool.get_stats()
        return {
            'pool_size': stats.get('pool_size', 0),
            'pool_available': stats.get('pool_available', 0),
            'requests_waiting': stats.get('requests_waiting', 0)
        }
    except Exception as e:
        logger.error(f"Error getting pool stats: {e}")
        return None


# ============================================================================
# SIMPLE MODE (Scripts) - Direct connection creation
# ============================================================================

def _create_connection():
    """
    Internal function to create a database connection with automatic fallback.
    
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
        if 'supabase.co' in host and not host.startswith('aws-'):
            # Extract project reference from db.PROJECT_REF.supabase.co
            parts = host.split('.')
            if len(parts) >= 3 and parts[0] == 'db':
                project_ref = parts[1]
                pooler_host = f"aws-0-us-east-1.pooler.supabase.com"
                
                logger.debug(f"Detected Supabase host: {host}")
                logger.debug(f"Project reference: {project_ref}")
                logger.debug(f"Attempting connection via pooler: {pooler_host}")
                
                try:
                    conn = psycopg.connect(
                        host=pooler_host,
                        dbname=DB_CONFIG['database'],
                        user=f"postgres.{project_ref}",
                        password=DB_CONFIG['password'],
                        port='6543',
                        row_factory=dict_row,
                        options='-c statement_timeout=30000',
                        autocommit=False,
                        prepare_threshold=None
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
            autocommit=False,
            prepare_threshold=None
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
        logger.error("  2. Check if you have IPv6 connectivity")
        logger.error("     Direct connection requires IPv6")
        logger.error("")
        logger.error("  3. For IPv4-only machines, use pooler connection:")
        logger.error("     export DB_HOST='aws-0-us-east-1.pooler.supabase.com'")
        logger.error("     export DB_USER='postgres.YOUR_PROJECT_REF'")
        logger.error("     export DB_PORT='6543'")
        logger.error("")
        raise


# ============================================================================
# UNIFIED CONNECTION INTERFACE
# ============================================================================

@contextmanager
def get_db_connection():
    """
    Get a database connection - works in both pooled and non-pooled modes
    
    In pooled mode (USE_POOLING=true):
        - Uses connection pool
        - Transaction managed by pool
        - Connection automatically returned to pool
    
    In simple mode (USE_POOLING=false):
        - Creates new connection each time
        - Auto-commits on success
        - Auto-rolls back on error
        - Closes connection when done
    
    Usage (same for both modes):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM songs")
                results = cur.fetchall()
    
    Returns:
        psycopg.Connection: Database connection with dict_row factory
    """
    if USE_POOLING:
        # POOLED MODE (Backend)
        global pool
        
        # Lazy initialization
        if pool is None:
            logger.info("Connection pool not initialized, initializing now...")
            if not init_connection_pool():
                raise RuntimeError("Failed to initialize connection pool")
        
        # Use pool's context manager
        try:
            with pool.connection() as conn:
                yield conn
                # Transaction committed automatically if no exception
        except Exception as e:
            logger.error(f"Database error: {e}")
            raise
    
    else:
        # SIMPLE MODE (Scripts)
        conn = None
        try:
            # Create new connection
            conn = _create_connection()
            
            # Yield for use
            yield conn
            
            # Commit on success
            conn.commit()
            logger.debug("Transaction committed successfully")
            
        except Exception as e:
            # Rollback on error
            if conn:
                try:
                    conn.rollback()
                    logger.debug("Transaction rolled back due to error")
                except Exception as rollback_error:
                    logger.error(f"Error rolling back transaction: {rollback_error}")
            raise
            
        finally:
            # Always close
            if conn:
                try:
                    conn.close()
                    logger.debug("Database connection closed")
                except Exception as close_error:
                    logger.error(f"Error closing connection: {close_error}")


# ============================================================================
# HELPER FUNCTIONS (Used by both modes)
# ============================================================================

def execute_query(query, params=None, fetch_one=False, fetch_all=True):
    """
    Execute a query with proper error handling
    
    Args:
        query: SQL query string
        params: Query parameters tuple
        fetch_one: If True, return only first result
        fetch_all: If True, return all results (ignored if fetch_one is True)
    
    Returns:
        Query results or None
    """
    start_time = time.time()
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                
                if fetch_one:
                    result = cur.fetchone()
                elif fetch_all:
                    result = cur.fetchall()
                else:
                    result = None
                
                duration = time.time() - start_time
                logger.debug(f"Query executed in {duration:.3f}s")
                
                return result
                
    except psycopg.OperationalError as e:
        logger.error(f"Database operational error after {time.time() - start_time:.3f}s: {e}")
        raise
    except Exception as e:
        logger.error(f"Query error after {time.time() - start_time:.3f}s: {e}")
        raise


def execute_update(query, params=None):
    """
    Execute an INSERT/UPDATE/DELETE query
    
    Args:
        query: SQL query string
        params: Query parameters tuple
    
    Returns:
        Number of affected rows
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                affected_rows = cur.rowcount
                return affected_rows
    except psycopg.Error as e:
        logger.error(f"Update execution error: {e}")
        raise


def find_performer_by_name(name):
    """
    Find a performer by name (case-insensitive)
    
    Args:
        name: Performer name to search for
    
    Returns:
        Performer record or None if not found
    """
    query = "SELECT * FROM performers WHERE LOWER(name) = LOWER(%s) LIMIT 1"
    return execute_query(query, (name,), fetch_one=True)


def find_performer_by_id(performer_id):
    """
    Find a performer by UUID
    
    Args:
        performer_id: UUID of the performer
    
    Returns:
        Performer record or None if not found
    """
    query = "SELECT * FROM performers WHERE id = %s"
    return execute_query(query, (performer_id,), fetch_one=True)


def update_performer_external_references(performer_id, external_refs, dry_run=False):
    """
    Update external_references JSONB field for a performer
    
    Args:
        performer_id: UUID of the performer
        external_refs: Dictionary of external references to merge
        dry_run: If True, don't actually update the database
    
    Returns:
        True if successful, False otherwise
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would update external_references for performer {performer_id}: {external_refs}")
        return True
    
    try:
        import json
        query = """
            UPDATE performers 
            SET external_links = COALESCE(external_links, '{}'::jsonb) || %s::jsonb,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        affected = execute_update(query, (json.dumps(external_refs), performer_id))
        return affected > 0
    except Exception as e:
        logger.error(f"Error updating external references: {e}")
        return False


def get_performer_images(performer_id):
    """
    Get all images for a performer
    
    Args:
        performer_id: UUID of the performer
    
    Returns:
        List of image records with join data
    """
    query = """
        SELECT i.*, ai.is_primary, ai.display_order
        FROM images i
        JOIN artist_images ai ON i.id = ai.image_id
        WHERE ai.performer_id = %s
        ORDER BY ai.is_primary DESC, ai.display_order, i.created_at
    """
    return execute_query(query, (performer_id,), fetch_all=True)


def normalize_apostrophes(text):
    """
    Normalize various apostrophe characters to the correct Unicode apostrophe (')
    
    Args:
        text: String that may contain various apostrophe characters
        
    Returns:
        String with all apostrophes normalized to U+2019 (')
    """
    if not text:
        return text
    
    # The correct apostrophe to normalize to (U+2019 RIGHT SINGLE QUOTATION MARK)
    correct_apostrophe = '\u2019'  # This is: '
    
    # Map of apostrophe variants to the correct Unicode apostrophe
    apostrophe_variants = {
        "'": correct_apostrophe,  # U+0027 (straight apostrophe)
        "`": correct_apostrophe,  # U+0060 (backtick/grave accent)
        "´": correct_apostrophe,  # U+00B4 (acute accent)
        "'": correct_apostrophe,  # U+2018 (left single quotation mark)
        "‛": correct_apostrophe,  # U+201B (single high-reversed-9 quotation mark)
    }
    
    result = text
    for variant, correct in apostrophe_variants.items():
        result = result.replace(variant, correct)
    
    return result


def test_connection():
    """
    Test the database connection and print connection info
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        logger.info("Testing database connection...")
        logger.info(f"Mode: {'POOLED' if USE_POOLING else 'SIMPLE'}")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user, version()")
                result = cur.fetchone()
                db, user, version = result['current_database'], result['current_user'], result['version']
                logger.info(f"✓ Connected to database: {db}")
                logger.info(f"  User: {user}")
                logger.info(f"  PostgreSQL version: {version.split(',')[0]}")
        return True
    except Exception as e:
        logger.error(f"✗ Connection test failed: {e}")
        return False


# ============================================================================
# MAIN - For Testing
# ============================================================================

if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Run connection test
    test_connection()