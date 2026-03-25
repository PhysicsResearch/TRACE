import os
import pandas as pd
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PySide6.QtWidgets import QVBoxLayout, QTableWidgetItem, QFileDialog, QMessageBox
from .fcn_edit import getDataframeFromTable, undoOperation


# --- EXPORT ---

def copyCurve(self):
    """Function to copy fragment N times
        Input: 
            - df: fragment to copy [pandas.dataframe]
            - N: number of times to copy [int],
        Output:
            - pandas.DataFrame with N copies of df
    """
    
    df          = self.dfEdit
    N           = self.n_copy_curve.value()
    timestep    = df.iloc[1]["timestamp"] - df.iloc[0]["timestamp"]
    
    if "instance" in df.columns and N > 1 and self.curve_origin == "import":
        # If instance information available, scale last cycle from minimum
        # until the end to ensure that the beginning and end of fragment match
        min1        = df[df["instance"] == df["instance"].max()]["amplitude"].min()
        min1_idx    = df[df["instance"] == df["instance"].max()]["amplitude"].idxmin()
        max1        = df.iloc[-1]["amplitude"]
        max2        = df.iloc[0]["amplitude"]
    
        scale       = (max2 - min1) / (max1 - min1)
        shift       = max2 - max1 * (max2 - min1) / (max1 - min1)
        df.loc[min1_idx:, "amplitude"] = df.loc[min1_idx:, "amplitude"] * scale + shift
    
    df["start"] = 0
    df.loc[0, "start"] = 1

    df_mult = df.copy()

    for i in range(N - 1):
        # Copy fragment N times
        df_copy             = df.copy()
        df_copy["timestamp"]+= df_mult["timestamp"].max() + timestep
        df_copy["time"]     += df_mult["time"].max() + timestep * 1e-3

        if "instance" in df.columns:
            df_copy["instance"] += df_mult["instance"].max()

        df_mult = pd.concat([df_mult, df_copy]).reset_index(drop=True)

    self.dfEdit = df_mult


def exportData(self):
    """Function to export all the columns of the edited fragment to a CSV file
        Input:
            - df: fragment to apply operations [pandas.dataframe]
            - breathholdStart: timestamp at which to insert breathhold [float],
            - breathholdDuration: duration of breathhold [float],
        Output:
            - pandas.DataFrame with shifted amplitude
    """

    if not hasattr(self, 'curve_origin'):
        return
    
    if not hasattr(self, "dfEdit"):
        getDataframeFromTable(self)
        
    self.dfEdit_copy = self.dfEdit.copy()
    # Copy the fragment N times
    copyCurve(self)

    # Prompt user to select a folder
    options = QFileDialog.Options()
    folder = QFileDialog.getExistingDirectory(self, options=options)

    # Save the DataFrame to a CSV file in the selected folder
    fileName = os.path.join(folder, self.export_filename.text()+"_metadata.csv")
    try:
        self.dfEdit.to_csv(fileName)
    except:
        QMessageBox.warning(None, "Warning", "Data could not be stored.\nMaybe the file is still open?")
        return
    
    # Reset the dataframe to one copy
    undoOperation(self)


def exportGCODE(self):
    if not hasattr(self, 'curve_origin'):
        return
    
    # Prompt user to select a folder
    self.dfEdit_copy = self.dfEdit.copy()
    folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
    if not folder_path:
        return  # User canceled, exit the function

    # Get the file name 
    file_name = self.export_filename.text()
    file_path = os.path.join(folder_path, file_name + ".csv")
    
    # If not edited
    if not hasattr(self, "dfEdit"):
        getDataframeFromTable(self)

        if 'time' not in self.dfEdit:
            self.dfEdit['time'] = self.dfEdit['timestamp'] * 1e-3

    # Copy the fragment N times and extract timestamp and amplitude data
    copyCurve(self)

    df = self.dfEdit[["timestamp", "amplitude", "time"]]

    # Convert the time column to TimedeltaIndex for resampling
    time_col = "timestamp"
    df[time_col] = pd.to_timedelta(df[time_col], unit='ms')
    
    if self.interp_export.isChecked():
        # Create a new index for resampling at 0.1s intervals
        freq = int(self.interp_export_value.value())
        new_index = pd.timedelta_range(start=df[time_col].min(), end=df[time_col].max(), freq=f'{freq}ms')

        # Reindex the DataFrame to the new index, keeping original data points
        df = df.set_index(time_col).reindex(new_index.union(df[time_col])).sort_index()
        
        # Interpolate only the missing values
        df = df.interpolate(method='linear', limit_area='inside')
        
        # Ensure the original time points are not modified
        if getattr(self, 'sampling_rate', None) is not None:
            if (((1 / self.sampling_rate) * 1e3) % freq) == 0:
                df.loc[df.index.isin(new_index) == False, :] = df.loc[df.index.isin(new_index) == False, :].fillna(method='ffill').fillna(method='bfill')
            else:
                df = df.loc[df.index.isin(new_index), :]
        if hasattr(self, 'freq_scaled'):
            df = df.loc[df.index.isin(new_index), :]

        df.reset_index(inplace=True)

    df.rename(columns={'index': time_col}, inplace=True)

    # Calculate velocity and acceleration for each column
    results             = pd.DataFrame()
    results['time']   = df[time_col].dt.total_seconds()

    # Add random fluctuation to avoid zero values being skipped
    col = 'amplitude'
    df["diff"] = df[col].diff().shift(-1)
    for i in range(len(df[col]) - 1):
        if df.loc[i, "diff"] < 1e-3:
            df.loc[i, col] += np.random.choice([-1, 1], 1) * np.random.choice(list(range(1, 1000)), 1) * 1e-5

    df.loc[df[col] < 0, col] = 0
    results[col] = df[col]

    # Calculate velocity, speed and acceleration
    vel             = df[col].diff().shift(-1) / df[time_col].diff().shift(-1).dt.total_seconds()
    vel.iloc[-1]    = vel.iloc[-2]  # Copy the second last value to the last element
    speed           = abs(vel) * 60 # in mm/min
    accel           = vel.diff() / df[time_col].diff().dt.total_seconds() 
    accel.iloc[-1]  = accel.iloc[-2]  # Copy the second last value to the last element

    results[f'{col}_vel']   = vel
    results[f'{col}_speed'] = speed 
    results[f'{col}_accel'] = accel

    # Add acquisition and start times closest to interpolated timepoints
    if "acq" in self.dfEdit and self.dfEdit["acq"].sum() > 0:
        times = self.dfEdit.loc[self.dfEdit["acq"] == 1, "time"]
        for t in times:
            closest_t = (df[time_col].dt.total_seconds() - t).abs().idxmin()
            df.loc[closest_t, "acq"] = 1 
    else:
        df["acq"] = np.nan

    times = self.dfEdit.loc[self.dfEdit["start"] == 1, "time"]
    for t in times:
        closest_t = (df[time_col].dt.total_seconds() - t).abs().idxmin()
        df.loc[closest_t, "start"] = 1 

    results["acq"]      = df["acq"] 
    results["start"]    = df["start"]

    try: # save results to csv
        results.to_csv(file_path, index=False, mode='w')
    except:
        QMessageBox.warning(None, "Warning", "Real-time verification data could not be stored.\nMaybe the file is still open?")
        return

    # Set recalculated velocity and speed after resampling
    df[f'{col}_vel'] = vel
    df[f'{col}_speed'] = speed
    
    # Remove timepoints with low speed, might smoothen phantom execution
    if self.compress_speed.value() > 0:
        df['keep'] = False

        # Always keep the first and last points
        df.loc[df.index[0], 'keep'] = True
        df.loc[df.index[-1], 'keep'] = True

        # Mark points with velocity above threshold
        df.loc[df[f'{col}_speed'].abs() > self.compress_speed.value(), 'keep'] = True

        # Also keep local extrema (changes in velocity sign)
        vel_sign = np.sign(vel)
        extrema = vel_sign.diff().fillna(0).ne(0)
        df.loc[extrema, 'keep'] = True

        # Filter to only the important points
        df = df[df['keep']].copy()
        df.drop(columns='keep', inplace=True)

        # Calculate velocity, speed
        vel = df[col].diff().shift(-1) / df[time_col].diff().shift(-1).dt.total_seconds()
        vel.iloc[-1] = vel.iloc[-2]  # Copy the second last value to the last element
        speed = abs(vel) * 60

        df[f'{col}_vel'] = vel
        df[f'{col}_speed'] = speed

    # Create G-code lines and write to file
    gcode_lines = ["G90"]  # Initialize G-code lines with absolute positioning command
    axis_labels         = ['X', 'Y', 'Z']  # Define axis labels
    max_min = df[df.columns[1]].max() + df[df.columns[1]].min()
    
    for i, row in df.iterrows():
        if i == 0:
            speed = 1000  # Set default speed for fast initialization
        else:
            speed = row['amplitude_speed'] * np.sqrt(len(axis_labels)) # speed in mm/min
        
        gcode_line = f"G0 F{speed:.6f}" # Prepare G-code line
        for j, col in enumerate(axis_labels):
            if col == 'Z':
                Z = row['amplitude']
                gcode_line += f" {axis_labels[j]}{Z:.6f}"  
            else:
                X = -row['amplitude'] + max_min # Invert input for X, Y (compression)
                gcode_line += f" {axis_labels[j]}{X:.6f}"  
        gcode_lines.append(gcode_line)

    with open(file_path.replace('csv', 'gcode'), 'w') as gcode_file:
        gcode_file.write('\n'.join(gcode_lines))

    # Set the DataFrame back to non-interpolated state
    undoOperation(self)


# --- STATISTICS ---

def calcStats(self):
    if not hasattr(self, 'dfEdit'):
        return
    
    if hasattr(self, 'peak_data'):
        delattr(self, 'peak_data')
    
    df = self.dfEdit

    cols = ["timestamp", "amplitude", "instance", "speed", "time"]
    df = df[cols]
    if 'mark' in self.dfEdit:
        self.peak_data = self.dfEdit[self.dfEdit['mark'] == 'P_max']
        self.valley_data = self.dfEdit[self.dfEdit['mark'] == 'P_min']

    for var in ["amplitude", "time", "speed"]:
        if var not in df.columns:
            continue
        stats = {}

        if hasattr(self, 'peak_data'):
            if var == 'amplitude':
                amplitudes = []
                for i in self.peak_data['instance'].unique():
                    if i in self.valley_data['instance'].unique():
                        high = float(self.peak_data[self.peak_data['instance']==i][var].values)
                        low  = float(self.valley_data[self.valley_data['instance']==i][var].values)
                        amplitudes.append(float(high - low))
                data = pd.DataFrame(amplitudes, columns=['amplitude'])
            elif var == 'speed':
                data = self.dfEdit[var].dropna()
            elif var == 'time':
                data = self.peak_data[var].diff().dropna()

            stats["min"]    = float(data.min(skipna=True))
            stats["max"]    = float(data.max(skipna=True))
            stats["mean"]   = float(data.mean(skipna=True))
            stats["median"] = float(data.median(skipna=True))
            stats["std"]    = float(data.std(skipna=True))
            q1              = np.nanpercentile(data, 25)
            q3              = np.nanpercentile(data, 75)
            stats["iqr"]    = float(q3 - q1)

        elif "instance" not in df.columns and var in ["amplitude", "speed"]:
            stats["max"] = df[var].max()

        if var == "amplitude":
            self.ampl_stats.clear()
            self.ampl_stats.setColumnCount(1)
            self.ampl_stats.setHorizontalHeaderLabels(['amplitude'])
            self.ampl_stats.setRowCount(len(stats))
            self.ampl_stats.setVerticalHeaderLabels(list(stats.keys()))
            for i, metric in enumerate(stats):
                self.ampl_stats.setItem(i, 0, QTableWidgetItem("{:.4f}".format(stats[metric])))

        elif var == "time":
            self.cycle_stats.clear()
            self.cycle_stats.setColumnCount(1)
            self.cycle_stats.setHorizontalHeaderLabels(['cycle time'])
            self.cycle_stats.setRowCount(len(stats))
            self.cycle_stats.setVerticalHeaderLabels(list(stats.keys()))

            for i, metric in enumerate(stats):
                self.cycle_stats.setItem(i, 0, QTableWidgetItem("{:.4f}".format(stats[metric])))

        elif var == "speed":
            self.speed_stats.clear()
            self.speed_stats.setColumnCount(1)
            self.speed_stats.setHorizontalHeaderLabels(['speed'])
            self.speed_stats.setRowCount(len(stats))
            self.speed_stats.setVerticalHeaderLabels(list(stats.keys()))

            for i, metric in enumerate(stats):
                self.speed_stats.setItem(i, 0, QTableWidgetItem("{:.4f}".format(stats[metric])))


# --- PLOTTING

def init_export_plot(self):

    if not hasattr(self, 'curve_origin'):
        return
    
    if not hasattr(self, "dfEdit"):
        getDataframeFromTable(self)

    self.plot_xaxis.setCurrentText("time")
    plotViewData(self)   

           

def plotViewData(self):
    x_col = self.plot_xaxis.currentText()
    y_col = 'amplitude'

    if not hasattr(self, 'dfEdit') or not x_col in self.dfEdit.columns:
        return
    
    if self.curve_origin == 'create':
        table = self.create_table_view
    elif self.curve_origin == 'import':
        table = self.import_table_view

    i_index = None
    for col in range(table.columnCount()):
        if table.horizontalHeaderItem(col).text() == "instance":
            i_index = col

    df = self.dfEdit
    
    if x_col in ["timestamp", "time", "velocity"]:
        x_data = df[x_col]
        y_data = df[y_col]
    elif x_col in ["phase", "cycle time"] and i_index is not None:
        df_filtered = df.dropna(subset=['instance'])
        grouped     = df_filtered.groupby('instance')
        x_data      = grouped[x_col].apply(list).tolist()
        y_data      = grouped[y_col].apply(list).tolist()    
    else:
        return

    self.plot_fig = Figure()  # Create a figure for the first time
    ax = self.plot_fig.add_subplot(111) 
    
    if self.selected_background == "Transparent":
        # Set plot background to transparent
        ax.patch.set_alpha(0.0)
        self.plot_fig.patch.set_alpha(0.0)
        
        # Customize text and axes properties
        ax.tick_params(colors='white', labelsize=self.selected_font_size-2)  # White ticks with larger text
        ax.xaxis.label.set_color('white')
        ax.yaxis.label.set_color('white')
        ax.spines['bottom'].set_color('white')
        ax.spines['top'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['right'].set_color('white')
    else:
        ax.tick_params(labelsize=self.selected_font_size-2)  # White ticks with larger text

    # Plot the data
    if x_col in ["timestamp", "time", "velocity"] and y_col == "amplitude":
        ax.set_xlim(np.min(x_data), np.max(x_data))
        ax.plot(x_data, y_data, label=f'{x_col} vs {y_col}')

    elif x_col in ["phase", "cycle time"] and y_col == "amplitude" and i_index is not None:
        ax.set_xlim(np.min([x for xs in x_data for x in xs]),
                    np.max([x for xs in x_data for x in xs]))
        for x, y in zip(x_data, y_data):
            ax.plot(x, y)

    if 'mark' in self.dfEdit.columns and self.plot_xaxis.currentText() in ['timestamp', 'time'] \
        and self.plot_peaks.isChecked():
        time_col = self.plot_xaxis.currentText()
        z_marks = self.dfEdit.loc[self.dfEdit['mark'] == 'P_max']
        ax.scatter(z_marks[time_col], z_marks['amplitude'],
                color='#bc80bd', marker='*', s=25, label='Peak')
        ax.vlines(z_marks[time_col], ymin=0, ymax=z_marks['amplitude'],
                colors='#bc80bd', linewidth=1.5)
        
    if self.plot_xaxis.currentText() in ['timestamp', 'time'] and self.plot_acq.isChecked():
        time_col = self.plot_xaxis.currentText()
        acq_marks = self.dfEdit.loc[self.dfEdit['acq'] == 1]
        ax.vlines(acq_marks[time_col], ymin=0, ymax=acq_marks['amplitude'],
                colors='red', linewidth=1.5)                

    # Set x_col as xlabel
    if x_col == 'time':
        ax.set_xlabel('Time (s)', fontsize=self.selected_font_size)
    elif x_col == 'timestamp':
        ax.set_xlabel('Time (ms)', fontsize=self.selected_font_size)
    else:
        ax.set_xlabel(x_col, fontsize=self.selected_font_size)

    # Set y_col as ylabel
    if y_col == 'amplitude':
        ax.set_ylabel('Amplitude (mm)', fontsize=self.selected_font_size)
    else:
        ax.set_ylabel(y_col, fontsize=self.selected_font_size)
        
    # if self.selected_background == "Transparent":
    #     self.plot_fig.suptitle(self.plotTitle_BrCv.text(), 
    #                            fontsize=self.selected_font_size + 4,
    #                            color="white")
    # else:
    #     self.plot_fig.suptitle(self.plotTitle_BrCv.text(), 
    #                            fontsize=self.selected_font_size + 4)
    
    if self.selected_legend_on_off == "On":
        if self.selected_background == "Transparent":
            ax.legend(edgecolor='white')
        else:
            ax.legend()
        

    # Create a canvas and toolbar
    canvas = FigureCanvas(self.plot_fig)
    canvas.setStyleSheet(f"background-color:{self.selected_background};")
    toolbar = NavigationToolbar(canvas, self)

    # Check if the container has a layout, set one if not
    container = self.plot_view
    if container.layout() is None:
        layout = QVBoxLayout(container)
        container.setLayout(layout)
    else:
        # Clear existing content in the container, if any
        while container.layout().count():
            child = container.layout().takeAt(0)
            if child.widget() and not isinstance(child.widget(), NavigationToolbar):
                child.widget().deleteLater()

    # Add the canvas and toolbar to the container
    container.layout().addWidget(toolbar)
    container.layout().addWidget(canvas)
    canvas.draw()