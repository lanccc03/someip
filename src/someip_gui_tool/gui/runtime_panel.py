from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QLineEdit

from someip_gui_tool.core.runtime_config import RuntimeServiceConfig, infer_runtime_config
from someip_gui_tool.domain.enums import Role
from someip_gui_tool.domain.models import ServiceDefinition


def _optional_port(text: str, label: str) -> int | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer: {stripped!r}") from exc


class RuntimePanel(QGroupBox):
    def __init__(self) -> None:
        super().__init__("Runtime")
        self.setObjectName("runtime_panel")
        self.role_combo = QComboBox()
        self.role_combo.addItems([Role.CLIENT.value, Role.SERVER.value])
        self.local_ip_edit = QLineEdit()
        self.remote_ip_edit = QLineEdit()
        self.server_port_edit = QLineEdit()
        self.client_port_edit = QLineEdit()
        self.multicast_ip_edit = QLineEdit()

        layout = QFormLayout(self)
        layout.addRow("Role", self.role_combo)
        layout.addRow("Local IP", self.local_ip_edit)
        layout.addRow("Remote IP", self.remote_ip_edit)
        layout.addRow("Server Port", self.server_port_edit)
        layout.addRow("Client Port", self.client_port_edit)
        layout.addRow("Multicast IP", self.multicast_ip_edit)

    def set_config(self, config: RuntimeServiceConfig) -> None:
        self.role_combo.setCurrentText(config.role.value)
        self.local_ip_edit.setText(config.local_ip)
        self.remote_ip_edit.setText(config.remote_ip)
        self.server_port_edit.setText(
            "" if config.server_port is None else str(config.server_port)
        )
        self.client_port_edit.setText(
            "" if config.client_port is None else str(config.client_port)
        )
        self.multicast_ip_edit.setText(config.multicast_ip)

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
