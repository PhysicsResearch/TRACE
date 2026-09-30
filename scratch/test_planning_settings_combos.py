import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import json
import tempfile

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTabWidget

# Ensure QApplication exists
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from fcn_create_gui.tab_planning import build_planning_tab, setup_settings_persistence

class DummyWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.tab_planning = QWidget(self)
        self.tabWidget = QTabWidget(self)
        self.tabWidget.addTab(self.tab_planning, "Planning")
        build_planning_tab(self)

def test_planning_settings_combos():
    win = DummyWindow()

    # 1. Verify existence of Lung Phantom dropdowns
    assert hasattr(win, 'combo_phantom_max_speed'), "Missing combo_phantom_max_speed"
    assert hasattr(win, 'combo_phantom_acc'), "Missing combo_phantom_acc"
    assert hasattr(win, 'combo_phantom_jerk'), "Missing combo_phantom_jerk"

    # Verify options for Lung Phantom
    phantom_speed_opts = [win.combo_phantom_max_speed.itemText(i) for i in range(win.combo_phantom_max_speed.count())]
    phantom_acc_opts = [win.combo_phantom_acc.itemText(i) for i in range(win.combo_phantom_acc.count())]
    phantom_jerk_opts = [win.combo_phantom_jerk.itemText(i) for i in range(win.combo_phantom_jerk.count())]

    assert phantom_speed_opts == ["10", "20", "30", "50"], f"Unexpected phantom speed options: {phantom_speed_opts}"
    assert phantom_acc_opts == ["500", "1000", "1500", "3000"], f"Unexpected phantom acc options: {phantom_acc_opts}"
    assert phantom_jerk_opts == ["300", "600", "900", "1200"], f"Unexpected phantom jerk options: {phantom_jerk_opts}"

    # 2. Verify existence of Motion Platform dropdowns
    assert hasattr(win, 'combo_platform_max_speed'), "Missing combo_platform_max_speed"
    assert hasattr(win, 'combo_platform_acc'), "Missing combo_platform_acc"
    assert hasattr(win, 'combo_platform_jerk'), "Missing combo_platform_jerk"

    # Verify options for Motion Platform
    platform_speed_opts = [win.combo_platform_max_speed.itemText(i) for i in range(win.combo_platform_max_speed.count())]
    platform_acc_opts = [win.combo_platform_acc.itemText(i) for i in range(win.combo_platform_acc.count())]
    platform_jerk_opts = [win.combo_platform_jerk.itemText(i) for i in range(win.combo_platform_jerk.count())]

    assert platform_speed_opts == ["10", "20", "30", "50"], f"Unexpected platform speed options: {platform_speed_opts}"
    assert platform_acc_opts == ["500", "1000", "1500", "3000"], f"Unexpected platform acc options: {platform_acc_opts}"
    assert platform_jerk_opts == ["300", "600", "900", "1200"], f"Unexpected platform jerk options: {platform_jerk_opts}"

    # 3. Verify .value() compatibility
    win.combo_phantom_max_speed.setCurrentText("30")
    assert win.combo_phantom_max_speed.value() == 30.0
    win.combo_phantom_acc.setCurrentText("1500")
    assert win.combo_phantom_acc.value() == 1500.0
    win.combo_phantom_jerk.setCurrentText("900")
    assert win.combo_phantom_jerk.value() == 900.0

    # 4. Verify independence between Lung Phantom and Motion Platform
    win.combo_phantom_max_speed.setCurrentText("10")
    win.combo_platform_max_speed.setCurrentText("50")
    assert win.combo_phantom_max_speed.currentText() == "10"
    assert win.combo_platform_max_speed.currentText() == "50"

    win.combo_phantom_acc.setCurrentText("500")
    win.combo_platform_acc.setCurrentText("3000")
    assert win.combo_phantom_acc.currentText() == "500"
    assert win.combo_platform_acc.currentText() == "3000"

    win.combo_phantom_jerk.setCurrentText("300")
    win.combo_platform_jerk.setCurrentText("1200")
    assert win.combo_phantom_jerk.currentText() == "300"
    assert win.combo_platform_jerk.currentText() == "1200"

    # 5. Verify persistence in configuration.json
    from fcn_init.app_config import get_config_path
    cfg_file = get_config_path('configuration.json', for_writing=False)
    with open(cfg_file, 'r') as f:
        data = json.load(f)

    assert data.get('phantom_max_speed') == "10", f"Config phantom_max_speed was: {data.get('phantom_max_speed')}"
    assert data.get('platform_max_speed') == "50", f"Config platform_max_speed was: {data.get('platform_max_speed')}"
    assert data.get('phantom_acc') == "500", f"Config phantom_acc was: {data.get('phantom_acc')}"
    assert data.get('platform_acc') == "3000", f"Config platform_acc was: {data.get('platform_acc')}"
    assert data.get('phantom_jerk') == "300", f"Config phantom_jerk was: {data.get('phantom_jerk')}"
    assert data.get('platform_jerk') == "1200", f"Config platform_jerk was: {data.get('platform_jerk')}"

    # 6. Verify reload persistence
    win2 = DummyWindow()
    assert win2.combo_phantom_max_speed.currentText() == "10"
    assert win2.combo_platform_max_speed.currentText() == "50"
    assert win2.combo_phantom_acc.currentText() == "500"
    assert win2.combo_platform_acc.currentText() == "3000"
    assert win2.combo_phantom_jerk.currentText() == "300"
    assert win2.combo_platform_jerk.currentText() == "1200"

    # 7. Verify device stack switching
    assert win2.settings_stack.currentIndex() == 0  # Default Lung Phantom
    win2.combo_device.setCurrentText("Motion Platform")
    assert win2.settings_stack.currentIndex() == 1  # Motion Platform page
    win2.combo_device.setCurrentText("Lung Phantom")
    assert win2.settings_stack.currentIndex() == 0  # Lung Phantom page

    # 8. Verify curve generation works cleanly with combo box values
    from fcn_plan.fcn_create import create_curve
    win2.combo_phantom_max_speed.setCurrentText("20")
    create_curve(win2)
    assert win2.dfEdit is not None
    assert len(win2.dfEdit) > 0

    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    test_planning_settings_combos()
