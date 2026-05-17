from __future__ import annotations

from pathlib import Path

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
from someip_gui_tool.gui.theme import monospace_font


ITEM_PAYLOAD_ROLE = Qt.ItemDataRole.UserRole


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SOME/IP Test Tool")
        self._registry: ServiceRegistry | None = None

        self.service_tree = QTreeWidget()
        self.service_tree.setObjectName("service_tree")
        self.service_tree.setHeaderLabels(["Service Browser"])
        self.service_tree.currentItemChanged.connect(self._on_current_item_changed)

        self.runtime_panel = RuntimePanel()
        self.runtime_panel.role_combo.currentTextChanged.connect(
            self._on_runtime_role_changed
        )
        self.operation_panel = OperationPanel()

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
        if current is None:
            return

        payload = current.data(0, ITEM_PAYLOAD_ROLE)
        service = self._service_for_item(current)
        if service is not None:
            self._set_runtime_config(service)

        role = Role(self.runtime_panel.role_combo.currentText())
        if isinstance(payload, MethodDefinition):
            self.operation_panel.show_method(payload, role)
        elif isinstance(payload, EventDefinition):
            self.operation_panel.show_event(payload, role)
        elif isinstance(payload, FieldDefinition):
            self.operation_panel.show_field(payload, role)
        else:
            self.operation_panel.clear_selection()

    def _on_runtime_role_changed(self, role_text: str) -> None:
        current = self.service_tree.currentItem()
        if current is None:
            return
        service = self._service_for_item(current)
        if service is not None:
            self._set_runtime_config(service)

    def _set_runtime_config(self, service: ServiceDefinition) -> None:
        role = Role(self.runtime_panel.role_combo.currentText())
        self.runtime_panel.set_config(infer_runtime_config(service, role))

    def _service_for_item(self, item: QTreeWidgetItem) -> ServiceDefinition | None:
        cursor: QTreeWidgetItem | None = item
        while cursor is not None:
            payload = cursor.data(0, ITEM_PAYLOAD_ROLE)
            if isinstance(payload, ServiceDefinition):
                return payload
            cursor = cursor.parent()
        return None
