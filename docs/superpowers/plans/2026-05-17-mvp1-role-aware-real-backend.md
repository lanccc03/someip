# MVP-1 Role-Aware Real Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the MVP-1 runtime loop role-aware and allow the GUI process to run against `SomeipyAdapter` instead of only the mock adapter.

**Architecture:** Keep GUI calls routed through `RuntimeSession`; do not let GUI call `someipy` directly. Add an adapter-layer start configuration so Core can pass role, IP, and port decisions to any backend without making adapters import Core models. Preserve the mock backend as the default development path, and expose the real backend through a small environment-based factory before building a fuller GUI settings dialog.

**Tech Stack:** Python 3.11+, PySide6, qasync, pytest, pytest-asyncio, pytest-qt, existing `someip_gui_tool` layered package, optional `someipy`.

---

## Scope

This plan implements the next MVP-1 hardening slice after the current GUI/runtime foundation:

- Role-aware start behavior:
  - Server start configures the adapter and offers the service.
  - Client start configures the adapter and performs a find-service check.
- Runtime config propagation to the adapter:
  - role
  - local IP
  - server port
  - client port
  - multicast IP
  - offer/find TTL
- `SomeipyAdapter` uses configured service endpoint ports instead of only deriving ports from `base_port + index`.
- The app can create a `SomeipyAdapter` session via environment variables while keeping mock as the default.

This plan does not implement event unsubscribe buttons, cycle publish buttons, project save/load, structured payload forms, raw hex mode, trace filtering, or Windows packaging. Those are separate follow-on slices.

## Planned File Structure

- Modify: `src/someip_gui_tool/adapters/base.py` - add `AdapterStartConfig` and extend `start_service`.
- Modify: `src/someip_gui_tool/adapters/mock.py` - accept and record start config; keep deterministic mock behavior.
- Modify: `src/someip_gui_tool/core/runtime_session.py` - map `RuntimeServiceConfig` to adapter config and run role-specific offer/find startup actions.
- Modify: `src/someip_gui_tool/adapters/someipy_adapter.py` - consume adapter config, use configured endpoint ports, avoid implicit server offer on client start.
- Create: `src/someip_gui_tool/gui/backend_factory.py` - create a `RuntimeSession` for mock or someipy from environment settings.
- Modify: `src/someip_gui_tool/gui/app.py` - use the backend factory when constructing `MainWindow`.
- Modify: `tests/test_runtime_session.py` - role-aware lifecycle tests.
- Modify: `tests/test_mock_adapter.py` - mock adapter config contract tests.
- Modify: `tests/test_someipy_adapter.py` - role/config/port behavior tests.
- Create: `tests/test_gui_backend_factory.py` - environment-driven backend factory tests.

---

### Task 1: Add Adapter Start Config and Role-Aware Core Lifecycle

**Files:**
- Modify: `src/someip_gui_tool/adapters/base.py`
- Modify: `src/someip_gui_tool/adapters/mock.py`
- Modify: `src/someip_gui_tool/core/runtime_session.py`
- Modify: `tests/test_runtime_session.py`
- Modify: `tests/test_mock_adapter.py`

- [ ] **Step 1: Write failing RuntimeSession lifecycle tests**

Append these tests to `tests/test_runtime_session.py`:

```python
class UnavailableFindAdapter(MockSomeIpAdapter):
    async def find_service(self, service):
        await super().find_service(service)
        return False


@pytest.mark.asyncio
async def test_runtime_session_server_start_offers_service(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)

    await session.start_service(service, _valid_config(service, Role.SERVER))

    assert [call.name for call in adapter.calls] == [
        "start_service",
        "offer_service",
    ]
    assert adapter.calls[0].details["role"] == "Server"
    assert adapter.calls[0].details["local_ip"] == service.deployment.server_ip
    assert adapter.calls[0].details["server_port"] == 30500
    assert adapter.calls[0].details["client_port"] == 30501
    assert session.run_log[-2].message == (
        f"Offered service {service.service_name} ({service.service_id_hex})"
    )
    assert session.run_log[-1].message == (
        f"Started service {service.service_name} ({service.service_id_hex})"
    )


@pytest.mark.asyncio
async def test_runtime_session_client_start_finds_service(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)

    await session.start_service(service, _valid_config(service, Role.CLIENT))

    assert [call.name for call in adapter.calls] == [
        "start_service",
        "find_service",
    ]
    assert adapter.calls[0].details["role"] == "Client"
    assert adapter.calls[0].details["local_ip"] == service.deployment.client_ip
    assert session.run_log[-2].message == (
        f"Found service {service.service_name} ({service.service_id_hex})"
    )
    assert session.run_log[-1].message == (
        f"Started service {service.service_name} ({service.service_id_hex})"
    )


@pytest.mark.asyncio
async def test_runtime_session_client_start_records_find_timeout_warning(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    session = RuntimeSession(adapter=UnavailableFindAdapter())

    await session.start_service(service, _valid_config(service, Role.CLIENT))

    assert session.problems[-1].code == "find_service_unavailable"
    assert session.problems[-1].severity == "warning"
    assert "not available" in session.problems[-1].message
    assert session.run_log[-2].level == "warning"
    assert session.run_log[-2].error_detail == "find_service_unavailable"
    assert session.run_log[-1].message == (
        f"Started service {service.service_name} ({service.service_id_hex})"
    )
```

- [ ] **Step 2: Write failing mock adapter config test**

Append this test to `tests/test_mock_adapter.py`:

```python
from someip_gui_tool.adapters.base import AdapterStartConfig
from someip_gui_tool.domain.enums import Role


@pytest.mark.asyncio
async def test_mock_adapter_records_start_config(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = MockSomeIpAdapter()
    config = AdapterStartConfig(
        role=Role.SERVER,
        local_ip="172.16.3.14/24",
        server_port=30500,
        client_port=30501,
        multicast_ip="239.192.255.251",
        offer_ttl_s=3.0,
        find_ttl_s=3.0,
    )

    await adapter.start_service(service, config)

    assert adapter.calls[-1].name == "start_service"
    assert adapter.calls[-1].details == {
        "service_id": service.service_id_hex,
        "role": "Server",
        "local_ip": "172.16.3.14/24",
        "server_port": 30500,
        "client_port": 30501,
    }
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_runtime_session.py::test_runtime_session_server_start_offers_service \
  tests/test_runtime_session.py::test_runtime_session_client_start_finds_service \
  tests/test_runtime_session.py::test_runtime_session_client_start_records_find_timeout_warning \
  tests/test_mock_adapter.py::test_mock_adapter_records_start_config -q
```

Expected: FAIL because `AdapterStartConfig` does not exist and `MockSomeIpAdapter.start_service()` does not accept a config argument.

- [ ] **Step 4: Add adapter start config contract**

In `src/someip_gui_tool/adapters/base.py`, add this import near the existing imports:

```python
from someip_gui_tool.domain.enums import Role
```

Add this dataclass above `AdapterMethodResult`:

```python
@dataclass(frozen=True)
class AdapterStartConfig:
    role: Role
    local_ip: str
    server_port: int
    client_port: int
    multicast_ip: str
    offer_ttl_s: float
    find_ttl_s: float
```

Change the abstract method signature:

```python
    @abstractmethod
    async def start_service(
        self,
        service: ServiceDefinition,
        config: AdapterStartConfig | None = None,
    ) -> None:
        raise NotImplementedError
```

- [ ] **Step 5: Update mock adapter start signature and recorded details**

In `src/someip_gui_tool/adapters/mock.py`, update the base import:

```python
from someip_gui_tool.adapters.base import (
    AdapterEvent,
    AdapterMethodResult,
    AdapterStartConfig,
    EventHandler,
    SomeIpAdapter,
)
```

Replace `MockSomeIpAdapter.start_service()` with:

```python
    async def start_service(
        self,
        service: ServiceDefinition,
        config: AdapterStartConfig | None = None,
    ) -> None:
        details: dict[str, object] = {"service_id": service.service_id_hex}
        if config is not None:
            details.update(
                {
                    "role": config.role.value,
                    "local_ip": config.local_ip,
                    "server_port": config.server_port,
                    "client_port": config.client_port,
                }
            )
        self.calls.append(AdapterCall("start_service", details))
```

- [ ] **Step 6: Make RuntimeSession build adapter config and run role-specific startup**

In `src/someip_gui_tool/core/runtime_session.py`, update the adapter import:

```python
from someip_gui_tool.adapters.base import (
    AdapterEvent,
    AdapterMethodResult,
    AdapterStartConfig,
    SomeIpAdapter,
)
```

Replace the adapter start block inside `RuntimeSession.start_service()` with:

```python
        adapter_config = _adapter_start_config(config)
        try:
            await self.adapter.start_service(service, adapter_config)
            if config.role is Role.SERVER:
                await self.adapter.offer_service(service)
                self._log(
                    "info",
                    "Core",
                    f"Offered service {service.service_name} ({service.service_id_hex})",
                    service_id=service.service_id_hex,
                )
            else:
                found = await self.adapter.find_service(service)
                if found:
                    self._log(
                        "info",
                        "Core",
                        f"Found service {service.service_name} ({service.service_id_hex})",
                        service_id=service.service_id_hex,
                    )
                else:
                    message = (
                        f"Service {service.service_name} ({service.service_id_hex}) "
                        "is not available after find-service polling."
                    )
                    self.problems.append(
                        RuntimeProblem(
                            code="find_service_unavailable",
                            severity="warning",
                            message=message,
                            service_id=service.service_id,
                        )
                    )
                    self._log(
                        "warning",
                        "Core",
                        message,
                        service_id=service.service_id_hex,
                        error_detail="find_service_unavailable",
                    )
        except Exception as exc:
            self._record_adapter_exception(
                "start_service_adapter_exception",
                service,
                f"Adapter failed to start service {service.service_name}",
                exc,
            )
            raise
```

Add this helper near the bottom of `src/someip_gui_tool/core/runtime_session.py`, before `_eventgroup_hex()`:

```python
def _adapter_start_config(config: RuntimeServiceConfig) -> AdapterStartConfig:
    if config.server_port is None or config.client_port is None:
        raise ValueError("Runtime config must have server_port and client_port after validation.")
    return AdapterStartConfig(
        role=config.role,
        local_ip=config.local_ip,
        server_port=config.server_port,
        client_port=config.client_port,
        multicast_ip=config.multicast_ip,
        offer_ttl_s=config.offer_ttl_s or 0.0,
        find_ttl_s=config.find_ttl_s or 0.0,
    )
```

- [ ] **Step 7: Run lifecycle tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_runtime_session.py::test_runtime_session_server_start_offers_service \
  tests/test_runtime_session.py::test_runtime_session_client_start_finds_service \
  tests/test_runtime_session.py::test_runtime_session_client_start_records_find_timeout_warning \
  tests/test_mock_adapter.py::test_mock_adapter_records_start_config -q
```

Expected: PASS.

- [ ] **Step 8: Run existing runtime and mock adapter tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_runtime_session.py \
  tests/test_mock_adapter.py -q
```

Expected: PASS. If an existing assertion expects only `start_service` before an event operation, update it to include the new role-specific `offer_service` or `find_service` call for the start path.

- [ ] **Step 9: Commit role-aware core lifecycle**

Run:

```bash
git add \
  src/someip_gui_tool/adapters/base.py \
  src/someip_gui_tool/adapters/mock.py \
  src/someip_gui_tool/core/runtime_session.py \
  tests/test_runtime_session.py \
  tests/test_mock_adapter.py
git commit -m "feat: make runtime service start role aware"
```

Expected: commit succeeds.

---

### Task 2: Make SomeipyAdapter Use Runtime Config Ports and Explicit Offer

**Files:**
- Modify: `src/someip_gui_tool/adapters/someipy_adapter.py`
- Modify: `tests/test_someipy_adapter.py`

- [ ] **Step 1: Write failing someipy adapter config tests**

Add this import to `tests/test_someipy_adapter.py`:

```python
from someip_gui_tool.adapters.base import AdapterStartConfig
from someip_gui_tool.domain.enums import Role
```

Add this helper near the top of `tests/test_someipy_adapter.py`:

```python
def _adapter_start_config(role: Role = Role.CLIENT) -> AdapterStartConfig:
    return AdapterStartConfig(
        role=role,
        local_ip="127.0.0.1/24",
        server_port=32000,
        client_port=32001,
        multicast_ip="239.192.255.251",
        offer_ttl_s=3.0,
        find_ttl_s=3.0,
    )
```

Append these tests:

```python
@pytest.mark.asyncio
async def test_someipy_adapter_start_service_uses_configured_ports(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(service, _adapter_start_config(Role.CLIENT))

    assert api.servers[0].endpoint_ip == "127.0.0.1"
    assert api.clients[0].endpoint_ip == "127.0.0.1"
    assert api.servers[0].endpoint_port == 32000
    assert api.clients[0].endpoint_port == 32001
    assert api.servers[0].start_awaited is False


@pytest.mark.asyncio
async def test_someipy_adapter_offer_service_starts_offer_after_configured_start(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(service, _adapter_start_config(Role.SERVER))
    await adapter.offer_service(service)

    assert len(api.servers) == 1
    assert api.servers[0].endpoint_port == 32000
    assert api.servers[0].start_awaited is True


@pytest.mark.asyncio
async def test_someipy_adapter_find_service_after_configured_start_uses_existing_client(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    api = FakeSomeipyApi(availability_sequences={service.service_id: [True]})
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)

    await adapter.start_service(service, _adapter_start_config(Role.CLIENT))
    result = await adapter.find_service(service)

    assert result is True
    assert len(api.clients) == 1
    assert api.clients[0].endpoint_port == 32001
    assert api.availability_calls[service.service_id] == 1
```

- [ ] **Step 2: Run new someipy adapter tests to verify they fail**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_someipy_adapter.py::test_someipy_adapter_start_service_uses_configured_ports \
  tests/test_someipy_adapter.py::test_someipy_adapter_offer_service_starts_offer_after_configured_start \
  tests/test_someipy_adapter.py::test_someipy_adapter_find_service_after_configured_start_uses_existing_client -q
```

Expected: FAIL because `SomeipyAdapter.start_service()` does not accept `AdapterStartConfig`, and legacy start implicitly starts offer.

- [ ] **Step 3: Update SomeipyAdapter imports and runtime model**

In `src/someip_gui_tool/adapters/someipy_adapter.py`, update the base import:

```python
from someip_gui_tool.adapters.base import (
    AdapterEvent,
    AdapterMethodResult,
    AdapterStartConfig,
    EventHandler,
    SomeIpAdapter,
)
```

Add this helper near the constants:

```python
def _endpoint_host(ip_address: str) -> str:
    return ip_address.split("/", 1)[0]
```

- [ ] **Step 4: Update start, offer, find, and runtime creation signatures**

Replace `SomeipyAdapter.start_service()` with:

```python
    async def start_service(
        self,
        service: ServiceDefinition,
        config: AdapterStartConfig | None = None,
    ) -> None:
        runtime = await self._runtime_for_service(service, config)
        if config is None:
            await _maybe_await(runtime.server.start_offer())
```

Replace `SomeipyAdapter.offer_service()` with:

```python
    async def offer_service(self, service: ServiceDefinition) -> None:
        runtime = await self._runtime_for_service(service)
        await _maybe_await(runtime.server.start_offer())
```

Leave `find_service()` public signature unchanged, but confirm it calls `_runtime_for_service(service)` and reuses an existing configured runtime.

Replace the service-index and endpoint calculation block inside `_runtime_for_service()` with:

```python
        service_index = self._next_service_index
        self._next_service_index += 1
        if config is None:
            endpoint_ip = self._local_ip
            endpoint_port = self._base_port + service_index * _PORT_STRIDE
            client_port = endpoint_port + 1
        else:
            endpoint_ip = _endpoint_host(config.local_ip)
            endpoint_port = config.server_port
            client_port = config.client_port
```

Change `_runtime_for_service()` signature to:

```python
    async def _runtime_for_service(
        self,
        service: ServiceDefinition,
        config: AdapterStartConfig | None = None,
    ) -> _SomeipyServiceRuntime:
```

Use `endpoint_ip` for both `ServerServiceInstance` and `ClientServiceInstance`:

```python
            endpoint_ip=endpoint_ip,
```

- [ ] **Step 5: Run new someipy adapter tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_someipy_adapter.py::test_someipy_adapter_start_service_uses_configured_ports \
  tests/test_someipy_adapter.py::test_someipy_adapter_offer_service_starts_offer_after_configured_start \
  tests/test_someipy_adapter.py::test_someipy_adapter_find_service_after_configured_start_uses_existing_client -q
```

Expected: PASS.

- [ ] **Step 6: Run all someipy adapter tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_someipy_adapter.py -q
```

Expected: PASS. Existing tests that call `start_service(service)` without config keep legacy implicit-offer behavior.

- [ ] **Step 7: Commit someipy config propagation**

Run:

```bash
git add src/someip_gui_tool/adapters/someipy_adapter.py tests/test_someipy_adapter.py
git commit -m "feat: pass runtime config to someipy adapter"
```

Expected: commit succeeds.

---

### Task 3: Add Environment-Based GUI Backend Factory

**Files:**
- Create: `src/someip_gui_tool/gui/backend_factory.py`
- Modify: `src/someip_gui_tool/gui/app.py`
- Create: `tests/test_gui_backend_factory.py`

- [ ] **Step 1: Write failing backend factory tests**

Create `tests/test_gui_backend_factory.py`:

```python
import pytest

from someip_gui_tool.adapters.mock import MockSomeIpAdapter
from someip_gui_tool.adapters.someipy_adapter import SomeipyAdapter
from someip_gui_tool.gui.backend_factory import BackendSettings, create_session


def test_create_session_defaults_to_mock_backend() -> None:
    session = create_session(BackendSettings())

    assert isinstance(session.adapter, MockSomeIpAdapter)


def test_create_session_can_select_someipy_backend() -> None:
    session = create_session(
        BackendSettings(
            backend="someipy",
            local_ip="127.0.0.1",
            base_port=30500,
            start_daemon=True,
        )
    )

    assert isinstance(session.adapter, SomeipyAdapter)
    assert session.adapter._local_ip == "127.0.0.1"
    assert session.adapter._base_port == 30500
    assert session.adapter._start_daemon is True


def test_create_session_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="Unsupported backend"):
        create_session(BackendSettings(backend="internal"))
```

- [ ] **Step 2: Run backend factory tests to verify they fail**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_gui_backend_factory.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `someip_gui_tool.gui.backend_factory`.

- [ ] **Step 3: Implement backend factory**

Create `src/someip_gui_tool/gui/backend_factory.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass

from someip_gui_tool.adapters.mock import MockSomeIpAdapter
from someip_gui_tool.adapters.someipy_adapter import SomeipyAdapter
from someip_gui_tool.core.runtime_session import RuntimeSession


@dataclass(frozen=True)
class BackendSettings:
    backend: str = "mock"
    local_ip: str = "127.0.0.1"
    base_port: int = 30500
    start_daemon: bool = False

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> BackendSettings:
        source = os.environ if environ is None else environ
        return cls(
            backend=source.get("SOMEIP_GUI_BACKEND", "mock").strip().lower(),
            local_ip=source.get("SOMEIP_GUI_LOCAL_IP", "127.0.0.1").strip(),
            base_port=int(source.get("SOMEIP_GUI_BASE_PORT", "30500")),
            start_daemon=_env_flag(source.get("SOMEIP_GUI_START_DAEMON", "")),
        )


def create_session(settings: BackendSettings | None = None) -> RuntimeSession:
    resolved = settings or BackendSettings.from_env()
    if resolved.backend == "mock":
        return RuntimeSession(MockSomeIpAdapter())
    if resolved.backend == "someipy":
        return RuntimeSession(
            SomeipyAdapter(
                local_ip=resolved.local_ip,
                base_port=resolved.base_port,
                start_daemon=resolved.start_daemon,
            )
        )
    raise ValueError(f"Unsupported backend: {resolved.backend!r}")


def _env_flag(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
```

- [ ] **Step 4: Add environment parsing test**

Append this test to `tests/test_gui_backend_factory.py`:

```python
def test_backend_settings_from_env() -> None:
    settings = BackendSettings.from_env(
        {
            "SOMEIP_GUI_BACKEND": "someipy",
            "SOMEIP_GUI_LOCAL_IP": "192.168.0.10",
            "SOMEIP_GUI_BASE_PORT": "31000",
            "SOMEIP_GUI_START_DAEMON": "true",
        }
    )

    assert settings == BackendSettings(
        backend="someipy",
        local_ip="192.168.0.10",
        base_port=31000,
        start_daemon=True,
    )
```

- [ ] **Step 5: Wire app startup through backend factory**

In `src/someip_gui_tool/gui/app.py`, add this import:

```python
from someip_gui_tool.gui.backend_factory import create_session
```

Replace:

```python
    window = MainWindow()
```

with:

```python
    window = MainWindow(session=create_session())
```

- [ ] **Step 6: Run backend factory tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_gui_backend_factory.py -q
```

Expected: PASS.

- [ ] **Step 7: Run GUI smoke tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_gui_smoke.py tests/test_gui_payload_defaults.py -q
```

Expected: PASS. The GUI remains mock-backed by default because `SOMEIP_GUI_BACKEND` is not set.

- [ ] **Step 8: Commit backend factory**

Run:

```bash
git add \
  src/someip_gui_tool/gui/backend_factory.py \
  src/someip_gui_tool/gui/app.py \
  tests/test_gui_backend_factory.py
git commit -m "feat: add gui backend factory"
```

Expected: commit succeeds.

---

### Task 4: Verify Full Suite and Real-Backend Operator Path

**Files:**
- No source file changes expected in this task unless verification exposes a defect.

- [ ] **Step 1: Run focused runtime/backend tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_runtime_session.py \
  tests/test_mock_adapter.py \
  tests/test_someipy_adapter.py \
  tests/test_gui_backend_factory.py \
  tests/test_gui_smoke.py \
  tests/test_gui_payload_defaults.py -q
```

Expected: PASS.

- [ ] **Step 2: Run the full test suite**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest
```

Expected: `166 passed` or a larger passing count after the new tests are added.

- [ ] **Step 3: Run protocol spike dry-run**

Run:

```bash
.venv/bin/python scripts/run_protocol_spike.py --mode dry-run
```

Expected output includes:

```text
PASS udp-ff-method - UDP FF method SecondStartCtrl: encoded 1 bytes
PASS tcp-method - TCP method AudioRecPopupReq: encoded 8 bytes
PASS udp-event - UDP cycle event VehicleInfo: encoded 8 bytes
PASS tcp-event - TCP trigger event IntellgntSwtDecoupSts: encoded 3 bytes
PASS field-getter-notifier - Field Getter/Notifier VertHeiRmdSts: encoded 1 bytes
```

- [ ] **Step 4: Record the real-backend GUI launch command in the final handoff**

Use this command for an operator smoke run on a machine with `someipy` and `someipyd` installed:

```bash
SOMEIP_GUI_BACKEND=someipy \
SOMEIP_GUI_LOCAL_IP=127.0.0.1 \
SOMEIP_GUI_BASE_PORT=30500 \
SOMEIP_GUI_START_DAEMON=1 \
.venv/bin/python -m someip_gui_tool
```

Expected:

```text
The GUI starts. Starting a service in Server role records start_service and offer_service activity. Starting a service in Client role records start_service and find_service activity. FF methods still report limited.
```

- [ ] **Step 5: Commit verification-only doc note if needed**

If no source changes were made during verification, do not create a commit. If a small documentation note is added during handoff, run:

```bash
git add docs/superpowers/plans/2026-05-17-mvp1-role-aware-real-backend.md
git commit -m "docs: add role-aware backend implementation plan"
```

Expected: commit succeeds only when documentation changed after Task 3.

---

## Self-Review

**Spec coverage**

- Covers MVP-1 role-based Client/Server start semantics by making Core call offer for Server and find for Client.
- Covers MVP-1 explicit backend status by adding logs/problems for find success and find unavailability.
- Covers configured runtime ports reaching the real adapter.
- Keeps FF method support limited and visible through the existing capability behavior.
- Does not cover unsubscribe, cycle event publish, field setter, server method response configuration, project files, recent sessions, structured forms, raw hex mode, trace filtering, or Windows packaging. Those remain separate spec gaps.

**Placeholder scan**

- No placeholder markers, repeated-by-reference instructions, or unspecified validation steps are used.
- Every task includes exact files, exact tests, exact implementation snippets, commands, and expected outcomes.

**Type consistency**

- `AdapterStartConfig` is defined in `adapters/base.py` before it is imported by mock, someipy, and tests.
- `RuntimeSession.start_service()` continues to receive `RuntimeServiceConfig`; only the adapter boundary receives `AdapterStartConfig`.
- `SomeipyAdapter.start_service(service)` remains compatible with existing tests by accepting `config=None`.
