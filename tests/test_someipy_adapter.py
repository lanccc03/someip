from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from someip_gui_tool.adapters.base import AdapterStartConfig, SomeIpAdapter
from someip_gui_tool.domain.enums import Role
from someip_gui_tool.adapters.someipy_adapter import SomeipyAdapter
from someip_gui_tool.parsing.service_json import load_service_definition
from tests.fakes_someipy_runtime import FakeSomeipyApi


def _adapter_start_config(role: Role = Role.CLIENT) -> AdapterStartConfig:
    return AdapterStartConfig(
        role=role,
        local_ip="127.0.0.1/24",
        server_port=32000,
        client_port=32001,
        multicast_ip="239.192.255.251",
        offer_ttl_s=3.0,
        find_ttl_s=3.0,
    )


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


def test_someipy_adapter_maps_non_ok_method_result_to_error() -> None:
    adapter = SomeipyAdapter(api=FakeSomeipyApi(), local_ip="127.0.0.1", base_port=31000)
    result = adapter._adapter_method_result(
        type("Result", (), {"return_code": "E_NOT_OK", "payload": b"\x01"})(),
        "success detail",
    )

    assert result.status == "error"
    assert "E_NOT_OK" in result.detail
    assert result.payload == b"\x01"


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


@pytest.mark.asyncio
async def test_someipy_adapter_can_own_someipyd_process(adc40_soc_dir, monkeypatch, tmp_path) -> None:
    api = FakeSomeipyApi()
    started = []
    stopped = []

    class FakeProcess:
        def stop(self) -> None:
            stopped.append(True)

    def fake_start(config, work_dir):
        started.append((config, work_dir))
        return FakeProcess()

    monkeypatch.setattr("someip_gui_tool.adapters.someipy_adapter.SomeipydProcess.start", fake_start)
    adapter = SomeipyAdapter(
        api=api,
        local_ip="127.0.0.1",
        base_port=31000,
        start_daemon=True,
        daemon_work_dir=tmp_path,
    )
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(service)
    await adapter.shutdown()

    assert len(started) == 1
    assert started[0][0].interface == "127.0.0.1"
    assert started[0][0].tcp_host == "127.0.0.1"
    assert started[0][0].tcp_port == 31000
    assert started[0][1] == tmp_path
    assert stopped == [True]


@pytest.mark.asyncio
async def test_someipy_adapter_assigns_monotonic_ports_across_stop_restart(adc40_soc_dir) -> None:
    """Regression: stop+restart must not reuse an index that is still in use."""
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    svc_a = load_service_definition(adc40_soc_dir / "0x080A.json")
    svc_c = load_service_definition(adc40_soc_dir / "0x080C.json")
    svc_e = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(svc_a)
    await adapter.start_service(svc_c)
    await adapter.stop_service(svc_a)
    await adapter.start_service(svc_e)

    rt_c = adapter._service_runtimes[svc_c.service_id]
    rt_e = adapter._service_runtimes[svc_e.service_id]
    assert rt_c.endpoint_port == 31010
    assert rt_e.endpoint_port == 31020
    assert {rt_c.endpoint_port, rt_e.endpoint_port} == {31010, 31020}


@pytest.mark.asyncio
async def test_someipy_adapter_shutdown_stops_active_offers(adc40_soc_dir) -> None:
    """Regression: shutdown must best-effort stop_offer on every active service."""
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(service)
    await adapter.shutdown()

    assert api.servers[0].stop_awaited is True


@pytest.mark.asyncio
async def test_someipy_adapter_start_service_uses_configured_ports(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(service, _adapter_start_config(Role.CLIENT))

    assert api.servers[0].endpoint_ip == "127.0.0.1"
    assert api.clients[0].endpoint_ip == "127.0.0.1"
    assert api.servers[0].endpoint_port == 32000
    assert api.clients[0].endpoint_port == 32001
    assert api.servers[0].start_awaited is False


@pytest.mark.asyncio
async def test_someipy_adapter_offer_service_starts_offer_after_configured_start(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(service, _adapter_start_config(Role.SERVER))
    await adapter.offer_service(service)

    assert len(api.servers) == 1
    assert api.servers[0].endpoint_port == 32000
    assert api.servers[0].start_awaited is True


@pytest.mark.asyncio
async def test_someipy_adapter_find_service_after_configured_start_uses_existing_client(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    api = FakeSomeipyApi(availability_sequences={service.service_id: [True]})
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)

    await adapter.start_service(service, _adapter_start_config(Role.CLIENT))
    result = await adapter.find_service(service)

    assert result is True
    assert len(api.clients) == 1
    assert api.clients[0].endpoint_port == 32001
    assert api.availability_calls[service.service_id] == 1


@pytest.mark.asyncio
async def test_someipy_adapter_configured_start_replaces_unconfigured_runtime(
    adc40_soc_dir,
) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    api = FakeSomeipyApi(availability_sequences={service.service_id: [True]})
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)

    await adapter.find_service(service)
    await adapter.start_service(service, _adapter_start_config(Role.CLIENT))

    assert len(api.servers) == 2
    assert len(api.clients) == 2
    assert api.servers[0].endpoint_port == 31000
    assert api.clients[0].endpoint_port == 31001
    assert api.servers[0].stop_awaited is True
    assert api.servers[1].endpoint_port == 32000
    assert api.clients[1].endpoint_port == 32001
    assert adapter._service_runtimes[service.service_id].endpoint_port == 32000
    assert adapter._service_runtimes[service.service_id].client_port == 32001


@pytest.mark.asyncio
async def test_someipy_adapter_repeated_configured_start_reuses_matching_runtime(
    adc40_soc_dir,
) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    config = _adapter_start_config(Role.CLIENT)

    await adapter.start_service(service, config)
    await adapter.start_service(service, config)

    assert len(api.servers) == 1
    assert len(api.clients) == 1
    assert api.servers[0].endpoint_port == 32000
    assert api.clients[0].endpoint_port == 32001
