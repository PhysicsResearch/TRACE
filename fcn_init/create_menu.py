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
    
    # Figures
    self.selected_font_size = 14
    self.selected_legend_font_size = 14
    self.selected_legend_on_off = "On"
    self.selected_background = "Transparent"
    self.selected_line_width = 2.0
    self.selected_line_color = "Red" 
    self.selected_point_size = 8
    self.selected_point_color = "Blue"

    styleMenu = self.menuBar().addMenu("Figures")

    # Font Size submenu
    fontSizeMenu = styleMenu.addMenu("Font Size")
    fontSizeGroup = QActionGroup(self)
    fontSizes = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40]
    for size in fontSizes:
        action = QAction(str(size), self, checkable=True)
        if size == self.selected_font_size:
            action.setChecked(True)
        action.triggered.connect(lambda checked, s=size: set_font_size(self,s))
        fontSizeMenu.addAction(action)
        fontSizeGroup.addAction(action)

    # Background submenu
    backgroundMenu = styleMenu.addMenu("Background")
    backgroundGroup = QActionGroup(self)
    backgrounds = ["Transparent", "White"]
    for bg in backgrounds:
        action = QAction(bg, self, checkable=True)
        if bg == self.selected_background:
            action.setChecked(True)
        action.triggered.connect(lambda checked, b=bg: set_background(self,b))
        backgroundMenu.addAction(action)
        backgroundGroup.addAction(action)
        
    # Legend on/off submenu
    legendMenu = styleMenu.addMenu("Legend")
    legendGroup = QActionGroup(self)
    legends = ["On", "Off"]
    for lg in legends:
        action = QAction(lg, self, checkable=True)
        if lg == "On":
            action.setChecked(True)
        action.triggered.connect(lambda checked, l=lg: set_legend_on_off(self,l))
        legendMenu.addAction(action)
        legendGroup.addAction(action)
    
    # Font Size LEgend submenu
    lg_fontSizeMenu = styleMenu.addMenu("Font Size Legend")
    lg_fontSizeGroup = QActionGroup(self)
    fontSizes = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40]
    for size in fontSizes:
        action = QAction(str(size), self, checkable=True)
        if size == self.selected_font_size:
            action.setChecked(True)
        action.triggered.connect(lambda checked, s=size: set_legend_font_size(self,s))
        lg_fontSizeMenu.addAction(action)
        lg_fontSizeGroup.addAction(action)

    # Line Width submenu
    lg_lineWidthMenu = styleMenu.addMenu("Line Width")
    lg_lineWidth     = QActionGroup(self)
    lineWidth        = [0.5, 1, 2, 3, 4, 5, 6]
    for size in lineWidth :
        action = QAction(str(size), self, checkable=True)
        if size == self.selected_line_width:
            action.setChecked(True)
        action.triggered.connect(lambda checked, s=size: set_line_width(self,s))
        lg_lineWidthMenu.addAction(action)
        lg_lineWidth.addAction(action)

    # Line Color submenu
    lg_lineColorMenu = styleMenu.addMenu("Line Color")
    lg_lineColor     = QActionGroup(self)
    lineColors       = ["blue","black","green","red","white"]
    for color in lineColors :
        action = QAction(str(color), self, checkable=True)
        if color == self.selected_line_color:
            action.setChecked(True)
        action.triggered.connect(lambda checked, s=color: set_line_color(self,s))
        lg_lineColorMenu.addAction(action)
        lg_lineColor.addAction(action)

    # Point size submenu
    lg_psizetMenu = styleMenu.addMenu("Point size")
    lg_psize     = QActionGroup(self)
    psize        = [2, 4, 6, 8, 10, 15, 20]
    for size in psize :
        action = QAction(str(size), self, checkable=True)
        if size == self.selected_point_size:
            action.setChecked(True)
        action.triggered.connect(lambda checked, s=size: set_psize(self,s))
        lg_psizetMenu.addAction(action)
        lg_psize.addAction(action)

    # Point Color submenu
    lg_pColorMenu = styleMenu.addMenu("Point Color")
    lg_pColor     = QActionGroup(self)
    lineColors       = ["blue","black","green","red","white"]
    for color in lineColors :
        action = QAction(str(color), self, checkable=True)
        if color == self.selected_point_color:
            action.setChecked(True)
        action.triggered.connect(lambda checked, s=color: set_point_color(self,s))
        lg_pColorMenu.addAction(action)
        lg_pColor.addAction(action)

    # adjust font size:
    apply_font_recursively(menu_bar, f)

    supportAction = QAction("Support", self)
    supportAction.triggered.connect(lambda: show_support_popup(self))
    self.menuBar().addAction(supportAction)

        
def set_font_size(self, size):
    self.selected_font_size = int(size)

def set_legend_font_size(self, size):
    self.selected_legend_font_size = int(size)

def set_background(self, background):
    self.selected_background    = background
    
def set_legend_on_off(self, legend):
    self.selected_legend_on_off = legend

def set_line_width(self, size):
    self.selected_line_width = float(size)

def set_line_color(self, color):
    self.selected_line_color = color

def set_psize(self, size):
    self.selected_point_size = int(size)

def set_p_color(self, color):
    self.selected_point_color = color

def set_point_color(self, color):
    self.selected_point_color = color


def apply_font_recursively(menu: QMenuBar, font: QFont):
    menu.setFont(font)
    for act in menu.actions():
        sub = act.menu()
        if sub is not None:
            apply_font_recursively(sub, font)