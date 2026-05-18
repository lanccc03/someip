# MVP-1 Real Backend Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the review findings from the MVP-1 role-aware real backend work so the GUI cleans up real backend resources, configured Someipy runtime settings cannot be silently ignored, and runtime multicast/TTL settings reach the backend.

**Architecture:** Keep GUI access routed through `RuntimeSession` and adapter interfaces. Treat `AdapterStartConfig` as the adapter boundary contract: `RuntimeSession` supplies service defaults when GUI panels omit TTLs, `SomeipyAdapter` stores and compares the config used to build a runtime, and daemon/runtime creation consumes config values when available. Preserve the mock adapter and legacy direct `SomeipyAdapter.start_service(service)` behavior for tests and development.

**Tech Stack:** Python 3.11+, PySide6, qasync, pytest, pytest-qt, existing `someip_gui_tool` package.

---

## File Structure

- Modify: `src/someip_gui_tool/gui/app.py` - ensure the app calls `session.adapter.shutdown()` after the Qt event loop stops.
- Create: `tests/test_gui_app.py` - headless unit coverage for app shutdown behavior without starting real Qt.
- Modify: `src/someip_gui_tool/adapters/someipy_adapter.py` - store runtime start config, rebuild stale unconfigured/differently configured runtimes, and consume configured multicast/TTL values.
- Modify: `tests/test_someipy_adapter.py` - regression coverage for runtime replacement and configured multicast/TTL propagation.
- Modify: `src/someip_gui_tool/core/runtime_session.py` - build `AdapterStartConfig` with service deployment TTL fallbacks.
- Modify: `tests/test_runtime_session.py` - regression coverage for TTL fallback at the adapter boundary.
- Modify: `src/someip_gui_tool/gui/runtime_panel.py` - preserve deployment TTL defaults when reconstructing runtime config from editable GUI fields.
- Modify: `tests/test_gui_smoke.py` - GUI runtime panel regression coverage for TTL preservation.

---

### Task 1: Shut Down the Adapter When the GUI Exits

**Files:**
- Modify: `src/someip_gui_tool/gui/app.py`
- Create: `tests/test_gui_app.py`

- [ ] **Step 1: Write the failing GUI app shutdown test**

Create `tests/test_gui_app.py`:

```python
from __future__ import annotations

from types import SimpleNamespace

from someip_gui_tool.gui import app as app_module


def _drive_immediate_coroutine(awaitable) -> None:
    try:
        awaitable.send(None)
    except StopIteration:
        return


def test_main_shuts_down_session_adapter(monkeypatch) -> None:
    shutdowns: list[str] = []
    shown: list[str] = []

    class FakeAdapter:
        async def shutdown(self) -> None:
            shutdowns.append("shutdown")

    class FakeLoop:
        def __init__(self, app) -> None:
            self.app = app
            self.ran_forever = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def run_forever(self) -> None:
            self.ran_forever = True

        def run_until_complete(self, awaitable) -> None:
            _drive_immediate_coroutine(awaitable)

    class FakeWindow:
        def __init__(self, *, session) -> None:
            self.session = session

        def show(self) -> None:
            shown.append("show")

    fake_session = SimpleNamespace(adapter=FakeAdapter())

    monkeypatch.setattr(app_module, "QApplication", lambda argv: object())
    monkeypatch.setattr(app_module, "QEventLoop", FakeLoop)
    monkeypatch.setattr(app_module, "MainWindow", FakeWindow)
    monkeypatch.setattr(app_module, "apply_theme", lambda app: None)
    monkeypatch.setattr(app_module, "create_session", lambda: fake_session)
    monkeypatch.setattr(app_module.asyncio, "set_event_loop", lambda loop: None)

    assert app_module.main() == 0

    assert shown == ["show"]
    assert shutdowns == ["shutdown"]
```

- [ ] **Step 2: Run the new test to verify it fails**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; .\.venv\Scripts\python -m pytest tests/test_gui_app.py -q
```

Expected: FAIL because `main()` never calls `session.adapter.shutdown()`.

- [ ] **Step 3: Update app startup to keep the session and shut it down after the Qt loop**

In `src/someip_gui_tool/gui/app.py`, replace `main()` with:

```python
def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    session = create_session()
    window = MainWindow(session=session)
    window.show()
    with loop:
        loop.run_forever()
        loop.run_until_complete(session.adapter.shutdown())
    return 0
```

- [ ] **Step 4: Run the GUI app shutdown test**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; .\.venv\Scripts\python -m pytest tests/test_gui_app.py -q
```

Expected: PASS.

- [ ] **Step 5: Run GUI smoke coverage**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; .\.venv\Scripts\python -m pytest tests/test_gui_smoke.py tests/test_gui_payload_defaults.py tests/test_gui_app.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit GUI shutdown fix**

Run:

```powershell
git add src/someip_gui_tool/gui/app.py tests/test_gui_app.py
git commit -m "fix: shut down gui backend on exit"
```

Expected: commit succeeds.

---

### Task 2: Prevent Configured Someipy Starts From Reusing Stale Unconfigured Runtimes

**Files:**
- Modify: `src/someip_gui_tool/adapters/someipy_adapter.py`
- Modify: `tests/test_someipy_adapter.py`

- [ ] **Step 1: Write failing regression tests for stale runtime reuse**

Append these tests to `tests/test_someipy_adapter.py`:

```python
@pytest.mark.asyncio
async def test_someipy_adapter_configured_start_replaces_unconfigured_runtime(
    adc40_soc_dir,
) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    api = FakeSomeipyApi(availability_sequences={service.service_id: [True]})
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)

    await adapter.find_service(service)
    await adapter.start_service(service, _adapter_start_config(Role.CLIENT))

    assert len(api.servers) == 2
    assert len(api.clients) == 2
    assert api.servers[0].endpoint_port == 31000
    assert api.clients[0].endpoint_port == 31001
    assert api.servers[0].stop_awaited is True
    assert api.servers[1].endpoint_port == 32000
    assert api.clients[1].endpoint_port == 32001
    assert adapter._service_runtimes[service.service_id].endpoint_port == 32000
    assert adapter._service_runtimes[service.service_id].client_port == 32001


@pytest.mark.asyncio
async def test_someipy_adapter_repeated_configured_start_reuses_matching_runtime(
    adc40_soc_dir,
) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    config = _adapter_start_config(Role.CLIENT)

    await adapter.start_service(service, config)
    await adapter.start_service(service, config)

    assert len(api.servers) == 1
    assert len(api.clients) == 1
    assert api.servers[0].endpoint_port == 32000
    assert api.clients[0].endpoint_port == 32001
```

- [ ] **Step 2: Run the new tests to verify the first one fails**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; .\.venv\Scripts\python -m pytest `
  tests/test_someipy_adapter.py::test_someipy_adapter_configured_start_replaces_unconfigured_runtime `
  tests/test_someipy_adapter.py::test_someipy_adapter_repeated_configured_start_reuses_matching_runtime -q
```

Expected: FAIL because `_runtime_for_service()` returns the existing runtime before checking the new config.

- [ ] **Step 3: Store the start config on each Someipy runtime**

In `src/someip_gui_tool/adapters/someipy_adapter.py`, extend `_SomeipyServiceRuntime`:

```python
@dataclass
class _SomeipyServiceRuntime:
    mapped_service: Any
    server: Any
    client: Any
    endpoint_port: int
    client_port: int
    active_eventgroups: set[int]
    start_config: AdapterStartConfig | None
```

- [ ] **Step 4: Replace stale runtimes when a configured start conflicts**

In `_runtime_for_service()`, replace the existing early return block:

```python
        runtime = self._service_runtimes.get(service.service_id)
        if runtime is not None:
            return runtime
```

with:

```python
        runtime = self._service_runtimes.get(service.service_id)
        if runtime is not None:
            if config is None or runtime.start_config == config:
                return runtime
            await _maybe_await(runtime.server.stop_offer())
            self._service_runtimes.pop(service.service_id, None)
```

When creating the runtime near the bottom of `_runtime_for_service()`, add `start_config=config`:

```python
        runtime = _SomeipyServiceRuntime(
            mapped_service=mapped_service,
            server=server,
            client=client,
            endpoint_port=endpoint_port,
            client_port=client_port,
            active_eventgroups=set(),
            start_config=config,
        )
```

- [ ] **Step 5: Run the stale-runtime tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; .\.venv\Scripts\python -m pytest `
  tests/test_someipy_adapter.py::test_someipy_adapter_configured_start_replaces_unconfigured_runtime `
  tests/test_someipy_adapter.py::test_someipy_adapter_repeated_configured_start_reuses_matching_runtime -q
```

Expected: PASS.

- [ ] **Step 6: Run all Someipy adapter tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; .\.venv\Scripts\python -m pytest tests/test_someipy_adapter.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit stale runtime fix**

Run:

```powershell
git add src/someip_gui_tool/adapters/someipy_adapter.py tests/test_someipy_adapter.py
git commit -m "fix: rebuild someipy runtime for new start config"
```

Expected: commit succeeds.

---

### Task 3: Propagate Runtime TTL and Multicast Config to the Real Backend

**Files:**
- Modify: `src/someip_gui_tool/adapters/someipy_adapter.py`
- Modify: `src/someip_gui_tool/core/runtime_session.py`
- Modify: `src/someip_gui_tool/gui/runtime_panel.py`
- Modify: `tests/test_someipy_adapter.py`
- Modify: `tests/test_runtime_session.py`
- Modify: `tests/test_gui_smoke.py`

- [ ] **Step 1: Update the Someipy test helper to allow custom network settings**

In `tests/test_someipy_adapter.py`, replace `_adapter_start_config()` with:

```python
def _adapter_start_config(
    role: Role = Role.CLIENT,
    *,
    local_ip: str = "127.0.0.1/24",
    multicast_ip: str = "239.192.255.251",
    offer_ttl_s: float = 3.0,
    find_ttl_s: float = 3.0,
) -> AdapterStartConfig:
    return AdapterStartConfig(
        role=role,
        local_ip=local_ip,
        server_port=32000,
        client_port=32001,
        multicast_ip=multicast_ip,
        offer_ttl_s=offer_ttl_s,
        find_ttl_s=find_ttl_s,
    )
```

- [ ] **Step 2: Write failing Someipy adapter tests for configured TTL and multicast**

Append these tests to `tests/test_someipy_adapter.py`:

```python
@pytest.mark.asyncio
async def test_someipy_adapter_uses_configured_offer_and_find_ttls(
    adc40_soc_dir,
) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]
    assert event.eventgroup_id is not None
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)

    await adapter.start_service(
        service,
        _adapter_start_config(Role.CLIENT, offer_ttl_s=7.0, find_ttl_s=11.0),
    )
    await adapter.subscribe_eventgroup(service, event.eventgroup_id)

    assert api.servers[0].ttl == 7
    assert api.clients[0].subscribed_eventgroups == [(event.eventgroup_id, 11)]


@pytest.mark.asyncio
async def test_someipy_adapter_owned_daemon_uses_configured_multicast_and_interface(
    adc40_soc_dir,
    monkeypatch,
    tmp_path,
) -> None:
    api = FakeSomeipyApi()
    started = []

    class FakeProcess:
        def stop(self) -> None:
            return None

    def fake_start(config, work_dir):
        started.append((config, work_dir))
        return FakeProcess()

    monkeypatch.setattr(
        "someip_gui_tool.adapters.someipy_adapter.SomeipydProcess.start",
        fake_start,
    )
    adapter = SomeipyAdapter(
        api=api,
        local_ip="127.0.0.1",
        base_port=31000,
        start_daemon=True,
        daemon_work_dir=tmp_path,
    )
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(
        service,
        _adapter_start_config(
            Role.SERVER,
            local_ip="192.168.0.10/24",
            multicast_ip="239.1.2.3",
        ),
    )
    await adapter.shutdown()

    assert len(started) == 1
    assert started[0][0].interface == "192.168.0.10"
    assert started[0][0].tcp_host == "192.168.0.10"
    assert started[0][0].sd_address == "239.1.2.3"
    assert started[0][0].tcp_port == 31000
    assert started[0][1] == tmp_path
```

- [ ] **Step 3: Write a failing RuntimeSession TTL fallback test**

Add this helper class to `tests/test_runtime_session.py` near the other adapter test doubles:

```python
class CaptureStartConfigAdapter(MockSomeIpAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.start_config = None

    async def start_service(self, service, config=None):
        self.start_config = config
        await super().start_service(service, config)
```

Append this test to `tests/test_runtime_session.py`:

```python
@pytest.mark.asyncio
async def test_runtime_session_adapter_config_uses_service_ttl_defaults(
    adc40_soc_dir,
):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = CaptureStartConfigAdapter()
    session = RuntimeSession(adapter=adapter)
    config = replace(
        _valid_config(service, Role.CLIENT),
        offer_ttl_s=None,
        find_ttl_s=None,
    )

    await session.start_service(service, config)

    assert adapter.start_config is not None
    assert adapter.start_config.offer_ttl_s == service.deployment.offer_ttl_s
    assert adapter.start_config.find_ttl_s == service.deployment.find_ttl_s
```

- [ ] **Step 4: Write a failing RuntimePanel TTL preservation test**

Add this import to `tests/test_gui_smoke.py` if it is not already present:

```python
from someip_gui_tool.core.runtime_config import infer_runtime_config
```

Append this test to `tests/test_gui_smoke.py`:

```python
def test_runtime_panel_preserves_deployment_ttls_when_reading_config(
    qtbot,
    adc40_soc_dir,
) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    panel = RuntimePanel()
    qtbot.addWidget(panel)

    panel.set_config(infer_runtime_config(service, Role.CLIENT))
    panel.server_port_edit.setText("30500")
    panel.client_port_edit.setText("30501")

    config = panel.config_for_service(service)

    assert config.offer_ttl_s == service.deployment.offer_ttl_s
    assert config.find_ttl_s == service.deployment.find_ttl_s
```

- [ ] **Step 5: Run the new TTL/multicast tests to verify they fail**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; .\.venv\Scripts\python -m pytest `
  tests/test_someipy_adapter.py::test_someipy_adapter_uses_configured_offer_and_find_ttls `
  tests/test_someipy_adapter.py::test_someipy_adapter_owned_daemon_uses_configured_multicast_and_interface `
  tests/test_runtime_session.py::test_runtime_session_adapter_config_uses_service_ttl_defaults `
  tests/test_gui_smoke.py::test_runtime_panel_preserves_deployment_ttls_when_reading_config -q
```

Expected: FAIL because Someipy uses deployment TTLs, daemon config ignores adapter start config, `RuntimeSession` uses `0.0` for missing TTLs, and `RuntimePanel.config_for_service()` drops deployment TTLs.

- [ ] **Step 6: Preserve deployment TTLs when RuntimePanel reconstructs config**

In `src/someip_gui_tool/gui/runtime_panel.py`, update the imports:

```python
from dataclasses import replace

from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QLineEdit

from someip_gui_tool.core.runtime_config import RuntimeServiceConfig, infer_runtime_config
```

Replace `config_for_service()` with:

```python
    def config_for_service(self, service: ServiceDefinition) -> RuntimeServiceConfig:
        role = Role(self.role_combo.currentText())
        base_config = infer_runtime_config(service, role)
        return replace(
            base_config,
            local_ip=self.local_ip_edit.text().strip(),
            remote_ip=self.remote_ip_edit.text().strip(),
            server_port=_optional_port(self.server_port_edit.text(), "Server port"),
            client_port=_optional_port(self.client_port_edit.text(), "Client port"),
            multicast_ip=self.multicast_ip_edit.text().strip(),
        )
```

- [ ] **Step 7: Use service deployment TTL defaults when RuntimeServiceConfig omits TTLs**

In `src/someip_gui_tool/core/runtime_session.py`, change the call site in `start_service()` from:

```python
        adapter_config = _adapter_start_config(config)
```

to:

```python
        adapter_config = _adapter_start_config(service, config)
```

Replace `_adapter_start_config()` with:

```python
def _adapter_start_config(
    service: ServiceDefinition,
    config: RuntimeServiceConfig,
) -> AdapterStartConfig:
    if config.server_port is None or config.client_port is None:
        raise ValueError("Runtime config must have server_port and client_port after validation.")
    return AdapterStartConfig(
        role=config.role,
        local_ip=config.local_ip,
        server_port=config.server_port,
        client_port=config.client_port,
        multicast_ip=config.multicast_ip,
        offer_ttl_s=(
            config.offer_ttl_s
            if config.offer_ttl_s is not None
            else service.deployment.offer_ttl_s
        ),
        find_ttl_s=(
            config.find_ttl_s
            if config.find_ttl_s is not None
            else service.deployment.find_ttl_s
        ),
    )
```

- [ ] **Step 8: Store and use configured TTLs in Someipy runtimes**

In `src/someip_gui_tool/adapters/someipy_adapter.py`, extend `_SomeipyServiceRuntime` again:

```python
@dataclass
class _SomeipyServiceRuntime:
    mapped_service: Any
    server: Any
    client: Any
    endpoint_port: int
    client_port: int
    active_eventgroups: set[int]
    start_config: AdapterStartConfig | None
    offer_ttl_s: float
    find_ttl_s: float
```

In `subscribe_eventgroup()`, replace:

```python
                ttl_subscription_seconds=int(service.deployment.find_ttl_s),
```

with:

```python
                ttl_subscription_seconds=int(runtime.find_ttl_s),
```

Inside `_runtime_for_service()`, after endpoint/client port calculation, add:

```python
        if config is None:
            offer_ttl_s = service.deployment.offer_ttl_s
            find_ttl_s = service.deployment.find_ttl_s
        else:
            offer_ttl_s = config.offer_ttl_s
            find_ttl_s = config.find_ttl_s
```

Replace server creation TTL:

```python
            ttl=int(service.deployment.offer_ttl_s),
```

with:

```python
            ttl=int(offer_ttl_s),
```

When creating `_SomeipyServiceRuntime`, include:

```python
            offer_ttl_s=offer_ttl_s,
            find_ttl_s=find_ttl_s,
```

- [ ] **Step 9: Pass configured daemon network values when Someipy owns the daemon**

In `src/someip_gui_tool/adapters/someipy_adapter.py`, change `_runtime_for_service()` to pass config into daemon setup:

```python
        daemon = await self._ensure_daemon(config)
```

Change `_ensure_daemon()` signature:

```python
    async def _ensure_daemon(self, config: AdapterStartConfig | None = None) -> Any:
```

Inside `_ensure_daemon()`, before the `if self._start_daemon...` block, add:

```python
            daemon_ip = self._local_ip if config is None else _endpoint_host(config.local_ip)
            sd_address = (
                "239.192.255.251"
                if config is None
                else config.multicast_ip
            )
```

Replace both `SomeipydConfig(...)` constructions in `_ensure_daemon()` with:

```python
                config = SomeipydConfig(
                    interface=daemon_ip,
                    sd_address=sd_address,
                    tcp_host=daemon_ip,
                    tcp_port=self._base_port,
                )
```

and:

```python
            config = SomeipydConfig(
                interface=daemon_ip,
                sd_address=sd_address,
                tcp_host=daemon_ip,
                tcp_port=self._base_port,
            ).client_config()
```

- [ ] **Step 10: Run the new TTL/multicast tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; .\.venv\Scripts\python -m pytest `
  tests/test_someipy_adapter.py::test_someipy_adapter_uses_configured_offer_and_find_ttls `
  tests/test_someipy_adapter.py::test_someipy_adapter_owned_daemon_uses_configured_multicast_and_interface `
  tests/test_runtime_session.py::test_runtime_session_adapter_config_uses_service_ttl_defaults `
  tests/test_gui_smoke.py::test_runtime_panel_preserves_deployment_ttls_when_reading_config -q
```

Expected: PASS.

- [ ] **Step 11: Run focused runtime/backend/GUI tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; .\.venv\Scripts\python -m pytest `
  tests/test_runtime_session.py `
  tests/test_mock_adapter.py `
  tests/test_someipy_adapter.py `
  tests/test_gui_backend_factory.py `
  tests/test_gui_smoke.py `
  tests/test_gui_payload_defaults.py `
  tests/test_gui_app.py -q
```

Expected: PASS.

- [ ] **Step 12: Commit TTL and multicast propagation fix**

Run:

```powershell
git add `
  src/someip_gui_tool/adapters/someipy_adapter.py `
  src/someip_gui_tool/core/runtime_session.py `
  src/someip_gui_tool/gui/runtime_panel.py `
  tests/test_someipy_adapter.py `
  tests/test_runtime_session.py `
  tests/test_gui_smoke.py
git commit -m "fix: propagate runtime ttl and multicast settings"
```

Expected: commit succeeds.

---

### Task 4: Final Verification

**Files:**
- No source file changes expected.

- [ ] **Step 1: Run the full test suite**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; .\.venv\Scripts\python -m pytest
```

Expected: PASS with at least `177 passed`; the exact count should be larger after the new tests are added.

- [ ] **Step 2: Run the protocol spike dry-run**

Run:

```powershell
.\.venv\Scripts\python scripts\run_protocol_spike.py --mode dry-run
```

Expected output includes:

```text
PASS udp-ff-method - UDP FF method SecondStartCtrl: encoded 1 bytes
PASS tcp-method - TCP method AudioRecPopupReq: encoded 8 bytes
PASS udp-event - UDP cycle event VehicleInfo: encoded 8 bytes
PASS tcp-event - TCP trigger event IntellgntSwtDecoupSts: encoded 3 bytes
PASS field-getter-notifier - Field Getter/Notifier VertHeiRmdSts: encoded 1 bytes
```

- [ ] **Step 3: Check git status**

Run:

```powershell
git status --short
```

Expected: no uncommitted changes unless the executor intentionally leaves verification notes.

---

## Self-Review

**Spec coverage**

- Fixes GUI resource cleanup by calling adapter shutdown after the Qt event loop exits.
- Fixes stale Someipy runtime reuse by comparing stored `AdapterStartConfig` and rebuilding when a configured start would otherwise reuse an incompatible runtime.
- Fixes runtime TTL propagation from GUI/Core to the real adapter.
- Fixes Someipy owned daemon multicast/interface configuration when a configured runtime start is the first daemon setup.
- Preserves mock backend behavior and direct unconfigured `SomeipyAdapter.start_service(service)` legacy behavior.

**Placeholder scan**

- No `TBD`, `TODO`, "similar to", or unspecified test steps remain.
- Every code-changing step includes exact snippets and exact commands.

**Type consistency**

- `AdapterStartConfig` remains the adapter boundary type.
- `RuntimeServiceConfig` remains the Core/GUI runtime type.
- `_SomeipyServiceRuntime.start_config` is `AdapterStartConfig | None`, matching the optional adapter start config.
- RuntimePanel continues to return `RuntimeServiceConfig`, now based on `infer_runtime_config()` plus editable overrides.
