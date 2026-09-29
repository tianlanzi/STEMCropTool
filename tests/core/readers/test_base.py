from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from stem_crop_tool.core.models import ImageMetadata
from stem_crop_tool.core.readers.base import ImageDocument


class FakeSource:
    def __init__(self, name: str) -> None:
        self.name = name
        self.shape = (2, 2)
        self.dtype = np.dtype(np.uint8)
        self.ndim = 2
        self.slice_count = 1
        self.metadata = ImageMetadata(name, "npy", self.shape, self.dtype)
        self.close_count = 0

    def get_slice(self, index: int = 0) -> np.ndarray:
        return np.zeros(self.shape, dtype=self.dtype)

    def close(self) -> None:
        self.close_count += 1


def test_document_closes_replaced_and_final_sources() -> None:
    first = FakeSource("first.npy")
    second = FakeSource("second.npy")
    document = ImageDocument()

    assert document.replace_source(first) is first
    assert document.replace_source(second) is second
    assert first.close_count == 1
    assert second.close_count == 0

    document.close()
    document.close()
    assert second.close_count == 1


def test_failed_open_preserves_current_source() -> None:
    first = FakeSource("first.npy")
    document = ImageDocument()
    document.replace_source(first)

    def fail(_: str | Path, **__: object) -> FakeSource:
        raise RuntimeError("open failed")

    with pytest.raises(RuntimeError, match="open failed"):
        document.open_with(fail, "bad.npy")

    assert document.source is first
    assert first.close_count == 0
