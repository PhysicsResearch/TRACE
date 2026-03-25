import math
import numpy as np
import pandas as pd
from scipy.signal import detrend
from scipy.ndimage import uniform_filter1d, median_filter
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PySide6.QtWidgets import QVBoxLayout, QMessageBox
from .fcn_import import calcGrad


def undoOperation(self):
    """Function to undo the last operations applied to the fragment
        Input: 
            - dfEdit_BrCv_copy: latest copy of the fragment [pandas.dataframe]
        Output:
            - pandas.DataFrame of fragment with operations undone [pandas.dataframe]
    """
    self.dfEdit = self.dfEdit_copy.copy() # Create copy for undo
    initXRange(self)
    plotViewData_edit(self)


# --- RANGE OPERATIONS

def initXRange(self):
    """Function to initialize the x-range sliders to 
        minimum and maximum time in the dataframe"""
    
    # Get minimum and maximum time
    min_val = math.floor(self.dfEdit['time'].min())
    max_val = math.ceil(self.dfEdit['time'].max())

    # Set x-min slider
    self.slider_edit_xmin.setMinimum(min_val)
    self.slider_edit_xmin.setMaximum(max_val - 1)
    self.slider_edit_xmin.setValue(min_val)
    
    # Set x-max slider
    self.slider_edit_xmax.setMinimum(min_val + 1)
    self.slider_edit_xmax.setMaximum(max_val)
    self.slider_edit_xmax.setValue(max_val)


def cropRange(self):
    """Function to update the dataframe to the x-range set
        using the sliders. If 'Instance' information is available
        then the curve is clipped to whole cycles as well."""

    self.dfEdit_copy = self.dfEdit.copy() # Set copy for undo
    
    # Clip dataframe to x-range set by sliders
    df = self.dfEdit
    df = df[(df['time'] >= self.slider_edit_xmin.value()) & \
            (df['time'] <= self.slider_edit_xmax.value())]
    df = df.reset_index(drop=True)
    
    if "instance" in df:
        # Get min and max index of valid cycles & clip 
        min_idx = df[df['mark'] == 'P_max'].index[0] 
        max_idx = df[df['mark'] == 'E'].index[-1] + 1
        df = df.iloc[min_idx:max_idx] 
        df = df.reset_index(drop=True)
    else:
        QMessageBox.warning(None, "Warning", f'Could not clip to whole cycles as no cycle \ninformation is available ("Instance" column)')
    
    # Reset time and instance columns
    df.loc[:, "timestamp"] -= df["timestamp"].min()
    df.loc[:, "time"] -= df["time"].min()
    df.loc[:, "instance"] -= df["instance"].min()
    self.dfEdit = df

    # Update sliders and plot
    initXRange(self)
    plotViewData_edit(self, self.dfEdit)


# --- AMPLITUDE OPERATIONS ---

def scaleAmpl(self):
    """Function to scale amplitude of the fragment
        Input:
            - df: fragment to scale [pandas.dataframe]
            - scaleAmpl_BrCv: factor to scale amplitude [float],
        Output:
            - pandas.DataFrame with scaled amplitude
    """
    # Create copy for undo
    self.dfEdit_copy = self.dfEdit.copy() 

    # Apply scaling factor to amplitude
    scale_factor = self.value_ampl_sf.value() 
    self.dfEdit["amplitude"] *= scale_factor 

    # Update speed
    self.dfEdit = calcGrad(self, self.dfEdit)

    # Update plot
    plotViewData_edit(self) 
    
    
def shiftAmpl(self):
    """Function to shift amplitude of the fragment
        Input:
            - df: fragment to shift [pandas.dataframe]
            - shiftAmpl_BrCv: value to shift amplitude [float],
        Output:
            - pandas.DataFrame with shifted amplitude
    """
    # Create copy for undo
    self.dfEdit_copy = self.dfEdit.copy() 

    # Apply shift to amplitude
    self.dfEdit["amplitude"] += self.value_ampl_shift.value()

    # Update plot
    plotViewData_edit(self) 


def zeroAmpl(self):
    """Function to set the minimum amplitude in the
        dataframe to zero
    """
    # Create copy for undo
    self.dfEdit_copy = self.dfEdit.copy() 

    # Shift the amplitude by the minimum value
    self.dfEdit["amplitude"] -= self.dfEdit["amplitude"].min()

    # Update plot
    plotViewData_edit(self) 


def clipAmpl(self):
    """Function to clip maximum amplitude of the fragment
        Input:
            - df: fragment to clip maximum amplitude [pandas.dataframe]
            - maxAmplThresh_BrCv: value to clip amplitude [float],
        Output:
            - pandas.DataFrame with clipped amplitude
    """
    # Create copy for undo
    self.dfEdit_copy = self.dfEdit.copy() 
    
    # Clip maximum and minimum
    t = self.value_ampl_max.value() 
    self.dfEdit.loc[self.dfEdit["amplitude"] > t, "amplitude"] = t

    t = self.value_ampl_min.value() 
    self.dfEdit.loc[self.dfEdit["amplitude"] < t, "amplitude"] = t

    # Update speed
    self.dfEdit = calcGrad(self, self.dfEdit)
    
    # Update plot
    plotViewData_edit(self) 


def insertBreathhold(self, x):
    """Function to insert breathhold in the fragment
        Input:
            - df: fragment to insert breathhold [pandas.dataframe]
            - breathholdStart: timestamp at which to insert breathhold [float],
            - breathholdDuration: duration of breathhold [float],
        Output:
            - pandas.DataFrame with shifted amplitude
    """
    
    df = self.dfEdit
    # Get the breathhold duration value
    duration = self.breathholdDuration.value()
    if duration == 0:
        return

    timestep_ms = df.loc[1, "timestamp"] - df.loc[0, "timestamp"]
    timestep    = df.loc[1, "time"] - df.loc[0, "time"]
    i_start     = int(x / timestep)
    idx         = i_start

    if self.closest_max.isChecked():
        idx = df.loc[i_start-20:i_start+20, 'amplitude'].idxmax()
    elif self.closest_min.isChecked():
        idx = df.loc[i_start-20:i_start+20, 'amplitude'].idxmin()

    n_time = int(duration / timestep) 
        
    # Copy the row at breathhold index and repeat it n_time times
    b = pd.concat([df.iloc[idx:idx+1]] * n_time)
    b = b.reset_index(drop=True)

    for n in range(n_time):
        b.loc[n, "timestamp"]   += n * timestep_ms
        b.loc[n, "time"]        += n * timestep
    
    df.loc[idx:, "timestamp"]   += (n + 1) * timestep_ms
    df.loc[idx:, "time"]        += (n + 1) * timestep
    
    # Insert the copied rows into the original DataFrame
    df = pd.concat([df.iloc[:idx], b, df.iloc[idx:]]).reset_index(drop=True)
    self.dfEdit_BrCv = df

    initXRange(self)


# --- BASELINE DRIFT OPERATIONS ---

def removeDrift(self):
    """Function to remove baseline drift from curve.
        The scipy.signal.detrend function is used to remove linear bias.
    """
    
    # Set copy for undo
    self.dfEdit_copy = self.dfEdit.copy()
    min_ = self.dfEdit['amplitude'].min()

    # Remove linear drift from amplitude signal
    self.dfEdit['amplitude'] = detrend(self.dfEdit['amplitude'])

    # Ensure minimum amplitude is equal to initial value
    self.dfEdit['amplitude'] = self.dfEdit['amplitude'] - self.dfEdit['amplitude'].min() + min_

    # Update speed
    self.dfEdit = calcGrad(self, self.dfEdit)

    # Update plot
    plotViewData_edit(self)


def addDrift(self):
    """Function to add baseline drift to curve.
        A linear curve is added, with the slope defined by the  user.
    """
    # Set copy for undo
    self.dfEdit_copy = self.dfEdit.copy()
    min_ = self.dfEdit['amplitude'].min()

    # Add linear curve to amplitude
    slope = self.value_drift.value()
    t0 = self.dfEdit['time'].min()
    self.dfEdit['amplitude'] += (self.dfEdit['time'] - t0) * slope

    # Ensure the minimum value in the curve stays the same
    self.dfEdit['amplitude'] = self.dfEdit['amplitude'] - self.dfEdit['amplitude'].min() + min_

    # Update speed
    self.dfEdit = calcGrad(self, self.dfEdit)

    # Update plot
    plotViewData_edit(self)


# --- FREQUENCY OPERATIONS ---

def scaleFreq(self):
    # Set copy for undo
    self.dfEdit_copy = self.dfEdit.copy()

    for col in ['timestamp', 'time', 'cycle time']:
        if col in self.dfEdit.columns:
            self.dfEdit[col] /= self.value_freq_sf.value()

    self.freq_scaled = True

    # Update sliders and plot
    initXRange(self)
    plotViewData_edit(self)


# --- SMOOTHING ---

def smoothAmpl(self):
    # Set copy for undo
    self.dfEdit_copy = self.dfEdit.copy()

    if self.smooth_method.currentText() == "Fourier":
        threshold = self.fourier_cutoffs[self.threshFourierSlider.value()]
        fourier = np.fft.rfft(self.dfEdit["amplitude"])
        frequencies = np.fft.rfftfreq(self.dfEdit["amplitude"].size, d=self.dfEdit["timestamp"].diff().iloc[1])
        fourier[frequencies > threshold] = 0
        smooth_signal = np.fft.irfft(fourier, n=self.dfEdit["amplitude"].size)
        self.dfEdit["amplitude"] = smooth_signal
        
    if self.smooth_method.currentText() == "Uniform":
        self.dfEdit["amplitude"] = uniform_filter1d(self.dfEdit["amplitude"], size=self.smooth_kernel.value())

    elif self.smooth_method.currentText() == "Median":
        self.dfEdit["amplitude"] = median_filter(self.dfEdit["amplitude"], size=self.smooth_kernel.value())

    # Update speed
    self.dfEdit = calcGrad(self, self.dfEdit)
    
    # Update plot
    plotViewData_edit(self)


# --- INITIALIZATION ---

def getColumnIndexByName(self, column_name):
    """Get index of column in tableWidget by name"""
    if self.curve_origin == 'create':
        table = self.create_table_view
    elif self.curve_origin == 'import':
        table = self.import_table_view
    
    for i in range(table.columnCount()):
        if table.horizontalHeaderItem(i).text() == column_name:
            return i
    return None


def on_fourierSlider_change(self):
    cutoff = self.fourier_cutoffs[self.threshFourierSlider.value()]
    self.threshFourierValue.setText(f"{cutoff:.2e} Hz")


def getDataframeFromTable(self):
    """Extract data from tableWidget and convert to pandas.DataFrame"""

    if self.curve_origin == 'create':
        table = self.create_table_view
    elif self.curve_origin == 'import':
        table = self.import_table_view
        
    # Extract data from the table widget
    data = {}
    for col in range(table.columnCount()):
        column_name = table.horizontalHeaderItem(col).text()
        data[column_name] = []
        for row in range(0, table.rowCount()):
            item = table.item(row, col)
            if item:
                try:
                    data[column_name].append(float(item.text()))
                except:
                    data[column_name].append(item.text())

    self.dfEdit = pd.DataFrame(data)
    self.dfEdit_copy = self.dfEdit.copy()
    
    
def init_edit(self):
    if self.tabWidget_BrCv.currentIndex() == 2 and self.Tab_index == 1:
        self.Tab_index = 2
        on_fourierSlider_change(self)
        self.threshFourierSlider.valueChanged.connect(lambda:on_fourierSlider_change(self))
        getDataframeFromTable(self)
        initXRange(self)
        plotViewData_edit(self)   

    
# --- PLOTTING FUNCTIONS ---

def onclick(self, event):
    """Function to handle mouse click events on the plot
    Used to set/delete acquisition timestamps for triggered imaging."""
    if event.button == 1:  # Left click
        # Retrieve the x-position of click and set acquisition to closest timestamp 
        if "acq" not in self.dfEdit.columns:
            self.dfEdit["acq"] = np.nan
        x = event.xdata
        self.dfEdit.loc[(self.dfEdit['time'] - x).abs().idxmin(), "acq"] = 1
    elif event.button == 2:
        x = event.xdata
        insertBreathhold(self, x)
    elif event.button == 3:  # Right click
        # Retrieve the x-position of click and delete acquisition closest to timestamp
        x = event.xdata
        if "acq" in self.dfEdit.columns and self.dfEdit["acq"].sum() > 0:
            delete_idx = (self.dfEdit.loc[self.dfEdit["acq"] == 1, 'time'] - x).abs().idxmin()
            self.dfEdit.loc[delete_idx, "acq"] = np.nan
    # Update plot
    plotViewData_edit(self)


def plotViewData_edit(self, df=None):
    """Function to plot the edited breathing curve real-time."""
    x_col = "time"
    y_col = "amplitude"
    
    self.lower_bound = self.slider_edit_xmin.value()
    self.upper_bound = self.slider_edit_xmax.value()
    
    if self.lower_bound >= self.upper_bound:
        initXRange(self)
        plotViewData_edit(self)
        
    if df is None and hasattr(self, 'dfEdit'):
        df = self.dfEdit
    else:
        return
    
    df_window = df[(df[x_col] >= self.lower_bound) & (df[x_col] <= self.upper_bound)]

    x_data = df_window[x_col]
    y_data = df_window[y_col]

    self.plot_fig = Figure()  # Create a figure for the first time
    ax = self.plot_fig.add_subplot(111) 
    
    # Set plot background to transparent
    ax.patch.set_alpha(0.0)
    self.plot_fig.patch.set_alpha(0.0)
    
    # Customize text and axes properties
    ax.tick_params(colors='white', labelsize=self.selected_font_size-2)  # White ticks with larger text
    ax.xaxis.label.set_color('white'); ax.yaxis.label.set_color('white')
    ax.spines['bottom'].set_color('white'); ax.spines['top'].set_color('white')
    ax.spines['left'].set_color('white'); ax.spines['right'].set_color('white')

    # Plot the data
    ax.set_xlim(np.min(x_data), np.max(x_data))
    ax.plot(x_data, y_data, label=f'{x_col} vs {y_col}')
    # Plot acquisition timestamps within window
    if "acq" in df_window and df_window["acq"].sum() > 0:
        x_acq = df_window[self.dfEdit["acq"] == 1][x_col]
        for x in x_acq:
            ax.axvline(x, color='red', label="Acquisition Timestamps")
            # Plot the 6-second HS-CBCT acquisition window
            ax.fill_between(x=[x, x + 6], y1=np.min(y_data), y2=np.max(y_data), facecolor="pink", alpha=0.5)

    ax.set_xlabel(x_col, fontsize=self.selected_font_size)
    ax.set_ylabel(y_col, fontsize=self.selected_font_size)

    # Create a canvas and toolbar
    canvas = FigureCanvas(self.plot_fig)
    canvas.setStyleSheet("background-color:Transparent;")
    canvas.mpl_connect('button_press_event', lambda event: onclick(self, event))

    # Check if the container has a layout, set one if not
    container = self.edit_ax_view
    if container.layout() is None:
        layout = QVBoxLayout(container)
        container.setLayout(layout)
    else:
        # Clear existing content in the container, if any
        while container.layout().count():
            child = container.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    # Add the canvas and toolbar to the container
    container.layout().addWidget(canvas)
    canvas.draw()
    