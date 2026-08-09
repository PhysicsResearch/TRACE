# Installation & Software Setup

This page guides you through installing the required dependencies and launching the TRACE Graphical User Interface (GUI).

---

## Prerequisites

Before installing TRACE, ensure you have installed:

- **Python 3.10 or later** (Conda or Miniconda environment recommended).
- **Git** (for repository cloning).

---

## Installation Steps

### Step 1: Clone the Repository

Clone the TRACE repository using Git or your preferred Git client (e.g., SourceTree, GitHub Desktop):

```bash
git clone https://github.com/YourUsername/TRACE.git
cd TRACE
```

### Step 2: Create Conda Environment

TRACE provides an `environment.yml` file containing all required packages (PyQt / DearPyGui, NumPy, SciPy, Matplotlib, PySerial, etc.).

Create and activate the environment:

```bash
conda env create -f environment.yml
conda activate trace-env
```

Alternatively, if installing dependencies manually via `pip`:

```bash
pip install numpy scipy matplotlib pyqt5 pyserial requests
```

---

## Configuration (`configuration.json`)

Check `configuration.json` in the root directory to verify hardware settings (IP address of Duet controller, default COM ports for Geiger module, default baud rates):

```json
{
  "duet_ip": "192.168.1.100",
  "geiger_port": "COM3",
  "baud_rate": 115250,
  "default_output_dir": "./output"
}
```

---

## Launching TRACE

To launch the graphical user interface, run `Launch_ImGUI.py`:

```bash
python Launch_ImGUI.py
```

!!! note "First Launch Verification"
    Upon successful launch, the TRACE interface window will open, displaying the navigation tabs (**Files**, **Planning**, **Control**, **Status**) and initializing the communication threads in the background.
