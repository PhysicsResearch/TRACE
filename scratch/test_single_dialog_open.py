import sys
import os
from unittest.mock import patch
from PySide6.QtWidgets import QApplication

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fcn_create_gui.tab_status import build_status_tab
from fcn_init.init_buttons import initialize_software_buttons


from PySide6.QtWidgets import QWidget


class MockUI(QWidget):
    def __init__(self):
        super().__init__()
        self.tab_status = QWidget(self)


def test_dialog_calls_once():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    ui = MockUI()
    build_status_tab(ui)
    initialize_software_buttons(ui)

    # Test 1: Button load log opens dialog exactly once
    with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', return_value=('', '')) as mock_file_dialog:
        ui.button_load_log.click()
        assert mock_file_dialog.call_count == 1, f"Expected 1 call to getOpenFileName for Load Log, got {mock_file_dialog.call_count}"
        print("PASS: button_load_log opens QFileDialog exactly once!")

    # Test 2: Button load gcode ref opens dialog exactly once
    with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', return_value=('', '')) as mock_file_dialog:
        ui.button_load_gcode_ref.click()
        assert mock_file_dialog.call_count == 1, f"Expected 1 call to getOpenFileName for Load G-code as Ref, got {mock_file_dialog.call_count}"
        print("PASS: button_load_gcode_ref opens QFileDialog exactly once!")

    # Test 3: Multiple tab re-initialization calls do not duplicate connections
    initialize_software_buttons(ui)
    initialize_software_buttons(ui)

    with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', return_value=('', '')) as mock_file_dialog:
        ui.button_load_log.click()
        assert mock_file_dialog.call_count == 1, f"Expected 1 call after multiple initializations, got {mock_file_dialog.call_count}"
        print("PASS: multiple initializations maintain single connection!")

    with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', return_value=('', '')) as mock_file_dialog:
        ui.button_load_gcode_ref.click()
        assert mock_file_dialog.call_count == 1, f"Expected 1 call after multiple initializations, got {mock_file_dialog.call_count}"
        print("PASS: multiple initializations maintain single connection for G-code ref!")

    print("\nALL SINGLE DIALOG TESTS PASSED!")


if __name__ == '__main__':
    test_dialog_calls_once()
