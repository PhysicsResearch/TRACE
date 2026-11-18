"""
Import Motion Curve dialog: "Centre at 0" for KINETIQ (user, 18 Nov 2026).

KINETIQ's zero is the platform centre, so an imported breathing curve is centred on it: the middle of the curve's
range goes to 0 (a 15 mm curve runs from -7.5 to +7.5 mm).  DYNAMIQ's zero is its home, at the bottom of each axis,
so it keeps "Shift minimum to 0 (Zero baseline)" (the lowest point goes to 0).

* The two options exclude each other (both off = the values as recorded).  The default follows the dialog's device:
  Motion Platform -> Centre at 0, Lung Phantom -> Zero baseline.  Changing the device sets that default again.
* The centre is taken from the curve that is imported (smoothed when Smoothing is on): fcn_plan/import_preview.py
  uses centre_offset() for the plot and for Import & Apply; the green preview banner shows the centred range.

    from fcn_plan.import_centre import install_import_centre, centre_offset
    install_import_centre(dlg)           # in install_import_preview, before its plot is connected
"""
import numpy as np
from PySide6.QtWidgets import QCheckBox, QGridLayout

CENTRE_DEVICES = ("Motion Platform",)
LABEL = "Centre at 0 (middle of the range)"
TIP = ("Shifts the curve so that the middle of its range is at 0 mm (the shape is kept, nothing is cut). On KINETIQ, "
       "0 is the platform centre, so the curve runs equally above and below the centre.\nDYNAMIQ uses Shift minimum to "
       "0 instead: its 0 is the home position, at the bottom of each axis.")


def centre_on(dlg):
    cb = getattr(dlg, 'cb_centre', None)
    return bool(cb is not None and cb.isChecked())


def centre_value(y):
    """Middle of the range of y (NaN ignored); 0 for an empty curve."""
    y = np.asarray(y, dtype=float)
    if not np.isfinite(y).any():
        return 0.0
    return float((np.nanmax(y) + np.nanmin(y)) / 2.0)


def centre_offset(dlg, y):
    """What to subtract from the output curve y: its centre when Centre at 0 is on, else 0."""
    return centre_value(y) if centre_on(dlg) else 0.0


def _find_layout_with(layout, widget):
    """(layout, index) of the (nested) layout that holds widget."""
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget() is widget:
            return layout, i
        sub = item.layout()
        if sub is not None:
            found = _find_layout_with(sub, widget)
            if found[0] is not None:
                return found
    return None, -1


def install_import_centre(dlg):
    zb, inv = dlg.cb_zero_baseline, dlg.cb_invert
    cb = QCheckBox(LABEL, zb.parentWidget())
    cb.setToolTip(TIP)
    cb.setStyleSheet(zb.styleSheet())
    dlg.cb_centre = cb

    # options: [Zero baseline] [Centre at 0] on one row, Flip below them (one row was too narrow for three)
    grid = zb.parentWidget().layout()
    row_lay, idx = _find_layout_with(grid, zb)
    placed = False
    if isinstance(grid, QGridLayout) and row_lay is not None:
        card = getattr(dlg, 'preview_card', None)
        r_opts = None
        for i in range(grid.count()):
            if grid.itemAt(i).layout() is row_lay:
                r_opts = grid.getItemPosition(i)[0]
        if r_opts is not None and card is not None and grid.indexOf(card) >= 0:
            r_card = grid.getItemPosition(grid.indexOf(card))[0]
            row_lay.removeWidget(inv)
            row_lay.insertWidget(idx + 1, cb)
            grid.removeWidget(card)
            grid.addWidget(inv, r_opts + 1, 0, 1, 2)
            grid.addWidget(card, max(r_card, r_opts + 1) + 1, 0, 1, 2)
            placed = True
    if not placed and row_lay is not None:
        row_lay.insertWidget(idx + 1, cb)

    def exclusive_centre(on):
        if on and zb.isChecked():
            zb.setChecked(False)

    def exclusive_baseline(on):
        if on and cb.isChecked():
            cb.setChecked(False)

    cb.toggled.connect(exclusive_centre)
    zb.toggled.connect(exclusive_baseline)

    def device_default(device=None):
        device = device or dlg.combo_device.currentText()
        if device in CENTRE_DEVICES:
            cb.setChecked(True)
        else:
            zb.setChecked(True)

    dlg.combo_device.currentTextChanged.connect(device_default)
    device_default()

    # the green banner (ImportMotionDialog.update_preview) shows the centred range; runs after update_preview
    def banner(*_):
        if not centre_on(dlg):
            return
        from fcn_plan.import_preview import _output
        s = dlg.spin_smooth.value() if hasattr(dlg, 'spin_smooth') else 0.0
        _t, _raw, out = _output(dlg, s)
        sps = max(0.001, dlg.spin_sps.value())
        lo, hi = float(np.nanmin(out)), float(np.nanmax(out))
        r_lo, r_hi = float(np.nanmin(dlg.raw_amp)), float(np.nanmax(dlg.raw_amp))
        dlg.lbl_preview_stats.setText(
            f"Raw: [{r_lo:.2f}, {r_hi:.2f}]  ➜  Output Range: [{lo:.2f}, {hi:.2f}] mm  (Peak-to-Peak: {hi - lo:.2f} mm)"
            f"\nTimeline: {len(dlg.raw_amp) / sps:.2f} s  ({len(dlg.raw_amp):,} points @ {sps:.2f} Hz)")

    cb.toggled.connect(dlg.update_preview)
    dlg.lbl_preview_stats.setWordWrap(True)          # centred values are longer: the line was cut at the column edge
    dlg._centre_banner = banner
    for sig in (dlg.spin_sps.valueChanged, dlg.spin_sf.valueChanged, dlg.cb_invert.toggled,
                dlg.cb_zero_baseline.toggled, cb.toggled):
        sig.connect(banner)
    return dlg
