"""Compatibility import for the historical upgraded AWS credential path.

The maintained implementation lives in ``aws_credential_manager``. This module
contains no independent credential-management implementation.
"""

from .aws_credential_manager import (
    AWSCredentialError,
    AWSCredentialManager,
    AWSSecretError,
)

__all__ = ["AWSCredentialError", "AWSCredentialManager", "AWSSecretError"]
