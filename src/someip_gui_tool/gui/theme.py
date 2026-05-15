"""Design tokens and theme application for the SOME/IP test tool."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

COLORS = {
    "app_background": "#F6F7F9",
    "surface": "#FFFFFF",
    "surface_muted": "#EEF2F5",
    "border": "#D8DEE6",
    "text_primary": "#1F2933",
    "text_secondary": "#667085",
    "text_disabled": "#98A2B3",
    "primary": "#087F8C",
    "primary_hover": "#066C77",
    "primary_subtle": "#DDF4F2",
    "link": "#3B5BDB",
    "success": "#178C55",
    "warning": "#B7791F",
    "danger": "#C2410C",
    "running": "#0E7490",
    "focus": "#7DD3FC",
}


def apply_theme(app: QApplication) -> None:
    """Apply the default light engineering theme to *app*."""
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(_stylesheet())


def monospace_font(point_size: int = 9) -> QFont:
    """Return the standard monospace font used for IDs, hex, and log output."""
    font = QFont("Consolas", point_size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


def _stylesheet() -> str:
    return f"""
/* ── Root surface ─────────────────────────────────────── */
QMainWindow {{
    background: {COLORS["app_background"]};
    color: {COLORS["text_primary"]};
}}

/* ── Service tree ─────────────────────────────────────── */
QTreeWidget {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    outline: none;
}}

QTreeWidget::item {{
    padding: 5px 8px;
    border-radius: 4px;
}}

QTreeWidget::item:hover {{
    background: {COLORS["surface_muted"]};
}}

QTreeWidget::item:selected {{
    background: {COLORS["primary_subtle"]};
    color: {COLORS["text_primary"]};
}}

QHeaderView::section {{
    background: {COLORS["surface_muted"]};
    color: {COLORS["text_secondary"]};
    border: none;
    border-bottom: 1px solid {COLORS["border"]};
    padding: 6px 8px;
    font-weight: 600;
}}

/* ── Panel cards (Runtime / Operation) ────────────────── */
QGroupBox {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    margin-top: 14px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 12px;
    top: 2px;
    color: {COLORS["text_primary"]};
}}

/* Form labels inside panels */
QGroupBox#runtime_panel QLabel {{
    color: {COLORS["text_secondary"]};
    font-weight: 400;
}}

/* ── Buttons ──────────────────────────────────────────── */
QPushButton {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 6px 14px;
    min-height: 20px;
}}

QPushButton:hover {{
    border-color: {COLORS["primary"]};
}}

QPushButton:pressed {{
    background: {COLORS["primary_subtle"]};
}}

QPushButton:disabled {{
    color: {COLORS["text_disabled"]};
    background: {COLORS["surface_muted"]};
}}

QPushButton[primary="true"] {{
    background: {COLORS["primary"]};
    border-color: {COLORS["primary"]};
    color: #FFFFFF;
}}

QPushButton[primary="true"]:hover {{
    background: {COLORS["primary_hover"]};
}}

QPushButton[primary="true"]:pressed {{
    background: {COLORS["primary_hover"]};
}}

QPushButton[primary="true"]:disabled {{
    background: {COLORS["text_disabled"]};
    border-color: {COLORS["text_disabled"]};
    color: #FFFFFF;
}}

/* ── Input fields ─────────────────────────────────────── */
QLineEdit, QComboBox {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 5px;
    padding: 5px 8px;
}}

QLineEdit:focus, QComboBox:focus {{
    border-color: {COLORS["primary"]};
}}

QLineEdit:disabled, QComboBox:disabled {{
    color: {COLORS["text_disabled"]};
    background: {COLORS["surface_muted"]};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border: none;
    border-left: 1px solid {COLORS["border"]};
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
}}

QComboBox QAbstractItemView {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    selection-background-color: {COLORS["primary_subtle"]};
    selection-color: {COLORS["text_primary"]};
}}

/* ── Bottom tabs ──────────────────────────────────────── */
QTabWidget::pane {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-top: none;
    border-radius: 0 0 6px 6px;
    top: -1px;
}}

QTabBar::tab {{
    background: {COLORS["surface_muted"]};
    color: {COLORS["text_secondary"]};
    border: 1px solid {COLORS["border"]};
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    padding: 7px 16px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background: {COLORS["surface"]};
    color: {COLORS["primary"]};
    border-bottom: 2px solid {COLORS["primary"]};
}}

QTabBar::tab:hover:!selected {{
    color: {COLORS["text_primary"]};
}}

/* ── Log / trace / details views ──────────────────────── */
QPlainTextEdit {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 8px;
    selection-background-color: {COLORS["primary_subtle"]};
}}

/* ── Status bar ───────────────────────────────────────── */
QStatusBar {{
    background: {COLORS["surface_muted"]};
    color: {COLORS["text_secondary"]};
    border-top: 1px solid {COLORS["border"]};
}}

/* ── Splitter ─────────────────────────────────────────── */
QSplitter::handle {{
    background: {COLORS["border"]};
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}
"""
