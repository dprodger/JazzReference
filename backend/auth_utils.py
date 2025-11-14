"""
Authentication utilities for JWT token management and password hashing

This module provides core authentication functionality including:
- JWT access and refresh token generation
- Password hashing with bcrypt
- Token validation and decoding
- Secure random token generation for password resets
"""

import os
import jwt
import bcrypt
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

# JWT Configuration
JWT_SECRET = os.getenv('JWT_SECRET')
if not JWT_SECRET:
    raise ValueError("JWT_SECRET environment variable must be set")

JWT_ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRY = timedelta(minutes=15)
REFRESH_TOKEN_EXPIRY = timedelta(days=30)


def hash_password(password: str) -> str:
    """
    Hash password using bcrypt with work factor 12
    
    Args:
        password: Plain text password to hash
        
    Returns:
        Bcrypt hashed password as string
    """
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify password against bcrypt hash
    
    Args:
        password: Plain text password to verify
        password_hash: Bcrypt hash to verify against
        
    Returns:
        True if password matches hash, False otherwise
    """
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False


def generate_access_token(user_id: str) -> str:
    """
    Generate JWT access token (15 minutes expiry)
    
    Args:
        user_id: UUID of the user
        
    Returns:
        JWT token as string
    """
    payload = {
        'user_id': str(user_id),
        'exp': datetime.now(timezone.utc) + ACCESS_TOKEN_EXPIRY,
        'iat': datetime.now(timezone.utc),
        'type': 'access'
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def generate_refresh_token(user_id: str) -> str:
    """
    Generate JWT refresh token (30 days expiry)
    
    Args:
        user_id: UUID of the user
        
    Returns:
        JWT token as string
    """
    payload = {
        'user_id': str(user_id),
        'exp': datetime.now(timezone.utc) + REFRESH_TOKEN_EXPIRY,
        'iat': datetime.now(timezone.utc),
        'type': 'refresh'
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and validate JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        ValueError: If token is expired or invalid
    """
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ValueError('Token has expired')
    except jwt.InvalidTokenError:
        raise ValueError('Invalid token')


def generate_reset_token() -> str:
    """
    Generate secure random token for password reset
    
    Returns:
        URL-safe random token string (32 bytes = 43 characters base64)
    """
    return secrets.token_urlsafe(32)


def generate_verification_token() -> str:
    """
    Generate secure random token for email verification
    
    Returns:
        URL-safe random token string (32 bytes = 43 characters base64)
    """
    return secrets.token_urlsafe(32)