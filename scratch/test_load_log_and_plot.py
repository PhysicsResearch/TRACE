import sys
import os
import numpy as np
import pandas as pd
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.insert(0, r"c:\TRACE")

from PySide6.QtWidgets import QApplication, QWidget, QCheckBox, QLineEdit, QPushButton
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

# Initialize Qt App if not already created
app = QApplication.instance()
if app is None:
    app = QApplication([])

from fcn_monitor.fcn_duet import (
    load_log_file_into_status,
    render_status_plot,
    clear_status_plot_data,
    log_data_point,
    close_data_log_file
)

def create_mock_ui():
    ui = MagicMock()
    ui.fig_status = Figure()
    ui.ax_status = ui.fig_status.add_subplot(111)
    ui.statusCanvas = MagicMock()

    ui.PhOperFolder = QLineEdit(r"c:\TRACE\scratch")
    ui.input_time_interval = QLineEdit("60")
    ui.check_show_reference = QCheckBox()
    ui.check_show_reference.setChecked(False)
    ui.statusDuetMessage = MagicMock()

    traces = [
        'status_check_X', 'status_check_Y', 'status_check_Z',
        'status_check_A', 'status_check_B', 'status_check_C', 'status_check_D',
        'status_check_e', 'status_check_f', 'status_check_a', 'status_check_c',
        'status_check_Roll', 'status_check_Pitch', 'status_check_Yaw',
        'status_check_LAT', 'status_check_AP', 'status_check_SI'
    ]
    for tr in traces:
        cb = QCheckBox()
        cb.setChecked(False)
        setattr(ui, tr, cb)

    ui.status_plot_lines = {}
    ui.status_ref_lines = {}
    ui._probe_span_patches = []
    ui.active_log_file = None
    ui.active_log_filepath = None
    return ui

def test_load_sample_log():
    print("=== Test 1: Load sample_log.txt ===")
    ui = create_mock_ui()
    sample_log = r"c:\TRACE\scratch\sample_log.txt"
    load_log_file_into_status(ui, sample_log)

    # Verify status_plot_data
    assert 't' in ui.status_plot_data
    assert len(ui.status_plot_data['t']) > 100
    assert len(ui.status_plot_data['X']) == len(ui.status_plot_data['t'])
    assert len(ui.status_plot_data['Y']) == len(ui.status_plot_data['t'])
    assert len(ui.status_plot_data['Z']) == len(ui.status_plot_data['t'])
    print(f"Loaded {len(ui.status_plot_data['t'])} points successfully.")

    # Verify checkboxes: X, Y, Z should be checked, all others unchecked
    assert ui.status_check_X.isChecked() == True, "X should be checked"
    assert ui.status_check_Y.isChecked() == True, "Y should be checked"
    assert ui.status_check_Z.isChecked() == True, "Z should be checked"
    assert ui.status_check_Roll.isChecked() == False, "Roll should be unchecked"
    assert ui.status_check_LAT.isChecked() == False, "LAT should be unchecked"
    assert ui.status_check_A.isChecked() == False, "A should be unchecked"
    print("Axes visibility checkboxes automatically verified!")

def test_load_log_with_probe_and_platform_axes():
    print("\n=== Test 2: Load Log with Probe > 0 and Platform Axes ===")
    test_csv = r"c:\TRACE\scratch\test_platform_probe.csv"
    
    # Create test csv with LAT, SI, AP and Probe active during [2.0, 5.0] and [7.0, 9.0]
    t = np.linspace(0, 10, 101) # 0 to 10s, dt=0.1
    lat = 5.0 * np.sin(t)
    si = 3.0 * np.cos(t)
    ap = 2.0 * np.sin(2 * t)
    probe = np.zeros_like(t)
    probe[(t >= 2.0) & (t <= 5.0)] = 1
    probe[(t >= 7.0) & (t <= 9.0)] = 1

    df = pd.DataFrame({
        'Time_s': t,
        'Pos_LAT_mm': lat,
        'Pos_SI_mm': si,
        'Pos_AP_mm': ap,
        'Probe': probe
    })
    df.to_csv(test_csv, index=False)

    ui = create_mock_ui()
    load_log_file_into_status(ui, test_csv)

    # Check automatically set visible axes: LAT, SI, AP should be True, X, Y, Z False
    assert ui.status_check_LAT.isChecked() == True, "LAT should be checked"
    assert ui.status_check_SI.isChecked() == True, "SI should be checked"
    assert ui.status_check_AP.isChecked() == True, "AP should be checked"
    assert ui.status_check_X.isChecked() == False, "X should be unchecked"
    assert ui.status_check_Y.isChecked() == False, "Y should be unchecked"
    assert ui.status_check_Z.isChecked() == False, "Z should be unchecked"
    print("Platform axes checked correctly, cartesian axes unchecked.")

    # Check probe shading
    assert hasattr(ui, '_probe_span_patches')
    print(f"Number of probe span patches: {len(ui._probe_span_patches)}")
    assert len(ui._probe_span_patches) == 2, f"Expected 2 shaded probe patches, got {len(ui._probe_span_patches)}"
    
    # Check that patches are red with alpha 0.22
    for patch in ui._probe_span_patches:
        fc = patch.get_facecolor()
        print("Patch facecolor:", fc)
        # Red is (1.0, 0.0, 0.0, 0.22)
        assert abs(fc[0] - 1.0) < 0.01, "Red channel should be ~1.0"
        assert abs(fc[3] - 0.22) < 0.01, "Alpha should be ~0.22"
    print("Probe shading verified with red background!")

    if os.path.exists(test_csv):
        os.remove(test_csv)

def test_log_file_saved_as_csv():
    print("\n=== Test 3: Verify log files are saved as CSV ===")
    ui = create_mock_ui()
    out_dir = r"c:\TRACE\scratch\test_log_dir"
    os.makedirs(out_dir, exist_ok=True)
    ui.PhOperFolder.setText(out_dir)

    # Log 3 data points
    log_data_point(ui, 0.0, 10.0, 20.0, 30.0, probe=0)
    log_data_point(ui, 0.1, 10.5, 20.5, 30.5, probe=1)
    log_data_point(ui, 0.2, 11.0, 21.0, 31.0, probe=0)

    filepath = ui.active_log_filepath
    assert filepath is not None
    assert filepath.endswith(".csv"), f"Log file must end with .csv, got {filepath}"
    assert os.path.exists(filepath), f"File {filepath} must exist"

    close_data_log_file(ui)

    # Check contents of the saved CSV
    df = pd.read_csv(filepath)
    print("Saved CSV columns:", list(df.columns))
    assert list(df.columns) == ['Time_s', 'Pos_X_mm', 'Pos_Y_mm', 'Pos_Z_mm', 'Probe']
    assert len(df) == 3
    assert df['Probe'].iloc[1] == 1
    print("Saved CSV successfully verified!")

    # Clean up test dir
    try:
        os.remove(filepath)
        os.rmdir(out_dir)
    except Exception:
        pass

if __name__ == '__main__':
    test_load_sample_log()
    test_load_log_with_probe_and_platform_axes()
    test_log_file_saved_as_csv()
    print("\nALL TESTS PASSED SUCCESSFULLY!")
