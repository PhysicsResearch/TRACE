# Import required libraries and functions
import os
import time
import numpy as np
import pandas as pd
from datetime import datetime
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from PySide6.QtWidgets import QVBoxLayout, QMessageBox
from PySide6.QtCore import QThread
from .fcn_duet import get_curr_file, get_duet_status, pause_continue_GCODE
from .fcn_sync import calc_diff
   
# --- INITIALIZATION ---

def import_planned_curve(self, filename):
    """
    Function to import the reference curve from CSV file
    corresponding to the GCODE being executed
    """
    # Retrieve and check folder with planned curves
    csv_root = self.PhOperFolder.text()
    if not os.path.exists(csv_root):
        self.orig_data = None
        QMessageBox.warning(None, "Warning", "No valid input folder was provided.")
        return
    
    # Check whether GCODE has a corresponding CSV with planned data
    filepath = os.path.join(csv_root, filename.replace("gcode", "csv"))
    if not os.path.exists(filepath):
        self.orig_data = None
        QMessageBox.warning(None, "Warning", "The input folder does not contain a csv file corresponding to the GCODE being executed.")
        return
    
    # Import the planned curve data
    self.orig_data = pd.read_csv(filepath)


def init_MoVeTab(self):
    """
    Function to initialize the motion verification tab
    Initializes variables to store motion verification data 
    and starts the MoVeThread.
    """
    # Retrieve DUET IP-address 
    self.duet_ip = self.DuetIPAddress.text()

    # Retrieve filename currently being executed on DUET
    filename = get_curr_file(self)
    if filename is None:
        return
    
    # Retrieve planned curve data (for sync)
    import_planned_curve(self, filename)
    if self.orig_data is None:
        return
    
    self.acq_times     = self.orig_data[self.orig_data["acq"] == 1]["time"].tolist()
    self.ampl_scaling_MoVe  = self.orig_data["amplitude"].min() + self.orig_data["amplitude"].max() # Scaling factor for sync
    self.MoVeOffsetSlider.setRange(-200, 200)

    # Initialize variables
    self.t0         = time.time() 
    self.MoVeData   = {'x': {'t': [], 'x': []}, 
                       'y': {'t': [], 'y': []},
                       'z': {'t': [], 'z': []},
                       'acq': [], 'geiger': []}

    # Initialize figure and axes 
    self.fig_MoVe   = Figure()  
    self.ax_MoVe    = self.fig_MoVe.gca()
    self.buffers    = {}
    self.lines      = {}
    self.plot_axes  = []

    # Start MoVe data thread
    self.move_thread = MoVeThread(self)
    self.move_thread.start()


def update_axes(self):
    """
    This function updates the axes of the motion verification plot
    Is called whenever a checkbox is (un)checked
    """
    # Retrieve checked axis
    self.plot_axes = []
    axes = ['x', 'y', 'z'] # TO-DO: extend to axes for motion platform
    for a, check in enumerate([self.check_axis_X, self.check_axis_Y, self.check_axis_Z]):
        if check.isChecked():
            self.plot_axes.append(axes[a])

    # Create axes layout
    n_axes = len(self.plot_axes)
    layouts = {0: (1,1), 1: (1,1), 2: (2,1), 3: (2,2), 4: (2,2),
               5: (3,2), 6: (3,2), 7: (3,3), 8: (3,3), 9: (3,3)} 

    # Reinitialize axes
    self.fig_MoVe, self.ax_MoVe   = plt.subplots(*layouts[n_axes])
    self.MoVeCanvas = FigureCanvas(self.fig_MoVe)
    self.MoVeCanvas.setStyleSheet("background-color:Transparent;")

    container = self.MoVeView
    layout = container.layout()
    if layout is None:
        layout = QVBoxLayout(container)
        container.setLayout(layout)
    else:
        # Clear existing content in the container, if any
        while container.layout().count():
            child = container.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    layout.addWidget(self.MoVeCanvas)
    plt.tight_layout()

    if n_axes == 0:
        self.MoVeCanvas.draw()
        return
    
    self.ax_MoVe = np.atleast_1d(self.ax_MoVe)
    for i, ax in enumerate(self.ax_MoVe.ravel()):
        if i >= n_axes:
            ax.remove() # Remove unused axes from figure
        else:
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Position (mm)")
            ax.set_title(f'Axis: {self.plot_axes[i]}')

            self.lines[self.plot_axes[i]] = {
                'line1': ax.plot([], []),
                'line2': ax.plot([], [], color='orange'),
                'line3': ax.plot([], [], color='wheat')}
        
    self.MoVeCanvas.draw()
    
    # Update buffers
    max_points = int(self.WINDOW_DURATION / self.UPDATE_INTERVAL)
    for ax in axes:
        if ax in self.plot_axes and ax not in self.buffers:
            self.buffers[ax] = {'t': deque(maxlen=max_points), 
                                ax:  deque(maxlen=max_points)}
        if ax not in self.plot_axes and ax in self.buffers:
            self.buffers.pop(ax)


# --- MAIN MOTION VERIFICATION FUNCTIONS

class MoVeThread(QThread):
    """
    Main thread that runs the motion verification
    The function calls the update_MoVeData function every 50ms
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.running = True
        self.parent = parent

    def run(self):
        while self.running:
            UPDATE_INTERVAL = 0.05
            start_time = time.time()
            update_MoVeData(self.parent)
            elapsed = time.time() - start_time
            sleep_time = max(0, UPDATE_INTERVAL - elapsed)
            time.sleep(sleep_time)

    def stop(self):
        self.running = False
        self.wait()


def on_radiation_trigger_check(self):

    # Continue if triggered imaging checkbox unchecked
    if hasattr(self, 'pause') and not self.stop_until_radiation.isChecked():
        pause_continue_GCODE(self, False)
        delattr(self, 'pause')

    # Remove past acquisition times
    data = get_duet_status(self)

    if data is None:
        return
    print(self.acq_times)

    t = data['t']
    while True:
        # Check if acquisition time has passed
        t_diff = t - (self.acq_times[0] - self.MoVeOffsetSlider.value() * self.UPDATE_INTERVAL)
        if t_diff > 0:
            # Remove past acquisition time
            self.acq_times.pop(0)
        else:
            break

    print(self.acq_times)


def update_MoVeData(self):
    """
    Main update function called in thread. 
    - retrieves and stores the motion positions from DUET 
    - handles the pause and continue for triggered imaging
    """
    # Get current status from DUET
    data = get_duet_status(self)

    if data is None:
        return
    else:
        t = data['t']
        x = data['x']
        y = data['y']
        z = data['z']
        geiger = data['geiger']
    
    if len(self.acq_times) > 0:
        # Check if acquisition time has passed
        if t > (self.acq_times[0] - self.MoVeOffsetSlider.value() * self.UPDATE_INTERVAL):
            self.acq_times.pop(0) # Remove past acquisition time
            if self.stop_until_radiation.isChecked():
                if not hasattr(self, 'pause'): # Pause if not paused yet
                    pause_continue_GCODE(self)
                    self.pause = time.time()
                    return
    
    # Continue if paused and radiation detected
    if self.stop_until_radiation.isChecked() and hasattr(self, 'pause'):
        if geiger > 0:
            self.t0 += (time.time() - self.pause)
            t       -= (time.time() - self.pause)
            pause_continue_GCODE(self, False)
            delattr(self, 'pause')
        else:
            return

    # Auto-control    
    if not self.MoVeAutoControl.isChecked(): 
        # Upon start auto-control, set current speed as default
        self.MoVeUserSetSpeed = self.MoVeSpeedFactor.value()
    if hasattr(self, 'buffers') and len(self.buffers) > 0:
        # Retrieve available axis and call synchronization
        axis                = list(self.buffers.keys())[0]
        self.time_buffer    = self.buffers[axis]['t'] 
        self.x_buffer       = self.buffers[axis][axis]
        if self.MoVeAutoControl.isChecked() and len(self.time_buffer) > 10:
            calc_diff(self)

    # Store data to buffers for plotting
    if 'x' in self.buffers:
        self.buffers['x']['t'].append(t)
        self.buffers['x']['x'].append(x)
    if 'y' in self.buffers:
        self.buffers['y']['t'].append(t)
        self.buffers['y']['y'].append(y)
    if 'z' in self.buffers:
        self.buffers['z']['t'].append(t)
        self.buffers['z']['z'].append(z)
    
    # Store motion verification data
    self.MoVeData['x']['t'].append(t)
    self.MoVeData['x']['x'].append(x)
    self.MoVeData['y']['t'].append(t)
    self.MoVeData['y']['y'].append(y)
    self.MoVeData['z']['t'].append(t)
    self.MoVeData['z']['z'].append(z)
    self.MoVeData['acq'].append(0)
    self.MoVeData['geiger'].append(geiger)

    # Update plot
    plot_MoVeData(self)


def plot_MoVeData(self):
    """
    Function to plot the motion verification data
    - planned and executed curve
    - acquisition times
    """

    if hasattr(self, 'vlines1'):
        for vline in self.vlines1:
            vline.remove()

    if hasattr(self, 'vlines2'):
        for vline in self.vlines2:
            vline.remove()

    if hasattr(self, 'axvspans'):
        for span in self.axvspans:
            span.remove()

    if len(self.plot_axes) == 0 or len(self.buffers) == 0:
        return

    self.ax_MoVe    = np.atleast_1d(self.ax_MoVe)
    self.vlines1    = []
    self.vlines2    = []
    self.axvspans   = []

    for i, ax_name in enumerate(self.plot_axes):
        ax = self.ax_MoVe.ravel()[i]

        if ax_name not in self.plot_axes or ax_name not in self.buffers:
            continue
        
        time_buffer = self.buffers[ax_name]['t']
        x_buffer    = self.buffers[ax_name][ax_name]

        if len(time_buffer) == 0:
            continue

        t0, t1 = min(time_buffer), max(time_buffer) 
        t_offset = self.MoVeOffsetSlider.value() * self.UPDATE_INTERVAL

        # Plot measured signal from buffer
        line1 = self.lines[ax_name]['line1'][0]
        line1.set_data(time_buffer, x_buffer)

        # Plot past planned signal from csv data
        df_roi = self.orig_data.loc[(self.orig_data["time"] >= t0 + t_offset) & \
                                    (self.orig_data["time"] <= t1 + t_offset)]
        t_roi = df_roi["time"] - t_offset
        x_roi = df_roi["amplitude"]
        line2 = self.lines[ax_name]['line2'][0]
        line2.set_data(t_roi, x_roi)

        # Plot planned signal ahead of current time
        df_roi = self.orig_data.loc[(self.orig_data["time"] > t1 + t_offset) & \
                                    (self.orig_data["time"] <= t1 + t_offset + 10)]
        t_roi = df_roi["time"] - t_offset
        x_roi = df_roi["amplitude"]
        line3 = self.lines[ax_name]['line3'][0]
        line3.set_data(t_roi, x_roi)
  
        # Plot times and window of acquisition regions-of-interest
        df_roi = self.orig_data.loc[(self.orig_data["time"] >= t0 + t_offset) & \
                                    (self.orig_data["time"] <= t1 + t_offset + 10)] 

        if df_roi["acq"].sum() > 0:
            t_acq = df_roi[df_roi["acq"] == 1]["time"] - t_offset
            self.vlines1.append(ax.vlines(t_acq, 0, 40, color="red"))
            for t in t_acq:
                self.axvspans.append(ax.axvspan(xmin=t, xmax=t + 6, color="lightblue"))

        # Plot times of start of curve
        if df_roi["start"].sum() > 0:
            copy_times = df_roi[df_roi["start"] == 1]["time"] - t_offset
            self.vlines2.append(ax.vlines(copy_times, 0, 40, color="red"))

        ax.set_xlim(min(time_buffer), max(time_buffer) + 10)
        ax.set_ylim(df_roi["amplitude"].min()-2, df_roi["amplitude"].max()+2)

    self.MoVeCanvas.draw()

    # Stop MoVe if end of curve is reached
    if self.orig_data['time'].max() < t1 + t_offset:
        exportMoVeData(self)


# --- STOP MOTION VERIFICATION & EXPORT DATA

def stop_threads(self):
    """
    Stop thread if motion verification is finished
    """

    if hasattr(self, "move_thread") and self.move_thread.isRunning():
        self.move_thread.stop()


def exportMoVeData(self):
    """
    Export the motion verification data to CSV
    The CSV will be stored with the same filename with current time as suffix
    """
    # Retrieve folder and create filename
    csv_root = self.PhOperFolder.text()
    if not os.path.exists(csv_root):
        return

    filename = get_curr_file(self, init=False)
    if filename is None or not hasattr(self, 'MoVeData'):
        return
    
    formatted_time = datetime.now().strftime("%Y%m%d_%H%M%S") 
    filepath = os.path.join(csv_root, filename.replace(".gcode", f"_MoVe_{formatted_time}.csv"))
    
    # Stop motion verification thread
    stop_threads(self)

    # Ensure all keys have same length (thread stopped during append)
    export_data = {}
    for k in self.MoVeData:
        if type(self.MoVeData[k]) == dict:
            for k2 in self.MoVeData[k]:
                export_data[k+k2] = self.MoVeData[k][k2]
        else:
            export_data[k] = self.MoVeData[k]
    max_length = min([len(export_data[k]) for k in export_data])

    for k in export_data:
        export_data[k] = export_data[k][:max_length]

    # Save motion verification to CSV
    df = pd.DataFrame(export_data)
    df.to_csv(filepath, index=False)