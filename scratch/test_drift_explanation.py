import numpy as np
import pandas as pd

# Analyze log file
log_df = pd.read_csv(r'C:\Users\gabri\Downloads\log_16_46_26_.csv')
t_log = log_df['Time_s'].values
x_log = log_df['Pos_X_mm'].values

import scipy.signal
peaks, _ = scipy.signal.find_peaks(x_log, distance=100, prominence=5)
peak_times = t_log[peaks]
peak_diffs = np.diff(peak_times)

print("=== LOG FILE ANALYSIS ===")
print(f"Total recorded peaks: {len(peaks)}")
print(f"Mean period between peaks: {peak_diffs.mean():.5f} s")
print(f"Discrepancy per 4.0s period: +{(peak_diffs.mean() - 4.0) * 1000:.2f} ms")
print(f"Total drift over {len(peaks)-1} cycles: {(peak_times[-1] - (peak_times[0] + (len(peaks)-1)*4.0)):.4f} s")

# Simulate G-code generation with current logic vs without G4 dwell
t = np.linspace(0.0, 4.0, 401)
val = 25.0 * (np.cos(np.pi * t / 4.0) ** 6)

def gen_moves(val, t, allow_speed_dwell=True):
    last_x = val[0]
    last_pos_written_idx = 0
    dwell_accum = 0.0
    moves = []
    
    for i in range(1, len(t)):
        dx = val[i] - last_x
        max_diff = abs(dx)
        dt_step = t[i] - t[i-1]
        step_speed = abs(val[i] - val[i-1]) / dt_step if dt_step > 0 else 0.0
        
        if allow_speed_dwell:
            is_stationary = (step_speed < 0.1) or (val[i] == val[i-1])
        else:
            is_stationary = (val[i] == val[i-1])
            
        if is_stationary:
            dwell_accum += dt_step
        elif max_diff < 0.01:
            pass
        else:
            dt_elapsed = max(0.001, t[i] - t[last_pos_written_idx] - dwell_accum)
            if dwell_accum >= 0.05:
                moves.append(('G4', dwell_accum))
            dwell_accum = 0.0
            dist = abs(dx)
            speed = (dist / dt_elapsed) * 60.0
            moves.append(('G1', dist, speed / 60.0, dt_elapsed))
            last_x = val[i]
            last_pos_written_idx = i
            
    if dwell_accum >= 0.05:
        moves.append(('G4', dwell_accum))
    return moves

moves_current = gen_moves(val, t, allow_speed_dwell=True)
moves_smooth = gen_moves(val, t, allow_speed_dwell=False)

g4_current = [m for m in moves_current if m[0] == 'G4']
g4_smooth = [m for m in moves_smooth if m[0] == 'G4']

print("\n=== G-CODE GENERATION COMPARISON ===")
print(f"Current logic G4 dwells per cycle: {len(g4_current)} ({g4_current[0][1]*1000:.0f} ms each)" if g4_current else "None")
print(f"Smooth logic G4 dwells per cycle: {len(g4_smooth)}")
print(f"Current logic G1 move count: {len([m for m in moves_current if m[0] == 'G1'])}")
print(f"Smooth logic G1 move count: {len([m for m in moves_smooth if m[0] == 'G1'])}")
