from PySide6.QtCore import Qt
import json

def initialize_software_variables(self):

    self.WINDOW_DURATION = 10     # seconds to show on the plot
    self.UPDATE_INTERVAL = 0.05    # seconds between polls
    self.Tab_index = 0
    self.gcode_folder = ''
    self.buffers    = {}
    self.lines      = {}
    self.plot_axes  = []
    
    with open('configuration.json', 'r') as f:
        data = json.load(f)

    self.duet_ip = data['duet_ip_address'] #'192.168.0.1'
    self.gcode_folder = data['move_folder']
    self.PhOperFolder.setText(self.gcode_folder)

    self.PATH_ROLE = Qt.UserRole + 1
    self.IS_DIR_ROLE = Qt.UserRole + 2
    self.current_dir = "/"
    self.statusPause = False