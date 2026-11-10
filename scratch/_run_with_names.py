"""Runs a test file with the display-name layer active (DYNAMIQ / KINETIQ on screen)."""
import os, runpy, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"C:\TRACE")
from PySide6.QtWidgets import QApplication
from fcn_create_gui.display_names import prepare_display_names
prepare_display_names()
target = sys.argv[1]
sys.argv = [target] + sys.argv[2:]
runpy.run_path(target, run_name="__main__")
