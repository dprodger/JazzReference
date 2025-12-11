"""
Authentication routes: register, login, token refresh, logout

This module handles core authentication operations including:
- User registration with email/password
- User login and token generation
- Access token refresh using refresh tokens
- User logout and token revocation
- Current user information retrieval
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
from email_service import send_welcome_email

# Google OAuth imports (ADD THESE LINES)
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Google OAuth configuration (NEW - ADD THIS)
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')

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

    # ADD THIS DEBUG LOGGING
    logger.info(f"🔍 Registration for: {email}")
    logger.info(f"🔍 Password length: {len(password) if password else 0}")
    logger.info(f"🔍 Password first char: {repr(password[0]) if password else 'N/A'}")
    logger.info(f"🔍 Password last char: {repr(password[-1]) if password else 'N/A'}")
    logger.info(f"🔍 Password repr: {repr(password)}")
    # END DEBUG LOGGING
    
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
                
                # Send welcome email (non-blocking - don't fail registration if email fails)
                try:
                    send_welcome_email(email, display_name)
                except Exception as email_error:
                    logger.warning(f"Welcome email failed for {email}: {email_error}")
                
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

    # ADD THIS DEBUG LOGGING
    logger.info(f"🔍 Login attempt for: {email}")
    logger.info(f"🔍 Password length: {len(password) if password else 0}")
    logger.info(f"🔍 Password first char: {repr(password[0]) if password else 'N/A'}")
    logger.info(f"🔍 Password last char: {repr(password[-1]) if password else 'N/A'}")
    logger.info(f"🔍 Password repr: {repr(password)}")
    # END DEBUG LOGGING
    
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
    
@auth_bp.route('/google', methods=['POST'])
def google_login():
    """
    Authenticate with Google ID token
    
    Request body:
        {
            "id_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6..."
        }
    
    Returns:
        200: {
            "user": {"id": "...", "email": "...", "display_name": "..."},
            "access_token": "...",
            "refresh_token": "..."
        }
        400: Invalid input
        401: Invalid token
        500: Server error
    """
    data = request.get_json()
    id_token_str = data.get('id_token')
    
    if not id_token_str:
        return jsonify({'error': 'ID token required'}), 400
    
    if not GOOGLE_CLIENT_ID:
        logger.error("GOOGLE_CLIENT_ID not configured")
        return jsonify({'error': 'Google authentication not configured'}), 500
    
    try:
        # Verify Google ID token
        idinfo = google_id_token.verify_oauth2_token(
            id_token_str, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID
        )
        
        # Extract user information from token
        google_id = idinfo['sub']
        email = idinfo['email']
        display_name = idinfo.get('name')
        profile_image = idinfo.get('picture')
        
        logger.info(f"🔐 Google login attempt for: {email}")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if user exists with this Google ID or email
                cur.execute("""
                    SELECT id, email, display_name, google_id
                    FROM users
                    WHERE google_id = %s OR email = %s
                """, (google_id, email))
                
                user = cur.fetchone()
                
                if user:
                    # User exists
                    user_id = user['id']
                    
                    # Update Google ID if not set (linking existing email account)
                    if not user.get('google_id'):
                        logger.info(f"🔗 Linking Google account to existing user: {email}")
                        cur.execute("""
                            UPDATE users
                            SET google_id = %s, 
                                email_verified = true,
                                profile_image_url = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (google_id, profile_image, user_id))
                        conn.commit()
                else:
                    # Create new user
                    logger.info(f"✨ Creating new user via Google: {email}")
                    cur.execute("""
                        INSERT INTO users (
                            email, google_id, display_name, 
                            profile_image_url, email_verified
                        )
                        VALUES (%s, %s, %s, %s, true)
                        RETURNING id
                    """, (email, google_id, display_name, profile_image))
                    
                    result = cur.fetchone()
                    user_id = result['id']
                    conn.commit()
                
                # Generate tokens
                access_token = generate_access_token(user_id)
                refresh_token = generate_refresh_token(user_id)
                
                # Store refresh token
                cur.execute("""
                    INSERT INTO refresh_tokens (user_id, token, expires_at)
                    VALUES (%s, %s, NOW() + INTERVAL '30 days')
                """, (user_id, refresh_token))
                conn.commit()
                
                # Get complete user details
                cur.execute("""
                    SELECT id, email, display_name, profile_image_url, email_verified
                    FROM users WHERE id = %s
                """, (user_id,))
                
                user_data = cur.fetchone()
                
                logger.info(f"✅ Google login successful for: {email}")
                
                return jsonify({
                    'user': {
                        'id': str(user_data['id']),
                        'email': user_data['email'],
                        'display_name': user_data['display_name'],
                        'profile_image_url': user_data.get('profile_image_url'),
                        'email_verified': user_data.get('email_verified', False)
                    },
                    'access_token': access_token,
                    'refresh_token': refresh_token
                }), 200
                
    except ValueError as e:
        logger.warning(f"Invalid Google token: {e}")
        return jsonify({'error': f'Invalid token: {str(e)}'}), 401
    except Exception as e:
        logger.error(f"Google login error: {e}", exc_info=True)
        return jsonify({'error': 'Authentication failed'}), 500 