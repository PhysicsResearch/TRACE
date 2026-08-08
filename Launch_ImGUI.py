import os, sys, faulthandler
faulthandler.enable()
os.environ.setdefault("QT_OPENGL", "software")  # safer on RDP/VM

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QSurfaceFormat, QIcon, QPixmap
from PySide6.QtWidgets import QMainWindow, QMenu

# Force software GL (stable on many Windows setups)
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)

# Compatibility profile is safest with VTK on Windows
fmt = QSurfaceFormat()
fmt.setRenderableType(QSurfaceFormat.OpenGL)
fmt.setProfile(QSurfaceFormat.CompatibilityProfile)
fmt.setVersion(3, 2)
fmt.setDepthBufferSize(24)
fmt.setStencilBufferSize(8)
QSurfaceFormat.setDefaultFormat(fmt)

from fcn_create_gui import create_gui
from fcn_init.ModulesTab_change     import set_fcn_tabModules_changed
from fcn_init.init_variables        import initialize_software_variables
from fcn_init.init_tables           import initialize_software_tables
from fcn_init.init_buttons          import initialize_software_buttons
from fcn_init.init_list_menus       import populate_list_menus
from fcn_plan.fcn_create            import create_curve
from fcn_plan.fcn_edit              import init_edit, plotViewData_edit
from fcn_control.fcn_filesystem     import start_gcode, delete_recursively, load_directory
from fcn_control.fcn_control        import setDuetIP

class MyApp(QMainWindow):

    def __init__(self, folder_path=None):
        super(MyApp, self).__init__()
        
        # Set up programmatic user interface with lazy loading
        create_gui(self)
        self.setWindowTitle("TRACE")

        # Initialize core variables
        initialize_software_variables(self)
        populate_list_menus(self)
        initialize_software_tables(self)
        initialize_software_buttons(self)

        set_fcn_tabModules_changed(self)

        # Apply tactile pressed feedback (padding shift) and scale all QPushButton heights by 50%
        import re
        def scale_style_height(style_str, factor=1.5):
            def repl(match):
                val = int(match.group(2))
                return f"{match.group(1)}: {int(val * factor)}px"
            scaled = re.sub(r'(min-height|height)\s*:\s*(\d+)px', repl, style_str, flags=re.IGNORECASE)
            return scaled

        def scale_style_font(style_str, factor=1.4):
            def repl(match):
                val = int(match.group(2))
                return f"{match.group(1)}: {int(val * factor)}px"
            scaled = re.sub(r'(font-size)\s*:\s*(\d+)px', repl, style_str, flags=re.IGNORECASE)
            return scaled

        from PySide6.QtWidgets import QPushButton, QLineEdit, QLabel, QRadioButton, QCheckBox
        
        # Scale top config row widgets (Duet IP input, status radio button, touchscreen checkbox)
        for widget in [getattr(self, 'DuetIPAddress', None), getattr(self, 'connect_status', None), getattr(self, 'check_touchscreen', None)]:
            if widget is not None:
                h = widget.minimumHeight()
                if h > 0:
                    widget.setMinimumHeight(int(h * 1.5))
                else:
                    widget.setMinimumHeight(60)
                style = widget.styleSheet().strip()
                if style:
                    style = scale_style_height(style, 1.5)
                    if "font-size" in style.lower():
                        style = scale_style_font(style, 1.4)
                    else:
                        style += "\nfont-size: 18px;"
                    widget.setStyleSheet(style)

        # Scale and style all buttons
        for btn in self.findChildren(QPushButton):
            # Exclude step buttons (they are styled/scaled specifically in set_global_step_size)
            if hasattr(self, 'step_buttons') and self.step_buttons and btn in self.step_buttons.values():
                # Apply pressed feedback to step buttons but don't scale their heights
                style = btn.styleSheet().strip()
                if style:
                    if ":pressed" not in style:
                        style += "\nQPushButton:pressed { padding-top: 3px; padding-left: 3px; }"
                    btn.setStyleSheet(style)
                else:
                    btn.setStyleSheet("QPushButton:pressed { padding-top: 3px; padding-left: 3px; }")
                continue

            # Exclude touchscreen button (already scaled in top bar block above)
            if btn == getattr(self, 'check_touchscreen', None):
                continue

            # Exclude motion panel jog & homing buttons (they have fixed 50px heights)
            btn_txt = btn.text().strip()
            if any(k in btn_txt for k in ['- ', '+ ', 'Home ']) or btn_txt in ['Home ALL', 'Go to', 'Go to ...', 'Go to center']:
                style = btn.styleSheet().strip()
                if style and ":pressed" not in style:
                    style += "\nQPushButton:pressed { padding-top: 3px; padding-left: 3px; }"
                    btn.setStyleSheet(style)
                continue

            # 1. Scale physical minimum height
            h = btn.minimumHeight()
            if h > 0:
                btn.setMinimumHeight(int(h * 1.5))
            else:
                sh = btn.sizeHint().height()
                btn.setMinimumHeight(int(max(sh, 30) * 1.5))

            # 2. Scale style sheet and add pressed/hover feedback
            style = btn.styleSheet().strip()
            if style:
                style = scale_style_height(style, 1.5)
                if "font-size" in style.lower():
                    style = scale_style_font(style, 1.4)
                else:
                    style += "\nfont-size: 18px;"
                if "QPushButton" not in style:
                    style = f"QPushButton {{ {style} }}"
                if ":pressed" not in style:
                    style += "\nQPushButton:pressed { padding-top: 3px; padding-left: 3px; }"
                btn.setStyleSheet(style)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        font-size: 18px;
                        font-weight: bold;
                    }
                    QPushButton:pressed {
                        padding-top: 3px;
                        padding-left: 3px;
                    }
                """)

        # Scale and style all QLineEdits (position and target fields)
        for le in self.findChildren(QLineEdit):
            if le == getattr(self, 'DuetIPAddress', None):
                continue
            h = le.minimumHeight()
            if h > 0:
                le.setMinimumHeight(int(h * 1.5))
            else:
                le.setMinimumHeight(55)
            
            style = le.styleSheet().strip()
            if style:
                style = scale_style_height(style, 1.5)
                if "font-size" in style.lower():
                    style = scale_style_font(style, 1.4)
                else:
                    style += "\nfont-size: 18px;"
                if "QLineEdit" not in style:
                    style = f"QLineEdit {{ {style} }}"
                le.setStyleSheet(style)
            else:
                le.setStyleSheet("QLineEdit { font-size: 18px; font-weight: bold; }")

        # Scale and style all labels
        for lbl in self.findChildren(QLabel):
            style = lbl.styleSheet().strip()
            if style:
                if "font-size" in style.lower():
                    style = scale_style_font(style, 1.4)
                else:
                    style += "\nfont-size: 17px;"
                lbl.setStyleSheet(style)
            else:
                font = lbl.font()
                font.setPointSize(15)
                font.setBold(True)
                lbl.setFont(font)

        # Scale and style radio buttons and checkboxes
        for widget in self.findChildren(QRadioButton) + self.findChildren(QCheckBox):
            if widget == getattr(self, 'check_touchscreen', None):
                continue
            style = widget.styleSheet().strip()
            if style:
                if "font-size" in style.lower():
                    style = scale_style_font(style, 1.4)
                else:
                    style += "\nfont-size: 16px;"
                widget.setStyleSheet(style)
            else:
                font = widget.font()
                font.setPointSize(15)
                font.setBold(True)
                widget.setFont(font)

    def on_item_double_clicked(self, index):
        item = self.model.itemFromIndex(index)

        path = item.data(self.PATH_ROLE)
        is_dir = item.data(self.IS_DIR_ROLE)

        if is_dir:
            load_directory(self, path)

    def open_context_menu(self, position):
        index = self.fileTreeView.indexAt(position)

        if not index.isValid():
            return # clicked empty space
        
        item = self.model.itemFromIndex(index)

        path = item.data(self.PATH_ROLE)
        is_dir = item.data(self.IS_DIR_ROLE)

        menu = QMenu()

        if not is_dir:
            run_action = menu.addAction("Run")
            download_action = menu.addAction("Download")
        else:
            run_action = None
            download_action = None

        delete_action = menu.addAction("Delete")

        action = menu.exec(self.fileTreeView.viewport().mapToGlobal(position))

        if run_action and action == run_action:
            start_gcode(self, item.data(self.PATH_ROLE))

        if download_action and action == download_action:
            from fcn_control.fcn_filesystem import download_file
            download_file(self, path)

        if action == delete_action:
            delete_recursively(self, path, is_dir)


if __name__ == "__main__":
    import sys, os
    from PySide6.QtCore import Qt, QCoreApplication
    from PySide6.QtGui import QSurfaceFormat, QPixmap, QIcon
    from PySide6.QtWidgets import QApplication, QSplashScreen

    # Set explicit AppUserModelID on Windows so taskbar & menu bar display the application icon
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TRACE.App.1.0")
        except Exception:
            pass

    # --- Keep GL defaults ---
    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setProfile(QSurfaceFormat.CompatibilityProfile)
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QMessageBox {
            background-color: #f5f5f5;
            min-width: 580px;
        }
        QMessageBox QLabel {
            font-size: 18px;
            font-weight: bold;
            qproperty-alignment: 'AlignLeft | AlignVCenter';
            qproperty-wordWrap: true;
            min-height: 80px;
            padding: 10px;
            color: #333333;
        }
        QMessageBox QPushButton {
            font-size: 16px;
            font-weight: bold;
            min-width: 120px;
            min-height: 48px;
            border-radius: 4px;
            padding: 6px 16px;
            background-color: #2196f3;
            color: white;
        }
        QMessageBox QPushButton:hover {
            background-color: #1976d2;
        }
    """)

    # Resolve logo asset path relative to script/exe location
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(base_dir, "assets", "Open-Logo.png")
    if not os.path.exists(logo_path):
        logo_path = "assets/Open-Logo.png"

    # Set application window icon
    app_icon = QIcon(logo_path)
    app.setWindowIcon(app_icon)

    # --- Show splash ASAP ---
    pix = QPixmap(logo_path)
    if pix.isNull():
        pix = QPixmap(300, 300)
        pix.fill(Qt.transparent)
    else:
        pix = pix.scaled(240, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    splash = QSplashScreen(pix)
    splash.setStyleSheet("background: transparent;")
    splash.showMessage("Starting TRACE…", Qt.AlignBottom | Qt.AlignHCenter | Qt.TextWordWrap, Qt.black)
    splash.show()
    app.processEvents()  # let splash paint immediately

    # --- Create main window ---
    folder_path = sys.argv[1] if len(sys.argv) > 1 else None
    window = MyApp(folder_path)
    window.setWindowIcon(app_icon)

    app.setStyle('Fusion')
    splash.showMessage("Loading UI…", Qt.AlignBottom | Qt.AlignHCenter | Qt.TextWordWrap, Qt.black)
    app.processEvents()

    # --- Show window and close splash ---
    window.showMaximized()
    splash.finish(window)

    sys.exit(app.exec())
