"""
JWT authentication for Admin API.

Validates API keys against LiteLLM and issues JWT tokens
for subsequent admin requests.
"""

import hmac
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "")


class LoginRequest(BaseModel):
    """Login request with API key."""

    api_key: str


class BootstrapRequest(BaseModel):
    """One-shot magic-link login for hosted trial machines.

    The trial-provisioner generates a random BOOTSTRAP_TOKEN per trial and
    injects it as an env var on the Fly machine (alongside SCUTUM_API_KEY).
    The /try page redirects the user to /admin/?bootstrap=<token>; admin-ui
    POSTs that token here, exchanges it for a JWT, then drops into the
    dashboard. The token is one-shot — see validate_bootstrap_token.
    """

    token: str


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
    email: Optional[str] = None
    org_id: Optional[str] = None
    is_platform_admin: bool = False
    org_roles: dict = {}


async def validate_api_key(api_key: str) -> Optional[dict]:
    """
    Validate API key against LiteLLM.

    Args:
        api_key: API key to validate

    Returns:
        Key info dict if valid, None otherwise
    """
    # Check if it's the master key
    if hmac.compare_digest(api_key, LITELLM_MASTER_KEY):
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
                headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
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


# Marker file path for one-shot bootstrap-token consumption. Lives on the
# /etc/scutum volume so it persists across machine restarts (the token can
# only ever be consumed once, even if the user clicks the magic link, the
# admin-api restarts, and they click again).
BOOTSTRAP_CONSUMED_PATH = os.getenv("BOOTSTRAP_CONSUMED_PATH", "/etc/scutum/bootstrap-consumed")


def validate_bootstrap_token(token: str) -> Optional[dict]:
    """Validate a one-shot bootstrap token from the trial magic-link URL.

    Returns the same admin-user dict shape as validate_api_key's master-key
    path on success. Returns None if:
      - the token has already been consumed (marker file exists),
      - BOOTSTRAP_TOKEN env is unset on this admin-api,
      - the supplied token doesn't match.

    On success, atomically creates the marker file. Subsequent attempts
    (refresh, second tab, leaked URL) get None and the user has to log in
    with their persistent SCUTUM_API_KEY.
    """
    expected = os.getenv("BOOTSTRAP_TOKEN", "")
    if not expected:
        return None
    if not token:
        return None
    if os.path.exists(BOOTSTRAP_CONSUMED_PATH):
        logger.info("bootstrap token rejected: already consumed")
        return None
    if not hmac.compare_digest(token, expected):
        logger.info("bootstrap token rejected: mismatch")
        return None

    # Mark consumed atomically. O_EXCL fails if the file appeared between
    # the existence check above and the create call (race), in which case
    # another request beat us to it — treat as already-consumed.
    #
    # The marker dir (/etc/scutum) is NOT guaranteed to exist inside the
    # admin-api container — install.sh runs on the HOST monolith filesystem,
    # not inside dind. Create it lazily on first successful exchange.
    try:
        os.makedirs(os.path.dirname(BOOTSTRAP_CONSUMED_PATH), exist_ok=True)
    except OSError as e:
        logger.error("could not create bootstrap marker dir: %s", e)
        return None
    try:
        fd = os.open(BOOTSTRAP_CONSUMED_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        logger.info("bootstrap token rejected: race-lost to concurrent exchange")
        return None
    except OSError as e:
        logger.error("could not mark bootstrap token consumed: %s", e)
        return None
    try:
        os.write(fd, datetime.now(timezone.utc).isoformat().encode())
    finally:
        os.close(fd)

    logger.info("bootstrap token accepted, marker written; admin JWT will be issued")
    return {
        "user_id": "admin",
        "role": "admin",
        "is_admin": True,
        "key": "bootstrap",
    }


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
        "email": user_info.get("email"),
        "org_id": user_info.get("org_id"),
        "is_platform_admin": user_info.get("is_platform_admin", False),
        "org_roles": user_info.get("org_roles", {}),
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


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserInfo:
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
        email=payload.get("email"),
        org_id=payload.get("org_id"),
        is_platform_admin=payload.get("is_platform_admin", False),
        org_roles=payload.get("org_roles", {}),
    )


async def require_admin(user: UserInfo = Depends(get_current_user)) -> UserInfo:
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


async def require_platform_admin(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """
    Require platform admin role for endpoint.

    Args:
        user: Current user

    Returns:
        UserInfo if platform admin

    Raises:
        HTTPException: If not platform admin
    """
    if not user.is_platform_admin and not user.is_admin and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
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


async def bootstrap_login(request: BootstrapRequest) -> TokenResponse:
    """Exchange a one-shot bootstrap token for an admin JWT.

    Used only by hosted-trial machines: trial-provisioner injects a random
    BOOTSTRAP_TOKEN env var on machine create, embeds the token in the URL
    the user is redirected to after email verification, and the admin-ui
    auto-calls this endpoint on page load. See validate_bootstrap_token for
    the one-shot semantics.
    """
    user_info = validate_bootstrap_token(request.token)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or already-used bootstrap token",
        )
    token, expires_at = create_access_token(user_info)
    return TokenResponse(
        access_token=token,
        expires_in=JWT_EXPIRATION_HOURS * 3600,
        expires_at=expires_at.isoformat(),
    )
