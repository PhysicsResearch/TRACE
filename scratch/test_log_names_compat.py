"""Log files with product names: new logs say DYNAMIQ / KINETIQ / LogIQ, old logs (Lung Phantom / Motion Platform /
TRACE) still read the same.     python scratch/test_log_names_compat.py"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"C:\TRACE")
os.chdir(r"C:\TRACE")

from fcn_logs import log_analysis as la
from fcn_logs.product_names import canonical_device, device_label

FAILS = []
N = [0]


def check(name, ok, info=""):
    N[0] += 1
    print(("PASS " if ok else "FAIL ") + name + (f"  [{info}]" if info and not ok else ""), flush=True)
    if not ok:
        FAILS.append(name)


# ---- names
check("01 written names", device_label("Motion Platform") == "KINETIQ" and device_label("Lung Phantom") == "DYNAMIQ")
for txt, want in [("KINETIQ", "Motion Platform"), ("Motion Platform", "Motion Platform"), ("motion platform", "Motion Platform"),
                  ("KINETIQ (motion platform)", "Motion Platform"), ("DYNAMIQ", "Lung Phantom"),
                  ("Lung Phantom", "Lung Phantom"), ("lung phantom", "Lung Phantom"), ("Lung", "Lung Phantom"),
                  ("", None), (None, None), ("Other rig", "Other rig")]:
    check(f"02 read {txt!r} -> {want!r}", canonical_device(txt) == want, canonical_device(txt))
check("03 round trip", all(canonical_device(device_label(d)) == d for d in ("Motion Platform", "Lung Phantom")))

# ---- the reader on old and new headers (v2 format: ';' columns, decimal comma)
HEAD = ("# Computer Time: 2026-11-09 10:00:00.000\r\n# G-code: 0:/gcodes/job.gcode\r\n# Device: {dev}\r\n"
        "# Axes (Duet order): X,Y,Z,A,B,C,D,a,c,e,f\r\n"
        "# Positions: actual (Duet machinePosition)\r\n"
        "# Probe: 0 none | 1-1499 detector | 2000 Release button | -1000 waiting for sensor (sensor_wait)\r\n"
        "# Wait timing: start = when {sw} received the Duet message\r\n")
PLAT = "Time_s;Pos_LAT_mm;Pos_SI_mm;Pos_AP_mm;Pos_A_mm;Probe\r\n0,0;0,0;0,0;0,0;0,0;0\r\n0,1;0,5;0,5;0,5;0,5;0\r\n0,2;1,0;1,0;1,0;1,0;0\r\n"
PHAN = "Time_s;Pos_X_mm;Pos_Y_mm;Pos_Z_mm;Probe\r\n0,0;0,0;0,0;0,0;0\r\n0,1;0,5;0,0;0,0;0\r\n0,2;1,0;0,0;0,0;0\r\n"
tmp = tempfile.mkdtemp(prefix="kq_names_")
cases = [
    ("new_platform", "KINETIQ", "LogIQ", PLAT, "Motion Platform"),
    ("old_platform", "Motion Platform", "TRACE", PLAT, "Motion Platform"),
    ("new_phantom", "DYNAMIQ", "LogIQ", PHAN, "Lung Phantom"),
    ("old_phantom", "Lung Phantom", "TRACE", PHAN, "Lung Phantom"),
]
for name, dev, sw, body, want in cases:
    path = os.path.join(tmp, f"log_{name}.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(HEAD.format(dev=dev, sw=sw) + body)
    try:
        lg = la.read_trace_log(path)
        meta = lg.meta if hasattr(lg, 'meta') else lg[1]
        check(f"10 {name}: device read as {want!r}", meta.get('device') == want, meta.get('device'))
        check(f"11 {name}: device taken from the header", meta.get('device_source') == 'header', meta.get('device_source'))
        check(f"12 {name}: format recognised", meta.get('format') == 'trace-header', meta.get('format'))
    except Exception as e:
        check(f"10 {name}: reads", False, repr(e))

# ---- the Log files tab label and the Planning importer
from fcn_create_gui.tab_logs import _short_device
check("20 Log files tab shows the product", _short_device("Motion Platform") == "KINETIQ" and _short_device("KINETIQ") == "KINETIQ"
      and _short_device("Lung Phantom") == "DYNAMIQ" and _short_device("DYNAMIQ") == "DYNAMIQ" and _short_device(None) == '')
from fcn_plan import fcn_import as fi
for name, _dev, _sw, _b, want in cases:
    path = os.path.join(tmp, f"log_{name}.csv")
    try:
        ok_log = fi.is_trace_log_file(path)
        check(f"21 {name}: Planning importer recognises the log", bool(ok_log), ok_log)
    except Exception as e:
        check(f"21 {name}: Planning importer recognises the log", False, repr(e))

# ---- the writer (header text in the logger)
src = open(r"C:\TRACE\fcn_monitor\fcn_duet.py", encoding="utf-8").read()
check("30 logger writes the product name", 'f"# Device: {_product_device_label(device)}"' in src)
check("31 logger names LogIQ in the wait-timing line", "when LogIQ received the Duet message" in src
      and "when TRACE received" not in src)

print(f"\n{N[0] - len(FAILS)}/{N[0]} passed", flush=True)
sys.exit(1 if FAILS else 0)
