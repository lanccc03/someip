from __future__ import annotations

import json
from typing import Any

from someip_gui_tool.domain.models import DatatypeDefinition, ParameterDefinition


def payload_values_json(parameters: list[ParameterDefinition]) -> str:
    return json.dumps(default_payload_values(parameters), indent=2, sort_keys=True) + "\n"


def default_payload_values(parameters: list[ParameterDefinition]) -> dict[str, Any]:
    return {parameter.name: _default_for_datatype(parameter.datatype) for parameter in parameters}


def _default_for_datatype(datatype: DatatypeDefinition | dict[str, Any]) -> Any:
    raw = datatype.raw if isinstance(datatype, DatatypeDefinition) else datatype
    kind = raw.get("Datatype")

    if kind in {"Typedef", "Integer", "Enum", "String", "Float"}:
        typedef = raw.get("TypedefReference")
        if typedef is None:
            return ""
        return _default_for_datatype(typedef)

    if kind == "BasicType":
        name = raw.get("DatatypeName")
        if name == "float32":
            return 0.0
        if name == "utf8":
            return ""
        return 0

    if kind == "Array":
        return []

    if kind == "Struct":
        members = sorted(raw.get("Members", []), key=lambda member: member.get("Position", 0))
        return {
            member["MemberName"]: _default_for_datatype(member["DatatypeReference"])
            for member in members
        }

    return None
