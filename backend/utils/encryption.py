import base64
import hashlib
from cryptography.fernet import Fernet
from config import Config

def _get_fernet(key: str | None = None) -> Fernet:
    raw_key = key or Config.GOOGLE_TOKEN_ENCRYPTION_KEY or Config.JWT_SECRET or "recruitmate-google-token-key-32b"
    derived_32 = hashlib.sha256(raw_key.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(derived_32)
    return Fernet(fernet_key)

def encrypt_token(token: str, key: str | None = None) -> str:
    """Encrypt a plaintext string token using authenticated AES Fernet."""
    if not token:
        return ""
    f = _get_fernet(key)
    return f.encrypt(token.encode("utf-8")).decode("utf-8")

def decrypt_token(encrypted_token: str, key: str | None = None) -> str:
    """Decrypt an encrypted token string back to plaintext."""
    if not encrypted_token:
        return ""
    f = _get_fernet(key)
    return f.decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
