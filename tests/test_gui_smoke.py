from someip_gui_tool.gui.main_window import MainWindow


def test_main_window_loads_services(qtbot, adc40_soc_dir):
    window = MainWindow()
    qtbot.addWidget(window)

    window.load_service_directory(adc40_soc_dir)

    assert window.service_tree.topLevelItemCount() >= 5
