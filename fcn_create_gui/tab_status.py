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
    QPushButton, QLabel, QSlider, QToolButton, QFrame, QProgressBar, QLineEdit, QCheckBox, QSizePolicy
)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from fcn_create_gui.touch_keyboard import register_touch_line_edit


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

    # Connect buttons
    from fcn_monitor.fcn_duet import pause_continue_GCODE, cancel_GCODE_job, start_selected_gcode_execution
    self.gcodeStart.clicked.connect(lambda: start_selected_gcode_execution(self))
    self.gcodePause.clicked.connect(lambda: pause_continue_GCODE(self, pause=True))
    self.gcodeResume.clicked.connect(lambda: pause_continue_GCODE(self, pause=False))
    self.gcodeStopJob.clicked.connect(lambda: cancel_GCODE_job(self))

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

    # Left 1/3 column: Status badge on left, Start, Pause, Resume, Stop buttons aligned so Stop ends at 1/3 width (end of progress bar)
    top_left_box = QHBoxLayout()
    top_left_box.setContentsMargins(0, 0, 0, 0)
    top_left_box.addWidget(hdr_label)
    top_left_box.addWidget(self.statusBadgeLabel)
    top_left_box.addStretch()
    top_left_box.addWidget(self.gcodeStart)
    top_left_box.addWidget(self.gcodePause)
    top_left_box.addWidget(self.gcodeResume)
    top_left_box.addWidget(self.gcodeStopJob)

    # Right 2/3 column: Speed Factor tightly grouped on left next to field, Auto release, Auto pause, Emergency STOP on right
    top_right_box = QHBoxLayout()
    top_right_box.setContentsMargins(0, 0, 0, 0)
    
    sf_container = QWidget(self.card_status)
    sf_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    sf_hlayout = QHBoxLayout(sf_container)
    sf_hlayout.setContentsMargins(0, 0, 0, 0)
    sf_hlayout.setSpacing(6)
    sf_hlayout.addWidget(label_sf)
    sf_hlayout.addWidget(self.labelSf)
    sf_hlayout.addWidget(self.minSf)
    sf_hlayout.addWidget(self.plusSf)

    top_right_box.addWidget(sf_container)
    top_right_box.addSpacing(15)

    # Add Auto-sync Speed (placed just before Pre-setup, disabled by default)
    self.check_auto_sync = QCheckBox("Auto-sync Speed", self.card_status)
    self.check_auto_sync.setChecked(False)
    self.check_auto_sync.setStyleSheet("QCheckBox { font-weight: bold; font-size: 14px; color: #1565c0; }")
    top_right_box.addWidget(self.check_auto_sync)

    def on_auto_sync_toggled(enabled):
        # Disable manual speed controls when auto-sync is enabled
        self.labelSf.setEnabled(not enabled)
        self.minSf.setEnabled(not enabled)
        self.plusSf.setEnabled(not enabled)
        style = "background-color: #f5f5f5; color: #9e9e9e;" if enabled else "background-color: #ffffff; color: #0d47a1;"
        self.labelSf.setStyleSheet(f"QLineEdit {{ font-weight: bold; font-size: 14px; border: 1px solid #b0bec5; border-radius: 4px; padding: 4px; text-align: center; {style} }}")

    self.check_auto_sync.toggled.connect(on_auto_sync_toggled)

    top_right_box.addSpacing(12)

    # Add Pre-setup checkbox (placed just after Auto-sync Speed, enabled by default)
    self.check_pre_setup = QCheckBox("Pre-setup", self.card_status)
    self.check_pre_setup.setChecked(True)
    self.check_pre_setup.setStyleSheet("QCheckBox { font-weight: bold; font-size: 14px; color: #2e7d32; }")
    top_right_box.addWidget(self.check_pre_setup)

    top_right_box.addSpacing(12)

    # Add Auto release and Auto pause checkboxes
    self.check_auto_release = QCheckBox("Auto release", self.card_status)
    self.check_auto_release.setChecked(False)
    self.check_auto_release.setStyleSheet("QCheckBox { font-weight: bold; font-size: 14px; color: #37474f; }")
    top_right_box.addWidget(self.check_auto_release)

    top_right_box.addSpacing(12)
    self.check_auto_pause = QCheckBox("Auto pause", self.card_status)
    self.check_auto_pause.setChecked(False)
    self.check_auto_pause.setStyleSheet("QCheckBox { font-weight: bold; font-size: 14px; color: #37474f; }")
    top_right_box.addWidget(self.check_auto_pause)

    top_right_box.addStretch()
    top_right_box.addWidget(self.emergencyButton_2)

    hdr_layout.addLayout(top_left_box, stretch=1)
    hdr_layout.addLayout(top_right_box, stretch=2)

    card_layout.addLayout(hdr_layout)

    # 2. HEADER TEXT ROW (ABOVE FIELDS): Print Duration & Time Remaining above Progress Bar (1/3), Duet Message label above Duet Message field (2/3)
    top_info_layout = QHBoxLayout()
    top_info_layout.setSpacing(15)

    self.labelPrintDuration = QLabel("Print Duration: 00:00:00", self.card_status)
    self.labelPrintDuration.setStyleSheet("color: #616161; font-size: 14px; font-weight: bold;")
    
    self.labelTimeRemaining = QLabel("Time Remaining: --:--:--", self.card_status)
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

    # Section: Tool Position & Speeds & Other Axes
    metrics_grid = QGridLayout()
    metrics_grid.setSpacing(10)

    # Speed Row on top (Row 0)
    label_speeds = QLabel("Speeds (mm/s):", self.card_status)
    label_speeds.setStyleSheet("font-weight: bold; font-size: 15px; color: #455a64;")
    metrics_grid.addWidget(label_speeds, 0, 0)
    
    self.statusReqSpeed = QLabel("Req: 0.0", self.card_status)
    self.statusTopSpeed = QLabel("Top: 0.0", self.card_status)
    self.statusProbe = QLabel("Probe: 0", self.card_status)
    for lbl in (self.statusReqSpeed, self.statusTopSpeed, self.statusProbe):
        lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: #2e7d32;")
    metrics_grid.addWidget(self.statusReqSpeed, 0, 1)
    metrics_grid.addWidget(self.statusTopSpeed, 0, 2)
    metrics_grid.addWidget(self.statusProbe, 0, 3)

    # Position Row in just one row (Row 1), containing all 14 axes
    self.statusPosX = QLabel("X 0.00", self.card_status)
    self.statusPosY = QLabel("Y 0.00", self.card_status)
    self.statusPosZ = QLabel("Z 0.00", self.card_status)
    for lbl in (self.statusPosX, self.statusPosY, self.statusPosZ):
        lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: #0d47a1;")
    metrics_grid.addWidget(self.statusPosX, 1, 0)
    metrics_grid.addWidget(self.statusPosY, 1, 1)
    metrics_grid.addWidget(self.statusPosZ, 1, 2)

    self.statusPosA = QLabel("A 0.00", self.card_status)
    self.statusPosB = QLabel("B 0.00", self.card_status)
    self.statusPosC = QLabel("C 0.00", self.card_status)
    self.statusPosD = QLabel("D 0.00", self.card_status)
    for lbl in (self.statusPosA, self.statusPosB, self.statusPosC, self.statusPosD):
        lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: #8e24aa;")
    metrics_grid.addWidget(self.statusPosA, 1, 3)
    metrics_grid.addWidget(self.statusPosB, 1, 4)
    metrics_grid.addWidget(self.statusPosC, 1, 5)
    metrics_grid.addWidget(self.statusPosD, 1, 6)

    self.statusPos_e = QLabel("'e 0.00", self.card_status)
    self.statusPos_f = QLabel("'f 0.00", self.card_status)
    self.statusPos_a = QLabel("'a 0.00", self.card_status)
    self.statusPos_c = QLabel("'c 0.00", self.card_status)
    for lbl in (self.statusPos_e, self.statusPos_f, self.statusPos_a, self.statusPos_c):
        lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: #795548;")
    metrics_grid.addWidget(self.statusPos_e, 1, 7)
    metrics_grid.addWidget(self.statusPos_f, 1, 8)
    metrics_grid.addWidget(self.statusPos_a, 1, 9)
    metrics_grid.addWidget(self.statusPos_c, 1, 10)

    self.statusPosRoll = QLabel("Roll 0.00", self.card_status)
    self.statusPosPitch = QLabel("Pitch 0.00", self.card_status)
    self.statusPosYaw = QLabel("Yaw 0.00", self.card_status)
    for lbl in (self.statusPosRoll, self.statusPosPitch, self.statusPosYaw):
        lbl.setStyleSheet("font-weight: bold; font-size: 15px; color: #3f51b5;")
    metrics_grid.addWidget(self.statusPosRoll, 1, 11)
    metrics_grid.addWidget(self.statusPosPitch, 1, 12)
    metrics_grid.addWidget(self.statusPosYaw, 1, 13)

    card_layout.addLayout(metrics_grid)
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
    self.PhOperFolder.setStyleSheet("font-size: 14px; padding: 4px;")
    register_touch_line_edit(self, self.PhOperFolder, label_name="Log Output Folder")

    self.setPhOperFolder = QPushButton("Set Folder", plot_box)
    self.setPhOperFolder.setStyleSheet("background-color: blue; color: white; font-weight: bold; font-size: 14px; min-height: 36px;")

    self.check_record_log = QCheckBox("Record Data Log (log_HH_MM_SS_.txt)", plot_box)
    self.check_record_log.setStyleSheet("font-weight: bold; color: #b71c1c; font-size: 14px;")

    # Max Speed Adjustment Limit control (default 20%)
    lbl_max_speed_adj = QLabel("Max Speed Adj (%):", plot_box)
    lbl_max_speed_adj.setStyleSheet("font-weight: bold; font-size: 14px; color: #455a64;")

    self.input_max_speed_adj = QLineEdit("20", plot_box)
    self.input_max_speed_adj.setFixedWidth(55)
    self.input_max_speed_adj.setStyleSheet("""
        QLineEdit {
            background-color: #ffffff;
            font-weight: bold;
            font-size: 14px;
            border: 1px solid #b0bec5;
            border-radius: 4px;
            padding: 4px 6px;
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
    self.input_ref_offset.setStyleSheet("""
        QLineEdit {
            background-color: #ffffff;
            font-weight: bold;
            font-size: 14px;
            border: 1px solid #b0bec5;
            border-radius: 4px;
            padding: 4px 6px;
            color: #2e7d32;
        }
    """)
    from PySide6.QtGui import QDoubleValidator
    validator_offset = QDoubleValidator(-1000.0, 1000.0, 2, self.input_ref_offset)
    validator_offset.setNotation(QDoubleValidator.StandardNotation)
    self.input_ref_offset.setValidator(validator_offset)
    register_touch_line_edit(self, self.input_ref_offset, label_name="Ref. Offset (s)")
    self.input_ref_offset.textChanged.connect(lambda: __import__('fcn_monitor.fcn_duet', fromlist=['render_status_plot']).render_status_plot(self))

    # Time interval control (placed between offset and clear plot button)
    lbl_time_interval = QLabel("Time interval (s):", plot_box)
    lbl_time_interval.setStyleSheet("font-weight: bold; font-size: 14px; color: #455a64;")

    self.input_time_interval = QLineEdit("60", plot_box)
    self.input_time_interval.setFixedWidth(65)
    self.input_time_interval.setStyleSheet("""
        QLineEdit {
            background-color: #ffffff;
            font-weight: bold;
            font-size: 14px;
            border: 1px solid #b0bec5;
            border-radius: 4px;
            padding: 4px 6px;
            color: #1565c0;
        }
    """)
    from PySide6.QtGui import QIntValidator
    self.input_time_interval.setValidator(QIntValidator(5, 86400, self.input_time_interval))
    register_touch_line_edit(self, self.input_time_interval, label_name="Time Interval (s)")
    self.input_time_interval.textChanged.connect(lambda: __import__('fcn_monitor.fcn_duet', fromlist=['render_status_plot']).render_status_plot(self))

    self.button_clear_plot = QPushButton("Clear Plot Data", plot_box)
    self.button_clear_plot.setMinimumHeight(36)
    self.button_clear_plot.setStyleSheet("background-color: #757575; color: white; font-weight: bold; font-size: 14px; padding: 6px 15px; border-radius: 4px;")

    log_layout.addWidget(label_folder)
    log_layout.addWidget(self.PhOperFolder, stretch=1)
    log_layout.addWidget(self.setPhOperFolder)
    log_layout.addWidget(self.check_record_log)
    log_layout.addWidget(lbl_max_speed_adj)
    log_layout.addWidget(self.input_max_speed_adj)
    log_layout.addWidget(lbl_ref_offset)
    log_layout.addWidget(self.input_ref_offset)
    log_layout.addWidget(lbl_time_interval)
    log_layout.addWidget(self.input_time_interval)
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



    # Checkboxes stacked vertically in a single column (Right side of the graph)
    self.status_checks_container = QWidget(plot_box)
    v_checks_layout = QVBoxLayout(self.status_checks_container)
    v_checks_layout.setContentsMargins(0, 0, 0, 0)
    v_checks_layout.setSpacing(2)

    # Show reference checkbox (always visible next to the plot)
    self.check_show_reference = QCheckBox("Show reference", self.status_checks_container)
    self.check_show_reference.setChecked(False)
    self.check_show_reference.setVisible(True)
    self.check_show_reference.setStyleSheet("QCheckBox { font-weight: bold; font-size: 15px; color: #1565c0; margin-bottom: 4px; }")

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
    v_checks_layout.addWidget(self.check_show_reference)

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
        cb.setStyleSheet(f"QCheckBox {{ font-weight: bold; font-size: 15px; color: {color}; }}")
        cb.clicked.connect(lambda: __import__('fcn_monitor.fcn_duet', fromlist=['render_status_plot']).render_status_plot(self))
        setattr(self, attr, cb)
        v_checks_layout.addWidget(cb)

    plot_content_layout.addWidget(self.status_checks_container)
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

    # Setup fast status polling timer (polls userPositions every 10 milliseconds)
    self.status_fast_timer = QTimer(self.tab_status)
    self.status_fast_timer.setInterval(10)
    self.status_fast_timer.timeout.connect(lambda: update_status_fast(self))
    self.status_fast_timer.start()
