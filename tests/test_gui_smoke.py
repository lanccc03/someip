import json

import pytest
from PySide6.QtCore import Qt

from someip_gui_tool.core.runtime_config import infer_runtime_config
from someip_gui_tool.domain.enums import Role
from someip_gui_tool.gui.main_window import MainWindow


def _top_level_labels(window):
    return [
        window.service_tree.topLevelItem(index).text(0)
        for index in range(window.service_tree.topLevelItemCount())
    ]


def _child_labels(item):
    return [item.child(index).text(0) for index in range(item.childCount())]


def test_main_window_loads_services(qtbot, adc40_soc_dir):
    window = MainWindow()
    qtbot.addWidget(window)

    window.load_service_directory(adc40_soc_dir)

    assert window.service_tree.topLevelItemCount() >= 5
    assert "Loaded" in window.details.toPlainText()

    service_labels = _top_level_labels(window)
    second_start_index = next(
        index
        for index, label in enumerate(service_labels)
        if "SecondStartSrv" in label
    )
    second_start_item = window.service_tree.topLevelItem(second_start_index)
    assert second_start_item.childCount() > 0

    second_start_child_labels = _child_labels(second_start_item)
    assert any("Method SecondStartCtrl" in label for label in second_start_child_labels)
    assert any("Event SecondStartPopup" in label for label in second_start_child_labels)

    assert any(
        any("Field VertHeiRmdSts" in label for label in _child_labels(item))
        for item in (
            window.service_tree.topLevelItem(index)
            for index in range(window.service_tree.topLevelItemCount())
        )
    )


def test_main_window_exposes_bottom_runtime_tabs(qtbot, adc40_soc_dir):
    window = MainWindow()
    qtbot.addWidget(window)

    window.load_service_directory(adc40_soc_dir)
    window.show()

    assert window.bottom_tabs.count() == 3
    assert [
        window.bottom_tabs.tabText(index)
        for index in range(window.bottom_tabs.count())
    ] == ["Run Log", "Message Trace", "Problems"]
    assert window.run_log_view.isReadOnly()
    assert window.message_trace_view.isReadOnly()
    assert window.problems_view.isReadOnly()

    for index in range(window.bottom_tabs.count()):
        window.bottom_tabs.setCurrentIndex(index)
        assert window.bottom_tabs.currentWidget().isVisible()

    assert window.service_tree.topLevelItemCount() >= 5


def test_main_window_shows_runtime_config_for_selected_service(qtbot, adc40_soc_dir):
    window = MainWindow()
    qtbot.addWidget(window)

    window.load_service_directory(adc40_soc_dir)
    first_item = window.service_tree.topLevelItem(0)
    window.service_tree.setCurrentItem(first_item)

    assert window.runtime_panel.role_combo.currentText() in {
        Role.CLIENT.value,
        Role.SERVER.value,
    }
    assert window.runtime_panel.server_port_edit.text() == ""
    assert window.runtime_panel.client_port_edit.text() == ""


def test_main_window_shows_field_operations(qtbot, adc40_soc_dir):
    window = MainWindow()
    qtbot.addWidget(window)

    window.load_service_directory(adc40_soc_dir)
    field_items = window.service_tree.findItems(
        "Field VertHeiRmdSts",
        Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
    )
    window.service_tree.setCurrentItem(field_items[0])

    assert window.operation_panel.title_label.text().startswith("Field")
    assert window.operation_panel.primary_button.text() == "Get"
    assert window.operation_panel.secondary_button.text() == "Notify"


def test_main_window_role_change_reinfers_selected_service_config(
    qtbot,
    adc40_soc_dir,
):
    window = MainWindow()
    qtbot.addWidget(window)

    window.load_service_directory(adc40_soc_dir)
    first_item = window.service_tree.topLevelItem(0)
    service = first_item.data(0, Qt.ItemDataRole.UserRole)
    expected_config = infer_runtime_config(service, Role.SERVER)

    window.service_tree.setCurrentItem(first_item)
    window.runtime_panel.role_combo.setCurrentText(Role.SERVER.value)

    assert window.runtime_panel.role_combo.currentText() == Role.SERVER.value
    assert window.runtime_panel.local_ip_edit.text() == expected_config.local_ip
    assert window.runtime_panel.remote_ip_edit.text() == expected_config.remote_ip
    assert window.runtime_panel.multicast_ip_edit.text() == expected_config.multicast_ip


def test_main_window_clears_field_operations_when_service_selected(
    qtbot,
    adc40_soc_dir,
):
    window = MainWindow()
    qtbot.addWidget(window)

    window.load_service_directory(adc40_soc_dir)
    field_item = window.service_tree.findItems(
        "Field VertHeiRmdSts",
        Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
    )[0]
    service_item = field_item.parent()

    window.service_tree.setCurrentItem(field_item)
    window.service_tree.setCurrentItem(service_item)

    assert window.operation_panel.title_label.text() == "Select a method, event, or field"
    assert window.operation_panel.primary_button.text() == "Start"
    assert window.operation_panel.secondary_button.text() == "Stop"


def test_main_window_clears_field_operations_when_field_part_selected(
    qtbot,
    adc40_soc_dir,
):
    window = MainWindow()
    qtbot.addWidget(window)

    window.load_service_directory(adc40_soc_dir)
    field_item = window.service_tree.findItems(
        "Field VertHeiRmdSts",
        Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
    )[0]
    field_part_item = field_item.child(0)

    window.service_tree.setCurrentItem(field_item)
    window.service_tree.setCurrentItem(field_part_item)

    assert window.operation_panel.title_label.text() == "Select a method, event, or field"
    assert window.operation_panel.primary_button.text() == "Start"
    assert window.operation_panel.secondary_button.text() == "Stop"


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
