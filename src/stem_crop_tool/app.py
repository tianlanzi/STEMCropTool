"""Application bootstrap for STEMCropTool."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from collections.abc import Sequence

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from stem_crop_tool.release_self_test import (
    run_release_self_test,
    write_failure_report,
)
from stem_crop_tool.ui.main_window import MainWindow


SMOKE_TEST_TIMEOUT_ENV = "STEM_CROP_TOOL_SMOKE_TEST_MS"
RELEASE_SELF_TEST_DIR_ENV = "STEM_CROP_TOOL_SELF_TEST_DIR"
EXTERNAL_TEST_DATA_ENV = "STEM_CROP_TOOL_TEST_DATA"
ICON_PATH = Path(__file__).resolve().parent / "assets" / "app_icon.ico"


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    """Return the process-wide Qt application, creating it when necessary."""

    existing = QApplication.instance()
    if existing is None:
        arguments = list(argv) if argv is not None else sys.argv
        app = QApplication(arguments)
    else:
        app = existing
    app.setApplicationName("STEMCropTool")
    app.setOrganizationName("STEMCropTool")
    icon = QIcon(str(ICON_PATH))
    if not icon.isNull():
        app.setWindowIcon(icon)
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
    self_test_dir = os.environ.get(RELEASE_SELF_TEST_DIR_ENV)
    if self_test_dir:
        try:
            run_release_self_test(
                self_test_dir,
                external_data_dir=os.environ.get(EXTERNAL_TEST_DATA_ENV),
            )
        except Exception as exc:
            write_failure_report(self_test_dir, exc)
            return 1
        else:
            return 0
    window = MainWindow()
    window.show()
    _schedule_smoke_test_exit(app)
    return app.exec()
