import numpy as np
import pytest

from stem_crop_tool.core.dtypes import output_dtype_for
from stem_crop_tool.core.exceptions import UnsupportedDTypeError
from stem_crop_tool.core.models import ExportFormat, NormalizationMode


@pytest.mark.parametrize(
    "source_dtype",
    [np.uint8, np.uint16, np.int16, np.float32, np.float64, np.bool_],
)
def test_raw_npy_preserves_source_dtype(source_dtype: np.dtype) -> None:
    assert output_dtype_for(
        source_dtype, ExportFormat.NPY, NormalizationMode.NONE
    ) == np.dtype(source_dtype)


@pytest.mark.parametrize(
    "output_format,expected",
    [(ExportFormat.NPY, np.float32), (ExportFormat.PNG, np.uint8)],
)
def test_normalized_output_dtype_is_fixed(
    output_format: ExportFormat, expected: np.dtype
) -> None:
    assert output_dtype_for(
        np.uint16, output_format, NormalizationMode.LOCAL_MINMAX
    ) == np.dtype(expected)


@pytest.mark.parametrize("source_dtype", [np.uint8, np.uint16])
def test_raw_png_preserves_supported_unsigned_dtype(source_dtype: np.dtype) -> None:
    assert output_dtype_for(
        source_dtype, ExportFormat.PNG, NormalizationMode.NONE
    ) == np.dtype(source_dtype)


@pytest.mark.parametrize(
    "source_dtype",
    [np.int8, np.int16, np.uint32, np.float32, np.float64, np.bool_],
)
def test_raw_png_rejects_unsupported_dtype(source_dtype: np.dtype) -> None:
    with pytest.raises(UnsupportedDTypeError, match="enable normalization"):
        output_dtype_for(source_dtype, ExportFormat.PNG, NormalizationMode.NONE)


@pytest.mark.parametrize("output_format", list(ExportFormat))
def test_complex_dtype_is_always_rejected(output_format: ExportFormat) -> None:
    with pytest.raises(UnsupportedDTypeError):
        output_dtype_for(
            np.complex64, output_format, NormalizationMode.LOCAL_MINMAX
        )
