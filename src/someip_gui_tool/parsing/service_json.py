from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from someip_gui_tool.domain.enums import FieldType, SendStrategy, TransportProtocol
from someip_gui_tool.domain.models import (
    DatatypeDefinition,
    DeploymentConfig,
    EventDefinition,
    FieldDefinition,
    FieldPartDefinition,
    MethodDefinition,
    ParameterDefinition,
    ServiceDefinition,
)


def _parse_int(value: Any) -> int | None:
    if value is None or value == "/":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        return int(text, 16) if text.lower().startswith("0x") else int(text)
    raise TypeError(f"Unsupported integer value: {value!r}")


def _parse_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "/":
        return default
    return float(value)


def _timing(deployment: dict[str, Any], logical_name: str, default: float = 0.0) -> float:
    for key, value in deployment.items():
        normalized = key.replace("\n", " ").strip().lower()
        if logical_name.lower() in normalized:
            return _parse_float(value, default)
    return default


def _datatype(raw: dict[str, Any]) -> DatatypeDefinition:
    return DatatypeDefinition(
        name=raw.get("DatatypeName") or raw.get("DatatypeReferenceName") or "anonymous",
        kind=raw.get("Datatype") or "Unknown",
        raw=raw,
    )


def _parameters(raw_parameters: list[dict[str, Any]] | None) -> list[ParameterDefinition]:
    parameters: list[ParameterDefinition] = []
    for raw in raw_parameters or []:
        parameters.append(
            ParameterDefinition(
                name=raw.get("ParameterName") or "",
                position=_parse_int(raw.get("Position")),
                direction=raw.get("IN/OUT"),
                datatype=_datatype(raw["DatatypeReference"]),
            )
        )
    return parameters


def _transport(raw: str | None, fallback: TransportProtocol) -> TransportProtocol:
    if raw in ("TCP", "UDP"):
        return TransportProtocol(raw)
    return fallback


def _send_strategy(raw: str | None) -> SendStrategy | None:
    if raw in ("Trigger", "Cycle"):
        return SendStrategy(raw)
    return None


def _group_fields(parts: list[FieldPartDefinition]) -> list[FieldDefinition]:
    grouped: dict[str, dict[FieldType, FieldPartDefinition]] = {}
    order: list[str] = []
    for part in parts:
        if part.name not in grouped:
            grouped[part.name] = {}
            order.append(part.name)
        grouped[part.name][part.field_type] = part

    return [
        FieldDefinition(
            name=name,
            getter=grouped[name].get(FieldType.GETTER),
            setter=grouped[name].get(FieldType.SETTER),
            notifier=grouped[name].get(FieldType.NOTIFIER),
        )
        for name in order
    ]


def _deployment(raw: dict[str, Any]) -> DeploymentConfig:
    default_transport = TransportProtocol(raw["Transport Protocol"])
    return DeploymentConfig(
        instance_id=_parse_int(raw["Service Interface Instance ID"]) or 0,
        major_version=int(raw["Major Version"]),
        minor_version=int(raw["Minor Version"]),
        server_ecu=raw["Server ECU"],
        server_ip=raw["Server IP Address"],
        client_ecu=raw["Client ECU"],
        client_ip=raw["Client IP Address"],
        multicast_ip=raw["Multicast IP Address"],
        vlan_id=_parse_int(raw.get("VLAN ID")),
        vlan_priority=_parse_int(raw.get("VLAN Priority")),
        default_transport=default_transport,
        offer_ttl_s=_timing(raw, "ttl for offer", 3.0),
        find_ttl_s=_timing(raw, "ttl for find", 3.0),
    )


def load_service_definition(path: Path) -> ServiceDefinition:
    text = path.read_text(encoding="utf-8-sig").lstrip("\ufeff\ufffc\r\n\t ")
    raw = json.loads(text)
    deployment = _deployment(raw["Deployment"])

    methods: list[MethodDefinition] = []
    events: list[EventDefinition] = []
    field_parts: list[FieldPartDefinition] = []

    for element in raw.get("ServiceInterfaces", []):
        transmission = element.get("TransmissionType")
        parameters = _parameters(element.get("Parameters"))
        transport = _transport(element.get("L4-Protocol"), deployment.default_transport)
        element_id = _parse_int(element.get("ElementID")) or 0

        if transmission == "Method":
            methods.append(
                MethodDefinition(
                    name=element["ElementName"],
                    method_id=element_id,
                    rr_ff=element.get("RR/FF"),
                    transport=transport,
                    parameters=parameters,
                    description=element.get("ElementDescription"),
                )
            )
        elif transmission == "Event":
            events.append(
                EventDefinition(
                    name=element["ElementName"],
                    event_id=element_id,
                    eventgroup_name=element.get("EventgroupName"),
                    eventgroup_id=_parse_int(element.get("EventgroupID")),
                    transport=transport,
                    send_strategy=_send_strategy(element.get("SendStrategy")),
                    cycle_time_s=(
                        _parse_float(element.get("CycleTime"))
                        if element.get("CycleTime") is not None
                        else None
                    ),
                    parameters=parameters,
                    description=element.get("ElementDescription"),
                )
            )
        elif transmission == "Field":
            field_parts.append(
                FieldPartDefinition(
                    name=element["ElementName"],
                    field_type=FieldType(element["FieldType"]),
                    element_id=element_id,
                    eventgroup_name=element.get("EventgroupName"),
                    eventgroup_id=_parse_int(element.get("EventgroupID")),
                    transport=transport,
                    parameters=parameters,
                    description=element.get("ElementDescription"),
                )
            )

    return ServiceDefinition(
        service_id=_parse_int(raw["ServiceInterfaceID"]) or 0,
        service_name=raw["ServiceInterfaceName"],
        deployment=deployment,
        methods=methods,
        events=events,
        fields=_group_fields(field_parts),
    )


def load_service_directory(directory: Path) -> list[ServiceDefinition]:
    return [load_service_definition(path) for path in sorted(directory.glob("*.json"))]
