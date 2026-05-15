from __future__ import annotations

from dataclasses import replace

import pytest

from someip_gui_tool.adapters.base import SomeIpAdapter
from someip_gui_tool.adapters.someipy_adapter import SomeipyAdapter
from someip_gui_tool.parsing.service_json import load_service_definition


class FakeDaemon:
    def __init__(self) -> None:
        self.disconnected = False

    async def disconnect_from_daemon(self) -> None:
        self.disconnected = True


class FakeApi:
    def __init__(self) -> None:
        self.connect_configs: list[dict[str, object]] = []
        self.daemon = FakeDaemon()

    async def connect_to_someipy_daemon(self, config: dict[str, object]) -> FakeDaemon:
        self.connect_configs.append(config)
        return self.daemon


@pytest.mark.asyncio
async def test_someipy_adapter_connects_with_client_config(adc40_soc_dir) -> None:
    api = FakeApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(service)
    await adapter.shutdown()

    assert api.connect_configs == [
        {
            "use_tcp": True,
            "tcp_host": "127.0.0.1",
            "tcp_port": 30500,
        }
    ]
    assert api.daemon.disconnected is True


@pytest.mark.asyncio
async def test_someipy_adapter_reports_ff_method_limited(adc40_soc_dir) -> None:
    adapter = SomeipyAdapter(api=FakeApi(), local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080D.json")

    result = await adapter.call_method(service, service.methods[0], b"\x01")

    assert result.status == "limited"
    assert "fire-and-forget" in result.detail


def test_someipy_adapter_is_someip_adapter_implementation() -> None:
    adapter = SomeipyAdapter(api=FakeApi(), local_ip="127.0.0.1", base_port=30500)

    assert isinstance(adapter, SomeIpAdapter)


@pytest.mark.asyncio
async def test_someipy_adapter_field_set_returns_error_without_setter(adc40_soc_dir) -> None:
    adapter = SomeipyAdapter(api=FakeApi(), local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080C.json")

    result = await adapter.field_set(service, service.fields[0], b"\x06")

    assert result.status == "error"
    assert "setter" in result.detail


@pytest.mark.asyncio
async def test_someipy_adapter_register_field_notifier_handler_uses_notifier_id(adc40_soc_dir) -> None:
    adapter = SomeipyAdapter(api=FakeApi(), local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    field = service.fields[0]
    received = []

    await adapter.register_field_notifier_handler(service, field, received.append)

    assert field.notifier is not None
    assert adapter._event_handlers[(service.service_id, field.notifier.element_id)] == [received.append]


@pytest.mark.asyncio
async def test_someipy_adapter_register_field_notifier_handler_raises_without_notifier(
    adc40_soc_dir,
) -> None:
    adapter = SomeipyAdapter(api=FakeApi(), local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    field = replace(service.fields[0], notifier=None)

    with pytest.raises(ValueError, match="notifier"):
        await adapter.register_field_notifier_handler(service, field, lambda event: None)
