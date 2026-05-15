from PySide6.QtCore import Qt

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
