"""Qt-independent numerical and data contracts for STEMCropTool."""

from stem_crop_tool.core.batch import (
    CancellationToken,
    ExportProgress,
    all_slice_indices,
    batch_item_filename,
    current_slice_indices,
    inclusive_slice_range,
    suggested_single_filename,
)
from stem_crop_tool.core.crop import (
    ResizeHandle,
    clamp_rect,
    crop_array,
    rect_from_drag,
    rect_from_fields,
    resize_rect,
    resize_rect_from_handle,
    translate_rect,
    validate_rect_within,
)
from stem_crop_tool.core.dtypes import output_dtype_for
from stem_crop_tool.core.models import (
    CropRect,
    ExportFormat,
    ExportRequest,
    ExportResult,
    ImageMetadata,
    NormalizationMode,
)
from stem_crop_tool.core.normalize import normalize_local_minmax

__all__ = [
    "CancellationToken",
    "CropRect",
    "ExportFormat",
    "ExportProgress",
    "ExportRequest",
    "ExportResult",
    "ImageMetadata",
    "NormalizationMode",
    "ResizeHandle",
    "all_slice_indices",
    "batch_item_filename",
    "clamp_rect",
    "crop_array",
    "current_slice_indices",
    "inclusive_slice_range",
    "normalize_local_minmax",
    "output_dtype_for",
    "rect_from_drag",
    "rect_from_fields",
    "resize_rect",
    "resize_rect_from_handle",
    "suggested_single_filename",
    "translate_rect",
    "validate_rect_within",
]
