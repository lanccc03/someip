from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from someip_gui_tool.domain.enums import Role, TraceDirection, TransportProtocol


class RunLogEntry(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    timestamp: datetime
    level: str
    source: str
    message: str
    service_id: str | None = None
    element_id: str | None = None
    error_detail: str | None = None


class MessageTraceEntry(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    timestamp: datetime
    direction: TraceDirection
    role: Role
    service_name: str
    service_id: str
    instance_id: str
    element_type: str
    element_name: str
    element_id: str
    eventgroup_id: str | None = None
    transport: TransportProtocol
    local_endpoint: str
    remote_endpoint: str
    session_id: str | None = None
    message_type: str | None = None
    return_code: str | None = None
    rr_ff: str | None = None
    raw_payload_hex: str
    decoded_payload: dict[str, Any] = Field(default_factory=dict)
    payload_decode_status: str = "ok"
    duration_ms: float | None = None
    result: str
    error_message: str | None = None
