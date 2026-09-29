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
