"""Atomic same-directory output helpers with explicit overwrite policy."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
import json
from pathlib import Path
from typing import Any

from stem_crop_tool.core.exceptions import ExportWriteError, OutputExistsError


def ensure_paths_available(
    paths: tuple[Path, ...],
    *,
    overwrite: bool,
) -> None:
    """Fail before export when any target conflicts with policy."""

    normalized = tuple(Path(path) for path in paths)
    if len(set(normalized)) != len(normalized):
        raise ExportWriteError("export targets contain duplicate paths")
    for path in normalized:
        if path.exists() and path.is_dir():
            raise ExportWriteError(f"output path is a directory: {path}")
        if path.exists() and not overwrite:
            raise OutputExistsError(f"output already exists: {path}")


def _sync_file(path: Path) -> None:
    # Windows requires a writable descriptor for FlushFileBuffers/fsync.
    with path.open("r+b") as stream:
        os.fsync(stream.fileno())


def _commit_without_replacement(temporary: Path, destination: Path) -> None:
    try:
        if os.name == "nt":
            os.rename(temporary, destination)
        else:
            os.link(temporary, destination)
            temporary.unlink()
    except FileExistsError as exc:
        raise OutputExistsError(f"output already exists: {destination}") from exc
    except OSError as exc:
        raise ExportWriteError(
            f"could not commit output '{destination.name}': {exc}"
        ) from exc


@contextmanager
def atomic_output_path(
    destination: str | Path,
    *,
    overwrite: bool,
) -> Iterator[Path]:
    """Yield a temporary path and atomically commit it on successful exit."""

    destination = Path(destination)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ExportWriteError(
            f"could not create output directory '{destination.parent}': {exc}"
        ) from exc

    ensure_paths_available((destination,), overwrite=overwrite)
    try:
        descriptor, raw_temporary = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
    except OSError as exc:
        raise ExportWriteError(
            f"could not create temporary output for '{destination.name}': {exc}"
        ) from exc
    os.close(descriptor)
    temporary = Path(raw_temporary)
    try:
        yield temporary
        if not temporary.is_file():
            raise ExportWriteError(
                f"export writer did not create '{destination.name}'"
            )
        try:
            _sync_file(temporary)
        except OSError as exc:
            raise ExportWriteError(
                f"could not flush output '{destination.name}': {exc}"
            ) from exc
        if overwrite:
            try:
                os.replace(temporary, destination)
            except OSError as exc:
                raise ExportWriteError(
                    f"could not replace output '{destination.name}': {exc}"
                ) from exc
        else:
            _commit_without_replacement(temporary, destination)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def write_json_atomic(
    destination: str | Path,
    payload: Mapping[str, Any],
    *,
    overwrite: bool,
) -> None:
    """Write deterministic UTF-8 JSON through the atomic path helper."""

    with atomic_output_path(destination, overwrite=overwrite) as temporary:
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                json.dump(
                    payload,
                    stream,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise ExportWriteError(
                f"could not write metadata '{Path(destination).name}': {exc}"
            ) from exc
