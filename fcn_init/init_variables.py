
def initialize_software_variables(self):

    self.WINDOW_DURATION = 10     # seconds to show on the plot
    self.UPDATE_INTERVAL = 0.05    # seconds between polls
    self.Tab_index = 0
    self.gcode_folder = ''
    self.buffers    = {}
    self.lines      = {}
    self.plot_axes  = []
