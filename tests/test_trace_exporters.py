from datetime import UTC, datetime

from someip_gui_tool.domain.enums import Role, TraceDirection, TransportProtocol
from someip_gui_tool.tracing.exporters import export_trace_csv, export_trace_json
from someip_gui_tool.tracing.trace_model import MessageTraceEntry


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
