from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QPlainTextEdit,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from someip_gui_tool.adapters.mock import MockSomeIpAdapter
from someip_gui_tool.core.runtime_config import (
    RuntimeProblem,
    RuntimeServiceConfig,
    infer_runtime_config,
)
from someip_gui_tool.core.runtime_session import RuntimeSession
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
from someip_gui_tool.gui.theme import monospace_font
from someip_gui_tool.tracing.exporters import export_run_log_text, export_trace_csv
from someip_gui_tool.tracing.trace_model import RunLogEntry


ITEM_PAYLOAD_ROLE = Qt.ItemDataRole.UserRole

AsyncRunner = Callable[[Coroutine[Any, Any, None]], None]


def schedule_async(awaitable: Coroutine[Any, Any, None]) -> None:
    asyncio.create_task(awaitable)


class MainWindow(QMainWindow):
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

        self.service_tree = QTreeWidget()
        self.service_tree.setObjectName("service_tree")
        self.service_tree.setHeaderLabels(["Service Browser"])
        self.service_tree.currentItemChanged.connect(self._on_current_item_changed)

        self.runtime_panel = RuntimePanel()
        self.runtime_panel.role_combo.currentTextChanged.connect(
            self._on_runtime_role_changed
        )
        self.operation_panel = OperationPanel()
        self.operation_panel.primary_button.clicked.connect(self._on_primary_action)
        self.operation_panel.secondary_button.clicked.connect(self._on_secondary_action)

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlainText("Ready")

        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setObjectName("bottom_tabs")
        self.run_log_view = QPlainTextEdit()
        self.message_trace_view = QPlainTextEdit()
        self.problems_view = QPlainTextEdit()
        _mono = monospace_font()
        for view in (
            self.run_log_view,
            self.message_trace_view,
            self.problems_view,
        ):
            view.setReadOnly(True)
            view.setFont(_mono)

        self.bottom_tabs.addTab(self.run_log_view, "Run Log")
        self.bottom_tabs.addTab(self.message_trace_view, "Message Trace")
        self.bottom_tabs.addTab(self.problems_view, "Problems")

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
        layout = QVBoxLayout(central_widget)
        layout.addWidget(splitter)
        layout.addWidget(self.bottom_tabs)
        layout.setStretch(0, 4)
        layout.setStretch(1, 1)
        self.setCentralWidget(central_widget)
        self.statusBar().showMessage("Ready")

    def load_service_directory(self, directory: Path) -> None:
        self._registry = ServiceRegistry.load_directory(directory)
        self.service_tree.clear()

        for service in self._registry.services:
            self.service_tree.addTopLevelItem(self._service_item(service))

        self.service_tree.expandAll()
        message = (
            f"Loaded {len(self._registry.services)} service definitions from {directory}"
        )
        self.details.setPlainText(message)
        self.statusBar().showMessage(message)

    def _service_item(self, service: ServiceDefinition) -> QTreeWidgetItem:
        service_item = QTreeWidgetItem(
            [f"{service.service_name} ({service.service_id_hex})"]
        )
        service_item.setData(0, ITEM_PAYLOAD_ROLE, service)

        for method in service.methods:
            method_item = QTreeWidgetItem(
                [f"Method {method.name} ({method.method_id_hex})"]
            )
            method_item.setData(0, ITEM_PAYLOAD_ROLE, method)
            service_item.addChild(method_item)

        for event in service.events:
            event_item = QTreeWidgetItem([f"Event {event.name} ({event.event_id_hex})"])
            event_item.setData(0, ITEM_PAYLOAD_ROLE, event)
            service_item.addChild(event_item)

        for field in service.fields:
            service_item.addChild(self._field_item(field))

        return service_item

    def _field_item(self, field: FieldDefinition) -> QTreeWidgetItem:
        field_item = QTreeWidgetItem([f"Field {field.name}"])
        field_item.setData(0, ITEM_PAYLOAD_ROLE, field)

        for label, part in (
            ("Getter", field.getter),
            ("Setter", field.setter),
            ("Notifier", field.notifier),
        ):
            if part is not None:
                field_item.addChild(
                    QTreeWidgetItem([f"{label}: {part.name} ({part.element_id:#06X})"])
                )

        return field_item

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

    def _service_for_item(self, item: QTreeWidgetItem) -> ServiceDefinition | None:
        cursor: QTreeWidgetItem | None = item
        while cursor is not None:
            payload = cursor.data(0, ITEM_PAYLOAD_ROLE)
            if isinstance(payload, ServiceDefinition):
                return payload
            cursor = cursor.parent()
        return None
