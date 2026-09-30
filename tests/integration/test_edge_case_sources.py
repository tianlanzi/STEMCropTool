from __future__ import annotations

import numpy as np
import pytest

from stem_crop_tool.core.exceptions import NonFiniteNormalizationError
from stem_crop_tool.core.models import (
    CropRect,
    ExportFormat,
    ExportRequest,
    NormalizationMode,
)
from stem_crop_tool.core.readers.npy import NpyImageSource
from stem_crop_tool.infrastructure.display import grayscale_display_buffer
from stem_crop_tool.infrastructure.exporters import export_source


def _normalized_request(destination, width: int, height: int) -> ExportRequest:
    return ExportRequest(
        destination=destination,
        crop=CropRect(0, 0, width, height),
        output_format=ExportFormat.NPY,
        normalization=NormalizationMode.LOCAL_MINMAX,
        slice_indices=(0,),
        overwrite=False,
    )


def test_constant_npy_opens_displays_and_normalizes_to_zero(tmp_path) -> None:
    path = tmp_path / "constant.npy"
    destination = tmp_path / "constant_crop.npy"
    np.save(path, np.full((32, 48), 17.0, dtype=np.float32))

    with NpyImageSource(path) as source:
        image = source.get_slice()
        assert np.count_nonzero(grayscale_display_buffer(image)) == 0
        export_source(source, _normalized_request(destination, 48, 32))

    output = np.load(destination, allow_pickle=False)
    assert output.dtype == np.float32
    assert np.count_nonzero(output) == 0


def test_non_finite_npy_displays_safely_and_rejects_normalization(tmp_path) -> None:
    path = tmp_path / "non_finite.npy"
    destination = tmp_path / "non_finite_crop.npy"
    data = np.array([[np.nan, -2.0], [2.0, np.inf]], dtype=np.float32)
    np.save(path, data)

    with NpyImageSource(path) as source:
        display = grayscale_display_buffer(source.get_slice())
        assert display.tolist() == [[0, 0], [255, 0]]
        with pytest.raises(NonFiniteNormalizationError, match="finite crop values"):
            export_source(source, _normalized_request(destination, 2, 2))

    assert not destination.exists()
    assert not destination.with_suffix(".json").exists()
    assert list(tmp_path.glob(".*.tmp")) == []
