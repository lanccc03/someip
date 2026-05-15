from __future__ import annotations

from PySide6.QtWidgets import QGroupBox, QLabel, QPushButton, QVBoxLayout

from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldDefinition,
    MethodDefinition,
)


class OperationPanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Operation")
        self.title_label = QLabel("Select a method, event, or field")
        self.primary_button = QPushButton("Start")
        self.secondary_button = QPushButton("Stop")

        layout = QVBoxLayout(self)
        layout.addWidget(self.title_label)
        layout.addWidget(self.primary_button)
        layout.addWidget(self.secondary_button)

    def show_method(self, method: MethodDefinition) -> None:
        self.title_label.setText(f"Method {method.name} ({method.method_id_hex})")
        self.primary_button.setText("Call")
        self.secondary_button.setText("Configure Response")

    def show_event(self, event: EventDefinition) -> None:
        self.title_label.setText(f"Event {event.name} ({event.event_id_hex})")
        self.primary_button.setText("Subscribe")
        self.secondary_button.setText("Publish")

    def show_field(self, field: FieldDefinition) -> None:
        self.title_label.setText(f"Field {field.name}")
        self.primary_button.setText("Get")
        self.secondary_button.setText("Notify")
