"""SAP authentication boundary."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .exceptions import SAPAuthenticationError, SAPConfigurationError
from .models import SAPAuthConfig


class SAPTokenProvider:
    """OAuth 2.0 client-credentials token provider."""

    def __init__(self, config: SAPAuthConfig) -> None:
        self.config = config

    async def acquire_token(self) -> Dict[str, Any]:
        if self.config.auth_mode != "oauth2_client_credentials":
            raise SAPAuthenticationError(
                "OAuth token acquisition requires oauth2_client_credentials mode."
            )

        try:
            import httpx
        except ImportError as exc:
            raise SAPConfigurationError(
                "httpx is required for SAP authentication."
            ) from exc

        data = {"grant_type": "client_credentials"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.config.token_url,
                data=data,
                auth=(self.config.client_id, self.config.client_secret),
                headers={"Accept": "application/json"},
            )

        if response.status_code >= 400:
            raise SAPAuthenticationError(
                f"SAP OAuth token request failed (HTTP {response.status_code})."
            )

        payload = response.json()
        if not payload.get("access_token"):
            raise SAPAuthenticationError(
                "SAP token response is missing access_token."
            )
        return payload


def build_basic_auth(config: SAPAuthConfig) -> tuple[str, str]:
    if config.auth_mode != "basic":
        raise SAPAuthenticationError(
            "Basic credentials requested for a non-basic configuration."
        )
    if not config.username or config.password is None:
        raise SAPAuthenticationError("SAP basic credentials are incomplete.")
    return config.username, config.password
