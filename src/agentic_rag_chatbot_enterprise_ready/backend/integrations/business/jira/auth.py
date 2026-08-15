"""Atlassian OAuth 2.0 3LO authentication boundary."""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from .exceptions import JiraAuthenticationError, JiraConfigurationError
from .models import JiraAuthConfig


class JiraTokenProvider:
    """OAuth 2.0 3LO provider for Jira Cloud."""

    def __init__(self, config: JiraAuthConfig) -> None:
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
        prompt: str = "consent",
    ) -> tuple[str, str]:
        state_value = state or self.create_state()

        params = {
            "audience": "api.atlassian.com",
            "client_id": self.config.client_id,
            "scope": " ".join(self.config.scopes),
            "redirect_uri": self.config.redirect_uri,
            "state": state_value,
            "response_type": "code",
            "prompt": prompt,
        }

        if self.config.require_pkce:
            if not pkce_verifier:
                raise JiraAuthenticationError(
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
        if not code.strip():
            raise JiraAuthenticationError("authorization code is required.")
        if self.config.require_pkce and not pkce_verifier:
            raise JiraAuthenticationError(
                "pkce_verifier is required when PKCE is enabled."
            )

        try:
            import httpx
        except ImportError as exc:
            raise JiraConfigurationError(
                "httpx is required for Jira authentication."
            ) from exc

        data = {
            "grant_type": "authorization_code",
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "code": code,
            "redirect_uri": self.config.redirect_uri,
        }
        if pkce_verifier:
            data["code_verifier"] = pkce_verifier

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.config.token_url, json=data)

        if response.status_code >= 400:
            raise JiraAuthenticationError(
                f"Atlassian OAuth exchange failed (HTTP {response.status_code})."
            )

        payload = response.json()
        if not payload.get("access_token"):
            raise JiraAuthenticationError(
                "Atlassian token response is missing access_token."
            )
        return payload

    async def get_accessible_resources(
        self,
        *,
        access_token: str,
    ) -> list[Dict[str, Any]]:
        if not access_token:
            raise JiraAuthenticationError("access_token is required.")

        try:
            import httpx
        except ImportError as exc:
            raise JiraConfigurationError(
                "httpx is required for Jira authentication."
            ) from exc

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                self.config.accessible_resources_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )

        if response.status_code == 401:
            raise JiraAuthenticationError("Atlassian access token is invalid.")
        if response.status_code >= 400:
            raise JiraAuthenticationError(
                f"Accessible Jira resources lookup failed "
                f"(HTTP {response.status_code})."
            )

        payload = response.json()
        if not isinstance(payload, list):
            raise JiraAuthenticationError(
                "Atlassian accessible-resources response is not a list."
            )
        return payload
