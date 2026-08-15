"""Salesforce OAuth 2.0 authentication boundary.

The application owns secure persistence of refresh/access tokens. This module
only builds authorization requests and exchanges credentials/tokens.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from .exceptions import SalesforceAuthenticationError, SalesforceConfigurationError
from .models import SalesforceAuthConfig


class SalesforceTokenProvider:
    """OAuth provider for Salesforce External Client Apps."""

    def __init__(self, config: SalesforceAuthConfig) -> None:
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
            raise SalesforceAuthenticationError(
                "Authorization URL is only available in delegated mode."
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
                raise SalesforceAuthenticationError(
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
            raise SalesforceAuthenticationError(
                "Authorization-code exchange requires delegated mode."
            )
        if not code.strip():
            raise SalesforceAuthenticationError("Authorization code is required.")

        if self.config.require_pkce and not pkce_verifier:
            raise SalesforceAuthenticationError(
                "pkce_verifier is required when PKCE is enabled."
            )

        try:
            import httpx
        except ImportError as exc:
            raise SalesforceConfigurationError(
                "httpx is required for Salesforce authentication."
            ) from exc

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
        }
        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret
        if pkce_verifier:
            data["code_verifier"] = pkce_verifier

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.config.token_url, data=data)

        if response.status_code >= 400:
            raise SalesforceAuthenticationError(
                f"Salesforce OAuth exchange failed (HTTP {response.status_code})."
            )

        payload = response.json()
        if not payload.get("access_token") or not payload.get("instance_url"):
            raise SalesforceAuthenticationError(
                "Salesforce token response is missing access_token or instance_url."
            )
        return payload

    async def acquire_client_credentials_token(self) -> Dict[str, Any]:
        if self.config.auth_mode != "client_credentials":
            raise SalesforceAuthenticationError(
                "Client credentials requires auth_mode='client_credentials'."
            )

        try:
            import httpx
        except ImportError as exc:
            raise SalesforceConfigurationError(
                "httpx is required for Salesforce authentication."
            ) from exc

        data = {
            "grant_type": "client_credentials",
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.config.token_url, data=data)

        if response.status_code >= 400:
            raise SalesforceAuthenticationError(
                f"Salesforce client-credentials authentication failed "
                f"(HTTP {response.status_code})."
            )

        payload = response.json()
        if not payload.get("access_token") or not payload.get("instance_url"):
            raise SalesforceAuthenticationError(
                "Salesforce token response is missing access_token or instance_url."
            )
        return payload
