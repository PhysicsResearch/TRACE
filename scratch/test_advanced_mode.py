import sys
import os
import json
from PySide6.QtWidgets import QApplication, QWidget

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fcn_create_gui.tab_status import build_status_tab, apply_status_advanced_mode, save_status_advanced_mode
from fcn_init.init_variables import initialize_software_variables
from fcn_init.app_config import get_config_path


class MockWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.tab_status = QWidget(self)


def test_advanced_mode():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    win = MockWindow()
    # Mock some default variables needed
    win.duet_ip = "192.168.8.2"
    win.status_advanced_mode = False

    build_status_tab(win)

    # 1. Verify check_advanced_mode exists
    assert hasattr(win, 'check_advanced_mode'), "check_advanced_mode should exist on win"
    assert win.check_advanced_mode.text() == "Advanced mode"
    print("PASS: check_advanced_mode exists with label 'Advanced mode'")

    # 2. Test Basic Mode (Default / unchecked)
    win.check_advanced_mode.setChecked(False)

    # Speed controls container must be hidden in Basic mode
    assert hasattr(win, 'speed_controls_container'), "speed_controls_container should exist"
    assert win.speed_controls_container.isHidden() == True, "speed_controls_container should be hidden in Basic mode"

    # Speeds and positions container must be hidden
    assert hasattr(win, 'metrics_container'), "metrics_container should exist"
    assert win.metrics_container.isHidden() == True, "metrics_container should be hidden in Basic mode"

    # Log folder container must be hidden
    assert hasattr(win, 'log_folder_container'), "log_folder_container should exist"
    assert win.log_folder_container.isHidden() == True, "log_folder_container should be hidden in Basic mode"

    # button_clear_plot must be visible
    assert hasattr(win, 'button_clear_plot'), "button_clear_plot should exist"
    assert win.button_clear_plot.isHidden() == False, "button_clear_plot should remain visible in Basic mode"

    # Verify visible axes in Basic mode
    basic_axes = [
        'status_check_X', 'status_check_Y', 'status_check_Z',
        'status_check_AP', 'status_check_LAT', 'status_check_SI',
        'status_check_Pitch', 'status_check_Roll'
    ]
    assert win.check_show_reference.isHidden() == False, "Show reference should be visible in Basic mode"
    for ax in basic_axes:
        cb = getattr(win, ax)
        assert cb.isHidden() == False, f"{ax} should be visible in Basic mode"

    # Verify hidden axes in Basic mode
    advanced_axes = [
        'status_check_A', 'status_check_B', 'status_check_C', 'status_check_D',
        'status_check_e', 'status_check_f', 'status_check_a', 'status_check_c',
        'status_check_Yaw'
    ]
    for ax in advanced_axes:
        cb = getattr(win, ax)
        assert cb.isHidden() == True, f"{ax} should be hidden in Basic mode"

    print("PASS: Basic mode hides speed factor controls, speeds row, positions row, log folder row (except clear plot), and advanced axes!")

    # 3. Test Advanced Mode (checked)
    win.check_advanced_mode.setChecked(True)

    assert win.speed_controls_container.isHidden() == False, "speed_controls_container should be visible in Advanced mode"
    assert win.metrics_container.isHidden() == False, "metrics_container should be visible in Advanced mode"
    assert win.log_folder_container.isHidden() == False, "log_folder_container should be visible in Advanced mode"
    assert win.button_clear_plot.isHidden() == False, "button_clear_plot should be visible in Advanced mode"

    # All axes should now be visible
    for ax in basic_axes + advanced_axes:
        cb = getattr(win, ax)
        assert cb.isHidden() == False, f"{ax} should be visible in Advanced mode"

    print("PASS: Advanced mode shows speeds row, positions row, log folder row, and all axes!")

    # 4. Test Persistence
    # When set to True, configuration.json should record status_advanced_mode: True
    cfg_file = get_config_path('configuration.json', for_writing=False)
    with open(cfg_file, 'r') as f:
        data = json.load(f)
    assert data.get('status_advanced_mode') == True, f"Expected status_advanced_mode=True in config, got {data.get('status_advanced_mode')}"

    # Test toggling back to False
    win.check_advanced_mode.setChecked(False)
    with open(cfg_file, 'r') as f:
        data = json.load(f)
    assert data.get('status_advanced_mode') == False, f"Expected status_advanced_mode=False in config, got {data.get('status_advanced_mode')}"

    # Test restoring via initialize_software_variables
    save_status_advanced_mode(win, True)
    win2 = MockWindow()
    initialize_software_variables(win2)
    assert getattr(win2, 'status_advanced_mode', None) == True, "initialize_software_variables should load True"

    build_status_tab(win2)
    assert win2.check_advanced_mode.isChecked() == True, "check_advanced_mode should initialize as True from config"
    assert win2.metrics_container.isHidden() == False, "metrics_container should be visible when starting in Advanced mode"
    assert win2.log_folder_container.isHidden() == False, "log_folder_container should be visible when starting in Advanced mode"

    print("PASS: Persistence across restart verified successfully!")
    print("\nALL ADVANCED MODE TESTS PASSED SUCCESSFULLY!")


if __name__ == '__main__':
    test_advanced_mode()
