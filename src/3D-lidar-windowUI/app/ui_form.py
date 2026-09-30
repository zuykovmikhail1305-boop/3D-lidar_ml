# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'form.ui'
##
## Created by: Qt User Interface Compiler version 6.11.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QDoubleSpinBox,
    QFormLayout, QFrame, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QMainWindow, QMenu,
    QMenuBar, QProgressBar, QPushButton, QRadioButton,
    QSizePolicy, QSpacerItem, QSplitter, QStatusBar,
    QTableView, QVBoxLayout, QWidget)
class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1440, 900)
        MainWindow.setMinimumSize(QSize(1024, 640))
        self.actionOpenPointCloud = QAction(MainWindow)
        self.actionOpenPointCloud.setObjectName(u"actionOpenPointCloud")
        self.actionOpenMLReport = QAction(MainWindow)
        self.actionOpenMLReport.setObjectName(u"actionOpenMLReport")
        self.actionQuit = QAction(MainWindow)
        self.actionQuit.setObjectName(u"actionQuit")
        self.actionResetView = QAction(MainWindow)
        self.actionResetView.setObjectName(u"actionResetView")
        self.actionCameraFront = QAction(MainWindow)
        self.actionCameraFront.setObjectName(u"actionCameraFront")
        self.actionCameraTop = QAction(MainWindow)
        self.actionCameraTop.setObjectName(u"actionCameraTop")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.centralLayout = QHBoxLayout(self.centralwidget)
        self.centralLayout.setSpacing(6)
        self.centralLayout.setObjectName(u"centralLayout")
        self.mainSplitter = QSplitter(self.centralwidget)
        self.mainSplitter.setObjectName(u"mainSplitter")
        self.mainSplitter.setOrientation(Qt.Horizontal)
        self.leftPanel = QFrame(self.mainSplitter)
        self.leftPanel.setObjectName(u"leftPanel")
        self.leftPanel.setMinimumSize(QSize(320, 0))
        self.leftPanel.setMaximumSize(QSize(440, 16777215))
        self.leftPanel.setFrameShape(QFrame.StyledPanel)
        self.leftPanel.setFrameShadow(QFrame.Raised)
        self.leftPanelLayout = QVBoxLayout(self.leftPanel)
        self.leftPanelLayout.setSpacing(8)
        self.leftPanelLayout.setObjectName(u"leftPanelLayout")
        self.leftTitleLabel = QLabel(self.leftPanel)
        self.leftTitleLabel.setObjectName(u"leftTitleLabel")

        self.leftPanelLayout.addWidget(self.leftTitleLabel)

        self.zoneCard_300 = QFrame(self.leftPanel)
        self.zoneCard_300.setObjectName(u"zoneCard_300")
        self.zoneCard_300.setMinimumSize(QSize(0, 118))
        self.zoneCard_300.setFrameShape(QFrame.StyledPanel)
        self.zoneLayout_300 = QVBoxLayout(self.zoneCard_300)
        self.zoneLayout_300.setObjectName(u"zoneLayout_300")
        self.zoneTitle_300 = QLabel(self.zoneCard_300)
        self.zoneTitle_300.setObjectName(u"zoneTitle_300")

        self.zoneLayout_300.addWidget(self.zoneTitle_300)

        self.zoneProb_300 = QLabel(self.zoneCard_300)
        self.zoneProb_300.setObjectName(u"zoneProb_300")

        self.zoneLayout_300.addWidget(self.zoneProb_300)

        self.zoneProgress_300 = QProgressBar(self.zoneCard_300)
        self.zoneProgress_300.setObjectName(u"zoneProgress_300")
        self.zoneProgress_300.setValue(0)

        self.zoneLayout_300.addWidget(self.zoneProgress_300)

        self.zoneStatus_300 = QLabel(self.zoneCard_300)
        self.zoneStatus_300.setObjectName(u"zoneStatus_300")

        self.zoneLayout_300.addWidget(self.zoneStatus_300)


        self.leftPanelLayout.addWidget(self.zoneCard_300)

        self.zoneCard_200 = QFrame(self.leftPanel)
        self.zoneCard_200.setObjectName(u"zoneCard_200")
        self.zoneCard_200.setMinimumSize(QSize(0, 118))
        self.zoneCard_200.setFrameShape(QFrame.StyledPanel)
        self.zoneLayout_200 = QVBoxLayout(self.zoneCard_200)
        self.zoneLayout_200.setObjectName(u"zoneLayout_200")
        self.zoneTitle_200 = QLabel(self.zoneCard_200)
        self.zoneTitle_200.setObjectName(u"zoneTitle_200")

        self.zoneLayout_200.addWidget(self.zoneTitle_200)

        self.zoneProb_200 = QLabel(self.zoneCard_200)
        self.zoneProb_200.setObjectName(u"zoneProb_200")

        self.zoneLayout_200.addWidget(self.zoneProb_200)

        self.zoneProgress_200 = QProgressBar(self.zoneCard_200)
        self.zoneProgress_200.setObjectName(u"zoneProgress_200")
        self.zoneProgress_200.setValue(0)

        self.zoneLayout_200.addWidget(self.zoneProgress_200)

        self.zoneStatus_200 = QLabel(self.zoneCard_200)
        self.zoneStatus_200.setObjectName(u"zoneStatus_200")

        self.zoneLayout_200.addWidget(self.zoneStatus_200)


        self.leftPanelLayout.addWidget(self.zoneCard_200)

        self.zoneCard_100 = QFrame(self.leftPanel)
        self.zoneCard_100.setObjectName(u"zoneCard_100")
        self.zoneCard_100.setMinimumSize(QSize(0, 118))
        self.zoneCard_100.setFrameShape(QFrame.StyledPanel)
        self.zoneLayout_100 = QVBoxLayout(self.zoneCard_100)
        self.zoneLayout_100.setObjectName(u"zoneLayout_100")
        self.zoneTitle_100 = QLabel(self.zoneCard_100)
        self.zoneTitle_100.setObjectName(u"zoneTitle_100")

        self.zoneLayout_100.addWidget(self.zoneTitle_100)

        self.zoneProb_100 = QLabel(self.zoneCard_100)
        self.zoneProb_100.setObjectName(u"zoneProb_100")

        self.zoneLayout_100.addWidget(self.zoneProb_100)

        self.zoneProgress_100 = QProgressBar(self.zoneCard_100)
        self.zoneProgress_100.setObjectName(u"zoneProgress_100")
        self.zoneProgress_100.setValue(0)

        self.zoneLayout_100.addWidget(self.zoneProgress_100)

        self.zoneStatus_100 = QLabel(self.zoneCard_100)
        self.zoneStatus_100.setObjectName(u"zoneStatus_100")

        self.zoneLayout_100.addWidget(self.zoneStatus_100)


        self.leftPanelLayout.addWidget(self.zoneCard_100)

        self.zonesTable = QTableView(self.leftPanel)
        self.zonesTable.setObjectName(u"zonesTable")
        self.zonesTable.setMinimumSize(QSize(0, 150))
        self.zonesTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.zonesTable.setAlternatingRowColors(True)
        self.zonesTable.setSelectionMode(QAbstractItemView.NoSelection)
        self.zonesTable.setShowGrid(False)
        self.zonesTable.horizontalHeader().setHighlightSections(False)
        self.zonesTable.verticalHeader().setVisible(False)
        self.zonesTable.verticalHeader().setHighlightSections(False)

        self.leftPanelLayout.addWidget(self.zonesTable)

        self.fileButtonsLayout = QHBoxLayout()
        self.fileButtonsLayout.setObjectName(u"fileButtonsLayout")
        self.openFileButton = QPushButton(self.leftPanel)
        self.openFileButton.setObjectName(u"openFileButton")

        self.fileButtonsLayout.addWidget(self.openFileButton)

        self.streamButton = QPushButton(self.leftPanel)
        self.streamButton.setObjectName(u"streamButton")

        self.fileButtonsLayout.addWidget(self.streamButton)


        self.leftPanelLayout.addLayout(self.fileButtonsLayout)

        self.voxelLayout = QFormLayout()
        self.voxelLayout.setObjectName(u"voxelLayout")
        self.voxelLabel = QLabel(self.leftPanel)
        self.voxelLabel.setObjectName(u"voxelLabel")

        self.voxelLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.voxelLabel)

        self.voxelLeafSpin = QDoubleSpinBox(self.leftPanel)
        self.voxelLeafSpin.setObjectName(u"voxelLeafSpin")
        self.voxelLeafSpin.setDecimals(2)
        self.voxelLeafSpin.setMinimum(0.010000000000000)
        self.voxelLeafSpin.setMaximum(5.000000000000000)
        self.voxelLeafSpin.setSingleStep(0.050000000000000)
        self.voxelLeafSpin.setValue(0.200000000000000)

        self.voxelLayout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.voxelLeafSpin)


        self.leftPanelLayout.addLayout(self.voxelLayout)

        self.coloringGroup = QGroupBox(self.leftPanel)
        self.coloringGroup.setObjectName(u"coloringGroup")
        self.coloringLayout = QVBoxLayout(self.coloringGroup)
        self.coloringLayout.setObjectName(u"coloringLayout")
        self.colorByDistanceRadio = QRadioButton(self.coloringGroup)
        self.colorByDistanceRadio.setObjectName(u"colorByDistanceRadio")
        self.colorByDistanceRadio.setChecked(True)

        self.coloringLayout.addWidget(self.colorByDistanceRadio)

        self.colorByIntensityRadio = QRadioButton(self.coloringGroup)
        self.colorByIntensityRadio.setObjectName(u"colorByIntensityRadio")

        self.coloringLayout.addWidget(self.colorByIntensityRadio)

        self.colorByHeightRadio = QRadioButton(self.coloringGroup)
        self.colorByHeightRadio.setObjectName(u"colorByHeightRadio")

        self.coloringLayout.addWidget(self.colorByHeightRadio)


        self.leftPanelLayout.addWidget(self.coloringGroup)

        self.overlayTogglesLayout = QHBoxLayout()
        self.overlayTogglesLayout.setObjectName(u"overlayTogglesLayout")
        self.zonesVisibleCheck = QCheckBox(self.leftPanel)
        self.zonesVisibleCheck.setObjectName(u"zonesVisibleCheck")
        self.zonesVisibleCheck.setChecked(True)

        self.overlayTogglesLayout.addWidget(self.zonesVisibleCheck)

        self.bboxVisibleCheck = QCheckBox(self.leftPanel)
        self.bboxVisibleCheck.setObjectName(u"bboxVisibleCheck")
        self.bboxVisibleCheck.setChecked(True)

        self.overlayTogglesLayout.addWidget(self.bboxVisibleCheck)

        self.gridVisibleCheck = QCheckBox(self.leftPanel)
        self.gridVisibleCheck.setObjectName(u"gridVisibleCheck")
        self.gridVisibleCheck.setChecked(True)

        self.overlayTogglesLayout.addWidget(self.gridVisibleCheck)


        self.leftPanelLayout.addLayout(self.overlayTogglesLayout)

        self.leftSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.leftPanelLayout.addItem(self.leftSpacer)

        self.mainSplitter.addWidget(self.leftPanel)
        self.viewportContainer = QWidget(self.mainSplitter)
        self.viewportContainer.setObjectName(u"viewportContainer")
        self.viewportContainer.setMinimumSize(QSize(600, 400))
        self.mainSplitter.addWidget(self.viewportContainer)

        self.centralLayout.addWidget(self.mainSplitter)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1440, 22))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuView = QMenu(self.menubar)
        self.menuView.setObjectName(u"menuView")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuView.menuAction())
        self.menuFile.addAction(self.actionOpenPointCloud)
        self.menuFile.addAction(self.actionOpenMLReport)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionQuit)
        self.menuView.addAction(self.actionResetView)
        self.menuView.addAction(self.actionCameraFront)
        self.menuView.addAction(self.actionCameraTop)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"LiDAR Obstacle Monitor \u2014 \u0430\u043d\u0430\u043b\u0438\u0437 \u043f\u0440\u0435\u043f\u044f\u0442\u0441\u0442\u0432\u0438\u0439 \u043f\u0435\u0440\u0435\u0434 \u043f\u043e\u0435\u0437\u0434\u043e\u043c", None))
        self.actionOpenPointCloud.setText(QCoreApplication.translate("MainWindow", u"\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u043e\u0431\u043b\u0430\u043a\u043e \u0442\u043e\u0447\u0435\u043a\u2026", None))
        self.actionOpenMLReport.setText(QCoreApplication.translate("MainWindow", u"\u041e\u0442\u043a\u0440\u044b\u0442\u044c ML-\u043e\u0442\u0447\u0451\u0442\u2026", None))
        self.actionQuit.setText(QCoreApplication.translate("MainWindow", u"\u0412\u044b\u0445\u043e\u0434", None))
        self.actionResetView.setText(QCoreApplication.translate("MainWindow", u"\u0421\u0431\u0440\u043e\u0441\u0438\u0442\u044c \u0432\u0438\u0434", None))
        self.actionCameraFront.setText(QCoreApplication.translate("MainWindow", u"\u041a\u0430\u043c\u0435\u0440\u0430: \u0444\u0440\u043e\u043d\u0442", None))
        self.actionCameraTop.setText(QCoreApplication.translate("MainWindow", u"\u041a\u0430\u043c\u0435\u0440\u0430: \u0441\u0432\u0435\u0440\u0445\u0443", None))
        self.leftTitleLabel.setText(QCoreApplication.translate("MainWindow", u"\u0417\u041e\u041d\u042b \u041e\u0411\u041d\u0410\u0420\u0423\u0416\u0415\u041d\u0418\u042f", None))
        self.zoneTitle_300.setText(QCoreApplication.translate("MainWindow", u"\u0417\u041e\u041d\u0410 300 \u043c", None))
        self.zoneProb_300.setText(QCoreApplication.translate("MainWindow", u"\u2014 %", None))
        self.zoneStatus_300.setText(QCoreApplication.translate("MainWindow", u"\u041d\u0415\u0422 \u0414\u0410\u041d\u041d\u042b\u0425", None))
        self.zoneTitle_200.setText(QCoreApplication.translate("MainWindow", u"\u0417\u041e\u041d\u0410 200 \u043c", None))
        self.zoneProb_200.setText(QCoreApplication.translate("MainWindow", u"\u2014 %", None))
        self.zoneStatus_200.setText(QCoreApplication.translate("MainWindow", u"\u041d\u0415\u0422 \u0414\u0410\u041d\u041d\u042b\u0425", None))
        self.zoneTitle_100.setText(QCoreApplication.translate("MainWindow", u"\u0417\u041e\u041d\u0410 100 \u043c", None))
        self.zoneProb_100.setText(QCoreApplication.translate("MainWindow", u"\u2014 %", None))
        self.zoneStatus_100.setText(QCoreApplication.translate("MainWindow", u"\u041d\u0415\u0422 \u0414\u0410\u041d\u041d\u042b\u0425", None))
        self.openFileButton.setText(QCoreApplication.translate("MainWindow", u"\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0444\u0430\u0439\u043b", None))
        self.streamButton.setText(QCoreApplication.translate("MainWindow", u"\u25b6 \u0421\u0442\u0440\u0438\u043c", None))
        self.voxelLabel.setText(QCoreApplication.translate("MainWindow", u"\u0412\u043e\u043a\u0441\u0435\u043b\u044c, \u043c:", None))
        self.coloringGroup.setTitle(QCoreApplication.translate("MainWindow", u"\u0420\u0430\u0441\u043a\u0440\u0430\u0441\u043a\u0430", None))
        self.colorByDistanceRadio.setText(QCoreApplication.translate("MainWindow", u"\u041f\u043e \u0440\u0430\u0441\u0441\u0442\u043e\u044f\u043d\u0438\u044e", None))
        self.colorByIntensityRadio.setText(QCoreApplication.translate("MainWindow", u"\u041f\u043e \u0438\u043d\u0442\u0435\u043d\u0441\u0438\u0432\u043d\u043e\u0441\u0442\u0438", None))
        self.colorByHeightRadio.setText(QCoreApplication.translate("MainWindow", u"\u041f\u043e \u0432\u044b\u0441\u043e\u0442\u0435", None))
        self.zonesVisibleCheck.setText(QCoreApplication.translate("MainWindow", u"\u0417\u043e\u043d\u044b", None))
        self.bboxVisibleCheck.setText(QCoreApplication.translate("MainWindow", u"BBox", None))
        self.gridVisibleCheck.setText(QCoreApplication.translate("MainWindow", u"\u0421\u0435\u0442\u043a\u0430", None))
        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", u"\u0424\u0430\u0439\u043b", None))
        self.menuView.setTitle(QCoreApplication.translate("MainWindow", u"\u0412\u0438\u0434", None))
    # retranslateUi

