from datetime import datetime, timezone

from backend.UploadFileWrapper import UploadedFileWrapper


def test_wrapper_accepts_path_and_keeps_content_lazy(tmp_path):
    path = tmp_path / "report.pdf"
    path.write_bytes(b"hello")

    wrapper = UploadedFileWrapper(path=path, name="report.pdf", content=None, createdAt=None)

    assert wrapper.name == "report.pdf"
    assert wrapper.path == path
    assert wrapper.path_str == str(path)
    assert wrapper.exists() is True
    assert wrapper.read() == b"hello"
    assert wrapper.content is None


def test_wrapper_supports_bytes_like_content_without_forcing_disk_read(tmp_path):
    path = tmp_path / "placeholder.txt"
    wrapper = UploadedFileWrapper(
        path=path,
        name="file.txt",
        content=bytearray(b"hello"),
        createdAt=datetime.now(timezone.utc),
    )

    assert wrapper.read() == b"hello"
    assert wrapper.to_dict()["content"] == bytearray(b"hello")
    assert wrapper.to_dict(include_content=False)["path"] == str(path)


def test_wrapper_round_trip_does_not_log_or_copy_file_contents_by_repr(tmp_path):
    path = tmp_path / "secret.txt"
    path.write_bytes(b"secret")
    wrapper = UploadedFileWrapper(path, "secret.txt", None, datetime.now(timezone.utc))

    restored = UploadedFileWrapper.from_dict(wrapper.to_dict(include_content=False))

    assert restored.path == path
    assert restored.name == wrapper.name
    assert "secret" not in repr(restored)


def test_wrapper_rejects_invalid_arguments(tmp_path):
    try:
        UploadedFileWrapper(tmp_path / "x", "", None, None)
    except ValueError:
        pass
    else:
        raise AssertionError("empty name should be rejected")

    try:
        UploadedFileWrapper(tmp_path / "x", "x.txt", "not-bytes", None)
    except TypeError:
        pass
    else:
        raise AssertionError("non-bytes content should be rejected")
