import json

import numpy as np

from stem_crop_tool.core.batch import all_slice_indices
from stem_crop_tool.core.models import CropRect, ExportFormat, ExportRequest
from stem_crop_tool.core.readers.npy import NpyImageSource
from stem_crop_tool.infrastructure.exporters import export_source


def test_memory_mapped_npy_stack_exports_slice_by_slice(tmp_path) -> None:
    source_path = tmp_path / "stack.npy"
    stack = np.arange(4 * 5 * 6, dtype=np.uint16).reshape(4, 5, 6)
    np.save(source_path, stack)
    destination = tmp_path / "batch"

    with NpyImageSource(source_path) as source:
        assert isinstance(source._array, np.memmap)
        result = export_source(
            source,
            ExportRequest(
                destination=destination,
                crop=CropRect(2, 1, 3, 2),
                output_format=ExportFormat.NPY,
                slice_indices=all_slice_indices(source.slice_count),
            ),
        )

    assert result.completed_slice_indices == (0, 1, 2, 3)
    for index, output_path in enumerate(result.output_paths):
        np.testing.assert_array_equal(
            np.load(output_path, allow_pickle=False),
            stack[index, 1:3, 2:5],
        )
    manifest = json.loads(
        (destination / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["completed_slice_indices"] == [0, 1, 2, 3]
