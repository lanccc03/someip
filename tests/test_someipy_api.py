from types import SimpleNamespace

from someip_gui_tool.adapters.someipy_api import SomeipyApiProbe, SomeipyApiStatus


def test_api_probe_reports_missing_module(monkeypatch):
    probe = SomeipyApiProbe(importer=lambda name: (_ for _ in ()).throw(ModuleNotFoundError(name)))

    status = probe.probe()

    assert status.available is False
    assert "not installed" in status.detail
    assert "python -m pip install -e .[someipy]" in status.detail


def test_api_probe_reports_missing_symbols():
    fake = SimpleNamespace(ServiceBuilder=object)
    probe = SomeipyApiProbe(importer=lambda name: fake)

    status = probe.probe()

    assert status.available is False
    assert "missing" in status.detail
    assert "ClientServiceInstance" in status.detail


def test_api_probe_returns_module_when_required_symbols_exist():
    names = [
        "ServiceBuilder",
        "Method",
        "Event",
        "EventGroup",
        "TransportLayerProtocol",
        "ClientServiceInstance",
        "ServerServiceInstance",
        "connect_to_someipy_daemon",
    ]
    fake = SimpleNamespace(**{name: object() for name in names})
    probe = SomeipyApiProbe(importer=lambda name: fake)

    status = probe.probe()
    module = probe.require_module()

    assert isinstance(status, SomeipyApiStatus)
    assert status.available is True
    assert status.detail == "someipy API is available"
    assert module is fake
