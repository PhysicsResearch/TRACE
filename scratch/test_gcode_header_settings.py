import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import numpy as np
import pandas as pd
from PySide6.QtWidgets import QApplication, QWidget, QTabWidget

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from fcn_create_gui.tab_planning import build_planning_tab
from fcn_plan.fcn_gcode import generate_gcode_string
from fcn_plan.fcn_create import generate_planned_gcode, create_curve


def test_gcode_header_settings():
    # 1. Pure function tests for Lung Phantom
    t_orig = np.linspace(0, 10, 101)
    cols_phantom = {'X': np.sin(t_orig) * 10, 'Y': np.cos(t_orig) * 10, 'Z': np.zeros_like(t_orig)}
    limits_phantom = (40.0, 40.0, 40.0)

    gcode_p, _ = generate_gcode_string("Lung Phantom", t_orig, cols_phantom, limits_phantom, speed=20, acc=1000, jerk=600)
    lines_p = gcode_p.splitlines()

    assert "M566 X600 Y600 Z600" in lines_p[:6], f"M566 missing in header: {lines_p[:6]}"
    assert "M201 X1000 Y1000 Z1000" in lines_p[:6], f"M201 missing in header: {lines_p[:6]}"
    assert "M203 X1200 Y1200 Z1200" in lines_p[:6], f"M203 missing in header: {lines_p[:6]}"  # 20 * 60 = 1200
    print("PASS: Pure function Lung Phantom headers verified!")

    # 2. Pure function tests for Motion Platform
    cols_platform = {
        'LAT': np.zeros_like(t_orig), 'SI': np.sin(t_orig) * 5, 'AP': np.zeros_like(t_orig),
        'Roll': np.zeros_like(t_orig), 'Pitch': np.zeros_like(t_orig), 'Yaw': np.zeros_like(t_orig)
    }
    limits_platform = (40.0, 40.0, 40.0, 40.0, 40.0, 40.0)

    gcode_m, _ = generate_gcode_string(
        "Motion Platform", t_orig, cols_platform, limits_platform,
        lat_dim=300.0, si_dim=500.0, off_ap=0.0, off_lat=0.0, off_si=0.0, axis_y_lo="'c",
        speed=30, acc=1500, jerk=900
    )
    lines_m = gcode_m.splitlines()

    expected_m566 = "M566 A900 B900 C900 D900 'c900 'a900  'f900 'e900"
    expected_m201 = "M201 A1500 B1500 C1500 D1500 'c1500 'a1500  'f1500 'e1500"
    expected_m203 = "M203 A1800 B1800 C1800 D1800 'c1800 'a1800  'f1800 'e1800"  # 30 * 60 = 1800

    assert expected_m566 in lines_m[:6], f"Expected {expected_m566}, got {lines_m[:6]}"
    assert expected_m201 in lines_m[:6], f"Expected {expected_m201}, got {lines_m[:6]}"
    assert expected_m203 in lines_m[:6], f"Expected {expected_m203}, got {lines_m[:6]}"
    print("PASS: Pure function Motion Platform headers verified!")

    # 3. Test through GUI instance and generate_planned_gcode
    class MockUI(QWidget):
        def __init__(self):
            super().__init__()
            self.tab_planning = QWidget(self)
            self.tabWidget = QTabWidget(self)
            self.tabWidget.addTab(self.tab_planning, "Planning")
            build_planning_tab(self)

    ui = MockUI()
    # Test Lung Phantom via UI
    ui.combo_device.setCurrentText("Lung Phantom")
    ui.combo_phantom_max_speed.setCurrentText("50")  # 50 * 60 = 3000
    ui.combo_phantom_acc.setCurrentText("3000")
    ui.combo_phantom_jerk.setCurrentText("1200")
    create_curve(ui)

    gcode_ui_p, name_p = generate_planned_gcode(ui)
    assert gcode_ui_p is not None
    lines_ui_p = gcode_ui_p.splitlines()
    assert "M566 X1200 Y1200 Z1200" in lines_ui_p[:6], f"UI Lung Phantom M566 failed: {lines_ui_p[:6]}"
    assert "M201 X3000 Y3000 Z3000" in lines_ui_p[:6], f"UI Lung Phantom M201 failed: {lines_ui_p[:6]}"
    assert "M203 X3000 Y3000 Z3000" in lines_ui_p[:6], f"UI Lung Phantom M203 failed: {lines_ui_p[:6]}"
    print("PASS: UI Lung Phantom generate_planned_gcode verified with selected dropdown values!")

    # Test Motion Platform via UI
    from PySide6.QtWidgets import QLineEdit
    ui.input_plat_lat = QLineEdit("300", ui)
    ui.input_plat_si = QLineEdit("500", ui)
    ui.combo_device.setCurrentText("Motion Platform")
    ui.combo_platform_max_speed.setCurrentText("10")  # 10 * 60 = 600
    ui.combo_platform_acc.setCurrentText("500")
    ui.combo_platform_jerk.setCurrentText("300")
    create_curve(ui)

    gcode_ui_m, name_m = generate_planned_gcode(ui)
    assert gcode_ui_m is not None
    lines_ui_m = gcode_ui_m.splitlines()
    assert "M566 A300 B300 C300 D300 'c300 'a300  'f300 'e300" in lines_ui_m[:6], f"UI Motion Platform M566 failed: {lines_ui_m[:6]}"
    assert "M201 A500 B500 C500 D500 'c500 'a500  'f500 'e500" in lines_ui_m[:6], f"UI Motion Platform M201 failed: {lines_ui_m[:6]}"
    assert "M203 A600 B600 C600 D600 'c600 'a600  'f600 'e600" in lines_ui_m[:6], f"UI Motion Platform M203 failed: {lines_ui_m[:6]}"
    print("PASS: UI Motion Platform generate_planned_gcode verified with selected dropdown values!")

    print("\nALL G-CODE HEADER SETTINGS TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    test_gcode_header_settings()
