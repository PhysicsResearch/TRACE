from PySide6.QtGui import QIcon
# Import functions to attach to buttons
from fcn_control.fcn_control    import setDuetIP, setPhOperFolder, step, home, move, send_cmd, \
                                        step_selected_ext_axis, move_selected_ext_axis, home_selected_ext_axis
from fcn_plan.fcn_create        import add_row, remove_row, createCurve
from fcn_plan.fcn_import        import openCSVFile_BrCv
from fcn_plan.fcn_edit          import scaleAmpl, shiftAmpl, zeroAmpl, clipAmpl, scaleFreq, \
                                        undoOperation, removeDrift, addDrift, cropRange, smoothAmpl
from fcn_plan.fcn_export        import exportData, exportGCODE, calcStats, plotViewData
from fcn_monitor.fcn_plotting   import update_axes, on_radiation_trigger_check
from fcn_monitor.fcn_duet       import clear_status_plot_data
from fcn_control.fcn_filesystem import setup_file_explorer, go_back, mkdir, delete_selected_item, download_selected_item, upload_file, run_selected_gcode_item


def initialize_software_buttons(self):

    # --- CONTROL PAGE ---
    if hasattr(self, 'setDuetIP'):
        self.setDuetIP.clicked.connect(lambda: setDuetIP(self))
        self.setDuetIP.setStyleSheet("background-color: blue; color: white; font-weight: bold; font-size: 17px; padding: 6px 18px; border-radius: 4px;")
    if hasattr(self, 'connect_status'):
        self.connect_status.setStyleSheet("QRadioButton::unchecked:pressed" "{" "background-color : red" "}")
        self.connect_status.setText('Not connected')

    if hasattr(self, 'setPhOperFolder'):
        self.setPhOperFolder.clicked.connect(lambda: setPhOperFolder(self))
        self.setPhOperFolder.setStyleSheet("background-color: blue; color: white;")

    if hasattr(self, 'button_clear_plot'):
        self.button_clear_plot.clicked.connect(lambda: clear_status_plot_data(self))

    if hasattr(self, 'sendCommandDUET'):
        self.sendCommandDUET.clicked.connect(lambda: send_cmd(self, None))
        self.sendCommandDUET.setStyleSheet("background-color: violet; color: white; font-weight: bold; font-size: 17px; padding: 6px 18px; border-radius: 4px;")

    if hasattr(self, 'gcodeRefresh'):
        self.gcodeRefresh.clicked.connect(lambda: setup_file_explorer(self))
        self.gcodeRefresh.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold; font-size: 16px; min-height: 50px; padding: 6px 16px; border-radius: 4px;")
    if hasattr(self, 'gcodeNewFolder'):
        self.gcodeNewFolder.clicked.connect(lambda: mkdir(self))
        self.gcodeNewFolder.setStyleSheet("background-color: #4caf50; color: white; font-weight: bold; font-size: 16px; min-height: 50px; padding: 6px 16px; border-radius: 4px;")
    if hasattr(self, 'gcodeDelete'):
        self.gcodeDelete.clicked.connect(lambda: delete_selected_item(self))
        self.gcodeDelete.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; font-size: 16px; min-height: 50px; padding: 6px 16px; border-radius: 4px;")
    if hasattr(self, 'gcodeRun'):
        self.gcodeRun.clicked.connect(lambda: run_selected_gcode_item(self))
        self.gcodeRun.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; font-size: 16px; min-height: 50px; min-width: 100px; padding: 6px 36px; border-radius: 4px;")
    if hasattr(self, 'gcodeUpload'):
        self.gcodeUpload.clicked.connect(lambda: upload_file(self))
        self.gcodeUpload.setStyleSheet("background-color: #2196f3; color: white; font-weight: bold; font-size: 16px; min-height: 50px; padding: 6px 16px; border-radius: 4px;")
    if hasattr(self, 'gcodeDownload'):
        self.gcodeDownload.clicked.connect(lambda: download_selected_item(self))
        self.gcodeDownload.setStyleSheet("background-color: #0288d1; color: white; font-weight: bold; font-size: 16px; min-height: 50px; padding: 6px 16px; border-radius: 4px;")

    if hasattr(self, 'treeViewBack'):
        self.treeViewBack.clicked.connect(lambda: go_back(self))

    for i in range(1, 5):
        btn = getattr(self, f'emergencyButton_{i}', None)
        if btn is not None:
            btn.clicked.connect(lambda _c=False: send_cmd(self, 'M112'))

    # HOME BUTTONS
    for axis in ['X', 'Y', 'Z', 'ROLL', 'PITCH', 'YAW', 'ALL']:
        btn = getattr(self, f'HOME_{axis}', None)
        if btn is not None:
            btn.clicked.connect(lambda _c=False, a=axis: home(self, a))

    btn_plat_all = getattr(self, 'HOME_ALL_PLATFORM', None)
    if btn_plat_all is not None:
        btn_plat_all.clicked.connect(lambda _c=False: home(self, 'ALL'))

    # STEP BUTTONS (Cartesian & Platform axes)
    for axis in ['XAXIS', 'YAXIS', 'ZAXIS', 'ROLL', 'PITCH', 'YAW']:
        b_min = getattr(self, f'MIN_{axis}', None)
        b_plus = getattr(self, f'PLUS_{axis}', None)
        if b_min is not None:
            b_min.clicked.connect(lambda _c=False, a=axis: step(self, a, plus=False))
        if b_plus is not None:
            b_plus.clicked.connect(lambda _c=False, a=axis: step(self, a, plus=True))

    # REMODELED INDIVIDUAL MOTORS SHARED CONTROLS
    if hasattr(self, 'btn_ext_jog_min') and self.btn_ext_jog_min:
        self.btn_ext_jog_min.clicked.connect(lambda _c=False: step_selected_ext_axis(self, plus=False))
    if hasattr(self, 'btn_ext_jog_plus') and self.btn_ext_jog_plus:
        self.btn_ext_jog_plus.clicked.connect(lambda _c=False: step_selected_ext_axis(self, plus=True))
    if hasattr(self, 'btn_move_ext') and self.btn_move_ext:
        self.btn_move_ext.clicked.connect(lambda _c=False: move_selected_ext_axis(self))
    if hasattr(self, 'btn_home_ext') and self.btn_home_ext:
        self.btn_home_ext.clicked.connect(lambda _c=False: home_selected_ext_axis(self))

    # TARGET POSITION CONFIRMATION (Return key)
    for axis_key in ['XAXIS', 'YAXIS', 'ZAXIS', 'ROLL', 'PITCH', 'YAW']:
        field = getattr(self, f'POS_DES_{axis_key}', None)
        if field is not None:
            field.returnPressed.connect(lambda _a=axis_key: move(self, _a))
    if hasattr(self, 'POS_DES_EXT') and self.POS_DES_EXT:
        self.POS_DES_EXT.returnPressed.connect(lambda: move_selected_ext_axis(self))

    #--- PLANNING PAGE ---
    if hasattr(self, 'create_add_row'):
        self.create_add_row.clicked.connect(lambda: add_row(self))
        self.create_add_row.setStyleSheet("background-color: green; color: white;")
    if hasattr(self, 'create_remove_row'):
        self.create_remove_row.clicked.connect(lambda: remove_row(self))
        self.create_remove_row.setStyleSheet("background-color: red; color: white;")
    if hasattr(self, 'button_create_curve'):
        self.button_create_curve.clicked.connect(lambda: createCurve(self))
        self.button_create_curve.setStyleSheet("background-color: green; color: white;")

    if hasattr(self, 'import_button'):
        self.import_button.clicked.connect(lambda: openCSVFile_BrCv(self))
        self.import_button.setStyleSheet("background-color: green; color: white;")

    if hasattr(self, 'button_scale_ampl'):
        self.button_scale_ampl.clicked.connect(lambda: scaleAmpl(self))
        self.button_scale_ampl.setStyleSheet("background-color: green; color: white;")
    if hasattr(self, 'button_shift_ampl'):
        self.button_shift_ampl.clicked.connect(lambda: shiftAmpl(self))
        self.button_shift_ampl.setStyleSheet("background-color: blue; color: white;")
    if hasattr(self, 'button_zero_ampl'):
        self.button_zero_ampl.clicked.connect(lambda: zeroAmpl(self))
        self.button_zero_ampl.setStyleSheet("background-color: green; color: white;")
    if hasattr(self, 'button_clip_ampl'):
        self.button_clip_ampl.clicked.connect(lambda: clipAmpl(self))
        self.button_clip_ampl.setStyleSheet("background-color: green; color: white;")
    if hasattr(self, 'edit_undo'):
        self.edit_undo.clicked.connect(lambda: undoOperation(self))
        self.edit_undo.setStyleSheet("background-color: red; color: white;")
    if hasattr(self, 'button_scale_freq'):
        self.button_scale_freq.clicked.connect(lambda: scaleFreq(self))
        self.button_scale_freq.setStyleSheet("background-color: blue; color: white;")
    if hasattr(self, 'button_remove_drift'):
        self.button_remove_drift.clicked.connect(lambda: removeDrift(self))
        self.button_remove_drift.setStyleSheet("background-color: blue; color: white;")
    if hasattr(self, 'button_add_drift'):
        self.button_add_drift.clicked.connect(lambda: addDrift(self))
        self.button_add_drift.setStyleSheet("background-color: green; color: white;")
    if hasattr(self, 'button_clip_cycles'):
        self.button_clip_cycles.clicked.connect(lambda: cropRange(self))
    if hasattr(self, 'button_apply_smooth'):
        self.button_apply_smooth.clicked.connect(lambda: smoothAmpl(self))
    
    # --- MONITORING ---
    if hasattr(self, 'check_axis_X'):
        self.check_axis_X.clicked.connect(lambda: update_axes(self))
    if hasattr(self, 'check_axis_Y'):
        self.check_axis_Y.clicked.connect(lambda: update_axes(self))
    if hasattr(self, 'check_axis_Z'):
        self.check_axis_Z.clicked.connect(lambda: update_axes(self))
    if hasattr(self, 'stop_until_radiation'):
        self.stop_until_radiation.stateChanged.connect(lambda: on_radiation_trigger_check(self))