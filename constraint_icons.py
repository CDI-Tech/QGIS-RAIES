# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# @par CDI-Technologies, Vincent Majorczyk

from PyQt5.QtGui import QPixmap, QPainter, QColor, QRadialGradient, QPainterPath, QPen, QFont
from PyQt5.QtCore import Qt, QPointF, QRectF, QSizeF
from PyQt5.QtWidgets import QApplication

from .constraint_item import ConstraintType

## @brief Factory class for generating constraint icons programmatically.
#
# Generates three kinds of icons using QPainter, all based on the same
# geometric primitive: a square divided into two zones by a circular arc.
# The circle has its centre at (-0.25·size, size) with radius = size,
# so the arc enters from the bottom-left corner and exits near the top-right,
# dividing the square into an "inside" (disc) zone and an "outside" zone.
#
# Three icon types are produced:
# - **config-inside** (12): active zone = inside; other zone filled with ZONE_COLOR.
#   The initial letter of the active type is drawn top-right.
# - **config-outside** (12): active zone = outside; other zone filled with ZONE_COLOR.
#   The initial letter of the active type is drawn bottom-left.
# - **combo** (36): both zones rendered with their respective types, no ZONE_COLOR.
#   Used as the main item icon in the list widget.
#
# Corner rounding is intentionally NOT applied to the pixmap; it should be
# handled by the QPushButton / QToolButton stylesheet so that the border-radius
# can be adjusted without regenerating icons:
#   button.setStyleSheet("border-radius: 6px;")
#
# Usage:
#   factory = ConstraintIconFactory(size=48)
#   pixmap  = factory.combo(ConstraintType.Attractive, ConstraintType.Excluded)
#   pixmap  = factory.config_inside(ConstraintType.Repulsive)
#   pixmap  = factory.config_outside(ConstraintType.Sanctuarized)
class ConstraintIconFactory:

    ## @brief Colour used for the inactive zone in config icons.
    # Change this value to adjust the appearance of all config icons at once.
    # Default: a soft orange, distinct from the blue arc and the grey/black/white types.
    ZONE_COLOR = QColor(255, 185, 90)

    ## @brief Arc/border colour.
    ARC_COLOR = QColor(74, 144, 226)

    ## @brief Arc border width in pixels (at size=48).
    ARC_WIDTH = 1.8

    ## @brief Background colour of each icon.
    BG_COLOR = QColor(245, 245, 243)

    ## @brief Checkerboard cell size in pixels (at size=48).
    CHECKER_CELL = 6

    ## @brief Checkerboard colours for Sanctuarized (forbidden, red).
    CHECKER_A = QColor(210, 90, 110)
    CHECKER_B = QColor(245, 175, 185)

    ## @brief Checkerboard colours for Mandatory (always-kept, green).
    MANDATORY_CHECKER_A = QColor(70, 165, 90)
    MANDATORY_CHECKER_B = QColor(180, 225, 190)

    ## @brief Font used for the type initial in config icons.
    LETTER_FONT_SIZE = 14  # points

    def __init__(self, size: int = 48):
        ## @var size
        # Side length of the generated square pixmap in pixels.
        self.size = size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    ## @brief Generate a combined icon for an (inside, outside) type pair.
    # @param type_in  ConstraintType applied to the inside zone.
    # @param type_out ConstraintType applied to the outside zone.
    # @return QPixmap of self.size × self.size.
    def combo(self, type_in: ConstraintType, type_out: ConstraintType) -> QPixmap:
        pixmap = self._make_pixmap()
        painter = QPainter(pixmap)
        self._setup_painter(painter)
        self._draw_zone(painter, inside=True,  ctype=type_in,  zone_color=None)
        self._draw_zone(painter, inside=False, ctype=type_out, zone_color=None)
        self._draw_arc(painter)
        painter.end()
        return pixmap

    ## @brief Generate a config icon for a given inside type.
    # The inside zone shows the type; the outside zone is filled with ZONE_COLOR.
    # The type initial is drawn top-right (in the outside / ZONE_COLOR area).
    # @param ctype ConstraintType for the inside zone.
    # @return QPixmap of self.size × self.size.
    def config_inside(self, ctype: ConstraintType) -> QPixmap:
        pixmap = self._make_pixmap()
        painter = QPainter(pixmap)
        self._setup_painter(painter)
        self._draw_zone(painter, inside=True,  ctype=ctype,           zone_color=None)
        self._draw_zone(painter, inside=False, ctype=ConstraintType.Excluded, zone_color=self.ZONE_COLOR)
        self._draw_arc(painter)
        self._draw_letter(painter, ctype, top_right=True)
        painter.end()
        return pixmap

    ## @brief Generate a config icon for a given outside type.
    # The outside zone shows the type; the inside zone is filled with ZONE_COLOR.
    # The type initial is drawn bottom-left (in the inside / ZONE_COLOR area).
    # @param ctype ConstraintType for the outside zone.
    # @return QPixmap of self.size × self.size.
    def config_outside(self, ctype: ConstraintType) -> QPixmap:
        pixmap = self._make_pixmap()
        painter = QPainter(pixmap)
        self._setup_painter(painter)
        self._draw_zone(painter, inside=True,  ctype=ConstraintType.Excluded, zone_color=self.ZONE_COLOR)
        self._draw_zone(painter, inside=False, ctype=ctype,                   zone_color=None)
        self._draw_arc(painter)
        self._draw_letter(painter, ctype, top_right=False)
        painter.end()
        return pixmap

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def _circle_center(self) -> QPointF:
        s = self.size
        return QPointF(-0.25 * s, float(s))

    def _circle_radius(self) -> float:
        return float(self.size)

    def _inside_path(self) -> QPainterPath:
        """Clipping path for the inside (disc) zone."""
        c = self._circle_center()
        r = self._circle_radius()
        path = QPainterPath()
        path.addEllipse(c, r, r)
        return path

    def _outside_path(self) -> QPainterPath:
        # Square minus disc using subtracted — fallback uses EvenOdd fill rule
        s = float(self.size)
        path = QPainterPath()
        path.setFillRule(Qt.OddEvenFill)
        path.addRect(QRectF(0, 0, s, s))
        c = self._circle_center()
        r = self._circle_radius()
        path.addEllipse(c, r, r)
        return path

    # ------------------------------------------------------------------
    # Drawing primitives
    # ------------------------------------------------------------------

    def _make_pixmap(self) -> QPixmap:
        pixmap = QPixmap(self.size, self.size)
        pixmap.fill(self.BG_COLOR)
        return pixmap

    def _setup_painter(self, painter: QPainter):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

    def _draw_zone(self, painter: QPainter, inside: bool, ctype: ConstraintType,
                   zone_color: QColor | None):
        """Fill one zone (inside or outside) according to ctype.
        If zone_color is not None, it overrides the type rendering (used for the
        inactive zone in config icons)."""
        clip = self._inside_path() if inside else self._outside_path()
        painter.save()
        painter.setClipPath(clip)

        if zone_color is not None:
            painter.fillRect(0, 0, self.size, self.size, zone_color)
        elif ctype == ConstraintType.Sanctuarized:
            self._fill_checkerboard(painter, self.CHECKER_A, self.CHECKER_B)
        elif ctype == ConstraintType.Mandatory:
            self._fill_checkerboard(painter, self.MANDATORY_CHECKER_A, self.MANDATORY_CHECKER_B)
        elif ctype == ConstraintType.Included:
            painter.fillRect(0, 0, self.size, self.size, QColor(30, 30, 30))
        elif ctype == ConstraintType.Excluded:
            painter.fillRect(0, 0, self.size, self.size, QColor(235, 235, 235))
        elif ctype == ConstraintType.Undefined:
            painter.fillRect(0, 0, self.size, self.size, QColor(155, 155, 155))
        elif ctype in (ConstraintType.Attractive, ConstraintType.Repulsive):
            self._fill_gradient(painter, inside=inside, repulsive=(ctype == ConstraintType.Repulsive))

        painter.restore()

    def _fill_checkerboard(self, painter: QPainter, color_a: QColor = None, color_b: QColor = None):
        """Tile the square with alternating color_a / color_b squares.
        Defaults to the Sanctuarized (red) colours when none are given."""
        if color_a is None: color_a = self.CHECKER_A
        if color_b is None: color_b = self.CHECKER_B
        cell = self.CHECKER_CELL
        s = self.size
        for row in range(0, s, cell):
            for col in range(0, s, cell):
                color = color_a if ((row // cell + col // cell) % 2 == 0) else color_b
                painter.fillRect(col, row, cell, cell, color)

    def _fill_gradient(self, painter: QPainter, inside: bool, repulsive: bool):
        # Inside zone: radial gradient from circle centre outward.
        # Outside zone: linear gradient from the arc boundary toward the
        # far corner of the canvas (top-right), because the radial centre
        # lies far outside the canvas and the visible outside region only
        # covers a tiny slice of the radial range.
        s = self.size

        if inside:
            c = self._circle_center()
            r = self._circle_radius()
            grad = QRadialGradient(c, r)
            if repulsive:
                # near centre = black, edge = white
                grad.setColorAt(0.0, QColor(20, 20, 20))
                grad.setColorAt(1.0, QColor(230, 230, 230))
            else:
                # near centre = white, edge = black
                grad.setColorAt(0.0, QColor(230, 230, 230))
                grad.setColorAt(1.0, QColor(20, 20, 20))

            painter.fillRect(QRectF(0, 0, s, s), grad)
        else:
            # Outside zone: radial gradient with radius = 2r centred at the
            # same circle centre.  The arc boundary sits at t=0.5 and the
            # far corner (top-right) at t≈0.8, giving a usable [0.5, 0.8]
            # range that produces a visible gradient across the outside zone.
            c = self._circle_center()
            r = self._circle_radius()
            grad = QRadialGradient(c, 2.0 * r)
            if repulsive:
                # arc boundary = white, far corner = black
                grad.setColorAt(0.0,  QColor(230, 230, 230))
                grad.setColorAt(0.5,  QColor(230, 230, 230))  # arc boundary
                grad.setColorAt(0.8,  QColor(20,  20,  20))   # far corner
                grad.setColorAt(1.0,  QColor(20,  20,  20))
            else:
                # arc boundary = black, far corner = white
                grad.setColorAt(0.0,  QColor(20,  20,  20))
                grad.setColorAt(0.5,  QColor(20,  20,  20))   # arc boundary
                grad.setColorAt(0.8,  QColor(230, 230, 230))  # far corner
                grad.setColorAt(1.0,  QColor(230, 230, 230))
            painter.fillRect(QRectF(0, 0, s, s), grad)

    def _draw_arc(self, painter: QPainter):
        """Draw the blue circular arc that separates the two zones."""
        c = self._circle_center()
        r = self._circle_radius()
        pen = QPen(self.ARC_COLOR, self.ARC_WIDTH)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        # Clip to the icon square so the arc doesn't bleed outside
        painter.save()
        clip = QPainterPath()
        clip.addRect(QRectF(0, 0, float(self.size), float(self.size)))
        painter.setClipPath(clip)
        painter.drawEllipse(c, r, r)
        painter.restore()

    def _draw_letter(self, painter: QPainter, ctype: ConstraintType, top_right: bool):
        """Draw the type initial letter in the ZONE_COLOR area."""
        letter = '?' if ctype == ConstraintType.Undefined else ctype.name[0].upper()
        font = QFont("monospace")
        font.setBold(True)
        font.setPixelSize(self.LETTER_FONT_SIZE)
        painter.setFont(font)
        painter.setPen(QColor(30, 30, 30))

        s = self.size
        if top_right:
            # Top-right corner = outside (ZONE_COLOR) area
            painter.drawText(QRectF(s * 0.55, 1, s * 0.42, s * 0.35),
                             Qt.AlignRight | Qt.AlignTop, letter)
        else:
            # Bottom-left corner = inside (ZONE_COLOR) area
            painter.drawText(QRectF(2, s * 0.65, s * 0.42, s * 0.32),
                             Qt.AlignLeft | Qt.AlignBottom, letter)


# ------------------------------------------------------------------
# Convenience cache — avoids regenerating the same pixmap repeatedly
# ------------------------------------------------------------------

## @brief Cached icon factory singleton.
# Instantiated once per QGIS session. Access via get_icon_factory().
_factory_instance: ConstraintIconFactory | None = None
_combo_cache:  dict[tuple, QPixmap] = {}
_config_cache: dict[tuple, QPixmap] = {}


def get_icon_factory(size: int = 48) -> ConstraintIconFactory:
    """Return (or create) the shared ConstraintIconFactory instance."""
    global _factory_instance
    if _factory_instance is None or _factory_instance.size != size:
        _factory_instance = ConstraintIconFactory(size)
        _combo_cache.clear()
        _config_cache.clear()
    return _factory_instance


def get_combo_icon(type_in: ConstraintType, type_out: ConstraintType,
                   size: int = 48) -> QPixmap:
    """Return a cached combo icon for the given type pair."""
    key = (type_in, type_out, size)
    if key not in _combo_cache:
        _combo_cache[key] = get_icon_factory(size).combo(type_in, type_out)
    return _combo_cache[key]


def get_config_inside_icon(ctype: ConstraintType, size: int = 48) -> QPixmap:
    """Return a cached config-inside icon for the given type."""
    key = ('in', ctype, size)
    if key not in _config_cache:
        _config_cache[key] = get_icon_factory(size).config_inside(ctype)
    return _config_cache[key]


def get_config_outside_icon(ctype: ConstraintType, size: int = 48) -> QPixmap:
    """Return a cached config-outside icon for the given type."""
    key = ('out', ctype, size)
    if key not in _config_cache:
        _config_cache[key] = get_icon_factory(size).config_outside(ctype)
    return _config_cache[key]
