# SOME/IP GUI Test Tool MVP-1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP-1 foundation for a Windows x64 PySide SOME/IP manual test tool: JSON import, domain models, payload codec, trace/export, protocol adapter boundary, someipy spike harness, and a minimal GUI shell.

**Architecture:** Create a layered Python package under `src/someip_gui_tool`: domain and JSON parsing are independent from GUI and protocol backend; payload codec is isolated; protocol access goes through an adapter interface with a mock implementation first and a someipy spike harness second. The PySide app consumes Core services only.

**Tech Stack:** Python 3.11+, PySide6, pytest, pydantic, qasync, optional someipy, PyInstaller.

---

## Scope

This plan implements the first executable foundation, not the complete polished GUI. It must prove that the current `ADC40_SOC/*.json` files can be parsed, modeled, encoded/decoded, traced, and driven through a replaceable adapter boundary.

Covered here:

- Project scaffolding.
- Service JSON parser.
- Method/Event/Field/datatype domain models.
- Field grouping by `ElementName`.
- Payload codec for datatypes currently present in `ADC40_SOC`.
- Project runtime override model.
- Trace and export model.
- Adapter interface plus mock adapter.
- someipy spike harness entry point.
- Minimal PySide window that imports definitions and shows services/elements.
- Packaging smoke configuration.

Not covered here:

- Full production GUI polish.
- Full action sequence editor.
- Complete CLI.
- ARXML import.
- Automatic VLAN or firewall configuration.

## Planned File Structure

- Create: `pyproject.toml` - package metadata, runtime dependencies, dev dependencies, pytest config.
- Create: `src/someip_gui_tool/__init__.py` - package marker and version.
- Create: `src/someip_gui_tool/domain/models.py` - immutable domain models for services, elements, fields, datatypes, deployments, runtime config.
- Create: `src/someip_gui_tool/domain/enums.py` - role, transport, transmission, field, send strategy, and trace enums.
- Create: `src/someip_gui_tool/parsing/service_json.py` - loader and normalizer for `ADC40_SOC/*.json`.
- Create: `src/someip_gui_tool/codec/payload_codec.py` - structured value to bytes and bytes to structured value conversion.
- Create: `src/someip_gui_tool/project/project_model.py` - project file schema and runtime overrides.
- Create: `src/someip_gui_tool/tracing/trace_model.py` - run log and message trace data structures.
- Create: `src/someip_gui_tool/tracing/exporters.py` - JSON and CSV export functions.
- Create: `src/someip_gui_tool/adapters/base.py` - protocol adapter interface.
- Create: `src/someip_gui_tool/adapters/mock.py` - deterministic mock adapter for tests and GUI development.
- Create: `src/someip_gui_tool/adapters/someipy_spike.py` - small spike harness around someipy availability and minimal scenario hooks.
- Create: `src/someip_gui_tool/core/service_registry.py` - imports definitions and exposes query helpers for GUI/CLI.
- Create: `src/someip_gui_tool/gui/app.py` - PySide application entry point.
- Create: `src/someip_gui_tool/gui/main_window.py` - minimal main window with service tree and details panel.
- Create: `src/someip_gui_tool/__main__.py` - `python -m someip_gui_tool` entry.
- Create: `tests/conftest.py` - shared test fixtures.
- Create: `tests/test_service_json_parser.py` - parser tests using current ADC40_SOC files.
- Create: `tests/test_field_grouping.py` - field grouping tests for `0x080C.json`.
- Create: `tests/test_payload_codec.py` - codec tests for enum, integer, float, string, array, struct, typedef.
- Create: `tests/test_project_model.py` - runtime override/project file tests.
- Create: `tests/test_trace_exporters.py` - trace JSON/CSV export tests.
- Create: `tests/test_mock_adapter.py` - adapter contract tests.
- Create: `scripts/run_someipy_spike.py` - operator script for the manual someipy spike.
- Create: `packaging/pyinstaller/someip-gui-tool.spec` - packaging smoke spec.

---

### Task 1: Create Python Package Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/someip_gui_tool/__init__.py`
- Create: `src/someip_gui_tool/__main__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the initial package metadata**

Create `pyproject.toml` with this content:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "someip-gui-tool"
version = "0.1.0"
description = "PySide SOME/IP manual test tool"
requires-python = ">=3.11"
dependencies = [
  "pydantic>=2.7,<3",
  "PySide6>=6.7,<7",
  "qasync>=0.27,<1",
]

[project.optional-dependencies]
dev = [
  "pytest>=8,<9",
  "pytest-qt>=4.4,<5",
  "pyinstaller>=6,<7",
]
someipy = [
  "someipy>=2.1,<3",
]

[project.scripts]
someip-gui-tool = "someip_gui_tool.gui.app:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-q"
```

- [ ] **Step 2: Add package entry files**

Create `src/someip_gui_tool/__init__.py`:

```python
"""SOME/IP GUI test tool."""

__version__ = "0.1.0"
```

Create `src/someip_gui_tool/__main__.py`:

```python
from someip_gui_tool.gui.app import main


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `tests/conftest.py`:

```python
from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def adc40_soc_dir(repo_root: Path) -> Path:
    return repo_root / "ADC40_SOC"
```

- [ ] **Step 3: Run package metadata smoke check**

Run:

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

Expected:

```text
no tests ran
```

- [ ] **Step 4: Commit scaffold**

Run:

```powershell
git add pyproject.toml src/someip_gui_tool tests/conftest.py
git commit -m "chore: scaffold someip gui tool package"
```

Expected: commit succeeds.

---

### Task 2: Add Domain Enums and Models

**Files:**
- Create: `src/someip_gui_tool/domain/enums.py`
- Create: `src/someip_gui_tool/domain/models.py`
- Create: `tests/test_service_json_parser.py`

- [ ] **Step 1: Write failing model construction test**

Create `tests/test_service_json_parser.py` with the first test:

```python
from someip_gui_tool.domain.enums import Role, TransportProtocol
from someip_gui_tool.domain.models import DeploymentConfig, ServiceDefinition


def test_service_definition_model_accepts_hex_ids():
    deployment = DeploymentConfig(
        instance_id=0x0001,
        major_version=1,
        minor_version=0,
        server_ecu="ADC40_SOC",
        server_ip="172.16.3.14/24",
        client_ecu="HUT_SOC_Android",
        client_ip="172.16.3.99/24",
        multicast_ip="239.192.255.251",
        vlan_id=3,
        vlan_priority=3,
        default_transport=TransportProtocol.TCP,
        offer_ttl_s=3.0,
        find_ttl_s=3.0,
    )
    service = ServiceDefinition(
        service_id=0x080A,
        service_name="CockpitIntellgntDecouplingSrv",
        deployment=deployment,
        methods=[],
        events=[],
        fields=[],
    )

    assert service.service_id_hex == "0x080A"
    assert service.deployment.local_ip_for(Role.SERVER) == "172.16.3.14/24"
    assert service.deployment.local_ip_for(Role.CLIENT) == "172.16.3.99/24"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_service_json_parser.py::test_service_definition_model_accepts_hex_ids -q
```

Expected: FAIL with `ModuleNotFoundError` for `someip_gui_tool.domain`.

- [ ] **Step 3: Implement enums**

Create `src/someip_gui_tool/domain/enums.py`:

```python
from enum import StrEnum


class Role(StrEnum):
    CLIENT = "Client"
    SERVER = "Server"


class TransportProtocol(StrEnum):
    TCP = "TCP"
    UDP = "UDP"


class TransmissionType(StrEnum):
    METHOD = "Method"
    EVENT = "Event"
    FIELD = "Field"


class FieldType(StrEnum):
    GETTER = "Getter"
    SETTER = "Setter"
    NOTIFIER = "Notifier"


class SendStrategy(StrEnum):
    TRIGGER = "Trigger"
    CYCLE = "Cycle"


class TraceDirection(StrEnum):
    TX = "TX"
    RX = "RX"
```

- [ ] **Step 4: Implement domain models**

Create `src/someip_gui_tool/domain/models.py`:

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```powershell
python -m pytest tests/test_service_json_parser.py::test_service_definition_model_accepts_hex_ids -q
```

Expected: PASS.

- [ ] **Step 6: Commit domain models**

Run:

```powershell
git add src/someip_gui_tool/domain tests/test_service_json_parser.py
git commit -m "feat: add someip domain models"
```

Expected: commit succeeds.

---

### Task 3: Parse ADC40_SOC JSON Service Definitions

**Files:**
- Create: `src/someip_gui_tool/parsing/service_json.py`
- Modify: `tests/test_service_json_parser.py`

- [ ] **Step 1: Add failing parser tests**

Append to `tests/test_service_json_parser.py`:

```python
from someip_gui_tool.parsing.service_json import load_service_definition, load_service_directory


def test_load_second_start_service(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080D.json")

    assert service.service_id == 0x080D
    assert service.service_name == "SecondStartSrv"
    assert service.deployment.instance_id == 0x0001
    assert service.deployment.default_transport.value == "UDP"
    assert [event.name for event in service.events] == ["SecondStartPopup"]
    assert [method.name for method in service.methods] == ["SecondStartCtrl"]
    assert service.methods[0].method_id == 0x0001
    assert service.events[0].eventgroup_id == 0x0001


def test_load_service_directory_includes_all_json(adc40_soc_dir):
    services = load_service_directory(adc40_soc_dir)
    ids = {service.service_id for service in services}

    assert {0x080A, 0x080C, 0x080D, 0x080E, 0x0F01}.issubset(ids)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_service_json_parser.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `someip_gui_tool.parsing`.

- [ ] **Step 3: Implement JSON parser**

Create `src/someip_gui_tool/parsing/service_json.py`:

```python
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
        return int(value, 16) if value.lower().startswith("0x") else int(value)
    raise TypeError(f"Unsupported integer value: {value!r}")


def _parse_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "/":
        return default
    return float(value)


def _field(deployment: dict[str, Any], name: str, default: Any = None) -> Any:
    return deployment.get(name, default)


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
    result: list[ParameterDefinition] = []
    for raw in raw_parameters or []:
        result.append(
            ParameterDefinition(
                name=raw.get("ParameterName") or "",
                position=_parse_int(raw.get("Position")),
                direction=raw.get("IN/OUT"),
                datatype=_datatype(raw["DatatypeReference"]),
            )
        )
    return result


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
    for part in parts:
        grouped.setdefault(part.name, {})[part.field_type] = part
    return [
        FieldDefinition(
            name=name,
            getter=by_type.get(FieldType.GETTER),
            setter=by_type.get(FieldType.SETTER),
            notifier=by_type.get(FieldType.NOTIFIER),
        )
        for name, by_type in sorted(grouped.items())
    ]


def load_service_definition(path: Path) -> ServiceDefinition:
    text = path.read_text(encoding="utf-8-sig")
    raw = json.loads(text)
    deployment_raw = raw["Deployment"]
    default_transport = TransportProtocol(deployment_raw["Transport Protocol"])

    deployment = DeploymentConfig(
        instance_id=_parse_int(deployment_raw["Service Interface Instance ID"]) or 0,
        major_version=int(deployment_raw["Major Version"]),
        minor_version=int(deployment_raw["Minor Version"]),
        server_ecu=deployment_raw["Server ECU"],
        server_ip=deployment_raw["Server IP Address"],
        client_ecu=deployment_raw["Client ECU"],
        client_ip=deployment_raw["Client IP Address"],
        multicast_ip=deployment_raw["Multicast IP Address"],
        vlan_id=_parse_int(deployment_raw.get("VLAN ID")),
        vlan_priority=_parse_int(deployment_raw.get("VLAN Priority")),
        default_transport=default_transport,
        offer_ttl_s=_timing(deployment_raw, "ttl for offer", 3.0),
        find_ttl_s=_timing(deployment_raw, "ttl for find", 3.0),
    )

    methods: list[MethodDefinition] = []
    events: list[EventDefinition] = []
    field_parts: list[FieldPartDefinition] = []

    for element in raw.get("ServiceInterfaces", []):
        transmission = element.get("TransmissionType")
        params = _parameters(element.get("Parameters"))
        transport = _transport(element.get("L4-Protocol"), default_transport)
        element_id = _parse_int(element.get("ElementID")) or 0

        if transmission == "Method":
            methods.append(
                MethodDefinition(
                    name=element["ElementName"],
                    method_id=element_id,
                    rr_ff=element.get("RR/FF"),
                    transport=transport,
                    parameters=params,
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
                    cycle_time_s=_parse_float(element.get("CycleTime"), default=0.0)
                    if element.get("CycleTime") is not None
                    else None,
                    parameters=params,
                    description=element.get("ElementDescription"),
                )
            )
        elif transmission == "Field":
            field_type = FieldType(element["FieldType"])
            field_parts.append(
                FieldPartDefinition(
                    name=element["ElementName"],
                    field_type=field_type,
                    element_id=element_id,
                    eventgroup_name=element.get("EventgroupName"),
                    eventgroup_id=_parse_int(element.get("EventgroupID")),
                    transport=transport,
                    parameters=params,
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
```

- [ ] **Step 4: Run parser tests**

Run:

```powershell
python -m pytest tests/test_service_json_parser.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit parser**

Run:

```powershell
git add src/someip_gui_tool/parsing tests/test_service_json_parser.py
git commit -m "feat: parse someip service json definitions"
```

Expected: commit succeeds.

---

### Task 4: Validate Field Grouping

**Files:**
- Create: `tests/test_field_grouping.py`
- Modify: `src/someip_gui_tool/parsing/service_json.py` only if the test exposes a grouping defect.

- [ ] **Step 1: Write field grouping test**

Create `tests/test_field_grouping.py`:

```python
from someip_gui_tool.parsing.service_json import load_service_definition


def test_groups_getter_and_notifier_by_field_name(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")

    assert len(service.fields) == 1
    field = service.fields[0]
    assert field.name == "VertHeiRmdSts"
    assert field.getter is not None
    assert field.getter.element_id == 0x1001
    assert field.setter is None
    assert field.notifier is not None
    assert field.notifier.element_id == 0x9001
    assert field.notifier.eventgroup_id == 0x0001
```

- [ ] **Step 2: Run field grouping test**

Run:

```powershell
python -m pytest tests/test_field_grouping.py -q
```

Expected: PASS. If it fails, fix only `_group_fields` in `src/someip_gui_tool/parsing/service_json.py` until this exact test passes.

- [ ] **Step 3: Commit field grouping coverage**

Run:

```powershell
git add tests/test_field_grouping.py src/someip_gui_tool/parsing/service_json.py
git commit -m "test: cover field getter notifier grouping"
```

Expected: commit succeeds.

---

### Task 5: Implement Payload Codec for Current Datatypes

**Files:**
- Create: `src/someip_gui_tool/codec/payload_codec.py`
- Create: `tests/test_payload_codec.py`

- [ ] **Step 1: Write codec tests**

Create `tests/test_payload_codec.py`:

```python
import math

from someip_gui_tool.codec.payload_codec import PayloadCodec
from someip_gui_tool.parsing.service_json import load_service_definition


def _first_param(service, element_name):
    for collection in (service.methods, service.events):
        for element in collection:
            if element.name == element_name:
                return element.parameters[0]
    for field in service.fields:
        for part in (field.getter, field.setter, field.notifier):
            if part and part.name == element_name:
                return part.parameters[0]
    raise AssertionError(f"element not found: {element_name}")


def test_enum_encodes_to_underlying_uint8(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080D.json")
    param = _first_param(service, "SecondStartPopup")

    encoded = PayloadCodec().encode_parameters([param], {"SecondStartPopup": 2})

    assert encoded == b"\x02"


def test_float_struct_round_trip(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    param = _first_param(service, "VehicleInfo")
    codec = PayloadCodec()

    encoded = codec.encode_parameters([param], {"VehicleInfo": {"VehicleSpeed": 12.5, "Odometer": 99.25}})
    decoded = codec.decode_parameters([param], encoded)

    assert math.isclose(decoded["VehicleInfo"]["VehicleSpeed"], 12.5, rel_tol=0.0001)
    assert math.isclose(decoded["VehicleInfo"]["Odometer"], 99.25, rel_tol=0.0001)


def test_uint8_array_encodes_all_values(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080A.json")
    param = _first_param(service, "IntellgntSwtDecoupSts")

    encoded = PayloadCodec().encode_parameters([param], {"IntellgntSwtDecoupSts": [1, 2, 255]})

    assert encoded == b"\x01\x02\xff"


def test_string_encodes_utf8(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x0F01.json")
    param = _first_param(service, "SlotIDReport")

    encoded = PayloadCodec().encode_parameters([param], {"SlotID": "A12"})

    assert encoded == b"A12"
```

- [ ] **Step 2: Run codec tests to verify failure**

Run:

```powershell
python -m pytest tests/test_payload_codec.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `someip_gui_tool.codec`.

- [ ] **Step 3: Implement payload codec**

Create `src/someip_gui_tool/codec/payload_codec.py`:

```python
from __future__ import annotations

import struct
from typing import Any

from someip_gui_tool.domain.models import ParameterDefinition


class PayloadCodec:
    def encode_parameters(self, parameters: list[ParameterDefinition], values: dict[str, Any]) -> bytes:
        payload = bytearray()
        for parameter in parameters:
            payload.extend(self._encode_datatype(parameter.datatype.raw, values[parameter.name]))
        return bytes(payload)

    def decode_parameters(self, parameters: list[ParameterDefinition], payload: bytes) -> dict[str, Any]:
        offset = 0
        decoded: dict[str, Any] = {}
        for parameter in parameters:
            value, offset = self._decode_datatype(parameter.datatype.raw, payload, offset)
            decoded[parameter.name] = value
        return decoded

    def _encode_datatype(self, raw: dict[str, Any], value: Any) -> bytes:
        kind = raw.get("Datatype")
        if kind == "Typedef":
            return self._encode_basic(raw["TypedefReference"]["DatatypeName"], value)
        if kind == "BasicType":
            return self._encode_basic(raw["DatatypeName"], value)
        if kind == "Enum":
            return self._encode_basic(raw["TypedefReference"]["DatatypeName"], value)
        if kind == "Integer":
            return self._encode_basic(raw["TypedefReference"]["DatatypeName"], value)
        if kind == "Float":
            return self._encode_basic(raw["TypedefReference"]["DatatypeName"], value)
        if kind == "String":
            return str(value).encode("utf-8")
        if kind == "Array":
            element_type = raw["ElementType"]
            return b"".join(self._encode_datatype(element_type, item) for item in value)
        if kind == "Struct":
            payload = bytearray()
            for member in sorted(raw["Members"], key=lambda item: item["Position"]):
                payload.extend(self._encode_datatype(member["DatatypeReference"], value[member["MemberName"]]))
            return bytes(payload)
        raise ValueError(f"Unsupported datatype for encode: {kind}")

    def _decode_datatype(self, raw: dict[str, Any], payload: bytes, offset: int) -> tuple[Any, int]:
        kind = raw.get("Datatype")
        if kind == "Typedef":
            return self._decode_basic(raw["TypedefReference"]["DatatypeName"], payload, offset)
        if kind == "BasicType":
            return self._decode_basic(raw["DatatypeName"], payload, offset)
        if kind == "Enum":
            return self._decode_basic(raw["TypedefReference"]["DatatypeName"], payload, offset)
        if kind == "Integer":
            return self._decode_basic(raw["TypedefReference"]["DatatypeName"], payload, offset)
        if kind == "Float":
            return self._decode_basic(raw["TypedefReference"]["DatatypeName"], payload, offset)
        if kind == "String":
            return payload[offset:].decode("utf-8"), len(payload)
        if kind == "Array":
            element_type = raw["ElementType"]
            values = []
            while offset < len(payload):
                value, offset = self._decode_datatype(element_type, payload, offset)
                values.append(value)
            return values, offset
        if kind == "Struct":
            values: dict[str, Any] = {}
            for member in sorted(raw["Members"], key=lambda item: item["Position"]):
                value, offset = self._decode_datatype(member["DatatypeReference"], payload, offset)
                values[member["MemberName"]] = value
            return values, offset
        raise ValueError(f"Unsupported datatype for decode: {kind}")

    def _encode_basic(self, basic_type: str, value: Any) -> bytes:
        if basic_type == "uint8":
            return struct.pack(">B", int(value))
        if basic_type == "uint64":
            return struct.pack(">Q", int(value))
        if basic_type == "float32":
            return struct.pack(">f", float(value))
        if basic_type == "utf8":
            return str(value).encode("utf-8")
        raise ValueError(f"Unsupported basic type for encode: {basic_type}")

    def _decode_basic(self, basic_type: str, payload: bytes, offset: int) -> tuple[Any, int]:
        if basic_type == "uint8":
            return struct.unpack_from(">B", payload, offset)[0], offset + 1
        if basic_type == "uint64":
            return struct.unpack_from(">Q", payload, offset)[0], offset + 8
        if basic_type == "float32":
            return struct.unpack_from(">f", payload, offset)[0], offset + 4
        if basic_type == "utf8":
            return payload[offset:].decode("utf-8"), len(payload)
        raise ValueError(f"Unsupported basic type for decode: {basic_type}")
```

- [ ] **Step 4: Run codec tests**

Run:

```powershell
python -m pytest tests/test_payload_codec.py -q
```

Expected: PASS.

- [ ] **Step 5: Run parser and codec tests together**

Run:

```powershell
python -m pytest tests/test_service_json_parser.py tests/test_field_grouping.py tests/test_payload_codec.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit payload codec**

Run:

```powershell
git add src/someip_gui_tool/codec tests/test_payload_codec.py
git commit -m "feat: add payload codec for json datatypes"
```

Expected: commit succeeds.

---

### Task 6: Add Project Runtime Override Model

**Files:**
- Create: `src/someip_gui_tool/project/project_model.py`
- Create: `tests/test_project_model.py`

- [ ] **Step 1: Write project model tests**

Create `tests/test_project_model.py`:

```python
from pathlib import Path

from someip_gui_tool.domain.enums import Role, TransportProtocol
from someip_gui_tool.project.project_model import (
    ProjectFile,
    ServiceRuntimeOverride,
)


def test_project_file_round_trip():
    project = ProjectFile(
        schema_version="1.0",
        project_name="ADC40_SOC manual test",
        definition_root=Path("ADC40_SOC"),
        services={
            "0x080D": ServiceRuntimeOverride(
                enabled=True,
                role=Role.CLIENT,
                local_ip="172.16.2.99/24",
                remote_ip="172.16.2.14/24",
                server_port=30501,
                client_port=0,
                multicast_ip="239.192.255.251",
                transport=TransportProtocol.UDP,
            )
        },
        sequences=[],
    )

    restored = ProjectFile.model_validate_json(project.model_dump_json())

    assert restored.services["0x080D"].role is Role.CLIENT
    assert restored.services["0x080D"].server_port == 30501
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m pytest tests/test_project_model.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `someip_gui_tool.project`.

- [ ] **Step 3: Implement project model**

Create `src/someip_gui_tool/project/project_model.py`:

```python
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
```

- [ ] **Step 4: Run project tests**

Run:

```powershell
python -m pytest tests/test_project_model.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit project model**

Run:

```powershell
git add src/someip_gui_tool/project tests/test_project_model.py
git commit -m "feat: add project runtime override model"
```

Expected: commit succeeds.

---

### Task 7: Add Trace Models and Exporters

**Files:**
- Create: `src/someip_gui_tool/tracing/trace_model.py`
- Create: `src/someip_gui_tool/tracing/exporters.py`
- Create: `tests/test_trace_exporters.py`

- [ ] **Step 1: Write trace exporter tests**

Create `tests/test_trace_exporters.py`:

```python
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
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m pytest tests/test_trace_exporters.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `someip_gui_tool.tracing`.

- [ ] **Step 3: Implement trace models**

Create `src/someip_gui_tool/tracing/trace_model.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from someip_gui_tool.domain.enums import Role, TraceDirection, TransportProtocol


class RunLogEntry(BaseModel):
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
    decoded_payload: dict[str, Any]
    payload_decode_status: str = "ok"
    duration_ms: float | None = None
    result: str
    error_message: str | None = None
```

- [ ] **Step 4: Implement exporters**

Create `src/someip_gui_tool/tracing/exporters.py`:

```python
from __future__ import annotations

import csv
import io

from someip_gui_tool.tracing.trace_model import MessageTraceEntry, RunLogEntry


def export_trace_json(entries: list[MessageTraceEntry]) -> str:
    return "[" + ",".join(entry.model_dump_json() for entry in entries) + "]"


def export_run_log_json(entries: list[RunLogEntry]) -> str:
    return "[" + ",".join(entry.model_dump_json() for entry in entries) + "]"


def export_run_log_text(entries: list[RunLogEntry]) -> str:
    return "\n".join(
        f"{entry.timestamp.isoformat()} [{entry.level.upper()}] {entry.source}: {entry.message}"
        for entry in entries
    )


def export_trace_csv(entries: list[MessageTraceEntry]) -> str:
    buffer = io.StringIO()
    fieldnames = [
        "timestamp",
        "direction",
        "role",
        "service_id",
        "instance_id",
        "element_type",
        "element_id",
        "transport",
        "result",
        "raw_payload_hex",
        "decoded_payload",
        "error_message",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for entry in entries:
        data = entry.model_dump(mode="json")
        writer.writerow({name: data.get(name) for name in fieldnames})
    return buffer.getvalue()
```

- [ ] **Step 5: Run trace tests**

Run:

```powershell
python -m pytest tests/test_trace_exporters.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit trace/export**

Run:

```powershell
git add src/someip_gui_tool/tracing tests/test_trace_exporters.py
git commit -m "feat: add trace models and exporters"
```

Expected: commit succeeds.

---

### Task 8: Add Adapter Interface and Mock Adapter

**Files:**
- Create: `src/someip_gui_tool/adapters/base.py`
- Create: `src/someip_gui_tool/adapters/mock.py`
- Create: `tests/test_mock_adapter.py`

- [ ] **Step 1: Write mock adapter contract test**

Create `tests/test_mock_adapter.py`:

```python
import pytest

from someip_gui_tool.adapters.mock import MockSomeIpAdapter
from someip_gui_tool.parsing.service_json import load_service_definition


@pytest.mark.asyncio
async def test_mock_adapter_records_method_and_event(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080D.json")
    adapter = MockSomeIpAdapter()

    await adapter.start_service(service)
    await adapter.call_method(service, service.methods[0], b"\x01")
    await adapter.publish_event(service, service.events[0], b"\x02")
    await adapter.stop_service(service)

    assert [call.name for call in adapter.calls] == [
        "start_service",
        "call_method",
        "publish_event",
        "stop_service",
    ]
```

- [ ] **Step 2: Run adapter test to verify failure**

Run:

```powershell
python -m pytest tests/test_mock_adapter.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `someip_gui_tool.adapters`.

- [ ] **Step 3: Add pytest asyncio dependency**

Modify `pyproject.toml` dev dependencies to include:

```toml
  "pytest-asyncio>=0.23,<1",
```

- [ ] **Step 4: Implement adapter interface**

Create `src/someip_gui_tool/adapters/base.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from someip_gui_tool.domain.models import EventDefinition, MethodDefinition, ServiceDefinition


class SomeIpAdapter(ABC):
    @abstractmethod
    async def start_service(self, service: ServiceDefinition) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop_service(self, service: ServiceDefinition) -> None:
        raise NotImplementedError

    @abstractmethod
    async def call_method(
        self,
        service: ServiceDefinition,
        method: MethodDefinition,
        payload: bytes,
    ) -> bytes | None:
        raise NotImplementedError

    @abstractmethod
    async def subscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def publish_event(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        payload: bytes,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def shutdown(self) -> None:
        raise NotImplementedError
```

- [ ] **Step 5: Implement mock adapter**

Create `src/someip_gui_tool/adapters/mock.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from someip_gui_tool.adapters.base import SomeIpAdapter
from someip_gui_tool.domain.models import EventDefinition, MethodDefinition, ServiceDefinition


@dataclass(frozen=True)
class AdapterCall:
    name: str
    details: dict[str, object]


class MockSomeIpAdapter(SomeIpAdapter):
    def __init__(self) -> None:
        self.calls: list[AdapterCall] = []

    async def start_service(self, service: ServiceDefinition) -> None:
        self.calls.append(AdapterCall("start_service", {"service_id": service.service_id_hex}))

    async def stop_service(self, service: ServiceDefinition) -> None:
        self.calls.append(AdapterCall("stop_service", {"service_id": service.service_id_hex}))

    async def call_method(
        self,
        service: ServiceDefinition,
        method: MethodDefinition,
        payload: bytes,
    ) -> bytes | None:
        self.calls.append(
            AdapterCall(
                "call_method",
                {
                    "service_id": service.service_id_hex,
                    "method_id": method.method_id_hex,
                    "payload": payload.hex(),
                },
            )
        )
        return None

    async def subscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        self.calls.append(
            AdapterCall(
                "subscribe_eventgroup",
                {"service_id": service.service_id_hex, "eventgroup_id": f"0x{eventgroup_id:04X}"},
            )
        )

    async def publish_event(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        payload: bytes,
    ) -> None:
        self.calls.append(
            AdapterCall(
                "publish_event",
                {
                    "service_id": service.service_id_hex,
                    "event_id": event.event_id_hex,
                    "payload": payload.hex(),
                },
            )
        )

    async def shutdown(self) -> None:
        self.calls.append(AdapterCall("shutdown", {}))
```

- [ ] **Step 6: Run adapter tests**

Run:

```powershell
python -m pip install -e ".[dev]"
python -m pytest tests/test_mock_adapter.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit adapter boundary**

Run:

```powershell
git add pyproject.toml src/someip_gui_tool/adapters tests/test_mock_adapter.py
git commit -m "feat: add protocol adapter interface"
```

Expected: commit succeeds.

---

### Task 9: Add Service Registry Core

**Files:**
- Create: `src/someip_gui_tool/core/service_registry.py`
- Modify: `tests/test_service_json_parser.py`

- [ ] **Step 1: Add registry test**

Append to `tests/test_service_json_parser.py`:

```python
from someip_gui_tool.core.service_registry import ServiceRegistry


def test_service_registry_loads_and_queries(adc40_soc_dir):
    registry = ServiceRegistry.load_directory(adc40_soc_dir)

    service = registry.get_service(0x080C)

    assert service.service_name == "IntelliDriveRmdSrv"
    assert registry.find_element(0x080C, 0x9001).name == "VertHeiRmdSts"
```

- [ ] **Step 2: Run registry test to verify failure**

Run:

```powershell
python -m pytest tests/test_service_json_parser.py::test_service_registry_loads_and_queries -q
```

Expected: FAIL with `ModuleNotFoundError` for `someip_gui_tool.core`.

- [ ] **Step 3: Implement service registry**

Create `src/someip_gui_tool/core/service_registry.py`:

```python
from __future__ import annotations

from pathlib import Path

from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldPartDefinition,
    MethodDefinition,
    ServiceDefinition,
)
from someip_gui_tool.parsing.service_json import load_service_directory

ElementDefinition = MethodDefinition | EventDefinition | FieldPartDefinition


class ServiceRegistry:
    def __init__(self, services: list[ServiceDefinition]) -> None:
        self.services = services
        self._by_id = {service.service_id: service for service in services}

    @classmethod
    def load_directory(cls, directory: Path) -> "ServiceRegistry":
        return cls(load_service_directory(directory))

    def get_service(self, service_id: int) -> ServiceDefinition:
        return self._by_id[service_id]

    def find_element(self, service_id: int, element_id: int) -> ElementDefinition:
        service = self.get_service(service_id)
        for method in service.methods:
            if method.method_id == element_id:
                return method
        for event in service.events:
            if event.event_id == element_id:
                return event
        for field in service.fields:
            for part in (field.getter, field.setter, field.notifier):
                if part and part.element_id == element_id:
                    return part
        raise KeyError(f"Element 0x{element_id:04X} not found in service 0x{service_id:04X}")
```

- [ ] **Step 4: Run registry tests**

Run:

```powershell
python -m pytest tests/test_service_json_parser.py::test_service_registry_loads_and_queries -q
```

Expected: PASS.

- [ ] **Step 5: Commit registry**

Run:

```powershell
git add src/someip_gui_tool/core tests/test_service_json_parser.py
git commit -m "feat: add service registry core"
```

Expected: commit succeeds.

---

### Task 10: Add Minimal PySide GUI Shell

**Files:**
- Create: `src/someip_gui_tool/gui/app.py`
- Create: `src/someip_gui_tool/gui/main_window.py`
- Create: `tests/test_gui_smoke.py`

- [ ] **Step 1: Write GUI smoke test**

Create `tests/test_gui_smoke.py`:

```python
from someip_gui_tool.gui.main_window import MainWindow


def test_main_window_loads_services(qtbot, adc40_soc_dir):
    window = MainWindow()
    qtbot.addWidget(window)

    window.load_service_directory(adc40_soc_dir)

    assert window.service_tree.topLevelItemCount() >= 5
```

- [ ] **Step 2: Run GUI smoke test to verify failure**

Run:

```powershell
python -m pytest tests/test_gui_smoke.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `someip_gui_tool.gui`.

- [ ] **Step 3: Implement main window**

Create `src/someip_gui_tool/gui/main_window.py`:

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from someip_gui_tool.core.service_registry import ServiceRegistry


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SOME/IP Test Tool")
        self.resize(1200, 760)

        self.service_tree = QTreeWidget()
        self.service_tree.setHeaderLabels(["Service Definitions"])

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlainText("Import a service definition directory to begin.")

        layout = QHBoxLayout()
        layout.addWidget(self.service_tree, 2)
        layout.addWidget(self.details, 3)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.statusBar().addWidget(QLabel("Ready"))

    def load_service_directory(self, directory: Path) -> None:
        registry = ServiceRegistry.load_directory(directory)
        self.service_tree.clear()
        for service in registry.services:
            service_item = QTreeWidgetItem(
                [
                    f"{service.service_name} ({service.service_id_hex}) "
                    f"instance 0x{service.deployment.instance_id:04X}"
                ]
            )
            for method in service.methods:
                service_item.addChild(QTreeWidgetItem([f"Method {method.name} ({method.method_id_hex})"]))
            for event in service.events:
                service_item.addChild(QTreeWidgetItem([f"Event {event.name} ({event.event_id_hex})"]))
            for field in service.fields:
                service_item.addChild(QTreeWidgetItem([f"Field {field.name}"]))
            self.service_tree.addTopLevelItem(service_item)
        self.service_tree.expandAll()
        self.details.setPlainText(f"Loaded {len(registry.services)} service definitions from {directory}")
```

- [ ] **Step 4: Implement GUI app entry**

Create `src/someip_gui_tool/gui/app.py`:

```python
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from someip_gui_tool.gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
```

- [ ] **Step 5: Run GUI smoke test**

Run:

```powershell
python -m pytest tests/test_gui_smoke.py -q
```

Expected: PASS.

- [ ] **Step 6: Run application manually**

Run:

```powershell
python -m someip_gui_tool
```

Expected: a window titled `SOME/IP Test Tool` opens. Close the window to return to the shell.

- [ ] **Step 7: Commit GUI shell**

Run:

```powershell
git add src/someip_gui_tool/gui src/someip_gui_tool/__main__.py tests/test_gui_smoke.py
git commit -m "feat: add minimal pyside service browser"
```

Expected: commit succeeds.

---

### Task 11: Add someipy Spike Harness

**Files:**
- Create: `src/someip_gui_tool/adapters/someipy_spike.py`
- Create: `scripts/run_someipy_spike.py`

- [ ] **Step 1: Create spike harness module**

Create `src/someip_gui_tool/adapters/someipy_spike.py`:

```python
from __future__ import annotations

import importlib.util
from dataclasses import dataclass


@dataclass(frozen=True)
class SomeipyAvailability:
    available: bool
    detail: str


def check_someipy_available() -> SomeipyAvailability:
    spec = importlib.util.find_spec("someipy")
    if spec is None:
        return SomeipyAvailability(
            available=False,
            detail="someipy is not installed. Install with: python -m pip install -e .[someipy]",
        )
    return SomeipyAvailability(available=True, detail="someipy import is available")


def describe_spike_plan() -> list[str]:
    return [
        "Start or connect to someipyd",
        "Run UDP FF method with 0x080D SecondStartCtrl",
        "Run TCP method with 0x0F01 AudioRecPopupReq",
        "Run UDP cycle event with 0x080E VehicleInfo",
        "Run TCP trigger event with 0x080A or 0x0F01",
        "Run Field Getter/Notifier with 0x080C VertHeiRmdSts",
        "Package minimal scenario with PyInstaller or Nuitka",
    ]
```

- [ ] **Step 2: Create operator script**

Create `scripts/run_someipy_spike.py`:

```python
from someip_gui_tool.adapters.someipy_spike import check_someipy_available, describe_spike_plan


def main() -> int:
    availability = check_someipy_available()
    print(availability.detail)
    print("Spike checklist:")
    for index, item in enumerate(describe_spike_plan(), start=1):
        print(f"{index}. {item}")
    return 0 if availability.available else 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run spike script without optional dependency**

Run:

```powershell
python scripts/run_someipy_spike.py
```

Expected:

```text
someipy is not installed. Install with: python -m pip install -e .[someipy]
Spike checklist:
1. Start or connect to someipyd
```

The process exits with code `2`.

- [ ] **Step 4: Install optional dependency and rerun**

Run:

```powershell
python -m pip install -e ".[someipy]"
python scripts/run_someipy_spike.py
```

Expected:

```text
someipy import is available
Spike checklist:
1. Start or connect to someipyd
```

The process exits with code `0`.

- [ ] **Step 5: Commit spike harness**

Run:

```powershell
git add src/someip_gui_tool/adapters/someipy_spike.py scripts/run_someipy_spike.py
git commit -m "feat: add someipy spike harness"
```

Expected: commit succeeds.

---

### Task 12: Add Packaging Smoke Spec

**Files:**
- Create: `packaging/pyinstaller/someip-gui-tool.spec`

- [ ] **Step 1: Create PyInstaller spec**

Create `packaging/pyinstaller/someip-gui-tool.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["src/someip_gui_tool/__main__.py"],
    pathex=[],
    binaries=[],
    datas=[("ADC40_SOC", "ADC40_SOC")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="someip-gui-tool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

- [ ] **Step 2: Run packaging smoke command**

Run:

```powershell
pyinstaller packaging/pyinstaller/someip-gui-tool.spec --noconfirm
```

Expected:

```text
Building EXE from EXE-00.toc completed successfully.
```

- [ ] **Step 3: Launch packaged app manually**

Run:

```powershell
.\dist\someip-gui-tool.exe
```

Expected: the same minimal GUI window opens. Close the window after verifying launch.

- [ ] **Step 4: Commit packaging spec**

Run:

```powershell
git add packaging/pyinstaller/someip-gui-tool.spec
git commit -m "chore: add pyinstaller packaging smoke spec"
```

Expected: commit succeeds.

---

## Final Verification

- [ ] **Step 1: Run all tests**

Run:

```powershell
python -m pytest
```

Expected: all tests pass.

- [ ] **Step 2: Run service import manually**

Run:

```powershell
python - <<'PY'
from pathlib import Path
from someip_gui_tool.core.service_registry import ServiceRegistry
registry = ServiceRegistry.load_directory(Path("ADC40_SOC"))
print(len(registry.services))
for service in registry.services:
    print(service.service_id_hex, service.service_name, len(service.methods), len(service.events), len(service.fields))
PY
```

Expected output includes:

```text
5
0x080C IntelliDriveRmdSrv 0 0 1
0x080D SecondStartSrv 1 1 0
```

- [ ] **Step 3: Run optional someipy availability check**

Run:

```powershell
python scripts/run_someipy_spike.py
```

Expected: prints either a clear install instruction or confirms `someipy import is available`.

- [ ] **Step 4: Check git status**

Run:

```powershell
git status --short
```

Expected: no uncommitted changes except environment/build artifacts intentionally left out of git.

---

## Notes for the Implementer

- Keep source files focused. Do not place GUI code in parser, codec, or adapter modules.
- Keep the protocol adapter boundary independent from `someipy` classes.
- Keep payload codec byte-order assumptions isolated in `payload_codec.py`.
- Treat `ADC40_SOC/*.json` as input fixtures. Do not modify those files during implementation.
- If a test exposes a UTF-8 BOM issue, read JSON with `encoding="utf-8-sig"`.
- If PySide tests fail in a headless environment, run the GUI smoke test locally on Windows before changing application code.
