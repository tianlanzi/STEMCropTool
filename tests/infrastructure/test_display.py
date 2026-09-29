from __future__ import annotations

import numpy as np

from stem_crop_tool.infrastructure.display import (
    grayscale_display_buffer,
    make_grayscale_qimage,
)


def test_display_mapping_is_independent_and_preserves_source() -> None:
    source = np.array([[0, 1000], [2000, 4000]], dtype=np.uint16)
    original = source.copy()

    display = grayscale_display_buffer(source)

    assert display.dtype == np.uint8
    assert display.flags.c_contiguous
    assert display.tolist() == [[0, 64], [128, 255]]
    np.testing.assert_array_equal(source, original)
    assert not np.shares_memory(display, source)


def test_display_mapping_handles_constant_and_non_finite_values() -> None:
    constant = np.full((2, 3), 7.5, dtype=np.float32)
    assert np.count_nonzero(grayscale_display_buffer(constant)) == 0

    source = np.array([[np.nan, -2.0], [2.0, np.inf]], dtype=np.float64)
    display = grayscale_display_buffer(source)
    assert display.tolist() == [[0, 0], [255, 0]]

    all_non_finite = np.array([[np.nan, np.inf]], dtype=np.float32)
    assert np.count_nonzero(grayscale_display_buffer(all_non_finite)) == 0


def test_qimage_detaches_from_numpy_buffer_and_uses_explicit_stride() -> None:
    frame = make_grayscale_qimage(np.arange(15, dtype=np.uint16).reshape(3, 5))

    assert frame.image.width() == 5
    assert frame.image.height() == 3
    assert frame.buffer.strides[0] == 5
    before = frame.image.pixelColor(4, 2).value()

    frame.buffer[:, :] = 0

    assert before == 255
    assert frame.image.pixelColor(4, 2).value() == before
