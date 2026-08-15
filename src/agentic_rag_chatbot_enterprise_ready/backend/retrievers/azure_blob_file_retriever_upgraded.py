from __future__ import annotations

import io
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from json import loads
from typing import Any, Iterable, Optional, Protocol


logger = logging.getLogger(__name__)


class BlobContainerClientProtocol(Protocol):
    def list_blobs(self, name_starts_with: str = "") -> Iterable[Any]: ...
    def get_blob_client(self, blob_name: str) -> Any: ...


@dataclass
class BlobStream:
    """Downloaded blob content plus the metadata needed by downstream ingestion."""

    name: str
    size: int
    content_type: Optional[str]
    last_modified: Optional[datetime]
    etag: Optional[str]
    stream: io.BytesIO

    def to_bytes(self) -> bytes:
        """Return the complete content without changing the caller's stream position."""
        pos = self.stream.tell()
        try:
            self.stream.seek(0)
            return self.stream.read()
        finally:
            self.stream.seek(pos)

    def to_json(self) -> Any:
        """Decode the complete stream as UTF-8 JSON."""
        return loads(self.to_bytes().decode("utf-8"))

    def to_str(self, encoding: str = "utf-8") -> str:
        """Decode the complete stream using the requested text encoding."""
        return self.to_bytes().decode(encoding)


class AzureBlobFileRetriever:
    """Small, testable adapter around Azure Blob Storage.

    Preferred production usage is dependency injection of an already configured
    ContainerClient. A connection string is retained for backward compatibility.
    An account URL + TokenCredential can also be supplied for passwordless Azure
    authentication.
    """

    def __init__(
        self,
        container_client_service: Optional[BlobContainerClientProtocol] = None,
        connection_string: Optional[str] = None,
        container_name: Optional[str] = None,
        *,
        account_url: Optional[str] = None,
        credential: Optional[Any] = None,
    ):
        supplied_container = container_client_service is not None
        connection_config = connection_string is not None
        passwordless_config = account_url is not None or credential is not None

        if supplied_container:
            self.container_client = container_client_service
            self.blob_service = None
            return

        if connection_config and (account_url is not None or credential is not None):
            raise ValueError(
                "Choose either connection_string or account_url/credential authentication."
            )

        if connection_config:
            if not container_name:
                raise ValueError(
                    "container_name is required when connection_string is provided."
                )
            try:
                from azure.storage.blob import BlobServiceClient
            except ImportError as exc:
                raise ImportError(
                    "azure-storage-blob is required when using connection_string authentication."
                ) from exc

            try:
                self.blob_service = BlobServiceClient.from_connection_string(
                    conn_str=connection_string
                )
                self.container_client = self.blob_service.get_container_client(
                    container=container_name
                )
            except Exception as exc:
                raise ValueError(
                    f"Failed to create Azure Blob container client for '{container_name}'."
                ) from exc
            return

        if passwordless_config:
            if not account_url or credential is None:
                raise ValueError(
                    "Both account_url and credential are required for passwordless authentication."
                )
            if not container_name:
                raise ValueError(
                    "container_name is required when account_url/credential is provided."
                )
            try:
                from azure.storage.blob import BlobServiceClient
            except ImportError as exc:
                raise ImportError(
                    "azure-storage-blob is required for passwordless authentication."
                ) from exc

            try:
                self.blob_service = BlobServiceClient(
                    account_url=account_url,
                    credential=credential,
                )
                self.container_client = self.blob_service.get_container_client(
                    container=container_name
                )
            except Exception as exc:
                raise ValueError(
                    f"Failed to create Azure Blob container client for '{container_name}'."
                ) from exc
            return

        raise ValueError(
            "Provide container_client_service, or connection_string + container_name, "
            "or account_url + credential + container_name."
        )

    @staticmethod
    def _to_utc_naive(dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    @staticmethod
    def _normalize_extension(extension: str) -> str:
        if not isinstance(extension, str) or not extension.strip():
            raise ValueError("extension must be a non-empty string.")
        extension = extension.strip().lower()
        return extension if extension.startswith(".") else f".{extension}"

    @staticmethod
    def _parse_date_from_name(
        name: str,
        date_regex: str,
        date_format: str,
    ) -> Optional[datetime]:
        try:
            match = re.search(date_regex, name)
            if not match:
                return None
            return datetime.strptime(match.group(1), date_format)
        except (IndexError, TypeError, ValueError, re.error):
            return None

    def _iter_blobs(self, prefix: Optional[str]) -> Iterable[Any]:
        return self.container_client.list_blobs(name_starts_with=prefix or "")

    def _pick_latest_blob(
        self,
        blobs: Iterable[Any],
        extension: str,
        prefer_name_date: bool,
        date_regex: str,
        date_format: str,
    ) -> Optional[Any]:
        extension = self._normalize_extension(extension)
        best_blob = None
        best_key = None

        for blob in blobs:
            name = getattr(blob, "name", None)
            if not name or not name.lower().endswith(extension):
                continue

            parsed_date = (
                self._parse_date_from_name(
                    name.rsplit("/", 1)[-1],
                    date_regex,
                    date_format,
                )
                if prefer_name_date
                else None
            )

            last_modified = self._to_utc_naive(
                getattr(blob, "last_modified", None)
            )

            if parsed_date is not None:
                # A valid filename date is authoritative when requested.
                # Last-modified and name provide deterministic tie-breakers.
                key = (
                    1,
                    parsed_date,
                    last_modified or datetime.min,
                    name,
                )
            else:
                # Blobs without a parseable date fall back to service metadata.
                key = (
                    0,
                    last_modified or datetime.min,
                    name,
                )

            if best_key is None or key > best_key:
                best_key = key
                best_blob = blob

        return best_blob

    @staticmethod
    def _blob_metadata(blob_client: Any, fallback_size: int) -> tuple[int, Optional[str], Optional[datetime], Optional[str]]:
        props = blob_client.get_blob_properties()
        content_settings = getattr(props, "content_settings", None)
        return (
            getattr(props, "size", fallback_size),
            getattr(content_settings, "content_type", None),
            getattr(props, "last_modified", None),
            getattr(props, "etag", None),
        )

    def get_latest_file_stream(
        self,
        prefix: Optional[str] = None,
        extension: str = ".csv",
        prefer_name_date: bool = True,
        date_regex: str = r"(\d{8})",
        date_format: str = "%Y%m%d",
        max_concurrency: int = 4,
    ) -> BlobStream:
        if not isinstance(max_concurrency, int) or max_concurrency < 1:
            raise ValueError("max_concurrency must be a positive integer.")

        extension = self._normalize_extension(extension)
        blobs = self._iter_blobs(prefix)

        latest = self._pick_latest_blob(
            blobs=blobs,
            extension=extension,
            prefer_name_date=prefer_name_date,
            date_regex=date_regex,
            date_format=date_format,
        )
        if latest is None:
            raise FileNotFoundError(
                f"No matching '*{extension}' blobs found under prefix='{prefix or ''}'"
            )

        blob_client = self.container_client.get_blob_client(latest.name)
        downloader = blob_client.download_blob(max_concurrency=max_concurrency)
        content = downloader.readall()

        size, content_type, last_modified, etag = self._blob_metadata(
            blob_client, len(content)
        )

        return BlobStream(
            name=latest.name,
            size=size,
            content_type=content_type,
            last_modified=last_modified,
            etag=etag,
            stream=io.BytesIO(content),
        )

    def get_blob(self, file_name: str) -> BlobStream:
        if not isinstance(file_name, str) or not file_name.strip():
            raise ValueError("file_name must be a non-empty string.")

        blob_client = self.container_client.get_blob_client(file_name)
        downloaded_stream = blob_client.download_blob()
        content = downloaded_stream.readall()
        size, content_type, last_modified, etag = self._blob_metadata(
            blob_client, len(content)
        )

        return BlobStream(
            name=blob_client.blob_name,
            size=size,
            content_type=content_type,
            last_modified=last_modified,
            etag=etag,
            stream=io.BytesIO(content),
        )

    def download_to_file(self, blob_stream: BlobStream, destination_path: str) -> str:
        """Write a BlobStream to disk and return the resolved destination path."""
        if not isinstance(blob_stream, BlobStream):
            raise TypeError("blob_stream must be a BlobStream.")
        if not isinstance(destination_path, str) or not destination_path.strip():
            raise ValueError("destination_path must be a non-empty path.")

        destination = os.path.abspath(os.path.expanduser(destination_path))
        parent = os.path.dirname(destination)
        if parent:
            os.makedirs(parent, exist_ok=True)

        with open(destination, "wb") as file_handle:
            file_handle.write(blob_stream.to_bytes())

        logger.info("Saved blob '%s' to '%s'", blob_stream.name, destination)
        return destination

    def get_and_save_latest(
        self,
        local_directory: str,
        prefix: Optional[str] = None,
        extension: str = ".pdf",
        prefer_name_date: bool = True,
        date_regex: str = r"(\d{8})",
        date_format: str = "%Y%m%d",
        max_concurrency: int = 4,
    ) -> str:
        """Find the latest matching blob, download it, and save it locally."""
        if not isinstance(local_directory, str) or not local_directory.strip():
            raise ValueError("local_directory must be a non-empty path.")

        blob_stream = self.get_latest_file_stream(
            prefix=prefix,
            extension=extension,
            prefer_name_date=prefer_name_date,
            date_regex=date_regex,
            date_format=date_format,
            max_concurrency=max_concurrency,
        )

        filename = os.path.basename(blob_stream.name)
        if not filename:
            raise ValueError(f"Blob name '{blob_stream.name}' has no filename component.")

        destination = os.path.join(local_directory, filename)
        return self.download_to_file(blob_stream, destination)
