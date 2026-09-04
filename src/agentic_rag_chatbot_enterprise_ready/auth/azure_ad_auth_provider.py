"""Azure AD OAuth provider for Chainlit authentication."""

from __future__ import annotations

import os
from typing import Any

import httpx
import jwt
from fastapi import HTTPException
from jwt import PyJWKClient
from chainlit.oauth_providers import OAuthProvider
from chainlit.user import User


class AzureADOAuthProvider(OAuthProvider):
    """Authenticate Chainlit users with Microsoft Entra ID v2 tokens."""

    id = "azure-ad"
    env = [
        "OAUTH_AZURE_AD_CLIENT_ID",
        "OAUTH_AZURE_AD_CLIENT_SECRET",
        "OAUTH_AZURE_AD_TENANT_ID",
    ]

    def __init__(self) -> None:
        self.client_id = os.environ.get("OAUTH_AZURE_AD_CLIENT_ID")
        self.client_secret = os.environ.get("OAUTH_AZURE_AD_CLIENT_SECRET")
        self.tenant = os.environ.get("OAUTH_AZURE_AD_TENANT_ID", "common").strip()
        if not self.tenant:
            raise ValueError("OAUTH_AZURE_AD_TENANT_ID must not be empty.")

        self.url_base = f"https://login.microsoftonline.com/{self.tenant}/"
        self.authorize_url = f"{self.url_base}oauth2/v2.0/authorize"
        self.token_url = f"{self.url_base}oauth2/v2.0/token"
        self.well_known_url = (
            f"https://login.microsoftonline.com/{self.tenant}"
            "/v2.0/.well-known/openid-configuration"
        )
        self.iss_url = f"https://login.microsoftonline.com/{self.tenant}/v2.0"
        self.authorize_params = {
            "response_type": "code",
            "response_mode": "query",
            "scope": "openid profile email offline_access",
        }

    async def get_token(self, code: str, url: str) -> str:
        """Exchange an authorization code for an ID token."""
        if not isinstance(code, str) or not code.strip():
            raise HTTPException(status_code=400, detail="Authorization code is required.")
        if not isinstance(url, str) or not url.strip():
            raise HTTPException(status_code=400, detail="Redirect URI is required.")
        if not self.client_id or not self.client_secret:
            raise HTTPException(status_code=500, detail="Azure AD OAuth credentials are not configured.")

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": url,
            "scope": "openid profile email offline_access",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(self.token_url, data=payload)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise HTTPException(
                    status_code=400,
                    detail="Azure AD token exchange failed.",
                ) from exc
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=502,
                    detail="Azure AD token service is unavailable.",
                ) from exc

        try:
            data: Any = response.json()
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="Azure AD returned invalid token data.") from exc

        token = data.get("id_token") if isinstance(data, dict) else None
        if not isinstance(token, str) or not token:
            raise HTTPException(status_code=400, detail="No id_token in token response.")
        return token

    async def get_user_info(self, token: str):
        """Validate an ID token against the tenant's OpenID configuration."""
        if not isinstance(token, str) or not token.strip():
            raise HTTPException(status_code=400, detail="ID token is required.")
        if not self.client_id:
            raise HTTPException(status_code=500, detail="Azure AD client ID is not configured.")

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(self.well_known_url)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise HTTPException(status_code=502, detail="Failed to fetch Azure AD OpenID configuration.") from exc
            except httpx.HTTPError as exc:
                raise HTTPException(status_code=502, detail="Azure AD OpenID configuration is unavailable.") from exc

        try:
            well_known: Any = resp.json()
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="Azure AD returned invalid OpenID configuration.") from exc

        if not isinstance(well_known, dict):
            raise HTTPException(status_code=502, detail="Azure AD OpenID configuration is invalid.")

        jwks_uri = well_known.get("jwks_uri")
        issuer = well_known.get("issuer")
        algorithms = well_known.get("id_token_signing_alg_values_supported")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise HTTPException(status_code=502, detail="Azure AD configuration has no JWKS endpoint.")
        if not isinstance(issuer, str) or not issuer:
            issuer = self.iss_url
        if not isinstance(algorithms, list) or not all(isinstance(item, str) for item in algorithms):
            algorithms = ["RS256"]

        try:
            signing_key = PyJWKClient(jwks_uri).get_signing_key_from_jwt(token).key
            azure_user = jwt.decode(
                token,
                signing_key,
                algorithms=algorithms,
                audience=self.client_id,
                issuer=issuer,
                options={"verify_aud": True, "verify_iss": True},
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(status_code=401, detail="Invalid Azure AD ID token.") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Unable to validate Azure AD ID token.") from exc

        identifier = (
            azure_user.get("oid")
            or azure_user.get("sub")
            or azure_user.get("preferred_username")
            or azure_user.get("email")
            or azure_user.get("upn")
        )
        if not isinstance(identifier, str) or not identifier.strip():
            raise HTTPException(status_code=400, detail="Could not determine user identifier from token claims.")

        user = User(
            identifier=identifier,
            metadata={
                "image": azure_user.get("image"),
                "provider": "azure-ad",
            },
        )
        return azure_user, user
