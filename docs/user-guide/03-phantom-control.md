# Chapter 3: Phantom Control & Execution

The **Control Tab** (`tab_control.py` & `fcn_control.py`) provides direct control over the dynamic thorax phantom hardware, motor initialization, manual jogging, G-code execution, and trigger synchronization.

---

## 1. Connecting to Hardware

1. Navigate to the **Control** tab.
2. Select connection mode: **Ethernet (REST API)** or **Serial (COM)**.
3. Click **Connect Controller**.
4. Check connection status indicator:
    - 🟢 **Connected**: IP / COM port open and responding.
    - 🔴 **Disconnected**: Verify wiring or IP settings in `configuration.json`.

---

## 2. Homing & Zeroing Axes

Before executing any motion trajectory, the physical platform **MUST** be homed to establish mechanical zero reference points.

1. Ensure the platform path is clear.
2. Click **Home All Axes** ($G28$).
3. Wait for all axis status indicators to turn green.
4. Verify position readout shows `(0.00, 0.00, 0.00)`.

!!! warning "Axis Safety Limits"
    Never attempt to run G-code without homing first. Running motion profiles from un-homed positions can cause mechanical collision against endstops.

---

## 3. Manual Jogging

Use the manual jog panel to fine-tune phantom position or perform pre-experiment align checks:

- **Step Sizes**: $0.1\,\text{mm}, 1.0\,\text{mm}, 5.0\,\text{mm}, 10.0\,\text{mm}$.
- **Directions**: $\pm X, \pm Y, \pm Z, \pm \text{Roll}, \pm \text{Pitch}, \pm \text{Yaw}$.
- **Feedrate Control**: Adjustable speed slider ($10 - 3000\,\text{mm/min}$).

---

## 4. Running Motion Trajectories

To execute a planned G-code motion file:

1. Click **Select G-Code File** and pick your compiled trajectory.
2. Select execution mode:
    - **Single Cycle**: Plays motion sequence once and returns to home.
    - **Continuous Loop**: Repeats motion sequence until manually stopped.
3. Click **Start Motion**.
4. Use **Pause Motion** ($M600$) or **Emergency Stop** ($M112$) at any time to halt movement.

---

## 5. Geiger Triggering Configuration

To enable imaging/gating triggers during specific phases of the trajectory:

1. Toggle **Enable Geiger Trigger Sync**.
2. Set **Phase Trigger Point** (e.g., peak inspiration at $90^\circ$ or end expiration at $270^\circ$).
3. Set **Pulse Duration** (e.g., $50\,\text{ms}$).
4. Click **Test Trigger Signal** to verify optocoupler pulse output on the Geiger hardware module.
