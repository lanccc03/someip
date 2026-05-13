import json
from datetime import UTC, datetime

from someip_gui_tool.domain.enums import Role, TraceDirection, TransportProtocol

from someip_gui_tool.tracing.exporters import (
    export_run_log_json,
    export_run_log_text,
    export_trace_csv,
    export_trace_json,
)
from someip_gui_tool.tracing.trace_model import MessageTraceEntry, RunLogEntry


def test_trace_exports_json_and_csv():
    entry = MessageTraceEntry(
        timestamp=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
        direction=TraceDirection.TX,
        role=Role.CLIENT,
        service_name="SecondStartSrv",
        service_id="0x080D",
        instance_id="0x0001",
        element_type="Method",
        element_name="SecondStartCtrl",
        element_id="0x0001",
        eventgroup_id=None,
        transport=TransportProtocol.UDP,
        local_endpoint="172.16.2.99:0",
        remote_endpoint="172.16.2.14:30501",
        raw_payload_hex="01",
        decoded_payload={"SecondStartCtrlCmd": 1},
        result="success",
    )

    json_text = export_trace_json([entry])
    csv_text = export_trace_csv([entry])

    assert '"service_id": "0x080D"' in json_text
    assert "SecondStartCtrl" in csv_text
    assert "raw_payload_hex" in csv_text.splitlines()[0]


def test_trace_models_export_defaults_and_enum_values():
    entry = MessageTraceEntry(
        timestamp=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
        direction=TraceDirection.RX,
        role=Role.SERVER,
        service_name="SecondStartSrv",
        service_id="0x080D",
        instance_id="0x0001",
        element_type="Method",
        element_name="SecondStartCtrl",
        element_id="0x0001",
        eventgroup_id=None,
        transport=TransportProtocol.TCP,
        local_endpoint="172.16.2.14:30501",
        remote_endpoint="172.16.2.99:0",
        raw_payload_hex="",
        decoded_payload={},
        result="success",
    )

    assert entry.payload_decode_status == "ok"
    assert entry.session_id is None
    assert entry.error_message is None

    rows = json.loads(export_trace_json([entry]))
    assert rows[0]["direction"] == "RX"
    assert rows[0]["role"] == "Server"
    assert rows[0]["transport"] == "TCP"
    assert rows[0]["payload_decode_status"] == "ok"

    csv_header = export_trace_csv([entry]).splitlines()[0].split(",")
    assert "error_message" in csv_header


def test_run_log_model_uses_plan_fields():
    assert set(RunLogEntry.model_fields) == {
        "timestamp",
        "level",
        "source",
        "message",
        "service_id",
        "element_id",
        "error_detail",
    }

    entry = RunLogEntry(
        timestamp=datetime(2026, 5, 13, 12, 1, tzinfo=UTC),
        level="ERROR",
        source="runner",
        message="Request failed",
        service_id="0x080D",
        element_id="0x0001",
        error_detail="timeout",
    )

    assert "timeout" in export_run_log_json([entry])
    assert "runner" in export_run_log_text([entry])
