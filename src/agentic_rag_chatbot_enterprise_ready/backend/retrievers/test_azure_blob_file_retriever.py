from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from azure_blob_file_retriever_upgraded import AzureBlobFileRetriever, BlobStream


def make_blob(name, last_modified=None):
    return SimpleNamespace(
        name=name,
        last_modified=last_modified,
    )


class FakeDownloader:
    def __init__(self, content):
        self.content = content

    def readall(self):
        return self.content


class FakeBlobClient:
    def __init__(
        self,
        blob_name,
        content=b"data",
        size=None,
        content_type="text/plain",
        last_modified=None,
        etag='"etag"',
    ):
        self.blob_name = blob_name
        self._content = content
        self._props = SimpleNamespace(
            size=len(content) if size is None else size,
            content_settings=SimpleNamespace(content_type=content_type),
            last_modified=last_modified,
            etag=etag,
        )
        self.download_calls = []

    def download_blob(self, **kwargs):
        self.download_calls.append(kwargs)
        return FakeDownloader(self._content)

    def get_blob_properties(self):
        return self._props


class FakeContainerClient:
    def __init__(self, blobs=None, clients=None):
        self.blobs = list(blobs or [])
        self.clients = clients or {}
        self.list_calls = []

    def list_blobs(self, name_starts_with=""):
        self.list_calls.append(name_starts_with)
        return iter(
            b for b in self.blobs
            if b.name.startswith(name_starts_with)
        )

    def get_blob_client(self, blob_name):
        return self.clients[blob_name]


def retriever(container):
    return AzureBlobFileRetriever(container_client_service=container)


def test_blob_stream_to_bytes_preserves_position():
    stream = BlobStream("a.txt", 3, "text/plain", None, None, BytesIO(b"abc"))
    stream.stream.seek(1)

    assert stream.to_bytes() == b"abc"
    assert stream.stream.tell() == 1


def test_blob_stream_helpers():
    stream = BlobStream(
        "data.json", 10, "application/json", None, None,
        BytesIO(b'{"ok": true}')
    )

    assert stream.to_str() == '{"ok": true}'
    assert stream.to_json() == {"ok": True}


def test_timezone_normalization():
    aware = datetime(2026, 1, 1, 5, tzinfo=timezone.utc)
    assert AzureBlobFileRetriever._to_utc_naive(aware) == datetime(2026, 1, 1, 5)
    assert AzureBlobFileRetriever._to_utc_naive(None) is None


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("report_20260808.csv", datetime(2026, 8, 8)),
        ("report.csv", None),
        ("report_20261399.csv", None),
        ("report_20260808.csv", datetime(2026, 8, 8)),
    ],
)
def test_parse_date_from_name(name, expected):
    assert AzureBlobFileRetriever._parse_date_from_name(
        name, r"(\d{8})", "%Y%m%d"
    ) == expected


def test_pick_latest_prefers_latest_filename_date():
    blobs = [
        make_blob("report_20260801.csv", datetime(2026, 8, 8, tzinfo=timezone.utc)),
        make_blob("report_20260808.csv", datetime(2026, 8, 1, tzinfo=timezone.utc)),
        make_blob("ignore.txt", datetime(2030, 1, 1, tzinfo=timezone.utc)),
    ]

    result = retriever(FakeContainerClient())._pick_latest_blob(
        blobs,
        ".csv",
        True,
        r"(\d{8})",
        "%Y%m%d",
    )

    assert result.name == "report_20260808.csv"


def test_pick_latest_falls_back_to_last_modified_without_dates():
    blobs = [
        make_blob("a.csv", datetime(2026, 8, 1, tzinfo=timezone.utc)),
        make_blob("b.csv", datetime(2026, 8, 8, tzinfo=timezone.utc)),
    ]

    result = retriever(FakeContainerClient())._pick_latest_blob(
        blobs,
        ".csv",
        True,
        r"(\d{8})",
        "%Y%m%d",
    )

    assert result.name == "b.csv"


def test_extension_is_case_insensitive_and_dot_is_optional():
    blobs = [
        make_blob("old.CSV", datetime(2026, 8, 1)),
        make_blob("new.CsV", datetime(2026, 8, 2)),
    ]

    result = retriever(FakeContainerClient())._pick_latest_blob( blobs, "csv", False, r"(\d{8})", "%Y%m%d"
    )

    assert result.name == "new.CsV"


def test_no_matching_blob_raises_file_not_found():
    container = FakeContainerClient([make_blob("document.txt", datetime(2026, 8, 8))])

    with pytest.raises(FileNotFoundError):
        retriever(container).get_latest_file_stream(extension=".csv")


def test_latest_download_returns_metadata_and_uses_concurrency():
    blobs = [
        make_blob("report_20260808.csv", datetime(2026, 8, 8, tzinfo=timezone.utc))
    ]
    client = FakeBlobClient(
        "report_20260808.csv",
        content=b"a,b\n1,2\n",
        content_type="text/csv",
        last_modified=datetime(2026, 8, 8, tzinfo=timezone.utc),
    )
    container = FakeContainerClient(blobs, {"report_20260808.csv": client})

    result = retriever(container).get_latest_file_stream(
        prefix="report",
        extension="csv",
        max_concurrency=8,
    )

    assert result.name == "report_20260808.csv"
    assert result.size == len(b"a,b\n1,2\n")
    assert result.content_type == "text/csv"
    assert result.to_bytes() == b"a,b\n1,2\n"
    assert client.download_calls == [{"max_concurrency": 8}]
    assert container.list_calls == ["report"]


def test_get_blob_validates_name_and_returns_content():
    client = FakeBlobClient("file.txt", content=b"hello")
    container = FakeContainerClient(clients={"file.txt": client})

    result = retriever(container).get_blob("file.txt")

    assert result.name == "file.txt"
    assert result.to_str() == "hello"

    with pytest.raises(ValueError):
        retriever(container).get_blob("")


def test_constructor_does_not_make_network_call_for_injected_client():
    class Client:
        def list_blobs(self, name_starts_with=""):
            return iter(())

        def get_blob_client(self, blob_name):
            raise AssertionError("not expected")

        def exists(self):
            raise AssertionError("constructor must not call exists()")

    instance = AzureBlobFileRetriever(container_client_service=Client())
    assert instance.container_client is not None


def test_constructor_requires_valid_configuration():
    with pytest.raises(ValueError):
        AzureBlobFileRetriever()


def test_invalid_download_concurrency():
    container = FakeContainerClient()
    instance = retriever(container)

    with pytest.raises(ValueError):
        instance.get_latest_file_stream(max_concurrency=0)


def test_download_to_file_supports_filename_without_directory(tmp_path, monkeypatch):
    stream = BlobStream("a.txt", 3, "text/plain", None, None, BytesIO(b"abc"))
    instance = retriever(FakeContainerClient())

    monkeypatch.chdir(tmp_path)
    destination = instance.download_to_file(stream, "a.txt")

    assert Path(destination).read_bytes() == b"abc"


def test_download_to_file_creates_nested_directory(tmp_path):
    stream = BlobStream("a.txt", 3, "text/plain", None, None, BytesIO(b"abc"))
    instance = retriever(FakeContainerClient())

    destination = instance.download_to_file(
        stream, str(tmp_path / "nested" / "a.txt")
    )

    assert Path(destination).read_bytes() == b"abc"


def test_get_and_save_latest_forwards_selection_options(tmp_path):
    blobs = [
        make_blob("reports/report_20260808.pdf", datetime(2026, 8, 8))
    ]
    client = FakeBlobClient(
        "reports/report_20260808.pdf",
        content=b"%PDF",
        content_type="application/pdf",
    )
    container = FakeContainerClient(blobs, {"reports/report_20260808.pdf": client})

    destination = retriever(container).get_and_save_latest(
        local_directory=str(tmp_path),
        prefix="reports/",
        extension=".pdf",
    )

    assert Path(destination).name == "report_20260808.pdf"
    assert Path(destination).read_bytes() == b"%PDF"


def test_pick_latest_is_deterministic_for_equal_timestamps():
    timestamp = datetime(2026, 8, 8)
    blobs = [
        make_blob("b.csv", timestamp),
        make_blob("a.csv", timestamp),
    ]

    result = retriever(FakeContainerClient())._pick_latest_blob( blobs, ".csv", False, r"(\d{8})", "%Y%m%d"
    )

    assert result.name == "b.csv"


def test_invalid_extension():
    with pytest.raises(ValueError):
        AzureBlobFileRetriever._normalize_extension("")
