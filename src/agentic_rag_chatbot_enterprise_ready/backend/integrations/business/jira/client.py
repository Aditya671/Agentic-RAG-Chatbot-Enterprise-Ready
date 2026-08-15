"""Asynchronous Jira Cloud REST API v3 client."""

from __future__ import annotations

import asyncio
from typing import Any, Mapping, Optional
from urllib.parse import quote

from .exceptions import (
    JiraAPIError,
    JiraAuthorizationError,
    JiraNotFoundError,
    JiraQueryError,
    JiraRateLimitError,
)


class JiraRESTClient:
    """Transport boundary for Atlassian Jira Cloud REST API v3."""

    def __init__(
        self,
        *,
        access_token: str,
        cloud_id: str,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        if not access_token:
            raise ValueError("access_token is required.")
        if not cloud_id or not cloud_id.strip():
            raise ValueError("cloud_id is required.")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative.")

        self.access_token = access_token
        self.cloud_id = cloud_id
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def base_url(self) -> str:
        return (
            f"https://api.atlassian.com/ex/jira/"
            f"{quote(self.cloud_id, safe='')}/rest/api/3"
        )

    def _url(self, path: str) -> str:
        if path.startswith("https://"):
            if not path.startswith(self.base_url):
                raise ValueError(
                    "Absolute URL is outside the connected Jira API boundary."
                )
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    @staticmethod
    def _error_message(response: Any) -> str:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                errors = payload.get("errorMessages")
                if errors:
                    return str(errors[0])
                if payload.get("errors"):
                    return str(payload["errors"])
                return str(
                    payload.get("message")
                    or payload.get("error")
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
            raise JiraAPIError("httpx is required for Jira integration.") from exc

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
                        raise JiraAPIError(
                            "Jira request failed after retries."
                        ) from exc
                    await asyncio.sleep(min(2**attempt, 8))
                    continue

                if response.status_code == 429:
                    if attempt >= self.max_retries:
                        raise JiraRateLimitError(
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
                        raise JiraAPIError(self._error_message(response))
                    await asyncio.sleep(min(2**attempt, 8))
                    continue

                if response.status_code == 401:
                    raise JiraAuthorizationError(
                        self._error_message(response)
                    )
                if response.status_code == 403:
                    raise JiraAuthorizationError(
                        self._error_message(response)
                    )
                if response.status_code == 404:
                    raise JiraNotFoundError(
                        self._error_message(response)
                    )
                if response.status_code == 400:
                    raise JiraQueryError(
                        self._error_message(response)
                    )
                if response.status_code >= 400:
                    raise JiraAPIError(self._error_message(response))

                if response.status_code == 204:
                    return None
                return response.json()

        raise JiraAPIError("Jira request failed.") from last_error

    async def get(self, path: str, **kwargs: Any) -> Any:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> Any:
        return await self.request("POST", path, **kwargs)
