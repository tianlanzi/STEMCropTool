"""Qt-codec-backed grayscale raster image source."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage, QImageReader

from stem_crop_tool.core.exceptions import (
    SourceClosedError,
    SourceOpenError,
    UnsupportedDTypeError,
)
from stem_crop_tool.core.models import ImageMetadata
from stem_crop_tool.core.readers.base import validate_slice_index


_RASTER_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _grayscale_array(image: QImage, source_name: str) -> np.ndarray:
    image_format = image.format()
    if image_format not in {
        QImage.Format.Format_Grayscale8,
        QImage.Format.Format_Grayscale16,
    }:
        if image_format == QImage.Format.Format_Indexed8 and image.isGrayscale():
            image = image.convertToFormat(QImage.Format.Format_Grayscale8)
            image_format = image.format()
        else:
            raise UnsupportedDTypeError(
                f"color raster images are unsupported: '{source_name}'"
            )

    height = image.height()
    width = image.width()
    bytes_per_line = image.bytesPerLine()
    buffer = image.constBits()
    if image_format == QImage.Format.Format_Grayscale8:
        rows = np.frombuffer(
            buffer,
            dtype=np.uint8,
            count=height * bytes_per_line,
        ).reshape(height, bytes_per_line)
        return rows[:, :width].copy()

    values_per_line = bytes_per_line // np.dtype(np.uint16).itemsize
    rows = np.frombuffer(
        buffer,
        dtype=np.uint16,
        count=height * values_per_line,
    ).reshape(height, values_per_line)
    return rows[:, :width].copy()


class RasterImageSource:
    """Own an in-memory grayscale PNG or JPEG decoded by Qt."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._array: np.ndarray | None = None
        suffix = self.path.suffix.lower()
        if suffix not in _RASTER_EXTENSIONS:
            raise SourceOpenError(
                f"expected a PNG or JPEG raster file: {self.path.name}"
            )

        reader = QImageReader(str(self.path))
        reader.setAutoTransform(False)
        image = reader.read()
        if image.isNull():
            detail = reader.errorString() or "unknown raster decoding error"
            raise SourceOpenError(
                f"could not open raster image '{self.path.name}': {detail}"
            )

        array = _grayscale_array(image, self.path.name)
        array.flags.writeable = False
        self._array = array
        self.shape = tuple(int(size) for size in array.shape)
        self.dtype = np.dtype(array.dtype)
        self.ndim = 2
        self.slice_count = 1
        source_format = "jpg" if suffix in {".jpg", ".jpeg"} else "png"
        self.metadata = ImageMetadata(
            source_name=self.path.name,
            source_format=source_format,
            shape=self.shape,
            dtype=self.dtype,
        )

    @property
    def closed(self) -> bool:
        return self._array is None

    def get_slice(self, index: int = 0) -> np.ndarray:
        array = self._array
        if array is None:
            raise SourceClosedError(f"raster source '{self.path.name}' is closed")
        validate_slice_index(index, 1)
        return array

    def close(self) -> None:
        self._array = None

    def __enter__(self) -> RasterImageSource:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
