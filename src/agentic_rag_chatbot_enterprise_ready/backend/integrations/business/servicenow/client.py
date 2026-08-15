"""Asynchronous ServiceNow Table API client."""

from __future__ import annotations

import asyncio
from typing import Any, Mapping, Optional
from urllib.parse import quote

from .exceptions import (
    ServiceNowAPIError,
    ServiceNowAuthorizationError,
    ServiceNowNotFoundError,
    ServiceNowQueryError,
    ServiceNowRateLimitError,
)


class ServiceNowRESTClient:
    """Transport boundary for ServiceNow REST APIs."""

    def __init__(
        self,
        *,
        access_token: str,
        instance_url: str,
        api_path: str = "/api/now",
        api_version: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        if not access_token:
            raise ValueError("access_token is required.")
        if not instance_url.startswith("https://"):
            raise ValueError("instance_url must use HTTPS.")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative.")

        self.access_token = access_token
        self.instance_url = instance_url.rstrip("/")
        self.api_path = "/" + api_path.strip("/")
        self.api_version = (
            "/" + api_version.strip("/")
            if api_version
            else ""
        )
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def base_url(self) -> str:
        return f"{self.instance_url}{self.api_path}{self.api_version}"

    def _url(self, path: str) -> str:
        if path.startswith("https://"):
            if not path.startswith(self.instance_url):
                raise ValueError(
                    "Absolute URL is outside the connected ServiceNow instance."
                )
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    @staticmethod
    def _error_message(response: Any) -> str:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                error = payload.get("error") or {}
                return str(
                    error.get("message")
                    or payload.get("message")
                    or error.get("detail")
                    or f"HTTP {response.status_code}"
                )
            if isinstance(payload, list) and payload:
                return str(payload[0])
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
            raise ServiceNowAPIError(
                "httpx is required for ServiceNow integration."
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
                        raise ServiceNowAPIError(
                            "ServiceNow request failed after retries."
                        ) from exc
                    await asyncio.sleep(min(2**attempt, 8))
                    continue

                if response.status_code == 429:
                    if attempt >= self.max_retries:
                        raise ServiceNowRateLimitError(
                            self._error_message(response)
                        )
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
                        raise ServiceNowAPIError(
                            self._error_message(response)
                        )
                    await asyncio.sleep(min(2**attempt, 8))
                    continue

                if response.status_code == 401:
                    raise ServiceNowAuthorizationError(
                        self._error_message(response)
                    )
                if response.status_code == 403:
                    raise ServiceNowAuthorizationError(
                        self._error_message(response)
                    )
                if response.status_code == 404:
                    raise ServiceNowNotFoundError(
                        self._error_message(response)
                    )
                if response.status_code == 400:
                    raise ServiceNowQueryError(
                        self._error_message(response)
                    )
                if response.status_code >= 400:
                    raise ServiceNowAPIError(
                        self._error_message(response)
                    )

                if response.status_code == 204:
                    return None
                return response.json()

        raise ServiceNowAPIError("ServiceNow request failed.") from last_error

    async def get(self, path: str, **kwargs: Any) -> Any:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> Any:
        return await self.request("POST", path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> Any:
        return await self.request("PATCH", path, **kwargs)
