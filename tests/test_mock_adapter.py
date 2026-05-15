import pytest

from someip_gui_tool.adapters.base import AdapterEvent
from someip_gui_tool.adapters.mock import MockSomeIpAdapter
from someip_gui_tool.parsing.service_json import load_service_definition


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
