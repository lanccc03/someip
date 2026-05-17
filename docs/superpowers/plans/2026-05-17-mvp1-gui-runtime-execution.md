# MVP-1 GUI Runtime Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing PySide UI execute the already-tested Core `RuntimeSession` operations for start/stop, event publish/subscribe, field get/notify, method call, and visible run log/message trace/problems feedback.

**Architecture:** Keep protocol work behind `RuntimeSession` and `SomeIpAdapter`; the GUI owns selection state, user-entered runtime config, payload JSON text, role-aware button states, and rendering. Production GUI actions run on a persistent `qasync` Qt/asyncio event loop, while tests inject an immediate async runner for deterministic button-click smoke coverage. Start with `MockSomeIpAdapter` in the GUI wiring so the user workflow is deterministic, while preserving an adapter injection point for the real `SomeipyAdapter`.

**Tech Stack:** Python 3.11+, PySide6, qasync, pytest, pytest-qt, existing `RuntimeSession`, existing `PayloadCodec`, existing trace exporters.

---

## Current Baseline

- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest` passes with 139 tests.
- The design doc defines MVP-1 as protocol loop closure before project management and action sequences.
- Core runtime behavior already exists in `src/someip_gui_tool/core/runtime_session.py`.
- The real `SomeipyAdapter` has formal event and field paths; fire-and-forget methods remain explicitly `limited`.
- The current GUI is mostly presentation:
  - `MainWindow` loads service definitions and shows tree nodes.
  - `RuntimePanel` displays inferred config but cannot return edited config.
  - `OperationPanel` changes button labels but does not emit typed actions.
  - Run Log, Message Trace, and Problems tabs exist but are not populated from a session.

## Scope

This plan implements the next working slice: GUI -> Core -> Adapter -> GUI feedback.

Covered here:

- Editable runtime config extraction from `RuntimePanel`.
- Default payload JSON generation for methods, events, and fields.
- Operation panel payload editor and selected-operation button states.
- Main window action wiring to `RuntimeSession` with Client/Server role guards.
- Bottom tab rendering for run log, message trace, and problems.
- Per-service runtime draft preservation while moving between service child nodes.
- GUI smoke tests that click buttons and verify adapter-backed behavior.

Not covered here:

- Full project save/load.
- Recent session restore.
- Simple action sequence editor.
- Complete structured payload form widgets.
- Real peer-device validation in the GUI.
- Switching the GUI default adapter to `SomeipyAdapter`.

## File Structure

- Create: `src/someip_gui_tool/gui/payload_defaults.py` - deterministic JSON-default values for selected parameters.
- Modify: `src/someip_gui_tool/gui/runtime_panel.py` - add `config_for_service()` and strict port parsing for user-edited fields.
- Modify: `src/someip_gui_tool/gui/operation_panel.py` - add payload editor and role-aware selected-operation button states.
- Modify: `src/someip_gui_tool/gui/main_window.py` - own a `RuntimeSession`, inject an async runner, preserve runtime drafts, guard active-service and role-specific operations, and render log/trace/problem tabs.
- Modify: `src/someip_gui_tool/gui/app.py` - install the qasync event loop used by production GUI actions.
- Create: `tests/test_gui_payload_defaults.py`
- Modify: `tests/test_gui_smoke.py`

---

### Task 1: Add Payload Default Helpers

**Files:**
- Create: `src/someip_gui_tool/gui/payload_defaults.py`
- Test: `tests/test_gui_payload_defaults.py`

- [ ] **Step 1: Write payload default tests**

Create `tests/test_gui_payload_defaults.py`:

```python
import json

from someip_gui_tool.gui.payload_defaults import default_payload_values, payload_values_json
from someip_gui_tool.parsing.service_json import load_service_definition


def test_default_payload_values_for_uint8_method(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080D.json")

    values = default_payload_values(service.methods[0].parameters)

    assert values == {"SecondStartCtrlCmd": 0}


def test_default_payload_values_for_struct_event(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    values = default_payload_values(service.events[0].parameters)

    assert values == {"VehicleInfo": {"VehicleSpeed": 0.0, "Odometer": 0.0}}


def test_payload_values_json_is_stable_and_pretty(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    field = service.fields[0]
    assert field.notifier is not None

    text = payload_values_json(field.notifier.parameters)

    assert json.loads(text) == {"VertHeiRmdSts": 0}
    assert text.endswith("\n")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_gui_payload_defaults.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `someip_gui_tool.gui.payload_defaults`.

- [ ] **Step 3: Implement payload defaults**

Create `src/someip_gui_tool/gui/payload_defaults.py`:

```python
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
```

- [ ] **Step 4: Run payload default tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_gui_payload_defaults.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit payload defaults**

Run:

```bash
git add src/someip_gui_tool/gui/payload_defaults.py tests/test_gui_payload_defaults.py
git commit -m "feat: add gui payload defaults"
```

Expected: commit succeeds.

---

### Task 2: Make RuntimePanel Return Edited Config

**Files:**
- Modify: `src/someip_gui_tool/gui/runtime_panel.py`
- Modify: `tests/test_gui_smoke.py`

- [ ] **Step 1: Add GUI test for edited runtime config**

Append to `tests/test_gui_smoke.py`:

```python
def test_runtime_panel_returns_user_edited_config(qtbot, adc40_soc_dir):
    window = MainWindow()
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    service_item = window.service_tree.topLevelItem(0)
    service = service_item.data(0, Qt.ItemDataRole.UserRole)

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.role_combo.setCurrentText(Role.SERVER.value)
    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")

    config = window.runtime_panel.config_for_service(service)

    assert config.role is Role.SERVER
    assert config.service_id == service.service_id
    assert config.instance_id == service.deployment.instance_id
    assert config.server_port == 30500
    assert config.client_port == 30501


def test_runtime_panel_rejects_non_integer_port(qtbot, adc40_soc_dir):
    window = MainWindow()
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    service_item = window.service_tree.topLevelItem(0)
    service = service_item.data(0, Qt.ItemDataRole.UserRole)

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.server_port_edit.setText("abc")
    window.runtime_panel.client_port_edit.setText("30501")

    with pytest.raises(ValueError, match="Server port must be an integer"):
        window.runtime_panel.config_for_service(service)
```

If `pytest` is not already imported in `tests/test_gui_smoke.py`, add:

```python
import pytest
```

- [ ] **Step 2: Run the new test to verify failure**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_gui_smoke.py::test_runtime_panel_returns_user_edited_config \
  tests/test_gui_smoke.py::test_runtime_panel_rejects_non_integer_port \
  -q
```

Expected: FAIL with `AttributeError` for `config_for_service`.

- [ ] **Step 3: Implement config extraction**

Add this import to `src/someip_gui_tool/gui/runtime_panel.py`:

```python
from someip_gui_tool.domain.models import ServiceDefinition
```

Add this method inside `RuntimePanel`:

```python
    def config_for_service(self, service: ServiceDefinition) -> RuntimeServiceConfig:
        return RuntimeServiceConfig(
            service_id=service.service_id,
            instance_id=service.deployment.instance_id,
            role=Role(self.role_combo.currentText()),
            local_ip=self.local_ip_edit.text().strip(),
            remote_ip=self.remote_ip_edit.text().strip(),
            server_port=_optional_port(self.server_port_edit.text(), "Server port"),
            client_port=_optional_port(self.client_port_edit.text(), "Client port"),
            multicast_ip=self.multicast_ip_edit.text().strip(),
        )
```

Add this helper at module level:

```python
def _optional_port(text: str, label: str) -> int | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer: {stripped!r}") from exc
```

- [ ] **Step 4: Run runtime panel test**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_gui_smoke.py::test_runtime_panel_returns_user_edited_config \
  tests/test_gui_smoke.py::test_runtime_panel_rejects_non_integer_port \
  -q
```

Expected: PASS.

- [ ] **Step 5: Commit runtime panel config extraction**

Run:

```bash
git add src/someip_gui_tool/gui/runtime_panel.py tests/test_gui_smoke.py
git commit -m "feat: read runtime config from gui"
```

Expected: commit succeeds.

---

### Task 3: Add OperationPanel Payload Editor and Role-Aware Buttons

**Files:**
- Modify: `src/someip_gui_tool/gui/operation_panel.py`
- Modify: `src/someip_gui_tool/gui/main_window.py`
- Modify: `tests/test_gui_smoke.py`

- [ ] **Step 1: Add GUI tests for payload editor defaults**

Append to `tests/test_gui_smoke.py`:

```python
import json


def test_operation_panel_shows_default_payload_for_client_event(qtbot, adc40_soc_dir):
    window = MainWindow()
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    event_items = window.service_tree.findItems(
        "Event VehicleInfo",
        Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
    )

    window.service_tree.setCurrentItem(event_items[0])

    assert window.operation_panel.primary_button.text() == "Subscribe"
    assert window.operation_panel.secondary_button.text() == "Publish"
    assert window.operation_panel.primary_button.isEnabled()
    assert not window.operation_panel.secondary_button.isEnabled()
    assert json.loads(window.operation_panel.payload_text.toPlainText()) == {
        "VehicleInfo": {"VehicleSpeed": 0.0, "Odometer": 0.0}
    }


def test_operation_panel_enables_publish_for_server_event(qtbot, adc40_soc_dir):
    window = MainWindow()
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    event_items = window.service_tree.findItems(
        "Event VehicleInfo",
        Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
    )
    service_item = event_items[0].parent()

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.role_combo.setCurrentText(Role.SERVER.value)
    window.service_tree.setCurrentItem(event_items[0])

    assert window.operation_panel.primary_button.text() == "Publish"
    assert window.operation_panel.primary_button.isEnabled()
    assert window.operation_panel.secondary_button.text() == "Subscribe"
    assert not window.operation_panel.secondary_button.isEnabled()


def test_operation_panel_uses_field_role_actions(qtbot, adc40_soc_dir):
    window = MainWindow()
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    field_item = window.service_tree.findItems(
        "Field VertHeiRmdSts",
        Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
    )[0]
    service_item = field_item.parent()

    window.service_tree.setCurrentItem(field_item)
    assert window.operation_panel.primary_button.text() == "Get"
    assert window.operation_panel.primary_button.isEnabled()
    assert window.operation_panel.secondary_button.text() == "Notify"
    assert not window.operation_panel.secondary_button.isEnabled()

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.role_combo.setCurrentText(Role.SERVER.value)
    window.service_tree.setCurrentItem(field_item)
    assert window.operation_panel.primary_button.text() == "Notify"
    assert window.operation_panel.primary_button.isEnabled()
    assert window.operation_panel.secondary_button.text() == "Get"
    assert not window.operation_panel.secondary_button.isEnabled()


def test_operation_panel_disables_method_response_configuration(qtbot, adc40_soc_dir):
    window = MainWindow()
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    method_items = window.service_tree.findItems(
        "Method SecondStartCtrl",
        Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
    )

    window.service_tree.setCurrentItem(method_items[0])

    assert window.operation_panel.primary_button.text() == "Call"
    assert window.operation_panel.primary_button.isEnabled()
    assert window.operation_panel.secondary_button.text() == "Configure Response"
    assert not window.operation_panel.secondary_button.isEnabled()

    service_item = method_items[0].parent()
    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.role_combo.setCurrentText(Role.SERVER.value)
    window.service_tree.setCurrentItem(method_items[0])
    assert window.operation_panel.primary_button.text() == "Configure Handler"
    assert not window.operation_panel.primary_button.isEnabled()
    assert window.operation_panel.secondary_button.text() == "Configure Response"
    assert not window.operation_panel.secondary_button.isEnabled()
```

- [ ] **Step 2: Run the operation panel test to verify failure**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_gui_smoke.py::test_operation_panel_shows_default_payload_for_client_event \
  tests/test_gui_smoke.py::test_operation_panel_enables_publish_for_server_event \
  tests/test_gui_smoke.py::test_operation_panel_uses_field_role_actions \
  tests/test_gui_smoke.py::test_operation_panel_disables_method_response_configuration \
  -q
```

Expected: FAIL because `payload_text` and role-aware `OperationPanel` button APIs are not implemented yet.

- [ ] **Step 3: Implement payload editor**

Replace `src/someip_gui_tool/gui/operation_panel.py` with:

```python
from __future__ import annotations

import json

from PySide6.QtWidgets import QGroupBox, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout

from someip_gui_tool.domain.enums import Role
from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldDefinition,
    MethodDefinition,
)
from someip_gui_tool.gui.payload_defaults import payload_values_json


class OperationPanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Operation")
        self.setObjectName("operation_panel")
        self.title_label = QLabel("Select a method, event, or field")
        self.title_label.setObjectName("operation_title")
        self.primary_button = QPushButton("Start")
        self.primary_button.setProperty("primary", True)
        self.secondary_button = QPushButton("Stop")
        self.payload_text = QPlainTextEdit()
        self.payload_text.setObjectName("payload_text")
        self.payload_text.setPlaceholderText("Payload JSON")

        layout = QVBoxLayout(self)
        layout.addWidget(self.title_label)
        layout.addWidget(self.payload_text)
        layout.addWidget(self.primary_button)
        layout.addWidget(self.secondary_button)

    def set_service_actions(self) -> None:
        self.title_label.setText("Select a method, event, or field")
        self.primary_button.setText("Start")
        self.primary_button.setEnabled(True)
        self.secondary_button.setText("Stop")
        self.secondary_button.setEnabled(True)
        self.payload_text.setPlainText("{}\n")

    def payload_values(self) -> dict[str, object]:
        value = json.loads(self.payload_text.toPlainText() or "{}")
        if not isinstance(value, dict):
            raise ValueError("Payload JSON must be an object")
        return value

    def clear_selection(self) -> None:
        self.title_label.setText("Select a method, event, or field")
        self.primary_button.setText("Start")
        self.primary_button.setEnabled(False)
        self.secondary_button.setText("Stop")
        self.secondary_button.setEnabled(False)
        self.payload_text.setPlainText("{}\n")

    def show_method(self, method: MethodDefinition, role: Role) -> None:
        self.title_label.setText(f"Method {method.name} ({method.method_id_hex})")
        if role is Role.CLIENT:
            self.primary_button.setText("Call")
            self.primary_button.setEnabled(True)
        else:
            self.primary_button.setText("Configure Handler")
            self.primary_button.setEnabled(False)
        self.secondary_button.setText("Configure Response")
        self.secondary_button.setEnabled(False)
        self.payload_text.setPlainText(payload_values_json(method.parameters))

    def show_event(self, event: EventDefinition, role: Role) -> None:
        self.title_label.setText(f"Event {event.name} ({event.event_id_hex})")
        if role is Role.CLIENT:
            self.primary_button.setText("Subscribe")
            self.primary_button.setEnabled(True)
            self.secondary_button.setText("Publish")
            self.secondary_button.setEnabled(False)
        else:
            self.primary_button.setText("Publish")
            self.primary_button.setEnabled(True)
            self.secondary_button.setText("Subscribe")
            self.secondary_button.setEnabled(False)
        self.payload_text.setPlainText(payload_values_json(event.parameters))

    def show_field(self, field: FieldDefinition, role: Role) -> None:
        self.title_label.setText(f"Field {field.name}")
        if role is Role.CLIENT:
            self.primary_button.setText("Get")
            self.primary_button.setEnabled(field.getter is not None)
            self.secondary_button.setText("Notify")
            self.secondary_button.setEnabled(False)
        else:
            self.primary_button.setText("Notify")
            self.primary_button.setEnabled(field.notifier is not None)
            self.secondary_button.setText("Get")
            self.secondary_button.setEnabled(False)
        parameters = []
        if role is Role.CLIENT and field.getter is not None:
            parameters = field.getter.parameters
        elif role is Role.SERVER and field.notifier is not None:
            parameters = field.notifier.parameters
        self.payload_text.setPlainText(payload_values_json(parameters))
```

Modify the operation-panel selection block in `src/someip_gui_tool/gui/main_window.py` so it passes the current role:

```python
        role = Role(self.runtime_panel.role_combo.currentText())
        if isinstance(payload, MethodDefinition):
            self.operation_panel.show_method(payload, role)
        elif isinstance(payload, EventDefinition):
            self.operation_panel.show_event(payload, role)
        elif isinstance(payload, FieldDefinition):
            self.operation_panel.show_field(payload, role)
        else:
            self.operation_panel.clear_selection()
```

- [ ] **Step 4: Run operation panel tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_gui_smoke.py::test_operation_panel_shows_default_payload_for_client_event \
  tests/test_gui_smoke.py::test_operation_panel_enables_publish_for_server_event \
  tests/test_gui_smoke.py::test_operation_panel_uses_field_role_actions \
  tests/test_gui_smoke.py::test_operation_panel_disables_method_response_configuration \
  tests/test_gui_payload_defaults.py \
  -q
```

Expected: PASS.

- [ ] **Step 5: Commit operation panel payload editor**

Run:

```bash
git add src/someip_gui_tool/gui/operation_panel.py src/someip_gui_tool/gui/main_window.py tests/test_gui_smoke.py
git commit -m "feat: add role-aware gui operation panel"
```

Expected: commit succeeds.

---

### Task 4: Wire Service Start and Stop from the GUI

**Files:**
- Modify: `src/someip_gui_tool/gui/main_window.py`
- Modify: `src/someip_gui_tool/gui/app.py`
- Modify: `tests/test_gui_smoke.py`

- [ ] **Step 1: Add GUI start/stop test**

Add these imports near the top of `tests/test_gui_smoke.py` if they are not already present:

```python
import asyncio
from collections.abc import Coroutine
from typing import Any

from pytestqt.qtbot import QtBot
```

Add this helper near the existing helper functions in `tests/test_gui_smoke.py`:

```python
def _run_immediate(awaitable: Coroutine[Any, Any, None]) -> None:
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(awaitable)
    finally:
        loop.close()
```

Append to `tests/test_gui_smoke.py`:

```python
def test_main_window_reports_invalid_runtime_config_in_problems(qtbot: QtBot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    service_item = window.service_tree.topLevelItem(0)

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.server_port_edit.setText("abc")
    window.runtime_panel.client_port_edit.setText("30501")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)

    assert "runtime_config_invalid" in window.problems_view.toPlainText()
    assert "Server port must be an integer" in window.problems_view.toPlainText()
    assert "GUI" in window.run_log_view.toPlainText()


def test_main_window_starts_and_stops_selected_service(qtbot: QtBot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    service_item = window.service_tree.topLevelItem(0)

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Started service" in window.run_log_view.toPlainText())

    qtbot.mouseClick(window.operation_panel.secondary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Stopped service" in window.run_log_view.toPlainText())

    assert "Started service" in window.run_log_view.toPlainText()
    assert "Stopped service" in window.run_log_view.toPlainText()


def test_main_window_keeps_runtime_edits_when_selecting_child_item(
    qtbot: QtBot,
    adc40_soc_dir,
):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    service_item = window.service_tree.topLevelItem(0)
    child_item = service_item.child(0)

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")
    window.service_tree.setCurrentItem(child_item)

    assert window.runtime_panel.server_port_edit.text() == "30500"
    assert window.runtime_panel.client_port_edit.text() == "30501"
```

- [ ] **Step 2: Run GUI start/stop test to verify failure**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_gui_smoke.py::test_main_window_reports_invalid_runtime_config_in_problems \
  tests/test_gui_smoke.py::test_main_window_starts_and_stops_selected_service \
  tests/test_gui_smoke.py::test_main_window_keeps_runtime_edits_when_selecting_child_item \
  -q
```

Expected: FAIL because `MainWindow` does not accept `async_runner` and buttons are not connected to runtime actions.

- [ ] **Step 3: Implement injected session and service-node actions**

Add these imports to `src/someip_gui_tool/gui/main_window.py`:

```python
import asyncio
import json
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from typing import Any

from someip_gui_tool.adapters.mock import MockSomeIpAdapter
from someip_gui_tool.core.runtime_config import RuntimeProblem, RuntimeServiceConfig
from someip_gui_tool.core.runtime_session import RuntimeSession
from someip_gui_tool.tracing.exporters import export_run_log_text, export_trace_csv
from someip_gui_tool.tracing.trace_model import RunLogEntry
```

Add this type alias and default async runner near `ITEM_PAYLOAD_ROLE`:

```python
AsyncRunner = Callable[[Coroutine[Any, Any, None]], None]


def schedule_async(awaitable: Coroutine[Any, Any, None]) -> None:
    asyncio.create_task(awaitable)
```

Update the `MainWindow.__init__` signature and initialize the session immediately after `_registry`:

```python
    def __init__(
        self,
        session: RuntimeSession | None = None,
        async_runner: AsyncRunner | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("SOME/IP Test Tool")
        self._registry: ServiceRegistry | None = None
        self.session = session or RuntimeSession(MockSomeIpAdapter())
        self._async_runner = async_runner or schedule_async
        self._running_service_ids: set[int] = set()
        self._runtime_drafts: dict[int, RuntimeServiceConfig] = {}
```

After `self.operation_panel = OperationPanel()`, add:

```python
        self.operation_panel.primary_button.clicked.connect(self._on_primary_action)
        self.operation_panel.secondary_button.clicked.connect(self._on_secondary_action)
```

Replace the existing `_on_current_item_changed`, `_on_runtime_role_changed`, and `_set_runtime_config` methods with:

```python
    def _on_current_item_changed(
        self,
        current: QTreeWidgetItem | None,
        previous: QTreeWidgetItem | None,
    ) -> None:
        previous_service = self._service_for_item(previous) if previous is not None else None
        current_service = self._service_for_item(current) if current is not None else None
        if previous_service is not None:
            self._save_runtime_draft(previous_service)
        if current_service is not None and (
            previous_service is None
            or previous_service.service_id != current_service.service_id
        ):
            self._set_runtime_config(current_service)
        self._refresh_operation_panel(current)

    def _on_runtime_role_changed(self, role_text: str) -> None:
        current = self.service_tree.currentItem()
        if current is None:
            return
        service = self._service_for_item(current)
        if service is not None:
            self._runtime_drafts.pop(service.service_id, None)
            self._set_runtime_config(service)
        self._refresh_operation_panel(current)

    def _set_runtime_config(self, service: ServiceDefinition) -> None:
        draft = self._runtime_drafts.get(service.service_id)
        if draft is not None and draft.role is Role(self.runtime_panel.role_combo.currentText()):
            self.runtime_panel.set_config(draft)
            return
        role = Role(self.runtime_panel.role_combo.currentText())
        self.runtime_panel.set_config(infer_runtime_config(service, role))

    def _save_runtime_draft(self, service: ServiceDefinition) -> None:
        try:
            self._runtime_drafts[service.service_id] = self.runtime_panel.config_for_service(service)
        except ValueError:
            return

    def _refresh_operation_panel(self, item: QTreeWidgetItem | None) -> None:
        if item is None:
            self.operation_panel.clear_selection()
            return
        payload = item.data(0, ITEM_PAYLOAD_ROLE)
        role = Role(self.runtime_panel.role_combo.currentText())
        if isinstance(payload, ServiceDefinition):
            self.operation_panel.set_service_actions()
        elif isinstance(payload, MethodDefinition):
            self.operation_panel.show_method(payload, role)
        elif isinstance(payload, EventDefinition):
            self.operation_panel.show_event(payload, role)
        elif isinstance(payload, FieldDefinition):
            self.operation_panel.show_field(payload, role)
        else:
            self.operation_panel.clear_selection()
```

Add these action methods inside `MainWindow`:

```python
    def _on_primary_action(self) -> None:
        current = self.service_tree.currentItem()
        if current is None:
            return
        payload = current.data(0, ITEM_PAYLOAD_ROLE)
        service = self._service_for_item(current)
        if isinstance(payload, ServiceDefinition):
            self._run_async(self._start_selected_service(payload), payload)
        elif service is not None:
            self._run_async(self._run_primary_element_action(service, payload), service)

    def _on_secondary_action(self) -> None:
        current = self.service_tree.currentItem()
        if current is None:
            return
        payload = current.data(0, ITEM_PAYLOAD_ROLE)
        service = self._service_for_item(current)
        if isinstance(payload, ServiceDefinition):
            self._run_async(self._stop_selected_service(payload), payload)
        elif service is not None:
            self._run_async(self._run_secondary_element_action(service, payload), service)

    def _run_async(
        self,
        awaitable: Coroutine[Any, Any, None],
        service: ServiceDefinition | None = None,
    ) -> None:
        self._async_runner(self._run_and_refresh(awaitable, service))

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

    async def _start_selected_service(self, service: ServiceDefinition) -> None:
        await self.session.start_service(service, self.runtime_panel.config_for_service(service))
        self._running_service_ids.add(service.service_id)

    async def _stop_selected_service(self, service: ServiceDefinition) -> None:
        await self.session.stop_service(service)
        self._running_service_ids.discard(service.service_id)

    def _record_gui_exception(
        self,
        error: Exception,
        service: ServiceDefinition | None,
    ) -> None:
        message = str(error)
        if isinstance(error, json.JSONDecodeError):
            code = "payload_json_invalid"
            message = f"Payload JSON is invalid: {error.msg}"
        elif isinstance(error, ValueError) and "Payload JSON" in message:
            code = "payload_json_invalid"
        elif isinstance(error, ValueError) and "port" in message.lower():
            code = "runtime_config_invalid"
        elif isinstance(error, RuntimeError) and "Start service" in message:
            code = "service_not_started"
        else:
            code = "gui_action_failed"
        self.session.problems.append(
            RuntimeProblem(
                code=code,
                severity="error",
                message=message,
                service_id=0 if service is None else service.service_id,
            )
        )
        self.session.run_log.append(
            RunLogEntry(
                timestamp=datetime.now(timezone.utc),
                level="error",
                source="GUI",
                message=message,
                service_id=None if service is None else service.service_id_hex,
                error_detail=code,
            )
        )
        self.statusBar().showMessage(message)

    def _refresh_runtime_views(self) -> None:
        self.run_log_view.setPlainText(export_run_log_text(self.session.run_log))
        self.message_trace_view.setPlainText(export_trace_csv(self.session.trace))
        self.problems_view.setPlainText(
            "\n".join(f"{problem.severity}: {problem.code}: {problem.message}" for problem in self.session.problems)
        )
```

- [ ] **Step 4: Install qasync event loop in app entry**

Replace `src/someip_gui_tool/gui/app.py` with:

```python
from __future__ import annotations

import asyncio
import sys

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from someip_gui_tool.gui.main_window import MainWindow
from someip_gui_tool.gui.theme import apply_theme


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    window = MainWindow()
    window.show()
    with loop:
        loop.run_forever()
    return 0
```

- [ ] **Step 5: Run GUI start/stop tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_gui_smoke.py::test_main_window_reports_invalid_runtime_config_in_problems \
  tests/test_gui_smoke.py::test_main_window_starts_and_stops_selected_service \
  tests/test_gui_smoke.py::test_main_window_keeps_runtime_edits_when_selecting_child_item \
  -q
```

Expected: PASS.

- [ ] **Step 6: Commit GUI service lifecycle wiring**

Run:

```bash
git add src/someip_gui_tool/gui/main_window.py src/someip_gui_tool/gui/app.py tests/test_gui_smoke.py
git commit -m "feat: wire gui service lifecycle"
```

Expected: commit succeeds.

---

### Task 5: Wire Element Operations and Trace Feedback

**Files:**
- Modify: `src/someip_gui_tool/gui/main_window.py`
- Modify: `tests/test_gui_smoke.py`

- [ ] **Step 1: Add GUI event operation test**

Append to `tests/test_gui_smoke.py`:

```python
def test_main_window_subscribes_event_as_client(qtbot, adc40_soc_dir):
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
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Subscribed eventgroup" in window.run_log_view.toPlainText())

    assert "Subscribed eventgroup" in window.run_log_view.toPlainText()
    assert "publish_event" not in window.message_trace_view.toPlainText()


def test_main_window_publishes_event_as_server(qtbot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    event_item = window.service_tree.findItems(
        "Event VehicleInfo",
        Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
    )[0]
    service_item = event_item.parent()

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.role_combo.setCurrentText(Role.SERVER.value)
    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Started service" in window.run_log_view.toPlainText())

    window.service_tree.setCurrentItem(event_item)
    assert window.operation_panel.primary_button.text() == "Publish"
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "VehicleInfo" in window.message_trace_view.toPlainText())

    assert "Published event VehicleInfo" in window.run_log_view.toPlainText()
    assert "VehicleInfo" in window.message_trace_view.toPlainText()
    assert "raw_payload_hex" in window.message_trace_view.toPlainText()


def test_main_window_reports_element_operation_before_service_start(qtbot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    event_item = window.service_tree.findItems(
        "Event VehicleInfo",
        Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
    )[0]

    window.service_tree.setCurrentItem(event_item)
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)

    assert "service_not_started" in window.problems_view.toPlainText()
    assert "Start service before running Event VehicleInfo" in window.problems_view.toPlainText()


def test_main_window_reports_invalid_payload_json(qtbot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    event_item = window.service_tree.findItems(
        "Event VehicleInfo",
        Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
    )[0]
    service_item = event_item.parent()

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.role_combo.setCurrentText(Role.SERVER.value)
    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)

    window.service_tree.setCurrentItem(event_item)
    window.operation_panel.payload_text.setPlainText("{")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)

    assert "payload_json_invalid" in window.problems_view.toPlainText()
    assert "Payload JSON is invalid" in window.problems_view.toPlainText()
```

- [ ] **Step 2: Add GUI field operation test**

Append to `tests/test_gui_smoke.py`:

```python
def test_main_window_gets_field_as_client(qtbot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    field_item = window.service_tree.findItems(
        "Field VertHeiRmdSts",
        Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
    )[0]
    service_item = field_item.parent()

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Started service" in window.run_log_view.toPlainText())

    window.service_tree.setCurrentItem(field_item)
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "VertHeiRmdSts" in window.message_trace_view.toPlainText())

    assert "Field getter VertHeiRmdSts" in window.run_log_view.toPlainText()
    assert "FieldGetter" in window.message_trace_view.toPlainText()


def test_main_window_notifies_field_as_server(qtbot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    field_item = window.service_tree.findItems(
        "Field VertHeiRmdSts",
        Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
    )[0]
    service_item = field_item.parent()

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.role_combo.setCurrentText(Role.SERVER.value)
    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Started service" in window.run_log_view.toPlainText())

    window.service_tree.setCurrentItem(field_item)
    assert window.operation_panel.primary_button.text() == "Notify"
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "VertHeiRmdSts" in window.message_trace_view.toPlainText())

    assert "Field notifier VertHeiRmdSts" in window.run_log_view.toPlainText()
    assert "FieldNotifier" in window.message_trace_view.toPlainText()


def test_main_window_calls_method_as_client(qtbot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    method_item = window.service_tree.findItems(
        "Method SecondStartCtrl",
        Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
    )[0]
    service_item = method_item.parent()

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Started service" in window.run_log_view.toPlainText())

    window.service_tree.setCurrentItem(method_item)
    assert window.operation_panel.primary_button.text() == "Call"
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Called method SecondStartCtrl" in window.run_log_view.toPlainText())

    assert "Method" in window.message_trace_view.toPlainText()
    assert "limited" in window.message_trace_view.toPlainText()
```

- [ ] **Step 3: Run element operation tests to verify failure**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_gui_smoke.py::test_main_window_subscribes_event_as_client \
  tests/test_gui_smoke.py::test_main_window_publishes_event_as_server \
  tests/test_gui_smoke.py::test_main_window_reports_element_operation_before_service_start \
  tests/test_gui_smoke.py::test_main_window_reports_invalid_payload_json \
  tests/test_gui_smoke.py::test_main_window_gets_field_as_client \
  tests/test_gui_smoke.py::test_main_window_notifies_field_as_server \
  tests/test_gui_smoke.py::test_main_window_calls_method_as_client \
  -q
```

Expected: FAIL because element actions are not wired yet.

- [ ] **Step 4: Implement element action dispatch**

Modify `src/someip_gui_tool/gui/main_window.py`:

```python
    async def _run_primary_element_action(self, service: ServiceDefinition, payload: object) -> None:
        self._require_service_running(service, payload)
        values = self.operation_panel.payload_values()
        role = self._current_role()
        if isinstance(payload, MethodDefinition):
            if role is not Role.CLIENT:
                raise RuntimeError("Method call is only available in Client role.")
            await self.session.call_method(service, payload, values)
        elif isinstance(payload, EventDefinition):
            if role is Role.CLIENT:
                await self.session.register_event_trace(service, payload)
                await self.session.subscribe_event(service, payload)
            else:
                await self.session.publish_event(service, payload, values)
        elif isinstance(payload, FieldDefinition):
            if role is Role.CLIENT:
                await self.session.field_get(service, payload, values)
            else:
                await self.session.field_notify(service, payload, values)

    async def _run_secondary_element_action(self, service: ServiceDefinition, payload: object) -> None:
        self._require_service_running(service, payload)
        raise RuntimeError("Secondary action is disabled for the current MVP-1 GUI slice.")

    def _current_role(self) -> Role:
        return Role(self.runtime_panel.role_combo.currentText())

    def _require_service_running(self, service: ServiceDefinition, payload: object) -> None:
        if service.service_id in self._running_service_ids:
            return
        if isinstance(payload, (MethodDefinition, EventDefinition, FieldDefinition)):
            target = f"{payload.__class__.__name__.replace('Definition', '')} {payload.name}"
        else:
            target = "selected operation"
        raise RuntimeError(f"Start service before running {target}.")
```

- [ ] **Step 5: Run element operation tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_gui_smoke.py::test_main_window_subscribes_event_as_client \
  tests/test_gui_smoke.py::test_main_window_publishes_event_as_server \
  tests/test_gui_smoke.py::test_main_window_reports_element_operation_before_service_start \
  tests/test_gui_smoke.py::test_main_window_reports_invalid_payload_json \
  tests/test_gui_smoke.py::test_main_window_gets_field_as_client \
  tests/test_gui_smoke.py::test_main_window_notifies_field_as_server \
  tests/test_gui_smoke.py::test_main_window_calls_method_as_client \
  -q
```

Expected: PASS.

- [ ] **Step 6: Commit GUI element operations**

Run:

```bash
git add src/someip_gui_tool/gui/main_window.py tests/test_gui_smoke.py
git commit -m "feat: wire gui runtime operations"
```

Expected: commit succeeds.

---

### Task 6: Verify GUI Runtime Slice

**Files:**
- No source changes expected unless verification finds a defect.

- [ ] **Step 1: Run focused GUI tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_gui_smoke.py tests/test_gui_payload_defaults.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest
```

Expected: PASS.

- [ ] **Step 3: Run a manual import smoke**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -c "from pathlib import Path; from PySide6.QtWidgets import QApplication; from someip_gui_tool.gui.main_window import MainWindow; app=QApplication([]); window=MainWindow(); window.load_service_directory(Path('ADC40_SOC')); print(window.service_tree.topLevelItemCount())"
```

Expected: prints a service count greater than or equal to `5`.

- [ ] **Step 4: Check repository status**

Run:

```bash
git status --short
```

Expected: only intentional files are modified, or the working tree is clean after commits.

---

## Follow-Up Plan Candidates

After this plan passes, the next plan should be one of these, in order:

1. `mvp1-project-save-load` - persist runtime overrides, payload defaults, and imported service paths to JSON project files.
2. `mvp1-gui-payload-forms` - replace JSON-only payload editing with structured widgets plus raw hex mode.
3. `mvp1-real-someipy-gui-adapter` - add adapter selection and run the GUI through the formal `SomeipyAdapter` with explicit method limitations.
4. `mvp1-packaging-smoke` - verify Windows x64 packaging with a method/event scenario.

## Self-Review

- Spec coverage: this plan directly advances MVP-1 GUI operation loop closure, trace visibility, runtime config editing, and payload editing. It now covers the review gaps for persistent Qt/asyncio execution, active-service guards before element operations, role-correct Client/Server actions, GUI input errors in Problems/Run Log, disabled method response configuration, and preserving runtime edits while navigating within a service. It intentionally defers project files, recent sessions, action sequences, and full structured forms because those belong to later MVP-2 efficiency work or separate MVP-1 hardening slices.
- Placeholder scan: no unfinished-marker text or unspecified implementation placeholders remain.
- Type consistency: plan uses existing names from current code: `RuntimeSession`, `RuntimeServiceConfig`, `RuntimeProblem`, `RunLogEntry`, `MockSomeIpAdapter`, `MethodDefinition`, `EventDefinition`, `FieldDefinition`, and existing GUI widget names.
