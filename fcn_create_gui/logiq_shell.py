"""
LogIQ window layout: the connection bar on top of every tab, the tabs as icons on the left.

    from fcn_create_gui.logiq_shell import apply_logiq_shell
    apply_logiq_shell(window)          # after apply_logiq_theme(window)

Layout only; the widgets and their logic stay the same objects:

* Header (all tabs): logo + 'LogIQ', then the connection bar that was at the top of the Control tab
  (IP, Connect, DYNAMIQ / KINETIQ, connection state, touch screen, Emergency STOP).  The 'Duet IP:' label is hidden,
  the IP field has the tooltip 'IP'.  The bar is no longer framed in red / green (the state pill keeps its colour).
* DYNAMIQ / KINETIQ are mutually exclusive: the CONNECTED device is filled (identified after connecting by the board
  name or its axes, fcn_control/device_identity.py), the other is an outline; neither when not connected.
  Clicking still fills in that device's IP and connects (unchanged).
* Left column: one icon button per tab (Control, Status, Files, Planning, Editor, Log files).  The QTabWidget is kept,
  only its tab bar is hidden, so tab indexes, lazy loading and currentChanged work as before.
* Planning: Import File and Clear All get an icon (folder / bin); Clear All shows as 'Clear'.  Opening Planning while
  a device is connected switches the plan to that device (planning_follow_device).
* One Emergency STOP, in the header: the copies inside the Status and Files tabs are hidden.
"""
from PySide6.QtCore import QByteArray, QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QToolButton, QVBoxLayout, QWidget)

try:
    from PySide6.QtSvg import QSvgRenderer
except Exception:                       # pragma: no cover
    QSvgRenderer = None

# colours of the LogIQ theme (targets of logiq_theme.COLOR_MAP, so the remap leaves them as they are)
TEXT = "#262d23"
TEXT_MUTED = "#5a6954"
OLIVE = "#4b6143"
OLIVE_DARK = "#354530"
LINE = "#ccd5c2"
NAV_BG = "#f4f6f0"
NAV_HOVER = "#e9eee3"
NAV_SELECTED = "#dce5d2"
HEADER_BG = "#ffffff"
CLEAR_RED = "#b4432b"
STATE_GAP = 40             # px between the device buttons and the connection state
CONNECT_WIDTH = 64         # Connect: icon only

DEVICE_IPS = {"btn_ip_lungphan": "192.168.8.3", "btn_ip_trace": "192.168.8.2"}   # as in tab_control

# ---------------------------------------------------------------------------------------------------- icons
ICONS = {
    "control": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 '
               '2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 '
               '19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 '
               '0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 '
               '2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 '
               '1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 '
               '0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    "status": '<line x1="6" y1="20" x2="6" y2="13" stroke-width="3.2"/><line x1="12" y1="20" x2="12" y2="8" '
              'stroke-width="3.2"/><line x1="18" y1="20" x2="18" y2="4" stroke-width="3.2"/>',
    "files": '<path fill="{c}" d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    "planning": '<polyline points="3 3 3 21 21 21"/><polyline points="6 16 10 11 13 14 20 7"/>',
    "editor": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>',
    "log-files": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 '
                 '20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
            '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "import":'<path d="M6 14l1.45-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.55 6a2 2 0 0 1-1.94 1.5H4a2 2 0 0 '
              '1-2-2V5c0-1.1.9-2 2-2h3.93a2 2 0 0 1 1.66.9l.82 1.2a2 2 0 0 0 1.66.9H18a2 2 0 0 1 2 2v2"/>',
    "clear": '<polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>'
             '<line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>'
             '<path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>',
}

# main tabs in the order of tabModules: (icon key, label on the left column)
NAV_ITEMS = [("control", "Control"), ("status", "Status"), ("files", "Files"), ("planning", "Planning"),
             ("editor", "Editor"), ("log-files", "Log files")]


def svg_icon(key, color, disabled="#b5c0a9", sizes=(24, 48, 64)):
    body = ICONS[key].replace("{c}", color)
    icon = QIcon()
    for px in sizes:
        for col, mode in ((color, QIcon.Normal), (color, QIcon.Active), (disabled, QIcon.Disabled)):
            b = body.replace(color, col) if col != color else body
            svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{col}" '
                   f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{b}</svg>')
            pm = QPixmap(px, px)
            pm.fill(Qt.transparent)
            if QSvgRenderer is not None:
                r = QSvgRenderer(QByteArray(svg.encode("utf-8")))
                p = QPainter(pm)
                p.setRenderHint(QPainter.Antialiasing, True)
                r.render(p)
                p.end()
            icon.addPixmap(pm, mode, QIcon.Off)
    return icon


def _logo_path():
    import os
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    p = os.path.join(base, "assets", "Open-Logo.png")
    return p if os.path.exists(p) else "assets/Open-Logo.png"


# ---------------------------------------------------------------------------------------------------- header
def _build_header(window, parent):
    header = QFrame(parent)
    header.setObjectName("logiqHeader")
    header.setAttribute(Qt.WA_StyledBackground, True)
    header.setStyleSheet(f"QFrame#logiqHeader {{ background: {HEADER_BG}; border: none; "
                         f"border-bottom: 1px solid {LINE}; }}")
    h = QHBoxLayout(header)
    h.setContentsMargins(14, 8, 14, 8)
    h.setSpacing(14)

    brand = QWidget(header)
    brand.setObjectName("logiqBrand")
    b = QHBoxLayout(brand)
    b.setContentsMargins(0, 0, 0, 0)
    b.setSpacing(10)
    logo = QLabel(brand)
    logo.setStyleSheet("background: transparent; border: none;")
    pix = QPixmap(_logo_path())
    if not pix.isNull():
        logo.setPixmap(pix.scaled(46, 46, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    b.addWidget(logo)
    word = QLabel("LogIQ", brand)
    word.setObjectName("logiqHeaderWordMark")
    word.setStyleSheet(f"QLabel#logiqHeaderWordMark {{ color: {TEXT}; background: transparent; border: none; "
                       f"font-size: 24px; font-weight: 600; letter-spacing: 2px; }}")
    b.addWidget(word)
    brand.setFixedWidth(NAV_WIDTH - 14 + 60)
    h.addWidget(brand, 0, Qt.AlignVCenter)

    bar = getattr(window, "top_bar_frame", None)
    if isinstance(bar, QFrame):
        lay = bar.parentWidget().layout() if bar.parentWidget() is not None else None
        if lay is not None:
            lay.removeWidget(bar)
        bar.setParent(header)
        _neutral_bar(bar)
        h.addWidget(bar, 1)
    return header


def _neutral_bar(bar):
    """No red / green frame around the connection bar (update_connection_status_ui restyles it on every change)."""
    QFrame.setStyleSheet(bar, "QFrame#top_bar_frame { background: transparent; border: none; }")
    bar.setStyleSheet = lambda css: None          # this frame only; the state pill inside keeps its colours
    lay = bar.layout()
    if lay is not None:
        m = lay.contentsMargins()
        lay.setContentsMargins(0, m.top(), 0, m.bottom())
    for lbl in bar.findChildren(QLabel):
        if lbl.text().strip().rstrip(":").lower() in ("duet ip", "ip"):
            lbl.hide()
    w = bar.window()
    _connect_icon(getattr(w, "setDuetIP", None))
    state = getattr(w, "connect_status", None)          # gap between DYNAMIQ / KINETIQ and the connection state
    i = lay.indexOf(state) if (lay is not None and state is not None) else -1
    if i >= 0:
        lay.insertSpacing(i, STATE_GAP)
    ip = getattr(w, "DuetIPAddress", None)
    if isinstance(ip, QComboBox):
        ip.setToolTip("IP")
        if ip.lineEdit() is not None:
            ip.lineEdit().setToolTip("IP")


def _connect_icon(btn):
    """Connect: a link icon instead of the text, narrower.  init_buttons re-sets this button's style on every tab
    build, so the style is kept for this button only."""
    if not isinstance(btn, QPushButton):
        return
    btn.setText("")
    btn.setToolTip("Connect")
    btn.setAccessibleName("Connect")
    btn.setIcon(svg_icon("link", "#ffffff", disabled="#dfe5d7"))
    btn.setIconSize(QSize(26, 26))
    btn.setMinimumWidth(0)
    btn.setFixedWidth(CONNECT_WIDTH)
    QPushButton.setStyleSheet(btn, f"""
        QPushButton {{ background-color: {OLIVE}; border: none; border-radius: 8px; padding: 0px; }}
        QPushButton:hover {{ background-color: {OLIVE_DARK}; }}
        QPushButton:pressed {{ padding-top: 3px; padding-left: 3px; }}
    """)
    btn.setStyleSheet = lambda css: None


def _device_buttons(window):
    """DYNAMIQ / KINETIQ: exclusive, the selected one filled, the other one an outline."""
    btns = {name: getattr(window, name, None) for name in DEVICE_IPS}
    if not all(isinstance(b, QPushButton) for b in btns.values()):
        return
    group = QButtonGroup(window)
    group.setExclusive(True)
    for b in btns.values():
        b.setCheckable(True)
        group.addButton(b)
        h = max(b.height(), b.minimumHeight(), 34)
        b.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; color: {OLIVE}; border: 2px solid {OLIVE};
                          border-radius: 8px; font-weight: bold; font-size: 19px; padding: 0px 16px; }}
            QPushButton:hover {{ background-color: {NAV_HOVER}; }}
            QPushButton:checked {{ background-color: {OLIVE}; color: #ffffff; }}
            QPushButton:checked:hover {{ background-color: {OLIVE_DARK}; }}
            QPushButton:pressed {{ padding-top: 3px; padding-left: 3px; }}
        """)
        b.setFixedHeight(h)
    window.device_button_group = group
    window._device_buttons = {"DYNAMIQ": btns["btn_ip_lungphan"], "KINETIQ": btns["btn_ip_trace"]}

    # the filled button is the CONNECTED device (fcn_control.device_identity), not the IP in the field: a click
    # starts the connection (unchanged) but does not fill the button by itself
    for b in btns.values():
        b.clicked.connect(lambda *_: show_connected_device(window))

    def on_title(title):                          # update_connection_status_ui sets 'LogIQ - NOT CONNECTED'
        if "NOT CONNECTED" in str(title).upper():
            window.connected_device = None
            show_connected_device(window)

    window.windowTitleChanged.connect(on_title)
    show_connected_device(window)


def show_connected_device(window):
    """Fill DYNAMIQ or KINETIQ for window.connected_device ('DYNAMIQ' / 'KINETIQ'); neither when not connected."""
    buttons = getattr(window, "_device_buttons", None)
    group = getattr(window, "device_button_group", None)
    if not buttons or group is None:
        return
    device = getattr(window, "connected_device", None) if getattr(window, "duet_connected", False) else None
    group.setExclusive(False)
    for name, b in buttons.items():
        b.setChecked(name == device)
        b.setToolTip(f"{name}: connected" if name == device else f"Connect to {name}")
    group.setExclusive(True)


# ---------------------------------------------------------------------------------------------------- left column
NAV_WIDTH = 108


def _build_nav(window, parent, tw):
    nav = QFrame(parent)
    nav.setObjectName("logiqNav")
    nav.setAttribute(Qt.WA_StyledBackground, True)
    nav.setFixedWidth(NAV_WIDTH)
    nav.setStyleSheet(f"""
        QFrame#logiqNav {{ background: {NAV_BG}; border: none; border-right: 1px solid {LINE}; }}
        QToolButton#logiqNavButton {{ background: transparent; border: none; border-radius: 14px; color: {TEXT_MUTED};
                                     font-size: 15px; padding: 10px 2px 8px 2px; }}
        QToolButton#logiqNavButton:hover {{ background: {NAV_HOVER}; }}
        QToolButton#logiqNavButton:checked {{ background: {NAV_SELECTED}; color: {TEXT}; font-weight: 600; }}
    """)
    v = QVBoxLayout(nav)
    v.setContentsMargins(10, 14, 10, 14)
    v.setSpacing(8)
    group = QButtonGroup(nav)
    group.setExclusive(True)
    buttons = []
    for i in range(tw.count()):
        key, label = NAV_ITEMS[i] if i < len(NAV_ITEMS) else ("log-files", tw.tabText(i))
        b = QToolButton(nav)
        b.setObjectName("logiqNavButton")
        b.setText(label)
        b.setToolTip(label)
        b.setIcon(svg_icon(key, OLIVE_DARK))
        b.setIconSize(QSize(34, 34))
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        b.setMinimumHeight(88)
        b.clicked.connect(lambda _=False, k=i: tw.setCurrentIndex(k))
        group.addButton(b, i)
        v.addWidget(b)
        buttons.append(b)
    v.addStretch(1)

    def sync(index):
        if 0 <= index < len(buttons) and not buttons[index].isChecked():
            buttons[index].setChecked(True)

    tw.currentChanged.connect(sync)
    sync(tw.currentIndex())
    window.nav_buttons = buttons
    return nav


# ---------------------------------------------------------------------------------------------------- Planning
def _planning_buttons(window):
    imp = getattr(window, "button_import_curve", None)
    clr = getattr(window, "button_clear_all", None)
    if imp is None or clr is None or getattr(window, "_logiq_shell_planning", False):
        return
    window._logiq_shell_planning = True
    h = max(imp.minimumHeight(), 40)
    imp.setIcon(svg_icon("import", TEXT))
    imp.setIconSize(QSize(24, 24))
    imp.setStyleSheet(f"""
        QPushButton {{ background-color: #e4e9dd; color: {TEXT}; border: 1px solid #d3dbca; border-radius: 12px;
                      font-size: 17px; font-weight: 600; padding: 0px 14px; }}
        QPushButton:hover {{ background-color: #dae1d1; }}
        QPushButton:pressed {{ padding-top: 3px; padding-left: 3px; }}
    """)
    clr.setText("Clear")
    clr.setToolTip("Clear all curves of the plan")
    clr.setIcon(svg_icon("clear", CLEAR_RED))
    clr.setIconSize(QSize(24, 24))
    clr.setStyleSheet(f"""
        QPushButton {{ background-color: #ffffff; color: {CLEAR_RED}; border: 2px solid {CLEAR_RED};
                      border-radius: {h // 2}px; font-size: 17px; font-weight: 600; padding: 0px 14px; }}
        QPushButton:hover {{ background-color: #fbeee9; }}
        QPushButton:pressed {{ padding-top: 3px; padding-left: 3px; }}
    """)
    for b in (imp, clr):
        b.setMinimumHeight(h)


# ---------------------------------------------------------------------------------------------------- per tab
TAB_ESTOPS = ("emergencyButton_2", "emergencyButton_3")      # Status / Files: the header's Emergency STOP is enough
PLANNING_INDEX = 3
PLANNING_DEVICE = {"DYNAMIQ": "Lung Phantom", "KINETIQ": "Motion Platform"}   # connected device -> plan device


def _hide_tab_estops(window):
    """One Emergency STOP: the one in the header (on every tab); the copies inside Status and Files are hidden."""
    for name in TAB_ESTOPS:
        b = getattr(window, name, None)
        if isinstance(b, QPushButton) and not b.isHidden():
            b.hide()


def planning_follow_device(window):
    """Opening Planning while a device is connected: the plan switches to that device (each device keeps its own
    plan, so nothing is lost).  Not connected: unchanged."""
    if not getattr(window, "duet_connected", False):
        return
    target = PLANNING_DEVICE.get(getattr(window, "connected_device", None))
    combo = getattr(window, "combo_device", None)
    pm = getattr(window, "planning_modern", None)
    if not target or combo is None:
        return
    i = combo.findText(target)
    if i < 0 or combo.currentIndex() == i:
        return
    if pm is not None and hasattr(pm, "on_device_clicked"):
        pm.on_device_clicked(i)                # same path as clicking the device segment
    else:
        combo.setCurrentIndex(i)


def _on_tab(window, index):
    _planning_buttons(window)
    _hide_tab_estops(window)
    if index == PLANNING_INDEX:
        planning_follow_device(window)


# ---------------------------------------------------------------------------------------------------- entry
def apply_logiq_shell(window):
    if getattr(window, "logiq_shell", False):
        return window
    tw = getattr(window, "tabModules", None)
    central = window.centralWidget()
    lay = central.layout() if central is not None else None
    if tw is None or lay is None:
        return window

    # tabs: the bar and its logo corner are replaced by the left column and the header
    tw.tabBar().hide()
    corner = tw.cornerWidget(Qt.TopLeftCorner)
    if corner is not None:
        corner.hide()
    tw.setStyleSheet(tw.styleSheet() + "\nQTabWidget::pane { border: none; top: 0px; }")

    lay.removeWidget(tw)
    header = _build_header(window, central)
    body = QWidget(central)
    body.setObjectName("logiqBody")
    bl = QHBoxLayout(body)
    bl.setContentsMargins(0, 0, 0, 0)
    bl.setSpacing(0)
    bl.addWidget(_build_nav(window, body, tw))
    tw.setParent(body)
    bl.addWidget(tw, 1)
    lay.setSpacing(0)
    lay.addWidget(header)
    lay.addWidget(body, 1)
    tw.show()

    _device_buttons(window)
    from fcn_create_gui.status_smooth import install_status_smoothing
    install_status_smoothing()                  # Status plot: measured curves through the position updates
    tw.currentChanged.connect(lambda i: QTimer.singleShot(0, lambda: _on_tab(window, i)))
    _planning_buttons(window)
    _hide_tab_estops(window)
    window.logiq_shell = True
    return window
