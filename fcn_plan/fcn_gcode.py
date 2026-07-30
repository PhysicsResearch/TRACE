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
    t_new = np.arange(0.0, t_max + 0.0005, 0.001)

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

        X_new = np.interp(t_new, t_orig, X_orig)
        Y_new = np.interp(t_new, t_orig, Y_orig)
        Z_new = np.interp(t_new, t_orig, Z_orig)

        lim_x, lim_y, lim_z = max_limits
        if np.any(np.abs(X_new) > lim_x) or np.any(np.abs(Y_new) > lim_y) or np.any(np.abs(Z_new) > lim_z):
            exceeds_limits = True

        gcode_lines = ["G90"]

        for i in range(len(t_new)):
            if i in new_commands_indices:
                gcode_lines.append(new_commands_indices[i])
            if i == 0:
                speed = 1000.0
            else:
                dx = X_new[i] - X_new[i-1]
                dy = Y_new[i] - Y_new[i-1]
                dz = Z_new[i] - Z_new[i-1]
                dist = np.sqrt(dx*dx + dy*dy + dz*dz)
                speed = dist * 60000.0

            gcode_lines.append(f"G1 F{speed:.6f} X{X_new[i]:.6f} Y{Y_new[i]:.6f} Z{Z_new[i]:.6f}")

    elif device == "Motion Platform":
        LAT_orig = columns_data["LAT"]
        SI_orig = columns_data["SI"]
        AP_orig = columns_data["AP"]
        Roll_orig = columns_data["Roll"]
        Pitch_orig = columns_data["Pitch"]
        Yaw_orig = columns_data["Yaw"]

        LAT_new = np.interp(t_new, t_orig, LAT_orig)
        SI_new = np.interp(t_new, t_orig, SI_orig)
        AP_new = np.interp(t_new, t_orig, AP_orig)
        Roll_new = np.interp(t_new, t_orig, Roll_orig)
        Pitch_new = np.interp(t_new, t_orig, Pitch_orig)
        Yaw_new = np.interp(t_new, t_orig, Yaw_orig)

        lim_lat, lim_si, lim_ap, lim_roll, lim_pitch, lim_yaw = max_limits
        if (np.any(np.abs(LAT_new) > lim_lat) or 
            np.any(np.abs(SI_new) > lim_si) or 
            np.any(np.abs(AP_new) > lim_ap) or 
            np.any(np.abs(Roll_new) > lim_roll) or 
            np.any(np.abs(Pitch_new) > lim_pitch) or 
            np.any(np.abs(Yaw_new) > lim_yaw)):
            exceeds_limits = True

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

            A_new[i] = target_z['A']
            B_new[i] = target_z['B']
            C_new[i] = target_z['C']
            D_new[i] = target_z['D']

        gcode_lines = ["G90"]

        for i in range(len(t_new)):
            if i in new_commands_indices:
                gcode_lines.append(new_commands_indices[i])
            if i == 0:
                speed = 1000.0
            else:
                dA = A_new[i] - A_new[i-1]
                dB = B_new[i] - B_new[i-1]
                dC = C_new[i] - C_new[i-1]
                dD = D_new[i] - D_new[i-1]
                de = LAT_new[i] - LAT_new[i-1]
                df = LAT_new[i] - LAT_new[i-1]
                da = SI_new[i] - SI_new[i-1]
                dc = SI_new[i] - SI_new[i-1]
                
                dist = np.sqrt(dA*dA + dB*dB + dC*dC + dD*dD + de*de + df*df + da*da + dc*dc)
                speed = dist * 60000.0

            gcode_lines.append(
                f"G1 F{speed:.6f} A{A_new[i]:.6f} B{B_new[i]:.6f} C{C_new[i]:.6f} D{D_new[i]:.6f} "
                f"'e{LAT_new[i]:.6f} 'f{LAT_new[i]:.6f} 'a{SI_new[i]:.6f} {axis_y_lo}{SI_new[i]:.6f}"
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

        gcode_lines = ["G90"]
        
        for i in range(len(t_new)):
            if i in new_commands_indices:
                gcode_lines.append(new_commands_indices[i])
            if i == 0:
                speed = 1000.0
            else:
                dist_sq = 0.0
                for col in new_data:
                    diff = new_data[col][i] - new_data[col][i-1]
                    dist_sq += diff * diff
                dist = np.sqrt(dist_sq)
                speed = dist * 60000.0
                
            axis_parts = []
            for col in sorted(new_data.keys()):
                axis_parts.append(f"{col}{new_data[col][i]:.6f}")
            axis_str = " ".join(axis_parts)
            gcode_lines.append(f"G1 F{speed:.6f} {axis_str}")

    return '\n'.join(gcode_lines), exceeds_limits
