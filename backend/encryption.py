import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def get_fernet_key():
    key_material = os.environ.get('ENCRYPTION_KEY', 'default-key-change-me')
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'securecomm-salt-v1',
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(key_material.encode()))
    return Fernet(key)

_fernet = None

def get_cipher():
    global _fernet
    if _fernet is None:
        _fernet = get_fernet_key()
    return _fernet

def encrypt_text(plaintext: str) -> str:
    if not plaintext:
        return plaintext
    cipher = get_cipher()
    return cipher.encrypt(plaintext.encode('utf-8')).decode('utf-8')

def decrypt_text(ciphertext: str) -> str:
    if not ciphertext:
        return ciphertext
    try:
        cipher = get_cipher()
        return cipher.decrypt(ciphertext.encode('utf-8')).decode('utf-8')
    except Exception:
        return ciphertext

def encrypt_bytes(data: bytes) -> bytes:
    cipher = get_cipher()
    return cipher.encrypt(data)

def decrypt_bytes(data: bytes) -> bytes:
    cipher = get_cipher()
    return cipher.decrypt(data)
