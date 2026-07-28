"""
fcn_create_gui package entry point
Main GUI construction and lazy loading orchestrator for TRACE application.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget

from .tab_control import build_control_tab
from .tab_status import build_status_tab
from .tab_files import build_files_tab
from .tab_planning import build_planning_tab
from .tab_motion_verification import build_motion_verification_tab


def create_gui(self):
    """
    Main function to programmatically build TRACE GUI inside QMainWindow (self).
    Sets up tabModules container and builds Tab 0 (Control) immediately,
    deferring other tabs to lazy-loading.
    """
    self.centralwidget = QWidget(self)
    self.setCentralWidget(self.centralwidget)

    layout = QVBoxLayout(self.centralwidget)
    layout.setContentsMargins(0, 0, 0, 0)

    # Main Tab Widget Container (Touchscreen optimized font & tab heights)
    self.tabModules = QTabWidget(self.centralwidget)
    self.tabModules.setStyleSheet("""
        QTabBar::tab {
            font-weight: bold;
            font-size: 20px;
            padding: 10px 24px;
            min-height: 52px;
        }
        QTabBar::tab:selected {
            background-color: #ffffff;
            color: #1565c0;
            border-bottom: 4px solid #1565c0;
        }
    """)
    layout.addWidget(self.tabModules)

    # Instantiate page widgets
    self.tab_2 = QWidget()
    self.tab_status = QWidget()
    self.tab_files = QWidget()
    self.tab_planning = QWidget()
    self.tab_phantom_operation = QWidget()

    # Add tabs to tabModules with exact titles expected by software logic
    self.tabModules.addTab(self.tab_2, "Control")
    self.tabModules.addTab(self.tab_status, "Status")
    self.tabModules.addTab(self.tab_files, "Files")
    self.tabModules.addTab(self.tab_planning, "Planning")
    self.tabModules.addTab(self.tab_phantom_operation, "Lung Phantom")

    # Track loaded main tabs for lazy loading
    self._loaded_tabs = set()

    # Connect main tab switch listener
    self.tabModules.currentChanged.connect(lambda idx: on_main_tab_changed(self, idx))

    # Build initial active tab 0 (Control) immediately on launch
    build_control_tab(self)
    self._loaded_tabs.add(0)


def on_main_tab_changed(self, index):
    """
    Lazy loads main tab widgets when user clicks a tab for the first time.
    """
    if index == 2:  # Files Tab
        if index not in self._loaded_tabs:
            build_files_tab(self)
            self._loaded_tabs.add(2)
            # Re-bind software buttons after dynamic tab build
            from fcn_init.init_buttons import initialize_software_buttons
            initialize_software_buttons(self)
        
        # Auto-refresh the file list when switching to Files tab if connected
        if getattr(self, 'duet_connected', False):
            from fcn_control.fcn_filesystem import load_directory
            load_directory(self, getattr(self, 'current_directory', '/'))
        return

    if index in self._loaded_tabs:
        return

    if index == 1:  # Status Tab
        build_status_tab(self)
        self._loaded_tabs.add(1)
    elif index == 3:  # Planning Tab
        build_planning_tab(self)
        self._loaded_tabs.add(3)
    elif index == 4:  # Lung Phantom Tab
        build_motion_verification_tab(self)
        self._loaded_tabs.add(4)

    # Re-bind software buttons after dynamic tab build
    from fcn_init.init_buttons import initialize_software_buttons
    initialize_software_buttons(self)
