"""
Files Tab creation for TRACE GUI
Constructs fileTreeView with multi-column overview, folder color coding, path breadcrumb bar,
directory navigation, uniform touchscreen file management buttons (Upload, Refresh, New Folder, Delete), and Emergency Stop 3.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QPushButton, QTreeView, QLabel
)

def build_files_tab(self):
    """Populate self.tab_files with Files tab widgets and setup tree view model."""
    layout_main = QVBoxLayout(self.tab_files)
    layout_main.setContentsMargins(10, 10, 10, 10)
    layout_main.setSpacing(8)

    # Top Toolbar (Uniform 42px Height Controls)
    top_layout = QHBoxLayout()
    top_layout.setSpacing(10)

    self.treeViewBack = QPushButton("⬆ Back", self.tab_files)
    self.treeViewBack.setMinimumHeight(50)
    self.treeViewBack.setStyleSheet("""
        QPushButton {
            background-color: #e0e0e0;
            color: #37474f;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            padding: 6px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #cfd8dc;
        }
    """)

    self.gcodeRun = QPushButton("Run", self.tab_files)
    self.gcodeRun.setMinimumHeight(50)
    self.gcodeRun.setStyleSheet("""
        QPushButton {
            background-color: #2e7d32;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            min-width: 100px;
            padding: 6px 36px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #1b5e20;
        }
    """)

    self.gcodeUpload = QPushButton("Upload G-code", self.tab_files)
    self.gcodeUpload.setMinimumHeight(50)
    self.gcodeUpload.setStyleSheet("""
        QPushButton {
            background-color: #2196f3;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            padding: 6px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #1976d2;
        }
    """)

    self.gcodeDownload = QPushButton("Download File", self.tab_files)
    self.gcodeDownload.setMinimumHeight(50)
    self.gcodeDownload.setStyleSheet("""
        QPushButton {
            background-color: #0288d1;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            padding: 6px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #0277bd;
        }
    """)

    self.gcodeToPlanning = QPushButton("To Planning", self.tab_files)
    self.gcodeToPlanning.setMinimumHeight(50)
    self.gcodeToPlanning.setStyleSheet("""
        QPushButton {
            background-color: #673ab7;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            padding: 6px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #512da8;
        }
    """)

    self.gcodeRefresh = QPushButton("Refresh", self.tab_files)
    self.gcodeRefresh.setMinimumHeight(50)
    self.gcodeRefresh.setStyleSheet("""
        QPushButton {
            background-color: #ff9800;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            padding: 6px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #f57c00;
        }
    """)

    self.gcodeNewFolder = QPushButton("New Folder", self.tab_files)
    self.gcodeNewFolder.setMinimumHeight(50)
    self.gcodeNewFolder.setStyleSheet("""
        QPushButton {
            background-color: #4caf50;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            padding: 6px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #388e3c;
        }
    """)

    self.gcodeMove = QPushButton("Move", self.tab_files)
    self.gcodeMove.setMinimumHeight(50)
    self.gcodeMove.setStyleSheet("""
        QPushButton {
            background-color: #8e24aa;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            padding: 6px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #7b1fa2;
        }
    """)

    self.gcodeCopy = QPushButton("Copy", self.tab_files)
    self.gcodeCopy.setMinimumHeight(50)
    self.gcodeCopy.setStyleSheet("""
        QPushButton {
            background-color: #00acc1;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            padding: 6px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #00838f;
        }
    """)

    self.gcodeDelete = QPushButton("Delete", self.tab_files)
    self.gcodeDelete.setMinimumHeight(50)
    self.gcodeDelete.setStyleSheet("""
        QPushButton {
            background-color: #f44336;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            padding: 6px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #d32f2f;
        }
    """)

    from PySide6.QtWidgets import QComboBox
    self.fileCategoryCombo = QComboBox(self.tab_files)
    self.fileCategoryCombo.addItems(["GCODE", "Macros", "System"])
    self.fileCategoryCombo.setMinimumHeight(50)
    self.fileCategoryCombo.setMinimumWidth(140)
    self.fileCategoryCombo.setStyleSheet("""
        QComboBox {
            background-color: #37474f;
            color: #ffffff;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            padding: 6px 12px;
            border-radius: 4px;
            border: 1px solid #263238;
        }
        QComboBox:hover {
            background-color: #455a64;
        }
        QComboBox QAbstractItemView {
            background-color: #37474f;
            color: #ffffff;
            font-size: 16px;
            font-weight: bold;
            selection-background-color: #1976d2;
            selection-color: #ffffff;
            border: 1px solid #263238;
            padding: 4px;
        }
        QComboBox QAbstractItemView::item {
            min-height: 40px;
            color: #ffffff;
            background-color: #37474f;
        }
        QComboBox QAbstractItemView::item:selected {
            background-color: #1976d2;
            color: #ffffff;
        }
    """)

    self.gcodeEdit = QPushButton("Text Editor", self.tab_files)
    self.gcodeEdit.setMinimumHeight(50)
    self.gcodeEdit.setStyleSheet("""
        QPushButton {
            background-color: #3949ab;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            padding: 6px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #283593;
        }
    """)

    self.gcodeRename = QPushButton("Rename", self.tab_files)
    self.gcodeRename.setMinimumHeight(50)
    self.gcodeRename.setStyleSheet("""
        QPushButton {
            background-color: #00796b;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            padding: 6px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #004d40;
        }
    """)

    self.emergencyButton_3 = QPushButton("Emergency STOP", self.tab_files)
    self.emergencyButton_3.setMinimumHeight(50)
    self.emergencyButton_3.setStyleSheet("""
        QPushButton {
            background-color: red;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 50px;
            padding: 6px 16px;
            border-radius: 4px;
        }
    """)

    top_layout.addWidget(self.treeViewBack)
    top_layout.addWidget(self.gcodeRefresh)
    top_layout.addWidget(self.gcodeNewFolder)
    top_layout.addWidget(self.gcodeMove)
    top_layout.addWidget(self.gcodeCopy)
    top_layout.addWidget(self.gcodeRename)
    top_layout.addWidget(self.gcodeDelete)
    top_layout.addWidget(self.fileCategoryCombo)
    top_layout.addStretch()
    top_layout.addWidget(self.emergencyButton_3)

    layout_main.addLayout(top_layout)

    # Path Breadcrumb Bar
    self.filePathLabel = QLabel("Current Directory: 0:/gcodes/", self.tab_files)
    self.filePathLabel.setStyleSheet("""
        QLabel {
            background-color: #f5f5f5;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 8px 12px;
            font-weight: bold;
            font-size: 16px;
            color: #1565c0;
        }
    """)
    layout_main.addWidget(self.filePathLabel)

    # File Tree View
    self.fileTreeView = QTreeView(self.tab_files)
    self.fileTreeView.setAlternatingRowColors(True)
    self.fileTreeView.setSelectionBehavior(QTreeView.SelectRows)
    self.fileTreeView.setUniformRowHeights(True)
    self.fileTreeView.setStyleSheet("""
        QTreeView {
            background-color: #ffffff;
            alternate-background-color: #fcfcfc;
            font-size: 18px;
            border: 1px solid #dcdcdc;
            border-radius: 4px;
        }
        QTreeView::item {
            height: 48px;
            padding: 4px 8px;
        }
        QTreeView::item:hover {
            background-color: #e3f2fd;
        }
        QTreeView::item:selected {
            background-color: #bbdefb;
            color: #0d47a1;
        }
        QHeaderView::section {
            background-color: #eceff1;
            color: #37474f;
            font-weight: bold;
            font-size: 16px;
            padding: 8px;
            border: none;
            border-right: 1px solid #cfd8dc;
            border-bottom: 2px solid #b0bec5;
        }
        QScrollBar:vertical {
            width: 40px;
            background: #f5f5f5;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:vertical {
            background: #bcbcbc;
            min-height: 40px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical:hover {
            background: #9e9e9e;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
    """)
    layout_main.addWidget(self.fileTreeView)

    # Bottom Toolbar (Action Toolbar)
    bottom_layout = QHBoxLayout()
    bottom_layout.setSpacing(10)
    bottom_layout.addWidget(self.gcodeEdit)
    bottom_layout.addWidget(self.gcodeUpload)
    bottom_layout.addWidget(self.gcodeDownload)
    bottom_layout.addWidget(self.gcodeToPlanning)
    bottom_layout.addStretch()
    bottom_layout.addWidget(self.gcodeRun)

    layout_main.addLayout(bottom_layout)

    # Initialize file explorer model once when tab is constructed
    from fcn_control.fcn_filesystem import setup_file_explorer
    setup_file_explorer(self)

    # Attach event listeners once
    if hasattr(self, 'on_item_double_clicked'):
        self.fileTreeView.doubleClicked.connect(self.on_item_double_clicked)

    if hasattr(self, 'open_context_menu'):
        self.fileTreeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.fileTreeView.customContextMenuRequested.connect(self.open_context_menu)
