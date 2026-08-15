"""Microsoft Entra authentication for SharePoint Online via Microsoft Graph.

Two modes are supported:

1. delegated: authorization-code flow for a user-opt-in web experience;
2. app-only: client-credential flow for controlled enterprise service scenarios.

The connector never persists raw access tokens. Token persistence belongs to
the application's secure connection store.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence
from urllib.parse import urlencode

from .exceptions import (
    SharePointAuthenticationError,
    SharePointConfigurationError,
)

DEFAULT_GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
DEFAULT_AUTHORITY_HOST = "https://login.microsoftonline.com"
DEFAULT_DELEGATED_SCOPES = (
    "openid",
    "profile",
    "offline_access",
    "User.Read",
    "Sites.Read.All",
    "Files.Read",
)


@dataclass(frozen=True)
class SharePointAuthConfig:
    tenant_id: str
    client_id: str
    client_secret: Optional[str] = None
    redirect_uri: Optional[str] = None
    authority_host: str = DEFAULT_AUTHORITY_HOST
    graph_base_url: str = DEFAULT_GRAPH_BASE_URL
    delegated_scopes: Sequence[str] = field(
        default_factory=lambda: DEFAULT_DELEGATED_SCOPES
    )
    auth_mode: str = "delegated"

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.tenant_id.strip():
            raise SharePointConfigurationError("tenant_id is required.")
        if not self.client_id or not self.client_id.strip():
            raise SharePointConfigurationError("client_id is required.")

        if self.auth_mode not in {"delegated", "app_only"}:
            raise SharePointConfigurationError(
                "auth_mode must be 'delegated' or 'app_only'."
            )

        if self.auth_mode == "delegated" and not self.redirect_uri:
            raise SharePointConfigurationError(
                "redirect_uri is required for delegated authentication."
            )

        if self.auth_mode == "app_only" and not self.client_secret:
            raise SharePointConfigurationError(
                "client_secret is required for the app_only connector mode."
            )

        object.__setattr__(
            self,
            "delegated_scopes",
            tuple(dict.fromkeys(self.delegated_scopes)),
        )

    @property
    def authority(self) -> str:
        return (
            f"{self.authority_host.rstrip('/')}/"
            f"{self.tenant_id}"
        )


class SharePointTokenProvider:
    """Acquire Microsoft Graph tokens without storing raw tokens."""

    def __init__(self, config: SharePointAuthConfig) -> None:
        self.config = config

    def build_authorization_url(
        self,
        *,
        state: Optional[str] = None,
        code_challenge: Optional[str] = None,
    ) -> tuple[str, str]:
        if self.config.auth_mode != "delegated":
            raise SharePointAuthenticationError(
                "Authorization URL is only available in delegated mode."
            )

        state_value = state or secrets.token_urlsafe(32)

        params = {
            "client_id": self.config.client_id,
            "response_type": "code",
            "redirect_uri": self.config.redirect_uri,
            "response_mode": "query",
            "scope": " ".join(self.config.delegated_scopes),
            "state": state_value,
        }

        if code_challenge:
            params.update(
                {
                    "code_challenge": code_challenge,
                    "code_challenge_method": "S256",
                }
            )

        url = (
            f"{self.config.authority}/oauth2/v2.0/authorize?"
            f"{urlencode(params)}"
        )
        return url, state_value

    @staticmethod
    def create_pkce_verifier() -> str:
        return secrets.token_urlsafe(64)

    @staticmethod
    def create_pkce_challenge(verifier: str) -> str:
        import base64

        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    async def exchange_authorization_code(
        self,
        *,
        code: str,
        pkce_verifier: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self.config.auth_mode != "delegated":
            raise SharePointAuthenticationError(
                "Authorization-code exchange is only available in delegated mode."
            )
        if not code or not code.strip():
            raise SharePointAuthenticationError("Authorization code is required.")

        try:
            import httpx
        except ImportError as exc:
            raise SharePointConfigurationError(
                "httpx is required for SharePoint authentication."
            ) from exc

        data = {
            "client_id": self.config.client_id,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(self.config.delegated_scopes),
        }
        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret
        if pkce_verifier:
            data["code_verifier"] = pkce_verifier

        token_url = f"{self.config.authority}/oauth2/v2.0/token"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(token_url, data=data)

        if response.status_code >= 400:
            raise SharePointAuthenticationError(
                f"Microsoft Entra token exchange failed "
                f"(HTTP {response.status_code})."
            )

        payload = response.json()
        if "access_token" not in payload:
            raise SharePointAuthenticationError(
                "Microsoft Entra token response did not contain access_token."
            )

        return payload

    async def acquire_app_only_token(self) -> str:
        if self.config.auth_mode != "app_only":
            raise SharePointAuthenticationError(
                "App-only token acquisition requires auth_mode='app_only'."
            )

        try:
            import msal
        except ImportError as exc:
            raise SharePointConfigurationError(
                "msal is required for app-only SharePoint authentication."
            ) from exc

        application = msal.ConfidentialClientApplication(
            client_id=self.config.client_id,
            authority=self.config.authority,
            client_credential=self.config.client_secret,
        )

        result = application.acquire_token_for_client(
            scopes=[f"{self.config.graph_base_url.rstrip('/').replace('/v1.0', '')}/.default"]
        )

        if "access_token" not in result:
            error = result.get("error_description") or result.get("error")
            raise SharePointAuthenticationError(
                f"Microsoft Entra app-only authentication failed: {error}"
            )

        return str(result["access_token"])
