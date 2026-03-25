from PySide6.QtWidgets import QMessageBox

def show_support_popup(self):

    if self.tabModules.currentIndex() == 1:

        if self.tabWidget_BrCv.currentIndex() == 0:
            QMessageBox.information(
                self,
                "Support",
                "This page allows you to create analytical breathing curves.\n\n"
                "Currently supported templates:\n"
                "• cos²\n"
                "• cos⁴\n"
                "• cos⁶\n\n"
                "Steps:\n"
                "1. Enter the desired parameters (period and amplitude) for each cycle\n"
                "2. Click 'Create curve' to generate and store the curve\n\n"
                "For additional help, please refer to the documentation or contact support."
            )

        elif self.tabWidget_BrCv.currentIndex() == 1:
            QMessageBox.information(
                self,
                "Support",
                "This page allows you to import breathing traces in VXP or CSV format.\n\n"
                "Notes:\n"
                "• VXP files are expected to contain phase information\n"
                "• CSV files should contain pre-processed VXP data (Export CSV metadata)\n\n"
                "For additional help, please refer to the documentation or contact support."
            )

        elif self.tabWidget_BrCv.currentIndex() == 2:
            QMessageBox.information(
                self,
                "Support",
                "This page allows you to edit a created or imported curve.\n\n"
                "Acquisition timestamps (for triggered phantom motion):\n"
                "• Left-click to insert a timestamp\n"
                "• Right-click to remove the closest timestamp\n\n"
                "Breath-hold insertion:\n"
                "1. Select insertion at maximum or minimum\n"
                "2. Specify the duration\n"
                "3. Click using the mouse wheel to insert\n\n"
                "Cropping curves:\n"
                "1. Select the desired range using the slider\n"
                "2. If phase information is present, press 'Crop' to clip to full cycles\n\n"
                "For additional help, please refer to the documentation or contact support."
            )

        elif self.tabWidget_BrCv.currentIndex() == 3:
            QMessageBox.information(
                self,
                "Support",
                "This page allows you to export and analyze the edited curve.\n\n"
                "Exporting:\n"
                "• Select the number of copies\n"
                "  (if phase information is present, the last cycle is scaled for continuity)\n"
                "• Enter a filename and click 'Export GCODE'\n"
                "• Use 'Export CSV' to save all available metadata\n\n"
                "Analysis:\n"
                "• 'Calculate statistics' computes amplitude, cycle time, and speed\n"
                "• Curves can be visualized and saved as figures\n\n"
                "For additional help, please refer to the documentation or contact support."
            )