import numpy as np
import pytest

from stem_crop_tool.core.exceptions import (
    NonFiniteNormalizationError,
    UnsupportedArrayShapeError,
    UnsupportedDTypeError,
)
from stem_crop_tool.core.normalize import normalize_local_minmax


def test_normalizes_integer_crop_to_float32_without_mutating_source() -> None:
    source = np.array([[2, 4], [6, 10]], dtype=np.uint16)
    original = source.copy()

    result = normalize_local_minmax(source)

    expected = np.array([[0.0, 0.25], [0.5, 1.0]], dtype=np.float32)
    np.testing.assert_allclose(result, expected)
    np.testing.assert_array_equal(source, original)
    assert result.dtype == np.float32


def test_normalizes_negative_float_values() -> None:
    source = np.array([[-5.0, -3.0], [-1.0, 3.0]], dtype=np.float64)

    result = normalize_local_minmax(source)

    np.testing.assert_allclose(
        result,
        np.array([[0.0, 0.25], [0.5, 1.0]], dtype=np.float32),
    )


def test_constant_crop_normalizes_to_zeros() -> None:
    result = normalize_local_minmax(np.full((3, 4), 7, dtype=np.int16))

    assert result.dtype == np.float32
    np.testing.assert_array_equal(result, np.zeros((3, 4), dtype=np.float32))


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_non_finite_crop_fails(value: float) -> None:
    source = np.array([[0.0, value]], dtype=np.float32)

    with pytest.raises(NonFiniteNormalizationError):
        normalize_local_minmax(source)


@pytest.mark.parametrize("shape", [(0, 2), (2,), (1, 2, 3)])
def test_normalization_rejects_non_2d_or_empty_crop(shape: tuple[int, ...]) -> None:
    with pytest.raises(UnsupportedArrayShapeError):
        normalize_local_minmax(np.zeros(shape, dtype=np.float32))


def test_normalization_rejects_complex_values() -> None:
    with pytest.raises(UnsupportedDTypeError):
        normalize_local_minmax(np.ones((2, 2), dtype=np.complex64))
