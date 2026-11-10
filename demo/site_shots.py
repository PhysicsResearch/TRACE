"""
Screenshots of LogIQ for the website (real fonts, the window's own rendering: window.grab / widget.grab, so nothing
else on the screen is captured).

    python demo/site_shots.py [out_dir]          default out_dir: C:\\LogIQ_site\\public\\images\\app

Writes full-window shots of every tab and crops of the Planning controls, with example plans for DYNAMIQ, KINETIQ
and pauses / triggers.  configuration.json is restored afterwards; nothing is sent to a Duet.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, r"C:\TRACE")
sys.path.insert(0, r"C:\TRACE\demo")
os.chdir(r"C:\TRACE")
OUT = sys.argv[1] if len(sys.argv) > 1 else r"C:\LogIQ_site\public\images\app"
os.makedirs(OUT, exist_ok=True)

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QFileDialog

cfg = os.path.join(r"C:\TRACE", "configuration.json")
cfg_bak = os.path.join(tempfile.gettempdir(), "logiq_site_shots_cfg.json")
shutil.copy2(cfg, cfg_bak)
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))

app = QApplication.instance() or QApplication(sys.argv)
import demo_planning as DP

w = DP.build_window()
w.showMaximized()
saved = []


def settle(n=8):
    for _ in range(n):
        app.processEvents()


def grab(widget, name, pad=0):
    settle()
    if widget is None or not widget.isVisible():
        print("skip", name, flush=True)
        return
    pm = widget.grab()
    pm.save(os.path.join(OUT, name + ".png"))
    saved.append((name, pm.width(), pm.height()))


def tab(i):
    w.tabModules.setCurrentIndex(i)
    settle(12)


def sub(name):
    tw = w.create_settings_tab_widget
    for k in range(tw.count()):
        if tw.tabText(k) == name:
            tw.setCurrentIndex(k)
    settle()


def axis(p, name):
    for a, b in p.axis_pills.items():
        if b.isChecked() != (a == name):
            b.click()
    settle(3)


def seg(func, amp, off, per, st, en=None, ph=0.0):
    w.combo_func_type.setCurrentText(func)
    w.input_amplitude.setValue(float(amp))
    if w.input_amp_offset.isEnabled():
        w.input_amp_offset.setValue(float(off))
    w.input_period.setValue(float(per))
    w.input_phase.setValue(float(ph))
    w.input_start_time.setValue(float(st))
    if en is not None and func != 'linear':
        w.input_end_time.setValue(float(en))
    w.button_create_curve.click()
    settle(3)


def clear_plan(p):
    try:
        w.button_clear_curve.click() if hasattr(w, 'button_clear_curve') else None
    except Exception:
        pass
    settle()


def run():
    # ---- other tabs (placeholders on the site)
    for i in range(w.tabModules.count()):
        name = w.tabModules.tabText(i).strip().lower().replace(' ', '-')
        if name == 'planning':
            continue
        tab(i)
        grab(w, f"tab-{name}")

    # ---- LogIQ layout: the bar on top of every tab (connection) and the tabs as icons on the left
    tab(0)
    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QFrame
    header = w.findChild(QFrame, 'logiqHeader')
    if header is not None:
        grab(header, 'app-header')
        ts = getattr(w, 'check_touchscreen', None)
        if ts is not None:
            right = ts.mapTo(header, ts.rect().topRight()).x() + 14
            settle()
            pm = header.grab(QRect(0, 0, right, header.height()))
            pm.save(os.path.join(OUT, 'ctl-connection.png'))
            saved.append(('ctl-connection', pm.width(), pm.height()))
    grab(getattr(w, 'emergencyButton_1', None), 'ctl-estop')
    nav = w.findChild(QFrame, 'logiqNav')
    if nav is not None:
        last = w.nav_buttons[-1]
        settle()
        pm = nav.grab(QRect(0, 0, nav.width(), last.mapTo(nav, last.rect().bottomLeft()).y() + 14))
        pm.save(os.path.join(OUT, 'app-nav.png'))
        saved.append(('app-nav', pm.width(), pm.height()))

    # ---- Planning, DYNAMIQ: ramp + sine + ramp on X, cos^2 on Y
    tab(3)
    p = w.planning_modern
    p.device_buttons[0].click()
    settle()
    grab(w, "planning-empty")
    axis(p, 'X')
    seg('linear', 0, 10, 2, 0)
    seg('sin', 10, 10, 4, 2, 18)
    seg('linear', 10, 0, 2, 18)
    axis(p, 'Y')
    seg('cos^2', 8, 0, 4, 4, 24, ph=180)
    w.input_phase.setValue(0.0)
    axis(p, 'X')
    w.combo_func_type.setCurrentText('sin')
    settle()
    grab(w, "planning-dynamiq")
    grab(getattr(p, 'plot_frame', None), "planning-plot-dynamiq")
    grab(getattr(p, 'device_box', None), "ctl-device")
    grab(getattr(p.curve_controls, 'func_box', None), "ctl-function")
    grab(getattr(p.curve_controls, 'time_box', None), "ctl-time")
    grab(getattr(p, 'axis_pill_box', None), "ctl-axis")
    grab(getattr(p.insert_replace, 'box', None), "ctl-insert-replace")
    grab(getattr(p, 'side_card', None), "ctl-plot-curves-dynamiq")
    grab(getattr(p, 'footer', None), "ctl-plot-footer")
    grab(getattr(p, 'bottom_row', None), "ctl-bottom-row")
    grab(getattr(w, 'button_import_curve', None), "ctl-import")
    grab(getattr(w, 'button_clear_all', None), "ctl-clear")
    grab(getattr(w, 'create_settings_tab_widget', None), "planning-lower-dynamiq")
    sub("Settings")
    grab(getattr(w, 'create_settings_tab_widget', None), "planning-settings-dynamiq")
    sub("Table")
    grab(getattr(w, 'create_settings_tab_widget', None), "planning-table")
    sub("Tools")
    grab(getattr(w, 'create_settings_tab_widget', None), "planning-tools")
    sub("Trigger")
    grab(getattr(w, 'create_settings_tab_widget', None), "planning-trigger-gate")
    sub("Curve")

    # ---- pauses and triggers on the same plan
    p.event_buttons['rad'].click(); w.input_wait_rad_time.setValue(5.0); p.btn_event_add.click(); settle()
    p.event_buttons['usr'].click(); w.input_wait_rad_time.setValue(12.0); p.btn_event_add.click(); settle()
    p.event_buttons['on'].click(); w.input_wait_rad_time.setValue(3.0); p.btn_event_add.click(); settle()
    p.event_buttons['off'].click(); w.input_wait_rad_time.setValue(8.0); p.btn_event_add.click(); settle()
    p.event_buttons['rad'].click()
    settle()
    grab(w, "planning-events")
    grab(getattr(p, 'plot_frame', None), "planning-plot-events")
    grab(getattr(p, 'event_card', None), "ctl-events-once")
    p.mode_buttons['repeat'].click()
    p.event_buttons['on'].click()
    settle()
    grab(getattr(p, 'event_card', None), "ctl-events-repeat")
    p.mode_buttons['once'].click()
    settle()

    # ---- KINETIQ: AP central position, Roll around it, SI cos^2
    p.device_buttons[1].click()
    settle()
    try:
        p.curve_controls.total_spin.setValue(30.0)
        p.curve_controls.total_spin.editingFinished.emit()
    except Exception:
        pass
    settle()
    for b in QApplication.topLevelWidgets():
        if b.isVisible() and b.inherits("QMessageBox"):
            b.accept()
    axis(p, 'AP')
    seg('linear', 0, 15, 3, 0)
    seg('constant', 15, 0, 4, 3, 27)
    seg('linear', 15, 0, 3, 27)
    axis(p, 'Roll')
    seg('sin', 3, 0, 4, 5, 25)
    axis(p, 'SI')
    seg('cos^2', 10, 0, 6, 6, 24, ph=180)
    w.input_phase.setValue(0.0)
    settle()
    grab(w, "planning-kinetiq")
    grab(getattr(p, 'plot_frame', None), "planning-plot-kinetiq")
    grab(getattr(p, 'side_card', None), "ctl-plot-curves-kinetiq")
    grab(getattr(p, 'rot_card', None), "ctl-rotation-centre")
    grab(getattr(p, 'axis_pill_box', None), "ctl-axis-kinetiq")
    sub("Settings")
    grab(getattr(w, 'create_settings_tab_widget', None), "planning-settings-kinetiq")
    sub("Curve")

    print("saved:", flush=True)
    for n, ww, hh in saved:
        print(f"  {n}.png {ww}x{hh}", flush=True)
    postprocess()
    w.close()
    shutil.copy2(cfg_bak, cfg)
    app.quit()


def postprocess():
    """Crops (empty card space, single controls) and WebP for the site."""
    import numpy as np
    from PIL import Image

    def img(n):
        return Image.open(os.path.join(OUT, n + ".png")).convert("RGB")

    def trim_bottom(n, pad=14):
        im = img(n)
        a = np.asarray(im.convert('L')).astype(int)
        bg = int(np.median(a[int(im.height * 0.9):int(im.height * 0.97), int(im.width * 0.3):int(im.width * 0.7)]))
        busy = np.where((np.abs(a[:, 6:-6] - bg) > 14).sum(axis=1) > 2)[0]
        last = busy[0]
        for r in busy:
            if r - last > 60 and last > 40:
                break
            last = r
        im.crop((0, 0, im.width, min(im.height, last + pad))).save(os.path.join(OUT, n + ".png"))

    for n in ('ctl-events-once', 'ctl-events-repeat', 'ctl-plot-curves-dynamiq', 'ctl-plot-curves-kinetiq'):
        trim_bottom(n)
    row = img('ctl-bottom-row')
    a = np.asarray(row.convert('L')).astype(int)
    bg = int(np.median(a))
    cols = np.where((np.abs(a - bg) > 20).sum(axis=0) > 1)[0]
    groups, s, p = [], cols[0], cols[0]
    for c in cols[1:]:
        if c - p > 40:
            groups.append((s, p))
            s = c
        p = c
    groups.append((s, p))
    row.crop((max(0, groups[0][0] - 4), 0, groups[0][1] + 6, row.height)).save(os.path.join(OUT, "ctl-view-kinematics.png"))
    right = groups[-1]                       # navigation icons + Export / Upload
    sub_cols = [c for c in cols if c >= right[0]]
    gs, s, p = [], sub_cols[0], sub_cols[0]
    for c in sub_cols[1:]:
        if c - p > 12:
            gs.append((s, p))
            s = c
        p = c
    gs.append((s, p))
    row.crop((gs[0][0] - 8, 0, gs[-2][1] + 8, row.height)).save(os.path.join(OUT, "ctl-plot-navigation.png"))
    row.crop((gs[-1][0] - 6, 0, gs[-1][1] + 1, row.height)).save(os.path.join(OUT, "ctl-export-upload.png"))
    undo = w.planning_modern.btn_undo
    if undo is not None and undo.isVisible():
        undo.grab().save(os.path.join(OUT, "ctl-undo.png"))
    for f in os.listdir(OUT):
        if f.endswith(".png"):
            Image.open(os.path.join(OUT, f)).convert("RGB").save(os.path.join(OUT, f[:-4] + ".webp"), "WEBP",
                                                                 quality=88, method=6)
            os.remove(os.path.join(OUT, f))
    print("webp:", len([f for f in os.listdir(OUT) if f.endswith('.webp')]), "files", flush=True)


QTimer.singleShot(1500, run)
app.exec()
