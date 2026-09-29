from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtGui import QColor, QImage, qRgb

from stem_crop_tool.core.exceptions import (
    InvalidSliceIndexError,
    SourceClosedError,
    SourceOpenError,
    UnsupportedDTypeError,
)
from stem_crop_tool.infrastructure.raster_io import RasterImageSource


def _save_grayscale(path, data: np.ndarray) -> None:
    height, width = data.shape
    if data.dtype == np.uint8:
        image_format = QImage.Format.Format_Grayscale8
    elif data.dtype == np.uint16:
        image_format = QImage.Format.Format_Grayscale16
    else:
        raise TypeError(data.dtype)

    image = QImage(width, height, image_format)
    bytes_per_line = image.bytesPerLine()
    if data.dtype == np.uint8:
        rows = np.frombuffer(
            image.bits(), dtype=np.uint8, count=height * bytes_per_line
        ).reshape(height, bytes_per_line)
    else:
        values_per_line = bytes_per_line // np.dtype(np.uint16).itemsize
        rows = np.frombuffer(
            image.bits(), dtype=np.uint16, count=height * values_per_line
        ).reshape(height, values_per_line)
    rows[:, :width] = data
    assert image.save(str(path))


@pytest.mark.parametrize("dtype", [np.uint8, np.uint16])
def test_png_round_trip_preserves_grayscale_values_exactly(tmp_path, dtype) -> None:
    path = tmp_path / f"gray_{np.dtype(dtype).name}.png"
    if dtype == np.uint8:
        expected = np.array([[0, 1, 127], [128, 254, 255]], dtype=dtype)
    else:
        expected = np.array(
            [[0, 1, 32767], [32768, 65534, 65535]], dtype=dtype
        )
    _save_grayscale(path, expected)

    with RasterImageSource(path) as source:
        assert source.shape == expected.shape
        assert source.dtype == np.dtype(dtype)
        assert source.slice_count == 1
        np.testing.assert_array_equal(source.get_slice(), expected)


def test_grayscale_jpeg_preserves_dimensions_and_uint8_dtype(tmp_path) -> None:
    path = tmp_path / "gray.jpg"
    expected = np.arange(63, dtype=np.uint8).reshape(7, 9) * 4
    _save_grayscale(path, expected)

    with RasterImageSource(path) as source:
        actual = source.get_slice()
        assert actual.shape == expected.shape
        assert actual.dtype == np.uint8
        assert np.max(np.abs(actual.astype(np.int16) - expected.astype(np.int16))) <= 8


def test_grayscale_indexed_png_is_accepted_without_color_conversion(tmp_path) -> None:
    path = tmp_path / "indexed_gray.png"
    image = QImage(4, 2, QImage.Format.Format_Indexed8)
    image.setColorTable([qRgb(value, value, value) for value in range(256)])
    rows = np.frombuffer(
        image.bits(), dtype=np.uint8, count=image.height() * image.bytesPerLine()
    ).reshape(image.height(), image.bytesPerLine())
    expected = np.array([[0, 64, 128, 255], [5, 10, 20, 30]], dtype=np.uint8)
    rows[:, : image.width()] = expected
    assert image.save(str(path))

    with RasterImageSource(path) as source:
        np.testing.assert_array_equal(source.get_slice(), expected)


@pytest.mark.parametrize(
    "image_format",
    [QImage.Format.Format_RGB888, QImage.Format.Format_RGBA8888],
)
def test_color_png_is_rejected_without_conversion(tmp_path, image_format) -> None:
    path = tmp_path / "color.png"
    image = QImage(4, 3, image_format)
    image.fill(QColor(255, 0, 0, 127))
    assert image.save(str(path))

    with pytest.raises(UnsupportedDTypeError, match="color"):
        RasterImageSource(path)


def test_malformed_raster_has_user_facing_open_error(tmp_path) -> None:
    path = tmp_path / "broken.png"
    path.write_bytes(b"not a png")

    with pytest.raises(SourceOpenError, match="could not open raster image"):
        RasterImageSource(path)


def test_raster_slice_bounds_and_close(tmp_path) -> None:
    path = tmp_path / "gray.png"
    _save_grayscale(path, np.zeros((2, 3), dtype=np.uint8))
    source = RasterImageSource(path)

    with pytest.raises(InvalidSliceIndexError):
        source.get_slice(1)
    source.close()
    source.close()
    with pytest.raises(SourceClosedError):
        source.get_slice()
