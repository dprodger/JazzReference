"""
Authentication routes: register, login, logout, refresh token, get current user

This module provides the core authentication endpoints:
- POST /auth/register - Register new user with email/password
- POST /auth/login - Login with email/password
- POST /auth/refresh-token - Get new access token using refresh token
- GET /auth/me - Get current user info (requires authentication)
- POST /auth/logout - Logout and revoke refresh token
"""

from flask import Blueprint, request, jsonify, g
import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_utils import get_db_connection
from auth_utils import (
    hash_password, 
    verify_password, 
    generate_access_token, 
    generate_refresh_token,
    decode_token
)
from middleware.auth_middleware import require_auth

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register new user with email and password
    
    Request body:
        {
            "email": "user@example.com",
            "password": "password123",
            "display_name": "John Doe" (optional)
        }
    
    Returns:
        201: {
            "user": {"id": "...", "email": "...", "display_name": "..."},
            "access_token": "...",
            "refresh_token": "..."
        }
        400: Invalid input
        409: Email already registered
        500: Server error
    """
    data = request.get_json()
    
    email = data.get('email')
    password = data.get('password')
    display_name = data.get('display_name')
    
    # Validation
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    
    # Basic email validation
    if '@' not in email or '.' not in email:
        return jsonify({'error': 'Invalid email format'}), 400
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if email already exists
                cur.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cur.fetchone():
                    return jsonify({'error': 'Email already registered'}), 409
                
                # Create user
                password_hash = hash_password(password)
                
                cur.execute("""
                    INSERT INTO users (email, password_hash, display_name)
                    VALUES (%s, %s, %s)
                    RETURNING id, email, display_name, created_at
                """, (email, password_hash, display_name))
                
                user = cur.fetchone()
                conn.commit()
                
                # Generate tokens
                access_token = generate_access_token(user['id'])
                refresh_token = generate_refresh_token(user['id'])
                
                # Store refresh token
                cur.execute("""
                    INSERT INTO refresh_tokens (user_id, token, expires_at)
                    VALUES (%s, %s, NOW() + INTERVAL '30 days')
                """, (user['id'], refresh_token))
                conn.commit()
                
                logger.info(f"User registered: {email}")
                
                return jsonify({
                    'user': {
                        'id': str(user['id']),
                        'email': user['email'],
                        'display_name': user['display_name']
                    },
                    'access_token': access_token,
                    'refresh_token': refresh_token
                }), 201
                
    except Exception as e:
        logger.error(f"Registration error: {e}", exc_info=True)
        return jsonify({'error': 'Registration failed'}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Login with email and password
    
    Request body:
        {
            "email": "user@example.com",
            "password": "password123"
        }
    
    Returns:
        200: {
            "user": {"id": "...", "email": "...", "display_name": "..."},
            "access_token": "...",
            "refresh_token": "..."
        }
        400: Invalid input
        401: Invalid credentials or account locked
        500: Server error
    """
    data = request.get_json()
    
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get user
                cur.execute("""
                    SELECT id, email, password_hash, display_name, 
                           is_active, account_locked, failed_login_attempts
                    FROM users
                    WHERE email = %s
                """, (email,))
                
                user = cur.fetchone()
                
                if not user:
                    return jsonify({'error': 'Invalid credentials'}), 401
                
                # Check account status
                if not user['is_active']:
                    return jsonify({'error': 'Account is inactive'}), 401
                
                if user['account_locked']:
                    return jsonify({'error': 'Account is locked. Please contact support.'}), 401
                
                # Verify password
                if not verify_password(password, user['password_hash']):
                    # Increment failed attempts
                    cur.execute("""
                        UPDATE users
                        SET failed_login_attempts = failed_login_attempts + 1,
                            last_failed_login_at = NOW(),
                            account_locked = CASE 
                                WHEN failed_login_attempts >= 4 THEN true 
                                ELSE false 
                            END
                        WHERE id = %s
                    """, (user['id'],))
                    conn.commit()
                    
                    return jsonify({'error': 'Invalid credentials'}), 401
                
                # Reset failed attempts on successful login
                cur.execute("""
                    UPDATE users
                    SET failed_login_attempts = 0,
                        last_login_at = NOW()
                    WHERE id = %s
                """, (user['id'],))
                conn.commit()
                
                # Generate tokens
                access_token = generate_access_token(user['id'])
                refresh_token = generate_refresh_token(user['id'])
                
                # Store refresh token
                cur.execute("""
                    INSERT INTO refresh_tokens (user_id, token, expires_at)
                    VALUES (%s, %s, NOW() + INTERVAL '30 days')
                """, (user['id'], refresh_token))
                conn.commit()
                
                logger.info(f"User logged in: {email}")
                
                return jsonify({
                    'user': {
                        'id': str(user['id']),
                        'email': user['email'],
                        'display_name': user['display_name']
                    },
                    'access_token': access_token,
                    'refresh_token': refresh_token
                }), 200
                
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        return jsonify({'error': 'Login failed'}), 500


@auth_bp.route('/refresh-token', methods=['POST'])
def refresh_token():
    """
    Get new access token using refresh token
    
    Request body:
        {
            "refresh_token": "..."
        }
    
    Returns:
        200: {
            "access_token": "...",
            "refresh_token": "..." (new refresh token)
        }
        400: Missing refresh token
        401: Invalid or expired refresh token
        500: Server error
    """
    data = request.get_json()
    refresh_token_value = data.get('refresh_token')
    
    if not refresh_token_value:
        return jsonify({'error': 'Refresh token required'}), 400
    
    try:
        # Decode token
        payload = decode_token(refresh_token_value)
        
        if payload.get('type') != 'refresh':
            return jsonify({'error': 'Invalid token type'}), 401
        
        user_id = payload['user_id']
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Verify refresh token exists and is not revoked
                cur.execute("""
                    SELECT id FROM refresh_tokens
                    WHERE token = %s 
                    AND user_id = %s
                    AND revoked_at IS NULL
                    AND expires_at > NOW()
                """, (refresh_token_value, user_id))
                
                if not cur.fetchone():
                    return jsonify({'error': 'Invalid or expired refresh token'}), 401
                
                # Generate new access token
                access_token = generate_access_token(user_id)
                
                # Rotate refresh token (more secure)
                new_refresh_token = generate_refresh_token(user_id)
                
                # Revoke old refresh token
                cur.execute("""
                    UPDATE refresh_tokens
                    SET revoked_at = NOW()
                    WHERE token = %s
                """, (refresh_token_value,))
                
                # Store new refresh token
                cur.execute("""
                    INSERT INTO refresh_tokens (user_id, token, expires_at)
                    VALUES (%s, %s, NOW() + INTERVAL '30 days')
                """, (user_id, new_refresh_token))
                
                conn.commit()
                
                return jsonify({
                    'access_token': access_token,
                    'refresh_token': new_refresh_token
                }), 200
                
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        logger.error(f"Token refresh error: {e}", exc_info=True)
        return jsonify({'error': 'Token refresh failed'}), 500


@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user():
    """
    Get current user info (requires valid access token)
    
    Headers:
        Authorization: Bearer <access_token>
    
    Returns:
        200: {
            "id": "...",
            "email": "...",
            "display_name": "..."
        }
        401: Invalid or missing token
    """
    user = g.current_user
    
    return jsonify({
        'id': str(user['id']),
        'email': user['email'],
        'display_name': user['display_name']
    }), 200


@auth_bp.route('/logout', methods=['POST'])
@require_auth
def logout():
    """
    Logout and revoke refresh token
    
    Headers:
        Authorization: Bearer <access_token>
    
    Request body:
        {
            "refresh_token": "..." (optional)
        }
    
    Returns:
        200: {"message": "Logged out successfully"}
        401: Invalid or missing token
    """
    data = request.get_json() or {}
    refresh_token_value = data.get('refresh_token')
    
    if refresh_token_value:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Revoke refresh token
                    cur.execute("""
                        UPDATE refresh_tokens
                        SET revoked_at = NOW()
                        WHERE token = %s AND user_id = %s
                    """, (refresh_token_value, g.current_user['id']))
                    conn.commit()
        except Exception as e:
            logger.error(f"Logout error: {e}", exc_info=True)
    
    return jsonify({'message': 'Logged out successfully'}), 200