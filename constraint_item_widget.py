# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# @par CDI-Technologies, Vincent Majorczyk

from qgis.PyQt.QtGui import QIcon, QPainter, QColor, QPixmap, QFont
from qgis.PyQt.QtCore import Qt, QTimer, pyqtSignal, QPoint, QSize
from qgis.PyQt.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QLabel, QToolButton, QSpinBox, QSlider, QSizePolicy,
    QProgressBar, QFrame
)

from .constraint_item import ConstraintItem, ConstraintType
from .constraint_icons import get_combo_icon, get_config_inside_icon, get_config_outside_icon

## @brief Ordered list of constraint types shown in config buttons (excluding Map).
_CONFIG_TYPES = [
    ConstraintType.Repulsive,
    ConstraintType.Attractive,
    ConstraintType.Included,
    ConstraintType.Excluded,
    ConstraintType.Sanctuarized,
    ConstraintType.Undefined,
]

_TYPE_TOOLTIP = {
    ConstraintType.Repulsive:    "Repulsive — gradient, far = preferred",
    ConstraintType.Attractive:   "Attractive — gradient, near = preferred",
    ConstraintType.Included:     "Included — zone value = 0 (best)",
    ConstraintType.Excluded:     "Excluded — zone value = priority (high)",
    ConstraintType.Sanctuarized: "Sanctuarized — zone excluded (No-Data)",
    ConstraintType.Undefined:    "Undefined — not yet configured",
}

## @brief Size of the left icon button in pixels.
ICON_SIZE = 48

## @brief Delay in ms before auto-saving spinner/slider changes.
AUTOSAVE_DELAY_MS = 600


# ---------------------------------------------------------------------------
# Helper: build a pixmap with an overlay badge
# ---------------------------------------------------------------------------

def _add_overlay(base: QPixmap, overlay_char: str, bg: QColor, fg: QColor,
                 corner: str = 'top-right') -> QPixmap:
    """Draw a small circular badge with a character on top of *base*."""
    result = QPixmap(base)
    p = QPainter(result)
    p.setRenderHint(QPainter.Antialiasing)
    r = ICON_SIZE // 4          # badge radius
    margin = 1
    if corner == 'top-right':
        cx = ICON_SIZE - r - margin
        cy = r + margin
    else:  # bottom-right
        cx = ICON_SIZE - r - margin
        cy = ICON_SIZE - r - margin
    p.setBrush(bg)
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPoint(cx, cy), r, r)
    font = QFont()
    font.setPixelSize(r + 2)
    font.setBold(True)
    p.setFont(font)
    p.setPen(fg)
    p.drawText(cx - r, cy - r, r * 2, r * 2, Qt.AlignCenter, overlay_char)
    p.end()
    return result


def _make_left_icon(constraint: ConstraintItem) -> QPixmap:
    """Build the appropriate 48×48 pixmap for the left icon button."""
    type_in  = constraint.typeIn
    type_out = constraint.typeOut

    base = get_combo_icon(type_in, type_out, ICON_SIZE)

    if not constraint.exists:
        # Red cross: layer missing on disk
        return _add_overlay(base, '✕', QColor(200, 40, 40), QColor(255, 255, 255),
                            corner='bottom-right')

    is_new = (type_in == ConstraintType.Sanctuarized and
              type_out == ConstraintType.Sanctuarized)
    if is_new:
        # Yellow star: newly added, not yet configured
        return _add_overlay(base, '★', QColor(240, 200, 0), QColor(60, 40, 0),
                            corner='top-right')

    return base


# ---------------------------------------------------------------------------
# ConstraintItemWidget
# ---------------------------------------------------------------------------

## @brief Widget representing a single ConstraintItem inside a QListWidget.
#
# Layout:
#   [icon 48×48] | [QStackedWidget]
#                     page 0 – info   : name / inside+outside / buffer+priority (read-only)
#                     page 1 – config : 6+6 type buttons, buffer spinner, priority slider, delete
#                     page 2 – progress: name + QProgressBar
#
# Signals:
#   changed(ConstraintItem)  emitted after any auto-save
#   deleted(str)             emitted when the user clicks the delete button (passes layer name)
class ConstraintItemWidget(QWidget):

    ## @brief Emitted after every auto-save with the updated ConstraintItem.
    changed = pyqtSignal(object)

    ## @brief Emitted when the user requests deletion; carries the layer name.
    deleted = pyqtSignal(str)

    ## @brief Emitted when the widget needs a different height (page switch).
    sizeChanged = pyqtSignal()

    # -----------------------------------------------------------------------
    # Construction
    # -----------------------------------------------------------------------

    ## @brief Constructor.
    # @param constraint  ConstraintItem to display and edit.
    # @param parent      Parent QWidget (the QListWidget viewport).
    def __init__(self, constraint: ConstraintItem, parent=None):
        super().__init__(parent)

        ## @var _constraint
        # The ConstraintItem managed by this widget.
        self._constraint = constraint

        ## @var _save_timer
        # Delays auto-save for spinners/sliders to avoid saving on every keystroke.
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._doSave)

        ## @var _leave_timer
        # Delays the info←config transition to avoid false triggers when focus
        # moves between child widgets inside the config page.
        self._leave_timer = QTimer(self)
        self._leave_timer.setSingleShot(True)
        self._leave_timer.setInterval(400)
        self._leave_timer.timeout.connect(self._collapseToInfo)

        self._buildUi()
        self._refreshInfoPage()
        self._refreshIconButton()

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    ## @brief Return the ConstraintItem currently held by this widget.
    def constraint(self) -> ConstraintItem:
        return self._constraint

    ## @brief Replace the constraint and refresh all pages.
    def setConstraint(self, constraint: ConstraintItem):
        self._constraint = constraint
        self._refreshInfoPage()
        self._refreshConfigPage()
        self._refreshIconButton()

    ## @brief Switch to the progress page and set progress value (0–100).
    def setProgress(self, value: int):
        self._w_progress.setValue(value)
        self._stack.setCurrentIndex(2)
        self._left_stack.setCurrentIndex(2)

    ## @brief Switch back to the info page (e.g. after computation ends).
    def showInfo(self):
        self._stack.setCurrentIndex(0)
        self._left_stack.setCurrentIndex(0)
        self.updateGeometry()
        self.sizeChanged.emit()

    ## @brief Return the preferred size based on the currently visible page.
    def sizeHint(self):
        from qgis.PyQt.QtCore import QSize
        # Force the layout to compute sizes first
        self._stack.currentWidget().adjustSize()
        h = self._stack.currentWidget().sizeHint().height()
        # Add icon button height or use it as minimum
        h = max(h, ICON_SIZE + 8)
        return QSize(self.width() if self.width() > 0 else 300, h + 8)

    ## @brief Update the exists flag and refresh the icon.
    def setExists(self, exists: bool):
        self._constraint.exists = exists
        self._refreshIconButton()

    # -----------------------------------------------------------------------
    # UI construction (private)
    # -----------------------------------------------------------------------

    def _buildUi(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(6)

        # ── Left stacked widget (icon changes per page) ─────────────────────
        self._left_stack = QStackedWidget(self)
        self._left_stack.setFixedWidth(ICON_SIZE)

        def _make_icon_btn():
            btn = QToolButton()
            btn.setFixedSize(ICON_SIZE, ICON_SIZE)
            btn.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
            btn.setStyleSheet(
                "QToolButton { border: none; border-radius: 6px; padding: 0; }"
                "QToolButton:hover { background: rgba(0,0,0,30); }"
            )
            return btn

        # Page 0 (info): icon only
        left_info = QWidget()
        left_info_layout = QVBoxLayout(left_info)
        left_info_layout.setContentsMargins(0, 0, 0, 0)
        left_info_layout.setSpacing(3)
        self._btn_icon = _make_icon_btn()
        self._btn_icon.clicked.connect(self._onIconClicked)
        # Rounded corners via stylesheet on the info icon
        self._btn_icon.setStyleSheet(
            "QToolButton { border: none; border-radius: 10px; padding: 0; }"
            "QToolButton:hover { background: rgba(0,0,0,30); }"
        )
        left_info_layout.addWidget(self._btn_icon)
        left_info_layout.addStretch()

        # Page 1 (config): icon + delete below
        left_config = QWidget()
        left_config_layout = QVBoxLayout(left_config)
        left_config_layout.setContentsMargins(0, 0, 0, 0)
        left_config_layout.setSpacing(3)
        self._btn_icon_config = _make_icon_btn()
        self._btn_icon_config.clicked.connect(self._onIconClicked)
        self._btn_delete_left = QToolButton()
        self._btn_delete_left.setText("🗑")
        self._btn_delete_left.setFixedSize(ICON_SIZE, 22)
        self._btn_delete_left.setToolTip("Remove this layer from the project")
        self._btn_delete_left.setStyleSheet(
            "QToolButton { border: 1px solid #c44; border-radius: 4px; color: #c44; font-size: 13px; }"
            "QToolButton:hover { background: #fee; }"
        )
        self._btn_delete_left.clicked.connect(self._onDeleteClicked)
        left_config_layout.addWidget(self._btn_icon_config)
        left_config_layout.addWidget(self._btn_delete_left)
        left_config_layout.addStretch()

        # Page 2 (progress): icon only
        left_progress = QWidget()
        left_progress_layout = QVBoxLayout(left_progress)
        left_progress_layout.setContentsMargins(0, 0, 0, 0)
        self._btn_icon_progress = _make_icon_btn()
        self._btn_icon_progress.setEnabled(False)
        left_progress_layout.addWidget(self._btn_icon_progress)
        left_progress_layout.addStretch()

        self._left_stack.addWidget(left_info)      # 0
        self._left_stack.addWidget(left_config)    # 1
        self._left_stack.addWidget(left_progress)  # 2
        self._left_stack.setCurrentIndex(0)
        root.addWidget(self._left_stack, 0, Qt.AlignTop)

        # ── Stacked widget ───────────────────────────────────────────────────
        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._buildInfoPage())    # 0
        self._stack.addWidget(self._buildConfigPage())  # 1
        self._stack.addWidget(self._buildProgressPage())# 2
        self._stack.setCurrentIndex(0)
        root.addWidget(self._stack, 1)

        self.setLayout(root)

    # ── Page 0: Info ────────────────────────────────────────────────────────

    def _buildInfoPage(self) -> QWidget:
        # Wrap in a clickable frame so clicking anywhere on the info page
        # opens the config page (same as clicking the icon button).
        page = QWidget()
        page.setCursor(Qt.PointingHandCursor)
        page.mousePressEvent = lambda e: self._onIconClicked()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        self._lbl_name = QLabel()
        self._lbl_name.setStyleSheet("font-weight: bold;")

        self._lbl_inout = QLabel()
        self._lbl_inout.setStyleSheet("color: #555; font-size: 11px;")

        self._lbl_params = QLabel()
        self._lbl_params.setStyleSheet("color: #777; font-size: 11px;")

        layout.addWidget(self._lbl_name)
        layout.addWidget(self._lbl_inout)
        layout.addWidget(self._lbl_params)
        layout.addStretch()
        return page

    # ── Page 1: Config ──────────────────────────────────────────────────────

    def _buildConfigPage(self) -> QWidget:
        page = QWidget()
        page.installEventFilter(self)   # detect mouse leaving the config page
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)

        # Inside row
        inside_row = self._buildTypeRow(is_inside=True)
        # Outside row
        outside_row = self._buildTypeRow(is_inside=False)

        # Buffer + priority row
        params_row = QHBoxLayout()

        self._spin_buffer = QSpinBox()
        self._spin_buffer.setMinimum(0)
        self._spin_buffer.setMaximum(30000)
        self._spin_buffer.setSingleStep(100)
        self._spin_buffer.setSuffix(" m")
        self._spin_buffer.setToolTip("Buffer distance around geometry")
        self._spin_buffer.setFixedWidth(110)
        self._spin_buffer.editingFinished.connect(self._scheduleSave)

        self._slider_priority = QSlider(Qt.Horizontal)
        self._slider_priority.setMinimum(1)
        self._slider_priority.setMaximum(10)
        self._slider_priority.setSingleStep(1)
        self._slider_priority.setPageStep(1)
        self._slider_priority.setToolTip("Layer weight (1 = low, 10 = high)")
        self._slider_priority.setFixedWidth(80)
        self._slider_priority.valueChanged.connect(self._onPriorityChanged)

        self._lbl_priority_val = QLabel("1")
        self._lbl_priority_val.setFixedWidth(16)
        self._lbl_priority_val.setAlignment(Qt.AlignCenter)

        params_row.addWidget(QLabel("Dist:"))
        params_row.addWidget(self._spin_buffer)
        params_row.addSpacing(8)
        params_row.addWidget(QLabel("Weight:"))
        params_row.addWidget(self._slider_priority)
        params_row.addWidget(self._lbl_priority_val)
        params_row.addStretch()

        layout.addLayout(inside_row)
        layout.addLayout(outside_row)
        layout.addLayout(params_row)
        return page

    def _buildTypeRow(self, is_inside: bool) -> QHBoxLayout:
        """Build a row of 6 icon buttons for inside or outside type selection."""
        row = QHBoxLayout()
        row.setSpacing(3)
        lbl = QLabel("In:" if is_inside else "Out:")
        lbl.setFixedWidth(28)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(lbl)

        buttons = []
        for ctype in _CONFIG_TYPES:
            btn = QToolButton()
            btn.setFixedSize(44, 44)
            btn.setIconSize(QSize(40, 40))
            btn.setCheckable(True)
            btn.setToolTip(_TYPE_TOOLTIP[ctype])
            btn.setStyleSheet(
                "QToolButton { border: 1px solid transparent; border-radius: 4px; padding: 1px; }"
                "QToolButton:checked { border: 2px solid #4a90e2; }"
                "QToolButton:hover { background: rgba(0,0,0,20); }"
            )
            if is_inside:
                icon_px = get_config_inside_icon(ctype, 40)
            else:
                icon_px = get_config_outside_icon(ctype, 40)
            btn.setIcon(QIcon(icon_px))

            # Connect with closure capturing ctype and is_inside
            btn.clicked.connect(self._makeTypeHandler(ctype, is_inside, buttons))
            buttons.append((ctype, btn))
            row.addWidget(btn)

        row.addStretch()

        if is_inside:
            self._inside_buttons = buttons
        else:
            self._outside_buttons = buttons

        return row

    # ── Page 2: Progress ────────────────────────────────────────────────────

    def _buildProgressPage(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 4)

        self._lbl_progress_name = QLabel()
        self._lbl_progress_name.setStyleSheet("font-weight: bold;")

        self._w_progress = QProgressBar()
        self._w_progress.setMinimum(0)
        self._w_progress.setMaximum(100)
        self._w_progress.setValue(0)

        layout.addWidget(self._lbl_progress_name)
        layout.addWidget(self._w_progress)
        layout.addStretch()
        return page

    # -----------------------------------------------------------------------
    # Refresh helpers (private)
    # -----------------------------------------------------------------------

    def _refreshInfoPage(self):
        c = self._constraint
        # Line 1: layer name
        self._lbl_name.setText(c.name)
        self._lbl_progress_name.setText(c.name)
        # Line 2: inside / outside types
        tin  = c.typeIn.name  if c.typeIn  else "—"
        tout = c.typeOut.name if c.typeOut else "—"
        self._lbl_inout.setText(f"In: {tin}   Out: {tout}")
        # Line 3: distance and weight
        weight = int(c.priority) // 10 if c.priority >= 10 else int(c.priority)
        self._lbl_params.setText(f"Buffer: {c.buffer} m   Weight: {weight}")

    def _refreshConfigPage(self):
        c = self._constraint
        # Set buffer spinner
        self._spin_buffer.blockSignals(True)
        self._spin_buffer.setValue(c.buffer)
        self._spin_buffer.blockSignals(False)
        # Set priority slider
        weight = int(c.priority) // 10 if c.priority >= 10 else max(1, int(c.priority))
        self._slider_priority.blockSignals(True)
        self._slider_priority.setValue(weight)
        self._slider_priority.blockSignals(False)
        self._lbl_priority_val.setText(str(weight))
        # Check correct type buttons
        for ctype, btn in self._inside_buttons:
            btn.setChecked(ctype == c.typeIn)
        for ctype, btn in self._outside_buttons:
            btn.setChecked(ctype == c.typeOut)

    def _refreshIconButton(self):
        px = _make_left_icon(self._constraint)
        icon = QIcon(px)
        self._btn_icon.setIcon(icon)
        self._btn_icon_config.setIcon(icon)
        self._btn_icon_progress.setIcon(icon)

    # -----------------------------------------------------------------------
    # Event handling (private)
    # -----------------------------------------------------------------------

    def _onIconClicked(self):
        """Toggle between info and config pages."""
        if self._stack.currentIndex() != 1:
            self._refreshConfigPage()
            self._stack.setCurrentIndex(1)
            self._left_stack.setCurrentIndex(1)
            self.updateGeometry()
            self.sizeChanged.emit()
        else:
            self._collapseToInfo()

    def _collapseToInfo(self):
        """Save and switch back to the info page."""
        if self._stack.currentIndex() == 1:
            self._doSave()
            self._stack.setCurrentIndex(0)

    def _makeTypeHandler(self, ctype: ConstraintType, is_inside: bool, buttons: list):
        """Return a slot that sets the type, un-checks siblings, and saves."""
        def handler(checked):
            if not checked:
                return
            # Uncheck all other buttons in this row
            target_list = self._inside_buttons if is_inside else self._outside_buttons
            for other_type, btn in target_list:
                btn.setChecked(other_type == ctype)
            # Update constraint
            if is_inside:
                self._constraint.typeIn = ctype
            else:
                self._constraint.typeOut = ctype
            self._refreshIconButton()
            self._scheduleSave()
        return handler

    def _onPriorityChanged(self, value: int):
        self._lbl_priority_val.setText(str(value))
        self._scheduleSave()

    def _onDeleteClicked(self):
        self.deleted.emit(self._constraint.name)

    def _scheduleSave(self):
        """Restart the debounce timer — actual save fires after AUTOSAVE_DELAY_MS."""
        self._save_timer.start(AUTOSAVE_DELAY_MS)

    def _doSave(self):
        """Commit spinner/slider values to the constraint and emit changed."""
        self._constraint.buffer   = self._spin_buffer.value()
        self._constraint.priority = self._slider_priority.value() * 10
        self._refreshInfoPage()
        self.changed.emit(self._constraint)

    # -----------------------------------------------------------------------
    # Mouse leave detection (config page → info page)
    # -----------------------------------------------------------------------

    def _isMouseOverSelf(self) -> bool:
        # Geometry check first: is cursor inside our screen rect?
        from qgis.PyQt.QtWidgets import QApplication
        from qgis.PyQt.QtGui import QCursor
        top_left = self.mapToGlobal(self.rect().topLeft())
        global_rect = self.rect().translated(top_left)
        if not global_rect.contains(QCursor.pos()):
            return False
        # Secondary: widgetAt check
        w = QApplication.widgetAt(QCursor.pos())
        while w is not None:
            if w is self:
                return True
            w = w.parent()
        return False

    def _collapseToInfo(self):
        # Save and switch to info page only if mouse has truly left.
        if self._stack.currentIndex() == 1 and not self._isMouseOverSelf():
            self._doSave()
            self._stack.setCurrentIndex(0)
            self._left_stack.setCurrentIndex(0)
            self.updateGeometry()
            self.sizeChanged.emit()

    def eventFilter(self, obj, event):
        from qgis.PyQt.QtCore import QEvent
        if event.type() == QEvent.Leave and self._stack.currentIndex() == 1:
            self._leave_timer.start()
        elif event.type() == QEvent.Enter and self._stack.currentIndex() == 1:
            self._leave_timer.stop()
        return super().eventFilter(obj, event)
