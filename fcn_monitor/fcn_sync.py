import numpy as np
from .fcn_duet import set_GCODE_speed

# --- SYNCHRONIZATION FUNCTIONS ---

def calc_diff(self):
    # Get the last time and position from the buffers
    t = self.time_buffer[-1]
    x_meas = self.x_buffer[-1]

    t_offset = self.MoVeOffsetSlider.value() * self.UPDATE_INTERVAL
    t0, t1 = t - 1.5, t + 1.5

    df_roi = self.orig_data.loc[(self.orig_data["time"] >= t0 + t_offset) & (self.orig_data["time"] <= t1 + t_offset)]
    t_roi = df_roi["time"] - t_offset
    x_planned = df_roi["amplitude"]

    # Calculate t_offset with minimum amplitude differences
    ampl_diff = x_planned - x_meas
    idx = ampl_diff.abs().idxmin()
    t_diff = t - t_roi[idx]

    # Calculate the speed factor adjustment, relative to user defined default 
    speed_factor = self.MoVeUserSetSpeed * (t_diff * np.median(self.MoVeData['x']['x']) / 35 + 1)

    # Clip between 90 - 120% to avoid explosive speed changes
    speed_factor = np.clip(speed_factor, 0.9 * self.MoVeUserSetSpeed, 1.2 * self.MoVeUserSetSpeed)

    # Set adjusted GCODE speed factor
    set_GCODE_speed(self, speed_factor)