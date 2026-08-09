# Troubleshooting & Safety Guide

This guide covers common operational issues, hardware error messages, recovery procedures, and safety protocols when running TRACE with the dynamic phantom.

---

## Hardware Connection Issues

### 1. "Duet Controller Disconnected / Timeout"

**Symptoms**: Red status indicator, commands fail to send.

**Solutions**:
- Verify Ethernet cable connection between workstation and Duet.
- Test network connectivity:
  ```bash
  ping 192.168.1.100
  ```
- Open browser and navigate to `http://192.168.1.100` to confirm Duet Web Control (DWC) is responding.
- Verify IP address matches `duet_ip` in `configuration.json`.

---

### 2. "Geiger Serial Port COMx Not Found"

**Symptoms**: Cannot toggle trigger synchronization or test pulses.

**Solutions**:
- Unplug USB-to-Serial cable and re-insert.
- Open Device Manager (Windows) or run `ls /dev/tty*` (Linux) to check assigned port number.
- Update `geiger_port` in `configuration.json` and restart TRACE.

---

## Motion & Limit Switch Errors

### 3. "Axis Hit Limit Switch / Endstop Triggered"

**Symptoms**: Emergency stop activated, movement freezes mid-trajectory.

**Solutions**:
1. Check physical platform position for mechanical obstruction or extreme travel.
2. Click **Reset Controller Alarm**.
3. Use manual jog controls in reverse direction at low speed ($0.1\,\text{mm}$) to backed off switch.
4. Verify motion trajectory limits in **Planning Tab** before re-running.

---

### 4. "Buffer Underrun / Stuttering Motion"

**Symptoms**: Phantom movement stutters or pauses intermittently.

**Solutions**:
- Reduce point density / increase step interval in **Planning Tab** during G-code generation.
- Close CPU-intensive background applications.
- Switch connection mode from Serial to Ethernet REST API for higher throughput.

---

## Safety Protocols

!!! caution "Laboratory Safety Guidelines"
    - **Never place hands or tools inside the phantom motion stage while power is applied.**
    - Keep the hardware Emergency Stop button within easy reach during all automated trajectory runs.
    - Inspect motor belts and mechanical fasteners weekly for wear or tension loss.
