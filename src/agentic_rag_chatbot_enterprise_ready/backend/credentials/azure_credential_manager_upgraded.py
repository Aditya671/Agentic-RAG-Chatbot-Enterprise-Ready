from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.identity import AzureCliCredential, DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger(__name__)


class SecretNotFoundError(ValueError):
    """Raised when a required secret is unavailable from all configured sources."""


@dataclass(frozen=True)
class _CachedSecret:
    value: str
    expires_at: float


class AzureCredentialManager:
    """Centralized Azure authentication and Key Vault secret access.

    Environment variables remain the first source for backward compatibility.
    Cloud environments use DefaultAzureCredential. Local environments retain
    AzureCliCredential by default, with an opt-in DefaultAzureCredential path
    for teams using multiple Azure developer tools.
    """

    LOCAL_ENVIRONMENTS = frozenset({"local", "local_emulator", "development", "dev"})

    def __init__(
        self,
        key_vault_url: Optional[str] = None,
        *,
        environment: Optional[str] = None,
        credential=None,
        use_cli_for_local: bool = True,
        additionally_allowed_tenants: Optional[list[str]] = None,
        cache_ttl_seconds: int = 300,
        allow_environment_override: bool = True,
        secret_client: Optional[SecretClient] = None,
    ) -> None:
        if cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds must be >= 0.")

        self.key_vault_url = self._normalize_vault_url(key_vault_url)
        self.environment = (
            environment or os.getenv("ENVIRONMENT") or "local"
        ).strip().lower()
        self.use_cli_for_local = use_cli_for_local
        self.additionally_allowed_tenants = (
            list(additionally_allowed_tenants)
            if additionally_allowed_tenants is not None
            else ["*"]
        )
        self.cache_ttl_seconds = cache_ttl_seconds
        self.allow_environment_override = allow_environment_override

        self.credential = credential or self.get_credential(
            environment=self.environment,
            use_cli_for_local=use_cli_for_local,
            additionally_allowed_tenants=self.additionally_allowed_tenants,
        )

        if secret_client is not None:
            self.client = secret_client
        elif self.key_vault_url:
            self.client = SecretClient(
                vault_url=self.key_vault_url,
                credential=self.credential,
            )
        else:
            self.client = None

        self._cache: Dict[str, _CachedSecret] = {}
        self._cache_lock = threading.RLock()

    @staticmethod
    def _normalize_vault_url(key_vault_url: Optional[str]) -> Optional[str]:
        if key_vault_url is None:
            return None

        value = key_vault_url.strip()
        if not value:
            return None

        if not (
            value.startswith("https://")
            and value.endswith(".vault.azure.net")
        ):
            raise ValueError(
                "key_vault_url must be an Azure Key Vault HTTPS URL "
                "ending in '.vault.azure.net'."
            )

        return value.rstrip("/")

    @classmethod
    def get_credential(
        cls,
        *,
        environment: Optional[str] = None,
        use_cli_for_local: bool = True,
        additionally_allowed_tenants: Optional[list[str]] = None,
    ):
        """Create the Azure Identity credential appropriate for the environment."""
        env = (environment or os.getenv("ENVIRONMENT") or "local").strip().lower()
        allowed = additionally_allowed_tenants or ["*"]

        if env in cls.LOCAL_ENVIRONMENTS and use_cli_for_local:
            return AzureCliCredential(
                additionally_allowed_tenants=allowed,
            )

        return DefaultAzureCredential()

    def get_secret(
        self,
        secret_name: str,
        *,
        required: bool = True,
        cache: bool = True,
    ) -> Optional[str]:
        """Resolve a secret from environment first, then Key Vault."""
        if not isinstance(secret_name, str):
            raise TypeError("secret_name must be a string.")

        name = secret_name.strip()
        if not name:
            raise ValueError("secret_name must not be empty.")

        # Environment variables intentionally allow underscores. Key Vault
        # naming rules are enforced only if the value must be sent to Key Vault.
        if self.allow_environment_override:
            environment_value = os.getenv(name)
            if environment_value:
                return environment_value

        if self.client is None:
            if required:
                raise SecretNotFoundError(
                    f"Secret '{name}' is not configured in the environment "
                    "and no Key Vault client is configured."
                )
            return None

        name = self._validate_secret_name(name)

        if cache and self.cache_ttl_seconds > 0:
            cached = self._get_cached(name)
            if cached is not None:
                return cached

        try:
            secret = self.client.get_secret(name)
        except ResourceNotFoundError as exc:
            if required:
                raise SecretNotFoundError(
                    f"Required secret '{name}' was not found in Azure Key Vault."
                ) from exc
            return None
        except AzureError as exc:
            logger.error(
                "Azure Key Vault request failed for secret '%s'.",
                name,
                exc_info=True,
            )
            raise RuntimeError(
                f"Failed to retrieve secret '{name}' from Azure Key Vault."
            ) from exc

        value = getattr(secret, "value", None)
        if not value:
            if required:
                raise SecretNotFoundError(
                    f"Secret '{name}' exists but contains no value."
                )
            return None

        if cache and self.cache_ttl_seconds > 0:
            self._set_cached(name, value)

        return value

    def clear_secret_cache(self, secret_name: Optional[str] = None) -> None:
        with self._cache_lock:
            if secret_name is None:
                self._cache.clear()
            else:
                self._cache.pop(self._validate_secret_name(secret_name), None)

    def close(self) -> None:
        client_close = getattr(self.client, "close", None)
        if callable(client_close):
            client_close()

        credential_close = getattr(self.credential, "close", None)
        if callable(credential_close):
            credential_close()

        self.clear_secret_cache()

    @staticmethod
    def _validate_secret_name(secret_name: str) -> str:
        if not isinstance(secret_name, str):
            raise TypeError("secret_name must be a string.")

        name = secret_name.strip()
        if not name:
            raise ValueError("secret_name must not be empty.")

        if not all(ch.isalnum() or ch == "-" for ch in name):
            raise ValueError(
                f"Invalid Key Vault secret name '{name}'. "
                "Use only alphanumeric characters and hyphens."
            )

        return name

    def _get_cached(self, secret_name: str) -> Optional[str]:
        now = time.monotonic()
        with self._cache_lock:
            entry = self._cache.get(secret_name)
            if entry is None:
                return None

            if entry.expires_at <= now:
                self._cache.pop(secret_name, None)
                return None

            return entry.value

    def _set_cached(self, secret_name: str, value: str) -> None:
        with self._cache_lock:
            self._cache[secret_name] = _CachedSecret(
                value=value,
                expires_at=time.monotonic() + self.cache_ttl_seconds,
            )
