# someipy Protocol Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real-protocol spike runner that verifies whether `someipy` can support the project's required TCP/UDP method, event, field, and multi-service SOME/IP scenarios using the existing `ADC40_SOC/*.json` definitions.

**Architecture:** Keep all real `someipy` integration isolated under the adapter/spike boundary. The spike has three layers: API/daemon diagnostics, service-definition-to-someipy mapping, and scenario execution/reporting. The runner must produce a clear evidence report with PASS/FAIL/SKIP per scenario so the team can decide whether to continue with `someipy` or evaluate `vsomeip_py`/an internal stack.

**Tech Stack:** Python 3.11+, pytest, optional `someipy>=2.1,<3`, asyncio, subprocess-managed `someipyd`, existing `someip_gui_tool` parser/codec/domain models.

---

## Scope

This plan verifies the real protocol backend. It does not build the full GUI operation panel.

Covered here:

- Install and environment diagnostics for optional `someipy`.
- API probe for the `someipy` classes/functions the project needs.
- `someipyd` process/config management.
- Mapping current domain models to `someipy` `Service`, `Method`, `Event`, and `EventGroup` objects.
- Dry-run scenario validation from `ADC40_SOC` JSON.
- Best-effort real loopback runner against local `someipyd`.
- Evidence report in JSON and text.

Not covered here:

- Production GUI wiring.
- Production `SomeIpAdapter` replacement.
- Multi-machine ECU testing.
- Automatic VLAN/firewall configuration.

## References

Use the current official `someipy` documentation while implementing:

- someipy v2 architecture and daemon model: `https://someipy.readthedocs.io/en/latest/whatsnew.html`
- daemon command/config: `https://someipy.readthedocs.io/en/v2.0.0/someipy_daemon.html`
- API reference: `https://someipy.readthedocs.io/en/latest/api/`
- `ClientServiceInstance`: `https://someipy.readthedocs.io/en/latest/api/client_service_instance.html`
- `ServerServiceInstance`: `https://someipy.readthedocs.io/en/latest/api/server_service_instance.html`
- `Method`: `https://someipy.readthedocs.io/en/latest/api/method.html`
- `EventGroup`: `https://someipy.readthedocs.io/en/latest/api/eventgroup.html`
- `Event`: `https://someipy.readthedocs.io/en/latest/api/event.html`
- `connect_to_someipy_daemon`: `https://someipy.readthedocs.io/en/latest/api/connect_to_someipy_daemon.html`

## Planned File Structure

- Create: `src/someip_gui_tool/spike/__init__.py` - package marker.
- Create: `src/someip_gui_tool/spike/result.py` - spike status, step result, and report models.
- Create: `src/someip_gui_tool/adapters/someipy_api.py` - optional import/API probe for `someipy`.
- Create: `src/someip_gui_tool/adapters/someipy_mapping.py` - domain model to `someipy` service object mapping.
- Create: `src/someip_gui_tool/adapters/someipy_daemon.py` - subprocess/config manager for `someipyd`.
- Create: `src/someip_gui_tool/spike/scenarios.py` - fixed scenario catalog from `ADC40_SOC` definitions.
- Create: `src/someip_gui_tool/spike/runner.py` - dry-run and real-run orchestration.
- Create: `scripts/run_protocol_spike.py` - CLI entry point.
- Create: `tests/test_spike_result.py` - report model tests.
- Create: `tests/test_someipy_api.py` - API probe tests without requiring real `someipy`.
- Create: `tests/test_someipy_mapping.py` - mapping tests with fake `someipy` classes.
- Create: `tests/test_someipy_daemon.py` - daemon manager tests with mocked subprocess.
- Create: `tests/test_protocol_scenarios.py` - scenario catalog and dry-run tests.
- Create: `tests/test_protocol_spike_cli.py` - CLI smoke tests.

---

### Task 1: Spike Result Models

**Files:**
- Create: `src/someip_gui_tool/spike/__init__.py`
- Create: `src/someip_gui_tool/spike/result.py`
- Test: `tests/test_spike_result.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_spike_result.py`:

```python
from someip_gui_tool.spike.result import SpikeReport, SpikeStatus, SpikeStepResult


def test_report_failed_is_true_when_any_step_fails():
    report = SpikeReport(
        name="protocol-spike",
        steps=[
            SpikeStepResult(name="api", status=SpikeStatus.PASS, detail="api ok"),
            SpikeStepResult(name="tcp-method", status=SpikeStatus.FAIL, detail="connection failed"),
        ],
    )

    assert report.failed is True
    text = report.as_text()
    assert "protocol-spike" in text
    assert "PASS api - api ok" in text
    assert "FAIL tcp-method - connection failed" in text


def test_report_failed_is_false_for_pass_and_skip():
    report = SpikeReport(
        name="protocol-spike",
        steps=[
            SpikeStepResult(name="api", status=SpikeStatus.PASS, detail="api ok"),
            SpikeStepResult(name="real-run", status=SpikeStatus.SKIP, detail="someipy missing"),
        ],
    )

    assert report.failed is False
```

- [ ] **Step 2: Run the tests and verify failure**

Run:

```powershell
python -m pytest tests/test_spike_result.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'someip_gui_tool.spike'`.

- [ ] **Step 3: Implement result models**

Create `src/someip_gui_tool/spike/__init__.py`:

```python
"""Protocol spike helpers."""
```

Create `src/someip_gui_tool/spike/result.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SpikeStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class SpikeStepResult:
    name: str
    status: SpikeStatus
    detail: str
    data: dict[str, Any] = field(default_factory=dict)

    def as_text(self) -> str:
        return f"{self.status.value} {self.name} - {self.detail}"


@dataclass(frozen=True)
class SpikeReport:
    name: str
    steps: list[SpikeStepResult]

    @property
    def failed(self) -> bool:
        return any(step.status is SpikeStatus.FAIL for step in self.steps)

    def as_text(self) -> str:
        lines = [f"Spike report: {self.name}"]
        lines.extend(step.as_text() for step in self.steps)
        return "\n".join(lines)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "failed": self.failed,
            "steps": [
                {
                    "name": step.name,
                    "status": step.status.value,
                    "detail": step.detail,
                    "data": step.data,
                }
                for step in self.steps
            ],
        }
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_spike_result.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/someip_gui_tool/spike tests/test_spike_result.py
git commit -m "feat: add protocol spike report models"
```

Expected: commit succeeds.

---

### Task 2: someipy API Probe

**Files:**
- Create: `src/someip_gui_tool/adapters/someipy_api.py`
- Test: `tests/test_someipy_api.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_someipy_api.py`:

```python
from types import SimpleNamespace

from someip_gui_tool.adapters.someipy_api import SomeipyApiProbe, SomeipyApiStatus


def test_api_probe_reports_missing_module(monkeypatch):
    probe = SomeipyApiProbe(importer=lambda name: (_ for _ in ()).throw(ModuleNotFoundError(name)))

    status = probe.probe()

    assert status.available is False
    assert "not installed" in status.detail
    assert "python -m pip install -e .[someipy]" in status.detail


def test_api_probe_reports_missing_symbols():
    fake = SimpleNamespace(ServiceBuilder=object)
    probe = SomeipyApiProbe(importer=lambda name: fake)

    status = probe.probe()

    assert status.available is False
    assert "missing" in status.detail
    assert "ClientServiceInstance" in status.detail


def test_api_probe_returns_module_when_required_symbols_exist():
    names = [
        "ServiceBuilder",
        "Method",
        "Event",
        "EventGroup",
        "TransportLayerProtocol",
        "ClientServiceInstance",
        "ServerServiceInstance",
        "connect_to_someipy_daemon",
    ]
    fake = SimpleNamespace(**{name: object() for name in names})
    probe = SomeipyApiProbe(importer=lambda name: fake)

    status = probe.probe()
    module = probe.require_module()

    assert isinstance(status, SomeipyApiStatus)
    assert status.available is True
    assert status.detail == "someipy API is available"
    assert module is fake
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_someipy_api.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `someipy_api`.

- [ ] **Step 3: Implement API probe**

Create `src/someip_gui_tool/adapters/someipy_api.py`:

```python
from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import ModuleType
from typing import Callable


REQUIRED_SOMEIPY_SYMBOLS = (
    "ServiceBuilder",
    "Method",
    "Event",
    "EventGroup",
    "TransportLayerProtocol",
    "ClientServiceInstance",
    "ServerServiceInstance",
    "connect_to_someipy_daemon",
)


@dataclass(frozen=True)
class SomeipyApiStatus:
    available: bool
    detail: str
    missing_symbols: tuple[str, ...] = ()


class SomeipyApiProbe:
    def __init__(self, importer: Callable[[str], object] | None = None) -> None:
        self._importer = importer or importlib.import_module
        self._module: object | None = None

    def probe(self) -> SomeipyApiStatus:
        try:
            module = self._importer("someipy")
        except ModuleNotFoundError:
            return SomeipyApiStatus(
                available=False,
                detail="someipy is not installed. Install with: python -m pip install -e .[someipy]",
            )

        missing = tuple(name for name in REQUIRED_SOMEIPY_SYMBOLS if not hasattr(module, name))
        if missing:
            return SomeipyApiStatus(
                available=False,
                detail="someipy API missing required symbols: " + ", ".join(missing),
                missing_symbols=missing,
            )
        self._module = module
        return SomeipyApiStatus(available=True, detail="someipy API is available")

    def require_module(self) -> ModuleType:
        if self._module is None:
            status = self.probe()
            if not status.available:
                raise RuntimeError(status.detail)
        return self._module  # type: ignore[return-value]
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_someipy_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/someip_gui_tool/adapters/someipy_api.py tests/test_someipy_api.py
git commit -m "feat: add someipy api probe"
```

Expected: commit succeeds.

---

### Task 3: Map Domain Services to someipy Service Objects

**Files:**
- Create: `src/someip_gui_tool/adapters/someipy_mapping.py`
- Test: `tests/test_someipy_mapping.py`

- [ ] **Step 1: Write fake someipy mapping tests**

Create `tests/test_someipy_mapping.py`:

```python
from dataclasses import dataclass
from types import SimpleNamespace

from someip_gui_tool.adapters.someipy_mapping import SomeipyServiceFactory
from someip_gui_tool.parsing.service_json import load_service_definition


@dataclass(frozen=True)
class FakeMethod:
    id: int
    protocol: str
    method_handler: object | None = None


@dataclass(frozen=True)
class FakeEvent:
    id: int
    protocol: str


@dataclass(frozen=True)
class FakeEventGroup:
    id: int
    events: list[FakeEvent]


class FakeBuilder:
    def __init__(self):
        self.service_id = None
        self.major_version = None
        self.minor_version = None
        self.methods = []
        self.eventgroups = []

    def with_service_id(self, id):
        self.service_id = id
        return self

    def with_major_version(self, major_version):
        self.major_version = major_version
        return self

    def with_minor_version(self, minor_version):
        self.minor_version = minor_version
        return self

    def with_method(self, method):
        self.methods.append(method)
        return self

    def with_eventgroup(self, eventgroup):
        self.eventgroups.append(eventgroup)
        return self

    def build(self):
        return SimpleNamespace(
            service_id=self.service_id,
            major_version=self.major_version,
            minor_version=self.minor_version,
            methods=self.methods,
            eventgroups=self.eventgroups,
        )


class FakeProtocol:
    TCP = "TCP"
    UDP = "UDP"


def fake_api():
    return SimpleNamespace(
        ServiceBuilder=FakeBuilder,
        Method=FakeMethod,
        Event=FakeEvent,
        EventGroup=FakeEventGroup,
        TransportLayerProtocol=FakeProtocol,
    )


def test_builds_udp_method_and_event_service(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080D.json")

    mapped = SomeipyServiceFactory(fake_api()).build_service(service)

    assert mapped.service_id == 0x080D
    assert mapped.major_version == 1
    assert mapped.minor_version == 0
    assert [method.id for method in mapped.methods] == [0x0001]
    assert mapped.methods[0].protocol == "UDP"
    assert [group.id for group in mapped.eventgroups] == [0x0001]
    assert [event.id for event in mapped.eventgroups[0].events] == [0x8001]
    assert mapped.eventgroups[0].events[0].protocol == "UDP"


def test_builds_field_notifier_as_eventgroup(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")

    mapped = SomeipyServiceFactory(fake_api()).build_service(service)

    assert [method.id for method in mapped.methods] == [0x1001]
    assert [group.id for group in mapped.eventgroups] == [0x0001]
    assert [event.id for event in mapped.eventgroups[0].events] == [0x9001]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_someipy_mapping.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `someipy_mapping`.

- [ ] **Step 3: Implement mapping**

Create `src/someip_gui_tool/adapters/someipy_mapping.py`:

```python
from __future__ import annotations

from collections import defaultdict
from typing import Any

from someip_gui_tool.domain.enums import TransportProtocol
from someip_gui_tool.domain.models import EventDefinition, FieldPartDefinition, MethodDefinition, ServiceDefinition


class SomeipyServiceFactory:
    def __init__(self, someipy_api: Any) -> None:
        self._api = someipy_api

    def build_service(self, service: ServiceDefinition) -> Any:
        builder = (
            self._api.ServiceBuilder()
            .with_service_id(service.service_id)
            .with_major_version(service.deployment.major_version)
            .with_minor_version(service.deployment.minor_version)
        )

        for method in self._method_parts(service):
            builder = builder.with_method(
                self._api.Method(
                    id=method.method_id if isinstance(method, MethodDefinition) else method.element_id,
                    protocol=self._protocol(method.transport),
                    method_handler=None,
                )
            )

        for eventgroup_id, events in self._eventgroups(service).items():
            builder = builder.with_eventgroup(
                self._api.EventGroup(
                    id=eventgroup_id,
                    events=[
                        self._api.Event(id=event_id, protocol=self._protocol(transport))
                        for event_id, transport in events
                    ],
                )
            )

        return builder.build()

    def _protocol(self, transport: TransportProtocol) -> Any:
        if transport == TransportProtocol.TCP:
            return self._api.TransportLayerProtocol.TCP
        if transport == TransportProtocol.UDP:
            return self._api.TransportLayerProtocol.UDP
        raise ValueError(f"Unsupported transport: {transport!r}")

    def _method_parts(self, service: ServiceDefinition) -> list[MethodDefinition | FieldPartDefinition]:
        parts: list[MethodDefinition | FieldPartDefinition] = list(service.methods)
        for field in service.fields:
            if field.getter is not None:
                parts.append(field.getter)
            if field.setter is not None:
                parts.append(field.setter)
        return parts

    def _eventgroups(self, service: ServiceDefinition) -> dict[int, list[tuple[int, TransportProtocol]]]:
        groups: dict[int, list[tuple[int, TransportProtocol]]] = defaultdict(list)
        for event in service.events:
            self._add_event(groups, event)
        for field in service.fields:
            if field.notifier is not None:
                self._add_field_notifier(groups, field.notifier)
        return dict(groups)

    def _add_event(
        self,
        groups: dict[int, list[tuple[int, TransportProtocol]]],
        event: EventDefinition,
    ) -> None:
        if event.eventgroup_id is None:
            return
        groups[event.eventgroup_id].append((event.event_id, event.transport))

    def _add_field_notifier(
        self,
        groups: dict[int, list[tuple[int, TransportProtocol]]],
        notifier: FieldPartDefinition,
    ) -> None:
        if notifier.eventgroup_id is None:
            return
        groups[notifier.eventgroup_id].append((notifier.element_id, notifier.transport))
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_someipy_mapping.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/someip_gui_tool/adapters/someipy_mapping.py tests/test_someipy_mapping.py
git commit -m "feat: map service definitions to someipy"
```

Expected: commit succeeds.

---

### Task 4: Manage someipyd Process and Config

**Files:**
- Create: `src/someip_gui_tool/adapters/someipy_daemon.py`
- Test: `tests/test_someipy_daemon.py`

- [ ] **Step 1: Write daemon manager tests**

Create `tests/test_someipy_daemon.py`:

```python
from pathlib import Path

import pytest

from someip_gui_tool.adapters.someipy_daemon import SomeipydConfig, SomeipydProcess


class FakePopen:
    def __init__(self, args, cwd=None):
        self.args = args
        self.cwd = cwd
        self.terminated = False
        self.killed = False
        self.returncode = None

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


def test_config_writes_someipyd_json(tmp_path):
    config = SomeipydConfig(interface="127.0.0.1", sd_address="239.192.255.251", sd_port=30490)

    path = config.write(tmp_path)

    text = path.read_text(encoding="utf-8")
    assert '"interface": "127.0.0.1"' in text
    assert '"sd_address": "239.192.255.251"' in text
    assert '"sd_port": 30490' in text


def test_process_start_uses_someipyd_config(monkeypatch, tmp_path):
    created = []
    monkeypatch.setattr("shutil.which", lambda command: "C:/tools/someipyd.exe")
    monkeypatch.setattr("subprocess.Popen", lambda args, cwd=None: created.append(FakePopen(args, cwd)) or created[-1])

    process = SomeipydProcess.start(
        config=SomeipydConfig(interface="127.0.0.1"),
        work_dir=tmp_path,
    )

    assert process.process.args[0] == "C:/tools/someipyd.exe"
    assert "--config" in process.process.args
    assert Path(process.process.args[-1]).exists()
    process.stop()
    assert process.process.terminated is True


def test_process_start_fails_when_command_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda command: None)

    with pytest.raises(RuntimeError, match="someipyd command not found"):
        SomeipydProcess.start(config=SomeipydConfig(interface="127.0.0.1"), work_dir=tmp_path)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_someipy_daemon.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `someipy_daemon`.

- [ ] **Step 3: Implement daemon manager**

Create `src/someip_gui_tool/adapters/someipy_daemon.py`:

```python
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SomeipydConfig:
    interface: str
    sd_address: str = "239.192.255.251"
    sd_port: int = 30490
    log_level: str = "DEBUG"

    def as_dict(self) -> dict[str, object]:
        return {
            "interface": self.interface,
            "sd_address": self.sd_address,
            "sd_port": self.sd_port,
            "log_level": self.log_level,
        }

    def write(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "someipyd-config.json"
        path.write_text(json.dumps(self.as_dict(), indent=2), encoding="utf-8")
        return path


@dataclass
class SomeipydProcess:
    process: subprocess.Popen
    config_path: Path

    @classmethod
    def start(cls, config: SomeipydConfig, work_dir: Path) -> "SomeipydProcess":
        command = shutil.which("someipyd")
        if command is None:
            raise RuntimeError("someipyd command not found. Install with: python -m pip install -e .[someipy]")
        config_path = config.write(work_dir)
        process = subprocess.Popen([command, "--config", str(config_path)], cwd=str(work_dir))
        return cls(process=process, config_path=config_path)

    def stop(self) -> None:
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_someipy_daemon.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/someip_gui_tool/adapters/someipy_daemon.py tests/test_someipy_daemon.py
git commit -m "feat: add someipyd process manager"
```

Expected: commit succeeds.

---

### Task 5: Protocol Scenario Catalog and Dry Run

**Files:**
- Create: `src/someip_gui_tool/spike/scenarios.py`
- Create: `src/someip_gui_tool/spike/runner.py`
- Test: `tests/test_protocol_scenarios.py`

- [ ] **Step 1: Write scenario tests**

Create `tests/test_protocol_scenarios.py`:

```python
from someip_gui_tool.spike.runner import ProtocolSpikeRunner
from someip_gui_tool.spike.scenarios import ScenarioKind, build_scenarios


def test_builds_required_scenarios(adc40_soc_dir):
    scenarios = build_scenarios(adc40_soc_dir)

    assert {scenario.kind for scenario in scenarios} == {
        ScenarioKind.UDP_FF_METHOD,
        ScenarioKind.TCP_METHOD,
        ScenarioKind.UDP_EVENT,
        ScenarioKind.TCP_EVENT,
        ScenarioKind.FIELD_GETTER_NOTIFIER,
    }


def test_dry_run_validates_payloads_and_services(adc40_soc_dir):
    runner = ProtocolSpikeRunner(definition_root=adc40_soc_dir)

    report = runner.run_dry()

    assert report.failed is False
    assert [step.status.value for step in report.steps] == ["PASS", "PASS", "PASS", "PASS", "PASS"]
    assert "UDP FF method" in report.as_text()
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_protocol_scenarios.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `spike.scenarios`.

- [ ] **Step 3: Implement scenarios**

Create `src/someip_gui_tool/spike/scenarios.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from someip_gui_tool.core.service_registry import ServiceRegistry
from someip_gui_tool.domain.models import EventDefinition, FieldDefinition, MethodDefinition, ServiceDefinition


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
    payload_values: dict[str, Any] | None = None


def build_scenarios(definition_root: Path) -> list[ProtocolScenario]:
    registry = ServiceRegistry.load_directory(definition_root)
    second_start = registry.get_service(0x080D)
    hut_system = registry.get_service(0x0F01)
    adas_route = registry.get_service(0x080E)
    cockpit = registry.get_service(0x080A)
    field_service = registry.get_service(0x080C)

    field = field_service.fields[0]
    return [
        ProtocolScenario(
            kind=ScenarioKind.UDP_FF_METHOD,
            title="UDP FF method SecondStartCtrl",
            service=second_start,
            method=second_start.methods[0],
            payload_values={"SecondStartCtrlCmd": 1},
        ),
        ProtocolScenario(
            kind=ScenarioKind.TCP_METHOD,
            title="TCP method AudioRecPopupReq",
            service=hut_system,
            method=hut_system.methods[0],
            payload_values={"AudioRecPopup": 1},
        ),
        ProtocolScenario(
            kind=ScenarioKind.UDP_EVENT,
            title="UDP cycle event VehicleInfo",
            service=adas_route,
            event=adas_route.events[0],
            payload_values={"VehicleInfo": {"VehicleSpeed": 12.5, "Odometer": 99.25}},
        ),
        ProtocolScenario(
            kind=ScenarioKind.TCP_EVENT,
            title="TCP trigger event IntellgntSwtDecoupSts",
            service=cockpit,
            event=cockpit.events[0],
            payload_values={"IntellgntSwtDecoupSts": [1, 2, 3]},
        ),
        ProtocolScenario(
            kind=ScenarioKind.FIELD_GETTER_NOTIFIER,
            title="Field Getter/Notifier VertHeiRmdSts",
            service=field_service,
            field=field,
            payload_values={"VertHeiRmdSts": 1},
        ),
    ]
```

- [ ] **Step 4: Implement dry runner**

Create `src/someip_gui_tool/spike/runner.py`:

```python
from __future__ import annotations

from pathlib import Path

from someip_gui_tool.codec.payload_codec import PayloadCodec
from someip_gui_tool.spike.result import SpikeReport, SpikeStatus, SpikeStepResult
from someip_gui_tool.spike.scenarios import ProtocolScenario, build_scenarios


class ProtocolSpikeRunner:
    def __init__(self, definition_root: Path) -> None:
        self.definition_root = definition_root
        self.codec = PayloadCodec()

    def run_dry(self) -> SpikeReport:
        steps = [self._dry_step(scenario) for scenario in build_scenarios(self.definition_root)]
        return SpikeReport(name="someipy-protocol-spike-dry-run", steps=steps)

    def _dry_step(self, scenario: ProtocolScenario) -> SpikeStepResult:
        try:
            payload = self._encode_payload(scenario)
        except Exception as exc:
            return SpikeStepResult(
                name=scenario.kind.value,
                status=SpikeStatus.FAIL,
                detail=f"{scenario.title}: payload encode failed: {exc}",
            )
        return SpikeStepResult(
            name=scenario.kind.value,
            status=SpikeStatus.PASS,
            detail=f"{scenario.title}: encoded {len(payload)} bytes",
            data={"service_id": scenario.service.service_id_hex, "payload_hex": payload.hex()},
        )

    def _encode_payload(self, scenario: ProtocolScenario) -> bytes:
        if scenario.method is not None:
            return self.codec.encode_parameters(scenario.method.parameters, scenario.payload_values or {})
        if scenario.event is not None:
            return self.codec.encode_parameters(scenario.event.parameters, scenario.payload_values or {})
        if scenario.field is not None and scenario.field.notifier is not None:
            return self.codec.encode_parameters(scenario.field.notifier.parameters, scenario.payload_values or {})
        raise ValueError(f"Scenario has no encodable element: {scenario.kind.value}")
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/test_protocol_scenarios.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/someip_gui_tool/spike/scenarios.py src/someip_gui_tool/spike/runner.py tests/test_protocol_scenarios.py
git commit -m "feat: add protocol spike scenarios"
```

Expected: commit succeeds.

---

### Task 6: Real someipy Loopback Runner

**Files:**
- Modify: `src/someip_gui_tool/spike/runner.py`
- Test: `tests/test_protocol_scenarios.py`

- [ ] **Step 1: Add real-run tests with fake dependencies**

Append to `tests/test_protocol_scenarios.py`:

```python
from someip_gui_tool.spike.result import SpikeStatus


def test_real_run_skips_when_someipy_api_missing(adc40_soc_dir):
    class MissingProbe:
        def probe(self):
            return type("Status", (), {"available": False, "detail": "someipy missing"})()

    report = ProtocolSpikeRunner(definition_root=adc40_soc_dir).run_real(
        api_probe=MissingProbe(),
        local_ip="127.0.0.1",
        base_port=30500,
        start_daemon=False,
    )

    assert report.failed is False
    assert report.steps[0].status is SpikeStatus.SKIP
    assert "someipy missing" in report.steps[0].detail


def test_real_run_records_api_available_before_network_attempt(adc40_soc_dir):
    class AvailableProbe:
        def probe(self):
            return type("Status", (), {"available": True, "detail": "api ok"})()

        def require_module(self):
            raise RuntimeError("fake network boundary")

    report = ProtocolSpikeRunner(definition_root=adc40_soc_dir).run_real(
        api_probe=AvailableProbe(),
        local_ip="127.0.0.1",
        base_port=30500,
        start_daemon=False,
    )

    assert report.failed is True
    assert report.steps[0].status is SpikeStatus.PASS
    assert report.steps[1].status is SpikeStatus.FAIL
    assert "fake network boundary" in report.steps[1].detail
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_protocol_scenarios.py -q
```

Expected: FAIL because `ProtocolSpikeRunner.run_real` does not exist.

- [ ] **Step 3: Implement real-run orchestration**

Modify `src/someip_gui_tool/spike/runner.py` to include these imports:

```python
import asyncio
import tempfile
from typing import Any

from someip_gui_tool.adapters.someipy_api import SomeipyApiProbe
from someip_gui_tool.adapters.someipy_daemon import SomeipydConfig, SomeipydProcess
from someip_gui_tool.adapters.someipy_mapping import SomeipyServiceFactory
```

Add these methods inside `ProtocolSpikeRunner`:

```python
    def run_real(
        self,
        *,
        api_probe: Any | None = None,
        local_ip: str,
        base_port: int,
        start_daemon: bool,
    ) -> SpikeReport:
        probe = api_probe or SomeipyApiProbe()
        status = probe.probe()
        if not status.available:
            return SpikeReport(
                name="someipy-protocol-spike-real-run",
                steps=[SpikeStepResult(name="someipy-api", status=SpikeStatus.SKIP, detail=status.detail)],
            )

        steps = [SpikeStepResult(name="someipy-api", status=SpikeStatus.PASS, detail=status.detail)]
        daemon_process: SomeipydProcess | None = None
        try:
            if start_daemon:
                work_dir = Path(tempfile.mkdtemp(prefix="someipyd-spike-"))
                daemon_process = SomeipydProcess.start(
                    config=SomeipydConfig(interface=local_ip),
                    work_dir=work_dir,
                )
                steps.append(SpikeStepResult(name="someipyd", status=SpikeStatus.PASS, detail="someipyd process started"))
            api = probe.require_module()
            real_steps = asyncio.run(self._run_real_async(api=api, local_ip=local_ip, base_port=base_port))
            steps.extend(real_steps)
        except Exception as exc:
            steps.append(SpikeStepResult(name="real-loopback", status=SpikeStatus.FAIL, detail=str(exc)))
        finally:
            if daemon_process is not None:
                daemon_process.stop()
        return SpikeReport(name="someipy-protocol-spike-real-run", steps=steps)

    async def _run_real_async(self, *, api: Any, local_ip: str, base_port: int) -> list[SpikeStepResult]:
        daemon = await api.connect_to_someipy_daemon()
        steps: list[SpikeStepResult] = []
        try:
            factory = SomeipyServiceFactory(api)
            for index, scenario in enumerate(build_scenarios(self.definition_root)):
                mapped_service = factory.build_service(scenario.service)
                server = api.ServerServiceInstance(
                    daemon=daemon,
                    service=mapped_service,
                    instance_id=scenario.service.deployment.instance_id,
                    endpoint_ip=local_ip,
                    endpoint_port=base_port + index * 10,
                    ttl=int(scenario.service.deployment.offer_ttl_s),
                    cyclic_offer_delay_ms=1000,
                )
                client = api.ClientServiceInstance(
                    daemon=daemon,
                    service=mapped_service,
                    instance_id=scenario.service.deployment.instance_id,
                    endpoint_ip=local_ip,
                    endpoint_port=base_port + index * 10 + 1,
                    client_id=0x1000 + index,
                )
                await server.start_offer()
                try:
                    available = await client.is_available()
                    status = SpikeStatus.PASS if available else SpikeStatus.FAIL
                    detail = f"{scenario.title}: availability={available}"
                    if scenario.event is not None and scenario.event.eventgroup_id is not None:
                        client.subscribe_eventgroup(
                            api.EventGroup(
                                id=scenario.event.eventgroup_id,
                                events=[api.Event(id=scenario.event.event_id, protocol=factory._protocol(scenario.event.transport))],
                            ),
                            ttl_subscription_seconds=int(scenario.service.deployment.find_ttl_s),
                        )
                        payload = self._encode_payload(scenario)
                        server.send_event(scenario.event.eventgroup_id, scenario.event.event_id, payload)
                        detail += f", event_payload={payload.hex()}"
                    if scenario.field is not None and scenario.field.notifier is not None:
                        notifier = scenario.field.notifier
                        client.subscribe_eventgroup(
                            api.EventGroup(
                                id=notifier.eventgroup_id,
                                events=[api.Event(id=notifier.element_id, protocol=factory._protocol(notifier.transport))],
                            ),
                            ttl_subscription_seconds=int(scenario.service.deployment.find_ttl_s),
                        )
                        payload = self._encode_payload(scenario)
                        server.send_event(notifier.eventgroup_id, notifier.element_id, payload)
                        detail += f", notifier_payload={payload.hex()}"
                    steps.append(SpikeStepResult(name=scenario.kind.value, status=status, detail=detail))
                finally:
                    await server.stop_offer()
        finally:
            disconnect = getattr(daemon, "disconnect_from_daemon", None)
            if disconnect is not None:
                await disconnect()
        return steps
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_protocol_scenarios.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/someip_gui_tool/spike/runner.py tests/test_protocol_scenarios.py
git commit -m "feat: add real someipy spike runner"
```

Expected: commit succeeds.

---

### Task 7: Protocol Spike CLI

**Files:**
- Create: `scripts/run_protocol_spike.py`
- Test: `tests/test_protocol_spike_cli.py`

- [ ] **Step 1: Write CLI tests**

Create `tests/test_protocol_spike_cli.py`:

```python
import json
import os
import subprocess
import sys
from pathlib import Path


def test_protocol_spike_cli_dry_run_outputs_text(repo_root):
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_protocol_spike.py",
            "--definition-root",
            "ADC40_SOC",
            "--mode",
            "dry-run",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "someipy-protocol-spike-dry-run" in result.stdout
    assert "PASS udp-ff-method" in result.stdout


def test_protocol_spike_cli_can_write_json_report(repo_root, tmp_path):
    report_path = tmp_path / "spike-report.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_protocol_spike.py",
            "--definition-root",
            "ADC40_SOC",
            "--mode",
            "dry-run",
            "--json-report",
            str(report_path),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["name"] == "someipy-protocol-spike-dry-run"
    assert payload["failed"] is False
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_protocol_spike_cli.py -q
```

Expected: FAIL because `scripts/run_protocol_spike.py` does not exist.

- [ ] **Step 3: Implement CLI**

Create `scripts/run_protocol_spike.py`:

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from someip_gui_tool.spike.runner import ProtocolSpikeRunner


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SOME/IP protocol spike scenarios.")
    parser.add_argument("--definition-root", default="ADC40_SOC")
    parser.add_argument("--mode", choices=("dry-run", "real"), default="dry-run")
    parser.add_argument("--local-ip", default="127.0.0.1")
    parser.add_argument("--base-port", type=int, default=30500)
    parser.add_argument("--start-daemon", action="store_true")
    parser.add_argument("--json-report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    runner = ProtocolSpikeRunner(definition_root=Path(args.definition_root))
    if args.mode == "dry-run":
        report = runner.run_dry()
    else:
        report = runner.run_real(
            local_ip=args.local_ip,
            base_port=args.base_port,
            start_daemon=args.start_daemon,
        )
    print(report.as_text())
    if args.json_report:
        Path(args.json_report).write_text(json.dumps(report.as_dict(), indent=2), encoding="utf-8")
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests**

Run:

```powershell
python -m pytest tests/test_protocol_spike_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Run the dry-run manually**

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

- [ ] **Step 6: Commit**

Run:

```powershell
git add scripts/run_protocol_spike.py tests/test_protocol_spike_cli.py
git commit -m "feat: add protocol spike cli"
```

Expected: commit succeeds.

---

### Task 8: Real Protocol Evidence Run

**Files:**
- Modify: `docs/superpowers/plans/2026-05-14-someipy-protocol-spike.md` only if the real run reveals command corrections that must be captured for repeatability.

- [ ] **Step 1: Install optional someipy dependency**

Run:

```powershell
python -m pip install -e ".[dev,someipy]"
```

Expected: command succeeds and `someipy` becomes importable.

- [ ] **Step 2: Run all tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest
```

Expected: all tests pass.

- [ ] **Step 3: Run dry-run report**

Run:

```powershell
python scripts/run_protocol_spike.py --definition-root ADC40_SOC --mode dry-run --json-report protocol-spike-dry-run.json
```

Expected: exit code `0`, all five dry-run scenarios PASS, and `protocol-spike-dry-run.json` is created. Do not commit the generated JSON report.

- [ ] **Step 4: Run real mode without daemon autostart**

Run:

```powershell
python scripts/run_protocol_spike.py --definition-root ADC40_SOC --mode real --local-ip 127.0.0.1 --base-port 30500 --json-report protocol-spike-real-no-daemon.json
```

Expected: command produces a report. If `someipyd` is not already running, the report may return exit code `1` with a FAIL step that identifies daemon connection failure. Do not treat this as implementation failure; it proves the error path is visible.

- [ ] **Step 5: Run real mode with daemon autostart**

Run:

```powershell
python scripts/run_protocol_spike.py --definition-root ADC40_SOC --mode real --local-ip 127.0.0.1 --base-port 30500 --start-daemon --json-report protocol-spike-real.json
```

Expected: command produces a JSON report with explicit PASS/FAIL/SKIP for API, daemon, UDP FF method availability, TCP method availability, UDP event send, TCP event send, and Field Notifier send. If any real scenario fails, keep the report and summarize the exact failing step in the final response. Do not commit generated JSON.

- [ ] **Step 6: Record decision summary in git commit if command corrections were needed**

If you changed the plan because a command needed correction, commit that correction:

```powershell
git add docs/superpowers/plans/2026-05-14-someipy-protocol-spike.md
git commit -m "docs: record protocol spike command corrections"
```

If no files changed, do not create an empty commit.

---

## Final Verification

- [ ] **Step 1: Run full tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest
```

Expected: all tests pass.

- [ ] **Step 2: Run dry spike**

Run:

```powershell
python scripts/run_protocol_spike.py --definition-root ADC40_SOC --mode dry-run
```

Expected: exit code `0` and all five dry-run scenarios PASS.

- [ ] **Step 3: Check git status**

Run:

```powershell
git status --short
```

Expected: no uncommitted source changes. Generated `protocol-spike-*.json` files should be deleted or ignored before completion.

---

## Decision Gate After This Plan

Use the real-run evidence to choose the next path:

- Continue with `someipy` if daemon start, service availability, TCP/UDP event send, and field notifier send all work locally.
- Keep `someipy` but constrain MVP scope if method FF/RR behavior or field getter behavior is incomplete but events and service discovery are usable.
- Evaluate `vsomeip_py` or an internal C/C++ backend if TCP service availability, eventgroup subscription, or daemon startup fails in a way that cannot be worked around on Windows.
