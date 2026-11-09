"""
Status plot: the measured curves without the staircase.

The Duet recomputes the reported (machine) position at most every 200 ms (MachineCoordinateUpdateInterval in
RRF's src/Movement/MoveTiming.h), while LogIQ samples about every 70 ms: the same value comes back two or three
times and the plot showed flat steps although the platform moves smoothly.  Here the measured lines are drawn
through the samples where a NEW value arrived (straight lines in between).  A value that really stays the same for
longer than HOLD_S (a hold, the platform at rest) keeps its first and last sample, so holds stay flat.

Display only: the samples, the log file and the reference curves are not changed.  Installed by
logiq_shell.apply_logiq_shell (install_status_smoothing).
"""
import functools

import numpy as np

HOLD_S = 0.35          # a run of equal values longer than this is a real hold (the cache refreshes every ~0.2 s)


def update_points(x, y, hold_s=HOLD_S):
    """Indexes of the samples to draw: the first sample of every new value, both ends of a real hold (longer than
    hold_s), the last sample, and NaN gaps kept as they are."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 3 or len(x) != n:
        return np.arange(n)
    nan = np.isnan(y)
    new = np.r_[True, (y[1:] != y[:-1]) | nan[1:] | nan[:-1]]
    starts = np.nonzero(new)[0]
    ends = np.r_[starts[1:] - 1, n - 1]
    long_run = (x[ends] - x[starts]) > hold_s
    return np.unique(np.r_[starts, ends[long_run], n - 1])


def smooth_lines(window):
    """Measured lines of the Status plot -> drawn through the position updates."""
    lines = getattr(window, 'status_plot_lines', None)
    if not isinstance(lines, dict):
        return False
    changed = False
    for line in lines.values():
        try:
            x, y = line.get_xdata(), line.get_ydata()
            if len(x) < 3:
                continue
            idx = update_points(x, y)
            if len(idx) < len(x):
                line.set_data(np.asarray(x, dtype=float)[idx], np.asarray(y, dtype=float)[idx])
                changed = True
        except Exception:
            continue
    return changed


def install_status_smoothing():
    """Wraps fcn_duet.render_status_plot once (other wrappers, e.g. the modern Status controls, keep working)."""
    from fcn_monitor import fcn_duet
    cur = fcn_duet.render_status_plot
    if getattr(cur, '_smooth_wrapper', False):
        return cur
    original = cur

    @functools.wraps(original)
    def render_status_plot(self):
        result = original(self)
        try:
            if getattr(self, 'status_smooth_plot', True) and smooth_lines(self):
                canvas = getattr(self, 'statusCanvas', None)
                if canvas is not None:
                    canvas.draw_idle()
        except RuntimeError:
            pass
        except Exception as e:
            print(f"Status plot smoothing skipped: {e}")
        return result

    render_status_plot._smooth_wrapper = True
    render_status_plot._smooth_original = original
    fcn_duet.render_status_plot = render_status_plot
    return render_status_plot
