"""
Status Tab creation for TRACE GUI
Constructs Duet Web-style Status Dashboard card, real-time interactive position plot vs time,
data logging configuration (with desktop default folder & automatic log naming), speed factor controls,
G-code Pause/Resume/Cancel Job, and Emergency Stop 2.
"""

import os
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QPushButton, QLabel, QSlider, QToolButton, QFrame, QProgressBar, QLineEdit, QCheckBox, QSizePolicy, QScrollArea
)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from fcn_create_gui.touch_keyboard import register_touch_line_edit


def save_status_advanced_mode(self, enabled):
    """Persists the status_advanced_mode setting to configuration.json."""
    self.status_advanced_mode = bool(enabled)
    try:
        from fcn_init.app_config import get_config_path
        import json
        cfg_path = get_config_path('configuration.json', for_writing=False)
        data = {}
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r') as f:
                data = json.load(f)
        data['status_advanced_mode'] = bool(enabled)
        write_path = get_config_path('configuration.json', for_writing=True)
        with open(write_path, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error persisting status_advanced_mode: {e}")


def update_status_axes_layout(self, is_advanced):
    """
    Arranges axes checkboxes on the right side of the status graph.
    In Basic mode:
      - Only Show reference, Show X, Show Y, Show Z, Show AP, Show LAT, Show SI, Show Pitch, Show Roll are shown.
      - A, B, C, D, 'e, 'f, 'a, 'c, Yaw are hidden.
    In Advanced mode:
      - All axes are visible.
    """
    if not hasattr(self, 'grid_checks_layout') or self.grid_checks_layout is None:
        return

    # Clear all items from the grid without destroying widgets
    while self.grid_checks_layout.count():
        item = self.grid_checks_layout.takeAt(0)
        w = item.widget()
        if w:
            self.grid_checks_layout.removeWidget(w)

    # Always row 0: Show reference spanning 2 columns
    if hasattr(self, 'check_show_reference') and self.check_show_reference is not None:
        self.check_show_reference.setVisible(True)
        self.grid_checks_layout.addWidget(self.check_show_reference, 0, 0, 1, 2)

    if not is_advanced:
        # Basic Mode: only show reference, Show X, Show Y, Show Z, Show AP, Show LAT, Show SI, Show Pitch, Show Roll
        basic_names = [
            'status_check_X', 'status_check_Y',
            'status_check_Z', 'status_check_AP',
            'status_check_LAT', 'status_check_SI',
            'status_check_Pitch', 'status_check_Roll'
        ]
        for idx, attr in enumerate(basic_names):
            cb = getattr(self, attr, None)
            if cb is not None:
                cb.setVisible(True)
                row = (idx // 2) + 1
                col = idx % 2
                self.grid_checks_layout.addWidget(cb, row, col)

        # Hide all advanced axes
        advanced_names = [
            'status_check_A', 'status_check_B',
            'status_check_C', 'status_check_D',
            'status_check_e', 'status_check_f',
            'status_check_a', 'status_check_c',
            'status_check_Yaw'
        ]
        for attr in advanced_names:
            cb = getattr(self, attr, None)
            if cb is not None:
                cb.setVisible(False)
    else:
        # Advanced Mode: all 17 axes visible in 2 columns
        all_names = [
            'status_check_X', 'status_check_Y',
            'status_check_Z', 'status_check_A',
            'status_check_B', 'status_check_C',
            'status_check_D', 'status_check_e',
            'status_check_f', 'status_check_a',
            'status_check_c', 'status_check_Roll',
            'status_check_Pitch', 'status_check_Yaw',
            'status_check_LAT', 'status_check_AP',
            'status_check_SI'
        ]
        for idx, attr in enumerate(all_names):
            cb = getattr(self, attr, None)
            if cb is not None:
                cb.setVisible(True)
                row = (idx // 2) + 1
                col = idx % 2
                self.grid_checks_layout.addWidget(cb, row, col)


def apply_status_advanced_mode(self, is_advanced):
    """
    Toggles visibility of Status tab elements based on Basic vs Advanced mode:
    - In Basic mode:
      * Speeds row (Req, Top, Probe) and Position row (all 14 axes) are hidden.
      * Log output folder row and all elements (except Clear Plot Data) are hidden.
      * Axes visualization checkboxes only show: Show reference, Show X, Show Y, Show Z, Show AP, Show LAT, Show SI, Show Pitch, Show Roll.
        (A, B, C, D, 'e, 'a, 'c, 'f, Yaw are hidden).
    - In Advanced mode:
      * All above elements are visible.
    """
    # 0. Header speed controls and pause/release checkboxes
    if hasattr(self, 'speed_controls_container') and self.speed_controls_container is not None:
        self.speed_controls_container.setVisible(is_advanced)

    # 1. Speeds and Positions rows
    if hasattr(self, 'metrics_container') and self.metrics_container is not None:
        self.metrics_container.setVisible(is_advanced)

    # 2. Log Output Folder row elements (excluding Clear Plot Data)
    if hasattr(self, 'log_folder_container') and self.log_folder_container is not None:
        self.log_folder_container.setVisible(is_advanced)

    # 3. Checkboxes layout and visibility
    update_status_axes_layout(self, is_advanced)

    # 4. Trigger plot update so hidden axes are not rendered
    try:
        from fcn_monitor.fcn_duet import render_status_plot
        render_status_plot(self)
    except Exception:
        pass


def build_status_tab(self):
    """Populate self.tab_status with Status tab widgets, Dashboard, Real-Time Plot, and Data Logger."""
    layout_main = QVBoxLayout(self.tab_status)
    layout_main.setContentsMargins(10, 4, 10, 4)
    layout_main.setSpacing(6)

    # --- 1. DWC-STYLE DASHBOARD CARD ---
    self.card_status = QGroupBox("", self.tab_status)
    self.card_status.setStyleSheet("""
        QGroupBox {
            border: 1px solid #cfd8dc;
            border-radius: 6px;
            background-color: #ffffff;
            margin-top: 5px;
        }
    """)
    card_layout = QVBoxLayout(self.card_status)
    card_layout.setContentsMargins(10, 10, 10, 10)
    card_layout.setSpacing(18)

    # Header Row: Status Badge, Pause/Resume/Stop, & Emergency STOP button (right-aligned)
    hdr_layout = QHBoxLayout()
    hdr_label = QLabel("Status:", self.card_status)
    hdr_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #455a64;")

    self.statusBadgeLabel = QLabel("Idle", self.card_status)
    self.statusBadgeLabel.setStyleSheet("""
        QLabel {
            background-color: #2196f3;
            color: white;
            font-weight: bold;
            font-size: 15px;
            border-radius: 8px;
            padding: 3px 10px;
        }
    """)

    # GCode Start / Pause / Resume / Stop Job Buttons (Uniformly Sized to match Emergency STOP height)
    self.gcodeStart = QPushButton("Start", self.card_status)
    self.gcodeStart.setFixedSize(85, 38)
    self.gcodeStart.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; font-size: 14px; border-radius: 4px;")

    self.gcodePause = QPushButton("Pause", self.card_status)
    self.gcodePause.setFixedSize(85, 38)
    self.gcodePause.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold; font-size: 14px; border-radius: 4px;")

    self.gcodeResume = QPushButton("Resume", self.card_status)
    self.gcodeResume.setFixedSize(85, 38)
    self.gcodeResume.setStyleSheet("background-color: #4caf50; color: white; font-weight: bold; font-size: 14px; border-radius: 4px;")

    self.gcodeStopJob = QPushButton("Stop", self.card_status)
    self.gcodeStopJob.setFixedSize(85, 38)
    self.gcodeStopJob.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold; font-size: 14px; border-radius: 4px;")

    self.gcodeReleaseWait = QPushButton("Release", self.card_status)
    self.gcodeReleaseWait.setFixedSize(85, 38)
    self.gcodeReleaseWait.setStyleSheet("background-color: #0288d1; color: white; font-weight: bold; font-size: 14px; border-radius: 4px;")

    # Connect buttons
    from fcn_monitor.fcn_duet import pause_continue_GCODE, cancel_GCODE_job, start_selected_gcode_execution, release_sensor_wait_action
    self.gcodeStart.clicked.connect(lambda: start_selected_gcode_execution(self))
    self.gcodePause.clicked.connect(lambda: pause_continue_GCODE(self, pause=True))
    self.gcodeResume.clicked.connect(lambda: pause_continue_GCODE(self, pause=False))
    self.gcodeStopJob.clicked.connect(lambda: cancel_GCODE_job(self))
    self.gcodeReleaseWait.clicked.connect(lambda: release_sensor_wait_action(self))

    self.emergencyButton_2 = QPushButton("Emergency STOP", self.card_status)
    self.emergencyButton_2.setStyleSheet("background-color: red; color: white; font-weight: bold; font-size: 15px; border-radius: 4px;")
    self.emergencyButton_2.setFixedSize(160, 38)

    # Column 2 (Right): Speed Factor controls (Label + Editable QLineEdit + min/plus buttons)
    sf_hlayout = QHBoxLayout()
    sf_hlayout.setSpacing(6)

    label_sf = QLabel("Speed Factor:")
    label_sf.setStyleSheet("font-weight: bold; font-size: 14px; color: #455a64;")

    self.labelSf = QLineEdit("100%", self.card_status)
    self.labelSf.setFixedWidth(80)
    self.labelSf.setStyleSheet("font-weight: bold; font-size: 14px; color: #2e7d32; padding: 2px;")
    
    # Restrict input to floats between 10.0 and 300.0 with up to 3 decimal places
    from PySide6.QtGui import QDoubleValidator
    validator = QDoubleValidator(10.0, 300.0, 3, self.labelSf)
    validator.setNotation(QDoubleValidator.StandardNotation)
    self.labelSf.setValidator(validator)
    register_touch_line_edit(self, self.labelSf, label_name="Speed Factor")

    self.minSf = QToolButton(self.card_status)
    self.minSf.setText("-")
    self.minSf.setStyleSheet("background-color: blue; color: white; font-weight: bold; width: 32px; height: 32px; font-size: 16px; border-radius: 4px;")

    self.plusSf = QToolButton(self.card_status)
    self.plusSf.setText("+")
    self.plusSf.setStyleSheet("background-color: blue; color: white; font-weight: bold; width: 32px; height: 32px; font-size: 16px; border-radius: 4px;")

    # Adjust speed callback (steps of 1.0)
    if not hasattr(self, 'status_speed_factor'):
        self.status_speed_factor = 100.0

    def on_sf_edited():
        try:
            val_str = self.labelSf.text().strip().replace("%", "")
            val = float(val_str)
            self.status_speed_factor = max(10.0, min(300.0, val))
            self.labelSf.setText(f"{self.status_speed_factor:.3f}%")
            from fcn_monitor.fcn_duet import set_GCODE_speed
            set_GCODE_speed(self, self.status_speed_factor)
        except ValueError:
            self.labelSf.setText(f"{getattr(self, 'status_speed_factor', 100.0):.3f}%")

    def adjust_speed(delta):
        try:
            val_str = self.labelSf.text().strip().replace("%", "")
            val = float(val_str)
        except ValueError:
            val = float(getattr(self, 'status_speed_factor', 100.0))
        new_val = max(10.0, min(300.0, val + delta))
        self.status_speed_factor = new_val
        self.labelSf.setText(f"{new_val:.3f}%")
        from fcn_monitor.fcn_duet import set_GCODE_speed
        set_GCODE_speed(self, new_val)

    self.labelSf.returnPressed.connect(on_sf_edited)
    self.minSf.clicked.connect(lambda: adjust_speed(-1.0))
    self.plusSf.clicked.connect(lambda: adjust_speed(1.0))

    # 1. TOP ROW: Proportional 1/3 and 2/3 column layout matching the Progress Bar and Duet Message field below
    hdr_layout = QHBoxLayout()
    hdr_layout.setSpacing(15)

    # Left 1/3 column: Status badge on left, Start, Pause, Resume, Stop, Release buttons
    top_left_box = QHBoxLayout()
    top_left_box.setContentsMargins(0, 0, 0, 0)
    top_left_box.addWidget(hdr_label)
    top_left_box.addWidget(self.statusBadgeLabel)
    top_left_box.addStretch()
    top_left_box.addWidget(self.gcodeStart)
    top_left_box.addWidget(self.gcodePause)
    top_left_box.addWidget(self.gcodeResume)
    top_left_box.addWidget(self.gcodeStopJob)
    top_left_box.addWidget(self.gcodeReleaseWait)

    # Right 2/3 column: Speed Factor tightly grouped on left next to field, Auto release, Auto pause, Emergency STOP on right
    top_right_box = QHBoxLayout()
    top_right_box.setContentsMargins(0, 0, 0, 0)
    
    self.speed_controls_container = QWidget(self.card_status)
    spd_layout = QHBoxLayout(self.speed_controls_container)
    spd_layout.setContentsMargins(0, 0, 0, 0)
    spd_layout.setSpacing(12)

    sf_container = QWidget(self.speed_controls_container)
    sf_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    sf_hlayout = QHBoxLayout(sf_container)
    sf_hlayout.setContentsMargins(0, 0, 0, 0)
    sf_hlayout.setSpacing(6)
    sf_hlayout.addWidget(label_sf)
    sf_hlayout.addWidget(self.labelSf)
    sf_hlayout.addWidget(self.minSf)
    sf_hlayout.addWidget(self.plusSf)

    spd_layout.addWidget(sf_container)

    # Add Auto-sync Speed (placed just before Pre-setup, disabled by default)
    self.check_auto_sync = QCheckBox("Auto-sync Speed", self.speed_controls_container)
    self.check_auto_sync.setChecked(False)
    self.check_auto_sync.setStyleSheet("QCheckBox { font-weight: bold; font-size: 14px; color: #1565c0; }")
    spd_layout.addWidget(self.check_auto_sync)

    def on_auto_sync_toggled(enabled):
        # Disable manual speed controls when auto-sync is enabled
        self.labelSf.setEnabled(not enabled)
        self.minSf.setEnabled(not enabled)
        self.plusSf.setEnabled(not enabled)
        style = "background-color: #f5f5f5; color: #9e9e9e;" if enabled else "background-color: #ffffff; color: #0d47a1;"
        self.labelSf.setStyleSheet(f"QLineEdit {{ font-weight: bold; font-size: 14px; border: 1px solid #b0bec5; border-radius: 4px; padding: 4px; text-align: center; {style} }}")

    self.check_auto_sync.toggled.connect(on_auto_sync_toggled)

    # Add Auto release and Auto pause checkboxes
    self.check_auto_release = QCheckBox("Auto release", self.speed_controls_container)
    self.check_auto_release.setChecked(False)
    self.check_auto_release.setStyleSheet("QCheckBox { font-weight: bold; font-size: 14px; color: #37474f; }")
    spd_layout.addWidget(self.check_auto_release)

    self.check_auto_pause = QCheckBox("Auto pause", self.speed_controls_container)
    self.check_auto_pause.setChecked(False)
    self.check_auto_pause.setStyleSheet("QCheckBox { font-weight: bold; font-size: 14px; color: #37474f; }")
    spd_layout.addWidget(self.check_auto_pause)

    self.check_include_pause = QCheckBox("Include pause", self.speed_controls_container)
    self.check_include_pause.setChecked(True)
    self.check_include_pause.setStyleSheet("QCheckBox { font-weight: bold; font-size: 14px; color: #37474f; }")
    spd_layout.addWidget(self.check_include_pause)

    top_right_box.addWidget(self.speed_controls_container)
    top_right_box.addStretch()

    # Advanced Mode Checkbox placed directly on the left of Emergency STOP
    self.check_advanced_mode = QCheckBox("Advanced mode", self.card_status)
    self.check_advanced_mode.setStyleSheet("""
        QCheckBox {
            font-weight: bold;
            font-size: 14px;
            color: #37474f;
            margin-right: 6px;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
        }
    """)
    top_right_box.addWidget(self.check_advanced_mode)
    top_right_box.addSpacing(12)
    top_right_box.addWidget(self.emergencyButton_2)

    hdr_layout.addLayout(top_left_box, stretch=1)
    hdr_layout.addLayout(top_right_box, stretch=2)

    card_layout.addLayout(hdr_layout)

    # 2. HEADER TEXT ROW (ABOVE FIELDS): Print Duration & Time Remaining above Progress Bar (1/3), Duet Message label above Duet Message field (2/3)
    top_info_layout = QHBoxLayout()
    top_info_layout.setSpacing(15)

    self.labelPrintDuration = QLabel("Print Duration: --", self.card_status)
    self.labelPrintDuration.setStyleSheet("color: #616161; font-size: 14px; font-weight: bold;")
    
    self.labelTimeRemaining = QLabel("Time left: --", self.card_status)
    self.labelTimeRemaining.setStyleSheet("color: #616161; font-size: 14px; font-weight: bold;")

    lbl_msg = QLabel("Duet Message:", self.card_status)
    lbl_msg.setStyleSheet("font-size: 14px; font-weight: bold; color: #455a64;")

    # Left 1/3 column for Print Duration & Time Remaining (aligned with right end of progress bar)
    prog_info_box = QHBoxLayout()
    prog_info_box.addWidget(self.labelPrintDuration)
    prog_info_box.addStretch()
    prog_info_box.addWidget(self.labelTimeRemaining)

    # Right 2/3 column for Duet Message label
    duet_info_box = QHBoxLayout()
    duet_info_box.addWidget(lbl_msg)
    duet_info_box.addStretch()

    top_info_layout.addLayout(prog_info_box, stretch=1)
    top_info_layout.addLayout(duet_info_box, stretch=2)

    card_layout.addLayout(top_info_layout)

    # 3. INTERACTIVE FIELDS ROW: Progress bar on left (1/3 width = 0.5 of Duet message), Duet Message entry field on right (2/3 width)
    prog_duet_row = QHBoxLayout()
    prog_duet_row.setSpacing(15)

    self.printProgressBar = QProgressBar(self.card_status)
    self.printProgressBar.setRange(0, 100)
    self.printProgressBar.setValue(0)
    self.printProgressBar.setTextVisible(True)
    self.printProgressBar.setStyleSheet("""
        QProgressBar {
            border: 1px solid #b0bec5;
            border-radius: 4px;
            text-align: center;
            height: 32px;
            font-weight: bold;
        }
        QProgressBar::chunk {
            background-color: #4caf50;
            border-radius: 3px;
        }
    """)

    self.statusDuetMessage = QLineEdit("None", self.card_status)
    self.statusDuetMessage.setReadOnly(True)
    self.statusDuetMessage.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    self.statusDuetMessage.setMinimumHeight(32)
    self.statusDuetMessage.setStyleSheet("""
        QLineEdit {
            background-color: #e0f7fa;
            color: #006064;
            font-weight: bold;
            font-size: 14px;
            border: 1px solid #80deea;
            border-radius: 4px;
            padding: 2px 8px;
        }
    """)

    prog_duet_row.addWidget(self.printProgressBar, stretch=1)
    prog_duet_row.addWidget(self.statusDuetMessage, stretch=2)

    card_layout.addLayout(prog_duet_row)

    # Section: Tool Position & Speeds & Other Axes (Wrapped in metrics_container for Basic/Advanced toggle)
    self.metrics_container = QWidget(self.card_status)
    metrics_grid = QGridLayout(self.metrics_container)
    metrics_grid.setContentsMargins(0, 0, 0, 0)
    metrics_grid.setSpacing(10)

    # Speed Row on top (Row 0)
    label_speeds = QLabel("Speeds (mm/s):", self.metrics_container)
    label_speeds.setStyleSheet("font-weight: bold; font-size: 15px; color: #455a64;")
    metrics_grid.addWidget(label_speeds, 0, 0)
    
    self.statusReqSpeed = QLabel("Req: 0.0", self.metrics_container)
    self.statusTopSpeed = QLabel("Top: 0.0", self.metrics_container)
    self.statusProbe = QLabel("Probe: 0", self.metrics_container)
    for lbl in (self.statusReqSpeed, self.statusTopSpeed, self.statusProbe):
        lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: #2e7d32;")
    metrics_grid.addWidget(self.statusReqSpeed, 0, 1)
    metrics_grid.addWidget(self.statusTopSpeed, 0, 2)
    metrics_grid.addWidget(self.statusProbe, 0, 3)

    # Position Row in just one row (Row 1), containing all 14 axes
    self.statusPosX = QLabel("X 0.00", self.metrics_container)
    self.statusPosY = QLabel("Y 0.00", self.metrics_container)
    self.statusPosZ = QLabel("Z 0.00", self.metrics_container)
    for lbl in (self.statusPosX, self.statusPosY, self.statusPosZ):
        lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: #0d47a1;")
    metrics_grid.addWidget(self.statusPosX, 1, 0)
    metrics_grid.addWidget(self.statusPosY, 1, 1)
    metrics_grid.addWidget(self.statusPosZ, 1, 2)

    self.statusPosA = QLabel("A 0.00", self.metrics_container)
    self.statusPosB = QLabel("B 0.00", self.metrics_container)
    self.statusPosC = QLabel("C 0.00", self.metrics_container)
    self.statusPosD = QLabel("D 0.00", self.metrics_container)
    for lbl in (self.statusPosA, self.statusPosB, self.statusPosC, self.statusPosD):
        lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: #8e24aa;")
    metrics_grid.addWidget(self.statusPosA, 1, 3)
    metrics_grid.addWidget(self.statusPosB, 1, 4)
    metrics_grid.addWidget(self.statusPosC, 1, 5)
    metrics_grid.addWidget(self.statusPosD, 1, 6)

    self.statusPos_e = QLabel("'e 0.00", self.metrics_container)
    self.statusPos_f = QLabel("'f 0.00", self.metrics_container)
    self.statusPos_a = QLabel("'a 0.00", self.metrics_container)
    self.statusPos_c = QLabel("'c 0.00", self.metrics_container)
    for lbl in (self.statusPos_e, self.statusPos_f, self.statusPos_a, self.statusPos_c):
        lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: #795548;")
    metrics_grid.addWidget(self.statusPos_e, 1, 7)
    metrics_grid.addWidget(self.statusPos_f, 1, 8)
    metrics_grid.addWidget(self.statusPos_a, 1, 9)
    metrics_grid.addWidget(self.statusPos_c, 1, 10)

    self.statusPosRoll = QLabel("Roll 0.00", self.metrics_container)
    self.statusPosPitch = QLabel("Pitch 0.00", self.metrics_container)
    self.statusPosYaw = QLabel("Yaw 0.00", self.metrics_container)
    for lbl in (self.statusPosRoll, self.statusPosPitch, self.statusPosYaw):
        lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: #3f51b5;")
    metrics_grid.addWidget(self.statusPosRoll, 1, 11)
    metrics_grid.addWidget(self.statusPosPitch, 1, 12)
    metrics_grid.addWidget(self.statusPosYaw, 1, 13)

    card_layout.addWidget(self.metrics_container)
    layout_main.addWidget(self.card_status)

    # --- 2. INTERACTIVE REAL-TIME POSITION PLOT GROUP (PROMINENT CENTER GRAPH) ---
    plot_box = QGroupBox("", self.tab_status)
    plot_box.setStyleSheet("""
        QGroupBox {
            border: 1px solid #cfd8dc;
            border-radius: 6px;
            background-color: #ffffff;
            margin-top: 5px;
        }
    """)
    plot_vlayout = QVBoxLayout(plot_box)
    plot_vlayout.setContentsMargins(8, 8, 8, 8)
    plot_vlayout.setSpacing(8)

    # 2.1 LOGGING CONTROLS ROW (placed above the graph)
    log_layout = QHBoxLayout()
    log_layout.setSpacing(10)
    log_layout.setContentsMargins(0, 0, 0, 0)

    desktop_default = os.path.join(os.path.expanduser("~"), "Desktop")

    label_folder = QLabel("Log Output Folder:", plot_box)
    label_folder.setStyleSheet("font-weight: bold; font-size: 14px; color: #455a64;")

    self.PhOperFolder = QLineEdit(desktop_default, plot_box)
    self.PhOperFolder.setMinimumWidth(260)
    self.PhOperFolder.setMaximumWidth(450)
    self.PhOperFolder.setFixedHeight(32)
    self.PhOperFolder.setStyleSheet("""
        QLineEdit {
            background-color: #ffffff;
            font-size: 13px;
            border: 1px solid #b0bec5;
            border-radius: 4px;
            padding: 2px 8px;
            color: #263238;
        }
    """)
    register_touch_line_edit(self, self.PhOperFolder, label_name="Log Output Folder", keyboard_mode="full")

    self.setPhOperFolder = QPushButton("Set Folder", plot_box)
    self.setPhOperFolder.setFixedHeight(32)
    self.setPhOperFolder.setStyleSheet("""
        QPushButton {
            background-color: #1565c0;
            color: white;
            font-weight: bold;
            font-size: 13px;
            padding: 2px 14px;
            border-radius: 4px;
            border: none;
        }
        QPushButton:hover {
            background-color: #0d47a1;
        }
        QPushButton:pressed {
            background-color: #0a3875;
        }
    """)

    self.button_load_log = QPushButton("Load Log", plot_box)
    self.button_load_log.setFixedHeight(32)
    self.button_load_log.setStyleSheet("""
        QPushButton {
            background-color: #0288d1;
            color: white;
            font-weight: bold;
            font-size: 13px;
            padding: 2px 14px;
            border-radius: 4px;
            border: none;
        }
        QPushButton:hover {
            background-color: #0277bd;
        }
        QPushButton:pressed {
            background-color: #01579b;
        }
    """)

    self.button_load_gcode_ref = QPushButton("Load G-code as Ref", plot_box)
    self.button_load_gcode_ref.setFixedHeight(32)
    self.button_load_gcode_ref.setStyleSheet("""
        QPushButton {
            background-color: #00897b;
            color: white;
            font-weight: bold;
            font-size: 13px;
            padding: 2px 14px;
            border-radius: 4px;
            border: none;
        }
        QPushButton:hover {
            background-color: #00796b;
        }
        QPushButton:pressed {
            background-color: #004d40;
        }
    """)

    self.check_record_log = QCheckBox("Record Data Log (log_HH_MM_SS_.csv)", plot_box)
    self.check_record_log.setStyleSheet("font-weight: bold; color: #b71c1c; font-size: 14px;")
    self.check_record_log.toggled.connect(lambda checked: __import__('fcn_monitor.fcn_duet', fromlist=['close_data_log_file']).close_data_log_file(self) if not checked else None)

    # Max Speed Adjustment Limit control (default 20%)
    lbl_max_speed_adj = QLabel("Max Speed Adj (%):", plot_box)
    lbl_max_speed_adj.setStyleSheet("font-weight: bold; font-size: 14px; color: #455a64;")

    self.input_max_speed_adj = QLineEdit("20", plot_box)
    self.input_max_speed_adj.setFixedWidth(55)
    self.input_max_speed_adj.setFixedHeight(32)
    self.input_max_speed_adj.setStyleSheet("""
        QLineEdit {
            background-color: #ffffff;
            font-weight: bold;
            font-size: 14px;
            border: 1px solid #b0bec5;
            border-radius: 4px;
            padding: 2px 6px;
            color: #d81b60;
        }
    """)
    validator_max_adj = QDoubleValidator(1.0, 200.0, 1, self.input_max_speed_adj)
    validator_max_adj.setNotation(QDoubleValidator.StandardNotation)
    self.input_max_speed_adj.setValidator(validator_max_adj)
    register_touch_line_edit(self, self.input_max_speed_adj, label_name="Max Speed Adj (%)")

    # Reference Time Offset control (placed to the left of Time interval)
    lbl_ref_offset = QLabel("Ref. Offset (s):", plot_box)
    lbl_ref_offset.setStyleSheet("font-weight: bold; font-size: 14px; color: #455a64;")

    self.input_ref_offset = QLineEdit("0", plot_box)
    self.input_ref_offset.setFixedWidth(65)
    self.input_ref_offset.setFixedHeight(32)
    self.input_ref_offset.setStyleSheet("""
        QLineEdit {
            background-color: #ffffff;
            font-weight: bold;
            font-size: 14px;
            border: 1px solid #b0bec5;
            border-radius: 4px;
            padding: 2px 6px;
            color: #2e7d32;
        }
    """)
    from PySide6.QtGui import QDoubleValidator
    from PySide6.QtCore import QLocale
    validator_offset = QDoubleValidator(-1000.0, 1000.0, 3, self.input_ref_offset)
    validator_offset.setNotation(QDoubleValidator.StandardNotation)
    validator_offset.setLocale(QLocale(QLocale.C))
    self.input_ref_offset.setValidator(validator_offset)
    register_touch_line_edit(self, self.input_ref_offset, label_name="Ref. Offset (s)")
    self.input_ref_offset.textChanged.connect(lambda: __import__('fcn_monitor.fcn_duet', fromlist=['render_status_plot']).render_status_plot(self))

    # Time interval control (placed between offset and clear plot button)
    lbl_time_interval = QLabel("Time interval (s):", plot_box)
    lbl_time_interval.setStyleSheet("font-weight: bold; font-size: 14px; color: #455a64;")

    self.input_time_interval = QLineEdit("60", plot_box)
    self.input_time_interval.setFixedWidth(65)
    self.input_time_interval.setFixedHeight(32)
    self.input_time_interval.setStyleSheet("""
        QLineEdit {
            background-color: #ffffff;
            font-weight: bold;
            font-size: 14px;
            border: 1px solid #b0bec5;
            border-radius: 4px;
            padding: 2px 6px;
            color: #1565c0;
        }
    """)
    from PySide6.QtGui import QIntValidator
    self.input_time_interval.setValidator(QIntValidator(5, 86400, self.input_time_interval))
    register_touch_line_edit(self, self.input_time_interval, label_name="Time Interval (s)")
    self.input_time_interval.textChanged.connect(lambda: __import__('fcn_monitor.fcn_duet', fromlist=['render_status_plot']).render_status_plot(self))

    self.button_clear_plot = QPushButton("Clear Plot Data", plot_box)
    self.button_clear_plot.setFixedHeight(32)
    self.button_clear_plot.setStyleSheet("""
        QPushButton {
            background-color: #757575;
            color: white;
            font-weight: bold;
            font-size: 13px;
            padding: 2px 14px;
            border-radius: 4px;
            border: none;
        }
        QPushButton:hover {
            background-color: #616161;
        }
        QPushButton:pressed {
            background-color: #424242;
        }
    """)

    self.log_folder_container = QWidget(plot_box)
    log_folder_layout = QHBoxLayout(self.log_folder_container)
    log_folder_layout.setContentsMargins(0, 0, 0, 0)
    log_folder_layout.setSpacing(10)

    log_folder_layout.addWidget(label_folder)
    log_folder_layout.addWidget(self.PhOperFolder, stretch=1)
    log_folder_layout.addWidget(self.setPhOperFolder)
    log_folder_layout.addWidget(self.button_load_log)
    log_folder_layout.addWidget(self.button_load_gcode_ref)
    log_folder_layout.addWidget(self.check_record_log)
    log_folder_layout.addWidget(lbl_max_speed_adj)
    log_folder_layout.addWidget(self.input_max_speed_adj)
    log_folder_layout.addWidget(lbl_ref_offset)
    log_folder_layout.addWidget(self.input_ref_offset)
    log_folder_layout.addWidget(lbl_time_interval)
    log_folder_layout.addWidget(self.input_time_interval)

    log_layout.addWidget(self.log_folder_container, stretch=1)
    log_layout.addStretch()
    log_layout.addWidget(self.button_clear_plot)

    plot_vlayout.addLayout(log_layout)

    # 2.2 PLOT MAIN CONTENT (Graph left, Checkboxes vertically stacked on the right)
    plot_content_layout = QHBoxLayout()
    plot_content_layout.setSpacing(12)
    plot_content_layout.setContentsMargins(0, 0, 0, 0)

    # Matplotlib Figure & Canvas (Left side)
    self.fig_status = Figure(figsize=(8, 3.2), dpi=90)
    self.ax_status = self.fig_status.add_subplot(111)
    self.ax_status.set_xlabel("Time (s)", fontsize=13, fontweight='bold')
    self.ax_status.set_ylabel("Position (mm)", fontsize=13, fontweight='bold')
    self.ax_status.tick_params(axis='both', which='major', labelsize=11)
    self.ax_status.grid(True, linestyle=":", alpha=0.6)
    self.fig_status.tight_layout()

    self.statusCanvas = FigureCanvas(self.fig_status)
    self.statusCanvas.setMinimumHeight(180)
    self.statusCanvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    plot_content_layout.addWidget(self.statusCanvas, stretch=1)



    # Checkboxes organized in 2 columns wrapped in QScrollArea (Right side of the graph)
    self.status_checks_scroll = QScrollArea(plot_box)
    self.status_checks_scroll.setWidgetResizable(True)
    self.status_checks_scroll.setFrameShape(QFrame.NoFrame)
    self.status_checks_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    self.status_checks_scroll.setStyleSheet("QScrollArea { background: transparent; }")

    self.status_checks_container = QWidget()
    self.grid_checks_layout = QGridLayout(self.status_checks_container)
    self.grid_checks_layout.setContentsMargins(0, 0, 5, 0)
    self.grid_checks_layout.setHorizontalSpacing(10)
    self.grid_checks_layout.setVerticalSpacing(4)

    # Show reference checkbox (row 0, spanning 2 columns)
    self.check_show_reference = QCheckBox("Show reference", self.status_checks_container)
    self.check_show_reference.setChecked(False)
    self.check_show_reference.setVisible(True)
    self.check_show_reference.setStyleSheet("QCheckBox { font-weight: bold; font-size: 13px; color: #1565c0; margin-bottom: 4px; }")

    def on_show_reference_toggled(checked):
        if checked:
            from fcn_monitor.fcn_duet import auto_load_current_gcode_reference, render_status_plot
            if getattr(self, 'status_reference_data', None) is None:
                auto_load_current_gcode_reference(self)
            render_status_plot(self)
        else:
            from fcn_monitor.fcn_duet import render_status_plot
            render_status_plot(self)

    self.check_show_reference.toggled.connect(on_show_reference_toggled)

    checkbox_specs = [
        # (attribute, label, color)
        ('status_check_X', "Show X", '#1e88e5'),
        ('status_check_Y', "Show Y", '#43a047'),
        ('status_check_Z', "Show Z", '#e53935'),
        ('status_check_A', "Show A", '#8e24aa'),
        ('status_check_B', "Show B", '#d81b60'),
        ('status_check_C', "Show C", '#00acc1'),
        ('status_check_D', "Show D", '#f4511e'),
        ('status_check_e', "Show 'e", '#795548'),
        ('status_check_f', "Show 'f", '#607d8b'),
        ('status_check_a', "Show 'a", '#009688'),
        ('status_check_c', "Show 'c", '#ffb300'),
        ('status_check_Roll', "Show Roll", '#3f51b5'),
        ('status_check_Pitch', "Show Pitch", '#9e9d24'),
        ('status_check_Yaw', "Show Yaw", '#673ab7'),
        ('status_check_LAT', "Show LAT", '#e65100'),
        ('status_check_AP', "Show AP", '#1b5e20'),
        ('status_check_SI', "Show SI", '#01579b')
    ]

    for attr, label, color in checkbox_specs:
        cb = QCheckBox(label, self.status_checks_container)
        if label in ["Show X", "Show Y", "Show Z"]:
            cb.setChecked(True)
        cb.setStyleSheet(f"QCheckBox {{ font-weight: bold; font-size: 13px; color: {color}; }}")
        cb.clicked.connect(lambda: __import__('fcn_monitor.fcn_duet', fromlist=['render_status_plot']).render_status_plot(self))
        setattr(self, attr, cb)

    self.status_checks_scroll.setWidget(self.status_checks_container)
    plot_content_layout.addWidget(self.status_checks_scroll)
    plot_vlayout.addLayout(plot_content_layout)

    # Add Navigation Toolbar for zoom and pan below the graph
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
    self.status_toolbar = NavigationToolbar(self.statusCanvas, self.tab_status)
    self.status_toolbar.setStyleSheet("background-color: #f5f5f5; border: none; font-weight: bold;")
    plot_vlayout.addWidget(self.status_toolbar)

    layout_main.addWidget(plot_box, stretch=1)



    # Setup periodic status polling timer (polls Duet every 1.0 seconds)
    self.status_polling_timer = QTimer(self.tab_status)
    self.status_polling_timer.setInterval(1000)
    
    from fcn_monitor.fcn_duet import update_status_tab_dashboard, update_status_fast
    self.status_polling_timer.timeout.connect(lambda: update_status_tab_dashboard(self))
    self.status_polling_timer.start()

    # Setup fast status polling timer (polls userPositions every 15 milliseconds)
    self.status_fast_timer = QTimer(self.tab_status)
    self.status_fast_timer.setInterval(15)
    self.status_fast_timer.timeout.connect(lambda: update_status_fast(self))
    self.status_fast_timer.start()

    # Initialize Advanced vs Basic mode from persisted configuration
    initial_adv = getattr(self, 'status_advanced_mode', False)
    self.check_advanced_mode.blockSignals(True)
    self.check_advanced_mode.setChecked(initial_adv)
    self.check_advanced_mode.blockSignals(False)
    apply_status_advanced_mode(self, initial_adv)

    self.check_advanced_mode.toggled.connect(lambda checked: (
        apply_status_advanced_mode(self, checked),
        save_status_advanced_mode(self, checked)
    ))
