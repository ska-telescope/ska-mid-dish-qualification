"""DiSQ GUI execute command method window."""

import logging

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget

from ska_mid_disq.constants import SKAO_ICON_PATH

logger = logging.getLogger("gui.view")


class CommandWindow(QWidget):
    """A window for executing any command method of the PLC program."""

    def __init__(
        self,
        command: str,
    ):
        """
        Initialise the CommandWindow.

        :param command: The command to open.
        """
        super().__init__()
        self.command = command
        self.setWindowTitle(self.command)
        self.setWindowIcon(QIcon(SKAO_ICON_PATH))
