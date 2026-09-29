from __future__ import annotations

import numpy as np
import pytest

from stem_crop_tool.core.exceptions import UnsupportedFileFormatError
from stem_crop_tool.core.readers.npy import NpyImageSource
from stem_crop_tool.infrastructure.source_loader import open_image_source


def test_loader_dispatches_npy_case_insensitively(tmp_path) -> None:
    path = tmp_path / "IMAGE.NPY"
    with path.open("wb") as stream:
        np.save(stream, np.zeros((2, 3), dtype=np.uint8))

    source = open_image_source(path)
    try:
        assert isinstance(source, NpyImageSource)
    finally:
        source.close()


def test_loader_rejects_unsupported_and_extensionless_paths(tmp_path) -> None:
    with pytest.raises(UnsupportedFileFormatError, match="unsupported"):
        open_image_source(tmp_path / "image.tiff")
    with pytest.raises(UnsupportedFileFormatError, match="<none>"):
        open_image_source(tmp_path / "image")


def test_loader_rejects_dataset_index_for_non_dm_source(tmp_path) -> None:
    path = tmp_path / "image.npy"
    np.save(path, np.zeros((2, 2), dtype=np.uint8))

    with pytest.raises(ValueError, match="only valid for DM"):
        open_image_source(path, dataset_index=0)
