"""
Replace | Insert mode of Add Curve in the modern Planning tab (requests I + J), built by
tab_planning_modern.ModernPlanning.build() next to the 'Add Curve' button.

- Replace (default): Add Curve as before (the values of the selected axes between Start and End are replaced).
- Insert: Add Curve first opens a gap of (End - Start) seconds at Start (linear: Duration) - every row from Start on,
  with its pauses and trigger switches, moves right; the gap holds every axis at its position at Start and keeps the
  trigger state there (fcn_plan/fcn_insert.insert_interval) - then writes the curve into the gap exactly as Replace
  does (the legacy create_curve).  When create_curve moves the curve later to reach its first value at the maximum
  speed (consecutive intervals), the gap is made that much longer, so the moved data is never overwritten.  The plan
  and the Total duration grow by the inserted length.  One undo step for the whole Insert.

fcn_plan.fcn_create.create_curve (looked up at call time by createCurve, the Add Curve handler) is wrapped once; the
original runs unchanged in Replace mode and for windows without the modern controls.
"""

import functools
import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy

MODES = [
    ('replace', "Replace",
     "Replace: Add Curve overwrites the selected axes between Start and End (the rest of the plan stays where it "
     "is).\nSelected = filled."),
    ('insert', "Insert",
     "Insert: Add Curve first inserts (End - Start) seconds at Start - everything from Start on (all axes, pauses, "
     "trigger switches)\nmoves right, the gap holds every axis at its position at Start - then writes the curve into "
     "the gap.\nThe plan and the Total duration grow by that length.  One undo step.  Selected = filled."),
]
DEFAULT_MODE = 'replace'
SEG_WIDTH = 92


def _fc():
    from fcn_plan import fcn_create
    return fcn_create


# ----------------------------------------------------------------------------------------- hook
def install_insert_hook():
    fc = _fc()
    cur = fc.create_curve
    if not getattr(cur, '_pm_insert_wrapper', False):
        fc.create_curve = _wrap_create_curve(cur)


def _wrap_create_curve(original):
    @functools.wraps(original)
    def wrapper(self, *args, **kwargs):
        ctl = getattr(getattr(self, 'planning_modern', None), 'insert_replace', None)
        if ctl is not None and ctl.alive() and ctl.mode == 'insert':
            return ctl.run_insert(original)
        return original(self, *args, **kwargs)

    wrapper._pm_insert_wrapper = True
    wrapper._pm_original = original
    return wrapper


# ----------------------------------------------------------------------------------------- controls
class InsertReplace:
    """The Replace | Insert pair next to Add Curve (one per window: pm.insert_replace)."""

    def __init__(self, pm):
        self.pm = pm
        self.win = pm.win
        self.mode = DEFAULT_MODE
        self.box = None
        self.buttons = {}
        self.last_insert = None          # (t_at, seconds inserted) of the last Insert (tests / status)

    def alive(self):
        return bool(getattr(self.pm, 'alive', False))

    def build(self):
        from fcn_create_gui.tab_planning_modern import _segmented, MODE_SEG_STYLE, EVENT_HEIGHT, _find_layout_with
        w = self.win
        create = getattr(w, 'button_create_curve', None)
        if create is None:
            return
        lay, idx = None, -1
        for root in (getattr(self.pm, 'curve_left', None), w.groupBox_BrCv_createCurve):
            if root is not None and root.layout() is not None:
                lay, idx = _find_layout_with(root.layout(), create)
                if lay is not None:
                    break
        if lay is None:
            return
        # [Add Curve] [Replace | Insert] [Import File] [Clear All]: the three buttons share the rest of the row equally
        self.box, self.buttons = _segmented(create.parentWidget(), MODES, MODE_SEG_STYLE, EVENT_HEIGHT, self.set_mode)
        self.box.setObjectName('pmAddMode')
        for b in self.buttons.values():
            b.setFixedWidth(SEG_WIDTH)
        self.box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        lay.insertWidget(idx + 1, self.box, 0, Qt.AlignVCenter)
        for name in ('button_create_curve', 'button_import_curve', 'button_clear_all'):
            b = getattr(w, name, None)
            i = lay.indexOf(b) if b is not None else -1
            if i >= 0:
                b.setMinimumWidth(0)
                b.setSizePolicy(QSizePolicy.Ignored, b.sizePolicy().verticalPolicy())
                lay.setStretch(i, 1)
        self.set_mode(DEFAULT_MODE)
        install_insert_hook()

    def set_mode(self, mode):
        self.mode = mode if mode in self.buttons else DEFAULT_MODE
        for k, b in self.buttons.items():
            if b.isChecked() != (k == self.mode):
                b.blockSignals(True)
                b.setChecked(k == self.mode)
                b.blockSignals(False)
        create = getattr(self.win, 'button_create_curve', None)
        if create is not None:
            tip = ("Add Curve (Insert): inserts (End - Start) s at Start, moves the rest of the plan right and "
                   "writes the curve into the gap (one undo step)." if self.mode == 'insert' else
                   "Add Curve (Replace): writes the curve to the selected axes between Start and End.")
            create.setToolTip(tip)

    # ------------------------------------------------------------------ Insert
    def _selected_axes(self):
        w = self.win
        axes = [a for a, cb in (getattr(w, 'create_curve_axis_checkboxes', None) or {}).items()
                if cb.isChecked() and cb.isEnabled()]
        if not axes and getattr(w, 'combo_axis', None) is not None and w.combo_axis.currentText():
            axes = [w.combo_axis.currentText()]
        return axes

    def run_insert(self, original):
        """Insert, then the legacy create_curve writes the curve into the gap; one undo step."""
        from fcn_plan.fcn_insert import insert_interval
        fc = _fc()
        w = self.win
        if getattr(w, 'dfEdit', None) is None:
            fc.initialize_default_curve_data(w)
        if not self._selected_axes():
            return original(w)                    # its 'No Axis Selected' warning, nothing changed
        start, end = w.input_start_time, w.input_end_time
        t0, t1 = start.value(), end.value()
        func = w.combo_func_type.currentText()
        length = w.input_period.value() if func == "linear" else t1 - t0
        pre = w.dfEdit.copy(deep=True)
        new, ins = insert_interval(pre, t0, length)
        if ins <= 0:                              # at / past the plan end or zero length: Replace (extends the plan)
            self.last_insert = (t0, 0.0)
            return original(w)
        fc.push_curve_state(w)                    # the one undo step: the plan before the Insert
        snap = list(getattr(w, '_curve_undo_stack', []))
        w.dfEdit = new
        result = original(w)
        shift = round(start.value() - t0, 6)      # create_curve moved the curve later (transit at max speed)
        if shift > 1e-9:
            for sp, v in ((start, t0), (end, t1)):
                sp.blockSignals(True)
                sp.setValue(v)
                sp.blockSignals(False)
            # the Start box shows the shift rounded to its decimals: round the extra gap up to whole rows so the
            # moved curve ends inside the gap
            from fcn_plan.fcn_duration import plan_step
            step = plan_step(pre)
            half = 0.5 * 10.0 ** -start.decimals()
            extra = math.ceil((shift + half) / step - 1e-6) * step
            new, ins = insert_interval(pre, t0, length + extra)
            w.dfEdit = new
            result = original(w)
        w._curve_undo_stack = snap
        fc.update_undo_button_state(w)
        self.last_insert = (t0, ins)
        try:
            from fcn_create_gui.tab_planning_trigger import _trg_status
            _trg_status(w, f"Insert: {ins:.2f} s inserted at {t0:.2f} s, the plan after it moved right and the curve "
                           f"written into the gap (Undo restores the plan before).", "ok")
        except Exception:
            pass
        return result
