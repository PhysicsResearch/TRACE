from PySide6.QtWidgets import QMenuBar
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtGui import QFont
from .init_support import show_support_popup

def initializeMenuBar(self):
    # define fontsize
    f = QFont()
    f.setPointSize(11)  
    # Create a menu bar
    menu_bar = QMenuBar(self)
    menu_bar.setFont(f)
    self.setMenuBar(menu_bar)
    
    # Figures variables
    self.selected_font_size = 14
    self.selected_legend_font_size = 14
    self.selected_legend_on_off = "On"
    self.selected_background = "Transparent"
    self.selected_line_width = 2.0
    self.selected_line_color = "Red" 
    self.selected_point_size = 8
    self.selected_point_color = "Blue"

    apply_font_recursively(menu_bar, f)

    supportAction = QAction("Support", self)
    supportAction.triggered.connect(lambda: show_support_popup(self))
    self.menuBar().addAction(supportAction)


def apply_font_recursively(menu: QMenuBar, font: QFont):
    menu.setFont(font)
    for act in menu.actions():
        sub = act.menu()
        if sub is not None:
            apply_font_recursively(sub, font)