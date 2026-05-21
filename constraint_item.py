# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# @par CDI-Technologies, Vincent Majorczyk

from enum import Enum

## @brief Corresponds to the different constraint types.
#
# These constraint types are applied to the inside and outside of the area
# delimited by a layer.  With 6 types there are 36 possible combinations,
# though Sanctuarized/Sanctuarized is reserved for newly added, unconfigured
# layers and is not a valid computation state.
#
# ![constraint combinations](assets/constraints.svg)
class ConstraintType(Enum):
    ## @brief Zone excluded from the result (No-Data).
    Sanctuarized = 0
    ## @brief Gradient: near the boundary is preferred (value 0 near, 1 far).
    Attractive   = 1
    ## @brief Gradient: far from the boundary is preferred (value 1 near, 0 far).
    Repulsive    = 2
    ## @brief Zone receives value 0 (best score).
    Included     = 3
    ## @brief Zone receives the priority value (high score).
    Excluded     = 4
    ## @brief Special type: marks the global working area of the project.
    Map          = 5
    ## @brief Not yet configured — placeholder for newly added layers.
    Undefined    = 6


## @brief Structure holding all parameters for a single constraint layer.
#
# This structure acts as the interface between:
# - the *project_config* layer file (persistent storage),
# - the ConstraintItemWidget / ConstraintWidget (user interface),
# - and SuricatesAlgo (computation task).
#
# **Note on the `name` attribute:**
# - For SuricatesAlgo the name must be the *absolute path* of the layer file.
# - For the UI and project_config it is the *display name* shown in the
#   QGIS layer panel.
#
# **Note on the Map type:**
# When typeIn == ConstraintType.Map, typeOut is ignored during computation
# and the `priority` attribute stores the threshold value (0–100) instead
# of the layer weight.
class ConstraintItem:
    ## @var name
    # Layer name (display name for UI/config; absolute path for SuricatesAlgo).

    ## @var buffer
    # Buffer distance in metres around the layer's geometry.

    ## @var priority
    # Layer weight (1–10, stored as value × 10, i.e. 10–100).
    # For a Map layer this holds the threshold value (0–100) instead.

    ## @var typeIn
    # Constraint type applied inside the geometry (ConstraintType).

    ## @var typeOut
    # Constraint type applied outside the geometry (ConstraintType).

    ## @var exists
    # True if the associated layer file exists on disk.

    ## @var progress
    # Computation progress for this layer (0–100).
    # Used by ConstraintItemWidget to update its progress bar during a run.
    # Stored here to allow SuricatesAlgo to update it without needing a
    # direct reference to the widget.

    ## @brief Constructor.
    # @param name     Layer name or absolute path.
    # @param buffer   Buffer distance in metres (default 100 m).
    # @param priority Layer weight × 10, or threshold for Map layers (default 100).
    # @param typeIn   Constraint type inside the geometry (default Undefined).
    # @param typeOut  Constraint type outside the geometry (default Undefined).
    def __init__(self,
                 name:     str,
                 buffer:   int           = 100,
                 priority: int           = 100,
                 typeIn:   ConstraintType = ConstraintType.Sanctuarized,
                 typeOut:  ConstraintType = ConstraintType.Sanctuarized):
        self.name     = name
        self.buffer   = buffer
        self.priority = priority
        self.typeIn   = typeIn
        self.typeOut  = typeOut
        self.exists   = True
        self.progress = 0
