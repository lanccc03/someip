from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QPlainTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from someip_gui_tool.core.service_registry import ServiceRegistry
from someip_gui_tool.domain.models import FieldDefinition, ServiceDefinition


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SOME/IP Test Tool")

        self.service_tree = QTreeWidget()
        self.service_tree.setHeaderLabels(["Service Browser"])

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlainText("Ready")

        central_widget = QWidget()
        layout = QHBoxLayout(central_widget)
        layout.addWidget(self.service_tree, 2)
        layout.addWidget(self.details, 1)
        self.setCentralWidget(central_widget)
        self.statusBar().showMessage("Ready")

    def load_service_directory(self, directory: Path) -> None:
        registry = ServiceRegistry.load_directory(directory)
        self.service_tree.clear()

        for service in registry.services:
            self.service_tree.addTopLevelItem(self._service_item(service))

        self.service_tree.expandAll()
        message = f"Loaded {len(registry.services)} service definitions from {directory}"
        self.details.setPlainText(message)
        self.statusBar().showMessage(message)

    def _service_item(self, service: ServiceDefinition) -> QTreeWidgetItem:
        service_item = QTreeWidgetItem(
            [f"{service.service_name} ({service.service_id_hex})"]
        )

        for method in service.methods:
            service_item.addChild(
                QTreeWidgetItem([f"Method {method.name} ({method.method_id_hex})"])
            )

        for event in service.events:
            service_item.addChild(
                QTreeWidgetItem([f"Event {event.name} ({event.event_id_hex})"])
            )

        for field in service.fields:
            service_item.addChild(self._field_item(field))

        return service_item

    def _field_item(self, field: FieldDefinition) -> QTreeWidgetItem:
        field_item = QTreeWidgetItem([f"Field {field.name}"])

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
