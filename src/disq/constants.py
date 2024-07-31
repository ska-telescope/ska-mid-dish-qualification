"""Common DiSQ enumerated types and other constants used in the package."""

from enum import Enum, IntEnum
from importlib import metadata
from typing import Final

# Constants
PACKAGE_VERSION: Final = metadata.version("DiSQ")


# Enumerations
class NodesStatus(Enum):
    """Nodes status."""

    NOT_CONNECTED = "Not connected to server"
    VALID = "Nodes valid"
    ATTR_NOT_FOUND = "Client is missing attribute(s). Check log!"
    NODE_INVALID = "Client has invalid attribute(s). Check log!"
    NOT_FOUND_INVALID = "Client is missing and has invalid attribute(s). Check log!"


class Command(Enum):
    """
    Commands of Dish Controller used in SCU methods.

    This needs to be kept up to date with the ICD.
    """

    TAKE_AUTH = "CommandArbiter.Commands.TakeAuth"
    RELEASE_AUTH = "CommandArbiter.Commands.ReleaseAuth"
    ACTIVATE = "Management.Commands.Activate"
    DEACTIVATE = "Management.Commands.DeActivate"
    MOVE2BAND = "Management.Commands.Move2Band"
    RESET = "Management.Commands.Reset"
    SLEW2ABS_AZ_EL = "Management.Commands.Slew2AbsAzEl"
    SLEW2ABS_SINGLE_AX = "Management.Commands.Slew2AbsSingleAx"
    STOP = "Management.Commands.Stop"
    STOW = "Management.Commands.Stow"
    AMBTEMP_CORR_SETUP = "Pointing.Commands.AmbTempCorrSetup"
    PM_CORR_ON_OFF = "Pointing.Commands.PmCorrOnOff"
    STATIC_PM_SETUP = "Pointing.Commands.StaticPmSetup"
    INTERLOCK_ACK = "Safety.Commands.InterlockAck"
    TRACK_LOAD_STATIC_OFF = "Tracking.Commands.TrackLoadStaticOff"
    TRACK_LOAD_TABLE = "Tracking.Commands.TrackLoadTable"
    TRACK_START = "Tracking.Commands.TrackStart"


class ResultCode(IntEnum):
    """
    Result codes of commands.

    This enum extens the CmdResponseType and needs to be kept up to date with the ICD.
    """

    UNKNOWN = -10
    # Codes for caught asyncua exceptions
    CONNECTION_CLOSED = -3
    UA_BASE_EXCEPTION = -2
    # Code for when command is not executed by SCU for some reason
    NOT_EXECUTED = -1
    # CmdResponseType enum
    NO_CMD_AUTH = 0
    DISH_LOCKED = 1
    COMMAND_REJECTED = 2
    COMMAND_TIMEOUT = 3
    COMMAND_FAILED = 4
    AXIS_NOT_ACTIVATED = 5
    STOWED = 6
    PARAMETER_INVALID = 7
    PARAMETER_OUT_OF_RANGE = 8
    COMMAND_ACTIVATED = 9
    COMMAND_DONE = 10
    NOT_IMPLEMENTED = 11


# Type aliases
CmdReturn = tuple[ResultCode, str, list[int | None] | None]
