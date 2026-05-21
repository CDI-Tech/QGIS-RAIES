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
    QListWidget, QListWidgetItem, QSpinBox, QPushButton, QMessageBox
)

from .debug import Debug
from .constraint_item import ConstraintType, ConstraintItem
from .constraint_item_widget import ConstraintItemWidget, ICON_SIZE



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

        # -- Threshold + Compute ---------------------------------------------
        bottom = QFormLayout()
        self.w_threshold = QSpinBox()
        self.w_threshold.setMinimum(0)
        self.w_threshold.setMaximum(100)
        self.w_threshold.setSingleStep(10)
        self.w_threshold.setSuffix(" %")
        bottom.addRow("Final Accepted Constraint (FAC)", self.w_threshold)
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

        for constraint in constraintsList:
            if constraint.typeIn == ConstraintType.Map:
                self.w_threshold.blockSignals(True)
                self.w_threshold.setValue(int(constraint.priority))
                self.w_threshold.blockSignals(False)
            else:
                self._addItemWidget(constraint)

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

        list_item = QListWidgetItem(self.w_listConstraints)
        list_item.setSizeHint(QSize(self.w_listConstraints.width(), ICON_SIZE + 12))
        self.w_listConstraints.addItem(list_item)
        self.w_listConstraints.setItemWidget(list_item, item_widget)

        # Update the list item height whenever the widget changes page
        def _onSizeChanged(li=list_item, iw=item_widget):
            li.setSizeHint(QSize(self.w_listConstraints.width(),
                                iw.sizeHint().height()))
        item_widget.sizeChanged.connect(_onSizeChanged)

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

        # Remove the '+' button, add the new item, then re-add the '+' button
        # (it is always the last item)
        last = self.w_listConstraints.count() - 1
        self.w_listConstraints.takeItem(last)
        self._addItemWidget(constraint)
        self._addPlusButton()

        self.suricates.iface.messageBar().pushMessage(
            "Success!", "create new constraint", level=Qgis.Success, duration=3)
        Debug.end("ConstraintWidget::onAddNewConstraint (success)")

    ## @brief Delete the constraint whose layer name is *name*.
    # Connected to ConstraintItemWidget.deleted signal.
    def onDeleteConstraint(self, name: str):
        Debug.begin("ConstraintWidget::onDeleteConstraint")
        self.suricates.deleteConstraint(self.currentProject, name)
        self.updateProject()
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

        a = SuricatesAlgo(inputList, self.currentProject, self.suricates)
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
                    w.setProgress(constraint.progress)

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
