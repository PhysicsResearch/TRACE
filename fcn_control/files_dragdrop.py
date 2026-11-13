"""
Files tab: drag files from Explorer onto the file list to upload them to the folder that is shown.

* GCODE: any number of files at once.
* Macros / System: one file per drop, after a confirmation (dropping a config.g or homing file replaces the live one).
* Files that already exist in the folder are only replaced after a confirmation that names them.
* Folders in the drop are skipped (named in the message).  The transfer is upload_multi.upload_paths (file dates kept).
"""
import os

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QMessageBox


def _existing_names(self):
    model = getattr(self, 'model', None)
    if model is None:
        return set()
    return {model.item(r, 0).text() for r in range(model.rowCount()) if model.item(r, 0) is not None
            and not model.item(r, 0).data(self.IS_DIR_ROLE)}


def handle_drop(self, paths):
    from fcn_control.files_multi import is_gcode_category
    from fcn_control.fcn_filesystem import get_root_prefix
    from fcn_control.upload_multi import upload_paths
    files = [p for p in paths if os.path.isfile(p)]
    skipped = [os.path.basename(p.rstrip("/\\")) for p in paths if not os.path.isfile(p)]
    if skipped:
        QMessageBox.information(self, "Upload", "Folders are not uploaded: " + ", ".join(skipped))
    if not files:
        return
    folder = get_root_prefix(self) + ("/" + getattr(self, 'current_directory', '/').strip('/')
                                      if getattr(self, 'current_directory', '/').strip('/') else "")
    if not is_gcode_category(self):
        if len(files) > 1:
            QMessageBox.warning(self, "Upload", f"In {folder} files are uploaded one at a time.\n"
                                                "Several files at once only in the GCODE folder.")
            return
        name = os.path.basename(files[0])
        verb = "replaces the file on the Duet" if name in _existing_names(self) else "is a new file"
        if QMessageBox.question(self, "Upload", f"Upload '{name}' to {folder}?\n({verb})",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
    else:
        clash = sorted(os.path.basename(p) for p in files if os.path.basename(p) in _existing_names(self))
        if clash:
            if QMessageBox.question(self, "Replace files?",
                                    f"{len(clash)} file(s) already exist in {folder} and will be replaced:\n  " +
                                    "\n  ".join(clash[:20]) + ("\n  ..." if len(clash) > 20 else ""),
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return
    upload_paths(self, files)


class _DropFilter(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window

    @staticmethod
    def _local_paths(event):
        md = event.mimeData()
        if md is None or not md.hasUrls():
            return []
        return [u.toLocalFile() for u in md.urls() if u.isLocalFile() and u.toLocalFile()]

    def eventFilter(self, obj, event):
        t = event.type()
        if t in (QEvent.DragEnter, QEvent.DragMove):
            if self._local_paths(event):
                event.acceptProposedAction()
                return True
        elif t == QEvent.Drop:
            paths = self._local_paths(event)
            if paths:
                event.acceptProposedAction()
                handle_drop(self.window, paths)
                return True
        return False


def install_drag_drop(self):
    tree = getattr(self, 'fileTreeView', None)
    if tree is None or getattr(self, '_files_drop_filter', None) is not None:
        return
    tree.setAcceptDrops(True)
    tree.viewport().setAcceptDrops(True)
    self._files_drop_filter = _DropFilter(self)
    tree.viewport().installEventFilter(self._files_drop_filter)
    tree.setToolTip("Drag files here from Explorer to upload them to this folder")
