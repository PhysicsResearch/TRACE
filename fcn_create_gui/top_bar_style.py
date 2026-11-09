"""
White top bar: the main tab bar strip (Control / Status / Files / Planning / Editor / Log files) and the logo corner
showed the grey window background.  Only that strip is restyled (by object name, so the sub-tab widgets inside the
pages and the page backgrounds keep their own look); the existing tab font / height / selected-tab style is kept.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

TOP_BAR_BG = "#ffffff"
TOP_BAR_LINE = "#cfd8dc"


def style_top_bar(window):
    tw = getattr(window, 'tabModules', None)
    if tw is None:
        return
    if not tw.objectName():
        tw.setObjectName("mainTabModules")
    name = tw.objectName()
    bar = tw.tabBar()
    bar.setObjectName("mainTabBar")
    bar.setAutoFillBackground(False)
    tw.setAttribute(Qt.WA_StyledBackground, True)
    # appended to the existing sheet: the earlier QTabBar::tab rules (font, padding, selected underline) stay
    tw.setStyleSheet(tw.styleSheet() + f"""
        QTabWidget#{name} {{ background: {TOP_BAR_BG}; }}
        QTabWidget#{name}::tab-bar {{ left: 0px; }}
        QTabWidget#{name}::pane {{ border: none; border-top: 1px solid {TOP_BAR_LINE}; top: -1px; }}
        QTabBar#mainTabBar {{ background: {TOP_BAR_BG}; }}
        QTabBar#mainTabBar::tab {{ background: {TOP_BAR_BG}; border: none; }}
        QTabBar#mainTabBar::tab:selected {{ color: #1565c0; border-bottom: 4px solid #1565c0; }}
    """)
    corner = tw.cornerWidget(Qt.TopLeftCorner)
    if isinstance(corner, QWidget):
        corner.setAttribute(Qt.WA_StyledBackground, True)
        corner.setStyleSheet(f"background: {TOP_BAR_BG};")
