"""
JWT authentication for Admin API.

Validates API keys against LiteLLM and issues JWT tokens
for subsequent admin requests.
"""

import os
import logging
from typing import Optional
from datetime import datetime, timedelta, timezone

import jwt
import httpx
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()

# JWT configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-in-production-please")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 8

# Validate JWT secret at startup
_environment = os.getenv("ENVIRONMENT", "development")
if _environment == "production" and JWT_SECRET_KEY == "change-in-production-please":
    raise RuntimeError(
        "FATAL: JWT_SECRET_KEY is set to the default value in production. "
        "Set a strong, unique JWT_SECRET_KEY environment variable."
    )

# LiteLLM configuration
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "$LITELLM_KEY")


class LoginRequest(BaseModel):
    """Login request with API key."""
    api_key: str


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    expires_at: str


class UserInfo(BaseModel):
    """Authenticated user information."""
    user_id: str
    role: str
    team_id: Optional[str] = None
    is_admin: bool = False


async def validate_api_key(api_key: str) -> Optional[dict]:
    """
    Validate API key against LiteLLM.

    Args:
        api_key: API key to validate

    Returns:
        Key info dict if valid, None otherwise
    """
    # Check if it's the master key
    if api_key == LITELLM_MASTER_KEY:
        return {
            "user_id": "admin",
            "role": "admin",
            "is_admin": True,
            "key": api_key,
        }

    # Validate against LiteLLM
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{LITELLM_URL}/key/info",
                params={"key": api_key},
                headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"}
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "user_id": data.get("user_id", "unknown"),
                    "role": data.get("metadata", {}).get("role", "user"),
                    "team_id": data.get("team_id"),
                    "is_admin": data.get("metadata", {}).get("is_admin", False),
                    "key_name": data.get("key_name"),
                }
    except Exception as e:
        logger.error(f"Failed to validate API key: {e}")

    return None


def create_access_token(user_info: dict) -> tuple[str, datetime]:
    """
    Create JWT access token.

    Args:
        user_info: User information to encode

    Returns:
        Tuple of (token, expiration datetime)
    """
    expires_at = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)

    payload = {
        "sub": user_info["user_id"],
        "role": user_info.get("role", "user"),
        "team_id": user_info.get("team_id"),
        "is_admin": user_info.get("is_admin", False),
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, expires_at


def decode_token(token: str) -> dict:
    """
    Decode and validate JWT token.

    Args:
        token: JWT token to decode

    Returns:
        Decoded payload

    Raises:
        HTTPException: If token is invalid
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserInfo:
    """
    Get current authenticated user from JWT token.

    Args:
        credentials: Bearer token credentials

    Returns:
        UserInfo for authenticated user
    """
    payload = decode_token(credentials.credentials)

    return UserInfo(
        user_id=payload["sub"],
        role=payload.get("role", "user"),
        team_id=payload.get("team_id"),
        is_admin=payload.get("is_admin", False),
    )


async def require_admin(
    user: UserInfo = Depends(get_current_user)
) -> UserInfo:
    """
    Require admin role for endpoint.

    Args:
        user: Current user

    Returns:
        UserInfo if admin

    Raises:
        HTTPException: If not admin
    """
    if not user.is_admin and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def login(request: LoginRequest) -> TokenResponse:
    """
    Authenticate with API key and get JWT token.

    Args:
        request: Login request with API key

    Returns:
        JWT token response
    """
    # Validate API key
    user_info = await validate_api_key(request.api_key)

    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Check if user has admin access
    if not user_info.get("is_admin") and user_info.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required. Use the master API key or an admin key.",
        )

    # Create JWT token
    token, expires_at = create_access_token(user_info)

    return TokenResponse(
        access_token=token,
        expires_in=JWT_EXPIRATION_HOURS * 3600,
        expires_at=expires_at.isoformat(),
    )
