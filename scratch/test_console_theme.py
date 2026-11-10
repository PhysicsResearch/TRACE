"""Console light/dark switch (fcn_create_gui/console_theme.py) on the real app window.  Restores the saved setting."""
import sys, os
sys.path.insert(0, r"C:\TRACE"); os.chdir(r"C:\TRACE")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSettings, QPoint
from PySide6.QtTest import QTest
app = QApplication.instance() or QApplication(sys.argv)
import Launch_ImGUI as L
import fcn_create_gui.console_theme as CT
from fcn_control.fcn_control import log_to_duet_console
OUT = os.environ.get("CT_OUT", "")
RES = []
def check(name, ok, info=""):
    RES.append(bool(ok)); print(("PASS: " if ok else "FAIL: ") + name + (f"  [{info}]" if info and not ok else ""), flush=True)
st = QSettings("TRACE", "TRACE"); had = st.contains(CT.SETTINGS_KEY); orig = st.value(CT.SETTINGS_KEY)
try:
    st.remove(CT.SETTINGS_KEY)
    w = L.MyApp(None); app.setStyle('Fusion')
    w.setAttribute(Qt.WA_DontShowOnScreen, True)
    dark0 = w.duet_log_console.styleSheet()
    ct = CT.add_console_theme_button(w)
    check("button added once (second call returns the same)", ct is not None and CT.add_console_theme_button(w) is ct)
    w.resize(2048, 1200); w.show(); w.tabModules.setCurrentIndex(0)
    for _ in range(10): app.processEvents()
    b, send = w.button_console_theme, w.sendCommandDUET
    check("button right of Send, same row, same height, visible",
          b.isVisible() and b.geometry().left() >= send.geometry().right() and abs(b.geometry().center().y() - send.geometry().center().y()) <= 2
          and b.height() == b.width() and abs(b.height() - send.height()) <= 4, f"{b.geometry()} {send.geometry()}")
    check("default dark: original style sheet, moon tooltip", ct.mode == "dark" and w.duet_log_console.styleSheet() == dark0 and "moon" in b.toolTip())
    log_to_duet_console(w, "M115"); log_to_duet_console(w, "Error: test", color="#ff3333"); log_to_duet_console(w, "note", color="#ff9800")
    if OUT: w.tab_2.grab().save(os.path.join(OUT, "console_dark.png"))
    QTest.mouseClick(b, Qt.LeftButton); app.processEvents()
    check("click -> light: white background, dark text, sun tooltip, saved",
          ct.mode == "light" and "#ffffff" in w.duet_log_console.styleSheet() and "sun" in b.toolTip()
          and str(QSettings("TRACE", "TRACE").value(CT.SETTINGS_KEY)) == "light")
    check("log text kept across the switch", "Error: test" in w.duet_log_console.toPlainText() and "M115" in w.duet_log_console.toPlainText())
    img = w.duet_log_console.viewport().grab().toImage()
    check("light console really white", img.pixelColor(img.width() - 5, img.height() - 5).name() == "#ffffff", img.pixelColor(img.width()-5, img.height()-5).name())
    if OUT: w.tab_2.grab().save(os.path.join(OUT, "console_light.png"))
    QTest.mouseClick(b, Qt.LeftButton); app.processEvents()
    check("click again -> dark: original style sheet restored exactly", ct.mode == "dark" and w.duet_log_console.styleSheet() == dark0
          and str(QSettings("TRACE", "TRACE").value(CT.SETTINGS_KEY)) == "dark")
    QSettings("TRACE", "TRACE").setValue(CT.SETTINGS_KEY, "light")
    w2 = L.MyApp(None); CT.add_console_theme_button(w2)
    check("saved light mode is applied on the next start", w2.console_theme.mode == "light" and "#ffffff" in w2.duet_log_console.styleSheet())
    w.close(); w2.close()
finally:
    st = QSettings("TRACE", "TRACE")
    if had: st.setValue(CT.SETTINGS_KEY, orig)
    else: st.remove(CT.SETTINGS_KEY)
    st.sync()
n = RES.count(False)
print(f"\n{'ALL PASSED' if not n else f'{n} FAILED'} ({len(RES)} checks)", flush=True)
os._exit(1 if n else 0)
