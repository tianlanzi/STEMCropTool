"""Qt-backed adapters and operating-system I/O integration."""

from stem_crop_tool.infrastructure.raster_io import RasterImageSource
from stem_crop_tool.infrastructure.source_loader import (
    SUPPORTED_INPUT_EXTENSIONS,
    open_image_source,
)

__all__ = [
    "RasterImageSource",
    "SUPPORTED_INPUT_EXTENSIONS",
    "open_image_source",
]
