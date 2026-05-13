from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from someip_gui_tool.domain.enums import Role, TraceDirection, TransportProtocol


class RunLogEntry(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    timestamp: datetime
    level: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)


class MessageTraceEntry(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

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
    raw_payload_hex: str
    decoded_payload: dict[str, Any] = Field(default_factory=dict)
    result: str
