from PySide6.QtWidgets import QTableWidgetItem, QHeaderView

def initialize_software_tables(self):
    """
    This function initializes the tables in the software
      - Table to create analytical curves
    """

    headers = ['Period', 'Amplitude']
    # Set number of columns
    self.create_table.setColumnCount(len(headers))

    # Set column headers
    self.create_table.setHorizontalHeaderLabels(headers)

    # Set number of rows
    self.create_table.setRowCount(3)

    # Fill rows with empty items
    for row in range(3):
        for col in range(len(headers)):
            self.create_table.setItem(row, col, QTableWidgetItem(""))

    self.create_table.resizeColumnsToContents()
    self.create_table.resizeRowsToContents()
    self.create_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

