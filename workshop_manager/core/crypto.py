"""Encryption of secrets stored in the database (the SMTP password, PRD §7.5, §8).

The key is `FIELD_ENCRYPTION_KEY` (a Fernet key) when set, otherwise one derived from
`SECRET_KEY`. Rotating whichever key is in use makes stored secrets unreadable: `decrypt()`
then returns an empty string and the administrator re-enters the password in Settings.
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)


def _fernet() -> Fernet:
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        digest = hashlib.sha256(f"field-encryption:{settings.SECRET_KEY}".encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key)


def encrypt(value: str) -> str:
    if not value:
        return ""
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        logger.warning("A stored secret cannot be decrypted; was the encryption key changed?")
        return ""
