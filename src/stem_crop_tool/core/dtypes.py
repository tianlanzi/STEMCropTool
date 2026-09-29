"""Output dtype decisions that do not perform file I/O."""

import numpy as np

from stem_crop_tool.core.exceptions import UnsupportedDTypeError
from stem_crop_tool.core.models import ExportFormat, NormalizationMode


def output_dtype_for(
    source_dtype: np.dtype,
    output_format: ExportFormat,
    normalization: NormalizationMode,
) -> np.dtype:
    """Return the required output dtype or raise for a forbidden conversion."""

    dtype = np.dtype(source_dtype)
    output_format = ExportFormat(output_format)
    normalization = NormalizationMode(normalization)

    if np.issubdtype(dtype, np.complexfloating):
        raise UnsupportedDTypeError("complex image arrays are unsupported")

    if normalization is NormalizationMode.LOCAL_MINMAX:
        if output_format is ExportFormat.NPY:
            return np.dtype(np.float32)
        return np.dtype(np.uint8)

    if output_format is ExportFormat.NPY:
        return dtype

    if dtype.kind == "u" and dtype.itemsize in (1, 2):
        return np.dtype(np.uint8 if dtype.itemsize == 1 else np.uint16)

    raise UnsupportedDTypeError(
        f"raw PNG export does not support dtype {dtype}; "
        "enable normalization or export NPY"
    )
