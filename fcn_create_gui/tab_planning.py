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
    self.combo_settings_device.addItems(["Lung Phantom", "Motion Platform", "Other"])
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
    self.combo_device.addItems(["Lung Phantom", "Motion Platform", "Other"])
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
        elif device == "Motion Platform":
            self.combo_axis.addItems(["LAT", "SI", "AP", "Roll", "Pitch", "Yaw"])
        else: # Other
            # Add all columns present in self.dfEdit excluding timestamp, time, Command
            exclude_cols = {'timestamp', 'time', 'Command'}
            cols = [col for col in getattr(self, 'dfEdit', type('Mock', (), {'columns': []})()).columns if col not in exclude_cols]
            self.combo_axis.addItems(cols)
        
        # Synchronize Settings tab dropdown & stack view
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

    create_buttons_layout.addWidget(self.button_create_curve)
    create_buttons_layout.addWidget(self.button_import_gcode)
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
    update_axis_dropdown()
