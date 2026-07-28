"""
Control Tab creation for TRACE GUI
Constructs Duet IP config, Touchscreen Mode toggle, Emergency Stop,
  Lung Phantom, Platform (2 axes per row), and Ind. Motors (Line 1: A, B, C, D, X, Y, Z; Line 2: 'a, 'c, 'e, 'f with Target Pos, Move Axis, Home Axis in Row 2 and -/+ Jog buttons in Row 3),
plus bottom panel with Command Console + Vertical Step Size Selector Bar (0.1, 0.5, 1, 10 mm).
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QFrame,
    QPushButton, QLineEdit, QRadioButton, QCheckBox, QTabWidget, QLabel, QTextEdit, QSizePolicy
)
from fcn_create_gui.touch_keyboard import register_touch_line_edit


def build_control_tab(self):
    """Populate self.tab_2 with all Control tab widgets."""
    layout_main = QVBoxLayout(self.tab_2)
    layout_main.setContentsMargins(6, 6, 6, 6)
    layout_main.setSpacing(6)

    # --- 1. TOP CONFIGURATION BAR (Height 40px, 17px bold Connect text) ---
    top_bar_layout = QHBoxLayout()
    top_bar_layout.setContentsMargins(4, 4, 4, 4)
    top_bar_layout.setSpacing(10)

    label_ip = QLabel("Duet IP:", self.tab_2)
    label_ip.setStyleSheet("font-weight: bold; font-size: 14px;")
    
    self.DuetIPAddress = QLineEdit(self.tab_2)
    self.DuetIPAddress.setText("192.168.0.1")
    self.DuetIPAddress.setMaximumWidth(140)
    self.DuetIPAddress.setMinimumHeight(55)
    self.DuetIPAddress.setStyleSheet("""
        QLineEdit {
            font-weight: bold;
            font-size: 14px;
            padding: 4px 8px;
            border: 1px solid #b0bec5;
            border-radius: 4px;
        }
    """)
    register_touch_line_edit(self, self.DuetIPAddress, label_name="Duet IP Address")
 
    self.setDuetIP = QPushButton("Connect", self.tab_2)
    self.setDuetIP.setMinimumHeight(55)
    self.setDuetIP.setMinimumWidth(180)
    self.setDuetIP.setStyleSheet("""
        QPushButton {
            background-color: blue;
            color: white;
            font-weight: bold;
            font-size: 17px;
            padding: 6px 18px;
            border-radius: 4px;
        }
    """)
    
    self.connect_status = QRadioButton("Status: Not connected", self.tab_2)
    self.connect_status.setEnabled(False)
    self.connect_status.setChecked(False)
    self.connect_status.setMinimumHeight(40)
    self.connect_status.setStyleSheet("""
        QRadioButton { font-weight: bold; color: red; font-size: 18px; }
        QRadioButton::indicator { width: 22px; height: 22px; border-radius: 11px; }
        QRadioButton::indicator:checked { background-color: #00e676; border: 1px solid #00c853; }
        QRadioButton::indicator:unchecked { background-color: #ff5252; border: 1px solid #d50000; }
    """)
 
    self.check_touchscreen = QCheckBox("Touchscreen Mode", self.tab_2)
    self.check_touchscreen.setMinimumHeight(42)
    self.check_touchscreen.setStyleSheet("""
        QCheckBox {
            font-weight: bold;
            color: #0288d1;
            font-size: 14px;
            min-height: 42px;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border-radius: 4px;
            border: 2px solid #0288d1;
        }
        QCheckBox::indicator:checked {
            background-color: #0288d1;
        }
    """)
 
    top_bar_layout.addWidget(label_ip)
    top_bar_layout.addWidget(self.DuetIPAddress)
    top_bar_layout.addWidget(self.setDuetIP)
    top_bar_layout.addWidget(self.connect_status)
    top_bar_layout.addWidget(self.check_touchscreen)
    top_bar_layout.addStretch()
 
    # Save touchscreen state on change
    self.check_touchscreen.stateChanged.connect(lambda: __import__('fcn_control.fcn_control', fromlist=['save_configuration']).save_configuration(self))
 
    # Emergency Stop Button 1
    self.emergencyButton_1 = QPushButton("Emergency STOP", self.tab_2)
    self.emergencyButton_1.setStyleSheet("background-color: red; color: white; font-weight: bold; font-size: 16px; border-radius: 6px;")
    self.emergencyButton_1.setMinimumHeight(55)
    self.emergencyButton_1.setMinimumWidth(220)
    top_bar_layout.addWidget(self.emergencyButton_1)

    layout_main.addLayout(top_bar_layout)

    # --- 2. SUB-TABS: LUNG PHANTOM, PLATFORM & IND. MOTORS ---
    self.tabWidget = QTabWidget(self.tab_2)
    self.tabWidget.setStyleSheet("""
        QTabBar::tab {
            font-weight: bold;
            font-size: 18px;
            padding: 8px 20px;
            min-height: 44px;
        }
        QTabBar::tab:selected {
            background-color: #ffffff;
            color: #1565c0;
            border-bottom: 3px solid #1565c0;
        }
        QTabWidget::pane { border: 1px solid #cfd8dc; border-radius: 4px; }
    """)
    
    # Sub-Tab 0: Lung Phantom
    self.tab = QWidget()
    build_motion_platform_subtab(self)
    self.tabWidget.addTab(self.tab, "Lung Phantom")

    # Sub-Tab 1: Platform (2 axes per row with 50px tall buttons)
    self.tab_platform = QWidget()
    build_platform_subtab(self)
    self.tabWidget.addTab(self.tab_platform, "Platform")

    # Sub-Tab 2: Ind. Motors
    self.tab_4 = QWidget()
    build_external_motors_subtab(self)
    self.tabWidget.addTab(self.tab_4, "Ind. Motors")

    layout_main.addWidget(self.tabWidget)

    # --- 3. BOTTOM PANEL: COMMAND CONSOLE + VERTICAL STEP BUTTONS SIDE-BY-SIDE ---
    bottom_hlayout = QHBoxLayout()
    bottom_hlayout.setContentsMargins(0, 0, 0, 0)
    bottom_hlayout.setSpacing(8)

    # Left: Command Console Panel
    box_cmd = QFrame(self.tab_2)
    box_cmd.setStyleSheet("QFrame { border: 1px solid #cfd8dc; border-radius: 4px; background-color: #ffffff; }")
    cmd_vlayout = QVBoxLayout(box_cmd)
    cmd_vlayout.setContentsMargins(8, 8, 8, 8)
    cmd_vlayout.setSpacing(6)

    cmd_input_layout = QHBoxLayout()
    label_cmd = QLabel("Send Command:", box_cmd)
    label_cmd.setStyleSheet("font-weight: bold; font-size: 14px; border: none;")
    
    self.duet_command = QLineEdit(box_cmd)
    self.duet_command.setMinimumHeight(40)
    self.duet_command.setStyleSheet("""
        QLineEdit {
            border: 1px solid #b0bec5;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 14px;
            font-weight: bold;
        }
    """)
    register_touch_line_edit(self, self.duet_command, label_name="Send Command")

    self.sendCommandDUET = QPushButton("Send", box_cmd)
    self.sendCommandDUET.setMinimumHeight(40)
    self.sendCommandDUET.setMinimumWidth(90)
    self.sendCommandDUET.setStyleSheet("""
        QPushButton {
            background-color: violet;
            color: white;
            font-weight: bold;
            font-size: 17px;
            padding: 6px 18px;
            border: none;
            border-radius: 4px;
        }
    """)

    cmd_input_layout.addWidget(label_cmd)
    cmd_input_layout.addWidget(self.duet_command)
    cmd_input_layout.addWidget(self.sendCommandDUET)
    cmd_vlayout.addLayout(cmd_input_layout)

    # Console Log Box
    self.duet_log_console = QTextEdit(box_cmd)
    self.duet_log_console.setReadOnly(True)
    self.duet_log_console.setMinimumHeight(75)
    self.duet_log_console.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    self.duet_log_console.setPlaceholderText("Command log and Duet replies will appear here...")
    self.duet_log_console.setStyleSheet("""
        QTextEdit {
            background-color: #1e1e1e;
            color: #00ff66;
            font-family: Consolas, monospace;
            font-size: 18px;
            border: none;
        }
        QScrollBar:vertical {
            width: 36px;
            background: #2d2d2d;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:vertical {
            background: #555555;
            min-height: 40px;
            border-radius: 6px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            background: none;
            height: 0px;
        }
    """)
    cmd_vlayout.addWidget(self.duet_log_console)

    bottom_hlayout.addWidget(box_cmd, stretch=1)

    # Right: Vertical Step Size Selection Panel
    box_step = QFrame(self.tab_2)
    box_step.setStyleSheet("QFrame { border: 1px solid #cfd8dc; border-radius: 4px; background-color: #ffffff; }")
    step_vlayout = QVBoxLayout(box_step)
    step_vlayout.setContentsMargins(6, 6, 6, 6)
    step_vlayout.setSpacing(6)

    label_step_header = QLabel("Step (mm)", box_step)
    label_step_header.setAlignment(Qt.AlignCenter)
    label_step_header.setStyleSheet("font-weight: bold; font-size: 14px; color: #37474f; border: none;")
    step_vlayout.addWidget(label_step_header)

    self.step_buttons = {}
    step_options = ["0.1", "0.5", "1", "5", "10"]
    self.global_step_val = 1.0

    from fcn_control.fcn_control import set_global_step_size

    for val_str in step_options:
        btn = QPushButton(f"{val_str}", box_step)
        btn.setCheckable(True)
        btn.setMinimumHeight(64)
        btn.setMinimumWidth(130)
        btn.clicked.connect(lambda _c=False, v=val_str: set_global_step_size(self, v))
        self.step_buttons[val_str] = btn
        step_vlayout.addWidget(btn)

    bottom_hlayout.addWidget(box_step)
    layout_main.addLayout(bottom_hlayout)

    # Initialize default step button state to "1" mm
    set_global_step_size(self, "1")


def build_motion_platform_subtab(self):
    """
    Build the 'Lung Phantom' sub-tab inside Control as one unified table panel.
    One row per axis: Axis label (X, Y, Z), Current Pos, Target Pos, - Axis, + Axis, Home Axis.
    All buttons set to 50px height for maximum touch clarity.
    """
    layout = QVBoxLayout(self.tab)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(6)

    # Unified Motion Table Panel
    table_frame = QFrame(self.tab)
    table_frame.setStyleSheet("QFrame { border: 1px solid #cfd8dc; border-radius: 6px; background-color: #ffffff; }")
    grid = QGridLayout(table_frame)
    grid.setContentsMargins(12, 10, 12, 10)
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(12)

    # Column Stretch Factors
    grid.setColumnStretch(0, 0) # Axis Label
    grid.setColumnStretch(1, 1) # Current Pos
    grid.setColumnStretch(2, 1) # Target Pos
    grid.setColumnStretch(3, 2) # Jog -
    grid.setColumnStretch(4, 2) # Jog +
    grid.setColumnStretch(5, 2) # Home

    # Table Header Row
    headers = ["Axis", "Current Pos (mm)", "Target Pos (mm)", "Jog -", "Jog +", "Homing"]
    for col_idx, h_text in enumerate(headers):
        lbl = QLabel(h_text, table_frame)
        lbl.setStyleSheet("font-weight: bold; color: #37474f; font-size: 14px; border: none;")
        if col_idx >= 3:
            lbl.setAlignment(Qt.AlignCenter)
        grid.addWidget(lbl, 0, col_idx)

    axes = ['XAXIS', 'YAXIS', 'ZAXIS']
    labels = ['X', 'Y', 'Z']
    
    button_style = """
        QPushButton {
            background-color: blue;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            border-radius: 6px;
        }
    """

    for row_idx, (axis, name) in enumerate(zip(axes, labels), start=1):
        # 1. Axis Label
        axis_lbl = QLabel(f"{name}", table_frame)
        axis_lbl.setStyleSheet("font-weight: bold; font-size: 18px; color: #1565c0; border: none;")
        axis_lbl.setAlignment(Qt.AlignCenter)
        grid.addWidget(axis_lbl, row_idx, 0)

        # 2. Current Pos
        curr_pos = QLineEdit("0.0", table_frame)
        curr_pos.setReadOnly(True)
        curr_pos.setMinimumHeight(44)
        curr_pos.setMaximumWidth(110)
        curr_pos.setStyleSheet("""
            QLineEdit {
                background-color: #f5f5f5;
                font-weight: bold;
                font-size: 15px;
                border: 1px solid #b0bec5;
                border-radius: 5px;
                padding: 4px 8px;
            }
        """)
        setattr(self, f"POS_CURR_{axis}", curr_pos)
        grid.addWidget(curr_pos, row_idx, 1)

        # 3. Target Pos
        des_pos = QLineEdit("0.0", table_frame)
        des_pos.setMinimumHeight(44)
        des_pos.setMaximumWidth(110)
        des_pos.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                font-weight: bold;
                font-size: 15px;
                border: 1px solid #b0bec5;
                border-radius: 5px;
                padding: 4px 8px;
            }
        """)
        setattr(self, f"POS_DES_{axis}", des_pos)
        register_touch_line_edit(self, des_pos, label_name=f"Target Pos {name}")
        grid.addWidget(des_pos, row_idx, 2)

        # 4. Minus Jog Button (50px height)
        btn_min = QPushButton(f"- {name}", table_frame)
        btn_min.setStyleSheet(button_style)
        setattr(self, f"MIN_{axis}", btn_min)
        grid.addWidget(btn_min, row_idx, 3)

        # 5. Plus Jog Button (50px height)
        btn_plus = QPushButton(f"+ {name}", table_frame)
        btn_plus.setStyleSheet(button_style)
        setattr(self, f"PLUS_{axis}", btn_plus)
        grid.addWidget(btn_plus, row_idx, 4)

        # 6. Home Axis Button (50px height)
        btn_home = QPushButton(f"Home {name}", table_frame)
        btn_home.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                font-weight: bold;
                font-size: 16px;
                min-height: 50px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1b5e20;
            }
        """)
        setattr(self, f"HOME_{name}", btn_home)
        grid.addWidget(btn_home, row_idx, 5)

    # Row 4: Home ALL Button (50px height, spans all columns)
    btn_home_all = QPushButton("Home ALL", table_frame)
    btn_home_all.setStyleSheet("""
        QPushButton {
            background-color: #2e7d32;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            border-radius: 6px;
        }
        QPushButton:hover {
            background-color: #1b5e20;
        }
    """)
    setattr(self, "HOME_ALL", btn_home_all)
    grid.addWidget(btn_home_all, 4, 0, 1, 6)

    layout.addWidget(table_frame)
    layout.addStretch()


def build_platform_subtab(self):
    """
    Build the 'Platform' sub-tab inside Control.
    2 Axes Per Row (50px tall touch buttons):
      Row 1: X Axis & Y Axis
      Row 2: Z Axis & Roll Axis
      Row 3: Pitch Axis & Yaw Axis
    Row 4: Home ALL Button placed directly below + YAW (Cols 5..9, 50px height).
    """
    layout = QVBoxLayout(self.tab_platform)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(6)

    table_frame = QFrame(self.tab_platform)
    table_frame.setStyleSheet("QFrame { border: 1px solid #cfd8dc; border-radius: 6px; background-color: #ffffff; }")
    grid = QGridLayout(table_frame)
    grid.setContentsMargins(12, 10, 12, 10)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(12)

    # 10 Columns Total
    grid.setColumnStretch(0, 0) # Block 1: Axis Label
    grid.setColumnStretch(1, 1) # Block 1: Current Pos
    grid.setColumnStretch(2, 1) # Block 1: Target Pos
    grid.setColumnStretch(3, 2) # Block 1: Jog -
    grid.setColumnStretch(4, 2) # Block 1: Jog +

    grid.setColumnStretch(5, 0) # Block 2: Axis Label
    grid.setColumnStretch(6, 1) # Block 2: Current Pos
    grid.setColumnStretch(7, 1) # Block 2: Target Pos
    grid.setColumnStretch(8, 2) # Block 2: Jog -
    grid.setColumnStretch(9, 2) # Block 2: Jog +

    # Row 0: Headers
    headers_b1 = ["Axis", "Current", "Target", "Jog -", "Jog +"]
    headers_b2 = ["Axis", "Current", "Target", "Jog -", "Jog +"]

    for col_idx, h_text in enumerate(headers_b1):
        lbl = QLabel(h_text, table_frame)
        lbl.setStyleSheet("font-weight: bold; color: #37474f; font-size: 14px; border: none;")
        if col_idx >= 3:
            lbl.setAlignment(Qt.AlignCenter)
        grid.addWidget(lbl, 0, col_idx)

    for col_idx, h_text in enumerate(headers_b2, start=5):
        lbl = QLabel(h_text, table_frame)
        lbl.setStyleSheet("font-weight: bold; color: #37474f; font-size: 14px; border: none;")
        if col_idx >= 8:
            lbl.setAlignment(Qt.AlignCenter)
        grid.addWidget(lbl, 0, col_idx)

    # 3 Pairs of Axes (2 axes per row)
    axis_pairs = [
        (('XAXIS', 'LAT'), ('YAXIS', 'SI')),
        (('ZAXIS', 'AP'), ('ROLL', 'Roll')),
        (('PITCH', 'Pitch'), ('YAW', 'Yaw'))
    ]

    button_style = """
        QPushButton {
            background-color: blue;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover {
            background-color: #1a73e8;
        }
        QPushButton:pressed {
            background-color: #0d47a1;
            padding-top: 3px;
            padding-left: 3px;
        }
    """

    for row_idx, (b1, b2) in enumerate(axis_pairs, start=1):
        # --- Block 1 ---
        axis1, name1 = b1
        lbl1 = QLabel(f"{name1}", table_frame)
        lbl1.setStyleSheet("font-weight: bold; font-size: 17px; color: #1565c0; border: none;")
        lbl1.setAlignment(Qt.AlignCenter)
        grid.addWidget(lbl1, row_idx, 0)

        curr1 = QLineEdit("0.0", table_frame)
        curr1.setReadOnly(True)
        curr1.setMinimumHeight(44)
        curr1.setMaximumWidth(100)
        curr1.setStyleSheet("""
            QLineEdit {
                background-color: #f5f5f5;
                font-weight: bold;
                font-size: 15px;
                border: 1px solid #b0bec5;
                border-radius: 5px;
                padding: 4px 8px;
            }
        """)
        setattr(self, f"POS_CURR_{axis1}", curr1)
        grid.addWidget(curr1, row_idx, 1)

        des1 = QLineEdit("0.0", table_frame)
        des1.setMinimumHeight(44)
        des1.setMaximumWidth(100)
        des1.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                font-weight: bold;
                font-size: 15px;
                border: 1px solid #b0bec5;
                border-radius: 5px;
                padding: 4px 8px;
            }
        """)
        setattr(self, f"POS_DES_{axis1}", des1)
        register_touch_line_edit(self, des1, label_name=f"Target Pos {name1}")
        grid.addWidget(des1, row_idx, 2)

        btn_min1 = QPushButton(f"- {name1}", table_frame)
        btn_min1.setStyleSheet(button_style)
        setattr(self, f"MIN_{axis1}", btn_min1)
        grid.addWidget(btn_min1, row_idx, 3)

        btn_plus1 = QPushButton(f"+ {name1}", table_frame)
        btn_plus1.setStyleSheet(button_style)
        setattr(self, f"PLUS_{axis1}", btn_plus1)
        grid.addWidget(btn_plus1, row_idx, 4)

        # --- Block 2 ---
        axis2, name2 = b2
        lbl2 = QLabel(f"{name2}", table_frame)
        lbl2.setStyleSheet("font-weight: bold; font-size: 17px; color: #1565c0; border: none;")
        lbl2.setAlignment(Qt.AlignCenter)
        grid.addWidget(lbl2, row_idx, 5)

        curr2 = QLineEdit("0.0", table_frame)
        curr2.setReadOnly(True)
        curr2.setMinimumHeight(44)
        curr2.setMaximumWidth(100)
        curr2.setStyleSheet("""
            QLineEdit {
                background-color: #f5f5f5;
                font-weight: bold;
                font-size: 15px;
                border: 1px solid #b0bec5;
                border-radius: 5px;
                padding: 4px 8px;
            }
        """)
        setattr(self, f"POS_CURR_{axis2}", curr2)
        grid.addWidget(curr2, row_idx, 6)

        des2 = QLineEdit("0.0", table_frame)
        des2.setMinimumHeight(44)
        des2.setMaximumWidth(100)
        des2.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                font-weight: bold;
                font-size: 15px;
                border: 1px solid #b0bec5;
                border-radius: 5px;
                padding: 4px 8px;
            }
        """)
        setattr(self, f"POS_DES_{axis2}", des2)
        register_touch_line_edit(self, des2, label_name=f"Target Pos {name2}")
        grid.addWidget(des2, row_idx, 7)

        btn_min2 = QPushButton(f"- {name2}", table_frame)
        btn_min2.setStyleSheet(button_style)
        setattr(self, f"MIN_{axis2}", btn_min2)
        grid.addWidget(btn_min2, row_idx, 8)

        btn_plus2 = QPushButton(f"+ {name2}", table_frame)
        btn_plus2.setStyleSheet(button_style)
        setattr(self, f"PLUS_{axis2}", btn_plus2)
        grid.addWidget(btn_plus2, row_idx, 9)

    layout.addWidget(table_frame)

    # Config Frame for Platform Dimensions and Offset Rotations in one row
    config_frame = QFrame(self.tab_platform)
    config_frame.setStyleSheet("QFrame { border: 1px solid #cfd8dc; border-radius: 6px; background-color: #ffffff; }")
    config_hlayout = QHBoxLayout(config_frame)
    config_hlayout.setContentsMargins(12, 10, 12, 10)
    config_hlayout.setSpacing(8)

    # Style for inputs
    input_style = """
        QLineEdit {
            background-color: #ffffff;
            font-weight: bold;
            font-size: 14px;
            border: 1px solid #b0bec5;
            border-radius: 4px;
            padding: 4px 8px;
        }
    """

    label_style = "font-weight: bold; color: #37474f; font-size: 14px; border: none;"
    label_sub_style = "color: #546e7a; font-size: 14px; border: none;"

    # 1. Platform Dimensions Part
    lbl_dim_title = QLabel("Platform Dimensions:", config_frame)
    lbl_dim_title.setStyleSheet(label_style)
    config_hlayout.addWidget(lbl_dim_title)

    lbl_dim_lat = QLabel("LAT (mm):", config_frame)
    lbl_dim_lat.setStyleSheet(label_sub_style)
    config_hlayout.addWidget(lbl_dim_lat)

    self.input_plat_lat = QLineEdit("0.0", config_frame)
    self.input_plat_lat.setStyleSheet(input_style)
    self.input_plat_lat.setMinimumHeight(35)
    self.input_plat_lat.setMaximumWidth(90)
    register_touch_line_edit(self, self.input_plat_lat, label_name="Platform LAT (mm)")
    config_hlayout.addWidget(self.input_plat_lat)

    lbl_dim_si = QLabel("SI (mm):", config_frame)
    lbl_dim_si.setStyleSheet(label_sub_style)
    config_hlayout.addWidget(lbl_dim_si)

    self.input_plat_si = QLineEdit("0.0", config_frame)
    self.input_plat_si.setStyleSheet(input_style)
    self.input_plat_si.setMinimumHeight(35)
    self.input_plat_si.setMaximumWidth(90)
    register_touch_line_edit(self, self.input_plat_si, label_name="Platform SI (mm)")
    config_hlayout.addWidget(self.input_plat_si)

    # Separator Line
    sep = QFrame(config_frame)
    sep.setFrameShape(QFrame.VLine)
    sep.setFrameShadow(QFrame.Sunken)
    sep.setStyleSheet("border: none; background-color: #cfd8dc; width: 1px; margin: 0px 8px;")
    config_hlayout.addWidget(sep)

    # 2. Offset Rot. (mm) Part
    lbl_off_title = QLabel("Offset Rot. (mm):", config_frame)
    lbl_off_title.setStyleSheet(label_style)
    config_hlayout.addWidget(lbl_off_title)

    lbl_off_ap = QLabel("AP:", config_frame)
    lbl_off_ap.setStyleSheet(label_sub_style)
    config_hlayout.addWidget(lbl_off_ap)

    self.input_offset_ap = QLineEdit("0.0", config_frame)
    self.input_offset_ap.setStyleSheet(input_style)
    self.input_offset_ap.setMinimumHeight(35)
    self.input_offset_ap.setMaximumWidth(90)
    register_touch_line_edit(self, self.input_offset_ap, label_name="Offset AP (mm)")
    config_hlayout.addWidget(self.input_offset_ap)

    lbl_off_lat = QLabel("LAT:", config_frame)
    lbl_off_lat.setStyleSheet(label_sub_style)
    config_hlayout.addWidget(lbl_off_lat)

    self.input_offset_lat = QLineEdit("0.0", config_frame)
    self.input_offset_lat.setStyleSheet(input_style)
    self.input_offset_lat.setMinimumHeight(35)
    self.input_offset_lat.setMaximumWidth(90)
    register_touch_line_edit(self, self.input_offset_lat, label_name="Offset LAT (mm)")
    config_hlayout.addWidget(self.input_offset_lat)

    lbl_off_si = QLabel("SI:", config_frame)
    lbl_off_si.setStyleSheet(label_sub_style)
    config_hlayout.addWidget(lbl_off_si)

    self.input_offset_si = QLineEdit("0.0", config_frame)
    self.input_offset_si.setStyleSheet(input_style)
    self.input_offset_si.setMinimumHeight(35)
    self.input_offset_si.setMaximumWidth(90)
    register_touch_line_edit(self, self.input_offset_si, label_name="Offset SI (mm)")
    config_hlayout.addWidget(self.input_offset_si)

    # Separator Line before buttons
    sep_btn = QFrame(config_frame)
    sep_btn.setFrameShape(QFrame.VLine)
    sep_btn.setFrameShadow(QFrame.Sunken)
    sep_btn.setStyleSheet("border: none; background-color: #cfd8dc; width: 1px; margin: 0px 8px;")
    config_hlayout.addWidget(sep_btn)

    # Go to ... Button
    self.btn_go_to = QPushButton("Go to ...", config_frame)
    self.btn_go_to.setMinimumHeight(45)
    self.btn_go_to.setMinimumWidth(140)
    self.btn_go_to.setStyleSheet("""
        QPushButton {
            background-color: blue;
            color: white;
            font-weight: bold;
            font-size: 16px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover { background-color: #1a73e8; }
        QPushButton:pressed { background-color: #0d47a1; padding-top: 3px; padding-left: 3px; }
    """)
    self.btn_go_to.clicked.connect(lambda: __import__('fcn_control.fcn_control', fromlist=['go_to_desired_positions']).go_to_desired_positions(self))
    config_hlayout.addWidget(self.btn_go_to)

    # Go to center Button
    self.btn_go_to_center = QPushButton("Go to center", config_frame)
    self.btn_go_to_center.setMinimumHeight(45)
    self.btn_go_to_center.setMinimumWidth(140)
    self.btn_go_to_center.setStyleSheet("""
        QPushButton {
            background-color: blue;
            color: white;
            font-weight: bold;
            font-size: 16px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover { background-color: #1a73e8; }
        QPushButton:pressed { background-color: #0d47a1; padding-top: 3px; padding-left: 3px; }
    """)
    self.btn_go_to_center.clicked.connect(lambda: __import__('fcn_control.fcn_control', fromlist=['go_to_center']).go_to_center(self))
    config_hlayout.addWidget(self.btn_go_to_center)

    # Home ALL Button (Platform context)
    btn_home_all_plat = QPushButton("Home ALL", config_frame)
    btn_home_all_plat.setMinimumHeight(45)
    btn_home_all_plat.setMinimumWidth(140)
    btn_home_all_plat.setStyleSheet("""
        QPushButton {
            background-color: #2e7d32;
            color: white;
            font-weight: bold;
            font-size: 16px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover { background-color: #1b5e20; }
        QPushButton:pressed { background-color: #0d3c12; padding-top: 3px; padding-left: 3px; }
    """)
    setattr(self, "HOME_ALL_PLATFORM", btn_home_all_plat)
    config_hlayout.addWidget(btn_home_all_plat)

    config_hlayout.addStretch()

    # Save to config on editingFinished
    self.input_plat_lat.editingFinished.connect(lambda: __import__('fcn_control.fcn_control', fromlist=['save_configuration']).save_configuration(self))
    self.input_plat_si.editingFinished.connect(lambda: __import__('fcn_control.fcn_control', fromlist=['save_configuration']).save_configuration(self))

    layout.addWidget(config_frame)
    layout.addStretch()


def build_external_motors_subtab(self):
    """
    Build the 'Ind. Motors' sub-tab inside Control.
    Line 1: A, B, C, D, X, Y, Z (Row 0 = Buttons, Row 1 = Curr Pos)
      Line 2 Left: 'a, 'c, 'e, 'f (Row 2 = Buttons with single quote prefix, Row 3 = Curr Pos)
    Line 2 Right (Cols 4..6):
      Row 2: Target Pos entry + Move Axis button + Home Axis button
      Row 3: Shared - and + Jog Buttons (placed directly below Target Pos / Move Axis / Home Axis)
    """
    layout = QVBoxLayout(self.tab_4)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)

    # Main Panel Frame
    main_frame = QFrame(self.tab_4)
    main_frame.setStyleSheet("QFrame { border: 1px solid #cfd8dc; border-radius: 6px; background-color: #ffffff; }")
    frame_layout = QVBoxLayout(main_frame)
    frame_layout.setContentsMargins(14, 12, 14, 12)
    frame_layout.setSpacing(10)

    line1_axes = ['A', 'B', 'C', 'D', 'X', 'Y', 'Z']
    line2_axes = ["'a", "'c", "'e", "'f"]

    self.selected_ext_axis = 'A'
    self.ext_axis_buttons = {}
    self.ext_curr_pos_fields = {}
    self.ext_axes_homed = {ax: False for ax in (line1_axes + line2_axes)}

    from fcn_control.fcn_control import select_external_axis

    # Header title
    lbl_title = QLabel("Individual Axis Selection", main_frame)
    lbl_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #37474f; border: none;")
    frame_layout.addWidget(lbl_title)

    # Grid for Axis Buttons, Positions & Controls (7 Columns)
    grid_axes = QGridLayout()
    grid_axes.setHorizontalSpacing(8)
    grid_axes.setVerticalSpacing(8)

    for col in range(7):
        grid_axes.setColumnStretch(col, 1)

    # --- LINE 1: A, B, C, D, X, Y, Z (Row 0 = Buttons, Row 1 = Curr Pos) ---
    for idx, axis_name in enumerate(line1_axes):
        btn = QPushButton(f"{axis_name}", main_frame)
        btn.setCheckable(True)
        btn.setMinimumHeight(44)
        btn.setFont(QFont("Arial", 13, QFont.Bold))
        btn.clicked.connect(lambda _c=False, a=axis_name: select_external_axis(self, a))
        self.ext_axis_buttons[axis_name] = btn
        grid_axes.addWidget(btn, 0, idx)

        pos_field = QLineEdit("0.000", main_frame)
        pos_field.setReadOnly(True)
        pos_field.setMinimumHeight(36)
        pos_field.setAlignment(Qt.AlignCenter)
        pos_field.setStyleSheet("""
            QLineEdit {
                background-color: #f5f5f5;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #b0bec5;
                border-radius: 5px;
            }
        """)
        setattr(self, f"POS_CURR_{axis_name}", pos_field)
        self.ext_curr_pos_fields[axis_name] = pos_field
        grid_axes.addWidget(pos_field, 1, idx)

    # --- LINE 2 LEFT: 'a, 'c, 'e, 'f (Row 2 = Buttons, Row 3 = Curr Pos) ---
    for idx, axis_name in enumerate(line2_axes):
        btn = QPushButton(f"{axis_name}", main_frame)
        btn.setCheckable(True)
        btn.setMinimumHeight(44)
        btn.setFont(QFont("Arial", 13, QFont.Bold))
        btn.clicked.connect(lambda _c=False, a=axis_name: select_external_axis(self, a))
        self.ext_axis_buttons[axis_name] = btn
        grid_axes.addWidget(btn, 2, idx)

        pos_field = QLineEdit("0.000", main_frame)
        pos_field.setReadOnly(True)
        pos_field.setMinimumHeight(36)
        pos_field.setAlignment(Qt.AlignCenter)
        pos_field.setStyleSheet("""
            QLineEdit {
                background-color: #f5f5f5;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #b0bec5;
                border-radius: 5px;
            }
        """)
        setattr(self, f"POS_CURR_{axis_name}", pos_field)
        self.ext_curr_pos_fields[axis_name] = pos_field
        grid_axes.addWidget(pos_field, 3, idx)

    # --- LINE 2 RIGHT (Cols 4..6): ROW 2 = TARGET POS, MOVE AXIS & HOME AXIS ---
    target_box = QHBoxLayout()
    target_box.setContentsMargins(0, 0, 0, 0)
    target_box.setSpacing(6)

    lbl_des = QLabel("Target Pos:", main_frame)
    lbl_des.setStyleSheet("font-weight: bold; font-size: 13px; border: none;")
    
    self.POS_DES_EXT = QLineEdit("0.0", main_frame)
    self.POS_DES_EXT.setMinimumHeight(44)
    self.POS_DES_EXT.setMaximumWidth(80)
    self.POS_DES_EXT.setStyleSheet("""
        QLineEdit {
            background-color: #ffffff;
            font-weight: bold;
            font-size: 14px;
            border: 1px solid #b0bec5;
            border-radius: 5px;
            padding: 4px;
        }
    """)
    register_touch_line_edit(self, self.POS_DES_EXT, label_name="Individual Axis Target Pos")

    self.btn_move_ext = QPushButton("Move Axis", main_frame)
    self.btn_move_ext.setMinimumHeight(44)
    self.btn_move_ext.setStyleSheet("""
        QPushButton {
            background-color: #1565c0;
            color: white;
            font-weight: bold;
            font-size: 14px;
            padding: 4px 10px;
            border-radius: 5px;
        }
    """)

    self.btn_home_ext = QPushButton("Home Axis A", main_frame)
    self.btn_home_ext.setMinimumHeight(44)
    self.btn_home_ext.setStyleSheet("""
        QPushButton {
            background-color: #d32f2f;
            color: white;
            font-weight: bold;
            font-size: 14px;
            padding: 4px 10px;
            border-radius: 5px;
        }
    """)

    target_box.addWidget(lbl_des)
    target_box.addWidget(self.POS_DES_EXT)
    target_box.addWidget(self.btn_move_ext)
    target_box.addWidget(self.btn_home_ext)

    grid_axes.addLayout(target_box, 2, 4, 1, 3)

    # --- LINE 2 RIGHT (Cols 4..6): ROW 3 = SHARED JOG BUTTONS DIRECTLY BELOW TARGET POS/MOVE/HOME ---
    jog_hlayout = QHBoxLayout()
    jog_hlayout.setContentsMargins(0, 0, 0, 0)
    jog_hlayout.setSpacing(6)

    self.btn_ext_jog_min = QPushButton("- Axis A", main_frame)
    self.btn_ext_jog_plus = QPushButton("+ Axis A", main_frame)

    jog_btn_style = """
        QPushButton {
            background-color: blue;
            color: white;
            font-weight: bold;
            font-size: 15px;
            min-height: 44px;
            border-radius: 5px;
        }
    """
    self.btn_ext_jog_min.setStyleSheet(jog_btn_style)
    self.btn_ext_jog_plus.setStyleSheet(jog_btn_style)

    jog_hlayout.addWidget(self.btn_ext_jog_min, 1)
    jog_hlayout.addWidget(self.btn_ext_jog_plus, 1)

    grid_axes.addLayout(jog_hlayout, 3, 4, 1, 3)

    frame_layout.addLayout(grid_axes)
    layout.addWidget(main_frame)
    layout.addStretch()

    # Select initial axis 'A'
    select_external_axis(self, 'A')
