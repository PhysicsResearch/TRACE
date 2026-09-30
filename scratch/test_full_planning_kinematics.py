import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, r"c:\TRACE")

from PySide6.QtWidgets import QApplication, QWidget, QTableWidget, QHBoxLayout, QCheckBox
import fcn_plan.fcn_create as fc

app = QApplication.instance()
if app is None:
    app = QApplication([])

class MockUI(QWidget):
    def __init__(self):
        super().__init__()
        self.create_table_view = QTableWidget(self)
        self.create_plot_checkboxes_widget = QWidget(self)
        self.create_plot_checkboxes_layout = QHBoxLayout(self.create_plot_checkboxes_widget)
        self.create_plot_canvas_container = QWidget(self)

        t = np.linspace(0, 10, 1001)
        self.dfEdit = pd.DataFrame({
            'timestamp': t * 1000.0,
            'time': t,
            'X': 25.0 * np.cos(2 * np.pi * t / 4.0)**6,
            'Y': 25.0 * np.sin(2 * np.pi * t / 4.0),
            'Z': np.zeros_like(t),
            'Command': [''] * len(t)
        })
        self.dfEdit_lung_phantom = self.dfEdit

mock = MockUI()

print("--- 1. Testing rebuild_axis_checkboxes ---")
fc.rebuild_axis_checkboxes(mock, ['X', 'Y', 'Z'])
assert hasattr(mock, 'check_show_pos'), "check_show_pos missing"
assert hasattr(mock, 'check_show_vel'), "check_show_vel missing"
assert hasattr(mock, 'check_show_acc'), "check_show_acc missing"
print("Kinematic checkboxes created successfully!")
print(f"Position checked: {mock.check_show_pos.isChecked()}")
print(f"Velocity checked: {mock.check_show_vel.isChecked()}")
print(f"Acceleration checked: {mock.check_show_acc.isChecked()}")

print("\n--- 2. Testing loadTable_create ---")
fc.loadTable_create(mock, mock.dfEdit)
cols = [mock.create_table_view.horizontalHeaderItem(i).text() for i in range(mock.create_table_view.columnCount())]
print(f"Table columns ({len(cols)}):", cols)

expected_headers = [
    'Time (s)', 'X (mm)', 'Y (mm)', 'Z (mm)',
    'Vel. X (mm/s)', 'Vel. Y (mm/s)', 'Vel. Z (mm/s)',
    'Acc. X (mm/s²)', 'Acc. Y (mm/s²)', 'Acc. Z (mm/s²)',
    'Command'
]
assert cols == expected_headers, f"Expected {expected_headers}, got {cols}"
print("Table columns match exact requested order and naming!")

print("\n--- 3. Testing sync_table_column_visibility ---")
# Check initial visibility (all visible)
for i, name in enumerate(cols):
    assert not mock.create_table_view.isColumnHidden(i), f"Column {name} should be visible"
print("All columns visible initially.")

# Uncheck Acceleration
mock.check_show_acc.setChecked(False)
fc.sync_table_column_visibility(mock)
for i, name in enumerate(cols):
    if name.startswith('Acc.'):
        assert mock.create_table_view.isColumnHidden(i), f"Column {name} should be hidden when Acc is unchecked"
    else:
        assert not mock.create_table_view.isColumnHidden(i), f"Column {name} should remain visible"
print("Acc columns hidden when check_show_acc is unchecked!")

# Uncheck Velocity
mock.check_show_vel.setChecked(False)
fc.sync_table_column_visibility(mock)
for i, name in enumerate(cols):
    if name.startswith('Vel.') or name.startswith('Acc.'):
        assert mock.create_table_view.isColumnHidden(i), f"Column {name} should be hidden"
    else:
        assert not mock.create_table_view.isColumnHidden(i), f"Column {name} should remain visible"
print("Vel & Acc columns hidden when both unchecked!")

# Re-check Velocity
mock.check_show_vel.setChecked(True)
fc.sync_table_column_visibility(mock)
for i, name in enumerate(cols):
    if name.startswith('Vel.'):
        assert not mock.create_table_view.isColumnHidden(i), f"Column {name} should be visible"
    elif name.startswith('Acc.'):
        assert mock.create_table_view.isColumnHidden(i), f"Column {name} should still be hidden"
print("Vel columns re-shown when checked!")

print("\n--- 4. Testing update_plot line styles ---")
fc.update_plot(mock, mock.dfEdit, ['X', 'Y'])
lines = mock.create_plot_ax.get_lines()
print(f"Total lines plotted on canvas: {len(lines)}")
for line in lines:
    print(f"  Line: label='{line.get_label()}', linestyle='{line.get_linestyle()}', color='{line.get_color()}'")

# We expect Pos X (solid), Pos Y (solid), Vel X (dashed), Vel Y (dashed)
linestyles = {line.get_label(): line.get_linestyle() for line in lines}
assert linestyles['X (Pos)'] == '-', "Position should be continuous solid line ('-')"
assert linestyles['Y (Pos)'] == '-', "Position should be continuous solid line ('-')"
assert linestyles['X (Vel)'] == '--', "Velocity should be dashed line ('--')"
assert linestyles['Y (Vel)'] == '--', "Velocity should be dashed line ('--')"

# Now check Acceleration as well
mock.check_show_acc.setChecked(True)
fc.update_plot(mock, mock.dfEdit, ['X', 'Y'])
lines = mock.create_plot_ax.get_lines()
linestyles = {line.get_label(): line.get_linestyle() for line in lines}
print(f"After enabling acceleration: {len(lines)} lines plotted")
for line in lines:
    print(f"  Line: label='{line.get_label()}', linestyle='{line.get_linestyle()}', color='{line.get_color()}'")

assert linestyles['X (Acc)'] == ':', "Acceleration should be point/dotted line (':')"
assert linestyles['Y (Acc)'] == ':', "Acceleration should be point/dotted line (':')"

print("\nALL VERIFICATION TESTS COMPLETED SUCCESSFULLY!")
