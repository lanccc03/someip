from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from someip_gui_tool.adapters.base import SomeIpAdapter
from someip_gui_tool.adapters.someipy_adapter import SomeipyAdapter
from someip_gui_tool.parsing.service_json import load_service_definition
from tests.fakes_someipy_runtime import FakeSomeipyApi


@pytest.mark.asyncio
async def test_someipy_adapter_connects_with_client_config(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
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
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(service)
    await adapter.start_service(service)

    assert api.connect_started_count == 1
    assert len(api.connect_configs) == 1


@pytest.mark.asyncio
async def test_someipy_adapter_concurrent_start_service_reuses_daemon(adc40_soc_dir) -> None:
    api = FakeSomeipyApi(connect_sleep=0)
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await asyncio.gather(adapter.start_service(service), adapter.start_service(service))

    assert api.connect_started_count == 1
    assert len(api.connect_configs) == 1


@pytest.mark.asyncio
async def test_someipy_adapter_reports_ff_method_limited(adc40_soc_dir) -> None:
    adapter = SomeipyAdapter(api=FakeSomeipyApi(), local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080D.json")

    result = await adapter.call_method(service, service.methods[0], b"\x01")

    assert result.status == "limited"
    assert "fire-and-forget" in result.detail


@pytest.mark.asyncio
async def test_someipy_adapter_find_service_polls_client_availability(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    api = FakeSomeipyApi(availability_sequences={service.service_id: [False, True]})
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)

    result = await adapter.find_service(service)

    assert result is True
    assert api.availability_calls[service.service_id] == 2


def test_someipy_adapter_is_someip_adapter_implementation() -> None:
    adapter = SomeipyAdapter(api=FakeSomeipyApi(), local_ip="127.0.0.1", base_port=30500)

    assert isinstance(adapter, SomeIpAdapter)


@pytest.mark.asyncio
async def test_someipy_adapter_field_set_returns_error_without_setter(adc40_soc_dir) -> None:
    adapter = SomeipyAdapter(api=FakeSomeipyApi(), local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080C.json")

    result = await adapter.field_set(service, service.fields[0], b"\x06")

    assert result.status == "error"
    assert "setter" in result.detail


@pytest.mark.asyncio
async def test_someipy_adapter_field_get_calls_getter_method_and_returns_payload(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    field = service.fields[0]

    result = await adapter.field_get(service, field, b"\x07")

    assert result.status == "success"
    assert result.detail == "someipy field getter completed"
    assert result.payload == b"\x07"
    assert api.connect_started_count == 1


@pytest.mark.asyncio
async def test_someipy_adapter_field_set_returns_unimplemented_error_with_setter(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    field = replace(service.fields[0], setter=service.fields[0].getter)

    result = await adapter.field_set(service, field, b"\x08")

    assert result.status == "error"
    assert "not implemented in Phase A adapter skeleton" in result.detail
    assert result.payload is None
    assert api.connect_started_count == 1


@pytest.mark.asyncio
async def test_someipy_adapter_field_notify_sends_notifier_event(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    field = service.fields[0]
    assert field.notifier is not None

    await adapter.field_notify(service, field, b"\x09")

    assert api.servers[0].sent_events == [
        (field.notifier.eventgroup_id, field.notifier.element_id, b"\x09")
    ]


@pytest.mark.asyncio
async def test_someipy_adapter_dispatches_field_notifier_to_registered_handlers(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    field = service.fields[0]
    assert field.notifier is not None
    assert field.notifier.eventgroup_id is not None
    received = []

    await adapter.register_field_notifier_handler(service, field, received.append)
    await adapter.subscribe_eventgroup(service, field.notifier.eventgroup_id)
    await adapter.field_notify(service, field, b"\x01")

    assert len(received) == 1
    assert received[0].service_id == service.service_id
    assert received[0].element_id == field.notifier.element_id
    assert received[0].eventgroup_id == field.notifier.eventgroup_id
    assert received[0].payload == b"\x01"


@pytest.mark.asyncio
async def test_someipy_adapter_publish_event_sends_payload(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]
    assert event.eventgroup_id is not None
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)

    await adapter.publish_event(service, event, b"\x41\x48\x00\x00\x42\xc6\x80\x00")

    assert api.servers[0].sent_events == [
        (event.eventgroup_id, event.event_id, b"\x41\x48\x00\x00\x42\xc6\x80\x00")
    ]


@pytest.mark.asyncio
async def test_someipy_adapter_dispatches_received_event_to_registered_handlers(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]
    assert event.eventgroup_id is not None
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    received = []

    await adapter.register_event_handler(service, event, received.append)
    await adapter.subscribe_eventgroup(service, event.eventgroup_id)
    await adapter.publish_event(service, event, b"\x01\x02\x03\x04")

    assert len(received) == 1
    assert received[0].service_id == service.service_id
    assert received[0].element_id == event.event_id
    assert received[0].eventgroup_id == event.eventgroup_id
    assert received[0].payload == b"\x01\x02\x03\x04"


@pytest.mark.asyncio
async def test_someipy_adapter_subscribes_eventgroup_with_service_ttl(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]
    assert event.eventgroup_id is not None
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)

    await adapter.subscribe_eventgroup(service, event.eventgroup_id)

    assert api.clients[0].subscribed_eventgroups == [
        (event.eventgroup_id, int(service.deployment.find_ttl_s))
    ]
    assert adapter._service_runtimes[service.service_id].active_eventgroups == {event.eventgroup_id}


@pytest.mark.asyncio
async def test_someipy_adapter_unsubscribes_eventgroup(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]
    assert event.eventgroup_id is not None
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)

    await adapter.subscribe_eventgroup(service, event.eventgroup_id)
    await adapter.unsubscribe_eventgroup(service, event.eventgroup_id)

    assert api.clients[0].unsubscribed_eventgroups == [event.eventgroup_id]
    assert adapter._service_runtimes[service.service_id].active_eventgroups == set()


@pytest.mark.asyncio
async def test_someipy_adapter_register_field_notifier_handler_uses_notifier_id(adc40_soc_dir) -> None:
    adapter = SomeipyAdapter(api=FakeSomeipyApi(), local_ip="127.0.0.1", base_port=30500)
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
    adapter = SomeipyAdapter(api=FakeSomeipyApi(), local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    field = replace(service.fields[0], notifier=None)

    with pytest.raises(ValueError, match="notifier"):
        await adapter.register_field_notifier_handler(service, field, lambda event: None)


@pytest.mark.asyncio
async def test_someipy_adapter_stop_service_clears_service_handlers(adc40_soc_dir) -> None:
    adapter = SomeipyAdapter(api=FakeSomeipyApi(), local_ip="127.0.0.1", base_port=30500)
    event_service = load_service_definition(adc40_soc_dir / "0x080E.json")
    field_service = load_service_definition(adc40_soc_dir / "0x080C.json")

    await adapter.register_event_handler(event_service, event_service.events[0], lambda event: None)
    await adapter.register_field_notifier_handler(field_service, field_service.fields[0], lambda event: None)
    await adapter.stop_service(event_service)

    assert all(service_id != event_service.service_id for service_id, element_id in adapter._event_handlers)
    assert adapter._event_handlers


@pytest.mark.asyncio
async def test_someipy_adapter_shutdown_clears_handlers_and_daemon(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.register_event_handler(service, service.events[0], lambda event: None)
    await adapter.start_service(service)
    await adapter.shutdown()

    assert adapter._event_handlers == {}
    assert adapter._daemon is None
    assert api.daemon.disconnected is True


@pytest.mark.asyncio
async def test_someipy_adapter_start_service_creates_server_and_client_instances(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(service)

    assert api.connect_started_count == 1
    assert len(api.servers) == 1
    assert len(api.clients) == 1
    assert api.servers[0].service.id == service.service_id
    assert api.clients[0].service.id == service.service_id
    assert api.servers[0].endpoint_ip == "127.0.0.1"
    assert api.clients[0].endpoint_ip == "127.0.0.1"
    assert api.servers[0].endpoint_port == 31000
    assert api.clients[0].endpoint_port == 31001
    assert api.servers[0].start_awaited is True


@pytest.mark.asyncio
async def test_someipy_adapter_repeated_start_reuses_service_runtime(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(service)
    await adapter.start_service(service)

    assert api.connect_started_count == 1
    assert len(api.servers) == 1
    assert len(api.clients) == 1
    assert api.servers[0].start_awaited is True


@pytest.mark.asyncio
async def test_someipy_adapter_stop_service_stops_offer_and_removes_runtime(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(service)
    await adapter.stop_service(service)

    assert api.servers[0].stop_awaited is True
    assert service.service_id not in adapter._service_runtimes
