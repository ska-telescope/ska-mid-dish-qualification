"""This package implements the SKA-Mid Dish Structure Qualification (DiSQ) software."""

from importlib.metadata import version  # noqa

from ska_mid_dish_steering_control import SCU, SteeringControlUnit
from ska_mid_dish_steering_control.constants import CmdReturn, Command, ResultCode

__version__ = version("ska-mid-disq")
from ska_mid_disq import configuration
from ska_mid_disq.data_logger import DataLogger
from ska_mid_disq.scu_generators import SCU_from_config
from ska_mid_disq.scu_weather_station import SCUWeatherStation
from ska_mid_disq.server_validator import OPCUAServerValidator

del version

__all__ = [
    "__version__",
    "configuration",
    "CmdReturn",
    "Command",
    "ResultCode",
    "DataLogger",
    "SCU",
    "SCU_from_config",
    "SCUWeatherStation",
    "SteeringControlUnit",
    "OPCUAServerValidator",
]
