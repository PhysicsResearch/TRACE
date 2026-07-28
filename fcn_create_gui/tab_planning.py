"""
Planning Tab creation for TRACE GUI
Constructs sub-tabs for Create, Import, Edit, and Export & visualize curves with lazy sub-tab loading.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox,
    QCheckBox, QSlider, QTextEdit, QTableWidget, QTabWidget, QLabel
)

def build_planning_tab(self):
    """Populate self.tab_planning with sub-tab widget container."""
    layout_main = QVBoxLayout(self.tab_planning)
    layout_main.setContentsMargins(5, 5, 5, 5)

    self.tabWidget_BrCv = QTabWidget(self.tab_planning)
    
    # Sub-tab pages (placeholders for lazy loading)
    self.tab_create = QWidget()
    self.tab_import = QWidget()
    self.tab_edit = QWidget()
    self.tab_export = QWidget()

    self.tabWidget_BrCv.addTab(self.tab_create, "Create ")
    self.tabWidget_BrCv.addTab(self.tab_import, "Import")
    self.tabWidget_BrCv.addTab(self.tab_edit, "Edit")
    self.tabWidget_BrCv.addTab(self.tab_export, "Export & visualize")

    layout_main.addWidget(self.tabWidget_BrCv)

    # Initialize sub-tab loaded tracking set
    self._loaded_subtabs = set()

    # Connect currentChanged for lazy loading of sub-tabs
    self.tabWidget_BrCv.currentChanged.connect(lambda idx: on_subtab_changed(self, idx))

    # Build initial sub-tab 0 ("Create") immediately
    build_create_subtab(self)
    self._loaded_subtabs.add(0)


def on_subtab_changed(self, index):
    """Lazy load sub-tabs inside Planning tab on first click."""
    if index in self._loaded_subtabs:
        return

    if index == 1:
        build_import_subtab(self)
    elif index == 2:
        build_edit_subtab(self)
    elif index == 3:
        build_export_subtab(self)

    self._loaded_subtabs.add(index)


def build_create_subtab(self):
    """Build 'Create' sub-tab inside Planning."""
    layout = QGridLayout(self.tab_create)

    # Preview canvas area
    self.create_plot_view = QWidget(self.tab_create)
    layout.addWidget(self.create_plot_view, 0, 0, 1, 2)

    # Options group
    self.groupBox_BrCv_createCurve = QGroupBox("Curve Options", self.tab_create)
    gb_layout = QGridLayout(self.groupBox_BrCv_createCurve)

    gb_layout.addWidget(QLabel("Curve Type:"), 0, 0)
    self.create_curve_type = QComboBox(self.groupBox_BrCv_createCurve)
    gb_layout.addWidget(self.create_curve_type, 0, 1)

    gb_layout.addWidget(QLabel("Sample Freq (Hz):"), 1, 0)
    self.create_sample_freq = QSpinBox(self.groupBox_BrCv_createCurve)
    self.create_sample_freq.setRange(1, 1000)
    self.create_sample_freq.setValue(100)
    gb_layout.addWidget(self.create_sample_freq, 1, 1)

    self.create_add_row = QPushButton("+ Add Row", self.groupBox_BrCv_createCurve)
    self.create_remove_row = QPushButton("- Remove Row", self.groupBox_BrCv_createCurve)
    self.button_create_curve = QPushButton("Create Curve", self.groupBox_BrCv_createCurve)

    gb_layout.addWidget(self.create_add_row, 2, 0)
    gb_layout.addWidget(self.create_remove_row, 2, 1)
    gb_layout.addWidget(self.button_create_curve, 3, 0, 1, 2)

    layout.addWidget(self.groupBox_BrCv_createCurve, 1, 0)

    # Analytical Table
    self.create_table = QTableWidget(self.groupBox_BrCv_createCurve)
    gb_layout.addWidget(self.create_table, 4, 0, 1, 2)

    self.create_table_view = QTableWidget(self.tab_create)
    layout.addWidget(self.create_table_view, 1, 1)


def build_import_subtab(self):
    """Build 'Import' sub-tab inside Planning."""
    layout = QGridLayout(self.tab_import)

    self.groupBox_BrCv_importCSV = QGroupBox("CSV Import Parameters", self.tab_import)
    gb_layout = QGridLayout(self.groupBox_BrCv_importCSV)

    gb_layout.addWidget(QLabel("Delimiter:"), 0, 0)
    self.import_delimiter = QComboBox(self.groupBox_BrCv_importCSV)
    gb_layout.addWidget(self.import_delimiter, 0, 1)

    gb_layout.addWidget(QLabel("Header Line:"), 1, 0)
    self.import_header_line = QSpinBox(self.groupBox_BrCv_importCSV)
    gb_layout.addWidget(self.import_header_line, 1, 1)

    gb_layout.addWidget(QLabel("Skip Lines:"), 2, 0)
    self.import_skip_lines = QSpinBox(self.groupBox_BrCv_importCSV)
    gb_layout.addWidget(self.import_skip_lines, 2, 1)

    gb_layout.addWidget(QLabel("Time Unit:"), 3, 0)
    self.import_time_unit = QComboBox(self.groupBox_BrCv_importCSV)
    gb_layout.addWidget(self.import_time_unit, 3, 1)

    self.import_flip = QCheckBox("Flip Signal", self.groupBox_BrCv_importCSV)
    gb_layout.addWidget(self.import_flip, 4, 0, 1, 2)

    self.import_button = QPushButton("Import CSV", self.groupBox_BrCv_importCSV)
    gb_layout.addWidget(self.import_button, 5, 0, 1, 2)

    layout.addWidget(self.groupBox_BrCv_importCSV, 0, 0)

    # Preview Text & Table
    self.import_text_view = QTextEdit(self.tab_import)
    self.import_table_view = QTableWidget(self.tab_import)

    layout.addWidget(self.import_text_view, 0, 1)
    layout.addWidget(self.import_table_view, 1, 0, 1, 2)


def build_edit_subtab(self):
    """Build 'Edit' sub-tab inside Planning."""
    layout = QGridLayout(self.tab_edit)

    # Editing Plot Canvas
    self.edit_ax_view = QWidget(self.tab_edit)
    layout.addWidget(self.edit_ax_view, 0, 0, 1, 4)

    # Range Sliders
    layout.addWidget(QLabel("X Min:"), 1, 0)
    self.slider_edit_xmin = QSlider(Qt.Horizontal, self.tab_edit)
    layout.addWidget(self.slider_edit_xmin, 1, 1)

    layout.addWidget(QLabel("X Max:"), 1, 2)
    self.slider_edit_xmax = QSlider(Qt.Horizontal, self.tab_edit)
    layout.addWidget(self.slider_edit_xmax, 1, 3)

    # Operations Groups
    # 1. Drift Group
    self.groupBox_drift = QGroupBox("Drift Adjustment", self.tab_edit)
    d_layout = QGridLayout(self.groupBox_drift)
    self.value_drift = QDoubleSpinBox(self.groupBox_drift)
    self.button_add_drift = QPushButton("Add Drift", self.groupBox_drift)
    self.button_remove_drift = QPushButton("Remove Drift", self.groupBox_drift)
    d_layout.addWidget(self.value_drift, 0, 0, 1, 2)
    d_layout.addWidget(self.button_add_drift, 1, 0)
    d_layout.addWidget(self.button_remove_drift, 1, 1)
    layout.addWidget(self.groupBox_drift, 2, 0)

    # 2. Breathhold Group
    self.breathhold_BrCv = QGroupBox("Breathhold", self.tab_edit)
    bh_layout = QGridLayout(self.breathhold_BrCv)
    self.breathholdDuration = QDoubleSpinBox(self.breathhold_BrCv)
    self.button_breath_hold = QPushButton("Apply Breathhold", self.breathhold_BrCv)
    self.closest_max = QCheckBox("Closest Max", self.breathhold_BrCv)
    self.closest_min = QCheckBox("Closest Min", self.breathhold_BrCv)
    bh_layout.addWidget(self.breathholdDuration, 0, 0, 1, 2)
    bh_layout.addWidget(self.closest_max, 1, 0)
    bh_layout.addWidget(self.closest_min, 1, 1)
    bh_layout.addWidget(self.button_breath_hold, 2, 0, 1, 2)
    layout.addWidget(self.breathhold_BrCv, 2, 1)

    # 3. Amplitude & Frequency Ops Group
    self.groupBox_operations = QGroupBox("Scaling & Shifting", self.tab_edit)
    op_layout = QGridLayout(self.groupBox_operations)
    
    self.value_ampl_sf = QDoubleSpinBox(self.groupBox_operations)
    self.button_scale_ampl = QPushButton("Scale Ampl", self.groupBox_operations)
    op_layout.addWidget(self.value_ampl_sf, 0, 0)
    op_layout.addWidget(self.button_scale_ampl, 0, 1)

    self.value_ampl_shift = QDoubleSpinBox(self.groupBox_operations)
    self.button_shift_ampl = QPushButton("Shift Ampl", self.groupBox_operations)
    op_layout.addWidget(self.value_ampl_shift, 1, 0)
    op_layout.addWidget(self.button_shift_ampl, 1, 1)

    self.button_zero_ampl = QPushButton("Zero Min", self.groupBox_operations)
    self.button_clip_ampl = QPushButton("Clip Ampl", self.groupBox_operations)
    self.value_ampl_min = QDoubleSpinBox(self.groupBox_operations)
    self.value_ampl_max = QDoubleSpinBox(self.groupBox_operations)
    op_layout.addWidget(self.value_ampl_min, 2, 0)
    op_layout.addWidget(self.value_ampl_max, 2, 1)
    op_layout.addWidget(self.button_zero_ampl, 3, 0)
    op_layout.addWidget(self.button_clip_ampl, 3, 1)

    self.value_freq_sf = QDoubleSpinBox(self.groupBox_operations)
    self.button_scale_freq = QPushButton("Scale Freq", self.groupBox_operations)
    op_layout.addWidget(self.value_freq_sf, 4, 0)
    op_layout.addWidget(self.button_scale_freq, 4, 1)

    layout.addWidget(self.groupBox_operations, 2, 2)

    # 4. Smoothing Group
    self.groupBox_smoothing = QGroupBox("Smoothing", self.tab_edit)
    sm_layout = QGridLayout(self.groupBox_smoothing)
    self.smooth_method = QComboBox(self.groupBox_smoothing)
    self.smooth_kernel = QSpinBox(self.groupBox_smoothing)
    self.threshFourierSlider = QSlider(Qt.Horizontal, self.groupBox_smoothing)
    self.threshFourierValue = QLineEdit(self.groupBox_smoothing)
    self.button_apply_smooth = QPushButton("Apply Smooth", self.groupBox_smoothing)
    sm_layout.addWidget(QLabel("Method:"), 0, 0)
    sm_layout.addWidget(self.smooth_method, 0, 1)
    sm_layout.addWidget(QLabel("Kernel:"), 1, 0)
    sm_layout.addWidget(self.smooth_kernel, 1, 1)
    sm_layout.addWidget(QLabel("Fourier Cutoff:"), 2, 0)
    sm_layout.addWidget(self.threshFourierSlider, 2, 1)
    sm_layout.addWidget(self.threshFourierValue, 3, 0)
    sm_layout.addWidget(self.button_apply_smooth, 3, 1)
    layout.addWidget(self.groupBox_smoothing, 2, 3)

    # Undo & Crop Buttons
    self.edit_undo = QPushButton("Undo", self.tab_edit)
    self.edit_undo.setStyleSheet("background-color: red; color: white;")
    self.button_clip_cycles = QPushButton("Crop Range", self.tab_edit)

    layout.addWidget(self.edit_undo, 3, 0, 1, 2)
    layout.addWidget(self.button_clip_cycles, 3, 2, 1, 2)


def build_export_subtab(self):
    """Build 'Export & visualize' sub-tab inside Planning."""
    layout = QGridLayout(self.tab_export)

    # Export Plot View
    self.plot_view = QWidget(self.tab_export)
    layout.addWidget(self.plot_view, 0, 0, 1, 2)

    # Stats Group
    self.groupBox_7 = QGroupBox("Statistics", self.tab_export)
    st_layout = QVBoxLayout(self.groupBox_7)
    self.calcStats = QPushButton("Calculate Stats", self.groupBox_7)
    st_layout.addWidget(self.calcStats)
    layout.addWidget(self.groupBox_7, 1, 0)

    # Export Parameters Group
    self.export_BrCv = QGroupBox("Export Parameters", self.tab_export)
    ex_layout = QGridLayout(self.export_BrCv)

    ex_layout.addWidget(QLabel("Filename:"), 0, 0)
    self.export_filename = QLineEdit(self.export_BrCv)
    ex_layout.addWidget(self.export_filename, 0, 1)

    self.interp_export = QCheckBox("Interpolate", self.export_BrCv)
    self.interp_export_value = QDoubleSpinBox(self.export_BrCv)
    ex_layout.addWidget(self.interp_export, 1, 0)
    ex_layout.addWidget(self.interp_export_value, 1, 1)

    ex_layout.addWidget(QLabel("Compress Speed:"), 2, 0)
    self.compress_speed = QDoubleSpinBox(self.export_BrCv)
    ex_layout.addWidget(self.compress_speed, 2, 1)

    ex_layout.addWidget(QLabel("Repeat Copies:"), 3, 0)
    self.n_copy_curve = QSpinBox(self.export_BrCv)
    ex_layout.addWidget(self.n_copy_curve, 3, 1)

    self.exportCSV = QPushButton("Export CSV", self.export_BrCv)
    self.exportGCODE = QPushButton("Export G-code", self.export_BrCv)
    ex_layout.addWidget(self.exportCSV, 4, 0)
    ex_layout.addWidget(self.exportGCODE, 4, 1)

    layout.addWidget(self.export_BrCv, 1, 1)

    # Plot Controls
    ctrl_layout = QHBoxLayout()
    self.plot_acq = QCheckBox("Show Acquisition", self.tab_export)
    self.plot_peaks = QCheckBox("Show Peaks", self.tab_export)
    self.plot_xaxis = QComboBox(self.tab_export)

    ctrl_layout.addWidget(self.plot_acq)
    ctrl_layout.addWidget(self.plot_peaks)
    ctrl_layout.addWidget(QLabel("X-Axis:"))
    ctrl_layout.addWidget(self.plot_xaxis)

    layout.addLayout(ctrl_layout, 2, 0, 1, 2)
