"""
On-Screen Touchscreen Keyboard for TRACE GUI
Provides a clean, touch-friendly virtual keyboard dialog for 11", 13", and desktop screens.
Automatically pops up when Touchscreen Mode is enabled and a target line edit is clicked.
"""

from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLineEdit, QLabel, QFrame
)


class VirtualKeyboardDialog(QDialog):
    """
    On-Screen Touchscreen Virtual Keyboard Dialog.
    """
    def __init__(self, parent_widget, target_line_edit, title="On-Screen Keyboard"):
        super().__init__(parent_widget)
        self.target_line_edit = target_line_edit
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #263238;
                border: 2px solid #00bcd4;
                border-radius: 8px;
            }
        """)

        layout_main = QVBoxLayout(self)
        layout_main.setContentsMargins(12, 12, 12, 12)
        layout_main.setSpacing(8)

        # Header Title
        lbl_header = QLabel(f"Keyboard Input: {title}", self)
        lbl_header.setStyleSheet("color: #00e5ff; font-weight: bold; font-size: 13px;")
        layout_main.addWidget(lbl_header)

        # Display Preview LineEdit
        self.preview_edit = QLineEdit(target_line_edit.text(), self)
        self.preview_edit.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                color: #1a237e;
                font-weight: bold;
                font-size: 16px;
                padding: 6px 10px;
                border: 2px solid #00bcd4;
                border-radius: 4px;
            }
        """)
        layout_main.addWidget(self.preview_edit)

        # Key Button Styles
        key_style = """
            QPushButton {
                background-color: #37474f;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
                border: 1px solid #546e7a;
                border-radius: 5px;
                min-width: 40px;
                min-height: 42px;
            }
            QPushButton:hover {
                background-color: #455a64;
                border-color: #00e5ff;
            }
            QPushButton:pressed {
                background-color: #00acc1;
            }
        """

        action_key_style = """
            QPushButton {
                background-color: #00838f;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #00acc1;
                border-radius: 5px;
                min-height: 42px;
            }
            QPushButton:hover {
                background-color: #0097a7;
            }
            QPushButton:pressed {
                background-color: #006064;
            }
        """

        # Keyboard Rows Definition
        rows = [
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", ".", "-"],
            ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
            ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
            ["z", "x", "c", "v", "b", "n", "m"]
        ]

        for r_idx, keys in enumerate(rows):
            r_layout = QHBoxLayout()
            r_layout.setSpacing(5)
            r_layout.addStretch()

            for key_char in keys:
                btn = QPushButton(key_char, self)
                btn.setStyleSheet(key_style)
                btn.clicked.connect(lambda _c=False, ch=key_char: self.on_key_click(ch))
                r_layout.addWidget(btn)

            r_layout.addStretch()
            layout_main.addLayout(r_layout)

        # Control Row (Clear, Space, Backspace, Enter/Done)
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(6)

        btn_clear = QPushButton("Clear", self)
        btn_clear.setStyleSheet(action_key_style)
        btn_clear.clicked.connect(self.on_clear)

        btn_space = QPushButton("Space", self)
        btn_space.setStyleSheet(action_key_style)
        btn_space.setMinimumWidth(120)
        btn_space.clicked.connect(lambda: self.on_key_click(" "))

        btn_back = QPushButton("⌫ Back", self)
        btn_back.setStyleSheet(action_key_style)
        btn_back.clicked.connect(self.on_backspace)

        btn_done = QPushButton("✔ Done", self)
        btn_done.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
                border: 1px solid #4caf50;
                border-radius: 5px;
                min-height: 42px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #388e3c;
            }
        """)
        btn_done.clicked.connect(self.on_done)

        ctrl_layout.addWidget(btn_clear)
        ctrl_layout.addWidget(btn_space, stretch=1)
        ctrl_layout.addWidget(btn_back)
        ctrl_layout.addWidget(btn_done)
        layout_main.addLayout(ctrl_layout)

    def on_key_click(self, char):
        self.preview_edit.setText(self.preview_edit.text() + char)

    def on_backspace(self):
        curr = self.preview_edit.text()
        if curr:
            self.preview_edit.setText(curr[:-1])

    def on_clear(self):
        self.preview_edit.clear()

    def on_done(self):
        self.target_line_edit.setText(self.preview_edit.text())
        self.accept()


class TouchKeyboardEventFilter(QObject):
    """
    Event filter that intercepts click/focus events on LineEdits when Touchscreen Mode is active.
    """
    def __init__(self, main_app, target_line_edit, label_name="Field"):
        super().__init__(main_app)
        self.main_app = main_app
        self.target_line_edit = target_line_edit
        self.label_name = label_name
        self._dialog_open = False

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            if hasattr(self.main_app, 'check_touchscreen') and self.main_app.check_touchscreen and self.main_app.check_touchscreen.isChecked():
                if not self._dialog_open:
                    self._dialog_open = True
                    dlg = VirtualKeyboardDialog(self.main_app, self.target_line_edit, title=self.label_name)
                    dlg.exec()
                    self._dialog_open = False
                    return True
        return super().eventFilter(obj, event)


def register_touch_line_edit(main_app, line_edit, label_name="Field"):
    """
    Helper function to attach touchscreen keyboard event filter to a QLineEdit.
    """
    if line_edit is None:
        return
    filt = TouchKeyboardEventFilter(main_app, line_edit, label_name=label_name)
    line_edit.installEventFilter(filt)
    # Store reference on widget to prevent garbage collection
    line_edit._touch_filter = filt
