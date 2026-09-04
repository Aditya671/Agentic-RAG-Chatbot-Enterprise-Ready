"""Asynchronous Jira Cloud REST API v3 client."""

from __future__ import annotations

import asyncio
from typing import Any, Mapping, Optional
from urllib.parse import quote, urlsplit

from .exceptions import (
    JiraAPIError,
    JiraAuthorizationError,
    JiraNotFoundError,
    JiraQueryError,
    JiraRateLimitError,
)


class JiraRESTClient:
    """Transport boundary for Atlassian Jira Cloud REST API v3."""

    _RETRYABLE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    def __init__(
        self,
        *,
        access_token: str,
        cloud_id: str,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        if not isinstance(access_token, str) or not access_token.strip():
            raise ValueError("access_token is required.")
        if not isinstance(cloud_id, str) or not cloud_id.strip():
            raise ValueError("cloud_id is required.")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError("timeout must be greater than zero.")
        if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
            raise ValueError("max_retries must be non-negative.")

        self.access_token = access_token.strip()
        self.cloud_id = cloud_id.strip()
        self.timeout = float(timeout)
        self.max_retries = max_retries

    @property
    def base_url(self) -> str:
        return f"https://api.atlassian.com/ex/jira/{quote(self.cloud_id, safe='')}/rest/api/3"

    def _url(self, path: str) -> str:
        if not isinstance(path, str) or not path.strip():
            raise ValueError("Jira API path must be a non-empty string.")

        candidate = path.strip()
        if candidate.startswith("https://"):
            parsed = urlsplit(candidate)
            base = urlsplit(self.base_url)
            if parsed.scheme != base.scheme or parsed.netloc != base.netloc:
                raise ValueError("Absolute URL is outside the connected Jira API host.")
            base_path = base.path.rstrip("/")
            if parsed.path != base_path and not parsed.path.startswith(base_path + "/"):
                raise ValueError("Absolute URL is outside the connected Jira API path.")
            return candidate
        if "://" in candidate:
            raise ValueError("Only HTTPS Jira API URLs are allowed.")
        return f"{self.base_url}/{candidate.lstrip('/')}"

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

        normalized_method = method.strip().upper() if isinstance(method, str) else ""
        if not normalized_method.isalpha():
            raise ValueError("HTTP method must be a valid method token.")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }
        if json is not None:
            headers["Content-Type"] = "application/json"

        url = self._url(path)
        last_error: Optional[Exception] = None
        retryable = normalized_method in self._RETRYABLE_METHODS

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.request(
                        normalized_method,
                        url,
                        params=params,
                        json=json,
                        headers=headers,
                    )
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    last_error = exc
                    if not retryable or attempt >= self.max_retries:
                        raise JiraAPIError("Jira request failed after retries.") from exc
                    await asyncio.sleep(min(2**attempt, 8))
                    continue

                if response.status_code == 429:
                    if not retryable or attempt >= self.max_retries:
                        raise JiraRateLimitError(self._error_message(response))
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = min(float(retry_after), 30.0) if retry_after else min(2**attempt, 8)
                    except (TypeError, ValueError):
                        delay = min(2**attempt, 8)
                    await asyncio.sleep(max(0.0, delay))
                    continue

                if response.status_code in {408, 500, 502, 503, 504}:
                    if not retryable or attempt >= self.max_retries:
                        raise JiraAPIError(self._error_message(response))
                    await asyncio.sleep(min(2**attempt, 8))
                    continue

                if response.status_code in {401, 403}:
                    raise JiraAuthorizationError(self._error_message(response))
                if response.status_code == 404:
                    raise JiraNotFoundError(self._error_message(response))
                if response.status_code == 400:
                    raise JiraQueryError(self._error_message(response))
                if response.status_code >= 400:
                    raise JiraAPIError(self._error_message(response))

                if response.status_code == 204:
                    return None
                try:
                    return response.json()
                except ValueError as exc:
                    raise JiraAPIError("Jira returned a non-JSON success response.") from exc

        raise JiraAPIError("Jira request failed.") from last_error

    async def get(self, path: str, **kwargs: Any) -> Any:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> Any:
        return await self.request("POST", path, **kwargs)
