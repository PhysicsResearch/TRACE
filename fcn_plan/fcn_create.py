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
    elif device == "Motion Platform":
        all_axes = ["LAT", "SI", "AP", "Roll", "Pitch", "Yaw"]
    else:
        exclude_cols = {'timestamp', 'time', 'Command'}
        all_axes = [col for col in self.dfEdit.columns if col not in exclude_cols]

    checked_axes = []
    for col in all_axes:
        cb = getattr(self, 'create_axis_checkboxes', {}).get(col, None)
        if cb is not None and cb.isChecked():
            checked_axes.append(col)

    # Check if we should plot high resolution or downsampled data
    df_to_plot = self.dfEdit
    high_res_cb = getattr(self, 'check_plot_high_res', None)
    if high_res_cb is not None and not high_res_cb.isChecked():
        if len(self.dfEdit) > 1:
            dt = self.dfEdit['time'].iat[1] - self.dfEdit['time'].iat[0]
            if dt > 0:
                step = max(1, int(round(0.1 / dt)))
                df_to_plot = self.dfEdit.iloc[::step]

    update_plot(self, df_to_plot, checked_axes)


def rebuild_axis_checkboxes(self, axes):
    from PySide6.QtWidgets import QCheckBox, QPushButton
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
            cb.stateChanged.connect(lambda state, c=col: trigger_plot_update(self))
            layout_cb.addWidget(cb)
            self.create_axis_checkboxes[col] = cb
        
        layout_cb.addStretch()

        # Add Plot High Resolution checkbox on the left of Export GCODE button
        self.check_plot_high_res = QCheckBox("Plot High Resolution", self.create_plot_checkboxes_widget)
        self.check_plot_high_res.setChecked(False)  # Unchecked by default for fast plotting
        self.check_plot_high_res.setStyleSheet("font-weight: bold; font-size: 14px; color: #0d47a1; margin-right: 15px;")
        self.check_plot_high_res.stateChanged.connect(lambda state: trigger_plot_update(self))
        layout_cb.addWidget(self.check_plot_high_res)

        # Add Export GCODE button at the right
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

        # Add Upload to Duet button next to it
        self.btn_upload_duet = QPushButton("Upload to Duet", self.create_plot_checkboxes_widget)
        self.btn_upload_duet.setMinimumHeight(35)
        self.btn_upload_duet.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding-left: 15px;
                padding-right: 15px;
                border-radius: 4px;
                margin-left: 5px;
            }
            QPushButton:hover {
                background-color: #1b5e20;
            }
        """)
        self.btn_upload_duet.clicked.connect(lambda: upload_gcode_to_duet_action(self))
        layout_cb.addWidget(self.btn_upload_duet)


def initialize_default_curve_data(self):
    """
    Initializes/restores curve data for Lung Phantom, Motion Platform, and Other.
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

    # 3. Initialize Other data if not already present
    if not hasattr(self, 'dfEdit_other') or self.dfEdit_other is None:
        t = np.linspace(0.0, 60.0, 6001)
        data = {
            'timestamp': t * 1000.0,
            'time': t,
            'A': np.zeros_like(t),
            'B': np.zeros_like(t),
            'C': np.zeros_like(t),
            'D': np.zeros_like(t),
            'Command': [""] * len(t)
        }
        self.dfEdit_other = pd.DataFrame(data)

    # 4. Retrieve current selection and switch active self.dfEdit reference
    device = self.combo_device.currentText()
    if device == "Lung Phantom":
        self.dfEdit = self.dfEdit_lung_phantom
        axes = ["X", "Y", "Z"]
    elif device == "Motion Platform":
        self.dfEdit = self.dfEdit_motion_platform
        axes = ["LAT", "SI", "AP", "Roll", "Pitch", "Yaw"]
    else:
        self.dfEdit = self.dfEdit_other
        exclude_cols = {'timestamp', 'time', 'Command'}
        axes = [col for col in self.dfEdit.columns if col not in exclude_cols]

    self.curve_origin = 'create'

    # Load table
    loadTable_create(self, self.dfEdit)

    # Rebuild checkboxes below the graph
    rebuild_axis_checkboxes(self, axes)

    # Plot initially showing all axes
    update_plot(self, self.dfEdit, axes)


def loadTable_create(self, dataframe, progress=None, start_val=0):
    from PySide6.QtCore import Qt, QCoreApplication
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QHeaderView, QTableWidgetItem
    
    table = self.create_table_view
    table.setUpdatesEnabled(False)
    table.blockSignals(True)
    table.clear()
    
    # Hide row numbers and style table
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(32)
    table.setStyleSheet("""
        QTableWidget {
            font-size: 15px;
        }
        QHeaderView::section {
            font-weight: bold;
            font-size: 15px;
        }
    """)
    
    # Reset index to guarantee clean lookup mapping
    dataframe = dataframe.reset_index(drop=True)
    
    # Compute downsampling step to target ~0.1s resolution in visual interface
    step = 1
    if dataframe.shape[0] > 1:
        dt = dataframe['time'].iat[1] - dataframe['time'].iat[0]
        if dt > 0:
            step = max(1, int(round(0.1 / dt)))
            
    # Always include indices that are multiples of step, plus any rows containing active commands
    display_indices = list(range(0, dataframe.shape[0], step))
    if 'Command' in dataframe.columns:
        cmd_indices = dataframe[dataframe['Command'].astype(str).str.strip() != ''].index.tolist()
        display_indices = sorted(list(set(display_indices + cmd_indices)))
    else:
        display_indices = sorted(list(set(display_indices)))

    # Filter out timestamp
    display_columns = [col for col in dataframe.columns if col != 'timestamp']
    table.setRowCount(len(display_indices))
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

    if progress is not None:
        progress.setLabelText("Populating table cells...")

    for row_idx, bg_row in enumerate(display_indices):
        if progress is not None and row_idx % 1000 == 0:
            progress.setValue(start_val + row_idx)
            QCoreApplication.processEvents()
            if progress.wasCanceled():
                break

        is_pause = False
        is_user_wait = False
        if 'Command' in dataframe.columns:
            cmd_val = dataframe.iat[bg_row, dataframe.columns.get_loc('Command')]
            if isinstance(cmd_val, str):
                if 'sensor_wait.g' in cmd_val:
                    is_pause = True
                elif 'M226' in cmd_val:
                    is_user_wait = True

        for col, col_name in enumerate(display_columns):
            val = dataframe.iat[bg_row, dataframe.columns.get_loc(col_name)]
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
                
            # Store original background index to sync edits
            item.setData(Qt.UserRole + 1, bg_row)
            
            if is_pause:
                item.setBackground(QColor("#ffcdd2"))
            elif is_user_wait:
                item.setBackground(QColor("#fff9c4"))
                
            table.setItem(row_idx, col, item)
            
    # Set column resize modes: numeric columns are interactive (120px), last column stretches
    header = table.horizontalHeader()
    for col in range(table.columnCount() - 1):
        header.setSectionResizeMode(col, QHeaderView.Interactive)
        table.setColumnWidth(col, 120)
    if table.columnCount() > 0:
        header.setSectionResizeMode(table.columnCount() - 1, QHeaderView.Stretch)

    table.blockSignals(False)
    table.setUpdatesEnabled(True)


def on_table_item_changed(self, item):
    """
    Applies user edits in visual table cells directly back to the
    background high-resolution self.dfEdit DataFrame at the correct index.
    """
    if not hasattr(self, 'dfEdit') or self.dfEdit is None:
        return
        
    from PySide6.QtCore import Qt
    bg_row = item.data(Qt.UserRole + 1)
    if bg_row is None or bg_row >= len(self.dfEdit):
        return
        
    col = item.column()
    table = self.create_table_view
    header_item = table.horizontalHeaderItem(col)
    if not header_item:
        return
    header_text = header_item.text()
    
    reverse_mapping = {
        'Time (s)': 'time',
        'Amplitude (mm)': 'amplitude',
        'X (mm)': 'X',
        'Y (mm)': 'Y',
        'Z (mm)': 'Z',
        'LAT (mm)': 'LAT',
        'SI (mm)': 'SI',
        'AP (mm)': 'AP',
        'Roll (deg)': 'Roll',
        'Pitch (deg)': 'Pitch',
        'Yaw (deg)': 'Yaw',
        'Command': 'Command'
    }
    col_name = reverse_mapping.get(header_text, header_text)
    
    val_text = item.text()
    try:
        if col_name == 'Command':
            new_val = val_text
        else:
            new_val = float(val_text)
    except ValueError:
        new_val = val_text
        
    self.dfEdit.at[bg_row, col_name] = new_val
    
    if col_name == 'time' and isinstance(new_val, (int, float)):
        self.dfEdit.at[bg_row, 'timestamp'] = new_val * 1000.0
        
    self.dfEdit_copy = self.dfEdit.copy()
    
    device = self.combo_device.currentText()
    if device == "Lung Phantom":
        self.dfEdit_lung_phantom = self.dfEdit
    elif device == "Motion Platform":
        self.dfEdit_motion_platform = self.dfEdit
    else:
        self.dfEdit_other = self.dfEdit


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
        # Detect active step dynamically from existing time steps, fallback to 0.001
        step = 0.001
        if len(self.dfEdit) > 1:
            step = self.dfEdit['time'].iat[1] - self.dfEdit['time'].iat[0]
            if step <= 0:
                step = 0.001

        new_t = np.arange(t_max + step, t_end + step/2.0, step)
        if len(new_t) > 0:
            new_rows = pd.DataFrame({
                'timestamp': new_t * 1000.0,
                'time': new_t
            })
            # Initialize all active axes columns present in self.dfEdit to 0.0 for new rows
            exclude_cols = {'timestamp', 'time', 'Command'}
            all_axes = [col for col in self.dfEdit.columns if col not in exclude_cols]
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
    elif device == "Motion Platform":
        self.dfEdit_motion_platform = self.dfEdit
    else:
        self.dfEdit_other = self.dfEdit

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


def generate_planned_gcode(self):
    """
    Interpolates active dataframe curve data at 0.001s intervals and generates G-code.
    Returns (gcode_content, default_filename) or (None, None) if validation fails.
    """
    from PySide6.QtWidgets import QMessageBox
    import pandas as pd
    import numpy as np

    if not hasattr(self, 'dfEdit') or self.dfEdit is None:
        QMessageBox.warning(self, "Warning", "No curve data available to export.")
        return None, None

    device = self.combo_device.currentText()
    if device not in ["Lung Phantom", "Motion Platform", "Other"]:
        QMessageBox.warning(self, "Warning", f"Unsupported device type: {device}")
        return None, None

    t_orig = self.dfEdit['time'].values
    columns_data = {}
    if 'Command' in self.dfEdit.columns:
        columns_data['Command'] = self.dfEdit['Command'].values

    if device == "Lung Phantom":
        for col in ["X", "Y", "Z"]:
            if col not in self.dfEdit.columns:
                QMessageBox.warning(self, "Warning", f"Missing axis data '{col}' in the planning table.")
                return None, None
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

    elif device == "Motion Platform":
        for col in ["LAT", "SI", "AP", "Roll", "Pitch", "Yaw"]:
            if col not in self.dfEdit.columns:
                QMessageBox.warning(self, "Warning", f"Missing axis data '{col}' in the planning table.")
                return None, None
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
            return None, None
        try:
            lat_dim = float(self.input_plat_lat.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Export Error", f"Invalid platform LAT dimension value: '{self.input_plat_lat.text()}'")
            return None, None

        if not hasattr(self, 'input_plat_si') or not self.input_plat_si or not self.input_plat_si.text().strip():
            QMessageBox.warning(self, "Export Error", "Platform SI dimension input field is missing or empty.")
            return None, None
        try:
            si_dim = float(self.input_plat_si.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Export Error", f"Invalid platform SI dimension value: '{self.input_plat_si.text()}'")
            return None, None

        if not hasattr(self, 'input_offset_ap') or not self.input_offset_ap or not self.input_offset_ap.text().strip():
            QMessageBox.warning(self, "Export Error", "Offset AP input field is missing or empty.")
            return None, None
        try:
            off_ap = float(self.input_offset_ap.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Export Error", f"Invalid offset AP value: '{self.input_offset_ap.text()}'")
            return None, None

        if not hasattr(self, 'input_offset_lat') or not self.input_offset_lat or not self.input_offset_lat.text().strip():
            QMessageBox.warning(self, "Export Error", "Offset LAT input field is missing or empty.")
            return None, None
        try:
            off_lat = float(self.input_offset_lat.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Export Error", f"Invalid offset LAT value: '{self.input_offset_lat.text()}'")
            return None, None

        if not hasattr(self, 'input_offset_si') or not self.input_offset_si or not self.input_offset_si.text().strip():
            QMessageBox.warning(self, "Export Error", "Offset SI input field is missing or empty.")
            return None, None
        try:
            off_si = float(self.input_offset_si.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Export Error", f"Invalid offset SI value: '{self.input_offset_si.text()}'")
            return None, None

        axis_y_lo = "'c"
        if hasattr(self, 'axis_max_limits') and ("b" in self.axis_max_limits or "'b" in self.axis_max_limits):
            axis_y_lo = "'b"

        gcode_content, exceeds_limits = generate_gcode_string(
            device, t_orig, columns_data, max_limits,
            lat_dim, si_dim, off_ap, off_lat, off_si, axis_y_lo
        )

    else: # Other
        exclude_cols = {'timestamp', 'time', 'Command'}
        axes_list = [col for col in self.dfEdit.columns if col not in exclude_cols]
        for col in axes_list:
            columns_data[col] = self.dfEdit[col].values

        max_lim_lat = getattr(self, 'settings_max_lim_lat', None)
        lim = max_lim_lat.value() if max_lim_lat else 40.0
        max_limits = [lim]

        gcode_content, exceeds_limits = generate_gcode_string(
            device, t_orig, columns_data, max_limits
        )

    if exceeds_limits:
        res = QMessageBox.question(
            self, 
            "Limits Exceeded", 
            "Warning: Some curve points exceed the maximum limits defined in Settings.\nDo you still want to proceed?",
            QMessageBox.Yes | QMessageBox.No
        )
        if res == QMessageBox.No:
            return None, None

    func_type = self.combo_func_type.currentText()
    selected_axis = self.combo_axis.currentText()
    default_name = f"planned_{device.lower().replace(' ', '_')}_{selected_axis}_{func_type}.gcode"
    return gcode_content, default_name


def export_gcode_action(self):
    """
    Interpolates active dataframe curve data at 0.001s intervals and writes G-code.
    """
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    
    try:
        gcode_content, default_name = generate_planned_gcode(self)
        if not gcode_content:
            return

        # Let user select where to save the GCODE file
        file_path, _ = QFileDialog.getSaveFileName(self, "Save G-code File", default_name, "G-code Files (*.gcode);;All Files (*)")
        if not file_path:
            return

        with open(file_path, 'w') as f:
            f.write(gcode_content)

        QMessageBox.information(self, "Success", f"G-code successfully exported to:\n{file_path}")

    except Exception as e:
        QMessageBox.critical(self, "Error", f"Failed to export G-code:\n{str(e)}")


def upload_gcode_to_duet_action(self):
    """
    Generates G-code string from the active curve, prompts for a target name on Duet,
    and uploads it to '0:/gcodes/' with a progress bar and cancel option.
    """
    from PySide6.QtWidgets import QMessageBox, QInputDialog, QProgressDialog, QLineEdit
    from PySide6.QtCore import Qt, QCoreApplication
    from fcn_monitor.fcn_duet import get_clean_duet_ip, duet_request
    import requests
    import io

    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before uploading files.")
        return

    polling_active = False
    fast_active = False
    original_connected_state = True
    try:
        # Temporarily set duet_connected to False and stop timers to completely inhibit concurrent polling requests
        self.duet_connected = False
        
        if hasattr(self, 'status_polling_timer') and self.status_polling_timer.isActive():
            self.status_polling_timer.stop()
            polling_active = True
        if hasattr(self, 'status_fast_timer') and self.status_fast_timer.isActive():
            self.status_fast_timer.stop()
            fast_active = True

        gcode_content, default_name = generate_planned_gcode(self)
        if not gcode_content:
            return

        # Prompt for target name on Duet (touchscreen-friendly sizing & styling)
        from PySide6.QtWidgets import QWidget
        parent_widget = self if (isinstance(self, QWidget) and not type(self).__name__.endswith('Mock')) else None
        dialog = QInputDialog(parent_widget)
        dialog.setWindowTitle("Upload Name")
        dialog.setLabelText("Enter target filename on Duet:")
        dialog.setTextValue(default_name)
        dialog.setInputMode(QInputDialog.TextInput)
        dialog.setMinimumWidth(1260)
        dialog.setMinimumHeight(200)
        dialog.setStyleSheet("""
            QInputDialog {
                font-size: 18px;
                font-weight: bold;
                min-width: 1260px;
            }
            QLabel {
                font-size: 18px;
                min-height: 40px;
            }
            QLineEdit {
                font-size: 18px;
                min-height: 45px;
                min-width: 1190px;
                padding: 6px;
            }
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                min-width: 120px;
                min-height: 45px;
                border-radius: 4px;
            }
        """)
        
        ok = dialog.exec()
        if not ok or not dialog.textValue().strip():
            return

        filename = dialog.textValue().strip()
        rrf_path = f"0:/gcodes/{filename}"

        ip = get_clean_duet_ip(self)
        url = f"http://{ip}/rr_upload"

        gcode_bytes = gcode_content.encode('utf-8')
        total_size = len(gcode_bytes)

        # Initialize progress dialog (touchscreen-friendly sizing & styling)
        progress = QProgressDialog("Uploading G-code to Duet...", "Cancel", 0, 100, parent_widget)
        progress.setWindowTitle("Uploading to Duet")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumWidth(550)
        progress.setMinimumHeight(180)
        progress.setStyleSheet("""
            QProgressDialog {
                font-size: 18px;
                font-weight: bold;
            }
            QLabel {
                font-size: 18px;
                min-height: 40px;
            }
            QProgressBar {
                text-align: center;
                font-size: 18px;
                font-weight: bold;
                height: 35px;
                border-radius: 4px;
            }
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                min-width: 120px;
                min-height: 45px;
                border-radius: 4px;
            }
        """)
        progress.setValue(0)
        progress.show()
        QCoreApplication.processEvents()

        # Update progress to show sending phase
        progress.setValue(30)
        QCoreApplication.processEvents()

        # Create a fresh, temporary connection session to upload the raw bytes, avoiding stale socket reuse in the shared pool
        session = requests.Session()
        session.trust_env = False
        try:
            response = session.post(url, params={'name': rrf_path}, data=gcode_bytes, timeout=30)
            response.raise_for_status()
        finally:
            session.close()

        progress.setValue(100)
        QMessageBox.information(parent_widget, "Upload Successful", f"G-code '{filename}' uploaded successfully to Duet root gcodes folder!")

    except Exception as e:
        if 'progress' in locals():
            progress.close()
        if "cancelled by user" in str(e):
            QMessageBox.information(parent_widget, "Upload Cancelled", "G-code upload was cancelled by the user.")
        else:
            QMessageBox.critical(parent_widget, "Upload Error", f"Failed to upload G-code to Duet:\n{str(e)}")
    finally:
        self.duet_connected = original_connected_state
        if polling_active and hasattr(self, 'status_polling_timer'):
            self.status_polling_timer.start()
        if fast_active and hasattr(self, 'status_fast_timer'):
            self.status_fast_timer.start()


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
    elif device == "Motion Platform":
        self.dfEdit_motion_platform = self.dfEdit
    else:
        self.dfEdit_other = self.dfEdit

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
    elif device == "Motion Platform":
        self.dfEdit_motion_platform = self.dfEdit
    else:
        self.dfEdit_other = self.dfEdit

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
    elif device == "Motion Platform":
        self.dfEdit_motion_platform = self.dfEdit
    else:
        self.dfEdit_other = self.dfEdit

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
    elif device == "Motion Platform":
        self.dfEdit_motion_platform = self.dfEdit
    else:
        self.dfEdit_other = self.dfEdit

    # Reload table & plot
    loadTable_create(self, self.dfEdit)
    from .fcn_edit import getDataframeFromTable
    getDataframeFromTable(self)
    trigger_plot_update(self)


def clear_all_action(self):
    """
    Clears all curve data by setting all coordinate axis values to 0.0 and clearing commands in self.dfEdit.
    """
    if not hasattr(self, 'dfEdit') or self.dfEdit is None:
        return

    exclude_cols = {'timestamp', 'time'}
    for col in self.dfEdit.columns:
        if col not in exclude_cols:
            if col == 'Command':
                self.dfEdit['Command'] = ""
            else:
                self.dfEdit[col] = 0.0

    # Save reference
    device = self.combo_device.currentText()
    if device == "Lung Phantom":
        self.dfEdit_lung_phantom = self.dfEdit
    elif device == "Motion Platform":
        self.dfEdit_motion_platform = self.dfEdit
    else:
        self.dfEdit_other = self.dfEdit

    # Reload table & plot
    loadTable_create(self, self.dfEdit)
    from .fcn_edit import getDataframeFromTable
    getDataframeFromTable(self)
    trigger_plot_update(self)


def _reverse_motion_platform_kinematics(self, df):
    """
    Reverse-maps actuator G-code columns (A, B, C, D, 'e, 'f, 'a, 'c/'b)
    back to Motion Platform DOFs (LAT, SI, AP, Roll, Pitch, Yaw).
    """
    import numpy as np

    A = df['A'].values
    B = df['B'].values
    C = df['C'].values
    D = df['D'].values

    # LAT from 'e and 'f (average)
    lat_cols = [c for c in df.columns if c in ["'e", "'f"]]
    if lat_cols:
        LAT = np.mean([df[c].values for c in lat_cols], axis=0)
    else:
        LAT = np.zeros(len(df))

    # SI from 'a, 'c, 'b (average)
    si_cols = [c for c in df.columns if c in ["'a", "'c", "'b"]]
    if si_cols:
        SI = np.mean([df[c].values for c in si_cols], axis=0)
    else:
        SI = np.zeros(len(df))

    # Read platform dimensions from settings, default to 100.0
    try:
        lat_dim = float(self.input_plat_lat.text().strip())
    except Exception:
        lat_dim = 100.0
    try:
        si_dim = float(self.input_plat_si.text().strip())
    except Exception:
        si_dim = 100.0
    try:
        off_ap = float(self.input_offset_ap.text().strip())
    except Exception:
        off_ap = 0.0

    # Pitch: D - A = si_dim * sin(p), where p = -pitch_rad
    sin_p = np.clip((D - A) / si_dim, -1.0, 1.0)
    p_rad = np.arcsin(sin_p)
    Pitch = -np.degrees(p_rad)

    # Roll: A - B = lat_dim * sin(roll) * cos(p)
    cos_p = np.cos(p_rad)
    cos_p_safe = np.where(np.abs(cos_p) < 1e-10, 1.0, cos_p)
    sin_r = np.clip((A - B) / (lat_dim * cos_p_safe), -1.0, 1.0)
    Roll = np.degrees(np.arcsin(sin_r))

    # AP: mean of actuators, corrected for rotation center offset
    cos_r = np.cos(np.radians(Roll))
    AP = (A + B + C + D) / 4.0 - off_ap * (1.0 - cos_r * cos_p)

    # Yaw = 0 (not recoverable from actuator heights)
    Yaw = np.zeros(len(df))

    result = pd.DataFrame({
        'timestamp': df['timestamp'].values,
        'time': df['time'].values,
        'LAT': LAT,
        'SI': SI,
        'AP': AP,
        'Roll': Roll,
        'Pitch': Pitch,
        'Yaw': Yaw,
        'Command': df['Command'].values
    })
    return result


def import_gcode_from_string(self, gcode_content, progress_dialog=None, progress_offset=0):
    """
    Parses GCODE content from a string and populates the planning workspace.
    """
    from PySide6.QtWidgets import QMessageBox
    from PySide6.QtCore import Qt, QCoreApplication
    import pandas as pd
    import numpy as np
    import re
    import time
    
    # Split content by lines
    lines = gcode_content.splitlines()
    num_lines = len(lines)
    if num_lines == 0:
        QMessageBox.warning(self, "Import Warning", "Downloaded G-code content is empty.")
        return

    # If progress dialog is provided, configure it
    progress = progress_dialog
    if progress is None:
        from PySide6.QtWidgets import QProgressDialog
        progress = QProgressDialog("Loading G-code...", "Cancel", 0, num_lines, self)
        progress.setWindowTitle("Importing G-code")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumWidth(550)
        progress.setMinimumHeight(180)
        progress.setStyleSheet("""
            QProgressDialog {
                font-size: 18px;
                font-weight: bold;
            }
            QLabel {
                font-size: 18px;
                min-height: 40px;
            }
            QProgressBar {
                text-align: center;
                font-size: 18px;
                font-weight: bold;
                height: 35px;
                border-radius: 4px;
            }
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                min-width: 120px;
                min-height: 45px;
                border-radius: 4px;
            }
        """)
        progress.setValue(0)
        progress.show()
        QCoreApplication.processEvents()

    pattern = re.compile(r"('?[a-zA-Z])([-+]?\d*\.\d+|\d+)")
    data_rows = []
    current_commands = []
    cancelled = False

    current_time = 0.0
    current_dwell = 0.0
    current_feedrate = 1000.0
    last_vals = {}

    for line_idx, line in enumerate(lines):
        if line_idx % 500 == 0:
            if progress_dialog is not None:
                progress.setValue(progress_offset + int((line_idx / num_lines) * 100))
            else:
                progress.setValue(line_idx)
            QCoreApplication.processEvents()
            if progress.wasCanceled():
                cancelled = True
                break

        line = line.strip()
        if not line or line.startswith(';'):
            continue
        
        if line.startswith('G1'):
            row_data = {}
            matches = pattern.findall(line)
            for axis, val in matches:
                if axis == 'F':
                    current_feedrate = float(val)
                elif axis != 'G':
                    row_data[axis] = float(val)
            
            # Calculate distance from last position to compute dt
            dist_sq = 0.0
            has_movement = False
            for axis, val in row_data.items():
                prev_val = last_vals.get(axis, None)
                if prev_val is not None:
                    diff = val - prev_val
                    dist_sq += diff * diff
                    has_movement = True
            
            dist = np.sqrt(dist_sq) if has_movement else 0.0
            dt = (dist * 60.0) / current_feedrate if (current_feedrate > 0.0 and dist > 0.0) else 0.0
            
            current_time += dt
            
            for axis, val in row_data.items():
                last_vals[axis] = val
                
            for axis, val in last_vals.items():
                if axis not in row_data:
                    row_data[axis] = val
            
            row_data['time'] = current_time
            row_data['timestamp'] = current_time * 1000.0
            
            if current_commands:
                row_data['Command'] = " ; ".join(current_commands)
                current_commands = []
            else:
                row_data['Command'] = ""
            
            data_rows.append(row_data)
        elif line.startswith('G4'):
            p_match = re.search(r'[pP](\d+)', line)
            if p_match:
                ms = float(p_match.group(1))
                dwell_sec = ms / 1000.0
                current_time += dwell_sec
                if last_vals:
                    dwell_row = {axis: val for axis, val in last_vals.items()}
                    dwell_row['time'] = current_time
                    dwell_row['timestamp'] = current_time * 1000.0
                    dwell_row['Command'] = ""
                    data_rows.append(dwell_row)
        elif line.startswith('M'):
            current_commands.append(line)

    if cancelled:
        QMessageBox.information(self, "Import Cancelled", "G-code import was cancelled by the user.")
        return

    if not data_rows:
        QMessageBox.warning(self, "Import Warning", "No G1 movement commands found in the G-code content.")
        return

    df = pd.DataFrame(data_rows)
    for col in df.columns:
        if col not in ['Command', 'time', 'timestamp']:
            df[col] = df[col].ffill().bfill().fillna(0.0)

    # Resample onto a uniform 10ms grid
    t_max = df['time'].max()
    if t_max > 0.0:
        t_grid = np.arange(0.0, t_max + 0.005, 0.01)
        resampled_data = {
            'timestamp': t_grid * 1000.0,
            'time': t_grid
        }
        exclude_cols = {'timestamp', 'time', 'Command'}
        axis_cols_raw = [c for c in df.columns if c not in exclude_cols]
        for c in axis_cols_raw:
            resampled_data[c] = np.interp(t_grid, df['time'].values, df[c].values)
        resampled_data['Command'] = [""] * len(t_grid)

        if 'Command' in df.columns:
            for idx, row in df.iterrows():
                cmd = str(row['Command']).strip()
                if cmd:
                    t_val = row['time']
                    grid_idx = np.argmin(np.abs(t_grid - t_val))
                    resampled_data['Command'][grid_idx] = cmd

        df = pd.DataFrame(resampled_data)

    # Ensure time and timestamp are the first columns
    cols = ['timestamp', 'time'] + [col for col in df.columns if col not in ['timestamp', 'time']]
    df = df[cols]

    exclude_cols = {'timestamp', 'time', 'Command'}
    axis_cols = sorted(col for col in df.columns if col not in exclude_cols)

    if set(axis_cols) == {'X', 'Y', 'Z'}:
        device = "Lung Phantom"
        self.dfEdit_lung_phantom = df
        self.dfEdit = self.dfEdit_lung_phantom
    elif 'A' in axis_cols and 'B' in axis_cols and 'C' in axis_cols and 'D' in axis_cols:
        device = "Motion Platform"
        df = _reverse_motion_platform_kinematics(self, df)
        self.dfEdit_motion_platform = df
        self.dfEdit = self.dfEdit_motion_platform
        axis_cols = ['LAT', 'SI', 'AP', 'Roll', 'Pitch', 'Yaw']
    else:
        device = "Other"
        self.dfEdit_other = df
        self.dfEdit = self.dfEdit_other

    self.combo_device.blockSignals(True)
    self.combo_device.setCurrentText(device)
    self.combo_device.blockSignals(False)

    if hasattr(self, 'combo_settings_device'):
        self.combo_settings_device.blockSignals(True)
        self.combo_settings_device.setCurrentText(device)
        self.combo_settings_device.blockSignals(False)
    if hasattr(self, 'settings_stack'):
        if device == "Lung Phantom":
            self.settings_stack.setCurrentIndex(0)
        elif device == "Motion Platform":
            self.settings_stack.setCurrentIndex(1)
        else:
            self.settings_stack.setCurrentIndex(2)

    self.combo_axis.clear()
    self.combo_axis.addItems(axis_cols)
    self.curve_origin = 'create'

    # Switch to Planning Tab before loading table to update UI context
    self.tabModules.setCurrentIndex(3)  # Index 3 is Planning Tab
    QCoreApplication.processEvents()

    if progress_dialog is not None:
        progress.setValue(progress_offset + 100)
        QCoreApplication.processEvents()

    # Re-scale progress range to cover table load
    if progress_dialog is not None:
        progress.setMaximum(progress_offset + 100 + n_points)
        loadTable_create(self, self.dfEdit, progress=progress, start_val=progress_offset + 100)
    else:
        progress.setMaximum(num_lines + n_points)
        loadTable_create(self, self.dfEdit, progress=progress, start_val=num_lines)

    if progress.wasCanceled():
        QMessageBox.information(self, "Import Cancelled", "G-code import was cancelled by the user.")
        return

    rebuild_axis_checkboxes(self, axis_cols)
    trigger_plot_update(self)

    progress.setLabelText("Done!")
    if progress_dialog is not None:
        progress.setValue(progress_offset + 100 + n_points)
    else:
        progress.setValue(num_lines + n_points)
    QCoreApplication.processEvents()
    time.sleep(0.8)
    progress.close()


def import_gcode_action(self):
    """
    Imports a GCODE file, parses its axes coordinates and commands,
    automatically detects device type, and populates the planning workspace.
    """
    from PySide6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog
    from PySide6.QtCore import Qt, QCoreApplication
    import pandas as pd
    import numpy as np
    import re

    file_path, _ = QFileDialog.getOpenFileName(self, "Open G-code File", "", "G-code Files (*.gcode *.g);;All Files (*)")
    if not file_path:
        return

    try:
        # Get total line count for progress bar
        with open(file_path, 'r') as f:
            num_lines = sum(1 for _ in f)

        if num_lines == 0:
            QMessageBox.warning(self, "Import Warning", "Selected G-code file is empty.")
            return

        # Initialize progress dialog (touchscreen-friendly sizing & styling)
        progress = QProgressDialog("Loading G-code file...", "Cancel", 0, num_lines, self)
        progress.setWindowTitle("Importing G-code")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)  # Show immediately
        progress.setMinimumWidth(550)
        progress.setMinimumHeight(180)
        progress.setStyleSheet("""
            QProgressDialog {
                font-size: 18px;
                font-weight: bold;
            }
            QLabel {
                font-size: 18px;
                min-height: 40px;
            }
            QProgressBar {
                text-align: center;
                font-size: 18px;
                font-weight: bold;
                height: 35px;
                border-radius: 4px;
            }
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                min-width: 120px;
                min-height: 45px;
                border-radius: 4px;
            }
        """)
        progress.setValue(0)

        # Pattern to match axis value: axis_name followed by float
        pattern = re.compile(r"('?[a-zA-Z])([-+]?\d*\.\d+|\d+)")
        
        data_rows = []
        current_commands = []
        cancelled = False
        
        current_time = 0.0
        current_dwell = 0.0
        current_feedrate = 1000.0
        last_vals = {}

        with open(file_path, 'r') as f:
            for line_idx, line in enumerate(f):
                # Update progress bar and process events to keep Cancel button responsive
                if line_idx % 500 == 0:
                    progress.setValue(line_idx)
                    QCoreApplication.processEvents()
                    if progress.wasCanceled():
                        cancelled = True
                        break

                line = line.strip()
                if not line or line.startswith(';'):
                    continue
                
                if line.startswith('G1'):
                    # Parse axes
                    row_data = {}
                    matches = pattern.findall(line)
                    for axis, val in matches:
                        if axis == 'F':
                            current_feedrate = float(val)
                        elif axis != 'G':  # Ignore G command type
                            row_data[axis] = float(val)
                    
                    # Calculate distance from last position to compute dt
                    dist_sq = 0.0
                    has_movement = False
                    for axis, val in row_data.items():
                        prev_val = last_vals.get(axis, None)
                        if prev_val is not None:
                            diff = val - prev_val
                            dist_sq += diff * diff
                            has_movement = True
                    
                    dist = np.sqrt(dist_sq) if has_movement else 0.0
                    dt = (dist * 60.0) / current_feedrate if (current_feedrate > 0.0 and dist > 0.0) else 0.0
                    
                    # Update current time
                    current_time += dt
                    
                    for axis, val in row_data.items():
                        last_vals[axis] = val
                        
                    for axis, val in last_vals.items():
                        if axis not in row_data:
                            row_data[axis] = val
                    
                    row_data['time'] = current_time
                    row_data['timestamp'] = current_time * 1000.0
                    
                    # Attach any accumulated commands to this row
                    if current_commands:
                        row_data['Command'] = " ; ".join(current_commands)
                        current_commands = []
                    else:
                        row_data['Command'] = ""
                    
                    data_rows.append(row_data)
                elif line.startswith('G4'):
                    p_match = re.search(r'[pP](\d+)', line)
                    if p_match:
                        ms = float(p_match.group(1))
                        dwell_sec = ms / 1000.0
                        current_time += dwell_sec
                        if last_vals:
                            dwell_row = {axis: val for axis, val in last_vals.items()}
                            dwell_row['time'] = current_time
                            dwell_row['timestamp'] = current_time * 1000.0
                            dwell_row['Command'] = ""
                            data_rows.append(dwell_row)
                elif line.startswith('M'):
                    # Store command to attach to the next G1 row
                    current_commands.append(line)

        if cancelled:
            QMessageBox.information(self, "Import Cancelled", "G-code import was cancelled by the user.")
            return

        if not data_rows:
            QMessageBox.warning(self, "Import Warning", "No G1 movement commands found in the selected G-code file.")
            return
            
        # Reconstruct DataFrame
        df = pd.DataFrame(data_rows)
        
        # Fill missing values in axes
        for col in df.columns:
            if col not in ['Command', 'time', 'timestamp']:
                df[col] = df[col].ffill().bfill().fillna(0.0)

        # Resample onto a uniform 10ms grid
        t_max = df['time'].max()
        if t_max > 0.0:
            t_grid = np.arange(0.0, t_max + 0.005, 0.01)
            resampled_data = {
                'timestamp': t_grid * 1000.0,
                'time': t_grid
            }
            exclude_cols = {'timestamp', 'time', 'Command'}
            axis_cols_raw = [c for c in df.columns if c not in exclude_cols]
            for c in axis_cols_raw:
                resampled_data[c] = np.interp(t_grid, df['time'].values, df[c].values)
            resampled_data['Command'] = [""] * len(t_grid)

            if 'Command' in df.columns:
                for idx, row in df.iterrows():
                    cmd = str(row['Command']).strip()
                    if cmd:
                        t_val = row['time']
                        grid_idx = np.argmin(np.abs(t_grid - t_val))
                        resampled_data['Command'][grid_idx] = cmd

            df = pd.DataFrame(resampled_data)
                
        # Ensure time and timestamp are the first columns
        cols = ['timestamp', 'time'] + [col for col in df.columns if col not in ['timestamp', 'time']]
        df = df[cols]

        n_points = len(df)

        # Set maximum for progress dialog to cover both parsing and table loading
        progress.setMaximum(num_lines + n_points)
        
        # Get active coordinate axes (excluding time, timestamp, Command)
        exclude_cols = {'timestamp', 'time', 'Command'}
        axis_cols = sorted(col for col in df.columns if col not in exclude_cols)
        
        # Automatically detect device type
        if set(axis_cols) == {'X', 'Y', 'Z'}:
            device = "Lung Phantom"
            self.dfEdit_lung_phantom = df
            self.dfEdit = self.dfEdit_lung_phantom
        elif 'A' in axis_cols and 'B' in axis_cols and 'C' in axis_cols and 'D' in axis_cols:
            device = "Motion Platform"
            df = _reverse_motion_platform_kinematics(self, df)
            self.dfEdit_motion_platform = df
            self.dfEdit = self.dfEdit_motion_platform
            axis_cols = ['LAT', 'SI', 'AP', 'Roll', 'Pitch', 'Yaw']
        else:
            device = "Other"
            self.dfEdit_other = df
            self.dfEdit = self.dfEdit_other
            
        # Block combo box signals to avoid triggering initialization while setting texts
        self.combo_device.blockSignals(True)
        self.combo_device.setCurrentText(device)
        self.combo_device.blockSignals(False)
        
        # Update settings view index
        if hasattr(self, 'combo_settings_device'):
            self.combo_settings_device.blockSignals(True)
            self.combo_settings_device.setCurrentText(device)
            self.combo_settings_device.blockSignals(False)
        if hasattr(self, 'settings_stack'):
            if device == "Lung Phantom":
                self.settings_stack.setCurrentIndex(0)
            elif device == "Motion Platform":
                self.settings_stack.setCurrentIndex(1)
            else:
                self.settings_stack.setCurrentIndex(2)

        # Refresh axis dropdown list (combo_axis)
        self.combo_axis.clear()
        self.combo_axis.addItems(axis_cols)
        
        self.curve_origin = 'create'
        
        # Reload table (with progress reporting)
        loadTable_create(self, self.dfEdit, progress=progress, start_val=num_lines)
        
        if progress.wasCanceled():
            QMessageBox.information(self, "Import Cancelled", "G-code import was cancelled by the user.")
            return

        # Rebuild checkboxes
        rebuild_axis_checkboxes(self, axis_cols)
        
        # Trigger plot update
        trigger_plot_update(self)
        
        # Finalize progress bar to 100% and show "Done!"
        progress.setLabelText("Done!")
        progress.setValue(num_lines + n_points)
        QCoreApplication.processEvents()
        import time
        time.sleep(0.8)
        progress.close()
        
    except Exception as e:
        QMessageBox.critical(self, "Error", f"Failed to import G-code:\n{str(e)}")