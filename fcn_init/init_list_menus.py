import os, sys
from PySide6 import QtWidgets

def populate_list_menus(self):

    # --- Control ---
    steps = ['0.1', '0.25', '1', '5', '10']
    self.STEP_X = self.findChild(QtWidgets.QComboBox, 'STEP_X')
    self.STEP_X.addItems(steps)

    self.STEP_Y = self.findChild(QtWidgets.QComboBox, 'STEP_Y')
    self.STEP_Y.addItems(steps)

    self.STEP_Z = self.findChild(QtWidgets.QComboBox, 'STEP_Z')
    self.STEP_Z.addItems(steps)

    # --- Create ---
    cv_types = ["Cosine^2", "Cosine^4", "Cosine^6", "Hysteresis"]
    self.create_curve_type = self.findChild(QtWidgets.QComboBox, 'create_curve_type')
    self.create_curve_type.addItems(cv_types)

    # --- Import ---
    Separators = [",", ";", "\\t", " ", "|"]
    self.import_delimiter = self.findChild(QtWidgets.QComboBox, 'import_delimiter')
    self.import_delimiter.addItems(Separators)

    time_units = ["ms", "s"]
    self.import_time_unit = self.findChild(QtWidgets.QComboBox, 'import_time_unit')
    self.import_time_unit.addItems(time_units)

    self.fourier_cutoffs = [(x*y) for y in [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1] for x in list(range(1, 10))] 
    self.threshFourierSlider.setMinimum(0)
    self.threshFourierSlider.setMaximum(len(self.fourier_cutoffs) - 1)
    self.threshFourierSlider.setValue(26)

    self.smooth_method = self.findChild(QtWidgets.QComboBox, 'smooth_method')
    self.smooth_method.addItems(["Fourier", "Uniform", "Median"])

    self.plot_xaxis = self.findChild(QtWidgets.QComboBox, 'plot_xaxis')
    self.plot_xaxis.addItems(['timestamp', 'time', 'cycle time', 'velocity'])
    return
