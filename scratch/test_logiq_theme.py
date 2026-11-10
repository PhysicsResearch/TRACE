"""LogIQ theme / names checks (offscreen).   python scratch/test_logiq_theme.py"""
import os
import re
import shutil
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"C:\TRACE")
os.chdir(r"C:\TRACE")
cfg_bak = os.path.join(tempfile.gettempdir(), "kq_test_cfg.json")
shutil.copy2("configuration.json", cfg_bak)

from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QToolButton
from PySide6.QtGui import QPalette

app = QApplication(sys.argv)
from fcn_create_gui import logiq_theme as K
from fcn_create_gui import display_names as DN

FAILS = []
N = [0]


def check(name, ok, info=""):
    N[0] += 1
    print(("PASS " if ok else "FAIL ") + name + (f"  [{info}]" if info and not ok else ""), flush=True)
    if not ok:
        FAILS.append(name)


# ---- pure remap
check("01 map targets are never keys (idempotent)", not (set(K.COLOR_MAP) & {v.lower() for v in K.COLOR_MAP.values()}))
css = "QPushButton { background-color: #1565C0; color: white; border: 1px solid #cfd8dc; } :hover { background: blue; }"
out = K.remap_css(css)
check("02 blue -> olive, grey border -> olive grey, named colour", "#1565C0" not in out and K.OLIVE in out
      and "#ccd5c2" in out and "background: " + K.OLIVE in out, out)
check("03 remap is idempotent", K.remap_css(out) == out)
for red in ("#d32f2f", "#c62828", "#b71c1c", "#ff3333", "red", "#e53935", "#f44336", "#ffebee", "#ff9800", "orange"):
    check(f"04 kept: {red}", K.remap_css(f"background-color: {red};") == f"background-color: {red};")
check("05 object names / words are not colours", K.remap_css("QPushButton#blueButton { color: #fff; }")
      == "QPushButton#blueButton { color: #fff; }")
check("06 violet (old Send) -> theme", K.remap_css("background-color: violet;") == f"background-color: {K.OLIVE_MID};")

# ---- the app
import Launch_ImGUI as L
from fcn_create_gui.window_fit import fit_tabs_to_current_page
from fcn_create_gui.top_bar_style import style_top_bar
from fcn_create_gui.console_theme import add_console_theme_button

K.prepare_logiq_theme()
w = L.MyApp(None)
app.setStyle('Fusion')
fit_tabs_to_current_page(w)
style_top_bar(w)
add_console_theme_button(w)
K.apply_logiq_theme(w)
w.resize(1800, 1000)
w.show()
for _ in range(5):
    app.processEvents()

check("10 window title LogIQ", w.windowTitle().startswith("LogIQ"), w.windowTitle())
wm = getattr(w, 'logiq_word_mark', None)
check("11 word mark next to the logo", wm is not None and wm.text() == "LogIQ" and wm.isVisible())
check("12 palette highlight is olive", app.palette().color(QPalette.Highlight).name() == K.OLIVE_MID)

send = w.sendCommandDUET.styleSheet().lower()
check("13 Send is no longer violet / pink", "violet" not in send and K.OLIVE_MID in send, send[:120])

ct = w.console_theme
ct.apply("dark", save=False)
con = w.duet_log_console.styleSheet().lower()
check("14 dark console is dark olive, not black", K.CONSOLE_DARK in con and "#1e1e1e" not in con, con[:120])
ct.apply("light", save=False)
check("15 console light mode still light", "#1e1e1e" not in w.duet_log_console.styleSheet().lower()
      and K.CONSOLE_DARK not in w.duet_log_console.styleSheet().lower())
ct.apply("dark", save=False)

# emergency / red buttons unchanged
reds = [b for b in w.findChildren(QPushButton) if 'emergency' in b.text().lower()]
check("16 emergency buttons keep red", reds and all(re.search(r"#ff3333|red|#d32f2f|#c62828|#b71c1c|#f44336|#ff0000",
                                                              b.styleSheet().lower()) for b in reds),
      [b.styleSheet()[:80] for b in reds])

# Planning: axis pills keep the plot colours
w.tabModules.setCurrentIndex(3)
for _ in range(5):
    app.processEvents()
p = w.planning_modern
from fcn_create_gui.tab_planning_modern import PLOT_COLORS
for key in ('X', 'Y', 'Z'):
    ss = p.pills[key].styleSheet().lower()
    check(f"20 Planning pill {key} keeps its plot colour", PLOT_COLORS[key] in ss, ss[:120])
p.device_buttons[1].click()
for _ in range(3):
    app.processEvents()
for key in ('LAT', 'Roll', 'A', "'a"):
    ss = p.pills[key].styleSheet().lower()
    check(f"21 platform pill {key} keeps its plot colour", PLOT_COLORS[key] in ss, ss[:120])
p.device_buttons[0].click()
add = w.button_create_curve.styleSheet().lower()
check("22 Add Curve themed (no material green)", "#2e7d32" not in add, add[:100])

# Status: legacy 'Show X' boxes keep the curve colour (the Status plot / pills read it)
w.tabModules.setCurrentIndex(1)
for _ in range(5):
    app.processEvents()
for attr, col in (('status_check_X', '#1e88e5'), ('status_check_Roll', '#3f51b5'), ('status_check_a', '#009688')):
    cb = getattr(w, attr, None)
    check(f"23 {attr} keeps {col}", cb is not None and col in cb.styleSheet().lower(),
          cb.styleSheet()[:80] if cb is not None else None)

# no primary blue left outside axis buttons
left = []
for wd in w.findChildren(QWidget):
    ss = (wd.styleSheet() or '').lower()
    if ('#1565c0' in ss or '#0d47a1' in ss or 'violet' in ss) and not K.is_axis_widget(wd):
        left.append((type(wd).__name__, wd.objectName(), (wd.text() if hasattr(wd, 'text') else '')))
check("30 no old primary blue / violet left in the UI stylesheets", not left, left[:8])

# a stylesheet set later (dynamic) is themed too
b = QPushButton("Later", w)
b.setStyleSheet("background-color: #1976d2;")
check("31 stylesheets set later are themed", "#1976d2" not in b.styleSheet().lower())
x = QToolButton(w)
x.setText("X")
x.setStyleSheet("QToolButton { background-color: #1976d2; }")
check("32 a later axis pill keeps its colour", "#1976d2" in x.styleSheet().lower())
lab = QLabel("X 0.00", w)
lab.setStyleSheet("color: #1565c0;")
check("33 an axis label follows the theme", "#1565c0" not in lab.styleSheet().lower())

# renamed visible strings
src = open(r"C:\TRACE\fcn_plan\fcn_import.py", encoding='utf-8').read()
check("40 import filter and its check renamed together", src.count('"LogIQ Log Files (log_*.csv log_*.txt *.txt);;"') == 1
      and 'if "LogIQ Log" in selected_filter' in src and '"TRACE Log' not in src)
from fcn_create_gui import tab_logs
check("41 log files filter renamed", tab_logs._LOG_FILTER.startswith("LogIQ logs"))

# ---- display names: DYNAMIQ / KINETIQ on screen, the code keeps 'Lung Phantom' / 'Motion Platform'
from PySide6.QtWidgets import QComboBox, QAbstractButton, QTabBar, QGroupBox
T = DN.display_text
check("50 names", T("Lung Phantom") == "DYNAMIQ" and T("Motion Platform") == "KINETIQ" and T("LungPhan") == "DYNAMIQ"
      and T("TRACE") == "KINETIQ" and T("Platform position") == "KINETIQ position" and T("LUNG PHANTOM") == "DYNAMIQ"
      and T("Lung phantom X position (mm)") == "DYNAMIQ X position (mm)" and T("PLATFORM") == "KINETIQ",
      [T(x) for x in ("Lung Phantom", "Motion Platform", "Platform position", "PLATFORM")])
check("51 paths / file names never mapped",
      T(r"C:\Users\me\Platform tests\run.gcode") == r"C:\Users\me\Platform tests\run.gcode"
      and T("planned_motion_platform_SI_sin.gcode") == "planned_motion_platform_SI_sin.gcode"
      and T("Output folder C:/TRACE/logs") == "Output folder C:/TRACE/logs")
check("52 anatomy kept: one for each lung", T("one for each lung") == "one for each lung")
w.tabModules.setCurrentIndex(3)
for _ in range(4):
    app.processEvents()
cd = w.combo_device
check("53 device combo keeps its items for the code",
      [cd.itemText(i) for i in range(cd.count())] == ["Lung Phantom", "Motion Platform"]
      and cd.currentText() in ("Lung Phantom", "Motion Platform"), [cd.itemText(i) for i in range(cd.count())])
sd = w.combo_settings_device
check("54 settings combo mapped on screen only", sd.property("dn_mapped") is True and sd.currentText() == "Lung Phantom",
      (sd.property("dn_mapped"), sd.currentText()))
p = w.planning_modern
db = p.device_buttons
shown = [DN._orig[(QAbstractButton, 'text')](b) for b in db]
check("55 device toggle shows DYNAMIQ / KINETIQ", shown == ["DYNAMIQ", "KINETIQ"], shown)
check("56 ... and text() returns the original to the code", [b.text() for b in db] == ["Lung Phantom", "Motion Platform"],
      [b.text() for b in db])
db[1].click()
for _ in range(3):
    app.processEvents()
check("57 switching the device still works (combo / axes)", cd.currentText() == "Motion Platform" and 'LAT' in p.axis_pills,
      cd.currentText())
db[0].click()
for _ in range(3):
    app.processEvents()
check("58 and back", cd.currentText() == "Lung Phantom" and 'X' in p.axis_pills)
alltabs = [b.tabText(i) for b in w.findChildren(QTabBar) for i in range(b.count())]
check("59 no tab shows Lung Phantom / Platform", not any(re.search(r"(?i)lung|platform|phantom", t or '') for t in alltabs),
      [t for t in alltabs if re.search(r"(?i)lung|platform|phantom", t or '')])
for idx in (0, 1, 3):
    w.tabModules.setCurrentIndex(idx)
    for _ in range(4):
        app.processEvents()
    vis = []
    for wd in w.findChildren(QWidget):
        if isinstance(wd, QAbstractButton):
            t = DN._orig[(QAbstractButton, 'text')](wd)
        elif isinstance(wd, QLabel):
            t = DN._orig[(QLabel, 'text')](wd)
        elif isinstance(wd, QGroupBox):
            t = DN._orig[(QGroupBox, 'title')](wd)
        else:
            continue
        if wd.isVisibleTo(w) and re.search(r"(?i)\blung ?phantom\b|\bmotion platform\b|\bplatform\b|\bLungPhan\b", t or '') \
                and not DN._PATHLIKE.search(t):
            vis.append(t)
    check(f"60 tab {idx}: no visible label / button says Lung Phantom / Platform", not vis, vis[:8])

w.close()
shutil.copy2(cfg_bak, "configuration.json")
print(f"\n{N[0] - len(FAILS)}/{N[0]} passed", flush=True)
sys.exit(1 if FAILS else 0)
