import os, sys
from PySide6 import QtWidgets

def populate_list_menus(self):
    steps = ['0.1', '0.25', '1', '5', '10']
    for step_attr in ['STEP_X', 'STEP_Y', 'STEP_Z']:
        combo = getattr(self, step_attr, None)
        if combo is not None and combo.count() == 0:
            combo.addItems(steps)

    # --- Create ---
    cv_types = ["Cosine^2", "Cosine^4", "Cosine^6", "Hysteresis"]
    combo_create = getattr(self, 'create_curve_type', None)
    if combo_create is not None and combo_create.count() == 0:
        combo_create.addItems(cv_types)

    # --- Import ---
    separators = [",", ";", "\\t", " ", "|"]
    combo_delim = getattr(self, 'import_delimiter', None)
    if combo_delim is not None and combo_delim.count() == 0:
        combo_delim.addItems(separators)

    time_units = ["ms", "s"]
    combo_unit = getattr(self, 'import_time_unit', None)
    if combo_unit is not None and combo_unit.count() == 0:
        combo_unit.addItems(time_units)

    # --- Edit ---
    slider_fourier = getattr(self, 'threshFourierSlider', None)
    if slider_fourier is not None:
        self.fourier_cutoffs = [(x*y) for y in [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1] for x in list(range(1, 10))] 
        slider_fourier.setMinimum(0)
        slider_fourier.setMaximum(len(self.fourier_cutoffs) - 1)
        slider_fourier.setValue(26)

    combo_smooth = getattr(self, 'smooth_method', None)
    if combo_smooth is not None and combo_smooth.count() == 0:
        combo_smooth.addItems(["Fourier", "Uniform", "Median"])

    # --- Export ---
    combo_xaxis = getattr(self, 'plot_xaxis', None)
    if combo_xaxis is not None and combo_xaxis.count() == 0:
        combo_xaxis.addItems(['timestamp', 'time', 'cycle time', 'velocity'])
