"""DiSQ environment and host OS related utilities."""

import os
import platform
import sys
from pathlib import Path


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


def open_path_in_explorer(path: Path) -> None:
    """
    Open a directory or file path in the system file explorer.

    :param path: to open.
    """
    # Open the path in the system file explorer
    if platform.system() == "Windows":
        # pylint: disable=no-member
        os.startfile(path)  # type: ignore
    elif platform.system() == "Darwin":  # macOS
        os.system(f"open {path}")
    else:  # Linux and other Unix-like systems
        os.system(f"xdg-open {path}")
