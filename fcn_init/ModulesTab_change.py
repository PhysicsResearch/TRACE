# Import required libraries and functions
import os
from PySide6.QtWidgets          import QMessageBox
from fcn_monitor.fcn_plotting   import exportMoVeData, init_MoVeTab
from fcn_monitor.fcn_duet       import set_GCODE_speed
from fcn_plan.fcn_export        import init_export_plot

def set_fcn_tabModules_changed(self):
    # Connect the currentChanged signal to the onTabChanged slot
    self.tabModules.currentChanged.connect(lambda: onTabChanged(self))
    self.tabWidget_BrCv.currentChanged.connect(lambda: onTabChanged(self))
    
def onTabChanged(self):
    # This function is called whenever the current tab changes.
    # 'index' is the index of the new current tab.

    if self.Tab_index == 3 and self.tabModules.currentIndex() != 3:
          self.Tab_index = self.tabModules.currentIndex()
          exportMoVeData(self)
          
          delattr(self, 'time_buffer')
          delattr(self, 'x_buffer')
          delattr(self, 'MoVeCanvas')

    if self.Tab_index != 3 and self.tabModules.currentIndex() == 3:
        if not os.path.isdir(self.PhOperFolder.text()):
            QMessageBox.warning(None, "Warning", f"No input folder on device with path: {self.PhOperFolder.text()}.\nSet the correct folder with GCODE and CSV files")
            self.Tab_index = 0
            self.tabModules.blockSignals(True)
            self.tabModules.setCurrentIndex(0)
            self.tabModules.blockSignals(False)
        else:
            self.Tab_index = self.tabModules.currentIndex()
            self.MoVeSpeedFactor.setValue(100)
            self.MoVeSpeedFactor.valueChanged.connect(lambda: set_GCODE_speed(self))
            init_MoVeTab(self)

    if self.tabModules.currentIndex() == 1 and self.tabWidget_BrCv.currentIndex() == 3:
        init_export_plot(self)

