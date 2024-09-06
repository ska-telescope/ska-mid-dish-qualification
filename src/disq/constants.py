"""Common DiSQ enumerated types and other constants used in the package."""

from enum import Enum, IntEnum
from importlib import metadata
from pathlib import Path
from typing import Final

from platformdirs import user_cache_dir

# Constants
USER_CACHE_DIR: Final = Path(user_cache_dir(appauthor="SKAO", appname="disq"))
PACKAGE_VERSION: Final = metadata.version("DiSQ")
SUBSCRIPTION_RATE_MS: Final = 100


# Enumerations
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
