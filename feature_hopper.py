# -*- coding: utf-8 -*-
"""Main plugin class for FeatureHopper."""

import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import Qt

try:
    from qgis.PyQt.QtWidgets import QAction
except ImportError:  # Qt6 / QGIS 4
    from qgis.PyQt.QtGui import QAction

from .feature_hopper_dockwidget import FeatureHopperDockWidget


class FeatureHopper:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dockwidget = None
        self.plugin_is_active = False

    def initGui(self):
        icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.png"))
        self.action = QAction(icon, "FeatureHopper", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.triggered.connect(self.toggle)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToVectorMenu("FeatureHopper", self.action)

    def unload(self):
        self.iface.removePluginVectorMenu("FeatureHopper", self.action)
        self.iface.removeToolBarIcon(self.action)

        if self.dockwidget is not None:
            self.iface.removeDockWidget(self.dockwidget)
            self.dockwidget = None

    def toggle(self, checked):
        if self.dockwidget is None:
            self.dockwidget = FeatureHopperDockWidget(self.iface)
            self.dockwidget.closingPlugin.connect(self.on_dockwidget_closed)
            self.iface.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dockwidget)

        self.dockwidget.setVisible(checked)
        self.plugin_is_active = checked

    def on_dockwidget_closed(self):
        self.action.setChecked(False)
        self.plugin_is_active = False
