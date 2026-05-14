from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import StrEnum
from pathlib import Path
from typing import Any

from someip_gui_tool.core.service_registry import ServiceRegistry
from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldDefinition,
    MethodDefinition,
    ServiceDefinition,
)


class ScenarioKind(StrEnum):
    UDP_FF_METHOD = "udp-ff-method"
    TCP_METHOD = "tcp-method"
    UDP_EVENT = "udp-event"
    TCP_EVENT = "tcp-event"
    FIELD_GETTER_NOTIFIER = "field-getter-notifier"


@dataclass(frozen=True)
class ProtocolScenario:
    kind: ScenarioKind
    title: str
    service: ServiceDefinition
    method: MethodDefinition | None = None
    event: EventDefinition | None = None
    field: FieldDefinition | None = None
    payload_values: dict[str, Any] = dataclass_field(default_factory=dict)


def build_scenarios(definition_root: Path) -> list[ProtocolScenario]:
    registry = ServiceRegistry.load_directory(definition_root)
    second_start = registry.get_service(0x080D)
    hut_system = registry.get_service(0x0F01)
    adas_route = registry.get_service(0x080E)
    cockpit = registry.get_service(0x080A)
    field_service = registry.get_service(0x080C)

    return [
        ProtocolScenario(
            kind=ScenarioKind.UDP_FF_METHOD,
            title="UDP FF method SecondStartCtrl",
            service=second_start,
            method=_find_method(second_start, "SecondStartCtrl"),
            payload_values={"SecondStartCtrlCmd": 1},
        ),
        ProtocolScenario(
            kind=ScenarioKind.TCP_METHOD,
            title="TCP method AudioRecPopupReq",
            service=hut_system,
            method=_find_method(hut_system, "AudioRecPopupReq"),
            payload_values={"AudioRecPopup": 1},
        ),
        ProtocolScenario(
            kind=ScenarioKind.UDP_EVENT,
            title="UDP cycle event VehicleInfo",
            service=adas_route,
            event=_find_event(adas_route, "VehicleInfo"),
            payload_values={"VehicleInfo": {"VehicleSpeed": 12.5, "Odometer": 99.25}},
        ),
        ProtocolScenario(
            kind=ScenarioKind.TCP_EVENT,
            title="TCP trigger event IntellgntSwtDecoupSts",
            service=cockpit,
            event=_find_event(cockpit, "IntellgntSwtDecoupSts"),
            payload_values={"IntellgntSwtDecoupSts": [1, 2, 3]},
        ),
        ProtocolScenario(
            kind=ScenarioKind.FIELD_GETTER_NOTIFIER,
            title="Field Getter/Notifier VertHeiRmdSts",
            service=field_service,
            field=_find_field(field_service, "VertHeiRmdSts"),
            payload_values={"VertHeiRmdSts": 1},
        ),
    ]


def _find_method(service: ServiceDefinition, name: str) -> MethodDefinition:
    for method in service.methods:
        if method.name == name:
            return method
    raise KeyError(f"Method {name!r} not found in service {service.service_id_hex}")


def _find_event(service: ServiceDefinition, name: str) -> EventDefinition:
    for event in service.events:
        if event.name == name:
            return event
    raise KeyError(f"Event {name!r} not found in service {service.service_id_hex}")


def _find_field(service: ServiceDefinition, name: str) -> FieldDefinition:
    for field_definition in service.fields:
        if field_definition.name == name:
            return field_definition
    raise KeyError(f"Field {name!r} not found in service {service.service_id_hex}")
