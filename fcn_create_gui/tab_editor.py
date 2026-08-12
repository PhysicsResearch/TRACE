"""
TRACE GUI Module - Editor Tab Construction
Builds self.tab_editor widget with dark-themed code editor, line numbers, and instant Save & Upload to Duet functionality.
"""
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QWidget
)
from PySide6.QtGui import QFont, QKeySequence, QShortcut, QSyntaxHighlighter, QTextCharFormat, QColor
from PySide6.QtCore import Qt, QRegularExpression


class GCodeHighlighter(QSyntaxHighlighter):
    """Native Qt syntax highlighter for G-code files."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        # 1. Axis Parameters & Coordinates (X, Y, Z, A, B, C, D, F, S, 'e, 'f, 'a, 'c, etc.) -> Emerald Green (#66bb6a)
        param_format = QTextCharFormat()
        param_format.setForeground(QColor("#66bb6a"))
        self.highlighting_rules.append((QRegularExpression(r"['\w]*[a-zA-Z][-+]?\d*\.?\d+\b"), param_format))

        # 2. G Commands (G0, G1, G4, G28, G90, G91, etc.) -> Bright Blue (#29b6f6)
        g_format = QTextCharFormat()
        g_format.setForeground(QColor("#29b6f6"))
        g_format.setFontWeight(QFont.Bold)
        self.highlighting_rules.append((QRegularExpression(r"\b[gG]\d+(\.\d+)?\b"), g_format))

        # 3. M Commands (M3, M4, M5, M104, M109, M140, M226, M400, M471, etc.) -> Vivid Red (#ff5252)
        m_format = QTextCharFormat()
        m_format.setForeground(QColor("#ff5252"))
        m_format.setFontWeight(QFont.Bold)
        self.highlighting_rules.append((QRegularExpression(r"\b[mM]\d+(\.\d+)?\b"), m_format))

        # 4. Comments (lines starting with ';' or inline comments ';...') -> Vibrant Orange (#ff9800)
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#ff9800"))
        comment_format.setFontItalic(True)
        self.highlighting_rules.append((QRegularExpression(r";[^\n]*"), comment_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


def build_editor_tab(self):
    """Populates self.tab_editor with code editor UI controls."""
    layout_main = QVBoxLayout(self.tab_editor)
    layout_main.setContentsMargins(12, 12, 12, 12)
    layout_main.setSpacing(10)

    # Top Toolbar / Header
    top_layout = QHBoxLayout()
    top_layout.setSpacing(12)

    self.btnCloseEditor = QPushButton("Back to Files", self.tab_editor)
    self.btnCloseEditor.setMinimumHeight(50)
    self.btnCloseEditor.setStyleSheet("""
        QPushButton {
            background-color: #616161;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            padding: 6px 18px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #424242;
        }
    """)

    self.editorTitleLabel = QLabel("Editing: [No file selected]", self.tab_editor)
    self.editorTitleLabel.setStyleSheet("""
        QLabel {
            font-size: 18px;
            font-weight: bold;
            color: #1565c0;
            padding: 6px;
        }
    """)

    self.btnSaveEditor = QPushButton("Save & Upload to Duet", self.tab_editor)
    self.btnSaveEditor.setMinimumHeight(50)
    self.btnSaveEditor.setMinimumWidth(240)
    self.btnSaveEditor.setStyleSheet("""
        QPushButton {
            background-color: #2e7d32;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            padding: 6px 20px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #1b5e20;
        }
    """)

    top_layout.addWidget(self.btnCloseEditor)
    top_layout.addWidget(self.editorTitleLabel)
    top_layout.addStretch()
    top_layout.addWidget(self.btnSaveEditor)

    layout_main.addLayout(top_layout)

    # Main Code Editor Widget (VS Code dark theme styling)
    self.fileTextEditor = QPlainTextEdit(self.tab_editor)
    editor_font = QFont("Consolas", 15)
    editor_font.setStyleHint(QFont.Monospace)
    self.fileTextEditor.setFont(editor_font)
    self.fileTextEditor.setTabStopDistance(4 * self.fileTextEditor.fontMetrics().horizontalAdvance(' '))
    self.fileTextEditor.setLineWrapMode(QPlainTextEdit.NoWrap)
    self.fileTextEditor.setStyleSheet("""
        QPlainTextEdit {
            background-color: #1e1e1e;
            color: #d4d4d4;
            selection-background-color: #264f78;
            selection-color: #ffffff;
            border: 1px solid #333333;
            border-radius: 4px;
            padding: 12px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 16px;
        }
    """)

    # Attach G-code Syntax Highlighter
    self.gcode_highlighter = GCodeHighlighter(self.fileTextEditor.document())

    layout_main.addWidget(self.fileTextEditor)

    # Editor Status / Info Footer
    self.editorStatusLabel = QLabel("Ready", self.tab_editor)
    self.editorStatusLabel.setStyleSheet("""
        QLabel {
            font-size: 14px;
            color: #555555;
            font-weight: bold;
            padding: 4px 8px;
        }
    """)
    layout_main.addWidget(self.editorStatusLabel)

    # Ctrl+S Keyboard Shortcut to Save & Upload
    self.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self.tab_editor)
    from fcn_control.fcn_filesystem import save_and_upload_editor_file
    self.save_shortcut.activated.connect(lambda: save_and_upload_editor_file(self))

    # Connect button clicked slots directly on construction
    def back_to_files():
        if hasattr(self, 'fileTextEditor') and self.fileTextEditor is not None:
            if self.fileTextEditor.document().isModified():
                from PySide6.QtWidgets import QMessageBox
                reply = QMessageBox.question(
                    self,
                    "Unsaved Changes",
                    "Unsaved changes will be lost, want to proceed?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

        if hasattr(self, 'tabModules') and hasattr(self, 'tab_files'):
            idx = self.tabModules.indexOf(self.tab_files)
            if idx >= 0:
                self.tabModules.setCurrentIndex(idx)

    self.btnCloseEditor.clicked.connect(back_to_files)
    self.btnSaveEditor.clicked.connect(lambda: save_and_upload_editor_file(self))
