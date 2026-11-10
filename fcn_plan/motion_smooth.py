"""
Smoothing of an imported motion curve (VXP / CSV respiratory signal) before it becomes the plan.

Recorded breathing signals carry sample-to-sample noise (~0.05-0.07 mm at 25 Hz in the VXP files tested): the device
cannot reproduce it, and a plan that zig-zags every sample makes the controller fall behind (measured: 1.4-2 % slower
on KINETIQ and DYNAMIQ).  A Savitzky-Golay filter (local quadratic fit over the window) removes the noise and keeps the
breathing peaks much better than a moving average of the same length.

    from fcn_plan.motion_smooth import smooth_curve, curve_stats
    y = smooth_curve(amp, samples_per_second, window_s)      # window_s 0 = unchanged
"""
import numpy as np

DEFAULT_WINDOW_S = 0.4       # s: removes the sample-to-sample noise of 25 Hz VXP files, peaks within ~0.1 mm
MAX_WINDOW_S = 5.0
POLYORDER = 2


def window_samples(sps, window_s):
    """Odd number of samples of the filter window (0 = no smoothing)."""
    n = int(round(float(window_s) * float(sps)))
    if n < POLYORDER + 3:
        return 0
    return n if n % 2 == 1 else n + 1


def smooth_curve(y, sps, window_s):
    """Savitzky-Golay smoothing over window_s seconds; NaN gaps are filled for the filter and put back."""
    y = np.asarray(y, dtype=float)
    n = window_samples(sps, window_s)
    if n == 0 or len(y) < n:
        return y.copy()
    from scipy.signal import savgol_filter
    nan = np.isnan(y)
    yy = y.copy()
    if nan.any():
        idx = np.arange(len(y))
        yy[nan] = np.interp(idx[nan], idx[~nan], y[~nan])
    out = savgol_filter(yy, n, POLYORDER, mode='interp')
    out[nan] = np.nan
    return out


def reversals(y):
    """Direction changes of a sampled curve (each costs time on the controller)."""
    d = np.diff(np.asarray(y, dtype=float))
    s = np.sign(d[np.abs(d) > 1e-9])
    return int(np.sum(s[1:] * s[:-1] < 0))


def curve_stats(raw, smooth):
    """What the smoothing changed: largest and RMS difference, direction changes before / after."""
    raw = np.asarray(raw, dtype=float)
    smooth = np.asarray(smooth, dtype=float)
    d = np.abs(smooth - raw)
    ok = ~np.isnan(d)
    return {
        'max_diff': float(np.max(d[ok])) if ok.any() else 0.0,
        'rms_diff': float(np.sqrt(np.mean(d[ok] ** 2))) if ok.any() else 0.0,
        'rev_raw': reversals(raw[ok]),
        'rev_smooth': reversals(smooth[ok]),
        'p2p_raw': float(np.nanmax(raw) - np.nanmin(raw)) if ok.any() else 0.0,
        'p2p_smooth': float(np.nanmax(smooth) - np.nanmin(smooth)) if ok.any() else 0.0,
    }
