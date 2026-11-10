"""
End-to-end check of the Status-tab live log against a simulated Duet (offscreen, real Status and
Planning tabs, real timers):
  - Start a Motion Platform job with the Planning combo left on "Lung Phantom": the log must use
    the platform columns (device from the G-code), never X/Y/Z zeros
  - simulated RRF: machinePosition cached lazily for 200 ms, flags=f replies without 'letter',
    paginated move.axes letters (page 2 fails once), one empty 'state' reply mid-job, detector
    probe 1000, release via global.force_release_sensor
  - the REAL sensor_wait.g wait: the job stays 'processing', the macro's echo messages are queued
    and rr_reply hands each one out once; the detector (> 500) or force_release ends the wait
    within the macro's 10 ms loop ("Sensor detected." / "force released" message)
  - every request takes SIM.latency (60 ms) and at most SIM.parallel requests are served at once
    (semaphore), so request contention between the position poll, the Duet-message poll and the
    GUI-thread dashboard is modelled
  - every logged row equals the plotted point (same t, values, probe); the pre-position is not
    logged; Probe 2000 after the Release button; the run ends with '# End: job finished'
  - log format v2: 10-line header, ';' columns, decimal comma everywhere, nothing but rows between
    the column names and the last row, run notes after the data in time order, '# End' last, no ';'
    in a '#' line, on every close path; Load Log and the Planning import read v2 and v1 logs
  - sensor wait mark: Probe -1000 from the first sample at or after the read that brought the
    "Waiting for sensor signal..." message up to the detector / Release sample (real value kept),
    probe 300 inside a wait kept, two waits per job, race case (detector right after the message)
    unmarked, '# Wait start' bounds contain the true start, '# Wait end' within one sample
  - one rr_reply reader (ReplyPoller); the dashboard and pause/resume do not read it while the
    poller runs; the Duet message field still shows the replies; it reads when the snapshot's
    seqs.reply changes (else on its timer); a 1.6 s WiFi stall loses no message, a longer one is
    reported; Release sends only 'set global...' (sensor_wait.g creates and resets the global, a
    'global ...' line is only an RRF error that hides the macro's messages from 'Include pause')
  - split mode: the ReplyPoller reads at the dashboard's tick rate (as the dashboard did itself);
    the motion backup end of a wait compares only against a position read after the M400 settled
  - GUI thread blocked 0.7 s every second: no gaps in the log
  - combined snapshot failing (503) -> split mode; a Lung Phantom job logs X/Y/Z
  - the Planning import and the Status-tab loader read the new log (logged DOF kept, raw axes
    shown, sensor waits shaded amber)
  - position sampling with and without the ReplyPoller (median / max interval, samples per s),
    reading on seqs.reply changes and on its timer, with 1, 2 and 3 requests served at once, and
    the GUI-thread dashboard tick time
Run:  set QT_QPA_PLATFORM=offscreen  &  C:\\Users\\gabri\\anaconda3\\envs\\TRACE\\python.exe scratch\\test_position_log.py
"""
import os
import re
import sys
import json
import math
import time
import tempfile
import threading
import collections
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import numpy as np
import pandas as pd
from unittest.mock import MagicMock
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget, QTabWidget, QLineEdit, QCheckBox, QMessageBox, QTextEdit

app = QApplication.instance() or QApplication(sys.argv)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.warning = staticmethod(lambda *a, **k: print("  [warning]", a[1] if len(a) > 1 else "", a[2] if len(a) > 2 else ""))
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.critical = staticmethod(lambda *a, **k: print("  [critical]", a[2] if len(a) > 2 else ""))

TMP = tempfile.mkdtemp(prefix="trace_poslog_")
from fcn_monitor import fcn_duet
fcn_duet.get_config_path = lambda name, for_writing=False: os.path.join(TMP, name)   # keep the user's debug dump
from fcn_monitor.fcn_duet import (start_selected_gcode_execution, release_sensor_wait_action,
                                  load_log_file_into_status, get_clean_duet_ip, update_status_tab_dashboard,
                                  pause_continue_GCODE, render_status_plot, handle_duet_reply,
                                  handle_position_sample, end_run, ReplyPoller)
from fcn_plan.fcn_import import parse_trace_log_file, import_trace_log_action
from fcn_create_gui.tab_status import build_status_tab
from fcn_create_gui.tab_planning import build_planning_tab

FAILS = []
NCHECK = [0]


def check(cond, msg):
    NCHECK[0] += 1
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        FAILS.append(msg)


# Who reads rr_reply: every fcn_duet request goes through this module global
RR_REPLY_BY_THREAD = collections.Counter()
_orig_duet_request = fcn_duet.duet_request


def _counting_duet_request(url, *a, **k):
    if '/rr_reply' in str(url):
        RR_REPLY_BY_THREAD[threading.current_thread().name] += 1
    return _orig_duet_request(url, *a, **k)


fcn_duet.duet_request = _counting_duet_request

# ============================================================== simulated Duet
LETTERS = ['X', 'Y', 'Z', 'A', 'B', 'C', 'D', 'a', 'c', 'e', 'f']
NAMES = ['X', 'Y', 'Z', 'A', 'B', 'C', 'D', "'a", "'c", "'e", "'f"]
PLATFORM_JOB = """; TIME: 12
G90
M203 I6
G1 F1000 A35 B35 C35 D35 'e50 'f50 'a25 'c25
G1 F37.5 A37.5 B37.5 C37.5 D37.5 'e50 'f50 'a25 'c25
M98 P"0:macros/sensor_wait.g"
G1 F42.43 A37.5 B37.5 C37.5 D37.5 'e50 'f50 'a26 'c26
"""
WAITS_JOB = """; TIME: 9
G90
M203 I6
G1 F1000 A35 B35 C35 D35 'e50 'f50 'a25 'c25
G1 F50 A36 B36 C36 D36 'e50 'f50 'a25 'c25
M98 P"0:macros/sensor_wait.g"
G1 F60 A36 B36 C36 D36 'e50 'f50 'a26 'c26
M98 P"0:macros/sensor_wait.g"
G1 F75 A36 B36 C36 D36 'e50 'f50 'a27 'c27
M98 P"0:macros/sensor_wait.g"
G1 F75 A36 B36 C36 D36 'e50 'f50 'a28 'c28
"""
PHANTOM_JOB = """; TIME: 4
G90
G1 F1000 X0 Y0 Z0
G1 F150 X5 Y0 Z0
"""
WAIT_MSG = "Waiting for sensor signal..."
DETECTED_MSG = "Sensor detected. Continuing G-code."
RELEASED_MSG = "Sensor wait force released by user. Continuing G-code."


def _plat4(v):
    return {'A': v, 'B': v, 'C': v, 'D': v}


# Job scripts: 'delay' / 'move' items take dt s; 'wait' is sensor_wait.g (M400 done, echo, loop
# every 10 ms until the probe is above 500 or force_release is set). 'det': detector windows
# (offset from the item start, length, value).
SCRIPTS = {
    'platform': [
        {'do': 'delay', 'dt': 0.3},
        {'do': 'move', 'dt': 4.0, 'to': _plat4(37.5), 'det': [(1.7, 1.0, 1000)]},
        {'do': 'delay', 'dt': 0.5},
        {'do': 'wait'},                                            # ended by the Release button
        {'do': 'move', 'dt': 2.0, 'to': {"'a": 26.0, "'c": 26.0}},
        {'do': 'delay', 'dt': 0.5}],
    'waits': [
        {'do': 'delay', 'dt': 0.3},
        {'do': 'move', 'dt': 1.2, 'to': _plat4(36.0)},
        {'do': 'delay', 'dt': 0.3},
        {'do': 'wait', 'det': [(1.0, 0.3, 300), (1.63, 0.6, 1000)]},   # A: probe 300 inside, detector at +1.63 s
        {'do': 'move', 'dt': 1.0, 'to': {"'a": 26.0, "'c": 26.0}},
        {'do': 'delay', 'dt': 0.3},
        {'do': 'wait', 'det': [(0.87, 0.5, 1000)]},                    # B: detector at +0.87 s
        {'do': 'move', 'dt': 0.8, 'to': {"'a": 27.0, "'c": 27.0}},
        {'do': 'delay', 'dt': 0.2},
        {'do': 'wait', 'det': [(0.012, 0.6, 1000)]},                   # C: race, detector 12 ms after the echo
        {'do': 'move', 'dt': 0.8, 'to': {"'a": 28.0, "'c": 28.0}},
        {'do': 'delay', 'dt': 0.5}],
    'phantom': [
        {'do': 'delay', 'dt': 0.3},
        {'do': 'move', 'dt': 2.0, 'to': {'X': 5.0}},
        {'do': 'delay', 'dt': 0.5}],
}


class Sim:
    def __init__(self):
        self.lock = threading.Lock()
        self.pos = {n: 0.0 for n in NAMES}
        self.pos.update({'A': 30.0, 'B': 30.0, 'C': 30.0, 'D': 30.0, "'e": 45.0, "'f": 45.0, "'a": 20.0, "'c": 20.0})
        self.target = dict(self.pos)
        self.segments = []            # (t0, t1, {axis: (from, to)})
        self.status = 'idle'
        self.job = None               # {'kind', 'n', 'script', 'i', 't_ph', 'begun'}
        self.cache = dict(self.pos)
        self.cache_t = -1.0
        self.release_t = None         # when global.force_release_sensor was set
        self.combined_503 = False
        self.page2_fail_once = True
        self.state_blip_done = False
        self.combined_blip_done = False
        self.detector = []            # (t0, t1, value) absolute perf_counter times
        self.msgs = []                # (t, text) echo messages; rr_reply hands each one out once
        self.seq = 0                  # seqs.reply: +1 per queued message (in the d99f snapshot)
        self.seqs_enabled = True
        self.global_exists = False    # global.force_release_sensor (sensor_wait.g creates it)
        self.release_cmds = []        # (t, command) of the force_release commands
        self.reply_hold = 0.0         # rr_reply response held this long after it was handled (WiFi stall)
        self.waits = []               # one dict per sensor_wait.g wait (true start / end / trigger)
        self.requests = 0
        self.reply_reads = 0
        self.m32_count = 0
        self.latency = 0.06           # s per request (WiFi Duet: ~60-80 ms)
        self.parallel = 2
        self.sem = threading.BoundedSemaphore(self.parallel)
        self.inflight = 0
        self.max_inflight = 0

    def set_parallel(self, n):
        self.parallel = n
        self.sem = threading.BoundedSemaphore(n)

    def queue(self, t, text):         # a Duet message (echo / error) for rr_reply
        self.msgs.append((t, text))
        self.seq += 1

    # --- motion -------------------------------------------------------------------------
    def actual(self, now):
        p = dict(self.pos)
        for t0, t1, moves in self.segments:
            f = min(max((now - t0) / (t1 - t0), 0.0), 1.0)
            for ax, (a, b) in moves.items():
                if now >= t0:
                    p[ax] = a + (b - a) * f
        return p

    def add_move(self, now, targets, duration):
        cur = self.actual(now)
        moves = {ax: (cur[ax], v) for ax, v in targets.items() if abs(cur[ax] - v) > 1e-12}
        self.pos = cur
        self.segments = [(now, now + duration, moves)] if moves else []
        self.target = dict(cur)
        self.target.update(targets)
        return now + duration

    def machine(self, now):            # RRF: lazy refresh, at most every 200 ms
        if now - self.cache_t > 0.200:
            self.cache = self.actual(now)
            self.cache_t = now
        return self.cache

    # --- sensor_wait.g ----------------------------------------------------------------------
    def macro_end(self, tw):
        """(end time, 'detector' | 'release', trigger time) of a wait that started at tw, or Nones."""
        trig, kind = None, None
        for a, b, v in self.detector:
            if v > 500 and b > tw:
                ta = max(a, tw)
                if trig is None or ta < trig:
                    trig, kind = ta, 'detector'
        r = self.release_t
        if r is not None and r >= tw and (trig is None or r < trig):
            trig, kind = r, 'release'
        if trig is None:
            return None, None, None
        k = max(0, math.ceil((trig - tw) / 0.010 - 1e-9))     # the loop checks every 10 ms
        return tw + k * 0.010, kind, trig

    def waiting(self):
        with self.lock:
            return (self.job is not None and bool(self.waits) and self.waits[-1]['t_end'] is None
                    and self.waits[-1]['n'] == self.job['n'])

    # --- job script -----------------------------------------------------------------------
    def step(self, now):
        j = self.job
        if j is None:
            if self.segments and now >= self.segments[0][1]:
                self.pos = self.actual(now)
                self.segments = []
            if self.status == 'busy' and not self.segments:
                self.status = 'idle'
            return
        while self.job is not None:
            j = self.job
            if j['i'] >= len(j['script']):
                self.pos = self.actual(j['t_ph'])
                self.segments = []
                self.status = 'idle'
                self.job = None
                return
            it = j['script'][j['i']]
            t_ph = j['t_ph']
            if not j['begun']:
                if now < t_ph:
                    return
                j['begun'] = True
                if j['i'] > 0:
                    self.status = 'processing'
                for off, length, val in it.get('det', []):
                    self.detector.append((t_ph + off, t_ph + off + length, val))
                if it['do'] == 'move':
                    self.add_move(t_ph, it['to'], it['dt'])
                elif it['do'] == 'wait':
                    self.global_exists = True            # sensor_wait.g: global ... / set ... = false
                    self.queue(t_ph, WAIT_MSG)
                    self.waits.append({'n': j['n'], 'kind': j['kind'], 't_start': t_ph, 't_end': None,
                                       'end': None, 'trigger': None})
            if it['do'] == 'wait':
                t_end, kind, trig = self.macro_end(t_ph)
                if t_end is None or t_end > now:
                    return
                self.queue(t_end, DETECTED_MSG if kind == 'detector' else RELEASED_MSG)
                self.waits[-1].update(t_end=t_end, end=kind, trigger=trig)
            else:
                t_end = t_ph + it['dt']
                if t_end > now:
                    return
            j['i'] += 1
            j['t_ph'] = t_end
            j['begun'] = False

    def probe(self, now):
        vals = [v for a, b, v in self.detector if a <= now < b]
        return max(vals) if vals else 0

    def axes(self, now, with_letters):
        m = self.machine(now)
        out = []
        for let, n in zip(LETTERS, NAMES):
            ax = {'machinePosition': round(m[n], 4), 'userPosition': round(self.target.get(n, m[n]), 3)}
            if with_letters:
                ax.update({'letter': let, 'homed': True})
            out.append(ax)
        return out


SIM = Sim()


class FakeDuet(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, body=None, text=None):
        self._resp = (code, body, text)

    def _send(self):
        code, body, text = self._resp
        data = (json.dumps(body) if body is not None else (text or "")).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json' if body is not None else 'text/plain')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        sem = SIM.sem
        hold = 0.0
        with sem:                                    # at most SIM.parallel requests served at once
            with SIM.lock:
                SIM.inflight += 1
                SIM.max_inflight = max(SIM.max_inflight, SIM.inflight)
            try:
                time.sleep(SIM.latency * 0.5)        # request on its way / queued in the Duet
                self._resp = None
                self.route()
                if self._resp is None:
                    self.reply(404, {"err": "not found"})
                time.sleep(SIM.latency * 0.5)        # reply on its way back
                if self.path.startswith('/rr_reply'):
                    hold = SIM.reply_hold
                if hold <= 0:
                    self._send()
            finally:
                with SIM.lock:
                    SIM.inflight -= 1
        if hold > 0:                                 # WiFi stall: rr_reply already handed its text out
            time.sleep(hold)
            try:
                self._send()
            except Exception:
                pass

    def route(self):
        now = time.perf_counter()                    # the Duet handles the request here
        u = urlparse(self.path)
        q = parse_qs(u.query)
        key = q.get('key', [''])[0]
        flags = q.get('flags', [''])[0]
        with SIM.lock:
            SIM.requests += 1
            SIM.step(now)
            if u.path == '/rr_model' and not key and flags == 'd99f':
                if SIM.combined_503:
                    return self.reply(503, {"err": "busy"})
                state = {'status': SIM.status}
                if (SIM.job and SIM.job['kind'] == 'platform' and SIM.job['i'] >= 1 and not SIM.combined_blip_done
                        and now - SIM.job['t0'] > 3.5):
                    SIM.combined_blip_done = True
                    state = {}
                body = {'key': '', 'flags': 'd99f', 'result': {
                    'move': {'axes': SIM.axes(now, False)},
                    'sensors': {'probes': [{'value': [SIM.probe(now)]}]},
                    'state': state}}
                if SIM.seqs_enabled:
                    body['result']['seqs'] = {'reply': SIM.seq, 'state': 0}
                return self.reply(200, body)
            if u.path == '/rr_model' and key == 'move.axes':
                if flags == 'f':
                    return self.reply(200, {'key': key, 'flags': 'f', 'result': SIM.axes(now, False)})
                if flags == 'd99':
                    return self.reply(200, {'key': key, 'flags': 'd99', 'result': SIM.axes(now, True)[:10], 'next': 10})
                if flags == 'd99a10':
                    if SIM.page2_fail_once:
                        SIM.page2_fail_once = False
                        return self.reply(503, {"err": "busy"})
                    return self.reply(200, {'key': key, 'flags': flags, 'result': SIM.axes(now, True)[10:], 'next': 0})
            if u.path == '/rr_model' and key == 'sensors.probes':
                return self.reply(200, {'key': key, 'result': [{'value': [SIM.probe(now)]}]})
            if u.path == '/rr_model' and key == 'sensors':
                return self.reply(200, {'key': key, 'result': {'probes': [{'value': [SIM.probe(now)]}]}})
            if u.path == '/rr_model' and key == 'state':
                if (SIM.job and SIM.job['kind'] == 'platform' and SIM.job['i'] >= 1 and not SIM.state_blip_done
                        and now - SIM.job['t0'] > 3.0):
                    SIM.state_blip_done = True
                    return self.reply(503, {"err": "busy"})      # partly failed dashboard poll
                return self.reply(200, {'key': key, 'result': {'status': SIM.status}})
            if u.path == '/rr_model' and key == 'move.currentMove':
                return self.reply(200, {'key': key, 'result': {'requestedSpeed': 0.0, 'topSpeed': 0.0}})
            if u.path == '/rr_model' and key == 'job':
                return self.reply(200, {'key': key, 'result': {'file': {'fileName': None}, 'duration': None}})
            if u.path == '/rr_model' and key == 'network':
                return self.reply(200, {'key': key, 'result': {}})
            if u.path == '/rr_reply':
                SIM.reply_reads += 1
                out = [m for t, m in SIM.msgs if t <= now]          # handed out once
                SIM.msgs = [(t, m) for t, m in SIM.msgs if t > now]
                return self.reply(200, text="".join(m + "\n" for m in out))
            if u.path == '/rr_download':
                name = q.get('name', [''])[0]
                txt = PHANTOM_JOB if 'phantom' in name else (WAITS_JOB if 'waits' in name else PLATFORM_JOB)
                return self.reply(200, text=txt)
            if u.path == '/rr_gcode':
                g = q.get('gcode', [''])[0]
                if 'force_release_sensor' in g:
                    # RRF: 'global x = ...' is an error once x exists, 'set global.x' one before
                    SIM.release_cmds.append((now, g))
                    t_ws = SIM.waits[-1]['t_start'] if SIM.waits else -1.0
                    is_set = g.strip().startswith('set ')
                    if is_set != SIM.global_exists:
                        SIM.queue(now, "Error: unknown variable 'force_release_sensor'" if is_set
                                  else "Error: variable 'force_release_sensor' already exists")
                    else:
                        SIM.global_exists = True
                        if SIM.release_t is None or SIM.release_t < t_ws:
                            SIM.release_t = now
                elif g.startswith('M32'):
                    SIM.m32_count += 1
                    kind = 'phantom' if 'phantom' in g else ('waits' if 'waits' in g else 'platform')
                    SIM.job = {'kind': kind, 'n': SIM.m32_count, 't0': now, 'script': SCRIPTS[kind],
                               'i': 0, 't_ph': now, 'begun': False}
                    SIM.status = 'idle'
                elif 'G1' in g:
                    targets = {}
                    for m in re.finditer(r"('?[A-Za-z])([-+]?\d*\.?\d+)", g.split('G1', 1)[1].split('\n')[0]):
                        let, val = m.group(1), float(m.group(2))
                        if let in ('F', 'f') and not let.startswith("'"):
                            continue
                        name = ("'" + let[1].lower()) if let.startswith("'") else let.upper()
                        if name in SIM.pos:
                            targets[name] = val
                    SIM.add_move(now, targets, 1.0)
                    SIM.status = 'busy'
                return self.reply(200, {'buff': 255})


srv = ThreadingHTTPServer(('127.0.0.1', 0), FakeDuet)
threading.Thread(target=srv.serve_forever, daemon=True).start()
PORT = srv.server_address[1]


# ============================================================== real Status + Planning tabs
class Win(QWidget):
    def __init__(self):
        super().__init__()
        self.tab_status = QWidget(self)
        self.tab_planning = QWidget(self)
        self.tabWidget = QTabWidget(self)
        self.tabWidget.addTab(self.tab_planning, "Planning")
        self.tabModules = QTabWidget(self)
        for _ in range(4):
            self.tabModules.addTab(QWidget(self), "tab")


ui = Win()
ui.duet_ip = f"127.0.0.1:{PORT}"
ui.status_advanced_mode = True
build_planning_tab(ui)
build_status_tab(ui)
ui.input_plat_lat = QLineEdit("300", ui)
ui.input_plat_si = QLineEdit("500", ui)
ui.DuetIPAddress = QLineEdit(f"127.0.0.1:{PORT}", ui)
ui.duet_log_console = QTextEdit()
get_clean_duet_ip(ui)
ui.duet_connected = True
ui.duet_api_mode = 'model'
ui.duet_status_code = 'I'
ui.PhOperFolder.setText(TMP)
check(ui.check_record_log.isChecked(), "'Record Data Log' is checked by default")
check('log_DDMMYYYY_HH_MM_SS.csv' in ui.check_record_log.text(), f"record checkbox shows the new name ({ui.check_record_log.text()})")
ui.check_show_reference.setChecked(False)
check(ui.combo_device.currentText() == "Lung Phantom", "Planning combo left on 'Lung Phantom' (the 6 Nov situation)")
RP = getattr(ui, 'duet_reply_poller', None)
check(isinstance(RP, ReplyPoller) and ui.status_fast_timer.companion is RP and RP.isActive(),
      "tab build created the ReplyPoller as companion of the position poll and started it")

# Recorders: every reply as handled on the GUI thread (+ the Duet message field afterwards), every
# live sample time, every dashboard tick duration, every rr_reply read the poller sends
REPLIES = []                        # (t_fetch, t_prev, text, statusDuetMessage text after)
SAMPLE_T = []
TICKS = []                          # (t_start, duration, reply poller active)
RP_READS = []                       # send times of the poller's reads
_orig_reply_handler = RP._handler


def _rec_reply(r):
    _orig_reply_handler(r)
    REPLIES.append((r[0], r[1], r[2], ui.statusDuetMessage.text(), tuple(r)))


RP._handler = _rec_reply
_orig_sample_handler = ui.status_fast_timer._handler


def _rec_sample(s):
    if isinstance(s, dict) and 't' in s and s.get('event') is None:
        SAMPLE_T.append(float(s['t']))
    _orig_sample_handler(s)


ui.status_fast_timer._handler = _rec_sample
_orig_rp_read = RP._read


def _rec_rp_read():
    RP_READS.append(time.perf_counter())
    return _orig_rp_read()


RP._read = _rec_rp_read
ui.status_polling_timer.timeout.disconnect()


def _timed_dashboard():
    t = time.perf_counter()
    active = RP.isActive()
    update_status_tab_dashboard(ui)
    TICKS.append((t, time.perf_counter() - t, active))


ui.status_polling_timer.timeout.connect(_timed_dashboard)

# Collect every plotted point of the run as the handler produces it
BUSY = {'blocked': 0.0}


def busy_gui():                      # stands in for heavy redraws on the GUI thread
    t = time.perf_counter()
    time.sleep(0.7)
    BUSY['blocked'] += time.perf_counter() - t


busy = QTimer()
busy.setInterval(1000)
busy.timeout.connect(busy_gui)

EV = {}


def wait_until(cond, timeout):
    t_end = time.perf_counter() + timeout
    while time.perf_counter() < t_end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


def run_job(fname, release_when_paused, double_start=False):
    ui.selected_gcode_path = fname
    EV.clear()
    EV['t_start_call'] = time.perf_counter()
    m32_before = SIM.m32_count
    if double_start:
        QTimer.singleShot(400, lambda: start_selected_gcode_execution(ui))   # pressed again while pre-positioning
    start_selected_gcode_execution(ui)
    EV['m32'] = SIM.m32_count - m32_before
    EV['job_n'] = SIM.m32_count
    EV['ref_loaded'] = ui.status_reference_data is not None and ui.check_show_reference.isChecked()
    EV['label'] = ui.statusGcodeName.text()
    EV['run_t0'] = ui.run_t0
    if release_when_paused:
        ok = wait_until(SIM.waiting, 30)                  # sensor_wait.g waits (job stays 'processing')
        wait_until(lambda: False, 1.0)                      # waiting for a while
        EV['t_release'] = time.perf_counter()
        release_sensor_wait_action(ui)
        EV['released'] = ok
    wait_until(lambda: getattr(ui, 'run_active', False) is not True, 40)
    EV['t_end'] = time.perf_counter()
    wait_until(lambda: False, 1.5)                          # trailing samples must not be logged


def read_log(path):
    with open(path, encoding='utf-8') as f:
        lines = f.read().splitlines()
    head = [l for l in lines if l.startswith('#')]
    df = pd.read_csv(path, comment='#', sep=';', decimal=',')      # format v2
    return head, df, lines


def num(s):
    """A number of the log text (decimal comma)."""
    return float(str(s).replace(',', '.'))


HDR_POS = "# Positions: actual (Duet machinePosition, refreshed at most every 200 ms, CAN expansion-board axes about every 100 ms)"
HDR_PROBE = "# Probe: 0 none | 1-1499 detector | 2000 Release button | -1000 waiting for sensor (sensor_wait)"
HDR_WAIT = ('# Wait timing: start = when LogIQ received the Duet message (read as soon as a position sample shows a '
            'new message, else every 0,5-1 s), so the real start is earlier, normally by up to ~0,5 s (on a slow link up '
            'to ~2 s). End = first '
            'position sample with the detector above 500 or Release pressed (within one sample, ~0,08 s), otherwise as '
            'stated at the end of the file')
HDR_NOTES = ('# Run notes: the times of each sensor wait (with the window in which the Duet sent its message), connection '
             'gaps and the run end are listed at the end of the file')
HDR_FORMAT = "# Format: columns separated by semicolons, decimal comma"
RE_WSTART = re.compile(r'^# Wait start: "Waiting for sensor signal\.\.\." received at (-?\d+,\d{3}) s '
                       r'\(Duet sent it between (-?\d+,\d{3}) and (-?\d+,\d{3}) s\)$')
RE_WEND = re.compile(r'^# Wait end: (detector (\d+)|Release button|Duet message "[^"]*"|motion|run end) at (-?\d+,\d{3}) s \((.*)\)$')
RE_NOTE_T = re.compile(r' at (-?\d+,\d{3}) s')
RE_TIME_CELL = re.compile(r'-?\d+,\d{4}')
RE_POS_CELL = re.compile(r'-?\d+,\d{3}')
RE_PROBE_CELL = re.compile(r'-?\d+(,\d+)?')
NOTE_PREFIXES = ('# Wait start:', '# Wait end:', '# Wait not marked:', '# Message read failed at ', '# Gap:', '# Gap end:')
V2_SEEN = {'neg_decimal': 0, 'neg_probe': 0, 'logs': 0}


def check_v2(label, lines, end_reason=None):
    """Format v2 of one log: the 10 header lines, ';' columns with a decimal comma in every cell, only
    rows between the column names and the last row, then the run notes in time order, '# End' last,
    no ';' in any '#' line. Returns (rows as lists of cells, notes)."""
    V2_SEEN['logs'] += 1
    errs = []
    hdr_ok = (len(lines) > 11 and all(l.startswith('#') for l in lines[:10]) and not lines[10].startswith('#')
              and lines[0].startswith('# Computer Time: ') and re.search(r"\d{2}:\d{2}:\d{2}\.\d{3}$", lines[0]) is not None
              and lines[1].startswith('# G-code: ') and lines[2].startswith('# Device: ')
              and lines[3].startswith('# Axes (Duet order): ') and lines[4] == HDR_POS and lines[5] == HDR_PROBE
              and lines[6] == HDR_WAIT and lines[7] == HDR_NOTES
              and re.fullmatch(r"# Recording from: \d+,\d{3} s of the run", lines[8]) is not None and lines[9] == HDR_FORMAT)
    if not hdr_ok:
        errs.append(f"header {lines[:11]}")
    cols = lines[10].split(';') if len(lines) > 10 else []
    if len(cols) < 5 or ',' in lines[10] or cols[0] != 'Time_s' or cols[-1] != 'Probe':
        errs.append(f"column line {lines[10] if len(lines) > 10 else None}")
    data_idx = [i for i, l in enumerate(lines) if i > 10 and not l.startswith('#')]
    last = data_idx[-1] if data_idx else 10
    between = [l for l in lines[11:last + 1] if l.startswith('#') or not l.strip()]
    if between:
        errs.append(f"'#' / empty lines between the column names and the last row: {between[:3]}")
    rows = [lines[i].split(';') for i in data_idx]
    for r in rows:
        if (len(r) != len(cols) or not RE_TIME_CELL.fullmatch(r[0]) or not all(RE_POS_CELL.fullmatch(c) for c in r[1:-1])
                or not RE_PROBE_CELL.fullmatch(r[-1]) or any('.' in c for c in r)):
            errs.append(f"row {';'.join(r)}")
            break
        V2_SEEN['neg_decimal'] += sum(1 for c in r[:-1] if c.startswith('-'))
        V2_SEEN['neg_probe'] += r[-1].startswith('-')
    notes = lines[last + 1:]
    if not notes or not all(l.startswith('#') for l in notes):
        errs.append(f"after the last row only '#' lines: {notes[:3]}")
    if notes and not (notes[-1].startswith('# End: ') and sum(1 for l in notes if l.startswith('# End: ')) == 1):
        errs.append(f"'# End' is the last line: {notes[-1]}")
    if end_reason is not None and notes and not notes[-1].startswith(f"# End: {end_reason} at "):
        errs.append(f"end reason {notes[-1]}")
    bad_prefix = [l for l in notes[:-1] if not l.startswith(NOTE_PREFIXES)]
    if bad_prefix:
        errs.append(f"unknown note lines {bad_prefix[:2]}")
    times = []
    for l in notes:
        m = RE_NOTE_T.search(l)
        if m is None:
            errs.append(f"note without a time: {l}")
            break
        times.append(num(m.group(1)))
    if any(b < a for a, b in zip(times, times[1:])):
        errs.append(f"notes not in time order: {times}")
    semi = [l for l in lines if l.startswith('#') and ';' in l]
    if semi:
        errs.append(f"';' in '#' lines: {semi[:2]}")
    dot = [l for l in lines if l.startswith('#') and re.search(r'\d\.\d', re.sub(r'"[^"]*"', '', l))
           and not l.startswith('# Computer Time: ')]
    if dot:
        errs.append(f"a '.' decimal in a '#' line: {dot[:2]}")
    check(not errs, f"{label}: format v2 ({len(rows)} rows, {len(notes)} notes after the data){'' if not errs else ': ' + str(errs[:3])}")
    return rows, notes


def start_reply_for(w):
    """The handled reply that brought the 'Waiting' message of SIM wait w."""
    for r in REPLIES:
        if WAIT_MSG in r[2] and r[0] >= w['t_start'] and (r[1] is None or r[1] <= w['t_start']):
            return r
    return None


def end_reply_for(w):
    for r in REPLIES:
        if (DETECTED_MSG in r[2] or RELEASED_MSG in r[2]) and w['t_end'] is not None and r[0] >= w['t_end']:
            return r
    return None


def check_marked_wait(label, t, probe, lines, w, run_t0, trig_val, next_start=None):
    """-1000 from the first row at/after the read up to the trigger row (real value), not after."""
    r = start_reply_for(w)
    check(r is not None, f"{label}: the 'Waiting' message was read by the ReplyPoller")
    if r is None:
        return None
    rf, tw = r[0] - run_t0, w['t_start'] - run_t0
    starts = [m for m in (RE_WSTART.match(l) for l in lines) if m and abs(num(m.group(1)) - rf) < 0.0015]
    check(len(starts) == 1, f"{label}: '# Wait start' line received at {rf:.3f} s")
    lo = hi = None
    if starts:
        lo, hi = num(starts[0].group(2)), num(starts[0].group(3))
        check(lo <= tw + 1e-3 and tw <= hi + 1e-3,
              f"{label}: bounds [{lo:.3f}, {hi:.3f}] contain the true start {tw:.3f} s (read {rf - tw:.3f} s after it)")
    i0 = int(np.searchsorted(t, rf - 1e-9))
    cand = [i for i in range(i0, len(t)) if probe[i] == trig_val]
    check(len(cand) > 0, f"{label}: trigger row with the real value {trig_val}")
    if not cand:
        return None
    ik = cand[0]
    seg = probe[i0:ik]
    check(i0 < len(t) and probe[i0] == -1000, f"{label}: first row at/after the read ({t[i0]:.3f} s) is -1000")
    check(len(seg) > 0 and set(np.unique(seg)) <= {-1000, 300}, f"{label}: rows {rf:.2f}..{t[ik]:.2f} s are -1000 "
          f"(or a real 300): {sorted(set(np.unique(seg)))}")
    before = probe[(t >= tw) & (t < rf)]
    check(not np.any(before == -1000), f"{label}: rows before the read are not marked ({len(before)} rows)")
    t_trig_true = w['trigger'] - run_t0 if w.get('trigger') is not None else None
    t_end_line = [m for m in (RE_WEND.match(l) for l in lines) if m and abs(num(m.group(3)) - t[ik]) < 0.0015]
    want = 'Release button' if trig_val == 2000 else f'detector {trig_val}'
    check(len(t_end_line) == 1 and t_end_line[0].group(1) == want,
          f"{label}: '# Wait end: {want}' at the trigger row {t[ik]:.3f} s, not from the Duet message: "
          f"{t_end_line[0].group(0) if t_end_line else None}")
    if t_trig_true is not None and w['end'] == 'detector':
        check(t[ik] >= t_trig_true - 0.04 and t[ik - 1] < t_trig_true + 0.04,
              f"{label}: end within one sample of the detector ({t_trig_true:.3f} s): previous row {t[ik - 1]:.3f}, "
              f"trigger row {t[ik]:.3f} s")
        er = end_reply_for(w)
        if er is not None:
            lead = (er[0] - run_t0) - t[ik]
            check(lead > -0.1, f"{label}: the sample end does not wait for the Duet message (message read {lead:+.3f} s later)")
            EV.setdefault('leads', []).append(lead)
    stop = len(t) if next_start is None else int(np.searchsorted(t, next_start - 1e-9))
    after = probe[ik + 1:stop]
    check(not np.any(after == -1000), f"{label}: no -1000 after the trigger row ({len(after)} rows checked)")
    return {'i0': i0, 'ik': ik, 'rf': rf, 'tw': tw, 'lo': lo, 'hi': hi}


# ============================================================== 1. platform job, combined snapshot
print("=== Motion Platform job, Planning combo on Lung Phantom, busy GUI ===")
# The axis letters come once per connection; page 2 fails once, so the poller retries after 5 s.
# Wait for that here: two 60 ms letter requests in the middle of the run would be a ~200 ms gap of
# the letter retry, not of the GUI blocking that the gap check below is about.
check(wait_until(lambda: getattr(ui, '_om_axis_letters', None) is not None, 10) and not SIM.page2_fail_once,
      f"axis letters fetched after the failed page 2 ({getattr(ui, '_om_axis_letters', None)})")
busy.start()
logs_before = set(os.listdir(TMP))
reads_main0 = RR_REPLY_BY_THREAD['MainThread']
run_job("job_platform.gcode", release_when_paused=True, double_start=True)
busy.stop()
check(EV['m32'] == 1, f"a second Start during the pre-position is ignored (M32 sent {EV['m32']}x)")
check(EV['ref_loaded'], "Start loaded the G-code reference and switched 'Show reference' on")
check(RR_REPLY_BY_THREAD['MainThread'] == reads_main0 and RR_REPLY_BY_THREAD['DuetReplyPoller'] > 3,
      f"one rr_reply reader during the run: {dict(RR_REPLY_BY_THREAD)}")
ui.statusDuetMessage.setText("some newer Duet message")
check(EV['label'] == "G-code: job_platform.gcode" and ui.statusGcodeName.text() == "G-code: job_platform.gcode",
      f"G-code name stays visible ({ui.statusGcodeName.text()})")
new_logs = sorted(f for f in set(os.listdir(TMP)) - logs_before if f.startswith('log_'))
check(len(new_logs) == 1, f"one log file for the run: {new_logs}")
check(BUSY['blocked'] > 5.0, f"GUI thread was blocked {BUSY['blocked']:.1f} s")
path = os.path.join(TMP, new_logs[0])
check(re.fullmatch(r"log_\d{8}_\d{2}_\d{2}_\d{2}\.csv", new_logs[0]) is not None
      and new_logs[0][4:12] == ui.run_wall.strftime('%d%m%Y'), f"file name {new_logs[0]} (DDMMYYYY + time)")
head, df, lines = read_log(path)
print("  " + "\n  ".join(head))
check(any(h.startswith("# Computer Time: ") and re.search(r"\d{2}:\d{2}:\d{2}\.\d{3}$", h) for h in head),
      "computer time with ms")
check(head[1] == "# G-code: 0:/gcodes/job_platform.gcode", f"G-code name on line 2 of the log ({head[1]})")
check(all(l.startswith('#') for l in lines[:10]) and lines[10].startswith('Time_s;') and lines[4] == HDR_POS
      and lines[5] == HDR_PROBE and lines[6] == HDR_WAIT and lines[7] == HDR_NOTES and lines[9] == HDR_FORMAT
      and re.fullmatch(r"# Recording from: 0,\d{3} s of the run", lines[8]) is not None,
      f"fixed 10-line header (Positions, Probe classes with -1000, Wait timing, Run notes, Recording from, Format): {lines[8]}")
others = [h for h in head[10:] if not (h.startswith('# Wait start:') or h.startswith('# Wait end:') or h.startswith('# End:'))]
check(not others, f"after the header only Wait / End comment lines: {others}")
rows_p, notes_p = check_v2("platform job log", lines, end_reason="job finished")
check(len(rows_p) == len(df) and [l for l in lines if l.startswith('#')][10:] == notes_p,
      f"every comment line after the header is in the notes block after the data ({len(notes_p)} notes)")
check("# Device: KINETIQ" in head, "device from the G-code (not the Planning combo), written as KINETIQ")
check(any(h.startswith("# Axes (Duet order): X,Y,Z,A,B,C,D,'a,'c,'e,'f") for h in head), "axis mapping in the header")
check(head[-1].startswith("# End: job finished"), f"log ends with the reason: {head[-1]}")
cols = list(df.columns)
check(cols == ['Time_s', 'Pos_LAT_mm', 'Pos_SI_mm', 'Pos_AP_mm', 'Pos_Roll_deg', 'Pos_Pitch_deg', 'Pos_Yaw_deg',
               'Pos_A_mm', 'Pos_B_mm', 'Pos_C_mm', 'Pos_D_mm', "Pos_'e_mm", "Pos_'f_mm", "Pos_'a_mm", "Pos_'c_mm", 'Probe'],
      "platform columns: DOF + raw actuators + Probe, no Cmd_*")
check(df['Pos_AP_mm'].abs().max() > 30 and df['Pos_LAT_mm'].abs().max() > 40 and df['Pos_SI_mm'].abs().max() > 20,
      "positions are real values, not zeros")

t = df['Time_s'].values
dt = np.diff(t)
check(len(df) > 50 and dt.max() <= 0.15, f"{len(df)} rows, largest gap {dt.max() * 1000:.0f} ms at {t[int(np.argmax(dt))]:.2f} s "
      f"(<= 150) with the GUI blocked")
check(t[0] >= 0 and t[0] < 0.2, f"first row at {t[0]:.3f} s of the run (pre-position not logged)")
check(abs(df['Pos_AP_mm'].values[0] - 35.0) < 0.01, f"run starts at the pre-positioned AP 35 ({df['Pos_AP_mm'].values[0]:.3f})")
check(abs(df['Pos_AP_mm'].values[-1] - 37.5) < 0.01 and abs(df['Pos_SI_mm'].values[-1] - 26.0) < 0.01,
      "run ends at AP 37.5 / SI 26")

# Same samples in the log and in the plot
spd = ui.status_plot_data
pt = np.array(spd['t'])
check(len(pt) == len(df), f"plot points {len(pt)} == log rows {len(df)}")
if len(pt) == len(df):
    check(np.max(np.abs(pt - t)) < 1e-4, f"same time base (max |dt| {np.max(np.abs(pt - t)):.1e} s)")
    worst = 0.0
    for col, key in [('Pos_LAT_mm', 'LAT'), ('Pos_SI_mm', 'SI'), ('Pos_AP_mm', 'AP'), ('Pos_Roll_deg', 'Roll'),
                     ('Pos_Pitch_deg', 'Pitch'), ('Pos_A_mm', 'A'), ('Pos_D_mm', 'D'), ("Pos_'e_mm", "'e"),
                     ("Pos_'f_mm", "'f"), ("Pos_'a_mm", "'a"), ("Pos_'c_mm", "'c")]:
        worst = max(worst, float(np.max(np.abs(df[col].values - np.array(spd[key])))))
    check(worst <= 0.0005 + 1e-9, f"every logged value equals the plotted one (max diff {worst:.4f}, rounding 0.0005)")
    check(np.array_equal(df['Probe'].values.astype(float), np.array(spd['probe'], dtype=float)), "same probe values in log and plot")

# Release marker and detector
probe = df['Probe'].values
t_rel = EV['t_release'] - EV['run_t0']
rel_rows = t[probe == 2000]
check(EV.get('released') and len(rel_rows) >= 1 and rel_rows.min() >= t_rel - 1e-6 and rel_rows.max() <= t_rel + 0.5 + 0.15,
      f"Probe 2000 on {len(rel_rows)} rows from {rel_rows.min() if len(rel_rows) else float('nan'):.2f} s (Release at {t_rel:.2f} s)")
det_rows = t[probe == 1000]
det_lo, det_hi = SIM.detector[0][0] - EV['run_t0'], SIM.detector[0][1] - EV['run_t0']
check(len(det_rows) > 3 and det_rows.min() >= det_lo - 0.1 and det_rows.max() <= det_hi + 0.1,
      f"detector 1000 rows {det_rows.min():.2f}..{det_rows.max():.2f} s (sim {det_lo:.2f}..{det_hi:.2f})")
check(set(np.unique(probe)) <= {-1000, 0, 1000, 2000} and -1000 in set(np.unique(probe)),
      f"probe values {sorted(set(np.unique(probe)))} (-1000 while sensor_wait.g waited)")

# The wait of this job (ended by the Release button): -1000 from the read up to the Release row
w1 = [w for w in SIM.waits if w['n'] == EV['job_n']]
check(len(w1) == 1 and w1[0]['end'] == 'release' and SIM.status == 'idle',
      f"simulated macro wait ended by force_release ({[w['end'] for w in w1]}), job stayed 'processing' meanwhile")
if w1:
    res1 = check_marked_wait("Release wait", t, probe, lines, w1[0], EV['run_t0'], 2000)
    rel_end = [l for l in lines if l.startswith('# Wait end: Release button at ')]
    check(len(rel_end) == 1 and abs(num(rel_end[0].split(' at ')[1].split(' s')[0]) - rel_rows.min()) < 0.0015,
          f"'# Wait end: Release button' at the first 2000 row: {rel_end}")
    rc = [g for tc, g in SIM.release_cmds if tc >= EV['run_t0']]
    check(rc == ['set global.force_release_sensor = true'],
          f"Release sends only 'set global...' (sensor_wait.g creates and resets the global itself): {rc}")
    lag = w1[0]['t_end'] - EV['t_release']
    t_end_row = num(rel_end[0].split(' at ')[1].split(' s')[0]) if rel_end else float('nan')
    check(0.0 <= lag <= 0.15 and abs((w1[0]['t_end'] - EV['run_t0']) - t_end_row) <= 0.15,
          f"the macro left the wait {lag:.3f} s after the press (first command), logged end {t_end_row:.3f} s vs "
          f"macro {w1[0]['t_end'] - EV['run_t0']:.3f} s")
    after_rel = [r for r in REPLIES if r[0] >= EV['t_release'] and r[2].strip() and r[0] <= EV['t_end']]
    check(not any("already exists" in r[2] for r in REPLIES) and after_rel and after_rel[-1][3] == RELEASED_MSG,
          f"fix a: no RRF 'already exists' error after Release, the Duet message field shows the macro's "
          f"'force released' text ({[r[3] for r in after_rel]})")

# The mid-job empty state replies did not end the run; the log covers the whole job
check(SIM.state_blip_done and SIM.combined_blip_done,
      f"empty-state replies were served mid-job (dashboard {SIM.state_blip_done}, snapshot {SIM.combined_blip_done})")
job_len = EV['t_end'] - EV['run_t0']
check(t[-1] > job_len - 1.5, f"log covers the job ({t[-1]:.1f} s of {job_len:.1f} s)")
check(ui.status_fast_timer.mode == 'combined', f"poller stayed in combined mode ({ui.status_fast_timer.mode})")

# Readers
print("\n=== Readers ===")
plan_df, device, matched, probe_seen, n_orig, dur = parse_trace_log_file(path)
check(device == "Motion Platform" and {'LAT', 'SI', 'AP', 'A', "'e", "'a"} <= set(matched), f"Planning parse: {device}, {sorted(matched)}")
import_trace_log_action(ui, path)
d = ui.dfEdit
si_imp = np.interp(t, d['time'].values, d['SI'].values)
ap_imp = np.interp(t, d['time'].values, d['AP'].values)
e_si = np.abs(si_imp - df['Pos_SI_mm'].values); e_ap = np.abs(ap_imp - df['Pos_AP_mm'].values)
print(f"  import diff: SI max {e_si.max():.4f} at t={t[int(np.argmax(e_si))]:.2f}, AP max {e_ap.max():.4f} at t={t[int(np.argmax(e_ap))]:.2f}")
# The logged ramp is a staircase (Duet machinePosition cache, ~0.125 mm per 200 ms here); the Planning
# bake may move its corners by about one stair. The point is that the logged DOF are kept, not zeros.
check(e_si.max() < 0.2 and e_ap.max() < 0.2 and abs(d['SI'].max() - 26.0) < 0.01 and abs(d['SI'].min() - 25.0) < 0.01
      and abs(d['AP'].max() - 37.5) < 0.01 and abs(d['AP'].min() - 35.0) < 0.01,
      f"Planning import keeps the logged DOF (SI {d['SI'].min():.2f}..{d['SI'].max():.2f}, not 0)")


def new_loader_ui():
    ui2 = MagicMock()
    from matplotlib.figure import Figure
    ui2.fig_status = Figure()
    ui2.ax_status = ui2.fig_status.add_subplot(111)
    ui2.PhOperFolder = QLineEdit(TMP)
    ui2.input_time_interval = QLineEdit("60")
    ui2.check_show_reference = QCheckBox()
    ui2.statusDuetMessage = MagicMock()
    for tr in ['X', 'Y', 'Z', 'A', 'B', 'C', 'D', 'e', 'f', 'a', 'c', 'Roll', 'Pitch', 'Yaw', 'LAT', 'AP', 'SI']:
        setattr(ui2, f'status_check_{tr}', QCheckBox())
    ui2.status_plot_lines = {}
    ui2.status_ref_lines = {}
    ui2._probe_span_patches = []
    ui2.active_log_file = None
    ui2.active_log_filepath = None
    ui2.check_record_log = None
    ui2.run_active = False
    return ui2


def span_colors(patches):
    return {tuple(np.round(p.get_facecolor()[:3], 3)) for p in patches}


RED, BLUE = (1.0, 0.0, 0.0), tuple(np.round(np.array([0x02, 0x88, 0xd1]) / 255.0, 3))
AMBER = tuple(np.round(np.array([0xff, 0xb3, 0x00]) / 255.0, 3))
ui2 = new_loader_ui()
load_log_file_into_status(ui2, path)
s2 = ui2.status_plot_data
check(len(s2['t']) == len(df) and np.allclose(s2["'a"], df["Pos_'a_mm"].values) and np.allclose(s2['AP'], df['Pos_AP_mm'].values),
      "Status-tab loader shows the DOF and the raw axes")
colors = span_colors(ui2._probe_span_patches)
check(RED in colors and BLUE in colors and AMBER in colors,
      f"plot shades the detector red, the Release marker blue and the sensor wait amber ({len(ui2._probe_span_patches)} spans)")
KEY_LABELS = ['Detector (Probe 1-1499)', 'Release button (Probe 2000)', 'Waiting for sensor (Probe -1000)']


def key_of(u_):
    """(labels, swatch colours with alpha) of the Status plot's probe colour key, or None."""
    k = getattr(u_, '_probe_key', None)
    if k is None or k not in u_.ax_status.artists:
        return None
    return ([tx.get_text() for tx in k.get_texts()],
            [tuple(np.round(h.get_facecolor(), 3)) for h in k.legend_handles])


kl = key_of(ui2)
check(kl is not None and kl[0] == KEY_LABELS and [c[:3] for c in kl[1]] == [RED, BLUE, AMBER]
      and all(abs(c[3] - 0.22) < 1e-3 for c in kl[1]) and ui2._probe_key is not ui2.ax_status.get_legend(),
      f"Load Log: colour key of the three shading classes (same colours / alpha 0.22), separate from the trace legend: {kl}")

# q9f issue 6: live run rendered once per second (13 Hz, 60 s window): the key lists the classes with shading
# in the SHOWN window, so it changes when the window scrolls past a class (and is rebuilt only then)
uk = new_loader_ui()
uk.status_plot_data = {k_: [] for k_ in ['t', 'X', 'Y', 'Z', 'A', 'B', 'C', 'D', "'e", "'f", "'a", "'c", 'Roll', 'Pitch',
                                         'Yaw', 'LAT', 'AP', 'SI', 'probe']}
EVK = [(8, 10, 1000), (18, 24, -1000), (24, 24.5, 2000), (150, 160, -1000)]
seen_k, key_ids = {}, set()
for i_ in range(int(200 * 13)):
    t_ = i_ / 13.0
    for k_ in uk.status_plot_data:
        uk.status_plot_data[k_].append(t_ if k_ == 't' else 0.0)
    uk.status_plot_data['probe'][-1] = next((v_ for a_, b_, v_ in EVK if a_ <= t_ < b_), 0)
    if i_ % 13 == 12:
        render_status_plot(uk)
        kk_ = key_of(uk)
        seen_k[int(round(t_))] = ([x.split(' (')[0] for x in kk_[0]] if kk_ else [],
                                  tuple(round(x_) for x_ in uk.ax_status.get_xlim()))
        if getattr(uk, '_probe_key', None) is not None:
            key_ids.add(id(uk._probe_key))
want_k = {9: ['Detector'], 25: ['Detector', 'Release button', 'Waiting for sensor'], 59: ['Detector', 'Release button',
          'Waiting for sensor'], 95: [], 140: [], 155: ['Waiting for sensor'], 199: ['Waiting for sensor']}
got_k = {s_: seen_k[min(seen_k, key=lambda x_: abs(x_ - s_))] for s_ in want_k}
check(all(got_k[s_][0] == want_k[s_] for s_ in want_k) and len(key_ids) <= 6,
      f"Status key follows the shown window (classes with shading inside it): "
      f"{[(s_, got_k[s_][1], got_k[s_][0]) for s_ in want_k]}, {len(key_ids)} key builds in 200 renders")


def to_v1(v2_lines, out_path):
    """The same log in format v1: ',' columns, '.' decimals, 8-line header, the notes between the rows."""
    data = [l for l in v2_lines[11:] if not l.startswith('#')]
    notes = [re.sub(r'(\d),(\d)', r'\1.\2', l) for l in v2_lines[11:] if l.startswith('#')]
    hdr = v2_lines[:4] + ["# Positions: actual (Duet machinePosition; refreshed at most every 200 ms)", v2_lines[5],
                          "# Wait timing: v1 header line", re.sub(r'(\d),(\d)', r'\1.\2', v2_lines[8])]
    body = [l.replace(',', '.').replace(';', ',') for l in data]
    mid = len(body) // 2
    out = hdr + [v2_lines[10].replace(';', ',')] + body[:mid] + notes[:-1] + body[mid:] + notes[-1:]
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write("\n".join(out) + "\n")


def plot_arrays(u_):
    return {k_: np.asarray(v_, dtype=float) for k_, v_ in u_.status_plot_data.items()}


path_v1 = os.path.join(TMP, "v1_" + os.path.basename(path))
to_v1(lines, path_v1)
ui2b = new_loader_ui()
load_log_file_into_status(ui2b, path_v1)
a2, a2b = plot_arrays(ui2), plot_arrays(ui2b)
check(set(a2) == set(a2b) and all(np.array_equal(a2[k_], a2b[k_]) for k_ in a2) and len(a2['t']) == len(df),
      f"Load Log reads the v2 log and the same log in v1 format (',' / '.', notes between rows) to the same arrays")
pl1 = parse_trace_log_file(path_v1)
check(pl1[1:] == (device, matched, probe_seen, n_orig, dur) and list(pl1[0].columns) == list(plan_df.columns)
      and all(np.array_equal(pl1[0][c_].values, plan_df[c_].values) for c_ in plan_df.columns if c_ != 'Command'),
      f"Planning import reads the v2 log and its v1 copy to the same plan ({n_orig} rows)")
from fcn_plan.fcn_import import is_trace_log_file, detect_file_format
check(is_trace_log_file(path) and detect_file_format(path) == 'trace_log' and is_trace_log_file(path_v1),
      "is_trace_log_file finds the column line after the 10-line v2 header (and in v1)")

# q9f issues 1 + 2: Excel on this PC (list separator ';', decimal ','), the log opened and saved again as CSV:
# every '#' cell holding '"' (each '# Wait start' note) comes back quoted ('"# Wait start: ""Waiting ..."" ...";;;'),
# rows are padded with ';', numbers lose their trailing zeros ('0,1'); 'CSV UTF-8' (or an editor) puts a BOM
# in front. Load Log and the Planning import must still read the same data as from the original file.
from fcn_plan.fcn_import import sniff_trace_log_format, is_trace_log_comment
import csv as _csv
BOM_CH, NL = chr(0xFEFF), chr(10)


def excel_resave(v2_lines, out_path, bom=False):
    ncol = len(v2_lines[10].split(';'))
    with open(out_path, 'w', newline='', encoding='utf-8-sig' if bom else 'cp1252') as fh:
        wr_ = _csv.writer(fh, delimiter=';', lineterminator=chr(13) + chr(10))    # minimal quoting, as Excel writes
        for i_, l_ in enumerate(v2_lines):
            if l_.startswith('#'):
                cells = [l_]
            elif i_ == 10:
                cells = l_.split(';')
            else:
                cells = [('%.15g' % num(c_)).replace('.', ',') for c_ in l_.split(';')]
            wr_.writerow(cells + [''] * (ncol - len(cells)))


def same_as_original(p_):
    """(Load Log arrays == the original's, Planning plan == the original's, rows loaded, plan rows / error)."""
    u_ = new_loader_ui()
    load_log_file_into_status(u_, p_)
    d_ = getattr(u_, 'status_plot_data', None)
    a_ = plot_arrays(u_) if isinstance(d_, dict) and 't' in d_ else {}
    ok_l = set(a_) == set(a2) and all(np.array_equal(a_[k_], a2[k_]) for k_ in a2)
    try:
        pl_ = parse_trace_log_file(p_)
        ok_p = (pl_[1:] == (device, matched, probe_seen, n_orig, dur)
                and all(np.array_equal(pl_[0][c_].values, plan_df[c_].values) for c_ in plan_df.columns if c_ != 'Command'))
        n_p = pl_[4]
    except Exception as e_:
        ok_p, n_p = False, f"{type(e_).__name__}: {e_}"
    return ok_l, ok_p, len(a_.get('t', [])), n_p


p_xl = os.path.join(TMP, "xl_" + os.path.basename(path))
excel_resave(lines, p_xl)
with open(p_xl, encoding='cp1252') as fh:
    xl_lines = fh.read().splitlines()
xl_q = [l_ for l_ in xl_lines if l_.startswith('"#')]
ok_l, ok_p, n_l, n_p = same_as_original(p_xl)
check(len(xl_q) >= 1 and xl_q[0].startswith('"# Wait start: ""Waiting for sensor signal..."" received at ')
      and xl_lines[0].endswith(';') and sniff_trace_log_format(p_xl) == (';', ',')
      and ok_l and ok_p and is_trace_log_file(p_xl) and detect_file_format(p_xl) == 'trace_log',
      f"Excel resave ({len(xl_q)} quoted '#' lines, ';'-padded, e.g. {xl_lines[11][:24]!r}): Load Log ({n_l} rows) and the "
      f"Planning import ({n_p}) read the same data as from the original")
p_bom = os.path.join(TMP, "bom_" + os.path.basename(path))
with open(p_bom, 'w', encoding='utf-8-sig') as fh:
    fh.write(NL.join(lines) + NL)
ok_l, ok_p, n_l, n_p = same_as_original(p_bom)
check(sniff_trace_log_format(p_bom) == (';', ',') and ok_l and ok_p and is_trace_log_file(p_bom)
      and detect_file_format(p_bom) == 'trace_log',
      f"v2 log with a UTF-8 BOM: sniffed as ';' / ',', Load Log ({n_l} rows) and the Planning import ({n_p}) as the original")
p_xlb = os.path.join(TMP, "xlbom_" + os.path.basename(path))
excel_resave(lines, p_xlb, bom=True)
ok_l, ok_p, n_l, n_p = same_as_original(p_xlb)
check(ok_l and ok_p and is_trace_log_file(p_xlb), f"Excel 'CSV UTF-8' resave (BOM + quoted '#' lines): Load Log ({n_l} rows) "
      f"and the Planning import ({n_p}) as the original")
p_v1b = os.path.join(TMP, "v1bom_" + os.path.basename(path))
with open(path_v1, encoding='utf-8') as fh, open(p_v1b, 'w', encoding='utf-8-sig') as gh:
    gh.write(fh.read())
ui_v1b = new_loader_ui()
load_log_file_into_status(ui_v1b, p_v1b)
a_v1b = plot_arrays(ui_v1b)
check(sniff_trace_log_format(p_v1b) == (',', '.') and set(a_v1b) == set(a2b)
      and all(np.array_equal(a_v1b[k_], a2b[k_]) for k_ in a2b) and parse_trace_log_file(p_v1b)[4] == n_orig,
      "v1 log with a BOM: still the old reader path, same arrays as without the BOM")
check([is_trace_log_comment(s_) for s_ in ('# x', '"# Wait start: ""W"" at 1,0 s";;', BOM_CH + '# Computer Time', '  # x',
                                            'Time_s;Pos_X_mm', '0,1;2;3', '"Time_s";"x"', '')]
      == [True, True, True, True, False, False, False, False], "is_trace_log_comment: '#', Excel-quoted '\"#', BOM, spaces")

# ============================================================== 1b. sensor waits: detector, probe 300, race
print("\n=== Sensor waits: two detector-ended waits and a race in one job ===")
logs_before = set(os.listdir(TMP))
reads_main0 = RR_REPLY_BY_THREAD['MainThread']
reads_sim0, reads_rp0 = SIM.reply_reads, RP.reads
n_rep0 = len(REPLIES)
run_job("job_waits.gcode", release_when_paused=False)
check(RR_REPLY_BY_THREAD['MainThread'] == reads_main0, f"no rr_reply from the GUI thread during the run ({dict(RR_REPLY_BY_THREAD)})")
d_sim, d_rp = SIM.reply_reads - reads_sim0, RP.reads - reads_rp0
dur_run = EV['t_end'] - EV['t_start_call']
check(abs(d_sim - d_rp) <= 2 and d_rp >= 3, f"every rr_reply the Duet served came from the ReplyPoller "
      f"({d_sim} served, {d_rp} sent, {d_rp / dur_run:.2f}/s)")
check(RP._seq_t is not None and time.perf_counter() - RP._seq_t < 2.0 and d_rp / dur_run < 1.6,
      f"the ReplyPoller read on seqs.reply changes ({d_rp / dur_run:.2f} reads/s instead of 2/s on its timer)")
new_logs = sorted(f for f in set(os.listdir(TMP)) - logs_before if f.startswith('log_'))
check(len(new_logs) == 1, f"one log for the waits run: {new_logs}")
path_w = os.path.join(TMP, new_logs[0])
head_w, df_w, lines_w = read_log(path_w)
print("  " + "\n  ".join(h for h in head_w[10:]))
check_v2("waits job log", lines_w, end_reason="job finished")
tw_ = df_w['Time_s'].values
pw = df_w['Probe'].values
r0 = EV['run_t0']
waits = [w for w in SIM.waits if w['n'] == EV['job_n']]
check(len(waits) == 3 and all(w['end'] == 'detector' for w in waits), f"three simulated waits, all ended by the detector")
spw = ui.status_plot_data
check(len(spw['t']) == len(df_w) and np.max(np.abs(np.array(spw['t']) - tw_)) < 1e-4
      and np.array_equal(pw.astype(float), np.array(spw['probe'], dtype=float)), f"log rows == plot points ({len(df_w)}), same probe")
if len(waits) == 3:
    wa, wb, wc = waits
    ra = check_marked_wait("Wait A", tw_, pw, lines_w, wa, r0, 1000, next_start=wb['t_start'] - r0)
    rb = check_marked_wait("Wait B", tw_, pw, lines_w, wb, r0, 1000, next_start=wc['t_start'] - r0)
    widths = [x['hi'] - x['lo'] for x in (ra, rb) if x and x.get('lo') is not None]
    lags = [x['rf'] - x['tw'] for x in (ra, rb) if x]
    w_txt = ", ".join("%.3f" % x for x in widths)
    l_txt = ", ".join("%.3f" % x for x in lags)
    check(len(widths) == 2 and max(widths) <= 0.35 and max(lags) <= 0.35,
          f"with seqs.reply the 'Waiting' message is read within one sample + one read of the wait start "
          f"(bounds {w_txt} s wide, read {l_txt} s after it)")
    # probe 300 inside wait A: real value, the wait goes on
    a300 = [(a - r0, b - r0) for a, b, v in SIM.detector if v == 300 and wa['t_start'] <= a <= wa['t_end']]
    if ra and a300:
        seg_t, seg_p = tw_[ra['i0']:ra['ik']], pw[ra['i0']:ra['ik']]
        rows300 = seg_t[seg_p == 300]
        lo300, hi300 = a300[0]
        check(len(rows300) >= 2 and rows300.min() >= lo300 - 0.04 and rows300.max() <= hi300 + 0.04
              and np.any((seg_t > hi300 + 0.04) & (seg_p == -1000)),
              f"probe 300 during wait A stays 300 ({len(rows300)} rows {rows300.min() if len(rows300) else 0:.2f}.."
              f"{rows300.max() if len(rows300) else 0:.2f} s, sim {lo300:.2f}..{hi300:.2f}) and the wait goes on (-1000 after)")
    # race: detector 12 ms after the echo, before TRACE read the message -> no -1000 rows
    tc = wc['t_start'] - r0
    in_c = pw[(tw_ >= tc - 0.05) & (tw_ <= tc + 1.0)]
    nm = [l for l in lines_w if l.startswith('# Wait not marked:')]
    check(len(in_c) > 5 and not np.any(in_c == -1000),
          f"race (detector before the message was read): no -1000 rows around {tc:.2f} s; log says: {nm}")
    check(len([l for l in lines_w if RE_WSTART.match(l)]) == len([l for l in lines_w if RE_WEND.match(l)]),
          "every '# Wait start' has its '# Wait end'")
    print(f"  sample end vs Duet message read: the message came {', '.join(f'{x:+.3f}' for x in EV.get('leads') or [])} s "
          f"after the end row")
# The Duet message field and the console still show the replies
reps = REPLIES[n_rep0:]
shown_ok = all(r[3] == r[2].strip() for r in reps if r[2].strip())
check(len(reps) >= 5 and shown_ok and any(WAIT_MSG in r[2] for r in reps) and any(DETECTED_MSG in r[2] for r in reps),
      f"statusDuetMessage showed each of the {len(reps)} replies ({[r[3] for r in reps][:6]})")
console = ui.duet_log_console.toPlainText()
check(f"Duet Message: {WAIT_MSG}" in console and f"Duet Message: {DETECTED_MSG}" in console, "console lines for the Duet messages")
# Status plot and loader: -1000 rows amber
render_status_plot(ui)
check(AMBER in span_colors(ui._probe_span_patches) and RED in span_colors(ui._probe_span_patches),
      "live Status plot shades the sensor waits amber (and the detector red)")
kl = key_of(ui)
leg = ui.ax_status.get_legend()
leg_labels = [tx.get_text() for tx in leg.get_texts()] if leg is not None else []
check(kl is not None and kl[0] == [KEY_LABELS[0], KEY_LABELS[2]] and [c[:3] for c in kl[1]] == [RED, AMBER]
      and leg is not None and leg is not ui._probe_key and leg_labels and not any('Probe' in x for x in leg_labels),
      f"live Status plot: colour key of only the classes present (no Release in this run): {kl and kl[0]}; the trace "
      f"legend is unchanged ({leg_labels[:4]})")
ui3 = new_loader_ui()
load_log_file_into_status(ui3, path_w)
check(len(ui3.status_plot_data['t']) == len(df_w) and AMBER in span_colors(ui3._probe_span_patches)
      and np.array_equal(np.array(ui3.status_plot_data['probe'], dtype=float), pw.astype(float)),
      f"Load Log reads every row of the waits log and shades the -1000 rows amber")
plan_w, dev_w, matched_w, probe_w, n_w, dur_w = parse_trace_log_file(path_w)
import_trace_log_action(ui, path_w)
dw = ui.dfEdit
check(dev_w == "Motion Platform" and n_w == len(df_w) and abs(dw['SI'].max() - 28.0) < 0.01 and abs(dw['SI'].min() - 25.0) < 0.01
      and abs(dw['AP'].max() - 36.0) < 0.01, f"Planning import of the waits log ({n_w} rows, SI {dw['SI'].min():.2f}..{dw['SI'].max():.2f})")

# Dashboard and pause/resume: no rr_reply of their own while the ReplyPoller runs
print("\n=== One rr_reply reader ===")
m0 = RR_REPLY_BY_THREAD['MainThread']
update_status_tab_dashboard(ui)
check(RR_REPLY_BY_THREAD['MainThread'] == m0, "dashboard tick does not read rr_reply while the ReplyPoller runs")
nr = len(RP_READS)
t_call = time.perf_counter()
pause_continue_GCODE(ui, pause=False)
t_pc = time.perf_counter() - t_call
wait_until(lambda: False, 0.4)
quick = [x - t_call for x in RP_READS[nr:] if x >= t_call]
check(RR_REPLY_BY_THREAD['MainThread'] == m0 and any(0.09 <= q <= 0.3 for q in quick),
      f"pause/resume asks the ReplyPoller for a read 0.1 s later instead of reading itself (reads at {[round(q, 3) for q in quick]} s)")
RP.stop()
check(not RP.isActive(), "ReplyPoller stopped")
m1 = RR_REPLY_BY_THREAD['MainThread']
update_status_tab_dashboard(ui)
check(RR_REPLY_BY_THREAD['MainThread'] == m1 + 1, "without the ReplyPoller the dashboard reads rr_reply itself (old path)")
with SIM.lock:
    SIM.queue(time.perf_counter(), "Hello from the Duet")
update_status_tab_dashboard(ui)
check(ui.statusDuetMessage.text() == "Hello from the Duet", f"old path still shows the message ({ui.statusDuetMessage.text()})")
t_call = time.perf_counter()
pause_continue_GCODE(ui, pause=False)
t_pc_old = time.perf_counter() - t_call
check(RR_REPLY_BY_THREAD['MainThread'] >= m1 + 3, "without the ReplyPoller pause/resume reads rr_reply itself (old path)")
print(f"  pause/resume call on the GUI thread: {t_pc * 1000:.0f} ms with the ReplyPoller, {t_pc_old * 1000:.0f} ms without")
EV_PC = (t_pc, t_pc_old)
ui.status_fast_timer.stop()
check(not RP.isActive(), "stopping the position poll (file transfer) keeps the ReplyPoller stopped")
ui.status_fast_timer.start()
wait_until(lambda: False, 0.3)
check(RP.isActive() and ui.status_fast_timer.isActive(), "starting the position poll starts the ReplyPoller too")
ui.status_fast_timer.stop()
check(not RP.isActive() and not ui.status_fast_timer.isActive(), "stopping the position poll stops the ReplyPoller")
ui.status_fast_timer.start()
wait_until(lambda: False, 0.5)

print("\n=== Duet message held by a WiFi stall (rr_reply handed the text out, the response comes late) ===")
check(fcn_duet.REPLY_POLL_TIMEOUT_S >= 2.0, f"ReplyPoller timeout {fcn_duet.REPLY_POLL_TIMEOUT_S} s")
n_rep = len(REPLIES)
SIM.reply_hold = 1.6
with SIM.lock:
    SIM.queue(time.perf_counter(), "Stalled message 1")
ok_st = wait_until(lambda: any("Stalled message 1" in r[2] for r in REPLIES[n_rep:]), 8)
SIM.reply_hold = 0.0
check(ok_st, "a message whose rr_reply response was held 1.6 s still arrives (lost with the former 1 s timeout)")
wait_until(lambda: not RP._busy.locked(), 3)
n_rep = len(REPLIES)
SIM.reply_hold = fcn_duet.REPLY_POLL_TIMEOUT_S + 0.8
with SIM.lock:
    SIM.queue(time.perf_counter(), "Stalled message 2")
got_fail = wait_until(lambda: RP._t_fail is not None, 10)
SIM.reply_hold = 0.0
with SIM.lock:
    SIM.queue(time.perf_counter() + 0.3, "After the stall")
ok_after = wait_until(lambda: any("After the stall" in r[2] for r in REPLIES[n_rep:]), 8)
rf_ = [r for r in REPLIES[n_rep:] if len(r[4]) > 4 and r[4][4] is not None]
check(got_fail and ok_after and len(rf_) >= 1,
      f"a read held past the timeout fails; the next reply carries its send time (t_fail) for the log ({len(rf_)} reply)")
wait_until(lambda: False, 0.5)

# ============================================================== 2. split fallback + Lung Phantom job
print("\n=== Combined snapshot unavailable (503) + Lung Phantom job ===")
plot_before = len(ui.status_plot_data['t'])
SIM.combined_503 = True
logs_before = set(os.listdir(TMP))
SPLIT_T = []
_orig_switch = ui.status_fast_timer._switch_to_split


def _rec_switch(why):
    if ui.status_fast_timer.mode != 'split':
        SPLIT_T.append(time.perf_counter())
    _orig_switch(why)


ui.status_fast_timer._switch_to_split = _rec_switch
n_reads_split0, m_split0 = len(RP_READS), RR_REPLY_BY_THREAD['MainThread']
run_job("job_phantom.gcode", release_when_paused=False)
ui.status_fast_timer._switch_to_split = _orig_switch
new_logs = sorted(f for f in set(os.listdir(TMP)) - logs_before if f.startswith('log_'))
check(ui.status_fast_timer.mode == 'split', f"poller fell back to split mode ({ui.status_fast_timer.mode})")
# q9f issue 5: in split mode (slow link) the ReplyPoller reads during a RUN every REPLY_POLL_SLOW_S (and at the
# dashboard ticks): a sensor wait's start text must arrive within ~1 s to be marked. Outside runs it reads at the
# dashboard's rate, inside each tick (fix b; checked after this run)
if SPLIT_T:
    wa_, wb_ = max(SPLIT_T[0] + fcn_duet.REPLY_SEQ_FRESH_S + 0.5, EV['run_t0'] + 0.2), EV['t_end'] - 0.2
    rd = [x for x in RP_READS[n_reads_split0:] if wa_ <= x <= wb_]
    gaps_ = np.diff(rd) if len(rd) > 1 else np.array([np.inf])
    check(RP._split and len(rd) >= 2 and gaps_.max() <= fcn_duet.REPLY_POLL_SLOW_S + 0.3
          and RR_REPLY_BY_THREAD['MainThread'] == m_split0,
          f"split mode during a run: rr_reply read at least every {fcn_duet.REPLY_POLL_SLOW_S:g} s, on the poller thread "
          f"({len(rd)} reads in {wb_ - wa_:.1f} s, longest gap {gaps_.max():.2f} s)")
else:
    check(False, "the poller switched to split mode during the phantom run")
check(len(new_logs) == 1, f"one log for the phantom run: {new_logs}")
if new_logs:
    head2, df2, _l2 = read_log(os.path.join(TMP, new_logs[0]))
    check_v2("Lung Phantom (split mode) log", _l2, end_reason="job finished")
    check("# Device: DYNAMIQ" in head2 and list(df2.columns) == ['Time_s', 'Pos_X_mm', 'Pos_Y_mm', 'Pos_Z_mm', 'Probe'],
          f"Lung Phantom columns {list(df2.columns)}")
    check(abs(df2['Pos_X_mm'].max() - 5.0) < 0.01, f"X reaches 5 mm ({df2['Pos_X_mm'].max():.3f})")
    check(head2[-1].startswith("# End: job finished"), f"split mode run ends on the dashboard's idle readings: {head2[-1]}")
    t2 = df2['Time_s'].values
    check(np.diff(t2).max() <= 0.25, f"split mode gaps <= 250 ms (max {np.diff(t2).max() * 1000:.0f} ms)")
    check(len(ui.status_plot_data['t']) == len(df2),
          f"Start cleared the plot: {len(ui.status_plot_data['t'])} points == {len(df2)} rows of this run (was {plot_before})")
# fix b outside runs: split mode without a run -> rr_reply read once per dashboard tick, inside the tick
wait_until(lambda: False, 1.5)
t_a_, n_rd0_ = time.perf_counter(), len(RP_READS)
wait_until(lambda: False, 5.0)
t_b_ = time.perf_counter()
rd = [x for x in RP_READS[n_rd0_:] if t_a_ <= x <= t_b_]
tk = [(a_, a_ + d_) for (a_, d_, _act) in TICKS if t_a_ - 1.0 <= a_ <= t_b_]
in_tick = [x for x in rd if any(a_ <= x <= b_ + 0.05 for a_, b_ in tk)]
n_tk = len([1 for a_, b_ in tk if a_ >= t_a_])
check(ui.status_fast_timer.mode == 'split' and getattr(ui, 'run_active', False) is not True and len(rd) >= 2
      and len(in_tick) == len(rd) and abs(len(rd) - n_tk) <= 1,
      f"fix b outside runs: split mode reads rr_reply once per dashboard tick ({len(rd)} reads, {len(in_tick)} inside a "
      f"tick, {n_tk} ticks in {t_b_ - t_a_:.1f} s)")

# q9f issue 5 end to end: a slow link (150 ms per request, one at a time), split mode, 4 sensor waits of
# ~2,5 s ended by a 0,9 s detector pulse (over before the next wait, after a 1,2 s move): every wait is
# marked (-1000 rows, no '# Wait not marked'), its start bounds
# contain the true start; q9f issue 3: a split-mode end note says when the probe was read, and is true
saved_s = (SCRIPTS['waits'], SIM.latency, SIM.parallel)
SCRIPTS['waits'] = ([{'do': 'delay', 'dt': 0.3}]
                    + [it_ for k_ in range(4) for it_ in ({'do': 'move', 'dt': 1.2, 'to': {"'a": 22.0 + 2 * k_, "'c": 22.0 + 2 * k_}},
                                                         {'do': 'wait', 'det': [(2.5, 0.9, 1000)]})]
                    + [{'do': 'delay', 'dt': 0.5}])
SIM.latency = 0.15
SIM.set_parallel(1)
logs_before = set(os.listdir(TMP))
n_rp0_ = len(RP_READS)
try:
    run_job("job_waits_split.gcode", release_when_paused=False)
finally:
    SCRIPTS['waits'] = saved_s[0]
    SIM.latency = saved_s[1]
    SIM.set_parallel(saved_s[2])
new_logs = sorted(f for f in set(os.listdir(TMP)) - logs_before if f.startswith('log_'))
check(len(new_logs) == 1 and ui.status_fast_timer.mode == 'split', f"one log for the slow-link waits run ({new_logs}, "
      f"poll mode {ui.status_fast_timer.mode})")
if new_logs:
    head_s, df_s, l_s = read_log(os.path.join(TMP, new_logs[0]))
    _r, notes_s = check_v2("slow-link split-mode waits log", l_s, end_reason="job finished")
    print(chr(10).join("    " + x for x in notes_s))
    ts_, ps_ = df_s['Time_s'].values, df_s['Probe'].values
    r0_ = EV['run_t0']
    ws_ = [w for w in SIM.waits if w['n'] == EV['job_n']]
    marked_ = [int(np.sum((ts_ >= w['t_start'] - r0_) & (ts_ < (w['t_end'] or 1e9) - r0_) & (ps_ == -1000))) for w in ws_]
    nm_ = [x for x in notes_s if x.startswith('# Wait not marked')]
    starts_ = [m for m in (RE_WSTART.match(x) for x in notes_s) if m]
    bounds_ok = all(any(num(m.group(2)) - 1e-3 <= w['t_start'] - r0_ <= num(m.group(3)) + 1e-3 for m in starts_) for w in ws_)
    rd_ = np.diff([x for x in RP_READS[n_rp0_:] if r0_ + 0.5 <= x <= EV['t_end'] - 0.2])
    rd_ = rd_ if len(rd_) else np.array([np.nan])
    check(len(ws_) == 4 and all(w['end'] == 'detector' for w in ws_) and all(m_ >= 1 for m_ in marked_) and not nm_
          and len(starts_) == 4 and bounds_ok,
          f"slow link (150 ms, one request at a time), split mode: all 4 waits marked ({marked_} rows -1000), no "
          f"'# Wait not marked' ({len(nm_)}), start bounds contain the true starts ({bounds_ok}); rr_reply read every "
          f"{np.median(rd_):.2f} s (max {np.max(rd_):.2f} s), rows every {np.median(np.diff(ts_)) * 1000:.0f} ms")
    re_sp = re.compile(r'^# Wait end: detector (\d+) at (-?\d+,\d{3}) s \(split mode, the probe was read up to '
                       r'(\d+,\d{3}) s after this row, previous sample at (-?\d+,\d{3}) s\)$')
    sp_ = [m for m in (re_sp.match(x) for x in notes_s) if m]
    sp_ok = []
    for m in sp_:
        t_e, lag_, t_p = num(m.group(2)), num(m.group(3)), num(m.group(4))
        tr_ = min((w['trigger'] - r0_ for w in ws_ if w.get('trigger') is not None), key=lambda x_: abs(x_ - t_e))
        sp_ok.append((round(t_p, 3), round(tr_, 3), round(t_e + lag_, 3), t_p - 0.001 < tr_ <= t_e + lag_ + 0.002))
    exact_det = [x for x in notes_s if x.startswith('# Wait end: detector') and 'exact to one sample' in x]
    check(len(sp_) >= 1 and all(x_[3] for x_ in sp_ok) and not exact_det,
          f"split-mode detector end notes give the probe read time, and the true detector rise lies in (previous "
          f"sample, row + probe lag] as they state: {sp_ok}; no 'exact to one sample' detector end ({len(exact_det)})")
fcn_duet.COMBINED_RETRY_S = 1.0
SIM.combined_503 = False
ui.status_fast_timer._next_combined_try = time.perf_counter() + 0.5
wait_until(lambda: ui.status_fast_timer.mode == 'combined', 5)
check(ui.status_fast_timer.mode == 'combined', "snapshot retried and back to combined mode once the Duet serves it again")

# ============================================================== 3. disconnect closes the log
print("\n=== Connection drop during a run: gap, then the job finishes ===")
SIM.combined_503 = False
logs_before = set(os.listdir(TMP))
ui.selected_gcode_path = "job_platform.gcode"
start_selected_gcode_execution(ui)
wait_until(lambda: SIM.status == 'processing', 10)
wait_until(lambda: False, 1.0)
plot_t_before = len(ui.status_plot_data['t'])
load_log_file_into_status(ui, path)          # must be refused during a run
check(ui.check_record_log.isChecked() and len(ui.status_plot_data['t']) >= plot_t_before,
      "Load Log is refused while a run is recorded")
ui.duet_connected = False
wait_until(lambda: False, 1.0)
check(getattr(ui, 'run_active', False) is True, "run stays active while disconnected")
ui.duet_connected = True
wait_until(SIM.waiting, 20)
wait_until(lambda: False, 0.8)
release_sensor_wait_action(ui)
wait_until(lambda: getattr(ui, 'run_active', False) is not True, 30)
new_logs = sorted(f for f in set(os.listdir(TMP)) - logs_before if f.startswith('log_'))
check(len(new_logs) == 1, f"still one log for the run: {new_logs}")
if new_logs:
    head3, df3, _l3 = read_log(os.path.join(TMP, new_logs[0]))
    gap = [h for h in head3 if h.startswith('# Gap')]
    check(len(gap) == 2 and gap[0].startswith('# Gap: connection lost at') and gap[1].startswith('# Gap end: reconnected at'),
          f"gap marked in the log: {gap}")
    _r3, notes3 = check_v2("connection-gap run log", _l3, end_reason="job finished")
    t_last3 = num(_r3[-1][0]) if _r3 else float('nan')
    g_t = [num(RE_NOTE_T.search(g).group(1)) for g in gap]
    check(len(g_t) == 2 and g_t[0] < g_t[1] < t_last3 and all(g in notes3 for g in gap),
          f"the gap notes are in the notes block after the last row ({t_last3:.3f} s), not between the rows: {g_t}")
    check(head3[-1].startswith("# End: job finished"), f"run ends normally after the reconnect: {head3[-1]}")
    t3 = df3['Time_s'].values
    check(np.all(np.diff(t3) > 0) and abs(df3['Pos_SI_mm'].values[-1] - 26.0) < 0.01,
          f"same time base before/after the gap, job logged to the end (SI {df3['Pos_SI_mm'].values[-1]:.3f})")

# ============================================================== 3b. a new Start while a run is logged
print("\n=== New Start while a log is open: the first log gets its notes and '# End: new start' ===")
logs_before = set(os.listdir(TMP))
ui.selected_gcode_path = "job_waits.gcode"
start_selected_gcode_execution(ui)
ok_w = wait_until(lambda: any(l_.startswith('# Wait start:') for _t, l_ in (getattr(ui, '_log_notes', None) or [])), 20)
first_path = ui.active_log_filepath
with open(first_path, encoding='utf-8') as fh:
    mid_lines = fh.read().splitlines()
check(ok_w and len(mid_lines) > 12 and mid_lines[10].startswith('Time_s;')
      and not any(l_.startswith('#') for l_ in mid_lines[11:]) and -1000 in [int(num(l_.split(';')[-1])) for l_ in mid_lines[11:]],
      f"during the run the file holds the header and the rows only, -1000 rows included (the wait note is in memory: "
      f"{[l_ for _t, l_ in (getattr(ui, '_log_notes', None) or [])][:1]})")
ui.selected_gcode_path = "job_phantom.gcode"
start_selected_gcode_execution(ui)
wait_until(lambda: getattr(ui, 'run_active', False) is not True, 30)
wait_until(lambda: False, 1.0)
new_logs = sorted(f for f in set(os.listdir(TMP)) - logs_before if f.startswith('log_'))
check(len(new_logs) == 2 and os.path.join(TMP, new_logs[0]) == first_path, f"two logs (new Start): {new_logs}")
if len(new_logs) == 2:
    with open(first_path, encoding='utf-8') as fh:
        l_ns = fh.read().splitlines()
    _r, n_ns = check_v2("log closed by a new Start", l_ns, end_reason="new start")
    check(any(x.startswith('# Wait start:') for x in n_ns) and any(x.startswith('# Wait end: run end at ') and
                                                                   x.endswith('(the run ended: new start)') for x in n_ns),
          f"close path 'new start' writes the notes kept in memory: {n_ns[:-1]}")
    with open(os.path.join(TMP, new_logs[1]), encoding='utf-8') as fh:
        check_v2("log of the run after the new Start", fh.read().splitlines(), end_reason="job finished")

# ============================================================== 4. position sampling with / without the ReplyPoller
print("\n=== Position sampling with and without the ReplyPoller (60 ms per request, one Duet message per second) ===")


def sampling_window(seconds):
    t_a = time.perf_counter()
    rs0, by0 = SIM.reply_reads, dict(RR_REPLY_BY_THREAD)
    t_msg, k = t_a + 0.2, 0
    while time.perf_counter() < t_a + seconds:
        if time.perf_counter() >= t_msg:          # a Duet message every second (more than a stepped job sends)
            k += 1
            with SIM.lock:
                SIM.queue(time.perf_counter(), f"Sampling message {k}")
            t_msg += 1.0
        app.processEvents()
        time.sleep(0.01)
    t_b = time.perf_counter()
    rs1, by1 = SIM.reply_reads, dict(RR_REPLY_BY_THREAD)
    wait_until(lambda: False, 0.8)          # samples of the window still queued behind a dashboard tick
    ts = np.array([x for x in SAMPLE_T if t_a <= x <= t_b])
    dts = np.diff(ts)
    ticks = [d for (ts0, d, _a) in TICKS if t_a <= ts0 <= t_b - 0.6]
    by = {k_: by1.get(k_, 0) - by0.get(k_, 0) for k_ in by1}
    return {'n': len(ts), 'rate': len(ts) / (t_b - t_a), 'median': float(np.median(dts)), 'p95': float(np.percentile(dts, 95)),
            'max': float(dts.max()), 'tick_med': float(np.median(ticks)) if ticks else float('nan'),
            'tick_max': float(max(ticks)) if ticks else float('nan'), 'ticks': len(ticks),
            'reply_per_s': (rs1 - rs0) / (t_b - t_a), 'gui_reads': by.get('MainThread', 0)}


# off: no ReplyPoller (the dashboard reads rr_reply 1/s on the GUI thread, as before);
# seq: ReplyPoller reading on seqs.reply changes; timed: ReplyPoller on its 0.5 s timer (no seqs.reply)
SAMPLING = {}
MODES = (('off', False, True), ('seq', True, True), ('timed', True, False))
for par in (1, 2, 3):
    SIM.set_parallel(par)
    for rep in range(2):
        for name, with_rp, seqs in MODES:
            SIM.seqs_enabled = seqs
            if with_rp:
                RP.start()
            else:
                RP.stop()
            wait_until(lambda: False, 0.4 if seqs else 1.3)     # sequence numbers count for 1 s after the last one
            st = sampling_window(3.5)
            st['active'] = RP.isActive()
            st['seq_mode'] = RP._seq_mode(time.perf_counter())
            SAMPLING.setdefault((par, name), []).append(st)
SIM.seqs_enabled = True
RP.start()
SIM.set_parallel(2)


def _agg(lst):
    return {k: (float(np.mean([x[k] for x in lst])) if k not in ('max', 'tick_max') else float(max(x[k] for x in lst)))
            for k in lst[0] if k not in ('active', 'seq_mode')}


SAMPLING_SUMMARY = {}
for par in (1, 2, 3):
    agg = {name: _agg(SAMPLING[(par, name)]) for name, _w, _s in MODES}
    SAMPLING_SUMMARY[par] = agg
    for name, s_ in agg.items():
        print(f"  parallel {par}, {name:5s}: {s_['rate']:.2f} samples/s, interval median {s_['median'] * 1000:.1f} ms, "
              f"p95 {s_['p95'] * 1000:.1f} ms, max {s_['max'] * 1000:.1f} ms; dashboard tick median "
              f"{s_['tick_med'] * 1000:.0f} ms (max {s_['tick_max'] * 1000:.0f} ms); rr_reply {s_['reply_per_s']:.2f}/s, "
              f"from the GUI thread {s_['gui_reads']:.1f} per window")
    off, seq, tim = agg['off'], agg['seq'], agg['timed']
    check(all(x['active'] and x['seq_mode'] for x in SAMPLING[(par, 'seq')])
          and all(x['active'] and not x['seq_mode'] for x in SAMPLING[(par, 'timed')])
          and not any(x['active'] for x in SAMPLING[(par, 'off')]),
          f"parallel {par}: windows ran without the poller / with it on seqs.reply / with it on its timer, as intended")
    check(abs(seq['median'] - off['median']) <= 0.10 * off['median'] and seq['rate'] >= 0.90 * off['rate'],
          f"parallel {par}: reading on seqs.reply changes keeps the sampling: median {seq['median'] * 1000:.1f} vs "
          f"{off['median'] * 1000:.1f} ms, {seq['rate']:.2f} vs {off['rate']:.2f} samples/s (within 10 %)")
    check(seq['reply_per_s'] <= off['reply_per_s'] + 0.3, f"parallel {par}: {seq['reply_per_s']:.2f} rr_reply/s on seqs.reply "
          f"changes vs {off['reply_per_s']:.2f}/s by the old dashboard read")
    if par >= 2:
        check(abs(tim['median'] - off['median']) <= 0.10 * off['median'] and tim['rate'] >= 0.90 * off['rate'],
              f"parallel {par}: the 0.5 s timer (no seqs.reply) keeps the sampling too: median {tim['median'] * 1000:.1f} vs "
              f"{off['median'] * 1000:.1f} ms, {tim['rate']:.2f} vs {off['rate']:.2f} samples/s")
    check(seq['tick_med'] < off['tick_med'], f"parallel {par}: dashboard tick {seq['tick_med'] * 1000:.0f} ms with vs "
          f"{off['tick_med'] * 1000:.0f} ms without the poller (GUI thread blocked less)")
    check(seq['gui_reads'] == 0 and tim['gui_reads'] == 0 and off['gui_reads'] >= 2,
          f"parallel {par}: rr_reply from the GUI thread only without the poller")
check(SIM.max_inflight <= 3, f"the simulated Duet served at most {SIM.max_inflight} requests at once")

# ============================================================== 5. wait mark units (deterministic timing)
print("\n=== Small units ===")
from fcn_monitor.fcn_duet import _axes_from_list, log_data_point, close_data_log_file
probe_ui = MagicMock()
probe_ui._om_axis_letters = None
probe_ui.duet_configured_axes = None
check(_axes_from_list(probe_ui, [{'machinePosition': 1.0}] * 7) is None, "7 axes without letters: sample skipped, not logged as zeros")
probe_ui._om_axis_letters = list(NAMES)
_axes_from_list(probe_ui, [{'machinePosition': 1.0}] * 7)
check(probe_ui._om_axis_letters is None, "letters cleared when the axis count changes")


class U:
    pass


def unit_ui():
    u = U()
    u.duet_connected = True
    u.status_stopped = False
    u.run_active = True
    u.run_t0 = time.perf_counter() - 100.0
    u.run_device = "Lung Phantom"
    u.check_record_log = QCheckBox()
    u.check_record_log.setChecked(True)
    u.PhOperFolder = QLineEdit(tempfile.mkdtemp(prefix="trace_wait_"))
    u.active_log_file = None
    u._log_open_failed = False
    return u


def us(u, t, p, x=0.0):          # one sample at run time t (axes still: sensor_wait.g runs M400 first)
    handle_position_sample(u, {'t': u.run_t0 + t, 'real': {'X': x}, 'probe': p, 'status': 'P'})


def ur(u, t_fetch, t_prev, text):  # one Duet reply at run times
    handle_duet_reply(u, (u.run_t0 + t_fetch, None if t_prev is None else u.run_t0 + t_prev, text))


def urs(u, t_fetch, t_prev, text, t_send, t_fail=None):   # ... as the ReplyPoller hands it on
    handle_duet_reply(u, (u.run_t0 + t_fetch, None if t_prev is None else u.run_t0 + t_prev, text, u.run_t0 + t_send,
                          None if t_fail is None else u.run_t0 + t_fail))


def ulog(u, label="unit log", reason="job finished"):
    p = u.active_log_filepath
    if getattr(u, 'run_active', False):
        end_run(u, reason)
    with open(p, encoding='utf-8') as f:
        ls = f.read().splitlines()
    rows, _notes = check_v2(label, ls, end_reason=reason)
    return ls, {num(r[0]): num(r[-1]) for r in rows}


u = unit_ui()
for k in range(6):
    us(u, 0.1 * k, 0, x=-1.25)       # a negative position: '-1,250'
ur(u, 0.55, 0.05, WAIT_MSG + "\n")
for k in range(6, 12):
    us(u, 0.1 * k, 300 if k == 8 else 0)
us(u, 1.2, 1000)
us(u, 1.3, 1000)
ur(u, 1.56, 1.05, DETECTED_MSG + "\n")
us(u, 1.6, 0)
ls, pv = ulog(u, "unit: detector-ended wait")
check([pv[round(0.1 * k, 1)] for k in range(5, 14)] == [0, -1000, -1000, 300, -1000, -1000, -1000, 1000, 1000] and pv[1.6] == 0,
      f"unit: -1000 from the first sample after the read, 300 kept, detector row 1000, then real values")
check('# Wait start: "Waiting for sensor signal..." received at 0,550 s (Duet sent it between 0,050 and 0,550 s)' in ls
      and '# Wait end: detector 1000 at 1,200 s (exact to one sample, previous sample at 1,100 s)' in ls,
      "unit: '# Wait start' / '# Wait end' lines in the specified format (decimal comma)")
i_trig = ls.index('1,2000;0,000;0,000;0,000;1000') if '1,2000;0,000;0,000;0,000;1000' in ls else -1
i_ws = ls.index('# Wait start: "Waiting for sensor signal..." received at 0,550 s (Duet sent it between 0,050 and 0,550 s)')
check(0 < i_trig < i_ws and ls[i_ws + 1] == '# Wait end: detector 1000 at 1,200 s (exact to one sample, previous sample at 1,100 s)'
      and ls[i_ws - 1] == '1,6000;0,000;0,000;0,000;0' and '0,5000;-1,250;0,000;0,000;0' in ls,
      "unit: the trigger row is a plain row; the start / end notes follow the last row, in time order; "
      "negative position '-1,250'")

u = unit_ui()                    # race guard: detector since the previous read, before the message
for k in range(4):
    us(u, 0.1 * k, 0)
us(u, 0.45, 1000)
us(u, 0.5, 0)
ur(u, 0.55, 0.3, WAIT_MSG + "\n")
for k in range(6, 12):
    us(u, 0.1 * k, 0)
ls, pv = ulog(u)
check(-1000 not in pv.values() and any(l.startswith('# Wait not marked: "Waiting for sensor signal..." received at 0,550 s')
                                     and 'detector 1000 at 0,450 s' in l for l in ls),
      f"unit: race guard (detector at 0.45 s since the read at 0.30 s): nothing marked, '# Wait not marked' line")

u = unit_ui()                    # a detector sample taken before the read but handled after it
for k in range(6):
    us(u, 0.1 * k, 0)
ur(u, 0.55, 0.05, WAIT_MSG + "\n")
us(u, 0.53, 1000)
for k in range(6, 10):
    us(u, 0.1 * k, 0)
ls, pv = ulog(u)
check(-1000 not in pv.values() and any(l.startswith('# Wait not marked:') for l in ls),
      "unit: detector sample in flight across the read: nothing marked")

u = unit_ui()                    # start and end in the same read
us(u, 0.1, 0)
ur(u, 0.55, 0.05, WAIT_MSG + "\n" + DETECTED_MSG + "\n")
for k in range(6, 10):
    us(u, 0.1 * k, 0)
ls, pv = ulog(u)
check(-1000 not in pv.values() and any(l.startswith('# Wait not marked:') and 'in the same read' in l for l in ls),
      "unit: wait started and ended within one read: nothing marked")

u = unit_ui()                    # backup end: the samples never saw the detector
us(u, 0.1, 0)
ur(u, 0.55, 0.05, WAIT_MSG + "\n")
for k in range(6, 11):
    us(u, 0.1 * k, 0)
ur(u, 1.05, 0.55, DETECTED_MSG + "\n")
us(u, 1.03, 0)                   # taken before that read: still waiting
us(u, 1.1, 0)
ls, pv = ulog(u)
check(pv[1.0] == -1000 and pv[1.03] == -1000 and pv[1.1] == 0
      and '# Wait end: Duet message "Sensor detected. Continuing G-code." at 1,050 s (from the Duet message, up to ~0,5 s late)' in ls,
      "unit: backup end from the Duet message (samples before the read stay -1000)")

u = unit_ui()                    # backup message read, but the detector sample (taken before it) arrives later
us(u, 0.1, 0)
ur(u, 0.55, 0.05, WAIT_MSG + "\n")
for k in range(6, 11):
    us(u, 0.1 * k, 0)
ur(u, 1.05, 0.55, DETECTED_MSG + "\n")
us(u, 1.03, 1000)
us(u, 1.1, 1000)
ls, pv = ulog(u)
check(pv[1.03] == 1000 and any(l.startswith('# Wait end: detector 1000 at 1,030 s') for l in ls),
      "unit: the exact sample end wins over a Duet message read before that sample arrived")

u = unit_ui()                    # Release button
us(u, 0.1, 0)
ur(u, 0.55, 0.05, WAIT_MSG + "\n")
for k in range(6, 10):
    us(u, 0.1 * k, 0)
u._release_mark_t = u.run_t0 + 0.95
u._release_mark_done = False
for k in range(10, 18):
    us(u, 0.1 * k, 0)
ls, pv = ulog(u)
check(pv[0.9] == -1000 and pv[1.0] == 2000 and -1000 not in [pv[round(0.1 * k, 1)] for k in range(10, 18)]
      and any(l.startswith('# Wait end: Release button at 1,000 s') for l in ls), "unit: Release ends the wait (2000 row, then no -1000)")

u = unit_ui()                    # gap does not end it; Cancel / run end does
us(u, 0.1, 0)
ur(u, 0.55, 0.05, WAIT_MSG + "\n")
us(u, 0.6, 0)
handle_position_sample(u, {'event': 'disconnected', 't': u.run_t0 + 0.65})
us(u, 1.5, 0)
us(u, 1.6, 0)
p_cancel = u.active_log_filepath
end_run(u, "cancelled")
with open(p_cancel, encoding='utf-8') as f:
    ls = f.read().splitlines()
_r, n_c = check_v2("unit: cancelled run", ls, end_reason="cancelled")
check([x.split(':')[0] for x in n_c] == ['# Wait start', '# Gap', '# Gap end', '# Wait end', '# End'],
      f"close path 'cancelled' writes the notes in time order: {[x.split(':')[0] for x in n_c]}")
iw = [i for i, l in enumerate(ls) if l.startswith('# Wait end: run end at ')]
check([l.split(';')[-1] for l in ls if l.startswith('1,')] == ['-1000', '-1000'] and len(iw) == 1
      and ls[iw[0]].endswith('(the run ended: cancelled)') and ls[iw[0] + 1].startswith('# End: cancelled'),
      f"unit: a connection gap keeps the wait, Cancel ends it ({ls[iw[0]] if iw else None})")

u = unit_ui()                    # two waits; a new 'Waiting' message while still marked
us(u, 0.1, 0)
ur(u, 0.55, 0.05, WAIT_MSG + "\n")
us(u, 0.6, 0)
us(u, 0.7, 900)
us(u, 0.8, 0)
ur(u, 2.05, 1.55, WAIT_MSG + "\n")
us(u, 2.1, 0)
ur(u, 3.05, 2.55, DETECTED_MSG + "\n" + WAIT_MSG + "\n")
us(u, 3.1, 0)
ls, pv = ulog(u)
check(pv[0.6] == -1000 and pv[0.7] == 900 and pv[0.8] == 0 and pv[2.1] == -1000 and pv[3.1] == -1000
      and len([l for l in ls if l.startswith('# Wait start:')]) == 3
      and len([l for l in ls if l.startswith('# Wait end:')]) == 3, "unit: several waits per run, back-to-back messages in order")

u = unit_ui()                    # back-to-back waits: the pulse that ended wait 1 does not block wait 2
us(u, 0.1, 0)
ur(u, 0.55, 0.05, WAIT_MSG + "\n")
for k in range(6, 12):
    us(u, 0.1 * k, 0)
us(u, 1.2, 1000)
us(u, 1.25, 1000)
us(u, 1.3, 0)
ur(u, 1.56, 1.05, DETECTED_MSG + "\n" + WAIT_MSG + "\n")
us(u, 1.6, 0)
us(u, 1.7, 0)
ls, pv = ulog(u)
check(pv[1.2] == 1000 and pv[1.25] == 1000 and pv[1.3] == 0 and pv[1.6] == -1000 and pv[1.7] == -1000
      and len([l for l in ls if l.startswith('# Wait start:')]) == 2 and not any(l.startswith('# Wait not marked') for l in ls),
      "unit: a wait starting within one read after the previous wait's detector end is still marked")

u = unit_ui()                    # ... but a detector pulse the Duet can have seen after the read was sent blocks it
us(u, 0.1, 0)
ur(u, 0.55, 0.05, WAIT_MSG + "\n")
for k in range(6, 12):
    us(u, 0.1 * k, 0)
us(u, 1.2, 1000)
us(u, 1.3, 0)
us(u, 1.47, 1000)                # its reply came back after the 'Waiting' read was sent (1.50 s)
us(u, 1.5, 0)
urs(u, 1.56, 1.05, DETECTED_MSG + "\n" + WAIT_MSG + "\n", t_send=1.50)
us(u, 1.6, 0)
ls, pv = ulog(u)
check(pv[1.6] == 0 and any(l.startswith('# Wait not marked:') and 'detector 1000 at 1,470 s' in l for l in ls),
      "unit: a detector pulse the Duet can have seen after the 'Waiting' read was sent blocks the wait (race guard)")

u = unit_ui()                    # issue 3: a pulse that ended before the wait began does not block it
for k in range(3):
    us(u, 0.1 * k, 0)
us(u, 0.3, 1000)
us(u, 0.4, 1000)                 # pulse 0.25..0.45 s while moving; the macro starts its wait at 0.50 s
us(u, 0.5, 0)
urs(u, 0.55, 0.05, WAIT_MSG + "\n", t_send=0.49)  # no end text: the wait still ran when this read was handled
for k in range(6, 20):
    us(u, 0.1 * k, 0)
us(u, 2.0, 1000)
us(u, 2.1, 0)
ls, pv = ulog(u)
check(all(pv[round(0.1 * k, 1)] == -1000 for k in range(6, 20)) and pv[2.0] == 1000
      and not any(l.startswith('# Wait not marked') for l in ls),
      "unit: a detector pulse that ended before the wait (its samples before the read was sent) does not block it")

u = unit_ui()                    # issues 2 / 6: the Release hold of a press that ended wait 1 does not end wait 2
us(u, 0.1, 0)
ur(u, 0.55, 0.05, WAIT_MSG + "\n")
for k in range(6, 10):
    us(u, 0.1 * k, 0)
u._release_mark_t = u.run_t0 + 0.98
u._release_mark_done = False
us(u, 1.0, 0)                    # 2000: ends wait 1
us(u, 1.1, 0)
urs(u, 1.25, 0.75, RELEASED_MSG + "\n" + WAIT_MSG + "\n", t_send=1.19)   # wait 2 (the macro cleared the flag)
for k in range(13, 30):
    us(u, 0.1 * k, 0)
us(u, 3.0, 1000)
us(u, 3.1, 0)
ls, pv = ulog(u)
ends = [l for l in ls if l.startswith('# Wait end:')]
check([pv[1.0], pv[1.1], pv[1.3], pv[1.4]] == [2000] * 4
      and all(pv[round(0.1 * k, 1)] == -1000 for k in range(15, 30)) and pv[3.0] == 1000
      and len(ends) == 2 and ends[0].startswith('# Wait end: Release button at 1,000 s')
      and ends[1].startswith('# Wait end: detector 1000 at 3,000 s'),
      f"unit: the Release hold of wait 1 stays 2000 in wait 2 but does not end it; -1000 after the hold ({ends})")

u = unit_ui()                    # issue 6: a press made before the wait began does not end it
for k in range(6):
    us(u, 0.1 * k, 0)
u._release_mark_t = u.run_t0 + 0.55
u._release_mark_done = False
for k in range(6, 9):
    us(u, 0.1 * k, 0)
urs(u, 0.85, 0.35, WAIT_MSG + "\n", t_send=0.79)
for k in range(9, 25):
    us(u, 0.1 * k, 0)
us(u, 2.5, 1000)
ls, pv = ulog(u)
check(pv[0.9] == 2000 and pv[1.0] == 2000 and all(pv[round(0.1 * k, 1)] == -1000 for k in range(11, 25)) and pv[2.5] == 1000
      and any(l.startswith('# Wait end: detector 1000 at 2,500 s') for l in ls),
      "unit: a Release press 0.24 s before the 'Waiting' read was sent does not end that wait")

u = unit_ui()                    # issue 7: a sample without its own probe value never ends a wait
u._last_probe_val = 1000         # the dashboard's stale value from an earlier pulse
us(u, 0.1, 0)
ur(u, 0.55, 0.05, WAIT_MSG + "\n")
us(u, 0.6, 0)
us(u, 0.7, None)
us(u, 0.8, 0)
us(u, 0.9, 1000)
ls, pv = ulog(u)
check(pv[0.6] == -1000 and pv[0.7] == -1000 and pv[0.8] == -1000 and pv[0.9] == 1000 and u._last_probe_val == 1000
      and any(l.startswith('# Wait end: detector 1000 at 0,900 s') for l in ls),
      "unit: a probe-less sample (stale dashboard value 1000) is written -1000 and does not end the wait")

u = unit_ui()                    # issue 1: end message lost, no sample saw the pulse -> the axes moving end the wait
us(u, 0.1, 0, x=10.0)
ur(u, 0.55, 0.05, WAIT_MSG + "\n")
us(u, 0.6, 0, x=10.0)
us(u, 0.7, 0, x=10.05)           # machinePosition still catching up after the M400 (within WAIT_POS_SETTLE_S)
for k in range(8, 11):
    us(u, 0.1 * k, 0, x=10.05)
for k in range(11, 31):          # pulse at 1.02 s ended the macro; its message was lost; the job moves on
    us(u, 0.1 * k, 0, x=10.05 + 0.5 * (k - 10))
ls, pv = ulog(u)
mv = [l for l in ls if l.startswith('# Wait end: motion at 1,100 s')]
check(all(pv[round(0.1 * k, 1)] == -1000 for k in range(6, 11)) and not any(pv[round(0.1 * k, 1)] == -1000 for k in range(11, 31))
      and len(mv) == 1 and 'previous sample at 1,000 s' in mv[0],
      f"unit: without an end message the first sample with moved axes ends the wait, not the settling after M400 ({mv})")


def stalled_reference_case(hold_until):
    """fix c: the sample sent right after the 'Waiting' read carries a pre-M400 position (machinePosition
    cache) and its response is stalled until hold_until; the macro keeps waiting until the detector at 3.0 s."""
    u_ = unit_ui()

    def usl(t_send, t_recv, p, x):          # one sample: request sent t_send, reply back t_recv (run times)
        handle_position_sample(u_, {'t': u_.run_t0 + 0.5 * (t_send + t_recv), 'latency': t_recv - t_send,
                                    'real': {'X': x}, 'probe': p, 'status': 'P', 'mode': 'combined'})

    def cached(h):                           # X moves 20 -> 26 mm in 0..0.5 s; cache refreshed every 0.2 s
        tc = int(h / 0.2 + 1e-9) * 0.2
        return round(20.0 + 6.0 * min(max(tc / 0.5, 0.0), 1.0), 4)

    ts = 0.0
    while ts < 0.45:
        usl(ts, ts + 0.06, 0, cached(ts + 0.03))
        ts += 0.07
    urs(u_, 0.56, 0.05, WAIT_MSG + "\n", t_send=0.50)     # echo at 0.50 s after the M400
    usl(0.52, hold_until, 0, cached(0.55))                # 'X' 24.8 instead of 26.0, response stalled
    ts = hold_until
    while ts < 3.0:
        usl(ts, ts + 0.06, 0, cached(ts + 0.03))
        ts += 0.07
    usl(3.0, 3.06, 1000, 26.0)
    urs(u_, 3.12, 0.50, DETECTED_MSG + "\n", t_send=3.06)
    usl(3.1, 3.16, 0, 26.0)
    ls_, pv_ = ulog(u_, f"unit: stalled pre-M400 sample until {hold_until} s")
    inside = [p_ for t_, p_ in pv_.items() if 0.56 <= t_ < 3.0]
    ends_ = [l_ for l_ in ls_ if l_.startswith('# Wait end:')]
    return inside, ends_


res_c = [stalled_reference_case(h_) for h_ in (1.20, 1.50)]
check(all(len(ins) > 15 and all(p_ == -1000 for p_ in ins) and len(en) == 1 and en[0].startswith('# Wait end: detector 1000 at 3,030 s')
          for ins, en in res_c),
      f"fix c: a stalled response with a pre-M400 position does not become the motion reference (no false 'motion' "
      f"end, every row -1000 up to the detector): {[(len(ins), sum(p_ != -1000 for p_ in ins), en) for ins, en in res_c]}")

u = unit_ui()                    # issue 1: a failed read is noted; a wait closed by the next one says its end was lost
us(u, 0.1, 0)
urs(u, 0.55, 0.05, WAIT_MSG + "\n", t_send=0.49)
us(u, 0.6, 0)
us(u, 0.7, 0)
urs(u, 3.6, 0.55, "", t_send=3.55, t_fail=1.05)        # read at 1.05 s timed out (its 'Sensor detected' is lost)
us(u, 3.65, 0)
urs(u, 4.05, 3.55, WAIT_MSG + "\n", t_send=4.0)
us(u, 4.1, 0)
ls, pv = ulog(u)
nf = [l for l in ls if l.startswith('# Message read failed at 1,050 s: Duet messages sent between 0,550 and 3,550 s may be lost')]
ew = [l for l in ls if l.startswith('# Wait end: Duet message "Waiting for sensor signal..." at 4,050 s (its end message was '
                                    'not received, a Duet message read failed at 1,050 s, the wait ended before')]
check(len(nf) == 1 and len(ew) == 1 and pv[4.1] == -1000, f"unit: failed read noted in the log ({nf}) and the wait it may have "
      f"cut short says its end message was lost ({ew})")

u = unit_ui()                    # message before the first logged row: its note joins the notes of the log
ur(u, 0.02, -0.4, WAIT_MSG + "\n")
us(u, 0.05, 0)
us(u, 0.1, 1000)
ls, pv = ulog(u)
check(ls[10].startswith('Time_s;') and ls[11] == '0,0500;0,000;0,000;0,000;-1000' and ls[12] == '0,1000;0,000;0,000;0,000;1000'
      and ls[13].startswith('# Wait start: "Waiting for sensor signal..." received at 0,020 s') and pv[0.05] == -1000,
      "unit: a wait known before the log file opened: its note is the first one after the last row")

# Close paths: every one writes the notes kept in memory, then '# End: <reason>' as the last line
u = unit_ui()                    # 'record off' in the middle of a run, then on again (new file)
us(u, 0.1, 0)
ur(u, 0.55, 0.05, WAIT_MSG + "\n")
us(u, 0.6, 0)
p_rec1 = u.active_log_filepath
u.check_record_log.setChecked(False)
us(u, 0.7, 0)                    # closes the log ('record off')
us(u, 0.8, 0)
us(u, 0.9, 1000)                 # the wait ends while no file is open: the note waits for the next file
u.check_record_log.setChecked(True)
us(u, 1.0, 0)
p_rec2 = u.active_log_filepath
ls2_, _pv = ulog(u)
with open(p_rec1, encoding='utf-8') as f:
    ls1_ = f.read().splitlines()
_r, n1_ = check_v2("unit: log closed by 'record off'", ls1_, end_reason="record off")
_r, n2_ = check_v2("unit: log reopened after 'record off'", ls2_, end_reason="job finished")
check(p_rec1 != p_rec2 and [x.split(':')[0] for x in n1_] == ['# Wait start', '# Wait end', '# End']
      and n1_[1].startswith('# Wait end: record off at ') and n1_[1].endswith('(the log was closed while the wait was still going on)')
      and [x.split(':')[0] for x in n2_] == ['# Wait start', '# Wait end', '# End'] and n2_[0] == n1_[0]
      and n2_[1].startswith('# Wait end: detector 1000 at 0,900 s'),
      f"close path 'record off' writes its notes (a wait still going on is closed in this log); the wait's end from "
      f"while recording was off joins the next file with its start ({n1_[:2]}, {n2_[:2]})")

u = unit_ui()                    # q9f issue 4: Record off and on again while the wait goes on; it ends in log 2
us(u, 0.1, 0)
ur(u, 0.55, 0.05, WAIT_MSG + "\n")
us(u, 0.6, 0)
us(u, 0.7, 0)
p_r1 = u.active_log_filepath
u.check_record_log.setChecked(False)
us(u, 0.8, 0)                    # closes log 1 ('record off'), the wait goes on
u.check_record_log.setChecked(True)
us(u, 1.0, 0)                    # opens log 2 during the wait
us(u, 1.1, 0)
p_r2 = u.active_log_filepath
us(u, 1.2, 1000)                 # the detector ends the wait
us(u, 1.3, 0)
ls_r2, pv_r2 = ulog(u)
with open(p_r1, encoding='utf-8') as f:
    ls_r1 = f.read().splitlines()
rows_r1, n_r1 = check_v2("unit: record off during a wait (log 1)", ls_r1, end_reason="record off")
_r, n_r2 = check_v2("unit: record on again during the wait (log 2)", ls_r2, end_reason="job finished")
ws_r = '# Wait start: "Waiting for sensor signal..." received at 0,550 s (Duet sent it between 0,050 and 0,550 s)'
check(p_r1 != p_r2 and len(n_r1) == 3 and n_r1[0] == ws_r and n_r1[1].startswith('# Wait end: record off at ')
      and [r_[-1] for r_ in rows_r1] == ['0', '-1000', '-1000'] and len(n_r2) == 3 and n_r2[0] == ws_r
      and n_r2[1] == '# Wait end: detector 1000 at 1,200 s (exact to one sample, previous sample at 1,100 s)'
      and [pv_r2[1.0], pv_r2[1.1], pv_r2[1.2], pv_r2[1.3]] == [-1000, -1000, 1000, 0],
      f"Record off and on during a wait: log 1 has the start and a 'record off' end ({n_r1[:2]}), log 2 the start "
      f"again and the detector end ({n_r2[:2]})")

# q9f issue 3: split mode (slow link). The row time is that of the positions request; the probe comes in a
# 2nd request (up to ~0,7 s later on a slow link), so the '# Wait end' note says so instead of 'exact'
u = unit_ui()
u.duet_status_code = 'P'


def usp(u_, t_send, t_pos, t_probe, p_, x=0.0):   # split sample: positions back at t_pos, the probe at t_probe
    handle_position_sample(u_, {'t': u_.run_t0 + 0.5 * (t_send + t_pos), 'latency': t_pos - t_send, 'real': {'X': x},
                                'probe': p_, 'status': None, 'mode': 'split', 'probe_t': u_.run_t0 + t_probe})


for k in range(8):
    if k == 4:
        urs(u, 0.55, 0.05, WAIT_MSG + "\n", t_send=0.5)
    usp(u, 0.15 * k, 0.15 * k + 0.05, 0.15 * k + 0.12, 0)
usp(u, 1.2, 1.25, 1.32, 1000)
usp(u, 1.35, 1.40, 1.47, 0)
ls, pv = ulog(u, "unit: split-mode wait")
se_ = [l for l in ls if l.startswith('# Wait end:')]
check(se_ == ['# Wait end: detector 1000 at 1,225 s (split mode, the probe was read up to 0,095 s after this row, '
              'previous sample at 1,075 s)'] and pv[1.075] == -1000 and pv[1.225] == 1000 and pv[1.375] == 0,
      f"split mode: the detector end note gives the probe read time instead of 'exact to one sample': {se_}")

# q9f issue 7: a double click on Release (the 2nd click handled right after the 1st press returns, which
# waits for the Duet) sends ONE command and keeps the 1st press's 2000 marker; a later press still works
from fcn_control import fcn_control as fcc_r
sent_r = []
orig_r = (fcc_r.send_cmd, fcc_r.log_to_duet_console)
fcc_r.send_cmd = lambda _s, g, *a, **k: (sent_r.append((time.perf_counter(), g)), time.sleep(0.4))
fcc_r.log_to_duet_console = lambda *a, **k: None
try:
    ru = unit_ui()
    release_sensor_wait_action(ru)          # 1st press: the command takes 0.4 s (slow link)
    m1_r = ru._release_mark_t
    release_sensor_wait_action(ru)          # 2nd click of the double click
    n_dbl, m2_r = len(sent_r), ru._release_mark_t
    time.sleep(0.35)
    release_sensor_wait_action(ru)          # a deliberate press 0.75 s after the 1st (e.g. the next wait)
finally:
    fcc_r.send_cmd, fcc_r.log_to_duet_console = orig_r
check(n_dbl == 1 and m2_r == m1_r and len(sent_r) == 2 and ru._release_mark_t > m1_r
      and all(g_ == 'set global.force_release_sensor = true' for _t, g_ in sent_r),
      f"Release double click: one command, the 1st press's marker kept; a press 0,75 s later is sent "
      f"({[g_ for _t, g_ in sent_r]})")

u = unit_ui()                    # connection lost while a log is open outside a run
us(u, 0.1, 0)
ur(u, 0.55, 0.05, WAIT_MSG + "\n")
us(u, 0.6, 0)
p_cl = u.active_log_filepath
u.run_active = False
handle_position_sample(u, {'event': 'disconnected', 't': u.run_t0 + 0.7})
with open(p_cl, encoding='utf-8') as f:
    ls_cl = f.read().splitlines()
_r, n_cl = check_v2("unit: log closed by 'connection lost'", ls_cl, end_reason="connection lost")
check(u.active_log_file is None and [x.split(':')[0] for x in n_cl] == ['# Wait start', '# End'],
      f"close path 'connection lost' (outside a run) writes the notes: {n_cl}")

from PySide6.QtWidgets import QMainWindow
from PySide6.QtGui import QCloseEvent
import Launch_ImGUI


class ClosingApp(Launch_ImGUI.MyApp):
    """The real MyApp.closeEvent on a window without the GUI build."""
    def __init__(self):
        QMainWindow.__init__(self)


ca = ClosingApp()
for k_, v_ in vars(unit_ui()).items():
    setattr(ca, k_, v_)
us(ca, 0.1, 0)
ur(ca, 0.55, 0.05, WAIT_MSG + "\n")
us(ca, 0.6, 0)
p_ca = ca.active_log_filepath
ca.closeEvent(QCloseEvent())
with open(p_ca, encoding='utf-8') as f:
    ls_ca = f.read().splitlines()
_r, n_ca = check_v2("unit: log closed by the app close (MyApp.closeEvent)", ls_ca, end_reason="application closed")
check(ca.active_log_file is None and [x.split(':')[0] for x in n_ca] == ['# Wait start', '# Wait end', '# End']
      and n_ca[1].endswith('(the run ended: application closed)'),
      f"close path 'application closed' writes the notes: {n_ca[:2]}")
check(V2_SEEN['neg_decimal'] > 0 and V2_SEEN['neg_probe'] > 0,
      f"negative numbers written with a decimal comma ({V2_SEEN['neg_decimal']} negative position cells, "
      f"{V2_SEEN['neg_probe']} -1000 cells) in {V2_SEEN['logs']} logs checked")

u = unit_ui()                    # outside a run: nothing armed
u.run_active = False
ur(u, 0.55, 0.05, WAIT_MSG + "\n")
check(getattr(u, '_sensor_wait', None) is None, "unit: a 'Waiting' message outside a run arms nothing")
check(not hasattr(u, '_last_probe_val'), "unit: the wait mark never touches _last_probe_val (auto-pause / auto-release)")

bad = os.path.join(TMP, 'not_a_folder.txt')
with open(bad, 'w') as fh:
    fh.write('x')
home = tempfile.mkdtemp(prefix="trace_home_")
os.makedirs(os.path.join(home, 'Desktop'), exist_ok=True)
old_profile = os.environ.get('USERPROFILE')
os.environ['USERPROFILE'] = home
try:
    lu = MagicMock()
    lu.PhOperFolder = QLineEdit(os.path.join(bad, 'sub'))
    lu.active_log_file = None
    lu._log_open_failed = False
    log_data_point(lu, 0.0, 1.0, 2.0, 3.0, probe=0)
    fb = lu.active_log_filepath
    close_data_log_file(lu)
    check(isinstance(fb, str) and fb.startswith(os.path.join(home, 'Desktop')), f"unwritable log folder falls back to the Desktop ({fb})")
finally:
    if old_profile is not None:
        os.environ['USERPROFILE'] = old_profile

from fcn_control import fcn_control as fcc
calls = []
orig = fcc.update_duet_status_ui
fcc.update_duet_status_ui = lambda *a, **k: calls.append(1)
hb = MagicMock()
hb._last_dashboard_poll_t = time.perf_counter()
fcc._duet_heartbeat_tick(hb)
hb._last_dashboard_poll_t = time.perf_counter() - 10.0
fcc._duet_heartbeat_tick(hb)
fcc.update_duet_status_ui = orig
check(len(calls) == 1, "heartbeat skips its poll while the dashboard is polling")

ui.status_fast_timer.shutdown()
check(not RP.isActive() and not (RP._thread and RP._thread.is_alive()), "shutdown of the position poll also ends the ReplyPoller thread")
srv.shutdown()
for f in os.listdir(TMP):
    try:
        os.remove(os.path.join(TMP, f))
    except Exception:
        pass
print(f"\n{NCHECK[0]} checks: " + ("ALL PASSED" if not FAILS else f"{len(FAILS)} FAILED"))
for m in FAILS:
    print("  FAILED: " + m)
sys.exit(1 if FAILS else 0)
