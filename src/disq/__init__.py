"""This package implements the SKA-Mid Dish Structure Qualification (DiSQ) software."""

from importlib.metadata import version  # noqa

from disq.constants import Command, ResultCode
from disq.sculib import SCU, SCU_from_config, SecondaryControlUnit, configure_logging

__version__ = version("DiSQ")
del version

__all__ = [
    "__version__",
    "Command",
    "ResultCode",
    "SCU",
    "SCU_from_config",
    "SecondaryControlUnit",
    "configure_logging",
]
