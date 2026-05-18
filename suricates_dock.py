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

class SuricatesDock(QDockWidget):
    ## @var suricates
    ## current SuricatesInstance

    ## @var w_suricates
    ## the SuricatesWidget contained in the panel

    ## @brief constructor
    # @param suricates current SuricatesInstance
    def __init__(self, suricates):
        from .SuricatesApp import SuricatesWidget
        Debug.begin("SuricatesDock::__init__")
        QDockWidget.__init__(self, "RAIES Model" ,suricates.iface.mainWindow())
        self.suricates = suricates
        self.w_suricates = SuricatesWidget(self)
        self.setWidget(self.w_suricates)
        Debug.end("SuricatesDock::__init__")