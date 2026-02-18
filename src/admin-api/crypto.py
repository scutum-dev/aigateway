"""Fernet encryption for SSO client secrets."""

import logging
import os

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_ENCRYPTION_KEY = os.getenv("SSO_ENCRYPTION_KEY", "")


def _get_fernet():
    if not _ENCRYPTION_KEY:
        raise ValueError("SSO_ENCRYPTION_KEY not configured")
    return Fernet(_ENCRYPTION_KEY.encode() if isinstance(_ENCRYPTION_KEY, str) else _ENCRYPTION_KEY)


def encrypt_value(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()
