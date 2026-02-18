"""Unit tests for the crypto utility (crypto.py).

Tests Fernet encryption/decryption of SSO client secrets, verifying:
- Encrypt/decrypt roundtrip with valid key
- ValueError when encryption key is missing
- Different ciphertext per call (random IV)
- Unicode and empty-string handling
- Invalid ciphertext error
- Key mismatch error
"""

import os
import sys
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet, InvalidToken

# ---------------------------------------------------------------------------
# Path setup — make admin-api importable
# ---------------------------------------------------------------------------

_service_dir = os.path.join(os.path.dirname(__file__), "../../src/admin-api")
sys.path.insert(0, _service_dir)

import crypto  # noqa: E402

# ---------------------------------------------------------------------------
# Test keys
# ---------------------------------------------------------------------------

_KEY_A = Fernet.generate_key().decode()
_KEY_B = Fernet.generate_key().decode()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCrypto:
    """Tests for crypto.encrypt_value / decrypt_value."""

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypt then decrypt with the same key — plaintext should match."""
        with patch.object(crypto, "_ENCRYPTION_KEY", _KEY_A):
            plaintext = "my-super-secret-client-secret"
            ciphertext = crypto.encrypt_value(plaintext)
            assert ciphertext != plaintext
            result = crypto.decrypt_value(ciphertext)
            assert result == plaintext

    def test_encrypt_raises_without_key(self):
        """encrypt_value raises ValueError when _ENCRYPTION_KEY is empty."""
        with patch.object(crypto, "_ENCRYPTION_KEY", ""):
            with pytest.raises(ValueError, match="SSO_ENCRYPTION_KEY not configured"):
                crypto.encrypt_value("something")

    def test_decrypt_raises_without_key(self):
        """decrypt_value raises ValueError when _ENCRYPTION_KEY is empty."""
        with patch.object(crypto, "_ENCRYPTION_KEY", ""):
            with pytest.raises(ValueError, match="SSO_ENCRYPTION_KEY not configured"):
                crypto.decrypt_value("something")

    def test_decrypt_wrong_key(self):
        """Encrypt with key A, decrypt with key B — should raise InvalidToken."""
        with patch.object(crypto, "_ENCRYPTION_KEY", _KEY_A):
            ciphertext = crypto.encrypt_value("secret-data")

        with patch.object(crypto, "_ENCRYPTION_KEY", _KEY_B):
            with pytest.raises(InvalidToken):
                crypto.decrypt_value(ciphertext)

    def test_encrypt_different_ciphertext_each_call(self):
        """Same plaintext encrypted twice produces different ciphertext (random IV)."""
        with patch.object(crypto, "_ENCRYPTION_KEY", _KEY_A):
            ct1 = crypto.encrypt_value("identical-input")
            ct2 = crypto.encrypt_value("identical-input")
            assert ct1 != ct2

    def test_empty_string_roundtrip(self):
        """Encrypt and decrypt an empty string."""
        with patch.object(crypto, "_ENCRYPTION_KEY", _KEY_A):
            ciphertext = crypto.encrypt_value("")
            assert crypto.decrypt_value(ciphertext) == ""

    def test_unicode_roundtrip(self):
        """Encrypt and decrypt unicode text (emoji, CJK, accented chars)."""
        with patch.object(crypto, "_ENCRYPTION_KEY", _KEY_A):
            plaintext = "Caf\u00e9 \u2615 \u4f60\u597d \U0001f680"
            ciphertext = crypto.encrypt_value(plaintext)
            assert crypto.decrypt_value(ciphertext) == plaintext

    def test_invalid_ciphertext_raises(self):
        """Decrypting invalid base64 garbage raises an error."""
        with patch.object(crypto, "_ENCRYPTION_KEY", _KEY_A):
            with pytest.raises(Exception):
                crypto.decrypt_value("not-valid-base64-at-all!!!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
