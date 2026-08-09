# Hardware Setup & Wiring

This guide details the physical hardware setup for connecting the dynamic anthropomorphic thorax phantom, the motion platform controller, and the triggering hardware to TRACE.

---

## Hardware Architecture

The TRACE ecosystem consists of three main hardware components:

```
+-------------------+        Ethernet / USB       +---------------------------+
|                   | <-------------------------> |  Duet Motion Controller   |
|   Workstation     |                             |   (Stepper Axis Drivers)  |
|  Running TRACE    |                             +---------------------------+
|                   |                                           |
|                   |        RS-232 / USB                       v
|                   | <-------------------------> +---------------------------+
+-------------------+                             | Dynamic Thorax Phantom    |
                                                  | (SI, AP, LR & Rotational) |
                                                  +---------------------------+
                                                                |
                                                                v
                                                  +---------------------------+
                                                  | Geiger Triggering Module  |
                                                  |   (4DCT / Linac Sync)     |
                                                  +---------------------------+
```

---

## 1. Duet Motion Controller Setup

TRACE communicates with a **Duet 3D motion controller** via HTTP REST API or Direct Serial Interface.

1. **Network Cable**: Connect an Ethernet cable from your workstation/switch to the Duet Ethernet port.
2. **IP Configuration**: Ensure the IP address matches `duet_ip` in `configuration.json` (Default: `192.168.1.100`).
3. **Axis Assignments**:
    - **Axis X**: Superior-Inferior (SI) translation.
    - **Axis Y**: Anterior-Posterior (AP) translation.
    - **Axis Z**: Left-Right (LR) translation.
    - **Axis U / V / W**: Rotational axes (Roll, Pitch, Yaw).

!!! warning "Emergency Stop Button"
    Always test the hardware E-STOP button wired to the Duet controller before running automated motion sequences.

---

## 2. Geiger Triggering Module Setup

The Geiger module enables synchronized X-ray imaging / 4DCT triggering during specific phases of phantom motion.

1. **Serial Connection**: Plug the USB-to-Serial adapter from the Geiger module into the workstation.
2. **Identify Port**: Note the assigned COM port (Windows: `COMx`, Linux/macOS: `/dev/ttyUSBx`).
3. **Trigger Output**: Connect the opto-isolated trigger output cable to the external trigger input of the imaging modality (Linac / CT scanner).

---

## 3. Power-On Checklist

Before launching TRACE:

- [ ] Verify 24V power supply connected to Duet controller.
- [ ] Confirm phantom motion stage is free from physical obstacles.
- [ ] Confirm Geiger module LED power indicator is green.
- [ ] Ping Duet IP (`ping 192.168.1.100`) from command prompt.
