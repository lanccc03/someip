import pytest

from someip_gui_tool.adapters.base import AdapterEvent, AdapterStartConfig
from someip_gui_tool.adapters.mock import MockSomeIpAdapter
from someip_gui_tool.domain.enums import Role
from someip_gui_tool.parsing.service_json import load_service_definition


@pytest.mark.asyncio
async def test_mock_adapter_reports_service_availability(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = MockSomeIpAdapter()

    result = await adapter.check_service_available(service)

    assert result.available is True
    assert result.detail == "mock service is available"


@pytest.mark.asyncio
async def test_mock_adapter_subscription_results_are_request_states(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]
    adapter = MockSomeIpAdapter()

    subscribe_result = await adapter.subscribe_eventgroup(service, event.eventgroup_id or 0)
    unsubscribe_result = await adapter.unsubscribe_eventgroup(service, event.eventgroup_id or 0)

    assert subscribe_result.status == "requested"
    assert subscribe_result.service_available is True
    assert unsubscribe_result.status == "cancel-requested"


@pytest.mark.asyncio
async def test_mock_adapter_records_runtime_operations(adc40_soc_dir):
    event_service = load_service_definition(adc40_soc_dir / "0x080E.json")
    field_service = load_service_definition(adc40_soc_dir / "0x080C.json")
    adapter = MockSomeIpAdapter()
    received = []

    event = event_service.events[0]
    field = field_service.fields[0]
    assert await adapter.find_service(event_service) is True
    await adapter.start_service(event_service)
    await adapter.offer_service(event_service)
    await adapter.register_event_handler(event_service, event, received.append)
    await adapter.subscribe_eventgroup(event_service, event.eventgroup_id or 0)
    await adapter.publish_event(event_service, event, b"\x01\x02")
    await adapter.unsubscribe_eventgroup(event_service, event.eventgroup_id or 0)
    field_result = await adapter.field_get(field_service, field, b"\x03")
    await adapter.field_notify(field_service, field, b"\x04")
    await adapter.stop_service(event_service)
    await adapter.shutdown()

    assert [call.name for call in adapter.calls] == [
        "find_service",
        "start_service",
        "offer_service",
        "register_event_handler",
        "subscribe_eventgroup",
        "publish_event",
        "unsubscribe_eventgroup",
        "field_get",
        "field_notify",
        "stop_service",
        "shutdown",
    ]
    assert received == [
        AdapterEvent(
            service_id=event_service.service_id,
            element_id=event.event_id,
            eventgroup_id=event.eventgroup_id,
            payload=b"\x01\x02",
        )
    ]
    assert field_result.status == "success"
    assert field_result.payload == b"\x03"


@pytest.mark.asyncio
async def test_mock_adapter_marks_ff_method_as_limited(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080D.json")
    adapter = MockSomeIpAdapter()

    result = await adapter.call_method(service, service.methods[0], b"\x01")

    assert result.status == "limited"
    assert "fire-and-forget" in result.detail


@pytest.mark.asyncio
async def test_mock_adapter_delivers_field_notifier_events(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    adapter = MockSomeIpAdapter()
    received = []

    field = service.fields[0]
    assert field.notifier is not None
    await adapter.register_field_notifier_handler(service, field, received.append)
    await adapter.subscribe_eventgroup(service, field.notifier.eventgroup_id or 0)
    await adapter.field_notify(service, field, b"\x05")

    assert received == [
        AdapterEvent(
            service_id=service.service_id,
            element_id=field.notifier.element_id,
            eventgroup_id=field.notifier.eventgroup_id,
            payload=b"\x05",
        )
    ]


@pytest.mark.asyncio
async def test_mock_adapter_stops_event_delivery_after_unsubscribe_and_shutdown(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = MockSomeIpAdapter()
    received = []

    event = service.events[0]
    await adapter.register_event_handler(service, event, received.append)
    await adapter.subscribe_eventgroup(service, event.eventgroup_id or 0)
    await adapter.publish_event(service, event, b"\x01")
    await adapter.unsubscribe_eventgroup(service, event.eventgroup_id or 0)
    await adapter.publish_event(service, event, b"\x02")
    await adapter.subscribe_eventgroup(service, event.eventgroup_id or 0)
    await adapter.shutdown()
    await adapter.publish_event(service, event, b"\x03")

    assert [event.payload for event in received] == [b"\x01"]


@pytest.mark.asyncio
async def test_mock_adapter_field_set_returns_error_without_setter(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    adapter = MockSomeIpAdapter()

    result = await adapter.field_set(service, service.fields[0], b"\x06")

    assert result.status == "error"
    assert "setter" in result.detail


@pytest.mark.asyncio
async def test_mock_adapter_records_start_config(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = MockSomeIpAdapter()
    config = AdapterStartConfig(
        role=Role.SERVER,
        local_ip="172.16.3.14/24",
        server_port=30500,
        client_port=30501,
        multicast_ip="239.192.255.251",
        offer_ttl_s=3.0,
        find_ttl_s=3.0,
    )

    await adapter.start_service(service, config)

    assert adapter.calls[-1].name == "start_service"
    assert adapter.calls[-1].details == {
        "service_id": service.service_id_hex,
        "role": "Server",
        "local_ip": "172.16.3.14/24",
        "server_port": 30500,
        "client_port": 30501,
    }


@pytest.mark.asyncio
async def test_mock_adapter_call_details_are_immutable(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = MockSomeIpAdapter()

    await adapter.start_service(service)

    with pytest.raises(TypeError):
        adapter.calls[0].details["service_id"] = "0xFFFF"
