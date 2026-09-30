"""Phase 0 import and window smoke tests."""

import numpy as np
import PySide6

from stem_crop_tool import __version__
from stem_crop_tool.app import create_application
from stem_crop_tool.ui.main_window import MainWindow


def test_runtime_dependencies_and_package_import() -> None:
    assert __version__ == "0.1.0"
    assert np.__version__
    assert PySide6.__version__


def test_main_window_opens_and_closes(qtbot) -> None:
    app = create_application([])
    assert not app.windowIcon().isNull()

    window = MainWindow()
    qtbot.addWidget(window)

    window.show()
    qtbot.waitUntil(window.isVisible)

    assert window.windowTitle() == "STEMCropTool"

    window.close()
    assert not window.isVisible()
