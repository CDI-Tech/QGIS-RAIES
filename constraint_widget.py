# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# @par CDI-Technologies, Vincent Majorczyk

## @brief simple dockwidget (panel) which contains a SuricatesWidget
#
# #
# ![User interface classes imbrication](assets\GuiStructure.png)
from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import *

from .debug import Debug
from .constraint_item import ConstraintType, ConstraintItem

## @brief widget which contains parameter interface for constrains configuration
#
# this interface contains:
# - a list interface to add, remove and select a constraints;
# - a group with radiobox and field to select type and parameter of the selected constraint (from the list interface);
# - a field for threshold selection and a button to start computation;
#
# ![User interface classes imbrication](assets\GuiStructure.png)
#
# ![User interface: list of constrained layers](assets\UserManual_ListOfConstraints.png)
#
# ![User interface: constraints configuration](assets\UserManual_ConstraintConfiguration.png)
class ConstraintWidget(QWidget):
    ## @var suricates
    # current SuricatesInstance

    ## @var w_listConstraints
    # QTreeWidget for a list of constrained layers

    ## @var w_buttonAdd
    # QPushButton for adding new constrained layer

    ## @var w_buttonDel
    # QPushButton for deletion of the selected constrained layer

    ## @var w_nearInRB
    # QRadioButton for the 'Near' option for the 'Inside' area

    ## @var w_farInRB
    # QRadioButton for the 'Far' option for the 'Inside' area

    ## @var w_inInRB
    # QRadioButton for the 'In' option for the 'Inside' area

    ## @var w_outInRB
    # QRadioButton for the 'Out' option for the 'Inside' area

    ## @var w_excludeInRB
    # QRadioButton for the 'Exclude' option for the 'Inside' area

    ## @var w_nearOutRB
    # QRadioButton for the 'Near' option for the 'Outside' area

    ## @var w_farOutRB
    # QRadioButton for the 'Far' option for the 'Outside' area

    ## @var w_inOutRB
    # QRadioButton for the 'In' option for the 'Outside' area

    ## @var w_outOutRB
    # QRadioButton for the 'Out' option for the 'Outside' area

    ## @var w_excludeOutRB
    # QRadioButton for the 'Exclude' option for the 'Outside' area

    ## @var w_buffer
    # QSpinBox for the buffer (distance around layer items)

    ## @var w_priority
    # QSpinBox for the priority/weight of the raster

    ## @var w_save
    # QPushButton to save the parameters of the constrained layer

    ## @var w_compute
    # QPushButton to run computation
    # @see SuricatesAlgo.run()

    ## @var w_threshold
    # QSpinBox for the threshold used on the cumulation raster

    ## @var currentProject
    # name of the current project (string)

    ## @brief constructor of the widget
    # @param parent parent widget (QWidget)
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        Debug.begin("ConstraintWidget::__init__")

        self.suricates = parent.suricates

        selectl = QVBoxLayout(self)
        selectl2 = QHBoxLayout(self)
        self.w_buttonAdd = QPushButton("Add", self)
        self.w_buttonDel = QPushButton("Del", self)
        selectl2.addWidget(self.w_buttonAdd)
        selectl2.addWidget(self.w_buttonDel)
        selectl.addLayout(selectl2)

        self.w_listConstraints = QTreeWidget(self)
        self.w_listConstraints.setHeaderLabels(["Name", "Inside", "Outside", "Distance", "Weight"])
        selectl.addWidget(self.w_listConstraints)

        groupw = QGroupBox("Constraints on selected layer:", self)
        groupl = QVBoxLayout()
        groupc = QHBoxLayout()
        groupc1 = QVBoxLayout()
        groupc2 = QVBoxLayout()

        self.w_farInRB = QRadioButton("Repulsive", self)
        self.w_nearInRB = QRadioButton("Attractive", self)
        self.w_inInRB = QRadioButton("Included", self)
        self.w_outInRB = QRadioButton("Excluded", self)
        self.w_outInRB.setToolTip("only applies to one selected layer whereas ")
        self.w_excludeInRB = QRadioButton("Sanctuarized", self)
        self.w_excludeInRB.setToolTip("applies accross all project layers.")

        self.w_farOutRB = QRadioButton("Repulsive", self)
        self.w_nearOutRB = QRadioButton("Attractive", self)
        self.w_inOutRB = QRadioButton("Included", self)
        self.w_outOutRB = QRadioButton("Excluded", self)
        self.w_outOutRB.setToolTip("only applies to one selected layer whereas ")
        self.w_excludeOutRB = QRadioButton("Sanctuarized", self)
        self.w_excludeOutRB.setToolTip("applies accross all project layers.")

        groupclw = QGroupBox("Inside the object")
        groupc1.addWidget(self.w_farInRB)
        groupc1.addWidget(self.w_nearInRB)
        groupc1.addWidget(self.w_inInRB)
        groupc1.addWidget(self.w_outInRB)
        groupc1.addWidget(self.w_excludeInRB)

        groupc2.addWidget(self.w_farOutRB)
        groupc2.addWidget(self.w_nearOutRB)
        groupc2.addWidget(self.w_inOutRB)
        groupc2.addWidget(self.w_outOutRB)
        groupc2.addWidget(self.w_excludeOutRB)

        groupc1b = QGroupBox("Inside:")
        groupc1b.setToolTip("Contraint inside the object")
        groupc1b.setLayout(groupc1)
        groupc2b = QGroupBox("Outside:")
        groupc2b.setToolTip("Contraint on the outside of object")
        groupc2b.setLayout(groupc2)

        groupc.addWidget(groupc1b)
        groupc.addWidget(groupc2b)
        groupl.addLayout(groupc)

        formL = QFormLayout()
        self.w_buffer = QSpinBox()
        self.w_buffer.setMinimum(0)
        self.w_buffer.setMaximum(30000)
        self.w_buffer.setSingleStep(100)
        self.w_buffer.setSuffix(" m")

        self.w_priority = QSpinBox()
        self.w_priority.setMinimum(1)
        self.w_priority.setMaximum(10)
        self.w_priority.setSingleStep(1)

        formL.addRow("Neighborhood distance (m)", self.w_buffer)
        formL.addRow("Layer’s weight (1-10)", self.w_priority)

        self.w_save = QPushButton("Save")
        layout = QHBoxLayout()
        layout.addStretch()
        layout.addWidget(self.w_save)

        self.w_compute = QPushButton("Compute")

        self.w_threshold = QSpinBox()
        self.w_threshold.setMinimum(0)
        self.w_threshold.setMaximum(100)
        self.w_threshold.setSingleStep(10)
        thresholdform = QFormLayout()
        thresholdform.addRow("Final Accepted Constraint (0<FAC>100)", self.w_threshold)

        groupl.addLayout(formL)
        groupl.addLayout(layout)
        groupw.setLayout(groupl)
        selectl.addWidget(groupw)
        selectl.addLayout(thresholdform)
        selectl.addWidget(self.w_compute)
        self.setLayout(selectl)

        self.w_buttonAdd.clicked.connect(self.onAddNewConstraint)
        self.w_buttonDel.clicked.connect(self.onDeleteConstraint)
        self.w_listConstraints.itemSelectionChanged.connect(self.onSelectedConstraintChanged)
        self.w_save.clicked.connect(self.onSave)
        self.w_compute.clicked.connect(self.onCompute)
        self.w_threshold.valueChanged.connect(self.onChangeThreshold)

        Debug.end("ConstraintWidget::__init__")

    ## @brief set the current project and update the list of constraints
    # @param name of the current project
    def setProject(self, name):
        if name != None:
            Debug.begin("ConstraintWidget::setProject:" + name)
        else:
            Debug.begin("ConstraintWidget::setProject: (Empty project)")

        self.currentProject = name
        self.updateProject()
        Debug.end("ConstraintWidget::setProject")

    ## @brief update the list of constraints
    def updateProject(self):
        from .SuricatesApp import SuricatesInstance

        Debug.begin("ConstraintWidget::updateProject")
        self.w_save.setEnabled(False)

        self.setOptionEnabled(False)
        if self.currentProject == None:
            self.setEnabled(False)
            Debug.end("ConstraintWidget::updateProject (Empty project)")
            return
        else:
            self.setEnabled(True)

        project = self.suricates.getProject(self.currentProject)
        if project == None:
            Debug.end("ConstraintWidget::updateProject (Error 1)")
            return
        Debug.print("selection:" + project.name())
        configLayer = self.suricates.getConfig(project)
        if configLayer == None:
            Debug.end("ConstraintWidget::updateProject (Error 2)")
            return

        constraintsList = self.suricates.getConstraintsFromConfig(project, configLayer)

        self.w_listConstraints.clear()
        # current code here
        for constraint in constraintsList:
            twi = QTreeWidgetItem([constraint.name, SuricatesInstance.ConstraintTypeToString(constraint.typeIn),
                                   SuricatesInstance.ConstraintTypeToString(constraint.typeOut), str(constraint.buffer),
                                   str(constraint.priority)])
            if not constraint.exists:
                twi.setIcon(0, QIcon(":/images/themes/default/mActionRemove.svg"))
            self.w_listConstraints.addTopLevelItem(twi)
            if constraint.typeIn == ConstraintType.Map:
                Debug.print("threshold:" + str(constraint.priority) + " " + str(constraint.priority))
                self.w_threshold.blockSignals(True)
                self.w_threshold.setValue(int(constraint.priority))
                self.w_threshold.blockSignals(False)

        Debug.end("ConstraintWidget::updateProject")

    ## @brief update the properties of the selected constraint
    # @param name name of the constraint
    def updateOption(self, name):
        Debug.begin("ConstraintWidget::updateOption")
        project = self.suricates.getProject(self.currentProject)
        if project == None:
            Debug.end("ConstraintWidget::updateOption (Error 1)")
            return
        Debug.print("selection:" + project.name())
        configLayer = self.suricates.getConfig(project)
        if configLayer == None:
            Debug.end("ConstraintWidget::updateOption (Error 2)")
            return

        constraintsList = self.suricates.getConstraintsFromConfig(project, configLayer)

        current = None
        for constraint in constraintsList:
            if constraint.name == name:
                current = constraint

        if current == None:
            self.setOptionEnabled(False)
            Debug.end("ConstraintWidget::updateOption (Error 3)")
            return

        self.w_save.setEnabled(True)

        if current.typeIn == ConstraintType.Map:
            self.w_nearInRB.setEnabled(False)
            self.w_farInRB.setEnabled(False)
            self.w_inInRB.setEnabled(False)
            self.w_outInRB.setEnabled(False)
            self.w_excludeInRB.setEnabled(False)

            self.w_nearInRB.setChecked(False)
            self.w_farInRB.setChecked(False)
            self.w_inInRB.setChecked(False)
            self.w_outInRB.setChecked(False)
            self.w_excludeInRB.setChecked(False)

            self.w_nearOutRB.setEnabled(False)
            self.w_farOutRB.setEnabled(False)
            self.w_inOutRB.setEnabled(False)
            self.w_outOutRB.setEnabled(False)
            self.w_excludeOutRB.setEnabled(False)

            self.w_nearOutRB.setChecked(False)
            self.w_farOutRB.setChecked(False)
            self.w_inOutRB.setChecked(False)
            self.w_outOutRB.setChecked(False)
            self.w_excludeOutRB.setChecked(False)

            self.w_buffer.setEnabled(True)
            self.w_priority.setEnabled(False)
        else:
            self.setOptionEnabled(True)
            if current.typeIn == ConstraintType.Attractive:
                self.w_nearInRB.setChecked(True)
            elif current.typeIn == ConstraintType.Repulsive:
                self.w_farInRB.setChecked(True)
            elif current.typeIn == ConstraintType.Included:
                self.w_inInRB.setChecked(True)
            elif current.typeIn == ConstraintType.Excluded:
                self.w_outInRB.setChecked(True)
            elif current.typeIn == ConstraintType.Sanctuarized:
                self.w_excludeInRB.setChecked(True)

            if current.typeOut == ConstraintType.Attractive:
                self.w_nearOutRB.setChecked(True)
            elif current.typeOut == ConstraintType.Repulsive:
                self.w_farOutRB.setChecked(True)
            elif current.typeOut == ConstraintType.Included:
                self.w_inOutRB.setChecked(True)
            elif current.typeOut == ConstraintType.Excluded:
                self.w_outOutRB.setChecked(True)
            elif current.typeOut == ConstraintType.Sanctuarized:
                self.w_excludeOutRB.setChecked(True)

        self.w_buffer.setValue(int(current.buffer))
        self.w_priority.setValue(int(current.priority / 10))

        Debug.end("ConstraintWidget::updateOption")

    ## @brief enable radiobuttons and fields of constraints configuration
    # @param enabled activate (or desactivate) the radiobox (contraints type) and spinbox (buffer ans priority)
    def setOptionEnabled(self, enabled):
        Debug.begin("ConstraintWidget::setOptionEnabled")
        self.w_nearInRB.setEnabled(enabled)
        self.w_farInRB.setEnabled(enabled)
        self.w_inInRB.setEnabled(enabled)
        self.w_outInRB.setEnabled(enabled)
        self.w_excludeInRB.setEnabled(enabled)

        self.w_nearOutRB.setEnabled(enabled)
        self.w_farOutRB.setEnabled(enabled)
        self.w_inOutRB.setEnabled(enabled)
        self.w_outOutRB.setEnabled(enabled)
        self.w_excludeOutRB.setEnabled(enabled)

        self.w_buffer.setEnabled(enabled)
        self.w_priority.setEnabled(enabled)
        Debug.end("ConstraintWidget::setOptionEnabled")

    ## get the configuration from name
    # @param name name of the constraint
    # @return the constraint data
    def getConstraintFromName(self, name):
        Debug.begin("ConstraintWidget::getConstraintFromName")
        project = self.suricates.getProject(self.currentProject)
        if project == None:
            Debug.end("ConstraintWidget::getConstraintFromName (Error 1)")
            return
        Debug.print("selection:" + project.name())
        configLayer = self.suricates.getConfig(project)
        if configLayer == None:
            Debug.end("ConstraintWidget::getConstraintFromName (Error 2)")
            return

        constraintsList = self.suricates.getConstraintsFromConfig(project, configLayer)

        current = None
        for constraint in constraintsList:
            if constraint.name == name:
                current = constraint

        if current == None:
            self.setOptionEnabled(False)
            Debug.end("ConstraintWidget::getConstraintFromName (Error 3)")
            return

        Debug.end("ConstraintWidget::getConstraintFromName")
        return current

    ## @brief compute constraints when user click button
    #
    # execute the process to create raster of constraints
    def onCompute(self):
        from .suricates_algo import SuricatesAlgo
        Debug.begin("ConstraintWidget::onCompute")
        project = self.suricates.getProject(self.currentProject)
        if project == None:
            Debug.end("ConstraintWidget::onCompute (Error 1)")
            return
        Debug.print("selection:" + project.name())
        configLayer = self.suricates.getConfig(project)
        if configLayer == None:
            Debug.end("ConstraintWidget::onCompute (Error 2)")
            return

        constraintsList = self.suricates.getConstraintsFromConfig(project, configLayer)
        intputList = list()

        for constraint in constraintsList:
            layer = self.suricates.getLayer(project, constraint.name)
            if (layer != None and layer.layer() != None):
                constraint.name = layer.layer().source()
                intputList.append(constraint)

        a = SuricatesAlgo(intputList, self.currentProject, self.suricates)
        a.deleteTmp = QMessageBox.question(None, "delete temporary files?",
                                           "do you want delete temporary file?") == QMessageBox.StandardButton.Yes

        self.suricates.tasks.append(a)
        # a.run()
        # a.finished(True)
        QgsApplication.taskManager().addTask(a)

        Debug.end("ConstraintWidget::onCompute")

    ## @brief save parameters of the current constraint when user click button
    def onSave(self):
        from .SuricatesApp import SuricatesInstance
        # get the type
        Debug.begin("ConstraintWidget::onSave")
        if not self.w_priority.isEnabled():
            typeIn = ConstraintType.Map
        elif self.w_nearInRB.isChecked():
            typeIn = ConstraintType.Attractive
        elif self.w_farInRB.isChecked():
            typeIn = ConstraintType.Repulsive
        elif self.w_inInRB.isChecked():
            typeIn = ConstraintType.Included
        elif self.w_outInRB.isChecked():
            typeIn = ConstraintType.Excluded
        elif self.w_excludeInRB.isChecked():
            typeIn = ConstraintType.Sanctuarized
        else:
            Debug.end("ConstraintWidget::onSave (Error 1)")
            return

        if typeIn == ConstraintType.Map:
            typeOut = ConstraintType.Excluded
        elif self.w_nearOutRB.isChecked():
            typeOut = ConstraintType.Attractive
        elif self.w_farOutRB.isChecked():
            typeOut = ConstraintType.Repulsive
        elif self.w_inOutRB.isChecked():
            typeOut = ConstraintType.Included
        elif self.w_outOutRB.isChecked():
            typeOut = ConstraintType.Excluded
        elif self.w_excludeOutRB.isChecked():
            typeOut = ConstraintType.Sanctuarized
        else:
            Debug.end("ConstraintWidget::onSave (Error 1)")
            return

        Debug.print("type:" + SuricatesInstance.ConstraintTypeToString(type))

        # get the distance
        distance = self.w_buffer.value()
        Debug.print("distance:" + str(distance))

        # get the priority
        priority = self.w_priority.value() * 10
        Debug.print("priority:" + str(priority))

        list = self.w_listConstraints.selectedItems()
        if len(list) == 0:
            self.setOptionEnabled(False)
            Debug.end("ConstraintWidget::onSave (Error 2)")
            return

        treeitem = list[0]
        name = treeitem.text(0)

        constraint = self.getConstraintFromName(name)
        if constraint == None:
            Debug.end("ConstraintWidget::onSave (Error 3)")
            return

        constraint.typeIn = typeIn
        constraint.typeOut = typeOut
        constraint.priority = priority
        constraint.buffer = distance

        if not self.suricates.saveConstraint(self.currentProject, constraint, False):
            self.suricates.iface.messageBar().pushMessage("Faillure!", "save constraint:", level=Qgis.Critical)
            Debug.end("ConstraintWidget::onSave (Error 4)")
            return

        treeitem.setText(1, SuricatesInstance.ConstraintTypeToString(constraint.typeIn))
        treeitem.setText(2, SuricatesInstance.ConstraintTypeToString(constraint.typeOut))
        treeitem.setText(3, str(distance))
        treeitem.setText(4, str(priority))

        Debug.end("ConstraintWidget::onSave")
        return

    ## @brief click on the button to create a new constraint
    #
    # @msc
    # Sender,Receiver;
    # Sender->Receiver [label="Command()", URL="\ref Receiver::Command()"];
    # Sender<-Receiver [label="Ack()", URL="\ref Ack()", ID="1"];
    # @endmsc
    #
    def onAddNewConstraint(self):
        from .SuricatesApp import SuricatesInstance
        Debug.begin("ConstraintWidget::onAddNewConstraint")
        project = self.suricates.getProject(self.currentProject)
        if project == None:
            Debug.end("ConstraintWidget::onAddNewConstraint (Error 1)")
            return
        Debug.print("selection:" + project.name())
        configLayer = self.suricates.getConfig(project)
        if configLayer == None:
            Debug.end("ConstraintWidget::onAddNewConstraint (Error 2)")
            return

        constraintsList = self.suricates.getConstraintsFromConfig(project, configLayer)

        haveMap = False
        for c in constraintsList:
            if c.typeIn == ConstraintType.Map:
                haveMap = True

        layer = self.suricates.copyCurrentLayer(self.currentProject)
        if layer == None:
            Debug.end("ConstraintWidget::onAddNewConstraint (faillure)")
            return

        if haveMap:
            constraint = ConstraintItem(layer.name())
        else:
            constraint = ConstraintItem(layer.name(), 0, 5, ConstraintType.Map)

        if not self.suricates.saveConstraint(self.currentProject, constraint, True):
            self.suricates.iface.messageBar().pushMessage("Faillure!", "create new constraint:", level=Qgis.Critical)
            Debug.end("ConstraintWidget::onAddNewConstraint (faillure)")
            return

        twi = QTreeWidgetItem([constraint.name, SuricatesInstance.ConstraintTypeToString(constraint.typeIn),
                               SuricatesInstance.ConstraintTypeToString(constraint.typeOut), str(constraint.buffer),
                               str(constraint.priority)])
        self.w_listConstraints.addTopLevelItem(twi)

        self.suricates.iface.messageBar().pushMessage("Success!", "create new constraint", level=Qgis.Success,
                                                      duration=3)
        Debug.end("ConstraintWidget::onAddNewConstraint (success)")
        return

    ## @brief click on a item of the constraint list
    def onSelectedConstraintChanged(self):
        Debug.begin("ConstraintWidget::onSelectedConstraintChanged")
        list = self.w_listConstraints.selectedItems()
        if len(list) == 0:
            self.setOptionEnabled(False)
            Debug.end("ConstraintWidget::onSelectedConstraintChanged")
            return

        current = list[0]
        name = current.text(0)
        Debug.print(name)
        self.updateOption(name)

        Debug.end("ConstraintWidget::onSelectedConstraintChanged")
        return

    ## @brief click on the button to delete constraint
    def onDeleteConstraint(self):
        Debug.begin("ConstraintWidget::onDeleteConstraint")
        list = self.w_listConstraints.selectedItems()
        if len(list) == 0:
            self.setOptionEnabled(False)
            Debug.end("ConstraintWidget::onSelectedConstraintChanged")
            return

        current = list[0]
        name = current.text(0)

        self.suricates.deleteConstraint(self.currentProject, name)
        self.updateProject()

        Debug.end("ConstraintWidget::onDeleteConstraint")
        return

    ## @brief change the value of the threshold
    def onChangeThreshold(self, value):
        Debug.begin("ConstraintWidget::onChangeThreshold")
        project = self.suricates.getProject(self.currentProject)
        if project == None:
            Debug.end("ConstraintWidget::onChangeThreshold (Error 1)")
            return
        Debug.print("selection:" + project.name())
        configLayer = self.suricates.getConfig(project)
        if configLayer == None:
            Debug.end("ConstraintWidget::onChangeThreshold (Error 2)")
            return

        constraintsList = self.suricates.getConstraintsFromConfig(project, configLayer)

        current = None
        for constraint in constraintsList:
            if constraint.typeIn == ConstraintType.Map:
                current = constraint

        if current == None:
            Debug.end("ConstraintWidget::onChangeThreshold (Error 3)")
            return

        current.priority = value

        ok = self.suricates.saveConstraint(self.currentProject, current, False)
        if not ok:
            self.suricates.iface.messageBar().pushMessage("Faillure!", "save constraint:", level=Qgis.Critical)
            Debug.end("ConstraintWidget::onChangeThreshold (Error 4)")
            return

        Debug.end("ConstraintWidget::onChangeThreshold")
        return