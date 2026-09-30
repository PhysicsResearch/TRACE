import sys
import os
from PySide6.QtWidgets import QApplication, QWidget, QSplitter
from PySide6.QtCore import Qt

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fcn_create_gui.tab_planning import build_planning_tab
from fcn_plan.fcn_create import toggle_planning_table_visibility


class MockPlanningUI(QWidget):
    def __init__(self):
        super().__init__()
        self.tab_planning = QWidget(self)


def test_planning_show_table():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    ui = MockPlanningUI()
    build_planning_tab(ui)
    ui.resize(1200, 800)
    ui.show()
    app.processEvents()

    # 1. Verify Plot High Resolution is removed
    assert not hasattr(ui, 'check_plot_high_res'), "check_plot_high_res should be removed"
    print("PASS: check_plot_high_res removed successfully!")

    # 2. Verify check_show_table exists
    assert hasattr(ui, 'check_show_table'), "check_show_table should exist on ui"
    assert ui.check_show_table.text() == "Show Table"
    print("PASS: check_show_table exists with label 'Show Table'!")

    # 3. Initially unselected by default: table hidden, speed (vel) unselected, acc unselected
    assert ui.check_show_table.isChecked() == False, "Show Table should be unselected by default"
    assert ui.create_table_view.isHidden() == True, "create_table_view should be hidden when Show Table is unselected"
    assert ui.check_show_vel.isChecked() == False, "Velocity (Speed) should be unselected by default"
    assert ui.check_show_acc.isChecked() == False, "Acceleration (Acc) should be unselected by default"
    assert ui.check_show_pos.isChecked() == True, "Position should be checked by default"
    print("PASS: Show Table, Speed (Velocity), and Acc are unselected by default; Position is selected!")

    # 4. Check Show Table: table becomes visible
    ui.check_show_table.setChecked(True)
    app.processEvents()

    assert ui.create_table_view.isHidden() == False, "create_table_view should be visible when Show Table is checked"
    print("PASS: Table visible when Show Table checked!")

    # 5. Uncheck Show Table: table hidden, bottom left settings widget extends all the way to the right
    ui.check_show_table.setChecked(False)
    app.processEvents()

    assert ui.create_table_view.isHidden() == True, "create_table_view should be hidden when Show Table is unchecked"
    splitter_w = ui.bottom_splitter.width()
    tab_w_extended = ui.create_settings_tab_widget.width()
    assert tab_w_extended >= splitter_w - 5, f"Settings widget should extend full width (~{splitter_w}), got {tab_w_extended}"
    print(f"PASS: Unchecked - Table hidden, settings widget extended full width: {tab_w_extended}px / {splitter_w}px!")

    print("\nALL PLANNING SHOW TABLE TESTS PASSED SUCCESSFULLY!")


if __name__ == '__main__':
    test_planning_show_table()
