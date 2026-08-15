from pathlib import Path
import importlib.util

import pytest


MODULE_PATH = Path("/mnt/data/UploadFileWrapper_upgraded.py")

spec = importlib.util.spec_from_file_location(
    "upload_file_wrapper_under_test",
    MODULE_PATH,
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

UploadedFileWrapper = module.UploadedFileWrapper


def test_constructor_preserves_original_public_contract(tmp_path):
    path = tmp_path / "document.pdf"
    path.write_bytes(b"hello")

    wrapper = UploadedFileWrapper(
        path,
        "document.pdf",
        b"hello",
        "2026-08-08T10:00:00Z",
    )

    assert wrapper.name == "document.pdf"
    assert wrapper.path == path
    assert wrapper.content == b"hello"
    assert wrapper.createdAt == "2026-08-08T10:00:00Z"


def test_pathlike_input_is_supported(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("hello")

    wrapper = UploadedFileWrapper(
        path,
        "file.txt",
        None,
        None,
    )

    assert wrapper.path == path


def test_read_returns_current_disk_content(tmp_path):
    path = tmp_path / "file.txt"
    path.write_bytes(b"first")

    wrapper = UploadedFileWrapper(
        path,
        "file.txt",
        b"old-content",
        None,
    )

    assert wrapper.read() == b"first"

    path.write_bytes(b"second")
    assert wrapper.read() == b"second"


def test_read_does_not_depend_on_content_attribute(tmp_path):
    path = tmp_path / "file.txt"
    path.write_bytes(b"disk-content")

    wrapper = UploadedFileWrapper(
        path,
        "file.txt",
        None,
        None,
    )

    assert wrapper.read() == b"disk-content"


def test_read_missing_file_propagates_filesystem_error(tmp_path):
    path = tmp_path / "missing.txt"

    wrapper = UploadedFileWrapper(
        path,
        "missing.txt",
        None,
        None,
    )

    with pytest.raises(FileNotFoundError):
        wrapper.read()


def test_exists_reports_file_state(tmp_path):
    path = tmp_path / "file.txt"
    wrapper = UploadedFileWrapper(path, "file.txt", None, None)

    assert wrapper.exists() is False

    path.write_bytes(b"x")
    assert wrapper.exists() is True


def test_to_dict_is_backward_compatible(tmp_path):
    path = tmp_path / "file.txt"
    content = b"hello"
    created = "2026-08-08T10:00:00Z"

    wrapper = UploadedFileWrapper(
        path,
        "file.txt",
        content,
        created,
    )

    payload = wrapper.to_dict()

    assert payload == {
        "name": "file.txt",
        "path": str(path),
        "content": content,
        "createdAt": created,
    }


def test_to_dict_can_omit_large_content(tmp_path):
    path = tmp_path / "large.bin"
    wrapper = UploadedFileWrapper(
        path,
        "large.bin",
        b"large-content",
        None,
    )

    payload = wrapper.to_dict(include_content=False)

    assert payload == {
        "name": "large.bin",
        "path": str(path),
        "createdAt": None,
    }
    assert "content" not in payload


def test_from_dict_round_trip(tmp_path):
    path = tmp_path / "file.txt"

    original = UploadedFileWrapper(
        path,
        "file.txt",
        b"hello",
        "created",
    )

    restored = UploadedFileWrapper.from_dict(original.to_dict())

    assert restored.name == original.name
    assert restored.path == original.path
    assert restored.content == original.content
    assert restored.createdAt == original.createdAt


def test_from_dict_supports_metadata_only_payload(tmp_path):
    path = tmp_path / "file.txt"

    restored = UploadedFileWrapper.from_dict(
        {
            "name": "file.txt",
            "path": str(path),
            "createdAt": "created",
        }
    )

    assert restored.content is None


def test_from_dict_rejects_non_dict():
    with pytest.raises(TypeError):
        UploadedFileWrapper.from_dict([])


def test_from_dict_reports_missing_fields(tmp_path):
    with pytest.raises(ValueError, match="Missing required fields"):
        UploadedFileWrapper.from_dict(
            {
                "name": "file.txt",
                "path": str(tmp_path / "file.txt"),
            }
        )


@pytest.mark.parametrize(
    "name",
    ["", "   ", None, 123],
)
def test_name_validation(name, tmp_path):
    with pytest.raises(ValueError):
        UploadedFileWrapper(
            tmp_path / "file.txt",
            name,
            None,
            None,
        )


@pytest.mark.parametrize(
    "path",
    [None, 123, object()],
)
def test_path_validation(path):
    with pytest.raises(TypeError):
        UploadedFileWrapper(
            path,
            "file.txt",
            None,
            None,
        )


@pytest.mark.parametrize(
    "content",
    ["text", 123, object()],
)
def test_content_validation(content, tmp_path):
    with pytest.raises(TypeError):
        UploadedFileWrapper(
            tmp_path / "file.txt",
            "file.txt",
            content,
            None,
        )


def test_memoryview_content_is_accepted(tmp_path):
    wrapper = UploadedFileWrapper(
        tmp_path / "file.txt",
        "file.txt",
        memoryview(b"hello"),
        None,
    )

    assert isinstance(wrapper.content, memoryview)


def test_created_at_alias_reads_original_field(tmp_path):
    wrapper = UploadedFileWrapper(
        tmp_path / "file.txt",
        "file.txt",
        None,
        "original",
    )

    assert wrapper.created_at == "original"


def test_created_at_alias_updates_original_field(tmp_path):
    wrapper = UploadedFileWrapper(
        tmp_path / "file.txt",
        "file.txt",
        None,
        "original",
    )

    wrapper.created_at = "updated"

    assert wrapper.createdAt == "updated"


def test_repr_does_not_include_content(tmp_path):
    wrapper = UploadedFileWrapper(
        tmp_path / "file.txt",
        "file.txt",
        b"SECRET-CONTENT",
        None,
    )

    representation = repr(wrapper)

    assert "UploadedFileWrapper" in representation
    assert "file.txt" in representation
    assert "SECRET-CONTENT" not in representation


def test_slots_prevent_accidental_dynamic_attributes(tmp_path):
    wrapper = UploadedFileWrapper(
        tmp_path / "file.txt",
        "file.txt",
        None,
        None,
    )

    with pytest.raises(AttributeError):
        wrapper.unexpected_attribute = "value"


def test_to_dict_does_not_change_original_object(tmp_path):
    wrapper = UploadedFileWrapper(
        tmp_path / "file.txt",
        "file.txt",
        bytearray(b"hello"),
        None,
    )

    payload = wrapper.to_dict()

    assert payload["name"] == wrapper.name
    assert payload["path"] == str(wrapper.path)
    assert payload["content"] is wrapper.content


def test_source_keeps_backward_compatible_field_names():
    source = MODULE_PATH.read_text()

    assert "self.createdAt" in source
    assert '"createdAt"' in source
    assert "def read(self)" in source
    assert "def to_dict" in source


def test_source_uses_context_managed_file_open():
    source = MODULE_PATH.read_text()

    assert "with self.path.open(\"rb\") as handle:" in source


def test_source_has_no_plain_print_statements():
    source = MODULE_PATH.read_text()

    assert "\nprint(" not in source


def test_source_repr_avoids_content():
    source = MODULE_PATH.read_text()

    assert "def __repr__" in source
    assert "content" not in source.split("def __repr__", 1)[1].split("\n", 8)[0]
