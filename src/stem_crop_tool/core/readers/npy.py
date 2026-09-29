"""Lazy reader for two- and three-dimensional NumPy arrays."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from stem_crop_tool.core.exceptions import SourceClosedError, SourceOpenError
from stem_crop_tool.core.models import ImageMetadata
from stem_crop_tool.core.readers.base import validate_image_array, validate_slice_index


class NpyImageSource:
    """Read a supported NPY file through a read-only memory map."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._array: np.memmap | None = None

        if self.path.suffix.lower() != ".npy":
            raise SourceOpenError(f"expected an NPY file: {self.path.name}")

        try:
            loaded = np.load(self.path, mmap_mode="r", allow_pickle=False)
        except (EOFError, OSError, ValueError) as exc:
            raise SourceOpenError(
                f"could not open NPY file '{self.path.name}': {exc}"
            ) from exc

        if not isinstance(loaded, np.memmap):
            if hasattr(loaded, "close"):
                loaded.close()
            raise SourceOpenError(
                f"'{self.path.name}' is not a memory-mappable NPY array"
            )

        try:
            shape = tuple(int(size) for size in loaded.shape)
            dtype = np.dtype(loaded.dtype)
            validate_image_array(shape, dtype)
        except Exception:
            loaded._mmap.close()
            raise

        self._array = loaded
        self.shape = shape
        self.dtype = dtype
        self.ndim = len(shape)
        self.slice_count = shape[0] if self.ndim == 3 else 1
        self.metadata = ImageMetadata(
            source_name=self.path.name,
            source_format="npy",
            shape=shape,
            dtype=dtype,
        )

    @property
    def closed(self) -> bool:
        return self._array is None

    def get_slice(self, index: int = 0) -> np.ndarray:
        array = self._array
        if array is None:
            raise SourceClosedError(f"NPY source '{self.path.name}' is closed")
        index = validate_slice_index(index, self.slice_count)
        result = array if self.ndim == 2 else array[index]
        result.flags.writeable = False
        return result

    def close(self) -> None:
        array = self._array
        self._array = None
        if array is not None:
            array._mmap.close()

    def __enter__(self) -> NpyImageSource:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
