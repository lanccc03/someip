from dataclasses import replace

import pytest

from someip_gui_tool.adapters.base import AdapterMethodResult
from someip_gui_tool.adapters.mock import MockSomeIpAdapter
from someip_gui_tool.core.runtime_config import RuntimeServiceConfig, infer_runtime_config
from someip_gui_tool.core.runtime_session import RuntimeSession
from someip_gui_tool.domain.enums import Role, TraceDirection
from someip_gui_tool.parsing.service_json import load_service_definition


class ResponsePayloadAdapter(MockSomeIpAdapter):
    def __init__(
        self,
        method_payload: bytes | None = None,
        field_payload: bytes | None = None,
    ) -> None:
        super().__init__()
        self.method_payload = method_payload
        self.field_payload = field_payload

    async def call_method(self, service, method, payload):
        await super().call_method(service, method, payload)
        return AdapterMethodResult(
            status="success",
            detail="mock response payload",
            payload=self.method_payload,
        )

    async def field_get(self, service, field, payload):
        await super().field_get(service, field, payload)
        return AdapterMethodResult(
            status="success",
            detail="mock field response payload",
            payload=self.field_payload,
        )


class ErrorResultAdapter(MockSomeIpAdapter):
    async def call_method(self, service, method, payload):
        await super().call_method(service, method, payload)
        return AdapterMethodResult(status="error", detail="method adapter rejected request")

    async def field_get(self, service, field, payload):
        await super().field_get(service, field, payload)
        return AdapterMethodResult(status="error", detail="field get adapter rejected request")

    async def field_set(self, service, field, payload):
        await super().field_set(service, field, payload)
        return AdapterMethodResult(status="error", detail="field set adapter rejected request")


class CaptureStartConfigAdapter(MockSomeIpAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.start_config = None

    async def start_service(self, service, config=None):
        self.start_config = config
        await super().start_service(service, config)


class FailingAdapter(MockSomeIpAdapter):
    async def start_service(self, service, config=None):
        raise RuntimeError("adapter start failed")

    async def subscribe_eventgroup(self, service, eventgroup_id):
        raise RuntimeError("adapter subscribe failed")

    async def publish_event(self, service, event, payload):
        raise RuntimeError("adapter publish failed")

    async def field_notify(self, service, field, payload):
        raise RuntimeError("adapter notify failed")


def _valid_config(service, role=Role.CLIENT) -> RuntimeServiceConfig:
    return replace(
        infer_runtime_config(service, role),
        server_port=30500,
        client_port=30501,
    )


@pytest.mark.asyncio
async def test_runtime_session_subscribes_and_publishes_event(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)
    config = _valid_config(service, Role.SERVER)

    await session.start_service(service, config)
    await session.subscribe_event(service, service.events[0])
    await session.publish_event(
        service,
        service.events[0],
        {"VehicleInfo": {"VehicleSpeed": 12.5, "Odometer": 99.25}},
    )

    assert [call.name for call in adapter.calls] == [
        "start_service",
        "offer_service",
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
    assert session.trace[-1].local_endpoint == f"{service.deployment.server_ip}:30500"
    assert session.trace[-1].remote_endpoint == f"{service.deployment.client_ip}:30501"


@pytest.mark.asyncio
async def test_runtime_session_rejects_invalid_start_config_before_adapter(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)

    with pytest.raises(ValueError, match="server_port_missing"):
        await session.start_service(service, infer_runtime_config(service, Role.SERVER))

    assert adapter.calls == []
    assert [entry.level for entry in session.run_log] == ["error", "error"]
    assert [entry.error_detail for entry in session.run_log] == [
        "server_port_missing",
        "client_port_missing",
    ]
    assert [problem.code for problem in session.problems] == [
        "server_port_missing",
        "client_port_missing",
    ]


@pytest.mark.asyncio
async def test_runtime_session_records_start_service_adapter_exception(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    session = RuntimeSession(adapter=FailingAdapter())

    with pytest.raises(RuntimeError, match="adapter start failed"):
        await session.start_service(service, _valid_config(service, Role.SERVER))

    assert session.problems[-1].code == "start_service_adapter_exception"
    assert session.problems[-1].severity == "error"
    assert "adapter start failed" in session.problems[-1].message
    assert session.run_log[-1].level == "error"
    assert session.run_log[-1].error_detail == "adapter start failed"


@pytest.mark.asyncio
async def test_runtime_session_records_subscribe_adapter_exception(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    session = RuntimeSession(adapter=FailingAdapter())

    with pytest.raises(RuntimeError, match="adapter subscribe failed"):
        await session.subscribe_event(service, service.events[0])

    assert session.problems[-1].code == "subscribe_event_adapter_exception"
    assert session.problems[-1].severity == "error"
    assert "adapter subscribe failed" in session.problems[-1].message
    assert session.run_log[-1].level == "error"
    assert session.run_log[-1].error_detail == "adapter subscribe failed"


@pytest.mark.asyncio
async def test_runtime_session_records_publish_adapter_exception(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    session = RuntimeSession(adapter=FailingAdapter())

    with pytest.raises(RuntimeError, match="adapter publish failed"):
        await session.publish_event(
            service,
            service.events[0],
            {"VehicleInfo": {"VehicleSpeed": 12.5, "Odometer": 99.25}},
        )

    assert session.problems[-1].code == "publish_event_adapter_exception"
    assert session.problems[-1].severity == "error"
    assert "adapter publish failed" in session.problems[-1].message
    assert session.run_log[-1].level == "error"
    assert session.run_log[-1].error_detail == "adapter publish failed"


@pytest.mark.asyncio
async def test_runtime_session_records_field_notify_adapter_exception(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    session = RuntimeSession(adapter=FailingAdapter())
    field = service.fields[0]

    with pytest.raises(RuntimeError, match="adapter notify failed"):
        await session.field_notify(service, field, {"VertHeiRmdSts": 1})

    assert session.problems[-1].code == "field_notify_adapter_exception"
    assert session.problems[-1].severity == "error"
    assert "adapter notify failed" in session.problems[-1].message
    assert session.run_log[-1].level == "error"
    assert session.run_log[-1].error_detail == "adapter notify failed"


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
    assert session.trace[1].element_type == "FieldGetter"
    assert session.trace[1].direction == TraceDirection.RX
    assert session.trace[1].result == "success"
    assert session.trace[2].element_type == "FieldNotifier"
    assert session.trace[2].result == "success"


@pytest.mark.asyncio
async def test_runtime_session_records_adapter_error_results_as_problems(adc40_soc_dir):
    method_service = load_service_definition(adc40_soc_dir / "0x080D.json")
    field_service = load_service_definition(adc40_soc_dir / "0x080C.json")
    adapter = ErrorResultAdapter()
    session = RuntimeSession(adapter=adapter)
    field = replace(field_service.fields[0], setter=field_service.fields[0].getter)

    method_result = await session.call_method(
        method_service,
        method_service.methods[0],
        {"SecondStartCtrlCmd": 1},
    )
    get_result = await session.field_get(field_service, field, {"VertHeiRmdSts": 1})
    set_result = await session.field_set(field_service, field, {"VertHeiRmdSts": 1})

    assert [method_result.status, get_result.status, set_result.status] == [
        "error",
        "error",
        "error",
    ]
    assert [problem.code for problem in session.problems] == [
        "call_method_adapter_error",
        "field_get_adapter_error",
        "field_set_adapter_error",
    ]
    assert [entry.level for entry in session.run_log[-3:]] == ["error", "error", "error"]
    assert [entry.error_detail for entry in session.run_log[-3:]] == [
        "method adapter rejected request",
        "field get adapter rejected request",
        "field set adapter rejected request",
    ]


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
async def test_runtime_session_decodes_method_response_payload_rx_trace(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080D.json")
    adapter = ResponsePayloadAdapter(method_payload=b"\x02")
    session = RuntimeSession(adapter=adapter)
    await session.start_service(service, _valid_config(service, Role.CLIENT))

    result = await session.call_method(service, service.methods[0], {"SecondStartCtrlCmd": 1})

    assert result.status == "success"
    rx_trace = session.trace[-1]
    assert rx_trace.direction == TraceDirection.RX
    assert rx_trace.element_type == "Method"
    assert rx_trace.raw_payload_hex == "02"
    assert rx_trace.decoded_payload == {"SecondStartCtrlCmd": 2}
    assert rx_trace.payload_decode_status == "ok"
    assert rx_trace.local_endpoint == f"{service.deployment.client_ip}:30501"
    assert rx_trace.remote_endpoint == f"{service.deployment.server_ip}:30500"


@pytest.mark.asyncio
async def test_runtime_session_records_method_response_decode_failure(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080D.json")
    adapter = ResponsePayloadAdapter(method_payload=b"\x02\x03")
    session = RuntimeSession(adapter=adapter)

    result = await session.call_method(service, service.methods[0], {"SecondStartCtrlCmd": 1})

    assert result.status == "success"
    rx_trace = session.trace[-1]
    assert rx_trace.direction == TraceDirection.RX
    assert rx_trace.payload_decode_status == "error"
    assert rx_trace.result == "error"
    assert "trailing bytes" in rx_trace.error_message


@pytest.mark.asyncio
async def test_runtime_session_decodes_field_get_response_payload_rx_trace(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    adapter = ResponsePayloadAdapter(field_payload=b"\x02")
    session = RuntimeSession(adapter=adapter)
    field = service.fields[0]

    result = await session.field_get(service, field, {"VertHeiRmdSts": 1})

    assert result.status == "success"
    rx_trace = session.trace[-1]
    assert rx_trace.direction == TraceDirection.RX
    assert rx_trace.element_type == "FieldGetter"
    assert rx_trace.raw_payload_hex == "02"
    assert rx_trace.decoded_payload == {"VertHeiRmdSts": 2}
    assert rx_trace.payload_decode_status == "ok"


@pytest.mark.asyncio
async def test_runtime_session_records_field_get_response_decode_failure(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    adapter = ResponsePayloadAdapter(field_payload=b"\x02\x03")
    session = RuntimeSession(adapter=adapter)
    field = service.fields[0]

    result = await session.field_get(service, field, {"VertHeiRmdSts": 1})

    assert result.status == "success"
    rx_trace = session.trace[-1]
    assert rx_trace.direction == TraceDirection.RX
    assert rx_trace.payload_decode_status == "error"
    assert rx_trace.result == "error"
    assert "trailing bytes" in rx_trace.error_message


@pytest.mark.asyncio
async def test_runtime_session_call_method_encode_error_is_logged_and_traced(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080D.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)

    result = await session.call_method(service, service.methods[0], {})

    assert result.status == "error"
    assert adapter.calls == []
    assert session.run_log[-1].level == "error"
    assert "SecondStartCtrlCmd" in session.run_log[-1].error_detail
    assert session.trace[-1].result == "error"
    assert session.trace[-1].payload_decode_status == "encode-error"
    assert session.trace[-1].raw_payload_hex == ""
    assert session.trace[-1].decoded_payload == {}


@pytest.mark.asyncio
async def test_runtime_session_publish_event_encode_error_is_logged_and_traced(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)

    with pytest.raises(KeyError):
        await session.publish_event(service, service.events[0], {})

    assert adapter.calls == []
    assert session.run_log[-1].level == "error"
    assert "VehicleInfo" in session.run_log[-1].error_detail
    assert session.trace[-1].element_type == "Event"
    assert session.trace[-1].payload_decode_status == "encode-error"


@pytest.mark.asyncio
async def test_runtime_session_field_get_encode_error_is_logged_and_traced(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)
    field = service.fields[0]

    result = await session.field_get(service, field, {})

    assert result.status == "error"
    assert adapter.calls == []
    assert session.run_log[-1].level == "error"
    assert "VertHeiRmdSts" in session.run_log[-1].error_detail
    assert session.trace[-1].element_type == "FieldGetter"
    assert session.trace[-1].payload_decode_status == "encode-error"


@pytest.mark.asyncio
async def test_runtime_session_field_set_encode_error_is_logged_and_traced(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)
    field = replace(service.fields[0], setter=service.fields[0].getter)

    result = await session.field_set(service, field, {})

    assert result.status == "error"
    assert adapter.calls == []
    assert session.run_log[-1].level == "error"
    assert "VertHeiRmdSts" in session.run_log[-1].error_detail
    assert session.trace[-1].element_type == "FieldSetter"
    assert session.trace[-1].payload_decode_status == "encode-error"


@pytest.mark.asyncio
async def test_runtime_session_field_notify_encode_error_is_logged_and_traced(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)
    field = service.fields[0]

    with pytest.raises(KeyError):
        await session.field_notify(service, field, {})

    assert adapter.calls == []
    assert session.run_log[-1].level == "error"
    assert "VertHeiRmdSts" in session.run_log[-1].error_detail
    assert session.trace[-1].element_type == "FieldNotifier"
    assert session.trace[-1].payload_decode_status == "encode-error"


@pytest.mark.asyncio
async def test_runtime_session_field_set_without_setter_returns_error(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)
    field = service.fields[0]

    result = await session.field_set(service, field, {"VertHeiRmdSts": 1})

    assert result.status == "error"
    assert "setter" in result.detail
    assert adapter.calls == []
    assert session.trace[-1].element_type == "FieldSetter"
    assert session.trace[-1].element_id == "missing"
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
    await session.register_event_trace(event_service, event)
    await session.start_service(event_service, _valid_config(event_service, Role.CLIENT))
    await session.subscribe_event(event_service, event)
    await session.publish_event(
        event_service,
        event,
        {"VehicleInfo": {"VehicleSpeed": 12.5, "Odometer": 99.25}},
    )
    await session.register_field_notifier_trace(field_service, field)
    await session.register_field_notifier_trace(field_service, field)
    await session.start_service(field_service, _valid_config(field_service, Role.CLIENT))
    await adapter.subscribe_eventgroup(field_service, field.notifier.eventgroup_id or 0)
    await session.field_notify(field_service, field, {"VertHeiRmdSts": 1})

    rx_entries = [entry for entry in session.trace if entry.direction == TraceDirection.RX]
    assert [entry.element_type for entry in rx_entries] == ["Event", "FieldNotifier"]
    assert rx_entries[0].raw_payload_hex == "4148000042c68000"
    assert rx_entries[0].payload_decode_status == "ok"
    assert rx_entries[1].raw_payload_hex == "01"
    assert rx_entries[1].payload_decode_status == "ok"
    assert [call.name for call in adapter.calls].count("register_event_handler") == 1
    assert [call.name for call in adapter.calls].count("register_field_notifier_handler") == 1


@pytest.mark.asyncio
async def test_runtime_session_trace_callbacks_stop_and_reregister(adc40_soc_dir):
    event_service = load_service_definition(adc40_soc_dir / "0x080E.json")
    field_service = load_service_definition(adc40_soc_dir / "0x080C.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)
    event = event_service.events[0]
    field = field_service.fields[0]
    assert field.notifier is not None

    await session.register_event_trace(event_service, event)
    await session.start_service(event_service, _valid_config(event_service, Role.CLIENT))
    await session.subscribe_event(event_service, event)
    await session.publish_event(
        event_service,
        event,
        {"VehicleInfo": {"VehicleSpeed": 12.5, "Odometer": 99.25}},
    )

    event_rx_count = _rx_trace_count(session, "Event")
    assert event_rx_count == 1

    await session.stop_service(event_service)
    await adapter.publish_event(event_service, event, b"\x41\x48\x00\x00\x42\xc6\x80\x00")

    assert _rx_trace_count(session, "Event") == event_rx_count

    await session.start_service(event_service, _valid_config(event_service, Role.CLIENT))
    await session.register_event_trace(event_service, event)
    await session.subscribe_event(event_service, event)
    await session.publish_event(
        event_service,
        event,
        {"VehicleInfo": {"VehicleSpeed": 12.5, "Odometer": 99.25}},
    )

    assert _rx_trace_count(session, "Event") == event_rx_count + 1

    await session.register_field_notifier_trace(field_service, field)
    await session.start_service(field_service, _valid_config(field_service, Role.CLIENT))
    await adapter.subscribe_eventgroup(field_service, field.notifier.eventgroup_id or 0)
    await session.field_notify(field_service, field, {"VertHeiRmdSts": 1})

    field_rx_count = _rx_trace_count(session, "FieldNotifier")
    assert field_rx_count == 1

    await session.stop_service(field_service)
    await adapter.field_notify(field_service, field, b"\x01")

    assert _rx_trace_count(session, "FieldNotifier") == field_rx_count

    await session.start_service(field_service, _valid_config(field_service, Role.CLIENT))
    await session.register_field_notifier_trace(field_service, field)
    await adapter.subscribe_eventgroup(field_service, field.notifier.eventgroup_id or 0)
    await session.field_notify(field_service, field, {"VertHeiRmdSts": 1})

    assert _rx_trace_count(session, "FieldNotifier") == field_rx_count + 1
    assert [call.name for call in adapter.calls].count("register_event_handler") == 2
    assert [call.name for call in adapter.calls].count("register_field_notifier_handler") == 2


class UnavailableFindAdapter(MockSomeIpAdapter):
    async def find_service(self, service):
        await super().find_service(service)
        return False


@pytest.mark.asyncio
async def test_runtime_session_server_start_offers_service(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)

    await session.start_service(service, _valid_config(service, Role.SERVER))

    assert [call.name for call in adapter.calls] == [
        "start_service",
        "offer_service",
    ]
    assert adapter.calls[0].details["role"] == "Server"
    assert adapter.calls[0].details["local_ip"] == service.deployment.server_ip
    assert adapter.calls[0].details["server_port"] == 30500
    assert adapter.calls[0].details["client_port"] == 30501
    assert session.run_log[-2].message == (
        f"Offered service {service.service_name} ({service.service_id_hex})"
    )
    assert session.run_log[-1].message == (
        f"Started service {service.service_name} ({service.service_id_hex})"
    )


@pytest.mark.asyncio
async def test_runtime_session_client_start_finds_service(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)

    await session.start_service(service, _valid_config(service, Role.CLIENT))

    assert [call.name for call in adapter.calls] == [
        "start_service",
        "find_service",
    ]
    assert adapter.calls[0].details["role"] == "Client"
    assert adapter.calls[0].details["local_ip"] == service.deployment.client_ip
    assert session.run_log[-2].message == (
        f"Found service {service.service_name} ({service.service_id_hex})"
    )
    assert session.run_log[-1].message == (
        f"Started service {service.service_name} ({service.service_id_hex})"
    )


@pytest.mark.asyncio
async def test_runtime_session_client_start_records_find_timeout_warning(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    session = RuntimeSession(adapter=UnavailableFindAdapter())

    await session.start_service(service, _valid_config(service, Role.CLIENT))

    assert session.problems[-1].code == "find_service_unavailable"
    assert session.problems[-1].severity == "warning"
    assert "not available" in session.problems[-1].message
    assert session.run_log[-2].level == "warning"
    assert session.run_log[-2].error_detail == "find_service_unavailable"
    assert session.run_log[-1].message == (
        f"Started service {service.service_name} ({service.service_id_hex})"
    )


def _rx_trace_count(session: RuntimeSession, element_type: str) -> int:
    return sum(
        1
        for entry in session.trace
        if entry.direction == TraceDirection.RX and entry.element_type == element_type
    )


@pytest.mark.asyncio
async def test_runtime_session_adapter_config_uses_service_ttl_defaults(
    adc40_soc_dir,
):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = CaptureStartConfigAdapter()
    session = RuntimeSession(adapter=adapter)
    config = replace(
        _valid_config(service, Role.CLIENT),
        offer_ttl_s=None,
        find_ttl_s=None,
    )

    await session.start_service(service, config)

    assert adapter.start_config is not None
    assert adapter.start_config.offer_ttl_s == service.deployment.offer_ttl_s
    assert adapter.start_config.find_ttl_s == service.deployment.find_ttl_s
