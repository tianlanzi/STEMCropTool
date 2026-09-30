"""Application-wide visual styling for the desktop interface."""

from __future__ import annotations


APPLICATION_STYLESHEET = """
QMainWindow,
QWidget#central_panel {
    background: #f3f5f6;
    color: #263238;
}

QMenuBar {
    background: #fafbfb;
    border-bottom: 1px solid #d9dfe3;
    padding: 2px 8px;
}
QMenuBar::item {
    border-radius: 4px;
    padding: 5px 10px;
}
QMenuBar::item:selected {
    background: #e8f4f4;
}
QMenu {
    background: #ffffff;
    border: 1px solid #d5dce0;
    padding: 5px;
}
QMenu::item {
    border-radius: 4px;
    padding: 6px 28px 6px 10px;
}
QMenu::item:selected {
    background: #dff1f1;
    color: #173f41;
}

QToolBar#main_toolbar {
    background: #fafbfb;
    border: none;
    border-bottom: 1px solid #d9dfe3;
    spacing: 3px;
    padding: 5px 8px;
}
QToolBar#main_toolbar::separator {
    background: #d9dfe3;
    width: 1px;
    margin: 5px 7px;
}
QToolBar#main_toolbar QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    color: #344047;
    padding: 5px 8px;
}
QToolBar#main_toolbar QToolButton:hover {
    background: #e8f4f4;
    border-color: #c7e3e3;
}
QToolBar#main_toolbar QToolButton:pressed {
    background: #d4ecec;
}
QToolBar#main_toolbar QToolButton:disabled {
    color: #9ca6ac;
}

QGraphicsView#image_view {
    border: 1px solid #1d2226;
    border-radius: 4px;
}
QGraphicsView#image_view[dropActive="true"] {
    border: 2px solid #4cc3c5;
}
QWidget#empty_state {
    background: rgba(38, 44, 50, 224);
    border: 1px solid #535d65;
    border-radius: 12px;
}
QWidget#empty_state[dropActive="true"] {
    background: rgba(30, 79, 81, 235);
    border: 2px solid #62d0d1;
}
QLabel#empty_state_title {
    color: #f2f5f6;
    font-size: 18px;
    font-weight: 600;
}
QLabel#empty_state_subtitle {
    color: #bdc6cb;
    font-size: 12px;
}
QLabel#empty_state_formats {
    color: #79d1d2;
    font-size: 11px;
    font-weight: 600;
}

QWidget#stack_controls {
    background: #ffffff;
    border: 1px solid #d9dfe3;
    border-radius: 6px;
}
QGroupBox#crop_controls {
    background: #ffffff;
    border: 1px solid #d4dce0;
    border-radius: 7px;
    margin-top: 9px;
    padding-top: 8px;
    font-weight: 600;
}
QGroupBox#crop_controls::title {
    color: #46545c;
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QGroupBox#crop_controls QLabel {
    color: #536169;
    font-weight: 400;
}
QLabel#crop_summary {
    color: #7a858c;
    font-size: 11px;
}

QSpinBox {
    background: #ffffff;
    border: 1px solid #cfd7dc;
    border-radius: 5px;
    padding: 4px 6px;
    min-height: 20px;
}
QSpinBox:focus {
    border: 1px solid #35aeb0;
}
QSpinBox:disabled {
    background: #f0f2f3;
    color: #9aa4aa;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #cbd4d9;
    border-radius: 5px;
    color: #344047;
    min-height: 22px;
    padding: 4px 14px;
}
QPushButton:hover {
    background: #e8f4f4;
    border-color: #8bc9ca;
}
QPushButton:pressed {
    background: #d6eeee;
}
QPushButton:disabled {
    background: #f1f3f4;
    color: #a1a9ae;
}
QPushButton#export_crop_button:enabled {
    background: #258f92;
    border-color: #258f92;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#export_crop_button:hover {
    background: #217f82;
    border-color: #217f82;
}
QPushButton#export_crop_button:pressed {
    background: #1c7072;
}

QStatusBar {
    background: #fafbfb;
    border-top: 1px solid #d9dfe3;
    color: #59666d;
}
QStatusBar QLabel {
    padding: 1px 6px;
}
QProgressBar {
    border: 1px solid #cbd4d9;
    border-radius: 3px;
    background: #edf0f2;
}
QProgressBar::chunk {
    background: #38aeb0;
}
"""
