from PySide6.QtCore import Qt
import json
from fcn_init.app_config import get_config_path

def initialize_software_variables(self):

    self.WINDOW_DURATION = 10     # seconds to show on the plot
    self.UPDATE_INTERVAL = 0.05    # seconds between polls
    self.Tab_index = 0
    self.gcode_folder = ''
    self.buffers    = {}
    self.lines      = {}
    self.plot_axes  = []
    
    # Figures variables (moved from menu bar)
    self.selected_font_size = 14
    self.selected_legend_font_size = 14
    self.selected_legend_on_off = "On"
    self.selected_background = "Transparent"
    self.selected_line_width = 2.0
    self.selected_line_color = "Red" 
    self.selected_point_size = 8
    self.selected_point_color = "Blue"
    
    try:
        with open(get_config_path('configuration.json', for_writing=False), 'r') as f:
            data = json.load(f)
        self.duet_ip = data.get('duet_ip_address', '192.168.8.3')
        self.duet_ip_history = data.get('duet_ip_history', ['192.168.8.3', '192.168.8.2', '172.18.38.125'])
        self.gcode_folder = data.get('move_folder', '')
        self.plat_lat_dim = data.get('platform_lat_dim', '100.0')
        self.plat_si_dim = data.get('platform_si_dim', '100.0')
        try:
            if float(self.plat_lat_dim) <= 0.0: self.plat_lat_dim = '100.0'
        except ValueError: self.plat_lat_dim = '100.0'
        try:
            if float(self.plat_si_dim) <= 0.0: self.plat_si_dim = '100.0'
        except ValueError: self.plat_si_dim = '100.0'
        self.touchscreen_mode = data.get('touchscreen_mode', False)
    except Exception:
        self.duet_ip = '192.168.8.3'
        self.duet_ip_history = ['192.168.8.3', '192.168.8.2', '172.18.38.125']
        self.gcode_folder = ''
        self.plat_lat_dim = '100.0'
        self.plat_si_dim = '100.0'
        self.touchscreen_mode = False

    if hasattr(self, 'DuetIPAddress') and self.DuetIPAddress is not None:
        if hasattr(self.DuetIPAddress, 'clear') and hasattr(self, 'duet_ip_history'):
            self.DuetIPAddress.clear()
            for hist_ip in self.duet_ip_history:
                self.DuetIPAddress.addItem(hist_ip)
        self.DuetIPAddress.setText(self.duet_ip)

    if hasattr(self, 'PhOperFolder') and self.PhOperFolder is not None:
        self.PhOperFolder.setText(self.gcode_folder)

    if hasattr(self, 'input_plat_lat') and self.input_plat_lat is not None:
        self.input_plat_lat.setText(self.plat_lat_dim)

    if hasattr(self, 'input_plat_si') and self.input_plat_si is not None:
        self.input_plat_si.setText(self.plat_si_dim)

    if hasattr(self, 'check_touchscreen') and self.check_touchscreen is not None:
        self.check_touchscreen.setChecked(self.touchscreen_mode)

    self.PATH_ROLE = Qt.UserRole + 1
    self.IS_DIR_ROLE = Qt.UserRole + 2
    self.current_dir = "/"
    self.statusPause = False
    self.duet_connected = False