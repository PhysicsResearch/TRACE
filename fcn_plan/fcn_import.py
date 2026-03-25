import pandas as pd
import numpy as np
from PySide6.QtWidgets import QFileDialog, QTableWidgetItem, QMessageBox

###########################################
##### IMPORT AND PROCESSING FUNCTIONS #####
###########################################

def openCSVFile_BrCv(self):
        """
        Function connected to the IMPORT button
        - previewFile: displays the raw contents of the selected file in TXT format
        - processVXP/CSV: imports the selected file as pandas.DataFrame
        """

        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(self, "Open CSV and VXP File", "", "CSV Files (*.csv *.vxp);;All Files (*)", options=options)
        if fileName:
            previewFile(self, fileName)
            processFile(self, fileName)



def previewFile(self, filePath):
    # Display raw text contents from VXP/CSV
    try:
        with open(filePath, 'r') as file:
            # Read the next 100 lines and add line numbers
            lines = []
            for i in range(1, 101):
                line = file.readline()
                if filePath.endswith('vxp'):
                    if '[Data]' in line:
                        self.import_skip_lines.setValue(i)  # Set the line number containing data
                    if 'Data_layout' in line:
                        self.import_header_line.setValue(i)  # Set the line number containing header
                if not line:
                    break
                lines.append(f"{i}: {line}")
            
            preview = ''.join(lines)
        self.import_text_view.setPlainText(preview)
    except Exception as e:
        self.import_text_view.setPlainText(f'Error reading file: {e}')       



def processFile(self, filePath):
    """
    Function to process the CSV/VXP file selected by the user, with
        user-defined parameters in UI (default for VXP): 
        - seperator
        - skip_lines
        - header_line
        - flip_curve
    """
    
    # Retrieve the user-defined import parameters
    separator   = self.import_delimiter.currentText()
    skip_lines  = int(self.import_skip_lines.value())
    header_line = int(self.import_header_line.value())-1
    scale_factor = 1.0

    try:
        # Determine the header parameter for pandas read_csv 
        if header_line >= 0:
            # Read the header line separately
            with open(filePath, 'r') as file:
                for i, line in enumerate(file):
                    if i == header_line: 
                        if '=' in line: # VXP
                            header_param = line.strip().split('=')[1].split(separator)
                        else: # CSV
                            header_param = line.strip().split(separator)
                    # VXP-specific
                    if "Samples_per_second" in line: 
                        self.import_sampling_rate = float(line.split('=')[1].strip())
                    if "Scale_factor" in line: 
                        scale_factor = float(line.split('=')[1].strip())
                    if i == skip_lines:
                        break
        else:
            header_param = None

        # Load the CSV file into a DataFrame
        dataframe = pd.read_csv(filePath, sep=separator, skiprows=skip_lines, header=None)
        dataframe.columns = header_param

        if 'timestamp' not in dataframe.columns or 'amplitude' not in dataframe.columns:
            QMessageBox.warning(None, "Warning", "The file does not contain columns named\n'timestamp' and/or 'amplitude'.")
            return

        # Ensure 'timestamp' is the first column
        cols = dataframe.columns.tolist()
        cols.insert(0, cols.pop(cols.index('timestamp')))
        dataframe = dataframe[cols]

        # Ensure 'amplitude' is the second column
        cols = dataframe.columns.tolist()
        cols.insert(1, cols.pop(cols.index('amplitude')))
        dataframe = dataframe[cols]

        # Reset start time to zero
        dataframe['timestamp'] -= dataframe['timestamp'].min()

        # Scale and flip amplitude if needed
        dataframe['amplitude'] = dataframe['amplitude'] * scale_factor
        if self.import_flip.isChecked():
            dataframe['amplitude'] = dataframe['amplitude'] * -1

        # VXP-specific preprocessing
        if filePath.endswith('vxp'):
            dataframe = preprocess_vxp(dataframe)

        # Add additional information
        self.curve_origin = 'import'
        dataframe = addColumns(self, dataframe)

        # Display the data in the QTableWidget
        loadTable(self, dataframe, header_line)

    except pd.errors.ParserError as e:
        # Handle the error, by showing a message to the user
        QMessageBox.warning(None, "Warning", f"Error parsing file: \n{e}.")


def preprocess_vxp(dataframe):
    """Function to remove/interpolate invalid data points (zero values)"""

    # Remove empty rows and trailing rows with zero amplitude (end of measurement)
    dataframe = dataframe.dropna(axis=1, how='all')
    dataframe = dataframe[dataframe.loc[::-1, 'amplitude'].ne(0).cummax()]
    # Interpolate zero amplitude (invalid timestamp)
    dataframe.loc[dataframe['amplitude'] == 0, 'amplitude'] = np.nan
    dataframe['amplitude'] = dataframe['amplitude'].interpolate(method='linear', limit_direction='forward')

    return dataframe


def addColumns(self, dataframe):
    """Function to add additional data to the dataframe, such as 
    time (in s), local maxima/minima, velocity/gradients"""

    # Add column with time in seconds
    dataframe["time"] = pd.to_timedelta(dataframe["timestamp"], unit=self.import_time_unit.currentText())
    dataframe["time"] = dataframe["time"].dt.total_seconds()
    time_step = dataframe.loc[1, "time"] - dataframe.loc[0, "time"]

    # Add local maxima and minima
    if 'mark' in dataframe.columns:
        
        # Not yet processed (VXP import)
        if 'P_min' not in dataframe['mark'].unique():
            df_copy = dataframe.copy()
            dataframe['mark'] = ''

            # Retrieve indices with peaks (mark = Z) and find closest peak
            idxs = df_copy[df_copy["mark"] == "Z"].index
            for idx in idxs:
                start = max(0, idx - 15)
                end = min(len(dataframe) - 1, idx + 15)
                peak_idx = df_copy.loc[start:end, 'amplitude'].idxmax()
                dataframe.at[peak_idx, 'mark'] = 'P_max'

            # Retrieve updated peak indices and add minimum and end timestamp
            idxs = dataframe[dataframe["mark"] == "P_max"].index
            for i in range(len(idxs)-1):
                min_idx = dataframe.loc[idxs[i]:idxs[i+1], "amplitude"].idxmin()
                dataframe.loc[min_idx, "mark"] = "P_min"
                dataframe.loc[idxs[i+1]-1, "mark"] = "E"

        # Add cycle ids (used for clipping)
        if 'instance' not in dataframe:
            dataframe["instance"] = np.nan
            idxs = dataframe[dataframe["mark"] == "P_max"].index
            for i in range(len(idxs)-1):
                start   = idxs[i]
                end     = idxs[i+1]
                dataframe.loc[start:end-1, "instance"] = i+1

    if "instance" in dataframe.columns and 'cycle time' not in dataframe.columns:
        dataframe["cycle time"] = np.nan

        # Iteratively add time step to cycle time
        idxs = dataframe[dataframe["mark"] == "P_max"].index
        for i in range(len(idxs)-1):
            counter = 0
            start   = idxs[i]
            end     = idxs[i+1]
            for j in range(start, end):
                dataframe.loc[j, "cycle time"] = counter
                counter += time_step

    # Calculate speed and acceleration
    if 'velocity' not in dataframe.columns or 'speed' not in dataframe.columns \
    or 'accel' not in dataframe.columns:
        dataframe = calcGrad(self, dataframe)

    return dataframe


def loadTable(self, dataframe, header_line):
    """Function to populate the table view widget"""
    # Clear the table before populating it
    if self.curve_origin == 'create':
        table = self.create_table_view
    elif self.curve_origin == 'import':
        table = self.import_table_view
    
    table.clear()
    table.setRowCount(dataframe.shape[0])
    table.setColumnCount(dataframe.shape[1])

    # Set table headers
    if header_line >= 0:
        table.setHorizontalHeaderLabels(dataframe.columns)
    else:
        table.setHorizontalHeaderLabels([f'C{i+1}' for i in range(dataframe.shape[1])])

    # Populate the table with data
    for row in range(dataframe.shape[0]):
        for col in range(dataframe.shape[1]):
            table.setItem(row, col, QTableWidgetItem(str(dataframe.iat[row, col])))

    # Clear and re-initialize variables       
    if hasattr(self, "dfEdit"):
        delattr(self, "dfEdit")

    if hasattr(self, 'freq_scaled'):
        delattr(self, 'freq_scaled')

    if hasattr(self, 'lower_bound'):
        del self.lower_bound
    if hasattr(self, 'upper_bound'):
        del self.upper_bound
        
    self.Tab_index = 1


def calcGrad(self, df):
    """Calculate the velocity, speed and acceleration based on the time and amplitude columns.
    Not used yet, but can be used to flag speed exceeding phantom capabilities."""

    col = "amplitude"
    # Calculate average speed
    vel = df[col].diff().shift(-1) / df["time"].diff().shift(-1)
    vel.iloc[-1] = vel.iloc[-2]  # Copy the second last value to the last element
    df['velocity'] = vel

    speed = abs(vel) * 60  # Convert m/s to mm/min
    df['speed'] = speed

    # Calculate acceleration
    accel = vel.diff(-1) / df["time"].diff(-1)
    accel.iloc[-1] = accel.iloc[-2]  # Copy the second last value to the last element
    df['accel'] = accel

    return df
