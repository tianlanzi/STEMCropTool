from pathlib import Path

import numpy as np
import pytest

from stem_crop_tool.core.batch import (
    CancellationToken,
    ExportProgress,
    all_slice_indices,
    batch_item_filename,
    current_slice_indices,
    inclusive_slice_range,
    suggested_single_filename,
)
from stem_crop_tool.core.exceptions import InvalidSliceIndexError
from stem_crop_tool.core.models import ExportFormat, ImageMetadata


def test_slice_selection_helpers_are_inclusive_and_ordered() -> None:
    assert current_slice_indices(2, 5) == (2,)
    assert inclusive_slice_range(1, 3, 5) == (1, 2, 3)
    assert all_slice_indices(4) == (0, 1, 2, 3)


@pytest.mark.parametrize("index", [-1, 3])
def test_current_slice_rejects_out_of_range_index(index: int) -> None:
    with pytest.raises(InvalidSliceIndexError):
        current_slice_indices(index, 3)


def test_inclusive_range_rejects_reverse_bounds() -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        inclusive_slice_range(3, 1, 5)


def test_default_names_are_stable_and_sortable() -> None:
    metadata = ImageMetadata("sample.stack.dm4", "dm4", (12_000, 8, 9), np.uint16)

    assert suggested_single_filename(metadata, ExportFormat.PNG) == "sample.stack_crop.png"
    assert batch_item_filename(metadata, 3, ExportFormat.NPY) == (
        "sample.stack_z00003_crop.npy"
    )


def test_cancellation_token_and_progress_are_thread_adapter_friendly() -> None:
    token = CancellationToken()
    assert not token.is_cancelled
    token.cancel()
    assert token.is_cancelled

    progress = ExportProgress(2, 4, 3, Path("out.npy"))
    assert progress.fraction == 0.5
