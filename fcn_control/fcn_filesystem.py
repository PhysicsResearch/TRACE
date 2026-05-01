
import requests
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon
from PySide6.QtWidgets import QMessageBox, QInputDialog


def setup_file_explorer(self):
    """
    Function to create file explorer tree
    """
    self.model = QStandardItemModel()
    self.model.setHorizontalHeaderLabels(["Name"])

    self.fileTreeView.setModel(self.model)

    self.fileTreeView.setRootIsDecorated(False)
    self.fileTreeView.setStyleSheet("""
    QTreeView::item {
        border-bottom: 1px solid grey; height: 28px;
    }
    """)

    # Load root directory
    load_directory(self, "/")


def get_files_for_dir(self, directory):
    """
    Function to retrieve the contents of a folder on SD card
    """
    url = f"http://{self.duet_ip}/rr_filelist?dir=/gcodes/{directory}"

    try:
        response = requests.get(url, timeout=2)
        response.raise_for_status()
        data = response.json()
        return data.get("files", [])
    except Exception as e:
        print("Error fetching files:", e)
        return []
    

def load_directory(self, directory):
    """
    Function to load a directory and display its contents
    """
    self.current_directory = directory

    root = self.model.invisibleRootItem()
    root.removeRows(0, root.rowCount())

    # Get files/folders in directory
    items = get_files_for_dir(self, directory)

    # Sort to display folders on top
    def sort_key(entry):
        is_dir = entry.get("type") == "d"
        name = entry.get("name", "").lower()
        return (not is_dir, name)
    
    items.sort(key=sort_key)

    # Create entries for files/folders
    for entry in items:
        item = create_item(self, entry, directory)
        root.appendRow(item)


def load_root(self):
    """
    Function to load the file/folder names in base
    """
    root = self.model.invisibleRootItem()
    root.removeRows(0, root.rowCount())

    # Get files/folders in root
    items = get_files_for_dir(self, "/")

    # Create items for files/folder
    for entry in items:
        node = create_item(self, entry, parent_path="/")
        root.appendRow(node)


def create_item(self, entry, parent_path):
    """
    Item helper to create file or folder entry
    """
    # Get name and item type (file/directory)
    name    = entry.get("name", "UNKNOWN")
    is_dir  = entry.get("type") == "d"

    # Build full path
    full_path = parent_path.rstrip("/") + "/" + name

    # Create item
    folder_icon = QIcon.fromTheme("folder")
    file_icon   = QIcon.fromTheme("text-x-generic")

    item = QStandardItem(name)
    item.setText(name)
    item.setIcon(folder_icon if is_dir else file_icon)
    item.setData(full_path, self.PATH_ROLE)
    item.setData(is_dir, self.IS_DIR_ROLE)

    return item


def go_back(self):
    """
    Function to go back one level in the file explorer tree
    """
    if self.current_directory == "/":
        return # Skip if in base directory
    
    parent = "/".join(self.current_directory.rstrip("/").split("/")[:-1])
    if parent == "":
        parent == "/"

    load_directory(self, parent) 


def start_gcode(self, fpath):
    """
    Function to start a gcode file from the file explorer
    """
    # Show a confirmation pop-up
    msg = QMessageBox()
    msg.setWindowTitle('Confirm')
    msg.setText(f"Do you want to start the following GCODE\n{fpath}?")
    msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
    result = msg.exec()

    if result == QMessageBox.StandardButton.Ok:
        try:
            # Send command to start gcode execution
            url = f'http://{self.duet_ip}/rr_gcode?gcode=M32 0:/gcodes{fpath}'
            requests.get(url, timeout=2)

            # Automatically go to Status tab
            self.Tab_index = 1
            self.tabModules.blockSignals(True)
            self.tabModules.setCurrentIndex(self.Tab_index)
            self.tabModules.blockSignals(False)
        except Exception as e:
            QMessageBox.warning(self, "Duet Error", f"Failed to start {fpath} (maybe no connection?)")


def mkdir(self):
    """
    Function to create a new directory in the file explorer
    """
    # Requests folder name from user
    folder_name, ok = QInputDialog.getText(self, 'Create folder', "Enter folder name: ")

    # Create new directory
    if ok and folder_name:
        try:
            url = f'http://{self.duet_ip}/rr_mkdir?dir=/gcodes{self.current_directory.rstrip('/')}/{folder_name}'
            requests.get(url, timeout=2)
        except Exception as e:
            QMessageBox.warning(self, "Duet Error", f"Failed to create folder {folder_name} (maybe no connection?)")
        

def delete_path(self, path):
    """
    Function to delete a single file 
    """

    # Never delete base folder
    if path in ['/', '', ' ', '//']:
        return 

    # Delete file
    try:
        url = f'http://{self.duet_ip}/rr_delete?name=/gcodes{path}'
        requests.get(url, timeout=2)
    except Exception as e:
        QMessageBox.warning(self, "Duet Error", f"Failed to delete {path} (maybe no connection?)")


def delete_recursively(self, path, is_dir):
    """
    Function to delete a folder recursively
    """

    # Show confirmation pop-up (file or folder specific)
    msg = QMessageBox()
    msg.setWindowTitle('Confirm')

    if is_dir:
        msg.setText(f"Are you sure you want to delete the\nfollowing folder AND contents\n{path}")
    else:
        msg.setText(f"Are you sure you want to delete the \nfollowing GCODE file?\n{path}")
    msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)

    result = msg.exec()

    if result == QMessageBox.StandardButton.Ok:
        # Delete recursively if folder
        if is_dir:
            items = get_files_for_dir(self, path)

            for entry in items:
                name = entry.get("name")
                is_dir = entry.get("type") == "d"

                fpath = path.rstrip("/") + "/" + name

                if is_dir:
                    delete_recursively(self, fpath, is_dir)
                
                delete_path(self, fpath)
        # Delete if single path
        delete_path(self, path)

    