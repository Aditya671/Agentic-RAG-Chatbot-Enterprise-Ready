"""ServiceNow OAuth 2.0 authentication boundary."""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from .exceptions import (
    ServiceNowAuthenticationError,
    ServiceNowConfigurationError,
)
from .models import ServiceNowAuthConfig


class ServiceNowTokenProvider:
    """OAuth provider for ServiceNow inbound external clients."""

    def __init__(self, config: ServiceNowAuthConfig) -> None:
        self.config = config

    @staticmethod
    def create_state() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def create_pkce_verifier() -> str:
        return secrets.token_urlsafe(64)

    @staticmethod
    def create_pkce_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def build_authorization_url(
        self,
        *,
        state: Optional[str] = None,
        pkce_verifier: Optional[str] = None,
    ) -> tuple[str, str]:
        if self.config.auth_mode != "delegated":
            raise ServiceNowAuthenticationError(
                "Authorization URL requires delegated mode."
            )

        state_value = state or self.create_state()

        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(self.config.scopes),
            "state": state_value,
        }

        if self.config.require_pkce:
            if not pkce_verifier:
                raise ServiceNowAuthenticationError(
                    "pkce_verifier is required when PKCE is enabled."
                )
            params["code_challenge"] = self.create_pkce_challenge(pkce_verifier)
            params["code_challenge_method"] = "S256"

        return f"{self.config.authorize_url}?{urlencode(params)}", state_value

    async def exchange_authorization_code(
        self,
        *,
        code: str,
        pkce_verifier: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self.config.auth_mode != "delegated":
            raise ServiceNowAuthenticationError(
                "Authorization-code exchange requires delegated mode."
            )
        if not code or not code.strip():
            raise ServiceNowAuthenticationError(
                "authorization code is required."
            )
        if self.config.require_pkce and not pkce_verifier:
            raise ServiceNowAuthenticationError(
                "pkce_verifier is required when PKCE is enabled."
            )

        try:
            import httpx
        except ImportError as exc:
            raise ServiceNowConfigurationError(
                "httpx is required for ServiceNow authentication."
            ) from exc

        data = {
            "grant_type": "authorization_code",
            "client_id": self.config.client_id,
            "code": code,
            "redirect_uri": self.config.redirect_uri,
        }

        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret
        if pkce_verifier:
            data["code_verifier"] = pkce_verifier

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.config.token_url, data=data)

        if response.status_code >= 400:
            raise ServiceNowAuthenticationError(
                f"ServiceNow OAuth exchange failed "
                f"(HTTP {response.status_code})."
            )

        payload = response.json()
        if not payload.get("access_token"):
            raise ServiceNowAuthenticationError(
                "ServiceNow token response is missing access_token."
            )
        return payload

    async def acquire_client_credentials_token(self) -> Dict[str, Any]:
        if self.config.auth_mode != "client_credentials":
            raise ServiceNowAuthenticationError(
                "Client credentials requires auth_mode='client_credentials'."
            )

        try:
            import httpx
        except ImportError as exc:
            raise ServiceNowConfigurationError(
                "httpx is required for ServiceNow authentication."
            ) from exc

        data = {
            "grant_type": "client_credentials",
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.config.token_url, data=data)

        if response.status_code >= 400:
            raise ServiceNowAuthenticationError(
                f"ServiceNow client-credentials authentication failed "
                f"(HTTP {response.status_code})."
            )

        payload = response.json()
        if not payload.get("access_token"):
            raise ServiceNowAuthenticationError(
                "ServiceNow token response is missing access_token."
            )
        return payload
