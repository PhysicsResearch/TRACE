"""
Keeps the TRACE main window inside the screen's work area (not behind the Windows taskbar).

A QTabWidget asks for the minimum size of its LARGEST page, also while that page is hidden: the Control page (about
1080 px tall) or a Status / Log files page that grew after loading data forced the whole window, on every tab, to be
taller than the work area, so a maximized window ran behind the taskbar and the bottom buttons were hidden.

``fit_tabs_to_current_page`` gives every page except the current one an Ignored size policy, so only the page that
is shown counts for the window's minimum size (QStackedLayout ignores Ignored widgets in its minimum size).  After a
tab change a maximized window is put back on the work area.
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QSizePolicy


def fit_tabs_to_current_page(window, tabwidget=None):
    tw = tabwidget if tabwidget is not None else getattr(window, 'tabModules', None)
    if tw is None:
        return
    original = {}

    def apply(index):
        for i in range(tw.count()):
            page = tw.widget(i)
            if page is None:
                continue
            if page not in original:
                original[page] = QSizePolicy(page.sizePolicy())
            if i == index:
                page.setSizePolicy(original[page])
            else:
                page.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        tw.updateGeometry()
        QTimer.singleShot(0, lambda: keep_on_screen(window))

    tw.currentChanged.connect(apply)
    apply(tw.currentIndex())


def keep_on_screen(window):
    """A maximized window whose frame runs past the screen's work area is fitted back onto it."""
    try:
        if not window.isMaximized():
            return
        screen = window.screen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        if window.frameGeometry().bottom() > avail.bottom() + 8 or window.frameGeometry().right() > avail.right() + 8:
            window.showNormal()
            window.showMaximized()
    except RuntimeError:
        pass        # window already deleted
