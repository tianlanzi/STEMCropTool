"""Shared source protocol and source-lifetime owner."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol, TypeVar, runtime_checkable

import numpy as np

from stem_crop_tool.core.exceptions import (
    InvalidSliceIndexError,
    SourceClosedError,
    UnsupportedArrayShapeError,
    UnsupportedDTypeError,
)
from stem_crop_tool.core.models import ImageMetadata


@runtime_checkable
class ImageSource(Protocol):
    """Minimal interface consumed by display and export code."""

    shape: tuple[int, ...]
    dtype: np.dtype
    ndim: int
    metadata: ImageMetadata
    slice_count: int

    def get_slice(self, index: int = 0) -> np.ndarray:
        """Return one read-only two-dimensional source slice."""

    def close(self) -> None:
        """Release files and mappings owned by the source."""


def validate_image_array(shape: tuple[int, ...], dtype: np.dtype) -> None:
    """Validate the common dimensionality and dtype input contract."""

    if len(shape) not in (2, 3) or any(int(size) < 1 for size in shape):
        raise UnsupportedArrayShapeError(
            "supported image shapes are positive 2D (Y, X) or 3D (Z, Y, X)"
        )

    dtype = np.dtype(dtype)
    if np.issubdtype(dtype, np.complexfloating):
        raise UnsupportedDTypeError("complex image arrays are unsupported")
    if not (np.issubdtype(dtype, np.number) or np.issubdtype(dtype, np.bool_)):
        raise UnsupportedDTypeError(f"non-numeric image dtype is unsupported: {dtype}")


def validate_slice_index(index: int, slice_count: int) -> int:
    """Return a validated Python slice index."""

    if isinstance(index, bool) or not isinstance(index, (int, np.integer)):
        raise TypeError("slice index must be an integer")
    converted = int(index)
    if converted < 0 or converted >= slice_count:
        raise InvalidSliceIndexError(
            f"slice index {converted} is outside 0..{slice_count - 1}"
        )
    return converted


SourceT = TypeVar("SourceT", bound=ImageSource)


class ImageDocument:
    """Own exactly one source and replace it without losing a valid document."""

    def __init__(self) -> None:
        self._source: ImageSource | None = None

    @property
    def source(self) -> ImageSource | None:
        return self._source

    def require_source(self) -> ImageSource:
        if self._source is None:
            raise SourceClosedError("no image source is open")
        return self._source

    def replace_source(self, source: SourceT) -> SourceT:
        if source is self._source:
            return source
        previous = self._source
        self._source = source
        if previous is not None:
            previous.close()
        return source

    def open_with(
        self,
        opener: Callable[..., SourceT],
        path: str | Path,
        **kwargs: object,
    ) -> SourceT:
        """Open first, then swap so a failed open preserves the current source."""

        new_source = opener(path, **kwargs)
        return self.replace_source(new_source)

    def close(self) -> None:
        previous = self._source
        self._source = None
        if previous is not None:
            previous.close()

    def __enter__(self) -> ImageDocument:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
