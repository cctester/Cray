"""
Secrets management for Cray workflows.

Provides secure storage and retrieval of sensitive data like:
- API keys
- Database passwords
- OAuth tokens
- SSH keys

Storage backends:
- Environment variables (default)
- Encrypted file storage
- HashiCorp Vault (optional)
"""

from __future__ import annotations
import os
import json
import hashlib
import base64
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from loguru import logger

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography package not installed, encrypted storage disabled")


class SecretBackend(str, Enum):
    """Available secret backends."""
    ENV = "env"
    FILE = "file"
    VAULT = "vault"


@dataclass
class SecretMetadata:
    """Metadata about a stored secret."""
    name: str
    created_at: str
    updated_at: str
    backend: SecretBackend
    tags: List[str]


class SecretsManager:
    """
    Manages secrets for workflow execution.
    
    Usage:
        secrets = SecretsManager()
        
        # Store a secret
        secrets.set("api_key", "sk-123456")
        
        # Retrieve a secret
        key = secrets.get("api_key")
        
        # Use in workflow
        # {{ secrets.api_key }}
    """
    
    def __init__(
        self,
        backend: SecretBackend = SecretBackend.ENV,
        storage_path: Optional[str] = None,
        encryption_key: Optional[str] = None
    ):
        """
        Initialize secrets manager.
        
        Args:
            backend: Storage backend to use
            storage_path: Path for file-based storage
            encryption_key: Key for encrypting file storage
        """
        self.backend = backend
        self.storage_path = Path(storage_path or os.path.expanduser("~/.cray/secrets"))
        self._cache: Dict[str, str] = {}
        self._metadata: Dict[str, SecretMetadata] = {}
        self._fernet: Optional[Any] = None
        
        if backend == SecretBackend.FILE:
            self._init_file_storage(encryption_key)
    
    def _init_file_storage(self, encryption_key: Optional[str]) -> None:
        """Initialize encrypted file storage."""
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("cryptography package required for file storage")
        
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.storage_path.chmod(0o700)
        
        if encryption_key:
            self._init_encryption(encryption_key)
        
        self._load_metadata()
    
    def _init_encryption(self, password: str) -> None:
        """Initialize encryption from password."""
        salt_file = self.storage_path / ".salt"
        
        if salt_file.exists():
            salt = salt_file.read_bytes()
        else:
            salt = os.urandom(16)
            salt_file.write_bytes(salt)
            salt_file.chmod(0o600)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        self._fernet = Fernet(key)
    
    def _load_metadata(self) -> None:
        """Load secret metadata."""
        meta_file = self.storage_path / "metadata.json"
        if meta_file.exists():
            try:
                data = json.loads(meta_file.read_text())
                for name, meta in data.items():
                    self._metadata[name] = SecretMetadata(
                        name=name,
                        created_at=meta["created_at"],
                        updated_at=meta["updated_at"],
                        backend=SecretBackend(meta["backend"]),
                        tags=meta.get("tags", [])
                    )
            except Exception as e:
                logger.warning(f"Failed to load secrets metadata: {e}")
    
    def _save_metadata(self) -> None:
        """Save secret metadata."""
        meta_file = self.storage_path / "metadata.json"
        data = {
            name: {
                "created_at": meta.created_at,
                "updated_at": meta.updated_at,
                "backend": meta.backend.value,
                "tags": meta.tags
            }
            for name, meta in self._metadata.items()
        }
        meta_file.write_text(json.dumps(data, indent=2))
        meta_file.chmod(0o600)
    
    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret value.
        
        Args:
            name: Secret name
            default: Default value if not found
            
        Returns:
            Secret value or default
        """
        # Check cache first
        if name in self._cache:
            return self._cache[name]
        
        # Try environment variable
        env_name = self._get_env_name(name)
        value = os.environ.get(env_name)
        
        if value:
            self._cache[name] = value
            return value
        
        # Try file storage
        if self.backend == SecretBackend.FILE:
            value = self._get_from_file(name)
            if value:
                self._cache[name] = value
                return value
        
        return default
    
    def _get_env_name(self, name: str) -> str:
        """Convert secret name to environment variable name."""
        return f"CRAY_SECRET_{name.upper().replace('-', '_').replace('.', '_')}"
    
    def _get_from_file(self, name: str) -> Optional[str]:
        """Get secret from encrypted file storage."""
        secret_file = self.storage_path / f"{name}.enc"
        if not secret_file.exists():
            return None
        
        try:
            data = secret_file.read_bytes()
            if self._fernet:
                data = self._fernet.decrypt(data)
            return data.decode()
        except Exception as e:
            logger.error(f"Failed to read secret {name}: {e}")
            return None
    
    def set(
        self,
        name: str,
        value: str,
tags: Optional[List[str]] = None
    ) -> None:
        """
        Store a secret.
        
        Args:
            name: Secret name
            value: Secret value
            tags: Optional tags for organization
        """
        from datetime import datetime
        
        if self.backend == SecretBackend.ENV:
            # Set environment variable
            env_name = self._get_env_name(name)
            os.environ[env_name] = value
            self._cache[name] = value
            
        elif self.backend == SecretBackend.FILE:
            self._set_in_file(name, value)
        
        # Update metadata
        now = datetime.now().isoformat()
        if name in self._metadata:
            self._metadata[name].updated_at = now
            if tags:
                self._metadata[name].tags = tags
        else:
            self._metadata[name] = SecretMetadata(
                name=name,
                created_at=now,
                updated_at=now,
                backend=self.backend,
                tags=tags or []
            )
        
        self._save_metadata()
        logger.info(f"Secret '{name}' stored successfully")
    
    def _set_in_file(self, name: str, value: str) -> None:
        """Store secret in encrypted file."""
        secret_file = self.storage_path / f"{name}.enc"
        
        data = value.encode()
        if self._fernet:
            data = self._fernet.encrypt(data)
        
        secret_file.write_bytes(data)
        secret_file.chmod(0o600)
        self._cache[name] = value
    
    def delete(self, name: str) -> bool:
        """
        Delete a secret.
        
        Args:
            name: Secret name
            
        Returns:
            True if deleted, False if not found
        """
        # Remove from cache
        self._cache.pop(name, None)
        
        # Remove from environment
        env_name = self._get_env_name(name)
        os.environ.pop(env_name, None)
        
        # Remove from file storage
        if self.backend == SecretBackend.FILE:
            secret_file = self.storage_path / f"{name}.enc"
            if secret_file.exists():
                secret_file.unlink()
        
        # Remove metadata
        if name in self._metadata:
            del self._metadata[name]
            self._save_metadata()
            return True
        
        return False
    
    def list(self) -> List[SecretMetadata]:
        """
        List all stored secrets.
        
        Returns:
            List of secret metadata
        """
        return list(self._metadata.values())
    
    def exists(self, name: str) -> bool:
        """Check if a secret exists."""
        return self.get(name) is not None
    
    def get_all_for_context(self) -> Dict[str, str]:
        """
        Get all secrets for template context.
        
        Returns:
            Dictionary of secret name -> value (for template access)
        """
        result = {}
        for meta in self._metadata.values():
            value = self.get(meta.name)
            if value is not None:
                result[meta.name] = value
        return result
    
    def export_env(self) -> Dict[str, str]:
        """
        Export all secrets as environment variables.
        
        Returns:
            Dictionary of env var name -> value
        """
        result = {}
        for meta in self._metadata.values():
            value = self.get(meta.name)
            if value is not None:
                env_name = self._get_env_name(meta.name)
                result[env_name] = value
        return result
    
    def rotate(self, name: str, new_value: str) -> None:
        """
        Rotate a secret (update with new value).
        
        Args:
            name: Secret name
            new_value: New secret value
        """
        self.set(name, new_value, tags=self._metadata.get(name, SecretMetadata(
            name=name, created_at="", updated_at="", backend=self.backend, tags=[]
        )).tags)
        logger.info(f"Secret '{name}' rotated successfully")


# Global secrets manager instance
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager() -> SecretsManager:
    """Get the global secrets manager instance."""
    global _secrets_manager
    if _secrets_manager is None:
        backend = SecretBackend(os.environ.get("CRAY_SECRETS_BACKEND", "env"))
        storage_path = os.environ.get("CRAY_SECRETS_PATH")
        encryption_key = os.environ.get("CRAY_SECRETS_KEY")
        
        _secrets_manager = SecretsManager(
            backend=backend,
            storage_path=storage_path,
            encryption_key=encryption_key
        )
    return _secrets_manager


def get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """Convenience function to get a secret."""
    return get_secrets_manager().get(name, default)


def set_secret(name: str, value: str, tags: Optional[List[str]] = None) -> None:
    pass
    """Convenience function to set a secret."""
    get_secrets_manager().set(name, value, tags)
