# Import required libraries and modules
import os
import time
import math
import requests
from datetime import datetime
from PySide6.QtWidgets import QMessageBox


def get_clean_duet_ip(self):
    """
    Utility to retrieve and clean Duet IP address (stripping http://, whitespace, slashes).
    """
    ip_raw = getattr(self, 'duet_ip', '192.168.0.1')
    if hasattr(self, 'DuetIPAddress') and self.DuetIPAddress and self.DuetIPAddress.text():
        ip_raw = self.DuetIPAddress.text()
    ip = ip_raw.strip().replace("http://", "").replace("https://", "").rstrip("/")
    if not ip:
        ip = "192.168.0.1"
    self.duet_ip = ip
    return ip


import threading

_thread_local = threading.local()

def get_shared_session():
    """
    Returns a thread-local persistent Session to ensure connection reuse (keep-alive)
    without multi-threaded socket access violations.
    """
    if not hasattr(_thread_local, 'session') or _thread_local.session is None:
        s = requests.Session()
        s.trust_env = False
        _thread_local.session = s
    return _thread_local.session


def duet_request(url, params=None, timeout=4):
    """
    Send an HTTP GET request to Duet, bypassing Windows system environment proxies
    to avoid false connection timeouts when connecting to local IP addresses.
    Uses a thread-local Session to reuse TCP connections (keep-alive) and prevent socket exhaustion.
    Automatically retries once with a fresh socket if an idle keep-alive connection is reset (WinError 10054).
    """
    session = get_shared_session()
    try:
        return session.get(url, params=params, timeout=timeout)
    except Exception:
        # Duet closed the idle keep-alive TCP connection. Recreate session & retry once with a fresh socket.
        if hasattr(_thread_local, 'session') and _thread_local.session:
            try:
                _thread_local.session.close()
            except Exception:
                pass
            _thread_local.session = None
        session = get_shared_session()
        return session.get(url, params=params, timeout=timeout)


def clear_status_plot(self):
    """
    Clears recorded plot history buffers and resets the real-time position plot.
    """
    self.status_plot_data = {
        't': [], 'X': [], 'Y': [], 'Z': [],
        'A': [], 'B': [], 'C': [], 'D': [],
        "'e": [], "'f": [], "'a": [], "'c": [],
        'Roll': [], 'Pitch': [], 'Yaw': []
    }
    self.status_t0 = None
    render_status_plot(self)


def render_status_plot(self):
    """
    Highly optimized updates of the Matplotlib plot using line reuse and draw_idle.
    Avoids calling clear() to prevent lag and CPU overload.
    """
    if not hasattr(self, 'ax_status') or self.ax_status is None:
        return

    plot_data = getattr(self, 'status_plot_data', None)
    if plot_data is None:
        return

    t_data = plot_data.get('t', [])
    if not t_data or len(t_data) == 0:
        return

    # Keep track of active line handles in self.status_plot_lines dict
    if not hasattr(self, 'status_plot_lines'):
        self.status_plot_lines = {}

    traces = [
        ('status_check_X', 'X', 'X (mm)', '#1e88e5'),
        ('status_check_Y', 'Y', 'Y (mm)', '#43a047'),
        ('status_check_Z', 'Z', 'Z (mm)', '#e53935'),
        ('status_check_A', 'A', 'A (mm)', '#8e24aa'),
        ('status_check_B', 'B', 'B (mm)', '#d81b60'),
        ('status_check_C', 'C', 'C (mm)', '#00acc1'),
        ('status_check_D', 'D', 'D (mm)', '#f4511e'),
        ('status_check_e', "'e", "'e (mm)", '#795548'),
        ('status_check_f', "'f", "'f (mm)", '#607d8b'),
        ('status_check_a', "'a", "'a (mm)", '#009688'),
        ('status_check_c', "'c", "'c (mm)", '#ffb300'),
        ('status_check_Roll', 'Roll', 'Roll (deg)', '#3f51b5'),
        ('status_check_Pitch', 'Pitch', 'Pitch (deg)', '#9e9d24'),
        ('status_check_Yaw', 'Yaw', 'Yaw (deg)', '#673ab7'),
        ('status_check_LAT', 'LAT', 'LAT (mm)', '#e65100'),
        ('status_check_AP', 'AP', 'AP (mm)', '#1b5e20'),
        ('status_check_SI', 'SI', 'SI (mm)', '#01579b')
    ]

    needs_legend_update = False
    min_x, max_x = t_data[0], t_data[-1]
    min_y, max_y = 1e9, -1e9

    for cb_name, key, label, color in traces:
        cb = getattr(self, cb_name, None)
        if cb is not None and cb.isChecked():
            data_list = plot_data.get(key, [])
            if len(data_list) == len(t_data):
                # Calculate Y limits for checked lines
                min_y = min(min_y, min(data_list))
                max_y = max(max_y, max(data_list))
                
                # Check if we already have a line created for this trace
                if key in self.status_plot_lines:
                    line = self.status_plot_lines[key]
                    line.set_data(t_data, data_list)
                    line.set_visible(True)
                else:
                    # Create the line
                    line, = self.ax_status.plot(t_data, data_list, label=label, color=color, linewidth=1.5)
                    self.status_plot_lines[key] = line
                    needs_legend_update = True
        else:
            # If the trace is unchecked, make the line invisible if it exists
            if key in self.status_plot_lines:
                if self.status_plot_lines[key].get_visible():
                    self.status_plot_lines[key].set_visible(False)
                    needs_legend_update = True

    # Remove stale lines that are not in the dictionary anymore
    stale_keys = []
    for key in list(self.status_plot_lines.keys()):
        if self.status_plot_lines[key] not in self.ax_status.lines:
            stale_keys.append(key)
    for key in stale_keys:
        self.status_plot_lines.pop(key, None)

    # Parse user-configured time window interval (default 60s)
    time_win = 60.0
    if hasattr(self, 'input_time_interval') and self.input_time_interval is not None:
        try:
            val = float(self.input_time_interval.text().strip())
            if val > 0:
                time_win = val
        except ValueError:
            time_win = 60.0

    # Dynamically update and auto-scroll live data respecting configured time window
    curr_xlim = self.ax_status.get_xlim()
    is_at_live_edge = (max_x - curr_xlim[1]) < 15.0 or curr_xlim[1] <= curr_xlim[0] or (curr_xlim[0] == 0.0 and curr_xlim[1] == 1.0)

    if is_at_live_edge:
        if max_x > 0:
            x_start = max(0.0, max_x - time_win)
            x_end = max_x if max_x > time_win else max(max_x, time_win)
            if x_start < x_end:
                self.ax_status.set_xlim(x_start, x_end)
        if min_y < max_y:
            pad = (max_y - min_y) * 0.1 if max_y != min_y else 1.0
            self.ax_status.set_ylim(min_y - pad, max_y + pad)

    # Rebuild legend containing ONLY currently visible checked line traces
    visible_handles = []
    visible_labels = []
    for cb_name, key, label, color in traces:
        if key in self.status_plot_lines:
            line = self.status_plot_lines[key]
            if line.get_visible():
                visible_handles.append(line)
                visible_labels.append(label)

    if visible_handles:
        self.ax_status.legend(visible_handles, visible_labels, loc='upper right', fontsize=10, ncol=2)
    else:
        leg = self.ax_status.get_legend()
        if leg is not None:
            leg.remove()

    self.fig_status.tight_layout()
    if hasattr(self, 'statusCanvas') and self.statusCanvas is not None:
        self.statusCanvas.draw_idle()


def clear_status_plot_data(self):
    """
    Clears all cached plot data and resets the Matplotlib plot.
    """
    self.status_plot_data = {
        't': [], 'X': [], 'Y': [], 'Z': [],
        'A': [], 'B': [], 'C': [], 'D': [],
        "'e": [], "'f": [], "'a": [], "'c": [],
        'Roll': [], 'Pitch': [], 'Yaw': []
    }
    if hasattr(self, 'status_plot_lines'):
        self.status_plot_lines.clear()
    if hasattr(self, 'ax_status') and self.ax_status is not None:
        self.ax_status.clear()
        self.ax_status.set_xlabel("Time (s)", fontsize=13, fontweight='bold')
        self.ax_status.set_ylabel("Position (mm / deg)", fontsize=13, fontweight='bold')
        self.ax_status.tick_params(axis='both', which='major', labelsize=11)
        self.ax_status.grid(True, linestyle=":", alpha=0.6)
    if hasattr(self, 'statusCanvas') and self.statusCanvas is not None:
        self.statusCanvas.draw_idle()


def log_data_point(self, t, x, y, z):
    """
    Writes live position and time data to an auto-named log file log_HH_MM_SS_.txt
    inside the selected output folder (default Desktop).
    """
    if not hasattr(self, 'active_log_file') or self.active_log_file is None:
        folder = self.PhOperFolder.text().strip() if hasattr(self, 'PhOperFolder') and self.PhOperFolder and self.PhOperFolder.text() else os.path.join(os.path.expanduser("~"), "Desktop")
        
        if not os.path.exists(folder):
            try:
                os.makedirs(folder, exist_ok=True)
            except Exception:
                folder = os.path.join(os.path.expanduser("~"), "Desktop")

        now_str = datetime.now().strftime("%H_%M_%S")
        filename = f"log_{now_str}_.txt"
        filepath = os.path.join(folder, filename)

        try:
            f = open(filepath, "a", encoding="utf-8")
            f.write("Time_s,Pos_X_mm,Pos_Y_mm,Pos_Z_mm\n")
            self.active_log_file = f
            self.active_log_filepath = filepath
            print(f"Started recording data log to file: {filepath}")
        except Exception as e:
            print(f"Failed to create data log file {filepath}: {e}")
            return

    try:
        self.active_log_file.write(f"{t:.2f},{x:.3f},{y:.3f},{z:.3f}\n")
        self.active_log_file.flush()
    except Exception as e:
        print(f"Error writing to data log file: {e}")


def close_data_log_file(self):
    """
    Closes the active log file handle when recording is unchecked or when printer becomes Idle.
    """
    if hasattr(self, 'active_log_file') and self.active_log_file is not None:
        try:
            self.active_log_file.close()
            print(f"Closed data log file: {getattr(self, 'active_log_filepath', '')}")
        except Exception:
            pass
        self.active_log_file = None
        self.active_log_filepath = None


def update_status_tab_dashboard(self):
    """
    Polls rr_status?type=3 from Duet ONLY if self.duet_connected is True.
    Does NOT attempt periodic background reconnects when disconnected.
    Updates all fields on the Status tab dashboard:
    - Status Badge (Printing, Idle, Paused, Homing)
    - Print Progress Bar (% fractionPrinted)
    - Print Duration & Time Remaining
    - Tool Positions (X, Y, Z)
    - Speeds (Requested vs Top Speed)
    - Sensors (Z-Probe, Vin, MCU Temp)
    - Real-Time Position Plotting & Logging
    """
    # Only poll if currently connected (prevents continuous background reconnect attempts)
    if not getattr(self, 'duet_connected', False):
        return


    if not hasattr(self, 'statusBadgeLabel') or self.statusBadgeLabel is None:
        return

    ip = get_clean_duet_ip(self)
    try:
        data, status_code = duet_status_request(self, ip, timeout=5)
        if status_code != 200:
            self.duet_connected = False
            from fcn_control.fcn_control import update_connection_status_ui
            update_connection_status_ui(self, connected=False)
            return

        # Update Control tab UI with the fetched status data (positions, home button states, etc.)
        try:
            from fcn_control.fcn_control import update_duet_status_ui
            update_duet_status_ui(self, data=data)
        except Exception as ex:
            print(f"Error updating Control UI from status poll: {ex}")

        # Poll /rr_reply for Duet messages (e.g. M117, macro responses, 'waiting for radiation')
        try:
            res_reply = duet_request(f'http://{ip}/rr_reply', timeout=2)
            if res_reply.status_code == 200:
                reply_str = res_reply.text.strip()
                if reply_str and reply_str != getattr(self, '_last_duet_reply', ''):
                    self._last_duet_reply = reply_str
                    if hasattr(self, 'statusDuetMessage') and self.statusDuetMessage:
                        self.statusDuetMessage.setText(reply_str)
                    from fcn_control.fcn_control import log_to_duet_console
                    log_to_duet_console(self, f"Duet Message: {reply_str}", color="#00acc1")
        except Exception:
            pass

        # Check for message payload fields in status response (e.g. RRF object model displayMessage/message)
        om_msg = None
        if isinstance(data, dict):
            om_msg = data.get("displayMessage") or data.get("message") or data.get("msg")
            if not om_msg and "state" in data and isinstance(data["state"], dict):
                om_msg = data["state"].get("displayMessage") or data["state"].get("message")
        if om_msg and isinstance(om_msg, str) and om_msg.strip():
            clean_om = om_msg.strip()
            if clean_om != getattr(self, '_last_duet_reply', ''):
                self._last_duet_reply = clean_om
                if hasattr(self, 'statusDuetMessage') and self.statusDuetMessage:
                    self.statusDuetMessage.setText(clean_om)
                from fcn_control.fcn_control import log_to_duet_console
                log_to_duet_console(self, f"Duet Message: {clean_om}", color="#00acc1")

        # 1. Status Badge
        status_code = data.get("status", "I")
        self.duet_status_code = status_code
        status_map = {
            "I": ("Idle", "#2196f3"),        # Blue
            "P": ("Running", "#4caf50"),    # Green
            "S": ("Paused", "#ff9800"),      # Orange
            "H": ("Homing", "#fbc02d"),      # Yellow
            "B": ("Busy", "#ff5722"),        # Deep Orange
            "C": ("Configuring", "#78909c"), # Grey
            "M": ("Simulating", "#9c27b0"),  # Purple
            "R": ("Resuming", "#4caf50"),    # Green
        }
        status_text, bg_color = status_map.get(status_code, (status_code, "#2196f3"))
        
        self.statusBadgeLabel.setText(status_text)
        self.statusBadgeLabel.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 8px;
                padding: 3px 10px;
            }}
        """)

        # 2. Speeds (Requested vs Top Speed)
        speeds = data.get("speeds", {})
        req_spd = speeds.get("requested", 0.0)
        top_spd = speeds.get("top", 0.0)

        if hasattr(self, 'statusReqSpeed') and self.statusReqSpeed:
            self.statusReqSpeed.setText(f"Req: {req_spd:.1f}")
        if hasattr(self, 'statusTopSpeed') and self.statusTopSpeed:
            self.statusTopSpeed.setText(f"Top: {top_spd:.1f}")

        # 3. Print Progress & Time
        fraction = data.get("fractionPrinted", 0.0)
        if hasattr(self, 'printProgressBar') and self.printProgressBar:
            self.printProgressBar.setValue(int(fraction))

        print_dur = data.get("printDuration", 0.0)
        time_left = data.get("timesLeft", {}).get("file", 0.0)

        def format_sec(sec):
            if not sec or sec <= 0:
                return "--:--:--"
            m, s = divmod(int(sec), 60)
            h, m = divmod(m, 60)
            return f"{h:02d}:{m:02d}:{s:02d}"

        if hasattr(self, 'labelPrintDuration') and self.labelPrintDuration:
            self.labelPrintDuration.setText(f"Print Duration: {format_sec(print_dur)}")
        if hasattr(self, 'labelTimeRemaining') and self.labelTimeRemaining:
            self.labelTimeRemaining.setText(f"Time Remaining: {format_sec(time_left)}")

        # 4. Sensors (Z-Probe)
        probe = data.get("sensors", {}).get("probeValue", 0)
        if hasattr(self, 'statusProbe') and self.statusProbe:
            self.statusProbe.setText(f"Probe: {probe}")
            
        # Auto-release on trigger check: if paused (S), checkbox checked, and probe > 500, auto-resume
        if status_code == 'S':
            check_auto = getattr(self, 'check_auto_release', None)
            if check_auto is not None and check_auto.isChecked() and probe > 500:
                self.duet_status_code = 'R'  # Prevent double triggers
                pause_continue_GCODE(self, pause=False)

        # Auto pause check: if active (not paused 'S' or idle 'I'), checkbox checked, and probe == 0, auto-pause
        if status_code not in ['S', 'I']:
            check_pause = getattr(self, 'check_auto_pause', None)
            if check_pause is not None and check_pause.isChecked() and probe == 0:
                self.duet_status_code = 'S'  # Prevent double triggers
                from fcn_control.fcn_control import log_to_duet_console
                log_to_duet_console(self, "Auto pause triggered: Z-probe is 0. Pausing GCODE execution.", color="#ff9800")
                pause_continue_GCODE(self, pause=True)

        params = data.get("params", {})
        speed_factor = params.get("speedFactor", 100.0)
        self.status_speed_factor = float(speed_factor)
        if hasattr(self, 'labelSf') and self.labelSf and not self.labelSf.hasFocus():
            if speed_factor % 1 == 0:
                self.labelSf.setText(f"{int(speed_factor)}%")
            else:
                self.labelSf.setText(f"{speed_factor:.3f}%")

        # 5. Render graph update every second
        if status_code != "I" and not getattr(self, 'status_stopped', False):
            render_status_plot(self)
        else:
            close_data_log_file(self)

    except Exception as e:
        print(f"Error updating status tab dashboard: {e}")
        self.duet_connected = False
        from fcn_control.fcn_control import update_connection_status_ui
        update_connection_status_ui(self, connected=False)


def get_positions_only_fast(self, ip):
    """
    Highly optimized request to fetch only axes positions (10ms polling).
    Uses RRF3 /rr_model?key=move.axes or falls back to legacy /rr_status?type=2.
    """
    # 1. RRF3 Model Path (lightweight key query)
    try:
        url = f"http://{ip}/rr_model?key=move.axes"
        response = duet_request(url, timeout=0.8)
        if response.status_code == 200:
            axes_list = response.json().get("result", [])
            if isinstance(axes_list, list) and axes_list:
                axis_positions = {}
                for ax in axes_list:
                    if isinstance(ax, dict) and "letter" in ax:
                        let = str(ax["letter"]).strip()
                        user_pos = ax.get("userPosition", 0.0)
                        axis_positions[let] = user_pos
                        axis_positions[let.lower()] = user_pos
                        axis_positions[f"'{let.lower()}"] = user_pos
                return axis_positions
    except Exception:
        pass

    # 2. Legacy /rr_status?type=2 Fallback
    try:
        url_legacy = f"http://{ip}/rr_status?type=2"
        response_legacy = duet_request(url_legacy, timeout=0.8)
        if response_legacy.status_code == 200:
            data = response_legacy.json()
            xyz = data.get("coords", {}).get("xyz", [0.0, 0.0, 0.0])
            axis_positions = {
                'X': xyz[0] if len(xyz) > 0 else 0.0,
                'Y': xyz[1] if len(xyz) > 1 else 0.0,
                'Z': xyz[2] if len(xyz) > 2 else 0.0,
            }
            axes_rrf_order = ['X', 'Y', 'Z', 'V', 'W', 'A', 'B', 'C', 'D', "'a", "'c", "'e", "'f"]
            for idx, ax_name in enumerate(axes_rrf_order):
                if idx < len(xyz):
                    axis_positions[ax_name] = xyz[idx]
            return axis_positions
    except Exception:
        pass

    return None


def update_status_fast(self):
    """
    Fast status loop (runs every 10ms).
    Fetches only the user positions from the Duet, updates the status position labels,
    logs data points to text files (if recording), and appends data to plot buffers.
    Does NOT call render_status_plot (graph redraw throttled to 1s in slow timer).
    """
    if not getattr(self, 'duet_connected', False):
        return
    if getattr(self, 'status_stopped', False):
        return
    status_code = getattr(self, 'duet_status_code', 'I')
    if status_code not in ["P", "S", "R", "M"]:
        return

    ip = get_clean_duet_ip(self)
    try:
        axis_positions = get_positions_only_fast(self, ip)
        if not axis_positions:
            return

        # Ensure we have defaults for all required axes
        for ax in ['X', 'Y', 'Z', 'A', 'B', 'C', 'D', "'e", "'f", "'a", "'c", 'W', 'V']:
            if ax not in axis_positions:
                axis_positions[ax] = 0.0

        # Update the UI labels
        x_val = axis_positions['X']
        y_val = axis_positions['Y']
        z_val = axis_positions['Z']
        if hasattr(self, 'statusPosX') and self.statusPosX:
            self.statusPosX.setText(f"X {x_val:.2f}")
        if hasattr(self, 'statusPosY') and self.statusPosY:
            self.statusPosY.setText(f"Y {y_val:.2f}")
        if hasattr(self, 'statusPosZ') and self.statusPosZ:
            self.statusPosZ.setText(f"Z {z_val:.2f}")

        for axis_name in ['A', 'B', 'C', 'D']:
            lbl = getattr(self, f'statusPos{axis_name}', None)
            if lbl is not None:
                lbl.setText(f"{axis_name} {axis_positions[axis_name]:.2f}")

        for axis_name, raw_name in [('e', "'e"), ('f', "'f"), ('a', "'a"), ('c', "'c")]:
            lbl = getattr(self, f'statusPos_{axis_name}', None)
            if lbl is not None:
                lbl.setText(f"{raw_name} {axis_positions[raw_name]:.2f}")

        # Calculate Roll & Pitch
        lat_dim = 100.0
        if hasattr(self, 'input_plat_lat') and self.input_plat_lat:
            try: lat_dim = float(self.input_plat_lat.text().strip())
            except ValueError: pass
        if lat_dim <= 0.0: lat_dim = 100.0

        si_dim = 100.0
        if hasattr(self, 'input_plat_si') and self.input_plat_si:
            try: si_dim = float(self.input_plat_si.text().strip())
            except ValueError: pass
        if si_dim <= 0.0: si_dim = 100.0

        curr_a = axis_positions['A']
        curr_b = axis_positions['B']
        curr_c = axis_positions['C']
        curr_d = axis_positions['D']

        h_ad = (curr_a + curr_d) / 2.0
        h_bc = (curr_b + curr_c) / 2.0
        diff_h = h_ad - h_bc
        current_roll = math.degrees(math.atan2(diff_h, lat_dim))

        h_ab = (curr_a + curr_b) / 2.0
        h_cd = (curr_c + curr_d) / 2.0
        diff_h_pitch = h_ab - h_cd
        current_pitch = math.degrees(math.atan2(diff_h_pitch, si_dim))
        
        current_yaw = axis_positions['W']

        # Calculate LAT, AP, SI
        curr_lower_e = axis_positions.get("'e", 0.0)
        curr_lower_f = axis_positions.get("'f", 0.0)
        current_lat = (curr_lower_e + curr_lower_f) / 2.0

        curr_lower_a = axis_positions.get("'a", 0.0)
        axis_y_lo_name = "'c"
        if hasattr(self, 'axis_max_limits') and ("b" in self.axis_max_limits or "'b" in self.axis_max_limits):
            axis_y_lo_name = "'b"
        curr_lower_y_lo = axis_positions.get(axis_y_lo_name, axis_positions.get("'c", 0.0))
        current_si = (curr_lower_a + curr_lower_y_lo) / 2.0

        current_ap = (curr_a + curr_b + curr_c + curr_d) / 4.0

        if hasattr(self, 'statusPosRoll') and self.statusPosRoll:
            self.statusPosRoll.setText(f"Roll {current_roll:.2f}")
        if hasattr(self, 'statusPosPitch') and self.statusPosPitch:
            self.statusPosPitch.setText(f"Pitch {current_pitch:.2f}")
        if hasattr(self, 'statusPosYaw') and self.statusPosYaw:
            self.statusPosYaw.setText(f"Yaw {current_yaw:.2f}")

        # Append to plot data
        if not hasattr(self, 'status_plot_data') or self.status_plot_data is None or 'A' not in self.status_plot_data:
            self.status_plot_data = {
                't': [], 'X': [], 'Y': [], 'Z': [],
                'A': [], 'B': [], 'C': [], 'D': [],
                "'e": [], "'f": [], "'a": [], "'c": [],
                'Roll': [], 'Pitch': [], 'Yaw': [],
                'LAT': [], 'AP': [], 'SI': []
            }

        t_now = time.time()
        if not hasattr(self, 'status_t0') or self.status_t0 is None:
            self.status_t0 = t_now
        elapsed_t = t_now - self.status_t0

        self.status_plot_data['t'].append(elapsed_t)
        self.status_plot_data['X'].append(axis_positions['X'])
        self.status_plot_data['Y'].append(axis_positions['Y'])
        self.status_plot_data['Z'].append(axis_positions['Z'])
        self.status_plot_data['A'].append(axis_positions['A'])
        self.status_plot_data['B'].append(axis_positions['B'])
        self.status_plot_data['C'].append(axis_positions['C'])
        self.status_plot_data['D'].append(axis_positions['D'])
        self.status_plot_data["'e"].append(axis_positions["'e"])
        self.status_plot_data["'f"].append(axis_positions["'f"])
        self.status_plot_data["'a"].append(axis_positions["'a"])
        self.status_plot_data["'c"].append(axis_positions["'c"])
        self.status_plot_data['Roll'].append(current_roll)
        self.status_plot_data['Pitch'].append(current_pitch)
        self.status_plot_data['Yaw'].append(current_yaw)
        self.status_plot_data['LAT'].append(current_lat)
        self.status_plot_data['AP'].append(current_ap)
        self.status_plot_data['SI'].append(current_si)

        # Cap history buffer at 100,000 points to retain full plot history for panning & zoom inspection
        if len(self.status_plot_data['t']) > 100000:
            for k in self.status_plot_data.keys():
                self.status_plot_data[k].pop(0)

        # File logging
        if hasattr(self, 'check_record_log') and self.check_record_log and self.check_record_log.isChecked():
            log_data_point(self, elapsed_t, x_val, y_val, z_val)
        else:
            close_data_log_file(self)

    except Exception as e:
        print(f"Error in fast status loop: {e}")


# --- DUET OPERATIONS ---

def get_curr_file(self, init=True):
    """
    Get the filename of the GCODE currently being executed on DUET
    """
    ip = get_clean_duet_ip(self)
    try:
        url = f'http://{ip}/rr_fileinfo'
        response = duet_request(url, timeout=4)
        if response.status_code == 200:
            data = response.json()
            if data.get('err') == 1:
                from fcn_control.fcn_control import log_to_duet_console
                log_to_duet_console(self, "Error: Duet fileinfo request returned error status", color="#ff3333")
                return None
            filepath = data.get('fileName', '')
            if init == True:
                self.tprint = data.get('printDuration', 0)
            _, filename = os.path.split(filepath)
            return filename
    except Exception as e:
        print(f"Duet fileinfo error ({url}): {e}")
        from fcn_control.fcn_control import log_to_duet_console
        log_to_duet_console(self, f"Error: Duet could not be reached at http://{ip}. Details: {e}", color="#ff3333")
        return None    


def get_duet_status(self):
    """
    Read the DUET status (motor positions, external sensors, time)
    """
    ip = get_clean_duet_ip(self)
    api_mode = getattr(self, 'duet_api_mode', None)
    
    # Fast path for modern standalone model mode to minimize latency and CPU load on the Duet
    if api_mode == 'model':
        try:
            url_pos = f'http://{ip}/rr_model?key=move.axes.userPosition'
            res_pos = duet_request(url_pos, timeout=2)
            
            url_sens = f'http://{ip}/rr_model?key=sensors.probes'
            res_sens = duet_request(url_sens, timeout=2)
            
            if res_pos.status_code == 200 and res_sens.status_code == 200:
                pos_data = res_pos.json().get("result", [])
                sens_data = res_sens.json().get("result", [])
                
                # Extract Z probe value
                probe_val = 0
                if isinstance(sens_data, list) and sens_data and isinstance(sens_data[0], dict):
                    val_list = sens_data[0].get("value", [])
                    if isinstance(val_list, list) and val_list:
                        probe_val = val_list[0]
                
                # Extract X, Y, Z positions
                x_pos = pos_data[0] if len(pos_data) > 0 else 0.0
                y_pos = pos_data[1] if len(pos_data) > 1 else 0.0
                z_pos = pos_data[2] if len(pos_data) > 2 else 0.0
                
                ampl_scale = getattr(self, 'ampl_scaling_MoVe', 0)
                t0 = getattr(self, 't0', time.time())
                tprint = getattr(self, 'tprint', 0)
                
                data = {}
                data['x'] = x_pos * -1 + ampl_scale
                data['y'] = y_pos * -1 + ampl_scale
                data['z'] = z_pos * -1 + ampl_scale
                data['geiger'] = probe_val
                data['t'] = time.time() - t0 + tprint
                return data
        except Exception as e:
            print(f"Fast path status fetch failed: {e}. Falling back to default...")
            
    # Default slow path (or legacy/SBC path)
    try:
        contents, status_code = duet_status_request(self, ip, timeout=4)
        if status_code == 200:
            data = {}

            ampl_scale = getattr(self, 'ampl_scaling_MoVe', 0)
            t0 = getattr(self, 't0', time.time())
            tprint = getattr(self, 'tprint', 0)

            data['x'] = contents['coords']['xyz'][0] * -1 + ampl_scale
            data['y'] = contents['coords']['xyz'][1] * -1 + ampl_scale
            data['z'] = contents['coords']['xyz'][2] * -1 + ampl_scale
            data['geiger'] = contents['sensors']['probeValue']
            data['t'] = time.time() - t0 + tprint
            return data
        else:
            print(f"Error: {status_code}")
            return None
    except Exception as e:
        print(f"Exception while retrieving DUET data from http://{ip}: {e}")
        return None


def pause_continue_GCODE(self, pause=True):
    """
    Send GCODE command to pause (M25) / continue (M24) the current print on DUET
    """
    ip = get_clean_duet_ip(self)
    try:
        code = "M25" if pause else "M24"
        url = f'http://{ip}/rr_gcode'
        duet_request(url, params={'gcode': code}, timeout=4)
        
        # Immediately fetch any console reply message sent by Duet upon pause/resume (e.g. 'waiting for radiation')
        time.sleep(0.1)
        try:
            res_reply = duet_request(f'http://{ip}/rr_reply', timeout=2)
            if res_reply.status_code == 200 and res_reply.text.strip():
                reply_text = res_reply.text.strip()
                if hasattr(self, 'statusDuetMessage') and self.statusDuetMessage:
                    self.statusDuetMessage.setText(reply_text)
                from fcn_control.fcn_control import log_to_duet_console
                log_to_duet_console(self, f"Duet Message: {reply_text}", color="#00acc1")
        except Exception:
            pass

        update_status_tab_dashboard(self)
    except Exception as e:
        print(f"Exception while pausing/resuming GCODE on http://{ip}: {e}")


def cancel_GCODE_job(self):
    """
    Asks confirmation from user before stopping/cancelling the active G-code print job.
    Sends M25 (pause) and M0 H1 (cancel job) to Duet.
    """
    msg = QMessageBox(self)
    msg.setWindowTitle("Confirm Cancel Job")
    msg.setText("Are you sure you want to stop and cancel the currently running print job?")
    msg.setIcon(QMessageBox.Warning)
    msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)

    result = msg.exec()
    if result == QMessageBox.StandardButton.Ok:
        self.status_t0 = None
        self.status_plot_data = None
        self.status_stopped = True
        ip = get_clean_duet_ip(self)
        try:
            url = f'http://{ip}/rr_gcode'
            # First pause, then issue cancel job command (M0 H1)
            duet_request(url, params={'gcode': 'M25'}, timeout=4)
            duet_request(url, params={'gcode': 'M0 H1'}, timeout=4)
            update_status_tab_dashboard(self)
        except Exception as e:
            print(f"Exception while cancelling GCODE job on http://{ip}: {e}")


def set_GCODE_speed(self, speed_factor=100):
    """
    Send GCODE command to adjust the speed factor (M220 S<val>) on DUET
    """
    ip = get_clean_duet_ip(self)
    try:
        url = f'http://{ip}/rr_gcode'
        code = f"M220 S{float(speed_factor):.3f}"
        duet_request(url, params={'gcode': code}, timeout=4)
        update_status_tab_dashboard(self)
    except Exception as e:
        print(f"Exception while sending speed factor to http://{ip}: {e}")


def translate_machine_status_to_legacy(om_data):
    """
    Translates RRF3 Object Model JSON (from /machine/status or /rr_model)
    to legacy RRF2 JSON format (from /rr_status?type=3)
    so the rest of the TRACE app can parse it transparently.
    """
    if not isinstance(om_data, dict):
        return {}

    # If wrapped in "result" (typical for standalone /rr_model)
    if "result" in om_data and isinstance(om_data["result"], dict):
        om_data = om_data["result"]

    legacy = {}
    
    # 1. Status Mapping
    state = om_data.get("state") or {}
    om_status = str(state.get("status", "idle")).lower()
    status_map = {
        "idle": "I",
        "processing": "P",
        "simulating": "M",
        "paused": "S",
        "resuming": "R",
        "homing": "H",
        "busy": "B",
        "configuring": "C",
        "updating": "B",
        "off": "I",
        "halted": "B",
    }
    legacy["status"] = status_map.get(om_status, "I")
    
    # 2. Extract Axes Information
    move = om_data.get("move") or {}
    if "axes" in om_data:
        move = om_data
    axes = move.get("axes") or []
    
    # Map by letter (cleaned of single quotes) for easy lookup
    axes_by_letter = {}
    if isinstance(axes, list):
        for ax in axes:
            if isinstance(ax, dict) and "letter" in ax:
                let = str(ax["letter"]).strip()
                let_clean = let.replace("'", "")
                if let_clean:
                    axes_by_letter[let_clean] = ax
            
    # Helper to check if ax is homed (checks both homed and userHomed)
    def is_axis_homed(ax_dict):
        if not isinstance(ax_dict, dict):
            return False
        homed_val = ax_dict.get("homed", ax_dict.get("userHomed", False))
        return (homed_val == 1 or homed_val is True)

    # Legacy coords structure
    x_pos = axes_by_letter.get("X", {}).get("userPosition", 0.0) if isinstance(axes_by_letter.get("X"), dict) else 0.0
    y_pos = axes_by_letter.get("Y", {}).get("userPosition", 0.0) if isinstance(axes_by_letter.get("Y"), dict) else 0.0
    z_pos = axes_by_letter.get("Z", {}).get("userPosition", 0.0) if isinstance(axes_by_letter.get("Z"), dict) else 0.0
    
    axes_homed = []
    # Cartesian X, Y, Z first
    for letter in ["X", "Y", "Z"]:
        homed_val = 1 if is_axis_homed(axes_by_letter.get(letter)) else 0
        axes_homed.append(homed_val)
        
    # Then other letters
    other_letters = ["V", "W", "A", "B", "C", "D", "a", "c", "e", "f"]
    for letter in other_letters:
        homed_val = 1 if is_axis_homed(axes_by_letter.get(letter)) else 0
        axes_homed.append(homed_val)
        
    legacy["coords"] = {
        "xyz": [x_pos, y_pos, z_pos],
        "axesHomed": axes_homed
    }
    
    # 3. Speeds
    current_move = move.get("currentMove") or {}
    legacy["speeds"] = {
        "requested": current_move.get("requestedSpeed", 0.0) if isinstance(current_move, dict) else 0.0,
        "top": current_move.get("topSpeed", 0.0) if isinstance(current_move, dict) else 0.0
    }
    
    # 4. Job Progress
    job = om_data.get("job") or {}
    file_percent = 0.0
    if isinstance(job, dict):
        file_percent = job.get("filePercent", 0.0)
        job_file = job.get("file") or {}
        if file_percent == 0.0 and isinstance(job_file, dict):
            file_percent = job_file.get("fractionPrinted", 0.0) * 100.0
        
    legacy["fractionPrinted"] = file_percent
    legacy["printDuration"] = job.get("duration", 0.0) if isinstance(job, dict) else 0.0
    
    times_left = job.get("timesLeft") or {} if isinstance(job, dict) else {}
    legacy["timesLeft"] = {
        "file": times_left.get("file", 0.0) if isinstance(times_left, dict) else 0.0
    }
    
    # 5. Sensors
    boards = om_data.get("boards") or [{}]
    board = boards[0] if (isinstance(boards, list) and boards and isinstance(boards[0], dict)) else {}
    
    mcu_temp = 45.0
    if isinstance(board, dict):
        mcu_temp_dict = board.get("mcuTemp")
        if isinstance(mcu_temp_dict, dict):
            mcu_temp = mcu_temp_dict.get("current", 45.0)
            
    vin = 24.0
    if isinstance(board, dict):
        vin_val = board.get("vIn")
        if isinstance(vin_val, dict):
            vin = vin_val.get("current", 24.0)
        elif isinstance(vin_val, (int, float)):
            vin = float(vin_val)
        
    # Probe value
    sensors = om_data.get("sensors") or {}
    probe_val = 0
    if isinstance(sensors, dict):
        probes = sensors.get("probes") or []
        if isinstance(probes, list) and probes and isinstance(probes[0], dict):
            probe_val_list = probes[0].get("value")
            if isinstance(probe_val_list, list) and probe_val_list:
                probe_val = probe_val_list[0]
        
    legacy["sensors"] = {
        "vin": vin,
        "mcuTemp": {
            "current": mcu_temp
        },
        "probeValue": probe_val
    }
    
    # 6. Keep move.axes for Individual Motors tab
    legacy_axes = []
    for letter, ax in axes_by_letter.items():
        if isinstance(ax, dict):
            legacy_axes.append({
                "letter": letter,
                "homed": is_axis_homed(ax),
                "userPosition": ax.get("userPosition", 0.0),
                "min": ax.get("min", 0.0),
                "max": ax.get("max", 200.0)
            })
    legacy["move"] = {
        "axes": legacy_axes
    }
    
    return legacy


def duet_status_request(self, ip, timeout=5):
    """
    Queries Duet status.
    Uses cached self.duet_api_mode if available to bypass failing endpoints.
    Fallback order:
    1. `/rr_status?type=3` (legacy standalone)
    2. `/rr_model?flags=d` (modern standalone Object Model)
    3. `/machine/status` (SBC Object Model)
    """
    import traceback

    api_mode = getattr(self, 'duet_api_mode', None)

    # Helper to check connection mode
    def try_request(mode):
        if mode == 'legacy':
            url = f'http://{ip}/rr_status?type=3'
            response = duet_request(url, timeout=timeout)
            if response.status_code == 200:
                return response.json(), 200
            return None, response.status_code
        elif mode == 'model':
            import json
            try:
                # Query keys separately using the shared session to ensure compatibility with RRF3 standalone boards
                url_move = f'http://{ip}/rr_model?key=move.axes&flags=d99'
                res_move = duet_request(url_move, timeout=timeout)
                move_json = res_move.json() if res_move.status_code == 200 else {}
                
                axes_list = move_json.get("result", []) if isinstance(move_json, dict) else []
                if not isinstance(axes_list, list):
                    axes_list = []
                    
                # Support pagination for move.axes if present
                next_index = move_json.get("next", 0) if isinstance(move_json, dict) else 0
                pagination_errors = []
                while next_index > 0:
                    url_paginated = f'http://{ip}/rr_model?key=move.axes&flags=d99a{next_index}'
                    try:
                        res_paginated = duet_request(url_paginated, timeout=timeout)
                        if res_paginated.status_code == 200:
                            paginated_json = res_paginated.json()
                            next_axes = paginated_json.get("result", []) if isinstance(paginated_json, dict) else []
                            if isinstance(next_axes, list):
                                axes_list.extend(next_axes)
                            next_index = paginated_json.get("next", 0) if isinstance(paginated_json, dict) else 0
                        else:
                            pagination_errors.append(f"Paginated request to {url_paginated} returned status {res_paginated.status_code}.")
                            break
                    except Exception as p_ex:
                        pagination_errors.append(f"Paginated request to {url_paginated} raised exception: {p_ex}")
                        break

                cm_json = {}
                try:
                    url_cm = f'http://{ip}/rr_model?key=move.currentMove&flags=d99'
                    res_cm = duet_request(url_cm, timeout=timeout)
                    cm_json = res_cm.json().get("result", {}) if res_cm.status_code == 200 else {}
                except Exception:
                    pass

                state_json = {}
                try:
                    url_state = f'http://{ip}/rr_model?key=state&flags=d99'
                    res_state = duet_request(url_state, timeout=timeout)
                    state_json = res_state.json().get("result", {}) if res_state.status_code == 200 else {}
                except Exception:
                    pass

                sensors_json = {}
                try:
                    url_sensors = f'http://{ip}/rr_model?key=sensors&flags=d99'
                    res_sensors = duet_request(url_sensors, timeout=timeout)
                    sensors_json = res_sensors.json().get("result", {}) if res_sensors.status_code == 200 else {}
                except Exception:
                    pass

                job_json = {}
                try:
                    url_job = f'http://{ip}/rr_model?key=job&flags=d99'
                    res_job = duet_request(url_job, timeout=timeout)
                    job_json = res_job.json().get("result", {}) if res_job.status_code == 200 else {}
                except Exception:
                    pass

                # Dump raw responses for debugging
                debug_data = {
                    "move_raw": move_json,
                    "axes_list_merged": axes_list,
                    "pagination_errors": pagination_errors,
                    "current_move_raw": cm_json,
                    "state_raw": state_json,
                    "sensors_raw": sensors_json,
                    "job_raw": job_json
                }
                try:
                    with open('duet_response_debug.json', 'w') as f:
                        json.dump(debug_data, f, indent=4)
                except Exception as ex:
                    print(f"Failed to write debug file: {ex}")
                    
                # Merge unwrapped results
                om_data = {
                    "move": {
                        "axes": axes_list,
                        "currentMove": cm_json
                    },
                    "state": state_json,
                    "sensors": sensors_json,
                    "job": job_json
                }
                
                legacy_data = translate_machine_status_to_legacy(om_data)
                return legacy_data, 200
            except Exception as ex:
                from fcn_control.fcn_control import log_to_duet_console
                log_to_duet_console(self, f"Failed in model request/merge: {ex}", color="#ff3333")
                return None, 500
        elif mode == 'sbc':
            url = f'http://{ip}/machine/status'
            response = duet_request(url, timeout=timeout)
            if response.status_code == 200:
                om_data = response.json()
                if isinstance(om_data, dict):
                    legacy_data = translate_machine_status_to_legacy(om_data)
                    return legacy_data, 200
            return None, response.status_code
        return None, 500

    # 1. Use cached mode if valid
    if api_mode:
        try:
            data, code = try_request(api_mode)
            if code == 200:
                self._api_mode_fail_count = 0
                return data, 200
            else:
                fail_cnt = getattr(self, '_api_mode_fail_count', 0) + 1
                self._api_mode_fail_count = fail_cnt
                if fail_cnt >= 3:
                    from fcn_control.fcn_control import log_to_duet_console
                    log_to_duet_console(self, f"Cached API mode '{api_mode}' failed {fail_cnt} times. Redetecting...", color="#ff3333")
                    self.duet_api_mode = None
                    self._api_mode_fail_count = 0
                else:
                    return None, code
        except Exception as e:
            fail_cnt = getattr(self, '_api_mode_fail_count', 0) + 1
            self._api_mode_fail_count = fail_cnt
            if fail_cnt >= 3:
                from fcn_control.fcn_control import log_to_duet_console
                log_to_duet_console(self, f"Cached API mode '{api_mode}' raised exception: {e}. Redetecting...", color="#ff3333")
                self.duet_api_mode = None
                self._api_mode_fail_count = 0
            else:
                return None, 500

    # 2. Run fallback detection
    is_explicit_connecting = getattr(self, '_connecting_in_progress', False)
    
    # Fallback 1: Legacy Standalone
    try:
        data, code = try_request('legacy')
        if code == 200:
            self.duet_api_mode = 'legacy'
            return data, 200
        elif is_explicit_connecting:
            from fcn_control.fcn_control import log_to_duet_console
            log_to_duet_console(self, f"Legacy check failed: /rr_status?type=3 returned status {code}", color="#ff3333")
    except Exception as e:
        if is_explicit_connecting:
            from fcn_control.fcn_control import log_to_duet_console
            log_to_duet_console(self, f"Legacy check failed: {e}", color="#ff3333")

    # Fallback 2: Modern Standalone Object Model
    try:
        data, code = try_request('model')
        if code == 200:
            self.duet_api_mode = 'model'
            if is_explicit_connecting:
                from fcn_control.fcn_control import log_to_duet_console
                log_to_duet_console(self, "Successfully connected to standalone Duet via modern API (/rr_model)")
            return data, 200
        elif is_explicit_connecting:
            from fcn_control.fcn_control import log_to_duet_console
            log_to_duet_console(self, f"Modern standalone check failed: /rr_model?key=move.axes returned status {code}", color="#ff3333")
    except Exception as e:
        if is_explicit_connecting:
            from fcn_control.fcn_control import log_to_duet_console
            log_to_duet_console(self, f"Modern standalone check failed: {e}", color="#ff3333")

    # Fallback 3: SBC Object Model
    try:
        data, code = try_request('sbc')
        if code == 200:
            self.duet_api_mode = 'sbc'
            if is_explicit_connecting:
                from fcn_control.fcn_control import log_to_duet_console
                log_to_duet_console(self, "Successfully connected to Duet via SBC API (/machine/status)")
            return data, 200
        elif is_explicit_connecting:
            from fcn_control.fcn_control import log_to_duet_console
            log_to_duet_console(self, f"SBC check failed: /machine/status returned status {code}", color="#ff3333")
    except Exception as e:
        if is_explicit_connecting:
            from fcn_control.fcn_control import log_to_duet_console
            log_to_duet_console(self, f"SBC check failed: {e}", color="#ff3333")

    return None, 500
