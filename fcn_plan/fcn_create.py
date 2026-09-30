# Import necessary libraries and modules
import numpy as np
import pandas as pd
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtWidgets import (
    QTableWidgetItem, QVBoxLayout, QHBoxLayout, QGridLayout, QWidget, QDialog, QListWidget,
    QScrollArea, QGroupBox, QLabel, QPushButton, QCheckBox, QRadioButton, QDoubleSpinBox, QMessageBox,
    QSpinBox, QSlider, QComboBox
)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar


def compute_motion_platform_actuators(self, df):
    """Computes individual actuator columns (A, B, C, D, 'a, 'c, 'e, 'f) for a Motion Platform DataFrame."""
    if df is None or len(df) == 0:
        return df

    df = df.copy()

    # Ensure degrees of freedom exist
    for col in ["LAT", "SI", "AP", "Roll", "Pitch", "Yaw"]:
        if col not in df.columns:
            df[col] = 0.0

    # Retrieve max limits from settings (or fallback to default 40.0)
    max_lim_lat = getattr(self, 'settings_max_lim_lat', None)
    max_lim_si = getattr(self, 'settings_max_lim_si', None)
    max_lim_ap = getattr(self, 'settings_max_lim_ap', None)

    lim_lat = max_lim_lat.value() if max_lim_lat else 40.0
    lim_si = max_lim_si.value() if max_lim_si else 40.0
    lim_ap = max_lim_ap.value() if max_lim_ap else 40.0

    lat_vals = df["LAT"].values
    si_vals = df["SI"].values
    ap_vals = df["AP"].values
    roll_vals = df["Roll"].values
    pitch_vals = df["Pitch"].values
    yaw_vals = df["Yaw"].values

    # Read platform offset AP, LAT, SI
    input_ap = getattr(self, 'input_offset_ap', None) or getattr(self, 'input_offset_ap_plan', None)
    try:
        off_ap = float(input_ap.text().strip()) if input_ap and input_ap.text().strip() else 0.0
    except Exception:
        off_ap = 0.0

    input_lat = getattr(self, 'input_offset_lat', None) or getattr(self, 'input_offset_lat_plan', None)
    try:
        off_lat = float(input_lat.text().strip()) if input_lat and input_lat.text().strip() else 0.0
    except Exception:
        off_lat = 0.0

    input_si = getattr(self, 'input_offset_si', None) or getattr(self, 'input_offset_si_plan', None)
    try:
        off_si = float(input_si.text().strip()) if input_si and input_si.text().strip() else 0.0
    except Exception:
        off_si = 0.0

    # Height above pivot for sway compensation (governed strictly by Offset AP field)
    roll_rad = np.radians(roll_vals)
    pitch_rad = np.radians(pitch_vals)

    lat_eff = off_lat + lat_vals + off_ap * np.sin(roll_rad)
    si_eff = off_si + si_vals + off_ap * np.sin(pitch_rad)

    df["LAT"] = np.clip(lat_eff, 0.0, lim_lat)
    df["SI"] = np.clip(si_eff, 0.0, lim_si)
    df["'e"] = df["LAT"]
    df["'f"] = df["LAT"]
    df["'a"] = df["SI"]
    df["'c"] = df["SI"]

    # Read platform dimensions
    try:
        lat_dim = float(self.input_plat_lat.text().strip()) if hasattr(self, 'input_plat_lat') and self.input_plat_lat else 100.0
        if lat_dim <= 0.0: lat_dim = 100.0
    except Exception:
        lat_dim = 100.0

    try:
        si_dim = float(self.input_plat_si.text().strip()) if hasattr(self, 'input_plat_si') and self.input_plat_si else 100.0
        if si_dim <= 0.0: si_dim = 100.0
    except Exception:
        si_dim = 100.0

    support_points = {
        'A': (-lat_dim / 2.0, -si_dim / 2.0, 0.0),
        'B': (lat_dim / 2.0, -si_dim / 2.0, 0.0),
        'C': (lat_dim / 2.0, si_dim / 2.0, 0.0),
        'D': (-lat_dim / 2.0, si_dim / 2.0, 0.0)
    }

    n = len(df)
    A_arr = np.zeros(n)
    B_arr = np.zeros(n)
    C_arr = np.zeros(n)
    D_arr = np.zeros(n)

    for i in range(n):
        r = np.radians(roll_vals[i])
        p = -np.radians(pitch_vals[i])
        y = np.radians(yaw_vals[i])

        cos_r, sin_r = np.cos(r), np.sin(r)
        cos_p, sin_p = np.cos(p), np.sin(p)
        cos_y, sin_y = np.cos(y), np.sin(y)

        xc, yc, zc = off_lat, off_si, off_ap

        target_z = {}
        for name, (px, py, pz) in support_points.items():
            x1 = px - xc
            y1 = py - yc
            z1 = pz - zc

            x2 = cos_y * x1 - sin_y * y1
            y2 = sin_y * x1 + cos_y * y1
            z2 = z1

            x3 = x2 * cos_r + z2 * sin_r
            y3 = y2
            z3 = -x2 * sin_r + z2 * cos_r

            x4 = x3
            y4 = y3 * cos_p - z3 * sin_p
            z4 = y3 * sin_p + z3 * cos_p

            target_z[name] = max(0.0, min(lim_ap, z4 + zc + ap_vals[i]))

        A_arr[i] = target_z['A']
        B_arr[i] = target_z['B']
        C_arr[i] = target_z['C']
        D_arr[i] = target_z['D']

    df["A"] = A_arr
    df["B"] = B_arr
    df["C"] = C_arr
    df["D"] = D_arr

    # Recompute achievable Roll, Pitch, and AP constrained by physical actuator limits [0.0, lim_ap]
    sin_p = np.clip(np.nan_to_num((D_arr - A_arr) / si_dim, nan=0.0), -1.0, 1.0)
    p_rad = np.arcsin(sin_p)
    df["Pitch"] = -np.degrees(p_rad)

    cos_p = np.cos(p_rad)
    cos_p_safe = np.where(np.abs(cos_p) < 1e-10, 1.0, cos_p)
    sin_r = np.clip(np.nan_to_num((A_arr - B_arr) / (lat_dim * cos_p_safe), nan=0.0), -1.0, 1.0)
    df["Roll"] = np.degrees(np.arcsin(sin_r))

    cos_r = np.cos(np.radians(df["Roll"].values))
    df["AP"] = (A_arr + B_arr + C_arr + D_arr) / 4.0 - off_ap * (1.0 - cos_r * cos_p)

    return df


def compute_kinematics(dataframe, pos_cols):
    """
    Computes velocity (mm/s or deg/s) and acceleration (mm/s² or deg/s²)
    for each position column using np.gradient on the full-resolution time array.
    Returns:
        vel_dict: {col: vel_array}
        acc_dict: {col: acc_array}
    """
    import numpy as np
    import pandas as pd

    t = dataframe['time'].values if 'time' in dataframe.columns else np.arange(len(dataframe)) * 0.01
    vel_dict = {}
    acc_dict = {}

    if len(t) < 2:
        for col in pos_cols:
            vel_dict[col] = np.zeros(len(t))
            acc_dict[col] = np.zeros(len(t))
        return vel_dict, acc_dict

    t_clean = np.array(t, dtype=float)
    if np.any(np.diff(t_clean) <= 0):
        t_clean = np.maximum.accumulate(t_clean)
        for i in range(1, len(t_clean)):
            if t_clean[i] <= t_clean[i - 1]:
                t_clean[i] = t_clean[i - 1] + 1e-4

    for col in pos_cols:
        vel_col_name = f"Vel. {col}"
        acc_col_name = f"Acc. {col}"
        if vel_col_name in dataframe.columns and acc_col_name in dataframe.columns:
            # Use precalculated kinematics (e.g. from imported log file or smoothing)
            vel_dict[col] = pd.to_numeric(dataframe[vel_col_name], errors='coerce').fillna(0.0).values
            acc_dict[col] = pd.to_numeric(dataframe[acc_col_name], errors='coerce').fillna(0.0).values
        elif col in dataframe.columns:
            pos = pd.to_numeric(dataframe[col], errors='coerce').fillna(0.0).values
            v = np.gradient(pos, t_clean)
            a = np.gradient(v, t_clean)
            vel_dict[col] = v
            acc_dict[col] = a
        else:
            vel_dict[col] = np.zeros(len(t))
            acc_dict[col] = np.zeros(len(t))

    return vel_dict, acc_dict


def trigger_plot_update(self):
    combo = getattr(self, 'combo_device', None)
    device = combo.currentText() if combo is not None else "Lung Phantom"
    if device == "Lung Phantom":
        all_axes = ["X", "Y", "Z"]
    elif device == "Motion Platform":
        all_axes = ["LAT", "SI", "AP", "Roll", "Pitch", "Yaw", "A", "B", "C", "D", "'a", "'c", "'e", "'f"]
    else:
        exclude_cols = {'timestamp', 'time', 'Command'}
        all_axes = [col for col in self.dfEdit.columns if col not in exclude_cols and not col.startswith(('Vel.', 'Acc.'))]

    checked_axes = []
    for col in all_axes:
        cb = getattr(self, 'create_axis_checkboxes', {}).get(col, None)
        if cb is not None and cb.isChecked():
            checked_axes.append(col)

    df_full = self.dfEdit
    if device == "Motion Platform":
        df_full = compute_motion_platform_actuators(self, df_full)

    # Compute high-resolution kinematics on full data first for exact numerical accuracy
    vel_full, acc_full = compute_kinematics(df_full, checked_axes)

    # Prepare data for plotting
    df_to_plot = df_full
    step = 1
    if len(df_to_plot) > 20000:
        step = max(1, len(df_to_plot) // 10000)
        df_to_plot = df_to_plot.iloc[::step]

    vel_plot = {col: vel_full[col][::step] if step > 1 else vel_full[col] for col in checked_axes}
    acc_plot = {col: acc_full[col][::step] if step > 1 else acc_full[col] for col in checked_axes}

    update_plot(self, df_to_plot, checked_axes, vel_plot=vel_plot, acc_plot=acc_plot)


def select_all_axes(self):
    for col, cb in getattr(self, 'create_axis_checkboxes', {}).items():
        cb.blockSignals(True)
        cb.setChecked(True)
        cb.blockSignals(False)
    trigger_plot_update(self)


def clear_all_axes(self):
    for col, cb in getattr(self, 'create_axis_checkboxes', {}).items():
        cb.blockSignals(True)
        cb.setChecked(False)
        cb.blockSignals(False)
    trigger_plot_update(self)


def sync_table_column_visibility(self):
    """Shows or hides table columns matching the state of Position, Velocity, and Acceleration checkboxes."""
    table = getattr(self, 'create_table_view', None)
    if table is None or table.columnCount() == 0:
        return

    show_pos = getattr(self, 'check_show_pos', None)
    show_vel = getattr(self, 'check_show_vel', None)
    show_acc = getattr(self, 'check_show_acc', None)

    is_pos = show_pos.isChecked() if show_pos is not None else True
    is_vel = show_vel.isChecked() if show_vel is not None else False
    is_acc = show_acc.isChecked() if show_acc is not None else False

    for col_idx in range(table.columnCount()):
        header_item = table.horizontalHeaderItem(col_idx)
        if not header_item:
            continue
        hdr = header_item.text()
        if hdr.startswith('Time') or hdr == 'Command':
            table.setColumnHidden(col_idx, False)
        elif hdr.startswith('Vel.'):
            table.setColumnHidden(col_idx, not is_vel)
        elif hdr.startswith('Acc.'):
            table.setColumnHidden(col_idx, not is_acc)
        else:
            table.setColumnHidden(col_idx, not is_pos)


def on_kinematic_checkbox_changed(self):
    """Handler for Position, Velocity, Acceleration checkbox state changes."""
    sync_table_column_visibility(self)
    trigger_plot_update(self)


def toggle_planning_table_visibility(self, visible):
    """
    Shows or hides the bottom-right planning table (create_table_view).
    When hidden (unselected), the bottom-left settings tabs widget extends all the way to the right.
    """
    self.planning_show_table = bool(visible)
    table = getattr(self, 'create_table_view', None)
    splitter = getattr(self, 'bottom_splitter', None)

    if splitter is None and table is not None and hasattr(table, 'parent'):
        from PySide6.QtWidgets import QSplitter
        p = table.parent()
        if isinstance(p, QSplitter):
            splitter = p
            self.bottom_splitter = splitter

    if not visible:
        if splitter is not None:
            sizes = splitter.sizes()
            if len(sizes) == 2 and sizes[1] > 0:
                self._last_bottom_splitter_sizes = sizes
            splitter.setSizes([1000, 0])
        if table is not None:
            table.setVisible(False)
    else:
        if table is not None:
            table.setVisible(True)
        if splitter is not None:
            saved_sizes = getattr(self, '_last_bottom_splitter_sizes', [280, 620])
            splitter.setSizes(saved_sizes)


def rebuild_axis_checkboxes(self, axes):
    from PySide6.QtWidgets import QCheckBox, QPushButton, QLabel
    if hasattr(self, 'create_plot_checkboxes_layout') and self.create_plot_checkboxes_layout is not None:
        layout_cb = self.create_plot_checkboxes_layout

        # Preserve previous kinematic checkbox selections
        prev_pos = getattr(self, 'check_show_pos', None)
        prev_vel = getattr(self, 'check_show_vel', None)
        prev_acc = getattr(self, 'check_show_acc', None)
        prev_table = getattr(self, 'check_show_table', None)
        pos_val = prev_pos.isChecked() if prev_pos is not None else True
        vel_val = prev_vel.isChecked() if prev_vel is not None else False
        acc_val = prev_acc.isChecked() if prev_acc is not None else False
        table_val = prev_table.isChecked() if prev_table is not None else getattr(self, 'planning_show_table', False)

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

        # Visual divider between axes and kinematic types
        lbl_div = QLabel(" | ", self.create_plot_checkboxes_widget)
        lbl_div.setStyleSheet("color: #90a4ae; font-size: 16px; font-weight: bold; margin-left: 6px; margin-right: 6px;")
        layout_cb.addWidget(lbl_div)

        # Kinematic type checkboxes: Position (continuous), Velocity (dashed), Acceleration (point)
        self.check_show_pos = QCheckBox("Position (—)", self.create_plot_checkboxes_widget)
        self.check_show_pos.setChecked(pos_val)
        self.check_show_pos.setStyleSheet("font-weight: bold; font-size: 14px; color: #1565c0; margin-right: 6px;")
        self.check_show_pos.setToolTip("Show Position as continuous solid line (—)")
        self.check_show_pos.stateChanged.connect(lambda state: on_kinematic_checkbox_changed(self))
        layout_cb.addWidget(self.check_show_pos)

        self.check_show_vel = QCheckBox("Velocity (--)", self.create_plot_checkboxes_widget)
        self.check_show_vel.setChecked(vel_val)
        self.check_show_vel.setStyleSheet("font-weight: bold; font-size: 14px; color: #0277bd; margin-right: 6px;")
        self.check_show_vel.setToolTip("Show Velocity as dashed line (--)")
        self.check_show_vel.stateChanged.connect(lambda state: on_kinematic_checkbox_changed(self))
        layout_cb.addWidget(self.check_show_vel)

        self.check_show_acc = QCheckBox("Acceleration (···)", self.create_plot_checkboxes_widget)
        self.check_show_acc.setChecked(acc_val)
        self.check_show_acc.setStyleSheet("font-weight: bold; font-size: 14px; color: #c2185b; margin-right: 12px;")
        self.check_show_acc.setToolTip("Show Acceleration as point/dotted line (···)")
        self.check_show_acc.stateChanged.connect(lambda state: on_kinematic_checkbox_changed(self))
        layout_cb.addWidget(self.check_show_acc)
        
        layout_cb.addStretch()

        # Add Select All and Clear All buttons on the right side
        self.btn_select_all_axes = QPushButton("Select All", self.create_plot_checkboxes_widget)
        self.btn_select_all_axes.setMinimumHeight(35)
        self.btn_select_all_axes.setStyleSheet("""
            QPushButton {
                background-color: #455a64;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding-left: 10px;
                padding-right: 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #37474f;
            }
        """)
        self.btn_select_all_axes.clicked.connect(lambda: select_all_axes(self))
        layout_cb.addWidget(self.btn_select_all_axes)

        self.btn_clear_all_axes = QPushButton("Clear All", self.create_plot_checkboxes_widget)
        self.btn_clear_all_axes.setMinimumHeight(35)
        self.btn_clear_all_axes.setStyleSheet("""
            QPushButton {
                background-color: #78909c;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding-left: 10px;
                padding-right: 10px;
                border-radius: 4px;
                margin-left: 5px;
                margin-right: 15px;
            }
            QPushButton:hover {
                background-color: #546e7a;
            }
        """)
        self.btn_clear_all_axes.clicked.connect(lambda: clear_all_axes(self))
        layout_cb.addWidget(self.btn_clear_all_axes)

        # Add Show Table checkbox on the left of Export GCODE button
        self.check_show_table = QCheckBox("Show Table", self.create_plot_checkboxes_widget)
        self.check_show_table.setChecked(table_val)
        self.check_show_table.setStyleSheet("font-weight: bold; font-size: 14px; color: #0d47a1; margin-right: 15px;")
        self.check_show_table.toggled.connect(lambda checked: toggle_planning_table_visibility(self, checked))
        layout_cb.addWidget(self.check_show_table)
        toggle_planning_table_visibility(self, table_val)

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
        self.dfEdit = compute_motion_platform_actuators(self, self.dfEdit)
        self.dfEdit_motion_platform = self.dfEdit
        axes = ["LAT", "SI", "AP", "Roll", "Pitch", "Yaw", "A", "B", "C", "D", "'a", "'c", "'e", "'f"]
    else:
        self.dfEdit = self.dfEdit_other
        exclude_cols = {'timestamp', 'time', 'Command'}
        axes = [col for col in self.dfEdit.columns if col not in exclude_cols and not col.startswith(('Vel.', 'Acc.'))]

    self.curve_origin = 'create'

    # Load table
    loadTable_create(self, self.dfEdit)

    # Rebuild checkboxes below the graph
    rebuild_axis_checkboxes(self, axes)

    # Plot initially showing all axes
    update_plot(self, self.dfEdit, axes)


def loadTable_create(self, dataframe, progress=None, start_val=0):
    if not hasattr(self, 'create_table_view') or self.create_table_view is None:
        return

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

    # Determine position columns for current device
    device = getattr(self, 'combo_device', None)
    device_name = device.currentText() if device else "Lung Phantom"
    if device_name == "Lung Phantom":
        pos_cols = [c for c in ['X', 'Y', 'Z'] if c in dataframe.columns]
    elif device_name == "Motion Platform":
        pos_cols = [c for c in ['LAT', 'SI', 'AP', 'Roll', 'Pitch', 'Yaw'] if c in dataframe.columns]
    else:
        exclude_cols = {'timestamp', 'time', 'Command'}
        pos_cols = [c for c in dataframe.columns if c not in exclude_cols and not c.startswith(('Vel.', 'Acc.'))]

    # Compute high-resolution kinematics on full data
    vel_dict, acc_dict = compute_kinematics(dataframe, pos_cols)
    
    # Compute downsampling step to target ~0.1s resolution in visual interface
    step = 1
    if dataframe.shape[0] > 1:
        dt = dataframe['time'].iat[1] - dataframe['time'].iat[0]
        if dt > 0:
            target_dt = max(0.1, dataframe['time'].max() / 5000.0)
            step = max(1, int(round(target_dt / dt)))
            
    # Always include indices that are multiples of step, plus any rows containing active commands
    display_indices = list(range(0, dataframe.shape[0], step))
    if 'Command' in dataframe.columns:
        cmd_indices = dataframe[dataframe['Command'].astype(str).str.strip() != ''].index.tolist()
        display_indices = sorted(list(set(display_indices + cmd_indices)))
    else:
        display_indices = sorted(list(set(display_indices)))

    # Assemble display columns in requested order:
    # time, then pos_cols, then vel_cols, then acc_cols, extra actuator cols, Command
    vel_cols = [f"Vel. {c}" for c in pos_cols]
    acc_cols = [f"Acc. {c}" for c in pos_cols]
    handled = set(['timestamp', 'time', 'Command'] + pos_cols)
    extra_cols = [c for c in dataframe.columns if c not in handled and not c.startswith(('Vel.', 'Acc.'))]

    display_columns = ['time'] + pos_cols + vel_cols + acc_cols + extra_cols
    if 'Command' in dataframe.columns:
        display_columns.append('Command')

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
        'Vel. X': 'Vel. X (mm/s)',
        'Vel. Y': 'Vel. Y (mm/s)',
        'Vel. Z': 'Vel. Z (mm/s)',
        'Vel. LAT': 'Vel. LAT (mm/s)',
        'Vel. SI': 'Vel. SI (mm/s)',
        'Vel. AP': 'Vel. AP (mm/s)',
        'Vel. Roll': 'Vel. Roll (deg/s)',
        'Vel. Pitch': 'Vel. Pitch (deg/s)',
        'Vel. Yaw': 'Vel. Yaw (deg/s)',
        'Vel. Amplitude': 'Vel. Amplitude (mm/s)',
        'Acc. X': 'Acc. X (mm/s²)',
        'Acc. Y': 'Acc. Y (mm/s²)',
        'Acc. Z': 'Acc. Z (mm/s²)',
        'Acc. LAT': 'Acc. LAT (mm/s²)',
        'Acc. SI': 'Acc. SI (mm/s²)',
        'Acc. AP': 'Acc. AP (mm/s²)',
        'Acc. Roll': 'Acc. Roll (deg/s²)',
        'Acc. Pitch': 'Acc. Pitch (deg/s²)',
        'Acc. Yaw': 'Acc. Yaw (deg/s²)',
        'Acc. Amplitude': 'Acc. Amplitude (mm/s²)',
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
            is_derived = False
            if col_name.startswith('Vel. '):
                base_axis = col_name[5:]
                val = vel_dict.get(base_axis, np.zeros(len(dataframe)))[bg_row]
                is_derived = True
            elif col_name.startswith('Acc. '):
                base_axis = col_name[5:]
                val = acc_dict.get(base_axis, np.zeros(len(dataframe)))[bg_row]
                is_derived = True
            else:
                val = dataframe.iat[bg_row, dataframe.columns.get_loc(col_name)]

            try:
                float_val = float(val)
                display_text = f"{float_val:.2f}"
                item = QTableWidgetItem(display_text)
                item.setData(Qt.UserRole, float_val)
            except (ValueError, TypeError):
                item = QTableWidgetItem(str(val))
                item.setData(Qt.UserRole, val)
                
            item.setData(Qt.UserRole + 1, bg_row)
            if is_derived:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

            if is_pause:
                item.setBackground(QColor("#ffcdd2"))
            elif is_user_wait:
                item.setBackground(QColor("#fff9c4"))
                
            table.setItem(row_idx, col, item)
            
    header = table.horizontalHeader()
    for col in range(table.columnCount() - 1):
        header.setSectionResizeMode(col, QHeaderView.Interactive)
        table.setColumnWidth(col, 120)
    if table.columnCount() > 0:
        header.setSectionResizeMode(table.columnCount() - 1, QHeaderView.Stretch)

    sync_table_column_visibility(self)

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

    # Derived velocity and acceleration columns are not directly editable
    if header_text.startswith(('Vel.', 'Acc.')):
        return
    
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
            if isinstance(new_val, (int, float)) and col_name not in ['time', 'timestamp', 'Roll', 'Pitch', 'Yaw']:
                if new_val < 0.0:
                    new_val = 0.0
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
        self.dfEdit = compute_motion_platform_actuators(self, self.dfEdit)
        self.dfEdit_motion_platform = self.dfEdit
    else:
        self.dfEdit_other = self.dfEdit


def update_undo_button_state(self):
    """Updates the Planning Curve tab Undo button enabled status based on whether an undo state is available."""
    btn = getattr(self, 'button_undo_curve', None)
    if btn is not None:
        has_undo = bool(getattr(self, '_curve_undo_stack', []))
        btn.setEnabled(has_undo)
        btn.setText("Undo")
        if has_undo:
            btn.setToolTip("Revert last curve action")
        else:
            btn.setToolTip("No action to undo")


def push_curve_state(self):
    """
    Saves a snapshot of the current curve state for single-step undo.
    Allows the user to go back one step.
    """
    if not hasattr(self, 'dfEdit') or self.dfEdit is None:
        return

    snapshot = {
        'df': self.dfEdit.copy(deep=True),
        'device': self.combo_device.currentText() if hasattr(self, 'combo_device') else None,
        'origin': getattr(self, 'curve_origin', 'create'),
    }

    # Store strictly the single previous state
    self._curve_undo_stack = [snapshot]

    update_undo_button_state(self)


def undo_curve_action(self):
    """
    Restores the previous curve state from the undo snapshot.
    """
    if not hasattr(self, '_curve_undo_stack') or not self._curve_undo_stack:
        return

    snapshot = self._curve_undo_stack.pop()
    restored_df = snapshot['df']
    self.dfEdit = restored_df.copy(deep=True)
    self.curve_origin = snapshot.get('origin', 'create')

    device = snapshot.get('device') or (self.combo_device.currentText() if hasattr(self, 'combo_device') else "Lung Phantom")
    if hasattr(self, 'combo_device') and device and self.combo_device.currentText() != device:
        self.combo_device.blockSignals(True)
        self.combo_device.setCurrentText(device)
        self.combo_device.blockSignals(False)

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

    from PySide6.QtCore import QCoreApplication
    QCoreApplication.processEvents()

    update_undo_button_state(self)


def create_curve(self):
    """
    Applies/Adds a curve segment to the selected axes over the defined [t_start, t_end] interval,
    overwriting only that interval, keeping the rest of the column data intact,
    and expanding the dataframe range up to t_end if it goes past the current limits.
    If adding consecutive intervals (t_start > 0), checks previous position and calculates transit time
    at max_speed, shifting the segment in time to account for it.
    """
    if not hasattr(self, 'dfEdit') or self.dfEdit is None:
        initialize_default_curve_data(self)

    device = self.combo_device.currentText()
    
    selected_axes = []
    if hasattr(self, 'create_curve_axis_checkboxes'):
        for ax_name, cb in self.create_curve_axis_checkboxes.items():
            if cb.isChecked() and cb.isEnabled():
                selected_axes.append(ax_name)

    if not selected_axes and hasattr(self, 'combo_axis'):
        txt = self.combo_axis.currentText()
        if txt:
            selected_axes = [txt]

    if not selected_axes:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "No Axis Selected", "Please select at least one axis checkbox before adding a curve.")
        return

    push_curve_state(self)

    func_type = self.combo_func_type.currentText()
    amplitude = self.input_amplitude.value()
    period = self.input_period.value()
    phase_deg = self.input_phase.value()
    phase_rad = np.deg2rad(phase_deg)
    t_start = self.input_start_time.value()

    if func_type == "linear":
        t_end = t_start + period
        if hasattr(self, 'input_end_time'):
            self.input_end_time.blockSignals(True)
            self.input_end_time.setValue(round(t_end, 3))
            self.input_end_time.blockSignals(False)
    else:
        t_end = self.input_end_time.value()

    # Retrieve max speed setting (mm/s or deg/s) based on active device
    active_device = self.combo_device.currentText() if hasattr(self, 'combo_device') and self.combo_device else ""
    if active_device == "Lung Phantom":
        sb_speed = getattr(self, 'combo_phantom_max_speed', None) or getattr(self, 'settings_max_speed', None)
    elif active_device == "Motion Platform":
        sb_speed = getattr(self, 'combo_platform_max_speed', None) or getattr(self, 'settings_max_speed_plat', None)
    else:
        sb_speed = getattr(self, 'combo_platform_max_speed', None) or getattr(self, 'settings_max_speed_plat', None) or getattr(self, 'settings_max_speed', None)

    if sb_speed is not None:
        if hasattr(sb_speed, 'value') and callable(sb_speed.value):
            max_speed = float(sb_speed.value())
        elif hasattr(sb_speed, 'currentText'):
            try:
                max_speed = float(sb_speed.currentText())
            except (ValueError, TypeError):
                max_speed = 20.0
        else:
            max_speed = 20.0
    else:
        max_speed = 20.0

    if max_speed <= 0.0:
        max_speed = 20.0

    # Calculate starting values and max required shift time for consecutive intervals
    max_shift_dt = 0.0
    t_prev = 0.0
    has_prev = False
    prev_vals = {}
    val_starts = {}

    for selected_axis in selected_axes:
        if selected_axis in ["Roll", "Pitch", "Yaw"] and func_type != "linear":
            amp_offset = 0.0
        else:
            amp_offset = self.input_amp_offset.value() if hasattr(self, 'input_amp_offset') else 0.0

        if func_type == "sin":
            val_start = amplitude * np.sin(phase_rad) + amp_offset
        elif func_type in ["cos", "cos^1"]:
            val_start = amplitude * np.cos(phase_rad) + amp_offset
        elif func_type == "cos^2":
            val_start = amplitude * (np.cos(phase_rad / 2.0) ** 2) + amp_offset
        elif func_type == "cos^4":
            val_start = amplitude * (np.cos(phase_rad / 2.0) ** 4) + amp_offset
        elif func_type == "cos^6":
            val_start = amplitude * (np.cos(phase_rad / 2.0) ** 6) + amp_offset
        elif func_type == "constant":
            val_start = amplitude + amp_offset
        elif func_type == "linear":
            val_start = amplitude
        else:
            val_start = amplitude * np.sin(phase_rad) + amp_offset

        if val_start < 0.0 and selected_axis not in ["Roll", "Pitch", "Yaw"]:
            val_start = 0.0

        val_starts[selected_axis] = val_start

        if t_start > 0.0 and selected_axis in self.dfEdit.columns:
            times_prev = self.dfEdit['time'].values
            valid_indices = np.where(times_prev <= t_start)[0]
            if len(valid_indices) > 0:
                idx_prev = valid_indices[-1]
                t_prev = times_prev[idx_prev]
                val_prev = self.dfEdit.at[idx_prev, selected_axis]
                prev_vals[selected_axis] = val_prev
                has_prev = True

                dt_required = abs(val_start - val_prev) / max_speed
                dt_gap = t_start - t_prev
                shift_dt = max(0.0, dt_required - dt_gap)
                if shift_dt > max_shift_dt:
                    max_shift_dt = shift_dt

    if max_shift_dt > 0.0:
        t_start = round(t_start + max_shift_dt, 3)
        t_end = round(t_end + max_shift_dt, 3)

        if hasattr(self, 'input_start_time'):
            self.input_start_time.blockSignals(True)
            self.input_start_time.setValue(t_start)
            self.input_start_time.blockSignals(False)
        if hasattr(self, 'input_end_time'):
            self.input_end_time.blockSignals(True)
            self.input_end_time.setValue(t_end)
            self.input_end_time.blockSignals(False)

    # 1. Expand limits if t_end is greater than current maximum time in the dataframe
    t_max = self.dfEdit['time'].max()
    if t_end > t_max:
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
            exclude_cols = {'timestamp', 'time', 'Command'}
            all_axes = [col for col in self.dfEdit.columns if col not in exclude_cols and not col.startswith(('Vel.', 'Acc.'))]
            for col in all_axes:
                new_rows[col] = 0.0
            new_rows['Command'] = ""
            
            self.dfEdit = pd.concat([self.dfEdit, new_rows], ignore_index=True)

    if 'Command' not in self.dfEdit.columns:
        self.dfEdit['Command'] = ""

    # Apply calculations for each selected axis
    for selected_axis in selected_axes:
        val_start = val_starts[selected_axis]

        if selected_axis in ["Roll", "Pitch", "Yaw"] and func_type != "linear":
            amp_offset = 0.0
        else:
            amp_offset = self.input_amp_offset.value() if hasattr(self, 'input_amp_offset') else 0.0

        # 2. Interpolate transition interval at max speed if applicable
        if has_prev and selected_axis in prev_vals and t_start > t_prev and selected_axis in self.dfEdit.columns:
            val_prev = prev_vals[selected_axis]
            for idx, t_val in enumerate(self.dfEdit['time'].values):
                if t_prev <= t_val < t_start:
                    frac = (t_val - t_prev) / (t_start - t_prev)
                    interp_val = val_prev + frac * (val_start - val_prev)
                    if interp_val < 0.0 and selected_axis not in ["Roll", "Pitch", "Yaw"]:
                        interp_val = 0.0
                    self.dfEdit.at[idx, selected_axis] = interp_val

        # 3. Find indices where t_start <= t <= t_end and compute the values
        for idx, t_val in enumerate(self.dfEdit['time'].values):
            if t_start <= t_val <= t_end:
                t_rel = t_val - t_start
                if func_type == "sin":
                    val = amplitude * np.sin(2.0 * np.pi * t_rel / period + phase_rad) + amp_offset
                elif func_type in ["cos", "cos^1"]:
                    val = amplitude * np.cos(2.0 * np.pi * t_rel / period + phase_rad) + amp_offset
                elif func_type == "cos^2":
                    val = amplitude * (np.cos(np.pi * t_rel / period + phase_rad / 2.0) ** 2) + amp_offset
                elif func_type == "cos^4":
                    val = amplitude * (np.cos(np.pi * t_rel / period + phase_rad / 2.0) ** 4) + amp_offset
                elif func_type == "cos^6":
                    val = amplitude * (np.cos(np.pi * t_rel / period + phase_rad / 2.0) ** 6) + amp_offset
                elif func_type == "constant":
                    val = amplitude + amp_offset
                elif func_type == "linear":
                    if period > 0:
                        frac = t_rel / period
                        frac = min(max(frac, 0.0), 1.0)
                        val = amplitude + frac * (amp_offset - amplitude)
                    else:
                        val = amp_offset
                else:
                    val = amplitude * np.sin(2.0 * np.pi * t_rel / period + phase_rad) + amp_offset
                
                if val < 0.0 and selected_axis not in ["Roll", "Pitch", "Yaw"]:
                    val = 0.0

                if selected_axis in self.dfEdit.columns:
                    self.dfEdit.at[idx, selected_axis] = val

    cols_to_drop = [c for c in self.dfEdit.columns if c.startswith(('Vel.', 'Acc.'))]
    if cols_to_drop:
        self.dfEdit.drop(columns=cols_to_drop, inplace=True)

    # Save the reference back to the appropriate persistent dataframe
    if device == "Lung Phantom":
        self.dfEdit_lung_phantom = self.dfEdit
    elif device == "Motion Platform":
        self.dfEdit = compute_motion_platform_actuators(self, self.dfEdit)
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


def update_plot(self, dataframe, axes_list, vel_plot=None, acc_plot=None):
    """This function plots the created curves from the dataframe."""
    if not hasattr(self, 'create_plot_canvas_container') or self.create_plot_canvas_container is None:
        return
    container = self.create_plot_canvas_container
    if container.layout() is None:
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        container.setLayout(layout)

    # Initialize persistent Figure, Canvas, and Toolbar once
    if not hasattr(self, 'create_plot_canvas') or self.create_plot_canvas is None or self.create_plot_canvas.parent() != container:
        while container.layout().count():
            child = container.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.plot_fig = Figure()
        self.create_plot_ax = self.plot_fig.add_subplot(111)
        self.create_plot_canvas = FigureCanvas(self.plot_fig)
        self.create_plot_canvas.setStyleSheet("background-color:Transparent;")
        container.layout().addWidget(self.create_plot_canvas)

        self.create_plot_toolbar = NavigationToolbar(self.create_plot_canvas, container)
        self.create_plot_toolbar.setStyleSheet("background-color: #f5f5f5; border: none; font-weight: bold;")
        container.layout().addWidget(self.create_plot_toolbar)

    ax = self.create_plot_ax
    ax.clear()

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

    show_pos = getattr(self, 'check_show_pos', None)
    show_vel = getattr(self, 'check_show_vel', None)
    show_acc = getattr(self, 'check_show_acc', None)
    is_pos = show_pos.isChecked() if show_pos is not None else True
    is_vel = show_vel.isChecked() if show_vel is not None else False
    is_acc = show_acc.isChecked() if show_acc is not None else False

    if vel_plot is None or acc_plot is None:
        vel_plot, acc_plot = compute_kinematics(dataframe, axes_list)

    AXIS_COLORS = {
        'X': '#1976d2',      # Blue
        'Y': '#f57c00',      # Orange
        'Z': '#388e3c',      # Green
        'LAT': '#1976d2',    # Blue
        'SI': '#f57c00',     # Orange
        'AP': '#388e3c',     # Green
        'Roll': '#7b1fa2',   # Purple
        'Pitch': '#d32f2f',  # Red
        'Yaw': '#0097a7',    # Teal
        'A': '#5c6bc0',
        'B': '#26a69a',
        'C': '#ffa726',
        'D': '#ab47bc',
        "'a": "#8d6e63",
        "'c": "#78909c",
        "'e": "#5c6bc0",
        "'f": "#26a69a",
        'amplitude': '#1976d2'
    }

    t_data = dataframe["time"]
    num_kin_active = sum([is_pos, is_vel, is_acc])
    use_tags = num_kin_active > 1 or is_vel or is_acc

    for col in axes_list:
        if col in dataframe.columns:
            c = AXIS_COLORS.get(col, None)

            # 1. Position: continuous solid line ('-')
            if is_pos:
                lbl = f"{col} (Pos)" if use_tags else col
                kwargs = {'label': lbl, 'linestyle': '-', 'linewidth': 1.6}
                if c:
                    kwargs['color'] = c
                ax.plot(t_data, dataframe[col], **kwargs)

            # 2. Velocity: dashed line ('--')
            if is_vel and col in vel_plot:
                lbl = f"{col} (Vel)" if use_tags else col
                kwargs = {'label': lbl, 'linestyle': '--', 'linewidth': 1.6}
                if c:
                    kwargs['color'] = c
                ax.plot(t_data, vel_plot[col], **kwargs)

            # 3. Acceleration: point / dotted line (':')
            if is_acc and col in acc_plot:
                lbl = f"{col} (Acc)" if use_tags else col
                kwargs = {'label': lbl, 'linestyle': ':', 'linewidth': 1.8}
                if c:
                    kwargs['color'] = c
                ax.plot(t_data, acc_plot[col], **kwargs)

    # Draw vertical lines for pause/wait commands
    if 'Command' in dataframe.columns:
        for idx, cmd in enumerate(dataframe['Command'].values):
            if isinstance(cmd, str) and cmd.strip():
                t_val = dataframe['time'].values[idx]
                if 'sensor_wait.g' in cmd:
                    ax.axvline(x=t_val, color='#e53935', linestyle='--', linewidth=1.5, alpha=0.85)
                elif 'M226' in cmd:
                    ax.axvline(x=t_val, color='#fbc02d', linestyle='--', linewidth=1.5, alpha=0.85)

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc='upper right', fontsize=10, labelcolor='#333333')
    if len(t_data) > 0 and t_data.min() < t_data.max():
        ax.set_xlim(t_data.min(), t_data.max())
    ax.set_xlabel('Time (s)', fontsize=font_sz, fontweight='bold')

    y_labels = []
    if is_pos:
        y_labels.append("Pos (mm / deg)")
    if is_vel:
        y_labels.append("Vel (mm/s, deg/s)")
    if is_acc:
        y_labels.append("Acc (mm/s², deg/s²)")
    y_label_str = " | ".join(y_labels) if y_labels else "Amplitude (mm / deg)"
    ax.set_ylabel(y_label_str, fontsize=font_sz, fontweight='bold')
    ax.grid(True, linestyle=":", alpha=0.5, color="#888888")

    self.plot_fig.tight_layout()
    self.create_plot_canvas.draw()


from .fcn_import import addColumns, loadTable, open_import_motion_dialog


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

        # Retrieve speed, acc, jerk settings for Lung Phantom
        sb_speed = getattr(self, 'combo_phantom_max_speed', None) or getattr(self, 'settings_max_speed', None)
        speed_val = sb_speed.value() if (sb_speed and hasattr(sb_speed, 'value')) else (float(sb_speed.currentText()) if (sb_speed and hasattr(sb_speed, 'currentText')) else 50.0)

        sb_acc = getattr(self, 'combo_phantom_acc', None) or getattr(self, 'settings_acc_phantom', None)
        acc_val = sb_acc.value() if (sb_acc and hasattr(sb_acc, 'value')) else (float(sb_acc.currentText()) if (sb_acc and hasattr(sb_acc, 'currentText')) else 1000.0)

        sb_jerk = getattr(self, 'combo_phantom_jerk', None) or getattr(self, 'settings_jerk_phantom', None)
        jerk_val = sb_jerk.value() if (sb_jerk and hasattr(sb_jerk, 'value')) else (float(sb_jerk.currentText()) if (sb_jerk and hasattr(sb_jerk, 'currentText')) else 300.0)

        gcode_content, exceeds_limits = generate_gcode_string(
            device, t_orig, columns_data, max_limits,
            speed=speed_val, acc=acc_val, jerk=jerk_val
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

        # Retrieve speed, acc, jerk settings for Motion Platform
        sb_speed = getattr(self, 'combo_platform_max_speed', None) or getattr(self, 'settings_max_speed_plat', None)
        speed_val = sb_speed.value() if (sb_speed and hasattr(sb_speed, 'value')) else (float(sb_speed.currentText()) if (sb_speed and hasattr(sb_speed, 'currentText')) else 20.0)

        sb_acc = getattr(self, 'combo_platform_acc', None) or getattr(self, 'settings_acc_plat', None)
        acc_val = sb_acc.value() if (sb_acc and hasattr(sb_acc, 'value')) else (float(sb_acc.currentText()) if (sb_acc and hasattr(sb_acc, 'currentText')) else 500.0)

        sb_jerk = getattr(self, 'combo_platform_jerk', None) or getattr(self, 'settings_jerk_plat', None)
        jerk_val = sb_jerk.value() if (sb_jerk and hasattr(sb_jerk, 'value')) else (float(sb_jerk.currentText()) if (sb_jerk and hasattr(sb_jerk, 'currentText')) else 300.0)

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

        if lat_dim <= 0.0 or si_dim <= 0.0:
            QMessageBox.warning(
                self,
                "Platform Dimension Error",
                f"Platform LAT and SI dimensions must be greater than 0 mm (currently LAT: {lat_dim} mm, SI: {si_dim} mm).\n\nPlease set valid platform dimensions in the Control tab settings before exporting."
            )
            return None, None

        input_ap = getattr(self, 'input_offset_ap', None) or getattr(self, 'input_offset_ap_plan', None)
        if not input_ap or not input_ap.text().strip():
            QMessageBox.warning(self, "Export Error", "Offset AP input field is missing or empty.")
            return None, None
        try:
            off_ap = float(input_ap.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Export Error", f"Invalid offset AP value: '{input_ap.text()}'")
            return None, None

        input_lat = getattr(self, 'input_offset_lat', None) or getattr(self, 'input_offset_lat_plan', None)
        if not input_lat or not input_lat.text().strip():
            QMessageBox.warning(self, "Export Error", "Offset LAT input field is missing or empty.")
            return None, None
        try:
            off_lat = float(input_lat.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Export Error", f"Invalid offset LAT value: '{input_lat.text()}'")
            return None, None

        input_si = getattr(self, 'input_offset_si', None) or getattr(self, 'input_offset_si_plan', None)
        if not input_si or not input_si.text().strip():
            QMessageBox.warning(self, "Export Error", "Offset SI input field is missing or empty.")
            return None, None
        try:
            off_si = float(input_si.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Export Error", f"Invalid offset SI value: '{input_si.text()}'")
            return None, None

        axis_y_lo = "'c"

        gcode_content, exceeds_limits = generate_gcode_string(
            device, t_orig, columns_data, max_limits,
            lat_dim, si_dim, off_ap, off_lat, off_si, axis_y_lo,
            speed=speed_val, acc=acc_val, jerk=jerk_val
        )

    else: # Other
        exclude_cols = {'timestamp', 'time', 'Command'}
        axes_list = [col for col in self.dfEdit.columns if col not in exclude_cols and not col.startswith(('Vel.', 'Acc.'))]
        for col in axes_list:
            columns_data[col] = self.dfEdit[col].values

        max_lim_lat = getattr(self, 'settings_max_lim_lat', None)
        lim = max_lim_lat.value() if max_lim_lat else 40.0
        max_limits = [lim]

        sb_speed = getattr(self, 'combo_platform_max_speed', None) or getattr(self, 'combo_phantom_max_speed', None)
        speed_val = sb_speed.value() if (sb_speed and hasattr(sb_speed, 'value')) else (float(sb_speed.currentText()) if (sb_speed and hasattr(sb_speed, 'currentText')) else 20.0)

        sb_acc = getattr(self, 'combo_platform_acc', None) or getattr(self, 'combo_phantom_acc', None)
        acc_val = sb_acc.value() if (sb_acc and hasattr(sb_acc, 'value')) else (float(sb_acc.currentText()) if (sb_acc and hasattr(sb_acc, 'currentText')) else 500.0)

        sb_jerk = getattr(self, 'combo_platform_jerk', None) or getattr(self, 'combo_phantom_jerk', None)
        jerk_val = sb_jerk.value() if (sb_jerk and hasattr(sb_jerk, 'value')) else (float(sb_jerk.currentText()) if (sb_jerk and hasattr(sb_jerk, 'currentText')) else 300.0)

        gcode_content, exceeds_limits = generate_gcode_string(
            device, t_orig, columns_data, max_limits,
            speed=speed_val, acc=acc_val, jerk=jerk_val
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
    if hasattr(self, 'combo_axis') and self.combo_axis.currentText():
        selected_axis = self.combo_axis.currentText()
    elif hasattr(self, 'create_curve_axis_checkboxes'):
        checked = [a for a, cb in self.create_curve_axis_checkboxes.items() if cb.isChecked()]
        selected_axis = "_".join(checked) if checked else "axis"
    else:
        selected_axis = "axis"
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
    Generates G-code string from the active curve and uploads it directly to Duet SD card (0:/gcodes/).
    Writes G-code to a temp file, stops background polling, then uploads using the shared session
    (same code path as the Files tab upload_file).
    """
    from PySide6.QtWidgets import QMessageBox, QInputDialog, QProgressDialog, QWidget
    from PySide6.QtCore import Qt, QCoreApplication
    from fcn_monitor.fcn_duet import get_clean_duet_ip, get_shared_session
    import io
    import time

    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before uploading files.")
        return

    gcode_content, default_name = generate_planned_gcode(self)
    if not gcode_content:
        return

    # Prompt for target name on Duet
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

    file_data = gcode_content.encode('utf-8')

    # ── Stop background polling to prevent concurrent HTTP requests to Duet ──
    polling_was_active = False
    fast_was_active = False
    if hasattr(self, 'status_polling_timer') and self.status_polling_timer.isActive():
        self.status_polling_timer.stop()
        polling_was_active = True
    if hasattr(self, 'status_fast_timer') and self.status_fast_timer.isActive():
        self.status_fast_timer.stop()
        fast_was_active = True

    # Process pending events to flush any in-flight timer callbacks
    QCoreApplication.processEvents()
    # Small delay to let any active HTTP request on the shared session complete
    time.sleep(0.3)

    # Initialize progress dialog
    progress = QProgressDialog(f"Uploading '{filename}' to Duet...", "Cancel", 0, 100, parent_widget)
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

    def progress_callback(bytes_read, total):
        if progress.wasCanceled():
            raise Exception("Upload cancelled by user")
        percent = int((bytes_read / total) * 100) if total > 0 else 0
        progress.setValue(percent)
        QCoreApplication.processEvents()

    class ProgressIO(io.BytesIO):
        def __init__(self, data_bytes, callback):
            super().__init__(data_bytes)
            self.callback = callback
            self.total = len(data_bytes)
            self.read_bytes = 0

        def read(self, size=-1):
            chunk = super().read(size)
            self.read_bytes += len(chunk)
            self.callback(self.read_bytes, self.total)
            return chunk

    progress_io = ProgressIO(file_data, progress_callback)

    try:
        # Use the shared session — same code path as the Files tab upload_file
        session = get_shared_session()
        print(f"[UPLOAD DEBUG] Using shared session, uploading to {url} name={rrf_path}, data size={len(file_data)} bytes")
        response = session.post(url, params={'name': rrf_path}, data=progress_io, timeout=30)
        print(f"[UPLOAD DEBUG] Response status: {response.status_code}, body: {response.text[:200]}")
        response.raise_for_status()

        progress.setValue(100)
        QMessageBox.information(parent_widget, "Upload Successful", f"G-code '{filename}' uploaded successfully to Duet root gcodes folder!")
    except Exception as e:
        print(f"[UPLOAD DEBUG] Upload exception: {type(e).__name__}: {e}")
        progress.close()
        if "cancelled by user" in str(e):
            QMessageBox.information(parent_widget, "Upload Cancelled", "G-code upload was cancelled by the user.")
        else:
            QMessageBox.critical(parent_widget, "Upload Error", f"Failed to upload G-code to Duet:\n{str(e)}")
    finally:
        # Restart polling timers
        if polling_was_active and hasattr(self, 'status_polling_timer'):
            self.status_polling_timer.start()
        if fast_was_active and hasattr(self, 'status_fast_timer'):
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

    push_curve_state(self)

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

    push_curve_state(self)

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

    push_curve_state(self)

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

    push_curve_state(self)

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

    push_curve_state(self)

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
    Reverse-maps actuator G-code columns (A, B, C, D, 'e, 'f, 'a, 'c)
    back to Motion Platform DOFs (LAT, SI, AP, Roll, Pitch, Yaw).
    """
    import numpy as np

    max_lim_ap = getattr(self, 'settings_max_lim_ap', None)
    lim_ap = max_lim_ap.value() if max_lim_ap else 40.0

    A = np.clip(np.nan_to_num(np.asarray(df['A'].values, dtype=float), nan=0.0), 0.0, lim_ap)
    B = np.clip(np.nan_to_num(np.asarray(df['B'].values, dtype=float), nan=0.0), 0.0, lim_ap)
    C = np.clip(np.nan_to_num(np.asarray(df['C'].values, dtype=float), nan=0.0), 0.0, lim_ap)
    D = np.clip(np.nan_to_num(np.asarray(df['D'].values, dtype=float), nan=0.0), 0.0, lim_ap)

    # LAT from 'e and 'f (average)
    lat_cols = [c for c in df.columns if c in ["'e", "'f", "e", "f"]]
    if lat_cols:
        LAT = np.nan_to_num(np.mean([df[c].values for c in lat_cols], axis=0), nan=0.0)
    else:
        LAT = np.zeros(len(df))

    # SI from 'a and 'c (average)
    si_cols = [c for c in df.columns if c in ["'a", "'c", "a", "c"]]
    if si_cols:
        SI = np.nan_to_num(np.mean([df[c].values for c in si_cols], axis=0), nan=0.0)
    else:
        SI = np.zeros(len(df))

    # Read platform dimensions from settings, default to 100.0 if missing/invalid/<=0
    try:
        lat_dim = float(self.input_plat_lat.text().strip())
        if lat_dim <= 0.0:
            lat_dim = 100.0
    except Exception:
        lat_dim = 100.0

    try:
        si_dim = float(self.input_plat_si.text().strip())
        if si_dim <= 0.0:
            si_dim = 100.0
    except Exception:
        si_dim = 100.0

    try:
        off_ap = float(self.input_offset_ap.text().strip())
    except Exception:
        off_ap = 0.0

    # Pitch: D - A = si_dim * sin(p), where p = -pitch_rad
    sin_p = np.clip(np.nan_to_num((D - A) / si_dim, nan=0.0), -1.0, 1.0)
    p_rad = np.arcsin(sin_p)
    Pitch = -np.degrees(p_rad)

    # Roll: A - B = lat_dim * sin(roll) * cos(p)
    cos_p = np.cos(p_rad)
    cos_p_safe = np.where(np.abs(cos_p) < 1e-10, 1.0, cos_p)
    sin_r = np.clip(np.nan_to_num((A - B) / (lat_dim * cos_p_safe), nan=0.0), -1.0, 1.0)
    Roll = np.degrees(np.arcsin(sin_r))

    # AP: mean of actuators, corrected for rotation center offset
    cos_r = np.cos(np.radians(Roll))
    AP = (A + B + C + D) / 4.0 - off_ap * (1.0 - cos_r * cos_p)

    # Subtract sway compensation offset from LAT and SI
    roll_rad = np.radians(Roll)
    pitch_rad = np.radians(Pitch)

    LAT = LAT - off_ap * np.sin(roll_rad)
    SI = SI - off_ap * np.sin(pitch_rad)

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

        line_clean = line.split(';', 1)[0].strip()
        if not line_clean:
            continue
        
        first_word = line_clean.split()[0].upper()
        is_movement = False
        if first_word.startswith(('G0', 'G1', 'G00', 'G01')):
            rem = first_word[2:] if first_word.startswith(('G0', 'G1')) else first_word[3:]
            if not rem or not rem[0].isdigit():
                is_movement = True

        if is_movement:
            row_data = {}
            matches = pattern.findall(line_clean)
            for axis, val in matches:
                axis = axis.upper() if not axis.startswith("'") else axis
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
        elif line_clean.upper().startswith('G4'):
            p_match = re.search(r'[pP](\d+)', line_clean)
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
        elif line_clean.upper().startswith('M'):
            current_commands.append(line_clean)

    if cancelled:
        QMessageBox.information(self, "Import Cancelled", "G-code import was cancelled by the user.")
        return

    if not data_rows:
        QMessageBox.warning(self, "Import Warning", "No G0/G1 movement commands found in the G-code content.")
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
            cmd_mask = df['Command'].astype(str).str.strip().ne('')
            if cmd_mask.any():
                for t_val, cmd in zip(df.loc[cmd_mask, 'time'], df.loc[cmd_mask, 'Command']):
                    grid_idx = int(round(t_val / 0.01))
                    if 0 <= grid_idx < len(t_grid):
                        resampled_data['Command'][grid_idx] = str(cmd).strip()

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
        axis_cols = ['LAT', 'SI', 'AP', 'Roll', 'Pitch', 'Yaw', 'A', 'B', 'C', 'D', "'a", "'c", "'e", "'f"]
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

    if hasattr(self, 'offset_rot_widget'):
        self.offset_rot_widget.setVisible(device == "Motion Platform")

    if hasattr(self, 'combo_axis'):
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
    n_points = len(self.dfEdit) if hasattr(self, 'dfEdit') and self.dfEdit is not None else 0
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


def import_gcode_action(self, file_path=None):
    """
    Imports a GCODE file, parses its axes coordinates and commands,
    automatically detects device type, and populates the planning workspace.
    If file_path is None, prompts user with a file dialog.
    """
    from PySide6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog, QWidget
    from PySide6.QtCore import Qt, QCoreApplication
    import pandas as pd
    import numpy as np
    import re
    import os

    if file_path is None:
        file_path, _ = QFileDialog.getOpenFileName(
            self if isinstance(self, QWidget) else None,
            "Open G-code File",
            "",
            "G-code Files (*.gcode *.g *.nc);;All Files (*)"
        )
    if not file_path or not os.path.isfile(file_path):
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
                if line_idx % 2000 == 0:
                    progress.setValue(line_idx)
                    QCoreApplication.processEvents()
                    if progress.wasCanceled():
                        cancelled = True
                        break

                line_clean = line.split(';', 1)[0].strip()
                if not line_clean:
                    continue

                first_word = line_clean.split()[0].upper()
                is_movement = False
                if first_word.startswith(('G0', 'G1', 'G00', 'G01')):
                    rem = first_word[2:] if first_word.startswith(('G0', 'G1')) else first_word[3:]
                    if not rem or not rem[0].isdigit():
                        is_movement = True

                if is_movement:
                    # Parse axes
                    row_data = {}
                    matches = pattern.findall(line_clean)
                    for axis, val in matches:
                        axis = axis.upper() if not axis.startswith("'") else axis
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
                elif line_clean.upper().startswith('G4'):
                    p_match = re.search(r'[pP](\d+)', line_clean)
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
                elif line_clean.upper().startswith('M'):
                    # Store command to attach to the next movement row
                    current_commands.append(line_clean)

        if cancelled:
            QMessageBox.information(self, "Import Cancelled", "G-code import was cancelled by the user.")
            return

        if not data_rows:
            QMessageBox.warning(self, "Import Warning", "No G0/G1 movement commands found in the selected G-code file.")
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
                cmd_mask = df['Command'].astype(str).str.strip().ne('')
                if cmd_mask.any():
                    for t_val, cmd in zip(df.loc[cmd_mask, 'time'], df.loc[cmd_mask, 'Command']):
                        grid_idx = int(round(t_val / 0.01))
                        if 0 <= grid_idx < len(t_grid):
                            resampled_data['Command'][grid_idx] = str(cmd).strip()

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
        
        push_curve_state(self)

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
            axis_cols = ['LAT', 'SI', 'AP', 'Roll', 'Pitch', 'Yaw', 'A', 'B', 'C', 'D', "'a", "'c", "'e", "'f"]
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

        if hasattr(self, 'offset_rot_widget'):
            self.offset_rot_widget.setVisible(device == "Motion Platform")

        # Refresh axis dropdown list if present
        if hasattr(self, 'combo_axis'):
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


class CopyAxisDialog(QDialog):
    def __init__(self, parent_ui):
        parent_widget = parent_ui if isinstance(parent_ui, QWidget) else None
        super().__init__(parent_widget)
        self.parent_ui = parent_ui
        self.setWindowTitle("Copy Axis Data")
        self.setMinimumSize(520, 420)
        self.resize(560, 450)

        # Style dialog
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                background-color: #ffffff;
                border: 1px solid #cfd8dc;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #263238;
            }
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #b0bec5;
                border-radius: 4px;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 6px 10px;
            }
            QListWidget::item:selected {
                background-color: #bbdefb;
                color: #0d47a1;
                font-weight: bold;
            }
            QCheckBox {
                font-size: 14px;
                padding: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Header label
        header_lbl = QLabel("Select the source axis on the left and target destination axes on the right:", self)
        header_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #37474f;")
        layout.addWidget(header_lbl)

        # Split layout: Left (Source) vs Right (Destination)
        panels_layout = QHBoxLayout()
        panels_layout.setSpacing(15)

        # 1. Left Panel (Source Axis)
        gb_source = QGroupBox("Source Axis (Copy From)", self)
        gb_src_lay = QVBoxLayout(gb_source)
        gb_src_lay.setContentsMargins(10, 15, 10, 10)

        self.list_source = QListWidget(gb_source)
        gb_src_lay.addWidget(self.list_source)
        panels_layout.addWidget(gb_source, 1)

        # 2. Right Panel (Destination Axes)
        gb_dest = QGroupBox("Destination Axes (Copy To)", self)
        gb_dst_lay = QVBoxLayout(gb_dest)
        gb_dst_lay.setContentsMargins(10, 15, 10, 10)

        self.dst_scroll_widget = QWidget(gb_dest)
        self.dst_checkboxes_layout = QVBoxLayout(self.dst_scroll_widget)
        self.dst_checkboxes_layout.setContentsMargins(5, 5, 5, 5)
        self.dst_checkboxes_layout.setSpacing(6)

        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea(gb_dest)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.dst_scroll_widget)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #b0bec5; background-color: #ffffff; border-radius: 4px; }")
        gb_dst_lay.addWidget(scroll)

        panels_layout.addWidget(gb_dest, 1)
        layout.addLayout(panels_layout)

        # Get available axes from dfEdit (excluding metadata and derived actuator columns)
        exclude_cols = {'timestamp', 'time', 'Command', 'A', 'B', 'C', 'D', "'a", "'c", "'e", "'f", 'a', 'c', 'e', 'f'}
        df = getattr(parent_ui, 'dfEdit', None)
        if df is not None:
            self.available_axes = [col for col in df.columns if col not in exclude_cols and not col.startswith(('Vel.', 'Acc.'))]
        else:
            self.available_axes = ["X", "Y", "Z"]

        # Populate Left List (Source Axis)
        for ax in self.available_axes:
            self.list_source.addItem(ax)

        # Populate Right Checkboxes (Destination Axes)
        self.dst_checkboxes = {}
        for ax in self.available_axes:
            cb = QCheckBox(ax, self.dst_scroll_widget)
            cb.setStyleSheet("font-weight: bold; font-size: 14px;")
            self.dst_checkboxes_layout.addWidget(cb)
            self.dst_checkboxes[ax] = cb

        self.dst_checkboxes_layout.addStretch()

        # Connect source selection change
        self.list_source.currentItemChanged.connect(self.on_source_axis_changed)

        # Select first item by default on left list
        if self.list_source.count() > 0:
            self.list_source.setCurrentRow(0)

        # Bottom Button Row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_select_all = QPushButton("Select All Target", self)
        self.btn_select_all.setMinimumHeight(38)
        self.btn_select_all.setStyleSheet("""
            QPushButton {
                background-color: #eceff1;
                color: #37474f;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #b0bec5;
                border-radius: 4px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #cfd8dc;
            }
        """)
        self.btn_select_all.clicked.connect(self.select_all_enabled_targets)
        btn_layout.addWidget(self.btn_select_all)

        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.setMinimumHeight(38)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                color: #333333;
                font-weight: bold;
                font-size: 13px;
                border-radius: 4px;
                padding: 0 15px;
            }
            QPushButton:hover {
                background-color: #d6d6d6;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_copy = QPushButton("Copy Axis Data", self)
        self.btn_copy.setMinimumHeight(38)
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #1b5e20;
            }
        """)
        self.btn_copy.clicked.connect(self.execute_copy)
        btn_layout.addWidget(self.btn_copy)

        layout.addLayout(btn_layout)

    def on_source_axis_changed(self, current_item, previous_item):
        if not current_item:
            return
        src_axis = current_item.text()
        for ax_name, cb in self.dst_checkboxes.items():
            if ax_name == src_axis:
                cb.setChecked(False)
                cb.setEnabled(False)
                cb.setToolTip("Cannot copy source axis into itself")
            else:
                cb.setEnabled(True)
                cb.setToolTip("")

    def select_all_enabled_targets(self):
        for cb in self.dst_checkboxes.values():
            if cb.isEnabled():
                cb.setChecked(True)

    def execute_copy(self):
        curr = self.list_source.currentItem()
        if not curr:
            QMessageBox.warning(self, "Selection Warning", "Please select a source axis from the left list.")
            return

        source_axis = curr.text()
        target_axes = [ax for ax, cb in self.dst_checkboxes.items() if cb.isChecked() and cb.isEnabled()]

        if not target_axes:
            QMessageBox.warning(self, "Selection Warning", "Please select at least one destination axis checkbox on the right.")
            return

        parent = self.parent_ui
        if not hasattr(parent, 'dfEdit') or parent.dfEdit is None:
            return

        push_curve_state(parent)

        # Perform copy
        for target_ax in target_axes:
            parent.dfEdit[target_ax] = parent.dfEdit[source_axis].copy()

        device = parent.combo_device.currentText() if hasattr(parent, 'combo_device') else "Lung Phantom"
        if device == "Lung Phantom":
            parent.dfEdit_lung_phantom = parent.dfEdit
        elif device == "Motion Platform":
            parent.dfEdit = compute_motion_platform_actuators(parent, parent.dfEdit)
            parent.dfEdit_motion_platform = parent.dfEdit
        else:
            parent.dfEdit_other = parent.dfEdit

        loadTable_create(parent, parent.dfEdit)
        trigger_plot_update(parent)

        QMessageBox.information(
            self,
            "Copy Successful",
            f"Successfully copied motion curve data from '{source_axis}' to: {', '.join(target_axes)}."
        )
        self.accept()


def open_copy_axis_dialog(self):
    dlg = CopyAxisDialog(self)
    dlg.exec_()


class CropTrimDialog(QDialog):
    def __init__(self, parent_ui, mode="crop"):
        parent_widget = parent_ui if isinstance(parent_ui, QWidget) else None
        super().__init__(parent_widget)
        self.parent_ui = parent_ui
        self.mode = mode.lower()

        title = "Crop Interval (Keep Selection)" if self.mode == "crop" else "Trim Interval (Remove Selection)"
        self.setWindowTitle(title)
        self.setMinimumSize(420, 300)
        self.resize(460, 320)

        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                background-color: #ffffff;
                border: 1px solid #cfd8dc;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #263238;
            }
            QLabel {
                font-size: 13px;
            }
            QDoubleSpinBox {
                background-color: #ffffff;
                border: 1px solid #b0bec5;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 14px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Description text
        if self.mode == "crop":
            desc = "Crop keeps <b>ONLY</b> the motion curve data within the selected time interval [Start Time, End Time], discarding everything outside. Time is re-indexed from 0.0s."
        else:
            desc = "Trim <b>REMOVES</b> the motion curve data within the selected time interval [Start Time, End Time]. Remaining segments before and after are spliced together seamlessly."

        desc_lbl = QLabel(desc, self)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #37474f; font-size: 13px; line-height: 1.4;")
        layout.addWidget(desc_lbl)

        # Interval Spinboxes
        gb_range = QGroupBox("Select Time Interval", self)
        gb_range_lay = QGridLayout(gb_range)
        gb_range_lay.setContentsMargins(15, 20, 15, 15)
        gb_range_lay.setSpacing(10)

        lbl_start = QLabel("Start Time (s):", gb_range)
        lbl_start.setStyleSheet("font-weight: bold;")
        self.input_start = QDoubleSpinBox(gb_range)
        self.input_start.setRange(0.0, 10000.0)
        self.input_start.setDecimals(3)
        self.input_start.setMinimumHeight(38)

        def_start = parent_ui.input_start_time.value() if hasattr(parent_ui, 'input_start_time') else 0.0
        self.input_start.setValue(def_start)

        lbl_end = QLabel("End Time (s):", gb_range)
        lbl_end.setStyleSheet("font-weight: bold;")
        self.input_end = QDoubleSpinBox(gb_range)
        self.input_end.setRange(0.0, 10000.0)
        self.input_end.setDecimals(3)
        self.input_end.setMinimumHeight(38)

        def_end = parent_ui.input_end_time.value() if hasattr(parent_ui, 'input_end_time') else 10.0
        self.input_end.setValue(def_end)

        gb_range_lay.addWidget(lbl_start, 0, 0)
        gb_range_lay.addWidget(self.input_start, 0, 1)
        gb_range_lay.addWidget(lbl_end, 1, 0)
        gb_range_lay.addWidget(self.input_end, 1, 1)

        layout.addWidget(gb_range)
        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.setMinimumHeight(38)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                color: #333333;
                font-weight: bold;
                font-size: 13px;
                border-radius: 4px;
                padding: 0 15px;
            }
            QPushButton:hover {
                background-color: #d6d6d6;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        btn_text = "Crop Data" if self.mode == "crop" else "Trim Data"
        btn_bg = "#2e7d32" if self.mode == "crop" else "#c62828"
        btn_hover = "#1b5e20" if self.mode == "crop" else "#b71c1c"

        self.btn_action = QPushButton(btn_text, self)
        self.btn_action.setMinimumHeight(38)
        self.btn_action.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_bg};
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
                padding: 0 20px;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
            }}
        """)
        self.btn_action.clicked.connect(self.execute_action)
        btn_layout.addWidget(self.btn_action)

        layout.addLayout(btn_layout)

    def execute_action(self):
        t_start = round(self.input_start.value(), 3)
        t_end = round(self.input_end.value(), 3)

        if t_start >= t_end:
            QMessageBox.warning(self, "Invalid Time Range", "Start Time must be strictly less than End Time.")
            return

        parent = self.parent_ui
        if not hasattr(parent, 'dfEdit') or parent.dfEdit is None or len(parent.dfEdit) == 0:
            QMessageBox.warning(self, "Data Warning", "No active curve data found to process.")
            return

        df = parent.dfEdit
        push_curve_state(parent)

        if self.mode == "crop":
            # Crop logic: keep t_start <= time <= t_end
            df_cropped = df[(df['time'] >= t_start) & (df['time'] <= t_end)].copy()
            if len(df_cropped) == 0:
                QMessageBox.warning(self, "Crop Error", f"No data points found within [{t_start} s, {t_end} s].")
                return

            min_t = df_cropped['time'].min()
            df_cropped['time'] = (df_cropped['time'] - min_t).round(3)
            df_cropped['timestamp'] = (df_cropped['time'] * 1000.0).round(1)
            df_cropped.reset_index(drop=True, inplace=True)

            parent.dfEdit = df_cropped

        else:
            # Trim logic: remove t_start <= time <= t_end
            part1 = df[df['time'] < t_start].copy()
            part3 = df[df['time'] > t_end].copy()

            if len(part1) == 0 and len(part3) == 0:
                QMessageBox.warning(self, "Trim Error", "Trimming the entire interval would leave no data points.")
                return

            if len(part1) > 0 and len(part3) > 0:
                dt_step = 0.001
                if len(df) > 1:
                    dt_step = df['time'].iat[1] - df['time'].iat[0]
                    if dt_step <= 0:
                        dt_step = 0.001

                t_last = part1['time'].max()
                t3_start = part3['time'].min()
                shift_amount = t3_start - (t_last + dt_step)
                part3['time'] = (part3['time'] - shift_amount).round(3)
                part3['timestamp'] = (part3['time'] * 1000.0).round(1)
                df_trimmed = pd.concat([part1, part3], ignore_index=True)
            elif len(part1) == 0:
                t3_start = part3['time'].min()
                part3['time'] = (part3['time'] - t3_start).round(3)
                part3['timestamp'] = (part3['time'] * 1000.0).round(1)
                df_trimmed = part3.reset_index(drop=True)
            else:
                df_trimmed = part1.reset_index(drop=True)

            parent.dfEdit = df_trimmed

        device = parent.combo_device.currentText() if hasattr(parent, 'combo_device') else "Lung Phantom"
        if device == "Lung Phantom":
            parent.dfEdit_lung_phantom = parent.dfEdit
        elif device == "Motion Platform":
            parent.dfEdit = compute_motion_platform_actuators(parent, parent.dfEdit)
            parent.dfEdit_motion_platform = parent.dfEdit
        else:
            parent.dfEdit_other = parent.dfEdit

        loadTable_create(parent, parent.dfEdit)
        trigger_plot_update(parent)

        action_name = "cropped to" if self.mode == "crop" else "trimmed from"
        QMessageBox.information(
            self,
            "Success",
            f"Successfully {action_name} range [{t_start} s, {t_end} s]. Total curve duration is now {parent.dfEdit['time'].max():.3f} s."
        )
        self.accept()


def open_crop_interval_dialog(self):
    dlg = CropTrimDialog(self, mode="crop")
    dlg.exec_()


def open_trim_interval_dialog(self):
    dlg = CropTrimDialog(self, mode="trim")
    dlg.exec_()


class MathOperationsDialog(QDialog):
    def __init__(self, parent_ui):
        parent_widget = parent_ui if isinstance(parent_ui, QWidget) else None
        super().__init__(parent_widget)
        self.parent_ui = parent_ui
        self.setWindowTitle("Curve Math Operations")
        self.setMinimumSize(540, 520)
        self.resize(580, 560)

        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                background-color: #ffffff;
                border: 1px solid #cfd8dc;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #263238;
            }
            QLabel {
                font-size: 13px;
            }
            QRadioButton {
                font-size: 13px;
                font-weight: bold;
                padding: 3px;
            }
            QDoubleSpinBox {
                background-color: #ffffff;
                border: 1px solid #b0bec5;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 14px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # 1. Operation Selection GroupBox
        gb_op = QGroupBox("1. Select Operation & Value", self)
        gb_op_lay = QGridLayout(gb_op)
        gb_op_lay.setContentsMargins(15, 15, 15, 15)
        gb_op_lay.setSpacing(10)

        self.radio_offset = QRadioButton("Offset (+/-)", gb_op)
        self.radio_multiply = QRadioButton("Multiply (x)", gb_op)
        self.radio_divide = QRadioButton("Divide (/)", gb_op)
        self.radio_invert = QRadioButton("Invert (Flip Y)", gb_op)
        self.radio_offset.setChecked(True)

        gb_op_lay.addWidget(self.radio_offset, 0, 0)
        gb_op_lay.addWidget(self.radio_multiply, 0, 1)
        gb_op_lay.addWidget(self.radio_divide, 1, 0)
        gb_op_lay.addWidget(self.radio_invert, 1, 1)

        self.lbl_val = QLabel("Value (k):", gb_op)
        self.lbl_val.setStyleSheet("font-weight: bold;")
        self.input_val_k = QDoubleSpinBox(gb_op)
        self.input_val_k.setRange(-10000.0, 10000.0)
        self.input_val_k.setValue(1.0)
        self.input_val_k.setDecimals(3)
        self.input_val_k.setMinimumHeight(38)

        gb_op_lay.addWidget(self.lbl_val, 2, 0)
        gb_op_lay.addWidget(self.input_val_k, 2, 1)

        layout.addWidget(gb_op)

        # Connect radio buttons to toggle value spinbox state
        self.radio_offset.toggled.connect(self.on_op_changed)
        self.radio_multiply.toggled.connect(self.on_op_changed)
        self.radio_divide.toggled.connect(self.on_op_changed)
        self.radio_invert.toggled.connect(self.on_op_changed)

        # 2. Time Scope Selection GroupBox
        gb_scope = QGroupBox("2. Time Scope", self)
        gb_scope_lay = QVBoxLayout(gb_scope)
        gb_scope_lay.setContentsMargins(15, 15, 15, 15)
        gb_scope_lay.setSpacing(8)

        self.radio_entire = QRadioButton("Entire Curve", gb_scope)
        self.radio_segment = QRadioButton("Specific Segment [t_start, t_end]", gb_scope)
        self.radio_entire.setChecked(True)

        gb_scope_lay.addWidget(self.radio_entire)
        gb_scope_lay.addWidget(self.radio_segment)

        # Segment inputs container
        self.segment_widget = QWidget(gb_scope)
        seg_lay = QHBoxLayout(self.segment_widget)
        seg_lay.setContentsMargins(20, 0, 0, 0)
        seg_lay.setSpacing(10)

        lbl_tstart = QLabel("Start (s):", self.segment_widget)
        lbl_tstart.setStyleSheet("font-weight: bold;")
        self.input_t_start = QDoubleSpinBox(self.segment_widget)
        self.input_t_start.setRange(0.0, 10000.0)
        self.input_t_start.setDecimals(3)
        self.input_t_start.setMinimumHeight(36)
        def_start = parent_ui.input_start_time.value() if hasattr(parent_ui, 'input_start_time') else 0.0
        self.input_t_start.setValue(def_start)

        lbl_tend = QLabel("End (s):", self.segment_widget)
        lbl_tend.setStyleSheet("font-weight: bold;")
        self.input_t_end = QDoubleSpinBox(self.segment_widget)
        self.input_t_end.setRange(0.0, 10000.0)
        self.input_t_end.setDecimals(3)
        self.input_t_end.setMinimumHeight(36)
        def_end = parent_ui.input_end_time.value() if hasattr(parent_ui, 'input_end_time') else 10.0
        self.input_t_end.setValue(def_end)

        seg_lay.addWidget(lbl_tstart)
        seg_lay.addWidget(self.input_t_start)
        seg_lay.addWidget(lbl_tend)
        seg_lay.addWidget(self.input_t_end)

        self.segment_widget.setEnabled(False)
        gb_scope_lay.addWidget(self.segment_widget)
        layout.addWidget(gb_scope)

        self.radio_entire.toggled.connect(lambda chk: self.segment_widget.setEnabled(not chk))

        # 3. Target Axes GroupBox
        gb_axes = QGroupBox("3. Target Axes (Multi-Select)", self)
        gb_axes_lay = QVBoxLayout(gb_axes)
        gb_axes_lay.setContentsMargins(15, 15, 15, 15)
        gb_axes_lay.setSpacing(8)

        # Helper buttons top row
        axes_btn_lay = QHBoxLayout()
        axes_btn_lay.setSpacing(10)
        self.btn_select_all = QPushButton("Select All", gb_axes)
        self.btn_select_all.setStyleSheet("font-size: 12px; font-weight: bold; padding: 4px 10px;")
        self.btn_select_all.clicked.connect(self.select_all_axes)

        self.btn_clear_all = QPushButton("Clear All", gb_axes)
        self.btn_clear_all.setStyleSheet("font-size: 12px; font-weight: bold; padding: 4px 10px;")
        self.btn_clear_all.clicked.connect(self.clear_all_axes)

        axes_btn_lay.addWidget(self.btn_select_all)
        axes_btn_lay.addWidget(self.btn_clear_all)
        axes_btn_lay.addStretch()
        gb_axes_lay.addLayout(axes_btn_lay)

        # Checkboxes grid (excluding metadata and derived actuator columns)
        exclude_cols = {'timestamp', 'time', 'Command', 'A', 'B', 'C', 'D', "'a", "'c", "'e", "'f", 'a', 'c', 'e', 'f'}
        df = getattr(parent_ui, 'dfEdit', None)
        if df is not None:
            available_axes = [col for col in df.columns if col not in exclude_cols and not col.startswith(('Vel.', 'Acc.'))]
        else:
            available_axes = ["X", "Y", "Z"]

        self.axis_checkboxes = {}
        cb_grid = QGridLayout()
        cb_grid.setSpacing(10)

        for i, ax_name in enumerate(available_axes):
            cb = QCheckBox(ax_name, gb_axes)
            cb.setStyleSheet("font-weight: bold; font-size: 14px;")
            cb.setChecked(True)
            row = i // 4
            col = i % 4
            cb_grid.addWidget(cb, row, col)
            self.axis_checkboxes[ax_name] = cb

        gb_axes_lay.addLayout(cb_grid)
        layout.addWidget(gb_axes)
        layout.addStretch()

        # Status message label
        self.lbl_status = QLabel("", self)
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold;")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_status)

        # Action Buttons Bottom
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_cancel = QPushButton("Close", self)
        self.btn_cancel.setMinimumHeight(38)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                color: #333333;
                font-weight: bold;
                font-size: 13px;
                border-radius: 4px;
                padding: 0 15px;
            }
            QPushButton:hover {
                background-color: #d6d6d6;
            }
        """)
        self.btn_cancel.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_action = QPushButton("Apply Operation", self)
        self.btn_action.setMinimumHeight(38)
        self.btn_action.setStyleSheet("""
            QPushButton {
                background-color: #5e35b1;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #4527a0;
            }
        """)
        self.btn_action.clicked.connect(self.execute_math_op)
        btn_layout.addWidget(self.btn_action)

        layout.addLayout(btn_layout)

    def on_op_changed(self):
        if self.radio_invert.isChecked():
            self.input_val_k.setEnabled(False)
            self.lbl_val.setText("Offset:")
            self.lbl_val.setToolTip("Inverts curve vertically while preserving the Y center/range so values remain non-negative.")
        elif self.radio_offset.isChecked():
            self.input_val_k.setEnabled(True)
            self.lbl_val.setText("Offset (mm):")
        elif self.radio_multiply.isChecked():
            self.input_val_k.setEnabled(True)
            self.lbl_val.setText("Factor (x):")
        elif self.radio_divide.isChecked():
            self.input_val_k.setEnabled(True)
            self.lbl_val.setText("Divisor (/):")

    def select_all_axes(self):
        for cb in self.axis_checkboxes.values():
            cb.setChecked(True)

    def clear_all_axes(self):
        for cb in self.axis_checkboxes.values():
            cb.setChecked(False)

    def execute_math_op(self):
        parent = self.parent_ui
        if not hasattr(parent, 'dfEdit') or parent.dfEdit is None or len(parent.dfEdit) == 0:
            QMessageBox.warning(self, "Data Warning", "No active curve data found to process.")
            return

        target_axes = [ax for ax, cb in self.axis_checkboxes.items() if cb.isChecked()]
        if not target_axes:
            QMessageBox.warning(self, "Selection Warning", "Please select at least one target axis checkbox.")
            return

        val_k = self.input_val_k.value()

        # Determine operation
        if self.radio_offset.isChecked():
            op_type = "offset"
        elif self.radio_multiply.isChecked():
            op_type = "multiply"
        elif self.radio_divide.isChecked():
            op_type = "divide"
            if val_k == 0.0:
                QMessageBox.warning(self, "Division Error", "Division by zero (k = 0.0) is not allowed.")
                return
        else:
            op_type = "invert"

        # Determine time mask
        df = parent.dfEdit
        if self.radio_entire.isChecked():
            t_mask = pd.Series([True] * len(df), index=df.index)
            scope_str = "entire curve"
        else:
            t_start = round(self.input_t_start.value(), 3)
            t_end = round(self.input_t_end.value(), 3)
            if t_start >= t_end:
                QMessageBox.warning(self, "Invalid Time Range", "Start Time must be strictly less than End Time.")
                return
            t_mask = (df['time'] >= t_start) & (df['time'] <= t_end)
            if not t_mask.any():
                QMessageBox.warning(self, "Scope Error", f"No data points found within [{t_start} s, {t_end} s].")
                return
            scope_str = f"segment [{t_start} s, {t_end} s]"

        # Save copy for undo
        push_curve_state(parent)
        parent.dfEdit_copy = df.copy()

        # Apply math operation
        for ax in target_axes:
            if ax not in df.columns:
                continue
            if op_type == "offset":
                df.loc[t_mask, ax] = df.loc[t_mask, ax] + val_k
            elif op_type == "multiply":
                df.loc[t_mask, ax] = df.loc[t_mask, ax] * val_k
            elif op_type == "divide":
                df.loc[t_mask, ax] = df.loc[t_mask, ax] / val_k
            elif op_type == "invert":
                vals = df.loc[t_mask, ax]
                if len(vals) > 0:
                    y_min = vals.min()
                    y_max = vals.max()
                    # Invert vertically while keeping center/range in Y identical:
                    # y_new = (y_max + y_min) - y
                    # Flips peaks/troughs while ensuring numbers never turn negative for linear axes.
                    df.loc[t_mask, ax] = (y_max + y_min) - vals

        # Ensure linear axes are never negative
        for ax in target_axes:
            if ax not in ["Roll", "Pitch", "Yaw"] and ax in df.columns:
                df.loc[t_mask, ax] = df.loc[t_mask, ax].clip(lower=0.0)

        device = parent.combo_device.currentText() if hasattr(parent, 'combo_device') else "Lung Phantom"
        if device == "Lung Phantom":
            parent.dfEdit_lung_phantom = parent.dfEdit
        elif device == "Motion Platform":
            parent.dfEdit = compute_motion_platform_actuators(parent, parent.dfEdit)
            parent.dfEdit_motion_platform = parent.dfEdit
        else:
            parent.dfEdit_other = parent.dfEdit

        loadTable_create(parent, parent.dfEdit)
        trigger_plot_update(parent)
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()

        self.lbl_status.setText(f"✓ Applied {op_type.upper()} across {scope_str} to: {', '.join(target_axes)}")
        self.lbl_status.setStyleSheet("color: #2e7d32; font-weight: bold; font-size: 13px;")


def open_math_operations_dialog(self):
    dlg = MathOperationsDialog(self)
    dlg.exec_()


class SmoothAxisDialog(QDialog):
    """
    Dialog allowing the user to select target axes and a smoothing level/method
    to smooth digital motion curves and remove high-frequency noise.
    """
    def __init__(self, parent_ui):
        parent_widget = parent_ui if isinstance(parent_ui, QWidget) else None
        super().__init__(parent_widget)
        self.parent_ui = parent_ui

        self.setWindowTitle("Smooth Curve Axes")
        self.setMinimumSize(540, 560)
        self.resize(580, 600)

        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                background-color: #ffffff;
                border: 1px solid #cfd8dc;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #263238;
            }
            QLabel {
                font-size: 13px;
                color: #37474f;
            }
            QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #ffffff;
                border: 1px solid #b0bec5;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border: 2px solid #00897b;
            }
            QCheckBox {
                font-size: 14px;
                font-weight: bold;
                padding: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Overview Description
        # Overview Description
        desc_lbl = QLabel(
            "Apply digital smoothing filters to eliminate signal jitter and noise on selected position axes.<br>"
            "Adjust the <b>Smooth Level</b> to control filter strength. Velocity and acceleration are automatically recalculated from smoothed positions.",
            self
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #37474f; font-size: 13px; line-height: 1.4;")
        layout.addWidget(desc_lbl)

        # 1. Target Axes Selection GroupBox
        gb_axes = QGroupBox("1. Target Position Axes Selection", self)
        gb_axes_lay = QVBoxLayout(gb_axes)
        gb_axes_lay.setContentsMargins(15, 15, 15, 15)
        gb_axes_lay.setSpacing(8)

        lbl_ax_info = QLabel("Select position axes to smooth (velocity & acceleration are recalculated):", gb_axes)
        lbl_ax_info.setStyleSheet("font-weight: bold;")
        gb_axes_lay.addWidget(lbl_ax_info)

        # Convenience buttons: Select All / Clear All
        axes_btn_lay = QHBoxLayout()
        axes_btn_lay.setSpacing(10)
        self.btn_select_all = QPushButton("Select All", gb_axes)
        self.btn_select_all.setStyleSheet("font-size: 12px; font-weight: bold; padding: 4px 10px;")
        self.btn_select_all.clicked.connect(self.select_all_axes)

        self.btn_clear_all = QPushButton("Clear All", gb_axes)
        self.btn_clear_all.setStyleSheet("font-size: 12px; font-weight: bold; padding: 4px 10px;")
        self.btn_clear_all.clicked.connect(self.clear_all_axes)

        axes_btn_lay.addWidget(self.btn_select_all)
        axes_btn_lay.addWidget(self.btn_clear_all)
        axes_btn_lay.addStretch()
        gb_axes_lay.addLayout(axes_btn_lay)

        # Build list of available position axes from current planning dataframe
        exclude_cols = {'timestamp', 'time', 'Command', 'A', 'B', 'C', 'D', "'a", "'c", "'e", "'f", 'a', 'c', 'e', 'f'}
        df = getattr(parent_ui, 'dfEdit', None)
        combo = getattr(parent_ui, 'combo_device', None)
        device = combo.currentText() if combo is not None else "Lung Phantom"

        if device == "Lung Phantom":
            available_axes = [col for col in ['X', 'Y', 'Z'] if df is None or col in df.columns]
        elif device == "Motion Platform":
            available_axes = [col for col in ['LAT', 'SI', 'AP', 'Roll', 'Pitch', 'Yaw'] if df is None or col in df.columns]
        elif df is not None:
            available_axes = [col for col in df.columns if col not in exclude_cols and not col.startswith(('Vel.', 'Acc.'))]
        else:
            available_axes = ["X", "Y", "Z"]

        self.axis_checkboxes = {}
        cb_grid = QGridLayout()
        cb_grid.setSpacing(10)

        for i, ax_name in enumerate(available_axes):
            cb = QCheckBox(f"{ax_name} (Pos)", gb_axes)
            cb.setStyleSheet("font-weight: bold; font-size: 14px;")
            is_active = True
            if df is not None and ax_name in df.columns:
                try:
                    s = df[ax_name].to_numpy(dtype=float)
                    is_active = bool(np.ptp(s) > 1e-4 or np.any(np.abs(s) > 1e-4))
                except Exception:
                    is_active = True
            cb.setChecked(is_active)
            cb_grid.addWidget(cb, i // 4, i % 4)
            self.axis_checkboxes[ax_name] = cb

        gb_axes_lay.addLayout(cb_grid)
        layout.addWidget(gb_axes)

        # 2. Smoothing Level & Parameters GroupBox
        gb_smooth = QGroupBox("2. Smoothing Level & Parameters", self)
        gb_smooth_lay = QGridLayout(gb_smooth)
        gb_smooth_lay.setContentsMargins(15, 15, 15, 15)
        gb_smooth_lay.setSpacing(10)

        # Method Selector
        lbl_method = QLabel("Smoothing Method:", gb_smooth)
        lbl_method.setStyleSheet("font-weight: bold;")
        self.combo_method = QComboBox(gb_smooth)
        self.combo_method.setMinimumHeight(38)
        self.combo_method.addItems([
            "Savitzky-Golay (Preserves Peak Amplitude)",
            "Moving Average (Uniform Filter)",
            "Gaussian Filter (Smooth Bell-Curve)",
            "Median Filter (Spike & Glitch Removal)"
        ])
        gb_smooth_lay.addWidget(lbl_method, 0, 0)
        gb_smooth_lay.addWidget(self.combo_method, 0, 1)

        # Smooth Level: SpinBox + Slider
        lbl_level = QLabel("Smooth Level:", gb_smooth)
        lbl_level.setStyleSheet("font-weight: bold;")
        gb_smooth_lay.addWidget(lbl_level, 1, 0)

        level_container = QWidget(gb_smooth)
        level_lay = QHBoxLayout(level_container)
        level_lay.setContentsMargins(0, 0, 0, 0)
        level_lay.setSpacing(10)

        self.slider_level = QSlider(Qt.Horizontal, level_container)
        self.slider_level.setRange(1, 50)
        self.slider_level.setValue(5)
        self.slider_level.setMinimumHeight(30)

        self.spin_level = QSpinBox(level_container)
        self.spin_level.setRange(1, 50)
        self.spin_level.setValue(5)
        self.spin_level.setMinimumHeight(38)
        self.spin_level.setMinimumWidth(80)

        self.slider_level.valueChanged.connect(self.spin_level.setValue)
        self.spin_level.valueChanged.connect(self.slider_level.setValue)
        self.spin_level.valueChanged.connect(self.update_info_label)
        self.combo_method.currentIndexChanged.connect(self.update_info_label)

        level_lay.addWidget(self.slider_level, 1)
        level_lay.addWidget(self.spin_level)
        gb_smooth_lay.addWidget(level_container, 1, 1)

        # Dynamic info label
        self.lbl_window_info = QLabel("", gb_smooth)
        self.lbl_window_info.setStyleSheet("color: #00796b; font-weight: bold; font-size: 13px;")
        gb_smooth_lay.addWidget(self.lbl_window_info, 2, 0, 1, 2)

        # Boundary Option
        self.cb_clip_zero = QCheckBox("Ensure non-negative coordinates (clip ≥ 0 mm for linear axes)", gb_smooth)
        self.cb_clip_zero.setChecked(True)
        self.cb_clip_zero.setToolTip("Ensures linear axes do not dip below 0 mm, staying within physical phantom boundaries.")
        gb_smooth_lay.addWidget(self.cb_clip_zero, 3, 0, 1, 2)

        layout.addWidget(gb_smooth)
        layout.addStretch()

        # Status Label
        self.lbl_status = QLabel("", self)
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold;")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_status)

        # Bottom Button Row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_undo = QPushButton("Undo Last Smooth", self)
        self.btn_undo.setMinimumHeight(40)
        self.btn_undo.setEnabled(False)
        self.btn_undo.setStyleSheet("""
            QPushButton {
                background-color: #ef5350;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 4px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: #e53935;
            }
            QPushButton:disabled {
                background-color: #e0e0e0;
                color: #9e9e9e;
            }
        """)
        self.btn_undo.clicked.connect(self.execute_undo)
        btn_layout.addWidget(self.btn_undo)

        btn_layout.addStretch()

        self.btn_close = QPushButton("Close", self)
        self.btn_close.setMinimumHeight(40)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #cfd8dc;
                color: #263238;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #b0bec5;
            }
        """)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        self.btn_apply = QPushButton("Apply Smoothing", self)
        self.btn_apply.setMinimumHeight(40)
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #00897b;
                color: white;
                font-weight: bold;
                font-size: 15px;
                border-radius: 4px;
                padding: 0 22px;
            }
            QPushButton:hover {
                background-color: #00695c;
            }
        """)
        self.btn_apply.clicked.connect(self.execute_smoothing)
        btn_layout.addWidget(self.btn_apply)

        layout.addLayout(btn_layout)

        self.update_info_label()

    def update_info_label(self):
        level = self.spin_level.value()
        w = 2 * level + 1
        parent = self.parent_ui
        df = getattr(parent, 'dfEdit', None)

        time_info = ""
        if df is not None and 'time' in df.columns and len(df['time']) > 1:
            try:
                dt = float(df['time'].iloc[1] - df['time'].iloc[0])
                if dt > 0:
                    time_span = w * dt
                    time_info = f" (~{time_span:.2f} s span @ {1.0/dt:.1f} Hz)"
            except Exception:
                pass

        method_text = self.combo_method.currentText().split('(')[0].strip()
        self.lbl_window_info.setText(f"Filter window: {w} points{time_info} via {method_text}")

    def execute_smoothing(self):
        parent = self.parent_ui
        if parent is None or not hasattr(parent, 'dfEdit') or parent.dfEdit is None:
            QMessageBox.warning(self, "No Motion Curve", "No active curve in Planning workspace to smooth.")
            return

        df = parent.dfEdit
        if len(df) < 3:
            QMessageBox.warning(self, "Curve Too Short", "Curve requires at least 3 points to apply smoothing.")
            return

        target_axes = [ax for ax, cb in self.axis_checkboxes.items() if cb.isChecked() and ax in df.columns]
        if not target_axes:
            QMessageBox.warning(self, "Selection Warning", "Please select at least one axis checkbox to smooth.")
            return

        level = self.spin_level.value()
        method = self.combo_method.currentText()
        clip_zero = self.cb_clip_zero.isChecked()
        rotational_axes = {"Roll", "Pitch", "Yaw"}

        # Backup for undo
        push_curve_state(parent)
        parent.dfEdit_copy = df.copy()

        import scipy.signal
        import scipy.ndimage

        n = len(df)
        w = 2 * int(level) + 1
        w = max(3, min(w, n))
        if w % 2 == 0:
            w -= 1
        if w < 3:
            w = 3

        t_arr = df['time'].values if 'time' in df.columns else np.arange(len(df)) * 0.01
        t_clean = np.array(t_arr, dtype=float)
        if np.any(np.diff(t_clean) <= 0):
            t_clean = np.maximum.accumulate(t_clean)
            for i in range(1, len(t_clean)):
                if t_clean[i] <= t_clean[i - 1]:
                    t_clean[i] = t_clean[i - 1] + 1e-4

        for ax in target_axes:
            signal = df[ax].to_numpy(dtype=float)
            is_rot = ax in rotational_axes

            if "Savitzky-Golay" in method:
                poly = min(3, w - 1)
                if poly < 1:
                    poly = 1
                smoothed = scipy.signal.savgol_filter(signal, window_length=w, polyorder=poly, mode='interp')
            elif "Gaussian" in method:
                sigma = max(0.5, float(level) / 2.0)
                smoothed = scipy.ndimage.gaussian_filter1d(signal, sigma=sigma, mode='nearest')
            elif "Median" in method:
                smoothed = scipy.ndimage.median_filter(signal, size=w, mode='nearest')
            else:  # Moving Average
                smoothed = scipy.ndimage.uniform_filter1d(signal, size=w, mode='nearest')

            if clip_zero and not is_rot:
                smoothed = np.clip(smoothed, a_min=0.0, a_max=None)

            # 1. Apply smooth to position
            df[ax] = smoothed

            # 2. Recalculate velocity and acceleration from the smoothed position and time
            if len(t_clean) >= 2:
                v_smooth = np.gradient(smoothed, t_clean)
                if len(t_clean) >= 3:
                    a_smooth = np.gradient(v_smooth, t_clean)
                else:
                    a_smooth = np.zeros_like(v_smooth)
            else:
                v_smooth = np.zeros_like(smoothed)
                a_smooth = np.zeros_like(smoothed)

            df[f"Vel. {ax}"] = np.nan_to_num(v_smooth, nan=0.0)
            df[f"Acc. {ax}"] = np.nan_to_num(a_smooth, nan=0.0)

        device = parent.combo_device.currentText() if hasattr(parent, 'combo_device') else "Lung Phantom"
        if device == "Lung Phantom":
            parent.dfEdit_lung_phantom = parent.dfEdit
        elif device == "Motion Platform":
            parent.dfEdit = compute_motion_platform_actuators(parent, parent.dfEdit)
            for m_ax in ['Pitch', 'Roll', 'AP', 'A', 'B', 'C', 'D']:
                if m_ax in parent.dfEdit.columns and (f"Vel. {m_ax}" in parent.dfEdit.columns or m_ax in target_axes):
                    pos_m = parent.dfEdit[m_ax].to_numpy(dtype=float)
                    v_m = np.gradient(pos_m, t_clean)
                    a_m = np.gradient(v_m, t_clean)
                    parent.dfEdit[f"Vel. {m_ax}"] = np.nan_to_num(v_m, nan=0.0)
                    parent.dfEdit[f"Acc. {m_ax}"] = np.nan_to_num(a_m, nan=0.0)
            parent.dfEdit_motion_platform = parent.dfEdit
        else:
            parent.dfEdit_other = parent.dfEdit

        loadTable_create(parent, parent.dfEdit)
        trigger_plot_update(parent)
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()

        self.btn_undo.setEnabled(True)
        self.lbl_status.setText(f"✓ Smoothed {', '.join(target_axes)} (Level {level}, Window {w} pts)")
        self.lbl_status.setStyleSheet("color: #00796b; font-weight: bold; font-size: 13px;")

    def execute_undo(self):
        parent = self.parent_ui
        if parent is None or not hasattr(parent, 'dfEdit_copy') or parent.dfEdit_copy is None:
            return

        parent.dfEdit = parent.dfEdit_copy.copy()
        device = parent.combo_device.currentText() if hasattr(parent, 'combo_device') else "Lung Phantom"
        if device == "Lung Phantom":
            parent.dfEdit_lung_phantom = parent.dfEdit
        elif device == "Motion Platform":
            parent.dfEdit = compute_motion_platform_actuators(parent, parent.dfEdit)
            parent.dfEdit_motion_platform = parent.dfEdit
        else:
            parent.dfEdit_other = parent.dfEdit

        loadTable_create(parent, parent.dfEdit)
        trigger_plot_update(parent)
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()

        self.btn_undo.setEnabled(False)
        self.lbl_status.setText("✓ Smoothing undone. Curve restored.")
        self.lbl_status.setStyleSheet("color: #c62828; font-weight: bold; font-size: 13px;")

    def select_all_axes(self):
        for cb in self.axis_checkboxes.values():
            cb.setChecked(True)

    def clear_all_axes(self):
        for cb in self.axis_checkboxes.values():
            cb.setChecked(False)


def open_smooth_axes_dialog(self):
    if getattr(self, '_smooth_dialog_open', False):
        return
    self._smooth_dialog_open = True
    try:
        dlg = SmoothAxisDialog(self)
        dlg.exec_()
    finally:
        self._smooth_dialog_open = False