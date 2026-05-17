import pytest

from someip_gui_tool.adapters.mock import MockSomeIpAdapter
from someip_gui_tool.adapters.someipy_adapter import SomeipyAdapter
from someip_gui_tool.gui.backend_factory import BackendSettings, create_session


def test_create_session_defaults_to_mock_backend() -> None:
    session = create_session(BackendSettings())

    assert isinstance(session.adapter, MockSomeIpAdapter)


def test_create_session_can_select_someipy_backend() -> None:
    session = create_session(
        BackendSettings(
            backend="someipy",
            local_ip="127.0.0.1",
            base_port=30500,
            start_daemon=True,
        )
    )

    assert isinstance(session.adapter, SomeipyAdapter)
    assert session.adapter._local_ip == "127.0.0.1"
    assert session.adapter._base_port == 30500
    assert session.adapter._start_daemon is True


def test_create_session_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="Unsupported backend"):
        create_session(BackendSettings(backend="internal"))


def test_backend_settings_from_env() -> None:
    settings = BackendSettings.from_env(
        {
            "SOMEIP_GUI_BACKEND": "someipy",
            "SOMEIP_GUI_LOCAL_IP": "192.168.0.10",
            "SOMEIP_GUI_BASE_PORT": "31000",
            "SOMEIP_GUI_START_DAEMON": "true",
        }
    )

    assert settings == BackendSettings(
        backend="someipy",
        local_ip="192.168.0.10",
        base_port=31000,
        start_daemon=True,
    )
