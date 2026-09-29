"""Minimal Phase 0 main window."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow


class MainWindow(QMainWindow):
    """Application shell used to validate the desktop and packaging stack."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("STEMCropTool")
        self.resize(960, 640)

        placeholder = QLabel("STEMCropTool\nPhase 0 application shell")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(placeholder)
        self.statusBar().showMessage("Ready")
