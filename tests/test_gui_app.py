from __future__ import annotations

from types import SimpleNamespace

from someip_gui_tool.gui import app as app_module


def _drive_immediate_coroutine(awaitable) -> None:
    try:
        while True:
            awaitable.send(None)
    except StopIteration:
        return


def test_main_shuts_down_session_adapter(monkeypatch) -> None:
    shutdowns: list[str] = []
    shown: list[str] = []

    class FakeAdapter:
        async def shutdown(self) -> None:
            shutdowns.append("shutdown")

    class FakeLoop:
        def __init__(self, app) -> None:
            self.app = app

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def run_forever(self) -> None:
            self.ran_forever = True

        def run_until_complete(self, awaitable) -> None:
            _drive_immediate_coroutine(awaitable)

    class FakeWindow:
        def __init__(self, *, session) -> None:
            self.session = session

        def show(self) -> None:
            shown.append("show")

    fake_session = SimpleNamespace(adapter=FakeAdapter())

    monkeypatch.setattr(app_module, "QApplication", lambda argv: object())
    monkeypatch.setattr(app_module, "QEventLoop", FakeLoop)
    monkeypatch.setattr(app_module, "MainWindow", FakeWindow)
    monkeypatch.setattr(app_module, "apply_theme", lambda app: None)
    monkeypatch.setattr(app_module, "create_session", lambda: fake_session)
    monkeypatch.setattr(app_module.asyncio, "set_event_loop", lambda loop: None)

    assert app_module.main() == 0

    assert shown == ["show"]
    assert shutdowns == ["shutdown"]
