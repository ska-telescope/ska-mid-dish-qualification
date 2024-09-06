"""This package implements the SKA-Mid Dish Structure Qualification (DiSQ) software."""

from importlib.metadata import version  # noqa

from ska_mid_dish_steering_control import SCU, SteeringControlUnit
from ska_mid_dish_steering_control.constants import (
    CmdReturn,
    Command,
    NamePlate,
    ResultCode,
)

from disq import configuration
from disq.constants import PACKAGE_VERSION
from disq.logger import Logger
from disq.scu_generators import SCU_from_config
from disq.server_validator import OPCUAServerValidator

__version__ = version("DiSQ")
del version

__all__ = [
    "__version__",
    "configuration",
    "CmdReturn",
    "Command",
    "NamePlate",
    "ResultCode",
    "Logger",
    "SCU",
    "SCU_from_config",
    "SteeringControlUnit",
    "OPCUAServerValidator",
    "PACKAGE_VERSION",
]
