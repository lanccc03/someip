# MVP-1 Remaining Loop Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining MVP-1 GUI/runtime loop closure so the tool can be used as a Windows PySide manual SOME/IP test application with visible runtime state, supported event/field operations, trace export, environment validation, and repeatable acceptance checks.

**Architecture:** Keep GUI access routed through `RuntimeSession`; GUI must not call `someipy` or the mock adapter directly. Add small, focused runtime services for cycle tasks and environment validation behind Core boundaries, while preserving the adapter interface as the protocol boundary. MVP-2 features such as project save/load, structured forms, raw hex mode, service filtering, recent sessions, and action sequences remain out of scope for this plan.

**Tech Stack:** Python 3.11+, PySide6, qasync, pytest, pytest-asyncio, pytest-qt, PyInstaller, existing `someip_gui_tool` package.

---

## Scope Boundary

This plan closes MVP-1 items that are already partially implemented but not yet product-complete:

- Service runtime state and role visible in the service tree.
- Event subscribe, unsubscribe, publish once, start cycle, and stop cycle from the GUI.
- Field getter/notifier flow stays supported; field setter and RR method paths remain explicitly gated until fixtures/backend support exist.
- Backend capability status is visible when an operation is limited or unsupported.
- Runtime environment validation covers local IP mismatch and occupied ports when enabled by the app.
- Run log and message trace can be exported from the GUI.
- Packaged app smoke and real `someipy` loopback acceptance are repeatable.

Explicitly deferred to MVP-2:

- Service tree search and filters.
- Structured payload forms.
- Raw hex payload mode.
- Project save/load.
- Recent session recovery.
- Simple action sequences.

---

## File Structure

- Modify: `src/someip_gui_tool/gui/operation_panel.py`
  - Add action-specific status text and a third action button for event cycle stop.
  - Keep JSON payload editor as the MVP-1 payload input.
- Modify: `src/someip_gui_tool/gui/main_window.py`
  - Track service tree items, refresh role/state labels, route new event actions, and add export menu actions.
- Modify: `src/someip_gui_tool/core/runtime_session.py`
  - Add event unsubscribe, cycle publish management, cycle cleanup on stop, and optional environment validation.
- Modify: `src/someip_gui_tool/core/runtime_config.py`
  - Accept optional environment probe results when validating runtime config.
- Create: `src/someip_gui_tool/core/runtime_environment.py`
  - Provide local IP and port availability checks using stdlib networking.
- Modify: `src/someip_gui_tool/gui/backend_factory.py`
  - Enable environment validation for sessions created by the app.
- Modify: `src/someip_gui_tool/gui/app.py`
  - Add `--smoke-exit` support for packaged GUI smoke tests.
- Create: `scripts/run_mvp1_acceptance.py`
  - Run unit tests, protocol dry-run, optional real loopback, and optional PyInstaller smoke.
- Modify: `packaging/pyinstaller/someip-gui-tool.spec`
  - Include hidden imports or datas discovered by smoke testing.
- Test: `tests/test_runtime_session.py`
  - Runtime event unsubscribe, cycle publish, cleanup, and validation tests.
- Test: `tests/test_runtime_config.py`
  - Environment validation unit tests.
- Test: `tests/test_gui_smoke.py`
  - GUI state, event action, export, and smoke-exit coverage.
- Test: `tests/test_gui_backend_factory.py`
  - App-created sessions enable environment validation.
- Test: `tests/test_mvp1_acceptance_script.py`
  - Acceptance script command construction and failure propagation.

---

### Task 1: Show Service Role and Runtime State in the Service Tree

**Files:**
- Modify: `src/someip_gui_tool/gui/main_window.py`
- Test: `tests/test_gui_smoke.py`

- [ ] **Step 1: Write the failing service tree state test**

Append this test to `tests/test_gui_smoke.py`:

```python
def test_main_window_service_tree_shows_role_and_state(qtbot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    service_item = window.service_tree.topLevelItem(0)

    window.service_tree.setCurrentItem(service_item)

    assert "Role: Client" in service_item.text(0)
    assert "State: Stopped" in service_item.text(0)

    window.runtime_panel.role_combo.setCurrentText(Role.SERVER.value)

    assert "Role: Server" in service_item.text(0)
    assert "State: Stopped" in service_item.text(0)
```

- [ ] **Step 2: Write the failing start/stop state label test**

Append this test to `tests/test_gui_smoke.py`:

```python
def test_main_window_service_tree_state_changes_on_start_and_stop(qtbot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    service_item = window.service_tree.topLevelItem(0)

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")

    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Started service" in window.run_log_view.toPlainText())

    assert "State: Running" in service_item.text(0)

    qtbot.mouseClick(window.operation_panel.secondary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Stopped service" in window.run_log_view.toPlainText())

    assert "State: Stopped" in service_item.text(0)
```

- [ ] **Step 3: Run the new GUI tests to verify they fail**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest `
  tests/test_gui_smoke.py::test_main_window_service_tree_shows_role_and_state `
  tests/test_gui_smoke.py::test_main_window_service_tree_state_changes_on_start_and_stop -q
```

Expected: FAIL because service tree labels do not show role/state.

- [ ] **Step 4: Track service tree items by service id**

In `src/someip_gui_tool/gui/main_window.py`, add this initialization in `MainWindow.__init__` near `_running_configs`:

```python
        self._service_items: dict[int, QTreeWidgetItem] = {}
```

In `load_service_directory()`, clear that mapping before adding items:

```python
        self._service_items.clear()
```

In `_service_item()`, store the created item:

```python
        self._service_items[service.service_id] = service_item
        self._refresh_service_item_label(service)
```

- [ ] **Step 5: Add service label helpers**

Add these methods to `MainWindow`:

```python
    def _refresh_service_item_label(self, service: ServiceDefinition) -> None:
        item = self._service_items.get(service.service_id)
        if item is None:
            return
        role = self._display_role_for_service(service)
        state = "Running" if service.service_id in self._running_service_ids else "Stopped"
        item.setText(
            0,
            (
                f"{service.service_name} ({service.service_id_hex}) "
                f"[Role: {role.value}; State: {state}]"
            ),
        )

    def _refresh_all_service_item_labels(self) -> None:
        if self._registry is None:
            return
        for service in self._registry.services:
            self._refresh_service_item_label(service)

    def _display_role_for_service(self, service: ServiceDefinition) -> Role:
        running_config = self._running_configs.get(service.service_id)
        if running_config is not None:
            return running_config.role
        draft = self._runtime_drafts.get(service.service_id)
        if draft is not None:
            return draft.role
        current = self.service_tree.currentItem()
        if current is not None and self._service_for_item(current) is service:
            return Role(self.runtime_panel.role_combo.currentText())
        return Role.CLIENT
```

- [ ] **Step 6: Refresh labels after selection, role changes, start, and stop**

In `_on_current_item_changed()`, call this before `_refresh_selected_state()`:

```python
        self._refresh_all_service_item_labels()
```

In `_on_runtime_role_changed()`, call this before `_refresh_selected_state()`:

```python
        self._refresh_all_service_item_labels()
```

In `_start_selected_service()`, add after updating `_running_configs`:

```python
        self._refresh_service_item_label(service)
```

In `_stop_selected_service()`, add after removing `_running_configs`:

```python
        self._refresh_service_item_label(service)
```

- [ ] **Step 7: Run GUI state tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest `
  tests/test_gui_smoke.py::test_main_window_service_tree_shows_role_and_state `
  tests/test_gui_smoke.py::test_main_window_service_tree_state_changes_on_start_and_stop -q
```

Expected: PASS.

- [ ] **Step 8: Commit service state visibility**

Run:

```powershell
git add src/someip_gui_tool/gui/main_window.py tests/test_gui_smoke.py
git commit -m "feat: show service runtime state in tree"
```

Expected: commit succeeds.

---

### Task 2: Add Event Unsubscribe and Cycle Publish Runtime Support

**Files:**
- Modify: `src/someip_gui_tool/core/runtime_session.py`
- Test: `tests/test_runtime_session.py`

- [ ] **Step 1: Write the failing event unsubscribe test**

Append this test to `tests/test_runtime_session.py`:

```python
@pytest.mark.asyncio
async def test_runtime_session_unsubscribes_event(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)

    await session.start_service(service, _valid_config(service, Role.CLIENT))
    await session.subscribe_event(service, event)
    await session.unsubscribe_event(service, event)

    assert [call.name for call in adapter.calls][-2:] == [
        "subscribe_eventgroup",
        "unsubscribe_eventgroup",
    ]
    assert session.run_log[-1].message == (
        f"Unsubscribed eventgroup 0x{event.eventgroup_id:04X} for {event.name}"
    )
```

- [ ] **Step 2: Write failing cycle publish tests**

Append these tests to `tests/test_runtime_session.py`:

```python
@pytest.mark.asyncio
async def test_runtime_session_cycle_event_publishes_until_stopped(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)
    values = {"VehicleInfo": {"VehicleSpeed": 12.5, "Odometer": 99.25}}

    await session.start_service(service, _valid_config(service, Role.SERVER))
    await session.start_cycle_event(service, event, values, cycle_time_s=0.01)
    await asyncio.sleep(0.035)
    await session.stop_cycle_event(service, event)
    publish_count_after_stop = sum(call.name == "publish_event" for call in adapter.calls)
    await asyncio.sleep(0.025)

    assert publish_count_after_stop >= 2
    assert sum(call.name == "publish_event" for call in adapter.calls) == publish_count_after_stop
    assert any("Started cycle event VehicleInfo" in entry.message for entry in session.run_log)
    assert session.run_log[-1].message == "Stopped cycle event VehicleInfo"


@pytest.mark.asyncio
async def test_runtime_session_stop_service_cancels_cycle_events(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]
    adapter = MockSomeIpAdapter()
    session = RuntimeSession(adapter=adapter)
    values = {"VehicleInfo": {"VehicleSpeed": 12.5, "Odometer": 99.25}}

    await session.start_service(service, _valid_config(service, Role.SERVER))
    await session.start_cycle_event(service, event, values, cycle_time_s=0.01)
    await asyncio.sleep(0.025)
    await session.stop_service(service)
    publish_count_after_stop = sum(call.name == "publish_event" for call in adapter.calls)
    await asyncio.sleep(0.025)

    assert sum(call.name == "publish_event" for call in adapter.calls) == publish_count_after_stop
```

- [ ] **Step 3: Run runtime tests to verify they fail**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest `
  tests/test_runtime_session.py::test_runtime_session_unsubscribes_event `
  tests/test_runtime_session.py::test_runtime_session_cycle_event_publishes_until_stopped `
  tests/test_runtime_session.py::test_runtime_session_stop_service_cancels_cycle_events -q
```

Expected: FAIL because `unsubscribe_event`, `start_cycle_event`, and `stop_cycle_event` do not exist.

- [ ] **Step 4: Add cycle task storage**

In `RuntimeSession.__init__`, add:

```python
        self._cycle_tasks: dict[tuple[int, int], asyncio.Task[None]] = {}
```

Add `import asyncio` at the top of `runtime_session.py`.

- [ ] **Step 5: Implement event unsubscribe**

Add this method to `RuntimeSession` after `subscribe_event()`:

```python
    async def unsubscribe_event(self, service: ServiceDefinition, event: EventDefinition) -> None:
        if event.eventgroup_id is None:
            raise ValueError(f"Event {event.name!r} has no eventgroup id")
        try:
            await self.adapter.unsubscribe_eventgroup(service, event.eventgroup_id)
        except Exception as exc:
            self._record_adapter_exception(
                "unsubscribe_event_adapter_exception",
                service,
                f"Adapter failed to unsubscribe event {event.name}",
                exc,
                element_id=event.event_id_hex,
            )
            raise
        self._log(
            "info",
            "Core",
            f"Unsubscribed eventgroup 0x{event.eventgroup_id:04X} for {event.name}",
            service_id=service.service_id_hex,
            element_id=event.event_id_hex,
        )
```

- [ ] **Step 6: Implement cycle publish controls**

Add these methods to `RuntimeSession` after `publish_event()`:

```python
    async def start_cycle_event(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        values: dict[str, Any],
        *,
        cycle_time_s: float | None = None,
    ) -> None:
        interval = cycle_time_s if cycle_time_s is not None else event.cycle_time_s
        if interval is None or interval <= 0:
            raise ValueError(f"Event {event.name!r} has no positive cycle time")
        key = (service.service_id, event.event_id)
        if key in self._cycle_tasks:
            return

        async def run_cycle() -> None:
            try:
                while True:
                    await self.publish_event(service, event, values)
                    await asyncio.sleep(interval)
            except asyncio.CancelledError:
                raise

        self._cycle_tasks[key] = asyncio.create_task(run_cycle())
        self._log(
            "info",
            "Core",
            f"Started cycle event {event.name}",
            service_id=service.service_id_hex,
            element_id=event.event_id_hex,
        )

    async def stop_cycle_event(self, service: ServiceDefinition, event: EventDefinition) -> None:
        key = (service.service_id, event.event_id)
        task = self._cycle_tasks.pop(key, None)
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        self._log(
            "info",
            "Core",
            f"Stopped cycle event {event.name}",
            service_id=service.service_id_hex,
            element_id=event.event_id_hex,
        )
```

- [ ] **Step 7: Cancel cycle tasks on service stop**

At the beginning of `stop_service()`, before `adapter.stop_service()`, add:

```python
        for event in service.events:
            await self.stop_cycle_event(service, event)
```

- [ ] **Step 8: Run the runtime event tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest `
  tests/test_runtime_session.py::test_runtime_session_unsubscribes_event `
  tests/test_runtime_session.py::test_runtime_session_cycle_event_publishes_until_stopped `
  tests/test_runtime_session.py::test_runtime_session_stop_service_cancels_cycle_events -q
```

Expected: PASS.

- [ ] **Step 9: Run existing runtime session coverage**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests/test_runtime_session.py tests/test_mock_adapter.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit runtime event controls**

Run:

```powershell
git add src/someip_gui_tool/core/runtime_session.py tests/test_runtime_session.py
git commit -m "feat: add event unsubscribe and cycle runtime"
```

Expected: commit succeeds.

---

### Task 3: Expose Event Unsubscribe and Cycle Publish in the GUI

**Files:**
- Modify: `src/someip_gui_tool/gui/operation_panel.py`
- Modify: `src/someip_gui_tool/gui/main_window.py`
- Test: `tests/test_gui_smoke.py`

- [ ] **Step 1: Write failing GUI event action tests**

Append these tests to `tests/test_gui_smoke.py`:

```python
def test_main_window_unsubscribes_event_as_client(qtbot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    service_item = window.service_tree.topLevelItem(0)
    event_item = service_item.child(0)

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.role_combo.setCurrentText(Role.CLIENT.value)
    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Started service" in window.run_log_view.toPlainText())

    window.service_tree.setCurrentItem(event_item)
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Subscribed eventgroup" in window.run_log_view.toPlainText())
    qtbot.mouseClick(window.operation_panel.secondary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Unsubscribed eventgroup" in window.run_log_view.toPlainText())

    assert "Unsubscribed eventgroup" in window.run_log_view.toPlainText()


def test_main_window_starts_and_stops_cycle_event_as_server(qtbot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    service_item = None
    event_item = None
    for index in range(window.service_tree.topLevelItemCount()):
        candidate = window.service_tree.topLevelItem(index)
        if "0x080E" in candidate.text(0):
            service_item = candidate
            event_item = candidate.child(0)
            break
    assert service_item is not None
    assert event_item is not None

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.role_combo.setCurrentText(Role.SERVER.value)
    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Started service" in window.run_log_view.toPlainText())

    window.service_tree.setCurrentItem(event_item)
    assert window.operation_panel.primary_button.text() == "Publish Once"
    assert window.operation_panel.secondary_button.text() == "Start Cycle"
    assert window.operation_panel.tertiary_button.text() == "Stop Cycle"
    qtbot.mouseClick(window.operation_panel.secondary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Started cycle event VehicleInfo" in window.run_log_view.toPlainText())
    qtbot.mouseClick(window.operation_panel.tertiary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Stopped cycle event VehicleInfo" in window.run_log_view.toPlainText())
```

- [ ] **Step 2: Run GUI event tests to verify they fail**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest `
  tests/test_gui_smoke.py::test_main_window_unsubscribes_event_as_client `
  tests/test_gui_smoke.py::test_main_window_starts_and_stops_cycle_event_as_server -q
```

Expected: FAIL because the GUI has no event unsubscribe or cycle buttons.

- [ ] **Step 3: Add a third operation button**

In `OperationPanel.__init__`, add after `secondary_button`:

```python
        self.tertiary_button = QPushButton("Stop Cycle")
```

Add it to the layout after `secondary_button`:

```python
        layout.addWidget(self.tertiary_button)
```

In `clear_selection()` and `set_service_actions()`, disable it:

```python
        self.tertiary_button.setText("Stop Cycle")
        self.tertiary_button.setEnabled(False)
```

- [ ] **Step 4: Update event button labels**

Replace `OperationPanel.show_event()` with:

```python
    def show_event(self, event: EventDefinition, role: Role) -> None:
        self.title_label.setText(f"Event {event.name} ({event.event_id_hex})")
        if role is Role.CLIENT:
            self.primary_button.setText("Subscribe")
            self.primary_button.setEnabled(True)
            self.secondary_button.setText("Unsubscribe")
            self.secondary_button.setEnabled(True)
            self.tertiary_button.setText("Stop Cycle")
            self.tertiary_button.setEnabled(False)
        else:
            self.primary_button.setText("Publish Once")
            self.primary_button.setEnabled(True)
            self.secondary_button.setText("Start Cycle")
            self.secondary_button.setEnabled(event.cycle_time_s is not None)
            self.tertiary_button.setText("Stop Cycle")
            self.tertiary_button.setEnabled(event.cycle_time_s is not None)
        self.payload_text.setPlainText(payload_values_json(event.parameters))
```

- [ ] **Step 5: Connect the third button**

In `MainWindow.__init__`, add:

```python
        self.operation_panel.tertiary_button.clicked.connect(self._on_tertiary_action)
```

Add this method after `_on_secondary_action()`:

```python
    def _on_tertiary_action(self) -> None:
        current = self.service_tree.currentItem()
        if current is None:
            return
        payload = current.data(0, ITEM_PAYLOAD_ROLE)
        service = self._service_for_item(current)
        if service is not None:
            self._run_async(self._run_tertiary_element_action(service, payload), service)
```

- [ ] **Step 6: Route secondary and tertiary element actions**

Replace `_run_secondary_element_action()` with:

```python
    async def _run_secondary_element_action(self, service: ServiceDefinition, payload: object) -> None:
        self._require_service_running(service, payload)
        role = self._current_role()
        if isinstance(payload, EventDefinition):
            if role is Role.CLIENT:
                await self.session.unsubscribe_event(service, payload)
                return
            values = self.operation_panel.payload_values()
            await self.session.start_cycle_event(service, payload, values)
            return
        raise RuntimeError("Secondary action is disabled for the current MVP-1 GUI slice.")
```

Add this method:

```python
    async def _run_tertiary_element_action(self, service: ServiceDefinition, payload: object) -> None:
        self._require_service_running(service, payload)
        role = self._current_role()
        if isinstance(payload, EventDefinition) and role is Role.SERVER:
            await self.session.stop_cycle_event(service, payload)
            return
        raise RuntimeError("Tertiary action is disabled for the current MVP-1 GUI slice.")
```

- [ ] **Step 7: Update primary server event action to use publish once label only**

No behavior change is needed in `_run_primary_element_action()`. Verify this branch remains:

```python
        elif isinstance(payload, EventDefinition):
            if role is Role.CLIENT:
                await self.session.register_event_trace(service, payload)
                await self.session.subscribe_event(service, payload)
            else:
                values = self.operation_panel.payload_values()
                await self.session.publish_event(service, payload, values)
```

- [ ] **Step 8: Run GUI event action tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest `
  tests/test_gui_smoke.py::test_main_window_unsubscribes_event_as_client `
  tests/test_gui_smoke.py::test_main_window_starts_and_stops_cycle_event_as_server -q
```

Expected: PASS.

- [ ] **Step 9: Run GUI smoke tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests/test_gui_smoke.py tests/test_gui_payload_defaults.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit GUI event controls**

Run:

```powershell
git add src/someip_gui_tool/gui/operation_panel.py src/someip_gui_tool/gui/main_window.py tests/test_gui_smoke.py
git commit -m "feat: expose event unsubscribe and cycle actions"
```

Expected: commit succeeds.

---

### Task 4: Surface Backend Capability Gates in the Operation Panel

**Files:**
- Modify: `src/someip_gui_tool/gui/operation_panel.py`
- Modify: `src/someip_gui_tool/gui/main_window.py`
- Test: `tests/test_gui_smoke.py`

- [ ] **Step 1: Write failing capability message tests**

Append these tests to `tests/test_gui_smoke.py`:

```python
def test_operation_panel_marks_ff_methods_limited(qtbot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    method_item = None
    for service_index in range(window.service_tree.topLevelItemCount()):
        service_item = window.service_tree.topLevelItem(service_index)
        for child_index in range(service_item.childCount()):
            child = service_item.child(child_index)
            if "SecondStartCtrl" in child.text(0):
                method_item = child
                break
        if method_item is not None:
            break
    assert method_item is not None

    window.service_tree.setCurrentItem(method_item)

    assert "fire-and-forget" in window.operation_panel.status_label.text().lower()
    assert "limited" in window.operation_panel.status_label.text().lower()


def test_operation_panel_marks_field_setter_gated(qtbot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    field_item = None
    for service_index in range(window.service_tree.topLevelItemCount()):
        service_item = window.service_tree.topLevelItem(service_index)
        for child_index in range(service_item.childCount()):
            child = service_item.child(child_index)
            if "VertHeiRmdSts" in child.text(0):
                field_item = child
                break
        if field_item is not None:
            break
    assert field_item is not None

    window.service_tree.setCurrentItem(field_item)

    assert "setter unavailable" in window.operation_panel.status_label.text().lower()
```

- [ ] **Step 2: Run capability tests to verify they fail**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest `
  tests/test_gui_smoke.py::test_operation_panel_marks_ff_methods_limited `
  tests/test_gui_smoke.py::test_operation_panel_marks_field_setter_gated -q
```

Expected: FAIL because `status_label` does not exist.

- [ ] **Step 3: Add operation status label**

In `OperationPanel.__init__`, add after `title_label`:

```python
        self.status_label = QLabel("")
        self.status_label.setObjectName("operation_status")
        self.status_label.setWordWrap(True)
```

Add it to the layout after `title_label`:

```python
        layout.addWidget(self.status_label)
```

In `clear_selection()` and `set_service_actions()`, clear it:

```python
        self.status_label.setText("")
```

- [ ] **Step 4: Set method capability status text**

In `OperationPanel.show_method()`, after setting `title_label`, add:

```python
        if method.rr_ff == "FF":
            self.status_label.setText(
                "Backend status: fire-and-forget method execution is limited; "
                "adapter reports availability but cannot prove an end-to-end FF response."
            )
        elif method.rr_ff == "RR":
            self.status_label.setText(
                "Backend status: RR method execution is gated until a proven fixture "
                "and adapter request/response path are available."
            )
        else:
            self.status_label.setText("")
```

- [ ] **Step 5: Set event and field capability status text**

In `OperationPanel.show_event()`, after `title_label`, add:

```python
        if event.cycle_time_s is None:
            self.status_label.setText("Backend status: trigger event supports manual publish.")
        else:
            self.status_label.setText(
                f"Backend status: cycle event supports manual publish and cycle publish every {event.cycle_time_s:g}s."
            )
```

In `OperationPanel.show_field()`, after `title_label`, add:

```python
        messages = []
        if field.getter is not None:
            messages.append("getter supported")
        if field.notifier is not None:
            messages.append("notifier supported")
        if field.setter is None:
            messages.append("setter unavailable")
        else:
            messages.append("setter gated until a supported backend path exists")
        self.status_label.setText("Backend status: " + ", ".join(messages) + ".")
```

- [ ] **Step 6: Run capability tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest `
  tests/test_gui_smoke.py::test_operation_panel_marks_ff_methods_limited `
  tests/test_gui_smoke.py::test_operation_panel_marks_field_setter_gated -q
```

Expected: PASS.

- [ ] **Step 7: Commit capability messages**

Run:

```powershell
git add src/someip_gui_tool/gui/operation_panel.py tests/test_gui_smoke.py
git commit -m "feat: show backend capability gates in gui"
```

Expected: commit succeeds.

---

### Task 5: Add Runtime Environment Validation for App-Created Sessions

**Files:**
- Create: `src/someip_gui_tool/core/runtime_environment.py`
- Modify: `src/someip_gui_tool/core/runtime_config.py`
- Modify: `src/someip_gui_tool/core/runtime_session.py`
- Modify: `src/someip_gui_tool/gui/backend_factory.py`
- Test: `tests/test_runtime_config.py`
- Test: `tests/test_runtime_session.py`
- Test: `tests/test_gui_backend_factory.py`

- [ ] **Step 1: Write failing runtime config environment tests**

Append this helper and tests to `tests/test_runtime_config.py`:

```python
class FakeEnvironmentProbe:
    def __init__(self, *, local_ips=None, occupied_ports=None):
        self._local_ips = set(local_ips or [])
        self._occupied_ports = set(occupied_ports or set())

    def local_ip_addresses(self) -> set[str]:
        return set(self._local_ips)

    def is_port_available(self, ip_address: str, port: int) -> bool:
        return (ip_address, port) not in self._occupied_ports


def test_validate_runtime_config_rejects_local_ip_not_on_adapter(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    config = replace(
        infer_runtime_config(service, Role.CLIENT),
        local_ip="172.16.3.15",
        server_port=30500,
        client_port=30501,
    )

    problems = validate_runtime_config(
        service,
        config,
        environment=FakeEnvironmentProbe(local_ips={"127.0.0.1"}),
    )

    assert any(problem.code == "local_ip_not_on_adapter" for problem in problems)


def test_validate_runtime_config_rejects_occupied_ports(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    config = replace(
        infer_runtime_config(service, Role.CLIENT),
        local_ip="127.0.0.1",
        server_port=30500,
        client_port=30501,
    )

    problems = validate_runtime_config(
        service,
        config,
        environment=FakeEnvironmentProbe(
            local_ips={"127.0.0.1"},
            occupied_ports={("127.0.0.1", 30501)},
        ),
    )

    assert any(problem.code == "client_port_occupied" for problem in problems)
```

Add this import at the top of `tests/test_runtime_config.py`:

```python
from dataclasses import replace
```

- [ ] **Step 2: Write failing session environment propagation test**

Append this test to `tests/test_runtime_session.py`:

```python
@pytest.mark.asyncio
async def test_runtime_session_uses_environment_validation(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    config = _valid_config(service, Role.CLIENT)
    environment = FakeEnvironmentProbe(local_ips={"127.0.0.1"})
    session = RuntimeSession(adapter=MockSomeIpAdapter(), environment=environment)

    with pytest.raises(ValueError, match="local_ip_not_on_adapter"):
        await session.start_service(service, config)

    assert session.problems[-1].code == "local_ip_not_on_adapter"
```

If `FakeEnvironmentProbe` is local to `tests/test_runtime_config.py`, duplicate the same simple fake class in `tests/test_runtime_session.py`.

- [ ] **Step 3: Run validation tests to verify they fail**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest `
  tests/test_runtime_config.py::test_validate_runtime_config_rejects_local_ip_not_on_adapter `
  tests/test_runtime_config.py::test_validate_runtime_config_rejects_occupied_ports `
  tests/test_runtime_session.py::test_runtime_session_uses_environment_validation -q
```

Expected: FAIL because environment validation is not implemented.

- [ ] **Step 4: Add runtime environment probe**

Create `src/someip_gui_tool/core/runtime_environment.py`:

```python
from __future__ import annotations

import socket
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeEnvironmentProbe:
    def local_ip_addresses(self) -> set[str]:
        addresses = {"127.0.0.1", "::1"}
        try:
            hostname = socket.gethostname()
            for family, _, _, _, sockaddr in socket.getaddrinfo(hostname, None):
                if family in {socket.AF_INET, socket.AF_INET6}:
                    addresses.add(str(sockaddr[0]))
        except OSError:
            pass
        return addresses

    def is_port_available(self, ip_address: str, port: int) -> bool:
        host = ip_address.split("/", 1)[0]
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, port))
            except OSError:
                return False
        return True
```

- [ ] **Step 5: Extend runtime config validation signature**

In `runtime_config.py`, add this import:

```python
from typing import Protocol
```

Add this protocol above `RuntimeProblem`:

```python
class RuntimeEnvironment(Protocol):
    def local_ip_addresses(self) -> set[str]:
        ...

    def is_port_available(self, ip_address: str, port: int) -> bool:
        ...
```

Change `validate_runtime_config()` signature:

```python
def validate_runtime_config(
    service: ServiceDefinition,
    config: RuntimeServiceConfig,
    *,
    environment: RuntimeEnvironment | None = None,
) -> list[RuntimeProblem]:
```

- [ ] **Step 6: Add environment checks after syntax checks**

Near the end of `validate_runtime_config()`, before `return problems`, add:

```python
    has_error = any(problem.severity == "error" for problem in problems)
    if environment is not None and not has_error:
        local_host = config.local_ip.split("/", 1)[0]
        local_ips = environment.local_ip_addresses()
        if local_host not in local_ips:
            problems.append(
                RuntimeProblem(
                    code="local_ip_not_on_adapter",
                    severity="error",
                    message=f"Local IP {local_host!r} was not found on local network adapters.",
                    service_id=service.service_id,
                )
            )
        if config.server_port is not None and not environment.is_port_available(local_host, config.server_port):
            problems.append(
                RuntimeProblem(
                    code="server_port_occupied",
                    severity="error",
                    message=f"Server port {config.server_port} is already occupied on {local_host}.",
                    service_id=service.service_id,
                )
            )
        if config.client_port is not None and not environment.is_port_available(local_host, config.client_port):
            problems.append(
                RuntimeProblem(
                    code="client_port_occupied",
                    severity="error",
                    message=f"Client port {config.client_port} is already occupied on {local_host}.",
                    service_id=service.service_id,
                )
            )
```

- [ ] **Step 7: Wire environment through RuntimeSession**

In `RuntimeSession.__init__`, change the signature:

```python
    def __init__(
        self,
        adapter: SomeIpAdapter,
        codec: PayloadCodec | None = None,
        environment: Any | None = None,
    ) -> None:
```

Add:

```python
        self.environment = environment
```

In `start_service()`, replace:

```python
        problems = validate_runtime_config(service, config)
```

with:

```python
        problems = validate_runtime_config(service, config, environment=self.environment)
```

- [ ] **Step 8: Enable environment validation for app-created sessions**

In `gui/backend_factory.py`, add:

```python
from someip_gui_tool.core.runtime_environment import RuntimeEnvironmentProbe
```

In `create_session()`, instantiate once:

```python
    environment = RuntimeEnvironmentProbe()
```

Return sessions like this:

```python
        return RuntimeSession(MockSomeIpAdapter(), environment=environment)
```

and:

```python
        return RuntimeSession(
            SomeipyAdapter(
                local_ip=resolved.local_ip,
                base_port=resolved.base_port,
                start_daemon=resolved.start_daemon,
            ),
            environment=environment,
        )
```

- [ ] **Step 9: Add backend factory coverage**

Append this test to `tests/test_gui_backend_factory.py`:

```python
def test_create_session_enables_environment_validation() -> None:
    session = create_session(BackendSettings(backend="mock"))

    assert session.environment is not None
```

- [ ] **Step 10: Run validation and factory tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest `
  tests/test_runtime_config.py `
  tests/test_runtime_session.py::test_runtime_session_uses_environment_validation `
  tests/test_gui_backend_factory.py -q
```

Expected: PASS.

- [ ] **Step 11: Commit runtime environment validation**

Run:

```powershell
git add src/someip_gui_tool/core/runtime_environment.py src/someip_gui_tool/core/runtime_config.py src/someip_gui_tool/core/runtime_session.py src/someip_gui_tool/gui/backend_factory.py tests/test_runtime_config.py tests/test_runtime_session.py tests/test_gui_backend_factory.py
git commit -m "feat: validate runtime environment before start"
```

Expected: commit succeeds.

---

### Task 6: Add GUI Trace and Run Log Export Actions

**Files:**
- Modify: `src/someip_gui_tool/gui/main_window.py`
- Test: `tests/test_gui_smoke.py`

- [ ] **Step 1: Write failing GUI export test**

Append this test to `tests/test_gui_smoke.py`:

```python
def test_main_window_exports_trace_and_run_log(qtbot, adc40_soc_dir, tmp_path):
    exports = [
        tmp_path / "trace.csv",
        tmp_path / "trace.json",
        tmp_path / "run-log.txt",
        tmp_path / "run-log.json",
    ]

    def save_file_dialog(parent, title, suggested_name, file_filter):
        return exports.pop(0)

    window = MainWindow(
        async_runner=_run_immediate,
        save_file_dialog=save_file_dialog,
    )
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    service_item = window.service_tree.topLevelItem(0)
    event_item = service_item.child(0)

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Started service" in window.run_log_view.toPlainText())
    window.service_tree.setCurrentItem(event_item)
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Subscribed eventgroup" in window.run_log_view.toPlainText())

    window.export_trace_csv_action.trigger()
    window.export_trace_json_action.trigger()
    window.export_run_log_text_action.trigger()
    window.export_run_log_json_action.trigger()

    assert (tmp_path / "trace.csv").read_text(encoding="utf-8").startswith("timestamp,direction")
    assert "element_name" in (tmp_path / "trace.json").read_text(encoding="utf-8")
    assert "Started service" in (tmp_path / "run-log.txt").read_text(encoding="utf-8")
    assert "Started service" in (tmp_path / "run-log.json").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run export test to verify it fails**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests/test_gui_smoke.py::test_main_window_exports_trace_and_run_log -q
```

Expected: FAIL because save/export actions do not exist.

- [ ] **Step 3: Add save file dialog type and default implementation**

In `main_window.py`, add this type near `DefinitionDirectoryDialog`:

```python
SaveFileDialog = Callable[[QWidget, str, str, str], Path | None]
```

Add this function near `choose_definition_directory()`:

```python
def choose_save_file(parent: QWidget, title: str, suggested_name: str, file_filter: str) -> Path | None:
    filename, _ = QFileDialog.getSaveFileName(parent, title, suggested_name, file_filter)
    if not filename:
        return None
    return Path(filename)
```

Change `MainWindow.__init__` signature:

```python
        save_file_dialog: SaveFileDialog | None = None,
```

Store it:

```python
        self._save_file_dialog = save_file_dialog or choose_save_file
```

- [ ] **Step 4: Import all exporters**

Change the exporter import in `main_window.py` to:

```python
from someip_gui_tool.tracing.exporters import (
    export_run_log_json,
    export_run_log_text,
    export_trace_csv,
    export_trace_json,
)
```

- [ ] **Step 5: Add export menu actions**

In `_create_menus()`, after the open action, add:

```python
        file_menu.addSeparator()
        self.export_trace_csv_action = QAction("Export Message Trace CSV...", self)
        self.export_trace_json_action = QAction("Export Message Trace JSON...", self)
        self.export_run_log_text_action = QAction("Export Run Log TXT...", self)
        self.export_run_log_json_action = QAction("Export Run Log JSON...", self)

        self.export_trace_csv_action.triggered.connect(self.export_trace_csv)
        self.export_trace_json_action.triggered.connect(self.export_trace_json)
        self.export_run_log_text_action.triggered.connect(self.export_run_log_text)
        self.export_run_log_json_action.triggered.connect(self.export_run_log_json)

        file_menu.addAction(self.export_trace_csv_action)
        file_menu.addAction(self.export_trace_json_action)
        file_menu.addAction(self.export_run_log_text_action)
        file_menu.addAction(self.export_run_log_json_action)
```

- [ ] **Step 6: Add export methods**

Add these methods to `MainWindow`:

```python
    def export_trace_csv(self) -> None:
        self._export_text(
            "Export Message Trace CSV",
            "message-trace.csv",
            "CSV Files (*.csv)",
            export_trace_csv(self.session.trace),
        )

    def export_trace_json(self) -> None:
        self._export_text(
            "Export Message Trace JSON",
            "message-trace.json",
            "JSON Files (*.json)",
            export_trace_json(self.session.trace),
        )

    def export_run_log_text(self) -> None:
        self._export_text(
            "Export Run Log TXT",
            "run-log.txt",
            "Text Files (*.txt)",
            export_run_log_text(self.session.run_log),
        )

    def export_run_log_json(self) -> None:
        self._export_text(
            "Export Run Log JSON",
            "run-log.json",
            "JSON Files (*.json)",
            export_run_log_json(self.session.run_log),
        )

    def _export_text(
        self,
        title: str,
        suggested_name: str,
        file_filter: str,
        content: str,
    ) -> None:
        path = self._save_file_dialog(self, title, suggested_name, file_filter)
        if path is None:
            return
        path.write_text(content, encoding="utf-8")
        message = f"Exported {title} to {path}"
        self.session.run_log.append(
            RunLogEntry(
                timestamp=datetime.now(timezone.utc),
                level="info",
                source="GUI",
                message=message,
            )
        )
        self.statusBar().showMessage(message)
        self._refresh_runtime_views()
```

- [ ] **Step 7: Run GUI export test**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests/test_gui_smoke.py::test_main_window_exports_trace_and_run_log -q
```

Expected: PASS.

- [ ] **Step 8: Commit GUI export actions**

Run:

```powershell
git add src/someip_gui_tool/gui/main_window.py tests/test_gui_smoke.py
git commit -m "feat: add gui trace export actions"
```

Expected: commit succeeds.

---

### Task 7: Add Packaged GUI Smoke Exit and MVP-1 Acceptance Runner

**Files:**
- Modify: `src/someip_gui_tool/gui/app.py`
- Create: `scripts/run_mvp1_acceptance.py`
- Create: `tests/test_mvp1_acceptance_script.py`
- Test: `tests/test_gui_app.py`

- [ ] **Step 1: Write failing app smoke-exit test**

Append this test to `tests/test_gui_app.py`:

```python
def test_main_supports_smoke_exit(monkeypatch) -> None:
    shutdowns: list[str] = []
    quits: list[str] = []

    class FakeAdapter:
        async def shutdown(self) -> None:
            shutdowns.append("shutdown")

    class FakeApp:
        def __init__(self, argv) -> None:
            self.argv = argv

        def quit(self) -> None:
            quits.append("quit")

    class FakeLoop:
        def __init__(self, app) -> None:
            self.app = app

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def run_forever(self) -> None:
            return None

        def run_until_complete(self, awaitable) -> None:
            _drive_immediate_coroutine(awaitable)

    class FakeTimer:
        @staticmethod
        def singleShot(delay_ms, callback) -> None:
            assert delay_ms == 0
            callback()

    class FakeWindow:
        def __init__(self, *, session) -> None:
            self.session = session

        def show(self) -> None:
            return None

    fake_session = SimpleNamespace(adapter=FakeAdapter())

    monkeypatch.setattr(app_module, "QApplication", FakeApp)
    monkeypatch.setattr(app_module, "QEventLoop", FakeLoop)
    monkeypatch.setattr(app_module, "QTimer", FakeTimer)
    monkeypatch.setattr(app_module, "MainWindow", FakeWindow)
    monkeypatch.setattr(app_module, "apply_theme", lambda app: None)
    monkeypatch.setattr(app_module, "create_session", lambda: fake_session)
    monkeypatch.setattr(app_module.asyncio, "set_event_loop", lambda loop: None)

    assert app_module.main(["someip-gui-tool", "--smoke-exit"]) == 0
    assert quits == ["quit"]
    assert shutdowns == ["shutdown"]
```

- [ ] **Step 2: Run app smoke-exit test to verify it fails**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests/test_gui_app.py::test_main_supports_smoke_exit -q
```

Expected: FAIL because `main()` does not accept argv and `QTimer` is not imported.

- [ ] **Step 3: Implement smoke-exit**

In `src/someip_gui_tool/gui/app.py`, import `QTimer`:

```python
from PySide6.QtCore import QTimer
```

Change `main()` signature and argv handling:

```python
def main(argv: list[str] | None = None) -> int:
    resolved_argv = sys.argv if argv is None else argv
    smoke_exit = "--smoke-exit" in resolved_argv
    qt_argv = [arg for arg in resolved_argv if arg != "--smoke-exit"]
    app = QApplication(qt_argv)
```

Before entering `with loop:`, add:

```python
    if smoke_exit:
        QTimer.singleShot(0, app.quit)
```

Keep shutdown after `loop.run_forever()`:

```python
    with loop:
        loop.run_forever()
        try:
            loop.run_until_complete(session.adapter.shutdown())
        except Exception:
            import traceback

            traceback.print_exc()
```

- [ ] **Step 4: Write failing acceptance script test**

Create `tests/test_mvp1_acceptance_script.py`:

```python
from __future__ import annotations

from pathlib import Path

import scripts.run_mvp1_acceptance as acceptance


def test_acceptance_runner_runs_required_default_commands(monkeypatch, tmp_path):
    calls: list[list[str]] = []

    def fake_run(command, cwd, check):
        calls.append(list(command))
        assert cwd == Path.cwd()
        assert check is True

    monkeypatch.setattr(acceptance.subprocess, "run", fake_run)

    assert acceptance.main(["--skip-real", "--skip-package"]) == 0

    assert calls[0][-3:] == ["-m", "pytest", "-q"]
    assert calls[1][-2:] == ["--mode", "dry-run"]
    assert all("pyinstaller" not in call for command in calls for call in command)


def test_acceptance_runner_can_include_real_and_package(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(command, cwd, check):
        calls.append(list(command))

    monkeypatch.setattr(acceptance.subprocess, "run", fake_run)

    assert acceptance.main([]) == 0

    assert any("--start-daemon" in command for command in calls)
    assert any("pyinstaller" in command for command in calls)
    assert any("--smoke-exit" in command for command in calls)
```

- [ ] **Step 5: Create MVP-1 acceptance runner**

Create `scripts/run_mvp1_acceptance.py`:

```python
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MVP-1 acceptance checks.")
    parser.add_argument("--skip-real", action="store_true", help="Skip real someipy loopback.")
    parser.add_argument("--skip-package", action="store_true", help="Skip PyInstaller package smoke.")
    args = parser.parse_args(argv)

    python = sys.executable
    commands = [
        [python, "-m", "pytest", "-q"],
        [python, "scripts/run_protocol_spike.py", "--mode", "dry-run"],
    ]
    if not args.skip_real:
        commands.append(
            [
                python,
                "scripts/run_protocol_spike.py",
                "--mode",
                "real",
                "--start-daemon",
            ]
        )
    if not args.skip_package:
        commands.extend(
            [
                [python, "-m", "PyInstaller", "packaging/pyinstaller/someip-gui-tool.spec"],
                [str(REPO_ROOT / "dist" / "someip-gui-tool.exe"), "--smoke-exit"],
            ]
        )

    for command in commands:
        subprocess.run(command, cwd=REPO_ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run app and acceptance script tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests/test_gui_app.py tests/test_mvp1_acceptance_script.py -q
```

Expected: PASS.

- [ ] **Step 7: Run acceptance script without real/package by default during development**

Run:

```powershell
.\.venv\Scripts\python scripts/run_mvp1_acceptance.py --skip-real --skip-package
```

Expected: unit tests pass and protocol dry-run passes.

- [ ] **Step 8: Run real loopback acceptance on a machine with `someipy` and `someipyd` available**

Run:

```powershell
.\.venv\Scripts\python scripts/run_mvp1_acceptance.py --skip-package
```

Expected:

- `pytest -q` passes.
- protocol dry-run passes.
- real protocol spike starts `someipyd`.
- FF method scenarios are SKIP/limited.
- UDP event, TCP event, and field getter/notifier scenarios pass.

- [ ] **Step 9: Run package smoke**

Run:

```powershell
.\.venv\Scripts\python scripts/run_mvp1_acceptance.py --skip-real
```

Expected:

- PyInstaller build succeeds.
- `dist\someip-gui-tool.exe --smoke-exit` exits with code 0.

- [ ] **Step 10: Commit acceptance runner**

Run:

```powershell
git add src/someip_gui_tool/gui/app.py scripts/run_mvp1_acceptance.py tests/test_gui_app.py tests/test_mvp1_acceptance_script.py
git commit -m "chore: add mvp1 acceptance runner"
```

Expected: commit succeeds.

---

### Task 8: Final MVP-1 Verification and Known Limits

**Files:**
- Modify: `docs/superpowers/specs/2026-05-13-someip-gui-test-tool-design.md`
- Create: `docs/mvp1-known-limits.md`

- [ ] **Step 1: Create known limits document**

Create `docs/mvp1-known-limits.md`:

```markdown
# MVP-1 Known Limits

## Backend

- `someipy` is the first backend, but all GUI/runtime calls still go through `SomeIpAdapter`.
- Fire-and-forget method paths report `limited` because the current backend can prove availability but cannot prove end-to-end FF handling.
- RR method execution is gated until a proven fixture and adapter request/response path exist.
- Field setter execution is gated until a supported JSON fixture and adapter path exist.

## GUI

- Payload input is JSON text in MVP-1.
- Structured payload forms are MVP-2.
- Raw hex mode is MVP-2.
- Search, filtering, project files, recent sessions, and action sequences are MVP-2.

## Network

- VLAN and firewall rules are not automatically configured.
- Runtime validation reports local IP and occupied port issues, but target-machine firewall/VLAN readiness still requires manual verification.

## Packaging

- PyInstaller package smoke verifies app startup and shutdown.
- Real SOME/IP loopback is verified by `scripts/run_protocol_spike.py --mode real --start-daemon`.
```

- [ ] **Step 2: Add spec status note**

Append this section to `docs/superpowers/specs/2026-05-13-someip-gui-test-tool-design.md`:

```markdown
## 11. Implementation Status Notes

MVP-1 accepts the current `someipy` backend capability gates:

- FF method paths may report `limited`.
- RR methods remain gated.
- Field setter remains gated.
- Event subscribe/unsubscribe, event publish/cycle publish, field getter, and field notifier are the supported GUI runtime paths.

See `docs/mvp1-known-limits.md` for the current release boundary.
```

- [ ] **Step 3: Run full verification**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python scripts/run_protocol_spike.py --mode dry-run
.\.venv\Scripts\python scripts/run_protocol_spike.py --mode real --start-daemon
.\.venv\Scripts\python scripts/run_mvp1_acceptance.py --skip-real
```

Expected:

- pytest passes.
- protocol dry-run passes.
- real loopback passes supported scenarios and skips FF method scenarios as limited.
- package smoke exits with code 0.

- [ ] **Step 4: Commit MVP-1 status documentation**

Run:

```powershell
git add docs/mvp1-known-limits.md docs/superpowers/specs/2026-05-13-someip-gui-test-tool-design.md
git commit -m "docs: document mvp1 release limits"
```

Expected: commit succeeds.

---

## Self-Review

Spec coverage:

- MVP-1 GUI startup, directory import, parsing, role config, ports, start/stop: covered by existing code plus Task 1 state visibility.
- Event subscription/publish and field getter/notifier: covered by existing code plus Task 2 and Task 3 for unsubscribe/cycle GUI controls.
- Method execution status and backend gates: covered by existing capability reports plus Task 4 GUI visibility.
- Message trace and exports: covered by existing trace model/exporters plus Task 6 GUI export actions.
- Runtime validation: covered by existing required fields plus Task 5 environment checks.
- Packaged Windows app and real backend scenario: covered by Task 7 acceptance runner and smoke exit.

Intentional gaps:

- Structured payload forms, raw hex mode, project save/load, recent session, service tree search/filtering, and action sequences are MVP-2.
- Long-running stability, reconnect visibility, trace memory control, and full network hardening are MVP-3.

Placeholder scan:

- This plan contains no placeholder markers or generic "write tests" steps.
- Each task includes concrete tests, expected failures, implementation snippets, commands, and commit messages.

Type consistency:

- New GUI constructor parameter `save_file_dialog` matches the test call and `SaveFileDialog` alias.
- New `RuntimeSession` constructor parameter is named `environment` in tests and implementation.
- New event methods are consistently named `unsubscribe_event`, `start_cycle_event`, and `stop_cycle_event`.
- New operation button is consistently named `tertiary_button`.
