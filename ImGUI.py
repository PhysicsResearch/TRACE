# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ImGUI.ui'
##
## Created by: Qt User Interface Compiler version 6.10.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QCheckBox, QComboBox,
    QDoubleSpinBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QPushButton, QSizePolicy, QSlider,
    QSpacerItem, QSpinBox, QStatusBar, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QToolButton,
    QTreeView, QWidget)

class Ui_AMIGOpy(object):
    def setupUi(self, AMIGOpy):
        if not AMIGOpy.objectName():
            AMIGOpy.setObjectName(u"AMIGOpy")
        AMIGOpy.resize(1713, 1122)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(AMIGOpy.sizePolicy().hasHeightForWidth())
        AMIGOpy.setSizePolicy(sizePolicy)
        AMIGOpy.setAutoFillBackground(False)
        AMIGOpy.setStyleSheet(u")")
        AMIGOpy.setInputMethodHints(Qt.InputMethodHint.ImhNone)
        self.centralwidget = QWidget(AMIGOpy)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayout_3 = QGridLayout(self.centralwidget)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.tabModules = QTabWidget(self.centralwidget)
        self.tabModules.setObjectName(u"tabModules")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.gridLayout_6 = QGridLayout(self.tab_2)
        self.gridLayout_6.setObjectName(u"gridLayout_6")
        self.gridLayout_24 = QGridLayout()
        self.gridLayout_24.setObjectName(u"gridLayout_24")
        self.tabWidget = QTabWidget(self.tab_2)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.gridLayout_7 = QGridLayout(self.tab)
        self.gridLayout_7.setObjectName(u"gridLayout_7")
        self.POS_DES_D_2 = QLineEdit(self.tab)
        self.POS_DES_D_2.setObjectName(u"POS_DES_D_2")

        self.gridLayout_7.addWidget(self.POS_DES_D_2, 8, 3, 1, 1)

        self.POS_DES_D = QLineEdit(self.tab)
        self.POS_DES_D.setObjectName(u"POS_DES_D")

        self.gridLayout_7.addWidget(self.POS_DES_D, 7, 3, 1, 1)

        self.lineEdit_45 = QLineEdit(self.tab)
        self.lineEdit_45.setObjectName(u"lineEdit_45")
        self.lineEdit_45.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_45, 18, 3, 1, 1)

        self.lineEdit_16 = QLineEdit(self.tab)
        self.lineEdit_16.setObjectName(u"lineEdit_16")
        self.lineEdit_16.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_16, 15, 3, 1, 1)

        self.POS_CURR_X = QLineEdit(self.tab)
        self.POS_CURR_X.setObjectName(u"POS_CURR_X")
        self.POS_CURR_X.setEnabled(False)

        self.gridLayout_7.addWidget(self.POS_CURR_X, 12, 2, 1, 1)

        self.lineEdit_47 = QLineEdit(self.tab)
        self.lineEdit_47.setObjectName(u"lineEdit_47")
        self.lineEdit_47.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_47, 19, 0, 1, 2)

        self.lineEdit_8 = QLineEdit(self.tab)
        self.lineEdit_8.setObjectName(u"lineEdit_8")
        self.lineEdit_8.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_8, 8, 0, 1, 2)

        self.label_10 = QLabel(self.tab)
        self.label_10.setObjectName(u"label_10")
        self.label_10.setAlignment(Qt.AlignmentFlag.AlignBottom|Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft)

        self.gridLayout_7.addWidget(self.label_10, 2, 0, 1, 1)

        self.STEP_Y = QComboBox(self.tab)
        self.STEP_Y.setObjectName(u"STEP_Y")

        self.gridLayout_7.addWidget(self.STEP_Y, 15, 6, 1, 1)

        self.lineEdit_46 = QLineEdit(self.tab)
        self.lineEdit_46.setObjectName(u"lineEdit_46")
        self.lineEdit_46.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_46, 18, 5, 1, 1)

        self.lineEdit_49 = QLineEdit(self.tab)
        self.lineEdit_49.setObjectName(u"lineEdit_49")
        self.lineEdit_49.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_49, 21, 0, 1, 2)

        self.label_15 = QLabel(self.tab)
        self.label_15.setObjectName(u"label_15")
        self.label_15.setAlignment(Qt.AlignmentFlag.AlignBottom|Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft)

        self.gridLayout_7.addWidget(self.label_15, 17, 0, 1, 1)

        self.POS_DES_W = QLineEdit(self.tab)
        self.POS_DES_W.setObjectName(u"POS_DES_W")

        self.gridLayout_7.addWidget(self.POS_DES_W, 13, 3, 1, 1)

        self.MOVE_Y = QPushButton(self.tab)
        self.MOVE_Y.setObjectName(u"MOVE_Y")
        self.MOVE_Y.setStyleSheet(u"background-color: rgb(0, 0, 255)")

        self.gridLayout_7.addWidget(self.MOVE_Y, 15, 0, 1, 1)

        self.lineEdit_15 = QLineEdit(self.tab)
        self.lineEdit_15.setObjectName(u"lineEdit_15")
        self.lineEdit_15.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_15, 11, 2, 1, 1)

        self.lineEdit_14 = QLineEdit(self.tab)
        self.lineEdit_14.setObjectName(u"lineEdit_14")
        self.lineEdit_14.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_14, 11, 0, 1, 2)

        self.MIN_B = QPushButton(self.tab)
        self.MIN_B.setObjectName(u"MIN_B")
        self.MIN_B.setAutoFillBackground(False)
        self.MIN_B.setStyleSheet(u"background-color: rgb(197, 0, 0); color: white")

        self.gridLayout_7.addWidget(self.MIN_B, 6, 5, 1, 1)

        self.comboBox_3 = QComboBox(self.tab)
        self.comboBox_3.setObjectName(u"comboBox_3")

        self.gridLayout_7.addWidget(self.comboBox_3, 18, 6, 1, 1)

        self.POS_CURR_A = QLineEdit(self.tab)
        self.POS_CURR_A.setObjectName(u"POS_CURR_A")
        self.POS_CURR_A.setEnabled(False)

        self.gridLayout_7.addWidget(self.POS_CURR_A, 5, 2, 1, 1)

        self.lineEdit_55 = QLineEdit(self.tab)
        self.lineEdit_55.setObjectName(u"lineEdit_55")

        self.gridLayout_7.addWidget(self.lineEdit_55, 21, 3, 1, 1)

        self.POS_CURR_D = QLineEdit(self.tab)
        self.POS_CURR_D.setObjectName(u"POS_CURR_D")
        self.POS_CURR_D.setEnabled(False)

        self.gridLayout_7.addWidget(self.POS_CURR_D, 8, 2, 1, 1)

        self.verticalSpacer_11 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_7.addItem(self.verticalSpacer_11, 22, 0, 1, 1)

        self.lineEdit_5 = QLineEdit(self.tab)
        self.lineEdit_5.setObjectName(u"lineEdit_5")
        self.lineEdit_5.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_5, 5, 0, 1, 2)

        self.POS_CURR_Y = QLineEdit(self.tab)
        self.POS_CURR_Y.setObjectName(u"POS_CURR_Y")
        self.POS_CURR_Y.setEnabled(False)

        self.gridLayout_7.addWidget(self.POS_CURR_Y, 16, 2, 1, 1)

        self.pushButton_59 = QPushButton(self.tab)
        self.pushButton_59.setObjectName(u"pushButton_59")
        self.pushButton_59.setAutoFillBackground(False)
        self.pushButton_59.setStyleSheet(u"background-color: rgb(0, 170, 0); color: white")

        self.gridLayout_7.addWidget(self.pushButton_59, 21, 6, 1, 1)

        self.lineEdit_13 = QLineEdit(self.tab)
        self.lineEdit_13.setObjectName(u"lineEdit_13")

        self.gridLayout_7.addWidget(self.lineEdit_13, 4, 3, 1, 1)

        self.MIN_W = QPushButton(self.tab)
        self.MIN_W.setObjectName(u"MIN_W")
        self.MIN_W.setAutoFillBackground(False)
        self.MIN_W.setStyleSheet(u"background-color: rgb(197, 0, 0); color: white")

        self.gridLayout_7.addWidget(self.MIN_W, 13, 5, 1, 1)

        self.HOME_X = QPushButton(self.tab)
        self.HOME_X.setObjectName(u"HOME_X")
        self.HOME_X.setStyleSheet(u"background-color: rgb(170, 0, 255)")
        icon = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.GoHome))
        self.HOME_X.setIcon(icon)

        self.gridLayout_7.addWidget(self.HOME_X, 1, 0, 1, 1)

        self.POS_DES_B = QLineEdit(self.tab)
        self.POS_DES_B.setObjectName(u"POS_DES_B")

        self.gridLayout_7.addWidget(self.POS_DES_B, 6, 3, 1, 1)

        self.lineEdit_50 = QLineEdit(self.tab)
        self.lineEdit_50.setObjectName(u"lineEdit_50")
        self.lineEdit_50.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_50, 19, 2, 1, 1)

        self.pushButton_55 = QPushButton(self.tab)
        self.pushButton_55.setObjectName(u"pushButton_55")
        self.pushButton_55.setAutoFillBackground(False)
        self.pushButton_55.setStyleSheet(u"background-color: rgb(197, 0, 0); color: white")

        self.gridLayout_7.addWidget(self.pushButton_55, 20, 5, 1, 1)

        self.PLUS_XAXIS = QPushButton(self.tab)
        self.PLUS_XAXIS.setObjectName(u"PLUS_XAXIS")
        self.PLUS_XAXIS.setStyleSheet(u"background-color: rgb(0, 0, 255); color: white")

        self.gridLayout_7.addWidget(self.PLUS_XAXIS, 11, 6, 1, 1)

        self.lineEdit_23 = QLineEdit(self.tab)
        self.lineEdit_23.setObjectName(u"lineEdit_23")
        self.lineEdit_23.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_23, 16, 0, 1, 2)

        self.MOVE_X = QPushButton(self.tab)
        self.MOVE_X.setObjectName(u"MOVE_X")
        self.MOVE_X.setAutoFillBackground(False)
        self.MOVE_X.setStyleSheet(u"background-color: rgb(0, 0, 255)")
        self.MOVE_X.setFlat(False)

        self.gridLayout_7.addWidget(self.MOVE_X, 10, 0, 1, 1)

        self.pushButton_54 = QPushButton(self.tab)
        self.pushButton_54.setObjectName(u"pushButton_54")
        self.pushButton_54.setAutoFillBackground(False)
        self.pushButton_54.setStyleSheet(u"background-color: rgb(197, 0, 0); color: white")

        self.gridLayout_7.addWidget(self.pushButton_54, 19, 5, 1, 1)

        self.lineEdit_7 = QLineEdit(self.tab)
        self.lineEdit_7.setObjectName(u"lineEdit_7")
        self.lineEdit_7.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_7, 7, 0, 1, 2)

        self.lineEdit_2 = QLineEdit(self.tab)
        self.lineEdit_2.setObjectName(u"lineEdit_2")
        self.lineEdit_2.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_2, 3, 2, 1, 1)

        self.lineEdit_48 = QLineEdit(self.tab)
        self.lineEdit_48.setObjectName(u"lineEdit_48")
        self.lineEdit_48.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_48, 20, 0, 1, 2)

        self.PLUS_X = QPushButton(self.tab)
        self.PLUS_X.setObjectName(u"PLUS_X")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.PLUS_X.sizePolicy().hasHeightForWidth())
        self.PLUS_X.setSizePolicy(sizePolicy1)
        self.PLUS_X.setAutoFillBackground(False)
        self.PLUS_X.setStyleSheet(u"background-color: rgb(0, 170, 0); color: white")

        self.gridLayout_7.addWidget(self.PLUS_X, 12, 6, 1, 1)

        self.lineEdit_10 = QLineEdit(self.tab)
        self.lineEdit_10.setObjectName(u"lineEdit_10")
        self.lineEdit_10.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_10, 15, 2, 1, 1)

        self.lineEdit_3 = QLineEdit(self.tab)
        self.lineEdit_3.setObjectName(u"lineEdit_3")
        self.lineEdit_3.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_3, 3, 3, 1, 1)

        self.PLUS_ZAXIS = QPushButton(self.tab)
        self.PLUS_ZAXIS.setObjectName(u"PLUS_ZAXIS")
        self.PLUS_ZAXIS.setStyleSheet(u"background-color: rgb(0, 0, 255); color: white")

        self.gridLayout_7.addWidget(self.PLUS_ZAXIS, 4, 6, 1, 1)

        self.HOME_Y = QPushButton(self.tab)
        self.HOME_Y.setObjectName(u"HOME_Y")
        self.HOME_Y.setStyleSheet(u"background-color: rgb(170, 0, 255)")
        self.HOME_Y.setIcon(icon)

        self.gridLayout_7.addWidget(self.HOME_Y, 1, 2, 1, 1)

        self.PLUS_A = QPushButton(self.tab)
        self.PLUS_A.setObjectName(u"PLUS_A")
        sizePolicy1.setHeightForWidth(self.PLUS_A.sizePolicy().hasHeightForWidth())
        self.PLUS_A.setSizePolicy(sizePolicy1)
        self.PLUS_A.setAutoFillBackground(False)
        self.PLUS_A.setStyleSheet(u"background-color: rgb(0, 170, 0); color: white")

        self.gridLayout_7.addWidget(self.PLUS_A, 5, 6, 1, 1)

        self.HOME_Z = QPushButton(self.tab)
        self.HOME_Z.setObjectName(u"HOME_Z")
        self.HOME_Z.setAutoFillBackground(False)
        self.HOME_Z.setStyleSheet(u"background-color: rgb(170, 0, 255)")
        self.HOME_Z.setIcon(icon)

        self.gridLayout_7.addWidget(self.HOME_Z, 1, 3, 1, 1)

        self.label_14 = QLabel(self.tab)
        self.label_14.setObjectName(u"label_14")
        self.label_14.setAlignment(Qt.AlignmentFlag.AlignBottom|Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft)

        self.gridLayout_7.addWidget(self.label_14, 14, 0, 1, 1)

        self.lineEdit_66 = QLineEdit(self.tab)
        self.lineEdit_66.setObjectName(u"lineEdit_66")
        self.lineEdit_66.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_66, 10, 2, 1, 1)

        self.PLUS_W = QPushButton(self.tab)
        self.PLUS_W.setObjectName(u"PLUS_W")
        self.PLUS_W.setAutoFillBackground(False)
        self.PLUS_W.setStyleSheet(u"background-color: rgb(0, 170, 0); color: white")

        self.gridLayout_7.addWidget(self.PLUS_W, 13, 6, 1, 1)

        self.lineEdit_22 = QLineEdit(self.tab)
        self.lineEdit_22.setObjectName(u"lineEdit_22")
        self.lineEdit_22.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_22, 15, 5, 1, 1)

        self.lineEdit_51 = QLineEdit(self.tab)
        self.lineEdit_51.setObjectName(u"lineEdit_51")
        self.lineEdit_51.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_51, 20, 2, 1, 1)

        self.pushButton_57 = QPushButton(self.tab)
        self.pushButton_57.setObjectName(u"pushButton_57")
        self.pushButton_57.setAutoFillBackground(False)
        self.pushButton_57.setStyleSheet(u"background-color: rgb(0, 170, 0); color: white")

        self.gridLayout_7.addWidget(self.pushButton_57, 19, 6, 1, 1)

        self.label_13 = QLabel(self.tab)
        self.label_13.setObjectName(u"label_13")
        self.label_13.setAlignment(Qt.AlignmentFlag.AlignBottom|Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft)

        self.gridLayout_7.addWidget(self.label_13, 9, 0, 1, 1)

        self.MIN_XAXIS = QPushButton(self.tab)
        self.MIN_XAXIS.setObjectName(u"MIN_XAXIS")
        self.MIN_XAXIS.setStyleSheet(u"background-color: rgb(255, 0, 255); color: white")

        self.gridLayout_7.addWidget(self.MIN_XAXIS, 11, 5, 1, 1)

        self.POS_DES_A = QLineEdit(self.tab)
        self.POS_DES_A.setObjectName(u"POS_DES_A")

        self.gridLayout_7.addWidget(self.POS_DES_A, 5, 3, 1, 1)

        self.MIN_YAXIS = QPushButton(self.tab)
        self.MIN_YAXIS.setObjectName(u"MIN_YAXIS")
        self.MIN_YAXIS.setAutoFillBackground(False)
        self.MIN_YAXIS.setStyleSheet(u"background-color: rgb(255, 0, 255); color: white")

        self.gridLayout_7.addWidget(self.MIN_YAXIS, 16, 5, 1, 1)

        self.MIN_D = QPushButton(self.tab)
        self.MIN_D.setObjectName(u"MIN_D")
        self.MIN_D.setAutoFillBackground(False)
        self.MIN_D.setStyleSheet(u"background-color: rgb(197, 0, 0); color: white")

        self.gridLayout_7.addWidget(self.MIN_D, 8, 5, 1, 1)

        self.lineEdit_11 = QLineEdit(self.tab)
        self.lineEdit_11.setObjectName(u"lineEdit_11")
        self.lineEdit_11.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_11, 4, 0, 1, 2)

        self.lineEdit_4 = QLineEdit(self.tab)
        self.lineEdit_4.setObjectName(u"lineEdit_4")
        self.lineEdit_4.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_4, 3, 5, 1, 1)

        self.pushButton_56 = QPushButton(self.tab)
        self.pushButton_56.setObjectName(u"pushButton_56")
        self.pushButton_56.setAutoFillBackground(False)
        self.pushButton_56.setStyleSheet(u"background-color: rgb(197, 0, 0); color: white")

        self.gridLayout_7.addWidget(self.pushButton_56, 21, 5, 1, 1)

        self.lineEdit_70 = QLineEdit(self.tab)
        self.lineEdit_70.setObjectName(u"lineEdit_70")
        self.lineEdit_70.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_70, 10, 5, 1, 1)

        self.lineEdit_53 = QLineEdit(self.tab)
        self.lineEdit_53.setObjectName(u"lineEdit_53")

        self.gridLayout_7.addWidget(self.lineEdit_53, 19, 3, 1, 1)

        self.POS_DES_X = QLineEdit(self.tab)
        self.POS_DES_X.setObjectName(u"POS_DES_X")

        self.gridLayout_7.addWidget(self.POS_DES_X, 12, 3, 1, 1)

        self.MIN_X = QPushButton(self.tab)
        self.MIN_X.setObjectName(u"MIN_X")
        sizePolicy1.setHeightForWidth(self.MIN_X.sizePolicy().hasHeightForWidth())
        self.MIN_X.setSizePolicy(sizePolicy1)
        self.MIN_X.setAutoFillBackground(False)
        self.MIN_X.setStyleSheet(u"background-color: rgb(197, 0, 0); ; color: white;")

        self.gridLayout_7.addWidget(self.MIN_X, 12, 5, 1, 1)

        self.lineEdit_9 = QLineEdit(self.tab)
        self.lineEdit_9.setObjectName(u"lineEdit_9")
        self.lineEdit_9.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_9, 13, 0, 1, 2)

        self.lineEdit_65 = QLineEdit(self.tab)
        self.lineEdit_65.setObjectName(u"lineEdit_65")
        self.lineEdit_65.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_65, 10, 3, 1, 1)

        self.PLUS_C = QPushButton(self.tab)
        self.PLUS_C.setObjectName(u"PLUS_C")
        self.PLUS_C.setAutoFillBackground(False)
        self.PLUS_C.setStyleSheet(u"background-color: rgb(0, 170, 0); color: white")

        self.gridLayout_7.addWidget(self.PLUS_C, 7, 6, 1, 1)

        self.STEP_Z = QComboBox(self.tab)
        self.STEP_Z.setObjectName(u"STEP_Z")

        self.gridLayout_7.addWidget(self.STEP_Z, 3, 6, 1, 1)

        self.lineEdit_54 = QLineEdit(self.tab)
        self.lineEdit_54.setObjectName(u"lineEdit_54")

        self.gridLayout_7.addWidget(self.lineEdit_54, 20, 3, 1, 1)

        self.lineEdit_52 = QLineEdit(self.tab)
        self.lineEdit_52.setObjectName(u"lineEdit_52")
        self.lineEdit_52.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_52, 21, 2, 1, 1)

        self.PLUS_D = QPushButton(self.tab)
        self.PLUS_D.setObjectName(u"PLUS_D")
        self.PLUS_D.setAutoFillBackground(False)
        self.PLUS_D.setStyleSheet(u"background-color: rgb(0, 170, 0); color: white")

        self.gridLayout_7.addWidget(self.PLUS_D, 8, 6, 1, 1)

        self.lineEdit = QLineEdit(self.tab)
        self.lineEdit.setObjectName(u"lineEdit")
        self.lineEdit.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit, 12, 0, 1, 2)

        self.PLUS_YAXIS = QPushButton(self.tab)
        self.PLUS_YAXIS.setObjectName(u"PLUS_YAXIS")
        self.PLUS_YAXIS.setAutoFillBackground(False)
        self.PLUS_YAXIS.setStyleSheet(u"background-color: rgb(0, 0, 255); color: white")

        self.gridLayout_7.addWidget(self.PLUS_YAXIS, 16, 6, 1, 1)

        self.pushButton_53 = QPushButton(self.tab)
        self.pushButton_53.setObjectName(u"pushButton_53")
        self.pushButton_53.setAutoFillBackground(False)
        self.pushButton_53.setStyleSheet(u"background-color: rgb(0, 0, 255)")

        self.gridLayout_7.addWidget(self.pushButton_53, 18, 0, 1, 1)

        self.MOVE_Z = QPushButton(self.tab)
        self.MOVE_Z.setObjectName(u"MOVE_Z")
        self.MOVE_Z.setAutoFillBackground(False)
        self.MOVE_Z.setStyleSheet(u"background-color: rgb(0, 0, 255)")
        self.MOVE_Z.setFlat(False)

        self.gridLayout_7.addWidget(self.MOVE_Z, 3, 0, 1, 1)

        self.POS_CURR_W = QLineEdit(self.tab)
        self.POS_CURR_W.setObjectName(u"POS_CURR_W")
        self.POS_CURR_W.setEnabled(False)

        self.gridLayout_7.addWidget(self.POS_CURR_W, 13, 2, 1, 1)

        self.POS_DES_Y = QLineEdit(self.tab)
        self.POS_DES_Y.setObjectName(u"POS_DES_Y")

        self.gridLayout_7.addWidget(self.POS_DES_Y, 16, 3, 1, 1)

        self.STEP_X = QComboBox(self.tab)
        self.STEP_X.setObjectName(u"STEP_X")

        self.gridLayout_7.addWidget(self.STEP_X, 10, 6, 1, 1)

        self.PLUS_B = QPushButton(self.tab)
        self.PLUS_B.setObjectName(u"PLUS_B")
        self.PLUS_B.setAutoFillBackground(False)
        self.PLUS_B.setStyleSheet(u"background-color: rgb(0, 170, 0); color: white")

        self.gridLayout_7.addWidget(self.PLUS_B, 6, 6, 1, 1)

        self.lineEdit_6 = QLineEdit(self.tab)
        self.lineEdit_6.setObjectName(u"lineEdit_6")
        self.lineEdit_6.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_6, 6, 0, 1, 2)

        self.MIN_C = QPushButton(self.tab)
        self.MIN_C.setObjectName(u"MIN_C")
        self.MIN_C.setAutoFillBackground(False)
        self.MIN_C.setStyleSheet(u"background-color: rgb(197, 0, 0); color: white")

        self.gridLayout_7.addWidget(self.MIN_C, 7, 5, 1, 1)

        self.POS_CURR_C = QLineEdit(self.tab)
        self.POS_CURR_C.setObjectName(u"POS_CURR_C")
        self.POS_CURR_C.setEnabled(False)

        self.gridLayout_7.addWidget(self.POS_CURR_C, 7, 2, 1, 1)

        self.lineEdit_12 = QLineEdit(self.tab)
        self.lineEdit_12.setObjectName(u"lineEdit_12")
        self.lineEdit_12.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_12, 4, 2, 1, 1)

        self.label_16 = QLabel(self.tab)
        self.label_16.setObjectName(u"label_16")

        self.gridLayout_7.addWidget(self.label_16, 0, 0, 1, 1)

        self.MIN_ZAXIS = QPushButton(self.tab)
        self.MIN_ZAXIS.setObjectName(u"MIN_ZAXIS")
        self.MIN_ZAXIS.setStyleSheet(u"background-color: rgb(255, 0, 255); color: white")

        self.gridLayout_7.addWidget(self.MIN_ZAXIS, 4, 5, 1, 1)

        self.MIN_A = QPushButton(self.tab)
        self.MIN_A.setObjectName(u"MIN_A")
        sizePolicy1.setHeightForWidth(self.MIN_A.sizePolicy().hasHeightForWidth())
        self.MIN_A.setSizePolicy(sizePolicy1)
        self.MIN_A.setAutoFillBackground(False)
        self.MIN_A.setStyleSheet(u"background-color: rgb(197, 0, 0); ; color: white;")

        self.gridLayout_7.addWidget(self.MIN_A, 5, 5, 1, 1)

        self.pushButton_58 = QPushButton(self.tab)
        self.pushButton_58.setObjectName(u"pushButton_58")
        self.pushButton_58.setAutoFillBackground(False)
        self.pushButton_58.setStyleSheet(u"background-color: rgb(0, 170, 0); color: white")

        self.gridLayout_7.addWidget(self.pushButton_58, 20, 6, 1, 1)

        self.lineEdit_44 = QLineEdit(self.tab)
        self.lineEdit_44.setObjectName(u"lineEdit_44")
        self.lineEdit_44.setEnabled(False)

        self.gridLayout_7.addWidget(self.lineEdit_44, 18, 2, 1, 1)

        self.lineEdit_17 = QLineEdit(self.tab)
        self.lineEdit_17.setObjectName(u"lineEdit_17")

        self.gridLayout_7.addWidget(self.lineEdit_17, 11, 3, 1, 1)

        self.POS_CURR_B = QLineEdit(self.tab)
        self.POS_CURR_B.setObjectName(u"POS_CURR_B")
        self.POS_CURR_B.setEnabled(False)

        self.gridLayout_7.addWidget(self.POS_CURR_B, 6, 2, 1, 1)

        self.line = QFrame(self.tab)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.Shape.VLine)
        self.line.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_7.addWidget(self.line, 3, 4, 6, 1)

        self.line_2 = QFrame(self.tab)
        self.line_2.setObjectName(u"line_2")
        self.line_2.setFrameShape(QFrame.Shape.VLine)
        self.line_2.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_7.addWidget(self.line_2, 10, 4, 4, 1)

        self.line_3 = QFrame(self.tab)
        self.line_3.setObjectName(u"line_3")
        self.line_3.setFrameShape(QFrame.Shape.VLine)
        self.line_3.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_7.addWidget(self.line_3, 15, 4, 2, 1)

        self.line_4 = QFrame(self.tab)
        self.line_4.setObjectName(u"line_4")
        self.line_4.setFrameShape(QFrame.Shape.VLine)
        self.line_4.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_7.addWidget(self.line_4, 18, 4, 4, 1)

        self.gridLayout_7.setColumnStretch(0, 1)
        self.gridLayout_7.setColumnStretch(2, 1)
        self.gridLayout_7.setColumnStretch(3, 1)
        self.gridLayout_7.setColumnStretch(5, 1)
        self.gridLayout_7.setColumnStretch(6, 1)
        self.tabWidget.addTab(self.tab, "")
        self.tab_4 = QWidget()
        self.tab_4.setObjectName(u"tab_4")
        self.gridLayout_25 = QGridLayout(self.tab_4)
        self.gridLayout_25.setObjectName(u"gridLayout_25")
        self.groupBox_11 = QGroupBox(self.tab_4)
        self.groupBox_11.setObjectName(u"groupBox_11")
        self.gridLayout_20 = QGridLayout(self.groupBox_11)
        self.gridLayout_20.setObjectName(u"gridLayout_20")
        self.pushButton_29 = QPushButton(self.groupBox_11)
        self.pushButton_29.setObjectName(u"pushButton_29")
        self.pushButton_29.setAutoFillBackground(False)
        self.pushButton_29.setStyleSheet(u"background-color: rgb(0, 0, 255)")

        self.gridLayout_20.addWidget(self.pushButton_29, 0, 0, 1, 1)

        self.lineEdit_29 = QLineEdit(self.groupBox_11)
        self.lineEdit_29.setObjectName(u"lineEdit_29")
        self.lineEdit_29.setEnabled(False)

        self.gridLayout_20.addWidget(self.lineEdit_29, 0, 1, 1, 1)

        self.lineEdit_30 = QLineEdit(self.groupBox_11)
        self.lineEdit_30.setObjectName(u"lineEdit_30")
        self.lineEdit_30.setEnabled(False)

        self.gridLayout_20.addWidget(self.lineEdit_30, 0, 2, 1, 1)

        self.pushButton_30 = QPushButton(self.groupBox_11)
        self.pushButton_30.setObjectName(u"pushButton_30")
        self.pushButton_30.setAutoFillBackground(False)
        self.pushButton_30.setStyleSheet(u"background-color: rgb(170, 0, 255)")

        self.gridLayout_20.addWidget(self.pushButton_30, 0, 3, 1, 1)

        self.pushButton_36 = QPushButton(self.groupBox_11)
        self.pushButton_36.setObjectName(u"pushButton_36")
        self.pushButton_36.setAutoFillBackground(False)
        self.pushButton_36.setStyleSheet(u"background-color: rgb(0, 0, 255)")

        self.gridLayout_20.addWidget(self.pushButton_36, 0, 4, 1, 1)

        self.lineEdit_41 = QLineEdit(self.groupBox_11)
        self.lineEdit_41.setObjectName(u"lineEdit_41")
        self.lineEdit_41.setEnabled(False)

        self.gridLayout_20.addWidget(self.lineEdit_41, 0, 5, 1, 1)

        self.comboBox_2 = QComboBox(self.groupBox_11)
        self.comboBox_2.setObjectName(u"comboBox_2")

        self.gridLayout_20.addWidget(self.comboBox_2, 0, 6, 1, 1)

        self.lineEdit_24 = QLineEdit(self.groupBox_11)
        self.lineEdit_24.setObjectName(u"lineEdit_24")
        self.lineEdit_24.setEnabled(False)

        self.gridLayout_20.addWidget(self.lineEdit_24, 1, 0, 1, 1)

        self.lineEdit_31 = QLineEdit(self.groupBox_11)
        self.lineEdit_31.setObjectName(u"lineEdit_31")
        self.lineEdit_31.setEnabled(False)

        self.gridLayout_20.addWidget(self.lineEdit_31, 1, 1, 1, 1)

        self.lineEdit_36 = QLineEdit(self.groupBox_11)
        self.lineEdit_36.setObjectName(u"lineEdit_36")

        self.gridLayout_20.addWidget(self.lineEdit_36, 1, 2, 1, 1)

        self.pushButton_31 = QPushButton(self.groupBox_11)
        self.pushButton_31.setObjectName(u"pushButton_31")
        self.pushButton_31.setAutoFillBackground(False)
        self.pushButton_31.setStyleSheet(u"background-color: rgb(73, 0, 109)")

        self.gridLayout_20.addWidget(self.pushButton_31, 1, 3, 1, 1)

        self.pushButton_37 = QPushButton(self.groupBox_11)
        self.pushButton_37.setObjectName(u"pushButton_37")
        self.pushButton_37.setAutoFillBackground(False)
        self.pushButton_37.setStyleSheet(u"background-color: rgb(0, 0, 97)")

        self.gridLayout_20.addWidget(self.pushButton_37, 1, 4, 1, 1)

        self.pushButton_42 = QPushButton(self.groupBox_11)
        self.pushButton_42.setObjectName(u"pushButton_42")
        self.pushButton_42.setAutoFillBackground(False)
        self.pushButton_42.setStyleSheet(u"background-color: rgb(197, 0, 0); color: white")

        self.gridLayout_20.addWidget(self.pushButton_42, 1, 5, 1, 1)

        self.pushButton_47 = QPushButton(self.groupBox_11)
        self.pushButton_47.setObjectName(u"pushButton_47")
        self.pushButton_47.setAutoFillBackground(False)
        self.pushButton_47.setStyleSheet(u"background-color: rgb(0, 170, 0); color: white")

        self.gridLayout_20.addWidget(self.pushButton_47, 1, 6, 1, 1)

        self.lineEdit_25 = QLineEdit(self.groupBox_11)
        self.lineEdit_25.setObjectName(u"lineEdit_25")
        self.lineEdit_25.setEnabled(False)

        self.gridLayout_20.addWidget(self.lineEdit_25, 2, 0, 1, 1)

        self.lineEdit_32 = QLineEdit(self.groupBox_11)
        self.lineEdit_32.setObjectName(u"lineEdit_32")
        self.lineEdit_32.setEnabled(False)

        self.gridLayout_20.addWidget(self.lineEdit_32, 2, 1, 1, 1)

        self.lineEdit_37 = QLineEdit(self.groupBox_11)
        self.lineEdit_37.setObjectName(u"lineEdit_37")

        self.gridLayout_20.addWidget(self.lineEdit_37, 2, 2, 1, 1)

        self.pushButton_32 = QPushButton(self.groupBox_11)
        self.pushButton_32.setObjectName(u"pushButton_32")
        self.pushButton_32.setAutoFillBackground(False)
        self.pushButton_32.setStyleSheet(u"background-color: rgb(73, 0, 109)")

        self.gridLayout_20.addWidget(self.pushButton_32, 2, 3, 1, 1)

        self.pushButton_38 = QPushButton(self.groupBox_11)
        self.pushButton_38.setObjectName(u"pushButton_38")
        self.pushButton_38.setAutoFillBackground(False)
        self.pushButton_38.setStyleSheet(u"background-color: rgb(0, 0, 97)")

        self.gridLayout_20.addWidget(self.pushButton_38, 2, 4, 1, 1)

        self.pushButton_43 = QPushButton(self.groupBox_11)
        self.pushButton_43.setObjectName(u"pushButton_43")
        self.pushButton_43.setAutoFillBackground(False)
        self.pushButton_43.setStyleSheet(u"background-color: rgb(197, 0, 0); color: white")

        self.gridLayout_20.addWidget(self.pushButton_43, 2, 5, 1, 1)

        self.pushButton_48 = QPushButton(self.groupBox_11)
        self.pushButton_48.setObjectName(u"pushButton_48")
        self.pushButton_48.setAutoFillBackground(False)
        self.pushButton_48.setStyleSheet(u"background-color: rgb(0, 170, 0); color: white")

        self.gridLayout_20.addWidget(self.pushButton_48, 2, 6, 1, 1)

        self.lineEdit_26 = QLineEdit(self.groupBox_11)
        self.lineEdit_26.setObjectName(u"lineEdit_26")
        self.lineEdit_26.setEnabled(False)

        self.gridLayout_20.addWidget(self.lineEdit_26, 3, 0, 1, 1)

        self.lineEdit_33 = QLineEdit(self.groupBox_11)
        self.lineEdit_33.setObjectName(u"lineEdit_33")
        self.lineEdit_33.setEnabled(False)

        self.gridLayout_20.addWidget(self.lineEdit_33, 3, 1, 1, 1)

        self.lineEdit_38 = QLineEdit(self.groupBox_11)
        self.lineEdit_38.setObjectName(u"lineEdit_38")

        self.gridLayout_20.addWidget(self.lineEdit_38, 3, 2, 1, 1)

        self.pushButton_33 = QPushButton(self.groupBox_11)
        self.pushButton_33.setObjectName(u"pushButton_33")
        self.pushButton_33.setAutoFillBackground(False)
        self.pushButton_33.setStyleSheet(u"background-color: rgb(73, 0, 109)")

        self.gridLayout_20.addWidget(self.pushButton_33, 3, 3, 1, 1)

        self.pushButton_39 = QPushButton(self.groupBox_11)
        self.pushButton_39.setObjectName(u"pushButton_39")
        self.pushButton_39.setAutoFillBackground(False)
        self.pushButton_39.setStyleSheet(u"background-color: rgb(0, 0, 97)")

        self.gridLayout_20.addWidget(self.pushButton_39, 3, 4, 1, 1)

        self.pushButton_44 = QPushButton(self.groupBox_11)
        self.pushButton_44.setObjectName(u"pushButton_44")
        self.pushButton_44.setAutoFillBackground(False)
        self.pushButton_44.setStyleSheet(u"background-color: rgb(197, 0, 0); color: white")

        self.gridLayout_20.addWidget(self.pushButton_44, 3, 5, 1, 1)

        self.pushButton_49 = QPushButton(self.groupBox_11)
        self.pushButton_49.setObjectName(u"pushButton_49")
        self.pushButton_49.setAutoFillBackground(False)
        self.pushButton_49.setStyleSheet(u"background-color: rgb(0, 170, 0); color: white")

        self.gridLayout_20.addWidget(self.pushButton_49, 3, 6, 1, 1)

        self.lineEdit_27 = QLineEdit(self.groupBox_11)
        self.lineEdit_27.setObjectName(u"lineEdit_27")
        self.lineEdit_27.setEnabled(False)

        self.gridLayout_20.addWidget(self.lineEdit_27, 4, 0, 1, 1)

        self.lineEdit_34 = QLineEdit(self.groupBox_11)
        self.lineEdit_34.setObjectName(u"lineEdit_34")
        self.lineEdit_34.setEnabled(False)

        self.gridLayout_20.addWidget(self.lineEdit_34, 4, 1, 1, 1)

        self.lineEdit_39 = QLineEdit(self.groupBox_11)
        self.lineEdit_39.setObjectName(u"lineEdit_39")

        self.gridLayout_20.addWidget(self.lineEdit_39, 4, 2, 1, 1)

        self.pushButton_34 = QPushButton(self.groupBox_11)
        self.pushButton_34.setObjectName(u"pushButton_34")
        self.pushButton_34.setAutoFillBackground(False)
        self.pushButton_34.setStyleSheet(u"background-color: rgb(73, 0, 109)")

        self.gridLayout_20.addWidget(self.pushButton_34, 4, 3, 1, 1)

        self.pushButton_40 = QPushButton(self.groupBox_11)
        self.pushButton_40.setObjectName(u"pushButton_40")
        self.pushButton_40.setAutoFillBackground(False)
        self.pushButton_40.setStyleSheet(u"background-color: rgb(0, 0, 97)")

        self.gridLayout_20.addWidget(self.pushButton_40, 4, 4, 1, 1)

        self.pushButton_45 = QPushButton(self.groupBox_11)
        self.pushButton_45.setObjectName(u"pushButton_45")
        self.pushButton_45.setAutoFillBackground(False)
        self.pushButton_45.setStyleSheet(u"background-color: rgb(197, 0, 0); color: white")

        self.gridLayout_20.addWidget(self.pushButton_45, 4, 5, 1, 1)

        self.pushButton_50 = QPushButton(self.groupBox_11)
        self.pushButton_50.setObjectName(u"pushButton_50")
        self.pushButton_50.setAutoFillBackground(False)
        self.pushButton_50.setStyleSheet(u"background-color: rgb(0, 170, 0); color: white")

        self.gridLayout_20.addWidget(self.pushButton_50, 4, 6, 1, 1)

        self.lineEdit_28 = QLineEdit(self.groupBox_11)
        self.lineEdit_28.setObjectName(u"lineEdit_28")
        self.lineEdit_28.setEnabled(False)

        self.gridLayout_20.addWidget(self.lineEdit_28, 5, 0, 1, 1)

        self.lineEdit_35 = QLineEdit(self.groupBox_11)
        self.lineEdit_35.setObjectName(u"lineEdit_35")
        self.lineEdit_35.setEnabled(False)

        self.gridLayout_20.addWidget(self.lineEdit_35, 5, 1, 1, 1)

        self.lineEdit_40 = QLineEdit(self.groupBox_11)
        self.lineEdit_40.setObjectName(u"lineEdit_40")

        self.gridLayout_20.addWidget(self.lineEdit_40, 5, 2, 1, 1)

        self.pushButton_35 = QPushButton(self.groupBox_11)
        self.pushButton_35.setObjectName(u"pushButton_35")
        self.pushButton_35.setAutoFillBackground(False)
        self.pushButton_35.setStyleSheet(u"background-color: rgb(73, 0, 109)")

        self.gridLayout_20.addWidget(self.pushButton_35, 5, 3, 1, 1)

        self.pushButton_41 = QPushButton(self.groupBox_11)
        self.pushButton_41.setObjectName(u"pushButton_41")
        self.pushButton_41.setAutoFillBackground(False)
        self.pushButton_41.setStyleSheet(u"background-color: rgb(0, 0, 97)")

        self.gridLayout_20.addWidget(self.pushButton_41, 5, 4, 1, 1)

        self.pushButton_46 = QPushButton(self.groupBox_11)
        self.pushButton_46.setObjectName(u"pushButton_46")
        self.pushButton_46.setAutoFillBackground(False)
        self.pushButton_46.setStyleSheet(u"background-color: rgb(197, 0, 0); color: white")

        self.gridLayout_20.addWidget(self.pushButton_46, 5, 5, 1, 1)

        self.pushButton_51 = QPushButton(self.groupBox_11)
        self.pushButton_51.setObjectName(u"pushButton_51")
        self.pushButton_51.setAutoFillBackground(False)
        self.pushButton_51.setStyleSheet(u"background-color: rgb(0, 170, 0); color: white")

        self.gridLayout_20.addWidget(self.pushButton_51, 5, 6, 1, 1)

        self.gridLayout_20.setColumnStretch(0, 1)
        self.gridLayout_20.setColumnStretch(1, 1)
        self.gridLayout_20.setColumnStretch(2, 1)
        self.gridLayout_20.setColumnStretch(3, 1)
        self.gridLayout_20.setColumnStretch(4, 1)
        self.gridLayout_20.setColumnStretch(5, 1)
        self.gridLayout_20.setColumnStretch(6, 1)

        self.gridLayout_25.addWidget(self.groupBox_11, 0, 0, 1, 1)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_25.addItem(self.verticalSpacer_2, 1, 0, 1, 1)

        self.tabWidget.addTab(self.tab_4, "")

        self.gridLayout_24.addWidget(self.tabWidget, 0, 1, 1, 1)


        self.gridLayout_6.addLayout(self.gridLayout_24, 0, 0, 1, 1)

        self.gridLayout_31 = QGridLayout()
        self.gridLayout_31.setObjectName(u"gridLayout_31")
        self.emergencyButton_1 = QPushButton(self.tab_2)
        self.emergencyButton_1.setObjectName(u"emergencyButton_1")
        self.emergencyButton_1.setMinimumSize(QSize(200, 40))
        self.emergencyButton_1.setMaximumSize(QSize(200, 40))
        self.emergencyButton_1.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.emergencyButton_1.setStyleSheet(u"background-color: rgb(170, 0, 0);\n"
"font: 700 12pt \"Segoe UI\";")
        icon1 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.DialogError))
        self.emergencyButton_1.setIcon(icon1)

        self.gridLayout_31.addWidget(self.emergencyButton_1, 0, 1, 1, 1)

        self.horizontalSpacer_8 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_31.addItem(self.horizontalSpacer_8, 0, 0, 1, 1)

        self.groupBox_3 = QGroupBox(self.tab_2)
        self.groupBox_3.setObjectName(u"groupBox_3")
        self.gridLayout_8 = QGridLayout(self.groupBox_3)
        self.gridLayout_8.setObjectName(u"gridLayout_8")
        self.duet_command = QLineEdit(self.groupBox_3)
        self.duet_command.setObjectName(u"duet_command")

        self.gridLayout_8.addWidget(self.duet_command, 4, 0, 1, 1)

        self.DuetIPAddress = QLineEdit(self.groupBox_3)
        self.DuetIPAddress.setObjectName(u"DuetIPAddress")

        self.gridLayout_8.addWidget(self.DuetIPAddress, 1, 0, 1, 1)

        self.setDuetIP = QPushButton(self.groupBox_3)
        self.setDuetIP.setObjectName(u"setDuetIP")
        icon2 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.NetworkWireless))
        self.setDuetIP.setIcon(icon2)

        self.gridLayout_8.addWidget(self.setDuetIP, 2, 0, 1, 1)

        self.sendCommandDUET = QPushButton(self.groupBox_3)
        self.sendCommandDUET.setObjectName(u"sendCommandDUET")
        icon3 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.DocumentSend))
        self.sendCommandDUET.setIcon(icon3)

        self.gridLayout_8.addWidget(self.sendCommandDUET, 5, 0, 1, 1)

        self.lineEdit_42 = QLineEdit(self.groupBox_3)
        self.lineEdit_42.setObjectName(u"lineEdit_42")
        self.lineEdit_42.setEnabled(False)

        self.gridLayout_8.addWidget(self.lineEdit_42, 0, 0, 1, 1)

        self.connect_status = QLabel(self.groupBox_3)
        self.connect_status.setObjectName(u"connect_status")
        self.connect_status.setStyleSheet(u"QLabel { color: red }")

        self.gridLayout_8.addWidget(self.connect_status, 3, 0, 1, 1)


        self.gridLayout_31.addWidget(self.groupBox_3, 1, 0, 1, 2)

        self.groupBox_12 = QGroupBox(self.tab_2)
        self.groupBox_12.setObjectName(u"groupBox_12")
        self.gridLayout_21 = QGridLayout(self.groupBox_12)
        self.gridLayout_21.setObjectName(u"gridLayout_21")
        self.PhOperFolder = QLineEdit(self.groupBox_12)
        self.PhOperFolder.setObjectName(u"PhOperFolder")

        self.gridLayout_21.addWidget(self.PhOperFolder, 0, 0, 1, 1)

        self.setPhOperFolder = QPushButton(self.groupBox_12)
        self.setPhOperFolder.setObjectName(u"setPhOperFolder")
        icon4 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.FolderOpen))
        self.setPhOperFolder.setIcon(icon4)

        self.gridLayout_21.addWidget(self.setPhOperFolder, 1, 0, 1, 1)


        self.gridLayout_31.addWidget(self.groupBox_12, 2, 0, 1, 2)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_31.addItem(self.verticalSpacer, 3, 0, 1, 2)


        self.gridLayout_6.addLayout(self.gridLayout_31, 0, 1, 1, 1)

        self.gridLayout_6.setColumnStretch(0, 3)
        self.gridLayout_6.setColumnStretch(1, 1)
        self.tabModules.addTab(self.tab_2, "")
        self.tab_status = QWidget()
        self.tab_status.setObjectName(u"tab_status")
        self.gridLayout_22 = QGridLayout(self.tab_status)
        self.gridLayout_22.setObjectName(u"gridLayout_22")
        self.horizontalSpacer_7 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_22.addItem(self.horizontalSpacer_7, 2, 2, 1, 1)

        self.frame = QFrame(self.tab_status)
        self.frame.setObjectName(u"frame")
        self.frame.setStyleSheet(u"border-color: rgb(135, 135, 135);")
        self.frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame.setFrameShadow(QFrame.Shadow.Plain)
        self.gridLayout_18 = QGridLayout(self.frame)
        self.gridLayout_18.setObjectName(u"gridLayout_18")
        self.gridLayout_29 = QGridLayout()
        self.gridLayout_29.setObjectName(u"gridLayout_29")
        self.label_27 = QLabel(self.frame)
        self.label_27.setObjectName(u"label_27")
        self.label_27.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.label_27.setStyleSheet(u"font: italic 12pt \"Segoe UI\";")
        self.label_27.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_29.addWidget(self.label_27, 0, 0, 1, 1)

        self.horizontalSpacer_6 = QSpacerItem(40, 20, QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_29.addItem(self.horizontalSpacer_6, 0, 3, 1, 1)

        self.labelDuetStatus = QLabel(self.frame)
        self.labelDuetStatus.setObjectName(u"labelDuetStatus")
        self.labelDuetStatus.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.labelDuetStatus.setAutoFillBackground(False)
        self.labelDuetStatus.setStyleSheet(u"background-color: rgb(170, 255, 127);\n"
"font: 700 9pt \"Segoe UI\";")
        self.labelDuetStatus.setFrameShape(QFrame.Shape.Box)
        self.labelDuetStatus.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_29.addWidget(self.labelDuetStatus, 0, 1, 1, 1)

        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_29.addItem(self.horizontalSpacer_4, 0, 2, 1, 1)

        self.label_Zprobe = QLabel(self.frame)
        self.label_Zprobe.setObjectName(u"label_Zprobe")
        self.label_Zprobe.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.label_Zprobe.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_29.addWidget(self.label_Zprobe, 6, 1, 1, 3)

        self.label_31 = QLabel(self.frame)
        self.label_31.setObjectName(u"label_31")
        self.label_31.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.label_31.setStyleSheet(u"font: 700 9pt \"Segoe UI\";")
        self.label_31.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_29.addWidget(self.label_31, 5, 1, 1, 3)

        self.gridLayout_30 = QGridLayout()
        self.gridLayout_30.setObjectName(u"gridLayout_30")
        self.label_34 = QLabel(self.frame)
        self.label_34.setObjectName(u"label_34")
        self.label_34.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.label_34.setStyleSheet(u"font: 700 9pt \"Segoe UI\";")
        self.label_34.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_30.addWidget(self.label_34, 0, 0, 1, 1)

        self.label_Ypos = QLabel(self.frame)
        self.label_Ypos.setObjectName(u"label_Ypos")
        self.label_Ypos.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.label_Ypos.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_30.addWidget(self.label_Ypos, 1, 1, 1, 1)

        self.label_Xpos = QLabel(self.frame)
        self.label_Xpos.setObjectName(u"label_Xpos")
        self.label_Xpos.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.label_Xpos.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_30.addWidget(self.label_Xpos, 1, 0, 1, 1)

        self.label_30 = QLabel(self.frame)
        self.label_30.setObjectName(u"label_30")
        self.label_30.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.label_30.setStyleSheet(u"font: 700 9pt \"Segoe UI\";")
        self.label_30.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_30.addWidget(self.label_30, 0, 1, 1, 1)

        self.label_28 = QLabel(self.frame)
        self.label_28.setObjectName(u"label_28")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.label_28.sizePolicy().hasHeightForWidth())
        self.label_28.setSizePolicy(sizePolicy2)
        self.label_28.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.label_28.setStyleSheet(u"font: 700 9pt \"Segoe UI\";")
        self.label_28.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_30.addWidget(self.label_28, 0, 2, 1, 1)

        self.label_Zpos = QLabel(self.frame)
        self.label_Zpos.setObjectName(u"label_Zpos")
        self.label_Zpos.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.label_Zpos.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_30.addWidget(self.label_Zpos, 1, 2, 1, 1)

        self.gridLayout_30.setColumnStretch(0, 1)
        self.gridLayout_30.setColumnStretch(1, 1)
        self.gridLayout_30.setColumnStretch(2, 1)

        self.gridLayout_29.addLayout(self.gridLayout_30, 1, 1, 2, 3)

        self.label_38 = QLabel(self.frame)
        self.label_38.setObjectName(u"label_38")
        self.label_38.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.label_38.setStyleSheet(u"font: 700 9pt \"Segoe UI\";")
        self.label_38.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_29.addWidget(self.label_38, 1, 0, 2, 1)

        self.label_41 = QLabel(self.frame)
        self.label_41.setObjectName(u"label_41")
        self.label_41.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.label_41.setStyleSheet(u"font: 700 9pt \"Segoe UI\";")
        self.label_41.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_29.addWidget(self.label_41, 5, 0, 2, 1)

        self.label_36 = QLabel(self.frame)
        self.label_36.setObjectName(u"label_36")
        self.label_36.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.label_36.setStyleSheet(u"font: 700 9pt \"Segoe UI\";")
        self.label_36.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_29.addWidget(self.label_36, 3, 0, 2, 1)

        self.gridLayout_23 = QGridLayout()
        self.gridLayout_23.setObjectName(u"gridLayout_23")
        self.label_40 = QLabel(self.frame)
        self.label_40.setObjectName(u"label_40")
        sizePolicy2.setHeightForWidth(self.label_40.sizePolicy().hasHeightForWidth())
        self.label_40.setSizePolicy(sizePolicy2)
        self.label_40.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.label_40.setStyleSheet(u"font: 700 9pt \"Segoe UI\";")
        self.label_40.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_23.addWidget(self.label_40, 0, 0, 1, 1)

        self.label_33 = QLabel(self.frame)
        self.label_33.setObjectName(u"label_33")
        self.label_33.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.label_33.setStyleSheet(u"font: 700 9pt \"Segoe UI\";")
        self.label_33.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_23.addWidget(self.label_33, 0, 1, 1, 1)

        self.label_topSpeed = QLabel(self.frame)
        self.label_topSpeed.setObjectName(u"label_topSpeed")
        self.label_topSpeed.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.label_topSpeed.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_23.addWidget(self.label_topSpeed, 1, 1, 1, 1)

        self.label_reqSpeed = QLabel(self.frame)
        self.label_reqSpeed.setObjectName(u"label_reqSpeed")
        self.label_reqSpeed.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.label_reqSpeed.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_23.addWidget(self.label_reqSpeed, 1, 0, 1, 1)

        self.gridLayout_23.setColumnStretch(0, 1)
        self.gridLayout_23.setColumnStretch(1, 1)

        self.gridLayout_29.addLayout(self.gridLayout_23, 3, 1, 2, 3)

        self.gridLayout_29.setColumnStretch(0, 1)
        self.gridLayout_29.setColumnStretch(1, 1)
        self.gridLayout_29.setColumnStretch(2, 1)
        self.gridLayout_29.setColumnStretch(3, 1)

        self.gridLayout_18.addLayout(self.gridLayout_29, 0, 0, 1, 1)


        self.gridLayout_22.addWidget(self.frame, 0, 0, 1, 1)

        self.labelPrintStatus = QLabel(self.tab_status)
        self.labelPrintStatus.setObjectName(u"labelPrintStatus")
        self.labelPrintStatus.setStyleSheet(u"font: 12pt \"Segoe UI\";")
        self.labelPrintStatus.setAlignment(Qt.AlignmentFlag.AlignBottom|Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft)

        self.gridLayout_22.addWidget(self.labelPrintStatus, 1, 0, 1, 1)

        self.verticalSpacer_3 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_22.addItem(self.verticalSpacer_3, 3, 0, 1, 1)

        self.frame_2 = QFrame(self.tab_status)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setAutoFillBackground(False)
        self.frame_2.setStyleSheet(u"border-color: rgb(135, 135, 135);")
        self.frame_2.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Shadow.Plain)
        self.frame_2.setLineWidth(1)
        self.gridLayout_19 = QGridLayout(self.frame_2)
        self.gridLayout_19.setObjectName(u"gridLayout_19")
        self.gridLayout_9 = QGridLayout()
        self.gridLayout_9.setObjectName(u"gridLayout_9")
        self.gcodeCancel = QPushButton(self.frame_2)
        self.gcodeCancel.setObjectName(u"gcodeCancel")
        self.gcodeCancel.setStyleSheet(u"background-color: rgb(255, 117, 117);")
        icon5 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.MediaPlaybackStop))
        self.gcodeCancel.setIcon(icon5)

        self.gridLayout_9.addWidget(self.gcodeCancel, 2, 0, 1, 1)

        self.gcodePause = QPushButton(self.frame_2)
        self.gcodePause.setObjectName(u"gcodePause")
        self.gcodePause.setStyleSheet(u"background-color: rgb(255, 193, 107);")
        icon6 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.MediaPlaybackPause))
        self.gcodePause.setIcon(icon6)

        self.gridLayout_9.addWidget(self.gcodePause, 1, 0, 1, 1)

        self.verticalSpacer_10 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_9.addItem(self.verticalSpacer_10, 3, 0, 1, 1)

        self.label_17 = QLabel(self.frame_2)
        self.label_17.setObjectName(u"label_17")
        self.label_17.setStyleSheet(u"font: italic 12pt \"Segoe UI\";")

        self.gridLayout_9.addWidget(self.label_17, 0, 0, 1, 1)


        self.gridLayout_19.addLayout(self.gridLayout_9, 0, 0, 1, 1)


        self.gridLayout_22.addWidget(self.frame_2, 2, 0, 1, 1)

        self.frame_3 = QFrame(self.tab_status)
        self.frame_3.setObjectName(u"frame_3")
        self.frame_3.setStyleSheet(u"border-color: rgb(135, 135, 135);")
        self.frame_3.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame_3.setFrameShadow(QFrame.Shadow.Plain)
        self.gridLayout_27 = QGridLayout(self.frame_3)
        self.gridLayout_27.setObjectName(u"gridLayout_27")
        self.gridLayout_17 = QGridLayout()
        self.gridLayout_17.setObjectName(u"gridLayout_17")
        self.verticalSpacer_9 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_17.addItem(self.verticalSpacer_9, 3, 0, 1, 1)

        self.minSf = QToolButton(self.frame_3)
        self.minSf.setObjectName(u"minSf")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.minSf.sizePolicy().hasHeightForWidth())
        self.minSf.setSizePolicy(sizePolicy3)
        self.minSf.setMinimumSize(QSize(30, 30))
        self.minSf.setMaximumSize(QSize(30, 30))
        self.minSf.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.minSf.setStyleSheet(u"font: 24pt \"Segoe UI\";")
        self.minSf.setIconSize(QSize(30, 30))

        self.gridLayout_17.addWidget(self.minSf, 2, 0, 1, 1)

        self.plusSf = QToolButton(self.frame_3)
        self.plusSf.setObjectName(u"plusSf")
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.plusSf.sizePolicy().hasHeightForWidth())
        self.plusSf.setSizePolicy(sizePolicy4)
        self.plusSf.setMinimumSize(QSize(20, 20))
        self.plusSf.setMaximumSize(QSize(30, 30))
        self.plusSf.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.plusSf.setStyleSheet(u"font: 24pt \"Segoe UI\";")
        self.plusSf.setIconSize(QSize(20, 20))

        self.gridLayout_17.addWidget(self.plusSf, 2, 2, 1, 1)

        self.sliderSf = QSlider(self.frame_3)
        self.sliderSf.setObjectName(u"sliderSf")
        self.sliderSf.setAcceptDrops(False)
        self.sliderSf.setMinimum(50)
        self.sliderSf.setMaximum(150)
        self.sliderSf.setPageStep(5)
        self.sliderSf.setValue(100)
        self.sliderSf.setOrientation(Qt.Orientation.Horizontal)
        self.sliderSf.setTickPosition(QSlider.TickPosition.NoTicks)

        self.gridLayout_17.addWidget(self.sliderSf, 2, 1, 1, 1)

        self.labelSf = QLabel(self.frame_3)
        self.labelSf.setObjectName(u"labelSf")
        self.labelSf.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_17.addWidget(self.labelSf, 1, 0, 1, 3)

        self.label_18 = QLabel(self.frame_3)
        self.label_18.setObjectName(u"label_18")
        self.label_18.setStyleSheet(u"font: italic 12pt \"Segoe UI\";")

        self.gridLayout_17.addWidget(self.label_18, 0, 0, 1, 3)


        self.gridLayout_27.addLayout(self.gridLayout_17, 0, 0, 1, 1)


        self.gridLayout_22.addWidget(self.frame_3, 2, 1, 1, 1)

        self.gridLayout_28 = QGridLayout()
        self.gridLayout_28.setObjectName(u"gridLayout_28")
        self.emergencyButton_2 = QPushButton(self.tab_status)
        self.emergencyButton_2.setObjectName(u"emergencyButton_2")
        self.emergencyButton_2.setMinimumSize(QSize(200, 40))
        self.emergencyButton_2.setMaximumSize(QSize(200, 40))
        self.emergencyButton_2.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.emergencyButton_2.setStyleSheet(u"background-color: rgb(170, 0, 0);\n"
"font: 700 12pt \"Segoe UI\";")
        self.emergencyButton_2.setIcon(icon1)

        self.gridLayout_28.addWidget(self.emergencyButton_2, 0, 1, 1, 1)

        self.verticalSpacer_12 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_28.addItem(self.verticalSpacer_12, 1, 1, 1, 1)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_28.addItem(self.horizontalSpacer_2, 0, 0, 1, 1)


        self.gridLayout_22.addLayout(self.gridLayout_28, 0, 1, 1, 2)

        self.gridLayout_22.setRowStretch(0, 1)
        self.gridLayout_22.setRowStretch(1, 1)
        self.gridLayout_22.setRowStretch(2, 1)
        self.gridLayout_22.setRowStretch(3, 2)
        self.gridLayout_22.setColumnStretch(0, 1)
        self.gridLayout_22.setColumnStretch(1, 1)
        self.gridLayout_22.setColumnStretch(2, 3)
        self.tabModules.addTab(self.tab_status, "")
        self.tab_files = QWidget()
        self.tab_files.setObjectName(u"tab_files")
        self.gridLayout_26 = QGridLayout(self.tab_files)
        self.gridLayout_26.setObjectName(u"gridLayout_26")
        self.gcodeUpload = QPushButton(self.tab_files)
        self.gcodeUpload.setObjectName(u"gcodeUpload")
        icon7 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.DocumentOpen))
        self.gcodeUpload.setIcon(icon7)

        self.gridLayout_26.addWidget(self.gcodeUpload, 0, 4, 1, 1)

        self.horizontalSpacer_5 = QSpacerItem(596, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_26.addItem(self.horizontalSpacer_5, 0, 1, 1, 1)

        self.fileTreeView = QTreeView(self.tab_files)
        self.fileTreeView.setObjectName(u"fileTreeView")

        self.gridLayout_26.addWidget(self.fileTreeView, 1, 0, 1, 7)

        self.treeViewBack = QPushButton(self.tab_files)
        self.treeViewBack.setObjectName(u"treeViewBack")
        icon8 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.GoUp))
        self.treeViewBack.setIcon(icon8)

        self.gridLayout_26.addWidget(self.treeViewBack, 0, 0, 1, 1)

        self.gcodeRefresh = QPushButton(self.tab_files)
        self.gcodeRefresh.setObjectName(u"gcodeRefresh")
        icon9 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.ViewRefresh))
        self.gcodeRefresh.setIcon(icon9)

        self.gridLayout_26.addWidget(self.gcodeRefresh, 0, 3, 1, 1)

        self.gcodeNewFolder = QPushButton(self.tab_files)
        self.gcodeNewFolder.setObjectName(u"gcodeNewFolder")
        sizePolicy5 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy5.setHorizontalStretch(0)
        sizePolicy5.setVerticalStretch(0)
        sizePolicy5.setHeightForWidth(self.gcodeNewFolder.sizePolicy().hasHeightForWidth())
        self.gcodeNewFolder.setSizePolicy(sizePolicy5)
        self.gcodeNewFolder.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        icon10 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.FolderNew))
        self.gcodeNewFolder.setIcon(icon10)

        self.gridLayout_26.addWidget(self.gcodeNewFolder, 0, 2, 1, 1)

        self.emergencyButton_3 = QPushButton(self.tab_files)
        self.emergencyButton_3.setObjectName(u"emergencyButton_3")
        self.emergencyButton_3.setMinimumSize(QSize(200, 40))
        self.emergencyButton_3.setMaximumSize(QSize(200, 40))
        self.emergencyButton_3.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.emergencyButton_3.setStyleSheet(u"background-color: rgb(170, 0, 0);\n"
"font: 700 12pt \"Segoe UI\";")
        self.emergencyButton_3.setIcon(icon1)

        self.gridLayout_26.addWidget(self.emergencyButton_3, 0, 6, 1, 1)

        self.gridLayout_26.setColumnStretch(0, 1)
        self.gridLayout_26.setColumnStretch(1, 4)
        self.gridLayout_26.setColumnStretch(2, 2)
        self.gridLayout_26.setColumnStretch(3, 2)
        self.gridLayout_26.setColumnStretch(4, 2)
        self.tabModules.addTab(self.tab_files, "")
        self.tab_planning = QWidget()
        self.tab_planning.setObjectName(u"tab_planning")
        self.gridLayout_BrCv = QGridLayout(self.tab_planning)
        self.gridLayout_BrCv.setObjectName(u"gridLayout_BrCv")
        self.tabWidget_BrCv = QTabWidget(self.tab_planning)
        self.tabWidget_BrCv.setObjectName(u"tabWidget_BrCv")
        self.tab_create = QWidget()
        self.tab_create.setObjectName(u"tab_create")
        self.gridLayout = QGridLayout(self.tab_create)
        self.gridLayout.setObjectName(u"gridLayout")
        self.create_plot_view = QWidget(self.tab_create)
        self.create_plot_view.setObjectName(u"create_plot_view")

        self.gridLayout.addWidget(self.create_plot_view, 0, 1, 1, 1)

        self.groupBox_BrCv_createCurve = QGroupBox(self.tab_create)
        self.groupBox_BrCv_createCurve.setObjectName(u"groupBox_BrCv_createCurve")
        self.gridLayout_BrCv_2 = QGridLayout(self.groupBox_BrCv_createCurve)
        self.gridLayout_BrCv_2.setObjectName(u"gridLayout_BrCv_2")
        self.verticalSpacer_BrCv = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_BrCv_2.addItem(self.verticalSpacer_BrCv, 7, 0, 1, 1)

        self.lineEdit_BrCv_2 = QLineEdit(self.groupBox_BrCv_createCurve)
        self.lineEdit_BrCv_2.setObjectName(u"lineEdit_BrCv_2")
        self.lineEdit_BrCv_2.setEnabled(False)

        self.gridLayout_BrCv_2.addWidget(self.lineEdit_BrCv_2, 1, 0, 1, 1)

        self.create_curve_type = QComboBox(self.groupBox_BrCv_createCurve)
        self.create_curve_type.setObjectName(u"create_curve_type")

        self.gridLayout_BrCv_2.addWidget(self.create_curve_type, 0, 1, 1, 4)

        self.lineEdit_BrCv_4 = QLineEdit(self.groupBox_BrCv_createCurve)
        self.lineEdit_BrCv_4.setObjectName(u"lineEdit_BrCv_4")
        self.lineEdit_BrCv_4.setEnabled(False)

        self.gridLayout_BrCv_2.addWidget(self.lineEdit_BrCv_4, 0, 0, 1, 1)

        self.create_table = QTableWidget(self.groupBox_BrCv_createCurve)
        self.create_table.setObjectName(u"create_table")

        self.gridLayout_BrCv_2.addWidget(self.create_table, 4, 0, 1, 5)

        self.create_remove_row = QPushButton(self.groupBox_BrCv_createCurve)
        self.create_remove_row.setObjectName(u"create_remove_row")
        icon11 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.ListRemove))
        self.create_remove_row.setIcon(icon11)

        self.gridLayout_BrCv_2.addWidget(self.create_remove_row, 2, 3, 1, 1)

        self.create_sample_freq = QSpinBox(self.groupBox_BrCv_createCurve)
        self.create_sample_freq.setObjectName(u"create_sample_freq")
        self.create_sample_freq.setValue(25)

        self.gridLayout_BrCv_2.addWidget(self.create_sample_freq, 1, 1, 1, 4)

        self.create_add_row = QPushButton(self.groupBox_BrCv_createCurve)
        self.create_add_row.setObjectName(u"create_add_row")
        icon12 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.ListAdd))
        self.create_add_row.setIcon(icon12)

        self.gridLayout_BrCv_2.addWidget(self.create_add_row, 2, 1, 1, 2)

        self.button_create_curve = QPushButton(self.groupBox_BrCv_createCurve)
        self.button_create_curve.setObjectName(u"button_create_curve")
        self.button_create_curve.setIcon(icon3)

        self.gridLayout_BrCv_2.addWidget(self.button_create_curve, 5, 1, 1, 3)

        self.gridLayout_BrCv_2.setRowStretch(0, 1)
        self.gridLayout_BrCv_2.setColumnStretch(0, 3)

        self.gridLayout.addWidget(self.groupBox_BrCv_createCurve, 0, 0, 3, 1)

        self.create_table_view = QTableWidget(self.tab_create)
        self.create_table_view.setObjectName(u"create_table_view")

        self.gridLayout.addWidget(self.create_table_view, 1, 1, 1, 1)

        self.gridLayout.setRowStretch(0, 1)
        self.gridLayout.setRowStretch(1, 1)
        self.gridLayout.setColumnStretch(0, 1)
        self.gridLayout.setColumnStretch(1, 2)
        self.tabWidget_BrCv.addTab(self.tab_create, "")
        self.tab_import = QWidget()
        self.tab_import.setObjectName(u"tab_import")
        self.gridLayout_BrCv_1 = QGridLayout(self.tab_import)
        self.gridLayout_BrCv_1.setObjectName(u"gridLayout_BrCv_1")
        self.import_horizontal_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_BrCv_1.addItem(self.import_horizontal_spacer, 2, 1, 1, 1)

        self.groupBox_BrCv_importCSV = QGroupBox(self.tab_import)
        self.groupBox_BrCv_importCSV.setObjectName(u"groupBox_BrCv_importCSV")
        self.gridLayout_BrCv_3 = QGridLayout(self.groupBox_BrCv_importCSV)
        self.gridLayout_BrCv_3.setObjectName(u"gridLayout_BrCv_3")
        self.lineEdit_delimiter = QLineEdit(self.groupBox_BrCv_importCSV)
        self.lineEdit_delimiter.setObjectName(u"lineEdit_delimiter")
        self.lineEdit_delimiter.setEnabled(False)

        self.gridLayout_BrCv_3.addWidget(self.lineEdit_delimiter, 0, 0, 1, 1)

        self.import_delimiter = QComboBox(self.groupBox_BrCv_importCSV)
        self.import_delimiter.setObjectName(u"import_delimiter")

        self.gridLayout_BrCv_3.addWidget(self.import_delimiter, 0, 1, 1, 1)

        self.import_header_line = QSpinBox(self.groupBox_BrCv_importCSV)
        self.import_header_line.setObjectName(u"import_header_line")
        self.import_header_line.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        self.import_header_line.setValue(4)

        self.gridLayout_BrCv_3.addWidget(self.import_header_line, 1, 1, 1, 1)

        self.import_skip_lines = QSpinBox(self.groupBox_BrCv_importCSV)
        self.import_skip_lines.setObjectName(u"import_skip_lines")
        self.import_skip_lines.setValue(10)

        self.gridLayout_BrCv_3.addWidget(self.import_skip_lines, 2, 1, 1, 1)

        self.lineEdit_skip_lines = QLineEdit(self.groupBox_BrCv_importCSV)
        self.lineEdit_skip_lines.setObjectName(u"lineEdit_skip_lines")
        self.lineEdit_skip_lines.setEnabled(False)

        self.gridLayout_BrCv_3.addWidget(self.lineEdit_skip_lines, 2, 0, 1, 1)

        self.import_vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_BrCv_3.addItem(self.import_vertical_spacer, 6, 1, 1, 1)

        self.lineEdit_header_line = QLineEdit(self.groupBox_BrCv_importCSV)
        self.lineEdit_header_line.setObjectName(u"lineEdit_header_line")
        self.lineEdit_header_line.setEnabled(False)

        self.gridLayout_BrCv_3.addWidget(self.lineEdit_header_line, 1, 0, 1, 1)

        self.import_flip = QCheckBox(self.groupBox_BrCv_importCSV)
        self.import_flip.setObjectName(u"import_flip")
        self.import_flip.setEnabled(True)
        self.import_flip.setChecked(True)

        self.gridLayout_BrCv_3.addWidget(self.import_flip, 4, 1, 1, 1)

        self.import_button = QPushButton(self.groupBox_BrCv_importCSV)
        self.import_button.setObjectName(u"import_button")

        self.gridLayout_BrCv_3.addWidget(self.import_button, 5, 1, 1, 1)

        self.lineEdit_time_unit = QLineEdit(self.groupBox_BrCv_importCSV)
        self.lineEdit_time_unit.setObjectName(u"lineEdit_time_unit")
        self.lineEdit_time_unit.setEnabled(False)

        self.gridLayout_BrCv_3.addWidget(self.lineEdit_time_unit, 3, 0, 1, 1)

        self.import_time_unit = QComboBox(self.groupBox_BrCv_importCSV)
        self.import_time_unit.setObjectName(u"import_time_unit")

        self.gridLayout_BrCv_3.addWidget(self.import_time_unit, 3, 1, 1, 1)

        self.gridLayout_BrCv_3.setColumnStretch(0, 2)
        self.gridLayout_BrCv_3.setColumnStretch(1, 1)

        self.gridLayout_BrCv_1.addWidget(self.groupBox_BrCv_importCSV, 2, 0, 1, 1)

        self.import_horizontal_layout = QHBoxLayout()
        self.import_horizontal_layout.setObjectName(u"import_horizontal_layout")
        self.import_table_view = QTableWidget(self.tab_import)
        self.import_table_view.setObjectName(u"import_table_view")

        self.import_horizontal_layout.addWidget(self.import_table_view)

        self.import_text_view = QTextEdit(self.tab_import)
        self.import_text_view.setObjectName(u"import_text_view")

        self.import_horizontal_layout.addWidget(self.import_text_view)

        self.import_horizontal_layout.setStretch(0, 2)
        self.import_horizontal_layout.setStretch(1, 1)

        self.gridLayout_BrCv_1.addLayout(self.import_horizontal_layout, 0, 0, 1, 2)

        self.gridLayout_BrCv_1.setRowStretch(0, 2)
        self.gridLayout_BrCv_1.setColumnStretch(0, 1)
        self.gridLayout_BrCv_1.setColumnStretch(1, 2)
        self.tabWidget_BrCv.addTab(self.tab_import, "")
        self.tab_edit = QWidget()
        self.tab_edit.setObjectName(u"tab_edit")
        self.gridLayout_BrCv_edit = QGridLayout(self.tab_edit)
        self.gridLayout_BrCv_edit.setObjectName(u"gridLayout_BrCv_edit")
        self.gridLayout_BrCv_6 = QGridLayout()
        self.gridLayout_BrCv_6.setObjectName(u"gridLayout_BrCv_6")
        self.edit_undo = QPushButton(self.tab_edit)
        self.edit_undo.setObjectName(u"edit_undo")
        icon13 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.EditUndo))
        self.edit_undo.setIcon(icon13)

        self.gridLayout_BrCv_6.addWidget(self.edit_undo, 4, 1, 1, 2)

        self.groupBox_drift = QGroupBox(self.tab_edit)
        self.groupBox_drift.setObjectName(u"groupBox_drift")
        self.gridLayout_2 = QGridLayout(self.groupBox_drift)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.button_add_drift = QPushButton(self.groupBox_drift)
        self.button_add_drift.setObjectName(u"button_add_drift")

        self.gridLayout_2.addWidget(self.button_add_drift, 1, 0, 1, 1)

        self.button_remove_drift = QPushButton(self.groupBox_drift)
        self.button_remove_drift.setObjectName(u"button_remove_drift")

        self.gridLayout_2.addWidget(self.button_remove_drift, 0, 0, 1, 1)

        self.value_drift = QDoubleSpinBox(self.groupBox_drift)
        self.value_drift.setObjectName(u"value_drift")
        self.value_drift.setMinimum(-99.000000000000000)
        self.value_drift.setMaximum(99.000000000000000)

        self.gridLayout_2.addWidget(self.value_drift, 1, 1, 1, 1)


        self.gridLayout_BrCv_6.addWidget(self.groupBox_drift, 2, 1, 1, 2)

        self.breathhold_BrCv = QGroupBox(self.tab_edit)
        self.breathhold_BrCv.setObjectName(u"breathhold_BrCv")
        self.gridLayout_BrCv_8 = QGridLayout(self.breathhold_BrCv)
        self.gridLayout_BrCv_8.setObjectName(u"gridLayout_BrCv_8")
        self.breathholdDuration = QDoubleSpinBox(self.breathhold_BrCv)
        self.breathholdDuration.setObjectName(u"breathholdDuration")

        self.gridLayout_BrCv_8.addWidget(self.breathholdDuration, 1, 1, 1, 1)

        self.button_breath_hold = QPushButton(self.breathhold_BrCv)
        self.button_breath_hold.setObjectName(u"button_breath_hold")

        self.gridLayout_BrCv_8.addWidget(self.button_breath_hold, 1, 0, 1, 1)

        self.closest_max = QCheckBox(self.breathhold_BrCv)
        self.closest_max.setObjectName(u"closest_max")

        self.gridLayout_BrCv_8.addWidget(self.closest_max, 0, 0, 1, 1)

        self.closest_min = QCheckBox(self.breathhold_BrCv)
        self.closest_min.setObjectName(u"closest_min")

        self.gridLayout_BrCv_8.addWidget(self.closest_min, 0, 1, 1, 1)

        self.gridLayout_BrCv_8.setColumnStretch(0, 1)
        self.gridLayout_BrCv_8.setColumnStretch(1, 1)

        self.gridLayout_BrCv_6.addWidget(self.breathhold_BrCv, 1, 1, 1, 2)

        self.line_BrCv = QFrame(self.tab_edit)
        self.line_BrCv.setObjectName(u"line_BrCv")
        self.line_BrCv.setFrameShape(QFrame.Shape.HLine)
        self.line_BrCv.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_BrCv_6.addWidget(self.line_BrCv, 6, 1, 1, 2)

        self.groupBox_operations = QGroupBox(self.tab_edit)
        self.groupBox_operations.setObjectName(u"groupBox_operations")
        self.gridLayout_4 = QGridLayout(self.groupBox_operations)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.button_scale_ampl = QPushButton(self.groupBox_operations)
        self.button_scale_ampl.setObjectName(u"button_scale_ampl")
        sizePolicy1.setHeightForWidth(self.button_scale_ampl.sizePolicy().hasHeightForWidth())
        self.button_scale_ampl.setSizePolicy(sizePolicy1)

        self.gridLayout_4.addWidget(self.button_scale_ampl, 0, 0, 1, 1)

        self.value_freq_sf = QDoubleSpinBox(self.groupBox_operations)
        self.value_freq_sf.setObjectName(u"value_freq_sf")
        self.value_freq_sf.setValue(1.000000000000000)

        self.gridLayout_4.addWidget(self.value_freq_sf, 3, 1, 1, 1)

        self.button_shift_ampl = QPushButton(self.groupBox_operations)
        self.button_shift_ampl.setObjectName(u"button_shift_ampl")

        self.gridLayout_4.addWidget(self.button_shift_ampl, 1, 0, 1, 1)

        self.button_scale_freq = QPushButton(self.groupBox_operations)
        self.button_scale_freq.setObjectName(u"button_scale_freq")

        self.gridLayout_4.addWidget(self.button_scale_freq, 3, 0, 1, 1)

        self.value_ampl_shift = QDoubleSpinBox(self.groupBox_operations)
        self.value_ampl_shift.setObjectName(u"value_ampl_shift")
        self.value_ampl_shift.setMinimum(-99.000000000000000)
        self.value_ampl_shift.setMaximum(99.000000000000000)
        self.value_ampl_shift.setValue(0.000000000000000)

        self.gridLayout_4.addWidget(self.value_ampl_shift, 1, 1, 1, 1)

        self.value_ampl_sf = QDoubleSpinBox(self.groupBox_operations)
        self.value_ampl_sf.setObjectName(u"value_ampl_sf")
        self.value_ampl_sf.setMinimum(0.000000000000000)
        self.value_ampl_sf.setMaximum(99.000000000000000)
        self.value_ampl_sf.setValue(1.000000000000000)

        self.gridLayout_4.addWidget(self.value_ampl_sf, 0, 1, 1, 1)

        self.button_zero_ampl = QPushButton(self.groupBox_operations)
        self.button_zero_ampl.setObjectName(u"button_zero_ampl")

        self.gridLayout_4.addWidget(self.button_zero_ampl, 2, 0, 1, 1)

        self.button_clip_ampl = QPushButton(self.groupBox_operations)
        self.button_clip_ampl.setObjectName(u"button_clip_ampl")

        self.gridLayout_4.addWidget(self.button_clip_ampl, 4, 0, 1, 1)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.value_ampl_min = QDoubleSpinBox(self.groupBox_operations)
        self.value_ampl_min.setObjectName(u"value_ampl_min")

        self.horizontalLayout.addWidget(self.value_ampl_min)

        self.value_ampl_max = QDoubleSpinBox(self.groupBox_operations)
        self.value_ampl_max.setObjectName(u"value_ampl_max")
        self.value_ampl_max.setValue(39.000000000000000)

        self.horizontalLayout.addWidget(self.value_ampl_max)


        self.gridLayout_4.addLayout(self.horizontalLayout, 4, 1, 1, 1)

        self.gridLayout_4.setColumnStretch(0, 1)
        self.gridLayout_4.setColumnStretch(1, 1)

        self.gridLayout_BrCv_6.addWidget(self.groupBox_operations, 0, 1, 1, 1)

        self.verticalSpacer_BrCv_4 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_BrCv_6.addItem(self.verticalSpacer_BrCv_4, 10, 1, 1, 2)

        self.groupBox_smoothing = QGroupBox(self.tab_edit)
        self.groupBox_smoothing.setObjectName(u"groupBox_smoothing")
        self.gridLayout_77 = QGridLayout(self.groupBox_smoothing)
        self.gridLayout_77.setObjectName(u"gridLayout_77")
        self.threshFourierValue = QLineEdit(self.groupBox_smoothing)
        self.threshFourierValue.setObjectName(u"threshFourierValue")
        self.threshFourierValue.setEnabled(False)

        self.gridLayout_77.addWidget(self.threshFourierValue, 6, 1, 1, 1)

        self.smooth_kernel = QSpinBox(self.groupBox_smoothing)
        self.smooth_kernel.setObjectName(u"smooth_kernel")
        self.smooth_kernel.setValue(5)

        self.gridLayout_77.addWidget(self.smooth_kernel, 4, 1, 1, 1)

        self.smooth_method = QComboBox(self.groupBox_smoothing)
        self.smooth_method.setObjectName(u"smooth_method")

        self.gridLayout_77.addWidget(self.smooth_method, 2, 1, 1, 1)

        self.lineEdit_78 = QLineEdit(self.groupBox_smoothing)
        self.lineEdit_78.setObjectName(u"lineEdit_78")
        self.lineEdit_78.setEnabled(False)
        sizePolicy6 = QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        sizePolicy6.setHorizontalStretch(0)
        sizePolicy6.setVerticalStretch(0)
        sizePolicy6.setHeightForWidth(self.lineEdit_78.sizePolicy().hasHeightForWidth())
        self.lineEdit_78.setSizePolicy(sizePolicy6)

        self.gridLayout_77.addWidget(self.lineEdit_78, 2, 2, 1, 2)

        self.lineEdit_79 = QLineEdit(self.groupBox_smoothing)
        self.lineEdit_79.setObjectName(u"lineEdit_79")
        self.lineEdit_79.setEnabled(False)
        sizePolicy6.setHeightForWidth(self.lineEdit_79.sizePolicy().hasHeightForWidth())
        self.lineEdit_79.setSizePolicy(sizePolicy6)

        self.gridLayout_77.addWidget(self.lineEdit_79, 4, 2, 1, 2)

        self.lineEdit_81 = QLineEdit(self.groupBox_smoothing)
        self.lineEdit_81.setObjectName(u"lineEdit_81")
        self.lineEdit_81.setEnabled(False)
        sizePolicy6.setHeightForWidth(self.lineEdit_81.sizePolicy().hasHeightForWidth())
        self.lineEdit_81.setSizePolicy(sizePolicy6)

        self.gridLayout_77.addWidget(self.lineEdit_81, 6, 2, 1, 2)

        self.button_apply_smooth = QPushButton(self.groupBox_smoothing)
        self.button_apply_smooth.setObjectName(u"button_apply_smooth")

        self.gridLayout_77.addWidget(self.button_apply_smooth, 9, 1, 1, 1)

        self.threshFourierSlider = QSlider(self.groupBox_smoothing)
        self.threshFourierSlider.setObjectName(u"threshFourierSlider")
        sizePolicy1.setHeightForWidth(self.threshFourierSlider.sizePolicy().hasHeightForWidth())
        self.threshFourierSlider.setSizePolicy(sizePolicy1)
        self.threshFourierSlider.setOrientation(Qt.Orientation.Horizontal)

        self.gridLayout_77.addWidget(self.threshFourierSlider, 8, 1, 1, 2)

        self.gridLayout_77.setColumnStretch(1, 1)
        self.gridLayout_77.setColumnStretch(2, 1)

        self.gridLayout_BrCv_6.addWidget(self.groupBox_smoothing, 7, 1, 1, 1)


        self.gridLayout_BrCv_edit.addLayout(self.gridLayout_BrCv_6, 0, 0, 1, 1)

        self.gridLayout_BrCv_10 = QGridLayout()
        self.gridLayout_BrCv_10.setObjectName(u"gridLayout_BrCv_10")
        self.edit_ax_view = QWidget(self.tab_edit)
        self.edit_ax_view.setObjectName(u"edit_ax_view")

        self.gridLayout_BrCv_10.addWidget(self.edit_ax_view, 0, 0, 1, 2)

        self.lineEdit_BrCv_25 = QLineEdit(self.tab_edit)
        self.lineEdit_BrCv_25.setObjectName(u"lineEdit_BrCv_25")
        self.lineEdit_BrCv_25.setEnabled(False)

        self.gridLayout_BrCv_10.addWidget(self.lineEdit_BrCv_25, 1, 0, 1, 1)

        self.slider_edit_xmin = QSlider(self.tab_edit)
        self.slider_edit_xmin.setObjectName(u"slider_edit_xmin")
        self.slider_edit_xmin.setMaximum(999999)
        self.slider_edit_xmin.setOrientation(Qt.Orientation.Horizontal)

        self.gridLayout_BrCv_10.addWidget(self.slider_edit_xmin, 1, 1, 1, 1)

        self.button_clip_cycles = QPushButton(self.tab_edit)
        self.button_clip_cycles.setObjectName(u"button_clip_cycles")
        icon14 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.EditCut))
        self.button_clip_cycles.setIcon(icon14)

        self.gridLayout_BrCv_10.addWidget(self.button_clip_cycles, 3, 0, 1, 1)

        self.lineEdit_BrCv_26 = QLineEdit(self.tab_edit)
        self.lineEdit_BrCv_26.setObjectName(u"lineEdit_BrCv_26")
        self.lineEdit_BrCv_26.setEnabled(False)

        self.gridLayout_BrCv_10.addWidget(self.lineEdit_BrCv_26, 2, 0, 1, 1)

        self.verticalSpacer_BrCv_6 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_BrCv_10.addItem(self.verticalSpacer_BrCv_6, 5, 0, 1, 1)

        self.slider_edit_xmax = QSlider(self.tab_edit)
        self.slider_edit_xmax.setObjectName(u"slider_edit_xmax")
        self.slider_edit_xmax.setMaximum(999999)
        self.slider_edit_xmax.setOrientation(Qt.Orientation.Horizontal)

        self.gridLayout_BrCv_10.addWidget(self.slider_edit_xmax, 2, 1, 1, 1)

        self.gridLayout_BrCv_10.setRowStretch(0, 3)
        self.gridLayout_BrCv_10.setRowStretch(5, 2)
        self.gridLayout_BrCv_10.setColumnStretch(0, 1)
        self.gridLayout_BrCv_10.setColumnStretch(1, 3)

        self.gridLayout_BrCv_edit.addLayout(self.gridLayout_BrCv_10, 0, 1, 1, 1)

        self.gridLayout_BrCv_edit.setColumnStretch(0, 2)
        self.gridLayout_BrCv_edit.setColumnStretch(1, 5)
        self.tabWidget_BrCv.addTab(self.tab_edit, "")
        self.tab_export = QWidget()
        self.tab_export.setObjectName(u"tab_export")
        self.gridLayout_5 = QGridLayout(self.tab_export)
        self.gridLayout_5.setObjectName(u"gridLayout_5")
        self.groupBox_7 = QGroupBox(self.tab_export)
        self.groupBox_7.setObjectName(u"groupBox_7")
        self.gridLayout_16 = QGridLayout(self.groupBox_7)
        self.gridLayout_16.setObjectName(u"gridLayout_16")
        self.lineEdit_43 = QLineEdit(self.groupBox_7)
        self.lineEdit_43.setObjectName(u"lineEdit_43")
        self.lineEdit_43.setEnabled(False)

        self.gridLayout_16.addWidget(self.lineEdit_43, 1, 0, 1, 1)

        self.lineEdit_60 = QLineEdit(self.groupBox_7)
        self.lineEdit_60.setObjectName(u"lineEdit_60")
        self.lineEdit_60.setEnabled(False)

        self.gridLayout_16.addWidget(self.lineEdit_60, 3, 0, 1, 1)

        self.cycle_stats = QTableWidget(self.groupBox_7)
        self.cycle_stats.setObjectName(u"cycle_stats")

        self.gridLayout_16.addWidget(self.cycle_stats, 4, 0, 1, 1)

        self.speed_stats = QTableWidget(self.groupBox_7)
        self.speed_stats.setObjectName(u"speed_stats")

        self.gridLayout_16.addWidget(self.speed_stats, 6, 0, 1, 1)

        self.ampl_stats = QTableWidget(self.groupBox_7)
        self.ampl_stats.setObjectName(u"ampl_stats")

        self.gridLayout_16.addWidget(self.ampl_stats, 2, 0, 1, 1)

        self.lineEdit_61 = QLineEdit(self.groupBox_7)
        self.lineEdit_61.setObjectName(u"lineEdit_61")
        self.lineEdit_61.setEnabled(False)

        self.gridLayout_16.addWidget(self.lineEdit_61, 5, 0, 1, 1)

        self.calcStats = QPushButton(self.groupBox_7)
        self.calcStats.setObjectName(u"calcStats")

        self.gridLayout_16.addWidget(self.calcStats, 0, 0, 1, 1)


        self.gridLayout_5.addWidget(self.groupBox_7, 1, 0, 1, 1)

        self.export_BrCv = QGroupBox(self.tab_export)
        self.export_BrCv.setObjectName(u"export_BrCv")
        self.gridLayout_BrCv_9 = QGridLayout(self.export_BrCv)
        self.gridLayout_BrCv_9.setObjectName(u"gridLayout_BrCv_9")
        self.lineEdit_BrCv_24 = QLineEdit(self.export_BrCv)
        self.lineEdit_BrCv_24.setObjectName(u"lineEdit_BrCv_24")
        self.lineEdit_BrCv_24.setEnabled(False)

        self.gridLayout_BrCv_9.addWidget(self.lineEdit_BrCv_24, 2, 0, 1, 1)

        self.lineEdit_77 = QLineEdit(self.export_BrCv)
        self.lineEdit_77.setObjectName(u"lineEdit_77")
        self.lineEdit_77.setEnabled(False)
        sizePolicy6.setHeightForWidth(self.lineEdit_77.sizePolicy().hasHeightForWidth())
        self.lineEdit_77.setSizePolicy(sizePolicy6)

        self.gridLayout_BrCv_9.addWidget(self.lineEdit_77, 0, 2, 1, 1)

        self.lineEdit_BrCv_28 = QLineEdit(self.export_BrCv)
        self.lineEdit_BrCv_28.setObjectName(u"lineEdit_BrCv_28")
        self.lineEdit_BrCv_28.setEnabled(False)

        self.gridLayout_BrCv_9.addWidget(self.lineEdit_BrCv_28, 3, 0, 1, 1)

        self.export_filename = QLineEdit(self.export_BrCv)
        self.export_filename.setObjectName(u"export_filename")

        self.gridLayout_BrCv_9.addWidget(self.export_filename, 3, 1, 1, 2)

        self.interp_export = QCheckBox(self.export_BrCv)
        self.interp_export.setObjectName(u"interp_export")
        self.interp_export.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.interp_export.setChecked(True)

        self.gridLayout_BrCv_9.addWidget(self.interp_export, 0, 0, 1, 1)

        self.interp_export_value = QDoubleSpinBox(self.export_BrCv)
        self.interp_export_value.setObjectName(u"interp_export_value")
        self.interp_export_value.setValue(10.000000000000000)

        self.gridLayout_BrCv_9.addWidget(self.interp_export_value, 0, 1, 1, 1)

        self.compress_speed = QDoubleSpinBox(self.export_BrCv)
        self.compress_speed.setObjectName(u"compress_speed")

        self.gridLayout_BrCv_9.addWidget(self.compress_speed, 1, 1, 1, 2)

        self.exportCSV = QPushButton(self.export_BrCv)
        self.exportCSV.setObjectName(u"exportCSV")

        self.gridLayout_BrCv_9.addWidget(self.exportCSV, 4, 0, 1, 1)

        self.n_copy_curve = QSpinBox(self.export_BrCv)
        self.n_copy_curve.setObjectName(u"n_copy_curve")
        self.n_copy_curve.setValue(1)

        self.gridLayout_BrCv_9.addWidget(self.n_copy_curve, 2, 1, 1, 2)

        self.lineEdit_83 = QLineEdit(self.export_BrCv)
        self.lineEdit_83.setObjectName(u"lineEdit_83")
        self.lineEdit_83.setEnabled(False)

        self.gridLayout_BrCv_9.addWidget(self.lineEdit_83, 1, 0, 1, 1)

        self.exportGCODE = QPushButton(self.export_BrCv)
        self.exportGCODE.setObjectName(u"exportGCODE")
        icon15 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.DocumentSave))
        self.exportGCODE.setIcon(icon15)

        self.gridLayout_BrCv_9.addWidget(self.exportGCODE, 4, 1, 1, 2)

        self.verticalSpacer_7 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_BrCv_9.addItem(self.verticalSpacer_7, 5, 1, 1, 1)

        self.gridLayout_BrCv_9.setColumnStretch(0, 2)
        self.gridLayout_BrCv_9.setColumnStretch(1, 1)
        self.gridLayout_BrCv_9.setColumnStretch(2, 1)

        self.gridLayout_5.addWidget(self.export_BrCv, 0, 0, 1, 1)

        self.gridLayout_15 = QGridLayout()
        self.gridLayout_15.setObjectName(u"gridLayout_15")
        self.plot_acq = QCheckBox(self.tab_export)
        self.plot_acq.setObjectName(u"plot_acq")

        self.gridLayout_15.addWidget(self.plot_acq, 2, 1, 1, 1)

        self.lineEdit_62 = QLineEdit(self.tab_export)
        self.lineEdit_62.setObjectName(u"lineEdit_62")

        self.gridLayout_15.addWidget(self.lineEdit_62, 1, 0, 1, 1)

        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_15.addItem(self.horizontalSpacer_3, 1, 2, 1, 1)

        self.plot_xaxis = QComboBox(self.tab_export)
        self.plot_xaxis.setObjectName(u"plot_xaxis")

        self.gridLayout_15.addWidget(self.plot_xaxis, 1, 1, 1, 1)

        self.verticalSpacer_8 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_15.addItem(self.verticalSpacer_8, 3, 1, 1, 1)

        self.plot_view = QWidget(self.tab_export)
        self.plot_view.setObjectName(u"plot_view")

        self.gridLayout_15.addWidget(self.plot_view, 0, 0, 1, 3)

        self.plot_peaks = QCheckBox(self.tab_export)
        self.plot_peaks.setObjectName(u"plot_peaks")

        self.gridLayout_15.addWidget(self.plot_peaks, 2, 0, 1, 1)

        self.gridLayout_15.setRowStretch(0, 2)
        self.gridLayout_15.setRowStretch(3, 1)
        self.gridLayout_15.setColumnStretch(0, 1)
        self.gridLayout_15.setColumnStretch(1, 1)
        self.gridLayout_15.setColumnStretch(2, 2)

        self.gridLayout_5.addLayout(self.gridLayout_15, 0, 1, 2, 1)

        self.gridLayout_5.setRowStretch(0, 1)
        self.gridLayout_5.setRowStretch(1, 2)
        self.gridLayout_5.setColumnStretch(0, 1)
        self.gridLayout_5.setColumnStretch(1, 3)
        self.tabWidget_BrCv.addTab(self.tab_export, "")

        self.gridLayout_BrCv.addWidget(self.tabWidget_BrCv, 0, 0, 1, 1)

        self.tabModules.addTab(self.tab_planning, "")
        self.tab_phantom_operation = QWidget()
        self.tab_phantom_operation.setObjectName(u"tab_phantom_operation")
        self.gridLayout_63 = QGridLayout(self.tab_phantom_operation)
        self.gridLayout_63.setObjectName(u"gridLayout_63")
        self.gridLayout_10 = QGridLayout()
        self.gridLayout_10.setObjectName(u"gridLayout_10")
        self.groupBox_4 = QGroupBox(self.tab_phantom_operation)
        self.groupBox_4.setObjectName(u"groupBox_4")
        self.gridLayout_12 = QGridLayout(self.groupBox_4)
        self.gridLayout_12.setObjectName(u"gridLayout_12")
        self.checkBox_7 = QCheckBox(self.groupBox_4)
        self.checkBox_7.setObjectName(u"checkBox_7")

        self.gridLayout_12.addWidget(self.checkBox_7, 2, 4, 1, 1)

        self.checkBox_6 = QCheckBox(self.groupBox_4)
        self.checkBox_6.setObjectName(u"checkBox_6")

        self.gridLayout_12.addWidget(self.checkBox_6, 2, 3, 1, 1)

        self.lineEdit_57 = QLineEdit(self.groupBox_4)
        self.lineEdit_57.setObjectName(u"lineEdit_57")
        self.lineEdit_57.setEnabled(False)

        self.gridLayout_12.addWidget(self.lineEdit_57, 3, 0, 1, 6)

        self.lineEdit_56 = QLineEdit(self.groupBox_4)
        self.lineEdit_56.setObjectName(u"lineEdit_56")
        self.lineEdit_56.setEnabled(False)

        self.gridLayout_12.addWidget(self.lineEdit_56, 0, 0, 1, 6)

        self.verticalSpacer_4 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_12.addItem(self.verticalSpacer_4, 6, 0, 1, 1)

        self.label_3 = QLabel(self.groupBox_4)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout_12.addWidget(self.label_3, 1, 2, 1, 1)

        self.checkBox_8 = QCheckBox(self.groupBox_4)
        self.checkBox_8.setObjectName(u"checkBox_8")

        self.gridLayout_12.addWidget(self.checkBox_8, 2, 5, 1, 1)

        self.checkBox_4 = QCheckBox(self.groupBox_4)
        self.checkBox_4.setObjectName(u"checkBox_4")

        self.gridLayout_12.addWidget(self.checkBox_4, 2, 2, 1, 1)

        self.label_2 = QLabel(self.groupBox_4)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout_12.addWidget(self.label_2, 1, 1, 1, 1)

        self.label_6 = QLabel(self.groupBox_4)
        self.label_6.setObjectName(u"label_6")

        self.gridLayout_12.addWidget(self.label_6, 1, 5, 1, 1)

        self.checkBox_2 = QCheckBox(self.groupBox_4)
        self.checkBox_2.setObjectName(u"checkBox_2")
        self.checkBox_2.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        self.gridLayout_12.addWidget(self.checkBox_2, 2, 0, 1, 1)

        self.label = QLabel(self.groupBox_4)
        self.label.setObjectName(u"label")

        self.gridLayout_12.addWidget(self.label, 1, 0, 1, 1)

        self.checkBox_3 = QCheckBox(self.groupBox_4)
        self.checkBox_3.setObjectName(u"checkBox_3")

        self.gridLayout_12.addWidget(self.checkBox_3, 2, 1, 1, 1)

        self.check_axis_X = QCheckBox(self.groupBox_4)
        self.check_axis_X.setObjectName(u"check_axis_X")

        self.gridLayout_12.addWidget(self.check_axis_X, 5, 0, 1, 1)

        self.label_5 = QLabel(self.groupBox_4)
        self.label_5.setObjectName(u"label_5")

        self.gridLayout_12.addWidget(self.label_5, 1, 4, 1, 1)

        self.label_4 = QLabel(self.groupBox_4)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout_12.addWidget(self.label_4, 1, 3, 1, 1)

        self.label_7 = QLabel(self.groupBox_4)
        self.label_7.setObjectName(u"label_7")

        self.gridLayout_12.addWidget(self.label_7, 4, 0, 1, 1)

        self.label_8 = QLabel(self.groupBox_4)
        self.label_8.setObjectName(u"label_8")

        self.gridLayout_12.addWidget(self.label_8, 4, 1, 1, 1)

        self.label_9 = QLabel(self.groupBox_4)
        self.label_9.setObjectName(u"label_9")

        self.gridLayout_12.addWidget(self.label_9, 4, 2, 1, 1)

        self.check_axis_Y = QCheckBox(self.groupBox_4)
        self.check_axis_Y.setObjectName(u"check_axis_Y")

        self.gridLayout_12.addWidget(self.check_axis_Y, 5, 1, 1, 1)

        self.check_axis_Z = QCheckBox(self.groupBox_4)
        self.check_axis_Z.setObjectName(u"check_axis_Z")

        self.gridLayout_12.addWidget(self.check_axis_Z, 5, 2, 1, 1)


        self.gridLayout_10.addWidget(self.groupBox_4, 0, 0, 1, 1)

        self.groupBox_5 = QGroupBox(self.tab_phantom_operation)
        self.groupBox_5.setObjectName(u"groupBox_5")
        self.gridLayout_14 = QGridLayout(self.groupBox_5)
        self.gridLayout_14.setObjectName(u"gridLayout_14")
        self.lineEdit_58 = QLineEdit(self.groupBox_5)
        self.lineEdit_58.setObjectName(u"lineEdit_58")
        self.lineEdit_58.setEnabled(False)

        self.gridLayout_14.addWidget(self.lineEdit_58, 0, 0, 1, 1)

        self.MoVeSpeedFactor = QSpinBox(self.groupBox_5)
        self.MoVeSpeedFactor.setObjectName(u"MoVeSpeedFactor")
        self.MoVeSpeedFactor.setMinimum(70)
        self.MoVeSpeedFactor.setMaximum(130)
        self.MoVeSpeedFactor.setValue(100)

        self.gridLayout_14.addWidget(self.MoVeSpeedFactor, 0, 1, 1, 1)

        self.MoVeAutoControl = QCheckBox(self.groupBox_5)
        self.MoVeAutoControl.setObjectName(u"MoVeAutoControl")

        self.gridLayout_14.addWidget(self.MoVeAutoControl, 2, 0, 1, 1)

        self.verticalSpacer_5 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_14.addItem(self.verticalSpacer_5, 3, 0, 1, 1)

        self.MoVeOffsetSlider = QSlider(self.groupBox_5)
        self.MoVeOffsetSlider.setObjectName(u"MoVeOffsetSlider")
        self.MoVeOffsetSlider.setOrientation(Qt.Orientation.Horizontal)

        self.gridLayout_14.addWidget(self.MoVeOffsetSlider, 1, 1, 1, 1)

        self.lineEdit_59 = QLineEdit(self.groupBox_5)
        self.lineEdit_59.setObjectName(u"lineEdit_59")
        self.lineEdit_59.setEnabled(False)

        self.gridLayout_14.addWidget(self.lineEdit_59, 1, 0, 1, 1)


        self.gridLayout_10.addWidget(self.groupBox_5, 1, 0, 1, 1)

        self.groupBox_6 = QGroupBox(self.tab_phantom_operation)
        self.groupBox_6.setObjectName(u"groupBox_6")
        self.gridLayout_13 = QGridLayout(self.groupBox_6)
        self.gridLayout_13.setObjectName(u"gridLayout_13")
        self.stop_until_radiation = QCheckBox(self.groupBox_6)
        self.stop_until_radiation.setObjectName(u"stop_until_radiation")

        self.gridLayout_13.addWidget(self.stop_until_radiation, 0, 0, 1, 1)

        self.verticalSpacer_6 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_13.addItem(self.verticalSpacer_6, 1, 0, 1, 1)


        self.gridLayout_10.addWidget(self.groupBox_6, 2, 0, 1, 1)

        self.gridLayout_10.setRowStretch(0, 1)
        self.gridLayout_10.setRowStretch(1, 1)
        self.gridLayout_10.setRowStretch(2, 1)

        self.gridLayout_63.addLayout(self.gridLayout_10, 0, 0, 1, 1)

        self.gridLayout_11 = QGridLayout()
        self.gridLayout_11.setObjectName(u"gridLayout_11")
        self.emergencyButton_4 = QPushButton(self.tab_phantom_operation)
        self.emergencyButton_4.setObjectName(u"emergencyButton_4")
        self.emergencyButton_4.setMinimumSize(QSize(200, 40))
        self.emergencyButton_4.setMaximumSize(QSize(200, 40))
        self.emergencyButton_4.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.emergencyButton_4.setStyleSheet(u"background-color: rgb(170, 0, 0);\n"
"font: 700 12pt \"Segoe UI\";")
        self.emergencyButton_4.setIcon(icon1)

        self.gridLayout_11.addWidget(self.emergencyButton_4, 0, 1, 1, 1)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_11.addItem(self.horizontalSpacer, 0, 0, 1, 1)

        self.MoVeView = QWidget(self.tab_phantom_operation)
        self.MoVeView.setObjectName(u"MoVeView")

        self.gridLayout_11.addWidget(self.MoVeView, 1, 0, 1, 2)


        self.gridLayout_63.addLayout(self.gridLayout_11, 0, 1, 1, 1)

        self.gridLayout_63.setColumnStretch(0, 1)
        self.gridLayout_63.setColumnStretch(1, 4)
        self.tabModules.addTab(self.tab_phantom_operation, "")

        self.gridLayout_3.addWidget(self.tabModules, 1, 0, 2, 4)

        self.gridLayout_3.setColumnStretch(0, 6)
        self.gridLayout_3.setColumnStretch(1, 1)
        AMIGOpy.setCentralWidget(self.centralwidget)
        self.statusbar = QStatusBar(AMIGOpy)
        self.statusbar.setObjectName(u"statusbar")
        AMIGOpy.setStatusBar(self.statusbar)

        self.retranslateUi(AMIGOpy)

        self.tabModules.setCurrentIndex(0)
        self.tabWidget.setCurrentIndex(0)
        self.tabWidget_BrCv.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(AMIGOpy)
    # setupUi

    def retranslateUi(self, AMIGOpy):
        AMIGOpy.setWindowTitle(QCoreApplication.translate("AMIGOpy", u"MainWindow", None))
        self.tabModules.setProperty(u"Layout", "")
        self.POS_DES_D_2.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.POS_DES_D.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.lineEdit_45.setText(QCoreApplication.translate("AMIGOpy", u"DESIRED", None))
        self.lineEdit_16.setText(QCoreApplication.translate("AMIGOpy", u"DESIRED", None))
        self.POS_CURR_X.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.lineEdit_47.setText(QCoreApplication.translate("AMIGOpy", u"ROLL", None))
        self.lineEdit_8.setText(QCoreApplication.translate("AMIGOpy", u"D", None))
        self.label_10.setText(QCoreApplication.translate("AMIGOpy", u"Z", None))
        self.lineEdit_46.setText(QCoreApplication.translate("AMIGOpy", u"STEP", None))
        self.lineEdit_49.setText(QCoreApplication.translate("AMIGOpy", u"YAW", None))
        self.label_15.setText(QCoreApplication.translate("AMIGOpy", u"Rotation", None))
        self.POS_DES_W.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.MOVE_Y.setText(QCoreApplication.translate("AMIGOpy", u"MOVE Y", None))
        self.lineEdit_15.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.lineEdit_14.setText(QCoreApplication.translate("AMIGOpy", u"X-axis", None))
        self.MIN_B.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.POS_CURR_A.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.lineEdit_55.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.POS_CURR_D.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.lineEdit_5.setText(QCoreApplication.translate("AMIGOpy", u"A", None))
        self.POS_CURR_Y.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.pushButton_59.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.lineEdit_13.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.MIN_W.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.HOME_X.setText(QCoreApplication.translate("AMIGOpy", u" HOME X", None))
        self.POS_DES_B.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.lineEdit_50.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.pushButton_55.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.PLUS_XAXIS.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.lineEdit_23.setText(QCoreApplication.translate("AMIGOpy", u"Y-axis", None))
        self.MOVE_X.setText(QCoreApplication.translate("AMIGOpy", u"MOVE X", None))
        self.pushButton_54.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.lineEdit_7.setText(QCoreApplication.translate("AMIGOpy", u"C", None))
        self.lineEdit_2.setText(QCoreApplication.translate("AMIGOpy", u"CURRENT", None))
        self.lineEdit_48.setText(QCoreApplication.translate("AMIGOpy", u"PITCH", None))
        self.PLUS_X.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.lineEdit_10.setText(QCoreApplication.translate("AMIGOpy", u"CURRENT", None))
        self.lineEdit_3.setText(QCoreApplication.translate("AMIGOpy", u"DESIRED", None))
        self.PLUS_ZAXIS.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.HOME_Y.setText(QCoreApplication.translate("AMIGOpy", u" HOME Y", None))
        self.PLUS_A.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.HOME_Z.setText(QCoreApplication.translate("AMIGOpy", u" HOME Z", None))
        self.label_14.setText(QCoreApplication.translate("AMIGOpy", u"Y", None))
        self.lineEdit_66.setText(QCoreApplication.translate("AMIGOpy", u"CURRENT", None))
        self.PLUS_W.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.lineEdit_22.setText(QCoreApplication.translate("AMIGOpy", u"STEP", None))
        self.lineEdit_51.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.pushButton_57.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.label_13.setText(QCoreApplication.translate("AMIGOpy", u"X", None))
        self.MIN_XAXIS.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.POS_DES_A.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.MIN_YAXIS.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.MIN_D.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.lineEdit_11.setText(QCoreApplication.translate("AMIGOpy", u"Z-axis", None))
        self.lineEdit_4.setText(QCoreApplication.translate("AMIGOpy", u"STEP", None))
        self.pushButton_56.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.lineEdit_70.setText(QCoreApplication.translate("AMIGOpy", u"STEP", None))
        self.lineEdit_53.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.POS_DES_X.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.MIN_X.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.lineEdit_9.setText(QCoreApplication.translate("AMIGOpy", u"W", None))
        self.lineEdit_65.setText(QCoreApplication.translate("AMIGOpy", u"DESIRED", None))
        self.PLUS_C.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.lineEdit_54.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.lineEdit_52.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.PLUS_D.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.lineEdit.setText(QCoreApplication.translate("AMIGOpy", u"X", None))
        self.PLUS_YAXIS.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.pushButton_53.setText(QCoreApplication.translate("AMIGOpy", u"MOVE", None))
        self.MOVE_Z.setText(QCoreApplication.translate("AMIGOpy", u"MOVE Z", None))
        self.POS_CURR_W.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.POS_DES_Y.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.PLUS_B.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.lineEdit_6.setText(QCoreApplication.translate("AMIGOpy", u"B", None))
        self.MIN_C.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.POS_CURR_C.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.lineEdit_12.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.label_16.setText(QCoreApplication.translate("AMIGOpy", u"Home", None))
        self.MIN_ZAXIS.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.MIN_A.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.pushButton_58.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.lineEdit_44.setText(QCoreApplication.translate("AMIGOpy", u"CURRENT", None))
        self.lineEdit_17.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.POS_CURR_B.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab), QCoreApplication.translate("AMIGOpy", u"Motion Platform", None))
        self.groupBox_11.setTitle(QCoreApplication.translate("AMIGOpy", u"EXTERNAL MOTORS", None))
        self.pushButton_29.setText(QCoreApplication.translate("AMIGOpy", u"MOVE", None))
        self.lineEdit_29.setText(QCoreApplication.translate("AMIGOpy", u"CURRENT", None))
        self.lineEdit_30.setText(QCoreApplication.translate("AMIGOpy", u"DESIRED", None))
        self.pushButton_30.setText(QCoreApplication.translate("AMIGOpy", u"HOME ALL", None))
        self.pushButton_36.setText(QCoreApplication.translate("AMIGOpy", u"SET ALL 0", None))
        self.lineEdit_41.setText(QCoreApplication.translate("AMIGOpy", u"STEP", None))
        self.lineEdit_24.setText(QCoreApplication.translate("AMIGOpy", u"U", None))
        self.lineEdit_31.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.lineEdit_36.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.pushButton_31.setText(QCoreApplication.translate("AMIGOpy", u"HOME U", None))
        self.pushButton_37.setText(QCoreApplication.translate("AMIGOpy", u"SET 0", None))
        self.pushButton_42.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.pushButton_47.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.lineEdit_25.setText(QCoreApplication.translate("AMIGOpy", u"V", None))
        self.lineEdit_32.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.lineEdit_37.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.pushButton_32.setText(QCoreApplication.translate("AMIGOpy", u"HOME V", None))
        self.pushButton_38.setText(QCoreApplication.translate("AMIGOpy", u"SET 0", None))
        self.pushButton_43.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.pushButton_48.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.lineEdit_26.setText(QCoreApplication.translate("AMIGOpy", u"W", None))
        self.lineEdit_33.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.lineEdit_38.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.pushButton_33.setText(QCoreApplication.translate("AMIGOpy", u"HOME W", None))
        self.pushButton_39.setText(QCoreApplication.translate("AMIGOpy", u"SET 0", None))
        self.pushButton_44.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.pushButton_49.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.lineEdit_27.setText(QCoreApplication.translate("AMIGOpy", u"K", None))
        self.lineEdit_34.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.lineEdit_39.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.pushButton_34.setText(QCoreApplication.translate("AMIGOpy", u"HOME K", None))
        self.pushButton_40.setText(QCoreApplication.translate("AMIGOpy", u"SET 0", None))
        self.pushButton_45.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.pushButton_50.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.lineEdit_28.setText(QCoreApplication.translate("AMIGOpy", u"L", None))
        self.lineEdit_35.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.lineEdit_40.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.pushButton_35.setText(QCoreApplication.translate("AMIGOpy", u"HOME L", None))
        self.pushButton_41.setText(QCoreApplication.translate("AMIGOpy", u"SET 0", None))
        self.pushButton_46.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.pushButton_51.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_4), QCoreApplication.translate("AMIGOpy", u"External Motors", None))
        self.emergencyButton_1.setText(QCoreApplication.translate("AMIGOpy", u" Emergency Stop", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("AMIGOpy", u"Connect", None))
        self.DuetIPAddress.setText(QCoreApplication.translate("AMIGOpy", u"192.168.0.1", None))
        self.setDuetIP.setText(QCoreApplication.translate("AMIGOpy", u" Verify Connection", None))
        self.sendCommandDUET.setText(QCoreApplication.translate("AMIGOpy", u" Send Command", None))
        self.lineEdit_42.setText(QCoreApplication.translate("AMIGOpy", u"IP-ADDRESS", None))
        self.connect_status.setText(QCoreApplication.translate("AMIGOpy", u"Status: Not connected", None))
        self.groupBox_12.setTitle(QCoreApplication.translate("AMIGOpy", u"Motion verification", None))
        self.setPhOperFolder.setText(QCoreApplication.translate("AMIGOpy", u" Set Input Folder", None))
        self.tabModules.setTabText(self.tabModules.indexOf(self.tab_2), QCoreApplication.translate("AMIGOpy", u"Control", None))
        self.label_27.setText(QCoreApplication.translate("AMIGOpy", u"Status", None))
        self.labelDuetStatus.setText(QCoreApplication.translate("AMIGOpy", u"Idle", None))
        self.label_Zprobe.setText(QCoreApplication.translate("AMIGOpy", u"0", None))
        self.label_31.setText(QCoreApplication.translate("AMIGOpy", u"Z-Probe", None))
        self.label_34.setText(QCoreApplication.translate("AMIGOpy", u"X", None))
        self.label_Ypos.setText(QCoreApplication.translate("AMIGOpy", u"0.0", None))
        self.label_Xpos.setText(QCoreApplication.translate("AMIGOpy", u"0.0", None))
        self.label_30.setText(QCoreApplication.translate("AMIGOpy", u"Y", None))
        self.label_28.setText(QCoreApplication.translate("AMIGOpy", u"Z", None))
        self.label_Zpos.setText(QCoreApplication.translate("AMIGOpy", u"0.0", None))
        self.label_38.setText(QCoreApplication.translate("AMIGOpy", u"Positions", None))
        self.label_41.setText(QCoreApplication.translate("AMIGOpy", u"Sensors", None))
        self.label_36.setText(QCoreApplication.translate("AMIGOpy", u"Speeds", None))
        self.label_40.setText(QCoreApplication.translate("AMIGOpy", u"Requested Speed", None))
        self.label_33.setText(QCoreApplication.translate("AMIGOpy", u"Top Speed", None))
        self.label_topSpeed.setText(QCoreApplication.translate("AMIGOpy", u"0 mm/s", None))
        self.label_reqSpeed.setText(QCoreApplication.translate("AMIGOpy", u"0 mm/s", None))
        self.labelPrintStatus.setText(QCoreApplication.translate("AMIGOpy", u"Printing: None (Progress ... %)", None))
        self.gcodeCancel.setText(QCoreApplication.translate("AMIGOpy", u" Cancel", None))
        self.gcodePause.setText(QCoreApplication.translate("AMIGOpy", u" Pause", None))
        self.label_17.setText(QCoreApplication.translate("AMIGOpy", u"Job Control", None))
        self.minSf.setText(QCoreApplication.translate("AMIGOpy", u"-", None))
        self.plusSf.setText(QCoreApplication.translate("AMIGOpy", u"+", None))
        self.labelSf.setText(QCoreApplication.translate("AMIGOpy", u"100", None))
        self.label_18.setText(QCoreApplication.translate("AMIGOpy", u"Speed Factor", None))
        self.emergencyButton_2.setText(QCoreApplication.translate("AMIGOpy", u" Emergency Stop", None))
        self.tabModules.setTabText(self.tabModules.indexOf(self.tab_status), QCoreApplication.translate("AMIGOpy", u"Status", None))
        self.gcodeUpload.setText(QCoreApplication.translate("AMIGOpy", u" Upload G-Code File(s)", None))
        self.treeViewBack.setText(QCoreApplication.translate("AMIGOpy", u" Go Back", None))
        self.gcodeRefresh.setText(QCoreApplication.translate("AMIGOpy", u" Refresh", None))
        self.gcodeNewFolder.setText(QCoreApplication.translate("AMIGOpy", u" New Directory", None))
        self.emergencyButton_3.setText(QCoreApplication.translate("AMIGOpy", u" Emergency Stop", None))
        self.tabModules.setTabText(self.tabModules.indexOf(self.tab_files), QCoreApplication.translate("AMIGOpy", u"Files", None))
        self.groupBox_BrCv_createCurve.setTitle(QCoreApplication.translate("AMIGOpy", u"Phantom ", None))
        self.lineEdit_BrCv_2.setText(QCoreApplication.translate("AMIGOpy", u"Sampling frequency (Hz)", None))
        self.create_curve_type.setPlaceholderText("")
        self.lineEdit_BrCv_4.setText(QCoreApplication.translate("AMIGOpy", u"Curve type", None))
        self.create_remove_row.setText(QCoreApplication.translate("AMIGOpy", u"Cycle", None))
        self.create_add_row.setText(QCoreApplication.translate("AMIGOpy", u"Cycle", None))
        self.button_create_curve.setText(QCoreApplication.translate("AMIGOpy", u" Create curve", None))
        self.tabWidget_BrCv.setTabText(self.tabWidget_BrCv.indexOf(self.tab_create), QCoreApplication.translate("AMIGOpy", u"Create ", None))
        self.groupBox_BrCv_importCSV.setTitle(QCoreApplication.translate("AMIGOpy", u"Import CSV/VXP", None))
        self.lineEdit_delimiter.setText(QCoreApplication.translate("AMIGOpy", u"Delimiter", None))
        self.lineEdit_skip_lines.setText(QCoreApplication.translate("AMIGOpy", u"Lines to skip", None))
        self.lineEdit_header_line.setText(QCoreApplication.translate("AMIGOpy", u"Header line", None))
        self.import_flip.setText(QCoreApplication.translate("AMIGOpy", u"Flip", None))
        self.import_button.setText(QCoreApplication.translate("AMIGOpy", u"Import", None))
        self.lineEdit_time_unit.setText(QCoreApplication.translate("AMIGOpy", u"Time unit", None))
        self.tabWidget_BrCv.setTabText(self.tabWidget_BrCv.indexOf(self.tab_import), QCoreApplication.translate("AMIGOpy", u"Import", None))
        self.edit_undo.setText(QCoreApplication.translate("AMIGOpy", u" Undo", None))
        self.groupBox_drift.setTitle(QCoreApplication.translate("AMIGOpy", u"Baseline drift", None))
        self.button_add_drift.setText(QCoreApplication.translate("AMIGOpy", u"Add drift", None))
        self.button_remove_drift.setText(QCoreApplication.translate("AMIGOpy", u"Remove drift", None))
        self.value_drift.setSuffix(QCoreApplication.translate("AMIGOpy", u" mm/s", None))
        self.breathhold_BrCv.setTitle(QCoreApplication.translate("AMIGOpy", u"Breath hold", None))
        self.breathholdDuration.setSuffix(QCoreApplication.translate("AMIGOpy", u" s", None))
        self.button_breath_hold.setText(QCoreApplication.translate("AMIGOpy", u"Insert breath hold", None))
        self.closest_max.setText(QCoreApplication.translate("AMIGOpy", u"Closest maximum", None))
        self.closest_min.setText(QCoreApplication.translate("AMIGOpy", u"Closest minimum", None))
        self.groupBox_operations.setTitle(QCoreApplication.translate("AMIGOpy", u"Operations", None))
        self.button_scale_ampl.setText(QCoreApplication.translate("AMIGOpy", u"Scale amplitude", None))
        self.button_shift_ampl.setText(QCoreApplication.translate("AMIGOpy", u"Shift amplitude", None))
        self.button_scale_freq.setText(QCoreApplication.translate("AMIGOpy", u"Scale frequency", None))
        self.value_ampl_shift.setSuffix(QCoreApplication.translate("AMIGOpy", u" mm", None))
        self.value_ampl_sf.setSuffix("")
        self.button_zero_ampl.setText(QCoreApplication.translate("AMIGOpy", u"Zero amplitude", None))
        self.button_clip_ampl.setText(QCoreApplication.translate("AMIGOpy", u"Apply thresholds", None))
        self.value_ampl_min.setSuffix(QCoreApplication.translate("AMIGOpy", u" mm", None))
        self.value_ampl_max.setSuffix(QCoreApplication.translate("AMIGOpy", u" mm", None))
        self.groupBox_smoothing.setTitle(QCoreApplication.translate("AMIGOpy", u"Smoothing", None))
        self.lineEdit_78.setText(QCoreApplication.translate("AMIGOpy", u"method", None))
        self.lineEdit_79.setText(QCoreApplication.translate("AMIGOpy", u"kernel size", None))
        self.lineEdit_81.setText(QCoreApplication.translate("AMIGOpy", u"cut-off frequency", None))
        self.button_apply_smooth.setText(QCoreApplication.translate("AMIGOpy", u"Apply", None))
        self.lineEdit_BrCv_25.setText(QCoreApplication.translate("AMIGOpy", u"X min", None))
        self.button_clip_cycles.setText(QCoreApplication.translate("AMIGOpy", u" Crop", None))
        self.lineEdit_BrCv_26.setText(QCoreApplication.translate("AMIGOpy", u"X max", None))
        self.tabWidget_BrCv.setTabText(self.tabWidget_BrCv.indexOf(self.tab_edit), QCoreApplication.translate("AMIGOpy", u"Edit", None))
        self.groupBox_7.setTitle(QCoreApplication.translate("AMIGOpy", u"Statistics", None))
        self.lineEdit_43.setText(QCoreApplication.translate("AMIGOpy", u"Amplitude", None))
        self.lineEdit_60.setText(QCoreApplication.translate("AMIGOpy", u"Cycle time", None))
        self.lineEdit_61.setText(QCoreApplication.translate("AMIGOpy", u"Speed", None))
        self.calcStats.setText(QCoreApplication.translate("AMIGOpy", u"Calculate statistics", None))
        self.export_BrCv.setTitle(QCoreApplication.translate("AMIGOpy", u"Export", None))
        self.lineEdit_BrCv_24.setText(QCoreApplication.translate("AMIGOpy", u"Copy fragment", None))
        self.lineEdit_77.setText(QCoreApplication.translate("AMIGOpy", u"ms", None))
        self.lineEdit_BrCv_28.setText(QCoreApplication.translate("AMIGOpy", u"Filename", None))
        self.interp_export.setText(QCoreApplication.translate("AMIGOpy", u"Interpolate", None))
        self.exportCSV.setText(QCoreApplication.translate("AMIGOpy", u"Export CSV", None))
        self.lineEdit_83.setText(QCoreApplication.translate("AMIGOpy", u"Compress below speed", None))
        self.exportGCODE.setText(QCoreApplication.translate("AMIGOpy", u" Export GCODE", None))
        self.plot_acq.setText(QCoreApplication.translate("AMIGOpy", u"Plot acquistion timestamps", None))
        self.lineEdit_62.setText(QCoreApplication.translate("AMIGOpy", u"X-axis", None))
        self.plot_peaks.setText(QCoreApplication.translate("AMIGOpy", u"Plot peaks", None))
        self.tabWidget_BrCv.setTabText(self.tabWidget_BrCv.indexOf(self.tab_export), QCoreApplication.translate("AMIGOpy", u"Export && visualize", None))
        self.tabModules.setTabText(self.tabModules.indexOf(self.tab_planning), QCoreApplication.translate("AMIGOpy", u"Planning", None))
        self.groupBox_4.setTitle(QCoreApplication.translate("AMIGOpy", u"Show axis", None))
        self.checkBox_7.setText("")
        self.checkBox_6.setText("")
        self.lineEdit_57.setText(QCoreApplication.translate("AMIGOpy", u"PHANTOM", None))
        self.lineEdit_56.setText(QCoreApplication.translate("AMIGOpy", u"MOTION PLATFORM", None))
        self.label_3.setText(QCoreApplication.translate("AMIGOpy", u"C", None))
        self.checkBox_8.setText("")
        self.checkBox_4.setText("")
        self.label_2.setText(QCoreApplication.translate("AMIGOpy", u"B", None))
        self.label_6.setText(QCoreApplication.translate("AMIGOpy", u"V", None))
        self.checkBox_2.setText("")
        self.label.setText(QCoreApplication.translate("AMIGOpy", u"A", None))
        self.checkBox_3.setText("")
        self.check_axis_X.setText("")
        self.label_5.setText(QCoreApplication.translate("AMIGOpy", u"U", None))
        self.label_4.setText(QCoreApplication.translate("AMIGOpy", u"D", None))
        self.label_7.setText(QCoreApplication.translate("AMIGOpy", u"X", None))
        self.label_8.setText(QCoreApplication.translate("AMIGOpy", u"Y", None))
        self.label_9.setText(QCoreApplication.translate("AMIGOpy", u"Z", None))
        self.check_axis_Y.setText("")
        self.check_axis_Z.setText("")
        self.groupBox_5.setTitle(QCoreApplication.translate("AMIGOpy", u"Synchronization ", None))
        self.lineEdit_58.setText(QCoreApplication.translate("AMIGOpy", u"Speed factor", None))
        self.MoVeAutoControl.setText(QCoreApplication.translate("AMIGOpy", u"Auto-control", None))
        self.lineEdit_59.setText(QCoreApplication.translate("AMIGOpy", u"Offset", None))
        self.groupBox_6.setTitle(QCoreApplication.translate("AMIGOpy", u"Triggered imaging", None))
        self.stop_until_radiation.setText(QCoreApplication.translate("AMIGOpy", u"Pause until radiation", None))
        self.emergencyButton_4.setText(QCoreApplication.translate("AMIGOpy", u" Emergency Stop", None))
        self.tabModules.setTabText(self.tabModules.indexOf(self.tab_phantom_operation), QCoreApplication.translate("AMIGOpy", u"Motion Verification", None))
    # retranslateUi

