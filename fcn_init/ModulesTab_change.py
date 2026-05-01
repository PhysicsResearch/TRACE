# Import required libraries and functions
import os
from PySide6.QtWidgets          import QMessageBox
from fcn_monitor.fcn_plotting   import exportMoVeData, init_MoVeTab, update_axes
from fcn_monitor.fcn_duet       import set_GCODE_speed
from fcn_plan.fcn_export        import init_export_plot

def set_fcn_tabModules_changed(self):
    # Connect the currentChanged signal to the onTabChanged slot
    self.tabModules.currentChanged.connect(lambda: onTabChanged(self))
    self.tabWidget_BrCv.currentChanged.connect(lambda: onTabChanged(self))
    
def onTabChanged(self):
    # This function is called whenever the current tab changes.
    # 'index' is the index of the new current tab.

    if self.Tab_index == 4 and self.tabModules.currentIndex() != 4:
        self.Tab_index = self.tabModules.currentIndex()

        # Export motion verification data
        exportMoVeData(self)
        
        # Delete attributes with stored motion verification data
        if hasattr(self, 'time_buffer'):
            delattr(self, 'time_buffer')
        if hasattr(self, 'x_buffer'):
            delattr(self, 'x_buffer')
        if hasattr(self, 'MoVeCanvas'):
            delattr(self, 'MoVeCanvas')
          
        # Set all axis unchecked
        for check in [self.check_axis_X, self.check_axis_Y, self.check_axis_Z]:
            check.setChecked(False)

        # Draw blank plot
        update_axes(self)


    if self.Tab_index != 4 and self.tabModules.currentIndex() == 4:
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

    if self.tabModules.currentIndex() == 2 and self.tabWidget_BrCv.currentIndex() == 3:
        init_export_plot(self)

