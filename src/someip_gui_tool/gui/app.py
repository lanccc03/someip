from __future__ import annotations

import asyncio
import sys

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from someip_gui_tool.gui.backend_factory import create_session
from someip_gui_tool.gui.main_window import MainWindow
from someip_gui_tool.gui.theme import apply_theme


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    session = create_session()
    window = MainWindow(session=session)
    window.show()
    with loop:
        loop.run_forever()
        loop.run_until_complete(session.adapter.shutdown())
    return 0
