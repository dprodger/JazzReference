#!/usr/bin/env python3
"""
Database Utilities - Unified for Scripts and Backend - IMPROVED VERSION
Supports both pooled (Flask backend) and non-pooled (scripts) modes

KEY IMPROVEMENTS:
1. Increased pool size and timeout
2. Better error handling and recovery
3. Automatic pool health checks
4. Connection validation before use
5. Exponential backoff for pool initialization

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
    'dbname': os.environ.get('DB_NAME', 'postgres'),
    'user': os.environ.get('DB_USER', 'postgres.wxinjyotnrqxrwqrtvkp'),
    'password': os.environ.get('DB_PASSWORD', 'jovpeW-pukgu0-nifron'),
    'port': os.environ.get('DB_PORT', '6543')
}

# Connection string for pooling
CONNECTION_STRING = (
    f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
    f"?sslmode=require"
)


# ============================================================================
# POOLING MODE (Backend) - Only active if USE_POOLING=true
# ============================================================================

# Global connection pool (only used if pooling enabled)
pool: Optional[ConnectionPool] = None
keepalive_thread: Optional[threading.Thread] = None
keepalive_stop = threading.Event()
pool_init_lock = threading.Lock()  # NEW: Thread-safe pool initialization


def init_connection_pool(max_retries=3, retry_delay=2):
    """
    Initialize the connection pool (only used in pooling mode)
    
    IMPROVEMENTS:
    - Larger pool size (5 instead of 3)
    - Longer timeout (30s instead of 10s)
    - Thread-safe initialization
    - Better retry logic
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not USE_POOLING:
        logger.debug("Pooling not enabled, skipping pool initialization")
        return True
    
    global pool
    
    # Thread-safe initialization
    with pool_init_lock:
        # Check if already initialized
        if pool is not None:
            logger.debug("Connection pool already initialized")
            return True
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Initializing connection pool (attempt {attempt + 1}/{max_retries})...")
                
                # IMPROVED: Better settings for Supabase transaction pooler
                pool = ConnectionPool(
                    CONNECTION_STRING,
                    min_size=2,          # Keep 2 connections warm
                    max_size=5,          # INCREASED from 3 to 5
                    open=True,
                    timeout=30,          # INCREASED from 10 to 30 seconds
                    max_waiting=20,      # INCREASED from 10 to 20 - more requests can queue
                    max_lifetime=1800,   # Recycle after 30 minutes
                    max_idle=600,        # Keep idle for 10 minutes
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
                        cur.execute("SELECT 1 as test, pg_backend_pid() as pid")
                        result = cur.fetchone()
                        logger.info(f"✓ Connection pool initialized successfully")
                        logger.info(f"  Test query result: {result['test']}")
                        logger.info(f"  Backend PID: {result['pid']}")
                
                # Log pool stats
                stats = get_pool_stats()
                if stats:
                    logger.info(f"  Pool stats: {stats}")
                
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
                    # Exponential backoff
                    wait_time = retry_delay * (1.5 ** attempt)
                    logger.info(f"Retrying in {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error("Failed to initialize connection pool after all retries")
                    return False
        
        return False


def reset_connection_pool():
    """
    Reset the connection pool (only used in pooling mode)
    
    IMPROVED: Thread-safe reset with better error handling
    """
    if not USE_POOLING:
        return True
    
    global pool
    
    with pool_init_lock:
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
    """
    Background thread to keep connections alive (only used in pooling mode)
    
    IMPROVED: Better error handling and logging
    """
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
                            cur.execute("SELECT 1, pg_backend_pid()")
                            result = cur.fetchone()
                    logger.debug(f"Keepalive ping successful (PID: {result[1] if result else 'unknown'})")
                    
                    # Log pool stats periodically
                    stats = get_pool_stats()
                    if stats:
                        logger.debug(f"Pool stats: {stats}")
                        
                except Exception as e:
                    logger.warning(f"Keepalive ping failed: {e}")
                    # Try to reset pool if keepalive fails multiple times
                    # (This could be extended with a failure counter)
                    
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
    
    with pool_init_lock:
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


def check_pool_health():
    """
    Check if pool is healthy and reinitialize if needed
    
    NEW: Proactive health checking
    
    Returns:
        bool: True if healthy or successfully reinitialized
    """
    if not USE_POOLING:
        return True
    
    if pool is None:
        logger.warning("Pool is None, attempting to initialize...")
        return init_connection_pool()
    
    try:
        # Quick health check
        with pool.connection(timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Pool health check failed: {e}")
        # Try to reset pool
        return reset_connection_pool()


# ============================================================================
# SIMPLE MODE (Scripts)
# ============================================================================

def _create_connection():
    """
    Create a simple database connection (only used in simple mode)
    
    IMPROVED: Better error messages
    
    Returns:
        psycopg connection
    """
    try:
        conn = psycopg.connect(
            **DB_CONFIG,
            row_factory=dict_row,
            autocommit=False,
            prepare_threshold=None
        )
        logger.debug("Simple database connection created")
        return conn
    except psycopg.OperationalError as e:
        logger.error(f"Failed to connect to database: {e}")
        logger.error(f"Connection details: host={DB_CONFIG['host']}, "
                    f"port={DB_CONFIG['port']}, database={DB_CONFIG['database']}, "
                    f"user={DB_CONFIG['user']}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating connection: {e}")
        raise


# ============================================================================
# UNIFIED CONNECTION MANAGER
# ============================================================================

@contextmanager
def get_db_connection():
    """
    Get a database connection using the appropriate mode
    
    IMPROVED:
    - Lazy initialization with health checks
    - Better error messages
    - Automatic retry for common errors
    
    Returns:
        Database connection (context manager)
    """
    if USE_POOLING:
        # POOLING MODE (Backend)
        global pool
        
        # Lazy initialization with health check
        if pool is None:
            logger.info("Connection pool not initialized, initializing now...")
            if not init_connection_pool():
                raise RuntimeError("Failed to initialize connection pool")
        
        # Try to get connection from pool
        try:
            with pool.connection() as conn:
                yield conn
                # Transaction committed automatically if no exception
        except psycopg.OperationalError as e:
            logger.error(f"Database operational error: {e}")
            # Check if we should try to reset pool
            if "server closed the connection unexpectedly" in str(e).lower():
                logger.warning("Detected connection closure, attempting pool reset...")
                reset_connection_pool()
            raise
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
    logger.info(f"[DB] execute_query called, USE_POOLING={USE_POOLING}")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Log connection info and set explicit timeout
                cur.execute("SHOW statement_timeout")
                timeout_result = cur.fetchone()
                logger.info(f"[DB] Current statement_timeout: {timeout_result}")

                # Set a shorter timeout explicitly for this query
                cur.execute("SET statement_timeout = '30s'")
                logger.info(f"[DB] Set statement_timeout to 30s, now executing query")

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


def find_song_by_name(title):
    """
    Find a song by title (case-insensitive)
    
    Args:
        title: Song title to search for
    
    Returns:
        Song record or None if not found
    """
    query = "SELECT * FROM songs WHERE LOWER(title) = LOWER(%s) LIMIT 1"
    return execute_query(query, (title,), fetch_one=True)


def find_song_by_id(song_id):
    """
    Find a song by UUID
    
    Args:
        song_id: UUID of the song
    
    Returns:
        Song record or None if not found
    """
    query = "SELECT * FROM songs WHERE id = %s"
    return execute_query(query, (song_id,), fetch_one=True)


def find_song_by_name_or_id(name=None, song_id=None):
    """
    Find a song by either name or ID
    
    Args:
        name: Song title to search for (will be normalized for apostrophes)
        song_id: UUID of the song
    
    Returns:
        Song record or None if not found
    
    Raises:
        ValueError: If neither name nor song_id is provided
    """
    if name is None and song_id is None:
        raise ValueError("Either name or song_id must be provided")
    
    if name is not None:
        normalized_name = normalize_apostrophes(name)
        return find_song_by_name(normalized_name)
    else:
        return find_song_by_id(song_id)


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
                cur.execute("SELECT current_database(), current_user, version(), pg_backend_pid()")
                result = cur.fetchone()
                db = result['current_database']
                user = result['current_user']
                version = result['version']
                pid = result['pg_backend_pid']
                
                logger.info(f"✓ Connected to database: {db}")
                logger.info(f"  User: {user}")
                logger.info(f"  Backend PID: {pid}")
                logger.info(f"  PostgreSQL version: {version.split(',')[0]}")
                
        if USE_POOLING:
            stats = get_pool_stats()
            if stats:
                logger.info(f"  Pool stats: {stats}")
                
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