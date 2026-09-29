from __future__ import annotations

import numpy as np
import pytest

from stem_crop_tool.core.exceptions import (
    InvalidSliceIndexError,
    SourceClosedError,
    SourceOpenError,
    UnsupportedArrayShapeError,
    UnsupportedDTypeError,
)
from stem_crop_tool.core.readers.npy import NpyImageSource


@pytest.mark.parametrize(
    "dtype",
    [np.uint8, np.uint16, np.int16, np.float32, np.float64, np.bool_],
)
def test_two_dimensional_npy_preserves_values_and_dtype(tmp_path, dtype) -> None:
    path = tmp_path / f"image_{np.dtype(dtype).name}.npy"
    data = np.arange(20).reshape(4, 5).astype(dtype)
    np.save(path, data)

    with NpyImageSource(path) as source:
        assert isinstance(source._array, np.memmap)
        assert source.shape == (4, 5)
        assert source.dtype == np.dtype(dtype)
        assert source.slice_count == 1
        assert source.metadata.pixel_size_xy is None
        actual = source.get_slice()
        np.testing.assert_array_equal(actual, data)
        assert not actual.flags.writeable


def test_three_dimensional_npy_uses_axis_zero_slices(tmp_path) -> None:
    path = tmp_path / "stack.npy"
    data = np.arange(3 * 4 * 5, dtype=np.float32).reshape(3, 4, 5)
    np.save(path, data)

    source = NpyImageSource(path)
    try:
        assert isinstance(source._array, np.memmap)
        assert source.shape == (3, 4, 5)
        assert source.slice_count == 3
        np.testing.assert_array_equal(source.get_slice(2), data[2])
    finally:
        source.close()


@pytest.mark.parametrize("shape", [(5,), (1, 2, 3, 4), (1, 1, 3, 4)])
def test_npy_rejects_unsupported_declared_dimensions(tmp_path, shape) -> None:
    path = tmp_path / "unsupported.npy"
    np.save(path, np.zeros(shape, dtype=np.uint8))

    with pytest.raises(UnsupportedArrayShapeError):
        NpyImageSource(path)


def test_npy_rejects_complex_and_non_numeric_arrays(tmp_path) -> None:
    complex_path = tmp_path / "complex.npy"
    text_path = tmp_path / "text.npy"
    np.save(complex_path, np.ones((2, 2), dtype=np.complex64))
    np.save(text_path, np.full((2, 2), "x", dtype="U1"))

    with pytest.raises(UnsupportedDTypeError, match="complex"):
        NpyImageSource(complex_path)
    with pytest.raises(UnsupportedDTypeError, match="non-numeric"):
        NpyImageSource(text_path)


def test_npy_disables_pickle_and_rejects_malformed_files(tmp_path) -> None:
    object_path = tmp_path / "object.npy"
    malformed_path = tmp_path / "malformed.npy"
    np.save(object_path, np.array([[object()]], dtype=object))
    malformed_path.write_bytes(b"not a numpy file")

    with pytest.raises(SourceOpenError):
        NpyImageSource(object_path)
    with pytest.raises(SourceOpenError):
        NpyImageSource(malformed_path)


def test_npy_slice_bounds_and_close_are_explicit(tmp_path) -> None:
    path = tmp_path / "stack.npy"
    np.save(path, np.zeros((2, 3, 4), dtype=np.uint8))
    source = NpyImageSource(path)

    with pytest.raises(InvalidSliceIndexError):
        source.get_slice(-1)
    with pytest.raises(InvalidSliceIndexError):
        source.get_slice(2)
    with pytest.raises(TypeError):
        source.get_slice(0.5)

    source.close()
    source.close()
    with pytest.raises(SourceClosedError):
        source.get_slice()


def test_npy_mapping_closes_cleanly_and_file_can_be_reopened(tmp_path) -> None:
    path = tmp_path / "image.npy"
    moved_path = tmp_path / "moved.npy"
    expected = np.arange(12, dtype=np.uint16).reshape(3, 4)
    np.save(path, expected)

    first = NpyImageSource(path)
    first.close()
    path.rename(moved_path)

    with NpyImageSource(moved_path) as second:
        np.testing.assert_array_equal(second.get_slice(), expected)
