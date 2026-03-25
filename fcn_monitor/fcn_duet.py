# Import required libraries and modules
import os
import time
import requests
from PySide6.QtWidgets import QMessageBox

# --- DUET OPERATIONS ---

def get_curr_file(self, init=True):
    """
    Get the filename of the GCODE currently being executed on DUET
    """

    try:
        url = f'http://{self.duet_ip}/rr_fileinfo'
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            if data['err'] == 1:
                QMessageBox.warning(None, "Warning", "Duet could not be reached.")
                return None
            filepath = data['fileName']
            if init == True:
                self.tprint = data['printDuration']
            _, filename = os.path.split(filepath)
            return filename
    except:
        QMessageBox.warning(None, "Warning", "Duet could not be reached.")
        return None    
    

def get_duet_status(self):
    """
    Read the DUET status (motor positions, external sensors, time)
    """

    try:
        url = f'http://{self.duet_ip}/rr_status?type=3'
        response = requests.get(url)
        if response.status_code == 200:
            contents = response.json()
            data = {}

            # Store data
            data['x'] = contents['coords']['xyz'][0] * -1 + self.ampl_scaling_MoVe
            data['y'] = contents['coords']['xyz'][1] * -1 + self.ampl_scaling_MoVe
            data['z'] = contents['coords']['xyz'][2] * -1 + self.ampl_scaling_MoVe
            data['geiger'] = contents['sensors']['probeValue']
            data['t'] = time.time() - self.t0 + self.tprint
            return data

        else:
            print(f"Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception while retrieving DUET data: {e}")
        return None


def pause_continue_GCODE(self, pause=True):
    """
    Send GCODE command to pause/continue the current print on DUET
    """

    try:
        code = "M25" if pause else "M24"
        url = f'http://{self.duet_ip}/rr_gcode'
        response = requests.get(url, {'gcode': code})
        if response.status_code != 200:
            print(f"Error pausing GCODE: {response.status_code}")
    except Exception as e:
        print(f"Exception while pausing GCODE: {e}")


def set_GCODE_speed(self, speed_factor=None):
    """
    Send GCODE command to adjust the speed factor 
    """

    if self.MoVeAutoControl.isChecked() and speed_factor is None:
        return
    
    if speed_factor is None: # Speed factor defined by user
        speed_factor = self.MoVeSpeedFactor.value()
    else: # Speed factor calculate by auto-control
        self.MoVeSpeedFactor.setValue(int(speed_factor))

    try:
        url = f'http://{self.duet_ip}/rr_gcode'
        code = f"M220 S{speed_factor}"
        requests.get(url, {'gcode': code})
    except Exception as e:
        print(f"Exception while sending GCODE: {e}")
