"""Immutable value models shared by the Qt-independent core."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from numbers import Integral, Real
from pathlib import Path

import numpy as np

from stem_crop_tool.core.exceptions import (
    InvalidCropRectError,
    UnsupportedArrayShapeError,
    UnsupportedDTypeError,
)


def _coerce_integer(value: Integral, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{field_name} must be an integer")
    return int(value)


def _coerce_index_tuple(values: tuple[int, ...]) -> tuple[int, ...]:
    result = tuple(
        _coerce_integer(value, "slice index") for value in tuple(values)
    )
    if not result:
        raise ValueError("slice_indices must contain at least one index")
    if any(value < 0 for value in result):
        raise ValueError("slice indices must be non-negative")
    if any(current >= following for current, following in zip(result, result[1:])):
        raise ValueError("slice indices must be strictly increasing")
    return result


def _coerce_pair(
    value: tuple[object, object] | None,
    field_name: str,
) -> tuple[object, object] | None:
    if value is None:
        return None
    result = tuple(value)
    if len(result) != 2:
        raise ValueError(f"{field_name} must contain exactly two values")
    return result


class NormalizationMode(StrEnum):
    """Supported export normalization modes."""

    NONE = "none"
    LOCAL_MINMAX = "local_minmax"


class ExportFormat(StrEnum):
    """Supported initial-release output formats."""

    PNG = "png"
    NPY = "npy"


@dataclass(frozen=True, slots=True)
class CropRect:
    """Integer crop rectangle using top-left origin and half-open bounds."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        for field_name in ("x", "y", "width", "height"):
            object.__setattr__(
                self,
                field_name,
                _coerce_integer(getattr(self, field_name), field_name),
            )
        if self.width < 1 or self.height < 1:
            raise InvalidCropRectError("crop width and height must be at least 1")

    @property
    def x1(self) -> int:
        """Exclusive right boundary."""

        return self.x + self.width

    @property
    def y1(self) -> int:
        """Exclusive bottom boundary."""

        return self.y + self.height

    @property
    def slices(self) -> tuple[slice, slice]:
        """NumPy `(y, x)` slices for this rectangle."""

        return (slice(self.y, self.y1), slice(self.x, self.x1))


@dataclass(frozen=True, slots=True)
class ImageMetadata:
    """Format-neutral metadata for one supported 2D image or 3D stack."""

    source_name: str
    source_format: str
    shape: tuple[int, ...]
    dtype: np.dtype
    dataset_index: int | None = None
    pixel_size_xy: tuple[float, float] | None = None
    pixel_unit_xy: tuple[str, str] | None = None

    def __post_init__(self) -> None:
        if not self.source_name:
            raise ValueError("source_name must not be empty")
        if not self.source_format:
            raise ValueError("source_format must not be empty")
        object.__setattr__(self, "source_format", self.source_format.lower())

        shape = tuple(
            _coerce_integer(value, "shape dimension") for value in tuple(self.shape)
        )
        if len(shape) not in (2, 3) or any(value < 1 for value in shape):
            raise UnsupportedArrayShapeError(
                "supported image shapes are positive 2D (Y, X) or 3D (Z, Y, X)"
            )
        object.__setattr__(self, "shape", shape)

        dtype = np.dtype(self.dtype)
        if np.issubdtype(dtype, np.complexfloating):
            raise UnsupportedDTypeError("complex image arrays are unsupported")
        object.__setattr__(self, "dtype", dtype)

        if self.dataset_index is not None:
            dataset_index = _coerce_integer(self.dataset_index, "dataset_index")
            if dataset_index < 0:
                raise ValueError("dataset_index must be non-negative")
            object.__setattr__(self, "dataset_index", dataset_index)

        pixel_sizes = _coerce_pair(self.pixel_size_xy, "pixel_size_xy")
        if pixel_sizes is not None:
            converted_sizes: list[float] = []
            for value in pixel_sizes:
                if isinstance(value, bool) or not isinstance(value, Real):
                    raise TypeError("pixel sizes must be real numbers")
                converted = float(value)
                if not np.isfinite(converted) or converted <= 0:
                    raise ValueError("pixel sizes must be positive and finite")
                converted_sizes.append(converted)
            object.__setattr__(self, "pixel_size_xy", tuple(converted_sizes))

        pixel_units = _coerce_pair(self.pixel_unit_xy, "pixel_unit_xy")
        if pixel_units is not None:
            converted_units = tuple(str(value) for value in pixel_units)
            if any(not value for value in converted_units):
                raise ValueError("pixel units must not be empty")
            object.__setattr__(self, "pixel_unit_xy", converted_units)

    @property
    def slice_count(self) -> int:
        return self.shape[0] if len(self.shape) == 3 else 1

    @property
    def image_shape(self) -> tuple[int, int]:
        return (self.shape[-2], self.shape[-1])


@dataclass(frozen=True, slots=True)
class ExportRequest:
    """Immutable description of a future single or batch export operation."""

    destination: Path
    crop: CropRect
    output_format: ExportFormat
    normalization: NormalizationMode = NormalizationMode.NONE
    slice_indices: tuple[int, ...] = (0,)
    overwrite: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "destination", Path(self.destination))
        object.__setattr__(self, "output_format", ExportFormat(self.output_format))
        object.__setattr__(
            self, "normalization", NormalizationMode(self.normalization)
        )
        object.__setattr__(
            self, "slice_indices", _coerce_index_tuple(self.slice_indices)
        )
        if not isinstance(self.overwrite, bool):
            raise TypeError("overwrite must be a boolean")


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Immutable summary returned by the future export engine."""

    output_paths: tuple[Path, ...]
    completed_slice_indices: tuple[int, ...]
    cancelled: bool = False

    def __post_init__(self) -> None:
        output_paths = tuple(Path(path) for path in self.output_paths)
        completed = tuple(
            _coerce_integer(value, "completed slice index")
            for value in self.completed_slice_indices
        )
        if any(value < 0 for value in completed):
            raise ValueError("completed slice indices must be non-negative")
        if len(output_paths) != len(completed):
            raise ValueError(
                "output_paths and completed_slice_indices must have equal lengths"
            )
        if not isinstance(self.cancelled, bool):
            raise TypeError("cancelled must be a boolean")
        object.__setattr__(self, "output_paths", output_paths)
        object.__setattr__(self, "completed_slice_indices", completed)
