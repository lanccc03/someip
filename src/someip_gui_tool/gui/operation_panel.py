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
