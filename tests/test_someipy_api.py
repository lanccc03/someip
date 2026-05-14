from types import SimpleNamespace

import pytest

from someip_gui_tool.adapters.someipy_api import SomeipyApiProbe, SomeipyApiStatus


def test_api_probe_reports_missing_module(monkeypatch):
    probe = SomeipyApiProbe(
        importer=lambda name: (_ for _ in ()).throw(ModuleNotFoundError(name=name))
    )

    status = probe.probe()

    assert status.available is False
    assert "not installed" in status.detail
    assert "python -m pip install -e .[someipy]" in status.detail


def test_api_probe_reports_missing_dependency():
    probe = SomeipyApiProbe(
        importer=lambda name: (_ for _ in ()).throw(ModuleNotFoundError(name="missing_dep"))
    )

    status = probe.probe()

    assert status.available is False
    assert "not installed" not in status.detail
    assert "missing dependency" in status.detail
    assert "missing_dep" in status.detail


def test_api_probe_reports_generic_import_error():
    probe = SomeipyApiProbe(importer=lambda name: (_ for _ in ()).throw(ImportError("broken install")))

    status = probe.probe()

    assert status.available is False
    assert "someipy import failed" in status.detail
    assert "broken install" in status.detail


def test_api_probe_reports_lazy_symbol_import_error():
    class FakeLazyApi:
        def __getattr__(self, name):
            if name == "Method":
                raise ImportError("lazy broken")
            return object()

    probe = SomeipyApiProbe(importer=lambda name: FakeLazyApi())

    status = probe.probe()

    assert status.available is False
    assert "someipy API symbol Method import failed" in status.detail
    assert "lazy broken" in status.detail


def test_api_probe_reports_lazy_symbol_missing_dependency():
    class FakeLazyApi:
        def __getattr__(self, name):
            if name == "Method":
                raise ModuleNotFoundError(name="missing_lazy_dep")
            return object()

    probe = SomeipyApiProbe(importer=lambda name: FakeLazyApi())

    status = probe.probe()

    assert status.available is False
    assert "missing dependency" in status.detail
    assert "missing_lazy_dep" in status.detail


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


def test_api_probe_clears_stale_module_after_failed_probe():
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
    full_api = SimpleNamespace(**{name: object() for name in names})
    incomplete_api = SimpleNamespace(ServiceBuilder=object)
    modules = iter([full_api, incomplete_api, incomplete_api])
    probe = SomeipyApiProbe(importer=lambda name: next(modules))

    available_status = probe.probe()
    failed_status = probe.probe()

    assert available_status.available is True
    assert failed_status.available is False
    with pytest.raises(RuntimeError):
        probe.require_module()
