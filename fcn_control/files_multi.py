"""
Files tab: select several files at once -- only in the GCODE folder.

* GCODE: the list allows Ctrl / Shift multi-selection; Upload accepts several files in one dialog; Delete removes
  all selected files / folders after one confirmation that lists them.
* Macros and System: single selection, Upload one file, Delete one item, exactly as before (config.g, homing
  files and macros are not bulk-deleted or bulk-replaced by accident).
* Run, Text Editor, Rename, Move, Copy, Download and To Planning act on ONE file: with several selected they ask
  for a single selection instead of silently using one of them (Run would otherwise start the wrong file).
"""
from PySide6.QtWidgets import QAbstractItemView, QMessageBox

GCODE_CATEGORY = "GCODE"


def is_gcode_category(self):
    combo = getattr(self, 'fileCategoryCombo', None)
    if combo is not None:
        return combo.currentText() == GCODE_CATEGORY
    from fcn_control.fcn_filesystem import get_root_prefix
    return get_root_prefix(self) == "0:/gcodes"


def apply_selection_mode(self, *_):
    tree = getattr(self, 'fileTreeView', None)
    if tree is None:
        return
    if is_gcode_category(self):
        tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
    else:
        tree.setSelectionMode(QAbstractItemView.SingleSelection)
        tree.clearSelection()


def install_files_multi(self):
    """Idempotent: selection mode now and on every folder-type change."""
    if getattr(self, 'fileTreeView', None) is None:
        return
    apply_selection_mode(self)
    from fcn_control.files_dragdrop import install_drag_drop
    install_drag_drop(self)
    combo = getattr(self, 'fileCategoryCombo', None)
    if combo is not None and not getattr(self, '_files_multi_combo_hooked', False):
        combo.currentTextChanged.connect(lambda text: apply_selection_mode(self))
        self._files_multi_combo_hooked = True


def selected_items(self):
    """Column-0 items of the selected rows, in list order."""
    tree = getattr(self, 'fileTreeView', None)
    if tree is None or tree.selectionModel() is None:
        return []
    rows = sorted(tree.selectionModel().selectedRows(0), key=lambda ix: ix.row())
    return [it for it in (self.model.itemFromIndex(ix) for ix in rows) if it is not None]


def single_only(self, action_name, fn):
    """Runs fn(self) only when at most one row is selected."""
    n = len(selected_items(self))
    if n > 1:
        QMessageBox.information(self, action_name,
                                f"{n} items are selected. '{action_name}' works on one file: select a single file.")
        return
    fn(self)


def upload(self):
    from fcn_control.upload_multi import upload_files
    upload_files(self, multi=is_gcode_category(self))


def delete_selected_items(self):
    from fcn_control.fcn_filesystem import (delete_remote_path, delete_selected_item, get_clean_duet_ip,
                                            get_root_prefix, load_directory)
    items = selected_items(self)
    if len(items) <= 1 or not is_gcode_category(self):
        delete_selected_item(self)                      # unchanged single delete (with its own checks)
        return
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before deleting files.")
        return

    entries = [(it.text(), it.data(self.PATH_ROLE), bool(it.data(self.IS_DIR_ROLE))) for it in items]
    n_dirs = sum(1 for e in entries if e[2])
    shown = "\n".join(f"  {'[folder] ' if d else ''}{name}" for name, _, d in entries[:20])
    more = f"\n  ... and {len(entries) - 20} more" if len(entries) > 20 else ""
    warn = f"\n\n{n_dirs} folder(s) will be deleted with everything in them." if n_dirs else ""
    reply = QMessageBox.question(self, "Confirm Delete",
                                 f"Delete these {len(entries)} items from the SD card?\n\n{shown}{more}{warn}",
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    if reply != QMessageBox.Yes:
        return

    ip = get_clean_duet_ip(self)
    root = get_root_prefix(self)
    failed = []
    for name, rel, is_dir in entries:
        try:
            ok, code = delete_remote_path(self, ip, f"{root}/{rel}", is_dir)
            if not ok:
                failed.append(f"{name} (HTTP {code})")
        except Exception as e:
            failed.append(f"{name} ({e})")
    load_directory(self, getattr(self, 'current_directory', '/'))
    if failed:
        QMessageBox.warning(self, "Delete",
                            f"Deleted {len(entries) - len(failed)} of {len(entries)}.\nNot deleted:\n  " +
                            "\n  ".join(failed))
