"""Upload File (several files, any type) against a fake Duet rr_upload.   python scratch/test_upload_multi.py"""
import os
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"C:\TRACE")
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QWidget

received = {}


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        q = urllib.parse.urlparse(self.path)
        name = urllib.parse.parse_qs(q.query)['name'][0]
        n = int(self.headers.get('Content-Length', 0))
        received[name] = self.rfile.read(n)
        body = b'{"err":0}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
port = srv.server_address[1]

app = QApplication.instance() or QApplication(sys.argv)
import fcn_control.fcn_filesystem as FS
import fcn_control.upload_multi as UM

src = r"C:\TRACE\MP_setup_files"
files = [os.path.join(src, n) for n in ("homeall.g", "home'a.g", "config.g")]
QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: (files, ""))
msgs = []
QMessageBox.information = staticmethod(lambda *a, **k: msgs.append(("info", a[2])))
QMessageBox.critical = staticmethod(lambda *a, **k: msgs.append(("error", a[2])))
FS.get_clean_duet_ip = lambda self: f"127.0.0.1:{port}"
reloaded = []
FS.load_directory = lambda self, d: reloaded.append(d)

w = QWidget()
w.duet_connected = True
w.current_directory = "/"
from PySide6.QtWidgets import QComboBox
w.fileCategoryCombo = QComboBox(w)
w.fileCategoryCombo.addItems(["G-code", "Macros", "System"])
w.fileCategoryCombo.setCurrentText("System")
UM.upload_files(w)

ok = True
for f in files:
    name = os.path.basename(f)
    keys = [k for k in received if k.endswith("/" + name)]
    same = bool(keys) and received[keys[0]] == open(f, 'rb').read()
    print(f"{name:12s} -> {keys[0] if keys else 'MISSING'}  content equal: {same}")
    ok &= same and keys[0] == "0:/sys/" + name
print("message:", msgs)
print("folder reloaded:", reloaded)
ok &= len(msgs) == 1 and msgs[0][0] == "info" and reloaded == ["/"]
print("PASS" if ok else "FAIL")
srv.shutdown()
