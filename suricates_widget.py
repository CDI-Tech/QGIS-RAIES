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
from .header_widget import HeaderWidget
from .constraint_widget import ConstraintWidget

## @brief main widget for suricates, it containts a HeaderWidget and a ConstraintWidget
#
# ![User interface classes imbrication](assets\GuiStructure.png)
class SuricatesWidget(QWidget):
    ## @var suricates
    ## current SuricatesInstance

    ## @var projectWidget
    ## the HeaderWidget at the top of the widget: manage the projects and select the current project

    ## @var constraintWidget
    ## the ConstraintWidget at the bottom of the widget: manage the constrains of the selected project

    ## @brief constructor
    # @param parent parent of the widget (QWidget)
    def __init__(self, parent):
        Debug.begin("SuricatesWidget::__init__")
        QWidget.__init__(self,parent)

        self.suricates = parent.suricates

        globalLayout = QVBoxLayout(self)
        self.stackedWidget = QStackedWidget(self)
        globalLayout.addWidget(self.stackedWidget)

        # "credit" widget
        self.creditWidget = QWidget(self.stackedWidget)
        self.stackedWidget.addWidget(self.creditWidget)
        creditlayout = QVBoxLayout(self.creditWidget)

        self.logoWidget3 = QLabel(self.creditWidget)
        self.logoPixmap3 = QPixmap(":/plugins/suricates/logo_suricates.svg").scaledToWidth(400, Qt.SmoothTransformation)
        self.logoWidget3.setPixmap(self.logoPixmap3)
        self.logoWidget3.setAlignment(Qt.AlignHCenter)
        creditlayout.addWidget(self.logoWidget3)

        self.logoWidget = QLabel(self.creditWidget)
        self.logoPixmap = QPixmap(":/plugins/suricates/logo_cdi.svg").scaledToHeight(100, Qt.SmoothTransformation)
        self.logoWidget.setPixmap(self.logoPixmap)
        self.logoWidget.setAlignment(Qt.AlignHCenter)

        self.logo2Widget = QLabel(self.creditWidget)
        self.logo2Pixmap = QPixmap(":/plugins/suricates/logo_Universite_de_Lille.svg").scaledToHeight(100, Qt.SmoothTransformation)
        self.logo2Widget.setPixmap(self.logo2Pixmap)
        self.logo2Widget.setAlignment(Qt.AlignHCenter)

        selecth = QHBoxLayout(self.creditWidget)
        selecth.addWidget(self.logo2Widget)
        selecth.addWidget(self.logoWidget)
        creditlayout.addSpacing(50)
        creditlayout.addLayout(selecth)
        creditlayout.addStretch()
        self.stackedWidget.addWidget(self.creditWidget)

        # "main" widget
        self.mainWidget = QWidget(self.stackedWidget)
        selectl = QVBoxLayout(self.mainWidget)
        self.mainWidget.setLayout(selectl)

        self.projectWidget = HeaderWidget(self)
        self.constraintWidget = ConstraintWidget(self)

        selectl.addWidget(self.projectWidget)
        selectl.addWidget(self.constraintWidget)
        self.stackedWidget.addWidget(self.mainWidget)

        self.setLayout(globalLayout)
        self.suricates.iface.currentLayerChanged.connect(self.handleLayerChanged)

        QTimer.singleShot(4000, self.goToMainWidget)

        Debug.end("SuricatesWidget::__init__")

    def goToMainWidget(self):
        Debug.begin("SuricatesWidget::goToMainWidget")
        self.stackedWidget.setCurrentIndex(1)
        Debug.end("SuricatesWidget::goToMainWidget")

    ## @brief executed when a layer is changed, this was a test
    def handleLayerChanged(self):
        Debug.begin("SuricatesWidget::handleLayerChanged")
        # mylayer = self.suricates.iface.activeLayer()
        # if not (mylayer is None):
        #	 name = mylayer.name()
        #	 self.suricates.iface.messageBar().pushMessage("Layer changed", name, level = Qgis.Info, duration=3)
        # print(type(iface.activeLayer()))
        Debug.end("SuricatesWidget::handleLayerChanged")

    ## @brief select the curent project
    # @name name of the project
    def setProject(self, name):
        Debug.begin("SuricatesWidget::setProject")
        self.constraintWidget.setProject(name)
        Debug.end("SuricatesWidget::setProject")