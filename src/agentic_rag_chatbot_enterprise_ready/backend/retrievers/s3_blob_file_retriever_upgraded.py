from __future__ import annotations

import io
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from json import loads
from typing import Any, Iterable, Optional, Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


class S3ClientProtocol(Protocol):
    def get_paginator(self, operation_name: str) -> Any: ...
    def get_object(self, **kwargs: Any) -> Any: ...


@dataclass
class BlobStream:
    """Downloaded S3 object content plus metadata for downstream ingestion."""

    name: str
    size: int
    content_type: Optional[str]
    last_modified: Optional[datetime]
    etag: Optional[str]
    stream: io.BytesIO

    def to_bytes(self) -> bytes:
        """Return all bytes while preserving the current stream position."""
        pos = self.stream.tell()
        try:
            self.stream.seek(0)
            return self.stream.read()
        finally:
            self.stream.seek(pos)

    def to_json(self) -> Any:
        return loads(self.to_bytes().decode("utf-8"))

    def to_str(self, encoding: str = "utf-8") -> str:
        return self.to_bytes().decode(encoding)


class S3FileRetriever:
    """S3 adapter for selecting and downloading the latest matching object.

    Preferred production usage is dependency injection of an S3 client or
    boto3's standard credential provider chain. Explicit access keys remain
    supported for backward compatibility but should not be required in code.
    """

    def __init__(
        self,
        bucket_name: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: Optional[str] = None,
        *,
        aws_session_token: Optional[str] = None,
        profile_name: Optional[str] = None,
        s3_client: Optional[S3ClientProtocol] = None,
        validate_bucket: bool = False,
    ):
        if not isinstance(bucket_name, str) or not bucket_name.strip():
            raise ValueError("bucket_name must be a non-empty string.")

        if s3_client is not None and any(
            value is not None
            for value in (
                aws_access_key_id,
                aws_secret_access_key,
                aws_session_token,
                profile_name,
                region_name,
            )
        ):
            raise ValueError(
                "Provide either s3_client or boto3 client configuration, not both."
            )

        self.bucket_name = bucket_name.strip()

        if s3_client is not None:
            self.s3_client = s3_client
            return

        try:
            session = (
                boto3.Session(profile_name=profile_name, region_name=region_name)
                if profile_name
                else boto3.Session(region_name=region_name)
            )

            client_kwargs = {}
            if aws_access_key_id is not None:
                client_kwargs["aws_access_key_id"] = aws_access_key_id
            if aws_secret_access_key is not None:
                client_kwargs["aws_secret_access_key"] = aws_secret_access_key
            if aws_session_token is not None:
                client_kwargs["aws_session_token"] = aws_session_token

            self.s3_client = session.client("s3", **client_kwargs)

            if validate_bucket:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
        except (ClientError, BotoCoreError) as exc:
            raise ValueError(
                f"Unable to initialize S3 access for bucket '{self.bucket_name}'."
            ) from exc

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

    def _iter_objects(self, prefix: Optional[str]) -> Iterable[dict[str, Any]]:
        paginator = self.s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=self.bucket_name,
            Prefix=prefix or "",
        ):
            yield from page.get("Contents", [])

    def _pick_latest_object(
        self,
        objects: Iterable[dict[str, Any]],
        extension: str,
        prefer_name_date: bool,
        date_regex: str,
        date_format: str,
    ) -> Optional[dict[str, Any]]:
        extension = self._normalize_extension(extension)
        best_obj = None
        best_key = None

        for obj in objects:
            name = obj.get("Key")
            if not isinstance(name, str) or not name.lower().endswith(extension):
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

            last_modified = self._to_utc_naive(obj.get("LastModified"))

            if parsed_date is not None:
                # Preserve the original filename-date priority semantics.
                key = (
                    1,
                    parsed_date,
                    last_modified or datetime.min,
                    name,
                )
            else:
                key = (
                    0,
                    last_modified or datetime.min,
                    name,
                )

            if best_key is None or key > best_key:
                best_key = key
                best_obj = obj

        return best_obj

    def get_latest_file_stream(
        self,
        prefix: Optional[str] = None,
        extension: str = ".csv",
        prefer_name_date: bool = True,
        date_regex: str = r"(\d{8})",
        date_format: str = "%Y%m%d",
    ) -> BlobStream:
        extension = self._normalize_extension(extension)

        latest = self._pick_latest_object(
            objects=self._iter_objects(prefix),
            extension=extension,
            prefer_name_date=prefer_name_date,
            date_regex=date_regex,
            date_format=date_format,
        )

        if latest is None:
            raise FileNotFoundError(
                f"No matching '*{extension}' objects found under prefix='{prefix or ''}'"
            )

        key = latest["Key"]
        response = self.s3_client.get_object(
            Bucket=self.bucket_name,
            Key=key,
        )

        body = response["Body"]
        try:
            content = body.read()
        finally:
            close = getattr(body, "close", None)
            if callable(close):
                close()

        return BlobStream(
            name=key,
            size=response.get("ContentLength", latest.get("Size", len(content))),
            content_type=response.get("ContentType"),
            last_modified=response.get(
                "LastModified", latest.get("LastModified")
            ),
            etag=response.get("ETag", latest.get("ETag")),
            stream=io.BytesIO(content),
        )

    def get_object(self, file_name: str) -> BlobStream:
        if not isinstance(file_name, str) or not file_name.strip():
            raise ValueError("file_name must be a non-empty string.")

        response = self.s3_client.get_object(
            Bucket=self.bucket_name,
            Key=file_name,
        )

        body = response["Body"]
        try:
            content = body.read()
        finally:
            close = getattr(body, "close", None)
            if callable(close):
                close()

        return BlobStream(
            name=file_name,
            size=response.get("ContentLength", len(content)),
            content_type=response.get("ContentType"),
            last_modified=response.get("LastModified"),
            etag=response.get("ETag"),
            stream=io.BytesIO(content),
        )

    def download_to_file(
        self,
        blob_stream: BlobStream,
        destination_path: str,
    ) -> str:
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

        logger.info("Saved S3 object '%s' to '%s'", blob_stream.name, destination)
        return destination

    def get_and_save_latest(
        self,
        local_directory: str,
        prefix: Optional[str] = None,
        extension: str = ".pdf",
        prefer_name_date: bool = True,
        date_regex: str = r"(\d{8})",
        date_format: str = "%Y%m%d",
    ) -> str:
        if not isinstance(local_directory, str) or not local_directory.strip():
            raise ValueError("local_directory must be a non-empty path.")

        blob_stream = self.get_latest_file_stream(
            prefix=prefix,
            extension=extension,
            prefer_name_date=prefer_name_date,
            date_regex=date_regex,
            date_format=date_format,
        )

        filename = os.path.basename(blob_stream.name)
        if not filename:
            raise ValueError(
                f"S3 object key '{blob_stream.name}' has no filename component."
            )

        destination = os.path.join(local_directory, filename)
        return self.download_to_file(blob_stream, destination)
