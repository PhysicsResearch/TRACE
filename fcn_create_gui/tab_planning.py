"""
Planning Tab creation for TRACE GUI
Constructs the curve creation workspace directly inside the main Planning tab.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox,
    QCheckBox, QSlider, QTextEdit, QTableWidget, QLabel, QSplitter, QTabWidget, QStackedWidget
)

def setup_offset_sync(self):
    """Synchronizes offset rotation inputs (AP, LAT, SI) between Control tab and Planning tab."""
    if not (hasattr(self, 'input_offset_ap') and hasattr(self, 'input_offset_ap_plan')):
        return

    if getattr(self, '_offset_synced', False):
        return
    self._offset_synced = True

    # Initialize Planning tab fields with Control tab values
    self.input_offset_ap_plan.setText(self.input_offset_ap.text())
    self.input_offset_lat_plan.setText(self.input_offset_lat.text())
    self.input_offset_si_plan.setText(self.input_offset_si.text())

    def sync_ap_ctl(text):
        self.input_offset_ap_plan.blockSignals(True)
        self.input_offset_ap_plan.setText(text)
        self.input_offset_ap_plan.blockSignals(False)

    def sync_ap_plan(text):
        self.input_offset_ap.blockSignals(True)
        self.input_offset_ap.setText(text)
        self.input_offset_ap.blockSignals(False)

    def sync_lat_ctl(text):
        self.input_offset_lat_plan.blockSignals(True)
        self.input_offset_lat_plan.setText(text)
        self.input_offset_lat_plan.blockSignals(False)

    def sync_lat_plan(text):
        self.input_offset_lat.blockSignals(True)
        self.input_offset_lat.setText(text)
        self.input_offset_lat.blockSignals(False)

    def sync_si_ctl(text):
        self.input_offset_si_plan.blockSignals(True)
        self.input_offset_si_plan.setText(text)
        self.input_offset_si_plan.blockSignals(False)

    def sync_si_plan(text):
        self.input_offset_si.blockSignals(True)
        self.input_offset_si.setText(text)
        self.input_offset_si.blockSignals(False)

    def update_on_offset_change():
        if hasattr(self, 'combo_device') and self.combo_device.currentText() == "Motion Platform":
            from fcn_plan.fcn_create import trigger_plot_update, loadTable_create, compute_motion_platform_actuators
            if hasattr(self, 'dfEdit') and self.dfEdit is not None:
                self.dfEdit = compute_motion_platform_actuators(self, self.dfEdit)
                self.dfEdit_motion_platform = self.dfEdit
                loadTable_create(self, self.dfEdit)
            trigger_plot_update(self)

    self.input_offset_ap.textChanged.connect(sync_ap_ctl)
    self.input_offset_ap_plan.textChanged.connect(sync_ap_plan)
    self.input_offset_ap_plan.textChanged.connect(lambda t: update_on_offset_change())

    self.input_offset_lat.textChanged.connect(sync_lat_ctl)
    self.input_offset_lat_plan.textChanged.connect(sync_lat_plan)
    self.input_offset_lat_plan.textChanged.connect(lambda t: update_on_offset_change())

    self.input_offset_si.textChanged.connect(sync_si_ctl)
    self.input_offset_si_plan.textChanged.connect(sync_si_plan)
    self.input_offset_si_plan.textChanged.connect(lambda t: update_on_offset_change())


def build_planning_tab(self):
    """Build 'Create' interface directly inside self.tab_planning."""
    
    # Apply larger styling for QGroupBox titles
    self.tab_planning.setStyleSheet("""
        QGroupBox {
            font-weight: bold;
            font-size: 16px;
        }
    """)

    layout = QVBoxLayout(self.tab_planning)
    layout.setContentsMargins(5, 5, 5, 5)

    # Main vertical splitter (separates top graph and bottom settings/table)
    main_splitter = QSplitter(Qt.Vertical, self.tab_planning)
    layout.addWidget(main_splitter)

    # 1. Preview canvas area (Top panel)
    self.create_plot_view = QWidget(self.tab_planning)
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
    bottom_splitter = QSplitter(Qt.Horizontal, self.tab_planning)
    main_splitter.addWidget(bottom_splitter)

    # Options Tab Widget (Bottom Left panel)
    self.create_settings_tab_widget = QTabWidget(self.tab_planning)
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

    # Tools Tab Setup
    tools_tab_widget = QWidget(self.create_settings_tab_widget)
    tools_tab_layout = QVBoxLayout(tools_tab_widget)
    tools_tab_layout.setContentsMargins(15, 15, 15, 15)
    tools_tab_layout.setSpacing(15)

    gb_axis_tools = QGroupBox("Axis Data Operations", tools_tab_widget)
    gb_axis_tools_layout = QVBoxLayout(gb_axis_tools)
    gb_axis_tools_layout.setContentsMargins(15, 15, 15, 15)
    gb_axis_tools_layout.setSpacing(10)

    lbl_tools_desc = QLabel("Copy motion curve data from one source axis to multiple destination axes simultaneously.", gb_axis_tools)
    lbl_tools_desc.setWordWrap(True)
    lbl_tools_desc.setStyleSheet("font-size: 13px; color: #555555;")
    gb_axis_tools_layout.addWidget(lbl_tools_desc)

    self.btn_copy_axis_to = QPushButton("Copy Axis To...", gb_axis_tools)
    self.btn_copy_axis_to.setMinimumHeight(45)
    self.btn_copy_axis_to.setStyleSheet("""
        QPushButton {
            background-color: #1976d2;
            color: white;
            font-weight: bold;
            font-size: 15px;
            border-radius: 6px;
            padding: 0px 15px;
        }
        QPushButton:hover {
            background-color: #1565c0;
        }
    """)
    gb_axis_tools_layout.addWidget(self.btn_copy_axis_to)

    from fcn_plan.fcn_create import open_copy_axis_dialog
    self.btn_copy_axis_to.clicked.connect(lambda: open_copy_axis_dialog(self))

    gb_time_tools = QGroupBox("Time Interval Operations", tools_tab_widget)
    gb_time_tools_layout = QVBoxLayout(gb_time_tools)
    gb_time_tools_layout.setContentsMargins(15, 15, 15, 15)
    gb_time_tools_layout.setSpacing(10)

    lbl_time_desc = QLabel("Crop to keep only a specific interval or Trim to remove a specific interval from the motion curve.", gb_time_tools)
    lbl_time_desc.setWordWrap(True)
    lbl_time_desc.setStyleSheet("font-size: 13px; color: #555555;")
    gb_time_tools_layout.addWidget(lbl_time_desc)

    time_btn_lay = QHBoxLayout()
    time_btn_lay.setSpacing(10)

    self.btn_crop_interval = QPushButton("Crop Interval...", gb_time_tools)
    self.btn_crop_interval.setMinimumHeight(45)
    self.btn_crop_interval.setStyleSheet("""
        QPushButton {
            background-color: #2e7d32;
            color: white;
            font-weight: bold;
            font-size: 15px;
            border-radius: 6px;
        }
        QPushButton:hover {
            background-color: #1b5e20;
        }
    """)

    self.btn_trim_interval = QPushButton("Trim Interval...", gb_time_tools)
    self.btn_trim_interval.setMinimumHeight(45)
    self.btn_trim_interval.setStyleSheet("""
        QPushButton {
            background-color: #c62828;
            color: white;
            font-weight: bold;
            font-size: 15px;
            border-radius: 6px;
        }
        QPushButton:hover {
            background-color: #b71c1c;
        }
    """)

    from fcn_plan.fcn_create import open_crop_interval_dialog, open_trim_interval_dialog
    self.btn_crop_interval.clicked.connect(lambda: open_crop_interval_dialog(self))
    self.btn_trim_interval.clicked.connect(lambda: open_trim_interval_dialog(self))

    time_btn_lay.addWidget(self.btn_crop_interval)
    time_btn_lay.addWidget(self.btn_trim_interval)
    gb_time_tools_layout.addLayout(time_btn_lay)

    gb_math_tools = QGroupBox("Mathematical Operations", tools_tab_widget)
    gb_math_tools_layout = QVBoxLayout(gb_math_tools)
    gb_math_tools_layout.setContentsMargins(15, 15, 15, 15)
    gb_math_tools_layout.setSpacing(10)

    lbl_math_desc = QLabel("Apply mathematical operations (Offset, Multiply, Divide, Invert) to entire curves or specific segments across selected axes.", gb_math_tools)
    lbl_math_desc.setWordWrap(True)
    lbl_math_desc.setStyleSheet("font-size: 13px; color: #555555;")
    gb_math_tools_layout.addWidget(lbl_math_desc)

    self.btn_math_operations = QPushButton("Math Operations...", gb_math_tools)
    self.btn_math_operations.setMinimumHeight(45)
    self.btn_math_operations.setStyleSheet("""
        QPushButton {
            background-color: #5e35b1;
            color: white;
            font-weight: bold;
            font-size: 15px;
            border-radius: 6px;
            padding: 0px 15px;
        }
        QPushButton:hover {
            background-color: #4527a0;
        }
    """)
    gb_math_tools_layout.addWidget(self.btn_math_operations)

    from fcn_plan.fcn_create import open_math_operations_dialog
    self.btn_math_operations.clicked.connect(lambda: open_math_operations_dialog(self))

    tools_tab_layout.addWidget(gb_axis_tools)
    tools_tab_layout.addWidget(gb_time_tools)
    tools_tab_layout.addWidget(gb_math_tools)
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
    self.settings_max_speed_plat = add_platform_spinbox(platform_layout, "Max Speed (mm/s):", 20.0, 3, 0)
    self.settings_stack.addWidget(platform_page)

    # Page 2: Other device settings (simple info label)
    other_page = QWidget(self.settings_stack)
    other_layout = QVBoxLayout(other_page)
    other_lbl = QLabel("Custom G-code axes mode active.\nEuclidean velocity scaling will be used.", other_page)
    other_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #1565c0;")
    other_layout.addWidget(other_lbl)
    other_layout.addStretch()
    self.settings_stack.addWidget(other_page)

    # Connect settings dropdown selection to stack switch
    def update_settings_device_sync(text):
        self.combo_device.blockSignals(True)
        self.combo_device.setCurrentText(text)
        self.combo_device.blockSignals(False)
        if hasattr(self, 'axis_checkboxes_layout'):
            update_axis_checkboxes()

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

    # 1. Device Type & Function Type (Row 0)
    self.combo_device = QComboBox(self.groupBox_BrCv_createCurve)
    self.combo_device.setMinimumHeight(40)
    self.combo_device.addItems(["Lung Phantom", "Motion Platform"])
    add_field("Device Type:", self.combo_device, 0, 0)

    self.combo_func_type = QComboBox(self.groupBox_BrCv_createCurve)
    self.combo_func_type.setMinimumHeight(40)
    self.combo_func_type.addItems(["sin", "cos", "cos^1", "cos^2", "constant", "linear"])
    add_field("Function Type:", self.combo_func_type, 0, 1)

    # 2. Amplitude, Amp. offset, Period (Row 1)
    self.input_amplitude = QDoubleSpinBox(self.groupBox_BrCv_createCurve)
    self.input_amplitude.setRange(-1000.0, 1000.0)
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
    self.input_period.setRange(0.01, 1000.0)
    self.input_period.setValue(4.0)
    self.input_period.setDecimals(2)
    self.input_period.setMinimumHeight(40)
    self.label_period = add_field("Period (s):", self.input_period, 1, 2)

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

    # 4. Offset Rot. (mm) Section (Row 3, below Starting Phase)
    # Visible only when "Motion Platform" is selected
    from fcn_create_gui.touch_keyboard import register_touch_line_edit

    self.offset_rot_widget = QWidget(self.groupBox_BrCv_createCurve)
    offset_grid = QGridLayout(self.offset_rot_widget)
    offset_grid.setContentsMargins(0, 5, 0, 0)
    offset_grid.setSpacing(10)

    # Single Label Row (Row 0): "Offset Rot. (mm):" on the left, then AP:, LAT:, SI: in their respective columns
    lbl_off_title = QLabel("Offset Rot. (mm):", self.offset_rot_widget)
    lbl_off_title.setStyleSheet("font-weight: bold; font-size: 14px;")

    lbl_off_ap = QLabel("AP:", self.offset_rot_widget)
    lbl_off_ap.setStyleSheet("font-weight: bold; font-size: 14px;")

    col0_lbl_lay = QHBoxLayout()
    col0_lbl_lay.setContentsMargins(0, 0, 0, 0)
    col0_lbl_lay.addWidget(lbl_off_title)
    col0_lbl_lay.addStretch()
    col0_lbl_lay.addWidget(lbl_off_ap)
    offset_grid.addLayout(col0_lbl_lay, 0, 0)

    lbl_off_lat = QLabel("LAT:", self.offset_rot_widget)
    lbl_off_lat.setStyleSheet("font-weight: bold; font-size: 14px;")

    col1_lbl_lay = QHBoxLayout()
    col1_lbl_lay.setContentsMargins(0, 0, 0, 0)
    col1_lbl_lay.addStretch()
    col1_lbl_lay.addWidget(lbl_off_lat)
    offset_grid.addLayout(col1_lbl_lay, 0, 1)

    lbl_off_si = QLabel("SI:", self.offset_rot_widget)
    lbl_off_si.setStyleSheet("font-weight: bold; font-size: 14px;")

    col2_lbl_lay = QHBoxLayout()
    col2_lbl_lay.setContentsMargins(0, 0, 0, 0)
    col2_lbl_lay.addStretch()
    col2_lbl_lay.addWidget(lbl_off_si)
    offset_grid.addLayout(col2_lbl_lay, 0, 2)

    # Input Fields Row (Row 1): Input fields aligned with columns 0, 1, 2
    input_style_plan = """
        QLineEdit {
            background-color: #ffffff;
            font-weight: bold;
            font-size: 14px;
            border: 1px solid #b0bec5;
            border-radius: 4px;
            padding: 4px 8px;
        }
        QLineEdit:focus {
            border: 2px solid #1976d2;
        }
    """

    self.input_offset_ap_plan = QLineEdit("0.0", self.offset_rot_widget)
    self.input_offset_ap_plan.setStyleSheet(input_style_plan)
    self.input_offset_ap_plan.setMinimumHeight(40)
    register_touch_line_edit(self, self.input_offset_ap_plan, label_name="Offset AP (mm)")
    offset_grid.addWidget(self.input_offset_ap_plan, 1, 0)

    self.input_offset_lat_plan = QLineEdit("0.0", self.offset_rot_widget)
    self.input_offset_lat_plan.setStyleSheet(input_style_plan)
    self.input_offset_lat_plan.setMinimumHeight(40)
    register_touch_line_edit(self, self.input_offset_lat_plan, label_name="Offset LAT (mm)")
    offset_grid.addWidget(self.input_offset_lat_plan, 1, 1)

    self.input_offset_si_plan = QLineEdit("0.0", self.offset_rot_widget)
    self.input_offset_si_plan.setStyleSheet(input_style_plan)
    self.input_offset_si_plan.setMinimumHeight(40)
    register_touch_line_edit(self, self.input_offset_si_plan, label_name="Offset SI (mm)")
    offset_grid.addWidget(self.input_offset_si_plan, 1, 2)

    grid_inputs.addWidget(self.offset_rot_widget, 3, 0, 1, 3)

    # 5. Axis Selection Checkboxes (Row 4)
    self.axis_selection_widget = QWidget(self.groupBox_BrCv_createCurve)
    axis_sec_lay = QVBoxLayout(self.axis_selection_widget)
    axis_sec_lay.setContentsMargins(0, 5, 0, 0)
    axis_sec_lay.setSpacing(4)

    lbl_axis_title = QLabel("Axis:", self.axis_selection_widget)
    lbl_axis_title.setStyleSheet("font-weight: bold; font-size: 14px;")
    axis_sec_lay.addWidget(lbl_axis_title)

    self.axis_checkboxes_layout = QHBoxLayout()
    self.axis_checkboxes_layout.setSpacing(15)
    axis_sec_lay.addLayout(self.axis_checkboxes_layout)

    grid_inputs.addWidget(self.axis_selection_widget, 4, 0, 1, 3)

    # Set initial visibility based on selected device
    self.offset_rot_widget.setVisible(self.combo_device.currentText() == "Motion Platform")

    # Connect tab synchronization
    setup_offset_sync(self)

    # Dynamic label and state updater
    def update_curve_input_labels():
        func_type = self.combo_func_type.currentText()
        rotational_axes = {"Roll", "Pitch", "Yaw"}

        is_rotational = False
        if hasattr(self, 'create_curve_axis_checkboxes'):
            for rot_ax in rotational_axes:
                cb = self.create_curve_axis_checkboxes.get(rot_ax)
                if cb and cb.isChecked():
                    is_rotational = True
                    break

        if func_type == "linear":
            if hasattr(self, 'label_amplitude'):
                self.label_amplitude.setText("Initial pos (deg):" if is_rotational else "Initial pos (mm):")
            if hasattr(self, 'label_amp_offset'):
                self.label_amp_offset.setText("Final pos (deg):" if is_rotational else "Final pos (mm):")
            if hasattr(self, 'label_period'):
                self.label_period.setText("Duration (s):")
            if hasattr(self, 'input_amp_offset'):
                self.input_amp_offset.setEnabled(True)
            if hasattr(self, 'input_start_time') and hasattr(self, 'input_period') and hasattr(self, 'input_end_time'):
                self.input_end_time.blockSignals(True)
                self.input_end_time.setValue(round(self.input_start_time.value() + self.input_period.value(), 3))
                self.input_end_time.blockSignals(False)
        else:
            if hasattr(self, 'label_amplitude'):
                self.label_amplitude.setText("Amplitude (deg):" if is_rotational else "Amplitude (mm):")
            if hasattr(self, 'label_amp_offset'):
                self.label_amp_offset.setText("Amp. offset (mm):")
            if hasattr(self, 'label_period'):
                self.label_period.setText("Period (s):")
            if hasattr(self, 'input_amp_offset'):
                if is_rotational:
                    self.input_amp_offset.setEnabled(False)
                    self.input_amp_offset.setValue(0.0)
                else:
                    self.input_amp_offset.setEnabled(True)

    def update_axis_checkboxes():
        if hasattr(self, 'axis_checkboxes_layout') and self.axis_checkboxes_layout is not None:
            while self.axis_checkboxes_layout.count():
                child = self.axis_checkboxes_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        self.create_curve_axis_checkboxes = {}
        device = self.combo_device.currentText()

        if device == "Lung Phantom":
            axes_list = [("X", True), ("Y", False), ("Z", False)]
        elif device == "Motion Platform":
            axes_list = [
                ("SI", True), ("LAT", False), ("AP", False),
                ("Roll", False), ("Pitch", False), ("Yaw", False)
            ]
        else:
            exclude_cols = {'timestamp', 'time', 'Command'}
            cols = [col for col in getattr(self, 'dfEdit', type('Mock', (), {'columns': []})()).columns if col not in exclude_cols]
            axes_list = [(c, i == 0) for i, c in enumerate(cols)]

        linear_axes = {"SI", "LAT", "AP", "X", "Y", "Z"}
        rotational_axes = {"Roll", "Pitch", "Yaw"}

        def on_axis_toggled(changed_axis, is_checked):
            if is_checked:
                if changed_axis in linear_axes:
                    for rot_ax in rotational_axes:
                        cb_rot = self.create_curve_axis_checkboxes.get(rot_ax)
                        if cb_rot and cb_rot.isChecked():
                            cb_rot.blockSignals(True)
                            cb_rot.setChecked(False)
                            cb_rot.blockSignals(False)
                elif changed_axis in rotational_axes:
                    for lin_ax in linear_axes:
                        cb_lin = self.create_curve_axis_checkboxes.get(lin_ax)
                        if cb_lin and cb_lin.isChecked():
                            cb_lin.blockSignals(True)
                            cb_lin.setChecked(False)
                            cb_lin.blockSignals(False)
            update_curve_input_labels()

        for ax_name, default_check in axes_list:
            cb = QCheckBox(ax_name, self.axis_selection_widget)
            cb.setStyleSheet("font-weight: bold; font-size: 14px;")
            cb.setChecked(default_check)
            if ax_name == "Yaw":
                cb.setEnabled(False)
                cb.setToolTip("Yaw is currently disabled")

            cb.toggled.connect(lambda chk, a=ax_name: on_axis_toggled(a, chk))
            self.axis_checkboxes_layout.addWidget(cb)
            self.create_curve_axis_checkboxes[ax_name] = cb

        self.axis_checkboxes_layout.addStretch()

        if hasattr(self, 'offset_rot_widget'):
            self.offset_rot_widget.setVisible(device == "Motion Platform")

        if hasattr(self, 'combo_settings_device'):
            self.combo_settings_device.blockSignals(True)
            self.combo_settings_device.setCurrentText(device)
            self.combo_settings_device.blockSignals(False)
        if hasattr(self, 'settings_stack'):
            if device == "Lung Phantom":
                self.settings_stack.setCurrentIndex(0)
            elif device == "Motion Platform":
                self.settings_stack.setCurrentIndex(1)
            else:
                self.settings_stack.setCurrentIndex(2)

        if hasattr(self, 'create_table_view'):
            from fcn_plan.fcn_create import initialize_default_curve_data
            initialize_default_curve_data(self)
        update_curve_input_labels()

    self.combo_device.currentTextChanged.connect(update_axis_checkboxes)
    self.combo_func_type.currentTextChanged.connect(lambda _: update_curve_input_labels())

    def sync_linear_duration_to_end_time():
        if self.combo_func_type.currentText() == "linear":
            self.input_end_time.blockSignals(True)
            self.input_end_time.setValue(round(self.input_start_time.value() + self.input_period.value(), 3))
            self.input_end_time.blockSignals(False)

    def sync_linear_end_time_to_duration():
        if self.combo_func_type.currentText() == "linear":
            dur = max(0.01, round(self.input_end_time.value() - self.input_start_time.value(), 3))
            self.input_period.blockSignals(True)
            self.input_period.setValue(dur)
            self.input_period.blockSignals(False)

    self.input_period.valueChanged.connect(sync_linear_duration_to_end_time)
    self.input_start_time.valueChanged.connect(sync_linear_duration_to_end_time)
    self.input_end_time.valueChanged.connect(sync_linear_end_time_to_duration)

    # Action layout for Add Curve and Import G-code buttons
    create_buttons_layout = QHBoxLayout()
    create_buttons_layout.setSpacing(15)

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

    self.button_import_gcode = QPushButton("Import G-code", self.groupBox_BrCv_createCurve)
    self.button_import_gcode.setMinimumHeight(45)
    self.button_import_gcode.setStyleSheet("""
        QPushButton {
            background-color: #0d47a1;
            color: white;
            font-weight: bold;
            font-size: 16px;
            border-radius: 6px;
        }
        QPushButton:hover {
            background-color: #0a3780;
        }
    """)

    self.button_clear_all = QPushButton("Clear All", self.groupBox_BrCv_createCurve)
    self.button_clear_all.setMinimumHeight(45)
    self.button_clear_all.setStyleSheet("""
        QPushButton {
            background-color: #c62828;
            color: white;
            font-weight: bold;
            font-size: 16px;
            border-radius: 6px;
        }
        QPushButton:hover {
            background-color: #b71c1c;
        }
    """)

    create_buttons_layout.addWidget(self.button_create_curve)
    create_buttons_layout.addWidget(self.button_import_gcode)
    create_buttons_layout.addWidget(self.button_clear_all)
    gb_layout.addLayout(create_buttons_layout)

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
    self.create_table_view = QTableWidget(self.tab_planning)
    from fcn_plan.fcn_create import on_table_item_changed
    self.create_table_view.itemChanged.connect(lambda item: on_table_item_changed(self, item))
    bottom_splitter.addWidget(self.create_table_view)

    # Set splitter initial sizes (e.g. 50% top, 50% bottom; 30% settings, 70% table)
    main_splitter.setSizes([400, 400])
    bottom_splitter.setSizes([280, 620])

    # Initial trigger to populate axis and default curve data
    update_axis_checkboxes()

    # Automatic settings persistence across sessions
    setup_settings_persistence(self)


def setup_settings_persistence(self):
    """Loads saved settings from configuration.json and connects change listeners for automatic persistence."""
    import json
    from fcn_init.app_config import get_config_path

    spinbox_map = {
        'max_speed': getattr(self, 'settings_max_speed_plat', None) or getattr(self, 'settings_max_speed', None),
        'max_lim_lat': getattr(self, 'settings_max_lim_lat', None),
        'max_lim_si': getattr(self, 'settings_max_lim_si', None),
        'max_lim_ap': getattr(self, 'settings_max_lim_ap', None),
        'max_lim_roll': getattr(self, 'settings_max_lim_roll', None),
        'max_lim_pitch': getattr(self, 'settings_max_lim_pitch', None),
        'max_lim_yaw': getattr(self, 'settings_max_lim_yaw', None),
        'max_lim_x': getattr(self, 'settings_max_lim_x', None),
        'max_lim_y': getattr(self, 'settings_max_lim_y', None),
        'max_lim_z': getattr(self, 'settings_max_lim_z', None),
    }

    # Load existing config data
    config_data = {}
    try:
        config_path = get_config_path('configuration.json', for_writing=False)
        with open(config_path, 'r') as f:
            config_data = json.load(f)
    except Exception:
        config_data = {}

    # Set initial values from config if present
    for key, sb in spinbox_map.items():
        if sb is not None and key in config_data:
            try:
                val = float(config_data[key])
                sb.blockSignals(True)
                sb.setValue(val)
                sb.blockSignals(False)
            except (ValueError, TypeError):
                pass

    # Function to save updated settings back to configuration.json
    def save_current_settings():
        try:
            cfg_file = get_config_path('configuration.json', for_writing=False)
            existing_data = {}
            try:
                with open(cfg_file, 'r') as f:
                    existing_data = json.load(f)
            except Exception:
                existing_data = {}

            for key, sb in spinbox_map.items():
                if sb is not None:
                    existing_data[key] = sb.value()

            write_file = get_config_path('configuration.json', for_writing=True)
            with open(write_file, 'w') as f:
                json.dump(existing_data, f, indent=4)
        except Exception as e:
            print(f"Error saving planning settings to configuration.json: {e}")

    # Connect valueChanged listeners
    for sb in spinbox_map.values():
        if sb is not None:
            sb.valueChanged.connect(lambda v: save_current_settings())
