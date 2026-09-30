import sys
import os
import pandas as pd
import numpy as np

# Add project root to sys.path
sys.path.insert(0, r"c:\TRACE")

from fcn_plan.fcn_import import parse_trace_log_file, is_trace_log_file
from fcn_plan.fcn_create import compute_kinematics, SmoothAxisDialog, open_smooth_axes_dialog

def test_log_import_kinematics():
    print("=== 1. Testing Log Import Kinematics from Measured Data ===")
    sample_file = r"c:\TRACE\scratch\sample_log.txt"
    assert os.path.exists(sample_file), f"Sample file not found: {sample_file}"
    assert is_trace_log_file(sample_file), "File not recognized as TRACE log"

    plan_df, device, matched_axes, probe_detected, orig_count, t_max = parse_trace_log_file(sample_file)

    print(f"Device: {device}")
    print(f"Matched Axes: {matched_axes}")
    print(f"Orig count: {orig_count}, duration: {t_max:.2f}s")
    print(f"Resampled points: {len(plan_df)}")

    # Check columns
    assert 'X' in plan_df.columns
    assert 'Vel. X' in plan_df.columns
    assert 'Acc. X' in plan_df.columns

    # Verify measured derivative:
    # First raw point: t=0.00, x=23.032; second raw point: t=0.05, x=17.928
    # dx/dt at t=0 should be (17.928 - 23.032) / 0.05 = -102.08
    v0 = plan_df['Vel. X'].iloc[0]
    print(f"Velocity at t=0: {v0:.4f} mm/s (expected approx -102.08)")
    assert abs(v0 - (-102.08)) < 1e-2, f"Expected approx -102.08, got {v0}"

    # Verify compute_kinematics preserves the measured velocity and acceleration
    pos_cols = ['X', 'Y', 'Z']
    vel_dict, acc_dict = compute_kinematics(plan_df, pos_cols)
    np.testing.assert_allclose(vel_dict['X'], plan_df['Vel. X'].values)
    np.testing.assert_allclose(acc_dict['X'], plan_df['Acc. X'].values)
    print("compute_kinematics successfully preserves measured kinematics!")

def test_smooth_kinematics_and_axes():
    print("\n=== 2. Testing Smooth Dialog Position Axes and Recalculation ===")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    # Load log file
    sample_file = r"c:\TRACE\scratch\sample_log.txt"
    plan_df, device, matched_axes, probe_detected, orig_count, t_max = parse_trace_log_file(sample_file)

    # Create MockUI
    class MockCombo:
        def __init__(self, text):
            self._text = text
        def currentText(self):
            return self._text
        def blockSignals(self, b):
            pass
        def setCurrentText(self, t):
            self._text = t

    class MockUI:
        def __init__(self, df):
            self.dfEdit = df.copy()
            self.combo_device = MockCombo("Lung Phantom")
            self.curve_origin = 'create'
            self._curve_undo_stack = []

    mock_ui = MockUI(plan_df)
    v_orig_x = mock_ui.dfEdit['Vel. X'].copy().values
    a_orig_x = mock_ui.dfEdit['Acc. X'].copy().values
    pos_orig_x = mock_ui.dfEdit['X'].copy().values

    # Open dialog
    dlg = SmoothAxisDialog(mock_ui)

    # 1. Verify that available axes in smooth dialog ONLY contains position axes ('X', 'Y', 'Z'),
    # NOT 'Vel. X' or 'Acc. X'
    axes_in_dialog = list(dlg.axis_checkboxes.keys())
    print("Axes in Smooth dialog:", axes_in_dialog)
    assert 'X' in axes_in_dialog and 'Y' in axes_in_dialog and 'Z' in axes_in_dialog
    assert not any(ax.startswith(('Vel.', 'Acc.')) for ax in axes_in_dialog), "Vel/Acc should NOT appear in Smooth dialog!"
    print("Smooth dialog strictly displays only position axes!")

    # 2. Execute smoothing on X
    dlg.axis_checkboxes['X'].setChecked(True)
    dlg.axis_checkboxes['Y'].setChecked(False)
    dlg.axis_checkboxes['Z'].setChecked(False)
    dlg.spin_level.setValue(5)
    dlg.execute_smoothing()

    # Position must be modified by smoothing
    pos_new_x = mock_ui.dfEdit['X'].values
    assert not np.allclose(pos_new_x, pos_orig_x), "Position X was not smoothed!"
    print("Position X successfully smoothed!")

    # Velocity and Acceleration must be recalculated from the smoothed position
    v_new_x = mock_ui.dfEdit['Vel. X'].values
    a_new_x = mock_ui.dfEdit['Acc. X'].values
    assert not np.allclose(v_new_x, v_orig_x), "Velocity X was not recalculated!"
    assert not np.allclose(a_new_x, a_orig_x), "Acceleration X was not recalculated!"

    # Verify that v_new_x matches np.gradient of pos_new_x
    t = mock_ui.dfEdit['time'].values
    expected_v = np.gradient(pos_new_x, t)
    expected_a = np.gradient(expected_v, t)
    np.testing.assert_allclose(v_new_x, expected_v, rtol=1e-5, atol=1e-5)
    np.testing.assert_allclose(a_new_x, expected_a, rtol=1e-5, atol=1e-5)
    print("Velocity and acceleration successfully recalculated from smoothed position and time!")

    # 3. Test Undo
    dlg.execute_undo()
    np.testing.assert_allclose(mock_ui.dfEdit['X'].values, pos_orig_x)
    np.testing.assert_allclose(mock_ui.dfEdit['Vel. X'].values, v_orig_x)
    np.testing.assert_allclose(mock_ui.dfEdit['Acc. X'].values, a_orig_x)
    print("Undo successfully restored original position, velocity, and acceleration!")

def test_smooth_dialog_single_open_guard():
    print("\n=== 3. Testing Single-Open Re-entrancy Guard ===")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    class MockUI:
        def __init__(self):
            self._smooth_dialog_open = True  # Simulating dialog is already open

    mock_ui = MockUI()
    # Calling open_smooth_axes_dialog while _smooth_dialog_open is True should return immediately
    open_smooth_axes_dialog(mock_ui)
    assert mock_ui._smooth_dialog_open == True
    print("Re-entrancy guard prevented duplicate opening successfully!")

if __name__ == "__main__":
    test_log_import_kinematics()
    test_smooth_kinematics_and_axes()
    test_smooth_dialog_single_open_guard()
    print("\nALL VERIFICATION TESTS COMPLETED SUCCESSFULLY!")
