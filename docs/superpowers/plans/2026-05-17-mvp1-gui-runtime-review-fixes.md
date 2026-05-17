# MVP-1 GUI Runtime Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the GUI runtime review findings around running-service config consistency, payload parsing for client subscriptions, and Start/Stop button state.

**Architecture:** Treat a started service as bound to the exact runtime config used at Start. While that service is selected, runtime fields are locked, role-change attempts are reverted to the running config, and service-level Start/Stop buttons reflect running state. Element actions only parse payload JSON for actions that actually send payload bytes.

**Tech Stack:** Python 3.11+, PySide6, qasync, pytest, pytest-qt, existing `RuntimeSession`, existing `MockSomeIpAdapter`.

---

## Review Requirements

- Running service config must stay consistent with GUI action role and trace endpoints.
- Client event Subscribe must not fail because the payload editor contains invalid JSON.
- Service Stop must not be presented as available before Start, and Start must not remain available after a service starts.

## File Structure

- Modify: `src/someip_gui_tool/gui/runtime_panel.py`
  - Add a small method to enable or disable the runtime input widgets as a group.
- Modify: `src/someip_gui_tool/gui/operation_panel.py`
  - Make `set_service_actions()` accept running state so Start/Stop enabled states are accurate.
- Modify: `src/someip_gui_tool/gui/main_window.py`
  - Track the started `RuntimeServiceConfig` per service.
  - Reuse the running config while selected.
  - Revert role changes while a selected service is running.
  - Refresh operation buttons and runtime editability after selection changes and async actions.
  - Parse payload JSON only inside role branches that need payload values.
- Modify: `tests/test_gui_smoke.py`
  - Add GUI smoke regressions for the three review findings.

---

### Task 1: Add Regression Tests for Running-State UI and Config Locking

**Files:**
- Modify: `tests/test_gui_smoke.py`

- [ ] **Step 1: Add tests for service Start/Stop state and running config lock**

Append these tests after `test_main_window_starts_and_stops_selected_service` in `tests/test_gui_smoke.py`:

```python
def test_main_window_service_actions_follow_running_state(qtbot: QtBot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    service_item = window.service_tree.topLevelItem(0)

    window.service_tree.setCurrentItem(service_item)
    assert window.operation_panel.primary_button.text() == "Start"
    assert window.operation_panel.primary_button.isEnabled()
    assert window.operation_panel.secondary_button.text() == "Stop"
    assert not window.operation_panel.secondary_button.isEnabled()

    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Started service" in window.run_log_view.toPlainText())

    assert not window.operation_panel.primary_button.isEnabled()
    assert window.operation_panel.secondary_button.isEnabled()

    qtbot.mouseClick(window.operation_panel.secondary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Stopped service" in window.run_log_view.toPlainText())

    assert window.operation_panel.primary_button.isEnabled()
    assert not window.operation_panel.secondary_button.isEnabled()


def test_main_window_locks_runtime_config_while_service_is_running(
    qtbot: QtBot,
    adc40_soc_dir,
):
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

    assert not window.runtime_panel.role_combo.isEnabled()
    assert not window.runtime_panel.server_port_edit.isEnabled()
    assert not window.runtime_panel.client_port_edit.isEnabled()

    window.runtime_panel.role_combo.setCurrentText(Role.SERVER.value)

    assert window.runtime_panel.role_combo.currentText() == Role.CLIENT.value
    window.service_tree.setCurrentItem(event_item)
    assert window.operation_panel.primary_button.text() == "Subscribe"
```

- [ ] **Step 2: Run the new tests and verify failure**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_gui_smoke.py::test_main_window_service_actions_follow_running_state \
  tests/test_gui_smoke.py::test_main_window_locks_runtime_config_while_service_is_running \
  -q
```

Expected: FAIL. Current code enables Stop before Start, leaves Start enabled after Start, and does not lock or revert runtime role changes while running.

---

### Task 2: Implement Running Config Lock and Accurate Start/Stop State

**Files:**
- Modify: `src/someip_gui_tool/gui/runtime_panel.py`
- Modify: `src/someip_gui_tool/gui/operation_panel.py`
- Modify: `src/someip_gui_tool/gui/main_window.py`
- Test: `tests/test_gui_smoke.py`

- [ ] **Step 1: Add runtime editability helper**

In `src/someip_gui_tool/gui/runtime_panel.py`, add this method at the end of `RuntimePanel`:

```python
    def set_editing_enabled(self, enabled: bool) -> None:
        for widget in (
            self.role_combo,
            self.local_ip_edit,
            self.remote_ip_edit,
            self.server_port_edit,
            self.client_port_edit,
            self.multicast_ip_edit,
        ):
            widget.setEnabled(enabled)
```

- [ ] **Step 2: Make service action buttons state-aware**

In `src/someip_gui_tool/gui/operation_panel.py`, replace `set_service_actions()` with:

```python
    def set_service_actions(self, *, running: bool = False) -> None:
        self.title_label.setText("Select a method, event, or field")
        self.primary_button.setText("Start")
        self.primary_button.setEnabled(not running)
        self.secondary_button.setText("Stop")
        self.secondary_button.setEnabled(running)
        self.payload_text.setPlainText("{}\n")
```

- [ ] **Step 3: Track running configs in MainWindow initialization**

In `src/someip_gui_tool/gui/main_window.py`, replace this initialization:

```python
        self._running_service_ids: set[int] = set()
        self._runtime_drafts: dict[int, RuntimeServiceConfig] = {}
```

with:

```python
        self._running_service_ids: set[int] = set()
        self._running_configs: dict[int, RuntimeServiceConfig] = {}
        self._runtime_drafts: dict[int, RuntimeServiceConfig] = {}
```

- [ ] **Step 4: Refresh selected-state UI after selection changes**

In `src/someip_gui_tool/gui/main_window.py`, replace `_on_current_item_changed()` with:

```python
    def _on_current_item_changed(
        self,
        current: QTreeWidgetItem | None,
        previous: QTreeWidgetItem | None,
    ) -> None:
        previous_service = self._service_for_item(previous) if previous is not None else None
        current_service = self._service_for_item(current) if current is not None else None
        if previous_service is not None and previous_service.service_id not in self._running_service_ids:
            self._save_runtime_draft(previous_service)
        if current_service is not None and (
            previous_service is None
            or previous_service.service_id != current_service.service_id
        ):
            self._set_runtime_config(current_service)
        self._refresh_selected_state()
```

- [ ] **Step 5: Revert role changes while running**

In `src/someip_gui_tool/gui/main_window.py`, replace `_on_runtime_role_changed()` with:

```python
    def _on_runtime_role_changed(self, role_text: str) -> None:
        current = self.service_tree.currentItem()
        if current is None:
            return
        service = self._service_for_item(current)
        if service is not None:
            running_config = self._running_configs.get(service.service_id)
            if running_config is not None:
                if Role(role_text) is not running_config.role:
                    self.runtime_panel.set_config(running_config)
                self._refresh_selected_state()
                return
            self._runtime_drafts.pop(service.service_id, None)
            self._set_runtime_config(service)
        self._refresh_selected_state()
```

- [ ] **Step 6: Prefer running config when selected**

In `src/someip_gui_tool/gui/main_window.py`, replace `_set_runtime_config()` with:

```python
    def _set_runtime_config(self, service: ServiceDefinition) -> None:
        running_config = self._running_configs.get(service.service_id)
        if running_config is not None:
            self.runtime_panel.set_config(running_config)
            return
        draft = self._runtime_drafts.get(service.service_id)
        if draft is not None and draft.role is Role(self.runtime_panel.role_combo.currentText()):
            self.runtime_panel.set_config(draft)
            return
        role = Role(self.runtime_panel.role_combo.currentText())
        self.runtime_panel.set_config(infer_runtime_config(service, role))
```

- [ ] **Step 7: Make operation-panel refresh use service running state**

In `src/someip_gui_tool/gui/main_window.py`, replace `_refresh_operation_panel()` with:

```python
    def _refresh_operation_panel(self, item: QTreeWidgetItem | None) -> None:
        if item is None:
            self.operation_panel.clear_selection()
            return
        payload = item.data(0, ITEM_PAYLOAD_ROLE)
        service = self._service_for_item(item)
        role = Role(self.runtime_panel.role_combo.currentText())
        if isinstance(payload, ServiceDefinition):
            self.operation_panel.set_service_actions(
                running=payload.service_id in self._running_service_ids
            )
        elif isinstance(payload, MethodDefinition):
            self.operation_panel.show_method(payload, role)
        elif isinstance(payload, EventDefinition):
            self.operation_panel.show_event(payload, role)
        elif isinstance(payload, FieldDefinition):
            self.operation_panel.show_field(payload, role)
        else:
            self.operation_panel.clear_selection()
        self.runtime_panel.set_editing_enabled(
            service is None or service.service_id not in self._running_service_ids
        )
```

- [ ] **Step 8: Add selected-state refresh helper**

In `src/someip_gui_tool/gui/main_window.py`, add this helper after `_refresh_runtime_views()`:

```python
    def _refresh_selected_state(self) -> None:
        current = self.service_tree.currentItem()
        if current is None:
            self.runtime_panel.set_editing_enabled(True)
            self.operation_panel.clear_selection()
            return
        service = self._service_for_item(current)
        if service is not None and service.service_id in self._running_service_ids:
            self.runtime_panel.set_config(self._running_configs[service.service_id])
        self._refresh_operation_panel(current)
```

- [ ] **Step 9: Refresh selected-state UI after async actions**

In `src/someip_gui_tool/gui/main_window.py`, replace `_run_and_refresh()` with:

```python
    async def _run_and_refresh(
        self,
        awaitable: Coroutine[Any, Any, None],
        service: ServiceDefinition | None,
    ) -> None:
        try:
            await awaitable
        except Exception as exc:
            self._record_gui_exception(exc, service)
        finally:
            self._refresh_runtime_views()
            self._refresh_selected_state()
```

- [ ] **Step 10: Store and clear running configs at Start/Stop**

In `src/someip_gui_tool/gui/main_window.py`, replace `_start_selected_service()` and `_stop_selected_service()` with:

```python
    async def _start_selected_service(self, service: ServiceDefinition) -> None:
        config = self.runtime_panel.config_for_service(service)
        await self.session.start_service(service, config)
        self._running_service_ids.add(service.service_id)
        self._running_configs[service.service_id] = config

    async def _stop_selected_service(self, service: ServiceDefinition) -> None:
        self._require_service_running(service, service)
        await self.session.stop_service(service)
        self._running_service_ids.discard(service.service_id)
        self._running_configs.pop(service.service_id, None)
```

- [ ] **Step 11: Require matching running role for element actions**

In `src/someip_gui_tool/gui/main_window.py`, replace `_require_service_running()` with:

```python
    def _require_service_running(self, service: ServiceDefinition, payload: object) -> None:
        running_config = self._running_configs.get(service.service_id)
        if running_config is not None:
            current_role = self._current_role()
            if running_config.role is not current_role:
                raise RuntimeError(
                    f"Service {service.service_name} is running as {running_config.role.value}; "
                    f"stop it before switching to {current_role.value}."
                )
            return
        if isinstance(payload, (MethodDefinition, EventDefinition, FieldDefinition)):
            target = f"{payload.__class__.__name__.replace('Definition', '')} {payload.name}"
        elif isinstance(payload, ServiceDefinition):
            target = f"service {payload.service_name}"
        else:
            target = "selected operation"
        raise RuntimeError(f"Start service before running {target}.")
```

- [ ] **Step 12: Run focused tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_gui_smoke.py::test_main_window_service_actions_follow_running_state \
  tests/test_gui_smoke.py::test_main_window_locks_runtime_config_while_service_is_running \
  tests/test_gui_smoke.py::test_main_window_starts_and_stops_selected_service \
  -q
```

Expected: PASS.

- [ ] **Step 13: Commit running-state fixes**

Run:

```bash
git add src/someip_gui_tool/gui/runtime_panel.py src/someip_gui_tool/gui/operation_panel.py src/someip_gui_tool/gui/main_window.py tests/test_gui_smoke.py
git commit -m "fix: lock gui runtime config while service runs"
```

Expected: commit succeeds.

---

### Task 3: Avoid Payload Parsing for Client Event Subscribe

**Files:**
- Modify: `tests/test_gui_smoke.py`
- Modify: `src/someip_gui_tool/gui/main_window.py`

- [ ] **Step 1: Add client subscribe invalid-payload regression**

Append this test after `test_main_window_subscribes_event_as_client` in `tests/test_gui_smoke.py`:

```python
def test_main_window_subscribe_ignores_payload_editor_json(qtbot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    event_item = window.service_tree.findItems(
        "Event VehicleInfo",
        Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
    )[0]
    service_item = event_item.parent()

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Started service" in window.run_log_view.toPlainText())

    window.service_tree.setCurrentItem(event_item)
    window.operation_panel.payload_text.setPlainText("{")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Subscribed eventgroup" in window.run_log_view.toPlainText())

    assert "Subscribed eventgroup" in window.run_log_view.toPlainText()
    assert "payload_json_invalid" not in window.problems_view.toPlainText()
```

- [ ] **Step 2: Run the new test and verify failure**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_gui_smoke.py::test_main_window_subscribe_ignores_payload_editor_json \
  -q
```

Expected: FAIL. Current code parses `operation_panel.payload_values()` before checking whether the selected Client event action is Subscribe.

- [ ] **Step 3: Move payload parsing into payload-using branches**

In `src/someip_gui_tool/gui/main_window.py`, replace `_run_primary_element_action()` with:

```python
    async def _run_primary_element_action(self, service: ServiceDefinition, payload: object) -> None:
        self._require_service_running(service, payload)
        role = self._current_role()
        if isinstance(payload, MethodDefinition):
            if role is not Role.CLIENT:
                raise RuntimeError("Method call is only available in Client role.")
            values = self.operation_panel.payload_values()
            await self.session.call_method(service, payload, values)
        elif isinstance(payload, EventDefinition):
            if role is Role.CLIENT:
                await self.session.register_event_trace(service, payload)
                await self.session.subscribe_event(service, payload)
            else:
                values = self.operation_panel.payload_values()
                await self.session.publish_event(service, payload, values)
        elif isinstance(payload, FieldDefinition):
            values = self.operation_panel.payload_values()
            if role is Role.CLIENT:
                await self.session.field_get(service, payload, values)
            else:
                await self.session.field_notify(service, payload, values)
```

- [ ] **Step 4: Run focused payload tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_gui_smoke.py::test_main_window_subscribe_ignores_payload_editor_json \
  tests/test_gui_smoke.py::test_main_window_reports_invalid_payload_json \
  tests/test_gui_smoke.py::test_main_window_publishes_event_as_server \
  -q
```

Expected: PASS. Client Subscribe ignores invalid payload JSON, while Server Publish still reports invalid payload JSON.

- [ ] **Step 5: Commit payload parsing fix**

Run:

```bash
git add src/someip_gui_tool/gui/main_window.py tests/test_gui_smoke.py
git commit -m "fix: skip payload parsing for gui event subscribe"
```

Expected: commit succeeds.

---

### Task 4: Full Verification

**Files:**
- No code changes.

- [ ] **Step 1: Run full test suite**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest
```

Expected: PASS with all tests passing.

- [ ] **Step 2: Inspect diff**

Run:

```bash
git diff --stat HEAD~2..HEAD
git diff --check HEAD~2..HEAD
```

Expected: modified GUI and GUI smoke test files only; `git diff --check` prints no whitespace errors.

- [ ] **Step 3: Manual smoke path**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_gui_smoke.py -q
```

Expected: PASS. This validates the GUI runtime flow without launching the visible app.

## Self-Review

- Spec coverage: The plan covers all three review findings: role/config mismatch while running, unnecessary payload parsing for Subscribe, and incorrect Stop availability before Start.
- Placeholder scan: No `TBD`, `TODO`, or generic "add tests" placeholders remain.
- Type consistency: New code uses existing `RuntimeServiceConfig`, `Role`, `ServiceDefinition`, `MethodDefinition`, `EventDefinition`, `FieldDefinition`, and existing `MainWindow` helper style.

