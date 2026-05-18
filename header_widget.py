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

## @brief widget with controls to select, create and delete projects
#
# ![User interface classes imbrication](assets\GuiStructure.png)
#
# ![User interface: management of projects](assets\UserManuel_Project.png)
class HeaderWidget(QGroupBox):
    ## @var suricates
    # current SuricatesInstance

    ## @brief constructor
    # @param parent parent (QWidget)
    def __init__(self, parent=None):
        QGroupBox.__init__(self, "Projects", parent)
        Debug.begin("HeaderWidget::__init__")

        self.suricates = parent.suricates

        # build content of the widget
        ## first line
        ### create the label 'selection'
        label1 = QLabel("Selection",self)

        ### create a combobox to list projects
        self.combobox_project = QComboBox(self)

        ### create button to remove the project selected by the combobox
        self.button_delproject = QPushButton(self)
        self.button_delproject.setIcon(QIcon(":/images/themes/default/mActionRemove.svg"))
        self.button_delproject.setToolTip("Delete project")
        self.button_delproject.setMaximumWidth(self.button_delproject.sizeHint().height())

        ## second line
        ### create the label 'new'
        label2 = QLabel("New",self)

        ### create a combobox to list projects
        self.newlineedit_project = QLineEdit(self)

        ### create button to add a new project
        self.button_newproject = QPushButton(self)
        self.button_newproject.setIcon(QIcon(":/images/themes/default/mActionAdd.svg"))
        self.button_newproject.setToolTip("New project")
        self.button_newproject.setMaximumWidth(self.button_newproject.sizeHint().height())
        self.button_newproject.setEnabled(False)

        ### create global layout (grid) to order widgets:
        ### 'Selection', combobox, button 'delete'
        ### 'New', text field, button 'new'
        selectl = QGridLayout(self)
        selectl.addWidget(label1,0,0)
        selectl.addWidget(self.combobox_project,0,1)
        selectl.addWidget(self.button_delproject,0,2)
        selectl.addWidget(label2,1,0)
        selectl.addWidget(self.newlineedit_project,1,1)
        selectl.addWidget(self.button_newproject,1,2)

        ## set the layout at the groupbox
        self.setLayout(selectl)

        ## connections
        ### if user clicks on the button 'new' then program calls the method 'onCreateNewProject'
        self.button_newproject.clicked.connect(self.onCreateNewProject)
        ### if user clicks on the button 'delete' then program calls the method 'onDeleteProject'
        self.button_delproject.clicked.connect(self.onDeleteProject)
        ### if user edit the text field then the program calls the method 'onTextEdited'
        self.newlineedit_project.textChanged.connect(self.onTextEdited)
        ### if user change the selected item of the combobox then the program call the method 'onSelectionChange'
        self.combobox_project.currentTextChanged.connect(self.onSelectionChange)
        Debug.end("HeaderWidget::__init__")
        return

    ## @brief display projects in the combobox
    # @param projects map of the projects
    def setProjects(self, projects):
        Debug.begin("HeaderWidget::setProjects")
        self.combobox_project.clear()
        for x in projects.keys():
            self.combobox_project.addItem(x)
        Debug.end("HeaderWidget::setProjects")
        return

    ## @brief called if user edit text in line edit (name of the new project)
    # if the text is empty or corresponds to an existing project name then the button 'new project' is desactivated;
    # else the button 'new project' is enabled;
    def onTextEdited(self):
        Debug.begin("HeaderWidget::onTextEdited")
        t = self.newlineedit_project.text()
        if t == "" or self.suricates.projectNameExists(t):
            self.button_newproject.setEnabled(False)
        else:
            self.button_newproject.setEnabled(True)
        Debug.end("HeaderWidget::onTextEdited")
        return

    ## @brief called if button 'new project' is clicked
    # create a new group in layer in the layer panel with the name contained in the QTextEdit
    def onCreateNewProject(self):
        Debug.begin("HeaderWidget::onCreateNewProject")
        t = self.newlineedit_project.text()
        self.newlineedit_project.setText("")
        self.suricates.createNewProject(t)
        index = self.combobox_project.findText(t)
        self.combobox_project.setCurrentIndex(index)
        Debug.end("HeaderWidget::onCreateNewProject")
        return

    ## @brief called if button 'delete project' is clicked
    # delete the selected group
    def onDeleteProject(self):
        Debug.begin("HeaderWidget::onDeleteProject")
        t = self.combobox_project.currentText()
        self.suricates.deleteProject(t)
        Debug.end("HeaderWidget::onDeleteProject")
        return

    ## @brief called if the selected item of the combobox id changed
    # delete the selected group
    # @param text the value of the combobox
    def onSelectionChange(self, text):
        Debug.begin("HeaderWidget::onSelectionChange")
        self.suricates.selectProject(text)
        Debug.end("HeaderWidget::onSelectionChange")
        return