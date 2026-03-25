# Import necessary libraries and modules
import numpy as np
import pandas as pd
from PySide6.QtWidgets import QTableWidgetItem, QVBoxLayout
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas


def get_params_from_table(self):
    """
    This function retrieves the cycle parameters 
        provided by the user from the table.
    Output:
      - dictionary with the period and amplitude per cycle
    """

    cycle_params = {}
    cycle_no = 1

    for row in range(self.create_table.rowCount()):
        row_values  = [] # PERIOD, AMPLITUDE
        skip        = False

        for col in range(self.create_table.columnCount()):
            item = self.create_table.item(row, col)

            try:
                row_values.append(float(item.text()))
            except:
                skip = True
                break

        if not skip:
            cycle_params[cycle_no] = row_values
            cycle_no += 1

    return cycle_params


def create_curve(self):
    """
    This function retrieves the cycle parameters from the table
        and creates an analytical curve, based on the curve type and 
        sample frequency provided by the user
    Input
      - cycle parameters from table
      - curve type (from dropdown)
      - sample frequency (from spinbox)

    Output
      - timestamp (self.ts) and amplitude (self.ys)
      - automatic update of plot
        """
    
    # Import cycle parameters from table
    cycle_params = get_params_from_table(self)
    if len(cycle_params) == 0:
        return

    # Retrieve sample frequency and curve type
    sample_frequency    = float(self.create_sample_freq.value())
    time_step           = 1 / sample_frequency
    curve_type          = self.create_curve_type.currentText()

    # Initialize timestamp and amplitude arrays
    ts, ys = np.array([]), np.array([])
    marks = []

    # Iteratively create cycle from template 
    for i in cycle_params:
        period = cycle_params[i][0]
        amplitude = cycle_params[i][1]

        n_steps = int(sample_frequency * period)
        t = np.linspace(0, period - time_step, n_steps)

        if curve_type == 'Cosine^2':
            y = amplitude * np.sin(t * np.pi / period) ** 2
        elif curve_type == 'Cosine^4':
            y = amplitude * np.sin(t * np.pi / period) ** 4
        elif curve_type == 'Cosine^6':
            y = amplitude * np.sin(t * np.pi / period) ** 6
        else:
            print('Curve type not supported')
            return
        
        mark = len(t)*[np.nan]
        mark[len(mark) // 2] = 'Z'
        marks.extend(mark)
        
        # Append cycle to timestamp and amplitude arrays
        if len(ts) == 0:
            ts = np.append(ts, t)
            ys = np.append(ys, y)
        else:
            ts = np.append(ts, t + np.max(ts) + time_step)
            ys = np.append(ys, y)

    # Display the created curve in the plot
    update_plot(self, ts, ys)

    self.curve_origin = 'create'

    # Store generated curve as dataframe
    data = {'timestamp': ts * 1000, 'amplitude': ys, 'mark': marks}
    self.dfEdit = pd.DataFrame(data)


   

def add_row(self):
    """
    This function adds a row to the table by 
    copying the parameters of the last row
    """
    row_count = self.create_table.rowCount()
    col_count = self.create_table.columnCount()

    self.create_table.insertRow(row_count)

    # Copy last row values if one exists
    if row_count > 0:
        for col in range(col_count):
            item = self.create_table.item(row_count - 1, col)
            value = item.text() if item else ""
            self.create_table.setItem(row_count, col, QTableWidgetItem(value))


def remove_row(self):
    """
    This function removes the last row from the table and
    explicitly calls the function to update the creating curve.
    """
    row_count = self.create_table.rowCount()

    if row_count > 0:
        self.create_table.removeRow(row_count - 1)

    create_curve(self)


def update_plot(self, x_data, y_data):
    """This function plots the created curve."""

    # Create a figure for the first time
    self.plot_fig = Figure()  
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
    ax.plot(x_data, y_data)
    ax.set_xlim(np.min(x_data), np.max(x_data))
    ax.set_xlabel('Time (s)', fontsize=self.selected_font_size)
    ax.set_ylabel('Amplitude (mm)', fontsize=self.selected_font_size)

    # Create a canvas and toolbar
    canvas = FigureCanvas(self.plot_fig)
    canvas.setStyleSheet("background-color:Transparent;")

    # Check if the container has a layout, set one if not
    container = self.create_plot_view
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

from .fcn_import import addColumns, loadTable


def createCurve(self):
    self.dfEdit = addColumns(self, self.dfEdit)
    loadTable(self, self.dfEdit, 1)