import os
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

    if logicalIndex not in [0, 1, 2]:
        return  # Sort by Name (0), Size (1), or Last Modified (2)

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
    self.fileTreeView.setSortingEnabled(False)  # Allow custom folder-first sorting

    # Configure Header column sizes to be resizable (Interactive) and clickable
    header = self.fileTreeView.header()
    if header:
        header.setSectionsClickable(True)
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

        # Connect header clicked sort handler once safely
        if not getattr(self, '_tree_header_connected', False):
            self._tree_header_connected = True
            header.sectionClicked.connect(lambda col: on_header_section_clicked(self, col))

    # Load root directory if connected
    load_directory(self, "/")


def normalize_file_entry(item):
    """Normalizes string or dict items from Duet API into standard dict format."""
    if isinstance(item, dict):
        name = item.get("name") or item.get("filename") or ""
        item_type = item.get("type", "f")
        if item_type == "d" or name.endswith("/"):
            item_type = "d"
        name = name.rstrip('/')
        size = item.get("size", 0)
        date = item.get("date") or item.get("lastModified") or ""
        return {"name": name, "type": item_type, "size": size, "date": date}
    elif isinstance(item, str):
        is_dir = item.endswith("/")
        clean_name = item.rstrip("/")
        item_type = "d" if is_dir else "f"
        return {"name": clean_name, "type": item_type, "size": 0, "date": ""}
    return {"name": str(item), "type": "f", "size": 0, "date": ""}


def get_root_prefix(self):
    """Returns root SD card folder based on dropdown selection ('0:/gcodes', '0:/macros', '0:/sys')."""
    if hasattr(self, 'fileCategoryCombo') and self.fileCategoryCombo is not None:
        category = self.fileCategoryCombo.currentText()
        if category == "Macros":
            return "0:/macros"
        elif category == "System":
            return "0:/sys"
        else:
            return "0:/gcodes"
    return getattr(self, 'current_root_prefix', "0:/gcodes")


def on_file_category_changed(self, text=None):
    """
    Triggered when user selects GCODE, Macros, or System from the dropdown menu.
    Resets current directory to root '/' and loads the selected directory tree.
    """
    self.current_directory = "/"
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
    root_prefix = get_root_prefix(self)
    clean_dir = directory.strip('/')
    dir_param = root_prefix if not clean_dir else f"{root_prefix}/{clean_dir}"
    
    url = f"http://{ip}/rr_filelist"

    try:
        response = duet_request(url, params={'dir': dir_param}, timeout=4)
        response.raise_for_status()
        data = response.json()
        raw_files = data.get("files", [])
        return [normalize_file_entry(e) for e in raw_files]
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
        root_prefix = get_root_prefix(self)
        clean_dir = directory.strip('/')
        path_display = f"{root_prefix}/" if not clean_dir else f"{root_prefix}/{clean_dir}/"
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
    elif sort_col == 1:  # Sort by Size
        folders.sort(key=lambda e: int(e.get("size", 0)), reverse=reverse_sort)
        files.sort(key=lambda e: int(e.get("size", 0)), reverse=reverse_sort)
    elif sort_col == 2:  # Sort by Date / Last Modified
        folders.sort(key=lambda e: str(e.get("date", "")).lower(), reverse=reverse_sort)
        files.sort(key=lambda e: str(e.get("date", "")).lower(), reverse=reverse_sort)
    else:
        folders.sort(key=lambda e: e.get("name", "").lower(), reverse=reverse_sort)
        files.sort(key=lambda e: e.get("name", "").lower(), reverse=reverse_sort)

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
        root_prefix = get_root_prefix(self)
        dir_path = f"{root_prefix}/{folder_name.strip()}" if not curr else f"{root_prefix}/{curr}/{folder_name.strip()}"
        
        url = f"http://{ip}/rr_mkdir"
        try:
            response = duet_request(url, params={'dir': dir_path}, timeout=4)
            if response.status_code == 200:
                load_directory(self, getattr(self, 'current_directory', '/'))
            else:
                QMessageBox.warning(parent_widget, "Error", f"Failed to create directory (HTTP {response.status_code})")
        except Exception as e:
            QMessageBox.warning(parent_widget, "Error", f"Failed to create directory: {e}")


def delete_remote_path(self, ip, target_path, is_dir):
    """
    Deletes a file or directory on Duet SD card.
    If a directory is selected, recursively deletes its contents first before removing the directory.
    """
    clean_target = target_path.rstrip('/')
    if is_dir:
        # 1. Clean sub-path for file listing
        root_prefix = get_root_prefix(self)
        sub_dir = clean_target.replace(f"{root_prefix}/", "").replace(root_prefix, "")
        sub_items = get_files_for_dir(self, sub_dir)
        for sub in sub_items:
            sub_name = sub.get("name", "")
            sub_is_dir = (sub.get("type") == "d")
            sub_target = f"{clean_target}/{sub_name}"
            delete_remote_path(self, ip, sub_target, sub_is_dir)

        # 2. Try RRF rmdir / delete endpoints with dir and name parameters
        endpoints = [
            (f"http://{ip}/rr_rmdir", {'dir': clean_target}),
            (f"http://{ip}/rr_rmdir", {'name': clean_target}),
            (f"http://{ip}/rr_delete", {'name': clean_target}),
            (f"http://{ip}/rr_delete", {'path': clean_target})
        ]
        for url, p in endpoints:
            try:
                res = duet_request(url, params=p, timeout=4)
                if res.status_code == 200:
                    return True, 200
            except Exception:
                pass
        return False, 500
    else:
        endpoints = [
            (f"http://{ip}/rr_delete", {'name': clean_target}),
            (f"http://{ip}/rr_delete", {'path': clean_target})
        ]
        for url, p in endpoints:
            try:
                res = duet_request(url, params=p, timeout=4)
                if res.status_code == 200:
                    return True, 200
            except Exception:
                pass
        return False, 500


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
    root_prefix = get_root_prefix(self)
    target_path = f"{root_prefix}/{rel_path}"

    try:
        success, code = delete_remote_path(self, ip, target_path, is_dir)
        if success:
            load_directory(self, getattr(self, 'current_directory', '/'))
        else:
            QMessageBox.warning(self, "Delete Error", f"Failed to delete '{item_name}' (HTTP {code})")
    except Exception as e:
        QMessageBox.warning(self, "Delete Error", f"Failed to delete '{item_name}': {e}")


def select_gcode_for_status(self, fpath):
    """
    Selects a G-code file, switches to the Status tab, and prepares it for execution.
    Reference plot data is automatically downloaded on Start if 'Show reference' is enabled.
    """
    self.selected_gcode_path = fpath
    self.status_reference_data = None

    if hasattr(self, 'statusDuetMessage') and self.statusDuetMessage is not None:
        self.statusDuetMessage.setText(f"File 0:/gcodes/{os.path.basename(fpath)} selected for printing. Press 'Start' to begin motion.")

    if hasattr(self, 'tabModules') and self.tabModules is not None:
        self.tabModules.setCurrentIndex(1)


def start_gcode(self, fpath):
    """Selects the G-code file and moves to Status tab, ready to start."""
    select_gcode_for_status(self, fpath)


def run_selected_gcode_item(self):
    """
    Selects the currently highlighted G-code file on the Files tab and moves to the Status tab.
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

    select_gcode_for_status(self, path)


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


def get_all_folders_recursive(self, base_dir=""):
    """
    Recursively scans SD card directories to build a list of all available folder paths.
    Returns relative paths using slashes.
    """
    folder_paths = []
    
    def scan_dir(rel_path):
        items = get_files_for_dir(self, rel_path)
        for item in items:
            if item.get("type") == "d":
                fname = item.get("name", "")
                sub_rel = fname if not rel_path else f"{rel_path}/{fname}"
                folder_paths.append(sub_rel)
                scan_dir(sub_rel)

    scan_dir("")
    return folder_paths


def move_selected_item(self):
    """
    Moves a selected file or folder to a target destination folder selected from a dropdown of available folders.
    If RRF filemove endpoint is unsupported or fails, falls back to copy-and-delete.
    """
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before moving files.")
        return

    indexes = self.fileTreeView.selectedIndexes()
    if not indexes:
        QMessageBox.information(self, "Move Item", "Please select a file or folder to move.")
        return

    index = [i for i in indexes if i.column() == 0][0]
    item = self.model.itemFromIndex(index)
    if not item:
        return

    rel_path = item.data(role=self.PATH_ROLE)
    is_dir = item.data(role=self.IS_DIR_ROLE)
    item_name = item.text()

    # Retrieve all folders and subfolders on SD card
    raw_folder_paths = get_all_folders_recursive(self)
    
    # Exclude moving a directory into itself or its own subfolders
    if is_dir:
        filtered_paths = [p for p in raw_folder_paths if p != rel_path and not p.startswith(f"{rel_path}/")]
    else:
        filtered_paths = raw_folder_paths

    # Format options for display with backslashes: "folder\subfolder1"
    options_map = {"/ (Root Directory)": ""}
    display_options = ["/ (Root Directory)"]
    for p in filtered_paths:
        display_name = p.replace('/', '\\')
        options_map[display_name] = p
        display_options.append(display_name)

    selected_display, ok = QInputDialog.getItem(
        self,
        "Move File / Folder",
        f"Select destination folder for '{item_name}':",
        display_options,
        0,
        False
    )

    if not ok or selected_display not in options_map:
        return

    chosen_rel = options_map[selected_display]
    root_prefix = get_root_prefix(self)
    if chosen_rel == "":
        target_dir = root_prefix
    else:
        target_dir = f"{root_prefix}/{chosen_rel}"

    from_path = f"{root_prefix}/{rel_path}"
    to_path = f"{target_dir}/{item_name}"

    if from_path == to_path:
        return

    ip = get_clean_duet_ip(self)
    
    # 0. Ensure target directory exists on SD card
    if chosen_rel != "":
        try:
            duet_request(f"http://{ip}/rr_mkdir", params={'dir': target_dir}, timeout=4)
            duet_request(f"http://{ip}/rr_gcode", params={'gcode': f'M470 P"{target_dir}"'}, timeout=4)
        except Exception:
            pass

    from_dir = os.path.dirname(rel_path)
    moved = False

    # 1. Native RRF G-code M471 variants (Instant FatFS SD card move)
    clean_from = from_path.replace("0:/", "")
    clean_to = to_path.replace("0:/", "")
    m471_variants = [
        f'M471 S"{from_path}" T"{to_path}" D1',
        f'M471 S"{clean_from}" T"{clean_to}" D1',
        f'M471 S"/{clean_from}" T"/{clean_to}" D1'
    ]

    for cmd in m471_variants:
        try:
            duet_request(f"http://{ip}/rr_gcode", params={'gcode': cmd}, timeout=4)
            import time
            time.sleep(0.1)
            # Verify if item moved from source directory
            check_items = get_files_for_dir(self, from_dir)
            if not any(it.get("name") == item_name for it in check_items):
                moved = True
                break
        except Exception as e:
            print(f"M471 error: {e}")

    # 2. Try RRF HTTP move/rename API endpoints
    if not moved:
        endpoints = [
            (f"http://{ip}/rr_filemove", {'from': from_path, 'to': to_path}),
            (f"http://{ip}/rr_filemove", {'old': from_path, 'new': to_path}),
            (f"http://{ip}/rr_filemove", {'oldPath': from_path, 'newPath': to_path}),
            (f"http://{ip}/rr_rename", {'old': from_path, 'new': to_path}),
            (f"http://{ip}/rr_rename", {'from': from_path, 'to': to_path})
        ]

        for url, params in endpoints:
            try:
                res = duet_request(url, params=params, timeout=4)
                if res.status_code == 200:
                    try:
                        res_json = res.json()
                        if isinstance(res_json, dict) and res_json.get("err", 0) == 0:
                            moved = True
                            break
                    except Exception:
                        moved = True
                        break
            except Exception:
                pass

    # 3. Fallback for files: download content, upload to destination, delete original
    if not moved and not is_dir:
        try:
            dl_url = f"http://{ip}/rr_download"
            dl_res = duet_request(dl_url, params={'name': from_path}, timeout=10)
            if dl_res.status_code == 200 and dl_res.content:
                file_bytes = dl_res.content
                up_url = f"http://{ip}/rr_upload"
                up_res = duet_request(up_url, params={'name': to_path}, data=file_bytes, timeout=15)
                if up_res.status_code == 200:
                    delete_remote_path(self, ip, from_path, is_dir=False)
                    moved = True
        except Exception as e:
            print(f"File copy-delete move fallback error: {e}")

    if moved:
        from fcn_control.fcn_control import log_to_duet_console
        log_to_duet_console(self, f"Moved '{item_name}' -> '{to_path}'")
        load_directory(self, getattr(self, 'current_directory', '/'))
    else:
        QMessageBox.warning(self, "Move Error", f"Failed to move '{item_name}' to '{to_path}'. Ensure the target folder exists on the SD card.")


def copy_selected_item(self):
    """
    Copies a selected file or folder to a target destination folder selected from a dropdown.
    """
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before copying files.")
        return

    indexes = self.fileTreeView.selectedIndexes()
    if not indexes:
        QMessageBox.information(self, "Copy Item", "Please select a file or folder to copy.")
        return

    index = [i for i in indexes if i.column() == 0][0]
    item = self.model.itemFromIndex(index)
    if not item:
        return

    rel_path = item.data(role=self.PATH_ROLE)
    is_dir = item.data(role=self.IS_DIR_ROLE)
    item_name = item.text()

    # Retrieve all folders and subfolders on SD card
    raw_folder_paths = get_all_folders_recursive(self)
    
    if is_dir:
        filtered_paths = [p for p in raw_folder_paths if p != rel_path and not p.startswith(f"{rel_path}/")]
    else:
        filtered_paths = raw_folder_paths

    options_map = {"/ (Root Directory)": ""}
    display_options = ["/ (Root Directory)"]
    for p in filtered_paths:
        display_name = p.replace('/', '\\')
        options_map[display_name] = p
        display_options.append(display_name)

    selected_display, ok = QInputDialog.getItem(
        self,
        "Copy File / Folder",
        f"Select destination folder for '{item_name}':",
        display_options,
        0,
        False
    )

    if not ok or selected_display not in options_map:
        return

    chosen_rel = options_map[selected_display]
    root_prefix = get_root_prefix(self)
    if chosen_rel == "":
        target_dir = root_prefix
    else:
        target_dir = f"{root_prefix}/{chosen_rel}"

    from_path = f"{root_prefix}/{rel_path}"
    to_path = f"{target_dir}/{item_name}"

    if from_path == to_path:
        base, ext = os.path.splitext(item_name)
        to_path = f"{target_dir}/{base}_copy{ext}"

    ip = get_clean_duet_ip(self)

    # Ensure target directory exists
    if chosen_rel != "":
        try:
            duet_request(f"http://{ip}/rr_mkdir", params={'dir': target_dir}, timeout=4)
            duet_request(f"http://{ip}/rr_gcode", params={'gcode': f'M470 P"{target_dir}"'}, timeout=4)
        except Exception:
            pass

    copied = False

    def copy_file_single(src, dst):
        from fcn_monitor.fcn_duet import get_shared_session
        session = get_shared_session()
        dl_url = f"http://{ip}/rr_download"
        res = session.get(dl_url, params={'name': src}, timeout=15)
        if res.status_code == 200 and res.content:
            session.close()
            up_session = requests.Session()
            up_session.trust_env = False
            try:
                up_url = f"http://{ip}/rr_upload"
                up_res = up_session.post(up_url, params={'name': dst}, data=res.content, timeout=20)
                return up_res.status_code == 200
            finally:
                up_session.close()
        return False

    def copy_folder_recursive(src, dst):
        duet_request(f"http://{ip}/rr_mkdir", params={'dir': dst}, timeout=4)
        sub_rel = src.replace("0:/gcodes/", "").replace("0:/gcodes", "")
        sub_items = get_files_for_dir(self, sub_rel)
        for s in sub_items:
            s_name = s.get("name", "")
            s_is_dir = (s.get("type") == "d")
            s_src = f"{src.rstrip('/')}/{s_name}"
            s_dst = f"{dst.rstrip('/')}/{s_name}"
            if s_is_dir:
                copy_folder_recursive(s_src, s_dst)
            else:
                copy_file_single(s_src, s_dst)
        return True

    try:
        if is_dir:
            copied = copy_folder_recursive(from_path, to_path)
        else:
            copied = copy_file_single(from_path, to_path)
    except Exception as e:
        print(f"Copy error: {e}")

    if copied:
        from fcn_control.fcn_control import log_to_duet_console
        log_to_duet_console(self, f"Copied '{item_name}' -> '{to_path}'")
        load_directory(self, getattr(self, 'current_directory', '/'))
    else:
        QMessageBox.warning(self, "Copy Error", f"Failed to copy '{item_name}' to '{to_path}'.")


def open_in_editor(self, rrf_path):
    """
    Downloads file from Duet with a progress dialog, populates the Editor tab, and switches to the Editor tab.
    """
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before editing files.")
        return

    filename = os.path.basename(rrf_path)
    
    from PySide6.QtWidgets import QProgressDialog
    from PySide6.QtCore import Qt, QCoreApplication

    progress = QProgressDialog(f"Loading '{filename}' into editor...", "Cancel", 0, 100, self)
    progress.setWindowTitle("Loading Editor")
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
    dl_url = f"http://{ip}/rr_download"

    try:
        from fcn_monitor.fcn_duet import get_shared_session
        session = get_shared_session()
        res = session.get(dl_url, params={'name': rrf_path}, timeout=15, stream=True)
        res.raise_for_status()

        total_size = int(res.headers.get('content-length', 0))
        chunks = []
        bytes_read = 0

        for chunk in res.iter_content(chunk_size=16384):
            if progress.wasCanceled():
                progress.close()
                return
            if chunk:
                chunks.append(chunk)
                bytes_read += len(chunk)
                if total_size > 0:
                    percent = int((bytes_read / total_size) * 100)
                    progress.setValue(percent)
                else:
                    progress.setValue(50)
                QCoreApplication.processEvents()

        progress.setValue(100)
        QCoreApplication.processEvents()

        raw_bytes = b"".join(chunks)
        text_content = raw_bytes.decode('utf-8', errors='replace')
        progress.close()

    except Exception as e:
        progress.close()
        QMessageBox.critical(self, "Editor Error", f"Failed to download '{rrf_path}' from Duet:\n{e}")
        return

    self.current_editing_filepath = rrf_path

    # Ensure editor UI controls are built
    if not hasattr(self, 'fileTextEditor') or self.fileTextEditor is None:
        from fcn_create_gui.tab_editor import build_editor_tab
        build_editor_tab(self)
        if hasattr(self, '_loaded_tabs'):
            self._loaded_tabs.add(4)

    if hasattr(self, 'editorTitleLabel') and self.editorTitleLabel is not None:
        self.editorTitleLabel.setText(f"Editing: {rrf_path}")

    if hasattr(self, 'fileTextEditor') and self.fileTextEditor is not None:
        self.fileTextEditor.setPlainText(text_content)
        self.fileTextEditor.document().setModified(False)

    if hasattr(self, 'editorStatusLabel') and self.editorStatusLabel is not None:
        line_count = len(text_content.splitlines())
        size_kb = len(raw_bytes) / 1024.0
        self.editorStatusLabel.setText(f"Loaded {rrf_path} | {line_count} lines ({size_kb:.1f} KB) | Ready to edit")

    if hasattr(self, 'tabModules') and self.tabModules is not None:
        if hasattr(self, 'tab_editor') and self.tab_editor is not None:
            idx = self.tabModules.indexOf(self.tab_editor)
            if idx >= 0:
                self.tabModules.setCurrentIndex(idx)
            else:
                self.tabModules.setCurrentIndex(4)
        else:
            self.tabModules.setCurrentIndex(4)


def edit_selected_file(self):
    """
    Opens the currently highlighted file on the Files tab in the Editor tab.
    """
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Connection Required", "Duet not connected. Please connect first.")
        return

    indexes = self.fileTreeView.selectedIndexes()
    if not indexes:
        QMessageBox.warning(self, "Selection Required", "Please select a file to edit.")
        return

    index_col0 = indexes[0].siblingAtColumn(0)
    item = self.model.itemFromIndex(index_col0)
    if item is None:
        return

    rel_path = item.data(self.PATH_ROLE)
    is_dir = item.data(self.IS_DIR_ROLE)

    if is_dir:
        QMessageBox.warning(self, "Invalid Selection", "Cannot edit a folder. Please select a file.")
        return

    root_prefix = get_root_prefix(self)
    rrf_path = f"{root_prefix}/{rel_path}"
    open_in_editor(self, rrf_path)


def save_and_upload_editor_file(self):
    """
    Saves and uploads the current text content from the Editor tab back to Duet.
    """
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before saving.")
        return

    rrf_path = getattr(self, 'current_editing_filepath', None)
    if not rrf_path or not hasattr(self, 'fileTextEditor') or self.fileTextEditor is None:
        QMessageBox.warning(self, "Save Error", "No file is currently loaded in the editor.")
        return

    text_content = self.fileTextEditor.toPlainText()
    data_bytes = text_content.encode('utf-8')

    if hasattr(self, 'editorStatusLabel') and self.editorStatusLabel is not None:
        self.editorStatusLabel.setText(f"Uploading '{rrf_path}' to Duet...")

    ip = get_clean_duet_ip(self)
    url = f"http://{ip}/rr_upload"

    fast_was_active = False
    if hasattr(self, 'status_fast_timer') and self.status_fast_timer is not None and self.status_fast_timer.isActive():
        self.status_fast_timer.stop()
        fast_was_active = True

    try:
        from fcn_monitor.fcn_duet import get_shared_session
        get_shared_session().close()

        upload_session = requests.Session()
        upload_session.trust_env = False
        try:
            response = upload_session.post(url, params={'name': rrf_path}, data=data_bytes, timeout=20)
            response.raise_for_status()
        finally:
            upload_session.close()

        import datetime
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        if hasattr(self, 'editorStatusLabel') and self.editorStatusLabel is not None:
            self.editorStatusLabel.setText(f"Saved & uploaded '{rrf_path}' successfully at {now_str}")

        from fcn_control.fcn_control import log_to_duet_console
        log_to_duet_console(self, f"Saved and uploaded '{rrf_path}' to Duet SD card.")

        if hasattr(self, 'fileTextEditor') and self.fileTextEditor is not None:
            self.fileTextEditor.document().setModified(False)

        load_directory(self, getattr(self, 'current_directory', '/'))

        # Check if the saved file is config.g
        if os.path.basename(rrf_path).lower() == "config.g":
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
            
            dlg = QDialog(self)
            dlg.setWindowTitle("Config File Saved")
            dlg.setMinimumWidth(520)
            
            v_layout = QVBoxLayout(dlg)
            v_layout.setContentsMargins(24, 24, 24, 24)
            v_layout.setSpacing(14)

            lbl = QLabel("You edited 'config.g'. How would you like to apply your changes?", dlg)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #111111; margin-bottom: 12px;")
            v_layout.addWidget(lbl)

            btn_run = QPushButton("Run config.g now", dlg)
            btn_run.setMinimumHeight(55)
            btn_run.setStyleSheet("""
                QPushButton {
                    background-color: #2e7d32;
                    color: white;
                    font-weight: bold;
                    font-size: 16px;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #1b5e20;
                }
            """)
            
            btn_reset = QPushButton("Reset mainboard now (M999)", dlg)
            btn_reset.setMinimumHeight(55)
            btn_reset.setStyleSheet("""
                QPushButton {
                    background-color: #d32f2f;
                    color: white;
                    font-weight: bold;
                    font-size: 16px;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #b71c1c;
                }
            """)

            btn_later = QPushButton("Apply on next reboot", dlg)
            btn_later.setMinimumHeight(55)
            btn_later.setStyleSheet("""
                QPushButton {
                    background-color: #616161;
                    color: white;
                    font-weight: bold;
                    font-size: 16px;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #424242;
                }
            """)

            user_choice = ["later"]

            def on_run():
                user_choice[0] = "run"
                dlg.accept()

            def on_reset():
                user_choice[0] = "reset"
                dlg.accept()

            def on_later():
                user_choice[0] = "later"
                dlg.accept()

            btn_run.clicked.connect(on_run)
            btn_reset.clicked.connect(on_reset)
            btn_later.clicked.connect(on_later)

            v_layout.addWidget(btn_run)
            v_layout.addWidget(btn_reset)
            v_layout.addWidget(btn_later)

            dlg.exec()

            choice = user_choice[0]
            if choice == "run":
                duet_request(f"http://{ip}/rr_gcode", params={'gcode': 'M98 P"0:/sys/config.g"'}, timeout=5)
                log_to_duet_console(self, "Executing 'M98 P\"0:/sys/config.g\"'...")
                QMessageBox.information(self, "Config Executed", "Re-running 'config.g' on Duet...")
            elif choice == "reset":
                duet_request(f"http://{ip}/rr_gcode", params={'gcode': 'M999'}, timeout=5)
                log_to_duet_console(self, "Resetting Duet controller (M999)...")
                QMessageBox.information(self, "Mainboard Reset", "Issued M999 reset command to Duet.")
            else:
                log_to_duet_console(self, "Changes saved to config.g. Will take effect on next reboot.")
        else:
            QMessageBox.information(self, "Save Successful", f"File '{os.path.basename(rrf_path)}' saved and uploaded to Duet successfully!")
    except Exception as e:
        if hasattr(self, 'editorStatusLabel') and self.editorStatusLabel is not None:
            self.editorStatusLabel.setText(f"Upload failed: {e}")
        QMessageBox.critical(self, "Save Error", f"Failed to upload '{rrf_path}' to Duet:\n{e}")
    finally:
        if fast_was_active and hasattr(self, 'status_fast_timer') and self.status_fast_timer is not None:
            self.status_fast_timer.start(1000)


def rename_selected_item(self):
    """
    Renames the highlighted file or folder on the Duet SD card using native RRF M471 G-code command.
    """
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before renaming files.")
        return

    indexes = self.fileTreeView.selectedIndexes()
    if not indexes:
        QMessageBox.information(self, "Rename Item", "Please select a file or folder to rename.")
        return

    index = [i for i in indexes if i.column() == 0][0]
    item = self.model.itemFromIndex(index)
    if not item:
        return

    rel_path = item.data(role=self.PATH_ROLE)
    is_dir = item.data(role=self.IS_DIR_ROLE)
    item_name = item.text()

    # Create dialog prompt for new name
    from PySide6.QtWidgets import QInputDialog, QLineEdit
    dialog = QInputDialog(self)
    dialog.setWindowTitle("Rename Item")
    dialog.setLabelText(f"Enter new name for '{item_name}':")
    dialog.setTextValue(item_name)
    dialog.setMinimumWidth(500)
    dialog.setMinimumHeight(180)
    dialog.setStyleSheet("""
        QInputDialog {
            font-size: 16px;
        }
        QLabel {
            font-size: 18px;
            font-weight: bold;
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
    new_name = dialog.textValue().strip()
    if not ok or not new_name or new_name == item_name:
        return

    root_prefix = get_root_prefix(self)
    from_path = f"{root_prefix}/{rel_path}"

    # Get parent folder path
    parent_dir = os.path.dirname(rel_path)
    if parent_dir:
        to_path = f"{root_prefix}/{parent_dir}/{new_name}"
    else:
        to_path = f"{root_prefix}/{new_name}"

    ip = get_clean_duet_ip(self)
    renamed = False

    # 1. Native M471 instant move/rename command
    try:
        res = duet_request(f"http://{ip}/rr_gcode", params={'gcode': f'M471 S"{from_path}" T"{to_path}" D1'}, timeout=5)
        if res.status_code == 200:
            renamed = True
    except Exception:
        pass

    # 2. Fallback to /rr_filemove
    if not renamed:
        try:
            res = duet_request(f"http://{ip}/rr_filemove", params={'old': from_path, 'new': to_path}, timeout=5)
            if res.status_code == 200:
                renamed = True
        except Exception:
            pass

    if renamed:
        from fcn_control.fcn_control import log_to_duet_console
        log_to_duet_console(self, f"Renamed '{item_name}' -> '{new_name}'")
        load_directory(self, getattr(self, 'current_directory', '/'))
    else:
        QMessageBox.warning(self, "Rename Error", f"Failed to rename '{item_name}' to '{new_name}'.")


