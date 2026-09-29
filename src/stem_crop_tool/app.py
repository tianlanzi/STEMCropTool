"""Application bootstrap for the Phase 0 desktop shell."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from stem_crop_tool.ui.main_window import MainWindow


SMOKE_TEST_TIMEOUT_ENV = "STEM_CROP_TOOL_SMOKE_TEST_MS"


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    """Return the process-wide Qt application, creating it when necessary."""

    existing = QApplication.instance()
    if existing is not None:
        return existing

    arguments = list(argv) if argv is not None else sys.argv
    app = QApplication(arguments)
    app.setApplicationName("STEMCropTool")
    app.setOrganizationName("STEMCropTool")
    return app


def _schedule_smoke_test_exit(app: QApplication) -> None:
    """Schedule an opt-in bounded exit used by source and packaged smoke tests."""

    raw_timeout = os.environ.get(SMOKE_TEST_TIMEOUT_ENV)
    if raw_timeout is None:
        return

    try:
        timeout_ms = int(raw_timeout)
    except ValueError as exc:
        raise ValueError(
            f"{SMOKE_TEST_TIMEOUT_ENV} must be a positive integer"
        ) from exc

    if timeout_ms <= 0:
        raise ValueError(f"{SMOKE_TEST_TIMEOUT_ENV} must be a positive integer")

    QTimer.singleShot(timeout_ms, app.quit)


def main(argv: Sequence[str] | None = None) -> int:
    """Start the application and return the Qt event-loop exit code."""

    app = create_application(argv)
    window = MainWindow()
    window.show()
    _schedule_smoke_test_exit(app)
    return app.exec()
