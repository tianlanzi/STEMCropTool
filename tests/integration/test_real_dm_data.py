from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from stem_crop_tool.core.readers.dm import DMImageSource, list_dm_datasets


TEST_DATA_ENV = "STEM_CROP_TOOL_TEST_DATA"


def test_available_real_dm3_and_dm4_files() -> None:
    raw_root = os.environ.get(TEST_DATA_ENV)
    if not raw_root:
        pytest.skip(f"set {TEST_DATA_ENV} to run external real-data tests")
    root = Path(raw_root)
    if not root.is_dir():
        pytest.skip(f"external test-data directory does not exist: {root}")

    paths = sorted((*root.glob("*.dm3"), *root.glob("*.dm4")))
    suffixes = {path.suffix.lower() for path in paths}
    assert {".dm3", ".dm4"}.issubset(suffixes)

    calibrated = 0
    for path in paths:
        infos = list_dm_datasets(path)
        supported = [info for info in infos if info.supported]
        assert supported, f"no supported dataset in {path.name}"
        selected = supported[0]
        with DMImageSource(path, dataset_index=selected.index) as source:
            assert source.shape == selected.shape
            assert source.dtype == selected.dtype
            assert isinstance(source._array, np.memmap)
            sample = source.get_slice(0)
            assert sample.shape == source.metadata.image_shape
            assert sample.dtype == source.dtype
            if source.metadata.pixel_size_xy and source.metadata.pixel_unit_xy:
                calibrated += 1

    assert calibrated >= 1
