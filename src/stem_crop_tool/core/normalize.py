"""Strict normalization operations for exported crops."""

import numpy as np

from stem_crop_tool.core.exceptions import (
    NonFiniteNormalizationError,
    UnsupportedArrayShapeError,
    UnsupportedDTypeError,
)


def normalize_local_minmax(crop: np.ndarray) -> np.ndarray:
    """Return an independent local min-max normalized `float32` crop."""

    array = np.asarray(crop)
    if array.ndim != 2 or array.size == 0:
        raise UnsupportedArrayShapeError(
            "normalization requires a non-empty 2D crop"
        )
    if np.issubdtype(array.dtype, np.complexfloating):
        raise UnsupportedDTypeError("complex image arrays are unsupported")

    result = array.astype(np.float32, copy=True)
    if not np.all(np.isfinite(result)):
        raise NonFiniteNormalizationError(
            "normalized export requires finite crop values"
        )

    minimum = result.min()
    maximum = result.max()
    if maximum == minimum:
        result.fill(0.0)
        return result

    result -= minimum
    result /= maximum - minimum
    np.clip(result, 0.0, 1.0, out=result)
    return result
