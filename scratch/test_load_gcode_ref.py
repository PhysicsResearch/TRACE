import sys
import os
import numpy as np
from unittest.mock import MagicMock

sys.path.insert(0, r"c:\TRACE")

from PySide6.QtWidgets import QApplication, QWidget, QCheckBox, QLineEdit, QPushButton
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

app = QApplication.instance() or QApplication([])

from fcn_create_gui.tab_status import build_status_tab
from fcn_init.init_buttons import initialize_software_buttons
from fcn_monitor.fcn_duet import load_gcode_as_reference_into_status, render_status_plot

def test_load_gcode_reference_gui():
    print("=== Test 1: Verify Button in GUI and Dimensions ===")
    win = QWidget()
    win.tab_status = QWidget()
    build_status_tab(win)
    initialize_software_buttons(win)

    win.tab_status.resize(1300, 500)
    win.tab_status.show()
    app.processEvents()

    assert hasattr(win, 'button_load_gcode_ref'), "button_load_gcode_ref should exist"
    assert win.button_load_gcode_ref.text() == "Load G-code as Ref"
    assert win.button_load_gcode_ref.height() == 32
    assert win.button_load_log.height() == 32
    assert win.setPhOperFolder.height() == 32
    print("Button exists with matching 32px height!")

def test_load_gcode_reference_functionality():
    print("\n=== Test 2: Test Loading G-code as Reference ===")
    win = QWidget()
    win.tab_status = QWidget()
    win.settings_max_lim_ap = None
    win.settings_max_lim_si = None
    win.settings_max_lim_lat = None
    build_status_tab(win)
    initialize_software_buttons(win)

    gcode_file = r"c:\TRACE\planned_motion_platform_SI_sin.gcode"
    assert os.path.exists(gcode_file)

    load_gcode_as_reference_into_status(win, gcode_file)

    # 1. Check status_reference_data
    ref = win.status_reference_data
    assert ref is not None, "status_reference_data should not be None"
    assert 't' in ref
    assert len(ref['t']) > 100
    print(f"Loaded reference with {len(ref['t'])} points, duration: {ref['t'][-1]}s")

    # 2. Check that Show reference is now checked
    assert win.check_show_reference.isChecked() == True, "Show reference checkbox should be checked"

    # 3. Check that SI has motion and its checkbox is checked
    assert win.status_check_SI.isChecked() == True, "Show SI should be checked"
    print("Show reference and active axes checkboxes automatically checked!")

    # 4. Check reference line plotted in ax_status
    assert 'SI' in win.status_ref_lines
    rline = win.status_ref_lines['SI']
    assert rline.get_visible() == True
    print("Reference line is plotted and visible on status canvas!")

    # 5. Check Time Interval was updated to fit the reference
    time_int = float(win.input_time_interval.text())
    assert time_int >= ref['t'][-1], "Time interval should accommodate full reference trajectory"
    print(f"Time interval adjusted to {time_int}s!")

if __name__ == '__main__':
    test_load_gcode_reference_gui()
    test_load_gcode_reference_functionality()
    print("\nALL G-CODE REFERENCE TESTS PASSED SUCCESSFULLY!")
