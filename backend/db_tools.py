"""
Database Tools for Flask Backend
Handles database connection pooling and query execution
"""

import os
import logging
import time
import threading
from contextlib import contextmanager
from typing import Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


logger = logging.getLogger(__name__)


# Database configuration
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'db.wxinjyotnrqxrwqrtvkp.supabase.co'),
    'database': os.environ.get('DB_NAME', 'postgres'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', 'jovpeW-pukgu0-nifron'),
    'port': os.environ.get('DB_PORT', '5432')
}

# Connection string for pooling
CONNECTION_STRING = (
    f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    f"?sslmode=require"
)

# Global connection pool
pool: Optional[ConnectionPool] = None
keepalive_thread: Optional[threading.Thread] = None
keepalive_stop = threading.Event()


def reset_connection_pool():
    """Reset the connection pool by closing and reinitializing it"""
    global pool
    
    logger.warning("Resetting connection pool...")
    
    # Close existing pool
    if pool is not None:
        try:
            pool.close()
            logger.info("Old pool closed")
        except Exception as e:
            logger.error(f"Error closing old pool: {e}")
    
    pool = None
    
    # Reinitialize
    time.sleep(2)  # Brief pause
    success = init_connection_pool()
    
    if success:
        logger.info("✓ Connection pool reset successfully")
    else:
        logger.error("✗ Failed to reset connection pool")
    
    return success


def connection_keepalive():
    """Background thread to keep connections alive during idle periods"""
    logger.info("Starting connection keepalive thread...")
    
    while not keepalive_stop.is_set():
        try:
            # Wait 5 minutes between keepalive pings
            if keepalive_stop.wait(300):  # 300 seconds = 5 minutes
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


def init_connection_pool(max_retries=3, retry_delay=2):
    """Initialize the connection pool with retry logic optimized for port 6543"""
    global pool
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Initializing connection pool (attempt {attempt + 1}/{max_retries})...")
            
            # Use VERY conservative settings for Supabase free tier
            pool = ConnectionPool(
                CONNECTION_STRING,
                min_size=1,  # Only 1 connection
                max_size=2,  # Max 2 connections per worker
                open=True,
                timeout=10,  # Reduce timeout
                max_waiting=2,  # Fewer waiting requests
                max_lifetime=3600,  # recycle connections after one hour
                max_idle=300,       # close idle connections after 5 min
                kwargs={
                    'row_factory': dict_row,
                    'connect_timeout': 5,
                    'keepalives': 1,
                    'keepalives_idle': 30,
                    'keepalives_interval': 10,
                    'keepalives_count': 3,
                    'options': '-c statement_timeout=30000'
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
            
            # Clean up failed pool
            if pool is not None:
                try:
                    pool.close()
                except:
                    pass
                pool = None
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 1.5  # Exponential backoff
            else:
                logger.error("Failed to initialize connection pool after all retries")
                return False
    
    return False


@contextmanager
def get_db_connection():
    """Get a database connection from the pool with explicit transaction management"""
    global pool
    
    # Lazy initialization - create pool on first request if not exists
    if pool is None:
        logger.info("Connection pool not initialized, initializing now...")
        if not init_connection_pool():
            raise RuntimeError("Failed to initialize connection pool")
    
    conn = None
    max_retries = 2
    retry_delay = 0.5
    
    for attempt in range(max_retries):
        try:
            conn = pool.getconn(timeout=10)  # 10 second timeout to get connection from pool
            
            # Yield the connection for use
            yield conn
            
            # If we get here, the code block succeeded
            # Explicitly commit the transaction
            conn.commit()
            return  # Success, exit the function
            
        except psycopg.OperationalError as e:
            logger.error(f"Database operational error (attempt {attempt + 1}/{max_retries}): {e}")
            
            # Rollback on error
            if conn:
                try:
                    conn.rollback()
                except Exception as rollback_error:
                    logger.error(f"Error rolling back transaction: {rollback_error}")
            
            # If this was a connection error and we have retries left, try again
            if attempt < max_retries - 1:
                logger.info(f"Retrying connection in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
                
                # Return the bad connection if we got one
                if conn:
                    try:
                        pool.putconn(conn)
                    except:
                        pass
                conn = None
            else:
                raise
                
        except Exception as e:
            # Rollback on any error
            if conn:
                try:
                    conn.rollback()
                    logger.debug("Transaction rolled back due to error")
                except Exception as rollback_error:
                    logger.error(f"Error rolling back transaction: {rollback_error}")
            
            logger.error(f"Unexpected database error: {e}")
            raise
            
        finally:
            # Always return connection to pool
            if conn:
                try:
                    pool.putconn(conn)
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")


def execute_query(query, params=None, fetch_one=False, fetch_all=True):
    """Execute a query with proper error handling and logging"""
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


def get_pool_stats():
    """Get current connection pool statistics"""
    if pool is None:
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


def start_keepalive_thread():
    """Start the background keepalive thread"""
    global keepalive_thread
    
    if keepalive_thread is None or not keepalive_thread.is_alive():
        keepalive_stop.clear()
        keepalive_thread = threading.Thread(target=connection_keepalive, daemon=True)
        keepalive_thread.start()
        logger.info("Keepalive thread started")


def stop_keepalive_thread():
    """Stop the background keepalive thread"""
    global keepalive_thread
    
    logger.info("Stopping keepalive thread...")
    keepalive_stop.set()
    if keepalive_thread:
        keepalive_thread.join(timeout=5)
    logger.info("Keepalive thread stopped")


def close_connection_pool():
    """Close the connection pool on shutdown"""
    global pool
    
    if pool:
        logger.info("Closing connection pool...")
        try:
            pool.close()
            logger.info("Connection pool closed")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")
        pool = None