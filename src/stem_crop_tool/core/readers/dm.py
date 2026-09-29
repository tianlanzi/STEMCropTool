"""Adapter around the vendored NCEM DigitalMicrograph parser."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np

from stem_crop_tool.core.exceptions import (
    DatasetSelectionRequiredError,
    NoSupportedDatasetError,
    SourceClosedError,
    SourceOpenError,
    STEMCropError,
)
from stem_crop_tool.core.models import ImageMetadata
from stem_crop_tool.core.readers.base import validate_image_array, validate_slice_index
from stem_crop_tool.vendor.ncempy_dm import fileDM


@dataclass(frozen=True, slots=True)
class DMDatasetInfo:
    """One non-thumbnail dataset declared in a DM3/DM4 file."""

    index: int
    raw_index: int
    shape: tuple[int, ...]
    dtype: np.dtype | None
    pixel_size_xy: tuple[float, float] | None = None
    pixel_unit_xy: tuple[str, str] | None = None
    pixel_origin_xy: tuple[float, float] | None = None
    unsupported_reason: str | None = None

    @property
    def ndim(self) -> int:
        return len(self.shape)

    @property
    def supported(self) -> bool:
        return self.unsupported_reason is None


def _declared_shape(reader: fileDM, raw_index: int) -> tuple[int, ...]:
    ndim = int(reader.dataShape[raw_index])
    x = int(reader.xSize[raw_index])
    y = int(reader.ySize[raw_index])
    z = int(reader.zSize[raw_index])
    z2 = int(reader.zSize2[raw_index])
    if ndim == 1:
        return (x,)
    if ndim == 2:
        return (y, x)
    if ndim == 3:
        return (z, y, x)
    if ndim == 4:
        return (z2, z, y, x)
    return tuple()


def _xy_calibration(
    reader: fileDM,
    raw_index: int,
) -> tuple[
    tuple[float, float] | None,
    tuple[str, str] | None,
    tuple[float, float] | None,
]:
    if int(reader.dataShape[raw_index]) < 2:
        return None, None, None
    offset = sum(int(value) for value in reader.dataShape[:raw_index])
    try:
        sizes = (float(reader.scale[offset]), float(reader.scale[offset + 1]))
        units = (
            str(reader.scaleUnit[offset]),
            str(reader.scaleUnit[offset + 1]),
        )
        origins = (
            float(reader.origin[offset]),
            float(reader.origin[offset + 1]),
        )
    except (IndexError, TypeError, ValueError):
        return None, None, None

    valid_sizes = sizes if all(np.isfinite(value) and value > 0 for value in sizes) else None
    valid_units = units if all(units) else None
    valid_origins = origins if all(np.isfinite(value) for value in origins) else None
    return valid_sizes, valid_units, valid_origins


def _dataset_infos(reader: fileDM) -> tuple[DMDatasetInfo, ...]:
    first_raw_index = 1 if reader.thumbnail else 0
    infos: list[DMDatasetInfo] = []
    for logical_index, raw_index in enumerate(
        range(first_raw_index, int(reader.numObjects))
    ):
        shape = _declared_shape(reader, raw_index)
        reason: str | None = None
        dtype: np.dtype | None
        try:
            dtype = np.dtype(reader._DM2NPDataType(reader.dataType[raw_index]))
        except (KeyError, OSError, TypeError, ValueError):
            dtype = None
            reason = f"unsupported DM data type code {int(reader.dataType[raw_index])}"

        if len(shape) not in (2, 3):
            reason = (
                f"declared {len(shape)}D DM dataset is unsupported; "
                "only 2D and 3D datasets are accepted"
            )
        elif any(size < 1 for size in shape):
            reason = "DM dataset dimensions must all be positive"
        elif dtype is not None and np.issubdtype(dtype, np.complexfloating):
            reason = "complex DM datasets are unsupported"

        sizes, units, origins = _xy_calibration(reader, raw_index)
        infos.append(
            DMDatasetInfo(
                index=logical_index,
                raw_index=raw_index,
                shape=shape,
                dtype=dtype,
                pixel_size_xy=sizes,
                pixel_unit_xy=units,
                pixel_origin_xy=origins,
                unsupported_reason=reason,
            )
        )
    return tuple(infos)


def _open_reader(path: Path) -> fileDM:
    if path.suffix.lower() not in {".dm3", ".dm4"}:
        raise SourceOpenError(f"expected a DM3 or DM4 file: {path.name}")
    try:
        return fileDM(path, on_memory=False)
    except Exception as exc:
        raise SourceOpenError(
            f"could not open DM file '{path.name}': {exc}"
        ) from exc


def list_dm_datasets(path: str | Path) -> tuple[DMDatasetInfo, ...]:
    """Parse a DM file and return every non-thumbnail dataset declaration."""

    source_path = Path(path)
    reader = _open_reader(source_path)
    try:
        try:
            return _dataset_infos(reader)
        except STEMCropError:
            raise
        except Exception as exc:
            raise SourceOpenError(
                f"could not inspect DM file '{source_path.name}': {exc}"
            ) from exc
    finally:
        reader.close()


def _select_dataset(
    infos: tuple[DMDatasetInfo, ...],
    dataset_index: int | None,
) -> DMDatasetInfo:
    supported = tuple(info for info in infos if info.supported)
    if dataset_index is None:
        if not supported:
            reasons = "; ".join(
                info.unsupported_reason or "unsupported" for info in infos
            )
            raise NoSupportedDatasetError(
                f"DM file has no supported 2D/3D image dataset: {reasons or 'empty file'}"
            )
        if len(supported) > 1:
            raise DatasetSelectionRequiredError(
                tuple(info.index for info in supported)
            )
        return supported[0]

    if isinstance(dataset_index, bool) or not isinstance(
        dataset_index, (int, np.integer)
    ):
        raise TypeError("dataset_index must be an integer")
    requested = int(dataset_index)
    for info in infos:
        if info.index == requested:
            if not info.supported:
                raise NoSupportedDatasetError(
                    f"DM dataset {requested} is unsupported: {info.unsupported_reason}"
                )
            return info
    raise NoSupportedDatasetError(f"DM dataset index {requested} does not exist")


class DMImageSource:
    """Read one supported DM dataset through a read-only memory map."""

    def __init__(
        self,
        path: str | Path,
        *,
        dataset_index: int | None = None,
    ) -> None:
        self.path = Path(path)
        self._array: np.memmap | None = None
        self._all_tags: Mapping[str, Any] = MappingProxyType({})
        reader = _open_reader(self.path)
        try:
            infos = _dataset_infos(reader)
            selected = _select_dataset(infos, dataset_index)
            assert selected.dtype is not None
            validate_image_array(selected.shape, selected.dtype)
            mapped = reader.getMemmap(selected.index)
            if tuple(int(size) for size in mapped.shape) != selected.shape:
                mapped._mmap.close()
                raise SourceOpenError(
                    "DM memory-map shape does not match the declared dataset shape"
                )
            self._array = mapped
            self._all_tags = MappingProxyType(dict(reader.allTags))
        except Exception as exc:
            mapped = self._array
            self._array = None
            if mapped is not None:
                mapped._mmap.close()
            if isinstance(exc, STEMCropError):
                raise
            raise SourceOpenError(
                f"could not open DM dataset in '{self.path.name}': {exc}"
            ) from exc
        finally:
            reader.close()

        self.dataset_info = selected
        self.shape = selected.shape
        self.dtype = selected.dtype
        self.ndim = len(self.shape)
        self.slice_count = self.shape[0] if self.ndim == 3 else 1
        self.metadata = ImageMetadata(
            source_name=self.path.name,
            source_format=self.path.suffix.lower().lstrip("."),
            shape=self.shape,
            dtype=self.dtype,
            dataset_index=selected.index,
            pixel_size_xy=selected.pixel_size_xy,
            pixel_unit_xy=selected.pixel_unit_xy,
        )

    @property
    def all_tags(self) -> Mapping[str, Any]:
        return self._all_tags

    @property
    def closed(self) -> bool:
        return self._array is None

    def get_slice(self, index: int = 0) -> np.ndarray:
        array = self._array
        if array is None:
            raise SourceClosedError(f"DM source '{self.path.name}' is closed")
        index = validate_slice_index(index, self.slice_count)
        result = array if self.ndim == 2 else array[index]
        result.flags.writeable = False
        return result

    def close(self) -> None:
        array = self._array
        self._array = None
        if array is not None:
            array._mmap.close()

    def __enter__(self) -> DMImageSource:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
