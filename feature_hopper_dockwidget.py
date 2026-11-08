# -*- coding: utf-8 -*-
"""Dockwidget with all FeatureHopper UI and navigation/search logic."""

from qgis.core import (
    Qgis, QgsProject, QgsVectorLayer, QgsFeatureRequest, NULL, QgsCoordinateTransform,
)
from qgis.gui import QgsMapCanvasItem
from qgis.PyQt.QtCore import Qt, QRectF, QPointF, pyqtSignal

from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QPushButton, QCheckBox, QLineEdit, QFrame,
    QCompleter,
)

try:
    from qgis.PyQt.QtWidgets import QShortcut  # Qt5
except ImportError:
    from qgis.PyQt.QtGui import QShortcut  # Qt6

from qgis.PyQt.QtGui import QKeySequence, QColor

from .i18n import tr


class FeatureLabelItem(QgsMapCanvasItem):
    """A plain text-on-background label offset from a map point, with a thin
    connector line back to it (so it never covers the feature itself)."""

    PADDING_X = 6
    PADDING_Y = 4
    GAP = 12  # pixels between the anchor point and the label box

    def __init__(self, canvas):
        super().__init__(canvas)
        self._canvas = canvas
        self.text = ""
        self.map_point = None
        self.setZValue(1000)

    def set_label(self, map_point, text):
        self.map_point = map_point
        self.text = text
        self.updatePosition()
        self.update()

    def updatePosition(self):
        if self.map_point is not None:
            self.setPos(self.toCanvasCoordinates(self.map_point))

    def _box_size(self, font_metrics):
        width = font_metrics.horizontalAdvance(self.text) + 2 * self.PADDING_X
        height = font_metrics.height() + 2 * self.PADDING_Y
        return width, height

    def _box_rect(self, font_metrics):
        width, height = self._box_size(font_metrics)
        return QRectF(self.GAP, -(self.GAP + height), width, height)

    def boundingRect(self):
        # Any exception raised here is fatal to QGIS (this runs inside a Qt
        # C++ graphics callback), so this must never raise.
        try:
            if not self.text:
                return QRectF()
            return self._box_rect(self._canvas.fontMetrics()).united(QRectF(-2, -2, 4, 4))
        except Exception:
            return QRectF()

    def paint(self, painter, option=None, widget=None):
        # Same fatal-if-it-raises caveat as boundingRect().
        try:
            if not self.text:
                return
            box = self._box_rect(painter.fontMetrics())

            painter.setPen(QColor(60, 60, 60))
            painter.drawLine(QPointF(0, 0), box.bottomLeft())
            painter.setBrush(QColor(0, 0, 0))
            painter.drawEllipse(QPointF(0, 0), 2, 2)

            painter.setPen(QColor(0, 0, 0))
            painter.setBrush(QColor(255, 255, 255, 255))
            painter.drawRect(box)
            painter.drawText(box, int(Qt.AlignmentFlag.AlignCenter), self.text)
        except Exception:
            pass


class FeatureHopperDockWidget(QDockWidget):
    closingPlugin = pyqtSignal()
    PLUGIN_NAME = "FeatureHopper"

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface

        self.layer = None
        self.features = []
        self.feat_index = None
        self.value_map = {}
        self.label_item = None

        self._build_ui()
        self._connect_signals()

        QgsProject.instance().layerWasAdded.connect(self.refresh_layers_combo)
        QgsProject.instance().layerWillBeRemoved[str].connect(self.on_layer_will_be_removed)
        QgsProject.instance().layerRemoved.connect(self.refresh_layers_combo)

        self.refresh_layers_combo()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.setWindowTitle(self.PLUGIN_NAME)

        container = QWidget(self)
        self.setWidget(container)
        main_layout = QVBoxLayout(container)

        self.btn_use_active_layer = QPushButton(tr("use_active_layer"))
        self.btn_use_active_layer.setToolTip(tr("use_active_layer_tip"))
        main_layout.addWidget(self.btn_use_active_layer)

        form = QFormLayout()
        self.cbo_layer = QComboBox()
        form.addRow(QLabel(tr("layer_label")), self.cbo_layer)
        main_layout.addLayout(form)

        nav_row = QHBoxLayout()
        self.btn_prev = QPushButton(tr("previous"))
        self.btn_prev.setToolTip(tr("previous_tip"))
        self.lbl_count = QLabel(tr("count_none"))
        self.lbl_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_next = QPushButton(tr("next"))
        self.btn_next.setToolTip(tr("next_tip"))
        nav_row.addWidget(self.btn_prev)
        nav_row.addWidget(self.lbl_count)
        nav_row.addWidget(self.btn_next)
        main_layout.addLayout(nav_row)

        self.chk_auto_select = QCheckBox(tr("auto_select"))
        main_layout.addWidget(self.chk_auto_select)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)

        search_form = QFormLayout()
        self.cbo_search_field = QComboBox()
        search_form.addRow(QLabel(tr("search_field_label")), self.cbo_search_field)
        main_layout.addLayout(search_form)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(tr("search_placeholder"))
        self.txt_search.setClearButtonEnabled(True)
        main_layout.addWidget(self.txt_search)

        self.completer = QCompleter([], self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchStartsWith)
        self.txt_search.setCompleter(self.completer)

        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line2)

        self.chk_show_label = QCheckBox(tr("show_label"))
        self.chk_show_label.setToolTip(tr("show_label_tip"))
        main_layout.addWidget(self.chk_show_label)

        main_layout.addStretch()

        self.set_navigation_enabled(False)

        self.shortcut_next = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        self.shortcut_prev = QShortcut(QKeySequence(Qt.Key.Key_Left), self)

    def _connect_signals(self):
        self.cbo_layer.currentIndexChanged.connect(self.on_layer_changed)
        self.btn_prev.clicked.connect(lambda: self.hop(-1))
        self.btn_next.clicked.connect(lambda: self.hop(1))
        self.shortcut_prev.activated.connect(lambda: self.hop(-1))
        self.shortcut_next.activated.connect(lambda: self.hop(1))
        self.cbo_search_field.currentIndexChanged.connect(self.on_search_field_changed)
        self.completer.activated[str].connect(self.on_search_selected)
        self.txt_search.returnPressed.connect(self.on_search_return)
        self.btn_use_active_layer.clicked.connect(self.use_active_layer)
        self.chk_show_label.toggled.connect(self.on_toggle_label)
        self.visibilityChanged.connect(self.on_visibility_changed)

    # ------------------------------------------------------------------
    # Layer handling
    # ------------------------------------------------------------------
    def refresh_layers_combo(self):
        prev_layer_id = self.cbo_layer.currentData()

        self.cbo_layer.blockSignals(True)
        self.cbo_layer.clear()
        self.cbo_layer.addItem("", None)

        layers = [
            lyr for lyr in QgsProject.instance().mapLayers().values()
            if isinstance(lyr, QgsVectorLayer)
        ]
        for lyr in sorted(layers, key=lambda l: l.name().lower()):
            self.cbo_layer.addItem(lyr.name(), lyr.id())

        active = self.iface.activeLayer()
        if prev_layer_id and self.cbo_layer.findData(prev_layer_id) >= 0:
            self.cbo_layer.setCurrentIndex(self.cbo_layer.findData(prev_layer_id))
        elif isinstance(active, QgsVectorLayer) and self.cbo_layer.findData(active.id()) >= 0:
            self.cbo_layer.setCurrentIndex(self.cbo_layer.findData(active.id()))
        else:
            self.cbo_layer.setCurrentIndex(0)

        self.cbo_layer.blockSignals(False)

        # Layers are added/removed constantly when loading groups; only
        # rebuild the (potentially large) feature list if the selection moved.
        if self.layer is not None and prev_layer_id and self.cbo_layer.currentData() == prev_layer_id:
            return
        self.on_layer_changed()

    def on_layer_will_be_removed(self, layer_id):
        """Let go of the layer while its C++ object is still alive."""
        if self.layer is None or self.cbo_layer.currentData() != layer_id:
            return
        self._disconnect_layer_signals()
        self._clear_label()
        self.layer = None
        self.features = []
        self.feat_index = None

    def _disconnect_layer_signals(self):
        if self.layer is None:
            return
        for name in ("featureAdded", "featureDeleted", "editingStopped"):
            try:
                getattr(self.layer, name).disconnect(self.rebuild_features)
            except (TypeError, RuntimeError):
                # Not connected, or the layer's C++ object is already gone.
                pass

    def use_active_layer(self):
        active = self.iface.activeLayer()
        if not isinstance(active, QgsVectorLayer):
            self.warn(tr("warn_no_active_layer"))
            return

        idx = self.cbo_layer.findData(active.id())
        if idx < 0:
            self.warn(tr("warn_layer_not_listed"))
            return

        self.cbo_layer.setCurrentIndex(idx)

    def on_layer_changed(self):
        self._clear_label()

        self._disconnect_layer_signals()

        layer_id = self.cbo_layer.currentData()
        self.layer = QgsProject.instance().mapLayer(layer_id) if layer_id else None

        self.cbo_search_field.blockSignals(True)
        self.cbo_search_field.clear()
        if self.layer is not None:
            self.layer.featureAdded.connect(self.rebuild_features)
            self.layer.featureDeleted.connect(self.rebuild_features)
            self.layer.editingStopped.connect(self.rebuild_features)

            for field in self.layer.fields():
                self.cbo_search_field.addItem(field.name())
        self.cbo_search_field.blockSignals(False)

        self.rebuild_features()

    def rebuild_features(self, *args):
        self.feat_index = None
        self._clear_label()
        if self.layer is not None:
            self.features = list(self.layer.getFeatures(QgsFeatureRequest()))
        else:
            self.features = []

        has_features = len(self.features) > 0
        self.set_navigation_enabled(has_features)
        self.cbo_search_field.setEnabled(has_features)
        self.txt_search.setEnabled(has_features)
        self.update_count_label()
        self.rebuild_search_values()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def set_navigation_enabled(self, enabled):
        self.btn_prev.setEnabled(enabled)
        self.btn_next.setEnabled(enabled)

    def hop(self, direction):
        if not self.features:
            return
        if self.feat_index is None:
            self.feat_index = 0
        else:
            self.feat_index = (self.feat_index + direction) % len(self.features)

        self.focus_on_feature(self.features[self.feat_index])
        self.update_count_label()

    def update_count_label(self):
        if not self.features:
            self.lbl_count.setText(tr("count_none"))
        elif self.feat_index is None:
            self.lbl_count.setText(tr("count_total", len(self.features)))
        else:
            self.lbl_count.setText(tr("count_position", self.feat_index + 1, len(self.features)))

    def focus_on_feature(self, feature):
        geom = feature.geometry()
        if geom is None or geom.isNull():
            self.warn(tr("warn_no_geometry"))
            return

        self.iface.mapCanvas().zoomToFeatureIds(self.layer, [feature.id()])

        if self.chk_auto_select.isChecked():
            self.layer.selectByIds([feature.id()])
            self.layer.triggerRepaint()

        self.iface.mapCanvas().refresh()
        self._update_label(feature)

    # ------------------------------------------------------------------
    # Label annotation
    # ------------------------------------------------------------------
    def _clear_label(self):
        if self.label_item is not None:
            self.iface.mapCanvas().scene().removeItem(self.label_item)
            self.label_item = None

    def _update_label(self, feature):
        if not self.chk_show_label.isChecked():
            self._clear_label()
            return

        field_name = self.cbo_search_field.currentText()
        geom = feature.geometry()
        if self.layer is None or not field_name or geom is None or geom.isNull():
            self._clear_label()
            return

        value = feature[field_name]
        if value in (None, NULL):
            self._clear_label()
            return

        canvas = self.iface.mapCanvas()
        point = geom.centroid().asPoint()
        if self.layer.crs() != canvas.mapSettings().destinationCrs():
            transform = QgsCoordinateTransform(
                self.layer.crs(), canvas.mapSettings().destinationCrs(), QgsProject.instance()
            )
            point = transform.transform(point)

        if self.label_item is None:
            self.label_item = FeatureLabelItem(canvas)

        self.label_item.set_label(point, str(value))

    def on_toggle_label(self, checked):
        if not checked:
            self._clear_label()
        elif self.feat_index is not None and self.features:
            self._update_label(self.features[self.feat_index])

    def on_visibility_changed(self, visible):
        if not visible:
            self._clear_label()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def on_search_field_changed(self):
        self.rebuild_search_values()
        if self.feat_index is not None and self.features:
            self._update_label(self.features[self.feat_index])

    def rebuild_search_values(self):
        self.value_map = {}
        field_name = self.cbo_search_field.currentText()

        if self.layer is not None and field_name:
            seen_counts = {}
            for feature in self.features:
                value = feature[field_name]
                if value in (None, NULL):
                    continue
                text = str(value)
                seen_counts[text] = seen_counts.get(text, 0) + 1
                display = text if seen_counts[text] == 1 else "%s (%d)" % (text, seen_counts[text])
                self.value_map[display] = feature.id()

        self.completer.model().setStringList(sorted(self.value_map.keys(), key=str.lower))

    def on_search_selected(self, display_text):
        self.jump_to_value(display_text)

    def on_search_return(self):
        text = self.txt_search.text()
        if text in self.value_map:
            self.jump_to_value(text)
            return
        matches = [v for v in self.value_map if v.lower().startswith(text.lower())]
        if len(matches) == 1:
            self.jump_to_value(matches[0])
        elif not matches:
            self.warn(tr("warn_no_match"))

    def jump_to_value(self, display_text):
        feature_id = self.value_map.get(display_text)
        if feature_id is None:
            return

        for idx, feature in enumerate(self.features):
            if feature.id() == feature_id:
                self.feat_index = idx
                self.focus_on_feature(feature)
                self.update_count_label()
                break

        self.txt_search.clear()

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------
    def warn(self, message):
        self.iface.messageBar().pushMessage(self.PLUGIN_NAME, message, Qgis.MessageLevel.Warning)

    def closeEvent(self, event):
        self._clear_label()
        self.closingPlugin.emit()
        event.accept()
