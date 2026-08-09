# Chapter 4: Real-Time Status & Monitoring

The **Status Tab** (`tab_status.py`, `fcn_duet.py`, `fcn_plotting.py`) monitors motion execution in real time, displays live feedback plots, and logs trigger events for post-experiment validation.

---

## 1. Live Motion Tracking Plots

During motion execution, TRACE renders real-time multi-axis tracking plots:

- **Planned Trajectory (Blue)**: Target position requested by G-code.
- **Actual Feedback Position (Red)**: Encoder / motor feedback reported by controller.
- **Position Error (Green)**: Difference $\Delta z(t) = z_{\text{actual}}(t) - z_{\text{planned}}(t)$.

---

## 2. Dynamic Performance Indicators

The telemetry panel displays:

- **Current Axis Positions**: Live coordinates $(X, Y, Z, U, V, W)$.
- **Actual Speed / Velocity**: Real-time motion speed in $\text{mm/s}$.
- **Buffer State**: Controller G-code command buffer fill level (prevents buffer underruns during high-frequency motion).
- **Trigger Event Counter**: Total number of Geiger trigger pulses issued during the session.

---

## 3. Logging & Data Export

TRACE automatically records execution logs for motion quality assurance (QA):

- **Save Log File**: Exports execution history to CSV format (`motion_log_YYYYMMDD_HHMMSS.csv`).
- **QA Metrics**:
    - **Root Mean Square Error (RMSE)** across the entire trajectory:
      $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} \left(z_{\text{actual}}(i) - z_{\text{planned}}(i)\right)^2}$$
    - **Max Peak Position Error**.
    - **Trigger Jitter**: Timing variation between planned phase and actual electrical pulse.
