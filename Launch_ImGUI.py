import os, sys, faulthandler
faulthandler.enable()
os.environ.setdefault("QT_OPENGL", "software")  # safer on RDP/VM

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QMainWindow
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

from ImGUI import Ui_AMIGOpy
from fcn_init.create_menu           import initializeMenuBar
from fcn_init.ModulesTab_change     import set_fcn_tabModules_changed
from fcn_init.init_variables        import initialize_software_variables
from fcn_init.init_tables           import initialize_software_tables
from fcn_init.init_buttons          import initialize_software_buttons
from fcn_init.init_list_menus       import populate_list_menus
from fcn_plan.fcn_create            import create_curve
from fcn_plan.fcn_edit              import init_edit, plotViewData_edit

class MyApp(QMainWindow, Ui_AMIGOpy): # or QWidget/Ui_Form, QDialog/Ui_Dialog, etc.

    def __init__(self, folder_path=None):
        super(MyApp, self).__init__()
        
        # Set up the user interface from Designer.
        self.setupUi(self)
        self.setWindowTitle("TRACE")

        # Initialize
        populate_list_menus(self)
        initialize_software_variables(self)
        initialize_software_tables(self)
        initialize_software_buttons(self)

        self.tabWidget_BrCv.currentChanged.connect(lambda: init_edit(self))
        self.slider_edit_xmin.valueChanged.connect(lambda: plotViewData_edit(self))
        self.slider_edit_xmax.valueChanged.connect(lambda: plotViewData_edit(self))

        set_fcn_tabModules_changed(self)

        self.create_table.itemChanged.connect(lambda: create_curve(self))
        self.create_curve_type.currentTextChanged.connect(lambda: create_curve(self))
        self.create_sample_freq.valueChanged.connect(lambda: create_curve(self))

        initializeMenuBar(self)


if __name__ == "__main__":
    import sys, os
    from PySide6.QtCore import Qt, QCoreApplication
    from PySide6.QtGui import QSurfaceFormat, QPixmap
    from PySide6.QtWidgets import QApplication, QSplashScreen

    # --- Keep your GL defaults (unchanged) ---
    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setProfile(QSurfaceFormat.CompatibilityProfile)
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)

    # --- Show splash ASAP ---
    pix = QPixmap(":/assets/Open-Logo.png")
    if pix.isNull():
        pix = QPixmap(600, 300)  # fallback
        pix.fill(Qt.black)
    splash = QSplashScreen(pix)
    splash.showMessage("Starting TRACE…", Qt.AlignBottom | Qt.AlignHCenter | Qt.TextWordWrap, Qt.white)
    splash.show()
    app.processEvents()  # let the splash paint immediately

    # --- Create main window (keep __init__ as-is for now) ---
    folder_path = sys.argv[1] if len(sys.argv) > 1 else None
    window = MyApp(folder_path)

    # Optional: apply theme after splash is visible
    # app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyside6'))
    app.setStyle('Fusion')
    splash.showMessage("Loading UI…", Qt.AlignBottom | Qt.AlignHCenter | Qt.TextWordWrap, Qt.white)
    app.processEvents()

    # --- Show window and close splash ---
    window.show()
    splash.finish(window)

    sys.exit(app.exec())
