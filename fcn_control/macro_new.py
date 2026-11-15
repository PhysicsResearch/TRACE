"""
Files tab > Macros: "New Macro" (new file; one hook line in fcn_init/init_buttons.py).

The button sits next to "New Folder" and is shown only while the folder list is on Macros. It opens a dialog with two
kinds of macro:

* Blank          -> <name>.g in the Macros folder shown, with one comment line.
* Wi-Fi network  -> wifi_<name>.g in 0:/macros, from a commented template that joins one saved Wi-Fi network.
                    The touch panel's WIFI list (Control tab) shows the macros in 0:/macros whose name starts with
                    "wifi" and runs the one touched. The dialog asks for the network name (SSID) only: the password is
                    never asked for and never written to the file. It is saved once in the controller's Wi-Fi module
                    with M587, typed on the panel's Console; M587 without parameters lists the saved network names,
                    never the passwords.

The file is uploaded like the Text Editor's Save (rr_upload), the list reloads and the file opens in the Editor tab.
"""
import datetime
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QButtonGroup, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

MACROS_ROOT = "0:/macros"
WIFI_PREFIX = "wifi_"
SSID_MAX_BYTES = 32            # longest Wi-Fi network name
NAME_MAX = 40

BUTTON_STYLE = ("background-color: #4caf50; color: white; font-weight: bold; font-size: 16px; min-height: 50px; "
                "padding: 6px 16px; border-radius: 4px;")


# ---------------------------------------------------------------------------------------------------------- texts

def clean_name(text):
    """File-name part: letters, digits, '_' and '-'; spaces become '_', anything else is dropped."""
    s = re.sub(r"\s+", "_", (text or "").strip())
    s = re.sub(r"[^A-Za-z0-9_\-]", "", s)
    return s[:NAME_MAX]


def blank_name_part(text):
    """Name typed for a blank macro, without a '.g' the user may have typed."""
    s = (text or "").strip()
    if s.lower().endswith(".g"):
        s = s[:-2]
    return clean_name(s)


def wifi_name_part(text):
    """Name typed for the WIFI list, without a 'wifi' / 'wifi_' prefix or '.g' the user may have typed."""
    s = (text or "").strip()
    if s.lower().endswith(".g"):
        s = s[:-2]
    s = re.sub(r"^wifi[_\- ]?", "", s, flags=re.IGNORECASE)
    return clean_name(s)


def rrf_quoted(text):
    """Text inside an RRF quoted string: '"' is written '""' and "'" is written "''" (a lone ' before a letter
    would make that letter lower case)."""
    return text.replace('"', '""').replace("'", "''")


def ssid_problem(ssid):
    """None when the network name can be used, else the reason."""
    if not ssid:
        return "Type the network name."
    if ssid != ssid.strip():
        return "The network name starts or ends with a space: check it."
    if any(ord(c) < 32 for c in ssid):
        return "The network name contains a control character."
    if len(ssid.encode("utf-8")) > SSID_MAX_BYTES:
        return f"A network name has at most {SSID_MAX_BYTES} characters."
    return None


def blank_file(file_name):
    return f"; {file_name}\n\n"


def _cmd(command, comment, width=34):
    return f"{command.ljust(width)}; {comment}"


def wifi_file(file_name, ssid, today=None):
    """Template of a Wi-Fi macro: joins the saved network `ssid`. No password anywhere."""
    today = today or datetime.date.today().isoformat()
    q = rrf_quoted(ssid)
    shown = ssid.replace('"', "").replace("'", "")          # for the echo text only
    first = [("M552 S0", "Wi-Fi module on, not connected"),
             (f'M587 S"{q}" P"your password"', "save this network and its password"),
             ("M552 S1", "connect")]
    lines = [
        f'; {file_name} - join the Wi-Fi network "{ssid}"',
        f"; Made with LogIQ on {today}. Touch panel: Control tab > WIFI > {file_name}",
        '; The WIFI list shows the macros in 0:/macros whose name starts with "wifi".',
        ";",
        "; FIRST TIME ONLY - save the network and its password in the controller's Wi-Fi module.",
        "; On the touch panel: Console tab > keyboard, one command at a time:",
    ]
    lines += [";   " + _cmd(c, t, 40) for c, t in first]
    lines += [
        "; The password stays in the Wi-Fi module. It is not in this file and the controller never shows it:",
        "; M587 on its own lists the saved network names only.",
        ";",
        "; Running this macro drops the current Wi-Fi connection. LogIQ and the web page then reach the",
        "; controller at its new address, shown on the touch panel (Setup tab, bottom left).",
        "",
        f'echo "Connecting to Wi-Fi network {shown}..."',
        _cmd("M552 S0", "Wi-Fi module idle: leave the current network"),
        _cmd("G4 P1000", "wait 1 s"),
        _cmd(f'M552 S1 P"{q}"', f"join {ssid} (saved earlier with M587)"),
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------------------------------------- dialog

_DIALOG_CSS = """
QDialog { background: #ffffff; }
QLabel { font-size: 16px; color: #263238; }
QLabel#title { font-size: 21px; font-weight: bold; color: #172319; }
QLabel#field { font-size: 16px; font-weight: bold; color: #37474f; }
QLabel#path { font-size: 16px; color: #1565c0; font-weight: bold; }
QLabel#problem { font-size: 15px; color: #c62828; }
QLabel#prefix { font-size: 18px; font-weight: bold; color: #37474f; }
QLineEdit { font-size: 18px; min-height: 44px; padding: 4px 10px; border: 1px solid #b0bec5; border-radius: 4px; }
QLineEdit:focus { border: 2px solid #1976d2; }
QPushButton#kind { font-size: 17px; font-weight: bold; min-height: 54px; padding: 6px 18px; border-radius: 6px;
                   background: #eceff1; color: #37474f; border: 2px solid #cfd8dc; }
QPushButton#kind:checked { background: #1976d2; color: #ffffff; border: 2px solid #1565c0; }
QPushButton#create { font-size: 18px; font-weight: bold; min-height: 48px; min-width: 150px; border-radius: 4px;
                     background: #2e7d32; color: #ffffff; }
QPushButton#create:disabled { background: #a5d6a7; }
QPushButton#cancel { font-size: 18px; font-weight: bold; min-height: 48px; min-width: 130px; border-radius: 4px;
                     background: #eceff1; color: #37474f; }
QFrame#note { background: #e8f5e9; border: 1px solid #a5d6a7; border-radius: 6px; }
QFrame#note QLabel { font-size: 15px; color: #1b5e20; }
QPlainTextEdit { font-size: 14px; background: #fafafa; border: 1px solid #cfd8dc; border-radius: 4px; }
"""


class NewMacroDialog(QDialog):
    """Kind (Blank / Wi-Fi network), names, the path it will be saved to and a preview of the file."""

    BLANK, WIFI = 0, 1

    def __init__(self, parent=None, folder=MACROS_ROOT):
        super().__init__(parent)
        self.folder = folder.rstrip("/") or MACROS_ROOT
        self.result_path = None
        self.result_text = None
        self._name_edited = False
        self.setWindowTitle("New Macro")
        self.setMinimumWidth(820)
        self.setStyleSheet(_DIALOG_CSS)

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(12)
        title = QLabel("New macro", self)
        title.setObjectName("title")
        v.addWidget(title)

        kinds = QHBoxLayout()
        kinds.setSpacing(12)
        self.btnBlank = QPushButton("Blank", self)
        self.btnWifi = QPushButton("Wi-Fi network (template)", self)
        self.kindGroup = QButtonGroup(self)
        for i, b in enumerate((self.btnBlank, self.btnWifi)):
            b.setObjectName("kind")
            b.setCheckable(True)
            self.kindGroup.addButton(b, i)
            kinds.addWidget(b, 1)
        self.btnBlank.setChecked(True)
        v.addLayout(kinds)

        # Blank
        self.pageBlank = QWidget(self)
        pb = QVBoxLayout(self.pageBlank)
        pb.setContentsMargins(0, 0, 0, 0)
        pb.setSpacing(6)
        lab = QLabel("Name of the macro", self.pageBlank)
        lab.setObjectName("field")
        pb.addWidget(lab)
        self.editBlankName = QLineEdit(self.pageBlank)
        self.editBlankName.setPlaceholderText("for example  park_platform")
        pb.addWidget(self.editBlankName)
        v.addWidget(self.pageBlank)

        # Wi-Fi network
        self.pageWifi = QWidget(self)
        pw = QVBoxLayout(self.pageWifi)
        pw.setContentsMargins(0, 0, 0, 0)
        pw.setSpacing(6)
        lab = QLabel("Network name (SSID), exactly as the Wi-Fi network is called", self.pageWifi)
        lab.setObjectName("field")
        pw.addWidget(lab)
        self.editSsid = QLineEdit(self.pageWifi)
        self.editSsid.setPlaceholderText("for example  Lab-WiFi")
        self.editSsid.setMaxLength(64)
        pw.addWidget(self.editSsid)
        lab = QLabel("Name in the touch panel's WIFI list", self.pageWifi)
        lab.setObjectName("field")
        pw.addWidget(lab)
        row = QHBoxLayout()
        row.setSpacing(4)
        pre = QLabel(WIFI_PREFIX, self.pageWifi)
        pre.setObjectName("prefix")
        row.addWidget(pre)
        self.editWifiName = QLineEdit(self.pageWifi)
        self.editWifiName.setPlaceholderText("short, for example  Lab")
        row.addWidget(self.editWifiName, 1)
        pw.addLayout(row)
        note = QFrame(self.pageWifi)
        note.setObjectName("note")
        nl = QVBoxLayout(note)
        nl.setContentsMargins(12, 8, 12, 8)
        self.noteLabel = QLabel(
            "<b>No password here.</b> The password is never asked for and never written to the macro. "
            "Save the network once on the touch panel (Console tab, keyboard):<br>"
            "<code>M552 S0</code> &nbsp;then&nbsp; <code>M587 S\"network\" P\"password\"</code> &nbsp;then&nbsp; "
            "<code>M552 S1</code>.<br>The password stays in the controller's Wi-Fi module: LogIQ, the web page and "
            "the files cannot read it.", note)
        self.noteLabel.setWordWrap(True)
        self.noteLabel.setTextFormat(Qt.RichText)
        nl.addWidget(self.noteLabel)
        pw.addWidget(note)
        v.addWidget(self.pageWifi)

        self.pathLabel = QLabel(self)
        self.pathLabel.setObjectName("path")
        v.addWidget(self.pathLabel)
        self.problemLabel = QLabel(self)
        self.problemLabel.setObjectName("problem")
        v.addWidget(self.problemLabel)

        self.preview = QPlainTextEdit(self)
        self.preview.setReadOnly(True)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.Monospace)
        mono.setPointSize(10)
        self.preview.setFont(mono)
        self.preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.preview.setMinimumHeight(250)
        v.addWidget(self.preview, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.btnCancel = QPushButton("Cancel", self)
        self.btnCancel.setObjectName("cancel")
        self.btnCreate = QPushButton("Create", self)
        self.btnCreate.setObjectName("create")
        self.btnCreate.setDefault(True)
        buttons.addWidget(self.btnCancel)
        buttons.addWidget(self.btnCreate)
        v.addLayout(buttons)

        self.kindGroup.idClicked.connect(lambda _id: self._refresh())
        self.editBlankName.textChanged.connect(lambda _t: self._refresh())
        self.editSsid.textChanged.connect(self._ssid_changed)
        self.editWifiName.textEdited.connect(self._wifi_name_edited)
        self.editWifiName.textChanged.connect(lambda _t: self._refresh())
        self.btnCancel.clicked.connect(self.reject)
        self.btnCreate.clicked.connect(self._create)
        self._refresh()

    # -- state
    def kind(self):
        return self.WIFI if self.btnWifi.isChecked() else self.BLANK

    def set_kind(self, kind):
        (self.btnWifi if kind == self.WIFI else self.btnBlank).setChecked(True)
        self._refresh()

    def _ssid_changed(self, text):
        if not self._name_edited:                      # follow the network name until the user types a name
            self.editWifiName.setText(wifi_name_part(text))
        self._refresh()

    def _wifi_name_edited(self, _text):
        self._name_edited = bool(self.editWifiName.text().strip())

    def target(self):
        """(path, text, problem): the file to create, or the reason it cannot be created yet."""
        if self.kind() == self.WIFI:
            ssid = self.editSsid.text()
            part = wifi_name_part(self.editWifiName.text())
            name = f"{WIFI_PREFIX}{part}.g" if part else ""
            path = f"{MACROS_ROOT}/{name}" if name else ""
            problem = ssid_problem(ssid) or (None if part else "Type a name for the WIFI list.")
            text = wifi_file(name or f"{WIFI_PREFIX}NAME.g", ssid or "NETWORK")
            return path, text, problem
        part = blank_name_part(self.editBlankName.text())
        name = f"{part}.g" if part else ""
        path = f"{self.folder}/{name}" if name else ""
        problem = None if part else "Type a name for the macro."
        return path, blank_file(name or "NAME.g"), problem

    def _refresh(self):
        wifi = self.kind() == self.WIFI
        self.pageWifi.setVisible(wifi)
        self.pageBlank.setVisible(not wifi)
        path, text, problem = self.target()
        self.pathLabel.setText(f"Saved as:  {path}" if path else "Saved as:  -")
        typed = self.editSsid.text() or self.editWifiName.text() if wifi else self.editBlankName.text()
        self.problemLabel.setText(problem if (problem and typed) else "")
        self.problemLabel.setVisible(bool(problem and typed))
        self.preview.setPlainText(text)
        self.btnCreate.setEnabled(problem is None)

    def _create(self):
        path, text, problem = self.target()
        if problem is None:
            self.result_path, self.result_text = path, text
            self.accept()


# --------------------------------------------------------------------------------------------------------- action

def _parent_widget(self):
    return self if (isinstance(self, QWidget) and not type(self).__name__.endswith('Mock')) else None


def upload_text(self, rrf_path, text):
    """Uploads `text` as `rrf_path` (as the Text Editor's Save). True when the board accepted it."""
    import requests
    from fcn_control.fcn_filesystem import get_clean_duet_ip
    timer = getattr(self, 'status_fast_timer', None)
    was_active = timer is not None and timer.isActive()
    if was_active:
        timer.stop()
    try:
        from fcn_monitor.fcn_duet import get_shared_session
        get_shared_session().close()
        session = requests.Session()
        session.trust_env = False
        try:
            r = session.post(f"http://{get_clean_duet_ip(self)}/rr_upload", params={'name': rrf_path},
                             data=text.encode('utf-8'), timeout=20)
            r.raise_for_status()
            try:
                err = int(r.json().get('err', 0))
            except Exception:
                err = 0
        finally:
            session.close()
        if err:
            QMessageBox.warning(_parent_widget(self), "New Macro", f"The controller refused '{rrf_path}' (err {err}).")
            return False
        return True
    except Exception as e:
        QMessageBox.critical(_parent_widget(self), "New Macro", f"Could not save '{rrf_path}':\n{e}")
        return False
    finally:
        if was_active and timer is not None:
            timer.start()


def new_macro(self, kind=None):
    """Dialog, then create the macro on the board and open it in the Editor tab."""
    from fcn_control.fcn_filesystem import get_files_for_dir, load_directory, open_in_editor
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(_parent_widget(self), "Not Connected", "Please connect to Duet before creating a macro.")
        return None
    curr = getattr(self, 'current_directory', '/').strip('/')
    folder = MACROS_ROOT if not curr else f"{MACROS_ROOT}/{curr}"
    dlg = NewMacroDialog(_parent_widget(self), folder)
    if kind is not None:
        dlg.set_kind(kind)
    self._new_macro_dialog = dlg                     # tests and screenshots reach the open dialog here
    try:
        if dlg.exec() != QDialog.Accepted or not dlg.result_path:
            return None
    finally:
        self._new_macro_dialog = None
    path, text = dlg.result_path, dlg.result_text

    directory, name = path.rsplit('/', 1)
    rel = directory[len(MACROS_ROOT):].strip('/')
    existing = {str(e.get('name', '')).lower() for e in get_files_for_dir(self, rel) if e.get('type') == 'f'}
    if name.lower() in existing:
        answer = QMessageBox.question(_parent_widget(self), "New Macro",
                                      f"'{name}' already exists in {directory}.\nReplace it?",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return None

    if not upload_text(self, path, text):
        return None
    try:
        from fcn_control.fcn_control import log_to_duet_console
        log_to_duet_console(self, f"Created macro '{path}'.")
    except Exception:
        pass
    load_directory(self, getattr(self, 'current_directory', '/'))
    open_in_editor(self, path)
    return path


# ---------------------------------------------------------------------------------------------------------- button

def _layout_holding(layout, widget):
    """The (sub)layout that holds `widget`, or None."""
    if layout is None:
        return None
    if layout.indexOf(widget) >= 0:
        return layout
    for i in range(layout.count()):
        sub = layout.itemAt(i).layout()
        found = _layout_holding(sub, widget)
        if found is not None:
            return found
    return None


def install_new_macro(self):
    """Idempotent: the New Macro button right of New Folder, visible while the folder list is on Macros."""
    folder_btn = getattr(self, 'gcodeNewFolder', None)
    if folder_btn is None or getattr(self, 'gcodeNewMacro', None) is not None:
        return
    parent = folder_btn.parentWidget()
    btn = QPushButton("New Macro", parent)
    btn.setObjectName("gcodeNewMacro")
    btn.setMinimumHeight(50)
    btn.setStyleSheet(BUTTON_STYLE)
    lay = _layout_holding(parent.layout() if parent is not None else None, folder_btn)
    if lay is not None:
        lay.insertWidget(lay.indexOf(folder_btn) + 1, btn)
    self.gcodeNewMacro = btn
    btn.clicked.connect(lambda: new_macro(self))

    combo = getattr(self, 'fileCategoryCombo', None)

    def sync(*_):
        btn.setVisible(combo is not None and combo.currentText() == "Macros")

    sync()
    if combo is not None:
        combo.currentTextChanged.connect(sync)
