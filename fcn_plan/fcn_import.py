import os
import pandas as pd
import numpy as np
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QDoubleSpinBox, QComboBox, QCheckBox,
    QFileDialog, QTableWidgetItem, QMessageBox, QScrollArea, QFrame
)


def parse_motion_file(file_path):
    """
    Parses a VXP or CSV motion file.
    Automatically detects:
      - Line where [Data] begins (for VXP files)
      - Samples_per_second (sampling rate)
      - Scale_factor (amplitude multiplier)
      - Data_layout (column names)
      - Metadata (study time, patient ID, date, etc.)
    Returns:
      (df, header_metadata, samples_per_second, scale_factor, data_start_line)
    """
    header_metadata = {}
    data_start_line = None
    data_layout = []
    samples_per_second = 25.0
    scale_factor = 1.0

    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
    lines = []
    
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                lines = f.readlines()
            break
        except (UnicodeDecodeError, Exception):
            continue

    if not lines:
        raise ValueError(f"Could not read file: {file_path}")

    # 1. Parse header and find [Data]
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue
        
        # Automatic recognition of [Data] section
        if '[data]' in line.lower():
            data_start_line = idx + 1
            break
        
        # Section header e.g. [Header]
        if line.startswith('[') and line.endswith(']'):
            continue
            
        if '=' in line:
            k, v = line.split('=', 1)
            k = k.strip().lower()
            v = v.strip()
            header_metadata[k] = v
            if k == 'data_layout':
                data_layout = [c.strip() for c in v.split(',') if c.strip()]
            elif k == 'samples_per_second':
                try:
                    samples_per_second = float(v)
                except ValueError:
                    pass
            elif k == 'scale_factor':
                try:
                    scale_factor = float(v)
                except ValueError:
                    pass

    # 2. Read data
    if data_start_line is not None:
        # File has [Data] tag (standard VXP format)
        df = pd.read_csv(file_path, skiprows=data_start_line, header=None, encoding=enc)
        
        # Strip trailing blank rows
        df = df.dropna(how='all')
        
        if data_layout and len(data_layout) <= df.shape[1]:
            col_names = list(data_layout) + [f"extra_{i}" for i in range(df.shape[1] - len(data_layout))]
            df.columns = col_names[:df.shape[1]]
        elif df.shape[1] == 7:
            df.columns = ['amplitude', 'phase', 'timestamp', 'validflag', 'ttlin', 'mark', 'ttlout']
        elif df.shape[1] == 2:
            df.columns = ['time', 'amplitude']
        else:
            df.columns = [f"col_{i}" for i in range(df.shape[1])]
            if 'amplitude' not in df.columns:
                df.rename(columns={'col_0': 'amplitude'}, inplace=True)
    else:
        # Regular CSV without [Data]
        df = pd.read_csv(file_path, encoding=enc)
        # Lowercase column lookup
        col_map = {c: c.strip().lower() for c in df.columns}
        inv_map = {v: k for k, v in col_map.items()}
        if 'amplitude' in inv_map:
            df.rename(columns={inv_map['amplitude']: 'amplitude'}, inplace=True)
        elif df.shape[1] >= 2 and ('time' in inv_map or 'timestamp' in inv_map):
            non_time = [c for c in df.columns if col_map[c] not in ['time', 'timestamp']]
            if non_time:
                df.rename(columns={non_time[0]: 'amplitude'}, inplace=True)
        elif df.shape[1] == 1:
            df.columns = ['amplitude']
        data_start_line = 1

    # Apply VXP preprocessing if needed
    if file_path.lower().endswith('.vxp'):
        df = preprocess_vxp(df)

    return df, header_metadata, samples_per_second, scale_factor, data_start_line


class ImportMotionDialog(QDialog):
    """
    Dialog allowing the user to inspect imported motion curve parameters:
    - Sampling frequency (Samples_per_second)
    - Scale factor (amplitude multiplier)
    - Zero-baseline shift & invert options
    - Checkbox selection of multiple target axes
    """
    def __init__(self, parent_ui, file_path):
        parent_widget = parent_ui if isinstance(parent_ui, QWidget) else None
        super().__init__(parent_widget)
        self.parent_ui = parent_ui
        self.file_path = file_path

        self.setWindowTitle("Import Motion Curve (VXP / CSV)")
        self.setMinimumSize(580, 680)
        self.resize(620, 740)

        # Style dialog consistent with TRACE theme
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
            QDoubleSpinBox, QComboBox, QLineEdit {
                background-color: #ffffff;
                border: 1px solid #b0bec5;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QDoubleSpinBox:focus, QComboBox:focus, QLineEdit:focus {
                border: 2px solid #1976d2;
            }
            QCheckBox {
                font-size: 14px;
                font-weight: bold;
                padding: 4px;
            }
        """)

        # Parse file data
        self.raw_df, self.header_meta, detected_sps, detected_sf, self.start_line = parse_motion_file(file_path)
        
        if 'amplitude' not in self.raw_df.columns:
            # Fallback to column 0 if amplitude not explicitly named
            self.raw_amp = self.raw_df.iloc[:, 0].astype(float).values
        else:
            self.raw_amp = self.raw_df['amplitude'].astype(float).values

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 1. File Details GroupBox
        gb_file = QGroupBox("1. File Details", self)
        gb_file_lay = QGridLayout(gb_file)
        gb_file_lay.setContentsMargins(12, 12, 12, 12)
        gb_file_lay.setSpacing(8)

        lbl_fname_title = QLabel("File:", gb_file)
        lbl_fname_title.setStyleSheet("font-weight: bold;")
        self.edit_fname = QLineEdit(os.path.basename(file_path), gb_file)
        self.edit_fname.setReadOnly(True)
        self.edit_fname.setToolTip(file_path)

        gb_file_lay.addWidget(lbl_fname_title, 0, 0)
        gb_file_lay.addWidget(self.edit_fname, 0, 1)

        points_count = len(self.raw_amp)
        dur_initial = points_count / max(0.001, detected_sps)

        lbl_meta_info = QLabel(
            f"• <b>[Data] Start:</b> Line {self.start_line} &nbsp;|&nbsp; "
            f"• <b>Points:</b> {points_count:,} &nbsp;|&nbsp; "
            f"• <b>Duration:</b> {dur_initial:.2f} s<br>"
            f"• <b>Layout:</b> {', '.join(self.raw_df.columns[:5])}" + ("..." if len(self.raw_df.columns) > 5 else ""),
            gb_file
        )
        lbl_meta_info.setStyleSheet("color: #455a64; font-size: 13px; line-height: 1.4;")
        gb_file_lay.addWidget(lbl_meta_info, 1, 0, 1, 2)
        layout.addWidget(gb_file)

        # 2. Scaling & Timing Parameters GroupBox
        gb_params = QGroupBox("2. Scaling & Timing Parameters", self)
        gb_params_lay = QGridLayout(gb_params)
        gb_params_lay.setContentsMargins(12, 12, 12, 12)
        gb_params_lay.setSpacing(10)

        lbl_sps = QLabel("Samples per second (Hz):", gb_params)
        lbl_sps.setStyleSheet("font-weight: bold;")
        self.spin_sps = QDoubleSpinBox(gb_params)
        self.spin_sps.setRange(0.01, 10000.0)
        self.spin_sps.setValue(detected_sps)
        self.spin_sps.setDecimals(2)
        self.spin_sps.setMinimumHeight(38)
        self.spin_sps.setToolTip("Determines time step (dt = 1 / Hz). Extracted automatically from file header.")

        gb_params_lay.addWidget(lbl_sps, 0, 0)
        gb_params_lay.addWidget(self.spin_sps, 0, 1)

        lbl_sf = QLabel("Scale factor (Amplitude multiplier):", gb_params)
        lbl_sf.setStyleSheet("font-weight: bold;")
        self.spin_sf = QDoubleSpinBox(gb_params)
        self.spin_sf.setRange(-10000.0, 10000.0)
        self.spin_sf.setValue(detected_sf)
        self.spin_sf.setDecimals(3)
        self.spin_sf.setMinimumHeight(38)
        self.spin_sf.setToolTip("Multiplier applied to the raw amplitude data. Extracted automatically from file header.")

        gb_params_lay.addWidget(lbl_sf, 1, 0)
        gb_params_lay.addWidget(self.spin_sf, 1, 1)

        # Checkboxes for Invert and Zero-Baseline
        options_lay = QHBoxLayout()
        options_lay.setSpacing(15)

        self.cb_zero_baseline = QCheckBox("Shift minimum to 0 (Zero baseline)", gb_params)
        self.cb_zero_baseline.setChecked(True)
        self.cb_zero_baseline.setToolTip("Shifts curve so minimum amplitude starts at 0.0 mm (recommended to stay within physical phantom limits [0, 40 mm]).")

        self.cb_invert = QCheckBox("Invert amplitude (Flip)", gb_params)
        self.cb_invert.setChecked(False)
        self.cb_invert.setToolTip("Multiplies amplitude values by -1 to invert the breathing peaks.")

        options_lay.addWidget(self.cb_zero_baseline)
        options_lay.addWidget(self.cb_invert)
        gb_params_lay.addLayout(options_lay, 2, 0, 1, 2)

        # Live Preview Banner
        self.preview_card = QFrame(gb_params)
        self.preview_card.setStyleSheet("""
            QFrame {
                background-color: #e8f5e9;
                border: 1px solid #c8e6c9;
                border-radius: 6px;
                padding: 6px 10px;
            }
        """)
        card_lay = QVBoxLayout(self.preview_card)
        card_lay.setContentsMargins(6, 4, 6, 4)
        card_lay.setSpacing(2)

        self.lbl_preview_title = QLabel("Curve Output Preview:", self.preview_card)
        self.lbl_preview_title.setStyleSheet("font-weight: bold; color: #2e7d32; font-size: 13px; border: none; background: transparent;")
        self.lbl_preview_stats = QLabel("", self.preview_card)
        self.lbl_preview_stats.setStyleSheet("color: #1b5e20; font-size: 13px; font-weight: bold; border: none; background: transparent;")
        card_lay.addWidget(self.lbl_preview_title)
        card_lay.addWidget(self.lbl_preview_stats)

        gb_params_lay.addWidget(self.preview_card, 3, 0, 1, 2)
        layout.addWidget(gb_params)

        # 3. Target Device & Axes GroupBox
        gb_axes = QGroupBox("3. Target Device & Axes Selection", self)
        gb_axes_lay = QVBoxLayout(gb_axes)
        gb_axes_lay.setContentsMargins(12, 12, 12, 12)
        gb_axes_lay.setSpacing(10)

        # Device selection row
        dev_row = QHBoxLayout()
        dev_row.setSpacing(10)
        lbl_dev = QLabel("Device Type:", gb_axes)
        lbl_dev.setStyleSheet("font-weight: bold;")
        self.combo_device = QComboBox(gb_axes)
        self.combo_device.addItems(["Motion Platform", "Lung Phantom"])
        self.combo_device.setMinimumHeight(38)

        # Synchronize default device with planning tab
        current_dev = getattr(parent_ui, 'combo_device', None)
        if current_dev and current_dev.currentText() in ["Motion Platform", "Lung Phantom"]:
            self.combo_device.setCurrentText(current_dev.currentText())

        dev_row.addWidget(lbl_dev)
        dev_row.addWidget(self.combo_device, 1)
        gb_axes_lay.addLayout(dev_row)

        lbl_axes_desc = QLabel("Select which axes to apply this motion curve to (multiple axes selectable):", gb_axes)
        lbl_axes_desc.setStyleSheet("font-size: 13px; color: #555555;")
        gb_axes_lay.addWidget(lbl_axes_desc)

        # Checkboxes layout container
        self.axes_container = QWidget(gb_axes)
        self.axes_grid = QGridLayout(self.axes_container)
        self.axes_grid.setContentsMargins(5, 5, 5, 5)
        self.axes_grid.setSpacing(12)
        gb_axes_lay.addWidget(self.axes_container)

        # Convenience buttons row (Select All / Clear All)
        btn_sel_lay = QHBoxLayout()
        btn_sel_lay.setSpacing(10)
        self.btn_select_all = QPushButton("Select All", gb_axes)
        self.btn_select_all.setMinimumHeight(34)
        self.btn_select_all.setStyleSheet("font-size: 12px; font-weight: bold; padding: 4px 12px;")
        self.btn_clear_all = QPushButton("Clear All", gb_axes)
        self.btn_clear_all.setMinimumHeight(34)
        self.btn_clear_all.setStyleSheet("font-size: 12px; font-weight: bold; padding: 4px 12px;")

        self.btn_select_all.clicked.connect(self.select_all_axes)
        self.btn_clear_all.clicked.connect(self.clear_all_axes)

        btn_sel_lay.addWidget(self.btn_select_all)
        btn_sel_lay.addWidget(self.btn_clear_all)
        btn_sel_lay.addStretch()
        gb_axes_lay.addLayout(btn_sel_lay)

        layout.addWidget(gb_axes)

        # Bottom Button Row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_import_apply = QPushButton("Import & Apply to Planning", self)
        self.btn_import_apply.setMinimumHeight(46)
        self.btn_import_apply.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                font-weight: bold;
                font-size: 15px;
                border-radius: 6px;
                padding: 0px 20px;
            }
            QPushButton:hover {
                background-color: #1b5e20;
            }
        """)

        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.setMinimumHeight(46)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #78909c;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 6px;
                padding: 0px 15px;
            }
            QPushButton:hover {
                background-color: #546e7a;
            }
        """)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_import_apply)
        layout.addLayout(btn_layout)

        # Signals
        self.spin_sps.valueChanged.connect(self.update_preview)
        self.spin_sf.valueChanged.connect(self.update_preview)
        self.cb_zero_baseline.toggled.connect(self.update_preview)
        self.cb_invert.toggled.connect(self.update_preview)
        self.combo_device.currentTextChanged.connect(self.build_axis_checkboxes)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_import_apply.clicked.connect(self.on_apply)

        # Initial build
        self.build_axis_checkboxes()
        self.update_preview()

    def build_axis_checkboxes(self):
        """Populates the grid with checkboxes for all available axes of the selected device."""
        while self.axes_grid.count():
            item = self.axes_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.axis_checkboxes = {}
        device = self.combo_device.currentText()

        if device == "Motion Platform":
            axes = ["SI", "LAT", "AP", "Roll", "Pitch", "Yaw"]
            # Default SI checked for respiratory curve
            default_checked = {"SI"}
        else:
            axes = ["X", "Y", "Z"]
            default_checked = {"X"}

        for idx, ax_name in enumerate(axes):
            row = idx // 3
            col = idx % 3
            cb = QCheckBox(ax_name, self.axes_container)
            cb.setStyleSheet("font-weight: bold; font-size: 14px;")
            cb.setChecked(ax_name in default_checked)
            self.axes_grid.addWidget(cb, row, col)
            self.axis_checkboxes[ax_name] = cb

    def select_all_axes(self):
        for cb in self.axis_checkboxes.values():
            cb.setChecked(True)

    def clear_all_axes(self):
        for cb in self.axis_checkboxes.values():
            cb.setChecked(False)

    def update_preview(self):
        """Updates the live preview banner with computed amplitude and time bounds."""
        sps = max(0.001, self.spin_sps.value())
        sf = self.spin_sf.value()
        dur = len(self.raw_amp) / sps

        amp = self.raw_amp * sf
        if self.cb_invert.isChecked():
            amp = -amp
        if self.cb_zero_baseline.isChecked():
            amp = amp - np.nanmin(amp)

        raw_min = np.nanmin(self.raw_amp)
        raw_max = np.nanmax(self.raw_amp)
        min_val = np.nanmin(amp)
        max_val = np.nanmax(amp)
        p2p = max_val - min_val

        self.lbl_preview_stats.setText(
            f"Raw: [{raw_min:.2f}, {raw_max:.2f}]  ➜  "
            f"Output Range: [{min_val:.2f}, {max_val:.2f}] mm  (Peak-to-Peak: {p2p:.2f} mm)\n"
            f"Timeline: {dur:.2f} s  ({len(self.raw_amp):,} points @ {sps:.2f} Hz)"
        )

    def on_apply(self):
        """Processes the imported motion data and applies it to the Planning tab workspace."""
        selected_axes = [ax for ax, cb in self.axis_checkboxes.items() if cb.isChecked()]
        if not selected_axes:
            QMessageBox.warning(self, "No Axis Selected", "Please select at least one axis checkbox to apply the motion curve.")
            return

        sps = max(0.001, self.spin_sps.value())
        sf = self.spin_sf.value()
        do_invert = self.cb_invert.isChecked()
        do_zero_baseline = self.cb_zero_baseline.isChecked()
        device = self.combo_device.currentText()

        # 1. Compute time array based on Samples_per_second
        n_points = len(self.raw_amp)
        dt = 1.0 / sps
        time = np.arange(n_points) * dt
        timestamp = time * 1000.0

        # 2. Scale amplitude
        amp = self.raw_amp * sf
        if do_invert:
            amp = -amp
        if do_zero_baseline:
            amp = amp - np.nanmin(amp)

        # 3. Construct planning dataframe
        plan_df = pd.DataFrame({
            'timestamp': timestamp,
            'time': time
        })

        if device == "Motion Platform":
            all_axes = ['LAT', 'SI', 'AP', 'Roll', 'Pitch', 'Yaw']
        elif device == "Lung Phantom":
            all_axes = ['X', 'Y', 'Z']
        else:
            all_axes = list(selected_axes)

        for ax in all_axes:
            if ax in selected_axes:
                plan_df[ax] = amp
            else:
                plan_df[ax] = 0.0

        plan_df['Command'] = [""] * n_points

        # 4. Synchronize with Planning Workspace
        p = self.parent_ui
        if p is not None:
            if device == "Motion Platform":
                from fcn_plan.fcn_create import compute_motion_platform_actuators
                plan_df = compute_motion_platform_actuators(p, plan_df)
                p.dfEdit_motion_platform = plan_df
                p.dfEdit = p.dfEdit_motion_platform
                axis_cols = ['LAT', 'SI', 'AP', 'Roll', 'Pitch', 'Yaw', 'A', 'B', 'C', 'D', "'a", "'c", "'e", "'f"]
            elif device == "Lung Phantom":
                p.dfEdit_lung_phantom = plan_df
                p.dfEdit = p.dfEdit_lung_phantom
                axis_cols = ['X', 'Y', 'Z']
            else:
                p.dfEdit_other = plan_df
                p.dfEdit = p.dfEdit_other
                axis_cols = all_axes

            # Update device dropdowns
            if hasattr(p, 'combo_device'):
                p.combo_device.blockSignals(True)
                p.combo_device.setCurrentText(device)
                p.combo_device.blockSignals(False)
            if hasattr(p, 'combo_settings_device'):
                p.combo_settings_device.blockSignals(True)
                p.combo_settings_device.setCurrentText(device)
                p.combo_settings_device.blockSignals(False)
            if hasattr(p, 'settings_stack'):
                if device == "Lung Phantom":
                    p.settings_stack.setCurrentIndex(0)
                elif device == "Motion Platform":
                    p.settings_stack.setCurrentIndex(1)
                else:
                    p.settings_stack.setCurrentIndex(2)
            if hasattr(p, 'offset_rot_widget'):
                p.offset_rot_widget.setVisible(device == "Motion Platform")

            p.curve_origin = 'create'

            # Load into Planning Table
            from fcn_plan.fcn_create import loadTable_create, rebuild_axis_checkboxes, trigger_plot_update
            loadTable_create(p, p.dfEdit)

            # Rebuild graph checkboxes
            rebuild_axis_checkboxes(p, axis_cols)

            # Select only the target axes in checkboxes below the graph so plot is clean
            if hasattr(p, 'create_axis_checkboxes'):
                for ax_col, cb in p.create_axis_checkboxes.items():
                    cb.blockSignals(True)
                    cb.setChecked(ax_col in selected_axes)
                    cb.blockSignals(False)

            # Update curve option checkboxes on the left
            if hasattr(p, 'create_curve_axis_checkboxes'):
                for ax_col, cb in p.create_curve_axis_checkboxes.items():
                    cb.blockSignals(True)
                    cb.setChecked(ax_col in selected_axes)
                    cb.blockSignals(False)

            # Refresh graph
            trigger_plot_update(p)

        self.accept()
        QMessageBox.information(
            self.parent_ui if isinstance(self.parent_ui, QWidget) else None,
            "Import Successful",
            f"Successfully imported motion curve from:\n{os.path.basename(self.file_path)}\n\n"
            f"• Target Axes: {', '.join(selected_axes)}\n"
            f"• Points: {n_points:,} @ {sps:.2f} Hz\n"
            f"• Duration: {time[-1]:.2f} s\n"
            f"• Amplitude: [{np.nanmin(amp):.2f}, {np.nanmax(amp):.2f}] mm"
        )


def detect_file_format(file_path):
    """
    Detects whether a file is a G-code file or a Motion/Respiratory file (VXP/CSV).
    Returns 'gcode' or 'motion'.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.gcode', '.g', '.nc']:
        return 'gcode'
    if ext == '.vxp':
        return 'motion'

    # Sample beginning of file to detect format
    try:
        with open(file_path, 'r', errors='ignore') as f:
            sample_lines = [f.readline() for _ in range(60)]
    except Exception:
        return 'motion'

    content = "".join(sample_lines)
    if "[Data]" in content or "[Patient_Data]" in content or "Samples_per_second" in content:
        return 'motion'

    gcode_count = 0
    for line in sample_lines:
        clean = line.split(';', 1)[0].strip().upper()
        if not clean:
            continue
        first_word = clean.split()[0]
        if first_word.startswith(('G0', 'G1', 'G2', 'G3', 'G4', 'G28', 'G90', 'G91', 'G92', 'M')):
            gcode_count += 1

    if gcode_count >= 2:
        return 'gcode'
    return 'motion'


def unified_import_action(self, file_path=None):
    """
    Unified import entry point. Prompts the user with a file dialog supporting
    both G-code files (*.gcode, *.nc, *.g) and Motion files (*.vxp, *.csv, *.txt).
    Automatically identifies the file format and applies the appropriate workflow.
    Guarded against duplicate re-entrant calls.
    """
    if getattr(self, '_import_dialog_open', False):
        return
    self._import_dialog_open = True
    try:
        selected_filter = ""
        if file_path is None:
            # Default to Downloads folder if available
            start_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            if not os.path.exists(start_dir):
                start_dir = ""

            filters = (
                "All Supported Files (*.gcode *.g *.nc *.vxp *.csv *.txt);;"
                "G-code Files (*.gcode *.g *.nc);;"
                "Motion / Respiratory Files (*.vxp *.csv *.txt);;"
                "All Files (*)"
            )
            file_path, selected_filter = QFileDialog.getOpenFileName(
                self if isinstance(self, QWidget) else None,
                "Select File to Import (G-code or Motion Data)",
                start_dir,
                filters
            )

        if not file_path or not os.path.isfile(file_path):
            return

        # Ensure Planning tab is active
        if hasattr(self, 'tabModules') and self.tabModules.currentIndex() != 3:
            self.tabModules.setCurrentIndex(3)

        # Determine format based on user filter selection or content detection
        if "G-code Files" in selected_filter:
            fmt = 'gcode'
        elif "Motion / Respiratory Files" in selected_filter:
            fmt = 'motion'
        else:
            fmt = detect_file_format(file_path)

        if fmt == 'gcode':
            from fcn_plan.fcn_create import import_gcode_action
            # Temporarily release guard so import_gcode_action can execute cleanly
            self._import_dialog_open = False
            import_gcode_action(self, file_path=file_path)
        else:
            dialog = ImportMotionDialog(self, file_path)
            dialog.exec()
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            QMessageBox.critical(
                self if isinstance(self, QWidget) else None,
                "Import Error",
                f"An error occurred while importing file:\n{e}"
            )
        except Exception:
            pass
    finally:
        self._import_dialog_open = False


def open_import_motion_dialog(self, file_path=None):
    """
    Backward-compatible action invoked to import motion files or unified files.
    """
    unified_import_action(self, file_path=file_path)


def openCSVFile_BrCv(self):
    """Backward-compatible function connected to import button."""
    unified_import_action(self)


def preprocess_vxp(dataframe):
    """Function to remove/interpolate invalid data points (zero values)"""
    if 'amplitude' not in dataframe.columns:
        return dataframe

    # Remove empty rows and trailing rows with zero amplitude (end of measurement)
    dataframe = dataframe.dropna(axis=1, how='all')
    try:
        mask = dataframe['amplitude'].ne(0).iloc[::-1].cummax().iloc[::-1]
        dataframe = dataframe[mask]
        # Interpolate zero amplitude (invalid timestamp)
        dataframe.loc[dataframe['amplitude'] == 0, 'amplitude'] = np.nan
        dataframe['amplitude'] = dataframe['amplitude'].interpolate(method='linear', limit_direction='forward')
    except Exception:
        pass

    return dataframe


def addColumns(self, dataframe):
    """Function to add additional data to the dataframe, such as 
    time (in s), local maxima/minima, velocity/gradients"""

    unit_str = self.import_time_unit.currentText() if hasattr(self, 'import_time_unit') and self.import_time_unit is not None else 'ms'
    dataframe["time"] = pd.to_timedelta(dataframe["timestamp"], unit=unit_str)
    dataframe["time"] = dataframe["time"].dt.total_seconds()
    time_step = dataframe.loc[1, "time"] - dataframe.loc[0, "time"]

    if 'mark' in dataframe.columns:
        if 'P_min' not in dataframe['mark'].unique():
            df_copy = dataframe.copy()
            dataframe['mark'] = ''

            idxs = df_copy[df_copy["mark"] == "Z"].index
            for idx in idxs:
                start = max(0, idx - 15)
                end = min(len(dataframe) - 1, idx + 15)
                peak_idx = df_copy.loc[start:end, 'amplitude'].idxmax()
                dataframe.at[peak_idx, 'mark'] = 'P_max'

            idxs = dataframe[dataframe["mark"] == "P_max"].index
            for i in range(len(idxs)-1):
                min_idx = dataframe.loc[idxs[i]:idxs[i+1], "amplitude"].idxmin()
                dataframe.loc[min_idx, "mark"] = "P_min"
                dataframe.loc[idxs[i+1]-1, "mark"] = "E"

        if 'instance' not in dataframe:
            dataframe["instance"] = np.nan
            idxs = dataframe[dataframe["mark"] == "P_max"].index
            for i in range(len(idxs)-1):
                start = idxs[i]
                end = idxs[i+1]
                dataframe.loc[start:end-1, "instance"] = i+1

        if 'E' not in dataframe['mark'].unique():
            idxs = dataframe[dataframe["mark"] == "P_max"].index
            for i in idxs[1:]:
                dataframe.loc[i-1, 'mark'] = 'E'

    if "instance" in dataframe.columns and 'cycle time' not in dataframe.columns:
        dataframe["cycle time"] = np.nan

        idxs = dataframe[dataframe["mark"] == "P_max"].index
        for i in range(len(idxs)-1):
            counter = 0
            start = idxs[i]
            end = idxs[i+1]
            for j in range(start, end):
                dataframe.loc[j, "cycle time"] = counter
                counter += time_step

    if 'velocity' not in dataframe.columns or 'speed' not in dataframe.columns \
    or 'accel' not in dataframe.columns:
        dataframe = calcGrad(self, dataframe)

    return dataframe


def loadTable(self, dataframe, header_line):
    """Function to populate the table view widget"""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QHeaderView
    
    if getattr(self, 'curve_origin', 'create') == 'create':
        table = getattr(self, 'create_table_view', None)
    else:
        table = getattr(self, 'import_table_view', None)
    
    if table is None:
        return

    table.setUpdatesEnabled(False)
    table.blockSignals(True)
    table.clear()
    
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

    if header_line >= 0:
        headers = [header_units.get(col, col) for col in display_columns]
        table.setHorizontalHeaderLabels(headers)
    else:
        table.setHorizontalHeaderLabels([f'C{i+1}' for i in range(len(display_columns))])

    for row in range(dataframe.shape[0]):
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
            table.setItem(row, col, item)
            
    header = table.horizontalHeader()
    for col in range(table.columnCount() - 1):
        header.setSectionResizeMode(col, QHeaderView.Interactive)
        table.setColumnWidth(col, 120)
    if table.columnCount() > 0:
        header.setSectionResizeMode(table.columnCount() - 1, QHeaderView.Stretch)

    table.blockSignals(False)
    table.setUpdatesEnabled(True)

    if hasattr(self, "dfEdit"):
        delattr(self, "dfEdit")
    if hasattr(self, 'freq_scaled'):
        delattr(self, 'freq_scaled')
    if hasattr(self, 'lower_bound'):
        del self.lower_bound
    if hasattr(self, 'upper_bound'):
        del self.upper_bound
        
    self.Tab_index = 1


def calcGrad(self, df):
    """Calculate the velocity, speed and acceleration based on the time and amplitude columns."""
    col = "amplitude" if "amplitude" in df.columns else df.columns[1]
    vel = df[col].diff().shift(-1) / df["time"].diff().shift(-1)
    if len(vel) > 1:
        vel.iloc[-1] = vel.iloc[-2]
    df['velocity'] = vel

    speed = abs(vel) * 60
    df['speed'] = speed

    accel = vel.diff(-1) / df["time"].diff(-1)
    if len(accel) > 1:
        accel.iloc[-1] = accel.iloc[-2]
    df['accel'] = accel

    return df
