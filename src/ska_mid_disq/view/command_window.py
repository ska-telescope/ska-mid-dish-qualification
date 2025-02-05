"""DiSQ GUI execute command method window."""

import logging
from typing import Callable

from asyncua import ua
from PySide6.QtCore import Qt, SignalInstance
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QDockWidget,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QWidget,
)

from ska_mid_disq.constants import SKAO_ICON_PATH

from .controller import Controller

logger = logging.getLogger("gui.view")


class CommandWindow(QDockWidget):
    """A window for executing any command method of the PLC program."""

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        command: str,
        command_method: Callable,
        input_args: list[tuple[str, str]],
        controller: Controller,
        close_signal: SignalInstance,
    ) -> None:
        """
        Initialise the CommandWindow.

        :param command: The command to open.
        :param command_method: Method to execute the command.
        :param input_args: A list of the input arguments and their types.
        :param controller: The controller object of the GUI view.
        :param close_signal: The signal to send when this window closes.
        """
        super().__init__()
        self.command = command
        self.command_method = command_method
        self.controller = controller
        self.close_signal = close_signal
        self.setWindowTitle("Command")
        self.setWindowIcon(QIcon(SKAO_ICON_PATH))
        self.grid_layout = QGridLayout()
        # Add labels for command name, and argument/input field columns
        command_str = command.split(".")
        label = QLabel(f"<b>{command_str[0]} -> {command_str[-1]}</b>")
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.grid_layout.addWidget(label, 0, 0, 1, 2)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        self.grid_layout.addWidget(line, 1, 0, 1, 2)
        label = QLabel("Argument")
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.grid_layout.addWidget(label, 2, 0)
        label = QLabel("Input field")
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.grid_layout.addWidget(label, 2, 1)
        # Add argument labels and corresponding line edit or checkbox widgets for input
        self.edit_inputs: list[QLineEdit | QCheckBox] = []
        for i, arg in enumerate(input_args, self.grid_layout.rowCount() + 1):
            label = QLabel(f"{arg[0]}:")
            label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.grid_layout.addWidget(label, i, 0)
            if arg[1] == "Boolean":
                checkbox = QCheckBox()
                checkbox.setToolTip("Boolean: Checked is true, unchecked is false.")
                self.edit_inputs.append(checkbox)
                self.grid_layout.addWidget(checkbox, i, 1)
            else:
                line_edit = QLineEdit()
                if arg[0] == "SessionID":
                    line_edit.setEnabled(False)
                    line_edit.setPlaceholderText("*****")
                    line_edit.setToolTip(
                        "SessionID is handled internally in the OPC-UA client instance "
                        "and cannot be changed."
                    )
                else:
                    line_edit.setPlaceholderText(arg[1])
                    self.edit_inputs.append(line_edit)
                self.grid_layout.addWidget(line_edit, i, 1)
        # Add button to execute command
        self.button_execute = QPushButton("Execute")
        self.button_execute.clicked.connect(self.execute_command)
        self.grid_layout.addWidget(
            self.button_execute, self.grid_layout.rowCount() + 1, 1
        )
        self.grid_layout.addItem(
            QSpacerItem(
                10, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            ),
            self.grid_layout.rowCount() + 1,
            0,
        )
        widget = QWidget()
        widget.setLayout(self.grid_layout)
        self.setWidget(widget)
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

    def execute_command(self) -> None:
        """Execute the command."""
        # Only needs to handle UInt16, Double, Boolean and String arguments
        args = []
        for input_wgt in self.edit_inputs:
            if isinstance(input_wgt, QCheckBox):
                args.append(input_wgt.isChecked())
            else:
                type_name = input_wgt.placeholderText()
                cast_type = getattr(ua, type_name)  # Get type conversion method
                try:
                    args.append(cast_type(input_wgt.text()))
                except (ValueError, TypeError) as e:
                    self.controller.emit_ui_status_message(
                        "ERROR",
                        f"Invalid input for command '{self.command}' argument - {e}",
                    )
                    return
        logger.debug("Calling command: %s, args: %s", self.command, args)
        result_code, result_msg, _ = self.command_method(*args)
        self.controller.command_response_str(self.command, result_code, result_msg)

    # pylint: disable=invalid-name
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Override of PYQT method, called when window is closed."""
        self.close_signal.emit(self.command)
        super().closeEvent(event)
