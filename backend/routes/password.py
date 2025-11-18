"""
Password management routes: forgot password, reset password, change password

This module handles password-related operations including:
- Password reset requests
- Password reset with token validation
- Password changes for authenticated users
"""

from flask import Blueprint, request, jsonify, g
import sys
import os
import logging
from datetime import datetime, timedelta, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_utils import get_db_connection
from auth_utils import hash_password, verify_password, generate_reset_token
from middleware.auth_middleware import require_auth
from email_service import send_password_reset_email

logger = logging.getLogger(__name__)
password_bp = Blueprint('password', __name__, url_prefix='/api/auth')


@password_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """
    Request password reset email
    
    Request body:
        {
            "email": "user@example.com"
        }
    
    Returns:
        200: {"message": "If that email exists, a reset link has been sent"}
        400: Invalid input
        500: Server error
    
    Note: Always returns success to prevent email enumeration attacks
    """
    data = request.get_json()
    email = data.get('email')
    
    if not email:
        return jsonify({'error': 'Email required'}), 400
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if user exists
                cur.execute("SELECT id FROM users WHERE email = %s", (email,))
                user = cur.fetchone()
                
                # Always return success to prevent email enumeration
                if not user:
                    logger.info(f"Password reset requested for non-existent email: {email}")
                    return jsonify({'message': 'If that email exists, a reset link has been sent'}), 200
                
                # Generate reset token
                reset_token = generate_reset_token()
                expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
                
                # Store token
                cur.execute("""
                    INSERT INTO password_reset_tokens (user_id, token, expires_at)
                    VALUES (%s, %s, %s)
                """, (user['id'], reset_token, expires_at))
                conn.commit()
                
                # Send password reset email
                email_sent = send_password_reset_email(email, reset_token)
                
                if email_sent:
                    logger.info(f"Password reset email sent to: {email}")
                else:
                    # Email failed to send, but still return success to user
                    # (logged in email_service.py)
                    logger.warning(f"Password reset email failed for: {email}")
                
                return jsonify({
                    'message': 'If that email exists, a reset link has been sent'
                }), 200
                
    except Exception as e:
        logger.error(f"Forgot password error: {e}", exc_info=True)
        return jsonify({'error': 'Request failed'}), 500


@password_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """
    Reset password using token
    
    Request body:
        {
            "token": "...",
            "password": "newpassword123"
        }
    
    Returns:
        200: {"message": "Password reset successfully"}
        400: Invalid input
        401: Invalid or expired token
        500: Server error
    """
    data = request.get_json()
    
    token = data.get('token')
    new_password = data.get('password')
    
    if not token or not new_password:
        return jsonify({'error': 'Token and password required'}), 400
    
    if len(new_password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Verify token
                cur.execute("""
                    SELECT user_id FROM password_reset_tokens
                    WHERE token = %s
                    AND expires_at > NOW()
                    AND used_at IS NULL
                """, (token,))
                
                result = cur.fetchone()
                
                if not result:
                    return jsonify({'error': 'Invalid or expired token'}), 401
                
                user_id = result['user_id']
                
                # Update password
                password_hash = hash_password(new_password)
                
                cur.execute("""
                    UPDATE users
                    SET password_hash = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (password_hash, user_id))
                
                # Mark token as used
                cur.execute("""
                    UPDATE password_reset_tokens
                    SET used_at = NOW()
                    WHERE token = %s
                """, (token,))
                
                conn.commit()
                
                logger.info(f"Password reset completed for user: {user_id}")
                
                return jsonify({'message': 'Password reset successfully'}), 200
                
    except Exception as e:
        logger.error(f"Reset password error: {e}", exc_info=True)
        return jsonify({'error': 'Reset failed'}), 500


@password_bp.route('/change-password', methods=['POST'])
@require_auth
def change_password():
    """
    Change password for authenticated user
    
    Headers:
        Authorization: Bearer <access_token>
    
    Request body:
        {
            "current_password": "oldpassword123",
            "new_password": "newpassword123"
        }
    
    Returns:
        200: {"message": "Password changed successfully"}
        400: Invalid input
        401: Current password is incorrect
        500: Server error
    """
    data = request.get_json()
    
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not current_password or not new_password:
        return jsonify({'error': 'Current and new password required'}), 400
    
    if len(new_password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    
    if current_password == new_password:
        return jsonify({'error': 'New password must be different from current password'}), 400
    
    try:
        user_id = g.current_user['id']
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get current password hash
                cur.execute("""
                    SELECT password_hash FROM users WHERE id = %s
                """, (user_id,))
                
                user = cur.fetchone()
                
                if not user:
                    return jsonify({'error': 'User not found'}), 404
                
                # Verify current password
                if not verify_password(current_password, user['password_hash']):
                    return jsonify({'error': 'Current password is incorrect'}), 401
                
                # Update password
                new_password_hash = hash_password(new_password)
                
                cur.execute("""
                    UPDATE users
                    SET password_hash = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (new_password_hash, user_id))
                
                conn.commit()
                
                logger.info(f"Password changed for user: {user_id}")
                
                return jsonify({'message': 'Password changed successfully'}), 200
                
    except Exception as e:
        logger.error(f"Change password error: {e}", exc_info=True)
        return jsonify({'error': 'Password change failed'}), 500