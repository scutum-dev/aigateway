"""Unit tests for the Admin API auth module.

Tests JWT creation, decoding, validation, and API key validation
against LiteLLM.
"""

import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Load the admin-api auth module under a unique name to avoid sys.modules collision
_service_dir = os.path.join(os.path.dirname(__file__), "../../src/admin-api")
_service_path = os.path.join(_service_dir, "auth.py")
sys.path.insert(0, _service_dir)  # needed so local imports inside auth.py work
_spec = importlib.util.spec_from_file_location("admin_api_auth", _service_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["admin_api_auth"] = _mod
_spec.loader.exec_module(_mod)

create_access_token = _mod.create_access_token
decode_token = _mod.decode_token
validate_api_key = _mod.validate_api_key
JWT_SECRET_KEY = _mod.JWT_SECRET_KEY
JWT_ALGORITHM = _mod.JWT_ALGORITHM
JWT_EXPIRATION_HOURS = _mod.JWT_EXPIRATION_HOURS
LITELLM_MASTER_KEY = _mod.LITELLM_MASTER_KEY


# ============================================================================
# create_access_token
# ============================================================================


class TestCreateAccessToken:
    def test_returns_string_and_datetime(self):
        """Should return a (str, datetime) tuple."""
        token, expires_at = create_access_token({"user_id": "alice"})
        assert isinstance(token, str)
        assert isinstance(expires_at, datetime)

    def test_token_contains_sub_claim(self):
        """Token payload should contain the sub claim matching user_id."""
        import jwt

        token, _ = create_access_token({"user_id": "bob"})
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        assert payload["sub"] == "bob"

    def test_token_contains_exp_claim(self):
        """Token payload should contain an exp claim in the future."""
        import jwt

        token, _ = create_access_token({"user_id": "carol"})
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        assert "exp" in payload
        assert payload["exp"] > datetime.now(timezone.utc).timestamp()

    def test_custom_user_info_fields(self):
        """Token should encode role, team_id, and is_admin from user_info."""
        import jwt

        user_info = {
            "user_id": "dave",
            "role": "admin",
            "team_id": "team-42",
            "is_admin": True,
        }
        token, _ = create_access_token(user_info)
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        assert payload["role"] == "admin"
        assert payload["team_id"] == "team-42"
        assert payload["is_admin"] is True

    def test_default_role_is_user(self):
        """When role is not provided, it should default to 'user'."""
        import jwt

        token, _ = create_access_token({"user_id": "eve"})
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        assert payload["role"] == "user"


# ============================================================================
# decode_token
# ============================================================================


class TestDecodeToken:
    def test_valid_roundtrip(self):
        """A freshly created token should decode successfully."""
        token, _ = create_access_token({"user_id": "frank", "role": "viewer"})
        payload = decode_token(token)
        assert payload["sub"] == "frank"
        assert payload["role"] == "viewer"

    def test_expired_token_raises_401(self):
        """An expired token should raise HTTPException with status 401."""
        import jwt as pyjwt
        from fastapi import HTTPException

        expired_payload = {
            "sub": "grace",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=9),
        }
        token = pyjwt.encode(expired_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)
        assert exc_info.value.status_code == 401

    def test_tampered_token_raises_401(self):
        """A tampered token should raise HTTPException with status 401."""
        from fastapi import HTTPException

        token, _ = create_access_token({"user_id": "heidi"})
        # Flip a character in the signature portion
        tampered = token[:-4] + "XXXX"

        with pytest.raises(HTTPException) as exc_info:
            decode_token(tampered)
        assert exc_info.value.status_code == 401

    def test_garbage_token_raises_401(self):
        """Completely invalid input should raise HTTPException with status 401."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_token("this.is.not.a.jwt")
        assert exc_info.value.status_code == 401

    def test_wrong_secret_raises_401(self):
        """A token signed with a different secret should raise HTTPException."""
        import jwt as pyjwt
        from fastapi import HTTPException

        payload = {
            "sub": "ivan",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = pyjwt.encode(payload, "wrong-secret-key", algorithm=JWT_ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)
        assert exc_info.value.status_code == 401


# ============================================================================
# validate_api_key
# ============================================================================


class TestValidateApiKey:
    @pytest.mark.asyncio
    async def test_master_key_returns_admin(self):
        """Master key should return admin dict without calling LiteLLM."""
        result = await validate_api_key(LITELLM_MASTER_KEY)
        assert result is not None
        assert result["user_id"] == "admin"
        assert result["is_admin"] is True
        assert result["role"] == "admin"

    @pytest.mark.asyncio
    async def test_non_master_key_calls_litellm(self):
        """Non-master key should call LiteLLM /key/info endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user_id": "test-user",
            "team_id": "team-1",
            "metadata": {"role": "developer", "is_admin": False},
            "key_name": "dev-key",
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await validate_api_key("sk-some-other-key")

        assert result is not None
        assert result["user_id"] == "test-user"
        assert result["team_id"] == "team-1"
        assert result["role"] == "developer"

    @pytest.mark.asyncio
    async def test_invalid_key_returns_none(self):
        """An invalid key (LiteLLM returns 404) should return None."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await validate_api_key("sk-invalid-key")

        assert result is None

    @pytest.mark.asyncio
    async def test_network_error_returns_none(self):
        """Network failure when calling LiteLLM should return None."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await validate_api_key("sk-some-key")

        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
