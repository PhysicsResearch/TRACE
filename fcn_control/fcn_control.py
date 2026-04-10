
import requests
from PySide6.QtWidgets import QFileDialog, QMessageBox


def send_cmd(self, cmd):
    """
    Function to send GCODE command through DUET HTTP API.
    The request has a time-out of 2 seconds to handle e.g.
    connection issues and raise a pop-up. 
    """
    self.duet_ip = self.DuetIPAddress.text()

    url = f'http://{self.duet_ip}/rr_gcode?gcode={cmd}'

    try:
        response = requests.get(url, timeout=2)
    except:
        QMessageBox.warning(self, "Duet Error", f"Failed to execute command {cmd} (maybe no connection?)")



def home(self, ax):
    """
    Function to call the macros (.g) to home the axis
    Homing is performed on a per-axis basis (cartesian X, Y, Z)
    """

    if ax == 'X': # X-axis
        send_cmd(self, 'M98 P"homex.g"')
        send_cmd(self, 'M98 P"homew.g"')
    elif ax == 'Y': # Y-axis
        send_cmd(self, 'M98 P"homey.g"')
        send_cmd(self, 'M98 P"homev.g"')
    elif ax == 'Z': # Z-axis
        send_cmd(self, 'M98 P"homea.g"')
        send_cmd(self, 'M98 P"homeb.g"')
        send_cmd(self, 'M98 P"homec.g"')
        send_cmd(self, 'M98 P"homed.g"')



def step(self, ax, plus=True):
    """
    Function to move axes step-wise, depending on the step size 
    selected by the user. Step-wise movement can be performed in a 
    per-motor or per-axis fashion. 
    """

    # Define step size
    if ax in ['A', 'B', 'C', 'D', 'ZAXIS']:
        step = float(self.STEP_Z.currentText())
    elif ax in ['X', 'W', 'XAXIS']:
        step = float(self.STEP_X.currentText())
    elif ax == 'YAXIS':
        step = float(self.STEP_Y.currentText())
    else:
        return
    
    if not plus:
        step *= -1
    
    # Define GCODE commands
    send_cmd(self, "G91") # set relative mode

    if 'AXIS' in ax:
        if ax == 'XAXIS':
            cmd = f"G1 X{step:.4f} W{step:.4f} F600"
        elif ax == 'YAXIS':
            cmd = f"G1 Y{step:.4f} V{step} F600"     
        elif ax == 'ZAXIS':
            cmd = f"G1 A{step:.4f} B{step:.4f} C{step:.4f} D{step:.4f} F600"     
    else:
        cmd = f"G1 {ax}{step:.4f} F600"

    send_cmd(cmd) # send command to move step

    # Retrieve current positions
    # x, y, z, a, b, c, d, v, w


def move(self, ax):

    # Retrieve desired positions

    # Store data
    if ax == 'Z':
        step = float(self.STEP_Z.currentText())
    elif ax == 'X':
        step = float(self.STEP_X.currentText())
    elif ax == 'Y':
        step = float(self.STEP_X.currentText())

    pos = curr_pos[ax] + step if plus else curr_pos[ax] - step
    cmd = f"G1 {ax}{pos:.4f} F600"
    url = f'http://{self.duet_ip}/rr_gcode?gcode={cmd}'

    # Define GCODE commands
    send_cmd(self, "G90") # set absolute mode

    # Set current positions







    

    
    

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