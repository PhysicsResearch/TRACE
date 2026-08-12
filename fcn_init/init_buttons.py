from PySide6.QtGui import QIcon
# Import functions to attach to buttons
from fcn_control.fcn_control    import setDuetIP, setPhOperFolder, step, home, move, send_cmd, \
                                        step_selected_ext_axis, move_selected_ext_axis, home_selected_ext_axis
from fcn_plan.fcn_create        import add_row, remove_row, createCurve
from fcn_plan.fcn_import        import openCSVFile_BrCv
from fcn_plan.fcn_edit          import scaleAmpl, shiftAmpl, zeroAmpl, clipAmpl, scaleFreq, \
                                        undoOperation, removeDrift, addDrift, cropRange, smoothAmpl
from fcn_plan.fcn_export        import exportData, exportGCODE, calcStats, plotViewData
from fcn_monitor.fcn_duet       import clear_status_plot_data
from fcn_control.fcn_filesystem import setup_file_explorer, go_back, mkdir, delete_selected_item, move_selected_item, copy_selected_item, download_selected_item, upload_file, run_selected_gcode_item, on_file_category_changed, edit_selected_file, save_and_upload_editor_file, rename_selected_item


def initialize_software_buttons(self):
    if not hasattr(self, '_connected_buttons'):
        self._connected_buttons = set()

    def safe_connect(btn, slot):
        if btn is not None and btn not in self._connected_buttons:
            btn.clicked.connect(slot)
            self._connected_buttons.add(btn)

    def safe_connect_return(le, slot):
        if le is not None and le not in self._connected_buttons:
            le.returnPressed.connect(slot)
            self._connected_buttons.add(le)

    def safe_connect_state_changed(cb, slot):
        if cb is not None and cb not in self._connected_buttons:
            cb.currentTextChanged.connect(slot)
            self._connected_buttons.add(cb)

    # --- CONTROL PAGE ---
    if hasattr(self, 'setDuetIP'):
        safe_connect(self.setDuetIP, lambda: setDuetIP(self))
        self.setDuetIP.setStyleSheet("background-color: blue; color: white; font-weight: bold; font-size: 17px; padding: 6px 18px; border-radius: 4px;")
    if hasattr(self, 'connect_status'):
        from fcn_control.fcn_control import update_connection_status_ui
        update_connection_status_ui(self, getattr(self, 'duet_connected', False))

    if hasattr(self, 'setPhOperFolder'):
        safe_connect(self.setPhOperFolder, lambda: setPhOperFolder(self))
        self.setPhOperFolder.setStyleSheet("background-color: blue; color: white;")

    if hasattr(self, 'button_clear_plot'):
        safe_connect(self.button_clear_plot, lambda: clear_status_plot_data(self))

    if hasattr(self, 'sendCommandDUET'):
        safe_connect(self.sendCommandDUET, lambda: send_cmd(self, None))
        self.sendCommandDUET.setStyleSheet("background-color: violet; color: white; font-weight: bold; font-size: 17px; padding: 6px 18px; border-radius: 4px;")

    if hasattr(self, 'gcodeRefresh'):
        safe_connect(self.gcodeRefresh, lambda: setup_file_explorer(self))
        self.gcodeRefresh.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold; font-size: 16px; min-height: 50px; padding: 6px 16px; border-radius: 4px;")
    if hasattr(self, 'gcodeNewFolder'):
        safe_connect(self.gcodeNewFolder, lambda: mkdir(self))
        self.gcodeNewFolder.setStyleSheet("background-color: #4caf50; color: white; font-weight: bold; font-size: 16px; min-height: 50px; padding: 6px 16px; border-radius: 4px;")
    if hasattr(self, 'gcodeMove'):
        safe_connect(self.gcodeMove, lambda: move_selected_item(self))
        self.gcodeMove.setStyleSheet("background-color: #8e24aa; color: white; font-weight: bold; font-size: 16px; min-height: 50px; padding: 6px 16px; border-radius: 4px;")
    if hasattr(self, 'gcodeCopy'):
        safe_connect(self.gcodeCopy, lambda: copy_selected_item(self))
        self.gcodeCopy.setStyleSheet("background-color: #00acc1; color: white; font-weight: bold; font-size: 16px; min-height: 50px; padding: 6px 16px; border-radius: 4px;")
    if hasattr(self, 'gcodeRename'):
        safe_connect(self.gcodeRename, lambda: rename_selected_item(self))
        self.gcodeRename.setStyleSheet("background-color: #00796b; color: white; font-weight: bold; font-size: 16px; min-height: 50px; padding: 6px 16px; border-radius: 4px;")
    if hasattr(self, 'gcodeEdit'):
        safe_connect(self.gcodeEdit, lambda: edit_selected_file(self))
        self.gcodeEdit.setStyleSheet("background-color: #3949ab; color: white; font-weight: bold; font-size: 16px; min-height: 50px; padding: 6px 16px; border-radius: 4px;")
    if hasattr(self, 'gcodeDelete'):
        safe_connect(self.gcodeDelete, lambda: delete_selected_item(self))
        self.gcodeDelete.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; font-size: 16px; min-height: 50px; padding: 6px 16px; border-radius: 4px;")
    if hasattr(self, 'fileCategoryCombo'):
        safe_connect_state_changed(self.fileCategoryCombo, lambda text: on_file_category_changed(self, text))
    if hasattr(self, 'btnSaveEditor'):
        safe_connect(self.btnSaveEditor, lambda: save_and_upload_editor_file(self))
    if hasattr(self, 'btnCloseEditor'):
        safe_connect(self.btnCloseEditor, lambda: self.tabModules.setCurrentIndex(2) if hasattr(self, 'tabModules') else None)
    if hasattr(self, 'gcodeRun'):
        safe_connect(self.gcodeRun, lambda: run_selected_gcode_item(self))
        self.gcodeRun.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; font-size: 16px; min-height: 50px; min-width: 100px; padding: 6px 36px; border-radius: 4px;")
    if hasattr(self, 'gcodeUpload'):
        safe_connect(self.gcodeUpload, lambda: upload_file(self))
        self.gcodeUpload.setStyleSheet("background-color: #2196f3; color: white; font-weight: bold; font-size: 16px; min-height: 50px; padding: 6px 16px; border-radius: 4px;")
    if hasattr(self, 'gcodeDownload'):
        safe_connect(self.gcodeDownload, lambda: download_selected_item(self))
        self.gcodeDownload.setStyleSheet("background-color: #0288d1; color: white; font-weight: bold; font-size: 16px; min-height: 50px; padding: 6px 16px; border-radius: 4px;")
    if hasattr(self, 'gcodeToPlanning'):
        from fcn_control.fcn_filesystem import transfer_to_planning_action
        safe_connect(self.gcodeToPlanning, lambda: transfer_to_planning_action(self))
        self.gcodeToPlanning.setStyleSheet("background-color: #673ab7; color: white; font-weight: bold; font-size: 16px; min-height: 50px; padding: 6px 16px; border-radius: 4px;")

    if hasattr(self, 'treeViewBack'):
        safe_connect(self.treeViewBack, lambda: go_back(self))

    for i in range(1, 5):
        btn = getattr(self, f'emergencyButton_{i}', None)
        if btn is not None:
            safe_connect(btn, lambda _c=False: send_cmd(self, 'M112'))

    # HOME BUTTONS
    for axis in ['X', 'Y', 'Z', 'ROLL', 'PITCH', 'YAW', 'ALL']:
        btn = getattr(self, f'HOME_{axis}', None)
        if btn is not None:
            safe_connect(btn, lambda _c=False, a=axis: home(self, a))

    btn_plat_all = getattr(self, 'HOME_ALL_PLATFORM', None)
    if btn_plat_all is not None:
        safe_connect(btn_plat_all, lambda _c=False: home(self, 'ALL'))

    # GOTO BUTTONS (Lung Phantom axes move to target position)
    from fcn_control.fcn_control import move
    btn_goto_lung = getattr(self, 'btn_goto_lung', None)
    if btn_goto_lung is not None:
        def move_all_lung():
            for a in ['XAXIS_LUNG', 'YAXIS_LUNG', 'ZAXIS_LUNG']:
                move(self, a)
        safe_connect(btn_goto_lung, lambda _c=False: move_all_lung())
    for axis, ax_key in [('X', 'XAXIS_LUNG'), ('Y', 'YAXIS_LUNG'), ('Z', 'ZAXIS_LUNG')]:
        btn = getattr(self, f'GOTO_{axis}', None)
        if btn is not None:
            safe_connect(btn, lambda _c=False, a=ax_key: move(self, a))

    # STEP BUTTONS (Cartesian & Platform axes)
    for axis in ['LATAXIS', 'SIAXIS', 'APAXIS', 'ROLL', 'PITCH', 'YAW']:
        b_min = getattr(self, f'MIN_{axis}', None)
        b_plus = getattr(self, f'PLUS_{axis}', None)
        if b_min is not None:
            safe_connect(b_min, lambda _c=False, a=axis: step(self, a, plus=False))
        if b_plus is not None:
            safe_connect(b_plus, lambda _c=False, a=axis: step(self, a, plus=True))

    for axis in ['XAXIS', 'YAXIS', 'ZAXIS']:
        target_ax = f"{axis}_LUNG"
        b_min = getattr(self, f'MIN_{target_ax}', None)
        b_plus = getattr(self, f'PLUS_{target_ax}', None)
        if b_min is not None:
            safe_connect(b_min, lambda _c=False, a=target_ax: step(self, a, plus=False))
        if b_plus is not None:
            safe_connect(b_plus, lambda _c=False, a=target_ax: step(self, a, plus=True))

    # REMODELED INDIVIDUAL MOTORS SHARED CONTROLS
    if hasattr(self, 'btn_ext_jog_min') and self.btn_ext_jog_min:
        safe_connect(self.btn_ext_jog_min, lambda _c=False: step_selected_ext_axis(self, plus=False))
    if hasattr(self, 'btn_ext_jog_plus') and self.btn_ext_jog_plus:
        safe_connect(self.btn_ext_jog_plus, lambda _c=False: step_selected_ext_axis(self, plus=True))
    if hasattr(self, 'btn_move_ext') and self.btn_move_ext:
        safe_connect(self.btn_move_ext, lambda _c=False: move_selected_ext_axis(self))
    if hasattr(self, 'btn_home_ext') and self.btn_home_ext:
        safe_connect(self.btn_home_ext, lambda _c=False: home_selected_ext_axis(self))

    # TARGET POSITION CONFIRMATION (Return key)
    for axis_key in ['LATAXIS', 'SIAXIS', 'APAXIS', 'ROLL', 'PITCH', 'YAW']:
        field = getattr(self, f'POS_DES_{axis_key}', None)
        if field is not None:
            safe_connect_return(field, lambda _a=axis_key: move(self, _a))
            
    for axis_key in ['XAXIS', 'YAXIS', 'ZAXIS']:
        target_ax = f"{axis_key}_LUNG"
        field = getattr(self, f'POS_DES_{target_ax}', None)
        if field is not None:
            safe_connect_return(field, lambda _a=target_ax: move(self, _a))
    if hasattr(self, 'POS_DES_EXT') and self.POS_DES_EXT:
        safe_connect_return(self.POS_DES_EXT, lambda: move_selected_ext_axis(self))

    #--- PLANNING PAGE ---
    if hasattr(self, 'create_add_row'):
        safe_connect(self.create_add_row, lambda: add_row(self))
        self.create_add_row.setStyleSheet("background-color: green; color: white;")
    if hasattr(self, 'create_remove_row'):
        safe_connect(self.create_remove_row, lambda: remove_row(self))
        self.create_remove_row.setStyleSheet("background-color: red; color: white;")
    if hasattr(self, 'button_create_curve'):
        safe_connect(self.button_create_curve, lambda: createCurve(self))

    if hasattr(self, 'button_import_gcode'):
        from fcn_plan.fcn_create import import_gcode_action
        safe_connect(self.button_import_gcode, lambda: import_gcode_action(self))

    if hasattr(self, 'button_wait_radiation'):
        from fcn_plan.fcn_create import add_wait_radiation_action
        safe_connect(self.button_wait_radiation, lambda: add_wait_radiation_action(self))

    if hasattr(self, 'button_wait_user'):
        from fcn_plan.fcn_create import add_wait_user_action
        safe_connect(self.button_wait_user, lambda: add_wait_user_action(self))

    if hasattr(self, 'button_clear_rad'):
        from fcn_plan.fcn_create import clear_rad_pauses_action
        safe_connect(self.button_clear_rad, lambda: clear_rad_pauses_action(self))

    if hasattr(self, 'button_clear_user'):
        from fcn_plan.fcn_create import clear_usr_pauses_action
        safe_connect(self.button_clear_user, lambda: clear_usr_pauses_action(self))

    if hasattr(self, 'button_clear_all'):
        from fcn_plan.fcn_create import clear_all_action
        safe_connect(self.button_clear_all, lambda: clear_all_action(self))

    if hasattr(self, 'import_button'):
        safe_connect(self.import_button, lambda: openCSVFile_BrCv(self))
        self.import_button.setStyleSheet("background-color: green; color: white;")

    if hasattr(self, 'button_scale_ampl'):
        safe_connect(self.button_scale_ampl, lambda: scaleAmpl(self))
        self.button_scale_ampl.setStyleSheet("background-color: green; color: white;")
    if hasattr(self, 'button_shift_ampl'):
        safe_connect(self.button_shift_ampl, lambda: shiftAmpl(self))
        self.button_shift_ampl.setStyleSheet("background-color: blue; color: white;")
    if hasattr(self, 'button_zero_ampl'):
        safe_connect(self.button_zero_ampl, lambda: zeroAmpl(self))
        self.button_zero_ampl.setStyleSheet("background-color: green; color: white;")
    if hasattr(self, 'button_clip_ampl'):
        safe_connect(self.button_clip_ampl, lambda: clipAmpl(self))
        self.button_clip_ampl.setStyleSheet("background-color: green; color: white;")
    if hasattr(self, 'edit_undo'):
        safe_connect(self.edit_undo, lambda: undoOperation(self))
        self.edit_undo.setStyleSheet("background-color: red; color: white;")
    if hasattr(self, 'button_scale_freq'):
        safe_connect(self.button_scale_freq, lambda: scaleFreq(self))
        self.button_scale_freq.setStyleSheet("background-color: blue; color: white;")
    if hasattr(self, 'button_remove_drift'):
        safe_connect(self.button_remove_drift, lambda: removeDrift(self))
        self.button_remove_drift.setStyleSheet("background-color: blue; color: white;")
    if hasattr(self, 'button_add_drift'):
        safe_connect(self.button_add_drift, lambda: addDrift(self))
        self.button_add_drift.setStyleSheet("background-color: green; color: white;")
    if hasattr(self, 'button_clip_cycles'):
        safe_connect(self.button_clip_cycles, lambda: cropRange(self))
    if hasattr(self, 'button_apply_smooth'):
        safe_connect(self.button_apply_smooth, lambda: smoothAmpl(self))