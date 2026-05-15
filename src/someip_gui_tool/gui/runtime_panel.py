from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QLineEdit

from someip_gui_tool.core.runtime_config import RuntimeServiceConfig
from someip_gui_tool.domain.enums import Role


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
