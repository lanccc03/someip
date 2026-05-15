import pytest

from someip_gui_tool.adapters.mock import MockSomeIpAdapter
from someip_gui_tool.core.runtime_config import infer_runtime_config
from someip_gui_tool.core.runtime_session import RuntimeSession
from someip_gui_tool.domain.enums import Role, TraceDirection
from someip_gui_tool.parsing.service_json import load_service_definition


@pytest.mark.asyncio
async def test_runtime_session_subscribes_and_publishes_event(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)
    config = infer_runtime_config(service, Role.SERVER)

    await session.start_service(service, config)
    await session.subscribe_event(service, service.events[0])
    await session.publish_event(
        service,
        service.events[0],
        {"VehicleInfo": {"VehicleSpeed": 12.5, "Odometer": 99.25}},
    )

    assert [call.name for call in adapter.calls] == [
        "start_service",
        "subscribe_eventgroup",
        "publish_event",
    ]
    assert [entry.message for entry in session.run_log][-3:] == [
        f"Started service {service.service_name} ({service.service_id_hex})",
        "Subscribed eventgroup 0x0001 for VehicleInfo",
        "Published event VehicleInfo payload=4148000042c68000",
    ]
    assert session.trace[-1].raw_payload_hex == "4148000042c68000"
    assert session.trace[-1].element_name == "VehicleInfo"
    assert session.trace[-1].local_endpoint == ""
    assert session.trace[-1].remote_endpoint == ""


@pytest.mark.asyncio
async def test_runtime_session_field_get_and_notify(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)
    field = service.fields[0]

    result = await session.field_get(service, field, {"VertHeiRmdSts": 1})
    await session.field_notify(service, field, {"VertHeiRmdSts": 1})

    assert result.status == "success"
    assert [call.name for call in adapter.calls] == ["field_get", "field_notify"]
    assert session.trace[0].element_type == "FieldGetter"
    assert session.trace[0].result == "success"
    assert session.trace[1].element_type == "FieldNotifier"
    assert session.trace[1].result == "success"


@pytest.mark.asyncio
async def test_runtime_session_reports_limited_ff_method(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080D.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)

    result = await session.call_method(service, service.methods[0], {"SecondStartCtrlCmd": 1})

    assert result.status == "limited"
    assert "fire-and-forget" in result.detail
    assert session.trace[-1].result == "limited"
    assert session.trace[-1].element_type == "Method"
    assert session.run_log[-1].message == f"Called method {service.methods[0].name} result=limited"


@pytest.mark.asyncio
async def test_runtime_session_field_set_without_setter_returns_error(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)
    field = service.fields[0]

    result = await session.field_set(service, field, {"VertHeiRmdSts": 1})

    assert result.status == "error"
    assert "setter" in result.detail
    assert adapter.calls[-1].name == "field_set"
    assert adapter.calls[-1].details["payload"] == ""
    assert session.trace[-1].element_type == "FieldSetter"
    assert session.trace[-1].raw_payload_hex == ""
    assert session.trace[-1].result == "error"


@pytest.mark.asyncio
async def test_runtime_session_registers_rx_traces_after_subscription(adc40_soc_dir):
    event_service = load_service_definition(adc40_soc_dir / "0x080E.json")
    field_service = load_service_definition(adc40_soc_dir / "0x080C.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)
    event = event_service.events[0]
    field = field_service.fields[0]
    assert field.notifier is not None

    await session.register_event_trace(event_service, event)
    await session.subscribe_event(event_service, event)
    await session.publish_event(
        event_service,
        event,
        {"VehicleInfo": {"VehicleSpeed": 12.5, "Odometer": 99.25}},
    )
    await session.register_field_notifier_trace(field_service, field)
    await adapter.subscribe_eventgroup(field_service, field.notifier.eventgroup_id or 0)
    await session.field_notify(field_service, field, {"VertHeiRmdSts": 1})

    rx_entries = [entry for entry in session.trace if entry.direction == TraceDirection.RX]
    assert [entry.element_type for entry in rx_entries] == ["Event", "FieldNotifier"]
    assert rx_entries[0].raw_payload_hex == "4148000042c68000"
    assert rx_entries[0].payload_decode_status == "ok"
    assert rx_entries[1].raw_payload_hex == "01"
    assert rx_entries[1].payload_decode_status == "ok"
