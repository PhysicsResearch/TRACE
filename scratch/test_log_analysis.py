"""
Tests of fcn_logs/log_analysis.py (core of the Log files tab): synthetic data with known answers
(shift sign, comparison stats, ensemble band, peaks / periods on smooth and 200 ms staircase data,
movement detection, ROI, offsets, tables / CSV in the v2 style, aligned export read back), the logged
sensor waits of the v2 log format (reader: dummy, synthetic multi-wait logs written by write_wait_log,
every note kind, malformed notes, rows only; removal: CutMap / remove_waits; pairing with the G-code
pauses; no estimation), every real sample log format (v1 unchanged: set TRACE_LA_BASELINE to a copy of
the previous module to compare every real log with it) plus the curve2.gcode reference.
Prints PASS / FAIL lines and ends with "ALL PASSED" or "<n> FAILED" (exit code 1 on failure).
Run:  set QT_QPA_PLATFORM=offscreen  &  C:\\Users\\gabri\\anaconda3\\envs\\TRACE\\python.exe scratch\\test_log_analysis.py
"""
import glob
import math
import os
import shutil
import sys
import tempfile
import time
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

import numpy as np

from fcn_logs import log_analysis as la

RESULTS = []
TMP = tempfile.mkdtemp(prefix="trace_log_analysis_")
RNG = np.random.default_rng(12345)


def check(name, cond, detail=""):
    ok = bool(cond)
    RESULTS.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}: {name}" + (f"  [{detail}]" if detail else ""))
    return ok


def section(fn):
    print(f"\n=== {fn.__name__} ===")
    try:
        fn()
    except Exception:
        RESULTS.append(False)
        print(f"FAIL: {fn.__name__} raised\n{traceback.format_exc()}")


def curve(t, data, name="syn", kind="log", probe=None, meta=None):
    return la.Curve(name=name, kind=kind, path="", t=np.asarray(t, float), data=data,
                    probe=probe, meta=dict(meta or {}))


def sine(t, period=4.0, amp=2.0, lag=0.0, base=0.0):
    return base + amp * np.sin(2.0 * np.pi * (np.asarray(t) - lag) / period)


def staircase_times(t_end, dt_log=0.08, jitter=0.01, t0=0.0):
    ts = np.arange(t0, t_end, dt_log)
    ts = ts + RNG.uniform(-jitter, jitter, ts.size)
    ts[0] = max(ts[0], t0)
    return ts


def hold(ts, refresh=0.2):
    """Refresh times of a sample-and-hold position (Duet machinePosition every `refresh` s)."""
    return np.floor(np.asarray(ts) / refresh + 1e-9) * refresh


def near(a, b, tol):
    return a is not None and np.isfinite(a) and abs(a - b) <= tol


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path


# ---------------------------------------------------------------------------
# Synthetic tests
# ---------------------------------------------------------------------------
def test_constants_and_curve():
    check("AXIS_ORDER = DOF + raw + X/Y/Z",
          la.AXIS_ORDER == la.PLATFORM_DOF + la.PLATFORM_RAW + la.PHANTOM_AXES)
    check("PLATFORM_RAW", la.PLATFORM_RAW == ['A', 'B', 'C', 'D', "'e", "'f", "'a", "'c"])
    check("axis_unit deg / mm",
          [la.axis_unit(a) for a in ('Roll', 'Pitch', 'Yaw', 'Cmd Roll', 'Cmd Yaw', 'SI', 'Cmd LAT', "'e", 'X')]
          == ['deg'] * 5 + ['mm'] * 4)
    t = np.arange(5.0)
    c = curve(t, {'foo': t, 'Cmd SI': t, 'X': t, "'a": t, 'Roll': t, 'LAT': t})
    check("Curve.axes canonical order then Cmd then others", c.axes() == ['LAT', 'Roll', "'a", 'X', 'Cmd SI', 'foo'],
          str(c.axes()))
    check("Curve.has", c.has('LAT') and not c.has('SI'))
    c.time_offset = 1.5
    c.value_offsets = {'LAT': 10.0}
    check("Curve.times applies time_offset", np.allclose(c.times(), t + 1.5))
    check("Curve.values applies value offset", np.allclose(c.values('LAT'), t + 10.0)
          and np.allclose(c.values('X'), t))
    for k in ('computer_time', 'gcode', 'device', 'axes', 'end', 'gaps', 'pauses', 'format',
              'all_zero_axes', 'n', 'median_dt'):
        if k not in c.meta:
            check(f"meta key {k} present", False)
            break
    else:
        check("Curve meta keys always present", True)
    check("meta n / median_dt computed", c.meta['n'] == 5 and near(c.meta['median_dt'], 1.0, 1e-12))
    try:
        curve([0.0, 1.0, 1.0], {'X': [0, 1, 2]})
        check("non increasing times rejected", False)
    except ValueError:
        check("non increasing times rejected", True)
    check("roi_mask None = all", la.roi_mask(t, None).all())
    check("roi_mask inclusive / either order",
          list(la.roi_mask(t, (3, 1))) == [False, True, True, True, False])


def test_estimate_shift():
    t = np.arange(0.0, 30.0, 0.02)
    ref = curve(t, {'SI': sine(t)}, name="ref")
    for lag in (0.73, -1.234):
        cur = curve(t, {'SI': sine(t, lag=lag)}, name="cur")       # cur(t) = ref(t - lag)
        r = la.estimate_shift(ref, cur, 'SI', max_lag=1.5)
        check(f"sine lag {lag:+.3f}: shift = {-lag:+.3f} (sign convention)", near(r['shift'], -lag, 0.02),
              f"shift={r['shift']:.4f} corr={r['corr']:.4f}")
        check(f"sine lag {lag:+.3f}: corr ~ 1 and n > 0", r['corr'] > 0.999 and r['n'] > 1000)
        cur.time_offset += r['shift']
        cmp_ = la.compare(ref, cur, 'SI')
        check(f"sine lag {lag:+.3f}: adding shift to time_offset aligns the curves", cmp_['rms'] < 0.01,
              f"rms={cmp_['rms']:.5f}")
    cur = curve(t, {'SI': sine(t, lag=0.73)})
    r = la.estimate_shift(ref, cur, 'SI', max_lag=5.0)
    check("periodic sine, max_lag 5 > period: smallest |shift| peak chosen", near(r['shift'], -0.73, 0.02),
          f"shift={r['shift']:.4f}")

    # non-periodic signal, lag 2 s, both with noise
    tt = np.arange(0.0, 40.0, 0.01)
    base = lambda x: np.exp(-((x - 20) / 4.0) ** 2) * np.sin(2 * np.pi * x / 3.0) + 0.05 * x
    ref2 = curve(tt, {'AP': base(tt) + RNG.normal(0, 0.01, tt.size)})
    cur2 = curve(tt, {'AP': base(tt - 2.0) + RNG.normal(0, 0.01, tt.size)})
    r = la.estimate_shift(ref2, cur2, 'AP', max_lag=5.0)
    check("non-periodic noisy curve delayed by 2 s -> shift -2", near(r['shift'], -2.0, 0.02),
          f"shift={r['shift']:.4f} corr={r['corr']:.4f}")
    r_roi = la.estimate_shift(ref2, cur2, 'AP', roi=(14.0, 26.0), max_lag=5.0)
    check("ROI on the reference time base gives the same shift", near(r_roi['shift'], -2.0, 0.02),
          f"shift={r_roi['shift']:.4f} n={r_roi['n']}")
    check("ROI limits the number of compared samples", r_roi['n'] < r['n'] and r_roi['n'] <= 1201,
          f"n_roi={r_roi['n']} n={r['n']}")
    cur2.time_offset = 0.5                                   # existing offset: shift is relative to it
    r_off = la.estimate_shift(ref2, cur2, 'AP', max_lag=5.0)
    check("existing time_offset is taken into account", near(r_off['shift'], -2.5, 0.02),
          f"shift={r_off['shift']:.4f}")
    ref2.time_offset = 1.0
    r_off2 = la.estimate_shift(ref2, cur2, 'AP', max_lag=5.0)
    check("reference time_offset is taken into account", near(r_off2['shift'], -1.5, 0.02),
          f"shift={r_off2['shift']:.4f}")
    # staircase (200 ms refresh) copy of the delayed sine: shift within one refresh step
    ts = staircase_times(30.0)
    st = curve(ts, {'SI': sine(hold(ts), lag=0.5)})
    r = la.estimate_shift(ref, st, 'SI', max_lag=1.5)
    check("200 ms staircase copy: shift within one step", -0.5 - 0.2 - 0.02 <= r['shift'] <= -0.5 + 0.02,
          f"shift={r['shift']:.4f}")
    flat = curve(t, {'SI': np.zeros_like(t)})
    r = la.estimate_shift(flat, cur, 'SI')
    check("constant reference -> shift NaN", math.isnan(r['shift']))


def test_compare():
    t = np.arange(0.0, 30.0, 0.01)
    ref = curve(t, {'SI': sine(t)})
    noise = RNG.normal(0, 0.05, t.size)
    cur = curve(t, {'SI': sine(t) + 0.5 + noise})
    r = la.compare(ref, cur, 'SI')
    check("compare mean = offset 0.5", near(r['mean'], 0.5, 0.005), f"mean={r['mean']:.4f}")
    check("compare std = noise 0.05", near(r['std'], 0.05, 0.003), f"std={r['std']:.4f}")
    check("compare rms = sqrt(0.5^2+0.05^2)", near(r['rms'], math.hypot(0.5, 0.05), 0.005),
          f"rms={r['rms']:.4f}")
    check("compare max_abs / p95_abs", r['max_abs'] >= r['p95_abs'] > 0.5 and r['max_abs'] < 0.8)
    check("compare corr ~ 1, n = overlap samples", r['corr'] > 0.99 and r['n'] == t.size,
          f"corr={r['corr']:.4f} n={r['n']}")
    check("compare diff = cur - ref", np.allclose(r['diff'], 0.5 + noise, atol=1e-9))
    cur.value_offsets['SI'] = -0.5
    r2 = la.compare(ref, cur, 'SI')
    check("value offset changes mean (-0.5 -> ~0)", near(r2['mean'], 0.0, 0.005), f"mean={r2['mean']:.4f}")
    r3 = la.compare(ref, cur, 'SI', roi=(5.0, 10.0))
    check("ROI restricts compare to 5..10 s", r3['n'] == 501 and r3['t'][0] >= 5.0 - 1e-9 and r3['t'][-1] <= 10.0 + 1e-9,
          f"n={r3['n']}")
    short = curve(np.arange(10.0, 15.0, 0.01), {'SI': sine(np.arange(10.0, 15.0, 0.01))})
    r4 = la.compare(ref, short, 'SI')
    check("compare uses only the overlap", r4['n'] == 500 and near(r4['rms'], 0.0, 1e-9))
    short.time_offset = 100.0
    r5 = la.compare(ref, short, 'SI')
    check("no overlap -> n 0 and NaN stats", r5['n'] == 0 and math.isnan(r5['mean']))


def test_ensemble():
    t = np.arange(0.0, 30.0, 0.01)
    lags = [0.0, 0.3, -0.2]
    sigma = 0.02
    curves = [curve(t, {'SI': sine(t, lag=L) + RNG.normal(0, sigma, t.size)}, name=f"c{i}")
              for i, L in enumerate(lags)]
    raw = la.ensemble(curves, 'SI')
    for c in curves[1:]:
        c.time_offset = la.estimate_shift(curves[0], c, 'SI', max_lag=1.0)['shift']
    check("estimated offsets undo the lags", near(curves[1].time_offset, -0.3, 0.02)
          and near(curves[2].time_offset, 0.2, 0.02),
          f"{curves[1].time_offset:.3f}, {curves[2].time_offset:.3f}")
    e = la.ensemble(curves, 'SI', k=2.0)
    check("aligned ensemble: std band ~ noise", 0.012 < e['std_mean'] < 0.024,
          f"std_mean={e['std_mean']:.4f} std_max={e['std_max']:.4f}")
    check("unaligned ensemble std much larger", raw['std_mean'] > 5 * e['std_mean'],
          f"raw std_mean={raw['std_mean']:.4f}")
    ok = np.isfinite(e['std'])
    check("lo / hi = mean -/+ k*std", np.allclose(e['lo'][ok], e['mean'][ok] - 2 * e['std'][ok])
          and np.allclose(e['hi'][ok], e['mean'][ok] + 2 * e['std'][ok]))
    fin = e['n'] > 0
    check("vmin <= mean <= vmax", np.all(e['vmin'][fin] <= e['mean'][fin] + 1e-12)
          and np.all(e['mean'][fin] <= e['vmax'][fin] + 1e-12))
    check("n = 3 in the common part", int(np.max(e['n'])) == 3 and e['names'] == ['c0', 'c1', 'c2'])
    part = curve(np.arange(0.0, 10.0, 0.01), {'SI': sine(np.arange(0.0, 10.0, 0.01))}, name="part")
    single = curve(np.arange(0.0, 20.0, 0.01), {'SI': sine(np.arange(0.0, 20.0, 0.01))}, name="single")
    e2 = la.ensemble([part, single], 'SI')
    n_at = lambda tq: int(e2['n'][np.argmin(np.abs(e2['t'] - tq))])
    check("nan-aware: n follows the curves covering each time", n_at(5.0) == 2 and n_at(15.0) == 1)
    check("std NaN where only 1 curve", math.isnan(e2['std'][np.argmin(np.abs(e2['t'] - 15.0))]))
    e3 = la.ensemble(curves, 'SI', roi=(10.0, 12.0))
    check("ensemble ROI", e3['t'][0] >= 10.0 - 1e-9 and e3['t'][-1] <= 12.0 + 1e-9 and e3['t'].size == 201)
    e4 = la.ensemble([curve(t, {'X': t})], 'SI')
    check("ensemble without the axis -> empty", e4['t'].size == 0 and math.isnan(e4['std_mean']))


def test_peaks_periods():
    t = np.arange(0.0, 20.5, 0.01)
    c = curve(t, {'SI': sine(t)})
    p = la.find_peaks_curve(c, 'SI')
    check("sine maxima at 1, 5, 9, 13, 17", p['t'].size == 5 and np.allclose(p['t'], [1, 5, 9, 13, 17], atol=0.011),
          str(np.round(p['t'], 3)))
    check("peak values = amplitude", np.allclose(p['v'], 2.0, atol=1e-3) and p['kind'] == ['max'] * 5)
    ps = la.period_stats(p['t'])
    check("period_stats mean 4.0, freq 0.25", near(ps['mean'], 4.0, 0.01) and near(ps['freq'], 0.25, 0.001)
          and ps['n'] == 4 and ps['std'] < 0.01, str({k: ps[k] for k in ('n', 'mean', 'std', 'min', 'max')}))
    pm = la.find_peaks_curve(c, 'SI', kind='min')
    check("sine minima at 3, 7, 11, 15, 19", np.allclose(pm['t'], [3, 7, 11, 15, 19], atol=0.011)
          and np.allclose(pm['v'], -2.0, atol=1e-3))
    pb = la.find_peaks_curve(c, 'SI', kind='both')
    check("kind both: 10 peaks sorted, alternating", pb['t'].size == 10 and np.all(np.diff(pb['t']) > 0)
          and pb['kind'][:4] == ['max', 'min', 'max', 'min'])
    pr = la.find_peaks_curve(c, 'SI', roi=(4.0, 14.0))
    check("ROI: peaks 5, 9, 13 only", np.allclose(pr['t'], [5, 9, 13], atol=0.011), str(np.round(pr['t'], 3)))
    c.time_offset = 1.5
    po = la.find_peaks_curve(c, 'SI')
    check("time_offset shifts peak times", np.allclose(po['t'], np.array([1, 5, 9, 13, 17]) + 1.5, atol=0.011))
    c.time_offset = 0.0
    hp = la.find_peaks_curve(c, 'SI', prominence=5.0)
    check("prominence above the range -> no peak", hp['t'].size == 0)
    check("period_stats with 1 peak -> NaN", math.isnan(la.period_stats([3.0])['mean'])
          and la.period_stats([3.0])['n'] == 0)
    check("period_stats with 2 peaks -> one period", la.period_stats([1.0, 5.0])['mean'] == 4.0)

    # 200 ms staircase version (log every 80 ms with jitter)
    ts = staircase_times(20.5)
    st = curve(ts, {'SI': sine(hold(ts))})
    p2 = la.find_peaks_curve(st, 'SI')
    check("staircase: 5 maxima within one step (+hold delay)", p2['t'].size == 5
          and np.all(np.abs(p2['t'] - np.array([1, 5, 9, 13, 17]) - 0.1) <= 0.2), str(np.round(p2['t'], 3)))
    ps2 = la.period_stats(p2['t'])
    check("staircase: period 4.0 +- 0.05", near(ps2['mean'], 4.0, 0.05), f"mean={ps2['mean']:.4f}")

    d = la.dominant_period(c, 'SI')
    check("dominant_period sine = 4.0", near(d['period'], 4.0, 0.02) and d['strength'] > 0.9
          and near(d['freq'], 0.25, 0.002), str(d))
    d2 = la.dominant_period(st, 'SI')
    check("dominant_period staircase = 4.0", near(d2['period'], 4.0, 0.05), str(d2))
    trend = curve(t, {'SI': sine(t) + 0.3 * t + RNG.normal(0, 0.05, t.size)})
    d3 = la.dominant_period(trend, 'SI')
    check("dominant_period with trend + noise = 4.0", near(d3['period'], 4.0, 0.05), str(d3))
    d4 = la.dominant_period(c, 'SI', roi=(0.0, 10.0))
    check("dominant_period in a ROI", near(d4['period'], 4.0, 0.03), str(d4))
    d5 = la.dominant_period(curve(t, {'SI': np.ones_like(t)}), 'SI')
    check("dominant_period of a constant -> NaN", math.isnan(d5['period']))


def _piecewise(t, knots):
    kt, kv = zip(*knots)
    return np.interp(t, kt, kv)


def test_detect_movements():
    # (a) ramp 25 -> 28 mm at 1 mm/s from 5 to 8 s, logged as a 200 ms staircase
    ts = staircase_times(12.0)
    truth = [(0, 25.0), (5, 25.0), (8, 28.0), (12, 28.0)]
    c = curve(ts, {'SI': _piecewise(hold(ts), truth)})
    mv = la.detect_movements(c, 'SI')
    check("staircase ramp = ONE movement", len(mv) == 1, f"{len(mv)} movements")
    if mv:
        m = mv[0]
        check("staircase ramp start within one step of 5 s", 5.0 - 0.01 <= m['t_start'] <= 5.0 + 0.2 + 0.01,
              f"t_start={m['t_start']:.3f}")
        check("staircase ramp stop within one step of 8 s", 8.0 - 0.01 <= m['t_stop'] <= 8.0 + 0.2 + 0.01,
              f"t_stop={m['t_stop']:.3f}")
        check("staircase ramp v_start / v_stop / delta / duration",
              near(m['v_start'], 25.0, 1e-9) and near(m['v_stop'], 28.0, 1e-9) and near(m['delta'], 3.0, 1e-9)
              and near(m['duration'], m['t_stop'] - m['t_start'], 1e-12))
        check("staircase ramp peak_speed ~ 1 mm/s (not inflated by the holds)", 0.7 <= m['peak_speed'] <= 1.6,
              f"peak_speed={m['peak_speed']:.3f}")
        check("staircase ramp complete", m['complete'] is True)
    mv_short = la.detect_movements(c, 'SI', settle_time=0.1)
    check("settle_time shorter than the 200 ms holds splits the ramp", len(mv_short) > 5, f"{len(mv_short)}")

    # (b) two separated moves (smooth, 10 ms)
    t = np.arange(0.0, 10.0 + 1e-9, 0.01)
    knots = [(0, 0.0), (2, 0.0), (3, 5.0), (6, 5.0), (6.5, 2.0), (10, 2.0)]
    c2 = curve(t, {'AP': _piecewise(t, knots)})
    mv = la.detect_movements(c2, 'AP')
    check("two separated moves", len(mv) == 2, f"{len(mv)}")
    if len(mv) == 2:
        check("move 1: 2.0 -> 3.0 s, +5", near(mv[0]['t_start'], 2.0, 0.011) and near(mv[0]['t_stop'], 3.0, 0.011)
              and near(mv[0]['delta'], 5.0, 1e-6), str({k: round(v, 3) for k, v in mv[0].items() if k != 'complete'}))
        check("move 2: 6.0 -> 6.5 s, -3", near(mv[1]['t_start'], 6.0, 0.011) and near(mv[1]['t_stop'], 6.5, 0.011)
              and near(mv[1]['delta'], -3.0, 1e-6))
        check("peak speeds 5 and 6 mm/s", near(mv[0]['peak_speed'], 5.0, 0.05) and near(mv[1]['peak_speed'], 6.0, 0.06),
              f"{mv[0]['peak_speed']:.3f}, {mv[1]['peak_speed']:.3f}")
    mv_roi = la.detect_movements(c2, 'AP', roi=(5.0, 10.0))
    check("ROI 5..10 s: only the second move", len(mv_roi) == 1 and near(mv_roi[0]['t_start'], 6.0, 0.011))
    c2.time_offset = 10.0
    c2.value_offsets = {'AP': 100.0}
    mv_off = la.detect_movements(c2, 'AP')
    check("offsets: times +10 s, values +100, delta unchanged",
          len(mv_off) == 2 and near(mv_off[0]['t_start'], 12.0, 0.011) and near(mv_off[0]['v_start'], 100.0, 1e-9)
          and near(mv_off[0]['delta'], 5.0, 1e-6))
    reference_kind = curve(np.array([k[0] for k in knots], float), {'AP': np.array([k[1] for k in knots])},
                           kind="reference")
    mv_ref = la.detect_movements(reference_kind, 'AP')
    check("sparse piecewise-linear reference knots: same two moves",
          len(mv_ref) == 2 and near(mv_ref[0]['t_start'], 2.0, 1e-9) and near(mv_ref[0]['t_stop'], 3.0, 1e-9)
          and near(mv_ref[1]['t_stop'], 6.5, 1e-9) and near(mv_ref[0]['peak_speed'], 5.0, 1e-9))

    # (c) tiny wiggle below the threshold
    c3 = curve(t, {'SI': 10.0 + 0.01 * np.sin(2 * np.pi * t)})
    check("wiggle of 0.01 < threshold 0.02: no movement", la.detect_movements(c3, 'SI') == [])
    check("same wiggle with threshold 0.005: movement", len(la.detect_movements(c3, 'SI', threshold=0.005)) >= 1)

    # (d) merge_gap: two moves 0.8 s apart (10 mm/s, well above threshold per sample)
    c4 = curve(t, {'X': _piecewise(t, [(0, 0.0), (1, 0.0), (1.5, 5.0), (2.3, 5.0), (2.8, 10.0), (10, 10.0)])})
    check("moves 0.8 s apart are separate", len(la.detect_movements(c4, 'X')) == 2)
    mg = la.detect_movements(c4, 'X', merge_gap=1.0)
    check("merge_gap 1.0 merges them", len(mg) == 1 and near(mg[0]['t_start'], 1.0, 0.011)
          and near(mg[0]['t_stop'], 2.8, 0.011) and near(mg[0]['delta'], 10.0, 1e-6), str(mg))
    check("merge_gap 0.5 keeps them", len(la.detect_movements(c4, 'X', merge_gap=0.5)) == 2)

    # (e) min_duration: 0.2 s move and 2 s move
    c5 = curve(t, {'X': _piecewise(t, [(0, 0.0), (1, 0.0), (1.2, 1.0), (3, 1.0), (5, 11.0), (10, 11.0)])})
    check("min_duration 0: both moves", len(la.detect_movements(c5, 'X')) == 2)
    md = la.detect_movements(c5, 'X', min_duration=0.5)
    check("min_duration 0.5 drops the 0.2 s move", len(md) == 1 and near(md[0]['t_start'], 3.0, 0.011), str(md))
    # ramp changing by exactly the threshold per sample: start / stop stay within one sample
    c7 = curve(t, {'X': _piecewise(t, [(0, 0.0), (3, 0.0), (5, 4.0), (10, 4.0)])})
    mv7 = la.detect_movements(c7, 'X')
    check("ramp of exactly threshold per sample: one move, start/stop within one sample",
          len(mv7) == 1 and near(mv7[0]['t_start'], 3.0, 0.011) and near(mv7[0]['t_stop'], 5.0, 0.011), str(mv7))

    # (f) still moving at the end
    c6 = curve(t, {'X': _piecewise(t, [(0, 0.0), (8, 0.0), (10, 4.0)])})
    mv6 = la.detect_movements(c6, 'X')
    check("movement still running at the end: complete False, stop = end of data",
          len(mv6) == 1 and mv6[0]['complete'] is False and near(mv6[0]['t_stop'], 10.0, 0.011)
          and near(mv6[0]['t_start'], 8.0, 0.011), str(mv6))


GCODE_PAUSE = """G90
G1 X0 F600
G4 P1000
G1 X10 F600
G4 P2000
M98 P"0:macros/sensor_wait.g"
G4 P1000
G1 X20 F600
G4 P3000
"""

GCODE_TWO_PAUSES = """G90
G1 X0 F600
G4 P1000
G1 X10 F600
M98 P"0:macros/sensor_wait.g"
G4 P1000
G1 X20 F600
M226
G4 P1000
G1 X5 F600
G4 P2000
"""


def _log_from(ref, axis, dt=0.05, staircase=False, noise=0.0, t_end=None):
    t_end = t_end if t_end is not None else ref.t[-1]
    if staircase:
        ts = staircase_times(t_end)
        tq = hold(ts)
    else:
        ts = np.arange(0.0, t_end, dt)
        tq = ts
    v = la.sample(ref, axis, tq)
    v = np.where(np.isfinite(v), v, ref.data[axis][-1]) + (RNG.normal(0, noise, ts.size) if noise else 0.0)
    return curve(ts, {axis: v}, name="log")


def test_reference_and_pauses():
    ref = la.read_reference_gcode(GCODE_PAUSE, name="syn_ref")
    check("text G-code: name, kind, device", ref.name == "syn_ref" and ref.kind == "reference"
          and ref.meta['device'] == 'Lung Phantom' and ref.has('X'))
    check("pause detected at 4.0 s", len(ref.meta['pauses']) == 1 and ref.meta['pauses'][0][0] == 'sensor_wait'
          and near(ref.meta['pauses'][0][1], 4.0, 1e-9), str(ref.meta['pauses']))
    check("reference timeline: X 10 at 2 s, 20 at 6 s, ends 9 s",
          near(la.sample(ref, 'X', [2.0])[0], 10.0, 1e-9) and near(la.sample(ref, 'X', [6.0])[0], 20.0, 1e-9)
          and near(ref.t[-1], 9.0, 1e-9) and near(ref.meta['total_time'], 9.0, 1e-9))
    mv = la.detect_movements(ref, 'X')
    check("reference movements (1-2 s, 5-6 s)", len(mv) == 2 and near(mv[1]['t_start'], 5.0, 1e-9))

    ref.time_offset = 0.5
    ref.value_offsets = {'X': 1.0}
    ref5 = la.with_pause_durations(ref, [5.0])
    check("with_pause_durations keeps offsets", ref5.time_offset == 0.5 and ref5.value_offsets == {'X': 1.0})
    ref.time_offset, ref.value_offsets = 0.0, {}
    ref5.time_offset, ref5.value_offsets = 0.0, {}
    check("pause of 5 s: holds 10 mm from 4 to 9 s",
          np.allclose(la.sample(ref5, 'X', [4.0, 6.5, 9.0]), 10.0))
    check("pause of 5 s: later times shift by 5 s", near(la.sample(ref5, 'X', [11.0])[0], 20.0, 1e-9)
          and near(ref5.t[-1], 14.0, 1e-9) and near(ref5.meta['total_time'], 14.0, 1e-9))
    check("pause of 5 s: earlier times unchanged",
          np.allclose(la.sample(ref5, 'X', [0.5, 1.5, 2.0]), la.sample(ref, 'X', [0.5, 1.5, 2.0])))
    check("meta pause_durations / pauses", ref5.meta['pause_durations'] == [5.0]
          and near(ref5.meta['pauses'][0][1], 4.0, 1e-9))
    ref_kw = la.read_reference_gcode(GCODE_PAUSE, pause_durations=[5.0])
    check("read_reference_gcode(pause_durations=...) = with_pause_durations",
          np.allclose(ref_kw.t, ref5.t) and np.allclose(ref_kw.data['X'], ref5.data['X']))

    # a log without logged waits: shown as recorded, nothing paired, nothing estimated
    log = _log_from(ref5, 'X', dt=0.05)
    pr = la.pair_pause_waits(ref, log)
    check("log without logged waits: the pause stays 0 s (no estimate), note says so",
          len(pr) == 1 and pr[0]['length'] == 0.0 and pr[0]['kind'] == 'none' and 'no logged wait' in pr[0]['note'],
          str(pr))
    check("pause estimation is gone from the core (no estimate_pause_durations or its helpers)",
          not any(hasattr(la, n) for n in ('estimate_pause_durations', '_pause_search', '_pause_seed', '_move_pause',
                                           '_hidden_rival', '_first_start_after', '_largest_range_axis',
                                           '_PAUSE_DT', '_MIN_PAUSE_HOLD')))

    ref2 = la.read_reference_gcode(GCODE_TWO_PAUSES)
    check("two pauses (sensor_wait, M226)", [p[0] for p in ref2.meta['pauses']] == ['sensor_wait', 'M226'],
          str(ref2.meta['pauses']))
    p2 = la.pair_pause_waits(ref2, None)
    check("pairing without a source log: every pause 0 s; M226 'not logged', sensor_wait 'no logged wait'",
          [p['length'] for p in p2] == [0.0, 0.0] and p2[1]['note'] == 'not logged'
          and p2[0]['note'] == 'no logged wait', str(p2))
    try:
        la.with_pause_durations(log, [1.0])
        check("with_pause_durations on a log raises", False)
    except ValueError:
        check("with_pause_durations on a log raises", True)


# ---------------------------------------------------------------------------
# Regressions of the review findings (mid-motion pauses, slow staircase ramps, gaps, reader)
# ---------------------------------------------------------------------------
def _stair_log(truth, axis, t_end, name="log", meta=None):
    """Log of a reference as TRACE writes it: rows every ~80 ms, machinePosition refreshed every
    200 ms (sample-and-hold), values rounded to 0.001."""
    ts = staircase_times(t_end)
    v = la.sample(truth, axis, hold(ts))
    v = np.where(np.isfinite(v), v, truth.data[axis][-1])
    return curve(ts, {axis: np.round(v, 3)}, name=name, meta=meta)


def _cosine_gcode(t_pause, period=4.0, amp=5.0, t_end=8.0, step=0.1):
    """Z = amp * (1 - cos(2 pi t / period)) in 0.1 s G1 steps (M203 I0.6: min speed 0.01 mm/s) with a
    sensor_wait between two steps at t_pause (one time or a tuple of times; inside the motion, no
    dwell around it), then G4 P2000 / G1 Z5 / G4 P2000."""
    pts = tuple(t_pause) if isinstance(t_pause, (tuple, list)) else (t_pause,)
    lines = ["G90", "M203 I0.6", "G1 Z0 F600"]
    z_prev = 0.0
    for k in range(1, int(round(t_end / step)) + 1):
        t = k * step
        z = amp * (1.0 - math.cos(2.0 * math.pi * t / period))
        lines.append(f"G1 Z{z:.6f} F{max(abs(z - z_prev) / step * 60.0, 0.6):.6f}")
        z_prev = z
        if any(abs(t - tp) < 1e-9 for tp in pts):
            lines.append('M98 P"0:macros/sensor_wait.g"')
    lines += ["G4 P2000", "G1 Z5 F600", "G4 P2000"]
    return "\n".join(lines) + "\n"


def test_slow_staircase_ramps():
    # review finding 2: at 0.05 mm/s every 200 ms hold looked settled (~25 tiny movements), and
    # t_start / t_stop were the last / first sample inside the threshold band (late / early)
    for speed in (0.05, 0.1):
        dur = 1.0 / speed
        knots = [(0.0, 25.0), (5.0, 25.0), (5.0 + dur, 26.0), (10.0 + dur, 26.0)]
        kt = np.array([k[0] for k in knots])
        kv = np.array([k[1] for k in knots])
        truth = curve(kt, {'SI': kv}, kind="reference", name="ramp")
        log = _stair_log(truth, 'SI', kt[-1])
        mv = la.detect_movements(log, 'SI')
        check(f"{speed} mm/s staircase ramp (80 ms rows, 200 ms refresh, 0.001 rounding) = ONE movement",
              len(mv) == 1, f"{len(mv)} movements")
        if mv:
            m = mv[0]
            check(f"{speed} mm/s staircase ramp: start within 0.25 s of 5 s, stop within 0.25 s of {5 + dur:g} s",
                  near(m['t_start'], 5.0, 0.25) and near(m['t_stop'], 5.0 + dur, 0.25),
                  f"{m['t_start']:.3f} - {m['t_stop']:.3f}")
            check(f"{speed} mm/s staircase ramp: v_start / v_stop at the rest values, complete, not in a gap",
                  near(m['v_start'], 25.0, 1e-9) and near(m['v_stop'], 26.0, 1e-9) and m['complete'] is True
                  and m['in_gap'] is False)
        ts = np.arange(0.0, kt[-1] + 1e-9, 0.01)
        dense = curve(ts, {'SI': np.interp(ts, kt, kv)})
        md = la.detect_movements(dense, 'SI')
        tol_d = 0.003 / speed + 0.011        # rest tolerance / speed (was threshold / speed = 0.2 .. 0.4 s)
        check(f"{speed} mm/s dense 10 ms ramp: start / stop within {tol_d:.2f} s (not threshold/speed late / early)",
              len(md) == 1 and near(md[0]['t_start'], 5.0, tol_d) and near(md[0]['t_stop'], 5.0 + dur, tol_d),
              str([(round(x['t_start'], 3), round(x['t_stop'], 3)) for x in md]))
        mr = la.detect_movements(truth, 'SI')
        check(f"{speed} mm/s sparse reference rows: same rule, exact start / stop",
              len(mr) == 1 and near(mr[0]['t_start'], 5.0, 1e-9) and near(mr[0]['t_stop'], 5.0 + dur, 1e-9))
    # real stops are still found: two 0.05 mm/s ramps with a 1 s hold between them
    knots = [(0.0, 25.0), (2.0, 25.0), (12.0, 25.5), (13.0, 25.5), (23.0, 26.0), (26.0, 26.0)]
    two = _stair_log(curve([k[0] for k in knots], {'SI': [k[1] for k in knots]}, kind="reference"), 'SI', 26.0)
    mv2 = la.detect_movements(two, 'SI')
    check("two 0.05 mm/s staircase ramps with a 1 s hold: 2 movements, stop / start around the hold",
          len(mv2) == 2 and near(mv2[0]['t_stop'], 12.0, 0.25) and near(mv2[1]['t_start'], 13.0, 0.25)
          and near(mv2[0]['v_stop'], 25.5, 1e-9),
          str([(round(x['t_start'], 2), round(x['t_stop'], 2)) for x in mv2]))


GAP_LOG_HEAD = "# Device: Lung Phantom\nTime_s,Pos_X_mm,Probe\n"


def test_gap_movements():
    # review finding 3: a movement spanning a connection gap was reported complete with a
    # meaningless duration (3.97 -> 15.01 s for a real move 10 -> 12 s)
    rows = [f"{t:.3f},0.000,0" for t in np.arange(0.01, 3.98, 0.08)]
    rows += ["# Gap: connection lost at 4.000 s", "# Gap end: reconnected at 15.000 s"]
    rows += [f"{t:.3f},5.000,0" for t in np.arange(15.01, 18.0, 0.08)]
    rows += [f"{t:.3f},{min(8.0, 5.0 + 3.0 * (t - 18.0)):.3f},0" for t in np.arange(18.01, 24.0, 0.08)]
    c = la.read_trace_log(write(os.path.join(TMP, "gap_move.csv"), GAP_LOG_HEAD + "\n".join(rows) + "\n"))
    check("gap log: gap (4, 15) read", c.meta['gaps'] == [(4.0, 15.0)], str(c.meta['gaps']))
    check("gap_spans: last sample before / first after the gap",
          [(round(a, 3), round(b, 3)) for a, b in la.gap_spans(c)] == [(3.93, 15.01)], str(la.gap_spans(c)))
    mv = la.detect_movements(c, 'X')
    check("gap log: 2 movements", len(mv) == 2, str(mv))
    if len(mv) == 2:
        check("movement across the gap: in_gap True, complete False", mv[0]['in_gap'] is True
              and mv[0]['complete'] is False and near(mv[0]['delta'], 5.0, 1e-9), str(mv[0]))
        check("movement after the gap: in_gap False, complete True", mv[1]['in_gap'] is False
              and mv[1]['complete'] is True and near(mv[1]['t_start'], 18.0, 0.1))
    c.time_offset = 100.0
    mo = la.detect_movements(c, 'X')
    check("in_gap follows time_offset", len(mo) == 2 and mo[0]['in_gap'] and not mo[1]['in_gap']
          and near(mo[0]['t_start'], 103.93, 1e-6))
    mr = la.detect_movements(c, 'X', roi=(110.0, 130.0))
    check("ROI starting after the gap: the clean movement only", len(mr) == 1 and mr[0]['in_gap'] is False)
    check("every movement dict has in_gap (no gaps -> False)",
          all(m['in_gap'] is False for m in la.detect_movements(curve(np.arange(0, 5, 0.01),
              {'X': np.interp(np.arange(0, 5, 0.01), [0, 1, 2, 5], [0, 0, 3, 3])}), 'X')))


def test_reader_regressions():
    # review finding 4: a trailing delimiter shifted every column into the index
    trail = "Time_s,Pos_X_mm,Pos_Y_mm,Probe\n" + "".join(f"{0.1 * i:.2f},{i}.000,{2 * i}.000,{7 if i == 3 else 0},\n"
                                                         for i in range(10))
    c = la.read_trace_log(write(os.path.join(TMP, "trailing.csv"), trail))
    check("trailing delimiter on every row: columns not shifted",
          np.allclose(c.t, 0.1 * np.arange(10)) and np.allclose(c.data['X'], np.arange(10))
          and np.allclose(c.data['Y'], 2 * np.arange(10)) and c.probe is not None and c.probe[3] == 7
          and c.axes() == ['X', 'Y'], f"t={c.t[:3]} X={c.data.get('X', [])[:3]}")
    some = "Time_s,Pos_X_mm\n0.1,1\n0.2,2,\n0.3,3\n0.4,4,99\n0.5,5\n"
    c2 = la.read_trace_log(write(os.path.join(TMP, "trailing_some.csv"), some))
    check("extra fields on some rows: rows kept, extra fields ignored",
          np.allclose(c2.t, [0.1, 0.2, 0.3, 0.4, 0.5]) and np.allclose(c2.data['X'], [1, 2, 3, 4, 5]), f"{c2.t}")
    ws = "Time_s Pos_X_mm Probe\n0.1 1 0 \n0.2 2 0 5\n0.3 3 0\n"
    c3 = la.read_trace_log(write(os.path.join(TMP, "trailing_ws.txt"), ws))
    check("whitespace separated, extra field: columns not shifted",
          np.allclose(c3.t, [0.1, 0.2, 0.3]) and np.allclose(c3.data['X'], [1, 2, 3]))

    # review finding 5: Gap / End lines without 'at t s' took the time of the wrong row
    skip = "Time_s,Pos_X_mm\n0.1,1\n0.2,2,3,4\n0.3,3\n# End: closed\n0.4,9\n"
    c4 = la.read_trace_log(write(os.path.join(TMP, "fallback_end.csv"), skip))
    check("End line without time after a row with extra fields: time of the row before it (0.3)",
          c4.meta['end'] == ('closed', 0.3), str(c4.meta['end']))
    bad_t = ("Time_s,Pos_X_mm\n0.1,1\nabc,5\n# Gap: lost\n0.5,5\n0.6,6\n# Gap end: back\nxyz,1\n0.9,7\n1.0,8\n"
             "1.1,9\n,3\n# End: closed\n")
    c5 = la.read_trace_log(write(os.path.join(TMP, "fallback_gap.csv"), bad_t))
    check("Gap / Gap end / End without time next to rows with an invalid time: nearest kept rows",
          c5.meta['gaps'] == [(0.1, 0.9)] and c5.meta['end'] == ('closed', 1.1),
          f"{c5.meta['gaps']} {c5.meta['end']}")
    dup = "Time_s,Pos_X_mm\n0.1,1\n0.2,2\n0.2,7\n# End: closed\n0.3,3\n"
    c6 = la.read_trace_log(write(os.path.join(TMP, "fallback_dup.csv"), dup))
    check("End after a duplicate-time row: that time (0.2)", c6.meta['end'] == ('closed', 0.2), str(c6.meta['end']))

    # review finding 6: references always had all_zero_axes == []
    ref = la.read_reference_gcode("G90\nG1 X0 Y0 Z0 F600\nG1 X10 F600\nG4 P500\n")
    check("reference all_zero_axes computed (Y, Z)", ref.meta['all_zero_axes'] == ['Y', 'Z'],
          str(ref.meta['all_zero_axes']))
    check("with_pause_durations keeps all_zero_axes",
          la.with_pause_durations(la.read_reference_gcode(GCODE_PAUSE), [2.0]).meta['all_zero_axes'] == []
          and la.with_pause_durations(ref, []).meta['all_zero_axes'] == ['Y', 'Z'])


# ---------------------------------------------------------------------------
# Regressions of the second review (short / zero pauses inside motion, local rest level, stop +
# restart merges, gaps away from the pause, fewer fields than the header, drift cap)
# ---------------------------------------------------------------------------
def _seeded_log(fn, t_end, seed, row_dt=(0.075, 0.085), smooth=False, axis='Z', refresh=0.2):
    """Log of fn(t), reproducible per seed (its own RNG): rows at random intervals in row_dt,
    machinePosition refreshed every `refresh` s with a random phase (smooth=True: the value at the
    row time), values rounded to 0.001."""
    rng = np.random.default_rng(seed)
    n = int(math.ceil(t_end / row_dt[0])) + 5
    ts = np.concatenate(([0.0], np.cumsum(rng.uniform(row_dt[0], row_dt[1], n))))
    ts = ts[ts <= t_end]
    ph = rng.uniform(0.0, refresh)
    tq = ts if smooth else np.maximum(np.floor((ts - ph) / refresh) * refresh + ph, 0.0)
    return curve(ts, {axis: np.round(fn(tq), 3)}, name="log")


def _truth_fn(c, axis):
    return lambda t: la.sample(c, axis, np.clip(t, c.t[0], c.t[-1]), gaps_as_nan=False)


def test_rest_level_and_restart():
    # B: a sub-threshold step during a rest pulled the next movement start back to that step (2.98 s)
    fn = lambda t: np.interp(t, [0.0, 3.0, 3.05, 20.0, 25.0, 30.0], [0.0, 0.0, 0.01, 0.01, 5.0, 5.0])
    for smooth in (False, True):
        mv = la.detect_movements(_seeded_log(fn, 30.0, 1, smooth=smooth), 'Z')
        check(f"0.01 mm step at 3 s during a rest, 5 mm move 20 - 25 s ({'smooth' if smooth else 'staircase'}): one "
              f"movement starting at ~20 s from the rest value 0.01", len(mv) == 1 and near(mv[0]['t_start'], 20.0, 0.25)
              and near(mv[0]['v_start'], 0.01, 0.002), str([(round(m['t_start'], 2), round(m['t_stop'], 2)) for m in mv]))
    kt = [0.0, 2.0, 3.0, 4.0, 4.05, 20.0, 21.0, 25.0]
    kv = [0.0, 0.0, 1.0, 1.0, 1.008, 1.008, 2.0, 2.0]
    mr = la.detect_movements(curve(kt, {'Z': kv}, kind="reference"), 'Z')
    ml = la.detect_movements(_seeded_log(lambda t: np.interp(t, kt, kv), 25.0, 2), 'Z')
    check("creep of 0.008 after a stop, next move at 20 s: second movement starts at 20 s (reference exact, log "
          "within 0.25 s)", len(mr) == 2 and near(mr[1]['t_start'], 20.0, 1e-9) and len(ml) == 2
          and near(ml[1]['t_start'], 20.0, 0.25), f"{[(m['t_start'], m['t_stop']) for m in mr]} "
          f"{[(round(m['t_start'], 2), round(m['t_stop'], 2)) for m in ml]}")

    # C: stop, then restart 0.6 s later (settle 0.5): wrongly merged movements on a fixed seed set.
    # Original code (no drift rule): 28 / 0 / 0 of 150; first fix (interpolated drift): 60 / 44 / 18.
    rates = {}
    for speed, smooth in ((1.0, False), (0.35, False), (1.0, True)):
        t1 = 2.0 + 2.0 / speed
        knots = ([0.0, 2.0, t1, t1 + 0.6, t1 + 0.6 + 2.0 / speed, t1 + 4.6 + 2.0 / speed], [0, 0, 2.0, 2.0, 4.0, 4.0])
        f2 = lambda t, k=knots: np.interp(t, k[0], k[1])
        rates[(speed, smooth)] = sum(len(la.detect_movements(_seeded_log(f2, knots[0][-1], sd, smooth=smooth), 'Z')) != 2
                                     for sd in range(150))
    check("stop + restart 0.6 s later, 150 seeds: merge rate no worse than the original code (1 mm/s staircase "
          "<= 28 + 2, 0.35 mm/s staircase <= 1, 1 mm/s smooth 0)", rates[(1.0, False)] <= 30 and rates[(0.35, False)] <= 1
          and rates[(1.0, True)] == 0, str(rates))
    # ... while slow staircase ramps stay one movement (same seed set, rows 50 - 140 ms)
    for speed in (0.05, 0.1):
        t1 = 5.0 + 1.0 / speed
        f3 = lambda t, t1=t1: np.interp(t, [0.0, 5.0, t1, t1 + 5.0], [0.0, 0.0, 1.0, 1.0])
        counts = [len(la.detect_movements(_seeded_log(f3, t1 + 5.0, sd, row_dt=(0.05, 0.14)), 'Z')) for sd in range(20)]
        check(f"{speed} mm/s staircase ramp, 20 seeds: always one movement", counts == [1] * 20, str(counts))

    # F: the drift limit is capped (0.005) independently of the threshold band
    for thr in (0.1, 0.5):
        counts, starts, stops = [], [], []
        for sd in range(5):
            mv = la.detect_movements(_seeded_log(lambda t: np.interp(t, [0, 5, 25, 30], [0, 0, 1, 1]), 30.0, sd,
                                                 row_dt=(0.05, 0.14)), 'Z', threshold=thr)
            counts.append(len(mv))
            if mv:
                starts.append(mv[0]['t_start'])
                stops.append(mv[-1]['t_stop'])
        check(f"threshold {thr}: 0.05 mm/s staircase ramp 5 - 25 s is one movement, start / stop within 0.3 s "
              f"(was 8 pieces at 0.1)", counts == [1] * 5 and all(near(x, 5.0, 0.3) for x in starts)
              and all(near(x, 25.0, 0.3) for x in stops), f"{counts} {np.round(starts, 2)} {np.round(stops, 2)}")


def test_gaps_away_from_pause():
    # a gap strictly inside a movement (the estimate checks of this test went with the estimation)
    ref = la.read_reference_gcode(_cosine_gcode(6.0), name="cos")
    truth = la.with_pause_durations(ref, [5.0])
    full = _seeded_log(_truth_fn(truth, 'Z'), truth.t[-1] + 1.0, 3, row_dt=(0.05, 0.14))
    a, b = 2.0, 3.0
    keep = (full.t <= a) | (full.t >= b)
    log = curve(full.t[keep], {'Z': full.data['Z'][keep]}, meta={'gaps': [(a, b)]})
    mv = [m for m in la.detect_movements(log, 'Z') if m['t_start'] < a < m['t_stop']]
    check("gap strictly inside a movement: in_gap True, start_in_gap / stop_in_gap False",
          len(mv) == 1 and mv[0]['in_gap'] is True and mv[0]['start_in_gap'] is False
          and mv[0]['stop_in_gap'] is False, str(mv))
    # the movement across a gap (start before, stop after it): both sides flagged
    rows = [f"{t:.3f},0.000,0" for t in np.arange(0.01, 3.98, 0.08)]
    rows += ["# Gap: connection lost at 4.000 s", "# Gap end: reconnected at 15.000 s"]
    rows += [f"{t:.3f},5.000,0" for t in np.arange(15.01, 18.0, 0.08)]
    c = la.read_trace_log(write(os.path.join(TMP, "gap_sides.csv"), GAP_LOG_HEAD + "\n".join(rows) + "\n"))
    mv = la.detect_movements(c, 'X')
    check("movement across a gap: start_in_gap and stop_in_gap True",
          len(mv) == 1 and mv[0]['start_in_gap'] is True and mv[0]['stop_in_gap'] is True, str(mv))


def test_reader_fewer_fields():
    # E: rows with fewer fields than the header raised (the original code read them, missing Probe = 0)
    cases = {
        "hdr_trailing_rows_not.csv": ("Time_s,Pos_X_mm,Pos_Y_mm,Probe,\n0.0,1,2,0\n0.1,3,4,0\n0.2,5,6,7\n", [0, 0, 7]),
        "rows_without_probe.csv": ("# Device: Lung Phantom\nTime_s,Pos_X_mm,Pos_Y_mm,Probe\n0.0,1,2\n0.1,3,4\n0.2,5,6\n",
                                   [0, 0, 0]),
        "ws_rows_without_probe.txt": ("Time_s Pos_X_mm Pos_Y_mm Probe\n0.0 1 2\n0.1 3 4\n0.2 5 6\n", [0, 0, 0]),
        "tab_hdr_trailing.csv": ("Time_s\tPos_X_mm\tPos_Y_mm\tProbe\t\n0.0\t1\t2\t0\n0.1\t3\t4\t0\n0.2\t5\t6\t0\n",
                                 [0, 0, 0]),
        "hdr_and_rows_trailing.csv": ("Time_s,Pos_X_mm,Pos_Y_mm,Probe,\n0.0,1,2,0,\n0.1,3,4,9,\n0.2,5,6,0,\n", [0, 9, 0]),
        "semicolon_rows_trailing.csv": ("Time_s;Pos_X_mm;Pos_Y_mm;Probe\n0.0;1;2;0;\n0.1;3;4;0;\n0.2;5;6;0;\n", [0, 0, 0]),
        "one_short_row.csv": ("Time_s,Pos_X_mm,Pos_Y_mm,Probe\n0.0,1,2,0\n0.1,3\n0.2,5,6,0\n", [0, 0, 0]),
    }
    for fname, (text, probe) in cases.items():
        try:
            c = la.read_trace_log(write(os.path.join(TMP, fname), text))
        except Exception as e:
            check(f"fewer fields than the header ({fname}): read", False, f"{type(e).__name__}: {e}")
            continue
        check(f"fewer fields than the header ({fname}): t / X / Y / Probe, no unnamed axis",
              np.allclose(c.t, [0.0, 0.1, 0.2]) and np.allclose(c.data['X'], [1, 3, 5])
              and np.allclose(c.data['Y'], [2, 4, 6]) and c.probe is not None and np.allclose(c.probe, probe)
              and c.axes() == ['X', 'Y'], f"t={c.t} X={c.data.get('X')} Y={c.data.get('Y')} probe={c.probe} {c.axes()}")


def test_sample_nearest_table_csv():
    t = np.array([0.0, 1.0, 2.0, 3.0, 6.0, 7.0])
    c = curve(t, {'X': t * 2.0}, meta={'gaps': [(3.2, 5.9)]})
    s = la.sample(c, 'X', [-1.0, 0.5, 3.0, 4.0, 5.95, 6.5, 8.0])
    check("sample: NaN outside span and inside the gap",
          math.isnan(s[0]) and near(s[1], 1.0, 1e-12) and near(s[2], 6.0, 1e-12) and math.isnan(s[3])
          and math.isnan(s[4]) and near(s[5], 13.0, 1e-12) and math.isnan(s[6]), str(s))
    s2 = la.sample(c, 'X', [4.0], gaps_as_nan=False)
    check("sample gaps_as_nan=False interpolates across the gap", near(s2[0], 8.0, 1e-12))
    c.time_offset = 10.0
    s3 = la.sample(c, 'X', [14.0, 10.5])
    check("sample: gaps follow time_offset", math.isnan(s3[0]) and near(s3[1], 1.0, 1e-12))
    c_open = curve(t, {'X': t}, meta={'gaps': [(3.1, None)]})
    s4 = la.sample(c_open, 'X', [4.0, 6.5])
    check("open gap (no reconnection line): NaN until the next sample", math.isnan(s4[0]) and near(s4[1], 6.5, 1e-12))

    check("nearest_point", la.nearest_point(c, 'X', 11.4) == (11.0, 2.0) and la.nearest_point(c, 'X', 100) == (17.0, 14.0)
          and la.nearest_point(c, 'X', -5) == (10.0, 0.0))
    c.value_offsets['X'] = 1.0
    check("nearest_point applies value offset", la.nearest_point(c, 'X', 12.2) == (12.0, 5.0))

    a = curve(np.arange(0.0, 2.0001, 0.5), {'X': np.arange(5.0)}, name="same")
    b = curve(np.arange(1.0, 4.0001, 0.5), {'X': np.arange(7.0) * 10}, name="same")
    nox = curve(np.arange(0.0, 4.0, 0.5), {'SI': np.zeros(8)}, name="other")
    df = la.aligned_table([a, b, nox], 'X', dt=0.5)
    check("aligned_table columns (unique names)", list(df.columns) == ['Time_s', 'same', 'same (2)', 'other'],
          str(list(df.columns)))
    check("aligned_table grid = union of spans", np.allclose(df['Time_s'], np.arange(0.0, 4.0001, 0.5)))
    check("aligned_table NaN where a curve has no data",
          np.isnan(df['same (2)'].iloc[0]) and np.isnan(df['same'].iloc[-1]) and df['other'].isna().all()
          and near(df['same'].iloc[2], 2.0, 1e-12) and near(df['same (2)'].iloc[2], 0.0, 1e-12))
    df2 = la.aligned_table([a, b], 'X', roi=(1.0, 2.0), dt=0.5)
    check("aligned_table ROI", np.allclose(df2['Time_s'], [1.0, 1.5, 2.0]))
    b.time_offset = -1.0
    df3 = la.aligned_table([a, b], 'X', dt=0.5)
    check("aligned_table applies offsets", near(df3['same (2)'].iloc[0], 0.0, 1e-12))

    path = os.path.join(TMP, "out", "rows.csv")
    la.write_rows_csv(path, ['Name', 'Value', 'Count', 'Missing'],
                      [['a', 0.1 + 0.2, 3, float('nan')], {'Name': "b'e", 'Value': np.float64(2.5), 'Count': np.int64(4)},
                       ['x;y', -1.5e-7, -2, None]],
                      notes=['Time base: as recorded; waits shown', 'Format: semicolons, "decimal" comma'])
    with open(path, newline='', encoding='utf-8') as f:
        text = f.read()
    lines = text.splitlines()
    check("write_rows_csv: v2 style - '#' notes without ';' first, then ';' columns and a decimal comma",
          lines[0] == '# Time base: as recorded, waits shown' and lines[1] == "# Format: semicolons, 'decimal' comma"
          and lines[2] == 'Name;Value;Count;Missing' and lines[3] == 'a;0,3;3;' and lines[4] == "b'e;2,5;4;"
          and lines[5] == '"x;y";-1,5e-07;-2;', str(lines))
    notes, hdr, rows = la.read_rows_csv(path)
    check("read_rows_csv round trip (decimal comma back to '.', quoted ';' kept)",
          notes == ['Time base: as recorded, waits shown', "Format: semicolons, 'decimal' comma"]
          and hdr == ['Name', 'Value', 'Count', 'Missing'] and rows[0] == ['a', '0.3', '3', '']
          and rows[2] == ['x;y', '-1.5e-07', '-2', ''], f"{notes} {hdr} {rows}")


NEW_HEADER = """# Computer Time: 2026-11-06 13:11:39.207
# G-code: 0:/gcodes/job_platform.gcode
# Device: Motion Platform
# Axes (Duet order): X,Y,Z,A,B,C,D,'a,'c,'e,'f
# Positions: actual (Duet machinePosition; refreshed at most every 200 ms)
# Probe: 0 none | 1-1499 detector | 2000 Release button
# Recording from: 0.040 s of the run
Time_s,Pos_LAT_mm,Pos_SI_mm,Pos_AP_mm,Pos_Roll_deg,Pos_Pitch_deg,Pos_Yaw_deg,Pos_A_mm,Pos_B_mm,Pos_C_mm,Pos_D_mm,Pos_'e_mm,Pos_'f_mm,Pos_'a_mm,Pos_'c_mm,Probe
"""


def _row(t, si, probe=0):
    return (f"{t:.4f},50.000,{si:.3f},35.000,0.000,0.000,0.000,35.000,35.000,35.000,35.000,"
            f"50.000,50.000,{si:.3f},{si:.3f},{probe}\n")


def test_read_synthetic_files():
    body = "".join(_row(0.04 + 0.08 * i, 25.0 + 0.01 * i) for i in range(19))       # up to 1.48 s
    body += "# Gap: connection lost at 1.581 s\n# Gap end: reconnected at 2.713 s\n"
    body += "".join(_row(2.75 + 0.08 * i, 26.0, 2000 if i == 3 else 1000) for i in range(100))
    body += "# End: job finished at 10.661 s\n"
    p = write(os.path.join(TMP, "log_new.csv"), NEW_HEADER + body)
    c = la.read_trace_log(p)
    m = c.meta
    check("newest log: name / kind / format", c.name == "log_new" and c.kind == "log" and m['format'] == 'trace-header')
    check("newest log: header meta", m['computer_time'] == '2026-11-06 13:11:39.207'
          and m['gcode'] == '0:/gcodes/job_platform.gcode' and m['device'] == 'Motion Platform'
          and m['axes'] == ['X', 'Y', 'Z', 'A', 'B', 'C', 'D', "'a", "'c", "'e", "'f"]
          and near(m['recording_from'], 0.04, 1e-12), str({k: m[k] for k in ('computer_time', 'gcode', 'device')}))
    check("newest log: gap and end", m['gaps'] == [(1.581, 2.713)] and m['end'] == ('job finished', 10.661),
          f"{m['gaps']} {m['end']}")
    check("newest log: axes", c.axes() == la.PLATFORM_DOF + la.PLATFORM_RAW)
    check("newest log: probe and release marker", c.probe is not None and c.probe.max() == 2000
          and len(m['release_times']) == 1 and near(m['release_times'][0], 2.75 + 0.24, 1e-9))
    s = la.sample(c, 'SI', [1.0, 2.0, 3.0])
    check("newest log: sample NaN inside the connection gap", np.isfinite(s[0]) and math.isnan(s[1]) and np.isfinite(s[2]))
    check("newest log: all_zero_axes Roll/Pitch/Yaw", m['all_zero_axes'] == ['Roll', 'Pitch', 'Yaw'])

    ph = ("# Computer Time: 2026-11-07 09:00:00.000\n# G-code: none\n# Device: Lung Phantom\n# Axes (Duet order): X,Y,Z\n"
          "# Positions: actual\n# Probe: 0 none | 1-1499 detector | 2000 Release button\n# Recording from: 0.000 s of the run\n"
          "Time_s,Pos_X_mm,Pos_Y_mm,Pos_Z_mm,Probe\n"
          + "".join(f"{0.1 * i:.4f},{i:.3f},{2 * i:.3f},0.000,0\n" for i in range(20))
          + "# Gap: connection lost at 2.000 s\n")
    c2 = la.read_trace_log(write(os.path.join(TMP, "log_phantom.csv"), ph))
    check("phantom log: device, gcode none -> None, X/Y/Z", c2.meta['device'] == 'Lung Phantom'
          and c2.meta['gcode'] is None and c2.axes() == ['X', 'Y', 'Z'])
    check("phantom log: open gap at the end", c2.meta['gaps'] == [(2.0, None)] and c2.meta['end'] is None)

    unsorted = "Time_s,Pos_X_mm,Probe\n0.2,2,0\n0.1,1,0\n0.1,9,0\nabc,5,0\n0.3,,0\n0.4,4,0\n"
    c3 = la.read_trace_log(write(os.path.join(TMP, "unsorted.txt"), unsorted))
    check("unsorted / duplicate / invalid rows: strictly increasing, first duplicate kept, gaps filled",
          np.allclose(c3.t, [0.1, 0.2, 0.3, 0.4]) and np.allclose(c3.data['X'], [1, 2, 3, 4]), f"{c3.t} {c3.data['X']}")
    check("plain format, device from columns", c3.meta['format'] == 'plain' and c3.meta['device'] == 'Lung Phantom'
          and c3.meta['device_source'] == 'columns')

    bad = {
        "empty.csv": "",
        "comments_only.csv": "# Computer Time: 2026-11-06 10:00:00\n",
        "no_time.csv": "a,b,c\n1,2,3\n4,5,6\n",
        "header_only.csv": "Time_s,Pos_X_mm,Probe\n",
        "one_row.csv": "Time_s,Pos_X_mm,Probe\n0.0,1,0\n",
        "no_axes.csv": "Time_s,Probe\n0.0,0\n0.1,0\n",
    }
    for fname, text in bad.items():
        try:
            la.read_trace_log(write(os.path.join(TMP, fname), text))
            check(f"unusable file {fname} raises ValueError", False)
        except ValueError as e:
            check(f"unusable file {fname} raises ValueError", True, str(e)[:70])
    try:
        la.read_trace_log(os.path.join(TMP, "missing.csv"))
        check("missing file raises ValueError", False)
    except ValueError:
        check("missing file raises ValueError", True)


# ---------------------------------------------------------------------------
# Real files
# ---------------------------------------------------------------------------
HOME = os.path.expanduser("~")
DUMMY = os.path.join(ROOT, "log_06112026_12_34_12_case_02_DUMMY_wait.csv")
REAL_SETS = {
    'newest (C:\\TRACE)': [os.path.join(ROOT, "log_06112026_12_34_12_case_02.csv")],
    '5 Nov Pos+Cmd': sorted(glob.glob(os.path.join(HOME, "Desktop", "Check_log", "log_14_*.csv"))),
    '6 Nov broken X/Y/Z': sorted(glob.glob(os.path.join(HOME, "Desktop", "log_10_*.csv"))),
    '3 Nov': sorted(glob.glob(os.path.join(HOME, "Documents", "TriggeredImaging0311", "log_*.csv"))),
    'old text': [os.path.join(ROOT, "scratch", "sample_log.txt")],
}


def test_real_logs():
    for label, files in REAL_SETS.items():
        files = [f for f in files if os.path.isfile(f)]
        if not files:
            print(f"SKIP: {label}: no sample files on this machine")
            continue
        curves, errors = [], []
        for f in files:
            try:
                curves.append(la.read_trace_log(f))
            except Exception as e:
                errors.append(f"{os.path.basename(f)}: {e}")
        check(f"{label}: {len(files)} file(s) read without error", not errors, "; ".join(errors)[:200])
        check(f"{label}: strictly increasing time, n / median_dt", all(
            np.all(np.diff(c.t) > 0) and c.meta['n'] == c.t.size and c.meta['median_dt'] > 0 for c in curves))
        if label.startswith('newest'):
            c = curves[0]
            m = c.meta
            check("case_02: header meta (5-line variant, no G-code line)",
                  m['format'] == 'trace-header' and m['device'] == 'Motion Platform' and m['gcode'] is None
                  and m['computer_time'] == '2026-11-06 12:34:12.404' and m['axes'][:3] == ['X', 'Y', 'Z'],
                  str({k: m[k] for k in ('format', 'device', 'gcode', 'computer_time')}))
            check("case_02: end line, no gaps", m['end'] == ('job finished', 93.831) and m['gaps'] == [])
            check("case_02: platform DOF + raw axes, SI 25 -> 28.5",
                  c.axes() == la.PLATFORM_DOF + la.PLATFORM_RAW and near(c.data['SI'][0], 25.001, 1e-9)
                  and near(c.data['SI'][-1], 28.5, 1e-9) and c.meta['n'] == 1214)
            check("case_02: Release button marker", len(m['release_times']) == 1 and near(m['release_times'][0], 11.849, 0.001))
        elif label.startswith('5 Nov'):
            check("5 Nov: pos+cmd format, Cmd axes, device from columns", all(
                c.meta['format'] == 'pos+cmd' and c.has('Cmd LAT') and c.has('Cmd Yaw') and c.has('Roll')
                and c.meta['device'] == 'Motion Platform' and c.meta['computer_time'].startswith('2026-11-05')
                for c in curves))
            check("5 Nov: Cmd axes ordered after the Pos axes", curves[0].axes()[:6] == la.PLATFORM_DOF
                  and curves[0].axes()[6:] == [la.CMD_PREFIX + a for a in la.PLATFORM_DOF], str(curves[0].axes()))
            slow = [c for c in curves if c.name == 'log_14_01_00_']
            if slow:
                mv = [m_ for m_ in la.detect_movements(slow[0], 'AP') if 70.0 < m_['t_start'] < 90.0]
                check("5 Nov log_14_01_00_: the ~0.05 mm/s AP ramp 35.0 -> 35.5 is ONE movement (was 5 pieces)",
                      len(mv) == 1 and near(mv[0]['v_start'], 35.0, 0.002) and near(mv[0]['v_stop'], 35.5, 0.002)
                      and mv[0]['complete'], str([(round(x['t_start'], 2), round(x['t_stop'], 2)) for x in mv]))
        elif label.startswith('6 Nov'):
            check("6 Nov: all_zero_axes = X/Y/Z and Cmd X/Y/Z, with a warning", all(
                set(c.meta['all_zero_axes']) >= {'X', 'Y', 'Z', 'Cmd X', 'Cmd Y', 'Cmd Z'} and c.meta['warnings']
                for c in curves), str(curves[0].meta['all_zero_axes']))
        elif label.startswith('3 Nov'):
            check("3 Nov: computer-time format, DOF axes, detector probe", all(
                c.meta['format'] == 'computer-time' and c.axes() == la.PLATFORM_DOF and c.probe is not None
                for c in curves) and any(np.any((c.probe >= 1) & (c.probe < 1500)) for c in curves))
        elif label.startswith('old'):
            c = curves[0]
            check("old text log: plain, X/Y/Z, 2 duplicate times dropped",
                  c.meta['format'] == 'plain' and c.axes() == ['X', 'Y', 'Z'] and c.meta['n'] == 2827,
                  f"n={c.meta['n']}")


def test_real_reference():
    path = os.path.join(ROOT, "curve2.gcode")
    if not os.path.isfile(path):
        print("SKIP: curve2.gcode not found")
        return
    ref = la.read_reference_gcode(path)
    m = ref.meta
    check("curve2: reference meta", ref.kind == 'reference' and ref.name == 'curve2' and m['gcode'] == 'curve2.gcode'
          and m['device'] == 'Motion Platform' and m['n_rows'] == 33)
    check("curve2: pause sensor_wait at 9.99 s", len(m['pauses']) == 1 and m['pauses'][0][0] == 'sensor_wait'
          and near(m['pauses'][0][1], 9.99, 1e-6), str(m['pauses']))
    check("curve2: total 89.65 s", near(m['total_time'], 89.65, 0.01) and near(ref.t[-1], 89.65, 0.01))
    check("curve2: actuators and DOF present", all(ref.has(a) for a in la.PLATFORM_DOF + la.PLATFORM_RAW))
    check("curve2: SI 25 -> 28.5", near(ref.data['SI'][0], 25.0, 1e-9) and near(ref.data['SI'][-1], 28.5, 1e-9))

    try:
        from fcn_monitor.fcn_duet import _platform_dof
    except Exception as e:
        check("import fcn_monitor.fcn_duet._platform_dof", False, str(e))
        return
    raw = la.PLATFORM_RAW
    worst = 0.0
    for i in (0, 5, 12, len(ref.t) - 1):
        axes = {a: float(ref.data[a][i]) for a in raw}
        axes['W'] = 0.0
        dof = _platform_dof(axes, 100.0, 100.0)
        worst = max(worst, max(abs(dof[k] - ref.data[k][i]) for k in la.PLATFORM_DOF))
    check("curve2: DOF = logger formulas (_platform_dof) on several rows", worst < 1e-9, f"max err {worst:.2e}")
    tilt = ("G90\nG1 A30 B32 C35 D37 'e50 'f52 'a20 'c22 F600\nG1 A40 B30 C36 D31 'e40 'f44 'a30 'c25\n"
            "G4 P500\n")
    for lat_dim, si_dim in ((100.0, 100.0), (180.0, 240.0)):
        rt = la.read_reference_gcode(tilt, lat_dim=lat_dim, si_dim=si_dim)
        worst = 0.0
        for i in range(len(rt.t)):
            axes = {a: float(rt.data[a][i]) for a in raw}
            axes['W'] = 0.0
            dof = _platform_dof(axes, lat_dim, si_dim)
            worst = max(worst, max(abs(dof[k] - rt.data[k][i]) for k in la.PLATFORM_DOF))
        check(f"tilted platform G-code: Roll/Pitch/LAT/SI/AP = _platform_dof (dims {lat_dim:g}x{si_dim:g})",
              worst < 1e-9 and np.any(np.abs(rt.data['Roll']) > 0.1) and np.any(np.abs(rt.data['Pitch']) > 0.1),
              f"max err {worst:.2e}")

    r5 = la.with_pause_durations(ref, [5.0])
    later = ref.t > 9.99 + 1e-6
    check("curve2: with_pause_durations([5]) shifts later times by 5 s",
          np.allclose(la.sample(r5, 'SI', ref.t[later] + 5.0), ref.data['SI'][later])
          and near(r5.t[-1], ref.t[-1] + 5.0, 1e-9) and near(r5.meta['total_time'], m['total_time'] + 5.0, 1e-9))
    check("curve2: times before the pause unchanged", np.allclose(la.sample(r5, 'SI', [0.0, 5.0, 9.99]),
                                                                  la.sample(ref, 'SI', [0.0, 5.0, 9.99])))
    check("curve2: holds during the pause", np.allclose(la.sample(r5, 'SI', [10.0, 12.0, 14.99]), 25.0))

    log_path = os.path.join(ROOT, "log_06112026_12_34_12_case_02.csv")
    if not os.path.isfile(log_path):
        print("SKIP: case_02 log not found")
        return
    log = la.read_trace_log(log_path)
    pr = la.pair_pause_waits(ref, log)
    check("curve2 vs case_02 (v1, no -1000 / wait notes): shown as recorded, the pause stays 0 s",
          len(pr) == 1 and pr[0]['length'] == 0.0 and pr[0]['kind'] == 'none' and not log.meta['waits'], str(pr))
    check("curve2: reference all_zero_axes = Roll / Pitch / Yaw", m['all_zero_axes'] == ['Roll', 'Pitch', 'Yaw'],
          str(m['all_zero_axes']))

    # the dummy v2 copy of case_02 with one logged wait (received 10.110 s, Release at 11.849 s)
    if not os.path.isfile(DUMMY):
        print("SKIP: dummy wait log not found")
        return
    dl = la.read_trace_log(DUMMY)
    pd_ = la.pair_pause_waits(ref, dl)
    w = dl.meta['waits'][0]
    check("curve2 vs the dummy: the sensor_wait pause gets the logged length end - received (1.739 s), Release button",
          len(pd_) == 1 and pd_[0]['kind'] == 'marked' and near(pd_[0]['length'], 1.739, 0.0015)
          and pd_[0]['length'] == w['length'] and pd_[0]['ended_by'] == 'Release button', str(pd_[0]['length']))
    show = la.with_pause_durations(ref, [pd_[0]['length']])
    cut = la.remove_waits(dl)
    s_show = la.estimate_shift(show, dl, 'SI', max_lag=5.0)
    s_cut = la.estimate_shift(ref, cut, 'SI', max_lag=5.0)
    print(f"INFO: curve2 vs dummy on SI: Show shift {s_show['shift']:+.3f} s (corr {s_show['corr']:.5f}), "
          f"Remove shift {s_cut['shift']:+.3f} s (corr {s_cut['corr']:.5f})")
    check("dummy: Show and Remove need the same remaining shift (the Release-ended wait is logged at the press, "
          "the Duet resumed ~0.9 s later: -0.6 .. -1.1 s), corr > 0.999",
          -1.1 <= s_show['shift'] <= -0.6 and abs(s_show['shift'] - s_cut['shift']) < 0.02
          and s_show['corr'] > 0.999 and s_cut['corr'] > 0.999, f"{s_show['shift']:+.4f} / {s_cut['shift']:+.4f}")
    dl.time_offset = s_show['shift']
    r = la.compare(show, dl, 'SI')
    check("dummy aligned in Show mode: rms < 0.05 mm", r['rms'] < 0.05, f"rms {r['rms']:.4f}")
    dl.time_offset = 0.0
    mv_ref = la.detect_movements(show, 'SI')
    mv_log = la.detect_movements(dl, 'SI')
    print("INFO: movements ref  : " + ", ".join(f"{m_['t_start']:.2f}-{m_['t_stop']:.2f}s" for m_ in mv_ref))
    print("INFO: movements log  : " + ", ".join(f"{m_['t_start']:.2f}-{m_['t_stop']:.2f}s" for m_ in mv_log))
    check("curve2 vs the dummy: same number of SI movements (3)", len(mv_ref) == len(mv_log) == 3)


def test_performance():
    n = 100_000
    t = np.arange(n) * 0.08
    v = 25.0 + 2.0 * np.sin(2 * np.pi * hold(t) / 4.0)
    path = os.path.join(TMP, "big_log.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write(NEW_HEADER)
        for ti, vi in zip(t, v):
            f.write(_row(ti, vi))
    t0 = time.perf_counter()
    c = la.read_trace_log(path)
    t_read = time.perf_counter() - t0
    t0 = time.perf_counter()
    mv = la.detect_movements(c, 'SI')
    p = la.find_peaks_curve(c, 'SI')
    sh = la.estimate_shift(c, c, 'SI', roi=(1000.0, 2000.0))
    cm = la.compare(c, c, 'SI')
    e = la.ensemble([c, c], 'SI')
    dp = la.dominant_period(c, 'SI', roi=(0.0, 1000.0))
    t_ana = time.perf_counter() - t0
    print(f"INFO: 100k-row log ({c.t[-1]:.0f} s): read {t_read:.2f} s, analyses {t_ana:.2f} s "
          f"({len(mv)} movements, {p['t'].size} peaks)")
    check("100k rows: read + analyses fast (< 15 s)", t_read + t_ana < 15.0, f"{t_read + t_ana:.2f} s")
    check("100k rows: results sane", c.meta['n'] == n and abs(sh['shift']) < 0.02 and cm['rms'] == 0.0
          and near(dp['period'], 4.0, 0.05) and p['t'].size > 1900)


# ---------------------------------------------------------------------------
# Round 3: periodic motion behind a gap, slow ramps at a short settle_time, open gap while moving,
# noisy logs, aligned export read back
# ---------------------------------------------------------------------------
def _gap_log(fn, t_end, seed, gaps=(), row_dt=(0.05, 0.14), smooth=False, noise=0.0, axis='Z', refresh=0.2):
    """Like _seeded_log (rows 50-140 ms by default): rows strictly inside each gap (a, b) (b None:
    connection never back) removed and meta['gaps'] set; optional uniform noise +-noise added
    before the rounding to 0.001."""
    rng = np.random.default_rng(seed)
    n = int(math.ceil(t_end / row_dt[0])) + 5
    ts = np.concatenate(([0.0], np.cumsum(rng.uniform(row_dt[0], row_dt[1], n))))
    ts = ts[ts <= t_end]
    ph = rng.uniform(0.0, refresh)
    tq = ts if smooth else np.maximum(np.floor((ts - ph) / refresh) * refresh + ph, 0.0)
    v = fn(tq)
    if noise:
        v = v + rng.uniform(-noise, noise, v.size)
    keep = np.ones(ts.size, dtype=bool)
    for a, b in gaps:
        keep &= ~((ts > a) & (ts < (np.inf if b is None else b)))
    return curve(ts[keep], {axis: np.round(v, 3)[keep]}, name="log",
                 meta={'gaps': [(float(a), None if b is None else float(b)) for a, b in gaps]})


def _dtc(t, v):
    cps = np.concatenate(([0], np.flatnonzero(np.diff(v) != 0.0) + 1))
    return float(np.median(np.diff(t[cps])))


def test_floor_leaves_long_settle_unchanged():
    # Round 4: the staircase hold floor must not change detect_movements when settle_time >= floor
    # (approach hold stays 0.8 * settle), and the refresh interval behind the floor is measured on
    # value changes while moving, so sparse logs with long rests do not raise it to the 0.5 s cap.
    # Case of the round-3 verifier: two 0.2 mm moves at 0.5 mm/s, 130-150 ms rows, 0.6 s stop.
    tk = [0.0, 5.0, 5.4, 6.0, 6.4, 11.4]
    vk = [0.0, 0.0, 0.2, 0.2, 0.4, 0.4]
    fn = lambda x: np.interp(x, tk, vk)  # noqa: E731
    logs = [_gap_log(fn, tk[-1], sd, row_dt=(0.13, 0.15)) for sd in range(40)]
    orig = la._hold_floor
    try:
        la._hold_floor = lambda t, dtc, settle: 0.0
        base = [[(m['t_start'], m['t_stop']) for m in la.detect_movements(c, 'Z', settle_time=0.5)] for c in logs]
    finally:
        la._hold_floor = orig
    new = [[(m['t_start'], m['t_stop']) for m in la.detect_movements(c, 'Z', settle_time=0.5)] for c in logs]
    check("default settle 0.5 s: the staircase hold floor changes nothing (sparse 130-150 ms rows, 0.6 s stop, "
          "40 seeds)", new == base, f"{sum(a != b for a, b in zip(new, base))} of 40 differ")
    c = logs[0]
    t, v = c.times(), c.values('Z')
    cps = np.concatenate(([0], np.flatnonzero(np.diff(v) != 0.0) + 1))
    dcp = np.diff(t[cps])
    check("refresh interval of a log with long rests is taken from the value changes while moving (< 1 s)",
          float(np.median(dcp[dcp < la._DTC_MOVING_MAX])) < 0.45 < float(np.max(dcp)),
          f"moving median {np.median(dcp[dcp < 1.0]):.3f}, all median {np.median(dcp):.3f}")


def test_short_settle_slow_ramps():
    # B: with settle_time < ~0.43 s staircase holds (a value is shown for up to ~0.34 s with
    # 50-140 ms rows) passed for stops: the net change of a window holding one staircase value is 0,
    # and the approach-step rule only asked for a hold of 0.8 * settle_time.  0.05 mm/s at settle
    # 0.3 was one movement in 6 of 40 seeds (round 1: 40/40), 0.1 mm/s at settle 0.2 in 0/40
    # (round 1: 5/40); both rules now use the staircase hold floor (_hold_floor)
    for spd in (0.05, 0.1):
        T1 = 5.0 + 1.0 / spd
        fn = (lambda t, T1=T1: np.interp(t, [0.0, 5.0, T1, T1 + 5.0], [0.0, 0.0, 1.0, 1.0]))
        for settle in (0.3, 0.2):
            for row_dt in ((0.05, 0.14), (0.075, 0.085)):
                res = [la.detect_movements(_gap_log(fn, T1 + 5.0, sd, row_dt=row_dt), 'Z', threshold=0.02,
                                           settle_time=settle) for sd in range(12)]
                one = sum(len(m) == 1 for m in res)
                times = all(len(m) != 1 or (-0.1 <= m[0]['t_start'] - 5.0 <= 0.3 and -0.15 <= m[0]['t_stop'] - T1 <= 0.35)
                            for m in res)
                check(f"{spd} mm/s ramp (200 ms staircase, rows {row_dt[0]}-{row_dt[1]} s), settle {settle} s: one "
                      "movement in every seed (no worse than round 1), start / stop at the ramp ends",
                      one == len(res) and times, f"{one}/{len(res)}, counts {sorted(set(len(m) for m in res))}")
    # the floor: refresh interval + row spacing, 0 below ~the refresh interval, at most 0.5 s
    lg = _gap_log(lambda t: np.interp(t, [0.0, 5.0, 25.0, 30.0], [0.0, 0.0, 1.0, 1.0]), 30.0, 0)
    t, v = lg.t, lg.data['Z']
    dtc = _dtc(t, v)
    fl = la._hold_floor(t, dtc, 0.3)
    check("staircase hold floor ~0.34 s for 50-140 ms rows (dtc ~0.2 s), 0 for settle 0.1 s (< refresh: the "
          "staircase steps themselves are asked for), capped at 0.5 s",
          0.3 <= fl <= 0.36 and near(dtc, 0.2, 0.02) and la._hold_floor(t, dtc, 0.1) == 0.0
          and la._hold_floor(t, 10.0, 20.0) == 0.5, f"floor {fl:.3f}, dtc {dtc:.3f}")
    # settle 0.5: the floor (< 0.8 * 0.5 s) changes nothing, so the stop / restart merge rates stay
    same = True
    for sd in range(20):
        for speed, hold_s in ((1.0, 0.6), (0.35, 0.7), (3.0, 0.6)):
            T1 = 2.0 + 2.0 / speed
            T3 = T1 + hold_s + 2.0 / speed
            f2 = (lambda t, T1=T1, T3=T3, h=hold_s: np.interp(t, [0, 2.0, T1, T1 + h, T3, T3 + 4], [0, 0, 2, 2, 4, 4]))
            g = _gap_log(f2, T3 + 4.0, sd)
            tt, vv = g.t, g.data['Z']
            f5 = la._hold_floor(tt, _dtc(tt, vv), 0.5)
            same &= f5 < 0.4 and all(np.array_equal(la._settled_mask(tt, vv, thr, 0.5, floor=f5),
                                                    la._settled_mask(tt, vv, thr, 0.5)) for thr in (0.02, 0.05))
    check("settle 0.5 s, 50-140 ms rows: the floor is < 0.4 s and the settled samples are those without it (stop "
          "+ restart merge rates unchanged)", same)
    log_path = os.path.join(ROOT, "log_06112026_12_34_12_case_02.csv")
    if os.path.isfile(log_path):
        c = la.read_trace_log(log_path)
        counts = {st: len(la.detect_movements(c, 'SI', settle_time=st)) for st in (0.2, 0.3, 0.5)}
        check("case_02 SI: 3 movements at settle 0.2 / 0.3 / 0.5 s (round 2: 11 at 0.2, round 1: 7)",
              all(n == 3 for n in counts.values()), str(counts))


def test_open_gap_while_moving():
    # C: connection lost for good during a movement (1 mm/s 3 -> 6 s, lost at 4.5 s): in_gap /
    # stop_in_gap were usually False (t_stop is the first sample of the last value, before the gap)
    fn = lambda t: np.interp(t, [0.0, 3.0, 6.0, 15.0], [0.0, 0.0, 3.0, 3.0])
    flags = []
    for sd in range(8):
        mv = la.detect_movements(_gap_log(fn, 15.0, sd, gaps=((4.5, None),)), 'Z')
        m = mv[-1] if mv else {}
        flags.append((m.get('in_gap'), m.get('stop_in_gap'), m.get('complete')))
    check("open gap while moving: the last movement is in_gap and stop_in_gap and not complete (8 seeds)",
          all(f == (True, True, False) for f in flags), str(flags[:3]))
    m = la.detect_movements(_gap_log(fn, 4.5, 0), 'Z')[-1]
    check("data ending while moving, no gap: incomplete but not in a gap",
          not m['complete'] and not m['in_gap'] and not m['stop_in_gap'])
    mv = la.detect_movements(_gap_log(fn, 15.0, 0, gaps=((10.0, None),)), 'Z')
    check("open gap after the movement stopped: complete, not in the gap",
          len(mv) == 1 and mv[0]['complete'] and not mv[0]['in_gap'] and not mv[0]['stop_in_gap'])
    mv = la.detect_movements(_gap_log(fn, 15.0, 0, gaps=((5.5, None),)), 'Z', roi=(0.0, 4.5))
    check("ROI ending before an open gap: the gap is outside the movement's data, not flagged",
          len(mv) == 1 and not mv[0]['complete'] and not mv[0]['in_gap'] and not mv[0]['stop_in_gap'])


def test_noisy_stops():
    # D: on noisy data the 0.003 'at the rest value' tolerance put t_stop at the first settled
    # sample (up to 11.97 s for a move ending at 11 s, +-0.02 noise, threshold 0.1) and t_start early
    fn = lambda t: np.interp(t, [0.0, 10.0, 11.0, 25.0], [0.0, 0.0, 1.0, 1.0])
    for nz, thr in ((0.02, 0.1), (0.02, 0.05), (0.01, 0.05), (0.005, 0.02)):
        res = [la.detect_movements(_gap_log(fn, 25.0, sd, smooth=sm, noise=nz), 'Z', threshold=thr)
               for sd in range(8) for sm in (True, False)]
        st = [m[0]['t_start'] - 10.0 for m in res if m]
        sp = [m[0]['t_stop'] - 11.0 for m in res if m]
        check(f"noise +-{nz}, threshold {thr}: one movement, t_start within -0.2..+0.3 s of 10 s and t_stop within "
              "-0.15..+0.35 s of 11 s (16 logs)",
              all(len(m) == 1 for m in res) and min(st) >= -0.2 and max(st) <= 0.3 and min(sp) >= -0.15
              and max(sp) <= 0.35, f"start {min(st):+.2f}..{max(st):+.2f} stop {min(sp):+.2f}..{max(sp):+.2f}")
    # the settled test keeps its noise-free cap: a noisy slow ramp is still one movement
    f2 = lambda t: np.interp(t, [0.0, 5.0, 15.0, 25.0], [0.0, 0.0, 1.0, 1.0])
    res = [la.detect_movements(_gap_log(f2, 25.0, sd, smooth=sm, noise=0.01), 'Z', threshold=0.05)
           for sd in range(8) for sm in (True, False)]
    check("0.1 mm/s ramp with +-0.01 noise, threshold 0.05: one movement (16 logs)",
          all(len(m) == 1 for m in res), str(sorted(set(len(m) for m in res))))
    # noise estimate: ~3 x the step noise for noisy rest data, 0 for a noise-free staircase
    g = _gap_log(fn, 25.0, 0, smooth=True, noise=0.02)
    e = la._windows(g.t, g.data['Z'], 0.5)[1]
    nz_noisy = la._noise_rest_tol(g.data['Z'], la._settled_mask(g.t, g.data['Z'], 0.1, 0.5), e, 0.1)
    clean = []
    for sd in range(4):
        for f in (fn, f2):
            c = _gap_log(f, 25.0, sd)
            ec = la._windows(c.t, c.data['Z'], 0.5)[1]
            clean.append(la._noise_rest_tol(c.data['Z'], la._settled_mask(c.t, c.data['Z'], 0.02, 0.5), ec, 0.02))
    check("rest noise tolerance: ~0.03 for +-0.02 noise, 0 for noise-free staircase logs (they keep min(thr / 4, "
          "0.003))", 0.02 <= nz_noisy <= 0.05 and all(x == 0.0 for x in clean), f"{nz_noisy:.4f}, clean {max(clean)}")
    log_path = os.path.join(ROOT, "log_06112026_12_34_12_case_02.csv")
    if os.path.isfile(log_path):
        c = la.read_trace_log(log_path)
        tt, vv = c.t, c.data['SI']
        ec = la._windows(tt, vv, 0.5)[1]
        check("case_02 SI (firmware log): no noise detected",
              all(la._noise_rest_tol(vv, la._settled_mask(tt, vv, thr, 0.5), ec, thr) == 0.0 for thr in (0.02, 0.05, 0.1)))


def test_aligned_export_read_back():
    # E: an aligned export of the tab ('time [s]', '<axis>: <curve> [<unit>]') read back kept the
    # whole header as the axis name, so axis_unit gave 'mm' for its '[deg]' columns
    def rd(name, text):
        return la.read_trace_log(write(os.path.join(TMP, name), text))

    c = rd("al_roll.csv", "time [s],Roll: case_02 [deg]\n0.0,1\n0.1,2\n0.2,3\n")
    check("aligned export, one column: axis 'Roll' (lines up with the other curves), unit deg, format / device",
          c.axes() == ['Roll'] and c.meta['units'] == {'Roll': 'deg'} and la.axis_unit('Roll', c) == 'deg'
          and c.meta['format'] == 'aligned-export' and c.meta['device'] == 'Motion Platform'
          and c.meta['export_axes'] == {'Roll': 'Roll'} and c.meta['source_columns'] == {'Roll': 'Roll: case_02 [deg]'}
          and list(c.data['Roll']) == [1.0, 2.0, 3.0], f"{c.axes()} {c.meta['units']}")
    c = rd("al_two_roll.csv", "time [s],Roll: case_02 [deg],Roll: curve2 [deg],Roll: case_02 (2) [deg]\n"
                              "0.0,1,2,3\n0.1,2,3,4\n0.2,3,4,5\n")
    names = ['Roll case_02', 'Roll curve2', 'Roll case_02 (2)']
    check("aligned export, several curves on one axis: '<axis> <curve>' axes, unit deg from the file (the name "
          "alone would say mm)",
          sorted(c.data) == sorted(names) and all(la.axis_unit(a, c) == 'deg' for a in names)
          and all(la.axis_unit(a, c.meta) == 'deg' for a in names) and la.axis_unit('Roll case_02') == 'mm'
          and c.meta['device'] == 'Motion Platform' and list(c.data['Roll curve2']) == [2.0, 3.0, 4.0],
          f"{sorted(c.data)} {c.meta['units']}")
    c = rd("al_mixed.csv", "time [s],Roll: a [deg],SI: a [mm],Cmd Yaw: a [deg],Cmd Yaw: b [deg]\n"
                           "0.0,1,2,3,4\n0.1,2,3,4,5\n0.2,3,4,5,6\n")
    check("aligned export, one column per axis plus two 'Cmd Yaw': 'Roll', 'SI', 'Cmd Yaw a', 'Cmd Yaw b' with "
          "their units", sorted(c.data) == ['Cmd Yaw a', 'Cmd Yaw b', 'Roll', 'SI']
          and [la.axis_unit(a, c) for a in ('Roll', 'SI', 'Cmd Yaw a', 'Cmd Yaw b')] == ['deg', 'mm', 'deg', 'deg'],
          f"{sorted(c.data)}")
    c = rd("al_clash.csv", "time [s],SI: x [mm],SI: y [mm],SI x\n0.0,1,2,3\n0.1,2,3,4\n0.2,3,4,5\n")
    check("aligned export: names stay unique ('SI x (2)' next to a plain 'SI x' column)",
          sorted(c.data) == ['SI x', 'SI x (2)', 'SI y'] and list(c.data['SI x']) == [3.0, 4.0, 5.0]
          and list(c.data['SI x (2)']) == [1.0, 2.0, 3.0] and 'SI x' not in c.meta['units'], f"{sorted(c.data)}")
    c = rd("al_empty_col.csv", "time [s],Roll: x [deg],Roll: y [deg]\n0.0,1,\n0.1,2,\n0.2,3,\n")
    check("aligned export: a column without values is left out, the other one is 'Roll'",
          c.axes() == ['Roll'] and c.meta['units'] == {'Roll': 'deg'}, f"{c.axes()}")
    c = rd("al_not_export.csv", "Time_s,Pos_Roll_deg,Roll: x [deg]\n0.0,1,2\n0.1,2,3\n0.2,3,4\n")
    check("a 'Time_s' log is not an aligned export: its columns and units are as before",
          sorted(c.data) == ['Roll', 'Roll: x [deg]'] and c.meta['units'] == {} and c.meta['format'] == 'plain'
          and 'export_axes' not in c.meta)
    # round trip through aligned_table with the tab's header
    t = np.arange(0.0, 4.0, 0.05)
    a = curve(t, {'Roll': np.sin(t)}, name="a")
    b = curve(t, {'Roll': np.cos(t)}, name="b")
    df = la.aligned_table([a, b], 'Roll', dt=0.1)
    df.columns = ['time [s]', 'Roll: a [deg]', 'Roll: b [deg]']
    p = os.path.join(TMP, "al_round_trip.csv")
    df.to_csv(p, index=False, float_format='%.6f')
    c = la.read_trace_log(p)
    check("aligned export round trip: 'Roll a' / 'Roll b' with their values, unit deg",
          sorted(c.data) == ['Roll a', 'Roll b'] and np.allclose(c.data['Roll a'], df['Roll: a [deg]'], atol=1e-6)
          and np.allclose(c.data['Roll b'], df['Roll: b [deg]'], atol=1e-6) and la.axis_unit('Roll b', c) == 'deg')
    # the tab's v2-style export ('#' notes, ';' columns, decimal comma) reads back the same
    p2 = os.path.join(TMP, "al_round_trip_v2.csv")
    with open(p2, 'w', newline='', encoding='utf-8') as f:
        f.write(la.comment_line("TRACE Log files aligned export: Roll; 2 curve(s)") + '\r\n')
        f.write(la.comment_line("Time base: logged sensor waits removed from a, b") + '\r\n')
        df.to_csv(f, index=False, float_format='%.6f', sep=la.CSV_SEP, decimal=la.CSV_DECIMAL, lineterminator='\r\n')
    raw = open(p2, encoding='utf-8').read().splitlines()
    c2v = la.read_trace_log(p2)
    check("aligned export, v2 style (notes, ';', decimal comma): same curve as the ',' style, notes kept as header",
          raw[0] == '# TRACE Log files aligned export: Roll, 2 curve(s)' and ';' in raw[2] and ',' in raw[3]
          and sorted(c2v.data) == ['Roll a', 'Roll b'] and np.array_equal(c2v.t, c.t)
          and all(np.array_equal(c2v.data[k], c.data[k]) for k in c.data) and c2v.meta['decimal'] == ','
          and c2v.meta['format'] == 'aligned-export' and len(c2v.meta['header']) == 2, f"{raw[:4]}")
    # meta['units'] is always there ({} by default) and not shared between curves
    c1 = curve([0.0, 1.0], {'Q': [0.0, 1.0]})
    c2 = curve([0.0, 1.0], {'Q': [0.0, 1.0]})
    c1.meta['units']['Q'] = 'rad'
    check("meta['units'] defaults to {} per curve; axis_unit(axis, curve) uses it, axis_unit(axis) by name",
          c2.meta['units'] == {} and la._META_DEFAULTS['units'] == {} and la.axis_unit('Q', c1) == 'rad'
          and la.axis_unit('Q', c2) == 'mm' and la.axis_unit('Roll', c2) == 'deg' and la.axis_unit('Q') == 'mm'
          and la.axis_unit('Roll', None) == 'deg')


# ---------------------------------------------------------------------------
# Round 5: movement_stats (movements edited by hand) and value crossings (points edited by value)
# ---------------------------------------------------------------------------
_MV_NUM_KEYS = ('t_start', 't_stop', 'duration', 'v_start', 'v_stop', 'delta', 'peak_speed')
_MV_FLAG_KEYS = ('complete', 'in_gap', 'start_in_gap', 'stop_in_gap')


def _real_curves():
    files = [os.path.join(ROOT, "log_06112026_12_34_12_case_02.csv")]
    files += sorted(glob.glob(os.path.join(HOME, "Desktop", "Check_log", "log_14_*.csv")))
    files += sorted(glob.glob(os.path.join(HOME, "Documents", "TriggeredImaging0311", "log_*.csv")))
    out = [la.read_trace_log(f) for f in files if os.path.isfile(f)]
    g = os.path.join(ROOT, "curve2.gcode")
    if os.path.isfile(g):
        out.append(la.read_reference_gcode(g))
    return out


def test_movement_stats():
    # keys and the plain numbers of a span given by hand
    t = np.arange(0.0, 10.0, 0.05)
    v = np.interp(t, [0, 2, 4, 10], [1.0, 1.0, 5.0, 5.0])
    c = curve(t, {'X': v}, kind='reference')
    s = la.movement_stats(c, 'X', 2.0, 4.0)
    m = la.detect_movements(c, 'X')
    check("movement_stats: the keys of a detect_movements dict", m and set(s) == set(m[0]), str(sorted(s)))
    check("movement_stats: given span, values of the nearest samples, delta, peak speed (2 units/s)",
          s['t_start'] == 2.0 and s['t_stop'] == 4.0 and near(s['duration'], 2.0, 1e-12) and near(s['v_start'], 1.0, 1e-9)
          and near(s['v_stop'], 5.0, 1e-9) and near(s['delta'], 4.0, 1e-9) and near(s['peak_speed'], 2.0, 1e-6)
          and s['complete'] is True and s['in_gap'] is False and s['start_in_gap'] is False
          and s['stop_in_gap'] is False, str(s))
    s2 = la.movement_stats(c, 'X', 2.01, 3.0)
    check("movement_stats: v_start / v_stop from the nearest samples (2.0 / 3.0 s), times as given",
          s2['t_start'] == 2.01 and near(s2['v_start'], 1.0, 1e-9) and near(s2['v_stop'], 3.0, 1e-9)
          and near(s2['duration'], 0.99, 1e-12), str(s2))
    # offsets: displayed time base and values
    c.time_offset, c.value_offsets = 100.0, {'X': 0.5}
    so = la.movement_stats(c, 'X', 102.0, 104.0)
    check("movement_stats: displayed time base and value offset",
          near(so['v_start'], 1.5, 1e-9) and near(so['v_stop'], 5.5, 1e-9) and near(so['delta'], 4.0, 1e-9)
          and near(so['peak_speed'], 2.0, 1e-6) and so['complete'], str(so))
    c.time_offset, c.value_offsets = 0.0, {}
    # outside the data: incomplete
    check("movement_stats: t_stop beyond the data -> complete False", la.movement_stats(c, 'X', 5.0, 12.0)['complete']
          is False and la.movement_stats(c, 'X', -1.0, 3.0)['complete'] is False)
    # errors
    for args, what in (((4.0, 2.0), "t_stop before t_start"), ((float('nan'), 2.0), "NaN"),
                       ((1.0, float('inf')), "inf")):
        try:
            la.movement_stats(c, 'X', *args)
            ok = False
        except ValueError:
            ok = True
        check(f"movement_stats: {what} -> ValueError", ok)
    try:
        la.movement_stats(c, 'X', 1.0, 2.0, roi=(50.0, 60.0))
        ok = False
    except ValueError:
        ok = True
    check("movement_stats: ROI without samples -> ValueError", ok)
    try:
        la.movement_stats(c, 'Q', 1.0, 2.0)
        ok = False
    except ValueError:
        ok = True
    check("movement_stats: unknown axis -> ValueError", ok)

    # staircase log (200 ms refresh): peak speed de-staircased exactly as detect_movements
    ts = staircase_times(30.0, dt_log=0.08, jitter=0.01)
    truth = np.interp(hold(ts), [0, 5, 7, 15, 18, 30], [10.0, 10.0, 12.0, 12.0, 9.0, 9.0])
    lg = curve(ts, {'SI': np.round(truth, 3)})
    mv = la.detect_movements(lg, 'SI')
    ok = len(mv) == 2
    for m_ in mv:
        s_ = la.movement_stats(lg, 'SI', m_['t_start'], m_['t_stop'])
        ok = ok and all(s_[k] == m_[k] for k in _MV_NUM_KEYS + _MV_FLAG_KEYS)
    check("staircase log: movement_stats at the detected start / stop = detect_movements (all keys, exact)", ok,
          str([(round(m_['t_start'], 3), round(m_['t_stop'], 3), round(m_['peak_speed'], 4)) for m_ in mv]))
    s_wide = la.movement_stats(lg, 'SI', 4.0, 8.0)
    check("staircase log: a wider hand-set span keeps the de-staircased peak speed (~1 unit/s, not inflated)",
          0.7 <= s_wide['peak_speed'] <= 1.6 and near(s_wide['delta'], 2.0, 0.01), f"{s_wide['peak_speed']:.3f}")

    # gaps: the same flags as detect_movements (gap_spans)
    rows = [f"{t_:.3f},0.000,0" for t_ in np.arange(0.01, 3.98, 0.08)]
    rows += ["# Gap: connection lost at 4.000 s", "# Gap end: reconnected at 15.000 s"]
    rows += [f"{t_:.3f},5.000,0" for t_ in np.arange(15.01, 18.0, 0.08)]
    rows += [f"{t_:.3f},{min(8.0, 5.0 + 3.0 * (t_ - 18.0)):.3f},0" for t_ in np.arange(18.01, 24.0, 0.08)]
    gc = la.read_trace_log(write(os.path.join(TMP, "ms_gap.csv"), GAP_LOG_HEAD + "\n".join(rows) + "\n"))
    gm = la.detect_movements(gc, 'X')
    same = len(gm) == 2 and all(all(la.movement_stats(gc, 'X', m_['t_start'], m_['t_stop'])[k] == m_[k]
                                    for k in _MV_NUM_KEYS + _MV_FLAG_KEYS) for m_ in gm)
    check("gap log: movement_stats = detect_movements for the movement across the gap and the clean one", same,
          str([(m_['t_start'], m_['t_stop'], m_['in_gap'], m_['start_in_gap'], m_['stop_in_gap']) for m_ in gm]))
    sg = la.movement_stats(gc, 'X', 3.0, 16.0)
    check("gap log: a span over the gap -> in_gap, complete False (start / stop outside it)",
          sg['in_gap'] and not sg['complete'] and not sg['start_in_gap'] and not sg['stop_in_gap'], str(sg))
    sg2 = la.movement_stats(gc, 'X', 3.93, 15.01)
    check("gap log: start / stop on the samples bounding the gap -> start_in_gap and stop_in_gap",
          sg2['start_in_gap'] and sg2['stop_in_gap'] and sg2['in_gap'] and not sg2['complete'], str(sg2))
    sc = la.movement_stats(gc, 'X', 18.0, 20.0)
    check("gap log: a span after the gap is clean", sc['complete'] and not sc['in_gap'], str(sc))
    gc.time_offset = 50.0
    check("gap flags follow time_offset", la.movement_stats(gc, 'X', 53.0, 66.0)['in_gap']
          and not la.movement_stats(gc, 'X', 3.0, 16.0)['in_gap'])


def test_movement_stats_real():
    curves = _real_curves()
    if not curves:
        print("SKIP: no real logs")
        return
    n = n_roi = n_flags_roi = 0
    bad, bad_roi = [], []
    t0 = time.perf_counter()
    for c in curves:
        for ax in c.axes():
            for m in la.detect_movements(c, ax):
                s = la.movement_stats(c, ax, m['t_start'], m['t_stop'])
                n += 1
                diff = [k for k in _MV_NUM_KEYS + _MV_FLAG_KEYS if s[k] != m[k]]
                if diff:
                    bad.append(f"{c.name} {ax} {m['t_start']:.3f}: {diff}")
            for m in la.detect_movements(c, ax, roi=(20.0, 60.0)):
                s = la.movement_stats(c, ax, m['t_start'], m['t_stop'], roi=(20.0, 60.0))
                n_roi += 1
                diff = [k for k in _MV_NUM_KEYS if s[k] != m[k]]
                if m['complete'] or m['in_gap']:           # settled: the flags too
                    n_flags_roi += 1
                    diff += [k for k in _MV_FLAG_KEYS if s[k] != m[k]]
                if diff:
                    bad_roi.append(f"{c.name} {ax} {m['t_start']:.3f}: {diff}")
    dt = time.perf_counter() - t0
    check(f"real logs + curve2 ({len(curves)} curves, every axis): movement_stats at each detected movement's "
          f"start / stop reproduces detect_movements exactly ({n} movements: numbers and flags)",
          n >= 50 and not bad, "; ".join(bad[:4]) + f" ({dt:.2f} s)")
    check(f"real logs with ROI 20-60 s: same numbers with the same roi ({n_roi} movements; flags of the "
          f"{n_flags_roi} settled ones)", n_roi >= 20 and not bad_roi, "; ".join(bad_roi[:4]))
    case = [c for c in curves if 'case_02' in c.name]
    if case:
        c = case[0]
        mv = la.detect_movements(c, 'SI')
        check("case_02: 3 SI movements reproduced", len(mv) == 3 and all(
            la.movement_stats(c, 'SI', m['t_start'], m['t_stop'])['peak_speed'] == m['peak_speed'] for m in mv))
        # merge_gap > 0: same span numbers, the peak speed is at most the largest of the parts
        mm = la.detect_movements(c, 'SI', merge_gap=20.0)
        ok = bool(mm)
        for m in mm:
            s = la.movement_stats(c, 'SI', m['t_start'], m['t_stop'])
            ok = ok and all(s[k] == m[k] for k in ('t_start', 't_stop', 'duration', 'v_start', 'v_stop', 'delta')) \
                and s['peak_speed'] <= m['peak_speed'] + 1e-12
        check("case_02 merged movements (merge_gap 20 s): same span numbers, peak speed <= the parts' largest", ok,
              str([(round(m['t_start'], 2), round(m['t_stop'], 2)) for m in mm]))


def test_value_crossings():
    t = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    v = np.array([0.0, 2.0, 2.0, 0.0, 1.0])
    c = curve(t, {'X': v})
    tc = la.value_crossings(c, 'X', 1.0)
    check("value_crossings: linear crossings between samples and a sample at the value",
          np.allclose(tc, [0.5, 2.5, 4.0]), str(tc))
    check("value_crossings: a flat run at the value gives its samples", np.allclose(la.value_crossings(c, 'X', 2.0),
                                                                                    [1.0, 2.0]))
    check("nearest_crossing: the crossing nearest to t", la.nearest_crossing(c, 'X', 1.0, 2.2) == 2.5
          and la.nearest_crossing(c, 'X', 1.0, 0.0) == 0.5 and la.nearest_crossing(c, 'X', 1.0, 3.9) == 4.0)
    check("nearest_crossing: never reached -> None", la.nearest_crossing(c, 'X', 5.0, 1.0) is None
          and la.nearest_crossing(c, 'X', -0.1, 1.0) is None and la.nearest_crossing(c, 'X', float('nan'), 1.0) is None)
    c.time_offset, c.value_offsets = 10.0, {'X': 1.0}
    check("value crossings in the displayed time base, offsets applied",
          np.allclose(la.value_crossings(c, 'X', 2.0), [10.5, 12.5, 14.0]))
    c.time_offset, c.value_offsets = 0.0, {}
    # a crossing only across a connection gap is not one (the data is unknown there)
    g = curve([0.0, 1.0, 5.0, 6.0], {'X': [0.0, 0.0, 4.0, 4.0]}, meta={'gaps': [(1.5, 4.5)]})
    check("value_crossings: none across a connection gap; gaps=False takes the line",
          la.nearest_crossing(g, 'X', 2.0, 3.0) is None and near(la.nearest_crossing(g, 'X', 2.0, 3.0, gaps=False), 3.0,
                                                                1e-12))
    big = curve(np.arange(100_000) * 0.08, {'X': np.sin(np.arange(100_000) * 0.01)})
    t0 = time.perf_counter()
    r = la.nearest_crossing(big, 'X', 0.5, 4000.0)
    check("nearest_crossing on 100k rows: fast (< 50 ms) and on the curve",
          r is not None and abs(np.interp(r, big.t, big.data['X']) - 0.5) < 1e-9 and time.perf_counter() - t0 < 0.05,
          f"{1000 * (time.perf_counter() - t0):.1f} ms")


# ---------------------------------------------------------------------------
# Logged sensor waits (log format v2): reader, removal from the time axis (CutMap), pairing with the
# G-code pauses.  Nothing is estimated: a log without -1000 rows / wait notes is shown as recorded.
# ---------------------------------------------------------------------------
V2_HEADER_PHANTOM = [
    "# Computer Time: 2026-11-07 10:00:00.000",
    "# G-code: 0:/gcodes/wait3.gcode",
    "# Device: Lung Phantom",
    "# Axes (Duet order): X,Y,Z",
    "# Positions: actual (Duet machinePosition, refreshed at most every 200 ms, CAN expansion-board axes about "
    "every 100 ms)",
    "# Probe: 0 none | 1-1499 detector | 2000 Release button | -1000 waiting for sensor (sensor_wait)",
    "# Wait timing: start = when TRACE received the Duet message (read as soon as a position sample shows a new "
    "message, else every 0,5-1 s), so the real start is earlier, normally by up to ~0,5 s. End = first position "
    "sample with the detector above 500 or Release pressed (within one sample, ~0,08 s), otherwise as stated at "
    "the end of the file",
    "# Run notes: the times of each sensor wait (with the window in which the Duet sent its message), connection "
    "gaps and the run end are listed at the end of the file",
    "# Recording from: 0,000 s of the run",
    "# Format: columns separated by semicolons, decimal comma",
]
V2_COLUMNS_PHANTOM = "Time_s;Pos_X_mm;Pos_Y_mm;Pos_Z_mm;Probe"

# 3 sensor_wait pauses (at 2.0, 6.5 and 10.5 s of G-code time) with motion between them
WAIT3_GCODE = """G90
G1 X0 Y0 Z0 F600
G4 P2000
M98 P"0:macros/sensor_wait.g"
G1 X10 F600
G4 P1000
G1 X4 F360
G4 P1500
M98 P"0:macros/sensor_wait.g"
G1 X12 F480
G4 P1000
G1 X2 F600
G4 P1000
M98 P"0:macros/sensor_wait.g"
G1 X8 F360
G4 P2000
G1 X0 F480
G4 P2000
"""

# waits of the three synthetic logs: (kind, real length in s) per sensor_wait pause of WAIT3_GCODE
WAIT_PLANS = {
    'log_wait_A': [('marked', 3.0), ('not_marked', 0.05), ('marked', 2.0)],
    'log_wait_B': [('marked', 4.5), ('not_marked', 0.04), ('marked', 1.2)],
    'log_wait_C': [('marked', 2.2), ('not_marked', 0.06), ('marked', 5.0)],
}


def dc(x, nd=3):
    """A number as the v2 logger writes it: nd decimals, decimal comma."""
    return f"{float(x):.{nd}f}".replace('.', ',')


def long_wait_gcode(t_total=8000.0):
    """WAIT3_GCODE followed by back-and-forth moves (4 s per cycle) up to about t_total s (100k-row logs)."""
    cycles = max(1, int((t_total - 17.0) / 4.0))
    return WAIT3_GCODE + "G1 X10 F600\nG4 P1000\nG1 X0 F600\nG4 P1000\n" * cycles


def write_wait_log(path, ref, plan, seed=0, row_dt=(0.075, 0.085), refresh=0.2, noise=0.001, gap=None,
                   read_fail=None, t_extra=1.0, notes=True, end_line=True, lags=(0.01, 0.07)):
    """
    Write a v2 log (as the logger writes it: 10-line header, ';' columns, decimal comma, only data rows
    between the column line and the notes, the notes in time order after the last row, '# End' last)
    of a run of the G-code reference `ref` whose sensor_wait pause i really lasted plan[i] = ('marked',
    W) or ('not_marked', W) s.  Rows every row_dt s (uniform, 4 decimals); positions = the run
    (with_pause_durations) at the 200 ms machinePosition refresh (random phase), plus uniform noise
    +-noise (1 um), rounded to 0.001.  The Duet sends 'Waiting for sensor signal...' at the real start s;
    TRACE gets it lag later (uniform in lags; sent window: the 0.5 s since the previous read).  A marked
    wait: rows from the first one at / after 'received' up to the trigger row (the first row at / after
    the real end, detector 1000) carry -1000.  A 'not_marked' wait ends (detector) before TRACE gets
    the message: no row is marked.  gap = (a, b): rows strictly inside removed, Gap / Gap end notes;
    read_fail = time of a failed Duet message read.  notes=False: TRACE stopped before writing the
    notes (rows only).  Returns dict(path, truth, ts, probe, waits=[dict(kind, start, end_true,
    received, sent_from, end_row, prev_row, rows)], end).
    """
    rng = np.random.default_rng(seed)
    pauses = list(ref.meta['pauses_gcode'])
    sw = [i for i, (lb, _) in enumerate(pauses) if lb == 'sensor_wait']
    W = [0.0] * len(pauses)
    for i, (_, w) in zip(sw, plan):
        W[i] = float(w)
    truth = la.with_pause_durations(ref, W)
    t_end = float(truth.t[-1]) + t_extra
    n = int(t_end / row_dt[0]) + 5
    ts = 0.05 + np.concatenate(([0.0], np.cumsum(rng.uniform(row_dt[0], row_dt[1], n))))
    ts = np.unique(np.round(ts[ts <= t_end], 4))
    ph = rng.uniform(0.0, refresh)
    tq = np.clip(np.floor((ts - ph) / refresh) * refresh + ph, truth.t[0], truth.t[-1])
    vals = {}
    for a in ('X', 'Y', 'Z'):
        v = la.sample(truth, a, tq, gaps_as_nan=False) if truth.has(a) else np.zeros(ts.size)
        vals[a] = np.round(v + rng.uniform(-noise, noise, ts.size), 3)
    probe = np.zeros(ts.size, dtype=int)
    info = []
    for i, (kind, w) in zip(sw, plan):
        s = float(truth.meta['pauses'][i][1])
        e_true = s + float(w)
        lag = float(rng.uniform(*lags))
        d = {'kind': kind, 'start': s, 'end_true': e_true}
        if kind == 'marked':
            rec = s + lag
            j0 = int(np.searchsorted(ts, rec, side='left'))
            j1 = int(np.searchsorted(ts, e_true, side='left'))
            probe[j0:j1] = -1000
            probe[j1:j1 + 4] = 1000
            d.update(received=rec, end_row=float(ts[j1]), prev_row=float(ts[j1 - 1]))
        else:
            rec = e_true + lag
            j1 = int(np.searchsorted(ts, e_true, side='left'))
            probe[j1:j1 + 4] = 1000
            d.update(received=rec, end_row=None, prev_row=None, detector_at=float(ts[j1]))
        d['sent_from'] = d['received'] - 0.5
        info.append(d)
    keep = np.ones(ts.size, dtype=bool)
    if gap is not None:
        keep &= ~((ts > gap[0]) & (ts < gap[1]))
    ts, probe = ts[keep], probe[keep]
    vals = {a: v[keep] for a, v in vals.items()}
    for d in info:
        if d['kind'] == 'marked':
            d['rows'] = int(np.count_nonzero((ts >= d['received']) & (ts < d['end_row']) & (probe == -1000)))
    lines = list(V2_HEADER_PHANTOM) + [V2_COLUMNS_PHANTOM]
    lines += [f"{dc(t, 4)};{dc(x)};{dc(y)};{dc(z)};{p}" for t, x, y, z, p in
              zip(ts, vals['X'], vals['Y'], vals['Z'], probe)]
    ev = []
    for d in info:
        if d['kind'] == 'marked':
            ev.append((d['received'], f'# Wait start: "Waiting for sensor signal..." received at {dc(d["received"])} s '
                                      f'(Duet sent it between {dc(d["sent_from"])} and {dc(d["received"])} s)'))
            ev.append((d['end_row'], f"# Wait end: detector 1000 at {dc(d['end_row'])} s (exact to one sample, "
                                     f"previous sample at {dc(d['prev_row'])} s)"))
        else:
            ev.append((d['received'], f'# Wait not marked: "Waiting for sensor signal..." received at '
                                      f'{dc(d["received"])} s (Duet sent it between {dc(d["sent_from"])} and '
                                      f'{dc(d["received"])} s), the wait may already have ended: detector 1000 at '
                                      f'{dc(d["detector_at"])} s'))
    if read_fail is not None:
        ev.append((read_fail, f"# Message read failed at {dc(read_fail)} s: Duet messages sent between "
                              f"{dc(read_fail - 0.6)} and {dc(read_fail - 0.1)} s may be lost (a sensor wait start "
                              f"or end may be missing)"))
    if gap is not None:
        ev.append((gap[0], f"# Gap: connection lost at {dc(gap[0])} s"))
        ev.append((gap[1], f"# Gap end: reconnected at {dc(gap[1])} s"))
    end = float(ts[-1]) + 0.4
    if notes:
        lines += [txt for _, txt in sorted(ev, key=lambda x: x[0])]
        if end_line:
            lines.append(f"# End: job finished at {dc(end)} s")
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write("\r\n".join(lines) + "\r\n")
    return {'path': path, 'truth': truth, 'ts': ts, 'probe': probe, 'waits': info, 'end': end}


def _wait_logs(tmp=None, ref=None):
    """The three synthetic v2 logs of WAIT_PLANS (gap and failed read in each): {name: write_wait_log dict}."""
    tmp = tmp or TMP
    ref = ref if ref is not None else la.read_reference_gcode(WAIT3_GCODE, name="wait3")
    out = {}
    for k, (name, plan) in enumerate(WAIT_PLANS.items()):
        s2 = 2.0 + plan[0][1] + 4.5 + plan[1][1]              # real start of pause 2
        out[name] = write_wait_log(os.path.join(tmp, name + ".csv"), ref, plan, seed=100 + k,
                                   gap=(s2 + 1.25, s2 + 1.85), read_fail=1.0 + 0.3 * k)
    return out


def test_v2_reader_dummy():
    if not os.path.isfile(DUMMY):
        print("SKIP: dummy wait log not found")
        return
    c = la.read_trace_log(DUMMY)
    m = c.meta
    check("dummy v2: ';' columns, decimal comma, 10-line header, same rows as the v1 case_02",
          m['separator'] == ';' and m['decimal'] == ',' and len(m['header']) == 10 and m['n'] == 1214
          and m['format'] == 'trace-header' and m['gcode'] == '0:/gcodes/curve2.gcode', f"{m['separator']} {m['decimal']}")
    v1 = la.read_trace_log(os.path.join(ROOT, "log_06112026_12_34_12_case_02.csv"))
    check("dummy v2 = v1 case_02 in t and positions (only the text format and the -1000 rows differ)",
          np.array_equal(c.t, v1.t) and all(np.array_equal(c.data[k], v1.data[k]) for k in v1.data)
          and list(c.data) == list(v1.data))
    check("dummy v2: header numbers with a decimal comma ('# Recording from: 0,000 s')", m['recording_from'] == 0.0)
    check("dummy v2: End line read after the notes", m['end'] == ('job finished', 93.831), str(m['end']))
    w = m['waits'][0] if m['waits'] else {}
    check("dummy v2: one logged wait: received 10.110, Duet sent it 9.640 .. 10.110, Release button at 11.849 "
          "(exact to one sample), 21 rows with -1000, from the notes",
          len(m['waits']) == 1 and w['received'] == 10.11 and w['sent_from'] == 9.64 and w['end'] == 11.849
          and w['end_by'] == 'Release button' and w['end_exact'] is True and w['rows'] == 21
          and w['source'] == 'notes' and w['message'] == 'Waiting for sensor signal...'
          and w['end_note'] == 'exact to one sample, previous sample at 11,777 s', str(w))
    check("dummy v2: the wait's rows end at the trigger row 11.8491 (note 11.849, 3 decimals): length 1.7391 s",
          w.get('cut') == (10.11, 11.8491) and near(w.get('length'), 1.7391, 1e-9), str(w.get('cut')))
    check("dummy v2: the probe array keeps -1000 (21 rows), release onset at 11.8491, no warnings",
          int(np.sum(c.probe == -1000)) == 21 and np.allclose(m['release_times'], [11.8491]) and not m['warnings'])
    check("dummy v2: no wait not marked, no failed read, no gap", not m['waits_not_marked']
          and not m['message_read_failures'] and m['gaps'] == [])


def test_v2_synthetic_logs():
    ref = la.read_reference_gcode(WAIT3_GCODE, name="wait3")
    check("WAIT3 G-code: 3 sensor_wait pauses at 2.0, 6.5, 10.5 s",
          [p[0] for p in ref.meta['pauses']] == ['sensor_wait'] * 3
          and np.allclose([p[1] for p in ref.meta['pauses']], [2.0, 6.5, 10.5]), str(ref.meta['pauses']))
    logs = _wait_logs(ref=ref)
    for name, info in logs.items():
        c = la.read_trace_log(info['path'])
        m = c.meta
        mk = [d for d in info['waits'] if d['kind'] == 'marked']
        nm = [d for d in info['waits'] if d['kind'] == 'not_marked']
        ok_w = len(m['waits']) == len(mk) and all(
            abs(w['received'] - d['received']) <= 5e-4 and abs(w['sent_from'] - d['sent_from']) <= 5e-4
            and abs(w['end'] - d['end_row']) <= 5e-4 and w['cut'][1] == d['end_row'] and w['rows'] == d['rows']
            and w['end_exact'] and w['end_by'] == 'detector 1000' and w['source'] == 'notes'
            and near(w['length'], d['end_row'] - w['received'], 1e-12)
            for w, d in zip(m['waits'], mk))
        check(f"{name}: marked waits read (received / sent window / end within the 3-decimal rounding, the "
              f"end snapped to the trigger row, -1000 row counts)", ok_w,
              str([(round(w['received'], 4), round(w['end'], 4), w['rows']) for w in m['waits']]))
        check(f"{name}: wait not marked read (received, Duet send window, reason)",
              len(m['waits_not_marked']) == len(nm) == 1
              and abs(m['waits_not_marked'][0]['received'] - nm[0]['received']) <= 5e-4
              and abs(m['waits_not_marked'][0]['sent_from'] - nm[0]['sent_from']) <= 5e-4
              and m['waits_not_marked'][0]['reason'].startswith('detector 1000 at'), str(m['waits_not_marked']))
        f = m['message_read_failures']
        check(f"{name}: failed message read and the gap read (decimal commas)",
              len(f) == 1 and f[0]['sent_from'] is not None and f[0]['sent_to'] is not None
              and len(m['gaps']) == 1 and m['gaps'][0][1] is not None and m['end'][0] == 'job finished'
              and not m['warnings'], f"{f} {m['gaps']} {m['warnings']}")
    # rows-only (TRACE stopped before writing the notes): the waits come from the -1000 rows
    info = write_wait_log(os.path.join(TMP, "log_wait_crash.csv"), ref, WAIT_PLANS['log_wait_A'], seed=7,
                          notes=False)
    c = la.read_trace_log(info['path'])
    mk = [d for d in info['waits'] if d['kind'] == 'marked']
    rows_ok = len(c.meta['waits']) == 2 and all(
        w['source'] == 'rows' and w['sent_from'] is None and w['end_by'] == 'unknown (no notes at the end of the file)'
        and w['received'] == float(info['ts'][np.argmax(info['ts'] >= d['received'])]) and w['end'] == d['end_row']
        and w['rows'] == d['rows'] for w, d in zip(c.meta['waits'], mk))
    check("crash (no notes): 2 waits from the -1000 rows: start = first -1000 row, end = first row after the last, "
          "sent window unknown, a warning says so", rows_ok and any('only in the Probe -1000 rows' in x
                                                                     for x in c.meta['warnings']),
          str([(w['received'], w['end'], w['rows']) for w in c.meta['waits']]) + str(c.meta['warnings']))
    cut = la.remove_waits(c)
    check("crash: Remove leaves no -1000 row", not np.any(cut.probe == -1000))


def _v1_wait_text():
    """A v1 log (',' columns, '.' decimals) with the sensor-wait notes BETWEEN the rows, as the current
    v1 logger writes them (';' inside the notes), detector 300 rows inside the wait and a Release hold."""
    hdr = ("# Computer Time: 2026-11-07 09:00:00.000\n# G-code: 0:/gcodes/x.gcode\n# Device: Lung Phantom\n"
           "# Axes (Duet order): X,Y,Z\n# Positions: actual\n# Probe: 0 none | 1-1499 detector | 2000 Release button "
           "| -1000 waiting for sensor (sensor_wait)\n# Wait timing: start = when TRACE received the Duet message; "
           "end = first sample\n# Recording from: -0.250 s of the run\nTime_s,Pos_X_mm,Pos_Y_mm,Pos_Z_mm,Probe\n")
    rows = []
    for k in range(60):
        t = 0.1 * k
        p = 0
        if abs(t - 2.0) < 1e-9:
            rows.append('# Wait start: "Waiting for sensor signal..." received at 1.950 s (Duet sent it before 1.950 s '
                        '(no earlier read))')
        if 2.0 <= t < 3.5:
            p = 300 if abs(t - 2.5) < 1e-9 else -1000
        if abs(t - 3.5) < 1e-9:
            rows.append('# Wait end: Duet message "Continuing at 9 s; ok" at 3.500 s (its end message was not received; '
                        'the wait ended before this message was sent)')
            p = 0
        rows.append(f"{t:.4f},{1.0 if t < 3.8 else 2.0:.3f},0.000,0.000,{p}")
    rows.append("# End: cancelled at 6.000 s")
    return hdr + "\n".join(rows) + "\n"


def test_v2_notes_and_malformed():
    c = la.read_trace_log(write(os.path.join(TMP, "log_v1_waits.csv"), _v1_wait_text()))
    w = c.meta['waits'][0] if c.meta['waits'] else {}
    check("v1 log with wait notes between the rows: separator ',', decimal '.', negative 'Recording from'",
          c.meta['separator'] == ',' and c.meta['decimal'] == '.' and c.meta['recording_from'] == -0.25)
    check("v1 wait: 'before T s (no earlier read)' -> sent_from None; a quoted Duet message with ' at 9 s' and ';' "
          "does not hide the end time 3.500; how in the parentheses; detector 300 inside the wait kept",
          len(c.meta['waits']) == 1 and w['received'] == 1.95 and w['sent_from'] is None and w['end'] == 3.5
          and w['end_by'] == 'Duet message "Continuing at 9 s; ok"' and w['end_exact'] is False
          and w['end_note'].startswith('its end message was not received; the wait')
          and w['rows'] == 14 and c.probe[25] == 300 and not c.meta['warnings'], str(w))
    cut = la.remove_waits(c)
    check("v1 wait removed: rows 1.95 .. 3.5 cut (the 300 row too), 3.5 lands on the cut point 1.95",
          not np.any(cut.probe == -1000) and not np.any(cut.probe == 300) and np.any(np.isclose(cut.t, 1.95))
          and cut.meta['cuts'][0][0] == 1.95 and near(cut.meta['cuts'][0][1], 1.55, 1e-12), str(cut.meta['cuts']))

    # malformed notes: an end without a start, a start without a time, a start without an end, two starts
    rows = "".join(f"{dc(0.1 * k, 4)};{dc(1.0)};0;0;{-1000 if 30 <= k < 40 else 0}\n" for k in range(60))
    bad = ("\n".join(V2_HEADER_PHANTOM) + "\n" + V2_COLUMNS_PHANTOM + "\n" + rows
           + "# Wait end: detector 1000 at 1,000 s (exact to one sample)\n"
           + "# Wait start: received at sometime\n"
           + '# Wait start: "Waiting for sensor signal..." received at 2,980 s (Duet sent it between 2,500 and 2,980 s)\n'
           + "# Message read failed at 4,000 s: Duet messages sent before 4,000 s may be lost\n"
           + "# End: job finished at 6,000 s\n")
    c = la.read_trace_log(write(os.path.join(TMP, "log_v2_malformed.csv"), bad))
    m = c.meta
    w = m['waits'][0] if m['waits'] else {}
    check("malformed notes: an end without a start and a start without a time are ignored with warnings; a start "
          "without an end ends at the first row after its -1000 rows (warning)",
          len(m['waits']) == 1 and w['received'] == 2.98 and near(w['end'], 4.0, 1e-9) and w['rows'] == 10
          and w['end_by'] == 'unknown (no notes at the end of the file)'
          and sum(1 for x in m['warnings'] if 'ignored' in x.lower()) == 2
          and any("no '# Wait end' note" in x for x in m['warnings']), f"{w} {m['warnings']}")
    check("'Message read failed ... sent before T s': sent_from None, sent_to T",
          m['message_read_failures'][0]['sent_from'] is None and m['message_read_failures'][0]['sent_to'] == 4.0
          and m['message_read_failures'][0]['t'] == 4.0)
    # a ';' file with '.' decimals stays a '.' file; -1000 rows outside a noted wait get their own (rows) wait
    mix = ("Time_s;Pos_X_mm;Probe\n" + "".join(f"{0.1 * k:.4f};{k};{-1000 if k in (5, 6, 20) else 0}\n"
                                               for k in range(30))
           + '# Wait start: "W" received at 0.450 s (Duet sent it between 0.100 and 0.450 s)\n'
           + "# Wait end: Release button at 0.700 s (exact to one sample)\n")
    c = la.read_trace_log(write(os.path.join(TMP, "semi_dot.csv"), mix))
    check("';' with '.' decimals read as '.'; a -1000 row outside every noted wait -> an extra wait from the rows "
          "(warning)", c.meta['decimal'] == '.' and np.allclose(c.data['X'], np.arange(30))
          and [w['source'] for w in c.meta['waits']] == ['notes', 'rows'] and near(c.meta['waits'][1]['received'],
                                                                                   2.0, 1e-9)
          and near(c.meta['waits'][1]['end'], 2.1, 1e-9) and c.meta['warnings'], str(c.meta['waits']))
    # the notes anywhere: here in the header, before the column line
    hdr_notes = ("\n".join(V2_HEADER_PHANTOM) + "\n"
                 + '# Wait start: "Waiting for sensor signal..." received at 2,950 s (Duet sent it between 2,450 and '
                   '2,950 s)\n# Wait end: Release button at 4,000 s (exact to one sample, previous sample at 3,900 s)\n'
                 + V2_COLUMNS_PHANTOM + "\n" + rows + "# End: job finished at 6,000 s\n")
    c = la.read_trace_log(write(os.path.join(TMP, "log_v2_notes_in_header.csv"), hdr_notes))
    w = c.meta['waits'][0] if c.meta['waits'] else {}
    check("wait notes placed in the header (before the column line) are read as notes, not as header lines",
          len(c.meta['waits']) == 1 and w['received'] == 2.95 and w['end'] == 4.0 and w['rows'] == 10
          and w['sent_from'] == 2.45 and len(c.meta['header']) == 10 and not c.meta['warnings'], str(w))
    # negative numbers with a decimal comma in the data rows
    neg = "Time_s;Pos_X_mm;Probe\n" + "".join(f"{dc(0.1 * k, 4)};{dc(-1.5 * k)};0\n" for k in range(10))
    c = la.read_trace_log(write(os.path.join(TMP, "neg.csv"), neg))
    check("decimal comma: negative values read", c.meta['decimal'] == ',' and np.allclose(c.data['X'], -1.5 * np.arange(10)),
          str(c.data['X'][:3]))


def test_cut_map():
    waits = [{'cut': (2.0, 5.0)}, {'cut': (10.0, 10.5)}, {'cut': (4.0, 6.0)}, {'cut': (20.0, 20.0)}]
    iv = la.wait_intervals(waits)
    check("wait_intervals: sorted, an overlapping one clipped to the previous end, empty ones left out",
          [(a, b) for a, b, _ in iv] == [(2.0, 5.0), (5.0, 6.0), (10.0, 10.5)], str(iv))
    cm = la.CutMap(iv)
    t = np.array([0.0, 1.999, 2.0, 3.0, 5.0, 5.5, 6.0, 9.0, 10.0, 10.25, 10.5, 12.0])
    f = cm.forward(t)
    check("CutMap.forward: before unchanged, inside -> cut point, the end row exactly on the cut point, after moved",
          np.allclose(f, [0.0, 1.999, 2.0, 2.0, 2.0, 2.0, 2.0, 5.0, 6.0, 6.0, 6.0, 7.5])
          and f[6] == cm.c[0] + 0.0 and cm.forward(10.5) == 6.0 and isinstance(cm.forward(3.0), float), str(f))
    check("CutMap.inside / cuts / total", list(cm.inside(t)) == [False, False, True, True, True, True, False, False,
                                                                  True, True, False, False]
          and [round(x[0], 9) for x in cm.cuts()] == [2.0, 2.0, 6.0] and cm.total == 4.5)
    check("CutMap.inverse: the cut point maps back to the end of the (last) removed interval",
          cm.inverse(2.0) == 6.0 and cm.inverse(6.0) == 10.5 and cm.inverse(1.0) == 1.0 and near(cm.inverse(7.5), 12.0, 1e-12))
    rng = np.random.default_rng(1)
    x = np.sort(rng.uniform(-5.0, 30.0, 200_000))
    out = ~cm.inside(x)
    rt = cm.inverse(cm.forward(x[out]))
    check("CutMap round trip exact outside the removed intervals (200k random times, < 1e-12 s)",
          float(np.max(np.abs(rt - x[out]))) < 1e-12, f"{np.max(np.abs(rt - x[out])):.2e}")
    check("CutMap.forward is non-decreasing", np.all(np.diff(cm.forward(x)) >= 0.0))
    e = la.CutMap([])
    check("empty CutMap = identity", e.forward(3.5) == 3.5 and e.inverse(3.5) == 3.5 and not e.inside(3.5) and not e)

    # remove_waits on a 100k-row log: exact, fast
    n = 100_000
    tt = np.arange(n) * 0.08
    probe = np.zeros(n)
    ws = []
    for k, (a, b) in enumerate(((100.0, 103.0), (4000.0, 4010.0), (7000.0, 7000.5))):
        probe[(tt >= a) & (tt < b)] = -1000
        ws.append({'received': a, 'end': b, 'cut': (a, b), 'index': k})
    c = curve(tt, {'X': np.sin(tt)}, probe=probe, meta={'waits': ws, 'gaps': [(5000.0, 5001.0)], 'end': ('done', 8000.0)})
    c.time_offset, c.value_offsets = 2.5, {'X': 1.0}
    t0 = time.perf_counter()
    cut = la.remove_waits(c)
    el = time.perf_counter() - t0
    kept = cut.meta['cut_index']
    check("remove_waits on 100k rows: < 0.1 s, no -1000 row, the kept rows' values unchanged, times = forward",
          el < 0.1 and not np.any(cut.probe == -1000) and np.array_equal(cut.data['X'], c.data['X'][kept])
          and np.array_equal(cut.t, cut.meta['cut_map'].forward(c.t[kept])) and cut.t.size == n - int(np.sum(probe == -1000)),
          f"{1000 * el:.1f} ms")
    check("remove_waits: offsets copied (display = cut(t) + offset), gaps and End mapped, waits_removed kept",
          cut.time_offset == 2.5 and cut.value_offsets == {'X': 1.0} and cut.meta['waits'] == []
          and near(cut.meta['gaps'][0][0], 5000.0 - 13.0, 1e-9) and near(cut.meta['end'][1], 8000.0 - 13.5, 1e-9)
          and len(cut.meta['waits_removed']) == 3 and near(cut.meta['waits_removed'][1]['cut_at'], 4000.0 - 3.0, 1e-9))
    check("remove_waits: the recorded time of every kept row comes back exactly (inverse)",
          np.array_equal(cut.meta['cut_map'].inverse(cut.t), c.t[kept]) or
          float(np.max(np.abs(cut.meta['cut_map'].inverse(cut.t) - c.t[kept]))) < 1e-9)


def test_pairing_and_alignment():
    ref = la.read_reference_gcode(WAIT3_GCODE, name="wait3")
    logs = _wait_logs(ref=ref)
    curves = {n: la.read_trace_log(d['path']) for n, d in logs.items()}
    for name, c in curves.items():
        info = logs[name]
        pr = la.pair_pause_waits(ref, c)
        w = c.meta['waits']
        check(f"{name} Show: pauses paired in order with marked / not marked / marked; lengths = end - received of "
              f"the marked waits (exactly what Remove cuts), 0 and a note for the wait not marked",
              [p['kind'] for p in pr] == ['marked', 'not_marked', 'marked']
              and pr[0]['length'] == w[0]['length'] == w[0]['cut'][1] - w[0]['cut'][0]
              and pr[2]['length'] == w[1]['length'] and pr[1]['length'] == 0.0 and 'not marked' in pr[1]['note'],
              str([(p['kind'], round(p['length'], 4)) for p in pr]))
        cut = la.remove_waits(c)
        check(f"{name} Remove: no -1000 row left, the removed rows are the -1000 rows",
              not np.any(cut.probe == -1000) and cut.t.size == c.t.size - sum(x['rows'] for x in w))
        # expected misalignment of the cut log after each pause: the part [real start, received) that stays, minus
        # the trigger row's delay after the real end, plus the waits not marked (not removed)
        exp, acc = [], 0.0
        for d in info['waits']:
            if d['kind'] == 'marked':
                acc += (d['received'] - d['start']) - (d['end_row'] - d['end_true'])
            else:
                acc += d['end_true'] - d['start']
            exp.append(acc)
        m_ref = la.detect_movements(ref, 'X')
        m_cut = la.detect_movements(cut, 'X')
        # movement k of the reference follows pause p(k): 0-1 after pause 1, 2-3 after pause 2, 4-5 after pause 3
        errs = [m_cut[k]['t_start'] - (m_ref[k]['t_start'] + exp[k // 2]) for k in range(min(len(m_ref), len(m_cut)))]
        check(f"{name} Remove: lines up with the G-code within the staircase / sample error (6 movement starts "
              f"within 0.3 s once the logged timing uncertainty is accounted for)",
              len(m_cut) == len(m_ref) == 6 and all(-0.1 <= e_ <= 0.3 for e_ in errs),
              str(np.round(errs, 3)))
        show = la.with_pause_durations(ref, [p['length'] for p in pr])
        m_show = la.detect_movements(show, 'X')
        m_log = la.detect_movements(c, 'X')
        errs2 = [m_log[k]['t_start'] - (m_show[k]['t_start'] + exp[k // 2]) for k in range(min(len(m_show), len(m_log)))]
        check(f"{name} Show: the reference with the logged lengths lines up with the log the same way",
              len(m_log) == 6 and all(-0.1 <= e_ <= 0.3 for e_ in errs2), str(np.round(errs2, 3)))
    # the three logs without their waits line up with each other (ensemble)
    cuts = [la.remove_waits(c) for c in curves.values()]
    ens = la.ensemble(cuts, 'X', dt=0.02)
    raw = la.ensemble(list(curves.values()), 'X', dt=0.02)
    check("three logs with different wait lengths: without their waits they line up (mean STD << as recorded)",
          ens['std_mean'] < 0.25 * raw['std_mean'], f"{ens['std_mean']:.3f} vs {raw['std_mean']:.3f} mm")
    # a count mismatch: nothing paired, nothing guessed
    only2 = write_wait_log(os.path.join(TMP, "log_wait_two.csv"), la.read_reference_gcode(WAIT3_GCODE.replace(
        'M98 P"0:macros/sensor_wait.g"\nG1 X12', 'G1 X12')), [('marked', 2.0), ('marked', 3.0)], seed=3)
    c2 = la.read_trace_log(only2['path'])
    pr = la.pair_pause_waits(ref, c2)
    check("count mismatch (2 logged waits, 3 sensor_wait pauses): nothing paired, every length 0, a note says why",
          [p['length'] for p in pr] == [0.0] * 3 and all(p['kind'] == 'none' and 'not paired' in p['note'] for p in pr),
          pr[0]['note'])
    # other pause kinds: not logged
    g = WAIT3_GCODE.replace('G4 P1500\nM98 P"0:macros/sensor_wait.g"', 'G4 P1500\nM226')
    ref_m = la.read_reference_gcode(g)
    plan2 = [('marked', 2.5), ('marked', 1.5)]
    l2 = write_wait_log(os.path.join(TMP, "log_wait_m226.csv"), ref_m, plan2, seed=4)
    pr = la.pair_pause_waits(ref_m, la.read_trace_log(l2['path']))
    check("M226 between two sensor_wait pauses: 'not logged', 0 s; the sensor_waits get the logged lengths",
          [p['label'] for p in pr] == ['sensor_wait', 'M226', 'sensor_wait'] and pr[1]['length'] == 0.0
          and pr[1]['note'] == 'not logged' and pr[0]['length'] > 2.3 and pr[2]['length'] > 1.3, str(pr))


def test_v1_unchanged():
    """v1 logs read exactly as before (t, data, probe, every meta value of the previous module) when a baseline
    module is given: TRACE_LA_BASELINE = path of a copy of the previous fcn_logs/log_analysis.py."""
    files = [f for files in REAL_SETS.values() for f in files if os.path.isfile(f)]
    files += sorted(glob.glob(os.path.join(ROOT, "log_*.csv")))
    files += sorted(glob.glob(os.path.join(HOME, "Desktop", "log_*.csv")))
    files = sorted({os.path.abspath(f) for f in files if not f.endswith('_DUMMY_wait.csv')})
    curves = [la.read_trace_log(f) for f in files]
    check(f"{len(files)} real v1 logs: no logged waits, ',' separator, '.' decimals",
          all(not c.meta['waits'] and not c.meta['waits_not_marked'] and not c.meta['message_read_failures']
              and c.meta['decimal'] == '.' for c in curves), str(len(files)))
    base = os.environ.get('TRACE_LA_BASELINE')
    if not base or not os.path.isfile(base):
        print("SKIP: v1 comparison with the previous module (set TRACE_LA_BASELINE to its path)")
        return
    import importlib.util
    spec = importlib.util.spec_from_file_location('la_baseline', base)
    old = importlib.util.module_from_spec(spec)
    sys.modules['la_baseline'] = old
    spec.loader.exec_module(old)
    bad = []
    for f, c in zip(files, curves):
        o = old.read_trace_log(f)
        same = (np.array_equal(c.t, o.t) and list(c.data) == list(o.data)
                and all(np.array_equal(c.data[k], o.data[k]) for k in o.data)
                and ((c.probe is None and o.probe is None) or np.array_equal(c.probe, o.probe))
                and all(repr(c.meta.get(k)) == repr(o.meta[k]) for k in o.meta) and c.name == o.name)
        if not same:
            bad.append(os.path.basename(f))
    print(f"INFO: v1 comparison with {base}: {len(files)} logs, {len(bad)} different")
    check(f"v1 unchanged: all {len(files)} real logs give the same Curve as the previous module (t, data, probe, "
          f"every meta value)", not bad, str(bad))


def test_wait_performance():
    ref = la.read_reference_gcode(long_wait_gcode(8000.0), name="long")
    t0 = time.perf_counter()
    info = write_wait_log(os.path.join(TMP, "log_wait_long.csv"), ref, WAIT_PLANS['log_wait_A'], seed=11)
    t_w = time.perf_counter() - t0
    t0 = time.perf_counter()
    c = la.read_trace_log(info['path'])
    t_r = time.perf_counter() - t0
    t0 = time.perf_counter()
    cut = la.remove_waits(c)
    t_c = time.perf_counter() - t0
    print(f"INFO: 100k-row v2 wait log: write {t_w:.2f} s, read {t_r:.2f} s, remove_waits {1000 * t_c:.1f} ms")
    check("100k-row v2 log with waits: read < 5 s, remove_waits < 0.1 s, 2 waits removed",
          c.t.size > 99_000 and t_r < 5.0 and t_c < 0.1 and len(cut.meta['cuts']) == 2, f"n={c.t.size}")


_SNAP_HDR = ("# Computer Time: 2026-11-06 12:34:12.404\n# G-code: 0:/gcodes/x.gcode\n# Device: Lung Phantom\n"
             "# Axes (Duet order): X,Y,Z\n# Positions: actual\n# Probe: 0 none | 1-1499 detector | 2000 Release button | "
             "-1000 waiting for sensor (sensor_wait)\n# Wait timing: ...\n# Run notes: ... at the end of the file\n"
             "# Recording from: 0,000 s of the run\n# Format: columns separated by semicolons, decimal comma\n"
             "Time_s;Pos_X_mm;Pos_Y_mm;Pos_Z_mm;Probe\n")


def _snap_log(name, last_wait_row, end_note='25,000', t_fetch=24.99995, trigger_probe=0):
    """A v2 log whose wait (received 19.990 s) ends by a Duet message at end_note: rows every 0.08 s through
    last_wait_row; rows before t_fetch carry -1000 (the logger marks them while the wait is open); the first row
    after has trigger_probe."""
    t = np.unique(np.round(last_wait_row + 0.08 * np.arange(-312, 62), 4))
    probe = np.where((t >= 20.0) & (t < t_fetch), -1000, 0)
    j = int(np.searchsorted(t, t_fetch))
    if j < t.size:
        probe[j] = trigger_probe
    rows = "\n".join(f"{x:.4f};1,000;2,000;3,000;{p}".replace('.', ',') for x, p in zip(t, probe))
    notes = ('# Wait start: "Waiting for sensor signal..." received at 19,990 s (Duet sent it between 19,500 and '
             f'19,990 s)\n# Wait end: Duet message "Continuing" at {end_note} s (from the Duet message, up to ~0,5 s '
             'late)\n# End: job finished at 29,990 s\n')
    p = write(os.path.join(TMP, name), _SNAP_HDR + rows + "\n" + notes)
    return la.read_trace_log(p), t, probe


def _excel_resave(lines):
    """A v2 log as Excel (';' lists, decimal comma) writes it back: every '#' line holding '"' quoted with doubled
    quotes, every line padded with ';' to the widest row."""
    width = max(l.count(';') for l in lines if l and not l.startswith('#'))
    out = []
    for l in lines:
        if l.startswith('#'):
            if '"' in l:
                l = '"' + l.replace('"', '""') + '"'
            l = l + ';' * width
        out.append(l)
    return out


def test_review8_reader_and_cut():
    """Round 8 regressions in the core: a text cell in a v2 log (pandas 3 StringDtype), an Excel-saved v2 log
    (quoted '#' lines), the cut end of a wait ended between rows, an aligned export with a shorter column."""
    src = open(DUMMY, encoding='utf-8', newline='').read().split('\r\n')
    orig = la.read_trace_log(DUMMY)
    i0 = next(i for i, l in enumerate(src) if l and not l.startswith('#')) + 1          # first data row
    k = i0 + 300

    def edited(name, col, val):
        ls = list(src)
        cells = ls[k].split(';')
        cells[col] = val
        ls[k] = ';'.join(cells)
        return la.read_trace_log(write(os.path.join(TMP, name), '\r\n'.join(ls)))
    c = edited("r8_textcell_si.csv", 2, 'x')
    j = k - i0
    ok_rest = all(np.array_equal(np.delete(c.data[a], j), np.delete(orig.data[a], j)) for a in orig.data)
    check("v2 log with one text cell in Pos_SI_mm: SI kept (14 axes, decimal comma read), only that value "
          "interpolated, the waits unchanged",
          list(c.data) == list(orig.data) and ok_rest and np.isfinite(c.data['SI'][j])
          and [w['cut'] for w in c.meta['waits']] == [w['cut'] for w in orig.meta['waits']], f"{len(c.data)} axes")
    c = edited("r8_textcell_probe.csv", -1, 'x')
    check("v2 log with one text cell in Probe: that row reads 0, the 21 -1000 rows and the wait unchanged",
          int(np.sum(c.probe == -1000)) == 21 and c.probe[j] == 0.0
          and [w['cut'] for w in c.meta['waits']] == [w['cut'] for w in orig.meta['waits']])
    ls = list(src)
    hdr_i = i0 - 1
    ls[hdr_i] = ls[hdr_i] + ';Pos_Q_mm'
    for i in range(i0, len(ls)):
        if ls[i] and not ls[i].startswith('#'):
            ls[i] = ls[i] + ';err'
    c = la.read_trace_log(write(os.path.join(TMP, "r8_text_column.csv"), '\r\n'.join(ls)))
    check("v2 log with an axis column of text only: left out with a warning naming it (not silently)",
          'Q' not in c.data and len(c.data) == len(orig.data)
          and any("'Pos_Q_mm' has no numeric value" in x for x in c.meta['warnings']), str(c.meta['warnings']))
    # Excel opened the v2 log and saved it again (';' lists, decimal comma)
    c = la.read_trace_log(write(os.path.join(TMP, "r8_excel_resaved.csv"), '\r\n'.join(_excel_resave(src))))
    keys = ('received', 'sent_from', 'end', 'end_by', 'end_note', 'end_exact', 'rows', 'source', 'cut', 'message')
    check("Excel-saved v2 log (quoted '#' lines with \"\", rows padded with ';'): the same rows, the same noted wait "
          "(not the rows-only fallback), End and header; no warning",
          np.array_equal(c.t, orig.t) and all(np.array_equal(c.data[a], orig.data[a]) for a in orig.data)
          and np.array_equal(c.probe, orig.probe)
          and [{x: w[x] for x in keys} for w in c.meta['waits']] == [{x: w[x] for x in keys} for w in orig.meta['waits']]
          and c.meta['end'] == orig.meta['end'] and c.meta['header'] == orig.meta['header'] and not c.meta['warnings'],
          f"{[(w['received'], w['source']) for w in c.meta['waits']]} {c.meta['warnings']}")
    # a wait ended by a Duet message between rows: a -1000 row within the note's 0.5 ms rounding is a wait row
    ref1 = la.read_reference_gcode('G90\nG1 X0 F600\nG4 P2000\nM98 P"0:macros/sensor_wait.g"\nG1 X10 F600\nG4 P1000\n',
                                   name='one')
    for name, last, note, t_fetch in (("r8_snap_before.csv", 24.9998, '25,000', 24.99995),
                                      ("r8_snap_after.csv", 25.0003, '25,000', 25.00045)):
        c, t, probe = _snap_log(name, last, note, t_fetch)
        w = c.meta['waits'][0]
        cut = la.remove_waits(c)
        P = la.pair_pause_waits(ref1, c)
        check(f"wait ended by a Duet message, last -1000 row at {last} s (note {note.replace(',', '.')} s): one wait, "
              f"every -1000 row inside its cut, none left after remove_waits, no rows-only warning, paired",
              len(c.meta['waits']) == 1 and w['source'] == 'notes' and w['rows'] == int(np.sum(probe == -1000))
              and w['cut'][1] > last and w['cut'][1] <= 25.0 + la._NOTE_ROUND + 1e-9
              and not np.any(cut.probe == -1000) and not c.meta['warnings'] and P[0]['kind'] == 'marked'
              and abs(P[0]['length'] - (w['cut'][1] - 19.99)) < 1e-12,
              f"cut {w['cut']} rows {w['rows']} warnings {c.meta['warnings']}")
    c, t, probe = _snap_log("r8_snap_trigger.csv", 24.9998, '25,080', 25.0797, trigger_probe=1000)
    check("... a non -1000 row within the rounding is the row that ended it: the cut stops exactly there (kept)",
          c.meta['waits'][0]['cut'][1] == 25.0798 and 25.0798 in set(c.t[la.remove_waits(c).meta['cut_index']]),
          str(c.meta['waits'][0]['cut']))
    check("the dummy's wait still ends on its trigger row (Release, 11.8491 s)",
          orig.meta['waits'][0]['cut'] == (10.11, 11.8491))
    # an aligned export with a shorter column (a log shown without its waits next to an uncut one)
    p = write(os.path.join(TMP, "r8_export_tail.csv"),
              "# TRACE Log files aligned export: SI\r\ntime [s];SI: a [mm];SI: b [mm]\r\n0,0;1,0;1,0\r\n1,0;2,0;2,0\r\n"
              "2,0;3,0;3,0\r\n3,0;;4,0\r\n4,0;;5,0\r\n")
    c = la.read_trace_log(p)
    a, b = c.data['SI a'], c.data['SI b']
    check("aligned export read back: a column stays empty (NaN) after its last value (no value held beyond the file)",
          np.array_equal(a[:3], [1.0, 2.0, 3.0]) and np.isnan(a[3:]).all() and np.array_equal(b, [1, 2, 3, 4, 5.0]),
          f"{a} {b}")
    mv = la.detect_movements(c, 'SI a', threshold=0.5, settle_time=0.5)
    st_ = la.movement_stats(c, 'SI a', 0.0, 2.0)
    check("... the analyses use the samples that have a value (nearest point, detect_movements, movement_stats, "
          "sample)", la.nearest_point(c, 'SI a', 3.6) == (2.0, 3.0) and isinstance(mv, list)
          and st_['v_stop'] == 3.0 and np.isnan(la.sample(c, 'SI a', [3.5])[0])
          and la.nearest_point(c, 'SI b', 3.6) == (4.0, 5.0), f"{mv} {st_['v_stop']}")
    p = write(os.path.join(TMP, "r8_export_gap.csv"), "time [s],SI: a [mm]\n0.0,1\n1.0,\n2.0,3\n")
    check("... a hole inside a column is still interpolated (as before)",
          list(la.read_trace_log(p).data['SI']) == [1.0, 2.0, 3.0])


def main():
    for fn in (test_constants_and_curve, test_estimate_shift, test_compare, test_ensemble, test_peaks_periods,
               test_detect_movements, test_reference_and_pauses, test_slow_staircase_ramps,
               test_gap_movements, test_reader_regressions,
               test_rest_level_and_restart, test_gaps_away_from_pause, test_reader_fewer_fields,
               test_sample_nearest_table_csv,
               test_floor_leaves_long_settle_unchanged,
               test_short_settle_slow_ramps, test_open_gap_while_moving,
               test_noisy_stops, test_aligned_export_read_back,
               test_read_synthetic_files, test_real_logs, test_real_reference, test_performance,
               test_movement_stats, test_movement_stats_real, test_value_crossings,
               test_v2_reader_dummy, test_v2_synthetic_logs, test_v2_notes_and_malformed, test_cut_map,
               test_pairing_and_alignment, test_v1_unchanged, test_wait_performance, test_review8_reader_and_cut):
        section(fn)
    shutil.rmtree(TMP, ignore_errors=True)
    failed = RESULTS.count(False)
    print()
    if failed:
        print(f"{failed} FAILED (of {len(RESULTS)})")
        sys.exit(1)
    print(f"ALL PASSED ({len(RESULTS)} checks)")


if __name__ == "__main__":
    main()
