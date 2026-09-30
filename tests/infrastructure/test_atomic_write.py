import errno
from pathlib import Path

import pytest

import stem_crop_tool.infrastructure.atomic_write as atomic_write
from stem_crop_tool.core.exceptions import ExportWriteError, OutputExistsError
from stem_crop_tool.infrastructure.atomic_write import (
    atomic_output_path,
    write_json_atomic,
)


def _temporary_files(directory: Path) -> list[Path]:
    return list(directory.glob(".*.tmp"))


def test_atomic_output_commits_new_file(tmp_path) -> None:
    destination = tmp_path / "output.bin"

    with atomic_output_path(destination, overwrite=False) as temporary:
        temporary.write_bytes(b"complete")
        assert not destination.exists()

    assert destination.read_bytes() == b"complete"
    assert _temporary_files(tmp_path) == []


def test_atomic_output_failure_removes_partial_temporary_file(tmp_path) -> None:
    destination = tmp_path / "output.bin"

    with pytest.raises(RuntimeError, match="simulated"):
        with atomic_output_path(destination, overwrite=False) as temporary:
            temporary.write_bytes(b"partial")
            raise RuntimeError("simulated failure")

    assert not destination.exists()
    assert _temporary_files(tmp_path) == []


def test_atomic_output_respects_overwrite_policy(tmp_path) -> None:
    destination = tmp_path / "output.bin"
    destination.write_bytes(b"old")

    with pytest.raises(OutputExistsError):
        with atomic_output_path(destination, overwrite=False):
            pass
    assert destination.read_bytes() == b"old"

    with atomic_output_path(destination, overwrite=True) as temporary:
        temporary.write_bytes(b"new")
    assert destination.read_bytes() == b"new"


def test_json_writer_is_utf8_deterministic_and_atomic(tmp_path) -> None:
    destination = tmp_path / "metadata.json"
    write_json_atomic(destination, {"z": 1, "a": "nm"}, overwrite=False)

    assert destination.read_text(encoding="utf-8") == (
        '{\n  "a": "nm",\n  "z": 1\n}\n'
    )


def test_full_disk_flush_error_is_typed_and_removes_temporary_file(
    tmp_path, monkeypatch
) -> None:
    destination = tmp_path / "output.bin"

    def fail_flush(_path: Path) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(atomic_write, "_sync_file", fail_flush)
    with pytest.raises(ExportWriteError, match="could not flush"):
        with atomic_output_path(destination, overwrite=False) as temporary:
            temporary.write_bytes(b"complete")

    assert not destination.exists()
    assert _temporary_files(tmp_path) == []


def test_permission_error_creating_temporary_file_is_user_facing(
    tmp_path, monkeypatch
) -> None:
    destination = tmp_path / "output.bin"

    def deny_temporary(*_args, **_kwargs):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(atomic_write.tempfile, "mkstemp", deny_temporary)
    with pytest.raises(ExportWriteError, match="could not create temporary output"):
        with atomic_output_path(destination, overwrite=False):
            pass

    assert not destination.exists()
    assert _temporary_files(tmp_path) == []


def test_invalid_parent_path_is_reported_as_export_write_error(tmp_path) -> None:
    parent = tmp_path / "not-a-directory"
    parent.write_bytes(b"file")

    with pytest.raises(ExportWriteError, match="could not create output directory"):
        with atomic_output_path(parent / "output.bin", overwrite=False):
            pass


def test_json_disk_error_is_typed_and_removes_temporary_file(
    tmp_path, monkeypatch
) -> None:
    destination = tmp_path / "metadata.json"

    def fail_dump(*_args, **_kwargs) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(atomic_write.json, "dump", fail_dump)
    with pytest.raises(ExportWriteError, match="could not write metadata"):
        write_json_atomic(destination, {"a": 1}, overwrite=False)

    assert not destination.exists()
    assert _temporary_files(tmp_path) == []
