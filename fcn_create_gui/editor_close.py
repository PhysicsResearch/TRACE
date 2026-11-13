"""
Editor tab: 'Close File' button, shown only while a file is loaded.  Closing asks first when there are unsaved
changes, then empties the editor and forgets the file (Save & Upload then has nothing to upload).
"""
from PySide6.QtWidgets import QMessageBox, QPushButton


def _loaded(self):
    return bool(getattr(self, 'current_editing_filepath', None))


def _refresh(self):
    btn = getattr(self, 'btnCloseEditorFile', None)
    if btn is not None:
        btn.setVisible(_loaded(self))


def close_editor_file(self):
    ed = getattr(self, 'fileTextEditor', None)
    if ed is None or not _loaded(self):
        return
    if ed.document().isModified():
        reply = QMessageBox.question(self, "Unsaved Changes",
                                     f"{self.current_editing_filepath} has unsaved changes.\n"
                                     "Close it without saving?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
    self.current_editing_filepath = None
    ed.setPlainText("")
    ed.document().setModified(False)
    if getattr(self, 'editorTitleLabel', None) is not None:
        self.editorTitleLabel.setText("Editing: [No file selected]")
    if getattr(self, 'editorStatusLabel', None) is not None:
        self.editorStatusLabel.setText("Ready")
    _refresh(self)


def add_close_file_button(self, toolbar_layout):
    """Called once from build_editor_tab with its top toolbar layout."""
    if getattr(self, 'btnCloseEditorFile', None) is not None:
        return
    btn = QPushButton("Close File", self.tab_editor)
    btn.setMinimumHeight(50)
    btn.setStyleSheet("""
        QPushButton { background-color: #c62828; color: white; font-weight: bold; font-size: 16px;
                      min-height: 50px; padding: 6px 18px; border-radius: 4px; }
        QPushButton:hover { background-color: #8e0000; }
    """)
    btn.setToolTip("Close the file in the editor (asks first if there are unsaved changes)")
    btn.clicked.connect(lambda _c=False: close_editor_file(self))
    idx = toolbar_layout.indexOf(self.btnSaveEditor)
    toolbar_layout.insertWidget(idx if idx >= 0 else toolbar_layout.count(), btn)
    self.btnCloseEditorFile = btn
    # open_in_editor sets current_editing_filepath before setPlainText, so this shows the button on every load
    self.fileTextEditor.textChanged.connect(lambda: _refresh(self))
    _refresh(self)
