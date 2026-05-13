from __future__ import annotations

import csv
import io
import json
from typing import Any

from someip_gui_tool.tracing.trace_model import MessageTraceEntry, RunLogEntry


TRACE_CSV_FIELDS = [
    "timestamp",
    "direction",
    "role",
    "service_name",
    "service_id",
    "instance_id",
    "element_type",
    "element_name",
    "element_id",
    "eventgroup_id",
    "transport",
    "local_endpoint",
    "remote_endpoint",
    "session_id",
    "message_type",
    "return_code",
    "rr_ff",
    "raw_payload_hex",
    "decoded_payload",
    "payload_decode_status",
    "duration_ms",
    "result",
    "error_message",
]


def export_trace_json(entries: list[MessageTraceEntry]) -> str:
    return _export_model_json(entries)


def export_run_log_json(entries: list[RunLogEntry]) -> str:
    return _export_model_json(entries)


def export_run_log_text(entries: list[RunLogEntry]) -> str:
    lines = []
    for entry in entries:
        line = f"{entry.timestamp.isoformat()} [{entry.level}] {entry.source}: {entry.message}"
        details = {
            key: value
            for key, value in {
                "service_id": entry.service_id,
                "element_id": entry.element_id,
                "error_detail": entry.error_detail,
            }.items()
            if value is not None
        }
        if details:
            detail_text = json.dumps(details, ensure_ascii=False, sort_keys=True)
            line = f"{line} {detail_text}"
        lines.append(line)
    return "\n".join(lines)


def export_trace_csv(entries: list[MessageTraceEntry]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=TRACE_CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for entry in entries:
        writer.writerow(_trace_csv_row(entry))
    return output.getvalue()


def _export_model_json(entries: list[MessageTraceEntry] | list[RunLogEntry]) -> str:
    rows = [entry.model_dump(mode="json") for entry in entries]
    return json.dumps(rows, ensure_ascii=False, indent=2)


def _trace_csv_row(entry: MessageTraceEntry) -> dict[str, Any]:
    row = entry.model_dump(mode="json")
    row["decoded_payload"] = json.dumps(
        row["decoded_payload"],
        ensure_ascii=False,
        sort_keys=True,
    )
    return row
