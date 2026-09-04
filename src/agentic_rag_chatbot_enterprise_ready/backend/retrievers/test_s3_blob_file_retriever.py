from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.retrievers.s3_blob_file_retriever import BlobStream, S3FileRetriever


class FakeBody:
    def __init__(self, content): self.content = content; self.closed = False
    def read(self): return self.content
    def close(self): self.closed = True

class FakePaginator:
    def __init__(self, pages): self.pages = pages; self.calls = []
    def paginate(self, **kwargs): self.calls.append(kwargs); yield from self.pages

class FakeS3Client:
    def __init__(self, pages=None, responses=None): self.paginator = FakePaginator(pages or []); self.responses = responses or {}; self.get_object_calls = []
    def get_paginator(self, operation_name): assert operation_name == "list_objects_v2"; return self.paginator
    def get_object(self, **kwargs): self.get_object_calls.append(kwargs); return self.responses[kwargs["Key"]]

def retriever(client): return S3FileRetriever("test-bucket", s3_client=client)
def obj(key, last_modified=None, size=1): return {"Key": key, "LastModified": last_modified, "Size": size}
def response(content=b"abc", content_type="text/plain", last_modified=None, etag='"e"'): return {"Body": FakeBody(content), "ContentLength": len(content), "ContentType": content_type, "LastModified": last_modified, "ETag": etag}

def test_blob_stream_to_bytes_preserves_position():
    stream = BlobStream("a.txt", 3, "text/plain", None, None, BytesIO(b"abc")); stream.stream.seek(1); assert stream.to_bytes() == b"abc"; assert stream.stream.tell() == 1

def test_blob_stream_helpers():
    stream = BlobStream("data.json", 12, "application/json", None, None, BytesIO(b'{"ok": true}')); assert stream.to_str() == '{"ok": true}'; assert stream.to_json() == {"ok": True}

def test_timezone_normalization():
    aware = datetime(2026, 1, 1, 5, tzinfo=timezone.utc); assert S3FileRetriever._to_utc_naive(aware) == datetime(2026, 1, 1, 5); assert S3FileRetriever._to_utc_naive(None) is None

@pytest.mark.parametrize(("name", "expected"), [("report_20260808.csv", datetime(2026, 8, 8)), ("report.csv", None), ("report_20261399.csv", None)])
def test_parse_date_from_name(name, expected): assert S3FileRetriever._parse_date_from_name(name, r"(\d{8})", "%Y%m%d") == expected

def test_extension_normalization():
    assert S3FileRetriever._normalize_extension("csv") == ".csv"; assert S3FileRetriever._normalize_extension(".CSV") == ".csv"
    with pytest.raises(ValueError): S3FileRetriever._normalize_extension("")

def test_pick_latest_prefers_filename_date():
    timestamp = datetime(2026, 8, 8, tzinfo=timezone.utc); objects = [obj("report_20260801.csv", timestamp), obj("report_20260808.csv", datetime(2026, 8, 1, tzinfo=timezone.utc)), obj("ignore.txt", timestamp)]; result = retriever(FakeS3Client())._pick_latest_object(objects, ".csv", True, r"(\d{8})", "%Y%m%d"); assert result["Key"] == "report_20260808.csv"

def test_pick_latest_falls_back_to_last_modified():
    objects = [obj("a.csv", datetime(2026, 8, 1, tzinfo=timezone.utc)), obj("b.csv", datetime(2026, 8, 8, tzinfo=timezone.utc))]; assert retriever(FakeS3Client())._pick_latest_object(objects, ".csv", True, r"(\d{8})", "%Y%m%d")["Key"] == "b.csv"

def test_pick_latest_is_deterministic_for_equal_timestamps():
    timestamp = datetime(2026, 8, 8); objects = [obj("a.csv", timestamp), obj("b.csv", timestamp)]; assert retriever(FakeS3Client())._pick_latest_object(objects, ".csv", False, r"(\d{8})", "%Y%m%d")["Key"] == "b.csv"

def test_iter_objects_uses_s3_paginator_and_prefix():
    client = FakeS3Client(pages=[{"Contents": [obj("reports/a.csv")]}, {"Contents": [obj("reports/b.csv")]}, {}]); result = list(retriever(client)._iter_objects("reports/")); assert [x["Key"] for x in result] == ["reports/a.csv", "reports/b.csv"]; assert client.paginator.calls == [{"Bucket": "test-bucket", "Prefix": "reports/"}]

def test_latest_download_returns_metadata_and_closes_body():
    key = "reports/report_20260808.csv"; latest = obj(key, datetime(2026, 8, 8, tzinfo=timezone.utc), size=5); body = FakeBody(b"a,b\n1,2\n"); client = FakeS3Client(pages=[{"Contents": [latest]}], responses={key: {"Body": body, "ContentLength": 8, "ContentType": "text/csv", "LastModified": latest["LastModified"], "ETag": '"abc"'}}); result = retriever(client).get_latest_file_stream(prefix="reports/", extension="csv"); assert result.name == key; assert result.size == 8; assert result.content_type == "text/csv"; assert result.etag == '"abc"'; assert result.to_bytes() == b"a,b\n1,2\n"; assert body.closed is True

def test_missing_matching_object_raises_file_not_found():
    with pytest.raises(FileNotFoundError): retriever(FakeS3Client(pages=[{"Contents": [obj("document.txt", datetime(2026, 8, 8))]}])).get_latest_file_stream(extension=".csv")

def test_empty_listing_also_raises_file_not_found():
    with pytest.raises(FileNotFoundError): retriever(FakeS3Client(pages=[{}])).get_latest_file_stream(extension=".csv")

def test_get_object_validates_name_and_closes_body():
    body = FakeBody(b"hello"); client = FakeS3Client(responses={"file.txt": {"Body": body, "ContentLength": 5, "ContentType": "text/plain"}}); result = retriever(client).get_object("file.txt"); assert result.name == "file.txt"; assert result.to_str() == "hello"; assert body.closed is True
    with pytest.raises(ValueError): retriever(client).get_object("")

def test_constructor_dependency_injection_avoids_network(): assert S3FileRetriever("bucket", s3_client=FakeS3Client()).s3_client is not None

def test_constructor_requires_bucket():
    with pytest.raises(ValueError): S3FileRetriever("")

def test_constructor_rejects_mixed_client_configuration():
    with pytest.raises(ValueError): S3FileRetriever("bucket", aws_access_key_id="key", s3_client=FakeS3Client())

def test_download_to_file_supports_filename_without_directory(tmp_path, monkeypatch):
    stream = BlobStream("a.txt", 3, "text/plain", None, None, BytesIO(b"abc")); monkeypatch.chdir(tmp_path); destination = retriever(FakeS3Client()).download_to_file(stream, "a.txt"); assert Path(destination).read_bytes() == b"abc"

def test_download_to_file_creates_nested_directory(tmp_path):
    stream = BlobStream("a.txt", 3, "text/plain", None, None, BytesIO(b"abc")); destination = retriever(FakeS3Client()).download_to_file(stream, str(tmp_path / "nested" / "a.txt")); assert Path(destination).read_bytes() == b"abc"

def test_get_and_save_latest_forwards_selection_options(tmp_path):
    key = "reports/report_20260808.pdf"; client = FakeS3Client(pages=[{"Contents": [obj(key, datetime(2026, 8, 8))]}], responses={key: response(b"%PDF", "application/pdf")}); destination = retriever(client).get_and_save_latest(str(tmp_path), prefix="reports/", extension=".pdf"); assert Path(destination).name == "report_20260808.pdf"; assert Path(destination).read_bytes() == b"%PDF"

def test_get_and_save_latest_validates_directory():
    with pytest.raises(ValueError): retriever(FakeS3Client()).get_and_save_latest("")
