from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from someip_gui_tool.domain.enums import (
    FieldType,
    Role,
    SendStrategy,
    TransportProtocol,
)


def format_hex(value: int, width: int = 4) -> str:
    return f"0x{value:0{width}X}"


@dataclass(frozen=True)
class DatatypeDefinition:
    name: str
    kind: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class ParameterDefinition:
    name: str
    position: int | None
    direction: str | None
    datatype: DatatypeDefinition


@dataclass(frozen=True)
class MethodDefinition:
    name: str
    method_id: int
    rr_ff: str | None
    transport: TransportProtocol
    parameters: list[ParameterDefinition]
    description: str | None = None

    @property
    def method_id_hex(self) -> str:
        return format_hex(self.method_id)


@dataclass(frozen=True)
class EventDefinition:
    name: str
    event_id: int
    eventgroup_name: str | None
    eventgroup_id: int | None
    transport: TransportProtocol
    send_strategy: SendStrategy | None
    cycle_time_s: float | None
    parameters: list[ParameterDefinition]
    description: str | None = None

    @property
    def event_id_hex(self) -> str:
        return format_hex(self.event_id)


@dataclass(frozen=True)
class FieldPartDefinition:
    name: str
    field_type: FieldType
    element_id: int
    eventgroup_name: str | None
    eventgroup_id: int | None
    transport: TransportProtocol
    parameters: list[ParameterDefinition]
    description: str | None = None


@dataclass(frozen=True)
class FieldDefinition:
    name: str
    getter: FieldPartDefinition | None = None
    setter: FieldPartDefinition | None = None
    notifier: FieldPartDefinition | None = None


@dataclass(frozen=True)
class DeploymentConfig:
    instance_id: int
    major_version: int
    minor_version: int
    server_ecu: str
    server_ip: str
    client_ecu: str
    client_ip: str
    multicast_ip: str
    vlan_id: int | None
    vlan_priority: int | None
    default_transport: TransportProtocol
    offer_ttl_s: float
    find_ttl_s: float

    def local_ip_for(self, role: Role) -> str:
        return self.server_ip if role is Role.SERVER else self.client_ip

    def remote_ip_for(self, role: Role) -> str:
        return self.client_ip if role is Role.SERVER else self.server_ip


@dataclass(frozen=True)
class ServiceDefinition:
    service_id: int
    service_name: str
    deployment: DeploymentConfig
    methods: list[MethodDefinition] = field(default_factory=list)
    events: list[EventDefinition] = field(default_factory=list)
    fields: list[FieldDefinition] = field(default_factory=list)

    @property
    def service_id_hex(self) -> str:
        return format_hex(self.service_id)
