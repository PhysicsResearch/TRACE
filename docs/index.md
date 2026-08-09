# Welcome to TRACE

**TRACE (Triggered Radiotherapy Adaptive Control Engine)** is a dedicated software suite designed to control and verify dynamic anthropomorphic thorax phantoms used in 4D Radiotherapy (4DRT), motion management research, and image-guided radiation therapy (IGRT).

As described in *Lustermans et al. (2024)*, TRACE interfaces with multi-axis motion hardware and triggering electronics to simulate realistic patient breathing motions and evaluate 4DCT and radiotherapy treatment delivery.

---

## Key Features

- **Analytical & Patient-Derived Motion Profiles**:
    - Generate synthetic respiratory waveforms (sinusoidal, $\cos^4$, custom analytical functions).
    - Import and process patient-derived respiratory curves from 4DCT/RPM clinical logs.
    - Scale, smooth, adjust baseline drift, and resample motion profiles.
- **Multi-Axis Trajectory Planning**:
    - Full 6-DOF support (Translational: SI, AP, LR; Rotational: Roll, Pitch, Yaw).
    - Automated G-code generation optimized for Duet motion controllers.
- **Hardware Integration & Real-Time Control**:
    - Direct communication with Duet 3D motion platform controllers.
    - Real-time axis homing, position tracking, and manual jogging.
- **Triggered Imaging & Verification**:
    - Hardware synchronization with Geiger module for triggered imaging acquisition.
    - Live plotting and position error monitoring during motion execution.

---

## User Guide Overview

This User Guide provides end-to-end instructions for setting up, operating, and troubleshooting TRACE:

1. **[Installation](getting-started/installation.md)**: Setting up the Python environment and launching TRACE.
2. **[Hardware Setup](getting-started/hardware-setup.md)**: Connecting the Duet controller, phantom stage, and Geiger trigger module.
3. **[Files & Project Management](user-guide/01-files-tab.md)**: Managing project directories and patient motion datasets.
4. **[Motion Planning & G-code](user-guide/02-motion-planning.md)**: Creating analytical waveforms, editing patient curves, and exporting G-code.
5. **[Phantom Control & Execution](user-guide/03-phantom-control.md)**: Homing, running motion trajectories, and triggering.
6. **[Real-Time Status & Monitoring](user-guide/04-status-monitoring.md)**: Live verification, logging, and performance metrics.
7. **[Troubleshooting & Safety](troubleshooting/common-issues.md)**: Resolving connection issues, limit switch stops, and safety protocols.

!!! tip "Download PDF Manual"
    When built with the `with-pdf` plugin, the complete documentation is available as a single downloadable PDF manual under `exports/TRACE_User_Guide.pdf`.
