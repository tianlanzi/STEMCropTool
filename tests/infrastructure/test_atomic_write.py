from pathlib import Path

import pytest

from stem_crop_tool.core.exceptions import OutputExistsError
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
