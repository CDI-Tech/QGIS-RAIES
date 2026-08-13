# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# @par CDI-Technologies, Vincent Majorczyk

from qgis.PyQt.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from qgis.PyQt.QtCore import Qt, QSize, pyqtSignal, QRectF
from qgis.PyQt.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QToolButton
)

from .constraint_item import ConstraintItem

## @brief Pixel size of the left icon in MapItemWidget (matches ICON_SIZE in constraint_item_widget).
_MAP_ICON_SIZE = 48


def _make_map_pixmap(size: int) -> QPixmap:
    """Blue square with a white 'M' — identifies the working-area layer."""
    px = QPixmap(size, size)
    px.fill(QColor(74, 144, 226))
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    font = QFont("monospace")
    font.setBold(True)
    font.setPixelSize(int(size * 0.55))
    p.setFont(font)
    p.setPen(QColor(255, 255, 255))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, "M")
    p.end()
    return px


## @brief Widget representing the Map constraint (working area) in the constraint list.
#
# Displays the layer name and a button to replace the Map layer with the
# currently selected QGIS layer.  No delete button: a Map layer is mandatory
# for computation.
class MapItemWidget(QWidget):

    ## @brief Emitted when the user clicks the Replace button.
    replaced = pyqtSignal()

    def __init__(self, constraint: ConstraintItem, parent=None):
        super().__init__(parent)
        self._constraint = constraint
        self._buildUi()

    def constraint(self) -> ConstraintItem:
        return self._constraint

    def refresh(self, constraint: ConstraintItem):
        self._constraint = constraint
        self._lbl_name.setText(constraint.name)

    def _buildUi(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(6)

        # Left icon
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(_MAP_ICON_SIZE, _MAP_ICON_SIZE)
        icon_lbl.setPixmap(_make_map_pixmap(_MAP_ICON_SIZE))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("border-radius: 10px;")
        root.addWidget(icon_lbl, 0, Qt.AlignTop)

        # Info
        info = QVBoxLayout()
        info.setSpacing(2)
        lbl_title = QLabel("Map — working area")
        lbl_title.setStyleSheet("font-weight: bold; color: #4a90e2;")
        self._lbl_name = QLabel(self._constraint.name)
        self._lbl_name.setStyleSheet("color: #555; font-size: 11px;")
        info.addWidget(lbl_title)
        info.addWidget(self._lbl_name)
        info.addStretch()
        root.addLayout(info, 1)

        # Replace button
        btn = QToolButton()
        btn.setIcon(QIcon(":/images/themes/default/mActionFileOpen.svg"))
        btn.setIconSize(QSize(24, 24))
        btn.setToolTip("Replace with currently selected QGIS layer")
        btn.setFixedSize(36, 36)
        btn.setStyleSheet(
            "QToolButton { border: 1px solid #4a90e2; border-radius: 4px; }"
            "QToolButton:hover { background: #e8f0ff; }"
        )
        btn.clicked.connect(self.replaced.emit)
        root.addWidget(btn, 0, Qt.AlignTop)

        self.setLayout(root)
