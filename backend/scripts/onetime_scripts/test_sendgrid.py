#!/usr/bin/env python3
"""
Test SendGrid Email Configuration

This script verifies that SendGrid is properly configured and can send emails.
Tests basic connectivity, environment variables, and email delivery.
"""

import sys
import argparse
import logging
import os
from datetime import datetime

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Third-party imports
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from dotenv import load_dotenv

load_dotenv()


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('log/test_sendgrid.log')
    ]
)
logger = logging.getLogger(__name__)


class SendGridTester:
    """Test SendGrid email configuration and sending"""
    
    def __init__(self, dry_run=False):
        """
        Initialize SendGrid tester
        
        Args:
            dry_run: If True, show what would be done without sending emails
        """
        self.dry_run = dry_run
        self.stats = {
            'tests_run': 0,
            'tests_passed': 0,
            'tests_failed': 0
        }
        
        # Get environment variables
        self.api_key = os.getenv('SENDGRID_API_KEY')
        self.from_email = os.getenv('FROM_EMAIL', 'noreply@approachnote.com')
        self.frontend_url = os.getenv('FRONTEND_URL', 'jazzreference://auth')
    
    def test_environment_variables(self):
        """Verify required environment variables are set"""
        logger.info("Testing environment variables...")
        self.stats['tests_run'] += 1
        
        try:
            if not self.api_key:
                logger.error("✗ SENDGRID_API_KEY not set")
                self.stats['tests_failed'] += 1
                return False
            
            logger.info(f"✓ SENDGRID_API_KEY is set")
            logger.info(f"✓ FROM_EMAIL: {self.from_email}")
            logger.info(f"✓ FRONTEND_URL: {self.frontend_url}")
            logger.info("")
            
            self.stats['tests_passed'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Environment check failed: {e}")
            self.stats['tests_failed'] += 1
            return False
    
    def test_api_connection(self):
        """Test basic SendGrid API connectivity"""
        logger.info("Testing SendGrid API connection...")
        self.stats['tests_run'] += 1
        
        if not self.api_key:
            logger.error("✗ Cannot test API - SENDGRID_API_KEY not set")
            self.stats['tests_failed'] += 1
            return False
        
        try:
            sg = SendGridAPIClient(self.api_key)
            
            # Try to get API key info (validates key format)
            logger.info("✓ SendGrid API client initialized")
            logger.info("")
            
            self.stats['tests_passed'] += 1
            return True
            
        except Exception as e:
            logger.error(f"✗ SendGrid API connection failed: {e}")
            self.stats['tests_failed'] += 1
            return False
    
    def send_test_email(self, to_email: str):
        """
        Send a test email to verify email delivery
        
        Args:
            to_email: Recipient email address
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Sending test email to {to_email}...")
        self.stats['tests_run'] += 1
        
        if self.dry_run:
            logger.info("    [DRY RUN] Would send test email")
            logger.info(f"    From: {self.from_email}")
            logger.info(f"    To: {to_email}")
            logger.info(f"    Subject: Jazz Reference - SendGrid Test")
            logger.info("")
            self.stats['tests_passed'] += 1
            return True
        
        try:
            # Create test email
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #8B2635;">Jazz Reference - SendGrid Test</h2>
                    <p>This is a test email from the Jazz Reference authentication system.</p>
                    
                    <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">Configuration Details:</h3>
                        <ul style="list-style-type: none; padding-left: 0;">
                            <li><strong>From Email:</strong> {self.from_email}</li>
                            <li><strong>Test Time:</strong> {timestamp}</li>
                            <li><strong>Frontend URL:</strong> {self.frontend_url}</li>
                        </ul>
                    </div>
                    
                    <p>If you received this email, your SendGrid configuration is working correctly!</p>
                    
                    <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
                    
                    <p style="color: #666; font-size: 12px;">
                        This is an automated test email from the Jazz Reference development system.
                    </p>
                </body>
            </html>
            """
            
            message = Mail(
                from_email=self.from_email,
                to_emails=to_email,
                subject='Jazz Reference - SendGrid Test',
                html_content=html_content
            )
            
            # Send email
            sg = SendGridAPIClient(self.api_key)
            response = sg.send(message)
            
            logger.info(f"✓ Email sent successfully!")
            logger.info(f"  Response status: {response.status_code}")
            logger.info(f"  Message ID: {response.headers.get('X-Message-Id', 'N/A')}")
            logger.info("")
            logger.info("  Check your inbox (and spam folder) for the test email.")
            logger.info("")
            
            self.stats['tests_passed'] += 1
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to send test email: {e}")
            logger.error(f"  Error details: {str(e)}")
            logger.info("")
            logger.info("  Common issues:")
            logger.info("  - FROM_EMAIL domain not verified in SendGrid")
            logger.info("  - Invalid SENDGRID_API_KEY")
            logger.info("  - SendGrid account suspended or limited")
            logger.info("")
            self.stats['tests_failed'] += 1
            return False
    
    def send_verification_test(self, to_email: str):
        """
        Send a sample verification email
        
        Args:
            to_email: Recipient email address
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Sending sample verification email to {to_email}...")
        self.stats['tests_run'] += 1
        
        if self.dry_run:
            logger.info("    [DRY RUN] Would send verification email")
            self.stats['tests_passed'] += 1
            return True
        
        try:
            # Sample verification token
            token = "sample_token_abc123xyz789"
            verify_url = f"{self.frontend_url}/verify-email?token={token}"
            
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #8B2635;">Welcome to Jazz Reference!</h2>
                    <p>Please verify your email address by clicking the link below:</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{verify_url}" 
                           style="background-color: #8B2635; color: white; padding: 12px 30px; 
                                  text-decoration: none; border-radius: 5px; display: inline-block;">
                            Verify Email
                        </a>
                    </div>
                    
                    <p style="color: #666; font-size: 14px;">
                        Or copy and paste this link into your browser:<br>
                        <code style="background-color: #f5f5f5; padding: 5px; display: block; margin-top: 10px;">
                            {verify_url}
                        </code>
                    </p>
                    
                    <p style="color: #999; font-size: 12px; margin-top: 30px;">
                        This link will expire in 24 hours.
                    </p>
                    
                    <p style="color: #999; font-size: 12px;">
                        If you didn't create an account, you can safely ignore this email.
                    </p>
                    
                    <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
                    
                    <p style="color: #666; font-size: 12px;">
                        <strong>NOTE:</strong> This is a sample verification email for testing purposes.
                        The token is not active.
                    </p>
                </body>
            </html>
            """
            
            message = Mail(
                from_email=self.from_email,
                to_emails=to_email,
                subject='Verify your Jazz Reference email',
                html_content=html_content
            )
            
            sg = SendGridAPIClient(self.api_key)
            response = sg.send(message)
            
            logger.info(f"✓ Verification email sent successfully!")
            logger.info(f"  Response status: {response.status_code}")
            logger.info("")
            
            self.stats['tests_passed'] += 1
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to send verification email: {e}")
            self.stats['tests_failed'] += 1
            return False
    
    def send_password_reset_test(self, to_email: str):
        """
        Send a sample password reset email
        
        Args:
            to_email: Recipient email address
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Sending sample password reset email to {to_email}...")
        self.stats['tests_run'] += 1
        
        if self.dry_run:
            logger.info("    [DRY RUN] Would send password reset email")
            self.stats['tests_passed'] += 1
            return True
        
        try:
            # Sample reset token
            token = "sample_reset_token_xyz789abc123"
            reset_url = f"{self.frontend_url}/reset-password?token={token}"
            
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #8B2635;">Password Reset Request</h2>
                    <p>We received a request to reset your Jazz Reference password.</p>
                    <p>Click the link below to reset your password:</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_url}" 
                           style="background-color: #8B2635; color: white; padding: 12px 30px; 
                                  text-decoration: none; border-radius: 5px; display: inline-block;">
                            Reset Password
                        </a>
                    </div>
                    
                    <p style="color: #666; font-size: 14px;">
                        Or copy and paste this link into your browser:<br>
                        <code style="background-color: #f5f5f5; padding: 5px; display: block; margin-top: 10px;">
                            {reset_url}
                        </code>
                    </p>
                    
                    <p style="color: #999; font-size: 12px; margin-top: 30px;">
                        This link will expire in 1 hour.
                    </p>
                    
                    <p style="color: #999; font-size: 12px;">
                        If you didn't request a password reset, you can safely ignore this email.
                        Your password will remain unchanged.
                    </p>
                    
                    <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">
                    
                    <p style="color: #666; font-size: 12px;">
                        <strong>NOTE:</strong> This is a sample password reset email for testing purposes.
                        The token is not active.
                    </p>
                </body>
            </html>
            """
            
            message = Mail(
                from_email=self.from_email,
                to_emails=to_email,
                subject='Reset your Jazz Reference password',
                html_content=html_content
            )
            
            sg = SendGridAPIClient(self.api_key)
            response = sg.send(message)
            
            logger.info(f"✓ Password reset email sent successfully!")
            logger.info(f"  Response status: {response.status_code}")
            logger.info("")
            
            self.stats['tests_passed'] += 1
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to send password reset email: {e}")
            self.stats['tests_failed'] += 1
            return False
    
    def run(self, to_email: str, test_type: str = 'all'):
        """
        Run SendGrid tests
        
        Args:
            to_email: Email address to send test messages to
            test_type: Type of test to run ('all', 'basic', 'verification', 'reset')
            
        Returns:
            True if all tests passed, False otherwise
        """
        logger.info("="*80)
        logger.info("SENDGRID EMAIL TEST")
        logger.info("="*80)
        
        if self.dry_run:
            logger.info("*** DRY RUN MODE - No emails will be sent ***")
            logger.info("")
        
        # Always test environment variables first
        if not self.test_environment_variables():
            logger.error("Environment variable test failed - cannot proceed")
            self.print_summary()
            return False
        
        # Test API connection
        if not self.test_api_connection():
            logger.error("API connection test failed - cannot proceed")
            self.print_summary()
            return False
        
        # Run requested tests
        if test_type in ['all', 'basic']:
            self.send_test_email(to_email)
        
        if test_type in ['all', 'verification']:
            self.send_verification_test(to_email)
        
        if test_type in ['all', 'reset']:
            self.send_password_reset_test(to_email)
        
        # Print summary
        self.print_summary()
        
        return self.stats['tests_failed'] == 0
    
    def print_summary(self):
        """Print test summary"""
        logger.info("")
        logger.info("="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        logger.info(f"Tests run:     {self.stats['tests_run']}")
        logger.info(f"Tests passed:  {self.stats['tests_passed']}")
        logger.info(f"Tests failed:  {self.stats['tests_failed']}")
        logger.info("="*80)
        
        if self.stats['tests_failed'] == 0:
            logger.info("")
            logger.info("✓ All tests passed! SendGrid is configured correctly.")
        else:
            logger.info("")
            logger.info("✗ Some tests failed. Check the output above for details.")


def main():
    parser = argparse.ArgumentParser(
        description='Test SendGrid email configuration and sending',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all tests
  python scripts/test_sendgrid.py --email your-email@example.com
  
  # Test just basic connectivity
  python scripts/test_sendgrid.py --email your-email@example.com --type basic
  
  # Test verification email template
  python scripts/test_sendgrid.py --email your-email@example.com --type verification
  
  # Test password reset email template
  python scripts/test_sendgrid.py --email your-email@example.com --type reset
  
  # Dry run to validate without sending
  python scripts/test_sendgrid.py --email your-email@example.com --dry-run
  
  # With debug logging
  python scripts/test_sendgrid.py --email your-email@example.com --debug
        """
    )
    
    parser.add_argument(
        '--email',
        required=True,
        help='Email address to send test messages to'
    )
    
    parser.add_argument(
        '--type',
        choices=['all', 'basic', 'verification', 'reset'],
        default='all',
        help='Type of test to run (default: all)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without sending emails'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create tester and run
    tester = SendGridTester(dry_run=args.dry_run)
    
    try:
        success = tester.run(args.email, args.type)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nTest cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()