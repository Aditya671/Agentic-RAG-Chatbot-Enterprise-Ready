"""Compatibility export for the canonical Azure credential manager."""

from .credentials.azure_credential_manager import AzureCredentialManager, SecretNotFoundError

__all__ = ["AzureCredentialManager", "SecretNotFoundError"]
