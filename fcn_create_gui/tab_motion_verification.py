"""
Motion Verification Tab creation for TRACE GUI
Constructs MoVe canvas plot, axis selections, speed control, radiation trigger, and Emergency Stop 4.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QPushButton, QCheckBox, QSpinBox, QSlider, QLabel
)

def build_motion_verification_tab(self):
    """Populate self.tab_phantom_operation with Motion Verification tab widgets."""
    layout_main = QVBoxLayout(self.tab_phantom_operation)
    layout_main.setContentsMargins(10, 10, 10, 10)

    # Top Control Bar
    top_layout = QHBoxLayout()

    # Axis selection group
    gb_axes = QGroupBox("Select Motion Axes", self.tab_phantom_operation)
    axes_layout = QHBoxLayout(gb_axes)
    self.check_axis_X = QCheckBox("Axis X", gb_axes)
    self.check_axis_Y = QCheckBox("Axis Y", gb_axes)
    self.check_axis_Z = QCheckBox("Axis Z", gb_axes)
    axes_layout.addWidget(self.check_axis_X)
    axes_layout.addWidget(self.check_axis_Y)
    axes_layout.addWidget(self.check_axis_Z)
    top_layout.addWidget(gb_axes)

    # Speed & Offset group
    gb_speed = QGroupBox("Speed & Offset Control", self.tab_phantom_operation)
    sp_layout = QHBoxLayout(gb_speed)

    sp_layout.addWidget(QLabel("Speed (%):"))
    self.MoVeSpeedFactor = QSpinBox(gb_speed)
    self.MoVeSpeedFactor.setRange(1, 300)
    self.MoVeSpeedFactor.setValue(100)
    sp_layout.addWidget(self.MoVeSpeedFactor)

    self.MoVeAutoControl = QCheckBox("Auto Control", gb_speed)
    sp_layout.addWidget(self.MoVeAutoControl)

    sp_layout.addWidget(QLabel("Offset:"))
    self.MoVeOffsetSlider = QSlider(Qt.Horizontal, gb_speed)
    sp_layout.addWidget(self.MoVeOffsetSlider)
    top_layout.addWidget(gb_speed)

    # Trigger group
    gb_trig = QGroupBox("Radiation Trigger", self.tab_phantom_operation)
    trig_layout = QHBoxLayout(gb_trig)
    self.stop_until_radiation = QCheckBox("Pause until Radiation Trigger", gb_trig)
    trig_layout.addWidget(self.stop_until_radiation)
    top_layout.addWidget(gb_trig)

    # Emergency Button 4
    self.emergencyButton_4 = QPushButton("Emergency STOP", self.tab_phantom_operation)
    self.emergencyButton_4.setStyleSheet("background-color: red; color: white; font-weight: bold; font-size: 14px;")
    self.emergencyButton_4.setMinimumHeight(40)
    top_layout.addWidget(self.emergencyButton_4)

    layout_main.addLayout(top_layout)

    # Motion Verification Canvas Container
    self.MoVeView = QWidget(self.tab_phantom_operation)
    layout_main.addWidget(self.MoVeView)
