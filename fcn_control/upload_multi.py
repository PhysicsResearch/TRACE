"""
Files tab: Upload File - one or more files from the computer to the current folder on the Duet SD card.

Same transfer as fcn_filesystem.upload_file (rr_upload, background polling paused, a fresh HTTP session so the
Duet's HTTP server has a free connection), but the dialog allows several files and any file type (G-code, macros,
config.g, homing files such as home'a.g ...).  One progress dialog for all files, one summary at the end, then the
folder list is reloaded.
"""
import os

import requests
from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog

FILE_FILTER = "All Files (*);;G-code and macros (*.gcode *.g *._gcode)"


class _Cancelled(Exception):
    pass


class _ProgressReader:
    """File-like object for requests: reports the bytes sent and stops when the dialog is cancelled."""

    def __init__(self, data, on_progress):
        self.data, self.pos, self.on_progress = data, 0, on_progress

    def __len__(self):
        return len(self.data)

    def read(self, size=-1):
        if size is None or size < 0:
            size = len(self.data) - self.pos
        chunk = self.data[self.pos:self.pos + size]
        self.pos += len(chunk)
        self.on_progress(self.pos, len(self.data))
        return chunk


def _rrf_path(self, filename):
    from fcn_control.fcn_filesystem import get_root_prefix
    curr_dir = getattr(self, 'current_directory', '/').strip('/')
    root = get_root_prefix(self)
    return f"{root}/{filename}" if not curr_dir else f"{root}/{curr_dir}/{filename}"


def upload_files(self):
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before uploading files.")
        return
    paths, _ = QFileDialog.getOpenFileNames(self, "Upload Files", "", FILE_FILTER)
    if not paths:
        return

    from fcn_control.fcn_filesystem import get_clean_duet_ip, load_directory
    from fcn_monitor.fcn_duet import get_shared_session
    url = f"http://{get_clean_duet_ip(self)}/rr_upload"
    n = len(paths)

    progress = QProgressDialog("", "Cancel", 0, 100, self)
    progress.setWindowTitle("Uploading Files")
    progress.setWindowModality(Qt.WindowModal)
    progress.setMinimumWidth(550)
    progress.setMinimumHeight(180)
    progress.setStyleSheet("""
        QProgressDialog { font-size: 18px; font-weight: bold; }
        QLabel { font-size: 18px; min-height: 40px; }
        QProgressBar { text-align: center; font-size: 18px; font-weight: bold; height: 35px; border-radius: 4px; }
        QPushButton { font-size: 18px; font-weight: bold; min-width: 120px; min-height: 45px; border-radius: 4px; }
    """)
    progress.setValue(0)
    progress.show()
    QCoreApplication.processEvents()

    # no other HTTP request to the Duet during the upload
    timers = [t for t in (getattr(self, 'status_polling_timer', None), getattr(self, 'status_fast_timer', None))
              if t is not None and t.isActive()]
    for t in timers:
        t.stop()
    get_shared_session().close()

    done, failed, cancelled = [], [], False
    try:
        for k, path in enumerate(paths):
            name = os.path.basename(path)
            progress.setLabelText(f"Uploading '{name}' ({k + 1} of {n})...")

            def on_progress(sent, total, k=k):
                if progress.wasCanceled():
                    raise _Cancelled()
                frac = sent / total if total else 1.0
                progress.setValue(int(100 * (k + frac) / n))
                QCoreApplication.processEvents()

            try:
                with open(path, 'rb') as f:
                    data = f.read()
                session = requests.Session()
                session.trust_env = False
                try:
                    r = session.post(url, params={'name': _rrf_path(self, name)},
                                     data=_ProgressReader(data, on_progress), timeout=20)
                    r.raise_for_status()
                    if r.headers.get('content-type', '').startswith('application/json') and r.json().get('err', 0):
                        raise RuntimeError(f"Duet reported an error (err={r.json().get('err')})")
                finally:
                    session.close()
                done.append(name)
            except _Cancelled:
                cancelled = True
                break
            except Exception as e:
                failed.append((name, str(e)))
                if progress.wasCanceled():
                    cancelled = True
                    break
        progress.setValue(100)
    finally:
        progress.close()
        for t in timers:
            t.start()

    lines = []
    if done:
        lines.append(f"Uploaded ({len(done)}): " + ", ".join(done))
    if failed:
        lines.append(f"Failed ({len(failed)}):\n" + "\n".join(f"  {a}: {b}" for a, b in failed))
    if cancelled:
        lines.append(f"Cancelled: {n - len(done) - len(failed)} file(s) not uploaded.")
    text = "\n\n".join(lines) or "Nothing uploaded."
    if failed:
        QMessageBox.critical(self, "Upload", text)
    else:
        QMessageBox.information(self, "Upload", text)
    if done:
        load_directory(self, getattr(self, 'current_directory', '/'))
