#!/usr/bin/env python3
"""
Database Connection Diagnostics
Helps identify connection pool and database connection issues
"""

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
import os
import time
import sys

# Database configuration (from your app)
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'db.wxinjyotnrqxrwqrtvkp.supabase.co'),
    'database': os.environ.get('DB_NAME', 'postgres'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', 'jovpeW-pukgu0-nifron'),
    'port': os.environ.get('DB_PORT', '5432')
}

CONNECTION_STRING = (
    f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    f"?sslmode=require"
)

def print_section(title):
    """Print a section header"""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}\n")

def test_direct_connection():
    """Test a direct database connection"""
    print_section("TEST 1: Direct Database Connection")
    
    try:
        print(f"Connecting to: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        print(f"Database: {DB_CONFIG['database']}")
        print(f"User: {DB_CONFIG['user']}")
        print()
        
        start_time = time.time()
        conn = psycopg.connect(
            host=DB_CONFIG['host'],
            dbname=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            port=DB_CONFIG['port'],
            row_factory=dict_row,
            connect_timeout=10
        )
        connect_time = time.time() - start_time
        
        print(f"✓ Connection established in {connect_time:.2f}s")
        
        # Test query
        with conn.cursor() as cur:
            cur.execute("SELECT version(), current_database(), current_user, pg_backend_pid()")
            result = cur.fetchone()
            print(f"✓ Query successful")
            print(f"  PostgreSQL: {result['version'].split(',')[0]}")
            print(f"  Database: {result['current_database']}")
            print(f"  User: {result['current_user']}")
            print(f"  Backend PID: {result['pg_backend_pid']}")
        
        conn.close()
        print(f"✓ Connection closed")
        return True
        
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False

def test_connection_pool():
    """Test connection pool creation and usage"""
    print_section("TEST 2: Connection Pool")
    
    try:
        print("Creating connection pool...")
        print(f"  Min connections: 1")
        print(f"  Max connections: 2")
        print()
        
        pool = ConnectionPool(
            CONNECTION_STRING,
            min_size=1,
            max_size=2,
            open=True,
            timeout=10,
            max_waiting=2,
            kwargs={
                'row_factory': dict_row,
                'connect_timeout': 5,
                'keepalives': 1,
                'keepalives_idle': 30,
                'keepalives_interval': 10,
                'keepalives_count': 3,
            }
        )
        
        print("✓ Pool created")
        
        # Get pool stats
        stats = pool.get_stats()
        print(f"\nPool Statistics:")
        print(f"  Pool size: {stats.get('pool_size', 0)}")
        print(f"  Available: {stats.get('pool_available', 0)}")
        print(f"  Waiting: {stats.get('requests_waiting', 0)}")
        
        # Test getting a connection
        print(f"\nTesting connection from pool...")
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 as test, pg_backend_pid()")
                result = cur.fetchone()
                print(f"✓ Query successful (test={result['test']}, pid={result['pg_backend_pid']})")
        
        # Get stats after use
        stats = pool.get_stats()
        print(f"\nPool Statistics After Use:")
        print(f"  Pool size: {stats.get('pool_size', 0)}")
        print(f"  Available: {stats.get('pool_available', 0)}")
        print(f"  Waiting: {stats.get('requests_waiting', 0)}")
        
        pool.close()
        print(f"\n✓ Pool closed")
        return True
        
    except Exception as e:
        print(f"✗ Pool test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_active_connections():
    """Check active connections on the database"""
    print_section("TEST 3: Active Database Connections")
    
    try:
        conn = psycopg.connect(
            host=DB_CONFIG['host'],
            dbname=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            port=DB_CONFIG['port'],
            row_factory=dict_row,
            connect_timeout=10
        )
        
        with conn.cursor() as cur:
            # Get connection count
            cur.execute("""
                SELECT 
                    count(*) as total_connections,
                    count(*) FILTER (WHERE state = 'active') as active,
                    count(*) FILTER (WHERE state = 'idle') as idle,
                    count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction
                FROM pg_stat_activity
                WHERE datname = current_database()
            """)
            result = cur.fetchone()
            
            print(f"Connection Statistics for database '{DB_CONFIG['database']}':")
            print(f"  Total connections: {result['total_connections']}")
            print(f"  Active: {result['active']}")
            print(f"  Idle: {result['idle']}")
            print(f"  Idle in transaction: {result['idle_in_transaction']}")
            
            # Get detailed connection info
            cur.execute("""
                SELECT 
                    pid,
                    usename,
                    application_name,
                    client_addr,
                    state,
                    state_change,
                    query_start,
                    COALESCE(wait_event_type, '') as wait_event_type,
                    COALESCE(wait_event, '') as wait_event
                FROM pg_stat_activity
                WHERE datname = current_database()
                AND pid != pg_backend_pid()
                ORDER BY state_change DESC
                LIMIT 10
            """)
            connections = cur.fetchall()
            
            if connections:
                print(f"\nRecent Connections:")
                for conn_info in connections:
                    print(f"  PID {conn_info['pid']}: {conn_info['state']}")
                    print(f"    User: {conn_info['usename']}")
                    print(f"    App: {conn_info['application_name']}")
                    if conn_info['wait_event_type']:
                        print(f"    Waiting: {conn_info['wait_event_type']}/{conn_info['wait_event']}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"✗ Failed to check connections: {e}")
        return False

def test_connection_limits():
    """Check database connection limits"""
    print_section("TEST 4: Connection Limits")
    
    try:
        conn = psycopg.connect(
            host=DB_CONFIG['host'],
            dbname=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            port=DB_CONFIG['port'],
            row_factory=dict_row,
            connect_timeout=10
        )
        
        with conn.cursor() as cur:
            # Get connection limit
            cur.execute("""
                SELECT 
                    setting::int as max_connections
                FROM pg_settings
                WHERE name = 'max_connections'
            """)
            result = cur.fetchone()
            max_conn = result['max_connections']
            
            # Get current usage
            cur.execute("""
                SELECT count(*) as current_connections
                FROM pg_stat_activity
            """)
            result = cur.fetchone()
            current_conn = result['current_connections']
            
            print(f"Database Connection Limits:")
            print(f"  Max connections: {max_conn}")
            print(f"  Current connections: {current_conn}")
            print(f"  Available: {max_conn - current_conn}")
            print(f"  Usage: {(current_conn/max_conn)*100:.1f}%")
            
            if current_conn > max_conn * 0.8:
                print(f"\n⚠️  WARNING: Connection usage is high!")
                print(f"     Consider reducing your pool size or number of workers")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"✗ Failed to check limits: {e}")
        return False

def test_pool_stress():
    """Stress test the connection pool"""
    print_section("TEST 5: Connection Pool Stress Test")
    
    try:
        print("Creating connection pool...")
        pool = ConnectionPool(
            CONNECTION_STRING,
            min_size=1,
            max_size=2,
            open=True,
            timeout=10,
            max_waiting=2,
            kwargs={
                'row_factory': dict_row,
                'connect_timeout': 5,
            }
        )
        
        print("✓ Pool created")
        print(f"\nAttempting to get 5 connections sequentially...")
        
        for i in range(5):
            try:
                start = time.time()
                with pool.connection() as conn:
                    elapsed = time.time() - start
                    with conn.cursor() as cur:
                        cur.execute("SELECT pg_backend_pid()")
                        result = cur.fetchone()
                        print(f"  Connection {i+1}: ✓ Got connection in {elapsed:.2f}s (PID: {result['pg_backend_pid']})")
            except Exception as e:
                print(f"  Connection {i+1}: ✗ Failed - {e}")
        
        stats = pool.get_stats()
        print(f"\nFinal Pool Stats:")
        print(f"  Pool size: {stats.get('pool_size', 0)}")
        print(f"  Available: {stats.get('pool_available', 0)}")
        print(f"  Waiting: {stats.get('requests_waiting', 0)}")
        
        pool.close()
        return True
        
    except Exception as e:
        print(f"✗ Stress test failed: {e}")
        return False

def main():
    """Run all diagnostic tests"""
    print("="*80)
    print("DATABASE CONNECTION DIAGNOSTICS")
    print("="*80)
    print(f"\nTimestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Host: {DB_CONFIG['host']}")
    print(f"Port: {DB_CONFIG['port']}")
    print(f"Database: {DB_CONFIG['database']}")
    
    results = {
        'Direct Connection': test_direct_connection(),
        'Connection Pool': test_connection_pool(),
        'Active Connections': test_active_connections(),
        'Connection Limits': test_connection_limits(),
        'Pool Stress Test': test_pool_stress(),
    }
    
    print_section("SUMMARY")
    all_passed = True
    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print(f"\n✓ All tests passed!")
        print(f"\nYour connection pool issues may be related to:")
        print(f"  - Too many workers in gunicorn")
        print(f"  - Long-running transactions holding connections")
        print(f"  - Network instability between app and database")
        return 0
    else:
        print(f"\n✗ Some tests failed. Review the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())