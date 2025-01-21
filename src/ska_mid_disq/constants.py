"""Common DiSQ enumerated types and other constants used in the package."""

from enum import Enum, IntEnum
from typing import Final

from platformdirs import user_cache_path, user_config_path

# Constants
USER_CACHE_DIR: Final = user_cache_path(appauthor="SKAO", appname="disq")
USER_CONFIG_DIR: Final = user_config_path(appauthor="SKAO", appname="disq")
SUBSCRIPTION_RATE_MS: Final = 100
CURRENT_POINTING_NODE = "Pointing.Status.CurrentPointing"
SKAO_ICON_PATH: Final = ":/icons/skao.ico"


# Enumerations
class NamePlate(Enum):
    """
    Nodes used for DSC lifetime and identification.

    This needs to be kept up to date with the ICD.
    """

    DISH_ID = "Management.NamePlate.DishId"
    DISH_STRUCTURE_SERIAL_NO = "Management.NamePlate.DishStructureSerialNo"
    DSC_SOFTWARE_VERSION = "Management.NamePlate.DscSoftwareVersion"
    ICD_VERSION = "Management.NamePlate.IcdVersion"
    RUN_HOURS = "Management.NamePlate.RunHours"
    TOTAL_DIST_AZ = "Management.NamePlate.TotalDist_Az"
    TOTAL_DIST_EL_DEG = "Management.NamePlate.TotalDist_El_deg"
    TOTAL_DIST_EL_M = "Management.NamePlate.TotalDist_El_m"
    TOTAL_DIST_FI = "Management.NamePlate.TotalDist_Fi"
    TILTMETER_ONE_SERIAL_NO = "Pointing.TiltmeterParameters.One.Tiltmeter_serial_no"
    TILTMETER_TWO_SERIAL_NO = "Pointing.TiltmeterParameters.Two.Tiltmeter_serial_no"


class NodesStatus(Enum):
    """Nodes status."""

    NOT_CONNECTED = "Not connected to server"
    VALID = "Nodes valid"
    ATTR_NOT_FOUND = "Client is missing attribute(s). Check log!"
    NODE_INVALID = "Client has invalid attribute(s). Check log!"
    NOT_FOUND_INVALID = "Client is missing and has invalid attribute(s). Check log!"


class StatusTreeCategory(IntEnum):
    """
    Category of status update.

    Describes whether a status update is a warning or error.
    """

    ERROR = 0
    WARNING = 1


class PollerType(Enum):
    """Possible types of connected servers."""

    OPCUA = "OPCUA"
    WMS = "WMS"
    GRAPH = "GRAPH"
