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
    self.tabWidget_BrCv.setStyleSheet("""
        QTabBar::tab {
            font-weight: bold;
            font-size: 15px;
            padding: 8px 16px;
        }
        QGroupBox {
            font-weight: bold;
            font-size: 16px;
        }
    """)
    
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
    from PySide6.QtWidgets import QVBoxLayout, QDoubleSpinBox, QSplitter
    from PySide6.QtCore import Qt

    layout = QVBoxLayout(self.tab_create)
    layout.setContentsMargins(5, 5, 5, 5)

    # Main vertical splitter (separates top graph and bottom settings/table)
    main_splitter = QSplitter(Qt.Vertical, self.tab_create)
    layout.addWidget(main_splitter)

    # 1. Preview canvas area (Top panel)
    self.create_plot_view = QWidget(self.tab_create)
    plot_view_layout = QVBoxLayout(self.create_plot_view)
    plot_view_layout.setContentsMargins(0, 0, 0, 0)
    plot_view_layout.setSpacing(4)

    # Sub-container for canvas
    self.create_plot_canvas_container = QWidget(self.create_plot_view)
    plot_view_layout.addWidget(self.create_plot_canvas_container)

    # Sub-container for checkboxes row below the graph
    self.create_plot_checkboxes_widget = QWidget(self.create_plot_view)
    self.create_plot_checkboxes_layout = QHBoxLayout(self.create_plot_checkboxes_widget)
    self.create_plot_checkboxes_layout.setContentsMargins(10, 0, 10, 5)
    self.create_plot_checkboxes_layout.setSpacing(15)
    plot_view_layout.addWidget(self.create_plot_checkboxes_widget)

    main_splitter.addWidget(self.create_plot_view)

    # 2. Bottom panel: horizontal splitter (separates settings and table)
    bottom_splitter = QSplitter(Qt.Horizontal, self.tab_create)
    main_splitter.addWidget(bottom_splitter)

    # Options Tab Widget (Bottom Left panel)
    from PySide6.QtWidgets import QTabWidget, QStackedWidget
    self.create_settings_tab_widget = QTabWidget(self.tab_create)
    self.create_settings_tab_widget.setStyleSheet("QTabBar::tab { font-weight: bold; font-size: 13px; padding: 6px 12px; }")
    bottom_splitter.addWidget(self.create_settings_tab_widget)

    # Curve Tab Setup
    curve_tab_widget = QWidget(self.create_settings_tab_widget)
    curve_tab_layout = QVBoxLayout(curve_tab_widget)
    curve_tab_layout.setContentsMargins(5, 5, 5, 5)
    
    self.groupBox_BrCv_createCurve = QGroupBox("Curve Options", curve_tab_widget)
    gb_layout = QVBoxLayout(self.groupBox_BrCv_createCurve)
    gb_layout.setContentsMargins(15, 10, 15, 10)
    curve_tab_layout.addWidget(self.groupBox_BrCv_createCurve)
    
    self.create_settings_tab_widget.addTab(curve_tab_widget, "Curve")

    # Tools Tab Setup (Empty for now)
    tools_tab_widget = QWidget(self.create_settings_tab_widget)
    tools_tab_layout = QVBoxLayout(tools_tab_widget)
    tools_tab_layout.addStretch()
    self.create_settings_tab_widget.addTab(tools_tab_widget, "Tools")

    # Settings Tab Setup
    settings_tab_widget = QWidget(self.create_settings_tab_widget)
    settings_tab_layout = QVBoxLayout(settings_tab_widget)
    settings_tab_layout.setContentsMargins(15, 15, 15, 15)
    settings_tab_layout.setSpacing(10)

    # Settings: Device Type Selector
    lbl_set_dev = QLabel("Device Type:", settings_tab_widget)
    lbl_set_dev.setStyleSheet("font-weight: bold; font-size: 14px;")
    self.combo_settings_device = QComboBox(settings_tab_widget)
    self.combo_settings_device.setMinimumHeight(40)
    self.combo_settings_device.addItems(["Lung Phantom", "Motion Platform"])
    settings_tab_layout.addWidget(lbl_set_dev)
    settings_tab_layout.addWidget(self.combo_settings_device)

    # Settings: Stacked Layout
    self.settings_stack = QStackedWidget(settings_tab_widget)
    settings_tab_layout.addWidget(self.settings_stack)

    # Page 0: Lung Phantom settings
    lung_page = QWidget(self.settings_stack)
    lung_layout = QGridLayout(lung_page)
    lung_layout.setSpacing(10)
    lung_layout.setContentsMargins(0, 5, 0, 5)

    def add_setting_spinbox(layout, label_text, default_val, row, col):
        lbl = QLabel(label_text, lung_page)
        lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        sp = QDoubleSpinBox(lung_page)
        sp.setRange(0.1, 1000.0)
        sp.setValue(default_val)
        sp.setDecimals(1)
        sp.setMinimumHeight(38)
        
        sub_v = QVBoxLayout()
        sub_v.setSpacing(2)
        sub_v.addWidget(lbl)
        sub_v.addWidget(sp)
        layout.addLayout(sub_v, row, col)
        return sp

    self.settings_max_lim_x = add_setting_spinbox(lung_layout, "Max Lim. X (mm):", 40.0, 0, 0)
    self.settings_max_lim_y = add_setting_spinbox(lung_layout, "Max Lim. Y (mm):", 40.0, 0, 1)
    self.settings_max_lim_z = add_setting_spinbox(lung_layout, "Max Lim. Z (mm):", 40.0, 1, 0)
    self.settings_max_speed = add_setting_spinbox(lung_layout, "Max. Speed (mm/s):", 50.0, 1, 1)
    self.settings_stack.addWidget(lung_page)

    # Page 1: Motion Platform settings
    platform_page = QWidget(self.settings_stack)
    platform_layout = QGridLayout(platform_page)
    platform_layout.setSpacing(10)
    platform_layout.setContentsMargins(0, 5, 0, 5)

    def add_platform_spinbox(layout, label_text, default_val, row, col):
        lbl = QLabel(label_text, platform_page)
        lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        sp = QDoubleSpinBox(platform_page)
        sp.setRange(0.1, 1000.0)
        sp.setValue(default_val)
        sp.setDecimals(1)
        sp.setMinimumHeight(38)
        
        sub_v = QVBoxLayout()
        sub_v.setSpacing(2)
        sub_v.addWidget(lbl)
        sub_v.addWidget(sp)
        layout.addLayout(sub_v, row, col)
        return sp

    self.settings_max_lim_lat = add_platform_spinbox(platform_layout, "Max Lim. LAT (mm):", 40.0, 0, 0)
    self.settings_max_lim_si = add_platform_spinbox(platform_layout, "Max Lim. SI (mm):", 40.0, 0, 1)
    self.settings_max_lim_ap = add_platform_spinbox(platform_layout, "Max Lim. AP (mm):", 40.0, 1, 0)
    self.settings_max_lim_roll = add_platform_spinbox(platform_layout, "Max Lim. Roll (deg):", 40.0, 1, 1)
    self.settings_max_lim_pitch = add_platform_spinbox(platform_layout, "Max Lim. Pitch (deg):", 40.0, 2, 0)
    self.settings_max_lim_yaw = add_platform_spinbox(platform_layout, "Max Lim. Yaw (deg):", 40.0, 2, 1)
    self.settings_stack.addWidget(platform_page)

    # Connect settings dropdown selection to stack switch
    def update_settings_device_sync(text):
        self.combo_device.blockSignals(True)
        self.combo_device.setCurrentText(text)
        self.combo_device.blockSignals(False)
        update_axis_dropdown()

    self.combo_settings_device.currentTextChanged.connect(update_settings_device_sync)
    settings_tab_layout.addStretch()
    self.create_settings_tab_widget.addTab(settings_tab_widget, "Settings")

    grid_inputs = QGridLayout()
    grid_inputs.setSpacing(10)
    gb_layout.addLayout(grid_inputs)

    # Helper to add label + widget to grid
    def add_field(label_text, widget, row, col):
        lbl = QLabel(label_text, self.groupBox_BrCv_createCurve)
        lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        sub_lay = QVBoxLayout()
        sub_lay.setSpacing(2)
        sub_lay.addWidget(lbl)
        sub_lay.addWidget(widget)
        
        grid_inputs.addLayout(sub_lay, row, col)
        return lbl

    # 1. Device Type, Axis, Function Type (Row 0)
    self.combo_device = QComboBox(self.groupBox_BrCv_createCurve)
    self.combo_device.setMinimumHeight(40)
    self.combo_device.addItems(["Lung Phantom", "Motion Platform"])
    add_field("Device Type:", self.combo_device, 0, 0)

    self.combo_axis = QComboBox(self.groupBox_BrCv_createCurve)
    self.combo_axis.setMinimumHeight(40)
    add_field("Axis:", self.combo_axis, 0, 1)

    self.combo_func_type = QComboBox(self.groupBox_BrCv_createCurve)
    self.combo_func_type.setMinimumHeight(40)
    self.combo_func_type.addItems(["sin", "cos", "cos^1", "cos^2", "constant"])
    add_field("Function Type:", self.combo_func_type, 0, 2)

    # Helper function to dynamically update axes
    def update_axis_dropdown():
        self.combo_axis.clear()
        device = self.combo_device.currentText()
        if device == "Lung Phantom":
            self.combo_axis.addItems(["X", "Y", "Z"])
        else:
            self.combo_axis.addItems(["LAT", "SI", "AP", "Roll", "Pitch", "Yaw"])
        
        # Synchronize Settings tab dropdown & stack view
        if hasattr(self, 'combo_settings_device'):
            self.combo_settings_device.blockSignals(True)
            self.combo_settings_device.setCurrentText(device)
            self.combo_settings_device.blockSignals(False)
        if hasattr(self, 'settings_stack'):
            if device == "Lung Phantom":
                self.settings_stack.setCurrentIndex(0)
            else:
                self.settings_stack.setCurrentIndex(1)
        
        from fcn_plan.fcn_create import initialize_default_curve_data
        initialize_default_curve_data(self)

    self.combo_device.currentTextChanged.connect(update_axis_dropdown)

    # 2. Amplitude, Amp. offset, Period (Row 1)
    self.input_amplitude = QDoubleSpinBox(self.groupBox_BrCv_createCurve)
    self.input_amplitude.setRange(0.0, 1000.0)
    self.input_amplitude.setValue(10.0)
    self.input_amplitude.setDecimals(2)
    self.input_amplitude.setMinimumHeight(40)
    self.label_amplitude = add_field("Amplitude (mm):", self.input_amplitude, 1, 0)

    self.input_amp_offset = QDoubleSpinBox(self.groupBox_BrCv_createCurve)
    self.input_amp_offset.setRange(-1000.0, 1000.0)
    self.input_amp_offset.setValue(0.0)
    self.input_amp_offset.setDecimals(2)
    self.input_amp_offset.setMinimumHeight(40)
    self.label_amp_offset = add_field("Amp. offset (mm):", self.input_amp_offset, 1, 1)

    self.input_period = QDoubleSpinBox(self.groupBox_BrCv_createCurve)
    self.input_period.setRange(0.1, 1000.0)
    self.input_period.setValue(4.0)
    self.input_period.setDecimals(2)
    self.input_period.setMinimumHeight(40)
    add_field("Period (s):", self.input_period, 1, 2)

    # 3. Starting Phase, Start Time, End Time (Row 2)
    self.input_phase = QDoubleSpinBox(self.groupBox_BrCv_createCurve)
    self.input_phase.setRange(-360.0, 360.0)
    self.input_phase.setValue(0.0)
    self.input_phase.setDecimals(2)
    self.input_phase.setMinimumHeight(40)
    add_field("Starting Phase (deg):", self.input_phase, 2, 0)

    self.input_start_time = QDoubleSpinBox(self.groupBox_BrCv_createCurve)
    self.input_start_time.setRange(0.0, 10000.0)
    self.input_start_time.setValue(0.0)
    self.input_start_time.setDecimals(2)
    self.input_start_time.setMinimumHeight(40)
    add_field("Start Time (s):", self.input_start_time, 2, 1)

    self.input_end_time = QDoubleSpinBox(self.groupBox_BrCv_createCurve)
    self.input_end_time.setRange(0.1, 10000.0)
    self.input_end_time.setValue(20.0)
    self.input_end_time.setDecimals(2)
    self.input_end_time.setMinimumHeight(40)
    add_field("End Time (s):", self.input_end_time, 2, 2)

    # Connect axis change listener to dynamically modify labels and enable/disable offset inputs
    def update_axis_labels_and_state(axis):
        if not axis:
            return
        if axis in ["Roll", "Pitch", "Yaw"]:
            self.label_amplitude.setText("Amplitude (deg):")
            self.input_amp_offset.setEnabled(False)
            self.input_amp_offset.setValue(0.0)
        else:
            self.label_amplitude.setText("Amplitude (mm):")
            self.input_amp_offset.setEnabled(True)

    self.combo_axis.currentTextChanged.connect(update_axis_labels_and_state)

    self.button_create_curve = QPushButton("Add Curve", self.groupBox_BrCv_createCurve)
    self.button_create_curve.setMinimumHeight(45)
    self.button_create_curve.setStyleSheet("""
        QPushButton {
            background-color: #2e7d32;
            color: white;
            font-weight: bold;
            font-size: 16px;
            border-radius: 6px;
        }
        QPushButton:hover {
            background-color: #1b5e20;
        }
    """)
    gb_layout.addWidget(self.button_create_curve)

    # 6. Wait Radiation Section
    wait_rad_layout = QHBoxLayout()
    wait_rad_layout.setSpacing(10)

    self.input_wait_rad_time = QDoubleSpinBox(self.groupBox_BrCv_createCurve)
    self.input_wait_rad_time.setRange(0.0, 10000.0)
    self.input_wait_rad_time.setValue(10.0)
    self.input_wait_rad_time.setDecimals(2)
    self.input_wait_rad_time.setMinimumHeight(40)
    
    lbl_wait_time = QLabel("Time (s):", self.groupBox_BrCv_createCurve)
    lbl_wait_time.setStyleSheet("font-weight: bold; font-size: 14px;")
    
    wait_time_vlay = QVBoxLayout()
    wait_time_vlay.setSpacing(2)
    wait_time_vlay.addWidget(lbl_wait_time)
    wait_time_vlay.addWidget(self.input_wait_rad_time)
    wait_rad_layout.addLayout(wait_time_vlay)

    self.button_wait_radiation = QPushButton("Wait Radiation", self.groupBox_BrCv_createCurve)
    self.button_wait_radiation.setMinimumHeight(40)
    self.button_wait_radiation.setStyleSheet("""
        QPushButton {
            background-color: #d84315;
            color: white;
            font-weight: bold;
            font-size: 15px;
            border-radius: 6px;
            padding: 0px 15px;
        }
        QPushButton:hover {
            background-color: #bf360c;
        }
    """)

    self.button_wait_user = QPushButton("Wait User", self.groupBox_BrCv_createCurve)
    self.button_wait_user.setMinimumHeight(40)
    self.button_wait_user.setStyleSheet("""
        QPushButton {
            background-color: #fbc02d;
            color: black;
            font-weight: bold;
            font-size: 15px;
            border-radius: 6px;
            padding: 0px 15px;
        }
        QPushButton:hover {
            background-color: #f57f17;
        }
    """)

    self.button_clear_rad = QPushButton("Clear Rad Pauses", self.groupBox_BrCv_createCurve)
    self.button_clear_rad.setMinimumHeight(40)
    self.button_clear_rad.setStyleSheet("""
        QPushButton {
            background-color: #ffebee;
            color: #d84315;
            font-weight: bold;
            font-size: 14px;
            border: 1px solid #d84315;
            border-radius: 6px;
            padding: 0px 10px;
        }
        QPushButton:hover {
            background-color: #ffcdd2;
        }
    """)

    self.button_clear_user = QPushButton("Clear Usr Pauses", self.groupBox_BrCv_createCurve)
    self.button_clear_user.setMinimumHeight(40)
    self.button_clear_user.setStyleSheet("""
        QPushButton {
            background-color: #fffde7;
            color: #f57f17;
            font-weight: bold;
            font-size: 14px;
            border: 1px solid #fbc02d;
            border-radius: 6px;
            padding: 0px 10px;
        }
        QPushButton:hover {
            background-color: #fff9c4;
        }
    """)

    # Align buttons vertically with input
    wait_buttons_layout = QHBoxLayout()
    wait_buttons_layout.setSpacing(10)
    wait_buttons_layout.addWidget(self.button_wait_radiation)
    wait_buttons_layout.addWidget(self.button_wait_user)
    wait_buttons_layout.addWidget(self.button_clear_rad)
    wait_buttons_layout.addWidget(self.button_clear_user)

    wait_button_vlay = QVBoxLayout()
    wait_button_vlay.setSpacing(2)
    wait_button_vlay.addWidget(QLabel("", self.groupBox_BrCv_createCurve))
    wait_button_vlay.addLayout(wait_buttons_layout)
    wait_rad_layout.addLayout(wait_button_vlay)
    wait_rad_layout.addStretch()

    gb_layout.addLayout(wait_rad_layout)
    gb_layout.addStretch()

    # Table View (Bottom Right panel)
    self.create_table_view = QTableWidget(self.tab_create)
    bottom_splitter.addWidget(self.create_table_view)

    # Set splitter initial sizes (e.g. 50% top, 50% bottom; 30% settings, 70% table)
    main_splitter.setSizes([400, 400])
    bottom_splitter.setSizes([280, 620])

    # Initial trigger to populate axis and default curve data
    update_axis_dropdown()


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
