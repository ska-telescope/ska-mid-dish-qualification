"""DiSQ environment and host OS related utilities."""

import os
import sys


def is_standalone_executable() -> bool:
    """
    Check if the application is running as a standalone executable.

    :return: whether the application is running as a standalone executable.
    """
    # Check for PyInstaller or similar attributes
    if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"):
        return True
    # Check for a specific file or directory
    if os.path.exists(os.path.join(os.path.dirname(sys.executable), "_internal")):
        return True
    return False
