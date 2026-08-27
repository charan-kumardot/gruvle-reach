"""
Password hashing, JWT session tokens, and at-rest encryption for stored
integration credentials. Nothing in this module ever logs a secret value.
"""
import base64
import datetime as dt
import uuid
from typing import Any

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

JWT_ALGORITHM = "HS256"
_BCRYPT_MAX_BYTES = 72  # bcrypt's hard input limit


def hash_password(password: str) -> str:
    truncated = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    truncated = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(truncated, password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(*, user_id: uuid.UUID, extra_claims: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.access_token_expire_minutes),
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM])


class CredentialCipher:
    """Encrypts integration credentials (OAuth tokens, API keys) at rest.

    If no ENCRYPTION_KEY is configured (local dev only) we fall back to a
    clearly-marked no-op so the app still boots, but this must never happen
    in a deployed environment — settings.encryption_key should always be set.
    """

    def __init__(self) -> None:
        settings = get_settings()
        key = settings.encryption_key
        if key:
            self._fernet: Fernet | None = Fernet(key.encode() if isinstance(key, str) else key)
        else:
            self._fernet = None

    def encrypt(self, plaintext: str) -> str:
        if self._fernet is None:
            return "plaintext:" + base64.urlsafe_b64encode(plaintext.encode()).decode()
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if ciphertext.startswith("plaintext:"):
            return base64.urlsafe_b64decode(ciphertext.removeprefix("plaintext:").encode()).decode()
        if self._fernet is None:
            raise RuntimeError("ENCRYPTION_KEY not configured; cannot decrypt stored credential")
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Unable to decrypt credential — key rotated or data corrupted") from exc


_cipher: CredentialCipher | None = None


def get_cipher() -> CredentialCipher:
    global _cipher
    if _cipher is None:
        _cipher = CredentialCipher()
    return _cipher
