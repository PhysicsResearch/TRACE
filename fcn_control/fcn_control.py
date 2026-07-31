import json
import requests
from datetime import datetime
from PySide6.QtWidgets import QFileDialog, QMessageBox
from fcn_monitor.fcn_duet import get_clean_duet_ip, duet_request, duet_status_request


def log_to_duet_console(self, text, color=None):
    """
    Append a timestamped log entry into the Duet command console box.
    """
    if hasattr(self, 'duet_log_console') and self.duet_log_console is not None:
        t_str = datetime.now().strftime("%H:%M:%S")
        if color:
            self.duet_log_console.append(f"<span style='color: {color};'>[{t_str}] {text}</span>")
        else:
            self.duet_log_console.append(f"[{t_str}] {text}")
        sb = self.duet_log_console.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())


def is_axis_homed(self, axis_key):
    """
    Evaluates whether the given axis or platform degree of freedom is homed.
    """
    if not hasattr(self, 'ext_axes_homed') or not isinstance(self.ext_axes_homed, dict):
        return False

    h = self.ext_axes_homed
    key = str(axis_key).upper().strip()

    if key in ['XAXIS', 'LAT', 'X']:
        return bool(h.get('X', False) or (h.get("'e", False) and h.get("'f", False)))
    elif key in ['YAXIS', 'SI', 'Y']:
        return bool(h.get('Y', False) or (h.get("'a", False) and (h.get("'c", False) or h.get("'b", False))))
    elif key in ['ZAXIS', 'AP', 'Z']:
        return bool(h.get('Z', False) or (h.get('A', False) and h.get('B', False) and h.get('C', False) and h.get('D', False)))
    elif key in ['ROLL']:
        return bool((h.get('A', False) and h.get('B', False) and h.get('C', False) and h.get('D', False)) or h.get('U', False))
    elif key in ['PITCH']:
        return bool((h.get('A', False) and h.get('B', False) and h.get('C', False) and h.get('D', False)) or h.get('V', False))
    elif key in ['YAW']:
        return bool(h.get('W', False) or h.get('YAW', False))
    else:
        if axis_key in h:
            return bool(h[axis_key])
        if key in h:
            return bool(h[key])
        return False


def update_moving_button_styles(self):
    """
    Dynamically sets the background color of all motion buttons:
    - RED (#d32f2f) if the corresponding axis is NOT homed.
    - GREEN (#2e7d32) if the corresponding axis IS homed.
    """
    style_red = """
        QPushButton {
            background-color: #d32f2f;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 44px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover { background-color: #b71c1c; }
        QPushButton:pressed { background-color: #8e0000; padding-top: 3px; padding-left: 3px; }
    """

    style_green = """
        QPushButton {
            background-color: #2e7d32;
            color: white;
            font-weight: bold;
            font-size: 16px;
            min-height: 44px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover { background-color: #1b5e20; }
        QPushButton:pressed { background-color: #0d3c12; padding-top: 3px; padding-left: 3px; }
    """

    # 1. Platform & Lung Phantom jog buttons
    axis_keys = ['XAXIS', 'YAXIS', 'ZAXIS', 'ROLL', 'PITCH', 'YAW']
    for ax_key in axis_keys:
        homed = is_axis_homed(self, ax_key)
        target_style = style_green if homed else style_red

        for btn_prefix in ['MIN_', 'PLUS_']:
            for suffix in ['', '_LUNG']:
                btn = getattr(self, f"{btn_prefix}{ax_key}{suffix}", None)
                if btn is not None:
                    btn.setStyleSheet(target_style)

    # 2. Ind. Motors tab shared jog & move buttons
    selected_ext = getattr(self, 'selected_ext_axis', 'A')
    ext_homed = is_axis_homed(self, selected_ext)
    ext_style = style_green if ext_homed else style_red

    if hasattr(self, 'btn_ext_jog_min') and self.btn_ext_jog_min:
        self.btn_ext_jog_min.setStyleSheet(ext_style)
    if hasattr(self, 'btn_ext_jog_plus') and self.btn_ext_jog_plus:
        self.btn_ext_jog_plus.setStyleSheet(ext_style)
    if hasattr(self, 'btn_move_ext') and self.btn_move_ext:
        self.btn_move_ext.setStyleSheet(ext_style)

    # 3. Go to ... and Go to center buttons
    all_plat_homed = (is_axis_homed(self, 'XAXIS') and is_axis_homed(self, 'YAXIS') and is_axis_homed(self, 'ZAXIS'))
    if hasattr(self, 'btn_go_to') and self.btn_go_to:
        self.btn_go_to.setStyleSheet(style_green if all_plat_homed else style_red)
    if hasattr(self, 'btn_go_to_center') and self.btn_go_to_center:
        self.btn_go_to_center.setStyleSheet(style_green if all_plat_homed else style_red)


def refresh_external_axis_styles(self):
    """
    Evaluates and applies the 4 explicit visual states for all 11 axis selector buttons:
      1. Homed & Unselected -> Blue (#1565c0)
      2. Not Homed & Unselected -> Red (#d32f2f)
      3. Homed & Selected -> Light Green (#00e676)
      4. Not Homed & Selected -> Black (#1a1a1a)
    """
    selected = getattr(self, 'selected_ext_axis', 'A')
    if not hasattr(self, 'ext_axes_homed') or not isinstance(self.ext_axes_homed, dict):
        self.ext_axes_homed = {}

    style_homed_unselected = """
        QPushButton {
            background-color: #1565c0;
            color: #ffffff;
            font-weight: bold;
            font-size: 14px;
            min-height: 44px;
            border: 1px solid #0d47a1;
            border-radius: 6px;
        }
    """
    style_unhomed_unselected = """
        QPushButton {
            background-color: #d32f2f;
            color: #ffffff;
            font-weight: bold;
            font-size: 14px;
            min-height: 44px;
            border: 1px solid #b71c1c;
            border-radius: 6px;
        }
    """
    style_homed_selected = """
        QPushButton {
            background-color: #00e676;
            color: #000000;
            font-weight: bold;
            font-size: 14px;
            min-height: 44px;
            border: 2px solid #00c853;
            border-radius: 6px;
        }
    """
    style_unhomed_selected = """
        QPushButton {
            background-color: #1a1a1a;
            color: #ffffff;
            font-weight: bold;
            font-size: 14px;
            min-height: 44px;
            border: 2px solid #000000;
            border-radius: 6px;
        }
    """

    if hasattr(self, 'ext_axis_buttons') and self.ext_axis_buttons:
        for name, btn in self.ext_axis_buttons.items():
            is_sel = (name == selected)
            is_homed = self.ext_axes_homed.get(name, False)

            if is_sel and is_homed:
                btn.setStyleSheet(style_homed_selected)
                btn.setChecked(True)
            elif is_sel and not is_homed:
                btn.setStyleSheet(style_unhomed_selected)
                btn.setChecked(True)
            elif not is_sel and is_homed:
                btn.setStyleSheet(style_homed_unselected)
                btn.setChecked(False)
            else: # not is_sel and not is_homed
                btn.setStyleSheet(style_unhomed_unselected)
                btn.setChecked(False)

    update_moving_button_styles(self)


def select_external_axis(self, axis_name):
    """
    Selects active individual motor axis (A, B, C, D, X, Y, Z, 'a, 'c, 'e, 'f).
    Updates shared - and +, Move, and Home button labels.
    Refreshes axis button colors according to homing & selection states.
    """
    self.selected_ext_axis = axis_name

    if hasattr(self, 'btn_ext_jog_min') and self.btn_ext_jog_min:
        self.btn_ext_jog_min.setText(f"- Axis {axis_name}")
    if hasattr(self, 'btn_ext_jog_plus') and self.btn_ext_jog_plus:
        self.btn_ext_jog_plus.setText(f"+ Axis {axis_name}")
    if hasattr(self, 'btn_home_ext') and self.btn_home_ext:
        self.btn_home_ext.setText(f"Home Axis {axis_name}")

    refresh_external_axis_styles(self)


def home_selected_ext_axis(self):
    """
    Homes the currently selected individual motor axis (G28 {axis}).
    Handles lower case single quote prefixed axes ('a, 'c, 'e, 'f).
    """
    axis = getattr(self, 'selected_ext_axis', 'A')
    home(self, axis)
    if not hasattr(self, 'ext_axes_homed') or not isinstance(self.ext_axes_homed, dict):
        self.ext_axes_homed = {}
    self.ext_axes_homed[axis] = True
    refresh_external_axis_styles(self)


def step_selected_ext_axis(self, plus=True):
    """
    Steps the currently selected individual motor axis (A, B, C, D, X, Y, Z, 'a, 'c, 'e, 'f)
    using the global step size.
    """
    axis = getattr(self, 'selected_ext_axis', 'A')
    if not getattr(self, 'duet_connected', False):
        log_to_duet_console(self, f"Error: Cannot move axis {axis}. Not connected to Duet.", color="#ff3333")
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before moving axes.")
        return

    if not is_axis_homed(self, axis):
        log_to_duet_console(self, f"Error: Cannot move axis {axis}. Please home the axis first!", color="#ff3333")
        QMessageBox.warning(self, "Axis Not Homed", f"Cannot move axis {axis}.\nPlease home the axis first!")
        return
    step(self, axis, plus=plus)


def move_selected_ext_axis(self):
    """
    Moves the currently selected individual motor axis to target position.
    """
    axis = getattr(self, 'selected_ext_axis', 'A')
    if not getattr(self, 'duet_connected', False):
        log_to_duet_console(self, f"Error: Cannot move axis {axis}. Not connected to Duet.", color="#ff3333")
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before moving axes.")
        return

    if not is_axis_homed(self, axis):
        log_to_duet_console(self, f"Error: Cannot move axis {axis}. Please home the axis first!", color="#ff3333")
        QMessageBox.warning(self, "Axis Not Homed", f"Cannot move axis {axis}.\nPlease home the axis first!")
        return
    val_str = self.POS_DES_EXT.text().strip() if hasattr(self, 'POS_DES_EXT') else "0.0"
    try:
        val = float(val_str)
        send_cmd(self, "G90") # absolute positioning mode
        send_cmd(self, f"G1 {axis}{val:.4f} F600")
    except ValueError:
        pass


def set_global_step_size(self, val_str):
    """
    Sets global step size for all axis jog operations (0.1, 0.5, 1, 10 mm).
    Updates visual toggle styling on step buttons for touch screen clarity (42px height, 14px font).
    """
    try:
        self.global_step_val = float(val_str)
    except ValueError:
        self.global_step_val = 1.0

    active_style = """
        QPushButton {
            background-color: #a5d6a7;
            color: #1b5e20;
            font-weight: bold;
            font-size: 16px;
            min-height: 84px;
            border: 2px solid #2e7d32;
            border-radius: 6px;
            padding: 4px;
        }
    """
    inactive_style = """
        QPushButton {
            background-color: #e0e0e0;
            color: #37474f;
            font-weight: bold;
            font-size: 16px;
            min-height: 84px;
            border: 1px solid #b0bec5;
            border-radius: 6px;
            padding: 4px;
        }
        QPushButton:hover {
            background-color: #cfd8dc;
        }
    """

    if hasattr(self, 'step_buttons') and self.step_buttons:
        for key, btn in self.step_buttons.items():
            if key == str(val_str):
                btn.setChecked(True)
                btn.setStyleSheet(active_style)
            else:
                btn.setChecked(False)
                btn.setStyleSheet(inactive_style)


def update_duet_status_ui(self, data=None):
    """
    Fetch current status from Duet and update Home button colors & current position displays.
    Updates homed axes for Ind. Motors tab from Duet RRF status (object model move.axes or axesHomed).
    Supports capital (A, B, C, D) and single quote lower case ('a, 'c, 'e, 'f) motor axes.
    Only executes if self.duet_connected is True.
    """
    if not getattr(self, 'duet_connected', False):
        return

    if data is None:
        ip = get_clean_duet_ip(self)
        try:
            fetched_data, status_code = duet_status_request(self, ip, timeout=5)
            if status_code == 200:
                data = fetched_data
            else:
                return
        except Exception as e:
            print(f"Failed to update Duet status UI: {e}")
            log_to_duet_console(self, f"Status poll error: {e}")
            self.duet_connected = False
            update_connection_status_ui(self, connected=False)
            return

    try:
        if data is not None:
            coords = data.get('coords', {})
            axes_homed = coords.get('axesHomed', [])
            xyz = coords.get('xyz', [])

            # Update Cartesian Home button colors based on homed status (0=Not Homed -> GREEN, 1=Homed -> BLUE)
            axis_map = [('X', 0), ('Y', 1), ('Z', 2)]
            all_homed = True
            for name, idx in axis_map:
                btn = getattr(self, f'HOME_{name}', None)
                is_homed = (idx < len(axes_homed) and axes_homed[idx] == 1)
                if not is_homed:
                    all_homed = False
                if btn is not None:
                    if is_homed:
                        btn.setStyleSheet("""
                            QPushButton {
                                background-color: blue;
                                color: white;
                                font-weight: bold;
                                font-size: 16px;
                                min-height: 50px;
                                border-radius: 6px;
                            }
                            QPushButton:hover {
                                background-color: #1565c0;
                            }
                        """)
                    else:
                        btn.setStyleSheet("""
                            QPushButton {
                                background-color: #2e7d32;
                                color: white;
                                font-weight: bold;
                                font-size: 16px;
                                min-height: 50px;
                                border-radius: 6px;
                            }
                            QPushButton:hover {
                                background-color: #1b5e20;
                            }
                        """)

            # Update Home ALL button colors
            btn_all = getattr(self, 'HOME_ALL', None)
            if btn_all is not None:
                if all_homed:
                    btn_all.setStyleSheet("""
                        QPushButton {
                            background-color: blue;
                            color: white;
                            font-weight: bold;
                            font-size: 16px;
                            min-height: 50px;
                            border-radius: 6px;
                        }
                        QPushButton:hover {
                            background-color: #1565c0;
                        }
                    """)
                else:
                    btn_all.setStyleSheet("""
                        QPushButton {
                            background-color: #2e7d32;
                            color: white;
                            font-weight: bold;
                            font-size: 16px;
                            min-height: 50px;
                            border-radius: 6px;
                        }
                        QPushButton:hover {
                            background-color: #1b5e20;
                        }
                    """)

            btn_plat_all = getattr(self, 'HOME_ALL_PLATFORM', None)
            if btn_plat_all is not None:
                btn_plat_all.setMinimumHeight(45)
                btn_plat_all.setMinimumWidth(140)
                if all_homed:
                    btn_plat_all.setStyleSheet("""
                        QPushButton {
                            background-color: blue;
                            color: white;
                            font-weight: bold;
                            font-size: 16px;
                            min-height: 45px;
                            min-width: 140px;
                            border-radius: 6px;
                            border: none;
                        }
                        QPushButton:hover { background-color: #1a73e8; }
                        QPushButton:pressed { background-color: #0d47a1; padding-top: 3px; padding-left: 3px; }
                    """)
                else:
                    btn_plat_all.setStyleSheet("""
                        QPushButton {
                            background-color: #2e7d32;
                            color: white;
                            font-weight: bold;
                            font-size: 16px;
                            min-height: 45px;
                            min-width: 140px;
                            border-radius: 6px;
                            border: none;
                        }
                        QPushButton:hover { background-color: #1b5e20; }
                        QPushButton:pressed { background-color: #0d3c12; padding-top: 3px; padding-left: 3px; }
                    """)

            # Update current position displays for cartesian axes
            if len(xyz) >= 3:
                for axis_name, val in zip(['XAXIS', 'YAXIS', 'ZAXIS'], xyz[:3]):
                    pos_field = getattr(self, f'POS_CURR_{axis_name}', None)
                    if pos_field is not None:
                        pos_field.setText(f"{val:.3f}")

            # Update individual motor position displays & homed state
            if not hasattr(self, 'ext_axes_homed') or not isinstance(self.ext_axes_homed, dict):
                self.ext_axes_homed = {}
            if not hasattr(self, 'axis_min_limits') or not isinstance(self.axis_min_limits, dict):
                self.axis_min_limits = {}
            if not hasattr(self, 'axis_max_limits') or not isinstance(self.axis_max_limits, dict):
                self.axis_max_limits = {}

            # 1. Parse Object Model move.axes if available in RRF status response
            parsed_from_move_axes = False
            move_axes = data.get('move', {}).get('axes', [])
            if isinstance(move_axes, list) and len(move_axes) > 0:
                for ax_info in move_axes:
                    if isinstance(ax_info, dict):
                        let = str(ax_info.get('letter', '')).strip()
                        homed_val = ax_info.get('homed', ax_info.get('userHomed', 0))
                        is_h = (homed_val == 1 or homed_val is True)
                        if let:
                            self.ext_axes_homed[let] = is_h
                            self.ext_axes_homed[f"'{let}"] = is_h
                            self.axis_min_limits[let] = ax_info.get('min', 0.0)
                            self.axis_max_limits[let] = ax_info.get('max', 200.0)
                            self.axis_min_limits[f"'{let}"] = ax_info.get('min', 0.0)
                            self.axis_max_limits[f"'{let}"] = ax_info.get('max', 200.0)
                            parsed_from_move_axes = True

                            # Also update the current position display for this axis if it exists
                            # Note: The field can be named self.POS_CURR_A or self.POS_CURR_'a
                            field = getattr(self, f"POS_CURR_{let}", None)
                            if field is None:
                                field = getattr(self, f"POS_CURR_'{let}", None)
                            user_pos = ax_info.get('userPosition', 0.0)
                            if field is not None:
                                field.setText(f"{user_pos:.3f}")
                            if let == 'W' or let == 'w':
                                fy = getattr(self, "POS_CURR_YAW", None)
                                if fy is not None:
                                    fy.setText(f"{user_pos:.3f}")

            # 2. Map axesHomed array using exact TRACE RRF axis order (only as fallback if not parsed from move.axes)
            if not parsed_from_move_axes and isinstance(axes_homed, list) and len(axes_homed) > 0:
                axes_rrf_order = ['X', 'Y', 'Z', 'V', 'W', 'A', 'B', 'C', 'D', "'a", "'c", "'e", "'f"]
                for idx, ax_name in enumerate(axes_rrf_order):
                    if idx < len(axes_homed):
                        is_h = (axes_homed[idx] == 1)
                        self.ext_axes_homed[ax_name] = is_h
                        
                        # Fallback: update text fields too
                        field = getattr(self, f"POS_CURR_{ax_name}", None)
                        if field is not None and idx < len(xyz):
                            field.setText(f"{xyz[idx]:.3f}")
                        if ax_name == 'W':
                            fy = getattr(self, "POS_CURR_YAW", None)
                            if fy is not None and idx < len(xyz):
                                fy.setText(f"{xyz[idx]:.3f}")

            # Update position displays for Cartesian axes
            cart_letters = ['X', 'Y', 'Z']
            for idx, letter in enumerate(cart_letters):
                field = getattr(self, f'POS_CURR_{letter}', None)
                if field is not None and idx < len(xyz):
                    field.setText(f"{xyz[idx]:.3f}")

            # Calculate current Roll angle based on average A, D and B, C positions and lateral distance
            lat_dim = 100.0
            if hasattr(self, 'input_plat_lat') and self.input_plat_lat:
                try:
                    lat_dim = float(self.input_plat_lat.text().strip())
                except ValueError:
                    pass
            if lat_dim <= 0.0:
                lat_dim = 100.0

            curr_a = 0.0
            curr_b = 0.0
            curr_c = 0.0
            curr_d = 0.0

            if hasattr(self, 'POS_CURR_A') and self.POS_CURR_A:
                try:
                    curr_a = float(self.POS_CURR_A.text())
                except ValueError:
                    pass
            if hasattr(self, 'POS_CURR_B') and self.POS_CURR_B:
                try:
                    curr_b = float(self.POS_CURR_B.text())
                except ValueError:
                    pass
            if hasattr(self, 'POS_CURR_C') and self.POS_CURR_C:
                try:
                    curr_c = float(self.POS_CURR_C.text())
                except ValueError:
                    pass
            if hasattr(self, 'POS_CURR_D') and self.POS_CURR_D:
                try:
                    curr_d = float(self.POS_CURR_D.text())
                except ValueError:
                    pass

            h_ad = (curr_a + curr_d) / 2.0
            h_bc = (curr_b + curr_c) / 2.0
            diff_h = h_ad - h_bc

            import math
            current_roll_deg = math.degrees(math.atan2(diff_h, lat_dim))

            if hasattr(self, 'POS_CURR_ROLL') and self.POS_CURR_ROLL:
                self.POS_CURR_ROLL.setText(f"{current_roll_deg:.3f}")

            # Calculate current Pitch angle based on average A, B and C, D positions and transverse distance
            si_dim = 100.0
            if hasattr(self, 'input_plat_si') and self.input_plat_si:
                try:
                    si_dim = float(self.input_plat_si.text().strip())
                except ValueError:
                    pass
            if si_dim <= 0.0:
                si_dim = 100.0

            h_ab = (curr_a + curr_b) / 2.0
            h_cd = (curr_c + curr_d) / 2.0
            diff_h_pitch = h_ab - h_cd

            current_pitch_deg = math.degrees(math.atan2(diff_h_pitch, si_dim))

            if hasattr(self, 'POS_CURR_PITCH') and self.POS_CURR_PITCH:
                self.POS_CURR_PITCH.setText(f"{current_pitch_deg:.3f}")

            # Calculate current AP position (average of A, B, C, D actuator positions)
            h_ap = (curr_a + curr_b + curr_c + curr_d) / 4.0
            if hasattr(self, 'POS_CURR_ZAXIS') and self.POS_CURR_ZAXIS:
                self.POS_CURR_ZAXIS.setText(f"{h_ap:.3f}")

            # Calculate current LAT (average of 'e and 'f)
            curr_e = 0.0
            curr_f = 0.0
            f_e = getattr(self, "POS_CURR_e", getattr(self, "POS_CURR_'e", None))
            if f_e is not None:
                try:
                    curr_e = float(f_e.text())
                except ValueError:
                    pass
            f_f = getattr(self, "POS_CURR_f", getattr(self, "POS_CURR_'f", None))
            if f_f is not None:
                try:
                    curr_f = float(f_f.text())
                except ValueError:
                    pass
            h_lat = (curr_e + curr_f) / 2.0
            if hasattr(self, 'POS_CURR_XAXIS') and self.POS_CURR_XAXIS:
                self.POS_CURR_XAXIS.setText(f"{h_lat:.3f}")

            # Calculate current SI (average of 'a and 'c)
            curr_a_lo = 0.0
            curr_c_lo = 0.0
            f_a_lo = getattr(self, "POS_CURR_a", getattr(self, "POS_CURR_'a", None))
            if f_a_lo is not None:
                try:
                    curr_a_lo = float(f_a_lo.text())
                except ValueError:
                    pass
            f_c_lo = getattr(self, "POS_CURR_c", getattr(self, "POS_CURR_'c", None))
            if f_c_lo is not None:
                try:
                    curr_c_lo = float(f_c_lo.text())
                except ValueError:
                    pass
            h_si = (curr_a_lo + curr_c_lo) / 2.0
            if hasattr(self, 'POS_CURR_YAXIS') and self.POS_CURR_YAXIS:
                self.POS_CURR_YAXIS.setText(f"{h_si:.3f}")

            # Automatically synchronize current & target fields for all tabs (Platform & Lung Phantom)
            for ax_name in ['XAXIS', 'YAXIS', 'ZAXIS', 'ROLL', 'PITCH', 'YAW']:
                master_curr = getattr(self, f"POS_CURR_{ax_name}", None)
                for suffix in ['', '_LUNG']:
                    curr_f = getattr(self, f"POS_CURR_{ax_name}{suffix}", None)
                    des_f = getattr(self, f"POS_DES_{ax_name}{suffix}", None)
                    if curr_f is not None and master_curr is not None and curr_f != master_curr:
                        curr_f.setText(master_curr.text())
                    if curr_f is not None and des_f is not None and not des_f.hasFocus():
                        des_f.setText(curr_f.text())

            refresh_external_axis_styles(self)

    except Exception as e:
        print(f"Failed to update Duet status UI: {e}")
        log_to_duet_console(self, f"Status poll error: {e}")
        self.duet_connected = False
        update_connection_status_ui(self, connected=False)


def update_connection_status_ui(self, connected=False):
    """
    Updates the top bar and connection indicator:
    - RED and 'NOT CONNECTED' when disconnected.
    - GREEN and 'Connected' when connected.
    """
    status_text = "Connected" if connected else "NOT CONNECTED"

    # 1. Update Window Title
    if hasattr(self, 'setWindowTitle'):
        self.setWindowTitle(f"TRACE - {status_text}")

    # 2. Update connect_status widget
    if hasattr(self, 'connect_status') and self.connect_status:
        if hasattr(self.connect_status, 'setChecked'):
            self.connect_status.setChecked(connected)
            self.connect_status.setText(status_text)
            color_css = "color: #2e7d32;" if connected else "color: #d32f2f;"
            self.connect_status.setStyleSheet(f"""
                QRadioButton {{
                    font-weight: bold;
                    font-size: 17px;
                    padding: 6px 14px;
                    {color_css}
                }}
                QRadioButton::indicator {{ width: 20px; height: 20px; border-radius: 10px; }}
                QRadioButton::indicator:checked {{ background-color: #2e7d32; border: 1px solid #1b5e20; }}
                QRadioButton::indicator:unchecked {{ background-color: #d32f2f; border: 1px solid #b71c1c; }}
            """)
        else:
            self.connect_status.setText(status_text)
            bg_color = "#2e7d32" if connected else "#d32f2f"
            self.connect_status.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg_color};
                    color: white;
                    font-weight: bold;
                    font-size: 17px;
                    padding: 6px 20px;
                    border-radius: 6px;
                }}
            """)

    # 3. Update top_bar_frame container
    if hasattr(self, 'top_bar_frame') and self.top_bar_frame:
        bg_bar = "#e8f5e9" if connected else "#ffebee"
        border_bar = "#2e7d32" if connected else "#d32f2f"
        self.top_bar_frame.setStyleSheet(f"""
            QFrame#top_bar_frame {{
                background-color: {bg_bar};
                border: 2px solid {border_bar};
                border-radius: 8px;
            }}
        """)


def send_cmd(self, cmd=None):
    """
    Function to send GCODE command through DUET HTTP API.
    Logs sent command and Duet response into duet_log_console.
    """
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet first.")
        return

    ip = get_clean_duet_ip(self)

    if cmd is None:
        if hasattr(self, 'duet_command') and self.duet_command:
            cmd = self.duet_command.text().strip()
            self.duet_command.clear()
        else:
            cmd = ""

    if not cmd:
        return

    log_to_duet_console(self, f"Sent: {cmd}")
    url = f'http://{ip}/rr_gcode'

    try:
        response = duet_request(url, params={'gcode': cmd}, timeout=4)
        if response.status_code == 200:
            recv_txt = response.text.strip()
            log_to_duet_console(self, f"Recv: {recv_txt if recv_txt else 'OK (200)'}")
            self.duet_connected = True
            update_connection_status_ui(self, connected=True)
        else:
            log_to_duet_console(self, f"Error: HTTP {response.status_code} - Command '{cmd}' failed", color="#ff3333")
    except Exception as e:
        log_to_duet_console(self, f"Error: Failed to execute command '{cmd}': {e}", color="#ff3333")
        self.duet_connected = False
        update_connection_status_ui(self, connected=False)

    # Refresh status & button colors after command execution
    update_duet_status_ui(self)


def home(self, ax):
    """
    Function to call standard homing commands (G28) for cartesian & platform axes.
    Executes RRF macros (homex.g, homey.g, homez.g, homeall.g) on the Duet board.
    Supports single quote prefixed lower case axes ('a, 'c, 'e, 'f).
    """
    if ax in ['X', 'Y', 'Z']:
        send_cmd(self, f'G28 {ax}')
    elif ax in ['ROLL', 'Roll']:
        send_cmd(self, 'G28 U')
    elif ax in ['PITCH', 'Pitch']:
        send_cmd(self, 'G28 V')
    elif ax in ['YAW', 'Yaw']:
        send_cmd(self, 'G28 W')
    elif ax in ['ALL', 'all', 'All']:
        send_cmd(self, 'G28')
    else:
        send_cmd(self, f'G28 {ax}')


def step(self, ax, plus=True):
    """
    Function to move axes step-wise using the global step size selected by the user.
    Applies to all cartesian, platform (Roll, Pitch, Yaw), and individual motor axes (A, B, C, D, X, Y, Z, 'a, 'c, 'e, 'f).
    """
    if not getattr(self, 'duet_connected', False):
        log_to_duet_console(self, f"Error: Cannot move {ax}. Not connected to Duet.", color="#ff3333")
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before moving axes.")
        return

    if not is_axis_homed(self, ax):
        log_to_duet_console(self, f"Error: Cannot move {ax}. Please home the axis first!", color="#ff3333")
        QMessageBox.warning(self, "Axis Not Homed", f"Cannot move {ax}.\nPlease home the axis first!")
        return

    step_val = getattr(self, 'global_step_val', 1.0)
    if not plus:
        step_val *= -1
    
    # Define GCODE commands
    send_cmd(self, "G91") # set relative mode

    if ax == 'XAXIS':
        cmd = f"G1 'e{step_val:.4f} 'f{step_val:.4f} F600"
    elif ax == 'YAXIS':
        axis_y_lo = "'c"
        if hasattr(self, 'axis_max_limits') and ("b" in self.axis_max_limits or "'b" in self.axis_max_limits):
            axis_y_lo = "'b"
        cmd = f"G1 'a{step_val:.4f} {axis_y_lo}{step_val:.4f} F600"     
    elif ax == 'ZAXIS':
        cmd = f"G1 A{step_val:.4f} B{step_val:.4f} C{step_val:.4f} D{step_val:.4f} F600"
    elif ax in ['ROLL', 'Roll']:
        # Roll calculation using platform dimension LAT
        lat_dim = 100.0
        if hasattr(self, 'input_plat_lat') and self.input_plat_lat:
            try:
                lat_dim = float(self.input_plat_lat.text().strip())
            except ValueError:
                pass
        if lat_dim <= 0.0:
            lat_dim = 100.0

        import math
        theta_rad = math.radians(step_val)
        delta_z = (lat_dim / 2.0) * math.tan(theta_rad)

        curr_a = 0.0
        curr_b = 0.0
        curr_c = 0.0
        curr_d = 0.0
        
        if hasattr(self, 'POS_CURR_A') and self.POS_CURR_A:
            try:
                curr_a = float(self.POS_CURR_A.text())
            except ValueError:
                pass
        if hasattr(self, 'POS_CURR_B') and self.POS_CURR_B:
            try:
                curr_b = float(self.POS_CURR_B.text())
            except ValueError:
                pass
        if hasattr(self, 'POS_CURR_C') and self.POS_CURR_C:
            try:
                curr_c = float(self.POS_CURR_C.text())
            except ValueError:
                pass
        if hasattr(self, 'POS_CURR_D') and self.POS_CURR_D:
            try:
                curr_d = float(self.POS_CURR_D.text())
            except ValueError:
                pass

        # Get limits for A, B, C, D dynamically from Duet limits (enforcing min 0.2 mm, max 70.0 mm)
        limits_max = {}
        limits_min = {}
        for ax_name in ['A', 'B', 'C', 'D']:
            max_val = 70.0
            min_val = 0.2
            if hasattr(self, 'axis_max_limits') and self.axis_max_limits:
                max_val = min(self.axis_max_limits.get(ax_name, 70.0), 70.0)
            if hasattr(self, 'axis_min_limits') and self.axis_min_limits:
                min_val = max(self.axis_min_limits.get(ax_name, 0.2), 0.2)
            limits_max[ax_name] = max_val
            limits_min[ax_name] = min_val

        delta_A = delta_z
        delta_B = -delta_z
        delta_C = -delta_z
        delta_D = delta_z

        p_no_shift = {
            'A': curr_a + delta_A,
            'B': curr_b + delta_B,
            'C': curr_c + delta_C,
            'D': curr_d + delta_D
        }

        # Calculate shift range [s_min, s_max]
        s_min = max(limits_min[ax_name] - p_no_shift[ax_name] for ax_name in ['A', 'B', 'C', 'D'])
        s_max = min(limits_max[ax_name] - p_no_shift[ax_name] for ax_name in ['A', 'B', 'C', 'D'])

        if s_min > s_max:
            # Over-travel in both directions is impossible to resolve by shifting
            log_to_duet_console(self, f"Error: Roll rotation would exceed physical limits (Min: {min(limits_min.values()):.1f}, Max: {max(limits_max.values()):.1f} mm). Command blocked.", color="#ff3333")
            return

        # Determine the best shift
        if s_min <= 0.0 <= s_max:
            shift = 0.0
        elif s_min > 0.0:
            shift = s_min
            log_to_duet_console(self, f"Warning: Roll would drop actuator below minimum. Shifting AP up by {shift:.3f} mm.", color="#ff3333")
        else: # s_max < 0.0
            shift = s_max
            log_to_duet_console(self, f"Warning: Roll would exceed actuator maximum limit. Shifting AP down by {abs(shift):.3f} mm.", color="#ff3333")

        move_A = delta_A + shift
        move_B = delta_B + shift
        move_C = delta_C + shift
        move_D = delta_D + shift

        cmd = f"G1 A{move_A:.4f} B{move_B:.4f} C{move_C:.4f} D{move_D:.4f} F600"
    elif ax in ['PITCH', 'Pitch']:
        # Pitch calculation using platform dimension SI
        si_dim = 100.0
        if hasattr(self, 'input_plat_si') and self.input_plat_si:
            try:
                si_dim = float(self.input_plat_si.text().strip())
            except ValueError:
                pass
        if si_dim <= 0.0:
            si_dim = 100.0

        import math
        theta_rad = math.radians(step_val)
        delta_z = (si_dim / 2.0) * math.tan(theta_rad)

        curr_a = 0.0
        curr_b = 0.0
        curr_c = 0.0
        curr_d = 0.0
        
        if hasattr(self, 'POS_CURR_A') and self.POS_CURR_A:
            try:
                curr_a = float(self.POS_CURR_A.text())
            except ValueError:
                pass
        if hasattr(self, 'POS_CURR_B') and self.POS_CURR_B:
            try:
                curr_b = float(self.POS_CURR_B.text())
            except ValueError:
                pass
        if hasattr(self, 'POS_CURR_C') and self.POS_CURR_C:
            try:
                curr_c = float(self.POS_CURR_C.text())
            except ValueError:
                pass
        if hasattr(self, 'POS_CURR_D') and self.POS_CURR_D:
            try:
                curr_d = float(self.POS_CURR_D.text())
            except ValueError:
                pass

        # A B move together and C D move together
        delta_A = delta_z
        delta_B = delta_z
        delta_C = -delta_z
        delta_D = -delta_z

        limits_max = {}
        limits_min = {}
        for ax_name in ['A', 'B', 'C', 'D']:
            max_val = 70.0
            min_val = 0.2
            if hasattr(self, 'axis_max_limits') and self.axis_max_limits:
                max_val = min(self.axis_max_limits.get(ax_name, 70.0), 70.0)
            if hasattr(self, 'axis_min_limits') and self.axis_min_limits:
                min_val = max(self.axis_min_limits.get(ax_name, 0.2), 0.2)
            limits_max[ax_name] = max_val
            limits_min[ax_name] = min_val

        p_no_shift = {
            'A': curr_a + delta_A,
            'B': curr_b + delta_B,
            'C': curr_c + delta_C,
            'D': curr_d + delta_D
        }

        # Calculate shift range [s_min, s_max]
        s_min = max(limits_min[ax_name] - p_no_shift[ax_name] for ax_name in ['A', 'B', 'C', 'D'])
        s_max = min(limits_max[ax_name] - p_no_shift[ax_name] for ax_name in ['A', 'B', 'C', 'D'])

        if s_min > s_max:
            log_to_duet_console(self, f"Error: Pitch rotation would exceed physical limits (Min: {min(limits_min.values()):.1f}, Max: {max(limits_max.values()):.1f} mm). Command blocked.", color="#ff3333")
            return

        # Determine the best shift
        if s_min <= 0.0 <= s_max:
            shift = 0.0
        elif s_min > 0.0:
            shift = s_min
            log_to_duet_console(self, f"Warning: Pitch would drop actuator below minimum. Shifting AP up by {shift:.3f} mm.", color="#ff3333")
        else: # s_max < 0.0
            shift = s_max
            log_to_duet_console(self, f"Warning: Pitch would exceed actuator maximum limit. Shifting AP down by {abs(shift):.3f} mm.", color="#ff3333")

        move_A = delta_A + shift
        move_B = delta_B + shift
        move_C = delta_C + shift
        move_D = delta_D + shift

        cmd = f"G1 A{move_A:.4f} B{move_B:.4f} C{move_C:.4f} D{move_D:.4f} F600"
    elif ax in ['YAW', 'Yaw']:
        cmd = f"G1 W{step_val:.4f} F600"
    else:
        cmd = f"G1 {ax}{step_val:.4f} F600"

    send_cmd(self, cmd) # send command to move step


def move(self, ax):
    """
    Execute absolute move requests by calculating the relative delta from current position.
    This relative delta is applied to all paired actuators, preserving any existing rotation/offset.
    """
    if not getattr(self, 'duet_connected', False):
        log_to_duet_console(self, f"Error: Cannot move {ax}. Not connected to Duet.", color="#ff3333")
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before moving axes.")
        return

    if not is_axis_homed(self, ax):
        log_to_duet_console(self, f"Error: Cannot move {ax}. Please home the axis first!", color="#ff3333")
        QMessageBox.warning(self, "Axis Not Homed", f"Cannot move {ax}.\nPlease home the axis first!")
        return

    des_field = getattr(self, f"POS_DES_{ax}", None)
    if des_field is None or not des_field.text().strip():
        des_field = getattr(self, f"POS_DES_{ax}_LUNG", None)
    curr_field = getattr(self, f"POS_CURR_{ax}", None)
    if curr_field is None or not curr_field.text().strip():
        curr_field = getattr(self, f"POS_CURR_{ax}_LUNG", None)
    
    if des_field is None or curr_field is None:
        return

    try:
        target_val = float(des_field.text().strip())
        current_val = float(curr_field.text().strip())
    except ValueError:
        log_to_duet_console(self, f"Error: Invalid target or current position value for {ax}", color="#ff3333")
        return

    delta = target_val - current_val
    if abs(delta) < 0.0001:
        return

    # Generate and send command
    send_cmd(self, "G91") # relative positioning mode

    curr_a = 0.0
    curr_b = 0.0
    curr_c = 0.0
    curr_d = 0.0
    if hasattr(self, 'POS_CURR_A') and self.POS_CURR_A:
        try:
            curr_a = float(self.POS_CURR_A.text())
        except ValueError:
            pass
    if hasattr(self, 'POS_CURR_B') and self.POS_CURR_B:
        try:
            curr_b = float(self.POS_CURR_B.text())
        except ValueError:
            pass
    if hasattr(self, 'POS_CURR_C') and self.POS_CURR_C:
        try:
            curr_c = float(self.POS_CURR_C.text())
        except ValueError:
            pass
    if hasattr(self, 'POS_CURR_D') and self.POS_CURR_D:
        try:
            curr_d = float(self.POS_CURR_D.text())
        except ValueError:
            pass

    limits_max = {}
    limits_min = {}
    for ax_name in ['A', 'B', 'C', 'D']:
        max_val = 70.0
        min_val = 0.2
        if hasattr(self, 'axis_max_limits') and self.axis_max_limits:
            max_val = min(self.axis_max_limits.get(ax_name, 70.0), 70.0)
        if hasattr(self, 'axis_min_limits') and self.axis_min_limits:
            min_val = max(self.axis_min_limits.get(ax_name, 0.2), 0.2)
        limits_max[ax_name] = max_val
        limits_min[ax_name] = min_val

    if ax == 'XAXIS':
        cmd = f"G1 'e{delta:.4f} 'f{delta:.4f} F600"
        send_cmd(self, cmd)
    elif ax == 'YAXIS':
        axis_y_lo = "'c"
        if hasattr(self, 'axis_max_limits') and ("b" in self.axis_max_limits or "'b" in self.axis_max_limits):
            axis_y_lo = "'b"
        cmd = f"G1 'a{delta:.4f} {axis_y_lo}{delta:.4f} F600"
        send_cmd(self, cmd)
    elif ax == 'ZAXIS':
        # Check if moving by delta makes any actuator exceed limits
        new_A = curr_a + delta
        new_B = curr_b + delta
        new_C = curr_c + delta
        new_D = curr_d + delta

        min_new = min(new_A, new_B, new_C, new_D)
        max_new = max(new_A, new_B, new_C, new_D)

        if min_new < 0.2:
            log_to_duet_console(self, f"Error: AP movement blocked. Actuator would drop below minimum limit of 0.2 mm.", color="#ff3333")
            return
        if max_new > 70.0:
            log_to_duet_console(self, f"Error: AP movement blocked. Actuator would exceed maximum limit of 70.0 mm.", color="#ff3333")
            return

        cmd = f"G1 A{delta:.4f} B{delta:.4f} C{delta:.4f} D{delta:.4f} F600"
        send_cmd(self, cmd)
    elif ax in ['ROLL', 'Roll']:
        lat_dim = 100.0
        if hasattr(self, 'input_plat_lat') and self.input_plat_lat:
            try:
                lat_dim = float(self.input_plat_lat.text().strip())
            except ValueError:
                pass
        if lat_dim <= 0.0:
            lat_dim = 100.0

        import math
        theta_rad = math.radians(delta)
        delta_z = (lat_dim / 2.0) * math.tan(theta_rad)

        delta_A = delta_z
        delta_B = -delta_z
        delta_C = -delta_z
        delta_D = delta_z

        p_no_shift = {
            'A': curr_a + delta_A,
            'B': curr_b + delta_B,
            'C': curr_c + delta_C,
            'D': curr_d + delta_D
        }

        # Calculate shift range [s_min, s_max]
        s_min = max(limits_min[ax_name] - p_no_shift[ax_name] for ax_name in ['A', 'B', 'C', 'D'])
        s_max = min(limits_max[ax_name] - p_no_shift[ax_name] for ax_name in ['A', 'B', 'C', 'D'])

        if s_min > s_max:
            log_to_duet_console(self, f"Error: Roll rotation would exceed physical limits (Min: {min(limits_min.values()):.1f}, Max: {max(limits_max.values()):.1f} mm). Command blocked.", color="#ff3333")
            return

        # Determine the best shift
        if s_min <= 0.0 <= s_max:
            shift = 0.0
        elif s_min > 0.0:
            shift = s_min
            log_to_duet_console(self, f"Warning: Roll would drop actuator below minimum. Shifting AP up by {shift:.3f} mm.", color="#ff3333")
        else: # s_max < 0.0
            shift = s_max
            log_to_duet_console(self, f"Warning: Roll would exceed actuator maximum limit. Shifting AP down by {abs(shift):.3f} mm.", color="#ff3333")

        move_A = delta_A + shift
        move_B = delta_B + shift
        move_C = delta_C + shift
        move_D = delta_D + shift

        cmd = f"G1 A{move_A:.4f} B{move_B:.4f} C{move_C:.4f} D{move_D:.4f} F600"
        send_cmd(self, cmd)
    elif ax in ['PITCH', 'Pitch']:
        si_dim = 100.0
        if hasattr(self, 'input_plat_si') and self.input_plat_si:
            try:
                si_dim = float(self.input_plat_si.text().strip())
            except ValueError:
                pass
        if si_dim <= 0.0:
            si_dim = 100.0

        import math
        theta_rad = math.radians(delta)
        delta_z = (si_dim / 2.0) * math.tan(theta_rad)

        delta_A = delta_z
        delta_B = delta_z
        delta_C = -delta_z
        delta_D = -delta_z

        p_no_shift = {
            'A': curr_a + delta_A,
            'B': curr_b + delta_B,
            'C': curr_c + delta_C,
            'D': curr_d + delta_D
        }

        # Calculate shift range [s_min, s_max]
        s_min = max(limits_min[ax_name] - p_no_shift[ax_name] for ax_name in ['A', 'B', 'C', 'D'])
        s_max = min(limits_max[ax_name] - p_no_shift[ax_name] for ax_name in ['A', 'B', 'C', 'D'])

        if s_min > s_max:
            log_to_duet_console(self, f"Error: Pitch rotation would exceed physical limits (Min: {min(limits_min.values()):.1f}, Max: {max(limits_max.values()):.1f} mm). Command blocked.", color="#ff3333")
            return

        # Determine the best shift
        if s_min <= 0.0 <= s_max:
            shift = 0.0
        elif s_min > 0.0:
            shift = s_min
            log_to_duet_console(self, f"Warning: Pitch would drop actuator below minimum. Shifting AP up by {shift:.3f} mm.", color="#ff3333")
        else: # s_max < 0.0
            shift = s_max
            log_to_duet_console(self, f"Warning: Pitch would exceed actuator maximum limit. Shifting AP down by {abs(shift):.3f} mm.", color="#ff3333")

        move_A = delta_A + shift
        move_B = delta_B + shift
        move_C = delta_C + shift
        move_D = delta_D + shift

        cmd = f"G1 A{move_A:.4f} B{move_B:.4f} C{move_C:.4f} D{move_D:.4f} F600"
        send_cmd(self, cmd)
    else:
        cmd = f"G1 {ax}{delta:.4f} F600"
        send_cmd(self, cmd)


def save_configuration(self):
    ip = get_clean_duet_ip(self)
    folder = getattr(self, 'gcode_folder', '')
    lat_dim = self.input_plat_lat.text().strip() if hasattr(self, 'input_plat_lat') else '0.0'
    si_dim = self.input_plat_si.text().strip() if hasattr(self, 'input_plat_si') else '0.0'
    touch_mode = self.check_touchscreen.isChecked() if hasattr(self, 'check_touchscreen') and self.check_touchscreen is not None else False
    
    data = {
        'duet_ip_address': ip,
        'move_folder': folder,
        'platform_lat_dim': lat_dim,
        'platform_si_dim': si_dim,
        'touchscreen_mode': touch_mode
    }
    try:
        with open('configuration.json', 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving configuration.json: {e}")


def setDuetIP(self):
    """
    Called on code startup or when user explicitly presses the Connect button.
    Tests connection to Duet at IP address and sets self.duet_connected.
    No automatic background reconnect attempts will occur if self.duet_connected is False.
    """
    ip = get_clean_duet_ip(self)
    if hasattr(self, 'DuetIPAddress') and self.DuetIPAddress:
        self.DuetIPAddress.setText(ip)

    save_configuration(self)

    connected = False
    error_msg = ""

    try:
        data, status_code = duet_status_request(self, ip, timeout=6)
        if status_code == 200:
            connected = True
        else:
            error_msg = f"HTTP status {status_code}"
            log_to_duet_console(self, f"Connection check returned status {status_code}")
    except Exception as e:
        error_msg = str(e)
        print(f"Error testing connection to http://{ip}: {e}")
        log_to_duet_console(self, f"Connection error: {e}")

    self.duet_connected = connected
    update_connection_status_ui(self, connected=connected)

    if connected:
        log_to_duet_console(self, f"Connected to Duet at http://{ip}")
        
        # Determine machine name
        machine_name = None
        if isinstance(data, dict) and "name" in data:
            machine_name = str(data["name"]).strip()
        
        if not machine_name:
            try:
                r = requests.get(f"http://{ip}/rr_model?key=network", timeout=3)
                if r.status_code == 200:
                    r_json = r.json()
                    if isinstance(r_json, dict):
                        res_val = r_json.get("result", {})
                        if isinstance(res_val, dict) and "hostname" in res_val:
                            machine_name = str(res_val["hostname"]).strip()
            except Exception:
                pass
                
        if not machine_name:
            try:
                r = requests.get(f"http://{ip}/machine/status", timeout=3)
                if r.status_code == 200:
                    r_json = r.json()
                    if isinstance(r_json, dict):
                        network_val = r_json.get("network", {})
                        if isinstance(network_val, dict) and "hostname" in network_val:
                            machine_name = str(network_val["hostname"]).strip()
            except Exception:
                pass

        if machine_name:
            log_to_duet_console(self, f"Machine name: {machine_name}")
            if machine_name == "TRACE":
                if hasattr(self, 'tabWidget') and self.tabWidget and hasattr(self, 'tab_platform') and self.tab_platform:
                    self.tabWidget.setCurrentWidget(self.tab_platform)

        try:
            update_duet_status_ui(self)
        except Exception as ex:
            log_to_duet_console(self, f"Error: Connected, but failed to fetch status: {ex}", color="#ff3333")
    else:
        log_to_duet_console(self, f"Error: Failed to connect to Duet at http://{ip}. Details: {error_msg}", color="#ff3333")


def setPhOperFolder(self):
    """
    Function to set output folder for logs and files.
    """
    folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
    if folder:
        if hasattr(self, 'PhOperFolder') and self.PhOperFolder:
            self.PhOperFolder.setText(folder)


def go_to_desired_positions(self):
    """
    Retrieves all target positions and offsets from the UI,
    calculates full 3D rotation and translation kinematics for the actuators,
    checks if the resulting actuator positions are physically possible ([0.2, 70.0] mm),
    and sends the absolute moves to Duet.
    """
    if not getattr(self, 'duet_connected', False):
        log_to_duet_console(self, "Error: Not connected to Duet.", color="#ff3333")
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before moving axes.")
        return

    # Check homing state of platform axes
    for ax_check in ['XAXIS', 'YAXIS', 'ZAXIS', 'ROLL', 'PITCH', 'YAW']:
        if not is_axis_homed(self, ax_check):
            log_to_duet_console(self, f"Error: Cannot move platform. Axis {ax_check} is not homed! Please home first.", color="#ff3333")
            QMessageBox.warning(self, "Axis Not Homed", f"Cannot move platform.\nAxis {ax_check} is not homed.\nPlease home the axis first!")
            return

    # 1. Retrieve target translations & rotations
    try:
        t_lat = float(self.POS_DES_XAXIS.text().strip())
        t_si = float(self.POS_DES_YAXIS.text().strip())
        t_ap = float(self.POS_DES_ZAXIS.text().strip())
        t_roll = float(self.POS_DES_ROLL.text().strip())
        t_pitch = float(self.POS_DES_PITCH.text().strip())
        t_yaw = float(self.POS_DES_YAW.text().strip())
    except ValueError:
        log_to_duet_console(self, "Error: Invalid target translation or rotation value.", color="#ff3333")
        return

    # 2. Retrieve platform dimensions
    lat_dim = 100.0
    if hasattr(self, 'input_plat_lat') and self.input_plat_lat:
        try:
            lat_dim = float(self.input_plat_lat.text().strip())
        except ValueError:
            pass
    if lat_dim <= 0.0:
        lat_dim = 100.0

    si_dim = 100.0
    if hasattr(self, 'input_plat_si') and self.input_plat_si:
        try:
            si_dim = float(self.input_plat_si.text().strip())
        except ValueError:
            pass
    if si_dim <= 0.0:
        si_dim = 100.0

    # 3. Retrieve offset rotation center
    off_ap, off_lat, off_si = 0.0, 0.0, 0.0
    if hasattr(self, 'input_offset_ap') and self.input_offset_ap:
        try:
            off_ap = float(self.input_offset_ap.text().strip())
        except ValueError:
            pass
    if hasattr(self, 'input_offset_lat') and self.input_offset_lat:
        try:
            off_lat = float(self.input_offset_lat.text().strip())
        except ValueError:
            pass
    if hasattr(self, 'input_offset_si') and self.input_offset_si:
        try:
            off_si = float(self.input_offset_si.text().strip())
        except ValueError:
            pass

    # 4. Calculate target actuator positions A, B, C, D
    import math
    r = math.radians(t_roll)
    p = -math.radians(t_pitch)  # Negated to match step buttons convention
    y = math.radians(t_yaw)

    cos_r, sin_r = math.cos(r), math.sin(r)
    cos_p, sin_p = math.cos(p), math.sin(p)
    cos_y, sin_y = math.cos(y), math.sin(y)

    support_points = {
        'A': (-lat_dim / 2.0, -si_dim / 2.0, 0.0),
        'B': (lat_dim / 2.0, -si_dim / 2.0, 0.0),
        'C': (lat_dim / 2.0, si_dim / 2.0, 0.0),
        'D': (-lat_dim / 2.0, si_dim / 2.0, 0.0)
    }

    # Apply translation & rotation about offset center
    xc, yc, zc = 0.0, 0.0, off_ap
    target_z = {}
    for name, (px, py, pz) in support_points.items():
        x1 = px - xc
        y1 = py - yc
        z1 = pz - zc

        # Yaw (Z)
        x2 = cos_y * x1 - sin_y * y1
        y2 = sin_y * x1 + cos_y * y1
        z2 = z1

        # Roll (Y)
        x3 = x2 * cos_r + z2 * sin_r
        y3 = y2
        z3 = -x2 * sin_r + z2 * cos_r

        # Pitch (X)
        x4 = x3
        y4 = y3 * cos_p - z3 * sin_p
        z4 = y3 * sin_p + z3 * cos_p

        # Target absolute Z height
        target_z[name] = z4 + zc + t_ap

    # 5. Check physical limit violations for all actuators
    limits_max = {}
    limits_min = {}
    for ax_name in ['A', 'B', 'C', 'D']:
        max_val = 70.0
        min_val = 0.2
        if hasattr(self, 'axis_max_limits') and self.axis_max_limits:
            max_val = min(self.axis_max_limits.get(ax_name, 70.0), 70.0)
        if hasattr(self, 'axis_min_limits') and self.axis_min_limits:
            min_val = max(self.axis_min_limits.get(ax_name, 0.2), 0.2)
        limits_max[ax_name] = max_val
        limits_min[ax_name] = min_val

    out_of_bounds = []
    for name, val in target_z.items():
        if val < limits_min[name] or val > limits_max[name]:
            out_of_bounds.append((name, val, limits_min[name], limits_max[name]))

    if out_of_bounds:
        for name, val, mn, mx in out_of_bounds:
            log_to_duet_console(self, f"Error: Actuator {name} target position {val:.3f} mm is out of bounds [{mn:.1f}, {mx:.1f}] mm.", color="#ff3333")
        log_to_duet_console(self, "Error: Move command blocked.", color="#ff3333")
        return

    # 6. Generate and send movement commands
    send_cmd(self, "G90")  # Absolute positioning mode

    # Move horizontal axes
    axis_y_lo = "'c"
    if hasattr(self, 'axis_max_limits') and ("b" in self.axis_max_limits or "'b" in self.axis_max_limits):
        axis_y_lo = "'b"

    # Move all actuators to absolute positions
    cmd_horiz = f"G1 'e{t_lat:.4f} 'f{t_lat:.4f} 'a{t_si:.4f} {axis_y_lo}{t_si:.4f} F600"
    cmd_vert = f"G1 A{target_z['A']:.4f} B{target_z['B']:.4f} C{target_z['C']:.4f} D{target_z['D']:.4f} F600"
    
    send_cmd(self, cmd_horiz)
    send_cmd(self, cmd_vert)


def go_to_center(self):
    """
    Moves the platform to the physical center:
    Roll = 0, Pitch = 0, Yaw = 0
    Actuators A, B, C, D = 35.0 mm
    Horizontal axes ('e, 'f, 'a, 'c/'b) = 25.0 mm
    """
    if not getattr(self, 'duet_connected', False):
        log_to_duet_console(self, "Error: Not connected to Duet.", color="#ff3333")
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before moving axes.")
        return

    # Check homing state of platform axes
    for ax_check in ['XAXIS', 'YAXIS', 'ZAXIS', 'ROLL', 'PITCH', 'YAW']:
        if not is_axis_homed(self, ax_check):
            log_to_duet_console(self, f"Error: Cannot move platform to center. Axis {ax_check} is not homed! Please home first.", color="#ff3333")
            QMessageBox.warning(self, "Axis Not Homed", f"Cannot move to center.\nAxis {ax_check} is not homed.\nPlease home the axis first!")
            return

    # 1. Update target position input fields in UI to center values
    for ax, val in [('XAXIS', '25.000'), ('YAXIS', '25.000'), ('ZAXIS', '35.000'), ('ROLL', '0.000'), ('PITCH', '0.000'), ('YAW', '0.000')]:
        des_f = getattr(self, f"POS_DES_{ax}", None)
        if des_f is not None:
            des_f.setText(val)

    # 2. Send G-Code absolute center moves
    send_cmd(self, "G90")  # Absolute positioning mode

    # Determine y lower axis name
    axis_y_lo = "'c"
    if hasattr(self, 'axis_max_limits') and ("b" in self.axis_max_limits or "'b" in self.axis_max_limits):
        axis_y_lo = "'b"

    cmd_horiz = f"G1 'e25.0000 'f25.0000 'a25.0000 {axis_y_lo}25.0000 F600"
    cmd_vert = f"G1 A35.0000 B35.0000 C35.0000 D35.0000 F600"

    send_cmd(self, cmd_horiz)
    send_cmd(self, cmd_vert)
    log_to_duet_console(self, "Moving platform to center position: A, B, C, D = 35.0 mm; 'e, 'f, 'a, 'c/'b = 25.0 mm; Roll/Pitch/Yaw = 0 deg.")
