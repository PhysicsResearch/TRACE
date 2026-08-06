"""
Control Tab creation for TRACE GUI
Constructs Duet IP config, Touchscreen Mode toggle, Emergency Stop,
  Lung Phantom, Platform (2 axes per row), and Ind. Motors (Line 1: A, B, C, D, X, Y, Z; Line 2: 'a, 'c, 'e, 'f with Target Pos, Move Axis, Home Axis in Row 2 and -/+ Jog buttons in Row 3),
plus bottom panel with Command Console + Vertical Step Size Selector Bar (0.1, 0.5, 1, 10 mm).
"""

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QFrame,
    QPushButton, QLineEdit, QRadioButton, QCheckBox, QTabWidget, QLabel, QTextEdit, QSizePolicy,
    QStylePainter, QStyleOptionButton, QStyle
)
from fcn_create_gui.touch_keyboard import register_touch_line_edit


class RotatedButton(QPushButton):
    """
    QPushButton with text rotated 90 degrees (vertical text).
    """
    def __init__(self, text, parent=None, rotation=-90):
        super().__init__(text, parent)
        self.rotation = rotation

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        
        text = option.text
        option.text = ""  # Hide standard horizontal text
        painter.drawControl(QStyle.CE_PushButton, option)
        
        painter.save()
        painter.setPen(Qt.white)

        font = self.font()
        font.setBold(True)
        font.setPointSize(15)
        painter.setFont(font)
        
        rect = self.rect()
        painter.translate(rect.center())
        painter.rotate(self.rotation)
        
        text_rect = QRect(-rect.height() // 2, -rect.width() // 2, rect.height(), rect.width())
        painter.drawText(text_rect, Qt.AlignCenter, text)
        painter.restore()


def build_control_tab(self):
    """Populate self.tab_2 with all Control tab widgets."""
    layout_main = QVBoxLayout(self.tab_2)
    layout_main.setContentsMargins(6, 6, 6, 6)
    layout_main.setSpacing(6)

    # --- 1. TOP CONFIGURATION BAR ---
    self.top_bar_frame = QFrame(self.tab_2)
    self.top_bar_frame.setObjectName("top_bar_frame")
    self.top_bar_frame.setMinimumHeight(52)
    self.top_bar_frame.setStyleSheet("""
        QFrame#top_bar_frame {
            background-color: #ffebee;
            border: 2px solid #d32f2f;
            border-radius: 8px;
        }
    """)
    top_bar_layout = QHBoxLayout(self.top_bar_frame)
    top_bar_layout.setAlignment(Qt.AlignVCenter)
    top_bar_layout.setContentsMargins(12, 6, 12, 6)
    top_bar_layout.setSpacing(12)

    label_ip = QLabel("Duet IP:", self.top_bar_frame)
    label_ip.setAlignment(Qt.AlignVCenter)
    label_ip.setStyleSheet("font-weight: bold; font-size: 15px; color: #263238;")
    
    self.DuetIPAddress = QLineEdit(self.top_bar_frame)
    self.DuetIPAddress.setText("192.168.8.3")
    self.DuetIPAddress.setFixedWidth(180)
    self.DuetIPAddress.setFixedHeight(36)
    self.DuetIPAddress.setStyleSheet("""
        QLineEdit {
            font-weight: bold;
            font-size: 15px;
            padding: 0px 10px;
            border: 1px solid #b0bec5;
            border-radius: 6px;
            background-color: #ffffff;
        }
    """)
    register_touch_line_edit(self, self.DuetIPAddress, label_name="Duet IP Address")
 
    self.setDuetIP = QPushButton("Connect", self.top_bar_frame)
    self.setDuetIP.setFixedHeight(36)
    self.setDuetIP.setMinimumWidth(130)
    self.setDuetIP.setStyleSheet("""
        QPushButton {
            background-color: #1976d2;
            color: white;
            font-weight: bold;
            font-size: 15px;
            padding: 0px 16px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover { background-color: #1565c0; }
    """)
    
    self.btn_ip_lungphan = QPushButton("LungPhan", self.top_bar_frame)
    self.btn_ip_lungphan.setFixedHeight(36)
    self.btn_ip_lungphan.setFixedWidth(130)
    self.btn_ip_lungphan.setStyleSheet("""
        QPushButton {
            background-color: orange;
            color: white;
            font-weight: bold;
            font-size: 15px;
            padding: 0px 16px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover { background-color: darkorange; }
    """)
    self.btn_ip_lungphan.clicked.connect(lambda: (self.DuetIPAddress.setText("192.168.8.3"), self.setDuetIP.click()))

    self.btn_ip_trace = QPushButton("TRACE", self.top_bar_frame)
    self.btn_ip_trace.setFixedHeight(36)
    self.btn_ip_trace.setFixedWidth(130)
    self.btn_ip_trace.setStyleSheet("""
        QPushButton {
            background-color: purple;
            color: white;
            font-weight: bold;
            font-size: 15px;
            padding: 0px 16px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover { background-color: darkmagenta; }
    """)
    self.btn_ip_trace.clicked.connect(lambda: (self.DuetIPAddress.setText("192.168.8.2"), self.setDuetIP.click()))

    self.connect_status = QLabel("NOT CONNECTED", self.top_bar_frame)
    self.connect_status.setAlignment(Qt.AlignCenter)
    self.connect_status.setFixedHeight(36)
    self.connect_status.setMinimumWidth(200)
    self.connect_status.setStyleSheet("""
        QLabel {
            background-color: #ffebee;
            color: #c62828;
            font-weight: bold;
            font-size: 14px;
            padding: 0px 16px;
            border: 1px solid #ef9a9a;
            border-radius: 18px;
        }
    """)
 
    self.check_touchscreen = QPushButton("Touch Screen: OFF", self.top_bar_frame)
    self.check_touchscreen.setCheckable(True)
    self.check_touchscreen.setChecked(False)
    self.check_touchscreen.setMinimumWidth(210)

    _touchscreen_style_on = """
        QPushButton {
            background-color: #1976d2;
            color: #ffffff;
            font-weight: bold;
            font-size: 15px;
            padding: 0px 16px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover { background-color: #1565c0; }
    """
    _touchscreen_style_off = """
        QPushButton {
            background-color: #90caf9;
            color: #000000;
            font-weight: bold;
            font-size: 15px;
            padding: 0px 16px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover { background-color: #64b5f6; }
    """

    def update_touchscreen_ui(checked):
        # Read height from Connect button to stay in sync after any scaling
        ref_height = self.setDuetIP.height()
        # Read font-size from Connect button's stylesheet
        import re
        ref_style = self.setDuetIP.styleSheet()
        font_match = re.search(r'font-size\s*:\s*(\d+)px', ref_style)
        font_size = font_match.group(1) if font_match else '15'
        
        if checked:
            self.check_touchscreen.setText("Touch Screen: ON")
            self.check_touchscreen.setStyleSheet(f"""
                QPushButton {{
                    background-color: #1976d2;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: {font_size}px;
                    padding: 0px 16px;
                    border-radius: 6px;
                    border: none;
                }}
                QPushButton:hover {{ background-color: #1565c0; }}
            """)
        else:
            self.check_touchscreen.setText("Touch Screen: OFF")
            self.check_touchscreen.setStyleSheet(f"""
                QPushButton {{
                    background-color: #90caf9;
                    color: #000000;
                    font-weight: bold;
                    font-size: {font_size}px;
                    padding: 0px 16px;
                    border-radius: 6px;
                    border: none;
                }}
                QPushButton:hover {{ background-color: #64b5f6; }}
            """)
        self.check_touchscreen.setFixedHeight(ref_height)

    self.update_touchscreen_ui = update_touchscreen_ui

    def on_touchscreen_toggled(checked):
        update_touchscreen_ui(checked)
        from fcn_control.fcn_control import save_configuration
        save_configuration(self)

    # Apply initial style FIRST, then lock height
    self.check_touchscreen.setStyleSheet(_touchscreen_style_off)
    self.check_touchscreen.setFixedHeight(36)
    self.check_touchscreen.toggled.connect(on_touchscreen_toggled)

    top_bar_layout.addWidget(label_ip, 0, Qt.AlignVCenter)
    top_bar_layout.addWidget(self.DuetIPAddress, 0, Qt.AlignVCenter)
    top_bar_layout.addWidget(self.setDuetIP, 0, Qt.AlignVCenter)
    top_bar_layout.addWidget(self.btn_ip_lungphan, 0, Qt.AlignVCenter)
    top_bar_layout.addWidget(self.btn_ip_trace, 0, Qt.AlignVCenter)
    top_bar_layout.addWidget(self.connect_status, 0, Qt.AlignVCenter)
    top_bar_layout.addWidget(self.check_touchscreen, 0, Qt.AlignVCenter)
    top_bar_layout.addStretch()
 
    # Emergency Stop Button 1
    self.emergencyButton_1 = QPushButton("Emergency STOP", self.top_bar_frame)
    self.emergencyButton_1.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold; font-size: 15px; padding: 0px 16px; border-radius: 6px;")
    self.emergencyButton_1.setFixedHeight(36)
    self.emergencyButton_1.setMinimumWidth(200)
    top_bar_layout.addWidget(self.emergencyButton_1, 0, Qt.AlignVCenter)

    layout_main.addWidget(self.top_bar_frame)

    # --- 2. SUB-TABS: LUNG PHANTOM, PLATFORM & IND. MOTORS ---
    self.tabWidget = QTabWidget(self.tab_2)
    self.tabWidget.setStyleSheet("""
        QTabBar::tab {
            font-weight: bold;
            font-size: 16px;
            color: #424242;
            padding: 8px 22px;
            min-height: 40px;
            margin-right: 4px;
            background-color: transparent;
            border-bottom: 2px solid #e0e0e0;
        }
        QTabBar::tab:hover {
            color: #1976d2;
            background-color: #f5f5f5;
        }
        QTabBar::tab:selected {
            color: #1565c0;
            font-size: 20px;
            font-weight: bold;
            border-bottom: 4px solid #1565c0;
            background-color: transparent;
        }
        QTabWidget::pane {
            border: 1px solid #cfd8dc;
            border-radius: 4px;
            background-color: #ffffff;
        }
    """)
    
    # Sub-Tab 0: Lung Phantom
    self.tab = QWidget()
    build_motion_platform_subtab(self)
    self.tabWidget.addTab(self.tab, "LUNG PHANTOM")

    # Sub-Tab 1: Platform (2 axes per row with 50px tall buttons)
    self.tab_platform = QWidget()
    build_platform_subtab(self)
    self.tabWidget.addTab(self.tab_platform, "PLATFORM")

    # Sub-Tab 2: Ind. Motors
    self.tab_4 = QWidget()
    build_external_motors_subtab(self)
    self.tabWidget.addTab(self.tab_4, "IND. MOTORS")

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
    register_touch_line_edit(self, self.duet_command, label_name="Send Command", keyboard_mode="full")

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
    Build the 'Lung Phantom' sub-tab inside Control.
    Top Panel: Single row containing X, Y, Z Current Pos readouts & Target Pos input fields + ONE 'Go to' button.
    Bottom Panel: Jog (- / +) and Homing buttons for X, Y, Z with vertical 'Home ALL' on the far right.
    """
    layout = QVBoxLayout(self.tab)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(8)

    # --- 1. TOP PANEL: POSITION INPUTS & SINGLE GO TO BUTTON ---
    pos_frame = QFrame(self.tab)
    pos_frame.setFixedHeight(60)
    pos_frame.setStyleSheet("QFrame { border: 1px solid #cfd8dc; border-radius: 6px; background-color: #ffffff; }")
    pos_layout = QHBoxLayout(pos_frame)
    pos_layout.setAlignment(Qt.AlignVCenter)
    pos_layout.setContentsMargins(16, 8, 16, 8)
    pos_layout.setSpacing(10)

    axes = ['XAXIS', 'YAXIS', 'ZAXIS']
    labels = ['X', 'Y', 'Z']

    for idx, (axis, name) in enumerate(zip(axes, labels)):
        # Axis Label
        axis_lbl = QLabel(f"{name}", pos_frame)
        axis_lbl.setAlignment(Qt.AlignVCenter)
        axis_lbl.setStyleSheet("font-weight: bold; font-size: 18px; color: #1565c0; border: none;")
        pos_layout.addWidget(axis_lbl, 0, Qt.AlignVCenter)

        # Current Pos
        lbl_curr = QLabel("Curr:", pos_frame)
        lbl_curr.setAlignment(Qt.AlignVCenter)
        lbl_curr.setStyleSheet("font-weight: bold; color: #546e7a; font-size: 13px; border: none;")
        pos_layout.addWidget(lbl_curr, 0, Qt.AlignVCenter)

        curr_pos = QLineEdit("0.0", pos_frame)
        curr_pos.setReadOnly(True)
        curr_pos.setFixedHeight(36)
        curr_pos.setMinimumWidth(80)
        curr_pos.setMaximumWidth(100)
        curr_pos.setStyleSheet("""
            QLineEdit {
                background-color: #f5f5f5;
                font-weight: bold;
                font-size: 15px;
                border: 1px solid #b0bec5;
                border-radius: 5px;
                padding: 0px 6px;
            }
        """)
        setattr(self, f"POS_CURR_{axis}_LUNG", curr_pos)
        pos_layout.addWidget(curr_pos, 0, Qt.AlignVCenter)

        # Target Pos
        lbl_des = QLabel("Target:", pos_frame)
        lbl_des.setAlignment(Qt.AlignVCenter)
        lbl_des.setStyleSheet("font-weight: bold; color: #37474f; font-size: 13px; border: none;")
        pos_layout.addWidget(lbl_des, 0, Qt.AlignVCenter)

        des_pos = QLineEdit("0.0", pos_frame)
        des_pos.setFixedHeight(36)
        des_pos.setMinimumWidth(80)
        des_pos.setMaximumWidth(100)
        des_pos.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                font-weight: bold;
                font-size: 15px;
                border: 1px solid #b0bec5;
                border-radius: 5px;
                padding: 0px 6px;
            }
        """)
        setattr(self, f"POS_DES_{axis}_LUNG", des_pos)
        register_touch_line_edit(self, des_pos, label_name=f"Target Pos {name}")
        pos_layout.addWidget(des_pos, 0, Qt.AlignVCenter)

        # Separator line & stretch between axes
        if idx < len(axes) - 1:
            pos_layout.addStretch(1)
            sep = QFrame(pos_frame)
            sep.setFixedHeight(28)
            sep.setFrameShape(QFrame.VLine)
            sep.setFrameShadow(QFrame.Sunken)
            sep.setStyleSheet("border: none; background-color: #cfd8dc; width: 1px; margin: 0px 8px;")
            pos_layout.addWidget(sep, 0, Qt.AlignVCenter)
            pos_layout.addStretch(1)

    pos_layout.addStretch(2)

    # Single Go to Button
    self.btn_goto_lung = QPushButton("Go to", pos_frame)
    self.btn_goto_lung.setFixedHeight(36)
    self.btn_goto_lung.setMinimumWidth(140)
    self.btn_goto_lung.setStyleSheet("""
        QPushButton {
            background-color: #1976d2;
            color: white;
            font-weight: bold;
            font-size: 16px;
            padding: 0px 20px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover { background-color: #1565c0; }
    """)
    pos_layout.addWidget(self.btn_goto_lung, 0, Qt.AlignVCenter)
    layout.addWidget(pos_frame)

    # --- 2. BOTTOM PANEL: JOG & HOMING CONTROLS ---
    table_frame = QFrame(self.tab)
    table_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    table_frame.setStyleSheet("QFrame { border: 1px solid #cfd8dc; border-radius: 6px; background-color: #ffffff; }")
    grid = QGridLayout(table_frame)
    grid.setContentsMargins(12, 10, 12, 10)
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(10)

    grid.setColumnStretch(0, 1) # Jog -
    grid.setColumnStretch(1, 1) # Jog +
    grid.setColumnStretch(2, 1) # Homing
    grid.setColumnStretch(3, 0) # Home ALL (Vertical)

    grid.setRowStretch(0, 0) # Headers
    grid.setRowStretch(1, 1) # Row X
    grid.setRowStretch(2, 1) # Row Y
    grid.setRowStretch(3, 1) # Row Z

    headers = ["Jog -", "Jog +", "Homing"]
    for col_idx, h_text in enumerate(headers):
        lbl = QLabel(h_text, table_frame)
        lbl.setStyleSheet("font-weight: bold; color: #37474f; font-size: 16px; border: none;")
        lbl.setAlignment(Qt.AlignCenter)
        grid.addWidget(lbl, 0, col_idx)

    button_style = """
        QPushButton {
            background-color: #d32f2f;
            color: white;
            font-weight: bold;
            font-size: 20px;
            min-height: 45px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover {
            background-color: #b71c1c;
        }
    """

    for row_idx, (axis, name) in enumerate(zip(axes, labels), start=1):
        # 1. Minus Jog Button
        btn_min = QPushButton(f"- {name}", table_frame)
        btn_min.setStyleSheet(button_style)
        btn_min.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        setattr(self, f"MIN_{axis}_LUNG", btn_min)
        grid.addWidget(btn_min, row_idx, 0)

        # 2. Plus Jog Button
        btn_plus = QPushButton(f"+ {name}", table_frame)
        btn_plus.setStyleSheet(button_style)
        btn_plus.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        setattr(self, f"PLUS_{axis}_LUNG", btn_plus)
        grid.addWidget(btn_plus, row_idx, 1)

        # 3. Home Axis Button
        btn_home = QPushButton(f"Home {name}", table_frame)
        btn_home.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                font-weight: bold;
                font-size: 20px;
                min-height: 45px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1b5e20;
            }
        """)
        btn_home.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        setattr(self, f"HOME_{name}", btn_home)
        grid.addWidget(btn_home, row_idx, 2)

    # Home ALL Button (Vertical button placed to the right of Home X..Z, spanning rows 1 to 3)
    btn_home_all = RotatedButton("Home ALL", table_frame, rotation=-90)
    btn_home_all.setFixedWidth(80)
    btn_home_all.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
    btn_home_all.setStyleSheet("""
        QPushButton {
            background-color: #2e7d32;
            color: white;
            font-weight: bold;
            font-size: 20px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover {
            background-color: #1b5e20;
        }
    """)
    setattr(self, "HOME_ALL", btn_home_all)
    grid.addWidget(btn_home_all, 1, 3, 3, 1)

    layout.addWidget(table_frame)


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
    table_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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

    grid.setRowStretch(0, 0) # Headers
    grid.setRowStretch(1, 1) # Row 1: LAT & SI
    grid.setRowStretch(2, 1) # Row 2: AP & Roll
    grid.setRowStretch(3, 1) # Row 3: Pitch & Yaw

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
        (('LATAXIS', 'LAT'), ('SIAXIS', 'SI')),
        (('APAXIS', 'AP'), ('ROLL', 'Roll')),
        (('PITCH', 'Pitch'), ('YAW', 'Yaw'))
    ]

    button_style = """
        QPushButton {
            background-color: #d32f2f;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover {
            background-color: #b71c1c;
        }
        QPushButton:pressed {
            background-color: #8e0000;
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
        btn_min1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        setattr(self, f"MIN_{axis1}", btn_min1)
        grid.addWidget(btn_min1, row_idx, 3)

        btn_plus1 = QPushButton(f"+ {name1}", table_frame)
        btn_plus1.setStyleSheet(button_style)
        btn_plus1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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
        btn_min2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        setattr(self, f"MIN_{axis2}", btn_min2)
        grid.addWidget(btn_min2, row_idx, 8)

        btn_plus2 = QPushButton(f"+ {name2}", table_frame)
        btn_plus2.setStyleSheet(button_style)
        btn_plus2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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

    self.input_plat_lat = QLineEdit("100.0", config_frame)
    self.input_plat_lat.setStyleSheet(input_style)
    self.input_plat_lat.setMinimumHeight(35)
    self.input_plat_lat.setMaximumWidth(90)
    register_touch_line_edit(self, self.input_plat_lat, label_name="Platform LAT (mm)")
    config_hlayout.addWidget(self.input_plat_lat)

    lbl_dim_si = QLabel("SI (mm):", config_frame)
    lbl_dim_si.setStyleSheet(label_sub_style)
    config_hlayout.addWidget(lbl_dim_si)

    self.input_plat_si = QLineEdit("100.0", config_frame)
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
            background-color: #d32f2f;
            color: white;
            font-weight: bold;
            font-size: 16px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover { background-color: #b71c1c; }
        QPushButton:pressed { background-color: #8e0000; padding-top: 3px; padding-left: 3px; }
    """)
    self.btn_go_to.clicked.connect(lambda: __import__('fcn_control.fcn_control', fromlist=['go_to_desired_positions']).go_to_desired_positions(self))
    config_hlayout.addWidget(self.btn_go_to)

    # Go to center Button
    self.btn_go_to_center = QPushButton("Go to center", config_frame)
    self.btn_go_to_center.setMinimumHeight(45)
    self.btn_go_to_center.setMinimumWidth(140)
    self.btn_go_to_center.setStyleSheet("""
        QPushButton {
            background-color: #d32f2f;
            color: white;
            font-weight: bold;
            font-size: 16px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover { background-color: #b71c1c; }
        QPushButton:pressed { background-color: #8e0000; padding-top: 3px; padding-left: 3px; }
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
    main_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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

    grid_axes.setRowStretch(0, 2)
    grid_axes.setRowStretch(1, 0)
    grid_axes.setRowStretch(2, 2)
    grid_axes.setRowStretch(3, 2)

    # --- LINE 1: A, B, C, D, X, Y, Z (Row 0 = Buttons, Row 1 = Curr Pos) ---
    for idx, axis_name in enumerate(line1_axes):
        btn = QPushButton(f"{axis_name}", main_frame)
        btn.setCheckable(True)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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
    self.btn_move_ext.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    self.btn_move_ext.setStyleSheet("""
        QPushButton {
            background-color: #d32f2f;
            color: white;
            font-weight: bold;
            font-size: 14px;
            padding: 4px 10px;
            border-radius: 5px;
        }
    """)

    self.btn_home_ext = QPushButton("Home Axis A", main_frame)
    self.btn_home_ext.setMinimumHeight(44)
    self.btn_home_ext.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    self.btn_home_ext.setStyleSheet("""
        QPushButton {
            background-color: #2e7d32;
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
    self.btn_ext_jog_min.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    self.btn_ext_jog_plus.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    jog_btn_style = """
        QPushButton {
            background-color: #d32f2f;
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

    # Select initial axis 'A'
    select_external_axis(self, 'A')
