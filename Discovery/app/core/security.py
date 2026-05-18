import base64
import os
import sys
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

if getattr(sys, "frozen", False):
    _BASE = Path(sys.executable).parent
else:
    _BASE = Path(__file__).resolve().parent.parent.parent

KEY_FILE = _BASE / "config" / ".key"

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet

    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)

    if KEY_FILE.exists():
        key = KEY_FILE.read_bytes()
    else:
        # Derive key from machine-specific entropy + random salt
        salt = os.urandom(16)
        machine_id = _machine_id().encode()
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
        raw = kdf.derive(machine_id)
        key = base64.urlsafe_b64encode(raw)
        KEY_FILE.write_bytes(salt + key)
        KEY_FILE.chmod(0o600)

    if len(key) > 44:
        # File contains salt prefix
        key = key[16:]

    _fernet = Fernet(key)
    return _fernet


def _machine_id() -> str:
    try:
        import subprocess
        result = subprocess.run(
            ["wmic", "csproduct", "get", "UUID"],
            capture_output=True, text=True, timeout=5
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip() and l.strip() != "UUID"]
        if lines:
            return lines[0]
    except Exception:
        pass
    return "NetDiscoveryManager-DefaultKey-2024"


def encrypt(plaintext: str) -> str:
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


def encrypt_credentials(username: str, password: str) -> tuple[str, str]:
    return encrypt(username), encrypt(password)


def decrypt_credentials(enc_user: str, enc_pass: str) -> tuple[str, str]:
    return decrypt(enc_user), decrypt(enc_pass)
