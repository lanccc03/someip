from __future__ import annotations

import asyncio
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from someip_gui_tool.gui.backend_factory import create_session
from someip_gui_tool.gui.main_window import MainWindow
from someip_gui_tool.gui.theme import apply_theme


def main(argv: list[str] | None = None) -> int:
    resolved_argv = sys.argv if argv is None else argv
    smoke_exit = "--smoke-exit" in resolved_argv
    qt_argv = [arg for arg in resolved_argv if arg != "--smoke-exit"]
    app = QApplication(qt_argv)
    apply_theme(app)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    session = create_session()
    if smoke_exit:
        QTimer.singleShot(0, app.quit)
    window = MainWindow(session=session)
    window.show()
    with loop:
        loop.run_forever()
        try:
            loop.run_until_complete(session.adapter.shutdown())
        except Exception:
            import traceback

            traceback.print_exc()
    return 0
