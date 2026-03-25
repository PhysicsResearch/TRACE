# Import functions to attach to buttons
from fcn_control.fcn_control    import setDuetIP, setPhOperFolder, step, home
from fcn_plan.fcn_create        import add_row, remove_row, createCurve
from fcn_plan.fcn_import        import openCSVFile_BrCv
from fcn_plan.fcn_edit          import scaleAmpl, shiftAmpl, zeroAmpl, clipAmpl, scaleFreq, \
                                        undoOperation, removeDrift, addDrift, cropRange, smoothAmpl
from fcn_plan.fcn_export        import exportData, exportGCODE, calcStats, plotViewData
from fcn_monitor.fcn_plotting   import update_axes, on_radiation_trigger_check

def initialize_software_buttons(self):

    # --- CONTROL PAGE
    self.setDuetIP.clicked.connect(lambda: setDuetIP(self))
    self.setDuetIP.setStyleSheet("background-color: blue; color: white;")
    self.connect_status.setStyleSheet("QRadioButton::unchecked:pressed" "{" "background-color : red" "}")
    self.connect_status.setText('Not connected')

    self.setPhOperFolder.clicked.connect(lambda: setPhOperFolder(self))
    self.setPhOperFolder.setStyleSheet("background-color: blue; color: white;")

    # HOME BUTTONS
    self.HOME_Z.clicked.connect(lambda: home(self, 'Z'))
    self.HOME_X.clicked.connect(lambda: home(self, 'Z'))
    self.HOME_Y.clicked.connect(lambda: home(self, 'Z'))

    # STEP BUTTONS
    self.MIN_A.clicked.connect(lambda: step(self, 'A', plus=False))
    self.MIN_B.clicked.connect(lambda: step(self, 'B', plus=False))
    self.MIN_C.clicked.connect(lambda: step(self, 'C', plus=False))
    self.MIN_D.clicked.connect(lambda: step(self, 'D', plus=False))

    self.PLUS_A.clicked.connect(lambda: step(self, 'A'))
    self.PLUS_B.clicked.connect(lambda: step(self, 'B'))
    self.PLUS_C.clicked.connect(lambda: step(self, 'C'))
    self.PLUS_D.clicked.connect(lambda: step(self, 'D'))
    # self.MIN_X.clicked.connect(lambda: step(self, 'X'))
    # self.MIN_x.clicked.connect(lambda: step(self, "'x"))
    # self.MIN_Y.clicked.connect(lambda: step(self, 'Y'))


    #--- PLANNING: CREATE ---
    self.create_add_row.clicked.connect(lambda: add_row(self))
    self.create_add_row.setStyleSheet("background-color: green; color: white;")
    self.create_remove_row.clicked.connect(lambda: remove_row(self))
    self.create_remove_row.setStyleSheet("background-color: red; color: white;")
    self.button_create_curve.clicked.connect(lambda: createCurve(self))
    self.button_create_curve.setStyleSheet("background-color: green; color: white;")

    #--- PLANNING: IMPORT ---
    self.import_button.clicked.connect(lambda: openCSVFile_BrCv(self))
    self.import_button.setStyleSheet("background-color: green; color: white;")

    # --- PLANNING: EDIT ---
    self.button_scale_ampl.clicked.connect(lambda: scaleAmpl(self))
    self.button_scale_ampl.setStyleSheet("background-color: green; color: white;")
    self.button_shift_ampl.clicked.connect(lambda: shiftAmpl(self))
    self.button_shift_ampl.setStyleSheet("background-color: blue; color: white;")
    self.button_zero_ampl.clicked.connect(lambda: zeroAmpl(self))
    self.button_zero_ampl.setStyleSheet("background-color: green; color: white;")
    self.button_clip_ampl.clicked.connect(lambda: clipAmpl(self))
    self.button_clip_ampl.setStyleSheet("background-color: green; color: white;")
    self.edit_undo.clicked.connect(lambda: undoOperation(self))
    self.edit_undo.setStyleSheet("background-color: red; color: white;")
    self.button_scale_freq.clicked.connect(lambda: scaleFreq(self))
    self.button_scale_freq.setStyleSheet("background-color: blue; color: white;")
    self.button_remove_drift.clicked.connect(lambda: removeDrift(self))
    self.button_remove_drift.setStyleSheet("background-color: blue; color: white;")
    self.button_add_drift.clicked.connect(lambda: addDrift(self))
    self.button_add_drift.setStyleSheet("background-color: green; color: white;")
    self.button_clip_cycles.clicked.connect(lambda: cropRange(self))
    self.button_apply_smooth.clicked.connect(lambda: smoothAmpl(self))
    
    # --- PLANNING: PLOT ---
    self.exportCSV.clicked.connect(lambda: exportData(self))
    self.exportCSV.setStyleSheet("background-color: blue; color: white;")
    self.exportGCODE.clicked.connect(lambda: exportGCODE(self))
    self.exportGCODE.setStyleSheet("background-color: green; color: white;")
    self.calcStats.clicked.connect(lambda: calcStats(self))
    self.calcStats.setStyleSheet("background-color: green; color: white;")
    self.plot_peaks.stateChanged.connect(lambda: plotViewData(self))
    self.plot_acq.stateChanged.connect(lambda: plotViewData(self))
    self.plot_xaxis.currentTextChanged.connect(lambda: plotViewData(self))

    # --- MONITORING ---
    self.check_axis_X.clicked.connect(lambda: update_axes(self))
    self.check_axis_Y.clicked.connect(lambda: update_axes(self))
    self.check_axis_Z.clicked.connect(lambda: update_axes(self))
    self.stop_until_radiation.stateChanged.connect(lambda: on_radiation_trigger_check(self))

    