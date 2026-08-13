# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# @par CDI-Technologies, Vincent Majorczyk

from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import *

## @brief toolbox for debug functions
#
# this class aims to debug in the context of the python editor of QGis: there are not evolved tools to facilitate this task.
#
# developer can add calls static method of this class to display in the console the access to methods or functions:
# ```py
# def dummyFunction():
#     Debug.begin("dummyFunction")
#     i = 1 + 1
#     if i != 2:
#          Debug.end("dummyFunction")
#          return
#     Debug.print( str(i) + "==2" )
#     Debug.end("dummyFunction")
#     return
# ```
#
# the console output:
# ```
# dummyFunction begin
#  2==2
# dummyFunction end
# ```
#
# in the case of functions or methods which calls others functions or method using this system, a indent is used:
# ```
# dummyFunction begin
#  dummyFunction2 begin
#   dummyFunction3 begin
#    it says: helloword!
#   dummyFunction3 end
#  dummyFunction2 end
# dummyFunction end
# ```
class Debug():
    ## @brief display debug text is true
    enabled = False

    ## @brief indentation variable
    __indentDebug = 0

    ## @brief QGIS log tag
    __tag = "RAIES-Suricates"

    ## @brief write to both Python console and QGIS log panel
    @staticmethod
    def __log(text, level=Qgis.Info):
        QgsMessageLog.logMessage(text, Debug.__tag, level=level)
        print(text)

    ## @brief display text (start of a function) if debug mode
    @staticmethod
    def begin(text):
        if Debug.enabled:
            indent = " " * Debug.__indentDebug
            Debug.__log(indent + text + " begin")
            Debug.__indentDebug = Debug.__indentDebug + 1

    ## @brief display text if debug mode
    @staticmethod
    def print(text):
        if Debug.enabled:
            indent = " " * Debug.__indentDebug
            Debug.__log(indent + text)

    ## @brief display text (end of a function) if debug mode
    @staticmethod
    def end(text):
        if Debug.enabled:
            Debug.__indentDebug = max(0, Debug.__indentDebug - 1)
            indent = " " * Debug.__indentDebug
            Debug.__log(indent + text + " end")

    ## @brief always log a warning (visible in QGIS log panel even if debug is disabled)
    @staticmethod
    def warning(text):
        Debug.__log("[WARNING] " + text, level=Qgis.Warning)

    ## @brief always log an error (visible in QGIS log panel even if debug is disabled)
    @staticmethod
    def error(text):
        Debug.__log("[ERROR] " + text, level=Qgis.Critical)