"""
Set the Duet's clock from the PC when LogIQ connects, if the board does not know the date yet.

Duet Web Control sets it at login (rr_connect?time=...); LogIQ never logs in, so on a board without a set clock
every file it writes (editor saves, uploads without a 'time', echo-to-file) is dated 1980 and the Files tab shows
no "Last Modified".  Once per board per LogIQ session, in the background: read state.time (null = not set) and,
only then, send M905 with the PC's local date and time.  Never touches a clock that is already set.
"""
import threading
import time

import requests

_done = set()


def _sync(ip):
    s = requests.Session()
    s.trust_env = False
    try:
        r = s.get(f"http://{ip}/rr_model", params={"key": "state.time", "flags": "v"}, timeout=3)
        if r.status_code != 200 or r.json().get("result") is not None:
            return                                          # clock already set (or no answer): leave it alone
        now = time.localtime()
        s.get(f"http://{ip}/rr_gcode",
              params={"gcode": f'M905 P"{time.strftime("%Y-%m-%d", now)}" S"{time.strftime("%H:%M:%S", now)}"'},
              timeout=3)
    except (requests.RequestException, ValueError):
        _done.discard(ip)                                   # try again on the next connect
    finally:
        s.close()


def sync_board_clock_once(self):
    try:
        from fcn_monitor.fcn_duet import get_clean_duet_ip
        ip = get_clean_duet_ip(self)
    except Exception:
        return
    if ip in _done:
        return
    _done.add(ip)
    threading.Thread(target=_sync, args=(ip,), name="duet-clock", daemon=True).start()
