# MVP-1 GUI Definition Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the missing user-facing GUI entry point for opening a SOME/IP service definition directory and loading its JSON files into the service tree.

**Architecture:** Reuse the existing `MainWindow.load_service_directory()` path so parsing and registry behavior stay centralized. Add only a thin PySide action/dialog layer in `MainWindow`, with a dialog-provider injection point for deterministic GUI tests. Import success and failure are rendered through the existing details, status bar, Run Log, and Problems surfaces.

**Tech Stack:** Python 3.11+, PySide6, pytest, pytest-qt, existing `ServiceRegistry`, existing `RuntimeSession` log/problem models.

---

## Current Baseline

- `MainWindow.load_service_directory(directory)` already loads a directory and populates the service tree.
- Tests call `load_service_directory()` directly; the running app has no menu action, toolbar button, or file dialog for a user to choose `ADC40_SOC`.
- `MainWindow` already has Run Log, Message Trace, and Problems views, plus `_refresh_runtime_views()` and `_record_gui_exception()` helpers.
- The app entry point currently creates `MainWindow()` and shows it without loading definitions.

## Scope

Covered here:

- Add a File menu action named `Open Definition Directory...`.
- Open a native directory chooser using `QFileDialog.getExistingDirectory()`.
- Keep the action testable through a `definition_directory_dialog` dependency injected into `MainWindow`.
- Load the selected directory through the existing `load_service_directory()` method.
- Record successful imports in Run Log and the status/details area.
- Record import failures in Problems and Run Log without crashing the GUI.

Out of scope:

- Project save/load.
- Recent session restoration.
- Automatic default loading of `ADC40_SOC`.
- Search/filter UI.
- Structured payload forms and raw hex mode.

## File Structure

- Modify: `src/someip_gui_tool/gui/main_window.py`
  - Add the menu action, directory dialog helper, import action handler, success logging, and import failure reporting.
- Modify: `tests/test_gui_smoke.py`
  - Add GUI smoke coverage for the action, successful import, cancelled import, and failed import.

---

### Task 1: Add User-Facing Definition Directory Action

**Files:**
- Modify: `src/someip_gui_tool/gui/main_window.py`
- Modify: `tests/test_gui_smoke.py`

- [ ] **Step 1: Write failing GUI tests for the menu action and successful import**

Append these tests near the existing service-loading GUI tests in `tests/test_gui_smoke.py`:

```python
def test_main_window_exposes_open_definition_directory_action(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.open_definition_directory_action.objectName() == "open_definition_directory_action"
    assert window.open_definition_directory_action.text() == "Open Definition Directory..."

    file_menus = [
        action.menu()
        for action in window.menuBar().actions()
        if action.menu() is not None and action.text() == "&File"
    ]
    assert len(file_menus) == 1
    assert "Open Definition Directory..." in [
        action.text() for action in file_menus[0].actions()
    ]


def test_main_window_opens_definition_directory_from_action(qtbot, adc40_soc_dir):
    selected_directories = []

    def choose_directory(parent):
        selected_directories.append(parent)
        return adc40_soc_dir

    window = MainWindow(definition_directory_dialog=choose_directory)
    qtbot.addWidget(window)

    window.open_definition_directory_action.trigger()

    assert selected_directories == [window]
    assert window.service_tree.topLevelItemCount() >= 5
    assert "Loaded" in window.details.toPlainText()
    assert str(adc40_soc_dir) in window.details.toPlainText()
    assert "Loaded" in window.run_log_view.toPlainText()
```

- [ ] **Step 2: Run the new tests to verify failure**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_gui_smoke.py::test_main_window_exposes_open_definition_directory_action \
  tests/test_gui_smoke.py::test_main_window_opens_definition_directory_from_action \
  -q
```

Expected: FAIL with `AttributeError` because `MainWindow` has no `open_definition_directory_action` and does not accept `definition_directory_dialog`.

- [ ] **Step 3: Add dialog helper, constructor injection, and File menu action**

In `src/someip_gui_tool/gui/main_window.py`, add these imports:

```python
from PySide6.QtGui import QAction
```

Extend the existing `PySide6.QtWidgets` import block to include `QFileDialog`:

```python
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QPlainTextEdit,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
```

Add this type alias and helper below the existing `AsyncRunner` alias:

```python
DefinitionDirectoryDialog = Callable[[QWidget], Path | None]


def choose_definition_directory(parent: QWidget) -> Path | None:
    directory = QFileDialog.getExistingDirectory(
        parent,
        "Open Service Definition Directory",
    )
    if not directory:
        return None
    return Path(directory)
```

Update `MainWindow.__init__()` signature:

```python
    def __init__(
        self,
        session: RuntimeSession | None = None,
        async_runner: AsyncRunner | None = None,
        definition_directory_dialog: DefinitionDirectoryDialog | None = None,
    ) -> None:
```

After `_async_runner` is assigned in `__init__()`, add:

```python
        self._definition_directory_dialog = (
            definition_directory_dialog or choose_definition_directory
        )
```

After the status bar is initialized at the end of `__init__()`, call the menu builder:

```python
        self._create_menus()
```

Add this method inside `MainWindow`:

```python
    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        self.open_definition_directory_action = QAction(
            "Open Definition Directory...",
            self,
        )
        self.open_definition_directory_action.setObjectName(
            "open_definition_directory_action"
        )
        self.open_definition_directory_action.triggered.connect(
            self.open_definition_directory
        )
        file_menu.addAction(self.open_definition_directory_action)
```

- [ ] **Step 4: Add the action handler and success log**

Add this method inside `MainWindow`:

```python
    def open_definition_directory(self) -> None:
        directory = self._definition_directory_dialog(self)
        if directory is None:
            return
        self.load_service_directory(directory)
```

In `MainWindow.load_service_directory()`, after this existing line:

```python
        self.statusBar().showMessage(message)
```

add:

```python
        self.session.run_log.append(
            RunLogEntry(
                timestamp=datetime.now(timezone.utc),
                level="info",
                source="GUI",
                message=message,
            )
        )
        self._refresh_runtime_views()
```

- [ ] **Step 5: Run the action/import tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_gui_smoke.py::test_main_window_exposes_open_definition_directory_action \
  tests/test_gui_smoke.py::test_main_window_opens_definition_directory_from_action \
  -q
```

Expected: PASS.

- [ ] **Step 6: Commit the menu import entry point**

Run:

```bash
git add src/someip_gui_tool/gui/main_window.py tests/test_gui_smoke.py
git commit -m "feat: add gui definition import action"
```

Expected: commit succeeds.

---

### Task 2: Handle Cancelled and Failed Definition Imports

**Files:**
- Modify: `src/someip_gui_tool/gui/main_window.py`
- Modify: `tests/test_gui_smoke.py`

- [ ] **Step 1: Write failing GUI tests for cancelled and failed imports**

Append these tests near the tests from Task 1 in `tests/test_gui_smoke.py`:

```python
def test_main_window_open_definition_directory_cancel_is_noop(qtbot):
    window = MainWindow(definition_directory_dialog=lambda parent: None)
    qtbot.addWidget(window)

    window.open_definition_directory_action.trigger()

    assert window.service_tree.topLevelItemCount() == 0
    assert window.run_log_view.toPlainText() == ""
    assert window.problems_view.toPlainText() == ""


def test_main_window_reports_definition_import_failure(qtbot, tmp_path):
    broken_directory = tmp_path / "definitions"
    broken_directory.mkdir()
    (broken_directory / "broken.json").write_text("{", encoding="utf-8")

    window = MainWindow(definition_directory_dialog=lambda parent: broken_directory)
    qtbot.addWidget(window)

    window.open_definition_directory_action.trigger()

    assert window.service_tree.topLevelItemCount() == 0
    assert "definition_import_failed" in window.problems_view.toPlainText()
    assert str(broken_directory) in window.problems_view.toPlainText()
    assert "definition_import_failed" in window.run_log_view.toPlainText()
    assert "Failed to import service definitions" in window.details.toPlainText()
```

- [ ] **Step 2: Run the new tests to verify failure**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_gui_smoke.py::test_main_window_open_definition_directory_cancel_is_noop \
  tests/test_gui_smoke.py::test_main_window_reports_definition_import_failure \
  -q
```

Expected: `test_main_window_open_definition_directory_cancel_is_noop` passes and `test_main_window_reports_definition_import_failure` FAILS because the import exception escapes instead of being rendered in Problems.

- [ ] **Step 3: Catch import failures in the action handler**

Replace `open_definition_directory()` in `src/someip_gui_tool/gui/main_window.py` with:

```python
    def open_definition_directory(self) -> None:
        directory = self._definition_directory_dialog(self)
        if directory is None:
            return
        try:
            self.load_service_directory(directory)
        except Exception as exc:
            self._record_definition_import_error(directory, exc)
            self._refresh_runtime_views()
```

Add this helper inside `MainWindow` near `_record_gui_exception()`:

```python
    def _record_definition_import_error(self, directory: Path, error: Exception) -> None:
        message = f"Failed to import service definitions from {directory}: {error}"
        self.session.problems.append(
            RuntimeProblem(
                code="definition_import_failed",
                severity="error",
                message=message,
                service_id=0,
            )
        )
        self.session.run_log.append(
            RunLogEntry(
                timestamp=datetime.now(timezone.utc),
                level="error",
                source="GUI",
                message=message,
                error_detail="definition_import_failed",
            )
        )
        self.details.setPlainText(message)
        self.statusBar().showMessage(message)
```

- [ ] **Step 4: Run the cancelled and failed import tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_gui_smoke.py::test_main_window_open_definition_directory_cancel_is_noop \
  tests/test_gui_smoke.py::test_main_window_reports_definition_import_failure \
  -q
```

Expected: PASS.

- [ ] **Step 5: Run the full GUI smoke suite**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_gui_smoke.py -q
```

Expected: PASS with all GUI smoke tests passing.

- [ ] **Step 6: Run the full test suite**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
```

Expected: PASS with the full suite passing.

- [ ] **Step 7: Commit import failure handling**

Run:

```bash
git add src/someip_gui_tool/gui/main_window.py tests/test_gui_smoke.py
git commit -m "fix: report gui definition import failures"
```

Expected: commit succeeds.

---

## Self-Review

- Spec coverage: this plan implements the MVP-1 requirement that the GUI can open a service definition directory and import `ADC40_SOC/*.json` files. It also covers the display rule that import failures go to Run Log and Problems.
- Placeholder scan: no unfinished-marker text or unspecified implementation placeholders remain.
- Type consistency: the plan uses existing `MainWindow`, `RuntimeProblem`, `RunLogEntry`, `RuntimeSession`, and GUI test fixture names. The new `DefinitionDirectoryDialog` is defined before it is referenced in `MainWindow.__init__()`.
