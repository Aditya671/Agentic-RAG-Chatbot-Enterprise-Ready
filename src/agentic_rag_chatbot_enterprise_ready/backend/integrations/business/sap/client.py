"""Asynchronous SAP OData HTTP client."""

from __future__ import annotations

import asyncio
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

from .auth import build_basic_auth
from .exceptions import (
    SAPAPIError,
    SAPAuthenticationError,
    SAPAuthorizationError,
    SAPNotFoundError,
    SAPQueryError,
    SAPRateLimitError,
)
from .models import SAPAuthConfig


class SAPODataClient:
    """Transport boundary for SAP OData v2/v4 APIs."""

    def __init__(
        self,
        config: SAPAuthConfig,
        *,
        access_token: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative.")

        self.config = config
        self.access_token = access_token
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def base_url(self) -> str:
        return self.config.odata_root

    def set_access_token(self, access_token: str) -> None:
        if not access_token:
            raise SAPAuthenticationError("access_token is required.")
        self.access_token = access_token

    def _url(self, path: str) -> str:
        if path.startswith("https://"):
            parsed = urlparse(path)
            base = urlparse(self.base_url)
            if parsed.scheme != "https" or parsed.netloc != base.netloc:
                raise ValueError(
                    "Absolute URL is outside the connected SAP instance."
                )
            return path

        return f"{self.base_url}/{path.lstrip('/')}"

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "Enterprise-Agent-SAP-Connector/1.0",
        }
        if self.config.auth_mode == "bearer":
            if not self.access_token:
                raise SAPAuthenticationError("Bearer access token is required.")
            headers["Authorization"] = f"Bearer {self.access_token}"
        elif self.config.auth_mode == "oauth2_client_credentials":
            if not self.access_token:
                raise SAPAuthenticationError("OAuth access token is required.")
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    @staticmethod
    def _error_message(response: Any) -> str:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                error = payload.get("error") or {}
                if isinstance(error, dict):
                    inner = error.get("innererror") or {}
                    return str(
                        error.get("message")
                        or error.get("code")
                        or inner.get("errordetails")
                        or f"HTTP {response.status_code}"
                    )
                return str(error)
        except Exception:
            pass
        return f"HTTP {response.status_code}"

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        try:
            import httpx
        except ImportError as exc:
            raise SAPAPIError("httpx is required for SAP integration.") from exc

        auth = None
        if self.config.auth_mode == "basic":
            auth = build_basic_auth(self.config)

        url = self._url(path)
        last_error: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.request(
                        method,
                        url,
                        params=params,
                        headers=self._headers(),
                        auth=auth,
                    )
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    last_error = exc
                    if attempt >= self.max_retries:
                        raise SAPAPIError(
                            "SAP request failed after retries."
                        ) from exc
                    await asyncio.sleep(min(2**attempt, 8))
                    continue

                if response.status_code == 429:
                    if attempt >= self.max_retries:
                        raise SAPRateLimitError(self._error_message(response))
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = (
                            min(float(retry_after), 30.0)
                            if retry_after
                            else min(2**attempt, 8)
                        )
                    except ValueError:
                        delay = min(2**attempt, 8)
                    await asyncio.sleep(delay)
                    continue

                if response.status_code in {408, 500, 502, 503, 504}:
                    if attempt >= self.max_retries:
                        raise SAPAPIError(self._error_message(response))
                    await asyncio.sleep(min(2**attempt, 8))
                    continue

                if response.status_code == 401:
                    raise SAPAuthenticationError(
                        self._error_message(response)
                    )
                if response.status_code == 403:
                    raise SAPAuthorizationError(
                        self._error_message(response)
                    )
                if response.status_code == 404:
                    raise SAPNotFoundError(self._error_message(response))
                if response.status_code == 400:
                    raise SAPQueryError(self._error_message(response))
                if response.status_code >= 400:
                    raise SAPAPIError(self._error_message(response))

                if response.status_code == 204:
                    return None
                return response.json()

        raise SAPAPIError("SAP request failed.") from last_error

    async def get(self, path: str, **kwargs: Any) -> Any:
        return await self.request("GET", path, **kwargs)
