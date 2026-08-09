# Chapter 2: Motion Planning & G-code Export

The **Planning Tab** (`tab_planning.py` & `fcn_plan`) is where motion profiles are designed, edited, mathematically transformed, and compiled into controller-ready G-code.

---

## 1. Creating Analytical Waveforms

TRACE allows you to generate synthetic mathematical motion curves to simulate standard breathing patterns or mechanical test signals.

### Available Analytical Waveform Types

1. **Sinusoidal Curve**:
   $$z(t) = A \cdot \sin\left(\frac{2\pi}{T} t + \phi\right) + z_0$$
   - $A$: Amplitude (mm)
   - $T$: Breathing period (seconds)
   - $\phi$: Phase offset (rad)
   - $z_0$: Baseline offset (mm)

2. **Modified $\cos^4$ Breathing Curve**:
   Simulates realistic asymmetry between inspiration and expiration phases:
   $$z(t) = A \cdot \cos^4\left(\frac{\pi}{T} t\right) + z_0$$

3. **Trapezoidal / Step Motion**:
   Used for step response tests and static phantom offset calibrations.

---

## 2. Editing Patient-Derived Motion Curves

Raw clinical respiratory traces often contain baseline drift, high-frequency noise, or cardiac artifacts. TRACE provides interactive tools in `fcn_edit.py` to refine these profiles:

- **Baseline Correction**: Removes gradual baseline elevation drift over time.
- **Amplitude Scaling**: Rescales motion to match specific phantom limits (e.g., max 30 mm SI displacement).
- **Smoothing / Filtering**: Applies Savitzky-Golay or low-pass Butterworth filtering to eliminate signal noise.
- **Resampling**: Interpolates motion data to match the Duet motor update frequency (typically 50 Hz or 100 Hz).

---

## 3. Multi-Axis Preview

Before exporting G-code, preview the 6-DOF motion components in the interactive plot panel:

- **SI Axis (Z-motion)**: Primary Superior-Inferior displacement.
- **AP Axis (Y-motion)**: Anterior-Posterior displacement.
- **LR Axis (X-motion)**: Left-Right displacement.
- **Rotational Axes (Roll, Pitch, Yaw)**: Rotational tilting.

---

## 4. Exporting G-Code for Duet Controller

Once you are satisfied with the trajectory:

1. Select target motor acceleration and velocity limits.
2. Click **Generate G-Code** (`fcn_gcode.py`).
3. TRACE compiles linear/curved segment commands:
   ```gcode
   G90 ; Absolute positioning mode
   G1 X12.4 Y2.1 Z-5.0 F1200 ; Linear move with feedrate 1200 mm/min
   G1 X12.8 Y2.3 Z-4.8 F1250
   ```
4. Click **Save G-Code** to store the `.gcode` file into your project output directory.
