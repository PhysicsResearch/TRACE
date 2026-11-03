import numpy as np

t = np.linspace(0.0, 4.0, 401)
val = 25.0 * (np.cos(np.pi * t / 4.0) ** 6)
acc = 1500.0

last_x = val[0]
last_pos_written_idx = 0
dwell_accum = 0.0
items = []

for i in range(1, len(t)):
    dx = val[i] - last_x
    max_diff = abs(dx)
    dt_step = t[i] - t[i-1]
    step_speed = abs(val[i] - val[i-1]) / dt_step if dt_step > 0 else 0.0
    is_stationary = (step_speed < 0.1) or (val[i] == val[i-1])

    if is_stationary:
        if dwell_accum == 0.0 and max_diff > 0.001:
            dt_elapsed = max(0.001, t[i] - t[last_pos_written_idx])
            items.append({'type': 'G1', 'x': val[i], 'dist': abs(dx), 'dt': dt_elapsed})
            last_x = val[i]
            last_pos_written_idx = i
        dwell_accum += dt_step
    elif max_diff < 0.01:
        pass
    else:
        dt_elapsed = max(0.001, t[i] - t[last_pos_written_idx] - dwell_accum)
        if dwell_accum >= 0.05:
            items.append({'type': 'G4', 'dwell': dwell_accum})
        dwell_accum = 0.0
        items.append({'type': 'G1', 'x': val[i], 'dist': abs(dx), 'dt': dt_elapsed})
        last_x = val[i]
        last_pos_written_idx = i

# Trailing point
dt_elapsed = max(0.001, t[-1] - t[last_pos_written_idx] - dwell_accum)
if dwell_accum >= 0.05:
    items.append({'type': 'G4', 'dwell': dwell_accum})
dwell_accum = 0.0
if last_pos_written_idx < len(t) - 1:
    items.append({'type': 'G1', 'x': val[-1], 'dist': abs(val[-1] - last_x), 'dt': dt_elapsed})

# Correct speeds
g1_indices = [idx for idx, item in enumerate(items) if item['type'] == 'G1']
for idx in g1_indices:
    items[idx]['v_nom'] = items[idx]['dist'] / items[idx]['dt']

a_vec = acc * np.sqrt(3)

for k, idx in enumerate(g1_indices):
    item = items[idx]
    v_nom = item['v_nom']
    d = item['dist']
    dt = item['dt']
    
    if k == 0 or idx - 1 < 0 or items[idx-1]['type'] == 'G4':
        v0 = 0.0
    else:
        v0 = min(v_nom, items[g1_indices[k-1]]['v_nom'])
        
    if k == len(g1_indices) - 1 or idx + 1 >= len(items) or items[idx+1]['type'] == 'G4':
        v1 = 0.0
    else:
        v1 = min(v_nom, items[g1_indices[k+1]]['v_nom'])
        
    B = v0 + v1 + a_vec * dt
    C = a_vec * d + 0.5 * (v0**2 + v1**2)
    disc = B**2 - 4*C
    if disc >= 0:
        v_corr = (B - np.sqrt(disc)) / 2.0
    else:
        v_corr = v_nom
        
    item['speed'] = max(0.1, v_corr * 60.0)

# Simulate
n = len(g1_indices)
v_target = np.array([items[idx]['speed'] / 60.0 for idx in g1_indices])
d = np.array([items[idx]['dist'] for idx in g1_indices])

v_junc = np.zeros(n + 1)
v_junc[0] = 0.0
v_junc[n] = 0.0
for i in range(1, n):
    v_junc[i] = min(v_target[i-1], v_target[i])

for i in range(n-1, -1, -1):
    max_entry = np.sqrt(v_junc[i+1]**2 + 2*a_vec*d[i])
    if v_junc[i] > max_entry:
        v_junc[i] = max_entry

for i in range(n):
    max_exit = np.sqrt(v_junc[i]**2 + 2*a_vec*d[i])
    if v_junc[i+1] > max_exit:
        v_junc[i+1] = max_exit

durations = []
for i in range(n):
    v0 = v_junc[i]
    v1 = v_junc[i+1]
    vt = v_target[i]
    d_req = (2*vt**2 - v0**2 - v1**2)/(2*a_vec)
    if d[i] >= d_req:
        dur = (vt - v0)/a_vec + (vt - v1)/a_vec + (d[i] - d_req)/vt
    else:
        v_peak = np.sqrt((2*a_vec*d[i] + v0**2 + v1**2)/2.0)
        dur = (v_peak - v0)/a_vec + (v_peak - v1)/a_vec
    durations.append(dur)

total_g1 = sum(durations)
target_g1 = sum(it['dt'] for it in items if it['type'] == 'G1')
total_dwell = sum(it['dwell'] for it in items if it['type'] == 'G4')
print(f"Total G1 simulated: {total_g1:.6f}s (target nominal: {target_g1:.6f}s)")
print(f"Total cycle: {total_g1 + total_dwell:.6f}s")
print(f"Cycle error with kinematic speed correction: {(total_g1 + total_dwell - 4.0)*1000:.3f} ms!")
