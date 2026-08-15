"""Low-level asynchronous Microsoft Graph client for SharePoint."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Mapping, Optional
from urllib.parse import quote

from .exceptions import (
    SharePointAPIError,
    SharePointAuthorizationError,
    SharePointNotFoundError,
    SharePointRateLimitError,
)


class SharePointGraphClient:
    """Small, typed HTTP boundary over Microsoft Graph v1.0.

    The class intentionally does not contain business orchestration. It owns
    HTTP concerns: auth headers, retries for transient failures, pagination,
    error normalization, and response parsing.
    """

    def __init__(
        self,
        *,
        access_token: str,
        graph_base_url: str = "https://graph.microsoft.com/v1.0",
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        if not access_token:
            raise ValueError("access_token is required.")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative.")

        self.access_token = access_token
        self.graph_base_url = graph_base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    def _url(self, path_or_url: str) -> str:
        if path_or_url.startswith("https://"):
            if not path_or_url.startswith(self.graph_base_url):
                raise ValueError("Absolute URL is outside the configured Graph endpoint.")
            return path_or_url

        return f"{self.graph_base_url}/{path_or_url.lstrip('/')}"

    @staticmethod
    def _error_message(response: Any) -> str:
        try:
            payload = response.json()
            error = payload.get("error") or {}
            return str(
                error.get("message")
                or error.get("code")
                or f"HTTP {response.status_code}"
            )
        except Exception:
            return f"HTTP {response.status_code}"

    async def request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Any = None,
        content: Any = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        try:
            import httpx
        except ImportError as exc:
            raise SharePointAPIError(
                "httpx is required for SharePoint integration."
            ) from exc

        request_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }
        if json is not None:
            request_headers["Content-Type"] = "application/json"
        if headers:
            request_headers.update(headers)

        url = self._url(path_or_url)
        last_error: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.request(
                        method,
                        url,
                        params=params,
                        json=json,
                        content=content,
                        headers=request_headers,
                    )
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    last_error = exc
                    if attempt >= self.max_retries:
                        raise SharePointAPIError(
                            "Microsoft Graph request failed after retries."
                        ) from exc
                    await asyncio.sleep(min(2**attempt, 8))
                    continue

                if response.status_code == 429:
                    if attempt >= self.max_retries:
                        raise SharePointRateLimitError(
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
                        raise SharePointAPIError(self._error_message(response))
                    await asyncio.sleep(min(2**attempt, 8))
                    continue

                if response.status_code == 401:
                    raise SharePointAuthorizationError(
                        "Microsoft Graph rejected the access token."
                    )
                if response.status_code == 403:
                    raise SharePointAuthorizationError(
                        self._error_message(response)
                    )
                if response.status_code == 404:
                    raise SharePointNotFoundError(
                        self._error_message(response)
                    )
                if response.status_code >= 400:
                    raise SharePointAPIError(
                        self._error_message(response)
                    )

                if response.status_code == 204:
                    return None

                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    return response.json()
                return response.content

        raise SharePointAPIError("Microsoft Graph request failed.") from last_error

    async def get(self, path_or_url: str, **kwargs: Any) -> Any:
        return await self.request("GET", path_or_url, **kwargs)

    async def post(self, path_or_url: str, **kwargs: Any) -> Any:
        return await self.request("POST", path_or_url, **kwargs)

    async def put(self, path_or_url: str, **kwargs: Any) -> Any:
        return await self.request("PUT", path_or_url, **kwargs)

    async def delete(self, path_or_url: str, **kwargs: Any) -> Any:
        return await self.request("DELETE", path_or_url, **kwargs)

    async def paginate(
        self,
        path_or_url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
    ) -> list[Dict[str, Any]]:
        first = await self.get(path_or_url, params=params)
        values = list(first.get("value") or [])
        next_link = first.get("@odata.nextLink")

        while next_link:
            page = await self.get(next_link)
            values.extend(page.get("value") or [])
            next_link = page.get("@odata.nextLink")

        return values
