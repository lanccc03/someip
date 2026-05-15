from __future__ import annotations

import asyncio
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
    def __init__(self, *, connect_sleep: float | None = None) -> None:
        self.connect_sleep = connect_sleep
        self.connect_started_count = 0
        self.connect_configs: list[dict[str, object]] = []
        self.daemon = FakeDaemon()

    async def connect_to_someipy_daemon(self, config: dict[str, object]) -> FakeDaemon:
        self.connect_started_count += 1
        if self.connect_sleep is not None:
            await asyncio.sleep(self.connect_sleep)
        self.connect_configs.append(config)
        return self.daemon


class SyncDisconnectDaemon:
    def __init__(self) -> None:
        self.disconnected = False

    def disconnect_from_daemon(self) -> None:
        self.disconnected = True


class SyncDisconnectApi:
    def __init__(self) -> None:
        self.connect_configs: list[dict[str, object]] = []
        self.daemon = SyncDisconnectDaemon()

    async def connect_to_someipy_daemon(self, config: dict[str, object]) -> SyncDisconnectDaemon:
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
async def test_someipy_adapter_repeated_start_service_reuses_daemon(adc40_soc_dir) -> None:
    api = FakeApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(service)
    await adapter.start_service(service)

    assert api.connect_started_count == 1
    assert len(api.connect_configs) == 1


@pytest.mark.asyncio
async def test_someipy_adapter_concurrent_start_service_reuses_daemon(adc40_soc_dir) -> None:
    api = FakeApi(connect_sleep=0)
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await asyncio.gather(adapter.start_service(service), adapter.start_service(service))

    assert api.connect_started_count == 1
    assert len(api.connect_configs) == 1


@pytest.mark.asyncio
async def test_someipy_adapter_reports_ff_method_limited(adc40_soc_dir) -> None:
    adapter = SomeipyAdapter(api=FakeApi(), local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080D.json")

    result = await adapter.call_method(service, service.methods[0], b"\x01")

    assert result.status == "limited"
    assert "fire-and-forget" in result.detail


@pytest.mark.asyncio
async def test_someipy_adapter_find_service_returns_false_after_connecting(adc40_soc_dir) -> None:
    api = FakeApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    result = await adapter.find_service(service)

    assert result is False
    assert api.connect_started_count == 1


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
async def test_someipy_adapter_field_get_returns_unimplemented_error_with_getter(adc40_soc_dir) -> None:
    api = FakeApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080C.json")

    result = await adapter.field_get(service, service.fields[0], b"\x07")

    assert result.status == "error"
    assert "not implemented in Phase A adapter skeleton" in result.detail
    assert result.payload is None
    assert api.connect_started_count == 1


@pytest.mark.asyncio
async def test_someipy_adapter_field_set_returns_unimplemented_error_with_setter(adc40_soc_dir) -> None:
    api = FakeApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    field = replace(service.fields[0], setter=service.fields[0].getter)

    result = await adapter.field_set(service, field, b"\x08")

    assert result.status == "error"
    assert "not implemented in Phase A adapter skeleton" in result.detail
    assert result.payload is None
    assert api.connect_started_count == 1


@pytest.mark.asyncio
async def test_someipy_adapter_protocol_actions_raise_not_implemented(adc40_soc_dir) -> None:
    api = FakeApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=30500)
    event_service = load_service_definition(adc40_soc_dir / "0x080E.json")
    field_service = load_service_definition(adc40_soc_dir / "0x080C.json")
    event = event_service.events[0]
    field = field_service.fields[0]

    with pytest.raises(NotImplementedError, match="subscribe_eventgroup.*Phase A adapter skeleton"):
        await adapter.subscribe_eventgroup(event_service, event.eventgroup_id or 0)
    with pytest.raises(NotImplementedError, match="publish_event.*Phase A adapter skeleton"):
        await adapter.publish_event(event_service, event, b"\x01")
    with pytest.raises(NotImplementedError, match="field_notify.*Phase A adapter skeleton"):
        await adapter.field_notify(field_service, field, b"\x02")

    assert api.connect_started_count == 1


@pytest.mark.asyncio
async def test_someipy_adapter_unsubscribe_raises_not_implemented(adc40_soc_dir) -> None:
    api = FakeApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]

    with pytest.raises(NotImplementedError, match="unsubscribe_eventgroup.*Phase A adapter skeleton"):
        await adapter.unsubscribe_eventgroup(service, event.eventgroup_id or 0)

    assert api.connect_started_count == 1


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


@pytest.mark.asyncio
async def test_someipy_adapter_stop_service_clears_service_handlers(adc40_soc_dir) -> None:
    adapter = SomeipyAdapter(api=FakeApi(), local_ip="127.0.0.1", base_port=30500)
    event_service = load_service_definition(adc40_soc_dir / "0x080E.json")
    field_service = load_service_definition(adc40_soc_dir / "0x080C.json")

    await adapter.register_event_handler(event_service, event_service.events[0], lambda event: None)
    await adapter.register_field_notifier_handler(field_service, field_service.fields[0], lambda event: None)
    await adapter.stop_service(event_service)

    assert all(service_id != event_service.service_id for service_id, element_id in adapter._event_handlers)
    assert adapter._event_handlers


@pytest.mark.asyncio
async def test_someipy_adapter_shutdown_clears_handlers_and_daemon(adc40_soc_dir) -> None:
    api = SyncDisconnectApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.register_event_handler(service, service.events[0], lambda event: None)
    await adapter.start_service(service)
    await adapter.shutdown()

    assert adapter._event_handlers == {}
    assert adapter._daemon is None
    assert api.daemon.disconnected is True
