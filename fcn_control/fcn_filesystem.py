import requests
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon, QFont, QColor
from PySide6.QtWidgets import QMessageBox, QInputDialog, QHeaderView
from fcn_monitor.fcn_duet import get_clean_duet_ip, duet_request


def setup_file_explorer(self):
    """
    Function to create multi-column file explorer tree model with Name, Size, and Date.
    Only reads directory if Duet is connected.
    """
    self.model = QStandardItemModel()
    self.model.setHorizontalHeaderLabels(["Name", "Size", "Last Modified"])

    self.fileTreeView.setModel(self.model)
    self.fileTreeView.setRootIsDecorated(False)

    # Configure Header column sizes
    header = self.fileTreeView.header()
    if header:
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.fileTreeView.setColumnWidth(0, 380)

    # Load root directory if connected
    load_directory(self, "/")


def get_files_for_dir(self, directory):
    """
    Function to retrieve the contents of a folder on SD card.
    Only attempts HTTP request if self.duet_connected is True.
    """
    if not getattr(self, 'duet_connected', False):
        print("Duet is not connected; skipping SD card file read.")
        return []

    ip = get_clean_duet_ip(self)
    clean_dir = directory.strip('/')
    dir_param = "0:/gcodes" if not clean_dir else f"0:/gcodes/{clean_dir}"
    
    url = f"http://{ip}/rr_filelist"

    try:
        response = duet_request(url, params={'dir': dir_param}, timeout=4)
        response.raise_for_status()
        data = response.json()
        return data.get("files", [])
    except Exception as e:
        print(f"Error fetching files from {url} ({dir_param}): {e}")
        return []
    

def load_directory(self, directory):
    """
    Function to load a directory and display its contents with folder colors & metadata.
    Only reads directory from Duet if connected.
    """
    self.current_directory = directory

    if hasattr(self, 'model') and self.model is not None:
        root = self.model.invisibleRootItem()
        root.removeRows(0, root.rowCount())

    if not getattr(self, 'duet_connected', False):
        if hasattr(self, 'filePathLabel') and self.filePathLabel is not None:
            self.filePathLabel.setText("Current Directory: Duet not connected (Press Connect to load files)")
        return

    # Update path display label if available
    if hasattr(self, 'filePathLabel') and self.filePathLabel is not None:
        clean_dir = directory.strip('/')
        path_display = "0:/gcodes/" if not clean_dir else f"0:/gcodes/{clean_dir}/"
        self.filePathLabel.setText(f"Current Directory: {path_display}")

    root = self.model.invisibleRootItem()

    # Get files/folders in directory
    items = get_files_for_dir(self, directory)

    # Sort to display folders on top
    def sort_key(entry):
        is_dir = entry.get("type") == "d"
        name = entry.get("name", "").lower()
        return (not is_dir, name)
    
    items.sort(key=sort_key)

    # Create multi-column row entries for files/folders
    for entry in items:
        row_items = create_row_items(self, entry, directory)
        root.appendRow(row_items)


def create_row_items(self, entry, directory):
    """
    Creates QStandardItem list for a single row [Name, Size, Last Modified].
    Colors directory names blue (#1565c0) and adds folder icons.
    """
    is_dir = entry.get("type") == "d"
    raw_name = entry.get("name", "")
    size_bytes = entry.get("size", 0)
    date_str = entry.get("date", "")

    # Column 0: Name
    name_item = QStandardItem(raw_name)
    name_item.setEditable(False)
    
    # Store full path data on item
    clean_dir = directory.strip('/')
    rel_path = raw_name if not clean_dir else f"{clean_dir}/{raw_name}"
    name_item.setData(rel_path, role=self.PATH_ROLE)
    name_item.setData(is_dir, role=self.IS_DIR_ROLE)

    if is_dir:
        name_item.setForeground(QColor("#1565c0"))
        font = QFont()
        font.setBold(True)
        name_item.setFont(font)
        name_item.setIcon(QIcon.fromTheme("folder"))

    # Column 1: Size
    if is_dir:
        size_text = "Folder"
    else:
        size_text = format_file_size(size_bytes)
    size_item = QStandardItem(size_text)
    size_item.setEditable(False)

    # Column 2: Last Modified Date
    date_item = QStandardItem(date_str if date_str else "--")
    date_item.setEditable(False)

    return [name_item, size_item, date_item]


def format_file_size(size_bytes):
    """Format file size in KB or MB."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def go_back(self):
    """
    Navigate to parent directory in the SD card file explorer.
    """
    if not getattr(self, 'duet_connected', False):
        return
    curr = getattr(self, 'current_directory', '/')
    clean = curr.strip('/')
    if not clean:
        return
    parent = '/'.join(clean.split('/')[:-1])
    load_directory(self, parent if parent else '/')


def mkdir(self):
    """
    Create a new directory inside current folder on SD card.
    """
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before creating directories.")
        return

    folder_name, ok = QInputDialog.getText(self, "New Folder", "Folder Name:")
    if ok and folder_name.strip():
        ip = get_clean_duet_ip(self)
        curr = getattr(self, 'current_directory', '/').strip('/')
        dir_path = f"0:/gcodes/{folder_name.strip()}" if not curr else f"0:/gcodes/{curr}/{folder_name.strip()}"
        
        url = f"http://{ip}/rr_mkdir"
        try:
            response = duet_request(url, params={'dir': dir_path}, timeout=4)
            if response.status_code == 200:
                load_directory(self, getattr(self, 'current_directory', '/'))
            else:
                QMessageBox.warning(self, "Error", f"Failed to create directory (HTTP {response.status_code})")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to create directory: {e}")


def delete_selected_item(self):
    """
    Delete the selected file or folder from SD card with confirmation popup.
    """
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before deleting files.")
        return

    indexes = self.fileTreeView.selectedIndexes()
    if not indexes:
        QMessageBox.information(self, "Delete Item", "Please select a file or folder to delete.")
        return

    # Column 0 index
    index = [i for i in indexes if i.column() == 0][0]
    item = self.model.itemFromIndex(index)
    if not item:
        return

    rel_path = item.data(role=self.PATH_ROLE)
    is_dir = item.data(role=self.IS_DIR_ROLE)
    item_name = item.text()

    reply = QMessageBox.question(
        self,
        "Confirm Delete",
        f"Are you sure you want to delete {'folder' if is_dir else 'file'} '{item_name}'?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )

    if reply != QMessageBox.Yes:
        return

    ip = get_clean_duet_ip(self)
    target_path = f"0:/gcodes/{rel_path}"
    url = f"http://{ip}/rr_delete" if not is_dir else f"http://{ip}/rr_rmdir"

    try:
        response = duet_request(url, params={'name': target_path}, timeout=4)
        if response.status_code == 200:
            load_directory(self, getattr(self, 'current_directory', '/'))
        else:
            QMessageBox.warning(self, "Delete Error", f"Failed to delete '{item_name}' (HTTP {response.status_code})")
    except Exception as e:
        QMessageBox.warning(self, "Delete Error", f"Failed to delete '{item_name}': {e}")


def start_gcode(self, fpath):
    """Legacy wrapper function to start a GCODE file."""
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before starting print jobs.")
        return
    self.status_t0 = None
    self.status_plot_data = None
    self.status_stopped = False
    ip = get_clean_duet_ip(self)
    url = f'http://{ip}/rr_gcode'
    try:
        duet_request(url, params={'gcode': f'M32 0:/gcodes/{fpath.strip("/")}'}, timeout=4)
        if hasattr(self, 'tabModules'):
            self.tabModules.setCurrentIndex(1)
    except Exception as e:
        QMessageBox.warning(self, "Duet Error", f"Failed to start {fpath}: {e}")


def run_selected_gcode_item(self):
    """
    Runs the currently selected G-code file on the Duet.
    """
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Connection Required", "Duet not connected. Please connect first.")
        return

    indexes = self.fileTreeView.selectedIndexes()
    if not indexes:
        QMessageBox.warning(self, "Selection Required", "Please select a G-code file to run.")
        return

    index_col0 = indexes[0].siblingAtColumn(0)
    item = self.model.itemFromIndex(index_col0)
    if item is None:
        return
    path = item.data(self.PATH_ROLE)
    is_dir = item.data(self.IS_DIR_ROLE)

    if is_dir:
        QMessageBox.warning(self, "Invalid Selection", "Cannot run a folder. Please select a G-code file.")
        return

    start_gcode(self, path)


def delete_recursively(self, path, is_dir=False):
    """Legacy wrapper function for recursive delete."""
    delete_selected_item(self)


def download_file(self, filepath):
    """
    Downloads a file from the Duet SD card to the local computer.
    Prompts the user to select the destination file name and path using a QFileDialog.
    """
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before downloading files.")
        return

    # filepath is relative to '0:/gcodes' (e.g. 'subfolder/file.gcode' or 'file.gcode')
    clean_path = filepath.strip('/')
    rrf_path = f"0:/gcodes/{clean_path}" if clean_path else "0:/gcodes"

    # Get local destination filename from QFileDialog
    filename = filepath.split('/')[-1]
    
    from PySide6.QtWidgets import QFileDialog
    dest_path, _ = QFileDialog.getSaveFileName(self, "Download File to Computer", filename, "All Files (*)")
    if not dest_path:
        return # user cancelled

    ip = get_clean_duet_ip(self)
    url = f"http://{ip}/rr_download"

    try:
        # Avoid proxy issues by setting trust_env=False
        session = requests.Session()
        session.trust_env = False
        response = session.get(url, params={'name': rrf_path}, timeout=10, stream=True)
        response.raise_for_status()

        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        QMessageBox.information(self, "Download Complete", f"File downloaded successfully to:\n{dest_path}")
    except Exception as e:
        QMessageBox.critical(self, "Download Error", f"Failed to download file from Duet:\n{e}")


def download_selected_item(self):
    """
    Downloads the selected file in the tree view to the local computer.
    """
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before downloading files.")
        return

    indexes = self.fileTreeView.selectedIndexes()
    if not indexes:
        QMessageBox.information(self, "Download Item", "Please select a file to download.")
        return

    # Column 0 index
    index = [i for i in indexes if i.column() == 0][0]
    item = self.model.itemFromIndex(index)
    if not item:
        return

    rel_path = item.data(role=self.PATH_ROLE)
    is_dir = item.data(role=self.IS_DIR_ROLE)

    if is_dir:
        QMessageBox.warning(self, "Download Item", "Cannot download folders. Please select a file.")
        return

    download_file(self, rel_path)


def upload_file(self):
    """
    Prompts the user to select a G-code file from their local computer,
    and uploads it to the current directory on the Duet SD card.
    """
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before uploading files.")
        return

    from PySide6.QtWidgets import QFileDialog
    import os

    local_path, _ = QFileDialog.getOpenFileName(self, "Upload G-code File", "", "G-code Files (*.gcode *.g *._gcode);;All Files (*)")
    if not local_path:
        return # user cancelled

    filename = os.path.basename(local_path)
    curr_dir = getattr(self, 'current_directory', '/').strip('/')
    rrf_path = f"0:/gcodes/{filename}" if not curr_dir else f"0:/gcodes/{curr_dir}/{filename}"

    ip = get_clean_duet_ip(self)
    url = f"http://{ip}/rr_upload"

    try:
        with open(local_path, 'rb') as f:
            file_data = f.read()

        # Avoid proxy issues by setting trust_env=False
        session = requests.Session()
        session.trust_env = False
        
        # RRF expects POST request with raw data
        response = session.post(url, params={'name': rrf_path}, data=file_data, timeout=15)
        response.raise_for_status()

        QMessageBox.information(self, "Upload Successful", f"File '{filename}' uploaded successfully to Duet!")
        load_directory(self, getattr(self, 'current_directory', '/'))
    except Exception as e:
        QMessageBox.critical(self, "Upload Error", f"Failed to upload '{filename}':\n{e}")