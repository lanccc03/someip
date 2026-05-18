import asyncio
from collections.abc import Coroutine
from typing import Any

import json

import pytest
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from someip_gui_tool.core.runtime_config import infer_runtime_config
from someip_gui_tool.domain.enums import Role
from someip_gui_tool.gui.main_window import MainWindow
from someip_gui_tool.gui.runtime_panel import RuntimePanel
from someip_gui_tool.parsing.service_json import load_service_definition


def _top_level_labels(window):
    return [
        window.service_tree.topLevelItem(index).text(0)
        for index in range(window.service_tree.topLevelItemCount())
    ]


def _child_labels(item):
    return [item.child(index).text(0) for index in range(item.childCount())]


def _run_immediate(awaitable: Coroutine[Any, Any, None]) -> None:
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(awaitable)
    finally:
        loop.close()


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


def test_main_window_subscribe_ignores_payload_editor_json(qtbot, adc40_soc_dir):
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
    window.operation_panel.payload_text.setPlainText("{")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Subscribed eventgroup" in window.run_log_view.toPlainText())

    assert "Subscribed eventgroup" in window.run_log_view.toPlainText()
    assert "payload_json_invalid" not in window.problems_view.toPlainText()


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


def test_main_window_service_actions_follow_running_state(
    qtbot: QtBot,
    adc40_soc_dir,
):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    service_item = window.service_tree.topLevelItem(0)

    window.service_tree.setCurrentItem(service_item)
    assert window.operation_panel.primary_button.text() == "Start"
    assert window.operation_panel.primary_button.isEnabled()
    assert window.operation_panel.secondary_button.text() == "Stop"
    assert not window.operation_panel.secondary_button.isEnabled()

    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Started service" in window.run_log_view.toPlainText())

    assert not window.operation_panel.primary_button.isEnabled()
    assert window.operation_panel.secondary_button.isEnabled()

    qtbot.mouseClick(window.operation_panel.secondary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Stopped service" in window.run_log_view.toPlainText())

    assert window.operation_panel.primary_button.isEnabled()
    assert not window.operation_panel.secondary_button.isEnabled()


def test_main_window_locks_runtime_config_while_service_is_running(
    qtbot: QtBot,
    adc40_soc_dir,
):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    service_item = window.service_tree.topLevelItem(0)
    event_item = service_item.child(0)

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.role_combo.setCurrentText(Role.CLIENT.value)
    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Started service" in window.run_log_view.toPlainText())

    assert not window.runtime_panel.role_combo.isEnabled()
    assert not window.runtime_panel.server_port_edit.isEnabled()
    assert not window.runtime_panel.client_port_edit.isEnabled()

    window.runtime_panel.role_combo.setCurrentText(Role.SERVER.value)

    assert window.runtime_panel.role_combo.currentText() == Role.CLIENT.value
    window.service_tree.setCurrentItem(event_item)
    assert window.operation_panel.primary_button.text() == "Subscribe"


def test_main_window_exposes_open_definition_directory_action(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.open_definition_directory_action.objectName() == "open_definition_directory_action"
    assert window.open_definition_directory_action.text() == "Open Definition Directory..."

    file_menu_actions = [
        a for a in window.menuBar().actions()
        if a.menu() is not None and a.text() == "&File"
    ]
    assert len(file_menu_actions) == 1
    file_menu = file_menu_actions[0].menu()
    assert "Open Definition Directory..." in [
        action.text() for action in file_menu.actions()
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


def test_main_window_blocks_definition_import_while_services_run(
    qtbot,
    adc40_soc_dir,
):
    dialog_calls = []

    def choose_directory(parent):
        dialog_calls.append(parent)
        return adc40_soc_dir

    window = MainWindow(
        async_runner=_run_immediate,
        definition_directory_dialog=choose_directory,
    )
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    service_item = window.service_tree.topLevelItem(0)
    original_top_level_count = window.service_tree.topLevelItemCount()

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")
    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Started service" in window.run_log_view.toPlainText())

    window.open_definition_directory_action.trigger()

    assert len(dialog_calls) == 0
    assert "definition_import_blocked_service_running" in window.problems_view.toPlainText()
    assert "Stop running services" in window.problems_view.toPlainText()
    assert "definition_import_blocked_service_running" in window.run_log_view.toPlainText()
    assert window.service_tree.topLevelItemCount() == original_top_level_count
    assert not window.operation_panel.primary_button.isEnabled()
    assert window.operation_panel.secondary_button.isEnabled()


def test_main_window_service_tree_shows_role_and_state(qtbot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    service_item = window.service_tree.topLevelItem(0)

    window.service_tree.setCurrentItem(service_item)

    assert "Role: Client" in service_item.text(0)
    assert "State: Stopped" in service_item.text(0)

    window.runtime_panel.role_combo.setCurrentText(Role.SERVER.value)

    assert "Role: Server" in service_item.text(0)
    assert "State: Stopped" in service_item.text(0)


def test_main_window_service_tree_state_changes_on_start_and_stop(qtbot, adc40_soc_dir):
    window = MainWindow(async_runner=_run_immediate)
    qtbot.addWidget(window)
    window.load_service_directory(adc40_soc_dir)
    service_item = window.service_tree.topLevelItem(0)

    window.service_tree.setCurrentItem(service_item)
    window.runtime_panel.server_port_edit.setText("30500")
    window.runtime_panel.client_port_edit.setText("30501")

    qtbot.mouseClick(window.operation_panel.primary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Started service" in window.run_log_view.toPlainText())

    assert "State: Running" in service_item.text(0)

    qtbot.mouseClick(window.operation_panel.secondary_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: "Stopped service" in window.run_log_view.toPlainText())

    assert "State: Stopped" in service_item.text(0)


def test_runtime_panel_preserves_deployment_ttls_when_reading_config(
    qtbot,
    adc40_soc_dir,
) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    panel = RuntimePanel()
    qtbot.addWidget(panel)

    panel.set_config(infer_runtime_config(service, Role.CLIENT))
    panel.server_port_edit.setText("30500")
    panel.client_port_edit.setText("30501")

    config = panel.config_for_service(service)

    assert config.offer_ttl_s == service.deployment.offer_ttl_s
    assert config.find_ttl_s == service.deployment.find_ttl_s
