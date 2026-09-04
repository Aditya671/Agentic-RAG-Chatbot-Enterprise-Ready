"""AWS credential and Secrets Manager access."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

DEFAULT_REGION = "us-east-1"
DEFAULT_CACHE_TTL_SECONDS = 0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_CONNECT_TIMEOUT_SECONDS = 5
DEFAULT_READ_TIMEOUT_SECONDS = 30


class AWSCredentialError(ValueError):
    """Raised when AWS credentials cannot be resolved."""


class AWSSecretError(ValueError):
    """Raised when a configured secret cannot be retrieved."""


@dataclass(frozen=True)
class _CachedSecret:
    value: str
    expires_at: float


class AWSCredentialManager:
    """Resolve AWS credentials and retrieve application secrets safely."""

    def __init__(self, secret_name: Optional[str] = None, region_name: str = DEFAULT_REGION, *, cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS, max_attempts: int = DEFAULT_MAX_ATTEMPTS, connect_timeout: int = DEFAULT_CONNECT_TIMEOUT_SECONDS, read_timeout: int = DEFAULT_READ_TIMEOUT_SECONDS) -> None:
        self.secret_name = self._validate_optional_name(secret_name)
        self.region_name = self._validate_region(region_name)
        self.cache_ttl_seconds = self._validate_non_negative_int(cache_ttl_seconds, "cache_ttl_seconds")
        self.max_attempts = self._validate_positive_int(max_attempts, "max_attempts")
        self.connect_timeout = self._validate_positive_int(connect_timeout, "connect_timeout")
        self.read_timeout = self._validate_positive_int(read_timeout, "read_timeout")
        self._secret_cache: dict[str, _CachedSecret] = {}
        self.client = self.get_client() if self.secret_name else None

    @staticmethod
    def _validate_optional_name(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError("secret_name must be a non-empty string when provided.")
        return value.strip()

    @staticmethod
    def _validate_region(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("region_name must be a non-empty string.")
        return value.strip()

    @staticmethod
    def _validate_positive_int(value: int, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer.")
        return value

    @staticmethod
    def _validate_non_negative_int(value: int, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer.")
        return value

    @staticmethod
    def get_session() -> boto3.session.Session:
        """Resolve an AWS session through Boto3's standard credential chain."""
        try:
            session = boto3.session.Session()
            credentials = session.get_credentials()
        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise AWSCredentialError("No valid AWS credentials found. Configure an AWS profile, environment credentials, or an AWS workload identity/role.") from exc
        if credentials is None:
            raise AWSCredentialError("No valid AWS credentials found. Configure an AWS profile, environment credentials, or an AWS workload identity/role.")
        return session

    def get_client(self):
        """Create a configured Secrets Manager client."""
        session = self.get_session()
        config = Config(retries={"mode": "standard", "max_attempts": self.max_attempts}, connect_timeout=self.connect_timeout, read_timeout=self.read_timeout)
        return session.client(service_name="secretsmanager", region_name=self.region_name, config=config)

    def _get_cached_secret(self, secret_name: str) -> Optional[str]:
        if self.cache_ttl_seconds <= 0:
            return None
        cached = self._secret_cache.get(secret_name)
        if cached is None:
            return None
        if cached.expires_at <= time.monotonic():
            self._secret_cache.pop(secret_name, None)
            return None
        return cached.value

    def _cache_secret(self, secret_name: str, value: str) -> None:
        if self.cache_ttl_seconds <= 0:
            return
        self._secret_cache[secret_name] = _CachedSecret(value=value, expires_at=time.monotonic() + self.cache_ttl_seconds)

    def clear_cache(self, secret_name: Optional[str] = None) -> None:
        """Clear one cached secret or the complete in-process secret cache."""
        if secret_name is None:
            self._secret_cache.clear()
        else:
            self._secret_cache.pop(secret_name, None)

    @staticmethod
    def _decode_secret_response(response: dict) -> str:
        if "SecretString" in response:
            value = response["SecretString"]
            if not isinstance(value, str):
                raise AWSSecretError("AWS returned an invalid SecretString value.")
            return value
        if "SecretBinary" in response:
            binary_value = response["SecretBinary"]
            if isinstance(binary_value, str):
                return binary_value
            if isinstance(binary_value, (bytes, bytearray)):
                try:
                    return bytes(binary_value).decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise AWSSecretError("AWS SecretBinary is not valid UTF-8 text.") from exc
            raise AWSSecretError("AWS returned an invalid SecretBinary value.")
        raise AWSSecretError("AWS Secrets Manager returned neither SecretString nor SecretBinary.")

    def _get_secret_from_aws(self, secret_name: str) -> str:
        if self.client is None:
            raise AWSSecretError("AWS Secrets Manager is not configured.")
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = error.get("Code", "Unknown")
            if code == "ResourceNotFoundException":
                raise AWSSecretError(f"Secret '{secret_name}' not found in AWS Secrets Manager.") from exc
            if code in {"AccessDeniedException", "AccessDenied"}:
                raise AWSSecretError("Access denied while retrieving the configured AWS secret.") from exc
            raise AWSSecretError(f"AWS Secrets Manager failed to retrieve secret '{secret_name}' ({code}).") from exc
        value = self._decode_secret_response(response)
        self._cache_secret(secret_name, value)
        return value

    def get_secret(self, secret_name: Optional[str] = None) -> str:
        """Retrieve a secret from the environment or Secrets Manager."""
        resolved_name = self._validate_optional_name(self.secret_name if secret_name is None else secret_name)
        if not resolved_name:
            raise ValueError("No secret name provided.")
        environment_secret = os.environ.get(resolved_name)
        if environment_secret:
            return environment_secret
        cached_secret = self._get_cached_secret(resolved_name)
        if cached_secret is not None:
            return cached_secret
        if self.client is None:
            raise AWSSecretError(f"Secret '{resolved_name}' not found in environment variables or AWS Secrets Manager.")
        return self._get_secret_from_aws(resolved_name)
