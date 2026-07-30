# Import required libraries and functions
import os
from PySide6.QtWidgets          import QMessageBox
from fcn_plan.fcn_export        import init_export_plot

def set_fcn_tabModules_changed(self):
    # Connect the currentChanged signal to the onTabChanged slot
    self.tabModules.currentChanged.connect(lambda: onTabChanged(self))
    if hasattr(self, 'tabWidget_BrCv'):
        self.tabWidget_BrCv.currentChanged.connect(lambda: onTabChanged(self))
    
def onTabChanged(self):
    # Ensure tabWidget_BrCv signal is connected if it was lazily instantiated
    if hasattr(self, 'tabWidget_BrCv'):
        self.tabWidget_BrCv.currentChanged.connect(lambda: onTabChanged(self))

    if hasattr(self, 'tabWidget_BrCv') and self.tabModules.currentIndex() == 3 and self.tabWidget_BrCv.currentIndex() == 3:
        init_export_plot(self)
