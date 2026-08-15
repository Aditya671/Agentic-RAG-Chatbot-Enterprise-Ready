"""Asynchronous Salesforce REST API v67.0 client."""

from __future__ import annotations

import asyncio
from typing import Any, Mapping, Optional
from urllib.parse import quote

from .exceptions import (
    SalesforceAPIError,
    SalesforceAuthorizationError,
    SalesforceNotFoundError,
    SalesforceQueryError,
    SalesforceRateLimitError,
)


class SalesforceRESTClient:
    """HTTP boundary for Salesforce REST APIs.

    It owns transport concerns only: authorization headers, retries, API error
    normalization and SOQL/query endpoint handling.
    """

    def __init__(
        self,
        *,
        access_token: str,
        instance_url: str,
        api_version: str = "v67.0",
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        if not access_token:
            raise ValueError("access_token is required.")
        if not instance_url.startswith("https://"):
            raise ValueError("instance_url must use HTTPS.")
        if not api_version.startswith("v"):
            raise ValueError("api_version must look like vXX.0.")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative.")

        self.access_token = access_token
        self.instance_url = instance_url.rstrip("/")
        self.api_version = api_version
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def api_base_url(self) -> str:
        return f"{self.instance_url}/services/data/{self.api_version}"

    def _url(self, path: str) -> str:
        if path.startswith("https://"):
            if not path.startswith(self.instance_url):
                raise ValueError("Absolute URL is outside the Salesforce instance.")
            return path
        return f"{self.api_base_url}/{path.lstrip('/')}"

    @staticmethod
    def _error_message(response: Any) -> str:
        try:
            payload = response.json()
            if isinstance(payload, list) and payload:
                first = payload[0]
                return str(
                    first.get("message")
                    or first.get("errorCode")
                    or f"HTTP {response.status_code}"
                )
            if isinstance(payload, dict):
                return str(
                    payload.get("message")
                    or payload.get("error")
                    or f"HTTP {response.status_code}"
                )
        except Exception:
            pass
        return f"HTTP {response.status_code}"

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Any = None,
    ) -> Any:
        try:
            import httpx
        except ImportError as exc:
            raise SalesforceAPIError(
                "httpx is required for Salesforce integration."
            ) from exc

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }
        if json is not None:
            headers["Content-Type"] = "application/json"

        url = self._url(path)
        last_error: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.request(
                        method,
                        url,
                        params=params,
                        json=json,
                        headers=headers,
                    )
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    last_error = exc
                    if attempt >= self.max_retries:
                        raise SalesforceAPIError(
                            "Salesforce request failed after retries."
                        ) from exc
                    await asyncio.sleep(min(2**attempt, 8))
                    continue

                if response.status_code == 429:
                    if attempt >= self.max_retries:
                        raise SalesforceRateLimitError(
                            self._error_message(response)
                        )
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = min(float(retry_after), 30.0) if retry_after else min(2**attempt, 8)
                    except ValueError:
                        delay = min(2**attempt, 8)
                    await asyncio.sleep(delay)
                    continue

                if response.status_code in {408, 500, 502, 503, 504}:
                    if attempt >= self.max_retries:
                        raise SalesforceAPIError(self._error_message(response))
                    await asyncio.sleep(min(2**attempt, 8))
                    continue

                if response.status_code == 401:
                    raise SalesforceAuthorizationError(
                        self._error_message(response)
                    )
                if response.status_code == 403:
                    raise SalesforceAuthorizationError(
                        self._error_message(response)
                    )
                if response.status_code == 404:
                    raise SalesforceNotFoundError(
                        self._error_message(response)
                    )
                if response.status_code == 400:
                    raise SalesforceQueryError(self._error_message(response))
                if response.status_code >= 400:
                    raise SalesforceAPIError(self._error_message(response))

                if response.status_code == 204:
                    return None
                return response.json()

        raise SalesforceAPIError("Salesforce request failed.") from last_error

    async def get(self, path: str, **kwargs: Any) -> Any:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> Any:
        return await self.request("POST", path, **kwargs)
