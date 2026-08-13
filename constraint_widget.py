# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# @par CDI-Technologies, Vincent Majorczyk

from qgis.core import Qgis, QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QListWidget, QListWidgetItem, QSpinBox, QPushButton, QMessageBox, QLabel
)

from .debug import Debug
from .constraint_item import ConstraintType, ConstraintItem
from .constraint_item_widget import ConstraintItemWidget, ICON_SIZE
from .map_item_widget import MapItemWidget, _MAP_ICON_SIZE



## @brief Widget containing the constraint list and compute controls.
#
# Replaces the previous QTreeWidget + groupbox layout with a QListWidget
# whose items each embed a ConstraintItemWidget.  Configuration is done
# inline — no separate Save button is needed.
#
# Layout:
#   [QListWidget  with ConstraintItemWidgets + "+" add item at bottom]
#   [threshold spinbox]
#   [Compute button]
class ConstraintWidget(QWidget):

    ## @brief Constructor.
    # @param parent  Parent SuricatesWidget (must expose .suricates).
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        Debug.begin("ConstraintWidget::__init__")

        self.suricates = parent.suricates

        ## @var currentProject
        # Name of the currently selected RAIES project (str or None).
        self.currentProject = None

        self._buildUi()

        Debug.end("ConstraintWidget::__init__")

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _buildUi(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # -- Constraint list -------------------------------------------------
        self.w_listConstraints = QListWidget(self)
        self.w_listConstraints.setSpacing(2)
        self.w_listConstraints.setSelectionMode(QListWidget.NoSelection)
        self.w_listConstraints.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self.w_listConstraints, 1)

        # -- Threshold + Resolution + Compute --------------------------------
        bottom = QFormLayout()

        self.w_threshold = QSpinBox()
        self.w_threshold.setMinimum(0)
        self.w_threshold.setMaximum(100)
        self.w_threshold.setSingleStep(10)
        self.w_threshold.setSuffix(" %")
        bottom.addRow("Final Accepted Constraint (FAC)", self.w_threshold)

        # Resolution buttons + pixel count, stacked vertically on the right side
        res_container = QWidget()
        res_vbox = QVBoxLayout(res_container)
        res_vbox.setContentsMargins(0, 0, 0, 0)
        res_vbox.setSpacing(2)

        res_btns_row = QHBoxLayout()
        res_btns_row.setSpacing(4)
        self._res_btns = {}
        for val in (10, 100, 1000):
            btn = QPushButton(f"{val} m")
            btn.setCheckable(True)
            btn.setFixedWidth(64)
            btn.clicked.connect(lambda checked, v=val: self._onResolutionChanged(v))
            self._res_btns[val] = btn
            res_btns_row.addWidget(btn)
        res_btns_row.addStretch()
        res_vbox.addLayout(res_btns_row)

        self._lbl_pixels = QLabel()
        self._lbl_pixels.setStyleSheet("color: #888; font-size: 11px;")
        res_vbox.addWidget(self._lbl_pixels)

        bottom.addRow("Resolution:", res_container)

        layout.addLayout(bottom)

        self.w_compute = QPushButton("Compute")
        layout.addWidget(self.w_compute)

        self.setLayout(layout)

        # -- Signals ---------------------------------------------------------
        self.w_compute.clicked.connect(self.onCompute)
        self.w_threshold.valueChanged.connect(self.onChangeThreshold)

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    ## @brief Set the active project and repopulate the list.
    # @param name  Project name string, or None to clear.
    def setProject(self, name):
        if name is not None:
            Debug.begin("ConstraintWidget::setProject:" + name)
        else:
            Debug.begin("ConstraintWidget::setProject: (Empty project)")
        self.currentProject = name
        self.updateProject()
        Debug.end("ConstraintWidget::setProject")

    ## @brief Repopulate the list from the current project's config layer.
    def updateProject(self):
        Debug.begin("ConstraintWidget::updateProject")

        self.w_listConstraints.clear()

        if self.currentProject is None:
            self.setEnabled(False)
            Debug.end("ConstraintWidget::updateProject (Empty project)")
            return

        self.setEnabled(True)
        project = self.suricates.getProject(self.currentProject)
        if project is None:
            Debug.end("ConstraintWidget::updateProject (Error 1)")
            return

        configLayer = self.suricates.getConfig(project)
        if configLayer is None:
            Debug.end("ConstraintWidget::updateProject (Error 2)")
            return

        constraintsList = self.suricates.getConstraintsFromConfig(project, configLayer)

        # Map widget first, then regular constraints
        for constraint in constraintsList:
            if constraint.typeIn == ConstraintType.Map:
                self.w_threshold.blockSignals(True)
                self.w_threshold.setValue(int(constraint.priority))
                self.w_threshold.blockSignals(False)
                self._addMapItemWidget(constraint)
            else:
                self._addItemWidget(constraint)

        # Resolution buttons
        resolution = self.suricates.getResolution(self.currentProject)
        self._setResolutionButtons(resolution)

        # "+" button at the bottom of the list
        self._addPlusButton()

        Debug.end("ConstraintWidget::updateProject")

    # -----------------------------------------------------------------------
    # List management helpers
    # -----------------------------------------------------------------------

    def _addItemWidget(self, constraint: ConstraintItem):
        """Append a ConstraintItemWidget row to the list."""
        item_widget = ConstraintItemWidget(constraint, self)
        item_widget.changed.connect(self._onConstraintChanged)
        item_widget.deleted.connect(self.onDeleteConstraint)
        item_widget.expanded.connect(lambda iw=item_widget: self._onItemExpanded(iw))

        list_item = QListWidgetItem(self.w_listConstraints)
        list_item.setSizeHint(QSize(self.w_listConstraints.width(), ICON_SIZE + 12))
        self.w_listConstraints.addItem(list_item)
        self.w_listConstraints.setItemWidget(list_item, item_widget)

        # Update the list item height whenever the widget changes page
        def _onSizeChanged(li=list_item, iw=item_widget):
            li.setSizeHint(QSize(self.w_listConstraints.width(),
                                iw.sizeHint().height()))
        item_widget.sizeChanged.connect(_onSizeChanged)

    def _addMapItemWidget(self, constraint: ConstraintItem):
        """Insert the MapItemWidget as the first item in the list."""
        item_widget = MapItemWidget(constraint, self)
        item_widget.replaced.connect(self.onReplaceMap)

        list_item = QListWidgetItem()
        list_item.setSizeHint(QSize(self.w_listConstraints.width(), _MAP_ICON_SIZE + 12))
        self.w_listConstraints.insertItem(0, list_item)
        self.w_listConstraints.setItemWidget(list_item, item_widget)

    def _addPlusButton(self):
        """Append the '+' add-layer button as the last list item."""
        btn = QPushButton(self)
        btn.setIcon(QIcon(":/images/themes/default/mActionAdd.svg"))
        btn.setText("  Add selected layer")
        btn.setIconSize(QSize(20, 20))
        btn.setStyleSheet(
            "QPushButton { border: 1px dashed #aaa; border-radius: 6px;"
            " color: #666; padding: 6px; text-align: left; }"
            "QPushButton:hover { border-color: #4a90e2; color: #4a90e2; }"
        )
        btn.clicked.connect(self.onAddNewConstraint)

        list_item = QListWidgetItem(self.w_listConstraints)
        list_item.setSizeHint(QSize(self.w_listConstraints.width(), 40))
        self.w_listConstraints.addItem(list_item)
        self.w_listConstraints.setItemWidget(list_item, btn)

    def _onItemExpanded(self, expanded_widget):
        """Collapse all items except the one that just expanded."""
        for w in self._iterItemWidgets():
            if w is not expanded_widget:
                w.collapseToInfo()

    def _iterItemWidgets(self):
        """Yield every ConstraintItemWidget currently in the list."""
        for i in range(self.w_listConstraints.count()):
            w = self.w_listConstraints.itemWidget(self.w_listConstraints.item(i))
            if isinstance(w, ConstraintItemWidget):
                yield w

    def _findItemWidget(self, name: str):
        """Return the ConstraintItemWidget whose constraint.name matches, or None."""
        for w in self._iterItemWidgets():
            if w.constraint().name == name:
                return w
        return None

    def _setAllProgress(self, value: int):
        """Set all item widgets to progress page with the given value."""
        for w in self._iterItemWidgets():
            w.setProgress(value)

    def _setAllInfo(self):
        """Switch all item widgets back to info page."""
        for w in self._iterItemWidgets():
            w.showInfo()

    # -----------------------------------------------------------------------
    # Slots
    # -----------------------------------------------------------------------

    def _saveProject(self):
        """Save the QGIS project file. Warns if the project has no file yet."""
        from qgis.core import QgsProject
        if not QgsProject.instance().fileName():
            self.suricates.iface.messageBar().pushMessage(
                "Warning",
                "Save the QGIS project first (Ctrl+S) to persist layer references.",
                level=Qgis.Warning, duration=5)
            return
        QgsProject.instance().write()

    def _setResolutionButtons(self, resolution: int):
        """Check the button matching *resolution*, uncheck the others."""
        for val, btn in self._res_btns.items():
            btn.setChecked(val == resolution)
        self._updatePixelLabel(resolution)

    def _estimatePixelCount(self, resolution: int):
        """Return (pixels: int, reason: str).  pixels=0 means unknown/error."""
        if self.currentProject is None:
            return 0, "no project"
        project = self.suricates.getProject(self.currentProject)
        if project is None:
            return 0, "project not found"
        configLayer = self.suricates.getConfig(project)
        if configLayer is None:
            return 0, "no config"
        constraintsList = self.suricates.getConstraintsFromConfig(project, configLayer)
        map_c = next((c for c in constraintsList if c.typeIn == ConstraintType.Map), None)
        if map_c is None:
            return 0, "no Map layer"
        node = self.suricates.getLayer(project, map_c.name)
        if node is None or node.layer() is None:
            return 0, f"layer '{map_c.name}' missing from tree"
        ext = node.layer().extent()
        Debug.warning(f"_estimatePixelCount: layer={map_c.name} crs={node.layer().crs().authid()} w={ext.width():.1f} h={ext.height():.1f}")
        if ext.isEmpty() or ext.width() == 0 or ext.height() == 0:
            return 0, "empty extent"
        pixels = int((ext.width() / resolution) * (ext.height() / resolution))
        if pixels == 0:
            return 0, f"extent too small for {resolution}m resolution (CRS in degrees?)"
        return pixels, ""

    def _updatePixelLabel(self, resolution: int):
        """Update the pixel-count label and warn if > 4 M pixels."""
        pixels, reason = self._estimatePixelCount(resolution)
        if pixels <= 0:
            self._lbl_pixels.setText(f"— {reason}" if reason else "—")
            self._lbl_pixels.setStyleSheet("color: #aaa; font-size: 11px;")
            Debug.warning(f"_updatePixelLabel: pixels=0 reason={reason}")
            return
        if pixels < 1_000:
            text = f"~{pixels} px"
        elif pixels < 1_000_000:
            text = f"~{pixels / 1_000:.1f} kpx"
        else:
            text = f"~{pixels / 1_000_000:.2f} Mpx"
        if pixels > 4_000_000:
            self._lbl_pixels.setText(f"⚠ {text} (slow!)")
            self._lbl_pixels.setStyleSheet("color: #c44; font-size: 11px; font-weight: bold;")
        else:
            self._lbl_pixels.setText(text)
            self._lbl_pixels.setStyleSheet("color: #888; font-size: 11px;")

    def _onResolutionChanged(self, value: int):
        Debug.begin("ConstraintWidget::_onResolutionChanged")
        self._setResolutionButtons(value)
        self.suricates.setResolution(self.currentProject, value)
        Debug.end("ConstraintWidget::_onResolutionChanged")

    ## @brief Replace the Map layer with the currently active QGIS layer.
    def onReplaceMap(self):
        Debug.begin("ConstraintWidget::onReplaceMap")
        if not self.suricates.replaceMapLayer(self.currentProject):
            self.suricates.iface.messageBar().pushMessage(
                "Failure!", "replace Map layer", level=Qgis.Critical)
            Debug.end("ConstraintWidget::onReplaceMap (failure)")
            return
        self.updateProject()
        self._saveProject()
        Debug.end("ConstraintWidget::onReplaceMap (success)")

    ## @brief Auto-save handler: called when a ConstraintItemWidget emits changed().
    def _onConstraintChanged(self, constraint: ConstraintItem):
        Debug.begin("ConstraintWidget::_onConstraintChanged")
        if not self.suricates.saveConstraint(self.currentProject, constraint, False):
            self.suricates.iface.messageBar().pushMessage(
                "Failure!", "save constraint:", level=Qgis.Critical)
        Debug.end("ConstraintWidget::_onConstraintChanged")

    ## @brief Add the currently selected QGIS layer as a new constraint.
    def onAddNewConstraint(self):
        from .SuricatesApp import SuricatesInstance
        Debug.begin("ConstraintWidget::onAddNewConstraint")

        project = self.suricates.getProject(self.currentProject)
        if project is None:
            Debug.end("ConstraintWidget::onAddNewConstraint (Error 1)")
            return

        configLayer = self.suricates.getConfig(project)
        if configLayer is None:
            Debug.end("ConstraintWidget::onAddNewConstraint (Error 2)")
            return

        constraintsList = self.suricates.getConstraintsFromConfig(project, configLayer)
        haveMap = any(c.typeIn == ConstraintType.Map for c in constraintsList)

        layer = self.suricates.copyCurrentLayer(self.currentProject)
        if layer is None:
            Debug.end("ConstraintWidget::onAddNewConstraint (failure)")
            return

        if haveMap:
            # New unconfigured constraint: S/S signals "needs configuration"
            constraint = ConstraintItem(layer.name())
        else:
            constraint = ConstraintItem(layer.name(), 0, 5, ConstraintType.Map)

        if not self.suricates.saveConstraint(self.currentProject, constraint, True):
            self.suricates.iface.messageBar().pushMessage(
                "Failure!", "create new constraint:", level=Qgis.Critical)
            Debug.end("ConstraintWidget::onAddNewConstraint (failure)")
            return

        if not haveMap:
            # First layer is the Map — write default resolution into its config row
            self.suricates.setResolution(self.currentProject, 100)

        if not haveMap:
            # Map widget inserted at position 0 — full refresh is simpler
            self.updateProject()
        else:
            # Regular constraint: append before the '+' button
            last = self.w_listConstraints.count() - 1
            self.w_listConstraints.takeItem(last)
            self._addItemWidget(constraint)
            self._addPlusButton()

        self._saveProject()
        self.suricates.iface.messageBar().pushMessage(
            "Success!", "create new constraint", level=Qgis.Success, duration=3)
        Debug.end("ConstraintWidget::onAddNewConstraint (success)")

    ## @brief Delete the constraint whose layer name is *name*.
    # Connected to ConstraintItemWidget.deleted signal.
    def onDeleteConstraint(self, name: str):
        Debug.begin("ConstraintWidget::onDeleteConstraint")
        self.suricates.deleteConstraint(self.currentProject, name)
        self.updateProject()
        self._saveProject()
        Debug.end("ConstraintWidget::onDeleteConstraint")

    ## @brief Save the threshold value when the spinbox changes.
    def onChangeThreshold(self, value: int):
        Debug.begin("ConstraintWidget::onChangeThreshold")
        project = self.suricates.getProject(self.currentProject)
        if project is None:
            Debug.end("ConstraintWidget::onChangeThreshold (Error 1)")
            return

        configLayer = self.suricates.getConfig(project)
        if configLayer is None:
            Debug.end("ConstraintWidget::onChangeThreshold (Error 2)")
            return

        constraintsList = self.suricates.getConstraintsFromConfig(project, configLayer)
        current = next((c for c in constraintsList if c.typeIn == ConstraintType.Map), None)
        if current is None:
            Debug.end("ConstraintWidget::onChangeThreshold (Error 3)")
            return

        current.priority = value
        if not self.suricates.saveConstraint(self.currentProject, current, False):
            self.suricates.iface.messageBar().pushMessage(
                "Failure!", "save constraint:", level=Qgis.Critical)
        Debug.end("ConstraintWidget::onChangeThreshold")

    ## @brief Launch computation when the user clicks Compute.
    def onCompute(self):
        from .suricates_algo import SuricatesAlgo
        Debug.begin("ConstraintWidget::onCompute")

        project = self.suricates.getProject(self.currentProject)
        if project is None:
            Debug.end("ConstraintWidget::onCompute (Error 1)")
            return

        configLayer = self.suricates.getConfig(project)
        if configLayer is None:
            Debug.end("ConstraintWidget::onCompute (Error 2)")
            return

        constraintsList = self.suricates.getConstraintsFromConfig(project, configLayer)
        inputList = []
        # Map absolute path -> item widget BEFORE renaming constraint.name
        path_to_widget = {}
        for constraint in constraintsList:
            layer = self.suricates.getLayer(project, constraint.name)
            if layer is not None and layer.layer() is not None:
                # Find the item widget by display name before overwriting it
                w = self._findItemWidget(constraint.name)
                constraint.name = layer.layer().source()
                if w is not None:
                    path_to_widget[constraint.name] = w
                    Debug.warning('path_to_widget: ' + constraint.name + ' -> widget OK')
                else:
                    Debug.warning('path_to_widget: ' + constraint.name + ' -> NO WIDGET')
                inputList.append(constraint)

        resolution = self.suricates.getResolution(self.currentProject)
        a = SuricatesAlgo(inputList, self.currentProject, self.suricates, resolution)
        a.deleteTmp = (
            QMessageBox.question(
                None,
                "Delete temporary files?",
                "Do you want to delete temporary files?"
            ) == QMessageBox.StandardButton.Yes
        )

        # Switch all item widgets to progress page
        self._setAllProgress(0)

        # Poll constraint.progress every second via a QTimer.
        from qgis.PyQt.QtCore import QTimer as _QTimer
        _poll = _QTimer(self)
        _poll.setInterval(1000)

        def _pollProgress():
            Debug.warning('_pollProgress: ' + str(len(a.constraints)) + ' constraints, ' + str(len(path_to_widget)) + ' widgets')
            for constraint in a.constraints:
                Debug.warning('  constraint: ' + str(constraint.name) + ' progress=' + str(constraint.progress))
                w = path_to_widget.get(constraint.name)
                Debug.warning('  widget found: ' + str(w is not None))
                if w is not None:
                    try:
                        w.setProgress(constraint.progress)
                    except RuntimeError:
                        # The widget (QProgressBar) was deleted mid-computation — e.g. the
                        # user removed a layer. Harmless: skip this widget and keep polling.
                        pass

        def _onAlgoFinished():
            _poll.stop()
            self._setAllInfo()
            self.updateProject()

        _poll.timeout.connect(_pollProgress)
        a.taskCompleted.connect(_onAlgoFinished)
        a.taskTerminated.connect(_onAlgoFinished)
        _poll.start()

        self.suricates.tasks.append(a)
        QgsApplication.taskManager().addTask(a)
        Debug.end("ConstraintWidget::onCompute")
