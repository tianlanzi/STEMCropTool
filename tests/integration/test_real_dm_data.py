from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from stem_crop_tool.core.readers.dm import DMImageSource, list_dm_datasets
from stem_crop_tool.ui.main_window import MainWindow


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


def test_available_real_dm3_and_dm4_open_in_gui(qtbot) -> None:
    raw_root = os.environ.get(TEST_DATA_ENV)
    if not raw_root:
        pytest.skip(f"set {TEST_DATA_ENV} to run external real-data tests")
    root = Path(raw_root)
    if not root.is_dir():
        pytest.skip(f"external test-data directory does not exist: {root}")

    paths = []
    for suffix in ("*.dm3", "*.dm4"):
        matching = sorted(root.glob(suffix))
        assert matching, f"no {suffix} fixture in {root}"
        paths.append(matching[0])

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    for path in paths:
        selected = next(info for info in list_dm_datasets(path) if info.supported)
        window.open_path(path, dataset_index=selected.index)
        qtbot.waitUntil(lambda: not window.is_loading, timeout=10000)
        qtbot.waitUntil(lambda: window.loading_job_count == 0, timeout=10000)
        assert window.current_source is not None
        assert window.current_source.metadata.source_name == path.name
        assert window.image_view.source_index == 0
