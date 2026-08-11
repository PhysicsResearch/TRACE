import numpy as np
import math

def generate_gcode_string(
    device,
    t_orig,
    columns_data,
    max_limits,
    lat_dim=100.0,
    si_dim=100.0,
    off_ap=0.0,
    off_lat=0.0,
    off_si=0.0,
    axis_y_lo="'c"
):
    """
    Independent pure function to generate G-code lines from original time and axes data.
    Supports both "Lung Phantom" and "Motion Platform" devices.
    """
    t_max = t_orig.max()
    total_time_seconds = int(round(float(t_orig.max() - t_orig.min())))
    
    # Dynamically detect time step dt of the original curve
    if len(t_orig) > 1:
        dt = t_orig[1] - t_orig[0]
        if dt <= 0.0:
            dt = 0.001
    else:
        dt = 0.001
    t_new = np.arange(0.0, t_max + dt / 2.0, dt)

    # Map any wait radiation commands to the closest time index in t_new
    commands_dict = {}
    if "Command" in columns_data:
        for idx, cmd in enumerate(columns_data["Command"]):
            if isinstance(cmd, str) and cmd.strip():
                t_val = t_orig[idx]
                commands_dict[t_val] = cmd.strip()

    new_commands_indices = {}
    for t_val, cmd in commands_dict.items():
        new_idx = np.argmin(np.abs(t_new - t_val))
        new_commands_indices[new_idx] = cmd

    exceeds_limits = False

    if device == "Lung Phantom":
        X_orig = columns_data["X"]
        Y_orig = columns_data["Y"]
        Z_orig = columns_data["Z"]

        X_new = np.clip(np.interp(t_new, t_orig, X_orig), 0.0, None)
        Y_new = np.clip(np.interp(t_new, t_orig, Y_orig), 0.0, None)
        Z_new = np.clip(np.interp(t_new, t_orig, Z_orig), 0.0, None)

        lim_x, lim_y, lim_z = max_limits
        if np.any(np.abs(X_new) > lim_x) or np.any(np.abs(Y_new) > lim_y) or np.any(np.abs(Z_new) > lim_z):
            exceeds_limits = True

        gcode_lines = [f"; TIME: {total_time_seconds}", "G90"]
        last_x, last_y, last_z = X_new[0], Y_new[0], Z_new[0]
        dwell_accum = 0.0
        last_pos_written_idx = 0

        # Output first point
        gcode_lines.append(f"G1 F1000.000000 X{last_x:.6f} Y{last_y:.6f} Z{last_z:.6f}")

        def flush_dwell():
            nonlocal dwell_accum
            if dwell_accum > 0.0:
                ms = int(round(dwell_accum * 1000.0))
                if ms > 0:
                    gcode_lines.append(f"G4 P{ms}")
                dwell_accum = 0.0

        for i in range(1, len(t_new)):
            if i in new_commands_indices:
                flush_dwell()
                gcode_lines.append(new_commands_indices[i])

            dx_from_last = X_new[i] - last_x
            dy_from_last = Y_new[i] - last_y
            dz_from_last = Z_new[i] - last_z
            max_diff = max(abs(dx_from_last), abs(dy_from_last), abs(dz_from_last))

            # Distinguish between truly stationary and decimated steps
            is_stationary = (X_new[i] == X_new[i-1]) and (Y_new[i] == Y_new[i-1]) and (Z_new[i] == Z_new[i-1])

            if is_stationary:
                dwell_accum += (t_new[i] - t_new[i-1])
            elif max_diff < 0.01:
                # Decimated step (skip G1, don't accumulate dwell)
                pass
            else:
                # Calculate dt_elapsed BEFORE flushing dwell_accum
                dt_elapsed = max(0.001, t_new[i] - t_new[last_pos_written_idx] - dwell_accum)
                flush_dwell()
                dx = X_new[i] - last_x
                dy = Y_new[i] - last_y
                dz = Z_new[i] - last_z
                dist = np.sqrt(dx*dx + dy*dy + dz*dz)
                
                speed = (dist / dt_elapsed) * 60.0
                if speed < 0.1:
                    speed = 0.1

                gcode_lines.append(f"G1 F{speed:.6f} X{X_new[i]:.6f} Y{Y_new[i]:.6f} Z{Z_new[i]:.6f}")
                last_x, last_y, last_z = X_new[i], Y_new[i], Z_new[i]
                last_pos_written_idx = i

        dt_elapsed = max(0.001, t_new[-1] - t_new[last_pos_written_idx] - dwell_accum)
        flush_dwell()
        if last_pos_written_idx < len(t_new) - 1:
            idx = len(t_new) - 1
            dx = X_new[idx] - last_x
            dy = Y_new[idx] - last_y
            dz = Z_new[idx] - last_z
            dist = np.sqrt(dx*dx + dy*dy + dz*dz)
            speed = (dist / dt_elapsed) * 60.0
            if speed < 0.1:
                speed = 0.1
            gcode_lines.append(f"G1 F{speed:.6f} X{X_new[idx]:.6f} Y{Y_new[idx]:.6f} Z{Z_new[idx]:.6f}")

    elif device == "Motion Platform":
        LAT_orig = columns_data["LAT"]
        SI_orig = columns_data["SI"]
        AP_orig = columns_data["AP"]
        Roll_orig = columns_data["Roll"]
        Pitch_orig = columns_data["Pitch"]
        Yaw_orig = columns_data["Yaw"]

        lim_lat, lim_si, lim_ap, lim_roll, lim_pitch, lim_yaw = max_limits

        LAT_new = np.clip(np.interp(t_new, t_orig, LAT_orig), 0.0, lim_lat)
        SI_new = np.clip(np.interp(t_new, t_orig, SI_orig), 0.0, lim_si)
        AP_new = np.clip(np.interp(t_new, t_orig, AP_orig), 0.0, lim_ap)
        Roll_new = np.interp(t_new, t_orig, Roll_orig)
        Pitch_new = np.interp(t_new, t_orig, Pitch_orig)
        Yaw_new = np.interp(t_new, t_orig, Yaw_orig)

        if (np.any(np.abs(LAT_new) > lim_lat) or 
            np.any(np.abs(SI_new) > lim_si) or 
            np.any(np.abs(AP_new) > lim_ap) or 
            np.any(np.abs(Roll_new) > lim_roll) or 
            np.any(np.abs(Pitch_new) > lim_pitch) or 
            np.any(np.abs(Yaw_new) > lim_yaw)):
            exceeds_limits = True

        # Ensure platform dimensions are non-zero positive numbers
        if lat_dim <= 0.0:
            lat_dim = 100.0
        if si_dim <= 0.0:
            si_dim = 100.0

        # Calculate actuator positions A, B, C, D
        support_points = {
            'A': (-lat_dim / 2.0, -si_dim / 2.0, 0.0),
            'B': (lat_dim / 2.0, -si_dim / 2.0, 0.0),
            'C': (lat_dim / 2.0, si_dim / 2.0, 0.0),
            'D': (-lat_dim / 2.0, si_dim / 2.0, 0.0)
        }

        A_new = np.zeros_like(t_new)
        B_new = np.zeros_like(t_new)
        C_new = np.zeros_like(t_new)
        D_new = np.zeros_like(t_new)

        for i in range(len(t_new)):
            r = math.radians(Roll_new[i])
            p = -math.radians(Pitch_new[i])  # Negated to match step buttons convention
            y = math.radians(Yaw_new[i])

            cos_r, sin_r = math.cos(r), math.sin(r)
            cos_p, sin_p = math.cos(p), math.sin(p)
            cos_y, sin_y = math.cos(y), math.sin(y)

            xc, yc, zc = 0.0, 0.0, off_ap

            target_z = {}
            for name, (px, py, pz) in support_points.items():
                x1 = px - xc
                y1 = py - yc
                z1 = pz - zc

                # Yaw (Z)
                x2 = cos_y * x1 - sin_y * y1
                y2 = sin_y * x1 + cos_y * y1
                z2 = z1

                # Roll (Y)
                x3 = x2 * cos_r + z2 * sin_r
                y3 = y2
                z3 = -x2 * sin_r + z2 * cos_r

                # Pitch (X)
                x4 = x3
                y4 = y3 * cos_p - z3 * sin_p
                z4 = y3 * sin_p + z3 * cos_p

                target_z[name] = z4 + zc + AP_new[i]

            A_new[i] = max(0.0, min(lim_ap, target_z['A']))
            B_new[i] = max(0.0, min(lim_ap, target_z['B']))
            C_new[i] = max(0.0, min(lim_ap, target_z['C']))
            D_new[i] = max(0.0, min(lim_ap, target_z['D']))

        # Compute sway compensation offset for LAT and SI
        roll_rad = np.radians(Roll_new)
        pitch_rad = np.radians(Pitch_new)

        LAT_eff = np.clip(off_lat + LAT_new + off_ap * np.sin(roll_rad), 0.0, lim_lat)
        SI_eff = np.clip(off_si + SI_new + off_ap * np.sin(pitch_rad), 0.0, lim_si)

        gcode_lines = [f"; TIME: {total_time_seconds}", "G90"]
        last_A, last_B, last_C, last_D = A_new[0], B_new[0], C_new[0], D_new[0]
        last_LAT, last_SI = LAT_eff[0], SI_eff[0]
        dwell_accum = 0.0
        last_pos_written_idx = 0

        # Output first point
        gcode_lines.append(
            f"G1 F1000.000000 A{last_A:.6f} B{last_B:.6f} C{last_C:.6f} D{last_D:.6f} "
            f"'e{last_LAT:.6f} 'f{last_LAT:.6f} 'a{last_SI:.6f} {axis_y_lo}{last_SI:.6f}"
        )

        def flush_dwell():
            nonlocal dwell_accum
            if dwell_accum > 0.0:
                ms = int(round(dwell_accum * 1000.0))
                if ms > 0:
                    gcode_lines.append(f"G4 P{ms}")
                dwell_accum = 0.0

        for i in range(1, len(t_new)):
            if i in new_commands_indices:
                flush_dwell()
                gcode_lines.append(new_commands_indices[i])

            # Distinguish between truly stationary and moving steps
            is_stationary = (
                LAT_eff[i] == LAT_eff[i-1] and
                SI_eff[i] == SI_eff[i-1] and
                AP_new[i] == AP_new[i-1] and
                Roll_new[i] == Roll_new[i-1] and
                Pitch_new[i] == Pitch_new[i-1] and
                Yaw_new[i] == Yaw_new[i-1]
            )

            if is_stationary:
                dwell_accum += (t_new[i] - t_new[i-1])
            else:
                # Calculate dt_elapsed BEFORE flushing dwell_accum
                dt_elapsed = max(0.001, t_new[i] - t_new[last_pos_written_idx] - dwell_accum)
                flush_dwell()
                dA = A_new[i] - last_A
                dB = B_new[i] - last_B
                dC = C_new[i] - last_C
                dD = D_new[i] - last_D
                
                # Primary motion actuators for distance calculation
                dist = np.sqrt(dA*dA + dB*dB + dC*dC + dD*dD)
                speed = (dist / dt_elapsed) * 60.0
                if speed < 0.1:
                    speed = 0.1

                gcode_lines.append(
                    f"G1 F{speed:.6f} A{A_new[i]:.6f} B{B_new[i]:.6f} C{C_new[i]:.6f} D{D_new[i]:.6f} "
                    f"'e{LAT_eff[i]:.6f} 'f{LAT_eff[i]:.6f} 'a{SI_eff[i]:.6f} {axis_y_lo}{SI_eff[i]:.6f}"
                )
                last_A, last_B, last_C, last_D, last_LAT, last_SI = A_new[i], B_new[i], C_new[i], D_new[i], LAT_eff[i], SI_eff[i]
                last_pos_written_idx = i

        dt_elapsed = max(0.001, t_new[-1] - t_new[last_pos_written_idx] - dwell_accum)
        flush_dwell()
        if last_pos_written_idx < len(t_new) - 1:
            idx = len(t_new) - 1
            dA = A_new[idx] - last_A
            dB = B_new[idx] - last_B
            dC = C_new[idx] - last_C
            dD = D_new[idx] - last_D
            de = LAT_new[idx] - last_LAT
            df = LAT_new[idx] - last_LAT
            da = SI_new[idx] - last_SI
            dc = SI_new[idx] - last_SI
            dist = np.sqrt(dA*dA + dB*dB + dC*dC + dD*dD + de*de + df*df + da*da + dc*dc)
            speed = (dist / dt_elapsed) * 60.0
            if speed < 0.1:
                speed = 0.1
            gcode_lines.append(
                f"G1 F{speed:.6f} A{A_new[idx]:.6f} B{B_new[idx]:.6f} C{C_new[idx]:.6f} D{D_new[idx]:.6f} "
                f"'e{LAT_new[idx]:.6f} 'f{LAT_new[idx]:.6f} 'a{SI_new[idx]:.6f} {axis_y_lo}{SI_new[idx]:.6f}"
            )

    else: # Other
        new_data = {}
        for col, arr in columns_data.items():
            if col != "Command":
                new_data[col] = np.interp(t_new, t_orig, arr)
                
        if max_limits and len(max_limits) > 0:
            lim = max_limits[0]
            for col in new_data:
                if np.any(np.abs(new_data[col]) > lim):
                    exceeds_limits = True

        gcode_lines = [f"; TIME: {total_time_seconds}", "G90"]
        last_vals = {col: new_data[col][0] for col in new_data}
        dwell_accum = 0.0
        last_pos_written_idx = 0

        # Output first point
        axis_parts = []
        for col in sorted(new_data.keys()):
            axis_parts.append(f"{col}{last_vals[col]:.6f}")
        axis_str = " ".join(axis_parts)
        gcode_lines.append(f"G1 F1000.000000 {axis_str}")

        def flush_dwell():
            nonlocal dwell_accum
            if dwell_accum > 0.0:
                ms = int(round(dwell_accum * 1000.0))
                if ms > 0:
                    gcode_lines.append(f"G4 P{ms}")
                dwell_accum = 0.0

        for i in range(1, len(t_new)):
            if i in new_commands_indices:
                flush_dwell()
                gcode_lines.append(new_commands_indices[i])

            max_diff = max(abs(new_data[col][i] - last_vals[col]) for col in new_data)

            is_stationary = all(new_data[col][i] == new_data[col][i-1] for col in new_data)

            if is_stationary:
                dwell_accum += (t_new[i] - t_new[i-1])
            elif max_diff < 0.01:
                # Decimated step
                pass
            else:
                # Calculate dt_elapsed BEFORE flushing dwell_accum
                dt_elapsed = max(0.001, t_new[i] - t_new[last_pos_written_idx] - dwell_accum)
                flush_dwell()
                dist_sq = 0.0
                for col in new_data:
                    diff = new_data[col][i] - last_vals[col]
                    dist_sq += diff * diff
                dist = np.sqrt(dist_sq)
                speed = (dist / dt_elapsed) * 60.0
                if speed < 0.1:
                    speed = 0.1

                axis_parts = []
                for col in sorted(new_data.keys()):
                    axis_parts.append(f"{col}{new_data[col][i]:.6f}")
                axis_str = " ".join(axis_parts)
                gcode_lines.append(f"G1 F{speed:.6f} {axis_str}")
                for col in new_data:
                    last_vals[col] = new_data[col][i]
                last_pos_written_idx = i

        dt_elapsed = max(0.001, t_new[-1] - t_new[last_pos_written_idx] - dwell_accum)
        flush_dwell()
        if last_pos_written_idx < len(t_new) - 1:
            idx = len(t_new) - 1
            dist_sq = 0.0
            for col in new_data:
                diff = new_data[col][idx] - last_vals[col]
                dist_sq += diff * diff
            dist = np.sqrt(dist_sq)
            speed = (dist / dt_elapsed) * 60.0
            if speed < 0.1:
                speed = 0.1
            axis_parts = []
            for col in sorted(new_data.keys()):
                axis_parts.append(f"{col}{new_data[col][idx]:.6f}")
            axis_str = " ".join(axis_parts)
            gcode_lines.append(f"G1 F{speed:.6f} {axis_str}")

    return '\n'.join(gcode_lines), exceeds_limits
