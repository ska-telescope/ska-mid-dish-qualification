"""This package implements the SKA-Mid Dish Structure Qualification (DiSQ) software."""

from importlib.metadata import version  # noqa

from ska_mid_dish_steering_control import SCU, SteeringControlUnit
from ska_mid_dish_steering_control.constants import CmdReturn, Command, ResultCode

__version__ = version("ska-mid-disq")
from ska_mid_disq.model import DataLogger, SCUWeatherStation
from ska_mid_disq.server_validator import OPCUAServerValidator
from ska_mid_disq.utils import (
    SCU_from_config,
    SCUWeatherStation_from_config,
    hdf5_to_csv,
)

del version

__all__ = [
    "__version__",
    "CmdReturn",
    "Command",
    "ResultCode",
    "DataLogger",
    "SCU",
    "SCU_from_config",
    "SCUWeatherStation_from_config",
    "SCUWeatherStation",
    "SteeringControlUnit",
    "OPCUAServerValidator",
    "hdf5_to_csv",
]
