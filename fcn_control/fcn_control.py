
import requests
from PySide6.QtWidgets import QFileDialog, QMessageBox

def step(self, ax, plus=True):

    self.duet_ip = self.DuetIPAddress.text()
    
    if ax in ['A', 'B', 'C', 'D']:
        step = self.STEP_Z.currentText()
    if ax in ['X', "'x"]:
        step = self.STEP_X.currentText()
    if ax == 'Y':
        step = self.STEP_Y.currentText()

    if plus:
        cmd = f"G1 {ax}{step} F600"
    else:
        cmd = f"G1 {ax}-{step} F600"

    url = f'http://{self.duet_ip}/rr_gcode?gcode={cmd}'

    try:
        response = requests.get(url, timeout=2)
    except:
        QMessageBox.warning(self, "Duet Error", f"Command failed (maybe no connection?)")


def home(self, ax):
    return
    

def setDuetIP(self):
    self.duet_ip = self.DuetIPAddress.text()

    url = f'http://{self.duet_ip}/rr_status?type=3'
    connected = False

    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            connected = True
    except:
        pass
    if connected:
        self.connect_status.setText('Status: Connected')
        self.connect_status.setStyleSheet("QLabel { color: green }")
    else:
        self.connect_status.setText('Status: Not connected')
        self.connect_status.setStyleSheet("QLabel { color: red }")


def setPhOperFolder(self):
    options = QFileDialog.Options()
    folder = QFileDialog.getExistingDirectory(self, options=options)
    self.gcode_folder = folder
    self.PhOperFolder.setText(self.gcode_folder)