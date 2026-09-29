"""Safe, view-only conversion from scientific arrays to Qt images."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PySide6.QtGui import QImage


@dataclass(frozen=True, slots=True)
class DisplayFrame:
    """Own the display buffer and the detached Qt image made from it."""

    buffer: np.ndarray
    image: QImage


def grayscale_display_buffer(array: np.ndarray) -> np.ndarray:
    """Map one 2D source slice to an independent contiguous uint8 buffer.

    The finite minimum and maximum are mapped to 0 and 255. Constant slices
    and non-finite pixels display as black. The source is never modified.
    """

    source = np.asarray(array)
    if source.ndim != 2:
        raise ValueError("display input must be a two-dimensional array")
    if np.issubdtype(source.dtype, np.complexfloating):
        raise TypeError("complex arrays cannot be displayed")

    working = source.astype(np.float64, copy=False)
    finite = np.isfinite(working)
    output = np.zeros(source.shape, dtype=np.uint8, order="C")
    if not finite.any():
        return output

    finite_values = working[finite]
    minimum = float(finite_values.min())
    maximum = float(finite_values.max())
    if maximum == minimum:
        return output

    scaled = (working[finite] - minimum) / (maximum - minimum)
    output[finite] = np.rint(scaled * 255.0).astype(np.uint8)
    return output


def make_grayscale_qimage(array: np.ndarray) -> DisplayFrame:
    """Return an owned display frame with explicit row stride and lifetime.

    ``QImage`` initially wraps the NumPy bytes, then ``copy()`` detaches those
    bytes into Qt-owned storage. The returned frame also retains the original
    contiguous display buffer so the ownership relationship is unambiguous.
    """

    buffer = grayscale_display_buffer(array)
    height, width = buffer.shape
    wrapped = QImage(
        buffer.data,
        width,
        height,
        int(buffer.strides[0]),
        QImage.Format.Format_Grayscale8,
    )
    if wrapped.isNull():
        raise RuntimeError("could not construct a grayscale display image")
    image = wrapped.copy()
    return DisplayFrame(buffer=buffer, image=image)
