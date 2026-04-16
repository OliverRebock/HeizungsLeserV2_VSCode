"""
Token Encryption Module

Provides transparent encryption/decryption for sensitive secrets like InfluxDB tokens.
Uses Fernet (symmetric encryption) with a key derived from environment configuration.
"""

import base64
import logging
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenEncryptionError(Exception):
    """Raised when token encryption/decryption fails."""
    pass


class TokenEncryptor:
    """
    Encrypts and decrypts sensitive tokens using Fernet symmetric encryption.
    
    The encryption key is derived from the application's secret key. This provides:
    - Encryption at rest: tokens stored in database are not plaintext
    - Deterministic: same token always encrypts to same ciphertext
    - Integrity: Fernet includes HMAC verification
    """
    
    _cipher = None
    
    @classmethod
    def _get_cipher(cls) -> Fernet:
        """
        Gets or creates the Fernet cipher instance.
        
        The key is derived from settings.SECRET_KEY by:
        1. Encoding to UTF-8
        2. Base64-encoding to get Fernet-compatible key format
        
        Returns:
            Fernet cipher instance
            
        Raises:
            TokenEncryptionError: If key derivation fails
        """
        if cls._cipher is not None:
            return cls._cipher
        
        try:
            # Derive a Fernet key from the SECRET_KEY
            # Fernet keys must be 32 bytes when base64-decoded
            # We take the first 32 bytes of SHA256(SECRET_KEY) to ensure consistent length
            
            from hashlib import sha256
            
            secret_bytes = settings.SECRET_KEY.encode('utf-8')
            key_hash = sha256(secret_bytes).digest()
            
            # Base64 encode the 32-byte hash to get Fernet-compatible key
            fernet_key = base64.urlsafe_b64encode(key_hash)
            
            cls._cipher = Fernet(fernet_key)
            return cls._cipher
            
        except Exception as exc:
            raise TokenEncryptionError(f"Failed to initialize encryption cipher: {exc}")
    
    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        """
        Encrypts a plaintext token.
        
        Args:
            plaintext: The token/secret to encrypt
            
        Returns:
            Base64-encoded encrypted token (can be stored in database)
            
        Raises:
            TokenEncryptionError: If encryption fails
        """
        if not plaintext:
            return None
        
        try:
            cipher = cls._get_cipher()
            plaintext_bytes = plaintext.encode('utf-8')
            ciphertext_bytes = cipher.encrypt(plaintext_bytes)
            
            # Return as base64 string for database storage
            ciphertext_b64 = base64.b64encode(ciphertext_bytes).decode('utf-8')
            logger.debug(f"Encrypted token: {len(plaintext)} chars -> {len(ciphertext_b64)} chars")
            
            return ciphertext_b64
            
        except Exception as exc:
            raise TokenEncryptionError(f"Encryption failed: {exc}")
    
    @classmethod
    def decrypt(cls, ciphertext: str) -> Optional[str]:
        """
        Decrypts an encrypted token.
        
        Args:
            ciphertext: The base64-encoded encrypted token from database
            
        Returns:
            Decrypted plaintext token
            
        Raises:
            TokenEncryptionError: If decryption fails
        """
        if not ciphertext:
            return None
        
        try:
            cipher = cls._get_cipher()
            
            # Decode from base64
            if isinstance(ciphertext, str):
                ciphertext_bytes = base64.b64decode(ciphertext.encode('utf-8'))
            else:
                ciphertext_bytes = base64.b64decode(ciphertext)
            
            # Decrypt
            plaintext_bytes = cipher.decrypt(ciphertext_bytes)
            plaintext = plaintext_bytes.decode('utf-8')
            
            logger.debug(f"Decrypted token: {len(ciphertext)} chars -> {len(plaintext)} chars")
            return plaintext
            
        except InvalidToken as exc:
            raise TokenEncryptionError(f"Decryption failed: token tampered or wrong key: {exc}")
        except Exception as exc:
            raise TokenEncryptionError(f"Decryption failed: {exc}")
    
    @classmethod
    def test_encryption_roundtrip(cls) -> bool:
        """
        Tests encryption/decryption roundtrip to verify cipher is working.
        
        Returns:
            True if roundtrip successful
            
        Raises:
            TokenEncryptionError: If roundtrip fails
        """
        test_token = "test_token_12345"
        try:
            encrypted = cls.encrypt(test_token)
            decrypted = cls.decrypt(encrypted)
            
            if decrypted != test_token:
                raise TokenEncryptionError(
                    f"Roundtrip failed: {test_token} != {decrypted}"
                )
            
            logger.info("Token encryption roundtrip test passed")
            return True
            
        except Exception as exc:
            raise TokenEncryptionError(f"Roundtrip test failed: {exc}")


# Global convenience functions
def encrypt_token(token: str) -> str:
    """Encrypts a token. Convenience wrapper."""
    return TokenEncryptor.encrypt(token)


def decrypt_token(encrypted_token: str) -> Optional[str]:
    """Decrypts a token. Convenience wrapper."""
    return TokenEncryptor.decrypt(encrypted_token)
