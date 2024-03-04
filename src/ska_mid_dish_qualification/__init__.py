from importlib.metadata import version  # noqa

__version__ = version("ska-mid-dish-qualification")
del version

__all__ = ["__version__"]
