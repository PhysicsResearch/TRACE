"""
Import Motion Curve dialog (VXP / CSV): a plot of the curve that will be imported, and a Smoothing control.

    from fcn_plan.import_preview import install_import_preview
    install_import_preview(dialog)              # end of ImportMotionDialog.__init__

* The plot shows the output curve as it will be applied (scale factor, Invert / Flip, zero baseline): the raw curve
  (light) and, with Smoothing on, the smoothed curve (dark).  It follows every option at once, so flipping the curve
  or changing the scale is seen directly.  Toolbar: zoom / pan to look at the noise.
* Smoothing (s): Savitzky-Golay window (fcn_plan/motion_smooth.py); 0 = off (default, the curve is imported as
  recorded).  The line under the plot says what it changes: largest / RMS difference, direction changes, range.
* Import & Apply uses the smoothed curve when Smoothing is on; everything else of the import is unchanged.
"""
import numpy as np
from PySide6.QtWidgets import (QDoubleSpinBox, QGroupBox, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget)

from fcn_plan.motion_smooth import MAX_WINDOW_S, curve_stats, smooth_curve, window_samples

DEFAULT_SMOOTH_S = 0.0
RAW_COLOR = "#b5c0a9"
OUT_COLOR = "#354530"


def _output(dlg, smooth_s):
    """The curve the import produces (same order as ImportMotionDialog.on_apply), raw and smoothed."""
    sps = max(0.001, dlg.spin_sps.value())
    raw = np.asarray(dlg.raw_amp, dtype=float) * dlg.spin_sf.value()
    if dlg.cb_invert.isChecked():
        raw = -raw
    sm = smooth_curve(raw, sps, smooth_s) if smooth_s > 0 else raw.copy()
    if dlg.cb_zero_baseline.isChecked():
        base = np.nanmin(sm)
        raw, sm = raw - base, sm - base
    t = np.arange(len(raw)) / sps
    return t, raw, sm


def install_import_preview(dlg):
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
    from matplotlib.figure import Figure

    # '&' in the existing titles is read by Qt as a shortcut mark ("Scaling _Timing"): shown as a real '&'
    from PySide6.QtWidgets import QPushButton
    for w in dlg.findChildren(QGroupBox):
        if "&" in w.title() and "&&" not in w.title():
            w.setTitle(w.title().replace("&", "&&"))
    for w in dlg.findChildren(QPushButton):
        if "&" in w.text() and "&&" not in w.text():
            w.setText(w.text().replace("&", "&&"))

    # existing controls move to a left column; the preview goes on the right
    lay = dlg.layout()
    left = QWidget(dlg)
    lv = QVBoxLayout(left)
    lv.setContentsMargins(0, 0, 0, 0)
    lv.setSpacing(lay.spacing())
    while lay.count():
        item = lay.takeAt(0)
        if item.widget() is not None:
            lv.addWidget(item.widget())
        elif item.layout() is not None:
            lv.addLayout(item.layout())
        elif item.spacerItem() is not None:
            lv.addItem(item.spacerItem())
    left.setFixedWidth(600)

    box = QGroupBox("Preview && smoothing", dlg)          # '&&' = '&' in a group box title
    bv = QVBoxLayout(box)
    bv.setContentsMargins(12, 14, 12, 12)
    fig = Figure(figsize=(6, 4), dpi=90, layout='constrained')
    ax = fig.add_subplot(111)
    canvas = FigureCanvasQTAgg(fig)
    canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    canvas.setMinimumHeight(360)
    bar = NavigationToolbar2QT(canvas, box)
    bv.addWidget(bar)
    bv.addWidget(canvas, 1)

    row = QHBoxLayout()
    lbl = QLabel("Smoothing (s):", box)
    lbl.setStyleSheet("font-weight: bold;")
    spin = QDoubleSpinBox(box)
    spin.setRange(0.0, MAX_WINDOW_S)
    spin.setDecimals(2)
    spin.setSingleStep(0.1)
    spin.setValue(DEFAULT_SMOOTH_S)
    spin.setMinimumHeight(38)
    spin.setSpecialValueText("Off")
    spin.setToolTip("Savitzky-Golay smoothing window in seconds (a local quadratic fit): removes sample-to-sample "
                    "noise and keeps the breathing peaks. Off = the curve as recorded.\nThe noise of a recorded "
                    "curve cannot be reproduced by the device and makes the motion run late.")
    row.addWidget(lbl)
    row.addWidget(spin)
    row.addStretch(1)
    bv.addLayout(row)
    stats = QLabel("", box)
    stats.setWordWrap(True)
    stats.setStyleSheet("color: #455a64; font-size: 13px;")
    bv.addWidget(stats)

    h = QHBoxLayout()
    h.setSpacing(14)
    h.addWidget(left)
    h.addWidget(box, 1)
    lay.addLayout(h)
    dlg.setMinimumSize(1150, 760)
    dlg.resize(1300, 820)

    dlg.spin_smooth = spin
    dlg.preview_canvas = canvas
    dlg.preview_ax = ax
    dlg.preview_stats = stats
    state = {"view": None}

    def refresh(*_):
        s = spin.value()
        t, raw, sm = _output(dlg, s)
        keep = None
        if ax.lines and bar.mode:                          # keep a zoom while the user looks at a detail
            keep = (ax.get_xlim(), ax.get_ylim())
        ax.clear()
        ax.grid(True, linestyle=':', alpha=0.6)
        on = s > 0 and window_samples(dlg.spin_sps.value(), s) > 0
        ax.plot(t, raw, color=RAW_COLOR if on else OUT_COLOR, lw=0.9 if on else 1.1,
                label="as recorded" if on else "curve to import")
        if on:
            ax.plot(t, sm, color=OUT_COLOR, lw=1.3, label=f"smoothed ({s:g} s)")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Position (mm)")
        ax.legend(loc="upper right", fontsize=9)
        if keep is not None:
            ax.set_xlim(keep[0])
            ax.set_ylim(keep[1])
        canvas.draw_idle()
        if on:
            st = curve_stats(raw, sm)
            stats.setText(f"Smoothing changes the curve by at most {st['max_diff']:.3f} mm (RMS {st['rms_diff']:.3f} mm). "
                          f"Direction changes: {st['rev_raw']:,} → {st['rev_smooth']:,}. "
                          f"Range: {st['p2p_raw']:.2f} → {st['p2p_smooth']:.2f} mm.")
        else:
            stats.setText(f"Smoothing off: the curve is imported as recorded ({curve_stats(raw, raw)['rev_raw']:,} "
                          f"direction changes).")

    for sig in (dlg.spin_sps.valueChanged, dlg.spin_sf.valueChanged, dlg.cb_invert.toggled,
                dlg.cb_zero_baseline.toggled, spin.valueChanged):
        sig.connect(refresh)
    refresh()

    # Import & Apply: the smoothed curve (smoothing is linear, so it commutes with the scale factor and the flip; the
    # zero baseline of on_apply then shifts the smoothed curve, as in the preview)
    original_apply = type(dlg).on_apply
    try:
        dlg.btn_import_apply.clicked.disconnect()
    except (RuntimeError, TypeError):
        pass

    def apply_smoothed():
        s = spin.value()
        raw0 = dlg.raw_amp
        if s > 0:
            dlg.raw_amp = smooth_curve(np.asarray(raw0, dtype=float), max(0.001, dlg.spin_sps.value()), s)
        try:
            original_apply(dlg)
        finally:
            dlg.raw_amp = raw0
        p = dlg.parent_ui
        if p is not None:
            p.import_smoothing_s = s

    dlg.btn_import_apply.clicked.connect(apply_smoothed)
    return dlg
