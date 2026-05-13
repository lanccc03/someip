from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from someip_gui_tool.gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
