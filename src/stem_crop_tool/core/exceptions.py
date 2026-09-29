"""Application-specific exceptions raised by the numerical core."""


class STEMCropError(Exception):
    """Base exception for expected STEMCropTool failures."""


class InvalidCropRectError(STEMCropError, ValueError):
    """Raised when a crop rectangle is invalid for an image."""


class UnsupportedArrayShapeError(STEMCropError, ValueError):
    """Raised when an array shape or dimensionality is unsupported."""


class UnsupportedDTypeError(STEMCropError, TypeError):
    """Raised when a source or output dtype is unsupported."""


class NonFiniteNormalizationError(STEMCropError, ValueError):
    """Raised when normalized export encounters NaN or infinity."""


class SourceError(STEMCropError):
    """Base exception for expected image-source failures."""


class SourceOpenError(SourceError):
    """Raised when a source cannot be opened or parsed."""


class SourceClosedError(SourceError, RuntimeError):
    """Raised when pixel data is requested from a closed source."""


class UnsupportedFileFormatError(SourceError, ValueError):
    """Raised when a path has no supported input reader."""


class InvalidSliceIndexError(SourceError, IndexError):
    """Raised when a requested stack slice is outside the source."""


class DatasetSelectionRequiredError(SourceError):
    """Raised when a DM file has multiple supported image datasets."""

    def __init__(self, dataset_indices: tuple[int, ...]) -> None:
        self.dataset_indices = dataset_indices
        joined = ", ".join(str(index) for index in dataset_indices)
        super().__init__(f"select one DM dataset index: {joined}")


class NoSupportedDatasetError(SourceError):
    """Raised when a DM file contains no supported 2D/3D image dataset."""


class ExportError(STEMCropError):
    """Base exception for expected export failures."""


class ExportValidationError(ExportError, ValueError):
    """Raised when an export request conflicts with the source or format."""


class OutputExistsError(ExportError, FileExistsError):
    """Raised when export would overwrite a path without permission."""


class ExportWriteError(ExportError, OSError):
    """Raised when an output file cannot be encoded or committed."""
