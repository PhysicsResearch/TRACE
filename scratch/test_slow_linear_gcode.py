import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np

from fcn_plan.fcn_gcode import generate_gcode_string, parse_gcode_timeline


def _feeds(lines):
    out = []
    for l in lines:
        if l.startswith("G1"):
            for part in l.split():
                if part.startswith("F"):
                    out.append(float(part[1:]))
    return out


def test_slow_linear_movement_no_pauses():
    print("=== Testing slow linear movement (0.1 mm/s) ===")

    # 10 s ramp at 0.1 mm/s, 3 s hold, 10 s ramp down; dt = 0.01 s
    t = np.round(np.arange(0, 23.01, 0.01), 6)
    si = np.zeros_like(t)
    for idx, ti in enumerate(t):
        if ti <= 10.0:
            si[idx] = 0.1 * ti
        elif ti <= 13.0:
            si[idx] = 1.0
        else:
            si[idx] = 1.0 - 0.1 * (ti - 13.0)

    # 1. Motion Platform (SI is written to 'a and 'c -> RRF feed counts both: sqrt(2) * 0.1 mm/s)
    cols_platform = {'LAT': np.zeros_like(t), 'SI': si, 'AP': np.zeros_like(t),
                     'Roll': np.zeros_like(t), 'Pitch': np.zeros_like(t), 'Yaw': np.zeros_like(t)}
    gcode, _ = generate_gcode_string(
        "Motion Platform", t, cols_platform, (40.0,) * 6,
        lat_dim=300.0, si_dim=500.0, off_ap=0.0, off_lat=0.0, off_si=0.0, axis_y_lo="'c"
    )
    lines = gcode.splitlines()
    g4_lines = [l for l in lines if l.startswith("G4")]
    print(f"Total lines: {len(lines)}, G1: {sum(1 for l in lines if l.startswith('G1'))}, G4: {len(g4_lines)}")
    assert "M203 I6" in lines[:8], "header must set the Duet minimum speed (M203 I6)"
    assert len(g4_lines) == 1, f"Expected exactly 1 dwell for the 3 s hold, got {g4_lines}"
    ms_val = int(g4_lines[0].replace("G4 P", ""))
    assert 2990 <= ms_val <= 3010, f"Expected ~3000 ms dwell, got {g4_lines[0]}"
    ramp_feeds = _feeds(lines)[1:]
    expected = np.sqrt(2) * 0.1 * 60.0
    assert all(abs(f - expected) < 1e-3 for f in ramp_feeds), f"ramp feeds {ramp_feeds} != {expected:.3f}"
    dur = parse_gcode_timeline(lines).time
    assert abs(dur - 23.0) < 1e-3, f"duration {dur} != 23.0"
    print(f"PASS: Motion Platform: one 3 s dwell, ramp F{expected:.3f} (sqrt2*0.1 mm/s), duration {dur:.3f} s")

    # 2. Lung Phantom (single linear axis -> F = 6 mm/min)
    cols_phantom = {'X': si, 'Y': np.zeros_like(t), 'Z': np.zeros_like(t)}
    gcode_p, _ = generate_gcode_string("Lung Phantom", t, cols_phantom, (40.0, 40.0, 40.0))
    lines_p = gcode_p.splitlines()
    g4_p = [l for l in lines_p if l.startswith("G4")]
    assert len(g4_p) == 1, f"Expected exactly 1 dwell in Lung Phantom, got {len(g4_p)}"
    assert all(abs(f - 6.0) < 1e-3 for f in _feeds(lines_p)[1:]), _feeds(lines_p)
    dur_p = parse_gcode_timeline(lines_p).time
    assert abs(dur_p - 23.0) < 1e-3, f"duration {dur_p} != 23.0"
    print(f"PASS: Lung Phantom: one dwell, F6, duration {dur_p:.3f} s")

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_slow_linear_movement_no_pauses()
