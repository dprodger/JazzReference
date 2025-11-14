#!/usr/bin/env python3
"""
Test authentication endpoints for Phase 2

This script tests all the authentication endpoints to verify Phase 2
implementation is working correctly.
"""

import sys
import argparse
import logging
import requests
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scripts/log/test_auth_endpoints.log')
    ]
)
logger = logging.getLogger(__name__)


class AuthEndpointTester:
    """Test authentication endpoints"""
    
    def __init__(self, base_url, dry_run=False):
        """
        Initialize tester
        
        Args:
            base_url: Base URL of the API (e.g., http://localhost:5001)
            dry_run: If True, show what would be tested without making requests
        """
        self.base_url = base_url.rstrip('/')
        self.dry_run = dry_run
        self.test_email = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com"
        self.test_password = "testpass123"
        self.test_display_name = "Test User"
        
        self.access_token = None
        self.refresh_token = None
        self.user_id = None
        
        self.stats = {
            'tests_run': 0,
            'tests_passed': 0,
            'tests_failed': 0
        }
    
    def test_endpoint(self, test_name, method, endpoint, data=None, headers=None, expected_status=200):
        """
        Test a single endpoint
        
        Args:
            test_name: Name of the test
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body data
            headers: Request headers
            expected_status: Expected HTTP status code
            
        Returns:
            Response object if successful, None otherwise
        """
        self.stats['tests_run'] += 1
        
        url = f"{self.base_url}{endpoint}"
        
        logger.info(f"Testing: {test_name}")
        logger.info(f"  {method} {url}")
        
        if self.dry_run:
            logger.info(f"  [DRY RUN] Would send: {data}")
            self.stats['tests_passed'] += 1
            return None
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            else:
                logger.error(f"Unsupported method: {method}")
                self.stats['tests_failed'] += 1
                return None
            
            # Check status code
            if response.status_code == expected_status:
                logger.info(f"  ✓ Status: {response.status_code}")
                self.stats['tests_passed'] += 1
                
                # Log response
                try:
                    response_data = response.json()
                    logger.debug(f"  Response: {json.dumps(response_data, indent=2)}")
                except:
                    logger.debug(f"  Response: {response.text}")
                
                return response
            else:
                logger.error(f"  ✗ Expected status {expected_status}, got {response.status_code}")
                logger.error(f"  Response: {response.text}")
                self.stats['tests_failed'] += 1
                return None
                
        except Exception as e:
            logger.error(f"  ✗ Request failed: {e}")
            self.stats['tests_failed'] += 1
            return None
    
    def test_register(self):
        """Test user registration"""
        logger.info("")
        logger.info("="*80)
        logger.info("TEST: User Registration")
        logger.info("="*80)
        
        response = self.test_endpoint(
            "Register new user",
            "POST",
            "/api/auth/register",
            data={
                "email": self.test_email,
                "password": self.test_password,
                "display_name": self.test_display_name
            },
            expected_status=201
        )
        
        if response:
            data = response.json()
            self.access_token = data.get('access_token')
            self.refresh_token = data.get('refresh_token')
            self.user_id = data.get('user', {}).get('id')
            
            logger.info(f"  ✓ User ID: {self.user_id}")
            logger.info(f"  ✓ Access token received (length: {len(self.access_token)})")
            logger.info(f"  ✓ Refresh token received (length: {len(self.refresh_token)})")
            return True
        
        return False
    
    def test_login(self):
        """Test user login"""
        logger.info("")
        logger.info("="*80)
        logger.info("TEST: User Login")
        logger.info("="*80)
        
        response = self.test_endpoint(
            "Login with credentials",
            "POST",
            "/api/auth/login",
            data={
                "email": self.test_email,
                "password": self.test_password
            },
            expected_status=200
        )
        
        if response:
            data = response.json()
            self.access_token = data.get('access_token')
            self.refresh_token = data.get('refresh_token')
            
            logger.info(f"  ✓ Login successful")
            return True
        
        return False
    
    def test_login_invalid_password(self):
        """Test login with invalid password"""
        logger.info("")
        logger.info("="*80)
        logger.info("TEST: Login with Invalid Password")
        logger.info("="*80)
        
        response = self.test_endpoint(
            "Login with wrong password",
            "POST",
            "/api/auth/login",
            data={
                "email": self.test_email,
                "password": "wrongpassword"
            },
            expected_status=401
        )
        
        return response is not None
    
    def test_get_current_user(self):
        """Test getting current user info"""
        logger.info("")
        logger.info("="*80)
        logger.info("TEST: Get Current User")
        logger.info("="*80)
        
        if not self.access_token:
            logger.error("  ✗ No access token available")
            self.stats['tests_failed'] += 1
            return False
        
        response = self.test_endpoint(
            "Get current user info",
            "GET",
            "/api/auth/me",
            headers={"Authorization": f"Bearer {self.access_token}"},
            expected_status=200
        )
        
        if response:
            data = response.json()
            logger.info(f"  ✓ User email: {data.get('email')}")
            logger.info(f"  ✓ Display name: {data.get('display_name')}")
            return True
        
        return False
    
    def test_get_current_user_no_token(self):
        """Test getting current user without token"""
        logger.info("")
        logger.info("="*80)
        logger.info("TEST: Get Current User Without Token")
        logger.info("="*80)
        
        response = self.test_endpoint(
            "Get current user without token",
            "GET",
            "/api/auth/me",
            expected_status=401
        )
        
        return response is not None
    
    def test_refresh_token(self):
        """Test token refresh"""
        logger.info("")
        logger.info("="*80)
        logger.info("TEST: Refresh Token")
        logger.info("="*80)
        
        if not self.refresh_token:
            logger.error("  ✗ No refresh token available")
            self.stats['tests_failed'] += 1
            return False
        
        response = self.test_endpoint(
            "Refresh access token",
            "POST",
            "/api/auth/refresh-token",
            data={"refresh_token": self.refresh_token},
            expected_status=200
        )
        
        if response:
            data = response.json()
            self.access_token = data.get('access_token')
            self.refresh_token = data.get('refresh_token')
            
            logger.info(f"  ✓ New access token received")
            logger.info(f"  ✓ New refresh token received (rotated)")
            return True
        
        return False
    
    def test_change_password(self):
        """Test password change"""
        logger.info("")
        logger.info("="*80)
        logger.info("TEST: Change Password")
        logger.info("="*80)
        
        if not self.access_token:
            logger.error("  ✗ No access token available")
            self.stats['tests_failed'] += 1
            return False
        
        new_password = "newpass123"
        
        response = self.test_endpoint(
            "Change password",
            "POST",
            "/api/password/change-password",
            data={
                "current_password": self.test_password,
                "new_password": new_password
            },
            headers={"Authorization": f"Bearer {self.access_token}"},
            expected_status=200
        )
        
        if response:
            # Update test password for subsequent tests
            self.test_password = new_password
            logger.info(f"  ✓ Password changed successfully")
            return True
        
        return False
    
    def test_forgot_password(self):
        """Test forgot password flow"""
        logger.info("")
        logger.info("="*80)
        logger.info("TEST: Forgot Password")
        logger.info("="*80)
        
        response = self.test_endpoint(
            "Request password reset",
            "POST",
            "/api/password/forgot-password",
            data={"email": self.test_email},
            expected_status=200
        )
        
        if response:
            data = response.json()
            # In testing mode, token is returned (REMOVE IN PRODUCTION)
            reset_token = data.get('reset_token')
            if reset_token:
                logger.info(f"  ✓ Reset token: {reset_token}")
                self.reset_token = reset_token
            return True
        
        return False
    
    def test_logout(self):
        """Test user logout"""
        logger.info("")
        logger.info("="*80)
        logger.info("TEST: Logout")
        logger.info("="*80)
        
        if not self.access_token:
            logger.error("  ✗ No access token available")
            self.stats['tests_failed'] += 1
            return False
        
        response = self.test_endpoint(
            "Logout user",
            "POST",
            "/api/auth/logout",
            data={"refresh_token": self.refresh_token},
            headers={"Authorization": f"Bearer {self.access_token}"},
            expected_status=200
        )
        
        return response is not None
    
    def run_all_tests(self):
        """Run all authentication tests"""
        logger.info("="*80)
        logger.info("AUTHENTICATION ENDPOINTS TEST")
        logger.info("="*80)
        logger.info(f"Base URL: {self.base_url}")
        logger.info(f"Test email: {self.test_email}")
        
        if self.dry_run:
            logger.info("*** DRY RUN MODE - No actual requests will be made ***")
        
        logger.info("")
        
        # Test registration
        if not self.test_register():
            logger.error("Registration failed - stopping tests")
            return False
        
        # Test login
        self.test_login()
        
        # Test invalid login
        self.test_login_invalid_password()
        
        # Test protected endpoint
        self.test_get_current_user()
        
        # Test protected endpoint without token
        self.test_get_current_user_no_token()
        
        # Test token refresh
        self.test_refresh_token()
        
        # Test password change
        self.test_change_password()
        
        # Test forgot password
        self.test_forgot_password()
        
        # Test logout
        self.test_logout()
        
        return True
    
    def print_summary(self):
        """Print test summary"""
        logger.info("")
        logger.info("="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        logger.info(f"Tests run:    {self.stats['tests_run']}")
        logger.info(f"Tests passed: {self.stats['tests_passed']}")
        logger.info(f"Tests failed: {self.stats['tests_failed']}")
        
        if self.stats['tests_failed'] == 0:
            logger.info("="*80)
            logger.info("✓ ALL TESTS PASSED")
            logger.info("="*80)
        else:
            logger.info("="*80)
            logger.info("✗ SOME TESTS FAILED")
            logger.info("="*80)


def main():
    parser = argparse.ArgumentParser(
        description='Test authentication endpoints for Phase 2 verification',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test against local server
  python scripts/test_auth_endpoints.py http://localhost:5001
  
  # Test against production
  python scripts/test_auth_endpoints.py https://jazzreference.onrender.com
  
  # Dry run to see what would be tested
  python scripts/test_auth_endpoints.py http://localhost:5001 --dry-run
  
  # With debug logging
  python scripts/test_auth_endpoints.py http://localhost:5001 --debug
        """
    )
    
    parser.add_argument(
        'base_url',
        help='Base URL of the API (e.g., http://localhost:5001)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be tested without making requests'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create tester and run
    tester = AuthEndpointTester(args.base_url, dry_run=args.dry_run)
    
    try:
        success = tester.run_all_tests()
        tester.print_summary()
        
        sys.exit(0 if tester.stats['tests_failed'] == 0 else 1)
        
    except KeyboardInterrupt:
        logger.info("\nTests cancelled by user")
        tester.print_summary()
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()