# MVP-1 Runtime GUI Operations Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the validated protocol spike into the first formal runtime path for service configuration, adapter operations, trace/log emission, and a usable PySide operation slice.

**Architecture:** Keep the GUI away from `someipy`: GUI calls Core runtime services, Core calls `SomeIpAdapter`, and protocol implementations live behind adapter boundaries. Phase A starts with a backend decision gate for method support, then wires the already-proven event and field flows into Core and GUI while representing fire-and-forget method limitations explicitly.

**Tech Stack:** Python 3.11+, PySide6, pytest, pytest-qt, pytest-asyncio, optional `someipy>=2.1,<3`.

---

## Current Baseline

- `master` already contains parser, domain models, payload codec, project model, trace exporters, mock adapter, minimal GUI shell, someipy spike utilities, and protocol spike CLI.
- Verified protocol spike results:
  - `someipy` installs on Windows x64.
  - `someipyd` can be started/stopped by the app.
  - UDP and TCP event delivery works in local loopback with callback confirmation.
  - `0x080C` field getter and notifier work in local loopback.
  - Current `ADC40_SOC` method definitions are `RR/FF = "FF"`.
  - The current `someipy` path cannot prove fire-and-forget method calls, so method scenarios are reported as `SKIP` with a limitation.

## File Structure

- Create: `src/someip_gui_tool/adapters/capabilities.py` - backend capability matrix and method-support decision report.
- Modify: `src/someip_gui_tool/adapters/base.py` - formal adapter contract for runtime operations.
- Modify: `src/someip_gui_tool/adapters/mock.py` - richer deterministic adapter for Core and GUI tests.
- Create: `src/someip_gui_tool/adapters/someipy_adapter.py` - first production adapter for proven event and field operations.
- Create: `src/someip_gui_tool/core/runtime_config.py` - role-based runtime config inference and validation.
- Create: `src/someip_gui_tool/core/runtime_session.py` - Core orchestration over service definitions, codec, adapter, trace, and run log.
- Create: `src/someip_gui_tool/gui/runtime_panel.py` - service runtime configuration widget.
- Create: `src/someip_gui_tool/gui/operation_panel.py` - selected method/event/field operation widget.
- Modify: `src/someip_gui_tool/gui/main_window.py` - compose service tree, runtime panel, operation panel, log/trace/problems tabs.
- Create: `tests/test_backend_capabilities.py`
- Create: `tests/test_runtime_config.py`
- Create: `tests/test_runtime_session.py`
- Create: `tests/test_someipy_adapter.py`
- Modify: `tests/test_mock_adapter.py`
- Modify: `tests/test_gui_smoke.py`

---

### Task 1: Record Backend Capability Decision

**Files:**
- Create: `src/someip_gui_tool/adapters/capabilities.py`
- Test: `tests/test_backend_capabilities.py`

- [ ] **Step 1: Write capability tests**

Create `tests/test_backend_capabilities.py`:

```python
from someip_gui_tool.adapters.capabilities import (
    BackendCapabilityStatus,
    someipy_capability_report,
)


def test_someipy_report_marks_proven_event_and_field_paths() -> None:
    report = someipy_capability_report()

    assert report.backend == "someipy"
    assert report.operation_status["udp_event"] is BackendCapabilityStatus.SUPPORTED
    assert report.operation_status["tcp_event"] is BackendCapabilityStatus.SUPPORTED
    assert report.operation_status["field_getter"] is BackendCapabilityStatus.SUPPORTED
    assert report.operation_status["field_notifier"] is BackendCapabilityStatus.SUPPORTED


def test_someipy_report_marks_ff_methods_as_limited() -> None:
    report = someipy_capability_report()

    assert report.operation_status["udp_ff_method"] is BackendCapabilityStatus.LIMITED
    assert report.operation_status["tcp_ff_method"] is BackendCapabilityStatus.LIMITED
    assert "fire-and-forget" in report.notes["udp_ff_method"]
    assert "backend decision gate" in report.recommendation.lower()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_backend_capabilities.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `someip_gui_tool.adapters.capabilities`.

- [ ] **Step 3: Implement capability report**

Create `src/someip_gui_tool/adapters/capabilities.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BackendCapabilityStatus(StrEnum):
    SUPPORTED = "supported"
    LIMITED = "limited"
    UNSUPPORTED = "unsupported"


SOMEIPY_FF_LIMITATION = (
    "someipy local loopback proves availability for fire-and-forget methods, "
    "but the current adapter path cannot confirm that an FF request was "
    "transmitted and handled end-to-end."
)


@dataclass(frozen=True)
class BackendCapabilityReport:
    backend: str
    operation_status: dict[str, BackendCapabilityStatus]
    notes: dict[str, str]
    recommendation: str


def someipy_capability_report() -> BackendCapabilityReport:
    return BackendCapabilityReport(
        backend="someipy",
        operation_status={
            "udp_ff_method": BackendCapabilityStatus.LIMITED,
            "tcp_ff_method": BackendCapabilityStatus.LIMITED,
            "udp_event": BackendCapabilityStatus.SUPPORTED,
            "tcp_event": BackendCapabilityStatus.SUPPORTED,
            "field_getter": BackendCapabilityStatus.SUPPORTED,
            "field_notifier": BackendCapabilityStatus.SUPPORTED,
            "someipyd_process": BackendCapabilityStatus.SUPPORTED,
        },
        notes={
            "udp_ff_method": SOMEIPY_FF_LIMITATION,
            "tcp_ff_method": SOMEIPY_FF_LIMITATION,
            "udp_event": "Local loopback confirmed UDP event subscribe, send, and callback delivery.",
            "tcp_event": "Local loopback confirmed TCP event subscribe, send, and callback delivery.",
            "field_getter": "Local loopback confirmed getter request and response payload.",
            "field_notifier": "Local loopback confirmed notifier subscribe, send, and callback delivery.",
            "someipyd_process": "The application can start, connect to, and stop someipyd.",
        },
        recommendation=(
            "Use someipy for event and field Phase A runtime work. Keep method "
            "operations behind the adapter and run a backend decision gate before "
            "claiming FF method support in the GUI."
        ),
    )
```

- [ ] **Step 4: Run capability tests**

Run:

```powershell
python -m pytest tests/test_backend_capabilities.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit capability report**

Run:

```powershell
git add src/someip_gui_tool/adapters/capabilities.py tests/test_backend_capabilities.py
git commit -m "docs: record someipy backend capabilities"
```

Expected: commit succeeds.

---

### Task 2: Add Runtime Configuration Inference and Validation

**Files:**
- Create: `src/someip_gui_tool/core/runtime_config.py`
- Test: `tests/test_runtime_config.py`

- [ ] **Step 1: Write runtime config tests**

Create `tests/test_runtime_config.py`:

```python
from someip_gui_tool.core.runtime_config import (
    RuntimeServiceConfig,
    infer_runtime_config,
    validate_runtime_config,
)
from someip_gui_tool.domain.enums import Role
from someip_gui_tool.parsing.service_json import load_service_definition


def test_infer_runtime_config_uses_role_based_ips(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    config = infer_runtime_config(service, Role.SERVER)

    assert config.role is Role.SERVER
    assert config.local_ip == service.deployment.server_ip
    assert config.remote_ip == service.deployment.client_ip
    assert config.multicast_ip == service.deployment.multicast_ip
    assert config.instance_id == service.deployment.instance_id


def test_validate_runtime_config_requires_ports(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    config = infer_runtime_config(service, Role.SERVER)

    problems = validate_runtime_config(service, config)

    assert [problem.code for problem in problems] == ["server_port_missing", "client_port_missing"]
    assert all(problem.severity == "error" for problem in problems)


def test_validate_runtime_config_accepts_configured_ports(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    config = RuntimeServiceConfig(
        service_id=service.service_id,
        instance_id=service.deployment.instance_id,
        role=Role.CLIENT,
        local_ip=service.deployment.client_ip,
        remote_ip=service.deployment.server_ip,
        server_port=30500,
        client_port=30501,
        multicast_ip=service.deployment.multicast_ip,
    )

    assert validate_runtime_config(service, config) == []
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_runtime_config.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `someip_gui_tool.core.runtime_config`.

- [ ] **Step 3: Implement runtime config**

Create `src/someip_gui_tool/core/runtime_config.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from someip_gui_tool.domain.enums import Role, TransportProtocol
from someip_gui_tool.domain.models import ServiceDefinition


@dataclass(frozen=True)
class RuntimeProblem:
    code: str
    severity: str
    message: str
    service_id: int


@dataclass(frozen=True)
class RuntimeServiceConfig:
    service_id: int
    instance_id: int
    role: Role
    local_ip: str
    remote_ip: str
    server_port: int | None = None
    client_port: int | None = None
    multicast_ip: str = ""
    transport_override: TransportProtocol | None = None
    offer_ttl_s: float | None = None
    find_ttl_s: float | None = None
    payload_defaults: dict[str, object] = field(default_factory=dict)


def infer_runtime_config(service: ServiceDefinition, role: Role) -> RuntimeServiceConfig:
    return RuntimeServiceConfig(
        service_id=service.service_id,
        instance_id=service.deployment.instance_id,
        role=role,
        local_ip=service.deployment.local_ip_for(role),
        remote_ip=service.deployment.remote_ip_for(role),
        multicast_ip=service.deployment.multicast_ip,
        offer_ttl_s=service.deployment.offer_ttl_s,
        find_ttl_s=service.deployment.find_ttl_s,
    )


def validate_runtime_config(
    service: ServiceDefinition,
    config: RuntimeServiceConfig,
) -> list[RuntimeProblem]:
    problems: list[RuntimeProblem] = []
    if config.server_port is None:
        problems.append(
            RuntimeProblem(
                code="server_port_missing",
                severity="error",
                message="Server port must be configured before service start.",
                service_id=service.service_id,
            )
        )
    if config.client_port is None:
        problems.append(
            RuntimeProblem(
                code="client_port_missing",
                severity="error",
                message="Client port must be configured before service start.",
                service_id=service.service_id,
            )
        )
    if not config.local_ip:
        problems.append(
            RuntimeProblem(
                code="local_ip_missing",
                severity="error",
                message="Local IP must be configured before service start.",
                service_id=service.service_id,
            )
        )
    if not config.remote_ip:
        problems.append(
            RuntimeProblem(
                code="remote_ip_missing",
                severity="error",
                message="Remote IP must be configured before service start.",
                service_id=service.service_id,
            )
        )
    if not config.multicast_ip:
        problems.append(
            RuntimeProblem(
                code="multicast_ip_missing",
                severity="warning",
                message="Multicast IP is empty; service discovery may not work.",
                service_id=service.service_id,
            )
        )
    return problems
```

- [ ] **Step 4: Run runtime config tests**

Run:

```powershell
python -m pytest tests/test_runtime_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit runtime config**

Run:

```powershell
git add src/someip_gui_tool/core/runtime_config.py tests/test_runtime_config.py
git commit -m "feat: add runtime service config validation"
```

Expected: commit succeeds.

---

### Task 3: Expand Adapter Contract and Mock Adapter

**Files:**
- Modify: `src/someip_gui_tool/adapters/base.py`
- Modify: `src/someip_gui_tool/adapters/mock.py`
- Modify: `tests/test_mock_adapter.py`

- [ ] **Step 1: Replace mock adapter tests with runtime operation contract**

Modify `tests/test_mock_adapter.py`:

```python
import pytest

from someip_gui_tool.adapters.base import AdapterEvent
from someip_gui_tool.adapters.mock import MockSomeIpAdapter
from someip_gui_tool.parsing.service_json import load_service_definition


@pytest.mark.asyncio
async def test_mock_adapter_records_runtime_operations(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = MockSomeIpAdapter()
    received = []

    await adapter.start_service(service)
    await adapter.offer_service(service)
    await adapter.find_service(service)
    await adapter.register_event_handler(service, service.events[0], received.append)
    await adapter.subscribe_eventgroup(service, service.events[0].eventgroup_id or 0)
    await adapter.publish_event(service, service.events[0], b"\x01\x02")
    await adapter.stop_service(service)
    await adapter.shutdown()

    assert [call.name for call in adapter.calls] == [
        "start_service",
        "offer_service",
        "find_service",
        "register_event_handler",
        "subscribe_eventgroup",
        "publish_event",
        "stop_service",
        "shutdown",
    ]
    assert received == [
        AdapterEvent(
            service_id=service.service_id,
            element_id=service.events[0].event_id,
            eventgroup_id=service.events[0].eventgroup_id,
            payload=b"\x01\x02",
        )
    ]


@pytest.mark.asyncio
async def test_mock_adapter_marks_ff_method_as_limited(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080D.json")
    adapter = MockSomeIpAdapter()

    result = await adapter.call_method(service, service.methods[0], b"\x01")

    assert result.status == "limited"
    assert "fire-and-forget" in result.detail
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_mock_adapter.py -q
```

Expected: FAIL because `AdapterEvent`, `offer_service`, `find_service`, and method result support do not exist.

- [ ] **Step 3: Implement adapter contract**

Modify `src/someip_gui_tool/adapters/base.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldDefinition,
    MethodDefinition,
    ServiceDefinition,
)


@dataclass(frozen=True)
class AdapterMethodResult:
    status: str
    detail: str
    payload: bytes | None = None


@dataclass(frozen=True)
class AdapterEvent:
    service_id: int
    element_id: int
    eventgroup_id: int | None
    payload: bytes


EventHandler = Callable[[AdapterEvent], None]


class SomeIpAdapter(ABC):
    @abstractmethod
    async def start_service(self, service: ServiceDefinition) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop_service(self, service: ServiceDefinition) -> None:
        raise NotImplementedError

    @abstractmethod
    async def offer_service(self, service: ServiceDefinition) -> None:
        raise NotImplementedError

    @abstractmethod
    async def find_service(self, service: ServiceDefinition) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def call_method(
        self,
        service: ServiceDefinition,
        method: MethodDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        raise NotImplementedError

    @abstractmethod
    async def register_event_handler(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        handler: EventHandler,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def subscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def unsubscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
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
    async def field_get(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        raise NotImplementedError

    @abstractmethod
    async def field_notify(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def shutdown(self) -> None:
        raise NotImplementedError
```

- [ ] **Step 4: Implement richer mock adapter**

Modify `src/someip_gui_tool/adapters/mock.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from someip_gui_tool.adapters.base import (
    AdapterEvent,
    AdapterMethodResult,
    EventHandler,
    SomeIpAdapter,
)
from someip_gui_tool.adapters.capabilities import SOMEIPY_FF_LIMITATION
from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldDefinition,
    MethodDefinition,
    ServiceDefinition,
)


@dataclass(frozen=True)
class AdapterCall:
    name: str
    details: dict[str, object]


class MockSomeIpAdapter(SomeIpAdapter):
    def __init__(self) -> None:
        self.calls: list[AdapterCall] = []
        self._event_handlers: dict[tuple[int, int], list[EventHandler]] = {}

    async def start_service(self, service: ServiceDefinition) -> None:
        self.calls.append(AdapterCall("start_service", {"service_id": service.service_id_hex}))

    async def stop_service(self, service: ServiceDefinition) -> None:
        self.calls.append(AdapterCall("stop_service", {"service_id": service.service_id_hex}))

    async def offer_service(self, service: ServiceDefinition) -> None:
        self.calls.append(AdapterCall("offer_service", {"service_id": service.service_id_hex}))

    async def find_service(self, service: ServiceDefinition) -> bool:
        self.calls.append(AdapterCall("find_service", {"service_id": service.service_id_hex}))
        return True

    async def call_method(
        self,
        service: ServiceDefinition,
        method: MethodDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
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
        if method.rr_ff == "FF":
            return AdapterMethodResult(status="limited", detail=SOMEIPY_FF_LIMITATION)
        return AdapterMethodResult(status="success", detail="mock response", payload=payload)

    async def register_event_handler(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        handler: EventHandler,
    ) -> None:
        self.calls.append(
            AdapterCall(
                "register_event_handler",
                {"service_id": service.service_id_hex, "event_id": event.event_id_hex},
            )
        )
        self._event_handlers.setdefault((service.service_id, event.event_id), []).append(handler)

    async def subscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        self.calls.append(
            AdapterCall(
                "subscribe_eventgroup",
                {"service_id": service.service_id_hex, "eventgroup_id": f"0x{eventgroup_id:04X}"},
            )
        )

    async def unsubscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        self.calls.append(
            AdapterCall(
                "unsubscribe_eventgroup",
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
        adapter_event = AdapterEvent(
            service_id=service.service_id,
            element_id=event.event_id,
            eventgroup_id=event.eventgroup_id,
            payload=payload,
        )
        for handler in self._event_handlers.get((service.service_id, event.event_id), []):
            handler(adapter_event)

    async def field_get(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        if field.getter is None:
            return AdapterMethodResult(status="error", detail="field has no getter")
        self.calls.append(
            AdapterCall(
                "field_get",
                {
                    "service_id": service.service_id_hex,
                    "getter_id": f"0x{field.getter.element_id:04X}",
                    "payload": payload.hex(),
                },
            )
        )
        return AdapterMethodResult(status="success", detail="mock getter response", payload=payload)

    async def field_notify(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> None:
        if field.notifier is None:
            raise ValueError(f"Field {field.name!r} has no notifier")
        self.calls.append(
            AdapterCall(
                "field_notify",
                {
                    "service_id": service.service_id_hex,
                    "notifier_id": f"0x{field.notifier.element_id:04X}",
                    "payload": payload.hex(),
                },
            )
        )

    async def shutdown(self) -> None:
        self.calls.append(AdapterCall("shutdown", {}))
```

- [ ] **Step 5: Run adapter tests**

Run:

```powershell
python -m pytest tests/test_mock_adapter.py tests/test_backend_capabilities.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit adapter contract**

Run:

```powershell
git add src/someip_gui_tool/adapters/base.py src/someip_gui_tool/adapters/mock.py tests/test_mock_adapter.py
git commit -m "feat: expand runtime adapter contract"
```

Expected: commit succeeds.

---

### Task 4: Add Core Runtime Session

**Files:**
- Create: `src/someip_gui_tool/core/runtime_session.py`
- Test: `tests/test_runtime_session.py`

- [ ] **Step 1: Write runtime session tests**

Create `tests/test_runtime_session.py`:

```python
import pytest

from someip_gui_tool.adapters.mock import MockSomeIpAdapter
from someip_gui_tool.core.runtime_config import infer_runtime_config
from someip_gui_tool.core.runtime_session import RuntimeSession
from someip_gui_tool.domain.enums import Role
from someip_gui_tool.parsing.service_json import load_service_definition


@pytest.mark.asyncio
async def test_runtime_session_subscribes_and_publishes_event(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)
    config = infer_runtime_config(service, Role.SERVER)

    await session.start_service(service, config)
    await session.subscribe_event(service, service.events[0])
    await session.publish_event(
        service,
        service.events[0],
        {"VehicleInfo": {"VehicleSpeed": 12.5, "Odometer": 99.25}},
    )

    assert [entry.message for entry in session.run_log][-3:] == [
        "Started service ADASDrivingInfoSrv (0x080E)",
        "Subscribed eventgroup 0x0001 for VehicleInfo",
        "Published event VehicleInfo payload=4148000042c68000",
    ]
    assert session.trace[-1].raw_payload_hex == "4148000042c68000"
    assert session.trace[-1].element_name == "VehicleInfo"


@pytest.mark.asyncio
async def test_runtime_session_field_get_and_notify(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)
    field = service.fields[0]

    result = await session.field_get(service, field, {"VertHeiRmdSts": 1})
    await session.field_notify(service, field, {"VertHeiRmdSts": 1})

    assert result.status == "success"
    assert [call.name for call in adapter.calls] == ["field_get", "field_notify"]
    assert session.trace[0].element_type == "FieldGetter"
    assert session.trace[1].element_type == "FieldNotifier"


@pytest.mark.asyncio
async def test_runtime_session_reports_limited_ff_method(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080D.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)

    result = await session.call_method(service, service.methods[0], {"SecondStartCtrlCmd": 1})

    assert result.status == "limited"
    assert "fire-and-forget" in result.detail
    assert session.trace[-1].result == "limited"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_runtime_session.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `someip_gui_tool.core.runtime_session`.

- [ ] **Step 3: Implement runtime session**

Create `src/someip_gui_tool/core/runtime_session.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from someip_gui_tool.adapters.base import AdapterMethodResult, SomeIpAdapter
from someip_gui_tool.codec.payload_codec import PayloadCodec
from someip_gui_tool.core.runtime_config import RuntimeServiceConfig
from someip_gui_tool.domain.enums import Role, TraceDirection
from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldDefinition,
    MethodDefinition,
    ServiceDefinition,
)
from someip_gui_tool.tracing.trace_model import MessageTraceEntry, RunLogEntry


class RuntimeSession:
    def __init__(self, adapter: SomeIpAdapter, codec: PayloadCodec | None = None) -> None:
        self.adapter = adapter
        self.codec = codec or PayloadCodec()
        self.run_log: list[RunLogEntry] = []
        self.trace: list[MessageTraceEntry] = []

    async def start_service(
        self,
        service: ServiceDefinition,
        config: RuntimeServiceConfig,
    ) -> None:
        await self.adapter.start_service(service)
        self._log("info", "Core", f"Started service {service.service_name} ({service.service_id_hex})")

    async def stop_service(self, service: ServiceDefinition) -> None:
        await self.adapter.stop_service(service)
        self._log("info", "Core", f"Stopped service {service.service_name} ({service.service_id_hex})")

    async def call_method(
        self,
        service: ServiceDefinition,
        method: MethodDefinition,
        values: dict[str, Any],
    ) -> AdapterMethodResult:
        payload = self.codec.encode_parameters(method.parameters, values)
        result = await self.adapter.call_method(service, method, payload)
        self._trace(
            service=service,
            role=Role.CLIENT,
            direction=TraceDirection.TX,
            element_type="Method",
            element_name=method.name,
            element_id=method.method_id_hex,
            eventgroup_id=None,
            transport=method.transport,
            raw_payload_hex=payload.hex(),
            decoded_payload=values,
            rr_ff=method.rr_ff,
            result=result.status,
            error_message=None if result.status == "success" else result.detail,
        )
        self._log("info", "Core", f"Called method {method.name} result={result.status}")
        return result

    async def subscribe_event(self, service: ServiceDefinition, event: EventDefinition) -> None:
        if event.eventgroup_id is None:
            raise ValueError(f"Event {event.name!r} has no eventgroup id")
        await self.adapter.subscribe_eventgroup(service, event.eventgroup_id)
        self._log(
            "info",
            "Core",
            f"Subscribed eventgroup 0x{event.eventgroup_id:04X} for {event.name}",
        )

    async def publish_event(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        values: dict[str, Any],
    ) -> None:
        payload = self.codec.encode_parameters(event.parameters, values)
        await self.adapter.publish_event(service, event, payload)
        self._trace(
            service=service,
            role=Role.SERVER,
            direction=TraceDirection.TX,
            element_type="Event",
            element_name=event.name,
            element_id=event.event_id_hex,
            eventgroup_id=(f"0x{event.eventgroup_id:04X}" if event.eventgroup_id is not None else None),
            transport=event.transport,
            raw_payload_hex=payload.hex(),
            decoded_payload=values,
            rr_ff=None,
            result="success",
            error_message=None,
        )
        self._log("info", "Core", f"Published event {event.name} payload={payload.hex()}")

    async def field_get(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        values: dict[str, Any],
    ) -> AdapterMethodResult:
        if field.getter is None:
            raise ValueError(f"Field {field.name!r} has no getter")
        payload = self.codec.encode_parameters(field.getter.parameters, values)
        result = await self.adapter.field_get(service, field, payload)
        self._trace(
            service=service,
            role=Role.CLIENT,
            direction=TraceDirection.TX,
            element_type="FieldGetter",
            element_name=field.name,
            element_id=f"0x{field.getter.element_id:04X}",
            eventgroup_id=None,
            transport=field.getter.transport,
            raw_payload_hex=payload.hex(),
            decoded_payload=values,
            rr_ff=None,
            result=result.status,
            error_message=None if result.status == "success" else result.detail,
        )
        self._log("info", "Core", f"Field getter {field.name} result={result.status}")
        return result

    async def field_notify(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        values: dict[str, Any],
    ) -> None:
        if field.notifier is None:
            raise ValueError(f"Field {field.name!r} has no notifier")
        payload = self.codec.encode_parameters(field.notifier.parameters, values)
        await self.adapter.field_notify(service, field, payload)
        self._trace(
            service=service,
            role=Role.SERVER,
            direction=TraceDirection.TX,
            element_type="FieldNotifier",
            element_name=field.name,
            element_id=f"0x{field.notifier.element_id:04X}",
            eventgroup_id=(
                f"0x{field.notifier.eventgroup_id:04X}"
                if field.notifier.eventgroup_id is not None
                else None
            ),
            transport=field.notifier.transport,
            raw_payload_hex=payload.hex(),
            decoded_payload=values,
            rr_ff=None,
            result="success",
            error_message=None,
        )
        self._log("info", "Core", f"Field notifier {field.name} payload={payload.hex()}")

    def _log(self, level: str, source: str, message: str) -> None:
        self.run_log.append(
            RunLogEntry(
                timestamp=datetime.now(timezone.utc),
                level=level,
                source=source,
                message=message,
            )
        )

    def _trace(
        self,
        *,
        service: ServiceDefinition,
        role: Role,
        direction: TraceDirection,
        element_type: str,
        element_name: str,
        element_id: str,
        eventgroup_id: str | None,
        transport: Any,
        raw_payload_hex: str,
        decoded_payload: dict[str, Any],
        rr_ff: str | None,
        result: str,
        error_message: str | None,
    ) -> None:
        self.trace.append(
            MessageTraceEntry(
                timestamp=datetime.now(timezone.utc),
                direction=direction,
                role=role,
                service_name=service.service_name,
                service_id=service.service_id_hex,
                instance_id=f"0x{service.deployment.instance_id:04X}",
                element_type=element_type,
                element_name=element_name,
                element_id=element_id,
                eventgroup_id=eventgroup_id,
                transport=transport,
                local_endpoint="",
                remote_endpoint="",
                rr_ff=rr_ff,
                raw_payload_hex=raw_payload_hex,
                decoded_payload=decoded_payload,
                result=result,
                error_message=error_message,
            )
        )
```

- [ ] **Step 4: Run runtime session tests**

Run:

```powershell
python -m pytest tests/test_runtime_session.py tests/test_mock_adapter.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit runtime session**

Run:

```powershell
git add src/someip_gui_tool/core/runtime_session.py tests/test_runtime_session.py
git commit -m "feat: add core runtime session"
```

Expected: commit succeeds.

---

### Task 5: Add Someipy Adapter Phase A

**Files:**
- Create: `src/someip_gui_tool/adapters/someipy_adapter.py`
- Test: `tests/test_someipy_adapter.py`

- [ ] **Step 1: Write fake-backed adapter tests**

Create `tests/test_someipy_adapter.py`:

```python
from types import SimpleNamespace

import pytest

from someip_gui_tool.adapters.someipy_adapter import SomeipyAdapter
from someip_gui_tool.parsing.service_json import load_service_definition


class FakeDaemon:
    def __init__(self) -> None:
        self.disconnected = False

    async def disconnect_from_daemon(self) -> None:
        self.disconnected = True


class FakeApi:
    def __init__(self) -> None:
        self.daemon = FakeDaemon()
        self.connected_config = None
        self.sent_events = []

    async def connect_to_someipy_daemon(self, config=None):
        self.connected_config = config
        return self.daemon


@pytest.mark.asyncio
async def test_someipy_adapter_connects_with_client_config(adc40_soc_dir):
    api = FakeApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(service)
    await adapter.shutdown()

    assert api.connected_config == {
        "use_tcp": True,
        "tcp_host": "127.0.0.1",
        "tcp_port": 30500,
    }
    assert api.daemon.disconnected is True


@pytest.mark.asyncio
async def test_someipy_adapter_reports_ff_method_limited(adc40_soc_dir):
    adapter = SomeipyAdapter(api=FakeApi(), local_ip="127.0.0.1", base_port=30500)
    service = load_service_definition(adc40_soc_dir / "0x080D.json")

    result = await adapter.call_method(service, service.methods[0], b"\x01")

    assert result.status == "limited"
    assert "fire-and-forget" in result.detail
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_someipy_adapter.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `someip_gui_tool.adapters.someipy_adapter`.

- [ ] **Step 3: Implement Phase A adapter skeleton**

Create `src/someip_gui_tool/adapters/someipy_adapter.py`:

```python
from __future__ import annotations

from typing import Any

from someip_gui_tool.adapters.base import (
    AdapterMethodResult,
    EventHandler,
    SomeIpAdapter,
)
from someip_gui_tool.adapters.capabilities import SOMEIPY_FF_LIMITATION
from someip_gui_tool.adapters.someipy_api import SomeipyApiProbe
from someip_gui_tool.adapters.someipy_daemon import SomeipydConfig
from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldDefinition,
    MethodDefinition,
    ServiceDefinition,
)


class SomeipyAdapter(SomeIpAdapter):
    def __init__(
        self,
        *,
        api: Any | None = None,
        local_ip: str,
        base_port: int,
    ) -> None:
        self._api = api
        self._local_ip = local_ip
        self._base_port = base_port
        self._daemon: Any | None = None
        self._event_handlers: dict[tuple[int, int], list[EventHandler]] = {}

    async def start_service(self, service: ServiceDefinition) -> None:
        await self._ensure_daemon()

    async def stop_service(self, service: ServiceDefinition) -> None:
        return None

    async def offer_service(self, service: ServiceDefinition) -> None:
        await self._ensure_daemon()

    async def find_service(self, service: ServiceDefinition) -> bool:
        await self._ensure_daemon()
        return True

    async def call_method(
        self,
        service: ServiceDefinition,
        method: MethodDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        if method.rr_ff == "FF":
            return AdapterMethodResult(status="limited", detail=SOMEIPY_FF_LIMITATION)
        return AdapterMethodResult(
            status="error",
            detail="RR method execution is not enabled until a matching RR fixture is available.",
        )

    async def register_event_handler(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        handler: EventHandler,
    ) -> None:
        self._event_handlers.setdefault((service.service_id, event.event_id), []).append(handler)

    async def subscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        await self._ensure_daemon()

    async def unsubscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        await self._ensure_daemon()

    async def publish_event(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        payload: bytes,
    ) -> None:
        await self._ensure_daemon()

    async def field_get(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        if field.getter is None:
            return AdapterMethodResult(status="error", detail="field has no getter")
        await self._ensure_daemon()
        return AdapterMethodResult(status="success", detail="field getter completed", payload=payload)

    async def field_notify(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> None:
        if field.notifier is None:
            raise ValueError(f"Field {field.name!r} has no notifier")
        await self._ensure_daemon()

    async def shutdown(self) -> None:
        if self._daemon is None:
            return
        disconnect = getattr(self._daemon, "disconnect_from_daemon", None)
        if disconnect is not None:
            await disconnect()
        self._daemon = None

    async def _ensure_daemon(self) -> Any:
        if self._daemon is not None:
            return self._daemon
        api = self._api
        if api is None:
            probe = SomeipyApiProbe()
            api = probe.require_module()
            self._api = api
        config = SomeipydConfig(
            interface=self._local_ip,
            tcp_host=self._local_ip,
            tcp_port=self._base_port,
        ).client_config()
        self._daemon = await api.connect_to_someipy_daemon(config)
        return self._daemon
```

- [ ] **Step 4: Run adapter tests**

Run:

```powershell
python -m pytest tests/test_someipy_adapter.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit SomeipyAdapter skeleton**

Run:

```powershell
git add src/someip_gui_tool/adapters/someipy_adapter.py tests/test_someipy_adapter.py
git commit -m "feat: add someipy runtime adapter skeleton"
```

Expected: commit succeeds.

---

### Task 6: Add Runtime and Operation Panels

**Files:**
- Create: `src/someip_gui_tool/gui/runtime_panel.py`
- Create: `src/someip_gui_tool/gui/operation_panel.py`
- Modify: `src/someip_gui_tool/gui/main_window.py`
- Modify: `tests/test_gui_smoke.py`

- [ ] **Step 1: Add GUI smoke tests for runtime controls**

Append to `tests/test_gui_smoke.py`:

```python
from someip_gui_tool.domain.enums import Role


def test_main_window_shows_runtime_config_for_selected_service(qtbot, adc40_soc_dir):
    window = MainWindow()
    qtbot.addWidget(window)

    window.load_service_directory(adc40_soc_dir)
    first_item = window.service_tree.topLevelItem(0)
    window.service_tree.setCurrentItem(first_item)

    assert window.runtime_panel.role_combo.currentText() in {Role.CLIENT.value, Role.SERVER.value}
    assert window.runtime_panel.server_port_edit.text() == ""
    assert window.runtime_panel.client_port_edit.text() == ""


def test_main_window_shows_field_operations(qtbot, adc40_soc_dir):
    window = MainWindow()
    qtbot.addWidget(window)

    window.load_service_directory(adc40_soc_dir)
    field_item = window.service_tree.findItems("IntelliDriveRmdSrv", Qt.MatchFlag.MatchContains)[0].child(0)
    window.service_tree.setCurrentItem(field_item)

    assert window.operation_panel.title_label.text().startswith("Field")
    assert window.operation_panel.primary_button.text() == "Get"
    assert window.operation_panel.secondary_button.text() == "Notify"
```

Add this import at the top of `tests/test_gui_smoke.py`:

```python
from PySide6.QtCore import Qt
```

- [ ] **Step 2: Run GUI tests to verify failure**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest tests/test_gui_smoke.py -q
```

Expected: FAIL because `runtime_panel`, `operation_panel`, and selection behavior do not exist.

- [ ] **Step 3: Implement runtime panel**

Create `src/someip_gui_tool/gui/runtime_panel.py`:

```python
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
)

from someip_gui_tool.core.runtime_config import RuntimeServiceConfig
from someip_gui_tool.domain.enums import Role


class RuntimePanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Runtime")
        self.role_combo = QComboBox()
        self.role_combo.addItems([Role.CLIENT.value, Role.SERVER.value])
        self.local_ip_edit = QLineEdit()
        self.remote_ip_edit = QLineEdit()
        self.server_port_edit = QLineEdit()
        self.client_port_edit = QLineEdit()
        self.multicast_ip_edit = QLineEdit()

        layout = QFormLayout(self)
        layout.addRow("Role", self.role_combo)
        layout.addRow("Local IP", self.local_ip_edit)
        layout.addRow("Remote IP", self.remote_ip_edit)
        layout.addRow("Server Port", self.server_port_edit)
        layout.addRow("Client Port", self.client_port_edit)
        layout.addRow("Multicast IP", self.multicast_ip_edit)

    def set_config(self, config: RuntimeServiceConfig) -> None:
        self.role_combo.setCurrentText(config.role.value)
        self.local_ip_edit.setText(config.local_ip)
        self.remote_ip_edit.setText(config.remote_ip)
        self.server_port_edit.setText("" if config.server_port is None else str(config.server_port))
        self.client_port_edit.setText("" if config.client_port is None else str(config.client_port))
        self.multicast_ip_edit.setText(config.multicast_ip)
```

- [ ] **Step 4: Implement operation panel**

Create `src/someip_gui_tool/gui/operation_panel.py`:

```python
from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from someip_gui_tool.domain.models import EventDefinition, FieldDefinition, MethodDefinition


class OperationPanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Operation")
        self.title_label = QLabel("Select a method, event, or field")
        self.primary_button = QPushButton("Start")
        self.secondary_button = QPushButton("Stop")

        layout = QVBoxLayout(self)
        layout.addWidget(self.title_label)
        layout.addWidget(self.primary_button)
        layout.addWidget(self.secondary_button)

    def show_method(self, method: MethodDefinition) -> None:
        self.title_label.setText(f"Method {method.name} ({method.method_id_hex})")
        self.primary_button.setText("Call")
        self.secondary_button.setText("Configure Response")

    def show_event(self, event: EventDefinition) -> None:
        self.title_label.setText(f"Event {event.name} ({event.event_id_hex})")
        self.primary_button.setText("Subscribe")
        self.secondary_button.setText("Publish")

    def show_field(self, field: FieldDefinition) -> None:
        self.title_label.setText(f"Field {field.name}")
        self.primary_button.setText("Get")
        self.secondary_button.setText("Notify")
```

- [ ] **Step 5: Compose panels in main window**

Modify `src/someip_gui_tool/gui/main_window.py` so it stores item payloads and updates panels on selection:

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QPlainTextEdit,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from someip_gui_tool.core.runtime_config import infer_runtime_config
from someip_gui_tool.core.service_registry import ServiceRegistry
from someip_gui_tool.domain.enums import Role
from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldDefinition,
    MethodDefinition,
    ServiceDefinition,
)
from someip_gui_tool.gui.operation_panel import OperationPanel
from someip_gui_tool.gui.runtime_panel import RuntimePanel

ITEM_PAYLOAD_ROLE = Qt.ItemDataRole.UserRole


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SOME/IP Test Tool")
        self._registry: ServiceRegistry | None = None

        self.service_tree = QTreeWidget()
        self.service_tree.setHeaderLabels(["Service Browser"])
        self.service_tree.currentItemChanged.connect(self._on_current_item_changed)

        self.runtime_panel = RuntimePanel()
        self.operation_panel = OperationPanel()

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlainText("Ready")

        right_side = QWidget()
        right_layout = QVBoxLayout(right_side)
        right_layout.addWidget(self.runtime_panel)
        right_layout.addWidget(self.operation_panel)
        right_layout.addWidget(self.details)

        splitter = QSplitter()
        splitter.addWidget(self.service_tree)
        splitter.addWidget(right_side)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        central_widget = QWidget()
        layout = QHBoxLayout(central_widget)
        layout.addWidget(splitter)
        self.setCentralWidget(central_widget)
        self.statusBar().showMessage("Ready")

    def load_service_directory(self, directory: Path) -> None:
        self._registry = ServiceRegistry.load_directory(directory)
        self.service_tree.clear()

        for service in self._registry.services:
            self.service_tree.addTopLevelItem(self._service_item(service))

        self.service_tree.expandAll()
        message = f"Loaded {len(self._registry.services)} service definitions from {directory}"
        self.details.setPlainText(message)
        self.statusBar().showMessage(message)

    def _service_item(self, service: ServiceDefinition) -> QTreeWidgetItem:
        service_item = QTreeWidgetItem([f"{service.service_name} ({service.service_id_hex})"])
        service_item.setData(0, ITEM_PAYLOAD_ROLE, service)

        for method in service.methods:
            item = QTreeWidgetItem([f"Method {method.name} ({method.method_id_hex})"])
            item.setData(0, ITEM_PAYLOAD_ROLE, method)
            service_item.addChild(item)

        for event in service.events:
            item = QTreeWidgetItem([f"Event {event.name} ({event.event_id_hex})"])
            item.setData(0, ITEM_PAYLOAD_ROLE, event)
            service_item.addChild(item)

        for field in service.fields:
            service_item.addChild(self._field_item(field))

        return service_item

    def _field_item(self, field: FieldDefinition) -> QTreeWidgetItem:
        field_item = QTreeWidgetItem([f"Field {field.name}"])
        field_item.setData(0, ITEM_PAYLOAD_ROLE, field)
        return field_item

    def _on_current_item_changed(
        self,
        current: QTreeWidgetItem | None,
        previous: QTreeWidgetItem | None,
    ) -> None:
        if current is None:
            return
        payload = current.data(0, ITEM_PAYLOAD_ROLE)
        service = self._service_for_item(current)
        if service is not None:
            self.runtime_panel.set_config(infer_runtime_config(service, Role.CLIENT))
        if isinstance(payload, MethodDefinition):
            self.operation_panel.show_method(payload)
        elif isinstance(payload, EventDefinition):
            self.operation_panel.show_event(payload)
        elif isinstance(payload, FieldDefinition):
            self.operation_panel.show_field(payload)

    def _service_for_item(self, item: QTreeWidgetItem) -> ServiceDefinition | None:
        cursor: QTreeWidgetItem | None = item
        while cursor is not None:
            payload = cursor.data(0, ITEM_PAYLOAD_ROLE)
            if isinstance(payload, ServiceDefinition):
                return payload
            cursor = cursor.parent()
        return None
```

- [ ] **Step 6: Run GUI smoke tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest tests/test_gui_smoke.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit GUI panels**

Run:

```powershell
git add src/someip_gui_tool/gui tests/test_gui_smoke.py
git commit -m "feat: add runtime operation panels"
```

Expected: commit succeeds.

---

### Task 7: Add Run Log, Trace, and Problems Tabs to GUI

**Files:**
- Modify: `src/someip_gui_tool/gui/main_window.py`
- Test: `tests/test_gui_smoke.py`

- [ ] **Step 1: Add GUI test for bottom tabs**

Append to `tests/test_gui_smoke.py`:

```python
def test_main_window_has_log_trace_problem_tabs(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert [window.bottom_tabs.tabText(index) for index in range(window.bottom_tabs.count())] == [
        "Run Log",
        "Message Trace",
        "Problems",
    ]
```

- [ ] **Step 2: Run GUI test to verify failure**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest tests/test_gui_smoke.py::test_main_window_has_log_trace_problem_tabs -q
```

Expected: FAIL because `bottom_tabs` does not exist.

- [ ] **Step 3: Add bottom tabs**

Modify `src/someip_gui_tool/gui/main_window.py` imports:

```python
from PySide6.QtWidgets import QTabWidget
```

Add this in `MainWindow.__init__` after `self.details`:

```python
self.bottom_tabs = QTabWidget()
self.run_log_view = QPlainTextEdit()
self.message_trace_view = QPlainTextEdit()
self.problems_view = QPlainTextEdit()
for view in (self.run_log_view, self.message_trace_view, self.problems_view):
    view.setReadOnly(True)
self.bottom_tabs.addTab(self.run_log_view, "Run Log")
self.bottom_tabs.addTab(self.message_trace_view, "Message Trace")
self.bottom_tabs.addTab(self.problems_view, "Problems")
```

Replace:

```python
right_layout.addWidget(self.details)
```

With:

```python
right_layout.addWidget(self.details)
right_layout.addWidget(self.bottom_tabs)
```

- [ ] **Step 4: Run GUI tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest tests/test_gui_smoke.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit bottom tabs**

Run:

```powershell
git add src/someip_gui_tool/gui/main_window.py tests/test_gui_smoke.py
git commit -m "feat: add gui log trace problem tabs"
```

Expected: commit succeeds.

---

### Task 8: Final Verification and Phase Decision Summary

**Files:**
- Modify: `docs/superpowers/plans/2026-05-15-mvp1-runtime-gui-ops.md` only if execution uncovers command corrections.

- [ ] **Step 1: Run full tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest
```

Expected: all tests pass.

- [ ] **Step 2: Run dry protocol spike**

Run:

```powershell
python scripts/run_protocol_spike.py --definition-root ADC40_SOC --mode dry-run
```

Expected output includes:

```text
Spike report: someipy-protocol-spike-dry-run
PASS udp-ff-method
PASS tcp-method
PASS udp-event
PASS tcp-event
PASS field-getter-notifier
```

- [ ] **Step 3: Run real protocol spike with daemon autostart**

Run:

```powershell
python scripts/run_protocol_spike.py --definition-root ADC40_SOC --mode real --local-ip 127.0.0.1 --base-port 30500 --start-daemon
```

Expected output includes:

```text
PASS someipy-api
PASS someipyd
SKIP udp-ff-method
SKIP tcp-method
PASS udp-event
PASS tcp-event
PASS field-getter-notifier
```

- [ ] **Step 4: Run PySide import smoke**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest tests/test_gui_smoke.py -q
```

Expected: PASS.

- [ ] **Step 5: Check git status**

Run:

```powershell
git status --short
```

Expected: only intentional untracked local files remain, such as `.claude/` and `AGENTS.md`.

---

## Self-Review Checklist

- **Spec coverage:** This plan covers the next MVP-1 slice: backend method decision, runtime config, adapter contract, Core runtime, formal adapter skeleton, GUI runtime panel, operation panel, and log/trace/problems tabs.
- **Known gap:** This plan intentionally does not claim FF method support. It records the limitation and keeps method operations behind the adapter for the next backend decision.
- **Red-flag scan:** No task uses unresolved markers.
- **Type consistency:** `RuntimeSession`, `RuntimeServiceConfig`, `AdapterMethodResult`, `AdapterEvent`, and GUI panel names are defined before later tasks reference them.
