from __future__ import annotations

import struct
from typing import Any

from someip_gui_tool.domain.models import DatatypeDefinition, ParameterDefinition


class PayloadCodec:
    def encode_parameters(
        self, parameters: list[ParameterDefinition], values: dict[str, Any]
    ) -> bytes:
        chunks = [
            self._encode_datatype(parameter.datatype, values[parameter.name])
            for parameter in parameters
        ]
        return b"".join(chunks)

    def decode_parameters(
        self, parameters: list[ParameterDefinition], payload: bytes
    ) -> dict[str, Any]:
        offset = 0
        decoded: dict[str, Any] = {}
        for parameter in parameters:
            value, offset = self._decode_datatype(parameter.datatype, payload, offset)
            decoded[parameter.name] = value
        if offset != len(payload):
            raise ValueError("Payload contains trailing bytes")
        return decoded

    def _encode_datatype(self, datatype: DatatypeDefinition | dict[str, Any], value: Any) -> bytes:
        raw = self._raw(datatype)
        kind = raw.get("Datatype")

        if kind in {"Typedef", "Integer", "Float", "Enum", "String"}:
            typedef = raw.get("TypedefReference")
            if typedef is None:
                raise ValueError(f"Datatype {raw.get('DatatypeName')!r} has no typedef")
            return self._encode_datatype(typedef, value)

        if kind == "BasicType":
            return self._encode_basic(raw.get("DatatypeName"), value)

        if kind == "Array":
            element_type = raw.get("ElementType")
            if element_type is None:
                raise ValueError(f"Array {raw.get('DatatypeName')!r} has no element type")
            return b"".join(self._encode_datatype(element_type, item) for item in value)

        if kind == "Struct":
            return b"".join(
                self._encode_datatype(member["DatatypeReference"], value[member["MemberName"]])
                for member in self._members(raw)
            )

        raise ValueError(f"Unsupported datatype: {kind!r}")

    def _decode_datatype(
        self, datatype: DatatypeDefinition | dict[str, Any], payload: bytes, offset: int
    ) -> tuple[Any, int]:
        raw = self._raw(datatype)
        kind = raw.get("Datatype")

        if kind in {"Typedef", "Integer", "Float", "Enum", "String"}:
            typedef = raw.get("TypedefReference")
            if typedef is None:
                raise ValueError(f"Datatype {raw.get('DatatypeName')!r} has no typedef")
            return self._decode_datatype(typedef, payload, offset)

        if kind == "BasicType":
            return self._decode_basic(raw.get("DatatypeName"), payload, offset)

        if kind == "Array":
            element_type = raw.get("ElementType")
            if element_type is None:
                raise ValueError(f"Array {raw.get('DatatypeName')!r} has no element type")
            values = []
            while offset < len(payload):
                item, offset = self._decode_datatype(element_type, payload, offset)
                values.append(item)
            return values, offset

        if kind == "Struct":
            values: dict[str, Any] = {}
            for member in self._members(raw):
                values[member["MemberName"]], offset = self._decode_datatype(
                    member["DatatypeReference"], payload, offset
                )
            return values, offset

        raise ValueError(f"Unsupported datatype: {kind!r}")

    def _encode_basic(self, name: str | None, value: Any) -> bytes:
        if name == "uint8":
            return struct.pack(">B", int(value))
        if name == "uint64":
            return struct.pack(">Q", int(value))
        if name == "float32":
            return struct.pack(">f", float(value))
        if name == "utf8":
            return str(value).encode("utf-8")
        raise ValueError(f"Unsupported basic type: {name!r}")

    def _decode_basic(self, name: str | None, payload: bytes, offset: int) -> tuple[Any, int]:
        if name == "uint8":
            return self._unpack(">B", payload, offset)
        if name == "uint64":
            return self._unpack(">Q", payload, offset)
        if name == "float32":
            return self._unpack(">f", payload, offset)
        if name == "utf8":
            return payload[offset:].decode("utf-8"), len(payload)
        raise ValueError(f"Unsupported basic type: {name!r}")

    def _unpack(self, format_string: str, payload: bytes, offset: int) -> tuple[Any, int]:
        size = struct.calcsize(format_string)
        end = offset + size
        if end > len(payload):
            raise ValueError("Payload ended before datatype could be decoded")
        return struct.unpack(format_string, payload[offset:end])[0], end

    def _members(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        return sorted(raw.get("Members", []), key=lambda member: member.get("Position", 0))

    def _raw(self, datatype: DatatypeDefinition | dict[str, Any]) -> dict[str, Any]:
        if isinstance(datatype, DatatypeDefinition):
            return datatype.raw
        return datatype
