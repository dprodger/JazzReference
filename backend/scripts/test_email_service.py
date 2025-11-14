#!/usr/bin/env python3
"""
Test email service functionality

This script tests the email service by sending test emails for:
- Password reset
- Email verification
- Welcome email

Can be run in dry-run mode to test without sending actual emails.
"""

import sys
import argparse
import logging
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # ADD THIS LINE

# Load environment variables from .env file
load_dotenv()  # ADD THIS LINE


import email_service
from auth_utils import generate_reset_token

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('log/test_email_service.log')
    ]
)
logger = logging.getLogger(__name__)


def test_password_reset_email(test_email, dry_run=False):
    """Test password reset email"""
    logger.info("")
    logger.info("="*80)
    logger.info("TEST: Password Reset Email")
    logger.info("="*80)
    
    if dry_run:
        logger.info(f"[DRY RUN] Would send password reset email to: {test_email}")
        return True
    
    # Generate a test token
    token = generate_reset_token()
    logger.info(f"Generated test token: {token[:20]}...")
    
    success = email_service.send_password_reset_email(test_email, token)
    
    if success:
        logger.info("✓ Password reset email sent successfully")
        return True
    else:
        logger.error("✗ Password reset email failed")
        return False


def test_verification_email(test_email, dry_run=False):
    """Test email verification email"""
    logger.info("")
    logger.info("="*80)
    logger.info("TEST: Email Verification")
    logger.info("="*80)
    
    if dry_run:
        logger.info(f"[DRY RUN] Would send verification email to: {test_email}")
        return True
    
    # Generate a test token
    token = generate_reset_token()
    logger.info(f"Generated test token: {token[:20]}...")
    
    success = email_service.send_verification_email(test_email, token)
    
    if success:
        logger.info("✓ Verification email sent successfully")
        return True
    else:
        logger.error("✗ Verification email failed")
        return False


def test_welcome_email(test_email, display_name, dry_run=False):
    """Test welcome email"""
    logger.info("")
    logger.info("="*80)
    logger.info("TEST: Welcome Email")
    logger.info("="*80)
    
    if dry_run:
        logger.info(f"[DRY RUN] Would send welcome email to: {test_email}")
        return True
    
    success = email_service.send_welcome_email(test_email, display_name)
    
    if success:
        logger.info("✓ Welcome email sent successfully")
        return True
    else:
        logger.error("✗ Welcome email failed")
        return False


def check_configuration():
    """Check if email service is properly configured"""
    logger.info("")
    logger.info("="*80)
    logger.info("EMAIL SERVICE CONFIGURATION")
    logger.info("="*80)
    
    logger.info(f"SendGrid API Key: {'✓ Set' if email_service.SENDGRID_API_KEY else '✗ Not set'}")
    logger.info(f"From Email: {email_service.FROM_EMAIL}")
    logger.info(f"Frontend URL: {email_service.FRONTEND_URL}")
    logger.info(f"API Base URL: {email_service.API_BASE_URL}")
    logger.info(f"SendGrid Configured: {'✓ Yes' if email_service.SENDGRID_CONFIGURED else '✗ No'}")
    
    if not email_service.SENDGRID_CONFIGURED:
        logger.warning("")
        logger.warning("⚠️  SendGrid is not configured!")
        logger.warning("Set the SENDGRID_API_KEY environment variable to enable email sending.")
        logger.warning("Emails will be logged but not actually sent.")
        return False
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Test email service functionality',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check configuration only
  python scripts/test_email_service.py --check-only
  
  # Test all emails (dry run)
  python scripts/test_email_service.py test@example.com --dry-run
  
  # Test password reset email
  python scripts/test_email_service.py test@example.com --test password-reset
  
  # Test all emails
  python scripts/test_email_service.py test@example.com --test all
  
  # With debug logging
  python scripts/test_email_service.py test@example.com --debug

Configuration:
  Set these environment variables:
  - SENDGRID_API_KEY: Your SendGrid API key (required)
  - FROM_EMAIL: Sender email address (default: noreply@jazzreference.com)
  - FRONTEND_URL: Frontend URL for links (default: jazzreference://auth)
        """
    )
    
    parser.add_argument(
        'email',
        nargs='?',
        help='Email address to send test emails to'
    )
    
    parser.add_argument(
        '--test',
        choices=['all', 'password-reset', 'verification', 'welcome'],
        default='all',
        help='Which email type to test (default: all)'
    )
    
    parser.add_argument(
        '--display-name',
        default='Test User',
        help='Display name for welcome email (default: Test User)'
    )
    
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='Only check configuration without sending emails'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be sent without actually sending'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("="*80)
    logger.info("EMAIL SERVICE TEST")
    logger.info("="*80)
    
    # Check configuration
    configured = check_configuration()
    
    if args.check_only:
        return 0 if configured else 1
    
    if not args.email:
        logger.error("Error: Email address required unless using --check-only")
        return 1
    
    if args.dry_run:
        logger.info("")
        logger.info("*** DRY RUN MODE - No actual emails will be sent ***")
    
    # Run tests
    results = []
    
    if args.test in ['all', 'password-reset']:
        results.append(('Password Reset', test_password_reset_email(args.email, args.dry_run)))
    
    if args.test in ['all', 'verification']:
        results.append(('Verification', test_verification_email(args.email, args.dry_run)))
    
    if args.test in ['all', 'welcome']:
        results.append(('Welcome', test_welcome_email(args.email, args.display_name, args.dry_run)))
    
    # Print summary
    logger.info("")
    logger.info("="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    
    for test_name, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(success for _, success in results)
    
    if all_passed:
        logger.info("="*80)
        logger.info("✓ ALL TESTS PASSED")
        logger.info("="*80)
        return 0
    else:
        logger.info("="*80)
        logger.info("✗ SOME TESTS FAILED")
        logger.info("="*80)
        return 1


if __name__ == '__main__':
    sys.exit(main())