from importlib.metadata import version  # noqa

__version__ = version("DiSQ")
del version

__all__ = ["__version__"]
