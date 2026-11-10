"""
Modern Status tab controls (fcn_create_gui/tab_status_modern.py) in the real TRACE window (Launch_ImGUI.MyApp):

  - axis pills grouped Lung Phantom / Motion Platform (Platform position, Individual axes) + G-code reference:
    pill <-> legacy checkbox both ways (also the blockSignals paths of the log / reference loaders), the plotted
    lines follow, pill colour = drawn curve colour, tooltips
  - section titles select / deselect all (Motion Platform acts on both subsections, only on shown pills)
  - Basic vs Advanced: both persisted startup states and toggling both ways; the legacy checkbox panel, the
    matplotlib toolbar, the 'Record Data Log' checkbox and the Load Log / Load G-code as Ref buttons never show
  - navigation row: Pan / Zoom drags on the canvas update the limit boxes (Auto off), Back / Forward, Reset ->
    Auto, Save image; limit boxes (decimal comma or point, Enter) survive render_status_plot redraws with live
    samples (handle_position_sample during a run) and with a loaded log (load_log_file_into_status)
  - Record button mirrors check_record_log; Record OFF during a run closes the log ('# End: record off')
  - no grey backgrounds in the axis panel / navigation row; Status page minimum size not larger than before
  - follow-up layout: side card = scrolling panel (Reference, Lung Phantom, Motion Platform, View limits (time /
    position boxes + Auto; Time interval / Ref. offset / Max Speed Adj in Advanced), Data log (folder, Set Folder;
    Advanced)) + a fixed footer (Clear Plot Data, Record; both modes, never scrolled away); the old row above the
    plot stays hidden; the bottom row has only the navigation icons
  - Auto-sync Speed / Max Speed Adj work as before by default (no popup, field shown in Advanced); the optional
    popup (stm.ASK_MAX_SPEED_ADJ_IN_POPUP = True, separate window): OK writes the value into input_max_speed_adj
    and turns Auto-sync on, Cancel leaves it off, turning it off asks nothing
  - fixes after review (checks named 'FIX'): Record visible in Basic and never scrolled away, Clear Plot Data
    resets boxes / Auto / history without a redraw, tri-state boxes on the clickable titles, title / heading
    alignment, one decimal sign (point), outline Clear button, Auto box text not greyed, 22 px nav icons,
    modernise_status_tab never raises
  - screenshots (ST_OUT folder) of the Status tab at 2048x1232 in Basic and Advanced mode with a loaded log
The user's configuration.json (persisted Advanced mode) is restored byte-identically at the end.

Run:  set QT_QPA_PLATFORM=offscreen & set PYTHONIOENCODING=utf-8 &
      C:\\Users\\gabri\\anaconda3\\envs\\TRACE\\python.exe scratch\\test_status_modern_ui.py
      (optional: set ST_OUT=<folder> for the screenshots; QT_QPA_PLATFORM=windows gives real fonts, not shown)
"""
import os
import sys
import json
import time
import math
import shutil
import tempfile
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PySide6.QtCore import Qt, QPoint, QPointF, QEvent, QCoreApplication
from PySide6.QtGui import QMouseEvent, QColor
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
from PySide6.QtTest import QTest

app = QApplication.instance() or QApplication(sys.argv)
for _k in ('warning', 'information', 'critical'):
    setattr(QMessageBox, _k, staticmethod(lambda *a, **k: QMessageBox.Ok))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)

from fcn_init.app_config import get_config_path

CFG = get_config_path('configuration.json', for_writing=True)
TMP = tempfile.mkdtemp(prefix="st_modern_")
OUT = os.environ.get('ST_OUT') or TMP
os.makedirs(OUT, exist_ok=True)
CFG_EXISTED = os.path.exists(CFG)
CFG_BACKUP = os.path.join(TMP, 'configuration.json.bak')
if CFG_EXISTED:
    shutil.copyfile(CFG, CFG_BACKUP)

RES = []
ERRS = []
sys.excepthook = lambda t, v, tb: (ERRS.append("".join(traceback.format_exception(t, v, tb))),
                                   print("EXC:", ERRS[-1], flush=True))


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f"  [{detail}]" if detail else ""), flush=True)


def pump(n=6):
    for _ in range(n):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def set_cfg_mode(adv):
    data = {}
    if os.path.exists(CFG):
        with open(CFG, 'r') as f:
            data = json.load(f)
    data['status_advanced_mode'] = bool(adv)
    with open(CFG, 'w') as f:
        json.dump(data, f, indent=4)


def restore_cfg():
    if CFG_EXISTED:
        shutil.copyfile(CFG_BACKUP, CFG)
    elif os.path.exists(CFG):
        os.remove(CFG)


import Launch_ImGUI
import fcn_create_gui.tab_status_modern as stm
POPUP_DEFAULT = stm.ASK_MAX_SPEED_ADJ_IN_POPUP      # the user asked for the popup: True by default
stm.ASK_MAX_SPEED_ADJ_IN_POPUP = False             # main windows: the opt-out path (behaves as before)
from fcn_monitor import fcn_duet


def new_window(adv, modern=True):
    set_cfg_mode(adv)
    saved = stm.modernise_status_tab
    if not modern:
        stm.modernise_status_tab = lambda self: None
    try:
        win = Launch_ImGUI.MyApp()
        app.setStyle('Fusion')
        win.setAttribute(Qt.WA_DontShowOnScreen, True)
        win.resize(2048, 1232)
        win.show()
        pump()
        win.tabModules.setCurrentIndex(1)
        pump(10)
    finally:
        stm.modernise_status_tab = saved
    # No Duet here: the dashboard timer / live poll stay quiet (samples are fed by hand below)
    try:
        win.status_polling_timer.stop()
    except Exception:
        pass
    try:
        win.status_fast_timer.stop()
    except Exception:
        pass
    return win


def close_window(win):
    try:
        win.close()
    except Exception:
        pass
    pump()


def min_hint(win):
    s = win.tab_status.minimumSizeHint()
    return s.width(), s.height()


def legacy_never_visible(win):
    names = ('status_checks_scroll', 'status_toolbar', 'check_record_log', 'button_load_log', 'button_load_gcode_ref',
             'log_folder_container')
    # (input_max_speed_adj is moved into the panel's Advanced block: checked separately)
    return all(getattr(win, n).isHidden() and not getattr(win, n).isVisible() for n in names)


BASIC_KEYS = ['X', 'Y', 'Z', 'LAT', 'SI', 'AP', 'Roll', 'Pitch']
ADV_ONLY = ['Yaw', 'A', 'B', 'C', 'D', "'a", "'c", "'e", "'f"]
ALL_KEYS = BASIC_KEYS + ADV_ONLY

try:
    # ------------------------------------------------------------------ 1. baseline (no modern controls)
    base = new_window(False, modern=False)
    check("baseline window has no modern controls", getattr(base, 'status_modern', None) is None)
    base_min = {}
    base_min[False] = min_hint(base)
    base.check_advanced_mode.setChecked(True)
    pump(6)
    base_min[True] = min_hint(base)
    base.check_advanced_mode.setChecked(False)
    pump(4)
    print("baseline Status page minimum size (Basic / Advanced):", base_min[False], base_min[True])
    close_window(base)
    restore_cfg()

    # ------------------------------------------------------------------ 2. startup in both persisted states
    for adv in (True, False):
        w0 = new_window(adv)
        st0 = getattr(w0, 'status_modern', None)
        check(f"startup {'Advanced' if adv else 'Basic'}: modern controls built", st0 is not None)
        check(f"startup {'Advanced' if adv else 'Basic'}: mode restored from configuration.json",
              w0.check_advanced_mode.isChecked() == adv)
        vis = {k: st0.pills[k].isVisible() for k in ALL_KEYS}
        exp = {k: (adv or k in BASIC_KEYS) for k in ALL_KEYS}
        check(f"startup {'Advanced' if adv else 'Basic'}: pills shown = today's checkbox set", vis == exp,
              str({k: v for k, v in vis.items() if v != exp[k]}))
        check(f"startup {'Advanced' if adv else 'Basic'}: 'Individual axes' section "
              f"{'shown' if adv else 'hidden'}", st0.sections['individual'][2].isVisible() == adv)
        check(f"startup {'Advanced' if adv else 'Basic'}: legacy panel / toolbar / record checkbox / Load buttons "
              f"hidden", legacy_never_visible(w0))
        check(f"startup {'Advanced' if adv else 'Basic'}: axis panel, Clear Plot Data, Record and view limits visible",
              st0.panel_scroll.isVisible() and st0.nav_row.isVisible() and w0.button_clear_plot.isVisible()
              and st0.btn_record.isVisible() and st0.x_from.isVisible() and st0.y_auto.isVisible())
        check(f"FIX startup {'Advanced' if adv else 'Basic'}: Record button visible (fixed footer, both modes)",
              st0.btn_record.isVisible() and st0.footer.isAncestorOf(st0.btn_record)
              and not st0.datalog_box.isAncestorOf(st0.btn_record))
        check(f"startup {'Advanced' if adv else 'Basic'}: Data log section (folder, Set Folder) and Time "
              f"interval / Ref. offset / Max Speed Adj {'shown' if adv else 'hidden'}",
              all(x.isVisible() == adv for x in (w0.PhOperFolder, w0.setPhOperFolder, w0.input_time_interval,
                                                 w0.input_ref_offset, w0.input_max_speed_adj)))
        mh = min_hint(w0)
        check(f"startup {'Advanced' if adv else 'Basic'}: Status page minimum size not larger than before",
              mh[0] <= base_min[adv][0] and mh[1] <= base_min[adv][1], f"{mh} vs {base_min[adv]}")
        close_window(w0)
        restore_cfg()

    # ------------------------------------------------------------------ 3. main window (starts in Basic)
    win = new_window(False)
    st = win.status_modern
    ax = win.ax_status
    canvas = win.statusCanvas
    render = lambda: fcn_duet.render_status_plot(win)
    check("render_status_plot is wrapped once (original kept)",
          getattr(fcn_duet.render_status_plot, '_stm_wrapper', False)
          and not getattr(fcn_duet.render_status_plot._stm_original, '_stm_wrapper', False))

    # sizes: the global QPushButton x1.5 scaling (MyApp.__init__) does not reach the lazily built Status tab
    check("pill / nav / record sizes are the module's own (not scaled x1.5); FIX: nav icons 22 px in 34 px buttons",
          st.pills['X'].height() == 28 and st.btn_pan.size().width() == 34 and st.btn_pan.size().height() == 34
          and st.btn_pan.iconSize().width() == 22
          and st.btn_record.height() == 32 and st.x_from.height() == 28 and st.nav_row.height() == 34,
          f"pill {st.pills['X'].height()} nav {st.btn_pan.size()} rec {st.btn_record.height()} box {st.x_from.height()}")

    check("Back / Forward disabled while there is no view history", not st.btn_back.isEnabled()
          and not st.btn_forward.isEnabled())

    # tooltips everywhere
    tips = [st.pills[k].toolTip() for k in ALL_KEYS] + [st.ref_pill.toolTip(), st.btn_record.toolTip()]
    tips += [t.toolTip() for t, _k, _b in st.sections.values()]
    tips += [b.toolTip() for b in (st.btn_reset, st.btn_back, st.btn_forward, st.btn_pan, st.btn_zoom, st.btn_save,
                                   st.x_from, st.x_to, st.y_from, st.y_to, st.x_auto, st.y_auto)]
    check("every pill, title, nav button, limit box and the Record button has a tooltip", all(t.strip() for t in tips))
    check("section titles explain select / deselect all",
          all("select / deselect all" in t.toolTip() for t, _k, _b in st.sections.values()),
          st.sections['platform'][0].toolTip())
    check("Motion Platform title tooltip mentions both subsections",
          "platform position" in st.sections['platform'][0].toolTip().lower()
          and "individual axes" in st.sections['platform'][0].toolTip().lower())
    check("Record tooltip names the file pattern and the folder",
          "log_DDMMYYYY_HH_MM_SS.csv" in st.btn_record.toolTip() and win.PhOperFolder.text() in st.btn_record.toolTip())

    # pill colours = legacy checkbox colours (the drawn curve colours are checked after data below)
    check("pills start in the legacy checkbox state",
          all(st.pills[k].isChecked() == st.pill_cb[k].isChecked() for k in ALL_KEYS))

    # ---------------------------------------------- live samples during a run (real handle_position_sample)
    log_dir = os.path.join(TMP, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    win.PhOperFolder.setText(log_dir)
    win.duet_connected = True
    win.status_stopped = False
    win.run_active = True
    win.run_t0 = time.perf_counter() - 100.0
    win.run_device = "Lung Phantom"
    win.active_log_file = None
    win._log_open_failed = False
    win.check_record_log.setChecked(True)
    pump()
    check("Record button shows ON (green) like check_record_log",
          st.btn_record.isChecked() and 'ON' in st.btn_record.text() and '#2e7d32' in st.btn_record.styleSheet())

    def sample(t, x, y=0.0, z=0.0, p=0):
        fcn_duet.handle_position_sample(win, {'t': win.run_t0 + t, 'real': {'X': x, 'Y': y, 'Z': z},
                                              'probe': p, 'status': 'P'})

    for i in range(0, 120):
        t = 0.1 * i
        sample(t, 5.0 * math.sin(t), 2.0 * math.cos(t), 0.5 * t, 1000 if 3.0 <= t < 4.0 else 0)
    render()
    pump()
    check("a run log is open while recording", win.active_log_file is not None)
    lines = win.status_plot_lines
    check("live X / Y / Z curves drawn", all(k in lines and lines[k].get_visible() for k in ('X', 'Y', 'Z')))
    from matplotlib.colors import to_hex
    check("pill colour = drawn curve colour (X, Y, Z)",
          all(st.pill_color[k] == to_hex(lines[k].get_color()).lower() for k in ('X', 'Y', 'Z')),
          str({k: (st.pill_color[k], to_hex(lines[k].get_color())) for k in ('X', 'Y', 'Z')}))
    auto_x = tuple(ax.get_xlim())
    check("Auto: live window from render_status_plot", abs(auto_x[0]) < 1e-9 and abs(auto_x[1] - 60.0) < 1e-9,
          str(auto_x))
    check("Auto boxes show the current limits", st.x_from.text() == stm.format_number(auto_x[0], auto_x[1] - auto_x[0])
          and st.x_to.text() == stm.format_number(auto_x[1], auto_x[1] - auto_x[0]) and st.x_auto.isChecked())

    # pill click -> legacy checkbox -> line hidden / shown
    QTest.mouseClick(st.pills['Y'], Qt.LeftButton)
    pump()
    check("pill click (Y off) unchecks the legacy checkbox", not win.status_check_Y.isChecked())
    check("... and the Y curve is hidden", not lines['Y'].get_visible())
    QTest.mouseClick(st.pills['Y'], Qt.LeftButton)
    pump()
    check("pill click (Y on) checks the legacy checkbox and shows the curve",
          win.status_check_Y.isChecked() and lines['Y'].get_visible())
    # legacy -> pill (signal path)
    win.status_check_Z.setChecked(False)
    render()
    check("programmatic legacy change (Z off) updates the pill", not st.pills['Z'].isChecked()
          and not lines['Z'].get_visible())
    win.status_check_Z.setChecked(True)
    check("programmatic legacy change (Z on) updates the pill at once", st.pills['Z'].isChecked())
    # legacy -> pill with blocked signals (as the loaders do): synced on the next redraw
    win.status_check_LAT.blockSignals(True)
    win.status_check_LAT.setChecked(True)
    win.status_check_LAT.blockSignals(False)
    render()
    check("blocked-signal legacy change (LAT on) reaches the pill on the redraw", st.pills['LAT'].isChecked())
    win.status_check_LAT.setChecked(False)
    render()

    # titles (Basic: only the shown pills)
    def click_title(name):
        QTest.mouseClick(st.sections[name][0], Qt.LeftButton)
        pump()

    states = lambda keys: [win_cb.isChecked() for win_cb in (st.pill_cb[k] for k in keys)]
    click_title('phantom')
    check("Lung Phantom title: all on -> all off", states(['X', 'Y', 'Z']) == [False] * 3
          and not any(st.pills[k].isChecked() for k in 'XYZ') and not lines['X'].get_visible())
    click_title('phantom')
    check("Lung Phantom title: all off -> all on", states(['X', 'Y', 'Z']) == [True] * 3
          and all(st.pills[k].isChecked() for k in 'XYZ') and lines['X'].get_visible())
    QTest.mouseClick(st.pills['Y'], Qt.LeftButton)
    pump()
    click_title('phantom')
    check("Lung Phantom title: partly on -> all on", states(['X', 'Y', 'Z']) == [True] * 3)
    win.status_check_A.setChecked(False)
    click_title('platform')
    shown_plat = ['LAT', 'SI', 'AP', 'Roll', 'Pitch']
    check("Basic, Motion Platform title: selects the shown platform curves",
          states(shown_plat) == [True] * 5 and all(st.pills[k].isChecked() for k in shown_plat))
    check("Basic, Motion Platform title: hidden axes (Yaw, A ...) untouched",
          states(['Yaw', 'A', 'B', "'a"]) == [False] * 4)
    click_title('platform')
    check("Basic, Motion Platform title: all on -> all off", states(shown_plat) == [False] * 5)
    click_title('position')
    check("Platform position subtitle selects its shown pills", states(shown_plat) == [True] * 5)
    click_title('position')
    check("Platform position subtitle deselects them", states(shown_plat) == [False] * 5)

    # FIX: visible cue on the clickable titles = tri-state box (none / some / all of the SHOWN curves)
    def tstate(name):
        return st._title_state.get(st.sections[name][0])
    check("FIX: clickable titles carry a tri-state box icon; plain headings (Reference, View limits) are labels",
          all(not t.icon().isNull() and t.toolButtonStyle() == Qt.ToolButtonTextBesideIcon
              for t, _k, _b in st.sections.values())
          and type(st.ref_title).__name__ == 'QLabel')
    check("FIX: title box state: Lung Phantom all on -> 'all', platform all off -> 'none'",
          tstate('phantom') == 'all' and tstate('platform') == 'none' and tstate('position') == 'none',
          str({n: tstate(n) for n in st.sections}))
    win.status_check_SI.setChecked(True)                 # programmatic legacy change: box follows at once
    check("FIX: title box state follows a legacy change ('some')", tstate('position') == 'some'
          and tstate('platform') == 'some')
    click_title('position')
    check("FIX: Basic: all shown platform curves on -> Motion Platform box 'all' (hidden Yaw / A.. ignored)",
          tstate('position') == 'all' and tstate('platform') == 'all' and not win.status_check_Yaw.isChecked())
    click_title('platform')
    check("FIX: title click off -> box 'none'", tstate('platform') == 'none' and tstate('position') == 'none')
    icons_differ = (st._group_icons['none'].pixmap(16).toImage() != st._group_icons['all'].pixmap(16).toImage()
                    and st._group_icons['some'].pixmap(16).toImage() != st._group_icons['none'].pixmap(16).toImage())
    check("FIX: the three box icons are drawn and differ", icons_differ)
    check("FIX: tooltips explain the box", all("box in front of the title" in t.toolTip()
                                               for t, _k, _b in st.sections.values()))

    # FIX: headings line up: clickable titles (icon) and plain headings start at the same x in the panel
    def left_ink(wd):
        img = wd.grab().toImage()
        for xx in range(img.width()):
            for yy in range(img.height()):
                c = img.pixelColor(xx, yy)
                if min(c.red(), c.green(), c.blue()) < 170:
                    return wd.mapTo(st.panel, QPoint(xx, 0)).x()
        return None
    lefts = {n: left_ink(wd) for n, wd in (('Reference', st.ref_title), ('Lung Phantom', st.sections['phantom'][0]),
                                           ('Motion Platform', st.sections['platform'][0]))}
    check("FIX: 'Reference', 'Lung Phantom', 'Motion Platform' headings start within 2 px of each other",
          None not in lefts.values() and max(lefts.values()) - min(lefts.values()) <= 2, str(lefts))
    check("FIX: Position limit label names its unit", any(
        lb.text() == "Position (mm / deg)" for lb in st.panel.findChildren(type(st.ref_title))))

    # Advanced mode toggling (real click on the checkbox)
    QTest.mouseClick(win.check_advanced_mode, Qt.LeftButton,
                     pos=QPoint(10, win.check_advanced_mode.height() // 2))
    pump(6)
    check("Advanced via click: mode on", win.check_advanced_mode.isChecked())
    check("Advanced: every pill shown", all(st.pills[k].isVisible() for k in ALL_KEYS))
    check("Advanced: 'Individual axes' section shown", st.sections['individual'][2].isVisible())
    check("Advanced: legacy panel / toolbar / record checkbox / Load buttons stay hidden", legacy_never_visible(win))
    check("Advanced: Set Folder / folder / Record / Max Speed Adj shown in the panel, old row and Load buttons gone",
          not win.log_folder_container.isVisible() and win.setPhOperFolder.isVisible() and win.PhOperFolder.isVisible()
          and st.btn_record.isVisible() and not win.button_load_log.isVisible()
          and not win.button_load_gcode_ref.isVisible() and win.input_max_speed_adj.isVisible()
          and st.panel.isAncestorOf(win.input_max_speed_adj))

    # ---------------------------------------------- follow-up: positions in the side panel
    def top(wd):
        return wd.mapTo(st.panel, QPoint(0, 0)).y()

    def bottom(wd):
        return top(wd) + wd.height()

    moved = [st.x_from, st.x_to, st.x_auto, st.y_from, st.y_to, st.y_auto, win.input_time_interval,
             win.input_ref_offset, win.input_max_speed_adj, win.PhOperFolder, win.setPhOperFolder]
    check("follow-up: view limits, Time interval / Ref. offset / Max Speed Adj, folder and Set Folder are in "
          "the scrolling side panel", all(st.panel.isAncestorOf(x) for x in moved))
    check("FIX: Clear Plot Data and Record are in the fixed footer of the side card (outside the scroll area)",
          all(st.footer.isAncestorOf(x) and not st.panel_scroll.isAncestorOf(x)
              for x in (win.button_clear_plot, st.btn_record))
          and st.side_card.isAncestorOf(st.footer) and st.side_card.isAncestorOf(st.panel_scroll))
    order = [st.sections['individual'][2], st.x_from, st.y_from, win.input_time_interval,
             win.input_ref_offset, win.input_max_speed_adj, win.PhOperFolder, win.setPhOperFolder]
    tops = [top(x) for x in order]
    check("follow-up (Advanced): top to bottom = Individual axes, Time, Position, Time interval, "
          "Ref. offset, Max Speed Adj, folder, Set Folder",
          all(bottom(a) <= top(b) for a, b in zip(order, order[1:])), str(tops))

    def card_y(wd, y=0):
        return wd.mapTo(st.side_card, QPoint(0, y)).y()
    check("FIX: footer below the scroll area, Clear Plot Data above Record, Record inside the card",
          card_y(st.panel_scroll, st.panel_scroll.height()) <= card_y(win.button_clear_plot)
          and card_y(win.button_clear_plot, win.button_clear_plot.height()) <= card_y(st.btn_record)
          and card_y(st.btn_record, st.btn_record.height()) <= st.side_card.height(),
          f"{card_y(win.button_clear_plot)} {card_y(st.btn_record)} {st.side_card.height()}")
    # Record never below the fold: at the window's own minimum height too (Advanced = tallest panel)
    old_size = win.size()
    win.resize(win.width(), win.minimumSizeHint().height())
    pump(6)
    rb = card_y(st.btn_record, st.btn_record.height())
    check("FIX: at the window's minimum height (Advanced) Record and Clear Plot Data stay fully visible in the card",
          st.btn_record.isVisible() and rb <= st.side_card.height() and card_y(win.button_clear_plot) >= 0
          and st.btn_record.visibleRegion().boundingRect().height() == st.btn_record.height(),
          f"window {win.height()} card {st.side_card.height()} record bottom {rb} "
          f"scroll max {st.panel_scroll.verticalScrollBar().maximum()}")
    win.resize(old_size)
    pump(6)
    check("follow-up: time / position boxes fit the panel (from + to side by side, Auto on the title row)",
          top(st.x_from) == top(st.x_to) and top(st.y_from) == top(st.y_to) and bottom(st.x_auto) <= top(st.x_from)
          and st.x_to.mapTo(st.panel, QPoint(st.x_to.width(), 0)).x() <= st.panel.width())
    REAL_FONTS = QApplication.platformName() != 'offscreen'      # offscreen font metrics are not realistic
    from PySide6.QtWidgets import QStyle as _QStyle
    # narrowest viewport: inside the card's 2 px margins, with the vertical scroll bar shown
    worst_vp = (st.side_card.width() - 4 - st.panel_scroll.style().pixelMetric(_QStyle.PM_ScrollBarExtent))
    check("follow-up: the side card width is unchanged (236)" + (" and its content fits it (no horizontal overflow)"
                                                                 if REAL_FONTS else " (content width: real-font run only)"),
          st.side_card.width() == 236 and (not REAL_FONTS or st.panel.minimumSizeHint().width()
                                           <= worst_vp),
          f"{st.side_card.width()} {st.panel.minimumSizeHint().width()} worst-case viewport {worst_vp}")
    from PySide6.QtWidgets import QLineEdit as _QLE, QAbstractButton as _QAB
    check("follow-up: the bottom row holds only the navigation icons (no boxes)",
          not st.nav_row.findChildren(_QLE) and len(st.nav_row.findChildren(_QAB)) == 6)
    check("follow-up: the old row above the plot is hidden: the plot starts at the top of the plot card",
          win.statusCanvas.mapTo(st.plot_box, QPoint(0, 0)).y() < 20
          and st.side_card.mapTo(st.plot_box, QPoint(0, 0)).y() < 20,
          str(win.statusCanvas.mapTo(st.plot_box, QPoint(0, 0)).y()))
    vs = st.panel_scroll.verticalScrollBar()
    check("follow-up: the panel scrolls vertically when needed (vertical bar as needed, no horizontal bar)",
          st.panel_scroll.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded
          and st.panel_scroll.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
          and (st.panel.height() <= st.panel_scroll.viewport().height() or vs.maximum() > 0))

    # ---------------------------------------------- FIX: Auto-sync / Max Speed Adj as before (no popup by default)
    from PySide6.QtWidgets import QInputDialog
    DLG = []
    real_get_double = QInputDialog.getDouble

    def fake_get_double(answer):
        def f(parent, title, label, value, lo, hi, dec, *a, **k):
            DLG.append({'value': value, 'lo': lo, 'hi': hi, 'dec': dec, 'label': label,
                        'checked_during': win.check_auto_sync.isChecked()})
            return answer
        return staticmethod(f)

    def click_box(cb):
        QTest.mouseClick(cb, Qt.LeftButton, pos=QPoint(8, cb.height() // 2))
        pump(4)

    try:
        check("popup for the max speed adjustment is ON by default (user request); main window built with it off "
              "(opt-out path)", POPUP_DEFAULT is True and st.ask_max_adj is False)
        win.input_max_speed_adj.setText("20")
        QInputDialog.getDouble = fake_get_double((35.5, True))
        click_box(win.check_auto_sync)
        check("FIX: Auto-sync click -> on at once, no popup, Max Speed Adj unchanged and visible, manual speed "
              "controls disabled (existing handler)",
              not DLG and win.check_auto_sync.isChecked() and win.input_max_speed_adj.text() == "20"
              and win.input_max_speed_adj.isVisible() and not win.labelSf.isEnabled(), str(DLG))
        win.input_max_speed_adj.setFocus()
        win.input_max_speed_adj.selectAll()
        QTest.keyClicks(win.input_max_speed_adj, "35")
        QTest.keyClick(win.input_max_speed_adj, Qt.Key_Return)
        pump()
        check("FIX: Max Speed Adj can be changed while Auto-sync is on (as before)",
              win.input_max_speed_adj.text() == "35" and win.check_auto_sync.isChecked())
        click_box(win.check_auto_sync)
        check("FIX: Auto-sync off -> off, no popup, manual speed controls enabled again",
              not DLG and not win.check_auto_sync.isChecked() and win.labelSf.isEnabled())
        win.check_auto_sync.setChecked(True)
        pump(4)
        check("FIX: programmatic Auto-sync on -> stays on, no popup", not DLG and win.check_auto_sync.isChecked())
        win.check_auto_sync.setChecked(False)
        pump(4)
        win.input_max_speed_adj.setText("20")
        check("FIX: Time interval / Ref. offset / Max Speed Adj share the limit boxes' look (style only, 28 px)",
              all(le.styleSheet() == stm.FIELD_STYLE and le.height() == 28
                  for le in (win.input_time_interval, win.input_ref_offset, win.input_max_speed_adj)))
    finally:
        QInputDialog.getDouble = real_get_double

    # optional item 7 (popup) in a window of its own: the original checks, unchanged
    main_win = win
    stm.ASK_MAX_SPEED_ADJ_IN_POPUP = True
    pw = None
    try:
        pw = new_window(True)
        win = pw
        check("popup option: Max Speed Adj hidden, Auto-sync hooked", pw.status_modern.ask_max_adj
              and not pw.input_max_speed_adj.isVisible())
        win.input_max_speed_adj.setText("20")
        QInputDialog.getDouble = fake_get_double((35.5, True))
        click_box(win.check_auto_sync)
        check("Auto-sync on -> one popup, prefilled with the current value (20), range as the field (1-200, 1 dec.)",
              len(DLG) == 1 and DLG[0]['value'] == 20.0 and DLG[0]['lo'] == 1.0 and DLG[0]['hi'] == 200.0
              and DLG[0]['dec'] == 1 and 'Max speed adjustment (%)' in DLG[0]['label'], str(DLG))
        check("Auto-sync stays off while the popup is open (process_auto_sync_speed cannot use an old value)",
              DLG and DLG[0]['checked_during'] is False)
        check("popup OK: value written to input_max_speed_adj, Auto-sync on, manual speed controls disabled",
              win.input_max_speed_adj.text() == "35.5" and float(win.input_max_speed_adj.text()) == 35.5
              and win.check_auto_sync.isChecked() and not win.labelSf.isEnabled(),
              f"{win.input_max_speed_adj.text()} {win.check_auto_sync.isChecked()}")
        click_box(win.check_auto_sync)
        check("Auto-sync off -> no popup, off, manual speed controls enabled again",
              len(DLG) == 1 and not win.check_auto_sync.isChecked() and win.labelSf.isEnabled())
        QInputDialog.getDouble = fake_get_double((80.0, False))
        click_box(win.check_auto_sync)
        check("popup Cancel: Auto-sync stays off, value unchanged, no second popup",
              len(DLG) == 2 and DLG[1]['value'] == 35.5 and not win.check_auto_sync.isChecked()
              and win.input_max_speed_adj.text() == "35.5" and win.labelSf.isEnabled(), str(DLG[-1:]))
        QInputDialog.getDouble = fake_get_double((12.0, True))
        win.check_auto_sync.setChecked(True)            # programmatic on: asks too
        pump(4)
        check("programmatic Auto-sync on also asks (OK -> 12)", len(DLG) == 3 and win.check_auto_sync.isChecked()
              and win.input_max_speed_adj.text() == "12")
        win.check_auto_sync.setChecked(False)           # as process_auto_sync_speed does on a limit breach
        pump(4)
        check("Auto-sync turned off by the code: no popup", len(DLG) == 3 and not win.check_auto_sync.isChecked())
    finally:
        QInputDialog.getDouble = real_get_double
        stm.ASK_MAX_SPEED_ADJ_IN_POPUP = False
        win = main_win
        if pw is not None:
            close_window(pw)
        set_cfg_mode(True)
    check("Advanced: min size not larger than before", min_hint(win)[0] <= base_min[True][0]
          and min_hint(win)[1] <= base_min[True][1], f"{min_hint(win)} vs {base_min[True]}")
    plat_all = ['LAT', 'SI', 'AP', 'Roll', 'Pitch', 'Yaw', 'A', 'B', 'C', 'D', "'a", "'c", "'e", "'f"]
    click_title('platform')
    check("Advanced, Motion Platform title selects both subsections (14 curves)", states(plat_all) == [True] * 14
          and all(st.pills[k].isChecked() for k in plat_all))
    click_title('platform')
    check("Advanced, Motion Platform title deselects both subsections", states(plat_all) == [False] * 14)
    click_title('individual')
    check("Individual axes subtitle selects only A..'f",
          states(['A', 'B', 'C', 'D', "'a", "'c", "'e", "'f"]) == [True] * 8 and states(shown_plat + ['Yaw']) == [False] * 6)
    win.check_advanced_mode.setChecked(False)
    pump(6)
    check("back to Basic: Yaw / individual pills hidden, legacy widgets hidden",
          not any(st.pills[k].isVisible() for k in ADV_ONLY) and legacy_never_visible(win)
          and not st.sections['individual'][2].isVisible())
    check("Basic: min size not larger than before", min_hint(win)[0] <= base_min[False][0]
          and min_hint(win)[1] <= base_min[False][1], f"{min_hint(win)} vs {base_min[False]}")
    check("Basic: the hidden individual axes are not drawn (as before)",
          not any(win.status_plot_lines.get(k) is not None and win.status_plot_lines[k].get_visible()
                  for k in ['A', 'B', "'a"]))
    win.check_advanced_mode.setChecked(True)
    pump(4)
    win.check_advanced_mode.setChecked(False)
    pump(4)
    check("several Basic <-> Advanced toggles: legacy widgets never visible", legacy_never_visible(win))
    for k in ['A', 'B', 'C', 'D', "'a", "'c", "'e", "'f"]:
        st.pill_cb[k].setChecked(False)
    render()

    # ---------------------------------------------- manual limits survive live redraws
    QTest.mouseClick(st.x_from, Qt.LeftButton)
    st.x_from.selectAll()
    QTest.keyClicks(st.x_from, "2,5")
    QTest.keyClick(st.x_from, Qt.Key_Return)
    st.x_to.setFocus()
    st.x_to.selectAll()
    QTest.keyClicks(st.x_to, "8.25")
    QTest.keyClick(st.x_to, Qt.Key_Return)
    pump()
    check("time limits typed (decimal comma and point) applied", tuple(ax.get_xlim()) == (2.5, 8.25), str(ax.get_xlim()))
    check("FIX: one decimal sign on display: '2,5' typed is shown as '2.5' (as the plot ticks), whatever the locale",
          st.x_from.text() == "2.5" and st.x_to.text() == "8.25" and stm.format_number(-5.01, 10) == "-5.01",
          f"{st.x_from.text()} {st.x_to.text()}")
    check("FIX: manual limit boxes bold blue, Auto boxes dark grey #37474f (not placeholder-like)",
          st.x_from.styleSheet() == stm.LIMIT_STYLE_MANUAL and '#37474f' in stm.LIMIT_STYLE_AUTO
          and '#78909c' not in stm.LIMIT_STYLE_AUTO)
    check("Time Auto switched off", not st.x_auto.isChecked() and st.manual_x == (2.5, 8.25))
    st.y_from.setFocus()
    st.y_from.selectAll()
    QTest.keyClicks(st.y_from, "-3")
    QTest.keyClick(st.y_from, Qt.Key_Return)
    st.y_to.setFocus()
    st.y_to.selectAll()
    QTest.keyClicks(st.y_to, "4,5")
    QTest.keyClick(st.y_to, Qt.Key_Return)
    pump()
    check("position limits typed applied", tuple(ax.get_ylim()) == (-3.0, 4.5) and not st.y_auto.isChecked(),
          str(ax.get_ylim()))
    for i in range(120, 900):                 # 78 s more: the live window would jump to [30, 90] and beyond
        t = 0.1 * i
        sample(t, 5.0 * math.sin(t), 2.0 * math.cos(t), 0.5 * t)
        if i % 50 == 0:
            render()
    render()
    pump()
    check("manual limits survive live samples + redraws",
          tuple(ax.get_xlim()) == (2.5, 8.25) and tuple(ax.get_ylim()) == (-3.0, 4.5),
          f"{ax.get_xlim()} {ax.get_ylim()}")
    QTest.mouseClick(st.pills['Y'], Qt.LeftButton)        # a pill redraw too
    pump()
    check("manual limits survive a pill redraw", tuple(ax.get_xlim()) == (2.5, 8.25))
    QTest.mouseClick(st.pills['Y'], Qt.LeftButton)
    pump()
    bad_before = st.x_from.text()
    st.x_from.setFocus()
    st.x_from.selectAll()
    QTest.keyClicks(st.x_from, "abc")
    QTest.keyClick(st.x_from, Qt.Key_Return)
    pump()
    check("FIX Basic: view limit boxes, Clear Plot Data and Record usable in the side card", st.x_from.isVisible()
          and win.button_clear_plot.isVisible() and st.btn_record.isVisible())
    check("a non-number is refused (box shows the limit again)", tuple(ax.get_xlim()) == (2.5, 8.25)
          and st.x_from.text() == bad_before, st.x_from.text())
    # Auto y with a manual time range: fits the shown curves inside that range
    QTest.mouseClick(st.y_auto, Qt.LeftButton)
    pump()
    yl = ax.get_ylim()
    check("Position Auto on: y fits the curves inside the manual time range",
          st.y_auto.isChecked() and st.manual_y is None and yl[0] < -1.0 and yl[1] > 4.0 and yl[1] < 10.0, str(yl))
    QTest.mouseClick(st.x_auto, Qt.LeftButton)
    pump()
    xl = ax.get_xlim()
    check("Time Auto on: back to the live window", st.x_auto.isChecked() and st.manual_x is None
          and abs(xl[1] - xl[0] - 60.0) < 1e-6 and xl[0] <= 89.9 <= xl[1], str(xl))
    check("live probe shading kept (red detector span drawn)", len(getattr(win, '_probe_span_patches', [])) >= 1)

    # ---------------------------------------------- Record button: OFF closes the run log
    win.check_advanced_mode.setChecked(True)            # Record is shown in both modes (footer)
    pump(4)
    check("several toggles: the old row stays hidden", legacy_never_visible(win) and st.btn_record.isVisible())
    log_path = win.active_log_filepath
    QTest.mouseClick(st.btn_record, Qt.LeftButton)
    pump()
    check("Record button click -> check_record_log off", not win.check_record_log.isChecked())
    check("Record button shows OFF in red", 'OFF' in st.btn_record.text() and '#c62828' in st.btn_record.styleSheet()
          and not st.btn_record.isChecked())
    check("'record off' closed the run log", win.active_log_file is None)
    with open(log_path, encoding='utf-8') as f:
        log_lines = f.read().splitlines()
    check("log ends with '# End: record off'", log_lines[-1].startswith('# End: record off'), log_lines[-1])
    sample(90.0, 1.0)
    check("no new log while recording is off", win.active_log_file is None)
    win.check_record_log.setChecked(True)
    pump()
    check("programmatic check_record_log on -> button ON (green)", st.btn_record.isChecked()
          and 'ON' in st.btn_record.text())
    sample(90.1, 1.0)
    check("recording again opens a new log", win.active_log_file is not None and win.active_log_filepath != log_path)
    win.check_record_log.setChecked(False)
    pump()
    check("programmatic check_record_log off -> button OFF and log closed", not st.btn_record.isChecked()
          and win.active_log_file is None)
    QTest.mouseClick(st.btn_record, Qt.LeftButton)
    pump()
    check("Record button click -> ON again", win.check_record_log.isChecked() and st.btn_record.isChecked())
    fcn_duet.end_run(win, "job finished")
    win.duet_connected = False

    # ---------------------------------------------- loaded log (the hidden Load Log button's code path)
    plat_log = os.path.join(TMP, 'platform_log.csv')
    with open(plat_log, 'w', encoding='utf-8') as f:
        f.write("Time_s,Pos_LAT_mm,Pos_SI_mm,Pos_AP_mm,Pos_Roll_deg,Pos_Pitch_deg,Pos_Yaw_deg,"
                "Pos_A_mm,Pos_B_mm,Pos_C_mm,Pos_D_mm,Pos_'e_mm,Pos_'f_mm,Pos_'a_mm,Pos_'c_mm,Probe\n")
        for i in range(0, 1201):
            t = 0.05 * i
            si = 10.0 * math.sin(2 * math.pi * t / 4.0)
            ap = 4.0 * math.sin(2 * math.pi * t / 4.0 + 0.6)
            lat = 2.0 * math.sin(2 * math.pi * t / 8.0)
            probe = 1000 if (8 <= t < 11 or 30 <= t < 33) else (-1000 if 20 <= t < 22 else (2000 if 45 <= t < 46 else 0))
            vals = [t, lat, si, ap, 0.8 * math.sin(t / 3), 0.5 * math.cos(t / 3), 0.2 * math.sin(t / 5),
                    35 + si / 2, 35 + si / 2.2, 35 + ap / 2, 35 + ap / 2.4, 50 + lat, 50 - lat, 25 + si / 4, 25 - si / 4,
                    probe]
            f.write(",".join(f"{v:.4f}" if not isinstance(v, int) else str(v) for v in vals) + "\n")
    win.check_advanced_mode.setChecked(True)
    pump(4)
    st.manual_x = (1.0, 2.0)                     # stale manual limits from the live view
    fcn_duet.load_log_file_into_status(win, plat_log)
    pump()
    check("loading a log: new data set -> both axes Auto", st.manual_x is None and st.manual_y is None
          and st.x_auto.isChecked() and st.y_auto.isChecked())
    check("loaded log shown whole (loader's view kept)", abs(ax.get_xlim()[0]) < 1e-9 and abs(ax.get_xlim()[1] - 60.0) < 1e-6,
          str(ax.get_xlim()))
    check("pills follow the loader (blocked signals): platform curves on, phantom off",
          all(st.pills[k].isChecked() for k in plat_all) and not any(st.pills[k].isChecked() for k in 'XYZ'))
    lines = win.status_plot_lines
    check("pill colour = drawn curve colour for all 14 platform curves",
          all(st.pill_color[k] == to_hex(lines[k].get_color()).lower() for k in plat_all))
    check("boxes show the loaded log's limits", st.x_to.text() == stm.format_number(60.0, 60.0))
    st.x_from.setFocus()
    st.x_from.selectAll()
    QTest.keyClicks(st.x_from, "10")
    QTest.keyClick(st.x_from, Qt.Key_Return)
    st.x_to.setFocus()
    st.x_to.selectAll()
    QTest.keyClicks(st.x_to, "25,5")
    QTest.keyClick(st.x_to, Qt.Key_Return)
    pump()
    for k in ['A', 'B', 'C', 'D', "'a", "'c", "'e", "'f"]:      # raw motor axes off: SI (+-10 mm) is the widest left
        QTest.mouseClick(st.pills[k], Qt.LeftButton)
        pump(2)
    render()
    render()
    check("loaded log: manual time range survives pill clicks / redraws", tuple(ax.get_xlim()) == (10.0, 25.5),
          str(ax.get_xlim()))
    yl = ax.get_ylim()
    check("loaded log: Auto y fitted to the shown curves in 10-25,5 s", -14 < yl[0] < -9 and 9 < yl[1] < 14, str(yl))
    win.input_time_interval.setText("30")            # a legacy control that redraws too
    pump()
    check("loaded log: manual range survives a Time interval redraw", tuple(ax.get_xlim()) == (10.0, 25.5))
    win.input_time_interval.setText("60")
    pump()
    key = getattr(win, '_probe_key', None)
    key_labels = [t.get_text() for t in key.get_texts()] if key is not None else []
    check("probe colour key lists only classes in the manual range (detector, wait)",
          any('Detector' in s for s in key_labels) and any('Waiting' in s for s in key_labels)
          and not any('Release' in s for s in key_labels), str(key_labels))

    # ---------------------------------------------- reference pill (auto-loads the job's G-code)
    gcode_text = "G90\nG1 F600 A35 B35 C35 D35 'e50 'f50 'a25 'c25\nG1 F300 A40 B40 C35 D35\nG4 P500\nG1 F300 A35 B35\n"
    calls = []
    real_auto = fcn_duet.auto_load_current_gcode_reference

    def fake_auto(self, filename=None, force=False):
        calls.append(filename)
        self.status_reference_data = fcn_duet.load_and_parse_gcode_reference(self, gcode_text)
        self._loaded_ref_filename = 'job.gcode'
        return self.status_reference_data is not None

    fcn_duet.auto_load_current_gcode_reference = fake_auto
    try:
        win.status_reference_data = None
        QTest.mouseClick(st.ref_pill, Qt.LeftButton)
        pump()
        check("reference pill -> check_show_reference on, job G-code auto-loaded",
              win.check_show_reference.isChecked() and len(calls) == 1 and win.status_reference_data is not None)
        check("reference lines drawn (dashed)", any(l.get_visible() and l.get_linestyle() == '--'
                                                   for l in win.status_ref_lines.values()))
        QTest.mouseClick(st.ref_pill, Qt.LeftButton)
        pump()
        check("reference pill off -> legacy off, reference lines hidden", not win.check_show_reference.isChecked()
              and not any(l.get_visible() for l in win.status_ref_lines.values()))
        win.check_show_reference.blockSignals(True)          # as the Start of a job does
        win.check_show_reference.setChecked(True)
        win.check_show_reference.blockSignals(False)
        render()
        check("blocked-signal reference change reaches the pill on the redraw", st.ref_pill.isChecked())
        win.check_show_reference.setChecked(False)
        check("reference legacy off -> pill off", not st.ref_pill.isChecked())
    finally:
        fcn_duet.auto_load_current_gcode_reference = real_auto

    # ---------------------------------------------- navigation: pan / zoom drags, back / forward, reset
    QTest.mouseClick(st.btn_reset, Qt.LeftButton)
    pump()
    check("Reset view -> Auto on both axes", st.manual_x is None and st.manual_y is None
          and st.x_auto.isChecked() and st.y_auto.isChecked())
    check("Reset view -> whole log shown again", abs(ax.get_xlim()[0]) < 1e-9 and abs(ax.get_xlim()[1] - 60.0) < 1e-6,
          str(ax.get_xlim()))
    canvas.draw()
    pump()

    def to_qt(x, y):
        dpr = getattr(canvas, 'device_pixel_ratio', 1.0) or 1.0
        dx, dy = ax.transData.transform((x, y))
        return QPointF(dx / dpr, (canvas.figure.bbox.height - dy) / dpr)

    def mouse(kind, pos, buttons):
        ev = QMouseEvent(kind, pos, canvas.mapToGlobal(pos), Qt.LeftButton if kind != QEvent.MouseMove else Qt.NoButton,
                         buttons, Qt.NoModifier)
        QApplication.sendEvent(canvas, ev)

    def drag(p0, p1):
        mouse(QEvent.MouseButtonPress, p0, Qt.LeftButton)
        for k in range(1, 6):
            mouse(QEvent.MouseMove, QPointF(p0.x() + (p1.x() - p0.x()) * k / 5, p0.y() + (p1.y() - p0.y()) * k / 5),
                  Qt.LeftButton)
        mouse(QEvent.MouseButtonRelease, p1, Qt.NoButton)
        pump(4)

    QTest.mouseClick(st.btn_pan, Qt.LeftButton)
    pump()
    check("Pan button -> matplotlib pan mode, button lit", st._nav_mode() == 'pan/zoom' and st.btn_pan.isChecked()
          and not st.btn_zoom.isChecked())
    x0, y0 = ax.get_xlim(), ax.get_ylim()
    drag(to_qt(30, 0), to_qt(20, 3))
    x1, y1 = ax.get_xlim(), ax.get_ylim()
    check("pan drag moved the view", x1[0] > x0[0] + 5 and y1[0] < y0[0], f"{x0}->{x1}, {y0}->{y1}")
    check("after pan: Auto off on both axes, boxes show the panned limits",
          not st.x_auto.isChecked() and not st.y_auto.isChecked() and st.manual_x == tuple(x1)
          and st.x_from.text() == stm.format_number(x1[0], x1[1] - x1[0])
          and st.y_to.text() == stm.format_number(y1[1], y1[1] - y1[0]),
          f"{st.x_from.text()} {st.y_to.text()} {x1} {y1}")
    render()
    check("panned view survives a redraw", tuple(ax.get_xlim()) == tuple(x1) and tuple(ax.get_ylim()) == tuple(y1))
    QTest.mouseClick(st.btn_zoom, Qt.LeftButton)
    pump()
    check("Zoom button -> zoom mode (pan off)", st._nav_mode() == 'zoom rect' and st.btn_zoom.isChecked()
          and not st.btn_pan.isChecked())
    drag(to_qt(x1[0] + 5, -5), to_qt(x1[0] + 15, 5))
    x2, y2 = ax.get_xlim(), ax.get_ylim()
    check("zoom box zoomed in", abs((x2[1] - x2[0]) - 10) < 0.6 and abs((y2[1] - y2[0]) - 10) < 0.6, f"{x2} {y2}")
    check("after zoom: boxes show the zoomed limits", st.x_from.text() == stm.format_number(x2[0], x2[1] - x2[0])
          and st.y_from.text() == stm.format_number(y2[0], y2[1] - y2[0]) and st.manual_y == tuple(y2))
    render()
    check("zoomed view survives a redraw", tuple(ax.get_xlim()) == tuple(x2))
    check("Back enabled after navigation", st.btn_back.isEnabled())
    QTest.mouseClick(st.btn_back, Qt.LeftButton)
    pump()
    check("Back -> the panned view", all(abs(a - b) < 1e-6 for a, b in zip(ax.get_xlim(), x1)), f"{ax.get_xlim()} {x1}")
    render()
    check("Back view kept on redraw (manual)", all(abs(a - b) < 1e-6 for a, b in zip(ax.get_xlim(), x1)))
    QTest.mouseClick(st.btn_forward, Qt.LeftButton)
    pump()
    check("Forward -> the zoomed view", all(abs(a - b) < 1e-6 for a, b in zip(ax.get_xlim(), x2)))
    QTest.mouseClick(st.btn_zoom, Qt.LeftButton)
    pump()
    check("Zoom button again -> no mode", st._nav_mode() == '' and not st.btn_zoom.isChecked()
          and not st.btn_pan.isChecked())
    QTest.mouseClick(st.btn_reset, Qt.LeftButton)
    pump()
    check("Reset after pan/zoom -> Auto, whole log, history cleared",
          st.x_auto.isChecked() and st.y_auto.isChecked() and abs(ax.get_xlim()[1] - 60.0) < 1e-6
          and not st.btn_back.isEnabled())

    # Save image
    png = os.path.join(TMP, 'status_plot.png')
    real_save = QFileDialog.getSaveFileName
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (png, ''))
    try:
        QTest.mouseClick(st.btn_save, Qt.LeftButton)
        pump()
    finally:
        QFileDialog.getSaveFileName = real_save
    check("Save image writes the figure (matplotlib save_figure)", os.path.exists(png) and os.path.getsize(png) > 1000)

    # Clear plot (ax.clear resets matplotlib's callbacks): the boxes keep following the axes
    win.duet_connected = False                 # job over / disconnected: no dashboard redraw after the Clear
    win.status_stopped = True
    st.x_from.setText("5")                     # (text set from outside = touch keyboard path: applied at once)
    st.x_to.setText("15")
    st.y_from.setText("-2")
    st.y_to.setText("3")
    win.status_toolbar.push_current()
    win.status_toolbar.push_current()
    st.update_nav_buttons()
    pump()
    check("before Clear: manual limits 5-15 / -2-3, Auto off", st.manual_x == (5.0, 15.0) and st.manual_y == (-2.0, 3.0)
          and not st.x_auto.isChecked() and tuple(ax.get_xlim()) == (5.0, 15.0), f"{st.manual_x} {ax.get_xlim()}")
    renders = []
    real_original = fcn_duet.render_status_plot._stm_original
    fcn_duet.render_status_plot._stm_original = lambda self_: (renders.append(1), real_original(self_))[1]
    try:
        QTest.mouseClick(win.button_clear_plot, Qt.LeftButton)       # the Clear Plot Data button in the footer
        pump()
    finally:
        fcn_duet.render_status_plot._stm_original = real_original
    check("Clear Plot Data (footer) clears the plot data (legacy handler)",
          all(len(v) == 0 for v in win.status_plot_data.values()) and not win.status_plot_lines)
    check("FIX: Clear while disconnected (no redraw ran) -> boxes show the cleared axes 0-1, both Auto lit, manual "
          "limits dropped, Back / Forward history cleared",
          not renders and st.manual_x is None and st.manual_y is None and st.x_auto.isChecked() and st.y_auto.isChecked()
          and st.x_from.text() == "0" and st.x_to.text() == "1" and st.y_to.text() == "1"
          and st.x_from.styleSheet() == stm.LIMIT_STYLE_AUTO and not st.btn_back.isEnabled(),
          f"renders={len(renders)} boxes {st.x_from.text()} {st.x_to.text()} manual {st.manual_x} {st.manual_y}")
    ax.set_xlim(2.0, 4.0)
    check("FIX: after Clear (no redraw) the limit callbacks are re-attached at once",
          st.x_from.text() == "2" and st.x_to.text() == "4", f"{st.x_from.text()} {st.x_to.text()}")
    ax.set_xlim(0.0, 1.0)
    win.status_stopped = False
    win.duet_connected = True
    win.run_active = False
    for i in range(30):
        sample(0.1 * i, 1.0 + 0.1 * i)
    render()
    check("after Clear plot: new data set -> Auto", st.manual_x is None and st.x_auto.isChecked())
    ax.set_xlim(3.0, 7.0)
    check("after Clear plot: limit callbacks re-connected (boxes follow set_xlim)",
          st.x_from.text() == stm.format_number(3.0, 4.0) and st.x_to.text() == stm.format_number(7.0, 4.0),
          f"{st.x_from.text()} {st.x_to.text()}")
    win.duet_connected = False
    QTest.mouseClick(st.btn_reset, Qt.LeftButton)
    pump()

    # ---------------------------------------------- no grey backgrounds
    def grey_fraction(widget):
        img = widget.grab().toImage()
        n = grey = 0
        for yy in range(0, img.height(), 2):
            for xx in range(0, img.width(), 2):
                c = img.pixelColor(xx, yy)
                n += 1
                if c.red() == c.green() == c.blue() and 225 <= c.red() <= 250:
                    grey += 1
        return grey / max(n, 1), img

    for mode in (False, True):
        win.check_advanced_mode.setChecked(mode)
        pump(6)
        gp, img_p = grey_fraction(st.side_card)
        gn, img_n = grey_fraction(st.nav_row)
        name = 'Advanced' if mode else 'Basic'
        img_s = st.panel_scroll.grab().toImage()
        bg_p = img_s.pixelColor(img_s.width() - 3, img_s.height() // 2).name()
        gc, img_c = grey_fraction(win.button_clear_plot)
        from collections import Counter
        bg_c = Counter(img_c.pixelColor(xx, yy).name() for yy in range(img_c.height())
                       for xx in range(img_c.width())).most_common(1)[0][0]      # (#ffebee = hovered)
        dark_grey = sum(1 for yy in range(img_c.height()) for xx in range(img_c.width())
                        if img_c.pixelColor(xx, yy).name() in ('#757575', '#616161'))
        check(f"FIX {name}: Clear Plot Data is a white outline button (no grey #757575 block)",
              gc < 0.005 and bg_c in ('#ffffff', '#ffebee') and dark_grey == 0 and win.button_clear_plot.styleSheet() == stm.CLEAR_STYLE
              and not win.button_clear_plot.icon().isNull(), f"{gc:.4f} {bg_c} {dark_grey}")
        bg_n = img_n.pixelColor(img_n.width() // 2 - 40, img_n.height() // 2).name()
        check(f"{name}: axis panel has no grey background", gp < 0.005 and bg_p == '#ffffff', f"{gp:.4f} {bg_p}")
        check(f"{name}: navigation row has no grey strip", gn < 0.005, f"{gn:.4f} {bg_n}")
        check(f"{name}: plot card background white under the nav row", bg_n == '#ffffff', bg_n)

    # ---------------------------------------------- screenshots with a loaded log and some curves
    fcn_duet.load_log_file_into_status(win, plat_log)
    pump()
    for k in ['A', 'B', 'C', 'D', "'a", "'c", "'e", "'f", 'Yaw']:
        st.pill_cb[k].setChecked(False)
    render()
    win.check_advanced_mode.setChecked(False)
    pump(6)
    canvas.draw()
    pump()
    win.tab_status.grab().save(os.path.join(OUT, 'st_fix_basic.png'))
    win.check_advanced_mode.setChecked(True)
    pump(6)
    QTest.mouseClick(st.pills['A'], Qt.LeftButton)
    QTest.mouseClick(st.pills['B'], Qt.LeftButton)
    pump()
    st.x_from.setFocus()
    st.x_from.selectAll()
    QTest.keyClicks(st.x_from, "5")
    QTest.keyClick(st.x_from, Qt.Key_Return)
    st.x_to.setFocus()
    st.x_to.selectAll()
    QTest.keyClicks(st.x_to, "35")
    QTest.keyClick(st.x_to, Qt.Key_Return)
    canvas.setFocus()
    pump()
    canvas.draw()
    pump()
    win.tab_status.grab().save(os.path.join(OUT, 'st_fix_advanced.png'))
    QTest.mouseClick(st.btn_record, Qt.LeftButton)
    pump()
    win.tab_status.grab().save(os.path.join(OUT, 'st_fix_advanced_record_off.png'))
    QTest.mouseClick(st.btn_record, Qt.LeftButton)
    pump()
    check("screenshots saved", all(os.path.exists(os.path.join(OUT, n)) for n in
                                   ('st_fix_basic.png', 'st_fix_advanced.png', 'st_fix_advanced_record_off.png')),
          OUT)
    win.check_advanced_mode.setChecked(False)
    pump()
    # FIX: modernise_status_tab never raises (on_main_tab_changed must still mark the tab as built)
    class _Dummy:
        pass
    dummy = _Dummy()
    dummy.statusCanvas = object()
    dummy.check_advanced_mode = object()
    real_build = stm.ModernStatus.build
    stm.ModernStatus.build = lambda self_: (_ for _ in ()).throw(RuntimeError("simulated build error"))
    try:
        raised = False
        try:
            res = stm.modernise_status_tab(dummy)
        except Exception:
            raised, res = True, None
    finally:
        stm.ModernStatus.build = real_build
    check("FIX: a build error in modernise_status_tab is caught (prints, returns None, wrapper falls back)",
          not raised and res is None and getattr(dummy, 'status_modern', None) is not None
          and dummy.status_modern.alive is False)
    check("no Python exceptions in Qt slots", not ERRS, "\n".join(ERRS[:2]))
    close_window(win)
finally:
    restore_cfg()
    if CFG_EXISTED:
        with open(CFG, 'rb') as f1, open(CFG_BACKUP, 'rb') as f2:
            same = f1.read() == f2.read()
        print(f"{'PASS' if same else 'FAIL'}: configuration.json restored byte-identically")
        RES.append(same)

n_ok = sum(RES)
print(f"\n{n_ok}/{len(RES)} checks passed" + ("" if n_ok == len(RES) else f"  ({len(RES) - n_ok} FAILED)"))
sys.exit(0 if n_ok == len(RES) and RES else 1)
