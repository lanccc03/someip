from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from someip_gui_tool.gui.main_window import MainWindow
from someip_gui_tool.gui.theme import apply_theme


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()
