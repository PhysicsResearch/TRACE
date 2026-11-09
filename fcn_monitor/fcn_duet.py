# Import required libraries and modules
import os
import time
import math
import numpy as np
import requests
from datetime import datetime
from PySide6.QtWidgets import QMessageBox, QFileDialog
from fcn_init.app_config import get_config_path


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


def duet_request(url, params=None, timeout=4, retry=True):
    """
    Send an HTTP GET request to Duet, bypassing Windows system environment proxies
    to avoid false connection timeouts when connecting to local IP addresses.
    Uses a thread-local Session to reuse TCP connections (keep-alive) and prevent socket exhaustion.
    Automatically retries once with a fresh socket if an idle keep-alive connection is reset (WinError 10054).
    retry=False (live position worker) fails fast instead, so its in-flight time stays bounded.
    """
    session = get_shared_session()
    try:
        return session.get(url, params=params, timeout=timeout)
    except Exception:
        if not retry:
            raise
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
        'Roll': [], 'Pitch': [], 'Yaw': [],
        'LAT': [], 'AP': [], 'SI': []
    }
    self.status_t0 = None
    render_status_plot(self)


# Probe shading classes of the Status plot: (kind, key label, colour); same labels as the Log files tab
_PROBE_KEY = ((1, 'Detector (Probe 1-1499)', '#ff0000'),
              (2, 'Release button (Probe 2000)', '#0288d1'),
              (3, 'Waiting for sensor (Probe -1000)', '#ffb300'))
_PROBE_SPAN_ALPHA = 0.22


def _update_probe_key(self, kinds):
    """Colour key of the probe shading, in one row above the plot area (it covers no curve): only
    the classes present in the plotted data, same colours / alpha as the spans. Separate from the
    trace legend; rebuilt only when the classes present change."""
    ax = self.ax_status
    key = getattr(self, '_probe_key', None)
    present = tuple(k for k, _l, _c in _PROBE_KEY if k in kinds)
    alive = key is not None and key in ax.artists          # ax.clear() (Clear plot, Start) drops it
    if alive and getattr(self, '_probe_key_kinds', None) == present:
        return
    if alive:
        try:
            key.remove()
        except Exception:
            pass
    self._probe_key = None
    self._probe_key_kinds = present
    if not present:
        return
    from matplotlib.patches import Patch
    from matplotlib.legend import Legend
    handles = [Patch(facecolor=c, edgecolor=c, alpha=_PROBE_SPAN_ALPHA) for k, _l, c in _PROBE_KEY if k in present]
    labels = [l for k, l, _c in _PROBE_KEY if k in present]
    key = Legend(ax, handles, labels, loc='lower left', bbox_to_anchor=(0.0, 1.0), ncol=len(handles), fontsize=10,
                 frameon=False, borderaxespad=0.15, borderpad=0.2, handlelength=1.6, handleheight=0.9,
                 handletextpad=0.5, columnspacing=1.4)
    ax.add_artist(key)
    key.set_clip_on(False)          # outside the plot area: tight_layout then keeps a row for it
    self._probe_key = key


def _refresh_probe_key(self):
    """Colour key for the probe classes with a span (of the last render) in the shown x range.
    True when the listed classes changed."""
    spans = getattr(self, '_probe_spans_drawn', None) or []
    x_lo, x_hi = sorted(self.ax_status.get_xlim())
    before = getattr(self, '_probe_key_kinds', None)
    _update_probe_key(self, {k for k, a, b in spans if b >= x_lo and a <= x_hi})
    return getattr(self, '_probe_key_kinds', None) != before


def render_status_plot(self):
    """
    Highly optimized updates of the Matplotlib plot using line reuse and draw_idle.
    Avoids calling clear() to prevent lag and CPU overload.
    """
    if not hasattr(self, 'ax_status') or self.ax_status is None:
        return

    plot_data = getattr(self, 'status_plot_data', None)
    t_data = plot_data.get('t', []) if (plot_data is not None and isinstance(plot_data, dict)) else []

    show_ref = False
    if hasattr(self, 'check_show_reference') and self.check_show_reference is not None and self.check_show_reference.isChecked():
        show_ref = True

    ref_data = getattr(self, 'status_reference_data', None)

    # If no live data and no reference data, exit early
    # But first hide reference lines if show_ref was turned off
    if not show_ref and hasattr(self, 'status_ref_lines'):
        for rkey in self.status_ref_lines:
            if self.status_ref_lines[rkey].get_visible():
                self.status_ref_lines[rkey].set_visible(False)
        if hasattr(self, 'statusCanvas') and self.statusCanvas is not None:
            self.statusCanvas.draw_idle()

    if len(t_data) == 0 and not (show_ref and ref_data is not None):
        return

    # Keep track of active line handles in self.status_plot_lines dict
    if not hasattr(self, 'status_plot_lines'):
        self.status_plot_lines = {}

    # Keep track of active reference line handles
    if not hasattr(self, 'status_ref_lines'):
        self.status_ref_lines = {}

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
    live_max_x = t_data[-1] if (t_data is not None and len(t_data) > 0) else 0.0
    if live_max_x == 0.0 and show_ref and ref_data is not None:
        ref_t = ref_data.get('t', [])
        if len(ref_t) > 0:
            live_max_x = float(ref_t[-1])
    min_y, max_y = 1e9, -1e9

    for cb_name, key, label, color in traces:
        cb = getattr(self, cb_name, None)
        cb_visible = (not cb.isHidden()) if (cb is not None and hasattr(cb, 'isHidden')) else True
        if cb is not None and cb.isChecked() and cb_visible:
            data_list = plot_data.get(key, []) if (plot_data is not None and isinstance(plot_data, dict)) else []
            if len(data_list) > 0 and len(data_list) == len(t_data):
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
                if key in self.status_plot_lines:
                    self.status_plot_lines[key].set_visible(False)

            # Draw expected reference value using same color with a dashed line (--)
            if show_ref and ref_data is not None and key in ref_data:
                ref_t = ref_data.get('t', [])
                ref_vals = ref_data.get(key, [])
                if len(ref_t) > 0 and len(ref_vals) == len(ref_t):
                    # Read reference time offset (supports float decimals, retains last valid offset while typing)
                    ref_offset = getattr(self, '_last_valid_ref_offset', 0.0)
                    if hasattr(self, 'input_ref_offset') and self.input_ref_offset is not None:
                        text_val = self.input_ref_offset.text().strip()
                        try:
                            ref_offset = float(text_val)
                            self._last_valid_ref_offset = ref_offset
                        except ValueError:
                            ref_offset = getattr(self, '_last_valid_ref_offset', 0.0)

                    ref_t_shifted = np.asarray(ref_t, dtype=float) + ref_offset
                    min_y = min(min_y, min(ref_vals))
                    max_y = max(max_y, max(ref_vals))
                    if key in self.status_ref_lines:
                        rline = self.status_ref_lines[key]
                        rline.set_data(ref_t_shifted, ref_vals)
                        rline.set_visible(True)
                    else:
                        rline, = self.ax_status.plot(ref_t_shifted, ref_vals, linestyle='--', color=color, linewidth=1.5, alpha=0.85)
                        self.status_ref_lines[key] = rline
            else:
                if key in self.status_ref_lines:
                    if self.status_ref_lines[key].get_visible():
                        self.status_ref_lines[key].set_visible(False)
        else:
            # If the trace is unchecked, make the line invisible if it exists
            if key in self.status_plot_lines:
                if self.status_plot_lines[key].get_visible():
                    self.status_plot_lines[key].set_visible(False)
                    needs_legend_update = True
            if key in self.status_ref_lines:
                if self.status_ref_lines[key].get_visible():
                    self.status_ref_lines[key].set_visible(False)

    # Remove stale lines that are not in the dictionary anymore
    stale_keys = []
    for key in list(self.status_plot_lines.keys()):
        if self.status_plot_lines[key] not in self.ax_status.lines:
            stale_keys.append(key)
    for key in stale_keys:
        self.status_plot_lines.pop(key, None)

    # Draw vertical lines for planned pauses from reference data
    if not hasattr(self, '_ref_pause_lines'):
        self._ref_pause_lines = []
    if show_ref and ref_data is not None:
        pause_list = ref_data.get('pause_times', [])
        if pause_list:
            # Read reference time offset
            ref_offset = getattr(self, '_last_valid_ref_offset', 0.0)
            if hasattr(self, 'input_ref_offset') and self.input_ref_offset is not None:
                text_val = self.input_ref_offset.text().strip()
                try:
                    ref_offset = float(text_val)
                except ValueError:
                    ref_offset = getattr(self, '_last_valid_ref_offset', 0.0)

            # Remove old pause lines if count changed
            if len(self._ref_pause_lines) != len(pause_list):
                for old_line in self._ref_pause_lines:
                    try:
                        old_line.remove()
                    except Exception:
                        pass
                self._ref_pause_lines = []

            for i, (cmd_type, t_pause) in enumerate(pause_list):
                t_shifted = t_pause + ref_offset
                color = '#e53935' if 'sensor_wait' in cmd_type else '#fbc02d'
                if i < len(self._ref_pause_lines):
                    self._ref_pause_lines[i].set_xdata([t_shifted, t_shifted])
                    self._ref_pause_lines[i].set_visible(True)
                else:
                    vline = self.ax_status.axvline(
                        x=t_shifted, color=color, linestyle='--',
                        linewidth=1.5, alpha=0.85
                    )
                    self._ref_pause_lines.append(vline)
    # Render transparent red background shading for active radiation intervals (probe > 0)
    if not hasattr(self, '_probe_span_patches'):
        self._probe_span_patches = []

    for patch in self._probe_span_patches:
        try:
            patch.remove()
        except Exception:
            pass
    self._probe_span_patches = []

    # Probe classes: 0 none, 0 < v < 1500 detector (red), v >= 1500 Release-button marker (blue),
    # v <= -500 waiting for sensor (amber; sensor_wait.g, logged as PROBE_WAIT_MARK)
    probe_data = plot_data.get('probe', []) if (plot_data is not None and isinstance(plot_data, dict)) else []
    spans_drawn = []                # (kind, start, end): the colour key lists the classes in the shown x range
    if len(probe_data) > 0 and len(t_data) == len(probe_data):
        span_colors = {k: c for k, _l, c in _PROBE_KEY}
        dt_default = (t_data[1] - t_data[0]) if len(t_data) > 1 else 0.05

        def _add_span(kind, start, end):
            if end <= start:
                end = start + dt_default
            span = self.ax_status.axvspan(start, end, color=span_colors[kind], alpha=_PROBE_SPAN_ALPHA, zorder=0)
            self._probe_span_patches.append(span)
            spans_drawn.append((kind, start, end))

        cur_kind, span_start = 0, 0.0
        for i in range(len(t_data)):
            try:
                val = float(probe_data[i])
            except (ValueError, TypeError):
                val = 0.0
            kind = 3 if val <= -500 else (0 if val <= 0 else (2 if val >= 1500 else 1))
            if kind != cur_kind:
                if cur_kind:
                    _add_span(cur_kind, span_start, t_data[i])
                cur_kind, span_start = kind, t_data[i]
        if cur_kind:
            _add_span(cur_kind, span_start, t_data[-1])

    # Parse user-configured time window interval (default 60s)
    time_win = 60.0
    if hasattr(self, 'input_time_interval') and self.input_time_interval is not None:
        try:
            val = float(self.input_time_interval.text().strip())
            if val > 0:
                time_win = val
        except ValueError:
            time_win = 60.0

    # Calculate step-jump x-axis limits starting at [0.0, time_win]
    # Reaching 60s -> [30, 90], reaching 90s -> [60, 120]
    half_win = time_win / 2.0
    if live_max_x <= time_win:
        x_start = 0.0
        x_end = time_win
    else:
        import math
        steps = math.floor((live_max_x - time_win) / half_win) + 1
        x_start = steps * half_win
        x_end = x_start + time_win

    curr_xlim = self.ax_status.get_xlim()
    is_uninitialized = (curr_xlim[0] == 0.0 and curr_xlim[1] == 1.0) or curr_xlim[1] <= curr_xlim[0]
    is_at_live_edge = is_uninitialized or (live_max_x >= curr_xlim[1] - 1.0) or (live_max_x == 0.0)

    if is_at_live_edge:
        if abs(curr_xlim[0] - x_start) > 1e-4 or abs(curr_xlim[1] - x_end) > 1e-4:
            self.ax_status.set_xlim(x_start, x_end)

        if min_y < max_y:
            pad = (max_y - min_y) * 0.1 if max_y != min_y else 1.0
            self.ax_status.set_ylim(min_y - pad, max_y + pad)

    # Colour key of the probe shading: the classes with a span in the shown time range (the live
    # window scrolls past old ones); rebuilt only when that set changes
    try:
        self._probe_spans_drawn = spans_drawn
        _refresh_probe_key(self)
    except Exception as e:
        print(f"Could not draw the probe colour key: {e}")

    # Rebuild legend containing ONLY currently visible checked line traces
    visible_handles = []
    visible_labels = []
    for cb_name, key, label, color in traces:
        if key in self.status_plot_lines and self.status_plot_lines[key].get_visible():
            visible_handles.append(self.status_plot_lines[key])
            visible_labels.append(label)
        elif show_ref and key in self.status_ref_lines and self.status_ref_lines[key].get_visible():
            visible_handles.append(self.status_ref_lines[key])
            visible_labels.append(f"{label} (Ref)")

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
        'Roll': [], 'Pitch': [], 'Yaw': [],
        'LAT': [], 'AP': [], 'SI': [], 'probe': []
    }
    self._total_pause_duration = 0.0
    self._pause_start_perf = None
    if hasattr(self, 'status_plot_lines'):
        self.status_plot_lines.clear()
    if hasattr(self, 'status_ref_lines'):
        self.status_ref_lines.clear()
    if hasattr(self, '_ref_pause_lines'):
        self._ref_pause_lines.clear()
    if hasattr(self, '_probe_span_patches'):
        self._probe_span_patches.clear()
    if hasattr(self, 'ax_status') and self.ax_status is not None:
        self.ax_status.clear()
        self.ax_status.set_xlabel("Time (s)", fontsize=13, fontweight='bold')
        self.ax_status.set_ylabel("Position (mm)", fontsize=13, fontweight='bold')
        self.ax_status.tick_params(axis='both', which='major', labelsize=11)
        self.ax_status.grid(True, linestyle=":", alpha=0.6)
        if hasattr(self, 'statusCanvas') and self.statusCanvas is not None:
            self.statusCanvas.draw_idle()


def load_log_file_into_status(self, file_path=None):
    """
    Opens and parses a recorded TRACE log file (.csv or .txt), loads the data into
    status_plot_data, automatically checks the checkboxes for all axes contained
    in the log file, unchecks axes not in the log file, and renders the plot with
    red transparent shading for regions where probe > 0.
    """
    if getattr(self, '_log_dialog_open', False) is True:
        return
    if getattr(self, 'run_active', False) is True:
        # Loading would stop this run's recording and mix the file into the live plot
        QMessageBox.information(self, "Run in progress",
                                "A G-code run is being recorded. Load the log file after the run has finished.")
        return
    self._log_dialog_open = True
    try:
        _load_log_file_into_status_impl(self, file_path)
    finally:
        self._log_dialog_open = False


def _load_log_file_into_status_impl(self, file_path=None):
    if file_path is None or not file_path:
        default_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        if hasattr(self, 'PhOperFolder') and self.PhOperFolder and self.PhOperFolder.text().strip():
            candidate = self.PhOperFolder.text().strip()
            if os.path.isdir(candidate):
                default_dir = candidate

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Log File",
            default_dir,
            "Log Files (*.csv *.txt);;CSV Files (*.csv);;Text Files (*.txt);;All Files (*.*)"
        )
        if not file_path:
            return

    if not os.path.exists(file_path):
        QMessageBox.warning(self, "File Not Found", f"Selected file does not exist:\n{file_path}")
        return

    import pandas as pd
    import numpy as np
    import math
    from fcn_plan.fcn_import import match_log_axis_name, sniff_trace_log_format, read_trace_log_v2_table

    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
    df = None
    log_sep, log_dec = sniff_trace_log_format(file_path)
    for enc in encodings:
        try:
            if log_sep == ';':      # format v2: ';' columns, decimal comma, '#' notes after the data
                df = read_trace_log_v2_table(file_path, decimal=log_dec, encoding=enc)
            else:
                df = pd.read_csv(file_path, sep=None, engine='python', encoding=enc, comment='#')
            break
        except Exception:
            continue

    if df is None or df.empty:
        QMessageBox.warning(self, "Empty File", f"Could not read data from log file:\n{os.path.basename(file_path)}")
        return

    df = df.dropna(how='all')
    if len(df) < 1:
        QMessageBox.warning(self, "Invalid Log", f"The log file contains no data points:\n{os.path.basename(file_path)}")
        return

    time_col = None
    probe_col = None
    matched_axes = {}  # {target_axis: orig_column_name}

    for col in df.columns:
        c = str(col).strip()
        cl = c.lower()
        if 'probe' in cl or 'sensor' in cl:
            if probe_col is None:
                probe_col = col
            continue

        target = match_log_axis_name(col)
        if target == 'time':
            if time_col is None:
                time_col = col
        elif target is not None:
            matched_axes[target] = col

    if not matched_axes:
        QMessageBox.warning(
            self,
            "No Motion Axes Found",
            f"No recognizable motion axes (e.g. Pos_X_mm, Pos_LAT_mm) found in log file:\n{os.path.basename(file_path)}"
        )
        return

    # Extract time series
    if time_col is not None:
        t_raw = pd.to_numeric(df[time_col], errors='coerce').values
    else:
        # Fallback index if no time column found
        t_raw = np.arange(len(df)) * 0.05

    valid_mask = ~np.isnan(t_raw)
    if not np.all(valid_mask):
        df = df.iloc[valid_mask].copy()
        t_raw = t_raw[valid_mask]

    if len(t_raw) < 1:
        QMessageBox.warning(self, "Invalid Time", "Log file contains no valid timestamps.")
        return

    # If timestamps start far from 0 (e.g. epoch timestamps > 3600), align to 0
    if len(t_raw) > 0 and t_raw[0] > 3600.0:
        t_vals = list(t_raw - t_raw[0])
    else:
        t_vals = list(t_raw)
    n_pts = len(t_vals)

    # Close active file recording if running
    if hasattr(self, 'check_record_log') and self.check_record_log and self.check_record_log.isChecked():
        self.check_record_log.setChecked(False)
    if getattr(self, 'active_log_file', None) is not None:
        close_data_log_file(self)

    # Initialize empty status_plot_data
    all_keys = [
        'X', 'Y', 'Z', 'A', 'B', 'C', 'D',
        "'e", "'f", "'a", "'c",
        'Roll', 'Pitch', 'Yaw',
        'LAT', 'AP', 'SI'
    ]
    new_plot_data = {'t': t_vals}
    for k in all_keys:
        if k in matched_axes:
            vals = pd.to_numeric(df[matched_axes[k]], errors='coerce').fillna(0.0).values
            new_plot_data[k] = list(vals)
        else:
            new_plot_data[k] = []

    # Probe series
    if probe_col is not None:
        probe_vals = pd.to_numeric(df[probe_col], errors='coerce').fillna(0.0).values
        new_plot_data['probe'] = list(probe_vals)
    else:
        new_plot_data['probe'] = [0.0] * n_pts

    self.status_plot_data = new_plot_data

    # Automatically set visible the axes included in the log file
    traces = [
        ('status_check_X', 'X'),
        ('status_check_Y', 'Y'),
        ('status_check_Z', 'Z'),
        ('status_check_A', 'A'),
        ('status_check_B', 'B'),
        ('status_check_C', 'C'),
        ('status_check_D', 'D'),
        ('status_check_e', "'e"),
        ('status_check_f', "'f"),
        ('status_check_a', "'a"),
        ('status_check_c', "'c"),
        ('status_check_Roll', 'Roll'),
        ('status_check_Pitch', 'Pitch'),
        ('status_check_Yaw', 'Yaw'),
        ('status_check_LAT', 'LAT'),
        ('status_check_AP', 'AP'),
        ('status_check_SI', 'SI')
    ]

    for cb_name, key in traces:
        cb = getattr(self, cb_name, None)
        if cb is not None:
            cb.blockSignals(True)
            cb.setChecked(key in matched_axes)
            cb.blockSignals(False)

    if hasattr(self, 'check_show_reference') and self.check_show_reference:
        self.check_show_reference.blockSignals(True)
        self.check_show_reference.setChecked(False)
        self.check_show_reference.blockSignals(False)

    # Adjust Time interval control to show full duration
    max_t = t_vals[-1] if len(t_vals) > 0 else 60.0
    win_size = max(math.ceil(max_t), 10)
    if hasattr(self, 'input_time_interval') and self.input_time_interval is not None:
        self.input_time_interval.blockSignals(True)
        self.input_time_interval.setText(str(win_size))
        self.input_time_interval.blockSignals(False)

    # Clear old line handles
    if hasattr(self, 'status_plot_lines'):
        for line in self.status_plot_lines.values():
            try:
                line.remove()
            except Exception:
                pass
        self.status_plot_lines.clear()

    if hasattr(self, 'status_ref_lines'):
        for line in self.status_ref_lines.values():
            try:
                line.remove()
            except Exception:
                pass
        self.status_ref_lines.clear()

    render_status_plot(self)

    # Ensure full viewing bounds on axes
    if hasattr(self, 'ax_status') and self.ax_status is not None:
        self.ax_status.set_xlim(0.0, max(max_t, 1.0))
        try:
            if _refresh_probe_key(self):          # the whole log is shown now: key for all its classes
                self.fig_status.tight_layout()
        except Exception:
            pass
        # y-range from the traces actually shown (Basic mode hides e.g. the raw actuators)
        cb_by_key = {key: getattr(self, cb_name, None) for cb_name, key in traces}
        all_visible_vals = []
        for k in matched_axes.keys():
            cb = cb_by_key.get(k)
            shown = cb is None or (cb.isChecked() and not (hasattr(cb, 'isHidden') and cb.isHidden() is True))
            if shown:
                all_visible_vals.extend(new_plot_data[k])
        if all_visible_vals:
            y_min = min(all_visible_vals)
            y_max = max(all_visible_vals)
            pad = (y_max - y_min) * 0.1 if y_max != y_min else 1.0
            self.ax_status.set_ylim(y_min - pad, y_max + pad)
        if hasattr(self, 'statusCanvas') and self.statusCanvas is not None:
            self.statusCanvas.draw_idle()

    axes_str = ", ".join(sorted(matched_axes.keys()))
    has_pos_probe = any(p > 0 or p <= -500 for p in new_plot_data['probe'])   # detector, Release or sensor wait
    probe_info = "with active probe shading" if has_pos_probe else "no active probe"
    msg = f"Loaded {os.path.basename(file_path)}: {n_pts} pts, {max_t:.1f}s, axes [{axes_str}], {probe_info}"
    if hasattr(self, 'statusDuetMessage') and self.statusDuetMessage:
        self.statusDuetMessage.setText(msg)
    print(msg)


def load_and_parse_gcode_reference(self, fpath_or_content, progress_dialog=None):
    """
    Parses GCode string or file path into a dictionary of reference traces:
    t, X, Y, Z, A, B, C, D, 'e, 'f, 'a, 'c, LAT, SI, AP, Roll, Pitch, Yaw.
    Accepts an optional progress_dialog (QProgressDialog) to display parsing progress.
    """
    import os
    import re
    import pandas as pd
    import numpy as np
    from fcn_plan.fcn_create import _reverse_motion_platform_kinematics

    lines = []
    if isinstance(fpath_or_content, str) and os.path.exists(fpath_or_content):
        try:
            with open(fpath_or_content, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception:
            lines = []
    elif isinstance(fpath_or_content, str):
        lines = fpath_or_content.splitlines()

    if not lines:
        return None

    # Shared reader (fcn_plan.fcn_gcode): RRF time model for G1 (feed on linear vs rotary
    # axes, min-speed clamp, M203 caps) and G4 dwells plus the file's step overhead
    from fcn_plan.fcn_gcode import GcodeTimelineParser
    parser = GcodeTimelineParser(bare_lowercase_as_quoted=True)
    num_lines = len(lines)

    for idx, line in enumerate(lines):
        if progress_dialog is not None and num_lines > 0 and idx % 200 == 0:
            pct = 50 + int((idx / num_lines) * 45)
            progress_dialog.setValue(pct)
            from PySide6.QtCore import QCoreApplication
            QCoreApplication.processEvents()
            if progress_dialog.wasCanceled():
                return None
        parser.feed_line(line)

    data_rows = parser.rows
    pause_times = parser.pause_times  # Planned pause/wait command timestamps

    if not data_rows:
        return None

    df = pd.DataFrame(data_rows)
    for col in df.columns:
        if col not in ['Command', 'time', 'timestamp']:
            df[col] = df[col].ffill().bfill().fillna(0.0)

    # Ensure reference timeline is anchored at t=0.0
    if df['time'].iloc[0] > 0.0:
        first_row = df.iloc[0].copy()
        first_row['time'] = 0.0
        first_row['timestamp'] = 0.0
        df = pd.concat([pd.DataFrame([first_row]), df], ignore_index=True)

    t_max = df['time'].max()
    if t_max > 0.0:
        t_grid = np.arange(0.0, t_max + 0.005, 0.02)
        resampled = {'time': t_grid, 'timestamp': t_grid * 1000.0, 'Command': [""] * len(t_grid)}
        exclude = {'time', 'timestamp', 'Command'}
        for c in [col for col in df.columns if col not in exclude]:
            resampled[c] = np.interp(t_grid, df['time'].values, df[c].values)
        df = pd.DataFrame(resampled)

    # Calculate motion platform kinematics if A, B, C, D present
    if 'A' in df.columns and 'B' in df.columns and 'C' in df.columns and 'D' in df.columns:
        df_kin = _reverse_motion_platform_kinematics(self, df)
        for kin_col in ['LAT', 'SI', 'AP', 'Roll', 'Pitch', 'Yaw']:
            if kin_col in df_kin.columns:
                df[kin_col] = df_kin[kin_col].values

    ref_dict = {'t': df['time'].values, 'pause_times': pause_times}
    for col in df.columns:
        if col not in ['time', 'timestamp', 'Command']:
            ref_dict[col] = df[col].values
            clean_c = col.strip("'")
            ref_dict[clean_c] = df[col].values
            ref_dict[f"'{clean_c}"] = df[col].values

    return ref_dict


def load_gcode_as_reference_into_status(self, file_path=None):
    """
    Allows the user to pick a G-code file from the computer and load it as a reference
    in the status page, enabling 'Show reference' and rendering the trajectory.
    """
    if getattr(self, '_gcode_ref_dialog_open', False) is True:
        return
    self._gcode_ref_dialog_open = True
    try:
        _load_gcode_as_reference_into_status_impl(self, file_path)
    finally:
        self._gcode_ref_dialog_open = False


def _load_gcode_as_reference_into_status_impl(self, file_path=None):
    if file_path is None or not file_path:
        default_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        if hasattr(self, 'PhOperFolder') and self.PhOperFolder and self.PhOperFolder.text().strip():
            candidate = self.PhOperFolder.text().strip()
            if os.path.isdir(candidate):
                default_dir = candidate

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load G-code as Reference",
            default_dir,
            "G-code Files (*.gcode *.g *.nc *.txt);;All Files (*.*)"
        )
        if not file_path:
            return

    if not os.path.exists(file_path):
        QMessageBox.warning(self, "File Not Found", f"Selected file does not exist:\n{file_path}")
        return

    fname = os.path.basename(file_path)

    from PySide6.QtWidgets import QProgressDialog, QWidget, QApplication
    from PySide6.QtCore import Qt, QCoreApplication
    progress = None
    if QApplication.instance() is not None:
        parent_widget = self if isinstance(self, QWidget) else None
        progress = QProgressDialog(f"Loading reference plot data from '{fname}'...", "Cancel", 0, 100, parent_widget)
        progress.setWindowTitle("Loading Reference G-code")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumWidth(520)
        progress.setMinimumHeight(160)
        progress.setStyleSheet("""
            QProgressDialog { font-size: 16px; font-weight: bold; }
            QLabel { font-size: 16px; min-height: 35px; }
            QProgressBar { text-align: center; font-size: 16px; font-weight: bold; height: 30px; border-radius: 4px; }
            QPushButton { font-size: 16px; font-weight: bold; min-width: 100px; min-height: 38px; border-radius: 4px; }
        """)
        progress.setValue(10)
        progress.show()
        QCoreApplication.processEvents()

    try:
        ref_dict = load_and_parse_gcode_reference(self, file_path, progress_dialog=progress)
    except Exception as e:
        if progress:
            progress.close()
        QMessageBox.warning(self, "Parse Error", f"Error parsing G-code reference file:\n{e}")
        return
    finally:
        if progress:
            progress.setValue(100)
            progress.close()

    if ref_dict is None or 't' not in ref_dict or len(ref_dict['t']) < 2:
        QMessageBox.warning(self, "Invalid Reference", f"Could not extract motion trajectories from G-code file:\n{fname}")
        return

    self.status_reference_data = ref_dict
    self._loaded_ref_filename = fname

    # Enable 'Show reference' checkbox
    if hasattr(self, 'check_show_reference') and self.check_show_reference is not None:
        self.check_show_reference.blockSignals(True)
        self.check_show_reference.setChecked(True)
        self.check_show_reference.blockSignals(False)

    traces = [
        ('status_check_X', 'X'),
        ('status_check_Y', 'Y'),
        ('status_check_Z', 'Z'),
        ('status_check_A', 'A'),
        ('status_check_B', 'B'),
        ('status_check_C', 'C'),
        ('status_check_D', 'D'),
        ('status_check_e', "'e"),
        ('status_check_f', "'f"),
        ('status_check_a', "'a"),
        ('status_check_c', "'c"),
        ('status_check_Roll', 'Roll'),
        ('status_check_Pitch', 'Pitch'),
        ('status_check_Yaw', 'Yaw'),
        ('status_check_LAT', 'LAT'),
        ('status_check_AP', 'AP'),
        ('status_check_SI', 'SI')
    ]

    # Detect which axes have motion or variation in reference
    ref_axes_active = []
    for cb_name, key in traces:
        if key in ref_dict:
            try:
                vals = np.asarray(ref_dict[key], dtype=float)
                if len(vals) > 0 and (np.ptp(vals) > 1e-4 or np.any(np.abs(vals) > 1e-4)):
                    ref_axes_active.append(key)
            except Exception:
                pass

    if ref_axes_active:
        for cb_name, key in traces:
            cb = getattr(self, cb_name, None)
            if cb is not None:
                cb.blockSignals(True)
                cb.setChecked(key in ref_axes_active)
                cb.blockSignals(False)

    ref_t = ref_dict.get('t', [])
    max_ref_t = float(ref_t[-1]) if len(ref_t) > 0 else 60.0
    plot_data = getattr(self, 'status_plot_data', None)
    t_live = plot_data.get('t', []) if (plot_data is not None and isinstance(plot_data, dict)) else []

    import math
    win_size = max(math.ceil(max_ref_t), 10)
    if len(t_live) == 0:
        if hasattr(self, 'input_time_interval') and self.input_time_interval is not None:
            self.input_time_interval.blockSignals(True)
            self.input_time_interval.setText(str(win_size))
            self.input_time_interval.blockSignals(False)

    # Clear stale reference lines
    if hasattr(self, 'status_ref_lines'):
        for line in self.status_ref_lines.values():
            try:
                line.remove()
            except Exception:
                pass
        self.status_ref_lines.clear()

    render_status_plot(self)

    if len(t_live) == 0 and hasattr(self, 'ax_status') and self.ax_status is not None:
        self.ax_status.set_xlim(0.0, max(max_ref_t, 1.0))
        all_ref_vals = []
        for k in ref_axes_active:
            all_ref_vals.extend(ref_dict[k])
        if all_ref_vals:
            y_min = min(all_ref_vals)
            y_max = max(all_ref_vals)
            pad = (y_max - y_min) * 0.1 if y_max != y_min else 1.0
            self.ax_status.set_ylim(y_min - pad, y_max + pad)
        if hasattr(self, 'statusCanvas') and self.statusCanvas is not None:
            self.statusCanvas.draw_idle()

    axes_str = ", ".join(sorted(ref_axes_active)) if ref_axes_active else "active"
    msg = f"Loaded reference G-code {fname}: {len(ref_t)} pts, {max_ref_t:.1f}s, axes [{axes_str}]"
    if hasattr(self, 'statusDuetMessage') and self.statusDuetMessage:
        self.statusDuetMessage.setText(msg)
    print(msg)


def auto_load_current_gcode_reference(self, filename=None, force=False):
    """Attempts to fetch the active or specified GCODE filename from Duet and load its reference data."""
    if not filename:
        filename = get_curr_file(self, init=False)
    if not filename:
        return False

    fname = os.path.basename(filename)

    # Return True immediately if reference data is already loaded for this exact file
    if not force and getattr(self, 'status_reference_data', None) is not None:
        if getattr(self, '_loaded_ref_filename', None) == fname:
            return True

    from PySide6.QtWidgets import QProgressDialog, QWidget, QApplication
    from PySide6.QtCore import Qt, QCoreApplication
    progress = None
    if QApplication.instance() is not None:
        parent_widget = self if isinstance(self, QWidget) else None
        progress = QProgressDialog(f"Loading reference plot data from '{fname}'...", "Cancel", 0, 100, parent_widget)
        progress.setWindowTitle("Loading Reference Data")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumWidth(520)
        progress.setMinimumHeight(160)
        progress.setStyleSheet("""
            QProgressDialog { font-size: 16px; font-weight: bold; }
            QLabel { font-size: 16px; min-height: 35px; }
            QProgressBar { text-align: center; font-size: 16px; font-weight: bold; height: 30px; border-radius: 4px; }
            QPushButton { font-size: 16px; font-weight: bold; min-width: 100px; min-height: 38px; border-radius: 4px; }
        """)
        progress.setValue(10)
        progress.show()
        QCoreApplication.processEvents()

    ip = get_clean_duet_ip(self)
    dl_url = f'http://{ip}/rr_download?name=/gcodes/{filename.strip("/")}'
    try:
        res = duet_request(dl_url, timeout=5)
        if progress:
            progress.setValue(50)
            QCoreApplication.processEvents()
        if res.status_code == 200 and res.text:
            ref_dict = load_and_parse_gcode_reference(self, res.text, progress_dialog=progress)
            self.status_reference_data = ref_dict
            self._loaded_ref_filename = fname
            return ref_dict is not None
    except Exception as e:
        print(f"Failed to auto-load reference for {filename}: {e}")
    finally:
        if progress:
            progress.setValue(100)
            progress.close()
    return False


def start_selected_gcode_execution(self):
    """
    Executes the currently selected G-code file on the Duet when the green Start button is clicked.
    Guarded against a second Start while this one is still pre-positioning (the wait processes
    GUI events, so the button could otherwise be pressed again).
    """
    if getattr(self, '_starting_gcode', False) is True:
        return
    self._starting_gcode = True
    btn = getattr(self, 'gcodeStart', None)
    try:
        if btn is not None and hasattr(btn, 'setEnabled'):
            btn.setEnabled(False)
        _start_selected_gcode_execution_impl(self)
    finally:
        self._starting_gcode = False
        if btn is not None and hasattr(btn, 'setEnabled'):
            btn.setEnabled(True)


def update_gcode_name_label(self, name):
    """Shows the loaded / running G-code file name in the Status tab (stays visible, unlike the
    Duet message line)."""
    lbl = getattr(self, 'statusGcodeName', None)
    if lbl is None or not hasattr(lbl, 'setText'):
        return
    txt = f"G-code: {os.path.basename(str(name)) if name else '--'}"
    if lbl.text() != txt:
        lbl.setText(txt)
        lbl.setToolTip(str(name) if name else "")


def _start_selected_gcode_execution_impl(self):
    """
    Pre-positions the platform at the initial G-code coordinates, then starts the file (M32)
    with one time zero for the log and the plot.
    """
    from PySide6.QtWidgets import QMessageBox
    from PySide6.QtCore import QCoreApplication

    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before starting motion.")
        return

    fpath = getattr(self, 'selected_gcode_path', None)
    if not fpath:
        fpath = get_curr_file(self, init=False)

    if not fpath:
        QMessageBox.warning(self, "No File Selected", "Please select a G-code file from the Files tab first.")
        return

    ip = get_clean_duet_ip(self)
    url = f'http://{ip}/rr_gcode'
    fname = os.path.basename(fpath) if os.path.isabs(fpath) else fpath.strip("/")
    update_gcode_name_label(self, fname)

    # Always pre-position platform to starting coordinates of fname before launching execution
    if hasattr(self, 'statusDuetMessage') and self.statusDuetMessage is not None:
        self.statusDuetMessage.setText(f"Pre-positioning to starting coordinates of {fname}...")
        QCoreApplication.processEvents()

    first_g1 = None
    lines = []
    try:
        dl_url = f'http://{ip}/rr_download?name=/gcodes/{fname}'
        res = duet_request(dl_url, timeout=3)
        lines = res.text.splitlines() if (res.status_code == 200 and res.text) else []
        if not lines and os.path.exists(fpath):
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        for l in lines:
            l_clean = l.split(';')[0].strip()
            if l_clean.startswith('G1') and len(l_clean) > 3:
                first_g1 = l_clean
                break
    except Exception as e:
        print(f"Could not read first G1 line from {fname}: {e}")

    # A previous run that is still open ends here
    if getattr(self, 'run_active', False) is True or getattr(self, 'active_log_file', None) is not None:
        end_run(self, "new start")

    # Device of THIS job (decides the log columns), from the G-code axis letters
    run_device = _device_from_gcode_lines(lines)
    if run_device is None:
        combo = getattr(self, 'combo_device', None)
        txt = combo.currentText() if combo is not None and hasattr(combo, 'currentText') else None
        run_device = txt if isinstance(txt, str) and txt else "Lung Phantom"
    self.run_device = run_device

    # Parse target starting coordinates from first_g1 for exact snapshot anchor
    snapshot = _parse_g1_targets(first_g1) if first_g1 else {}

    self.status_stopped = False
    if first_g1:
        try:
            t_sent = time.perf_counter()
            duet_request(url, params={'gcode': f'G90\n{first_g1}\nM400'}, timeout=5)
            # Wait until the live samples show the platform at the start position
            _wait_for_preposition(self, snapshot, t_sent)
        except Exception as e:
            print(f"Pre-positioning move failed: {e}")

    self._start_pos_snapshot = snapshot if snapshot else None
    self._last_auto_sf = 100.0

    # Start from a clean plot (previous curves, reference, pause lines, probe shading) ...
    try:
        clear_status_plot_data(self)
    except Exception as e:
        print(f"Could not clear the status plot: {e}")
    # ... and show this file's planned trajectory as reference when it can be loaded
    # (before t0: downloading/parsing can take a while)
    ref_ok = False
    try:
        ref_ok = bool(auto_load_current_gcode_reference(self, filename=fname, force=False))
    except Exception as e:
        print(f"Could not load the reference for {fname}: {e}")
    if not ref_ok:
        self.status_reference_data = None
    show_ref_check = getattr(self, 'check_show_reference', None)
    if show_ref_check is not None and hasattr(show_ref_check, 'setChecked'):
        show_ref_check.blockSignals(True)
        show_ref_check.setChecked(ref_ok)
        show_ref_check.blockSignals(False)

    # One time zero for the log and the plot, taken right before the job is started
    t0 = time.perf_counter()
    self.run_wall = datetime.now()
    self.run_t0 = t0
    self.log_t0 = t0
    self.status_t0 = t0
    self.status_plot_data = None
    self._total_pause_duration = 0.0
    self._pause_start_perf = None
    self.run_seen_running = False
    self.run_idle_since = None
    self._dash_idle_count = 0
    self._release_mark_t = None
    self._sensor_wait = None             # sensor_wait.g wait being marked (PROBE_WAIT_MARK)
    self._wait_triggers = []             # recent in-run samples with detector > 500 or Release (race guard)
    self._release_used_t = None          # Release press that already ended a marked wait
    self._wait_prev_sample_t = None
    self._pending_log_comments = []
    self._run_gap_open = False
    self._log_open_failed = False
    self.run_gcode = f"0:/gcodes/{fname}"
    self.run_active = True
    # Mark G-code execution as active for continuous logging and clean completion detection
    self.gcode_executing = True
    self.gcode_seen_running = False
    self.gcode_started_time = t0

    try:
        duet_request(url, params={'gcode': f'M32 0:/gcodes/{fname}'}, timeout=4)
        if hasattr(self, 'statusDuetMessage') and self.statusDuetMessage is not None:
            self.statusDuetMessage.setText(f"Started execution of 0:/gcodes/{fname}")
        # Recording starts with the first live position sample taken after run_t0
        # (handle_position_sample); no synthetic t=0 row from the G-code target.
    except Exception as e:
        end_run(self, "start failed")
        QMessageBox.warning(self, "Duet Error", f"Failed to start execution of {fpath}: {e}")


_PLATFORM_LETTERS = {"A", "B", "C", "D", "'a", "'c", "'e", "'f"}
_PHANTOM_LETTERS = {"X", "Y", "Z"}


def _parse_g1_targets(g1_line):
    """Axis targets of one G1 line, e.g. {'A': 35.0, "'e": 50.0, 'e': 50.0}."""
    import re
    snapshot = {}
    pattern = re.compile(r"('?[a-zA-Z])([-+]?\d*\.\d+|[-+]?\d+)")
    for axis, val in pattern.findall(g1_line or ""):
        if axis in ('G', 'F', 'g', 'f') and not axis.startswith("'"):
            continue
        if axis.startswith("'") or (len(axis) == 1 and axis.islower()):
            clean_ax = axis.strip("'").lower()
            snapshot[f"'{clean_ax}"] = float(val)
            snapshot[clean_ax] = float(val)
        else:
            norm_axis = axis.upper() if (len(axis) == 1 and axis.isalpha()) else axis
            snapshot[norm_axis] = float(val)
    return snapshot


def _device_from_gcode_lines(lines):
    """
    Device of a G-code job from the axis letters of its G0/G1 moves:
    any of A B C D 'a 'c 'e 'f -> "Motion Platform"; only X/Y/Z -> "Lung Phantom"; else None.
    """
    import re
    word = re.compile(r"('[a-zA-Z]|[A-Za-z])\s*[-+]?(?:\d+\.\d*|\.\d+|\d+)")
    seen = set()
    for raw in lines or []:
        line = str(raw).split(';')[0].strip()
        if not line or line[0] not in "Gg":
            continue
        m = re.match(r"[Gg]0*([01])(?![\d.])", line)
        if not m:
            continue
        for let in word.findall(line[m.end():]):
            if let.startswith("'"):
                seen.add("'" + let[1].lower())
            elif let in ("F", "f"):
                continue
            else:
                seen.add(let.upper())
        if seen & _PLATFORM_LETTERS:
            return "Motion Platform"
    if seen and seen <= _PHANTOM_LETTERS:
        return "Lung Phantom"
    return None


def _wait_for_preposition(self, targets, t_sent, timeout=30.0, tol=0.02):
    """
    Waits (processing GUI events, so live samples keep arriving) until a sample taken
    after the pre-position command shows every target axis within `tol` mm and, when the
    sample carries the Duet state, the machine is idle again. Gives up after `timeout` s.
    """
    from PySide6.QtCore import QCoreApplication
    keys = [k for k in targets if k.startswith("'") or (len(k) == 1 and k.isupper())]
    if not keys:
        return True
    min_t = t_sent + 0.25          # machinePosition can be up to ~200 ms old (RRF cache)
    t_start = time.perf_counter()
    while time.perf_counter() - t_start < timeout:
        if not getattr(self, 'duet_connected', False):
            return False
        QCoreApplication.processEvents()
        s = getattr(self, '_latest_sample', None)
        if isinstance(s, dict) and s.get('t', 0.0) >= min_t:
            real = s.get('real') or {}
            at_target = all(k in real and abs(float(real[k]) - float(targets[k])) <= tol for k in keys)
            st = s.get('status')
            if at_target and (st is None or st == 'I'):
                return True
        time.sleep(0.02)
    print(f"Pre-positioning: start position not confirmed within {timeout:.0f} s; starting anyway.")
    return False


_PLATFORM_LOG_AXES = [("LAT", "mm"), ("SI", "mm"), ("AP", "mm"), ("Roll", "deg"), ("Pitch", "deg"), ("Yaw", "deg")]
# Raw actuator axes of the platform (the Status plot can show them too). Never W or V: the log
# readers map those letters to Yaw / Pitch.
_PLATFORM_RAW_AXES = ["A", "B", "C", "D", "'e", "'f", "'a", "'c"]
_PHANTOM_LOG_AXES = [("X", "mm"), ("Y", "mm"), ("Z", "mm")]
PROBE_RELEASE_MARK = 2000          # Probe value written while the Release button marker is active
PROBE_RELEASE_HOLD_S = 0.5
PROBE_WAIT_MARK = -1000            # Probe value written while sensor_wait.g waits (detector at 0 or below)
SENSOR_WAIT_THRESHOLD = 500        # sensor_wait.g waits while sensors.probes[0].value[0] <= 500
SENSOR_WAIT_MSG = "Waiting for sensor signal"    # sensor_wait.g echo when its wait starts
SENSOR_WAIT_END_MSGS = ("continuing", "force released", "sensor detected")   # ... when it ends (lower case)
REPLY_POLL_PERIOD_S = 0.5          # ReplyPoller without reply sequence numbers: rr_reply read this often
REPLY_POLL_SLOW_S = 1.0            # ... in split mode (slow link) during a run (sensor-wait marks); else at each dashboard tick
REPLY_POLL_SAFETY_S = 5.0          # ... with sequence numbers (seqs.reply): read on a change, else this often
REPLY_SEQ_FRESH_S = 1.0            # sequence numbers count while a position sample carried one this recently
REPLY_SEQ_MIN_GAP_S = 0.15         # ... and a changed one is read at most this soon after the previous read
REPLY_POLL_RETRY_S = 0.25          # a failed read is repeated after this (the Duet may still hold the text)
REPLY_POLL_TIMEOUT_S = 2.5         # rr_reply hands its text out on handling: a timed-out read loses it
REPLY_STOP_WAIT_S = 0.5            # stop() waits at most this long for an in-flight read (normally ~0.07 s)
REPLY_LATENCY_GUESS_S = 0.06       # send time of a read when the caller gives none (t_fetch - this)
WAIT_RACE_SLACK_S = 0.02           # the macro's 10 ms loop + 10 ms: race window after a sample's reply
RELEASE_CMD_DELAY_S = 0.15         # press -> force-release command handled by the Duet (at most)
RELEASE_DEBOUNCE_S = 0.3           # a Release press this soon after the previous one was handled is a double click
WAIT_POS_SETTLE_S = 0.35           # machinePosition can lag 200 ms after the wait's M400: settle first
WAIT_MOVE_TOL = 0.02               # mm / deg: an axis moved this far during a wait -> the wait has ended
LOG_SEP = ";"                      # log format v2: ';' between the columns and a decimal comma (Excel, NL/EU locale)


def _dc(x, fmt):
    """A number for the log (format v2): decimal comma."""
    return format(x, fmt).replace('.', ',')


def _note_text(line):
    """A '#' line of the log never holds ';' (Excel would split it into cells)."""
    return str(line).replace(';', ',')


def _product_device_label(device):
    """'Motion Platform' -> 'KINETIQ', 'Lung Phantom' -> 'DYNAMIQ' for the '# Device:' log line."""
    try:
        from fcn_logs.product_names import device_label
        return device_label(device)
    except Exception:
        return device


def _log_device(self, extra_axes):
    """Device whose columns a new log file gets: the running job's device, else the Planning combo."""
    dev = getattr(self, 'run_device', None)
    if isinstance(dev, str) and dev in ("Motion Platform", "Lung Phantom"):
        return dev
    combo = getattr(self, 'combo_device', None)
    txt = combo.currentText() if combo is not None and hasattr(combo, 'currentText') else None
    if isinstance(txt, str) and txt in ("Motion Platform", "Lung Phantom"):
        return txt
    return "Motion Platform" if extra_axes is not None else "Lung Phantom"


def _log_file_path(self, when):
    """<folder>/log_DDMMYYYY_HH_MM_SS.csv (with _1, _2 ... if that name exists)."""
    folder = None
    w = getattr(self, 'PhOperFolder', None)
    try:
        txt = w.text().strip() if w is not None else ""
        if isinstance(txt, str) and txt:
            folder = txt
    except Exception:
        folder = None
    if not folder:
        folder = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.exists(folder):
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception:
            folder = os.path.join(os.path.expanduser("~"), "Desktop")
    base = f"log_{when.strftime('%d%m%Y_%H_%M_%S')}"
    filepath = os.path.join(folder, f"{base}.csv")
    idx = 1
    while os.path.exists(filepath):
        filepath = os.path.join(folder, f"{base}_{idx}.csv")
        idx += 1
    return filepath


def log_data_point(self, t, x, y, z, probe=0, extra_axes=None, raw_axes=None):
    """
    Writes one live sample (actual positions + probe) to the log file of the current run,
    log_DDMMYYYY_HH_MM_SS.csv inside the selected output folder (default Desktop).
    The file is opened on the first sample, with a commented header (computer time with ms
    at the run's time zero, device, axis mapping, meaning of the columns).

    Columns follow the running job's device (G-code letters), not the Planning tab:
      Motion Platform: Time_s, Pos_LAT/SI/AP_mm, Pos_Roll/Pitch/Yaw_deg,
                       Pos_A/B/C/D_mm, Pos_'e/'f/'a/'c_mm (raw actuators), Probe
      Lung Phantom:    Time_s, Pos_X/Y/Z_mm, Probe
    """
    if not hasattr(self, 'active_log_file') or self.active_log_file is None:
        if getattr(self, '_log_open_failed', False) is True:
            return              # already reported for this run; do not retry on every sample
        in_run = getattr(self, 'run_active', False) is True
        run_wall = getattr(self, 'run_wall', None)
        now_dt = run_wall if isinstance(run_wall, datetime) and in_run else datetime.now()
        device = _log_device(self, extra_axes)
        is_platform = device == "Motion Platform"
        gcode = getattr(self, 'run_gcode', None) if in_run else None
        letters = getattr(self, '_axis_letters_used', None)
        letters_txt = ",".join(str(l) for l in letters if l) if isinstance(letters, (list, tuple)) and letters else "unknown"
        t_rec = float(t) if in_run and isinstance(t, (int, float)) else 0.0

        # Fixed 10-line header (format v2, every line starts with '#'), then the column names
        header = [
            f"# Computer Time: {now_dt.strftime('%Y-%m-%d %H:%M:%S')}.{now_dt.microsecond // 1000:03d}",
            _note_text(f"# G-code: {gcode if isinstance(gcode, str) and gcode else 'none'}"),
            f"# Device: {_product_device_label(device)}",          # DYNAMIQ / KINETIQ (readers accept old names)
            f"# Axes (Duet order): {letters_txt}",
            "# Positions: actual (Duet machinePosition, refreshed at most every 200 ms, CAN expansion-board axes about every 100 ms)",
            f"# Probe: 0 none | 1-1499 detector | {PROBE_RELEASE_MARK} Release button | {PROBE_WAIT_MARK} waiting for sensor (sensor_wait)",
            f"# Wait timing: start = when LogIQ received the Duet message (read as soon as a position sample shows a new "
            f"message, else every {_dc(REPLY_POLL_PERIOD_S, 'g')}-{_dc(REPLY_POLL_SLOW_S, 'g')} s), so the real start is "
            f"earlier, normally by up to ~{_dc(REPLY_POLL_PERIOD_S, 'g')} s (on a slow link up to "
            f"~{_dc(REPLY_POLL_SLOW_S + 1.0, 'g')} s). End = first position sample with the detector "
            f"above {SENSOR_WAIT_THRESHOLD} or Release pressed (within one sample, ~0,08 s), otherwise as stated at the end "
            f"of the file",
            "# Run notes: the times of each sensor wait (with the window in which the Duet sent its message), connection "
            "gaps and the run end are listed at the end of the file",
            f"# Recording from: {_dc(t_rec, '.3f')} s of the run",
            "# Format: columns separated by semicolons, decimal comma",
        ]
        if is_platform:
            columns = (["Time_s"] + [f"Pos_{n}_{u}" for n, u in _PLATFORM_LOG_AXES]
                       + [f"Pos_{a}_mm" for a in _PLATFORM_RAW_AXES] + ["Probe"])
        else:
            columns = ["Time_s"] + [f"Pos_{n}_{u}" for n, u in _PHANTOM_LOG_AXES] + ["Probe"]

        filepath = _log_file_path(self, now_dt)
        f = None
        errors = []
        for attempt in (filepath, os.path.join(os.path.expanduser("~"), "Desktop", os.path.basename(filepath))):
            try:
                f = open(attempt, "w", encoding="utf-8")
                filepath = attempt
                break
            except Exception as e:
                errors.append(f"{attempt}: {e}")
        if f is None:
            self._log_open_failed = True
            msg = f"Could not create the data log file ({'; '.join(errors)})"
            print(msg)
            if hasattr(self, 'statusDuetMessage') and self.statusDuetMessage is not None and hasattr(self.statusDuetMessage, 'setText'):
                self.statusDuetMessage.setText(msg)
            return
        if errors:
            print(f"Log folder not writable, logging to {filepath} instead ({errors[0]})")
        try:
            f.write("\n".join(header) + "\n")
            f.write(LOG_SEP.join(columns) + "\n")
            # Run notes are kept in memory and written after the last row (close_data_log_file);
            # '# Wait ...' notes from before the first row join them
            pending = getattr(self, '_pending_log_comments', None)
            self._log_notes = [x for x in pending if isinstance(x, tuple)] if isinstance(pending, list) else []
            self._pending_log_comments = []
            f.flush()
            self.active_log_file = f
            self.active_log_filepath = filepath
            self.active_log_is_platform = is_platform
            w = getattr(self, '_sensor_wait', None)
            if in_run and isinstance(w, dict) and w.get('started'):
                _note_wait_start(self, w)     # opened during a marked wait (Record off and on again)
            print(f"Started recording data log to file: {filepath} ({device}) at computer time {now_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            print(f"Failed to write data log header {filepath}: {e}")
            return

    try:
        p_val = probe if probe is not None else 0
        if getattr(self, 'active_log_is_platform', False):
            pos = extra_axes if extra_axes is not None else {}
            raw = raw_axes if raw_axes is not None else {}
            fields = ([f"{t:.4f}"] + [f"{float(pos.get(n, 0.0)):.3f}" for n, _ in _PLATFORM_LOG_AXES]
                      + [f"{float(raw.get(a, 0.0)):.3f}" for a in _PLATFORM_RAW_AXES] + [f"{p_val}"])
        else:
            fields = [f"{t:.4f}", f"{float(x):.3f}", f"{float(y):.3f}", f"{float(z):.3f}", f"{p_val}"]
        # format v2: ';' between the columns, decimal comma (the fields are numbers only)
        self.active_log_file.write(LOG_SEP.join(fields).replace('.', ',') + "\n")
        self.active_log_file.flush()
    except Exception as e:
        print(f"Error writing to data log file: {e}")


def close_data_log_file(self, reason="closed"):
    """
    Closes the active log file (recording unchecked, run finished, cancelled, disconnected ...).
    Writes the run notes kept in memory ('# Wait ...', '# Gap ...', '# Message read failed ...', in
    time order) after the last row, then a '# End: <reason> at <t> s' line (always the last line).
    """
    if hasattr(self, 'active_log_file') and self.active_log_file is not None:
        try:
            t_end = None
            t0 = getattr(self, 'run_t0', None)
            if isinstance(t0, float):
                t_end = time.perf_counter() - t0
            w = getattr(self, '_sensor_wait', None)
            if (getattr(self, 'run_active', False) is True and isinstance(w, dict) and w.get('started')
                    and w.get('end') is not None):
                # The Duet's end message was already read (no sample applied it yet): that is the end
                _end_sensor_wait(self, *w['end'][1:3], t=w['end'][0])
                w = None
            notes = getattr(self, '_log_notes', None)
            notes = list(notes) if isinstance(notes, list) else []
            if (getattr(self, 'run_active', False) is True and isinstance(w, dict) and w.get('started')
                    and t_end is not None):
                # Record off during a marked wait: this log's -1000 rows stop here, the wait goes on
                notes.append((t_end, _note_text(f"# Wait end: {reason} at {_dc(t_end, '.3f')} s (the log was "
                                                f"closed while the wait was still going on)")))
            out = [line for _t, line in sorted(notes, key=lambda x: x[0])]
            if reason:
                out.append(_note_text(f"# End: {reason}" + (f" at {_dc(t_end, '.3f')} s" if t_end is not None else "")))
            if out:
                self.active_log_file.write("\n".join(out) + "\n")
            self.active_log_file.flush()
            self.active_log_file.close()
            print(f"Closed data log file: {getattr(self, 'active_log_filepath', '')} ({reason})")
        except Exception:
            pass
        self.active_log_file = None
        self.active_log_filepath = None
        self._log_notes = []
    if getattr(self, 'run_active', False) is not True:
        self.log_t0 = None


def end_run(self, reason):
    """Ends the current run: closes its log with `reason` and clears the run flags."""
    was_active = getattr(self, 'run_active', False) is True
    _end_sensor_wait_at_run_end(self, reason)       # a sensor wait still marked ends with the run
    self.run_active = False
    self.gcode_executing = False
    self.gcode_seen_running = False
    self.run_idle_since = None
    close_data_log_file(self, reason)
    self._sensor_wait = None
    self._pending_log_comments = []
    self.log_t0 = None
    if was_active:
        print(f"Run ended: {reason}")


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

    ip = get_clean_duet_ip(self)
    try:
        data, status_code = duet_status_request(self, ip, timeout=5)
        if status_code != 200 or data is None:
            self.duet_connected = False
            from fcn_control.fcn_control import update_connection_status_ui, log_to_duet_console
            update_connection_status_ui(self, connected=False)
            log_to_duet_console(self, "Connection lost: Duet is offline or powered off.", color="#ff3333")
            return
    except Exception as ex:
        self.duet_connected = False
        from fcn_control.fcn_control import update_connection_status_ui, log_to_duet_console
        update_connection_status_ui(self, connected=False)
        log_to_duet_console(self, f"Connection lost: Duet unreachable ({ex})", color="#ff3333")
        return

    self._last_dashboard_poll_t = time.perf_counter()   # lets the 2 s heartbeat skip its duplicate poll

    # A partly failed poll (empty 'state' reply) carries no status: keep the last known one
    # instead of reading it as 'Idle' (which used to end the log in the middle of a job)
    if isinstance(data, dict) and not data.get("status"):
        data["status"] = getattr(self, 'duet_status_code', None) or "I"
        data["_status_unknown"] = True

    # Keep the G-code name visible: the running job's file, else the selected one
    try:
        job_file = data.get("jobFileName") if isinstance(data, dict) else None
        if job_file and data.get("status") in ("P", "S", "D", "R", "M"):
            update_gcode_name_label(self, job_file)
    except Exception:
        pass

    # Update Control tab UI with data even if Status tab widgets aren't instantiated
    try:
        from fcn_control.fcn_control import update_duet_status_ui
        update_duet_status_ui(self, data=data)
    except Exception as ex:
        print(f"Error updating Control UI from status poll: {ex}")

    if not hasattr(self, 'statusBadgeLabel') or self.statusBadgeLabel is None:
        return

    try:
        # Poll /rr_reply for Duet messages (e.g. M117, macro responses, 'waiting for radiation'),
        # unless the ReplyPoller runs: it is then the only rr_reply reader (the Duet hands each
        # reply out once) and its replies reach handle_duet_reply directly
        if not _reply_poller_running(self):
            try:
                t_send = time.perf_counter()
                res_reply = duet_request(f'http://{ip}/rr_reply', timeout=2)
                if res_reply.status_code == 200:
                    t_prev, self._rr_reply_prev_t = getattr(self, '_rr_reply_prev_t', None), t_send
                    handle_duet_reply(self, (time.perf_counter(), t_prev, res_reply.text, t_send))
            except Exception:
                pass
        else:
            try:
                self.duet_reply_poller.dashboard_tick()    # split mode: the poller reads now, the tick waits (old rate)
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
            "D": ("Pausing", "#ff9800"),     # Orange
            "T": ("Tool change", "#ff5722"), # Deep Orange
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
                return "--"
            sec_int = int(round(float(sec)))
            if sec_int < 60:
                return f"{sec_int}s"
            m, s = divmod(sec_int, 60)
            h, m = divmod(m, 60)
            if h > 0:
                return f"{h}h {m:02d}m {s:02d}s"
            else:
                return f"{m}m {s:02d}s"

        if hasattr(self, 'labelPrintDuration') and self.labelPrintDuration:
            self.labelPrintDuration.setText(f"Print Duration: {format_sec(print_dur)}")
        if hasattr(self, 'labelTimeRemaining') and self.labelTimeRemaining:
            self.labelTimeRemaining.setText(f"Time left: {format_sec(time_left)}")

        # 4. Sensors (Z-Probe). A failed/empty sensors reply has no probe value: keep the last
        # one and skip the auto-release / auto-pause checks (it used to read as probe 0)
        probe = data.get("sensors", {}).get("probeValue", 0) if isinstance(data.get("sensors"), dict) else None
        probe_known = probe is not None and not data.get("_status_unknown", False)
        if probe is not None:
            self._last_probe_val = probe
            if hasattr(self, 'statusProbe') and self.statusProbe:
                self.statusProbe.setText(f"Probe: {probe}")

        # Auto-release on trigger check: if paused (S), checkbox checked, and probe > 500, auto-resume
        if status_code == 'S' and probe_known:
            check_auto = getattr(self, 'check_auto_release', None)
            if check_auto is not None and check_auto.isChecked() and probe > 500:
                self.duet_status_code = 'R'  # Prevent double triggers
                pause_continue_GCODE(self, pause=False)

        # Auto pause check: if active (not paused 'S', pausing 'D' or idle 'I'), checkbox checked, and probe == 0, auto-pause
        if status_code not in ['S', 'I', 'D'] and probe_known:
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

        # Auto-sync speed processing during active printing/motion
        if status_code in ["P", "R", "S", "M", "B"]:
            try:
                process_auto_sync_speed(self)
            except Exception as se:
                print(f"Error in auto-sync speed: {se}")

        # Reset error count on successful status update
        self.duet_status_errors = 0

        # 5. Render graph update every second (continuous rendering whenever monitored)
        if not getattr(self, 'status_stopped', False):
            try:
                render_status_plot(self)
            except Exception as pe:
                print(f"Error rendering status plot: {pe}")
        # End of a run. When the live samples carry the Duet state (combined poll), the run end is
        # decided there, per sample (handle_position_sample). Otherwise the dashboard decides,
        # but only on two consecutive real 'Idle' readings: one stray 'I' must not end the log.
        last_state_t = getattr(self, '_last_sample_status_t', None)
        fast_state = isinstance(last_state_t, float) and (time.perf_counter() - last_state_t) < 2.0
        if not data.get("_status_unknown", False) and not fast_state:
            if status_code in ["P", "R", "B", "M", "S", "D", "T"]:
                self.gcode_seen_running = True
                self._dash_idle_count = 0
            elif status_code == "I":
                self._dash_idle_count = getattr(self, '_dash_idle_count', 0) + 1
                if getattr(self, 'run_active', False) is True and self._dash_idle_count >= 2:
                    run_t0 = getattr(self, 'run_t0', None)
                    if getattr(self, 'gcode_seen_running', False):
                        end_run(self, "job finished")
                    elif isinstance(run_t0, float) and time.perf_counter() - run_t0 >= RUN_START_TIMEOUT_S:
                        end_run(self, "job did not start (or finished between status polls)")
        if getattr(self, 'run_active', False) is not True and getattr(self, 'active_log_file', None) is not None:
            close_data_log_file(self, "no active run")

    except Exception as e:
        print(f"Error updating status tab dashboard: {e}")
        err_cnt = getattr(self, 'duet_status_errors', 0) + 1
        self.duet_status_errors = err_cnt
        if err_cnt >= 3:
            self.duet_connected = False
            from fcn_control.fcn_control import update_connection_status_ui
            update_connection_status_ui(self, connected=False)


def process_auto_sync_speed(self):
    """
    Evaluates phase lag using sliding window cross-correlation and adjusts Duet Speed Factor (M220) automatically.
    If required speed adjustment exceeds max_limit (default 20%), turns Auto-sync OFF and alerts user.
    """
    check_sync = getattr(self, 'check_auto_sync', None)
    if check_sync is None or not check_sync.isChecked():
        return

    plot_data = getattr(self, 'status_plot_data', None)
    ref_data = getattr(self, 'status_reference_data', None)
    if not plot_data or not ref_data:
        return

    t_live = plot_data.get('t', [])
    if len(t_live) < 30:  # Need at least ~3 seconds of live position points
        return

    t_elapsed = t_live[-1]
    if t_elapsed < 4.0:
        return

    # Select primary signal trace for correlation
    target_key = None
    for key in ['AP', 'LAT', 'SI', 'Roll', 'X', 'Y', 'Z']:
        if key in plot_data and key in ref_data and len(plot_data[key]) == len(t_live):
            target_key = key
            break

    if not target_key:
        return

    # Take recent 15s window of live plot points
    window_sec = 15.0
    recent_indices = [i for i, t in enumerate(t_live) if t >= max(0.0, t_elapsed - window_sec)]
    if len(recent_indices) < 15:
        return

    t_win = np.array([t_live[i] for i in recent_indices], dtype=float)
    y_win = np.array([plot_data[target_key][i] for i in recent_indices], dtype=float)

    # Interpolate matching reference values over same time window
    ref_t = ref_data.get('t', [])
    ref_y = ref_data.get(target_key, [])
    if len(ref_t) < 2 or len(ref_y) != len(ref_t):
        return

    # Apply any manual Ref. Offset
    ref_offset = 0.0
    if hasattr(self, 'input_ref_offset') and self.input_ref_offset is not None:
        try: ref_offset = float(self.input_ref_offset.text().strip())
        except ValueError: pass

    y_ref_win = np.interp(t_win - ref_offset, ref_t, ref_y)

    dt_sample = float(np.mean(np.diff(t_win))) if len(t_win) > 1 else 0.02
    if dt_sample <= 0:
        return

    # Estimate time lag via cross-correlation
    max_shift_samples = int(3.0 / dt_sample)
    y_win_norm = y_win - np.mean(y_win)
    y_ref_norm = y_ref_win - np.mean(y_ref_win)

    if np.std(y_win_norm) < 1e-3 or np.std(y_ref_norm) < 1e-3:
        return

    corr = np.correlate(y_win_norm, y_ref_norm, mode='full')
    zero_idx = len(y_win_norm) - 1
    search_start = max(0, zero_idx - max_shift_samples)
    search_end = min(len(corr), zero_idx + max_shift_samples + 1)

    best_idx = search_start + int(np.argmax(corr[search_start:search_end]))
    sample_shift = best_idx - zero_idx
    time_lag = sample_shift * dt_sample  # positive = live lags behind reference

    # Calculate required speed factor
    drift_rate = time_lag / max(1.0, t_elapsed)
    required_sf = 100.0 * (1.0 + drift_rate) + (time_lag * 0.5)
    required_sf = max(10.0, min(300.0, required_sf))
    required_adj_pct = abs(required_sf - 100.0)

    # Read maximum allowed adjustment limit (default 20%)
    max_limit = 20.0
    if hasattr(self, 'input_max_speed_adj') and self.input_max_speed_adj is not None:
        try:
            val = float(self.input_max_speed_adj.text().strip())
            if val > 0:
                max_limit = val
        except ValueError:
            max_limit = 20.0

    # Limit check: if required adjustment > max_limit, disable Auto-sync and warn user
    if required_adj_pct > max_limit:
        self.check_auto_sync.setChecked(False)  # Turn Auto-sync OFF
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(
            self,
            "Auto-Sync Limit Exceeded",
            f"Auto-Sync Disabled!\n\n"
            f"Required speed adjustment ({required_adj_pct:.1f}%) exceeds maximum limit ({max_limit:.1f}%).\n\n"
            f"Auto-Sync has been turned OFF for safety. Please check your setup or adjust speed manually."
        )
        return

    # Apply speed adjustment if within limits and changed by >= 0.5%
    last_applied = getattr(self, '_last_auto_sf', 100.0)
    if abs(required_sf - last_applied) >= 0.5:
        self._last_auto_sf = required_sf
        self.status_speed_factor = required_sf
        if hasattr(self, 'labelSf') and self.labelSf:
            self.labelSf.setText(f"{required_sf:.1f}%")
        set_GCODE_speed(self, required_sf)


# Status codes for which the live position poll runs (same set the GUI handler accepts)
_POLL_STATUS_CODES = ("P", "S", "R", "M", "I", "D", "B", "C", "T")
_LIVE_AXES = ['X', 'Y', 'Z', 'A', 'B', 'C', 'D', "'e", "'f", "'a", "'c", 'W', 'V']
_DEFAULT_AXES_11 = ['X', 'Y', 'Z', 'A', 'B', 'C', 'D', "'a", "'c", "'e", "'f"]
_DEFAULT_AXES_13 = ['X', 'Y', 'Z', 'V', 'W', 'A', 'B', 'C', 'D', "'a", "'c", "'e", "'f"]

# RRF object-model state.status -> one-letter status code used by TRACE
RRF_STATUS_CODES = {
    "idle": "I", "processing": "P", "simulating": "M", "paused": "S", "pausing": "D",
    "resuming": "R", "homing": "H", "busy": "B", "configuring": "C", "updating": "B",
    "off": "I", "halted": "B", "changingtool": "T", "cancelling": "B", "starting": "B",
}

# Live poll: one snapshot of the live object model per sample (positions, probe and state at
# the same instant). Falls back to the keyed requests (positions, then probe) if the Duet
# cannot serve it reliably or fast enough.
COMBINED_POLL_PATH = "rr_model?flags=d99f"
COMBINED_MAX_FAILS = 3              # consecutive failures before falling back
COMBINED_PROBE_SAMPLES = 20         # requests used to judge the combined latency
COMBINED_MAX_MEDIAN_S = 0.15        # fall back if the combined request is slower than this
COMBINED_RETRY_S = 30.0             # in split mode, try the snapshot again this often
RUN_IDLE_END_S = 1.0                # a run ends after the Duet reports idle this long
RUN_START_TIMEOUT_S = 10.0          # ... or if the job never shows a running state


def _num(v):
    """Float value of an object-model number, or None if missing / null."""
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _put_axis(target, let, value):
    """Store an axis value under its letter and the plain / quoted aliases ('a, a)."""
    clean = str(let).strip("'").strip()
    target[let] = value
    target[clean] = value
    target[f"'{clean}"] = value


def _om_letter(let):
    """Object-model axis letter -> TRACE axis name ('a' -> "'a", 'A' -> 'A')."""
    s = str(let).strip()
    if s.startswith("'"):
        return "'" + s[1:].lower() if len(s) > 1 else s
    if len(s) == 1 and s.islower():
        return "'" + s
    return s


def _axis_order(self, n):
    """Axis names for a move.axes list of length n: letters fetched from the Duet when their count
    matches, else the configured axes, else the default order of this platform build."""
    fetched = getattr(self, '_om_axis_letters', None)
    if isinstance(fetched, (list, tuple)) and len(fetched) != n:
        self._om_axis_letters = None          # axes changed (or stale letters): fetch them again
        fetched = None
    for cand in (fetched, getattr(self, 'duet_configured_axes', None)):
        if isinstance(cand, (list, tuple)) and len(cand) == n:
            return [_om_letter(c) for c in cand]
    if n == 11:
        return list(_DEFAULT_AXES_11)
    if n == 13:
        return list(_DEFAULT_AXES_13)
    return None


def _axes_from_list(self, axes_list):
    """move.axes list -> (real, cmd, homed). real = machinePosition (actual), cmd = userPosition."""
    real, cmd, homed = {}, {}, {}
    missing_machine = False
    order = _axis_order(self, len(axes_list))
    if order is None and not all(isinstance(ax, dict) and "letter" in ax for ax in axes_list):
        # Unknown axis count and no letters: naming by index would log zeros for every axis
        if not getattr(self, '_axis_count_warned', False):
            self._axis_count_warned = True
            print(f"Live poll: {len(axes_list)} axes reported and their letters are unknown; samples skipped until the letters are fetched.")
        return None
    used = []
    for idx, ax in enumerate(axes_list):
        if not isinstance(ax, dict):
            used.append(None)
            continue
        if "letter" in ax:
            let = _om_letter(ax["letter"])
        elif order is not None:
            let = order[idx]
        else:
            let = str(idx)
        used.append(let)

        user_pos = _num(ax.get("userPosition"))
        mach_pos = _num(ax.get("machinePosition"))
        if mach_pos is None:
            missing_machine = True
        if user_pos is None:
            user_pos = mach_pos if mach_pos is not None else 0.0
        _put_axis(cmd, let, user_pos)
        _put_axis(real, let, mach_pos if mach_pos is not None else user_pos)

        if "homed" in ax or "userHomed" in ax:
            homed_val = ax.get("homed", ax.get("userHomed", 0))
            homed[let] = (homed_val == 1 or homed_val is True)

    self._axis_letters_used = used
    if missing_machine and not getattr(self, '_machine_pos_missing_noted', False):
        self._machine_pos_missing_noted = True
        print("Duet does not report move.axes[].machinePosition: logging userPosition "
              "(requested position, runs ahead of the motors) instead.")
    return real, cmd, homed


def get_positions_only_fast(self, ip, legacy=True, retry=True):
    """
    Fetches the axis positions with one light request (safe to call from a worker thread:
    it touches no widgets). Uses RRF3 /rr_model?key=move.axes&flags=f; with legacy=True it
    falls back to /rr_status?type=2 (not served by RRF 3.6).

    Returns {'real', 'cmd', 'homed', 'probe'} or None:
      real  - machinePosition: where the motors actually are
      cmd   - userPosition: end point of the last QUEUED move (runs ahead of the motors)
      homed - {letter: bool} (only when the reply carries it)
      probe - probe value when the response carries it (legacy path), else None
    """
    # 1. RRF3 Model Path (lightweight key query using flags=f for fast single-page response of all axes)
    try:
        url = f"http://{ip}/rr_model?key=move.axes&flags=f"
        response = duet_request(url, timeout=0.8, retry=retry)
        if response.status_code == 200:
            axes_list = response.json().get("result", [])
            if isinstance(axes_list, list) and axes_list:
                parsed = _axes_from_list(self, axes_list)
                if parsed is None:
                    return None
                real, cmd, homed = parsed
                return {'real': real, 'cmd': cmd, 'homed': homed, 'probe': None}
    except Exception:
        pass

    if not legacy:
        return None

    # 2. Legacy /rr_status?type=2 Fallback
    try:
        url_legacy = f"http://{ip}/rr_status?type=2"
        response_legacy = duet_request(url_legacy, timeout=0.8)
        if response_legacy.status_code == 200:
            data = response_legacy.json()
            coords = data.get("coords", {})
            xyz = coords.get("xyz", [0.0, 0.0, 0.0])
            machine = coords.get("machine")
            if not isinstance(machine, list) or len(machine) != len(xyz):
                machine = xyz
            axes_homed = coords.get("axesHomed", [])

            axes_rrf_order = getattr(self, 'duet_configured_axes', None)
            if not axes_rrf_order:
                if len(axes_homed) == 11 or len(xyz) == 11:
                    axes_rrf_order = list(_DEFAULT_AXES_11)
                else:
                    axes_rrf_order = list(_DEFAULT_AXES_13)

            real, cmd, homed = {}, {}, {}
            for idx, ax_name in enumerate(axes_rrf_order):
                if idx < len(xyz):
                    _put_axis(cmd, ax_name, _num(xyz[idx]) or 0.0)
                    _put_axis(real, ax_name, _num(machine[idx]) or 0.0)
                if idx < len(axes_homed):
                    homed[ax_name] = (axes_homed[idx] == 1)

            probe = data.get("sensors", {}).get("probeValue") if isinstance(data.get("sensors"), dict) else None
            return {'real': real, 'cmd': cmd, 'homed': homed, 'probe': probe}
    except Exception:
        pass

    return None


def _probe_from_sensors(sensors):
    """Z-probe value from an object-model 'sensors' object (or its probes list), else None."""
    probes = sensors.get("probes") if isinstance(sensors, dict) else sensors
    if isinstance(probes, list) and probes and isinstance(probes[0], dict):
        vals = probes[0].get("value", [])
        if isinstance(vals, list) and vals:
            return vals[0]
        if isinstance(vals, (int, float)):
            return vals
    return None


def _poll_probe_value(ip, retry=True):
    """Current Z-probe value from /rr_model?key=sensors.probes, or None."""
    try:
        res = duet_request(f'http://{ip}/rr_model?key=sensors.probes', timeout=0.8, retry=retry)
        if res.status_code == 200:
            return _probe_from_sensors(res.json().get("result", []))
    except Exception:
        pass
    return None


def fetch_axis_letters(ip, timeout=0.8):
    """
    Axis letters in Duet order from /rr_model?key=move.axes&flags=d99, following the 'next'
    pagination. Returns TRACE axis names (e.g. "'a") or None if incomplete.
    """
    letters = []
    flags = "d99"
    for _page in range(4):
        res = duet_request(f"http://{ip}/rr_model?key=move.axes&flags={flags}", timeout=timeout, retry=False)
        if res.status_code != 200:
            return None
        js = res.json()
        arr = js.get("result", [])
        if not isinstance(arr, list):
            return None
        for ax in arr:
            if not isinstance(ax, dict) or "letter" not in ax:
                return None
            letters.append(_om_letter(ax["letter"]))
        nxt = js.get("next", 0)
        if not nxt:
            return letters or None
        flags = f"d99a{int(nxt)}"
    return None


def _parse_combined_snapshot(self, js):
    """Live object model (flags=d99f) -> {'real', 'cmd', 'homed', 'probe', 'status'} or None."""
    res = js.get("result") if isinstance(js, dict) else None
    if not isinstance(res, dict):
        return None
    move = res.get("move")
    axes_list = move.get("axes") if isinstance(move, dict) else None
    if not isinstance(axes_list, list) or not axes_list:
        return None
    parsed = _axes_from_list(self, axes_list)
    if parsed is None:
        return None
    real, cmd, homed = parsed
    probe = _probe_from_sensors(res.get("sensors"))
    state = res.get("state")
    st_txt = state.get("status") if isinstance(state, dict) else None
    status = RRF_STATUS_CODES.get(str(st_txt).lower()) if st_txt else None
    # seqs.reply (live): goes up when the Duet has a new message for rr_reply (ReplyPoller reads it then)
    seqs = res.get("seqs")
    reply_seq = seqs.get("reply") if isinstance(seqs, dict) else None
    if not isinstance(reply_seq, int) or isinstance(reply_seq, bool):
        reply_seq = None
    return {'real': real, 'cmd': cmd, 'homed': homed, 'probe': probe, 'status': status, 'reply_seq': reply_seq}


def poll_position_sample(self, mode="split", retry=True):
    """
    One live sample, timestamped with time.perf_counter() at the middle of its request
    (worker-thread safe):
      mode="combined": one rr_model?flags=d99f snapshot -> positions, probe and Duet state
                       from the same instant
      mode="split":    positions (key=move.axes&flags=f), then the probe (key=sensors.probes);
                       no state (status None)
    Returns {'t', 'real', 'cmd', 'homed', 'probe', 'status', 'mode', 'latency'} or None.
    """
    ip = getattr(self, 'duet_ip', None) or "192.168.0.1"   # kept current by get_clean_duet_ip (GUI thread)
    if mode == "combined":
        t0 = time.perf_counter()
        try:
            res = duet_request(f"http://{ip}/{COMBINED_POLL_PATH}", timeout=0.8, retry=retry)
            t1 = time.perf_counter()
            if res.status_code != 200:
                return None
            sample = _parse_combined_snapshot(self, res.json())
        except Exception:
            return None
        if not sample:
            return None
        sample.update({'t': 0.5 * (t0 + t1), 'mode': 'combined', 'latency': t1 - t0})
        return sample

    t0 = time.perf_counter()
    sample = get_positions_only_fast(self, ip, legacy=retry, retry=retry)
    t1 = time.perf_counter()
    if not sample:
        return None
    sample.update({'t': 0.5 * (t0 + t1), 'mode': 'split', 'latency': t1 - t0, 'status': None})
    if sample.get('probe') is None:
        sample['probe'] = _poll_probe_value(ip, retry=retry)
        sample['probe_t'] = time.perf_counter()     # the probe was read in a 2nd request, by this time (after 't')
    return sample


try:
    from PySide6.QtCore import QObject, Signal, Slot, Qt

    class PositionPoller(QObject):
        """
        Polls the Duet live positions (+ probe + state) on a background thread and hands every
        sample to `handler` on the GUI thread (queued, in order). The 1 s dashboard and plot
        redraw can block the GUI thread, but samples are still taken on time and are written
        with their own timestamps, so the log has no holes.

        Drop-in for the former 15 ms QTimer (`status_fast_timer`): isActive() / start() / stop().
        start() ignores an interval argument; stop() waits for an in-flight request so file
        transfers do not overlap a position poll (worker requests do not retry, which bounds it).
        A connected -> disconnected change is delivered as {'event': 'disconnected', 't': ...}.
        """
        sample = Signal(object)

        def __init__(self, ui, handler, min_period=0.05, parent=None, mode="combined"):
            super().__init__(parent)
            self._ui = ui
            self._handler = handler
            self._min_period = float(min_period)
            self._preferred_mode = mode
            self.mode = mode
            self._enabled = threading.Event()
            self._quit = threading.Event()
            self._busy = threading.Lock()
            self._thread = None
            self._fails = 0
            self._latencies = []
            self._next_letter_try = 0.0
            self._settle_until = 0.0
            self._next_combined_try = 0.0
            self.companion = None      # e.g. the ReplyPoller: started / stopped / shut down with this poller
            self.sample.connect(self._deliver, Qt.QueuedConnection)

        @Slot(object)
        def _deliver(self, s):
            try:
                self._handler(s)
            except Exception as e:
                print(f"Error in fast status loop: {e}")

        def isActive(self):
            return self._enabled.is_set()

        def start(self, *_ignored):
            self._enabled.set()
            if self._thread is None or not self._thread.is_alive():
                self._quit.clear()
                self._thread = threading.Thread(target=self._run, name="DuetPositionPoller", daemon=True)
                self._thread.start()
            if self.companion is not None:
                self.companion.start()

        def stop(self, wait=3.0):
            self._enabled.clear()
            if self.companion is not None:
                self.companion.stop(wait)
            if self._busy.acquire(timeout=wait):   # wait for an in-flight request
                self._busy.release()

        def shutdown(self, wait=3.0):
            self._quit.set()
            if self.companion is not None:
                self.companion.shutdown(wait)      # first: it then does not wait in stop() below
            self.stop(wait)
            th = self._thread
            if th is not None and th.is_alive():
                th.join(timeout=wait)

        def _reset_connection(self):
            self.mode = self._preferred_mode
            self._fails = 0
            self._latencies = []
            self._next_letter_try = 0.0
            self._settle_until = time.perf_counter() + 2.0     # judge latency after the connect burst
            self._next_combined_try = 0.0
            self._ui._om_axis_letters = None

        def _switch_to_split(self, why):
            if self.mode != "split":
                self.mode = "split"
                self._next_combined_try = time.perf_counter() + COMBINED_RETRY_S
                print(f"Live poll: combined snapshot not usable ({why}); using separate position and probe requests "
                      f"(retrying the snapshot every {COMBINED_RETRY_S:.0f} s).")

        def _try_combined_again(self, s):
            """In split mode: result of the periodic snapshot attempt."""
            if s is not None and float(s.get('latency', 1.0)) <= COMBINED_MAX_MEDIAN_S:
                self.mode = "combined"
                self._fails = 0
                self._latencies = []
                self._settle_until = 0.0
                print(f"Live poll: snapshot available again ({float(s['latency']) * 1000:.0f} ms); back to one request per sample.")
                return True
            self._next_combined_try = time.perf_counter() + COMBINED_RETRY_S
            return False

        def _account(self, s):
            if self.mode != "combined":
                return
            if s is None:
                self._fails += 1
                if self._fails >= COMBINED_MAX_FAILS:
                    self._switch_to_split(f"{self._fails} failed requests")
                return
            self._fails = 0
            if float(s.get('t', 0.0)) < self._settle_until:
                return
            if len(self._latencies) < COMBINED_PROBE_SAMPLES:
                self._latencies.append(float(s.get('latency', 0.0)))
                if len(self._latencies) == COMBINED_PROBE_SAMPLES:
                    med = float(np.median(self._latencies))
                    if med > COMBINED_MAX_MEDIAN_S:
                        self._switch_to_split(f"median {med * 1000:.0f} ms")
                    else:
                        print(f"Live poll: one snapshot per sample (positions, probe, state), median {med * 1000:.0f} ms")

        def _guarded(self, fn):
            """Runs one Duet request block under the in-flight lock (skipped once stopped)."""
            with self._busy:
                if not self._enabled.is_set() or self._quit.is_set():
                    return None
                try:
                    return fn()
                except Exception as e:
                    print(f"Error polling Duet positions: {e}")
                    return None

        def _run(self):
            ui = self._ui
            was_connected = False
            while not self._quit.is_set():
                if not self._enabled.wait(0.1):
                    continue
                t_start = time.perf_counter()
                connected = bool(getattr(ui, 'duet_connected', False))
                if not connected:
                    if was_connected:
                        self.sample.emit({'event': 'disconnected', 't': time.perf_counter()})
                    was_connected = False
                    self._quit.wait(0.1)
                    continue
                if not was_connected:
                    self._reset_connection()
                    was_connected = True
                if getattr(ui, 'status_stopped', False) or getattr(ui, 'duet_status_code', 'I') not in _POLL_STATUS_CODES:
                    self._quit.wait(0.1)
                    continue

                # Axis letters once per connection (flags=f replies carry none)
                if getattr(ui, '_om_axis_letters', None) is None and t_start >= self._next_letter_try:
                    ip = getattr(ui, 'duet_ip', None) or "192.168.0.1"
                    letters = self._guarded(lambda: fetch_axis_letters(ip))
                    if letters:
                        ui._om_axis_letters = letters
                    else:
                        self._next_letter_try = time.perf_counter() + 5.0

                s = None
                if self.mode == "split" and time.perf_counter() >= self._next_combined_try:
                    s = self._guarded(lambda: poll_position_sample(ui, mode="combined", retry=False))
                    if not self._try_combined_again(s):
                        s = None
                if s is None:
                    mode = self.mode
                    s = self._guarded(lambda: poll_position_sample(ui, mode=mode, retry=False))
                    if self._enabled.is_set():
                        self._account(s)
                if s is not None:
                    self.sample.emit(s)
                    comp = self.companion
                    if comp is not None and hasattr(comp, 'note_sample'):
                        try:
                            comp.note_sample(s)     # reply sequence number -> read the new Duet message now
                        except Exception:
                            pass
                rest = self._min_period - (time.perf_counter() - t_start)
                if rest > 0:
                    self._quit.wait(rest)

    class ReplyPoller(QObject):
        """
        Reads the Duet messages (rr_reply) on a background thread while connected and hands every
        reply to `handler` on the GUI thread (queued, in order) as (t_fetch, t_prev, text, t_send,
        t_fail): t_fetch = time.perf_counter() when the reply arrived, t_send = when this read was
        sent, t_prev = lower bound of when the Duet queued the text (the previous successful read's
        send time, or later when the reply sequence number showed nothing new until then; None
        before the first read), t_fail = send time of the first read that failed since the previous
        successful one (a text the Duet handed out to it is lost), else None. Empty replies are only
        handed on when a read failed before them.

        When to read: the position snapshots carry seqs.reply, which the Duet increments for every
        new message (the PositionPoller passes each sample to note_sample()). A change is read at
        once, so the extra load is about one request per message plus a safety read every
        REPLY_POLL_SAFETY_S. Without fresh sequence numbers it reads every `period` s (other
        firmware); in split mode (slow link) at each dashboard tick (dashboard_tick(), the rate at
        which the dashboard read rr_reply itself before), and during a run also every
        REPLY_POLL_SLOW_S (a sensor wait's start text must arrive within ~1 s to be marked; that
        costs some position samples on a slow link, in runs only), else every REPLY_POLL_SAFETY_S.

        The Duet hands each reply out once, so while this poller runs it is the ONLY rr_reply
        reader: the dashboard and pause_continue_GCODE skip their own reads (request_now() asks
        for an immediate read instead). Same interface as PositionPoller (isActive / start / stop /
        shutdown); it is that poller's `companion`, so it is started, stopped (file transfers) and
        shut down together with it. Requests do not retry and time out after `timeout` s (long, so a
        WiFi stall does not lose a text the Duet already handed out); stop() waits at most
        REPLY_STOP_WAIT_S for an in-flight read, whose reply is still delivered afterwards.
        """
        reply = Signal(object)

        def __init__(self, ui, handler, period=REPLY_POLL_PERIOD_S, timeout=REPLY_POLL_TIMEOUT_S, parent=None):
            super().__init__(parent)
            self._ui = ui
            self._handler = handler
            self._period = float(period)
            self._slow_period = max(self._period, REPLY_POLL_SAFETY_S)   # split mode: safety read (see dashboard_tick)
            self._timeout = float(timeout)
            self._enabled = threading.Event()
            self._quit = threading.Event()
            self._wake = threading.Event()
            self._busy = threading.Lock()
            self._thread = None
            self._asap = None          # perf_counter() time of a requested immediate read
            self._t_prev = None        # send time of the last successful read
            self._t_last_send = None   # send time of the last read (successful or not)
            self._t_fail = None        # send time of the first failed read since the last successful one
            self._seq_lock = threading.Lock()
            self._seq_seen = None      # latest seqs.reply of a position sample
            self._seq_read = None      # seqs.reply seen before the last successful read was sent
            self._seq_t = None         # perf_counter() when a sample last carried seqs.reply
            self._quiet_t0 = None      # send time of the latest sample that still showed _seq_read
            self._split = False        # the position poll is in split mode (slow link)
            self.reads = 0             # rr_reply requests sent (diagnostics / tests)
            self.reply.connect(self._deliver, Qt.QueuedConnection)

        @Slot(object)
        def _deliver(self, r):
            try:
                self._handler(r)
            except Exception as e:
                print(f"Error handling a Duet message: {e}")

        def isActive(self):
            th = self._thread
            return self._enabled.is_set() and th is not None and th.is_alive()

        def start(self, *_ignored):
            self._enabled.set()
            if self._thread is None or not self._thread.is_alive():
                self._quit.clear()
                self._thread = threading.Thread(target=self._run, name="DuetReplyPoller", daemon=True)
                self._thread.start()

        def stop(self, wait=3.0):
            self._enabled.clear()
            self._wake.set()
            if self._quit.is_set():
                return                     # shutting down: no file transfer follows
            if self._busy.acquire(timeout=min(float(wait), REPLY_STOP_WAIT_S)):   # wait for an in-flight read
                self._busy.release()

        def shutdown(self, wait=3.0):
            already = self._quit.is_set()
            self._quit.set()
            self.stop(wait)
            th = self._thread
            if th is not None and th.is_alive() and not already:
                th.join(timeout=min(float(wait), REPLY_STOP_WAIT_S))      # daemon thread: never holds the exit

        def request_now(self, delay=0.0):
            """Read rr_reply `delay` s from now instead of at the next periodic read."""
            self._asap = time.perf_counter() + max(0.0, float(delay))
            self._wake.set()

        def dashboard_tick(self, wait=REPLY_POLL_TIMEOUT_S):
            """GUI thread, once per dashboard tick: in split mode (slow link, no sequence numbers)
            the Duet messages are read now and the tick waits for that read, as it waited for its own
            read before. The dashboard then ticks (its 1 s timer fires about every 2 s on a slow link)
            and loads the link as before; the read stays with the poller (only rr_reply reader, send
            times, failed reads noted). A tick that no longer waited would come sooner and send more
            dashboard requests, which costs position samples on a link that serves one at a time."""
            if not self._split or self._seq_mode(time.perf_counter()):
                return
            if getattr(self._ui, 'run_active', False) is True:
                return                     # during a run the poller reads every REPLY_POLL_SLOW_S itself
            n0 = self.reads
            self.request_now()
            t_end = time.perf_counter() + float(wait)
            while time.perf_counter() < t_end and self.isActive():
                if self.reads > n0 and not self._busy.locked():
                    return                 # the requested read is done (its reply follows, queued)
                time.sleep(0.002)

        def note_sample(self, s):
            """PositionPoller thread: one position sample. A new seqs.reply value means a new Duet
            message, which is read right away."""
            self._split = s.get('mode') == 'split'
            seq = s.get('reply_seq')
            if seq is None:
                return
            try:
                t0 = float(s.get('t', 0.0)) - 0.5 * float(s.get('latency') or 0.0)   # sample request sent
            except (TypeError, ValueError):
                return
            with self._seq_lock:
                self._seq_t = time.perf_counter()
                self._seq_seen = seq
                if seq == self._seq_read:
                    if self._quiet_t0 is None or t0 > self._quiet_t0:
                        self._quiet_t0 = t0
                    return
            self._wake.set()

        def _seq_mode(self, now):
            t = self._seq_t
            return t is not None and now - t < REPLY_SEQ_FRESH_S

        def _next_read_t(self, now):
            """perf_counter() time of the next read."""
            last = self._t_last_send
            if last is None:
                t_next = now
            elif self._seq_mode(now):
                with self._seq_lock:
                    changed = self._seq_seen != self._seq_read
                if self._t_fail is not None:
                    t_next = last + REPLY_POLL_RETRY_S     # a read failed: the Duet may still hold the text
                else:
                    t_next = last + (REPLY_SEQ_MIN_GAP_S if changed else REPLY_POLL_SAFETY_S)
            elif self._split:
                # slow link: during a run every REPLY_POLL_SLOW_S (sensor-wait marks), else the
                # dashboard tick reads (dashboard_tick) and this safety read
                in_run = getattr(self._ui, 'run_active', False) is True
                t_next = last + (max(self._period, REPLY_POLL_SLOW_S) if in_run else self._slow_period)
            else:
                t_next = last + self._period
            asap = self._asap
            return min(t_next, asap) if asap is not None else t_next

        def _read(self):
            ip = getattr(self._ui, 'duet_ip', None) or "192.168.0.1"
            with self._seq_lock:
                seq_at_send = self._seq_seen
                quiet = self._quiet_t0
            t_send = time.perf_counter()
            self._t_last_send = t_send
            self.reads += 1
            try:
                res = duet_request(f"http://{ip}/rr_reply", timeout=self._timeout, retry=False)
                ok = res.status_code == 200
            except Exception:
                res, ok = None, False      # timeout / connection error
            t_got = time.perf_counter()
            if not ok:
                if self._t_fail is None:
                    self._t_fail = t_send
                return None
            t_prev = self._t_prev
            if isinstance(quiet, float) and t_prev is not None and quiet > t_prev:
                t_prev = quiet             # the samples showed no new message until then
            self._t_prev = t_send
            with self._seq_lock:
                if seq_at_send is not None and seq_at_send != self._seq_read:
                    self._seq_read = seq_at_send
                    self._quiet_t0 = None
            t_fail, self._t_fail = self._t_fail, None
            text = (res.text or "").strip()
            if not text and t_fail is None:
                return None
            return (t_got, t_prev, text, t_send, t_fail)

        def _run(self):
            while not self._quit.is_set():
                if not self._enabled.wait(0.1):
                    continue
                if not getattr(self._ui, 'duet_connected', False):
                    self._quit.wait(0.1)
                    continue
                now = time.perf_counter()
                rest = self._next_read_t(now) - now
                if rest > 0:
                    self._wake.wait(min(rest, 0.25))       # woken by note_sample / request_now / stop
                    self._wake.clear()
                    continue
                r = None
                with self._busy:
                    if self._enabled.is_set() and not self._quit.is_set():
                        asap = self._asap
                        if asap is not None and asap <= time.perf_counter():
                            self._asap = None      # this read serves request_now(); a later one stays due
                        try:
                            r = self._read()
                        except Exception:
                            r = None
                if r is not None:
                    try:
                        self.reply.emit(r)     # also after stop(): a text the Duet handed out is not dropped
                    except RuntimeError:
                        return                 # the Qt object is gone (application closed during a long read)
except ImportError:   # pragma: no cover - Qt is always present in the app
    PositionPoller = None
    ReplyPoller = None


def _apply_homed_flags(self, homed):
    """Sync self.ext_axes_homed from a sample and refresh the axis button styles on change (GUI thread)."""
    if not homed:
        return
    if not hasattr(self, 'ext_axes_homed') or not isinstance(self.ext_axes_homed, dict):
        self.ext_axes_homed = {}
    changed = False
    for let, is_h in homed.items():
        clean = str(let).strip("'").strip()
        if self.ext_axes_homed.get(clean) != is_h or self.ext_axes_homed.get(f"'{clean}") != is_h:
            changed = True
        self.ext_axes_homed[let] = is_h
        self.ext_axes_homed[clean] = is_h
        self.ext_axes_homed[f"'{clean}"] = is_h
    if changed:
        try:
            from fcn_control.fcn_control import refresh_external_axis_styles
            refresh_external_axis_styles(self)
        except Exception:
            pass


def _platform_dims(self):
    lat_dim = 100.0
    if hasattr(self, 'input_plat_lat') and self.input_plat_lat:
        try: lat_dim = float(self.input_plat_lat.text().strip())
        except (ValueError, TypeError, AttributeError): pass
    if not isinstance(lat_dim, float) or lat_dim <= 0.0: lat_dim = 100.0

    si_dim = 100.0
    if hasattr(self, 'input_plat_si') and self.input_plat_si:
        try: si_dim = float(self.input_plat_si.text().strip())
        except (ValueError, TypeError, AttributeError): pass
    if not isinstance(si_dim, float) or si_dim <= 0.0: si_dim = 100.0

    y_lo_name = "'c"
    lims = getattr(self, 'axis_max_limits', None)
    if isinstance(lims, dict) and ("b" in lims or "'b" in lims):
        y_lo_name = "'b"
    return lat_dim, si_dim, y_lo_name


def _platform_dof(axes, lat_dim, si_dim, y_lo_name="'c"):
    """Platform DOF (LAT/SI/AP in mm, Roll/Pitch/Yaw in deg) from actuator positions."""
    a, b, c, d = axes['A'], axes['B'], axes['C'], axes['D']
    roll = math.degrees(math.atan2((a + d) / 2.0 - (b + c) / 2.0, lat_dim))
    pitch = math.degrees(math.atan2((a + b) / 2.0 - (c + d) / 2.0, si_dim))
    lat = (axes.get("'e", 0.0) + axes.get("'f", 0.0)) / 2.0
    si = (axes.get("'a", 0.0) + axes.get(y_lo_name, axes.get("'c", 0.0))) / 2.0
    ap = (a + b + c + d) / 4.0
    return {'Roll': roll, 'Pitch': pitch, 'Yaw': axes['W'], 'LAT': lat, 'AP': ap, 'SI': si}


def _apply_release_mark(self, t, probe):
    """Probe value for a sample at time t: PROBE_RELEASE_MARK while the Release-button marker is
    active (PROBE_RELEASE_HOLD_S after the press, and at least the first sample after it)."""
    mark = getattr(self, '_release_mark_t', None)
    if not isinstance(mark, float) or t < mark:
        return probe
    if t < mark + PROBE_RELEASE_HOLD_S or not getattr(self, '_release_mark_done', False):
        self._release_mark_done = True
        return PROBE_RELEASE_MARK
    self._release_mark_t = None
    return probe


# --- sensor_wait.g mark (Probe PROBE_WAIT_MARK in the log and the plot while the macro waits) ---
# The macro keeps the job 'processing'; only its echo "Waiting for sensor signal..." tells that it
# waits. TRACE reads that text with the ReplyPoller (on a seqs.reply change, else on its timer), so
# the wait is known from the read that brought it (t_fetch); samples are marked from the first one
# taken at or after t_fetch. The wait ends on the FIRST sample with the detector above
# SENSOR_WAIT_THRESHOLD or with the Release marker of a press made during it (no waiting for the
# Duet's "Continuing" message). Backup ends: that message, the machine moving (the macro runs M400
# before its echo, so the axes stand still while it waits), a new wait, the run end.
# Race guard: the read that brought the start text had no end text, so the wait still ran when the
# Duet handled it (at or after t_send). Only a trigger the Duet can have seen after t_send can have
# ended the wait before TRACE knew of it; such a wait is left unmarked ('# Wait not marked').
# The mark goes to the log and the plot only, never to _last_probe_val / auto-pause / auto-release.

def _run_t(self, t):
    """Run time (s after run_t0) of a perf_counter() time."""
    t0 = getattr(self, 'run_t0', None)
    return float(t) - t0 if isinstance(t0, float) else float(t)


def _clean_msg(text):
    """One Duet message line for a '# ...' log comment: single line, no double quotes, no ';'."""
    return " ".join(str(text).replace('"', "'").replace(';', ',').split())[:160]


def _write_run_comment(self, line, t=None):
    """Keeps a '# ...' run note of the open log in memory (time order by t, the perf_counter() time
    it is about); close_data_log_file writes the notes after the last row. Before the log file is
    open (no sample of the run logged so far) the note waits in _pending_log_comments."""
    try:
        t_key = _run_t(self, t) if isinstance(t, (int, float)) and not isinstance(t, bool) else _run_t(self, time.perf_counter())
    except Exception:
        t_key = 0.0
    note = (float(t_key), _note_text(line))
    if getattr(self, 'active_log_file', None) is not None:
        notes = getattr(self, '_log_notes', None)
        if not isinstance(notes, list):
            notes = []
            self._log_notes = notes
        notes.append(note)
    elif getattr(self, 'run_active', False) is True:
        pending = getattr(self, '_pending_log_comments', None)
        if not isinstance(pending, list):
            pending = []
            self._pending_log_comments = pending
        pending.append(note)


def _wait_sent_bounds(self, w):
    """'between <t_prev> and <t_fetch> s' (run times) of a wait message."""
    if isinstance(w.get('t_prev'), float):
        return f"between {_dc(_run_t(self, w['t_prev']), '.3f')} and {_dc(_run_t(self, w['t_fetch']), '.3f')} s"
    return f"before {_dc(_run_t(self, w['t_fetch']), '.3f')} s (no earlier read)"


def _wait_start_line(self, w):
    return (f"# Wait start: \"{w['msg']}\" received at {_dc(_run_t(self, w['t_fetch']), '.3f')} s "
            f"(Duet sent it {_wait_sent_bounds(self, w)})")


def _note_wait_start(self, w):
    """The '# Wait start' note of wait w in the notes of the open log (or of the next one) unless it is
    there already: a log opened while the wait goes on (Record off and on again) then has the start
    of the wait whose end it gets."""
    line = _note_text(_wait_start_line(self, w))
    notes = (getattr(self, '_log_notes', None) if getattr(self, 'active_log_file', None) is not None
             else getattr(self, '_pending_log_comments', None))
    if isinstance(notes, list) and any(isinstance(n, tuple) and len(n) > 1 and n[1] == line for n in notes):
        return
    _write_run_comment(self, line, t=w['t_fetch'])


def _wait_not_marked(self, w, why):
    """The wait message arrived, but the wait may already have ended (race): no row is marked."""
    self._sensor_wait = None
    _write_run_comment(self, f"# Wait not marked: \"{w['msg']}\" received at {_dc(_run_t(self, w['t_fetch']), '.3f')} s "
                             f"(Duet sent it {_wait_sent_bounds(self, w)}), the wait may already have ended: {why}",
                       t=w['t_fetch'])


def _end_sensor_wait(self, what, how, t):
    """Ends the marked sensor wait: '# Wait end: <what> at <t> s (<how>)' (and its start line if no
    sample has been marked yet)."""
    w = getattr(self, '_sensor_wait', None)
    self._sensor_wait = None
    if not isinstance(w, dict):
        return
    if not w.get('started'):
        _write_run_comment(self, _wait_start_line(self, w), t=w['t_fetch'])
    else:
        _note_wait_start(self, w)        # a log opened during the wait (Record off and on again) gets it too
    _write_run_comment(self, f"# Wait end: {what} at {_dc(_run_t(self, t), '.3f')} s ({how})", t=t)


def _end_sensor_wait_at_run_end(self, reason):
    """A sensor wait still marked when the run ends (job end, Cancel, start of a new run)."""
    w = getattr(self, '_sensor_wait', None)
    if not isinstance(w, dict):
        return
    try:
        if w.get('end') is not None:
            _end_sensor_wait(self, *w['end'][1:3], t=w['end'][0])
        else:
            _end_sensor_wait(self, "run end", f"the run ended: {reason}", t=time.perf_counter())
    except Exception as e:
        print(f"Error in the sensor wait mark (run end): {e}")
        self._sensor_wait = None


def _sensor_wait_reply(self, t_fetch, t_prev, text):
    """
    One Duet reply (GUI thread): arms the wait mark on the macro's start text during a run, and
    ends a marked wait on its end text (backup end; normally a sample ends it first). Several
    messages can come in one reply; they are handled in order. The read's send time comes in
    self._reply_t_send (set by handle_duet_reply; t_fetch - REPLY_LATENCY_GUESS_S when unknown).
    """
    try:
        t_fetch = float(t_fetch)
        t_prev = float(t_prev) if isinstance(t_prev, (int, float)) and not isinstance(t_prev, bool) else None
        t_send = getattr(self, '_reply_t_send', None)
        if not isinstance(t_send, (int, float)) or isinstance(t_send, bool) or not t_send <= t_fetch:
            t_send = t_fetch - REPLY_LATENCY_GUESS_S
        t_send = float(t_send)
        text = str(text)
        low_text = text.lower()
        events = []                     # (position in the text, is_start)
        for phrase, is_start in [(SENSOR_WAIT_MSG.lower(), True)] + [(m, False) for m in SENSOR_WAIT_END_MSGS]:
            i = low_text.find(phrase)
            while i >= 0:
                events.append((i, is_start))
                i = low_text.find(phrase, i + 1)
        events.sort()
        for pos, is_start in events:
            ls = text.rfind('\n', 0, pos) + 1
            le = text.find('\n', pos)
            line = text[ls:le if le >= 0 else len(text)].strip()
            w = getattr(self, '_sensor_wait', None)
            if isinstance(w, dict):
                if not w.get('started') and w.get('t_fetch') == t_fetch:
                    # start and end in the same read: the wait ended before TRACE knew of it
                    _wait_not_marked(self, w, f"Duet message \"{_clean_msg(line)}\" in the same read")
                elif w.get('end') is not None:
                    if is_start:      # backup end already received: close it before the next wait
                        _end_sensor_wait(self, *w['end'][1:3], t=w['end'][0])
                elif is_start:
                    # A new wait while this one is still marked: its end message never arrived (lost
                    # in a failed read), so the end is only known to lie before this message
                    tf = w.get('read_failed')
                    note = f", a Duet message read failed at {_dc(_run_t(self, tf), '.3f')} s" if isinstance(tf, float) else ""
                    _end_sensor_wait(self, f"Duet message \"{_clean_msg(line)}\"",
                                     f"its end message was not received{note}, the wait ended before this "
                                     f"message was sent", t=t_fetch)
                else:
                    # Backup end from the Duet message. It takes effect at the first sample taken at
                    # or after this read, so a detector / Release sample still on its way (taken
                    # before the read) can end the wait exactly.
                    dt = (t_fetch - t_prev) if t_prev is not None else REPLY_POLL_PERIOD_S
                    w['end'] = (t_fetch, f"Duet message \"{_clean_msg(line)}\"",
                                f"from the Duet message, up to ~{_dc(dt, '.1f')} s late")
            if not is_start:
                continue
            run_t0 = getattr(self, 'run_t0', None)
            if getattr(self, 'run_active', False) is not True or not isinstance(run_t0, float) or t_fetch < run_t0:
                continue
            self._sensor_wait = {'t_fetch': t_fetch, 't_prev': t_prev, 't_send': min(t_send, t_fetch),
                                 'msg': _clean_msg(line), 'started': False, 'marked': 0, 'end': None,
                                 'ref': None, 'read_failed': None}
    except Exception as e:
        print(f"Error in the sensor wait mark (reply): {e}")


def _axes_moved(real, ref):
    """True when an axis present in both position dicts differs by more than WAIT_MOVE_TOL."""
    for k, v in real.items():
        r = ref.get(k)
        if r is None:
            continue
        try:
            if abs(float(v) - float(r)) > WAIT_MOVE_TOL:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _apply_wait_mark(self, t, raw, val, probe_known=True, pos=None, latency=None, probe_t=None):
    """
    Probe value to log and plot for an in-run sample at time t (raw = Duet probe value, val = after
    the Release marker; probe_known False when the sample carried no probe value, pos = its axis
    positions, latency = its request time, probe_t = when its probe value came back when it was read
    in a second request, split mode). While a sensor wait is marked: raw <= 0 (or unknown) ->
    PROBE_WAIT_MARK; 0 < raw <= SENSOR_WAIT_THRESHOLD keeps raw (the macro still waits); raw above
    the threshold or the Release marker of a press that can belong to this wait ends the wait on
    this sample, which keeps its real value (e.g. 1000 / 2000). The hold of an earlier press keeps
    2000 and does not end it (sensor_wait.g clears force_release_sensor when it starts).
    """
    try:
        try:
            raw_f = float(raw)
        except (TypeError, ValueError):
            raw_f, probe_known = 0.0, False
        press = getattr(self, '_release_mark_t', None)
        release_on = (val == PROBE_RELEASE_MARK and raw_f != PROBE_RELEASE_MARK and isinstance(press, float)
                      and press != getattr(self, '_release_used_t', None))
        detector_on = probe_known is not False and raw_f > SENSOR_WAIT_THRESHOLD
        try:
            half = 0.5 * float(latency) if latency is not None else 0.04
        except (TypeError, ValueError):
            half = 0.04
        # split mode: the probe was read after the positions, up to probe_lag s after the row time t
        probe_lag = None
        if isinstance(probe_t, float) and probe_t > t + half:
            probe_lag = probe_t - t
        prev_t = getattr(self, '_wait_prev_sample_t', None)
        self._wait_prev_sample_t = t
        trigs = getattr(self, '_wait_triggers', None)
        if not isinstance(trigs, list):
            trigs = []
            self._wait_triggers = trigs
        # Latest time the Duet can have seen each trigger of this sample: the probe was read before the
        # sample's reply came back (+ the macro's loop); the Release command reaches it after the press
        new = []
        if detector_on:
            new.append((t + half + WAIT_RACE_SLACK_S, f"detector {_dc(raw_f, 'g')}", t))
        if release_on:
            new.append((press + RELEASE_CMD_DELAY_S, "Release button", t))
        out = _wait_mark_value(self, t, raw_f, val, probe_known is not False, pos, prev_t, trigs,
                               detector_on, release_on, press, t - half, probe_lag)
        used = getattr(self, '_release_used_t', None)       # a press that ended a wait cannot end a later one
        trigs.extend(x for x in new if not (x[1] == "Release button" and used == press))
        trigs[:] = [x for x in trigs if x[2] >= t - 5.0]
        return out
    except Exception as e:
        print(f"Error in the sensor wait mark: {e}")
        return val


def _wait_mark_value(self, t, raw_f, val, probe_known, pos, prev_t, trigs, detector_on, release_on, press,
                     t_sent=None, probe_lag=None):
    """_apply_wait_mark for the current wait (trigs: earlier samples' triggers, this one not yet;
    t_sent: when this sample's request was sent, i.e. about when the Duet read its positions;
    probe_lag: split mode, the probe was read in a second request up to this many s after t)."""
    w = getattr(self, '_sensor_wait', None)
    if not isinstance(w, dict) or t < w['t_fetch']:
        return val
    t_send = w.get('t_send', w['t_fetch'])
    if not w.get('started'):
        # Race guard: a trigger the Duet can have seen after this read was sent may have ended the
        # wait before TRACE got the message -> nothing is marked
        race = [x for x in trigs if x[0] >= t_send]
        if race:
            _wait_not_marked(self, w, f"{race[-1][1]} at {_dc(_run_t(self, race[-1][2]), '.3f')} s")
            return val
        w['started'] = True
        _write_run_comment(self, _wait_start_line(self, w), t=w['t_fetch'])
    # A press can end this wait only if its command reached the Duet after the read that brought the
    # start text was handled (the macro clears the flag before its echo, and that read had no end text)
    release_ends = release_on and press + RELEASE_CMD_DELAY_S >= t_send
    if detector_on or release_ends:
        what = f"detector {_dc(raw_f, 'g')}" if detector_on else "Release button"
        how = (f"exact to one sample, previous sample at {_dc(_run_t(self, prev_t), '.3f')} s"
               if isinstance(prev_t, float) else "exact to one sample")
        if detector_on and probe_lag is not None:
            # split mode: the row time is that of the positions, the probe came in a later request,
            # so the detector rose after the previous sample and before t + probe_lag
            how = (f"split mode, the probe was read up to {_dc(probe_lag, '.3f')} s after this row"
                   + (f", previous sample at {_dc(_run_t(self, prev_t), '.3f')} s" if isinstance(prev_t, float) else ""))
        _end_sensor_wait(self, what, how, t=t)
        if release_ends:
            self._release_used_t = press
        return val
    if w.get('end') is not None and t >= w['end'][0]:
        _end_sensor_wait(self, *w['end'][1:3], t=w['end'][0])     # backup end (Duet message)
        return val
    # Backup end without a message: the axes stand still while the macro waits (M400 before the echo).
    # machinePosition can lag ~200 ms after the M400, so the reference follows the samples until one
    # whose request was SENT (the Duet read its positions then) WAIT_POS_SETTLE_S or more after the
    # read that brought the start text; only such a reference is compared (a stalled response of an
    # earlier request can hold a pre-M400 position).
    if isinstance(pos, dict) and pos:
        if t_sent is None:
            t_sent = t - 0.04
        if w.get('ref') is None or not w.get('ref_fresh'):
            w['ref'] = dict(pos)
            w['ref_fresh'] = t_sent >= w['t_fetch'] + WAIT_POS_SETTLE_S
        elif _axes_moved(pos, w['ref']):
            p_txt = _dc(_run_t(self, prev_t), '.3f') if isinstance(prev_t, float) else "?"
            _end_sensor_wait(self, "motion", f"no end message yet, the axes moved after the previous sample at "
                                             f"{p_txt} s, positions lag up to 0,2 s", t=t)
            return val
    if val == PROBE_RELEASE_MARK:
        return val              # hold of an earlier Release press (kept as the press marker)
    if not probe_known or raw_f <= 0:
        w['marked'] += 1
        return PROBE_WAIT_MARK
    return val


def _reply_poller_running(self):
    """True while the ReplyPoller reads rr_reply (it is then the only rr_reply reader)."""
    rp = getattr(self, 'duet_reply_poller', None)
    try:
        return ReplyPoller is not None and isinstance(rp, ReplyPoller) and rp.isActive()
    except Exception:
        return False


def _reply_read_failed(self, t_prev, t_send, t_fail):
    """A Duet-message read failed (timeout / connection error) before this reply: a text the Duet
    handed out to it is lost. Noted in the run's log and on the marked wait (its end may be missing)."""
    try:
        t_fail = float(t_fail)
        w = getattr(self, '_sensor_wait', None)
        if isinstance(w, dict) and w.get('read_failed') is None:
            w['read_failed'] = t_fail
        run_t0 = getattr(self, 'run_t0', None)
        if getattr(self, 'run_active', False) is not True or not isinstance(run_t0, float) or t_fail < run_t0:
            return
        lo = (f"between {_dc(_run_t(self, t_prev), '.3f')} and" if isinstance(t_prev, (int, float)) and not isinstance(t_prev, bool)
              else "before")
        hi = _run_t(self, t_send) if isinstance(t_send, (int, float)) and not isinstance(t_send, bool) else _run_t(self, t_fail)
        _write_run_comment(self, f"# Message read failed at {_dc(_run_t(self, t_fail), '.3f')} s: Duet messages sent {lo} "
                                 f"{_dc(hi, '.3f')} s may be lost (a sensor wait start or end may be missing)", t=t_fail)
    except Exception as e:
        print(f"Error noting a failed Duet message read: {e}")


def handle_duet_reply(self, r):
    """
    GUI thread: one Duet reply r = (t_fetch, t_prev, text[, t_send[, t_fail]]) from the ReplyPoller
    (or from the dashboard's own read when the poller is not running). Same effects as the
    dashboard's former read (Duet message field, _last_duet_reply that the include-pause logic
    reads, console line), plus the sensor_wait mark of the live log (every reply, also a repeated
    text) and a '# Message read failed' note when a read failed before this one (t_fail).
    """
    try:
        t_fetch, t_prev, text = r[0], r[1], r[2]
        t_send = r[3] if len(r) > 3 else None
        t_fail = r[4] if len(r) > 4 else None
    except (TypeError, ValueError, IndexError, KeyError):
        return
    if t_fail is not None:
        _reply_read_failed(self, t_prev, t_send, t_fail)
    reply_str = str(text or "").strip()
    if not reply_str:
        return
    self._reply_t_send = t_send
    try:
        _sensor_wait_reply(self, t_fetch, t_prev, reply_str)
    finally:
        self._reply_t_send = None
    if reply_str != getattr(self, '_last_duet_reply', ''):
        self._last_duet_reply = reply_str
        if hasattr(self, 'statusDuetMessage') and self.statusDuetMessage:
            self.statusDuetMessage.setText(reply_str)
        from fcn_control.fcn_control import log_to_duet_console
        log_to_duet_console(self, f"Duet Message: {reply_str}", color="#00acc1")


def update_status_fast(self):
    """Synchronous poll + handle (kept for callers/tests; the app uses PositionPoller)."""
    if not getattr(self, 'duet_connected', False) or getattr(self, 'status_stopped', False):
        return
    get_clean_duet_ip(self)
    s = poll_position_sample(self)
    if s:
        handle_position_sample(self, s)


def handle_position_sample(self, s):
    """
    Handles one live sample on the GUI thread: updates the status position labels, and during a
    run (Start -> job finished) writes the SAME sample to the log file and to the plot buffers,
    both on the run's time zero. Outside a run only the plot is fed (when the Duet is moving).
    Uses the sample's own timestamp s['t'] (time.perf_counter() when it was taken) and, when the
    sample carries it, the Duet state at that instant.
    Does NOT call render_status_plot (graph redraw throttled to 1s in slow timer).
    """
    if s.get('event') == 'disconnected':
        # The job keeps running on the Duet: keep the run (same t0) and mark the gap in the log;
        # after reconnecting, logging continues and the run ends normally when the job is done.
        if getattr(self, 'run_active', False) is True:
            run_t0 = getattr(self, 'run_t0', None)
            t_gap = (float(s.get('t', time.perf_counter())) - run_t0) if isinstance(run_t0, float) else 0.0
            if getattr(self, 'active_log_file', None) is not None:      # run note, written when the log closes
                _write_run_comment(self, f"# Gap: connection lost at {_dc(t_gap, '.3f')} s",
                                   t=float(s.get('t', time.perf_counter())))
            self._run_gap_open = True
            print(f"Connection lost during the run at {t_gap:.1f} s; logging resumes after reconnecting.")
        elif getattr(self, 'active_log_file', None) is not None:
            close_data_log_file(self, "connection lost")
        return
    if not getattr(self, 'duet_connected', False):
        return
    if getattr(self, 'status_stopped', False):
        return

    t_now = float(s.get('t', time.perf_counter()))
    sample_status = s.get('status')
    if sample_status is not None:
        self._last_sample_status_t = time.perf_counter()
    status_code = sample_status if sample_status is not None else getattr(self, 'duet_status_code', 'I')
    if status_code not in _POLL_STATUS_CODES:
        return

    try:
        _apply_homed_flags(self, s.get('homed'))

        # Ensure we have defaults for all required axes
        axis_positions = dict(s.get('real') or {})
        for ax in _LIVE_AXES:
            if ax not in axis_positions:
                axis_positions[ax] = 0.0

        # Update the UI labels (actual position)
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

        # Platform DOF from the actual actuator positions
        lat_dim, si_dim, y_lo_name = _platform_dims(self)
        dof = _platform_dof(axis_positions, lat_dim, si_dim, y_lo_name)
        current_roll, current_pitch, current_yaw = dof['Roll'], dof['Pitch'], dof['Yaw']
        current_lat, current_ap, current_si = dof['LAT'], dof['AP'], dof['SI']

        if hasattr(self, 'statusPosRoll') and self.statusPosRoll:
            self.statusPosRoll.setText(f"Roll {current_roll:.2f}")
        if hasattr(self, 'statusPosPitch') and self.statusPosPitch:
            self.statusPosPitch.setText(f"Pitch {current_pitch:.2f}")
        if hasattr(self, 'statusPosYaw') and self.statusPosYaw:
            self.statusPosYaw.setText(f"Yaw {current_yaw:.2f}")

        curr_p = s.get('probe')
        probe_known = curr_p is not None      # else the dashboard's last value (never ends a sensor wait)
        if curr_p is None:
            curr_p = getattr(self, '_last_probe_val', 0)
        raw_p = curr_p
        curr_p = _apply_release_mark(self, t_now, curr_p)   # + _apply_wait_mark below (in-run samples)

        self._latest_sample = {'t': t_now, 'real': axis_positions, 'status': sample_status}

        # --- Run (Start -> job finished): log and plot get the same samples on the same t0 ---
        run_active = getattr(self, 'run_active', False) is True
        run_t0 = getattr(self, 'run_t0', None) if run_active else None
        if run_active and not isinstance(run_t0, float):
            run_active = False
        if run_active and t_now < run_t0:
            return              # taken before the job was started (handled late)
        in_run = run_active

        ended = None
        if in_run and sample_status is not None:
            if sample_status == 'I':
                if getattr(self, 'run_idle_since', None) is None:
                    self.run_idle_since = t_now
                if getattr(self, 'run_seen_running', False) and t_now - self.run_idle_since >= RUN_IDLE_END_S:
                    ended = "job finished"
                elif not getattr(self, 'run_seen_running', False) and t_now - run_t0 >= RUN_START_TIMEOUT_S:
                    ended = "job did not start"
            else:
                self.run_seen_running = True
                self.gcode_seen_running = True
                self.run_idle_since = None

        if in_run and getattr(self, '_run_gap_open', False) is True:
            self._run_gap_open = False
            if getattr(self, 'active_log_file', None) is not None:      # run note, written when the log closes
                _write_run_comment(self, f"# Gap end: reconnected at {_dc(t_now - run_t0, '.3f')} s", t=t_now)

        if in_run:
            # sensor_wait.g: PROBE_WAIT_MARK while it waits; same value for the log row and the plot point
            curr_p = _apply_wait_mark(self, t_now, raw_p, curr_p, probe_known=probe_known,
                                      pos=s.get('real'), latency=s.get('latency'), probe_t=s.get('probe_t'))
            if hasattr(self, 'check_record_log') and self.check_record_log and self.check_record_log.isChecked():
                raw = {a: axis_positions[a] for a in _PLATFORM_RAW_AXES}
                log_data_point(self, t_now - run_t0, x_val, y_val, z_val, curr_p, extra_axes=dof, raw_axes=raw)
            elif getattr(self, 'active_log_file', None) is not None:
                close_data_log_file(self, "record off")
        elif getattr(self, 'active_log_file', None) is not None:
            close_data_log_file(self, "no active run")

        elapsed_t = 0.0
        # Determine whether to update plot data based on status code and 'Include pause' checkbox
        include_pause = True
        if hasattr(self, 'check_include_pause') and self.check_include_pause is not None:
            include_pause = self.check_include_pause.isChecked()

        # Detect if machine is in a firmware pause ('S') or macro wait state (e.g. sensor_wait macro)
        msg_text = ""
        if hasattr(self, 'statusDuetMessage') and self.statusDuetMessage:
            msg_text = self.statusDuetMessage.text().strip().lower()
        reply_text = getattr(self, '_last_duet_reply', '').strip().lower()

        def check_paused_message(text):
            if not text:
                return False
            if any(ok in text for ok in ["detected", "continuing", "resuming", "started", "complete", "completed"]):
                return False
            return any(k in text for k in ["waiting", "wait for", "pausing", "paused", "m226", "sensor_wait"])

        is_paused_state = False
        if status_code in ("S", "D"):
            is_paused_state = True
        elif check_paused_message(msg_text) or check_paused_message(reply_text):
            is_paused_state = True

        should_update_plot = False
        if in_run:
            should_update_plot = include_pause or not is_paused_state
        elif status_code in ["P", "S", "R", "M", "B", "D", "T"]:
            if is_paused_state:
                should_update_plot = include_pause
            else:
                should_update_plot = True

        if not should_update_plot:
            if is_paused_state and not include_pause:
                if getattr(self, '_pause_start_perf', None) is None:
                    self._pause_start_perf = t_now
        else:
            if getattr(self, '_pause_start_perf', None) is not None:
                pause_dur = t_now - self._pause_start_perf
                self._total_pause_duration = getattr(self, '_total_pause_duration', 0.0) + pause_dur
                self._pause_start_perf = None

            if not hasattr(self, 'status_plot_data') or self.status_plot_data is None or 'A' not in self.status_plot_data or 'LAT' not in self.status_plot_data:
                self.status_plot_data = {
                    't': [], 'X': [], 'Y': [], 'Z': [],
                    'A': [], 'B': [], 'C': [], 'D': [],
                    "'e": [], "'f": [], "'a": [], "'c": [],
                    'Roll': [], 'Pitch': [], 'Yaw': [],
                    'LAT': [], 'AP': [], 'SI': []
                }
                if not in_run:
                    self._total_pause_duration = 0.0
                    self._pause_start_perf = None

            if in_run:
                self.status_t0 = run_t0
            elif not hasattr(self, 'status_t0') or self.status_t0 is None:
                self.status_t0 = t_now
                self._total_pause_duration = 0.0
                self._pause_start_perf = None

            raw_elapsed = t_now - self.status_t0
            if include_pause:
                elapsed_t = max(0.0, raw_elapsed)
            else:
                elapsed_t = max(0.0, raw_elapsed - getattr(self, '_total_pause_duration', 0.0))

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
            if 'probe' not in self.status_plot_data:
                self.status_plot_data['probe'] = []
            self.status_plot_data['probe'].append(curr_p)

            # Cap history buffer at 100,000 points to retain full plot history for panning & zoom inspection
            if len(self.status_plot_data['t']) > 100000:
                for k in self.status_plot_data.keys():
                    self.status_plot_data[k].pop(0)

        if ended:
            end_run(self, ended)

    except Exception as e:
        print(f"Error in fast status loop: {e}")


# --- DUET OPERATIONS ---

def get_curr_file(self, init=True):
    """
    Get the filename of the GCODE currently being executed or selected on DUET
    """
    sel_path = getattr(self, 'selected_gcode_path', None)
    if sel_path:
        return os.path.basename(sel_path)

    ip = get_clean_duet_ip(self)
    try:
        url_job = f'http://{ip}/rr_model?key=job'
        res_job = duet_request(url_job, timeout=2)
        if res_job.status_code == 200:
            job_data = res_job.json().get('result', {})
            if isinstance(job_data, dict):
                file_info = job_data.get('file', {})
                fn = file_info.get('fileName') if isinstance(file_info, dict) else None
                if not fn:
                    fn = job_data.get('lastFileName')
                if fn:
                    return os.path.basename(fn)

        url = f'http://{ip}/rr_fileinfo'
        response = duet_request(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            filepath = data.get('fileName', '')
            if filepath:
                if init == True:
                    self.tprint = data.get('printDuration', 0)
                _, filename = os.path.split(filepath)
                return filename
    except Exception as e:
        print(f"Duet fileinfo error: {e}")
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
            data['geiger'] = contents['sensors'].get('probeValue') or 0
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
        if _reply_poller_running(self):
            self.duet_reply_poller.request_now(0.1)     # it is the only rr_reply reader while it runs
        else:
            time.sleep(0.1)
            try:
                t_send = time.perf_counter()
                res_reply = duet_request(f'http://{ip}/rr_reply', timeout=2)
                if res_reply.status_code == 200:
                    t_prev, self._rr_reply_prev_t = getattr(self, '_rr_reply_prev_t', None), t_send
                if res_reply.status_code == 200 and res_reply.text.strip():
                    reply_text = res_reply.text.strip()
                    self._reply_t_send = t_send
                    try:
                        _sensor_wait_reply(self, time.perf_counter(), t_prev, reply_text)
                    finally:
                        self._reply_t_send = None
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
        end_run(self, "cancelled")
        self.status_t0 = None
        self.status_plot_data = None
        self.status_stopped = True
        ip = get_clean_duet_ip(self)
        try:
            url = f'http://{ip}/rr_gcode'
            # First pause, then issue cancel job command (M0 H1)
            duet_request(url, params={'gcode': 'M25'}, timeout=4)
            duet_request(url, params={'gcode': 'M0 H1'}, timeout=4)
            # 5V trigger (planned trigger windows, M42 on fcn_trigger.TRIGGER_PORT) off: a cancelled
            # job must not leave it on
            try:
                from fcn_plan.fcn_trigger import TRIGGER_OFF_CMD
            except Exception:
                TRIGGER_OFF_CMD = 'M42 P5 S0'
            duet_request(url, params={'gcode': TRIGGER_OFF_CMD}, timeout=4)
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
    
    # 1. Status Mapping. An empty/failed 'state' reply gives status None ("unknown"), which the
    # dashboard replaces by the last known status instead of reading it as Idle.
    state = om_data.get("state") or {}
    om_status = str(state.get("status", "")).lower() if isinstance(state, dict) else ""
    legacy["status"] = RRF_STATUS_CODES.get(om_status, "B") if om_status else None
    
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
    xyz_all = []

    if isinstance(axes, list) and len(axes) > 0:
        for ax in axes:
            if isinstance(ax, dict):
                homed_val = 1 if is_axis_homed(ax) else 0
                axes_homed.append(homed_val)
                xyz_all.append(float(ax.get("userPosition", 0.0)))
    else:
        # Fallback if axes list is empty
        for letter in ["X", "Y", "Z", "A", "B", "C", "D", "a", "c", "e", "f"]:
            homed_val = 1 if is_axis_homed(axes_by_letter.get(letter)) else 0
            axes_homed.append(homed_val)
            xyz_all.append(float(axes_by_letter.get(letter, {}).get("userPosition", 0.0) if isinstance(axes_by_letter.get(letter), dict) else 0.0))

    if len(xyz_all) < 3:
        xyz_all = [x_pos, y_pos, z_pos]

    legacy["coords"] = {
        "xyz": xyz_all,
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
    job_file_obj = job.get("file") if isinstance(job, dict) else None
    legacy["jobFileName"] = job_file_obj.get("fileName") if isinstance(job_file_obj, dict) else None
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
        
    # Probe value (None when the sensors reply is empty/failed: keep the last value)
    sensors = om_data.get("sensors") or {}
    probe_val = _probe_from_sensors(sensors) if isinstance(sensors, dict) and sensors else None

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
                    with open(get_config_path('duet_response_debug.json', for_writing=True), 'w') as f:
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
    return None, 500


def release_sensor_wait_action(self):
    """
    Sends force release signal to Duet to break out of the sensor_wait macro loop.
    Marks the press in the live data: Probe reads PROBE_RELEASE_MARK (2000) for
    PROBE_RELEASE_HOLD_S in the log and the plot, distinct from a detector trigger.
    """
    from fcn_control.fcn_control import send_cmd, log_to_duet_console
    # Double click: the 2nd press (often handled right after the 1st returns, which waits for the
    # Duet) would release the NEXT wait and overwrite the 1st press's 2000 marker -> ignored
    now = time.perf_counter()
    last, done = getattr(self, '_release_press_t', None), getattr(self, '_release_press_done_t', None)
    if ((isinstance(last, float) and 0.0 <= now - last < PROBE_RELEASE_HOLD_S)
            or (isinstance(done, float) and 0.0 <= now - done < RELEASE_DEBOUNCE_S)):
        log_to_duet_console(self, "Release pressed again right away: ignored (the first press releases the wait)",
                            color="#0288d1")
        return
    self._release_press_t = now
    self._release_mark_t = now
    self._release_mark_done = False
    log_to_duet_console(self, "Sending force release signal to sensor_wait macro on Duet...", color="#0288d1")
    # Only 'set': sensor_wait.g creates the global and resets it to false every time it starts, so
    # a 'global force_release_sensor = true' never releases a wait (before a wait the macro resets
    # it, during a wait RRF rejects it with "variable 'force_release_sensor' already exists", and
    # that error would become the last Duet message, which the 'Include pause' check reads).
    send_cmd(self, "set global.force_release_sensor = true")
    self._release_press_done_t = time.perf_counter()

