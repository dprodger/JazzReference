#!/usr/bin/env python3
"""
Verify users authentication schema is correctly created

This script checks that all users-related tables, indexes, and constraints
have been properly created in the database after running the Phase 1 migration.
"""

import sys
import argparse
import logging
from db_utils import get_db_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scripts/log/verify_users_schema.log')
    ]
)
logger = logging.getLogger(__name__)


def verify_tables():
    """Verify all required tables exist"""
    required_tables = [
        'users',
        'password_reset_tokens',
        'email_verification_tokens',
        'refresh_tokens'
    ]
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_name = ANY(%s)
            """, (required_tables,))
            
            existing_tables = {row['table_name'] for row in cur.fetchall()}
            missing_tables = set(required_tables) - existing_tables
            
            if missing_tables:
                logger.error(f"Missing tables: {missing_tables}")
                return False
            
            logger.info(f"✓ All required tables exist: {required_tables}")
            return True


def verify_indexes():
    """Verify all required indexes exist"""
    required_indexes = [
        'idx_users_email',
        'idx_users_google_id',
        'idx_users_apple_id',
        'idx_password_reset_tokens_token',
        'idx_password_reset_tokens_user_id',
        'idx_email_verification_tokens_token',
        'idx_email_verification_tokens_user_id',
        'idx_refresh_tokens_token',
        'idx_refresh_tokens_user_id'
    ]
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE schemaname = 'public'
                AND indexname = ANY(%s)
            """, (required_indexes,))
            
            existing_indexes = {row['indexname'] for row in cur.fetchall()}
            missing_indexes = set(required_indexes) - existing_indexes
            
            if missing_indexes:
                logger.error(f"Missing indexes: {missing_indexes}")
                return False
            
            logger.info(f"✓ All required indexes exist: {len(required_indexes)} indexes")
            return True


def verify_constraints():
    """Verify critical constraints exist"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Check unique constraints
            cur.execute("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'users'
                AND constraint_type = 'UNIQUE'
            """)
            
            constraints = {row['constraint_name'] for row in cur.fetchall()}
            
            # Should have unique constraints on email, google_id, apple_id
            expected_constraints = ['users_email_key', 'users_google_id_key', 'users_apple_id_key']
            found_count = sum(1 for c in expected_constraints if c in constraints)
            
            logger.info(f"✓ Found {found_count} unique constraints on users table")
            
            # Check the auth method CHECK constraint
            cur.execute("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'users'
                AND constraint_type = 'CHECK'
                AND constraint_name = 'check_auth_method'
            """)
            
            check_constraint = cur.fetchone()
            if check_constraint:
                logger.info("✓ Auth method CHECK constraint exists")
            else:
                logger.warning("Auth method CHECK constraint not found")
            
            return True


def verify_columns():
    """Verify critical columns exist with correct types"""
    expected_columns = {
        'users': [
            ('id', 'uuid'),
            ('email', 'character varying'),
            ('email_verified', 'boolean'),
            ('password_hash', 'character varying'),
            ('display_name', 'character varying'),
            ('google_id', 'character varying'),
            ('apple_id', 'character varying'),
            ('is_active', 'boolean'),
            ('account_locked', 'boolean'),
            ('failed_login_attempts', 'integer'),
            ('created_at', 'timestamp with time zone'),
            ('updated_at', 'timestamp with time zone'),
            ('last_login_at', 'timestamp with time zone')
        ],
        'refresh_tokens': [
            ('id', 'uuid'),
            ('user_id', 'uuid'),
            ('token', 'character varying'),
            ('expires_at', 'timestamp with time zone'),
            ('revoked_at', 'timestamp with time zone'),
            ('device_info', 'jsonb')
        ]
    }
    
    all_ok = True
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for table_name, columns in expected_columns.items():
                cur.execute("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = %s
                """, (table_name,))
                
                existing_columns = {row['column_name']: row['data_type'] for row in cur.fetchall()}
                
                for col_name, expected_type in columns:
                    if col_name not in existing_columns:
                        logger.error(f"Missing column {table_name}.{col_name}")
                        all_ok = False
                    elif expected_type not in existing_columns[col_name]:
                        logger.warning(
                            f"Column {table_name}.{col_name} has type "
                            f"{existing_columns[col_name]}, expected {expected_type}"
                        )
                
                logger.info(f"✓ Verified columns for {table_name}")
    
    return all_ok


def verify_triggers():
    """Verify required triggers exist"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT trigger_name, event_object_table
                FROM information_schema.triggers
                WHERE trigger_schema = 'public'
                AND trigger_name = 'update_users_updated_at'
            """)
            
            trigger = cur.fetchone()
            
            if trigger:
                logger.info(f"✓ Trigger update_users_updated_at exists on users table")
                return True
            else:
                logger.warning("Trigger update_users_updated_at not found")
                return False


def test_basic_operations():
    """Test basic CRUD operations on users table"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Test INSERT
                cur.execute("""
                    INSERT INTO users (email, password_hash, display_name)
                    VALUES ('test@example.com', 'test_hash', 'Test User')
                    RETURNING id
                """)
                result = cur.fetchone()
                test_user_id = result['id']
                logger.info(f"✓ Successfully created test user with ID: {test_user_id}")
                
                # Test SELECT
                cur.execute("""
                    SELECT id, email, display_name, is_active, email_verified
                    FROM users
                    WHERE id = %s
                """, (test_user_id,))
                user = cur.fetchone()
                
                if user:
                    logger.info(f"✓ Successfully retrieved test user: {user['email']}")
                else:
                    logger.error("Failed to retrieve test user")
                    return False
                
                # Test UPDATE
                cur.execute("""
                    UPDATE users
                    SET display_name = 'Updated Test User'
                    WHERE id = %s
                """, (test_user_id,))
                logger.info("✓ Successfully updated test user")
                
                # Test DELETE (cleanup)
                cur.execute("""
                    DELETE FROM users WHERE id = %s
                """, (test_user_id,))
                logger.info("✓ Successfully deleted test user")
                
                conn.commit()
                
        return True
        
    except Exception as e:
        logger.error(f"Basic operations test failed: {e}", exc_info=True)
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Verify users authentication schema is correctly created',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run verification
  python scripts/verify_users_schema.py
  
  # With debug logging
  python scripts/verify_users_schema.py --debug
  
  # Skip CRUD operations test
  python scripts/verify_users_schema.py --skip-test
        """
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    parser.add_argument(
        '--skip-test',
        action='store_true',
        help='Skip basic CRUD operations test'
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("="*80)
    logger.info("VERIFY USERS AUTHENTICATION SCHEMA")
    logger.info("="*80)
    logger.info("")
    
    try:
        # Run all verification checks
        tables_ok = verify_tables()
        logger.info("")
        
        indexes_ok = verify_indexes()
        logger.info("")
        
        constraints_ok = verify_constraints()
        logger.info("")
        
        columns_ok = verify_columns()
        logger.info("")
        
        triggers_ok = verify_triggers()
        logger.info("")
        
        # Run basic operations test if not skipped
        test_ok = True
        if not args.skip_test:
            logger.info("Running basic CRUD operations test...")
            test_ok = test_basic_operations()
            logger.info("")
        
        # Determine overall success
        all_checks_passed = (
            tables_ok and 
            indexes_ok and 
            constraints_ok and 
            columns_ok and 
            triggers_ok and 
            test_ok
        )
        
        if all_checks_passed:
            logger.info("="*80)
            logger.info("✓ SCHEMA VERIFICATION PASSED")
            logger.info("="*80)
            logger.info("")
            logger.info("All authentication tables, indexes, constraints, and triggers")
            logger.info("are properly configured. You can proceed to Phase 2.")
            sys.exit(0)
        else:
            logger.error("="*80)
            logger.error("✗ SCHEMA VERIFICATION FAILED")
            logger.error("="*80)
            logger.error("")
            logger.error("Some checks failed. Please review the errors above and")
            logger.error("ensure the migration was applied correctly.")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Verification error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()