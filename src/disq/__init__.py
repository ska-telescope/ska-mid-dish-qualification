"""This package implements the SKA-Mid Dish Structure Qualification (DiSQ) software."""

from importlib.metadata import version  # noqa

from disq import configuration
from disq.constants import Command, ResultCode
from disq.logger import Logger
from disq.sculib import SCU, SCU_from_config, SteeringControlUnit, configure_logging
from disq.server_validator import OPCUAServerValidator

__version__ = version("DiSQ")
del version

__all__ = [
    "__version__",
    "configuration",
    "Command",
    "ResultCode",
    "Logger",
    "SCU",
    "SCU_from_config",
    "SteeringControlUnit",
    "configure_logging",
    "OPCUAServerValidator",
]
