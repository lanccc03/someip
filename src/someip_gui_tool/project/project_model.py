from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from someip_gui_tool.domain.enums import Role, TransportProtocol


class ServiceRuntimeOverride(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    enabled: bool = False
    role: Role
    local_ip: str
    remote_ip: str
    server_port: int | None = None
    client_port: int | None = None
    multicast_ip: str
    transport: TransportProtocol | None = None
    sd_timing: dict[str, float] = Field(default_factory=dict)
    payload_defaults: dict[str, Any] = Field(default_factory=dict)
    event_subscriptions: list[str] = Field(default_factory=list)
    cycle_events: dict[str, float] = Field(default_factory=dict)


class ActionStep(BaseModel):
    action: str
    service_id: str | None = None
    element_id: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)


class ProjectFile(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    schema_version: str
    project_name: str
    definition_root: Path
    services: dict[str, ServiceRuntimeOverride] = Field(default_factory=dict)
    sequences: list[ActionStep] = Field(default_factory=list)
