"""Qt-independent slice selection, naming, progress, and cancellation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event

from stem_crop_tool.core.exceptions import InvalidSliceIndexError
from stem_crop_tool.core.models import ExportFormat, ImageMetadata


def _validate_slice_count(slice_count: int) -> int:
    if isinstance(slice_count, bool) or not isinstance(slice_count, int):
        raise TypeError("slice_count must be an integer")
    if slice_count < 1:
        raise ValueError("slice_count must be at least 1")
    return slice_count


def _validate_index(index: int, slice_count: int, name: str) -> int:
    if isinstance(index, bool) or not isinstance(index, int):
        raise TypeError(f"{name} must be an integer")
    if index < 0 or index >= slice_count:
        raise InvalidSliceIndexError(
            f"{name} {index} is outside 0..{slice_count - 1}"
        )
    return index


def current_slice_indices(index: int, slice_count: int) -> tuple[int, ...]:
    """Return a validated one-element current-slice selection."""

    slice_count = _validate_slice_count(slice_count)
    return (_validate_index(index, slice_count, "slice index"),)


def inclusive_slice_range(
    start: int,
    stop: int,
    slice_count: int,
) -> tuple[int, ...]:
    """Return every slice from ``start`` through ``stop`` inclusively."""

    slice_count = _validate_slice_count(slice_count)
    start = _validate_index(start, slice_count, "range start")
    stop = _validate_index(stop, slice_count, "range stop")
    if start > stop:
        raise ValueError("range start must not exceed range stop")
    return tuple(range(start, stop + 1))


def all_slice_indices(slice_count: int) -> tuple[int, ...]:
    """Return every source slice in deterministic ascending order."""

    return tuple(range(_validate_slice_count(slice_count)))


def suggested_single_filename(
    metadata: ImageMetadata,
    output_format: ExportFormat,
) -> str:
    """Return the default single-crop filename."""

    suffix = ExportFormat(output_format).value
    return f"{Path(metadata.source_name).stem}_crop.{suffix}"


def batch_item_filename(
    metadata: ImageMetadata,
    slice_index: int,
    output_format: ExportFormat,
) -> str:
    """Return a batch filename whose lexical order matches slice order."""

    slice_index = _validate_index(
        slice_index,
        metadata.slice_count,
        "slice index",
    )
    padding = max(4, len(str(metadata.slice_count - 1)))
    suffix = ExportFormat(output_format).value
    return (
        f"{Path(metadata.source_name).stem}_z{slice_index:0{padding}d}_crop."
        f"{suffix}"
    )


class CancellationToken:
    """Thread-safe cooperative cancellation shared by core and UI workers."""

    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()


@dataclass(frozen=True, slots=True)
class ExportProgress:
    """Progress emitted only after one output has been committed."""

    completed: int
    total: int
    slice_index: int
    output_path: Path

    @property
    def fraction(self) -> float:
        return self.completed / self.total
