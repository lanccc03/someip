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
