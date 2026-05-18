# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# @par CDI-Technologies, Vincent Majorczyk

from enum import Enum

## @brief corresponds to the differents constraint types
#
# These constraint types are applyed to inside and outside of the area delimited by layer. There are 5 constraint types, so 25 possible combinations
# ![constraint combinations](assets\constraints.svg)
class ConstraintType(Enum):
    ## @brief exclude the area
    Sanctuarized=0
    ## @brief near location to the area is prefered
    Attractive=1
    ## @brief far location to the area is prefered
    Repulsive=2
    ## @brief inside the area
    Included=3
    ## @brief uside the area
    Excluded=4
    ## @brief global working area of the project
    Map=5

## @brief structure for constraint information
#
# This structure is an interface between the file of the layer *config_project*, the ConstraintWidget (user interface) and the SuricatesAlgo (task)
#
# There is minor difference between the requierement of the SuricatesAlgo and the other (*config_project* and ConstraintWidget).
# This concerns the attribute name:
# - for SuricatesAlgo: the name must be the absolute path of the layer
# - for the others: the name is the one used in the layer file *config_project*, that means the name of the layer in the panel of layers.
#
# typeIn and typeOut are the constraint types applyed to the layer
# If typeIn is set to the special type ConstraintType.Map, then typeOut is ignored in the process and the priority attribute contains the threshold parameter instead (thresholf used on the cumulation of rasters)
class ConstraintItem:
    ## @var name
    # name of the layer: either the absolute path of the layer for the SuricatesAlgo, or the name displayed in the panel of layers

    ## @var buffer
    # distance considered from layer items

    ## @var priority
    # priority of the current layer.
    # This set a weight to each layers of the list of constrained layers to define the importance of the layer in the computation result.
    #
    # In the case of a layer with the special type ConstraintType.Map, the attribute is used to store the threshold value.

    ## @var typeIn
    # constraint type used inside the zone of the layer (ConstraintType)

    ## @var typeOut
    # typeOut constraint type used outside the zone of the layer (ConstraintType)

    ## @var exists
    # used to determine if the layer associated to the constraint already exists.

    ## @brief constructor
    # @param name name of the layer
    # @param buffer distance considered from layer items
    # @param priority priority of the current layer
    # @param typeIn constraint type used inside the zone of the layer
    # @param typeOut constraint type used outside the zone of the layer
    def __init__(self, name, buffer = 50, priority = 100, typeIn:ConstraintType = ConstraintType.Sanctuarized, typeOut:ConstraintType = ConstraintType.Sanctuarized):
        self.name = name
        self.buffer = buffer
        self.priority = priority
        self.typeIn = typeIn
        self.typeOut = typeOut
        self.exists = True