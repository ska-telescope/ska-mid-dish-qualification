"""This package implements the SKA-Mid Dish Structure Qualification (DiSQ) software."""

from importlib.metadata import version  # noqa

from disq.constants import Command, ResultCode  # noqa: F401
from disq.sculib import (  # noqa: F401
    SCU,
    SCU_from_config,
    SecondaryControlUnit,
    configure_logging,
)

__version__ = version("DiSQ")
del version

__all__ = ["__version__"]
