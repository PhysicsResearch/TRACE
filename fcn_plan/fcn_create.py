# Import necessary libraries and modules
import numpy as np
import pandas as pd
from PySide6.QtWidgets import QTableWidgetItem, QVBoxLayout
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas


def trigger_plot_update(self):
    device = self.combo_device.currentText()
    if device == "Lung Phantom":
        all_axes = ["X", "Y", "Z"]
    else:
        all_axes = ["LAT", "SI", "AP", "Roll", "Pitch", "Yaw"]

    checked_axes = []
    for col in all_axes:
        cb = getattr(self, 'create_axis_checkboxes', {}).get(col, None)
        if cb is not None and cb.isChecked():
            checked_axes.append(col)

    update_plot(self, self.dfEdit, checked_axes)


def initialize_default_curve_data(self):
    """
    Initializes/restores curve data for both Lung Phantom and Motion Platform.
    Ensures switching between them preserves their edited state.
    """
    from PySide6.QtWidgets import QCheckBox

    # 1. Initialize Lung Phantom data if not already present
    if not hasattr(self, 'dfEdit_lung_phantom') or self.dfEdit_lung_phantom is None:
        t = np.linspace(0.0, 60.0, 6001)
        data = {
            'timestamp': t * 1000.0,
            'time': t,
            'X': np.zeros_like(t),
            'Y': np.zeros_like(t),
            'Z': np.zeros_like(t),
            'Command': [""] * len(t)
        }
        self.dfEdit_lung_phantom = pd.DataFrame(data)

    # 2. Initialize Motion Platform data if not already present
    if not hasattr(self, 'dfEdit_motion_platform') or self.dfEdit_motion_platform is None:
        t = np.linspace(0.0, 60.0, 6001)
        data = {
            'timestamp': t * 1000.0,
            'time': t,
            'LAT': np.zeros_like(t),
            'SI': np.zeros_like(t),
            'AP': np.zeros_like(t),
            'Roll': np.zeros_like(t),
            'Pitch': np.zeros_like(t),
            'Yaw': np.zeros_like(t),
            'Command': [""] * len(t)
        }
        self.dfEdit_motion_platform = pd.DataFrame(data)

    # 3. Retrieve current selection and switch active self.dfEdit reference
    device = self.combo_device.currentText()
    if device == "Lung Phantom":
        self.dfEdit = self.dfEdit_lung_phantom
        axes = ["X", "Y", "Z"]
    else:
        self.dfEdit = self.dfEdit_motion_platform
        axes = ["LAT", "SI", "AP", "Roll", "Pitch", "Yaw"]

    self.curve_origin = 'create'

    # Load table
    loadTable_create(self, self.dfEdit)

    # Rebuild checkboxes below the graph
    if hasattr(self, 'create_plot_checkboxes_layout') and self.create_plot_checkboxes_layout is not None:
        layout_cb = self.create_plot_checkboxes_layout
        while layout_cb.count():
            child = layout_cb.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.create_axis_checkboxes = {}
        for col in axes:
            cb = QCheckBox(col, self.create_plot_checkboxes_widget)
            cb.setChecked(True)
            cb.setStyleSheet("font-weight: bold; font-size: 14px; color: #333333;")
            cb.stateChanged.connect(lambda: trigger_plot_update(self))
            layout_cb.addWidget(cb)
            self.create_axis_checkboxes[col] = cb
        
        layout_cb.addStretch()

        # Add Export GCODE button at the right
        from PySide6.QtWidgets import QPushButton
        self.btn_export_gcode = QPushButton("Export GCODE", self.create_plot_checkboxes_widget)
        self.btn_export_gcode.setMinimumHeight(35)
        self.btn_export_gcode.setStyleSheet("""
            QPushButton {
                background-color: #0288d1;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding-left: 15px;
                padding-right: 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #01579b;
            }
        """)
        self.btn_export_gcode.clicked.connect(lambda: export_gcode_action(self))
        layout_cb.addWidget(self.btn_export_gcode)

    # Plot initially showing all axes
    update_plot(self, self.dfEdit, axes)


def loadTable_create(self, dataframe):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QHeaderView
    
    table = self.create_table_view
    table.clear()
    
    # Hide row numbers
    table.verticalHeader().setVisible(False)
    
    # Filter out timestamp
    display_columns = [col for col in dataframe.columns if col != 'timestamp']
    table.setRowCount(dataframe.shape[0])
    table.setColumnCount(len(display_columns))

    header_units = {
        'time': 'Time (s)',
        'amplitude': 'Amplitude (mm)',
        'X': 'X (mm)',
        'Y': 'Y (mm)',
        'Z': 'Z (mm)',
        'LAT': 'LAT (mm)',
        'SI': 'SI (mm)',
        'AP': 'AP (mm)',
        'Roll': 'Roll (deg)',
        'Pitch': 'Pitch (deg)',
        'Yaw': 'Yaw (deg)',
        'Command': 'Command'
    }
    
    headers = [header_units.get(col, col) for col in display_columns]
    table.setHorizontalHeaderLabels(headers)

    for row in range(dataframe.shape[0]):
        is_pause = False
        is_user_wait = False
        if 'Command' in dataframe.columns:
            cmd_val = dataframe.iat[row, dataframe.columns.get_loc('Command')]
            if isinstance(cmd_val, str):
                if 'sensor_wait.g' in cmd_val:
                    is_pause = True
                elif 'M226' in cmd_val:
                    is_user_wait = True

        for col, col_name in enumerate(display_columns):
            val = dataframe.iat[row, dataframe.columns.get_loc(col_name)]
            try:
                float_val = float(val)
                if col_name == 'timestamp':
                    display_text = str(int(round(float_val)))
                else:
                    display_text = f"{float_val:.2f}"
                item = QTableWidgetItem(display_text)
                item.setData(Qt.UserRole, float_val)
            except (ValueError, TypeError):
                item = QTableWidgetItem(str(val))
                item.setData(Qt.UserRole, val)
            
            if is_pause:
                item.setBackground(QColor("#ffcdd2"))
            elif is_user_wait:
                item.setBackground(QColor("#fff9c4"))
                
            table.setItem(row, col, item)
            
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)


def create_curve(self):
    """
    Applies/Adds a curve segment to the selected axis over the defined [t_start, t_end] interval,
    overwriting only that interval, keeping the rest of the column data intact,
    and expanding the dataframe range up to t_end if it goes past the current limits.
    """
    if not hasattr(self, 'dfEdit') or self.dfEdit is None:
        initialize_default_curve_data(self)

    device = self.combo_device.currentText()
    selected_axis = self.combo_axis.currentText()
    func_type = self.combo_func_type.currentText()

    amplitude = self.input_amplitude.value()
    amp_offset = self.input_amp_offset.value() if hasattr(self, 'input_amp_offset') else 0.0
    period = self.input_period.value()
    phase_deg = self.input_phase.value()
    phase_rad = np.deg2rad(phase_deg)
    t_start = self.input_start_time.value()
    t_end = self.input_end_time.value()

    # 1. Expand limits if t_end is greater than current maximum time in the dataframe
    t_max = self.dfEdit['time'].max()
    if t_end > t_max:
        # Generate extra timestamps
        step = 0.01
        new_t = np.arange(t_max + step, t_end + step/2.0, step)
        if len(new_t) > 0:
            new_rows = pd.DataFrame({
                'timestamp': new_t * 1000.0,
                'time': new_t
            })
            # Initialize all axes to 0.0 for new rows
            if device == "Lung Phantom":
                all_axes = ["X", "Y", "Z"]
            else:
                all_axes = ["LAT", "SI", "AP", "Roll", "Pitch", "Yaw"]
            for col in all_axes:
                new_rows[col] = 0.0
            new_rows['Command'] = ""
            
            # Append new rows to self.dfEdit
            self.dfEdit = pd.concat([self.dfEdit, new_rows], ignore_index=True)

    if 'Command' not in self.dfEdit.columns:
        self.dfEdit['Command'] = ""

    # 2. Re-read the time values from the expanded dataframe
    t_arr = self.dfEdit['time'].values

    # 3. Find indices where t_start <= t <= t_end and compute the values
    for idx, t_val in enumerate(t_arr):
        if t_start <= t_val <= t_end:
            t_rel = t_val - t_start
            if func_type == "sin":
                val = amplitude * np.sin(2.0 * np.pi * t_rel / period + phase_rad) + amp_offset
            elif func_type == "cos":
                val = amplitude * np.cos(2.0 * np.pi * t_rel / period + phase_rad) + amp_offset
            elif func_type == "cos^1":
                val = amplitude * (np.cos(2.0 * np.pi * t_rel / period + phase_rad) ** 1) + amp_offset
            elif func_type == "cos^2":
                val = amplitude * (np.cos(2.0 * np.pi * t_rel / period + phase_rad) ** 2) + amp_offset
            elif func_type == "constant":
                val = amplitude + amp_offset
            else:
                val = amplitude * np.sin(2.0 * np.pi * t_rel / period + phase_rad) + amp_offset
            
            # Overwrite the selected axis value at this index
            if selected_axis in self.dfEdit.columns:
                self.dfEdit.at[idx, selected_axis] = val

    # Save the reference back to the appropriate persistent dataframe
    if device == "Lung Phantom":
        self.dfEdit_lung_phantom = self.dfEdit
    else:
        self.dfEdit_motion_platform = self.dfEdit

    # 4. Reload table
    loadTable_create(self, self.dfEdit)

    # 5. Re-plot checked columns
    trigger_plot_update(self)


def add_row(self):
    pass


def remove_row(self):
    pass


def update_plot(self, dataframe, axes_list):
    """This function plots the created curves from the dataframe."""
    self.plot_fig = Figure()
    ax = self.plot_fig.add_subplot(111)
    
    # Set plot background to transparent
    ax.patch.set_alpha(0.0)
    self.plot_fig.patch.set_alpha(0.0)

    # Customize text and axes properties to be visible on the light background
    font_sz = getattr(self, 'selected_font_size', 14)
    ax.tick_params(colors='#333333', labelsize=font_sz-2)
    ax.xaxis.label.set_color('#333333')
    ax.yaxis.label.set_color('#333333')
    ax.spines['bottom'].set_color('#333333')
    ax.spines['top'].set_color('#333333')
    ax.spines['left'].set_color('#333333')
    ax.spines['right'].set_color('#333333')

    # Plot the data
    t_data = dataframe["time"]
    for col in axes_list:
        if col in dataframe.columns:
            ax.plot(t_data, dataframe[col], label=col, linewidth=1.5)

    # Draw vertical lines for pause/wait commands
    if 'Command' in dataframe.columns:
        for idx, cmd in enumerate(dataframe['Command'].values):
            if isinstance(cmd, str) and cmd.strip():
                t_val = dataframe['time'].values[idx]
                if 'sensor_wait.g' in cmd:
                    ax.axvline(x=t_val, color='#e53935', linestyle='--', linewidth=1.5, alpha=0.85)
                elif 'M226' in cmd:
                    ax.axvline(x=t_val, color='#fbc02d', linestyle='--', linewidth=1.5, alpha=0.85)

    ax.legend(loc='upper right', fontsize=10, labelcolor='#333333')
    ax.set_xlim(t_data.min(), t_data.max())
    ax.set_xlabel('Time (s)', fontsize=font_sz, fontweight='bold')
    ax.set_ylabel('Amplitude (mm / deg)', fontsize=font_sz, fontweight='bold')
    ax.grid(True, linestyle=":", alpha=0.5, color="#888888")

    self.plot_fig.tight_layout()

    # Create a canvas
    canvas = FigureCanvas(self.plot_fig)
    canvas.setStyleSheet("background-color:Transparent;")



    container = self.create_plot_canvas_container
    if container.layout() is None:
        layout = QVBoxLayout(container)
        container.setLayout(layout)
    else:
        # Clear existing content in the container
        while container.layout().count():
            child = container.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    # Add the canvas to the container
    container.layout().addWidget(canvas)

    # Add Navigation Toolbar for zoom and pan below the graph
    from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
    toolbar = NavigationToolbar(canvas, container)
    toolbar.setStyleSheet("background-color: #f5f5f5; border: none; font-weight: bold;")
    container.layout().addWidget(toolbar)

    canvas.draw()


from .fcn_import import addColumns, loadTable


def createCurve(self):
    # Overwrite curves on the selected column and plot
    create_curve(self)
    # Extract final dfEdit from the table to keep it fully synchronized
    from .fcn_edit import getDataframeFromTable
    getDataframeFromTable(self)


from .fcn_gcode import generate_gcode_string


def export_gcode_action(self):
    """
    Interpolates active dataframe curve data at 0.001s intervals and writes G-code.
    """
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    import pandas as pd
    import numpy as np
    import os

    if not hasattr(self, 'dfEdit') or self.dfEdit is None:
        QMessageBox.warning(self, "Warning", "No curve data available to export.")
        return

    device = self.combo_device.currentText()
    if device not in ["Lung Phantom", "Motion Platform"]:
        QMessageBox.warning(self, "Warning", f"Unsupported device type: {device}")
        return

    # Let user select where to save the GCODE file
    file_path, _ = QFileDialog.getSaveFileName(self, "Save G-code File", "", "G-code Files (*.gcode);;All Files (*)")
    if not file_path:
        return

    try:
        t_orig = self.dfEdit['time'].values
        columns_data = {}
        if 'Command' in self.dfEdit.columns:
            columns_data['Command'] = self.dfEdit['Command'].values

        if device == "Lung Phantom":
            for col in ["X", "Y", "Z"]:
                if col not in self.dfEdit.columns:
                    QMessageBox.warning(self, "Warning", f"Missing axis data '{col}' in the planning table.")
                    return
                columns_data[col] = self.dfEdit[col].values

            # Retrieve settings limits
            max_lim_x = getattr(self, 'settings_max_lim_x', None)
            max_lim_y = getattr(self, 'settings_max_lim_y', None)
            max_lim_z = getattr(self, 'settings_max_lim_z', None)

            lim_x = max_lim_x.value() if max_lim_x else 40.0
            lim_y = max_lim_y.value() if max_lim_y else 40.0
            lim_z = max_lim_z.value() if max_lim_z else 40.0
            max_limits = (lim_x, lim_y, lim_z)

            gcode_content, exceeds_limits = generate_gcode_string(
                device, t_orig, columns_data, max_limits
            )

        else: # Motion Platform
            for col in ["LAT", "SI", "AP", "Roll", "Pitch", "Yaw"]:
                if col not in self.dfEdit.columns:
                    QMessageBox.warning(self, "Warning", f"Missing axis data '{col}' in the planning table.")
                    return
                columns_data[col] = self.dfEdit[col].values

            # Retrieve settings limits
            max_lim_lat = getattr(self, 'settings_max_lim_lat', None)
            max_lim_si = getattr(self, 'settings_max_lim_si', None)
            max_lim_ap = getattr(self, 'settings_max_lim_ap', None)
            max_lim_roll = getattr(self, 'settings_max_lim_roll', None)
            max_lim_pitch = getattr(self, 'settings_max_lim_pitch', None)
            max_lim_yaw = getattr(self, 'settings_max_lim_yaw', None)

            lim_lat = max_lim_lat.value() if max_lim_lat else 40.0
            lim_si = max_lim_si.value() if max_lim_si else 40.0
            lim_ap = max_lim_ap.value() if max_lim_ap else 40.0
            lim_roll = max_lim_roll.value() if max_lim_roll else 40.0
            lim_pitch = max_lim_pitch.value() if max_lim_pitch else 40.0
            lim_yaw = max_lim_yaw.value() if max_lim_yaw else 40.0
            max_limits = (lim_lat, lim_si, lim_ap, lim_roll, lim_pitch, lim_yaw)

            # Retrieve and strictly validate dimensions and offsets (raise error if missing or invalid)
            if not hasattr(self, 'input_plat_lat') or not self.input_plat_lat or not self.input_plat_lat.text().strip():
                QMessageBox.warning(self, "Export Error", "Platform LAT dimension input field is missing or empty.")
                return
            try:
                lat_dim = float(self.input_plat_lat.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Export Error", f"Invalid platform LAT dimension value: '{self.input_plat_lat.text()}'")
                return

            if not hasattr(self, 'input_plat_si') or not self.input_plat_si or not self.input_plat_si.text().strip():
                QMessageBox.warning(self, "Export Error", "Platform SI dimension input field is missing or empty.")
                return
            try:
                si_dim = float(self.input_plat_si.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Export Error", f"Invalid platform SI dimension value: '{self.input_plat_si.text()}'")
                return

            if not hasattr(self, 'input_offset_ap') or not self.input_offset_ap or not self.input_offset_ap.text().strip():
                QMessageBox.warning(self, "Export Error", "Offset AP input field is missing or empty.")
                return
            try:
                off_ap = float(self.input_offset_ap.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Export Error", f"Invalid offset AP value: '{self.input_offset_ap.text()}'")
                return

            if not hasattr(self, 'input_offset_lat') or not self.input_offset_lat or not self.input_offset_lat.text().strip():
                QMessageBox.warning(self, "Export Error", "Offset LAT input field is missing or empty.")
                return
            try:
                off_lat = float(self.input_offset_lat.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Export Error", f"Invalid offset LAT value: '{self.input_offset_lat.text()}'")
                return

            if not hasattr(self, 'input_offset_si') or not self.input_offset_si or not self.input_offset_si.text().strip():
                QMessageBox.warning(self, "Export Error", "Offset SI input field is missing or empty.")
                return
            try:
                off_si = float(self.input_offset_si.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Export Error", f"Invalid offset SI value: '{self.input_offset_si.text()}'")
                return

            axis_y_lo = "'c"
            if hasattr(self, 'axis_max_limits') and ("b" in self.axis_max_limits or "'b" in self.axis_max_limits):
                axis_y_lo = "'b"

            gcode_content, exceeds_limits = generate_gcode_string(
                device, t_orig, columns_data, max_limits,
                lat_dim, si_dim, off_ap, off_lat, off_si, axis_y_lo
            )

        if exceeds_limits:
            res = QMessageBox.question(
                self, 
                "Limits Exceeded", 
                "Warning: Some curve points exceed the maximum limits defined in Settings.\nDo you still want to export?",
                QMessageBox.Yes | QMessageBox.No
            )
            if res == QMessageBox.No:
                return

        with open(file_path, 'w') as f:
            f.write(gcode_content)

        QMessageBox.information(self, "Success", f"G-code successfully exported to:\n{file_path}")

    except Exception as e:
        QMessageBox.critical(self, "Error", f"Failed to export G-code:\n{str(e)}")


def add_wait_radiation_action(self):
    """
    Adds a 'M98 P"0:macros/sensor_wait.g"' command to the closest time step in dfEdit.
    """
    from PySide6.QtWidgets import QMessageBox
    import numpy as np

    if not hasattr(self, 'dfEdit') or self.dfEdit is None:
        initialize_default_curve_data(self)

    if not hasattr(self, 'input_wait_rad_time') or not self.input_wait_rad_time:
        QMessageBox.warning(self, "Wait Radiation Error", "Wait radiation input field is missing.")
        return

    target_time = self.input_wait_rad_time.value()
    times = self.dfEdit['time'].values
    
    if len(times) == 0:
        QMessageBox.warning(self, "Wait Radiation Error", "Planning table is empty.")
        return

    # Find the closest time index in dfEdit
    idx = np.nanargmin(np.abs(times - target_time))
    
    if 'Command' not in self.dfEdit.columns:
        self.dfEdit['Command'] = ""

    # Set command
    self.dfEdit.at[idx, 'Command'] = 'M98 P"0:macros/sensor_wait.g"'

    # Save the reference back to the appropriate persistent dataframe
    device = self.combo_device.currentText()
    if device == "Lung Phantom":
        self.dfEdit_lung_phantom = self.dfEdit
    else:
        self.dfEdit_motion_platform = self.dfEdit

    # Reload table
    loadTable_create(self, self.dfEdit)
    
    # Save the change back from table to fully synchronize
    from .fcn_edit import getDataframeFromTable
    getDataframeFromTable(self)

    # Re-plot to show the vertical line immediately
    trigger_plot_update(self)


def add_wait_user_action(self):
    """
    Adds a 'M226' command to the closest time step in dfEdit.
    """
    from PySide6.QtWidgets import QMessageBox
    import numpy as np

    if not hasattr(self, 'dfEdit') or self.dfEdit is None:
        initialize_default_curve_data(self)

    if not hasattr(self, 'input_wait_rad_time') or not self.input_wait_rad_time:
        QMessageBox.warning(self, "Wait User Error", "Wait time input field is missing.")
        return

    target_time = self.input_wait_rad_time.value()
    times = self.dfEdit['time'].values
    
    if len(times) == 0:
        QMessageBox.warning(self, "Wait User Error", "Planning table is empty.")
        return

    # Find the closest time index in dfEdit
    idx = np.nanargmin(np.abs(times - target_time))
    
    if 'Command' not in self.dfEdit.columns:
        self.dfEdit['Command'] = ""

    # Set command
    self.dfEdit.at[idx, 'Command'] = 'M226'

    # Save the reference back to the appropriate persistent dataframe
    device = self.combo_device.currentText()
    if device == "Lung Phantom":
        self.dfEdit_lung_phantom = self.dfEdit
    else:
        self.dfEdit_motion_platform = self.dfEdit

    # Reload table
    loadTable_create(self, self.dfEdit)
    
    # Save the change back from table to fully synchronize
    from .fcn_edit import getDataframeFromTable
    getDataframeFromTable(self)

    # Re-plot to show the vertical line immediately
    trigger_plot_update(self)


def clear_rad_pauses_action(self):
    """
    Clears all Wait Radiation (sensor_wait.g) commands from dfEdit.
    """
    from PySide6.QtWidgets import QMessageBox
    if not hasattr(self, 'dfEdit') or self.dfEdit is None:
        return

    if 'Command' in self.dfEdit.columns:
        # Clear entries containing 'sensor_wait.g'
        for idx in range(len(self.dfEdit)):
            val = self.dfEdit.at[idx, 'Command']
            if isinstance(val, str) and 'sensor_wait.g' in val:
                self.dfEdit.at[idx, 'Command'] = ""

    # Save reference
    device = self.combo_device.currentText()
    if device == "Lung Phantom":
        self.dfEdit_lung_phantom = self.dfEdit
    else:
        self.dfEdit_motion_platform = self.dfEdit

    # Reload table & plot
    loadTable_create(self, self.dfEdit)
    from .fcn_edit import getDataframeFromTable
    getDataframeFromTable(self)
    trigger_plot_update(self)


def clear_usr_pauses_action(self):
    """
    Clears all Wait User (M226) commands from dfEdit.
    """
    from PySide6.QtWidgets import QMessageBox
    if not hasattr(self, 'dfEdit') or self.dfEdit is None:
        return

    if 'Command' in self.dfEdit.columns:
        # Clear entries containing 'M226'
        for idx in range(len(self.dfEdit)):
            val = self.dfEdit.at[idx, 'Command']
            if isinstance(val, str) and 'M226' in val:
                self.dfEdit.at[idx, 'Command'] = ""

    # Save reference
    device = self.combo_device.currentText()
    if device == "Lung Phantom":
        self.dfEdit_lung_phantom = self.dfEdit
    else:
        self.dfEdit_motion_platform = self.dfEdit

    # Reload table & plot
    loadTable_create(self, self.dfEdit)
    from .fcn_edit import getDataframeFromTable
    getDataframeFromTable(self)
    trigger_plot_update(self)