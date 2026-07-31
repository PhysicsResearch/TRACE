import requests
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon, QFont, QColor
from PySide6.QtWidgets import QMessageBox, QInputDialog, QHeaderView
from fcn_monitor.fcn_duet import get_clean_duet_ip, duet_request


def on_header_section_clicked(self, logicalIndex):
    """
    Called when a column section in the file tree header is clicked.
    Toggles sorting order and reloads the directory.
    """
    from PySide6.QtCore import Qt

    if logicalIndex not in [0, 2]:
        return  # Only sort by Name (0) and Last Modified (2)

    current_col = getattr(self, 'sort_column', 0)
    current_order = getattr(self, 'sort_order', Qt.AscendingOrder)

    if current_col == logicalIndex:
        new_order = Qt.DescendingOrder if current_order == Qt.AscendingOrder else Qt.AscendingOrder
    else:
        new_order = Qt.AscendingOrder

    self.sort_column = logicalIndex
    self.sort_order = new_order

    header = self.fileTreeView.header()
    if header:
        header.setSortIndicator(logicalIndex, new_order)

    if hasattr(self, 'current_directory'):
        load_directory(self, self.current_directory)


def setup_file_explorer(self):
    """
    Function to create multi-column file explorer tree model with Name, Size, and Date.
    Only reads directory if Duet is connected.
    """
    from PySide6.QtCore import Qt

    self.model = QStandardItemModel()
    self.model.setHorizontalHeaderLabels(["Name", "Size", "Last Modified"])

    self.fileTreeView.setModel(self.model)
    self.fileTreeView.setRootIsDecorated(False)

    # Configure Header column sizes to be resizable (Interactive)
    header = self.fileTreeView.header()
    if header:
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        self.fileTreeView.setColumnWidth(0, 350)
        self.fileTreeView.setColumnWidth(1, 100)
        self.fileTreeView.setColumnWidth(2, 200)

        # Set sort indicator properties
        header.setSortIndicatorShown(True)
        self.sort_column = getattr(self, 'sort_column', 0)
        self.sort_order = getattr(self, 'sort_order', Qt.AscendingOrder)
        header.setSortIndicator(self.sort_column, self.sort_order)

        # Connect header clicked sort handler
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            try:
                header.sectionClicked.disconnect()
            except:
                pass
        header.sectionClicked.connect(lambda col: on_header_section_clicked(self, col))

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

    from PySide6.QtCore import Qt

    sort_col = getattr(self, 'sort_column', 0)
    sort_ord = getattr(self, 'sort_order', Qt.AscendingOrder)
    reverse_sort = (sort_ord == Qt.DescendingOrder)

    # Separate directories and files so directories stay on top
    folders = [e for e in items if e.get("type") == "d"]
    files = [e for e in items if e.get("type") != "d"]

    if sort_col == 0:  # Sort by Name
        folders.sort(key=lambda e: e.get("name", "").lower(), reverse=reverse_sort)
        files.sort(key=lambda e: e.get("name", "").lower(), reverse=reverse_sort)
    elif sort_col == 2:  # Sort by Date
        folders.sort(key=lambda e: e.get("date", ""), reverse=reverse_sort)
        files.sort(key=lambda e: e.get("date", ""), reverse=reverse_sort)
    else:  # Unsortable / Default
        folders.sort(key=lambda e: e.get("name", "").lower())
        files.sort(key=lambda e: e.get("name", "").lower())

    sorted_items = folders + files

    # Create multi-column row entries for files/folders
    for entry in sorted_items:
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

    # Prompt for folder name (touchscreen-friendly sizing & styling)
    from PySide6.QtWidgets import QWidget
    parent_widget = self if (isinstance(self, QWidget) and not type(self).__name__.endswith('Mock')) else None
    dialog = QInputDialog(parent_widget)
    dialog.setWindowTitle("New Folder")
    dialog.setLabelText("Folder Name:")
    dialog.setInputMode(QInputDialog.TextInput)
    dialog.setMinimumWidth(600)
    dialog.setMinimumHeight(200)
    dialog.setStyleSheet("""
        QInputDialog {
            font-size: 18px;
            font-weight: bold;
        }
        QLabel {
            font-size: 18px;
            min-height: 40px;
        }
        QLineEdit {
            font-size: 18px;
            min-height: 45px;
            padding: 6px;
        }
        QPushButton {
            font-size: 18px;
            font-weight: bold;
            min-width: 120px;
            min-height: 45px;
            border-radius: 4px;
        }
    """)

    ok = dialog.exec()
    folder_name = dialog.textValue()
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
                QMessageBox.warning(parent_widget, "Error", f"Failed to create directory (HTTP {response.status_code})")
        except Exception as e:
            QMessageBox.warning(parent_widget, "Error", f"Failed to create directory: {e}")


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
    
    from PySide6.QtWidgets import QFileDialog, QProgressDialog
    from PySide6.QtCore import Qt, QCoreApplication
    dest_path, _ = QFileDialog.getSaveFileName(self, "Download File to Computer", filename, "All Files (*)")
    if not dest_path:
        return # user cancelled

    # Initialize progress dialog
    progress = QProgressDialog(f"Downloading '{filename}' to computer...", "Cancel", 0, 100, self)
    progress.setWindowTitle("Downloading File")
    progress.setWindowModality(Qt.WindowModal)
    progress.setMinimumWidth(550)
    progress.setMinimumHeight(180)
    progress.setStyleSheet("""
        QProgressDialog {
            font-size: 18px;
            font-weight: bold;
        }
        QLabel {
            font-size: 18px;
            min-height: 40px;
        }
        QProgressBar {
            text-align: center;
            font-size: 18px;
            font-weight: bold;
            height: 35px;
            border-radius: 4px;
        }
        QPushButton {
            font-size: 18px;
            font-weight: bold;
            min-width: 120px;
            min-height: 45px;
            border-radius: 4px;
        }
    """)
    progress.setValue(0)
    progress.show()
    QCoreApplication.processEvents()

    ip = get_clean_duet_ip(self)
    url = f"http://{ip}/rr_download"

    try:
        from fcn_monitor.fcn_duet import get_shared_session
        session = get_shared_session()
        response = session.get(url, params={'name': rrf_path}, timeout=10, stream=True)
        response.raise_for_status()

        # Try to get Content-Length from headers
        total_size = int(response.headers.get('content-length', 0))
        bytes_written = 0

        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=16384):
                if progress.wasCanceled():
                    raise Exception("Download cancelled by user")
                if chunk:
                    f.write(chunk)
                    bytes_written += len(chunk)
                    percent = int((bytes_written / total_size) * 100) if total_size > 0 else 50
                    progress.setValue(percent)
                    QCoreApplication.processEvents()

        progress.setValue(100)
        QMessageBox.information(self, "Download Complete", f"File downloaded successfully to:\n{dest_path}")
    except Exception as e:
        progress.close()
        if "cancelled by user" in str(e):
            QMessageBox.information(self, "Download Cancelled", "Download was cancelled by the user.")
        else:
            QMessageBox.critical(self, "Download Error", f"Failed to download file from Duet:\n{e}")


def transfer_to_planning_action(self):
    """
    Downloads the selected G-code file from the Duet SD card directly into memory,
    then parses it and imports it into the Planning tab.
    """
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before transferring files.")
        return

    indexes = self.fileTreeView.selectedIndexes()
    if not indexes:
        QMessageBox.information(self, "Transfer to Planning", "Please select a file to transfer.")
        return

    # Column 0 index
    index = [i for i in indexes if i.column() == 0][0]
    item = self.model.itemFromIndex(index)
    if not item:
        return

    rel_path = item.data(role=self.PATH_ROLE)
    is_dir = item.data(role=self.IS_DIR_ROLE)

    if is_dir:
        QMessageBox.warning(self, "Transfer to Planning", "Cannot transfer folders. Please select a file.")
        return

    import os
    filename = os.path.basename(rel_path)
    clean_path = rel_path.strip('/')
    rrf_path = f"0:/gcodes/{clean_path}" if clean_path else "0:/gcodes"

    # Ensure Planning tab is loaded
    if 3 not in getattr(self, '_loaded_tabs', set()):
        from fcn_create_gui.tab_planning import build_planning_tab
        build_planning_tab(self)
        self._loaded_tabs.add(3)
        from fcn_init.init_buttons import initialize_software_buttons
        initialize_software_buttons(self)

    from PySide6.QtWidgets import QProgressDialog
    from PySide6.QtCore import Qt, QCoreApplication
    import requests
    import io

    # 1. Start download with progress bar (touchscreen-friendly sizing & styling)
    progress = QProgressDialog(f"Downloading '{filename}' from Duet...", "Cancel", 0, 200, self)
    progress.setWindowTitle("Transfer to Planning")
    progress.setWindowModality(Qt.WindowModal)
    progress.setMinimumWidth(550)
    progress.setMinimumHeight(180)
    progress.setStyleSheet("""
        QProgressDialog {
            font-size: 18px;
            font-weight: bold;
        }
        QLabel {
            font-size: 18px;
            min-height: 40px;
        }
        QProgressBar {
            text-align: center;
            font-size: 18px;
            font-weight: bold;
            height: 35px;
            border-radius: 4px;
        }
        QPushButton {
            font-size: 18px;
            font-weight: bold;
            min-width: 120px;
            min-height: 45px;
            border-radius: 4px;
        }
    """)
    progress.setValue(0)
    progress.show()
    QCoreApplication.processEvents()

    ip = get_clean_duet_ip(self)
    url = f"http://{ip}/rr_download"

    try:
        # Fetch file size using stream=True and shared session
        from fcn_monitor.fcn_duet import get_shared_session
        session = get_shared_session()
        response = session.get(url, params={'name': rrf_path}, timeout=10, stream=True)
        response.raise_for_status()

        # Try to get Content-Length from headers
        total_size = int(response.headers.get('content-length', 0))
        
        # Read file chunks
        gcode_bytes = bytearray()
        bytes_read = 0

        for chunk in response.iter_content(chunk_size=16384):
            if progress.wasCanceled():
                raise Exception("Transfer cancelled by user")
            if chunk:
                gcode_bytes.extend(chunk)
                bytes_read += len(chunk)
                
                # First 50% (0 - 100 range) of progress bar is for downloading
                percent = int((bytes_read / total_size) * 100) if total_size > 0 else 50
                progress.setValue(int(percent))
                QCoreApplication.processEvents()

        gcode_content = gcode_bytes.decode('utf-8', errors='ignore')

        # 2. Start importing from memory
        progress.setLabelText("Parsing G-code and loading table...")
        progress.setValue(100)
        QCoreApplication.processEvents()

        from fcn_plan.fcn_create import import_gcode_from_string
        import_gcode_from_string(self, gcode_content, progress_dialog=progress, progress_offset=100)

    except Exception as e:
        progress.close()
        if "cancelled by user" in str(e):
            QMessageBox.information(self, "Transfer Cancelled", "Transfer to Planning was cancelled by the user.")
        else:
            QMessageBox.critical(self, "Transfer Error", f"Failed to transfer G-code:\n{e}")


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
    and uploads it to the current directory on the Duet SD card with a progress bar.
    """
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before uploading files.")
        return

    from PySide6.QtWidgets import QFileDialog, QProgressDialog
    from PySide6.QtCore import Qt, QCoreApplication
    import os
    import io
    import requests

    local_path, _ = QFileDialog.getOpenFileName(self, "Upload G-code File", "", "G-code Files (*.gcode *.g *._gcode);;All Files (*)")
    if not local_path:
        return # user cancelled

    filename = os.path.basename(local_path)
    curr_dir = getattr(self, 'current_directory', '/').strip('/')
    rrf_path = f"0:/gcodes/{filename}" if not curr_dir else f"0:/gcodes/{curr_dir}/{filename}"

    ip = get_clean_duet_ip(self)
    url = f"http://{ip}/rr_upload"

    try:
        # Read the file bytes
        with open(local_path, 'rb') as f:
            file_data = f.read()
        total_size = len(file_data)

        # Initialize progress dialog (touchscreen-friendly sizing & styling)
        progress = QProgressDialog(f"Uploading '{filename}' to Duet...", "Cancel", 0, 100, self)
        progress.setWindowTitle("Uploading File")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumWidth(550)
        progress.setMinimumHeight(180)
        progress.setStyleSheet("""
            QProgressDialog {
                font-size: 18px;
                font-weight: bold;
            }
            QLabel {
                font-size: 18px;
                min-height: 40px;
            }
            QProgressBar {
                text-align: center;
                font-size: 18px;
                font-weight: bold;
                height: 35px;
                border-radius: 4px;
            }
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                min-width: 120px;
                min-height: 45px;
                border-radius: 4px;
            }
        """)
        progress.setValue(0)
        progress.show()
        QCoreApplication.processEvents()

        def progress_callback(bytes_read, total):
            if progress.wasCanceled():
                raise Exception("Upload cancelled by user")
            percent = int((bytes_read / total) * 100) if total > 0 else 0
            progress.setValue(percent)
            QCoreApplication.processEvents()

        # Custom BytesIO wrapper to track reading progress
        class ProgressIO(io.BytesIO):
            def __init__(self, data_bytes, callback):
                super().__init__(data_bytes)
                self.callback = callback
                self.total = len(data_bytes)
                self.read_bytes = 0

            def read(self, size=-1):
                chunk = super().read(size)
                self.read_bytes += len(chunk)
                self.callback(self.read_bytes, self.total)
                return chunk

        progress_io = ProgressIO(file_data, progress_callback)

        # ── Stop background polling so no other HTTP request reaches Duet during upload ──
        polling_was_active = False
        fast_was_active = False
        if hasattr(self, 'status_polling_timer') and self.status_polling_timer.isActive():
            self.status_polling_timer.stop()
            polling_was_active = True
        if hasattr(self, 'status_fast_timer') and self.status_fast_timer.isActive():
            self.status_fast_timer.stop()
            fast_was_active = True

        # Close the shared session's TCP connection pool so Duet's single-connection
        # HTTP server has a free slot for our upload POST.
        from fcn_monitor.fcn_duet import get_shared_session
        get_shared_session().close()

        # Use a fresh, dedicated session for the upload
        upload_session = requests.Session()
        upload_session.trust_env = False
        try:
            response = upload_session.post(url, params={'name': rrf_path}, data=progress_io, timeout=20)
            response.raise_for_status()
        finally:
            upload_session.close()

        progress.setValue(100)
        QMessageBox.information(self, "Upload Successful", f"File '{filename}' uploaded successfully to Duet!")
        load_directory(self, getattr(self, 'current_directory', '/'))
    except Exception as e:
        if 'progress' in locals():
            progress.close()
        if "cancelled by user" in str(e):
            QMessageBox.information(self, "Upload Cancelled", f"Upload of '{filename}' was cancelled by the user.")
        else:
            QMessageBox.critical(self, "Upload Error", f"Failed to upload '{filename}':\n{e}")
    finally:
        if 'polling_was_active' in locals() and polling_was_active and hasattr(self, 'status_polling_timer'):
            self.status_polling_timer.start()
        if 'fast_was_active' in locals() and fast_was_active and hasattr(self, 'status_fast_timer'):
            self.status_fast_timer.start()