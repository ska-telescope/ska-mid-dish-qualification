# pylint: disable=too-many-lines
"""DiSQ GUI View."""

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from functools import cached_property
from importlib import resources
from pathlib import Path
from typing import Any, Callable, Final

from platformdirs import user_documents_dir
from PyQt6 import QtCore, QtWidgets, uic
from PyQt6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QDesktopServices,
    QIcon,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QFileDialog

from ska_mid_disq import ResultCode, __version__, controller, model
from ska_mid_disq.constants import StatusTreeCategory

from . import ui_resources  # noqa pylint: disable=unused-import

logger = logging.getLogger("gui.view")

# Constant definitions of attribute names on the OPC-UA server
TILT_CORR_ACTIVE: Final = "Pointing.Status.TiltCorrActive"
TILT_METER_TWO_ON: Final = "Pointing.Status.TiltTwo_On"
BAND_FOR_CORR: Final = "Pointing.Status.BandForCorr"
TEMP_CORR_ACTIVE: Final = "Pointing.Status.TempCorrActive"

# Axis limits defined in ICD
AZ_POS_MAX: Final = 271.0
AZ_POS_MIN: Final = -271.0
AZ_VEL_MAX: Final = 3.0
EL_POS_MAX: Final = 90.2
EL_POS_MIN: Final = 14.8
EL_VEL_MAX: Final = 1.0
FI_POS_MAX: Final = 106.0
FI_POS_MIN: Final = -106.0
FI_VEL_MAX: Final = 12.0

SKAO_ICON_PATH: Final = ":/icons/skao.ico"
DISPLAY_DECIMAL_PLACES: Final = 5


# pylint: disable=too-many-instance-attributes
class ServerConnectDialog(QtWidgets.QDialog):
    """
    A dialog-window class for connecting to the OPC-UA server.

    :param parent: The parent widget of the dialog.
    """

    def __init__(
        self, parent: QtWidgets.QWidget, mvc_controller: controller.Controller
    ):
        """
        Initialize the Server Connect dialog.

        :param parent: The parent widget for the dialog.
        """
        super().__init__(parent)
        self._controller = mvc_controller

        self.setWindowTitle("Server Connection")
        self.setWindowIcon(QIcon(SKAO_ICON_PATH))

        button = (
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )

        self.btn_box = QtWidgets.QDialogButtonBox(button)
        self.btn_box.accepted.connect(self.confirm_connect)
        self.btn_box.rejected.connect(self.reject)

        self.vbox_layout = QtWidgets.QVBoxLayout()
        message = QtWidgets.QLabel(
            "Enter or select the OPC-UA server details and click OK"
        )
        self.vbox_layout.addWidget(message)

        # Populate the server config select (drop-down) box with entries from
        # configuration file
        server_list = self._controller.get_config_servers()
        self.dropdown_server_config_select = QtWidgets.QComboBox()
        self.dropdown_server_config_select.addItems([""] + server_list)
        self.dropdown_server_config_select.setFocus()
        self.dropdown_server_config_select.currentTextChanged.connect(
            self.server_config_select_changed
        )
        self.vbox_layout.addWidget(QtWidgets.QLabel("Select server from config file:"))
        self.vbox_layout.addWidget(self.dropdown_server_config_select)

        self.vbox_layout.addWidget(QtWidgets.QLabel("Server Address:"))
        self.input_server_address = QtWidgets.QLineEdit()
        self.input_server_address.setPlaceholderText("Server Address")
        self.vbox_layout.addWidget(self.input_server_address)

        self.vbox_layout.addWidget(QtWidgets.QLabel("Server Port:"))
        self.input_server_port = QtWidgets.QLineEdit()
        self.input_server_port.setPlaceholderText("Server Port")
        self.vbox_layout.addWidget(self.input_server_port)

        self.vbox_layout.addWidget(QtWidgets.QLabel("Server Endpoint:"))
        self.input_server_endpoint = QtWidgets.QLineEdit()
        self.input_server_endpoint.setPlaceholderText("Server Endpoint")
        self.vbox_layout.addWidget(self.input_server_endpoint)

        self.vbox_layout.addWidget(QtWidgets.QLabel("Server Namespace:"))
        self.input_server_namespace = QtWidgets.QLineEdit()
        self.input_server_namespace.setPlaceholderText("Server Namespace")
        self.vbox_layout.addWidget(self.input_server_namespace)

        self.cache_checkbox = QtWidgets.QCheckBox()
        self.cache_checkbox.setText("Use nodes cache")
        self.cache_checkbox.setChecked(False)
        self.vbox_layout.addWidget(self.cache_checkbox)

        self.vbox_layout.addWidget(self.btn_box)
        self.setLayout(self.vbox_layout)
        self.server_details: dict[str, str] = {}

    @property
    def server_config_selected(self) -> str:
        """Return the server config selected in the drop-down box."""
        return self.dropdown_server_config_select.currentText()

    def server_config_select_changed(self, server_name: str) -> None:
        """
        User changed server selection in drop-down box.

        Enable/disable relevant widgets.
        """
        logger.debug("server config select changed: %s", server_name)
        if server_name is None or server_name == "":
            self._enable_server_widgets(True)
        else:
            # Clear the input boxes first
            self.input_server_address.clear()
            self.input_server_port.clear()
            self.input_server_endpoint.clear()
            self.input_server_namespace.clear()
            # Get the server config args from configfile
            server_config = self._controller.get_config_server_args(server_name)
            # Populate the widgets with the server config args
            if "endpoint" in server_config and "namespace" in server_config:
                self.input_server_address.setText(server_config["host"])
                self.input_server_port.setText(server_config["port"])
                self.input_server_endpoint.setText(server_config["endpoint"])
                self.input_server_namespace.setText(server_config["namespace"])
            else:
                # First physical controller does not have an endpoint or namespace
                self.input_server_address.setText(server_config["host"])
                self.input_server_port.setText(server_config["port"])
            # Disable editing of the widgets
            self._enable_server_widgets(False)

    def _enable_server_widgets(self, enable: bool = True) -> None:
        """
        Enable or disable server widgets and optionally update the connect button text.

        :param enable: Enable or disable server widgets (default True).
        :param connect_button: Update the connect button text (default False).
        """
        self.input_server_address.setEnabled(enable)
        self.input_server_port.setEnabled(enable)
        self.input_server_endpoint.setEnabled(enable)
        self.input_server_namespace.setEnabled(enable)

    def confirm_connect(self):
        """Accepts the server connection details entered in the dialog."""
        logger.debug("Server connect dialog accepted")
        self.server_details = {
            "host": self.input_server_address.text(),
            "port": self.input_server_port.text(),
            "endpoint": self.input_server_endpoint.text(),
            "namespace": self.input_server_namespace.text(),
            "use_nodes_cache": self.cache_checkbox.isChecked(),
        }
        self.accept()


class StatusBarMixin:
    """A mixin class to provide a window with a status bar."""

    def create_status_bar_widget(
        self,
        label: str = "",
    ) -> QtWidgets.QStatusBar:
        """Create the status bar widgets for the window."""
        # Add a label widget to the status bar for command/response status
        status_bar = QtWidgets.QStatusBar()
        self.cmd_status_label = QtWidgets.QLabel(label)
        status_bar.addWidget(self.cmd_status_label)
        return status_bar

    def status_bar_update(self, status: str) -> None:
        """Update the status bar with a status update."""
        self.cmd_status_label.setText(status[:200])


# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-statements
class RecordingConfigDialog(StatusBarMixin, QtWidgets.QDialog):
    """
    A dialog-window class for selecting OPC-UA parameters to be recorded.

    :param parent: The parent widget of the dialog.
    :param attributes: A list of OPC-UA attributes to be displayed and selected.
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        attributes: dict[str, dict[str, bool | int]],
    ):
        """
        Initialize the Recording Configuration dialog.

        :param parent: The parent widget for the dialog.
        :param attributes: A list of strings representing OPC-UA attributes to choose
            from.
        """
        super().__init__(parent)

        self.setWindowTitle("Recording Configuration")
        self.setWindowIcon(QIcon(SKAO_ICON_PATH))
        self.resize(544, 512)

        self._node_table_widgets: dict[
            str, dict[str, QtWidgets.QCheckBox | QtWidgets.QLineEdit]
        ] = {}

        button = (
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )

        self.btn_box = QtWidgets.QDialogButtonBox(button)
        self.btn_box.accepted.connect(self.accept_selection)
        self.btn_box.rejected.connect(self.reject)

        self.grid_layout = QtWidgets.QGridLayout()
        table_options_layout = QtWidgets.QGridLayout()
        self.table_file_label = QtWidgets.QLabel("Table config file:")
        self.table_file_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignCenter
        )
        self.table_file_load = QtWidgets.QPushButton("Open File...")
        self.table_file_load.clicked.connect(self._load_node_table)
        self.table_file_save = QtWidgets.QPushButton("Save As...")
        self.table_file_save.clicked.connect(self._save_node_table)
        self.record_column_label = QtWidgets.QLabel("Record column:")
        self.record_column_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignCenter
        )
        self.record_column_tick = QtWidgets.QPushButton("Record All")
        self.record_column_tick.clicked.connect(
            lambda: self._set_all_record_checkboxes(True)
        )
        self.record_column_clear = QtWidgets.QPushButton("Clear All")
        self.record_column_clear.clicked.connect(
            lambda: self._set_all_record_checkboxes(False)
        )
        self.period_column_label = QtWidgets.QLabel("Period column:")
        self.period_column_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignCenter
        )
        self.period_column_value = QtWidgets.QSpinBox()
        # Remove step buttons and prevent mouse wheel interaction
        self.period_column_value.setButtonSymbols(
            QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        self.period_column_value.wheelEvent = lambda e: None  # type: ignore[assignment]
        self.period_column_value.setRange(50, 60000)
        self.period_column_value.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.period_column_set = QtWidgets.QPushButton("Set All")
        self.period_column_set.clicked.connect(self._set_all_period_spinboxes)
        table_options_layout.addWidget(self.table_file_label, 0, 0)
        table_options_layout.addWidget(self.table_file_load, 0, 1)
        table_options_layout.addWidget(self.table_file_save, 0, 2)
        table_options_layout.addWidget(self.record_column_label, 1, 0)
        table_options_layout.addWidget(self.record_column_tick, 1, 1)
        table_options_layout.addWidget(self.record_column_clear, 1, 2)
        table_options_layout.addWidget(self.period_column_label, 2, 0)
        table_options_layout.addWidget(self.period_column_value, 2, 1)
        table_options_layout.addWidget(self.period_column_set, 2, 2)
        self.grid_layout.addLayout(table_options_layout, 0, 0)

        message = QtWidgets.QLabel(
            "Select all the OPC-UA attributes to record from the list and click OK"
        )
        message.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignCenter
        )
        self.grid_layout.addWidget(message)

        self.node_table = QtWidgets.QTableWidget(len(attributes), 3, self)
        self._create_node_table(attributes, self.node_table)
        self.grid_layout.addWidget(self.node_table)

        self.grid_layout.addWidget(self.btn_box)
        status_bar = self.create_status_bar_widget()
        self.grid_layout.addWidget(status_bar)
        self.setLayout(self.grid_layout)
        self.config_parameters: dict[str, dict[str, bool | int]] = {}

    def _create_node_table(self, attributes, node_table):
        """Create the attribute node table."""
        node_table.setStyleSheet(
            "QCheckBox {margin-left: 28px;} "
            "QCheckBox::indicator {width: 24px; height: 24px}"
        )
        node_table.setHorizontalHeaderLabels(
            ["Attribute Name", "Record", "Period (ms)"]
        )
        horizontal_header = node_table.horizontalHeader()
        horizontal_header.setDefaultSectionSize(80)
        horizontal_header.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch
        )

        vertical_header = QtWidgets.QHeaderView(QtCore.Qt.Orientation.Vertical)
        vertical_header.hide()
        node_table.setVerticalHeader(vertical_header)
        node_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        for i, (attr, value) in enumerate(attributes.items()):
            # Add node name in first column and turn off table interactions
            node_name = QtWidgets.QTableWidgetItem(attr)
            node_name.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            node_table.setItem(i, 0, node_name)
            # Ensure "Record" and "Period" columns are also not interactable
            add_background = QtWidgets.QTableWidgetItem()
            period_background = QtWidgets.QTableWidgetItem()
            add_background.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            period_background.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            node_table.setItem(i, 1, add_background)
            node_table.setItem(i, 2, period_background)
            # Add "Record" checkbox
            record_node = QtWidgets.QCheckBox()
            record_node.setChecked(value["record"])
            node_table.setCellWidget(i, 1, record_node)
            # Add "Period" line edit
            node_period = QtWidgets.QSpinBox()
            # Remove step buttons and prevent mouse wheel interaction
            node_period.setButtonSymbols(
                QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons
            )
            node_period.wheelEvent = node_table.wheelEvent
            node_period.setRange(50, 60000)
            node_period.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
            node_period.setValue(value["period"])
            node_table.setCellWidget(i, 2, node_period)
            self._node_table_widgets[attr] = {
                "record_check_box": record_node,
                "period_spin_box": node_period,
            }

    def _set_all_record_checkboxes(self, checked: bool) -> None:
        """Unchecks all of the "Record" checkboxes."""
        for widgets in self._node_table_widgets.values():
            widgets["record_check_box"].setChecked(checked)  # type: ignore[union-attr]

        status_update = "Record column "
        if checked:
            status_update += "ticked."
        else:
            status_update += "cleared."

        self.status_bar_update(status_update)

    def _set_all_period_spinboxes(self) -> None:
        """Sets all period spinboxes to the value in self.period_column_value."""
        value = self.period_column_value.value()
        for widgets in self._node_table_widgets.values():
            widgets["period_spin_box"].setValue(value)  # type: ignore[union-attr]

        self.status_bar_update(f"Period column set to {value} milliseconds.")

    def _save_node_table(self) -> None:
        """Save the node table to a json file."""
        _fname, _ = QFileDialog.getSaveFileName(
            parent=self,
            caption="Save Recording Config File",
            directory=user_documents_dir(),
            filter="Recording Config Files (*.json);;All Files (*)",
        )
        if _fname:
            filename = Path(_fname)
            logger.info("Recording save file name: %s", filename)
            if filename.suffix != ".json":
                filename = filename.parent / (filename.name + ".json")
            with open(filename, "w", encoding="UTF-8") as f:
                json.dump(self._get_current_config(), f, indent=4, sort_keys=True)

            self.status_bar_update(f"Recording config saved to file {filename}")

    def _load_node_table(self) -> None:
        """Load the node table from a json file."""
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            parent=self,
            caption="Load Recording Config File",
            directory=user_documents_dir(),
            filter="Recording Config Files (*.json);;All Files (*)",
        )
        if filename:
            logger.info("Recording load file name: %s", filename)
            with open(filename, "r", encoding="UTF-8") as f:
                try:
                    config = json.load(f)
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning("Could not load file %s: %s", filename, e)
                    self.status_bar_update(f"Could not load file {filename}")
                    return

            # Check stored values before updating table
            for node, values in config.items():
                try:
                    record = values["record"]
                    period = values["period"]
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning(
                        "Could not load file %s: %s:%s", filename, type(e).__name__, e
                    )
                    self.status_bar_update(
                        f"Error: {e} value missing for node {node} in file {filename}"
                    )
                    return

                if not isinstance(record, bool) or not isinstance(period, int):
                    logger.warning(
                        "Could not load file %s: incompatible values (%s, %s) for node "
                        "%s",
                        filename,
                        record,
                        period,
                        node,
                    )
                    self.status_bar_update(
                        f"Incompatible values ({record}, {period}) for {node} in file "
                        "{filename}"
                    )
                    return

            missing_nodes = list(self._node_table_widgets.keys())
            extra_nodes = []
            for node, values in config.items():
                if node in self._node_table_widgets:
                    self._node_table_widgets[node][
                        "record_check_box"
                    ].setChecked(  # type: ignore[union-attr]
                        values["record"]
                    )
                    self._node_table_widgets[node][
                        "period_spin_box"
                    ].setValue(  # type: ignore[union-attr]
                        values["period"]
                    )
                    missing_nodes.remove(node)
                else:
                    extra_nodes.append(node)

            self.status_bar_update(f"Recording config loaded from file {filename}")
            error_status_update = ""
            if missing_nodes:
                logger.warning(
                    "The server has attributes not in the config file. "
                    "The following attributes have not been updated: %s",
                    missing_nodes,
                )
                error_status_update += (
                    "This server has attributes not in the selected " "config file. "
                )

            if extra_nodes:
                logger.warning(
                    "The file contains attributes not available on the server. "
                    "The following attributes have not been updated: %s",
                    extra_nodes,
                )
                error_status_update += (
                    "The selected config file contains attributes not available on "
                    "this server. "
                )

            if error_status_update:
                error_status_update += "Only overlapping attributes will be updated."
                self.status_bar_update(error_status_update)

    def _get_current_config(self) -> dict[str, dict[str, bool | int]]:
        """Get the current attribute record and period values."""
        config_parameters = {}
        for node, widgets in self._node_table_widgets.items():
            config_parameters[node] = {
                "record": widgets[
                    "record_check_box"
                ].isChecked(),  # type: ignore[union-attr]
                "period": widgets[
                    "period_spin_box"
                ].value(),  # type: ignore[union-attr]
            }

        return config_parameters

    def accept_selection(self):
        """Accepts the selection made in the configuration dialog."""
        logger.debug("Recording config dialog accepted")
        self.config_parameters = self._get_current_config()
        self.accept()


# pylint: disable=too-many-statements, too-many-public-methods,
# pylint: disable=too-many-instance-attributes
class MainView(StatusBarMixin, QtWidgets.QMainWindow):
    """
    A class representing the main Window of the DiSQ GUI application.

    :param disq_model: The model instance for the MainView.
    :param disq_controller: The controller instance for the MainView.
    """

    _LED_COLOURS: Final[dict[str, dict[bool | str, str]]] = {
        "red": {True: "rgb(255, 0, 0)", False: "rgb(60, 0, 0)"},
        "green": {True: "rgb(10, 250, 25)", False: "rgb(10, 60, 0)"},
        "yellow": {True: "rgb(250, 255, 0)", False: "rgb(45, 44, 0)"},
        "orange": {True: "rgb(255, 170, 0)", False: "rgb(92, 61, 0)"},
        "StowPinStatusType": {
            "unknown": "rgb(10, 10, 10)",
            "retracted": "rgb(10, 250, 25)",
            "retracting": "rgb(250, 255, 0)",
            "deployed": "rgb(255, 0, 0)",
            "deploying": "rgb(250, 255, 0)",
            "motiontimeout": "rgb(255, 0, 0)",
        },
    }

    def __init__(
        self,
        disq_model: model.Model,
        disq_controller: controller.Controller,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the DiSQ GUI with the provided model and controller.

        The function initializes the GUI components with the provided model and
        controller objects. It loads the UI from the XML file, sets the window title,
        and connects various buttons and widgets to their corresponding functions in the
        controller.

        The function also reads server configuration details from environment variables
        and populates the input fields accordingly. It sets up event handlers for
        updating the UI based on server connection status, receiving data from the
        model, and handling recording functionality.

        Additionally, the function connects various buttons for different control
        actions such as slew, stop, activate, deactivate, etc. It also handles
        recording, track table loading, and configuration related functionalities.

        The function sets up the UI layout and initial widget states based on the
        provided model and controller objects.

        :param disq_model: The model object for DiSQ.
        :param disq_controller: The controller object for DiSQ.
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        """
        super().__init__(*args, **kwargs)
        # Load the UI from the XML .ui file
        ui_xml_filename = resources.files(__package__) / "ui/dishstructure_mvc.ui"
        uic.loadUi(ui_xml_filename, self)
        self.setWindowTitle(f"DiSQ GUI v{__version__}")
        self.setWindowIcon(QIcon(SKAO_ICON_PATH))

        # Adding a default style for the tooltip with a white background and black text
        # This is a work-around for the issue that tooltips inherit style from the
        # parent widget - and this choice of colour-scheme is at least readable.
        self.setStyleSheet(
            "QToolTip { color: black; background-color: white;"
            "border: 1px solid black; }"
        )

        # Menubar
        self.action_connect_opcua_server: QAction
        self.action_connect_opcua_server.triggered.connect(self.connect_button_clicked)
        self.action_disconnect_opcua_server: QAction
        self.action_disconnect_opcua_server.triggered.connect(
            self.connect_button_clicked
        )
        self.action_about: QAction
        self.action_about.triggered.connect(self.about_button_clicked)
        self.action_docs: QAction
        self.action_docs.triggered.connect(self.open_documentation)

        self.server_status_bar: QtWidgets.QWidget
        # Load a background image for the server connection QGroupBox
        pixmap = QPixmap(":/images/skao_colour_bar.png")
        palette = self.server_status_bar.palette()
        palette.setBrush(QPalette.ColorRole.Window, QBrush(pixmap))
        self.server_status_bar.setPalette(palette)
        self.server_status_bar.setAutoFillBackground(True)

        self.label_conn_status: QtWidgets.QLabel
        self.label_cache_status: QtWidgets.QLabel
        self.label_cache_status.setStyleSheet("QLabel { color: white; }")
        self.label_conn_status.setStyleSheet("QLabel { color: white; }")

        self.list_cmd_history: QtWidgets.QListWidget  # Command history list widget
        self.setStatusBar(self.create_status_bar_widget("ℹ️ Status"))

        # Keep a reference to model and controller
        self.model = disq_model
        self.controller = disq_controller

        # Connect widgets and slots to the Controller
        self.controller.ui_status_message.connect(self.command_response_status_update)
        self.controller.server_connected.connect(self.server_connected_event)
        self.controller.server_disconnected.connect(self.server_disconnected_event)

        # Listen for Model event signals
        self.model.data_received.connect(self.event_update)

        # Status panel widgets
        self.line_edit_warning_general: QtWidgets.QLineEdit

        # Authority status group widgets
        self.combobox_authority: QtWidgets.QComboBox
        self.button_take_auth: QtWidgets.QPushButton
        self.button_take_auth.clicked.connect(self.take_authority_button_clicked)
        self.button_release_auth: QtWidgets.QPushButton
        self.button_release_auth.clicked.connect(self.release_authority_button_clicked)
        self.button_interlock_ack: QtWidgets.QPushButton
        self.button_interlock_ack.clicked.connect(self.controller.command_interlock_ack)
        # Slew group widgets
        self.spinbox_slew_simul_azim_position: LimitedDisplaySpinBox
        self.spinbox_slew_simul_elev_position: LimitedDisplaySpinBox
        self.spinbox_slew_simul_azim_velocity: LimitedDisplaySpinBox
        self.spinbox_slew_simul_elev_velocity: LimitedDisplaySpinBox
        self.button_slew2abs: QtWidgets.QPushButton
        self.button_slew2abs.clicked.connect(self.slew2abs_button_clicked)
        # Commands group widgets
        self.button_stop: QtWidgets.QPushButton
        self.button_stop.clicked.connect(lambda: self.stop_button_clicked("AzEl"))
        self.button_stow: QtWidgets.QPushButton
        self.button_stow.clicked.connect(self.stow_button_clicked)
        self.button_unstow: QtWidgets.QPushButton
        self.button_unstow.clicked.connect(self.unstow_button_clicked)
        self.button_activate: QtWidgets.QPushButton
        self.button_activate.clicked.connect(
            lambda: self.activate_button_clicked("AzEl")
        )
        self.button_deactivate: QtWidgets.QPushButton
        self.button_deactivate.clicked.connect(
            lambda: self.deactivate_button_clicked("AzEl")
        )
        # Power tab widgets
        self.button_power_mode_normal: QtWidgets.QRadioButton
        self.button_power_mode_normal.setChecked(True)
        self.button_power_mode_low: QtWidgets.QRadioButton
        self.button_power_mode_low.setChecked(False)
        self.spinbox_power_lim_kw: QtWidgets.QDoubleSpinBox
        self.button_set_power_mode: QtWidgets.QPushButton
        self.button_set_power_mode.clicked.connect(self.set_power_mode_clicked)

        # Axis tab elevation group widgets
        self.button_elevation_slew: QtWidgets.QPushButton
        self.button_elevation_slew.clicked.connect(
            lambda: self.slew_button_clicked("El")
        )
        self.button_elevation_stop: QtWidgets.QPushButton
        self.button_elevation_stop.clicked.connect(
            lambda: self.stop_button_clicked("El")
        )
        self.button_elevation_activate: QtWidgets.QPushButton
        self.button_elevation_activate.clicked.connect(
            lambda: self.activate_button_clicked("El")
        )
        self.button_elevation_deactivate: QtWidgets.QPushButton
        self.button_elevation_deactivate.clicked.connect(
            lambda: self.deactivate_button_clicked("El")
        )
        self.spinbox_slew_only_elevation_position: LimitedDisplaySpinBox
        self.spinbox_slew_only_elevation_velocity: LimitedDisplaySpinBox
        self.button_elevation_reset: QtWidgets.QPushButton
        self.button_elevation_reset.clicked.connect(
            lambda: self.reset_button_clicked("El")
        )
        # Axis tab azimuth group widgets
        self.button_azimuth_slew: QtWidgets.QPushButton
        self.button_azimuth_slew.clicked.connect(lambda: self.slew_button_clicked("Az"))
        self.button_azimuth_stop: QtWidgets.QPushButton
        self.button_azimuth_stop.clicked.connect(lambda: self.stop_button_clicked("Az"))
        self.button_azimuth_activate: QtWidgets.QPushButton
        self.button_azimuth_activate.clicked.connect(
            lambda: self.activate_button_clicked("Az")
        )
        self.button_azimuth_deactivate: QtWidgets.QPushButton
        self.button_azimuth_deactivate.clicked.connect(
            lambda: self.deactivate_button_clicked("Az")
        )
        self.spinbox_slew_only_azimuth_position: LimitedDisplaySpinBox
        self.spinbox_slew_only_azimuth_velocity: LimitedDisplaySpinBox
        self.button_azimuth_reset: QtWidgets.QPushButton
        self.button_azimuth_reset.clicked.connect(
            lambda: self.reset_button_clicked("Az")
        )
        # Axis tab feed indexer group widgets
        self.button_indexer_slew: QtWidgets.QPushButton
        self.button_indexer_slew.clicked.connect(lambda: self.slew_button_clicked("Fi"))
        self.button_indexer_stop: QtWidgets.QPushButton
        self.button_indexer_stop.clicked.connect(lambda: self.stop_button_clicked("Fi"))
        self.button_indexer_activate: QtWidgets.QPushButton
        self.button_indexer_activate.clicked.connect(
            lambda: self.activate_button_clicked("Fi")
        )
        self.button_indexer_deactivate: QtWidgets.QPushButton
        self.button_indexer_deactivate.clicked.connect(
            lambda: self.deactivate_button_clicked("Fi")
        )
        self.spinbox_slew_only_indexer_position: LimitedDisplaySpinBox
        self.spinbox_slew_only_indexer_velocity: LimitedDisplaySpinBox
        self.button_indexer_reset: QtWidgets.QPushButton
        self.button_indexer_reset.clicked.connect(
            lambda: self.reset_button_clicked("Fi")
        )
        self.combobox_axis_input_step: QtWidgets.QComboBox
        self.combobox_axis_input_step.currentIndexChanged.connect(
            lambda: self.set_axis_inputs_step_size(
                float(self.combobox_axis_input_step.currentText())
            )
        )
        self.button_enable_axis_limits: QtWidgets.QRadioButton
        self.button_enable_axis_limits.toggled.connect(self.limit_axis_inputs_toggled)

        # Point tab static pointing model widgets
        self.button_static_point_model_import: QtWidgets.QPushButton
        self.button_static_point_model_import.clicked.connect(
            self.import_static_pointing_model
        )
        self.button_static_point_model_export: QtWidgets.QPushButton
        self.button_static_point_model_export.clicked.connect(
            self.export_static_pointing_model
        )
        self.button_static_point_model_apply: QtWidgets.QPushButton
        self.button_static_point_model_apply.clicked.connect(
            self.apply_static_pointing_parameters
        )
        self.button_static_point_model_toggle: ToggleSwitch
        self.button_static_point_model_toggle.clicked.connect(
            self.pointing_correction_setup_button_clicked
        )
        self.static_point_model_band: QtWidgets.QLabel
        self.static_point_model_band_index_prev: int = 0
        self.combo_static_point_model_band_input: QtWidgets.QComboBox
        self.combo_static_point_model_band_input.currentTextChanged.connect(
            self.pointing_model_band_selected_for_input
        )
        self.combo_static_point_model_band_display: QtWidgets.QComboBox
        self.combo_static_point_model_band_display.currentTextChanged.connect(
            self.update_static_pointing_parameters_values
        )
        # NB: The order of the following two lists MUST match the order of the
        # Pointing.StaticPmSetup command's arguments
        self.static_pointing_values: list[QtWidgets.QLabel] = [
            self.opcua_ia,  # type: ignore
            self.opcua_ca,  # type: ignore
            self.opcua_npae,  # type: ignore
            self.opcua_an,  # type: ignore
            self.opcua_an0,  # type: ignore
            self.opcua_aw,  # type: ignore
            self.opcua_aw0,  # type: ignore
            self.opcua_acec,  # type: ignore
            self.opcua_aces,  # type: ignore
            self.opcua_aba,  # type: ignore
            self.opcua_abphi,  # type: ignore
            self.opcua_ie,  # type: ignore
            self.opcua_ecec,  # type: ignore
            self.opcua_eces,  # type: ignore
            self.opcua_hece4,  # type: ignore
            self.opcua_hese4,  # type: ignore
            self.opcua_hece8,  # type: ignore
            self.opcua_hese8,  # type: ignore
        ]
        self.static_pointing_spinboxes: list[LimitedDisplaySpinBox] = [
            self.spinbox_ia,  # type: ignore
            self.spinbox_ca,  # type: ignore
            self.spinbox_npae,  # type: ignore
            self.spinbox_an,  # type: ignore
            self.spinbox_an0,  # type: ignore
            self.spinbox_aw,  # type: ignore
            self.spinbox_aw0,  # type: ignore
            self.spinbox_acec,  # type: ignore
            self.spinbox_aces,  # type: ignore
            self.spinbox_aba,  # type: ignore
            self.spinbox_abphi,  # type: ignore
            self.spinbox_ie,  # type: ignore
            self.spinbox_ecec,  # type: ignore
            self.spinbox_eces,  # type: ignore
            self.spinbox_hece4,  # type: ignore
            self.spinbox_hese4,  # type: ignore
            self.spinbox_hece8,  # type: ignore
            self.spinbox_hese8,  # type: ignore
        ]
        self.opcua_offset_xelev: QtWidgets.QLabel
        self.opcua_offset_elev: QtWidgets.QLabel
        self.spinbox_offset_xelev: LimitedDisplaySpinBox
        self.spinbox_offset_elev: LimitedDisplaySpinBox
        self.button_static_offset_apply: QtWidgets.QPushButton
        self.button_static_offset_apply.clicked.connect(
            self.apply_static_pointing_offsets
        )
        self._update_static_pointing_inputs_text = False
        # Point tab tilt correction widgets
        self.button_tilt_correction_toggle: ToggleSwitch
        self.button_tilt_correction_toggle.clicked.connect(
            self.pointing_correction_setup_button_clicked
        )
        self.button_tilt_correction_meter_toggle: ToggleSwitch
        self.button_tilt_correction_meter_toggle.label_false = "TM1"
        self.button_tilt_correction_meter_toggle.label_true = "TM2"
        self.button_tilt_correction_meter_toggle.change_color = False
        self.button_tilt_correction_meter_toggle.clicked.connect(
            self.update_tilt_meter_calibration_parameters_values
        )
        self.button_tilt_meter_cal_apply: QtWidgets.QPushButton
        self.button_tilt_meter_cal_apply.clicked.connect(
            self.apply_tilt_meter_calibration_parameters
        )
        self.tilt_meter_cal_values: list[QtWidgets.QLabel] = [
            self.opcua_x_filt_dt,  # type: ignore
            self.opcua_y_filt_dt,  # type: ignore
        ]
        self.tilt_meter_cal_spinboxes: list[LimitedDisplaySpinBox] = [
            self.spinbox_x_filt_dt,  # type: ignore
            self.spinbox_y_filt_dt,  # type: ignore
        ]
        self.tilt_meter_cal_inputs: list[LimitedDisplaySpinBox | str] = [
            "Pointing.TiltmeterParameters.[OneTwo].Tiltmeter_serial_no",
            "Pointing.TiltmeterParameters.[OneTwo].tilt_temp_scale",
            self.spinbox_x_filt_dt,  # type: ignore
            "Pointing.TiltmeterParameters.[OneTwo].x_off",
            "Pointing.TiltmeterParameters.[OneTwo].x_offTC",
            "Pointing.TiltmeterParameters.[OneTwo].x_scale",
            "Pointing.TiltmeterParameters.[OneTwo].x_scaleTC",
            "Pointing.TiltmeterParameters.[OneTwo].x_zero",
            "Pointing.TiltmeterParameters.[OneTwo].x_zeroTC",
            self.spinbox_y_filt_dt,  # type: ignore
            "Pointing.TiltmeterParameters.[OneTwo].y_off",
            "Pointing.TiltmeterParameters.[OneTwo].y_offTC",
            "Pointing.TiltmeterParameters.[OneTwo].y_scale",
            "Pointing.TiltmeterParameters.[OneTwo].y_scaleTC",
            "Pointing.TiltmeterParameters.[OneTwo].y_zero",
            "Pointing.TiltmeterParameters.[OneTwo].y_zeroTC",
        ]
        # Point tab ambient temperature correction widgets
        self.button_temp_correction_toggle: ToggleSwitch
        self.button_temp_correction_toggle.clicked.connect(
            self.pointing_correction_setup_button_clicked
        )
        self.button_temp_correction_apply: QtWidgets.QPushButton
        self.button_temp_correction_apply.clicked.connect(
            self.apply_ambtemp_correction_parameters
        )
        self.ambtemp_correction_values: list[QtWidgets.QLabel] = [
            self.opcua_ambtempfiltdt,  # type: ignore
            self.opcua_ambtempparam1,  # type: ignore
            self.opcua_ambtempparam2,  # type: ignore
            self.opcua_ambtempparam3,  # type: ignore
            self.opcua_ambtempparam4,  # type: ignore
            self.opcua_ambtempparam5,  # type: ignore
            self.opcua_ambtempparam6,  # type: ignore
        ]
        self.ambtemp_correction_spinboxes: list[LimitedDisplaySpinBox] = [
            self.spinbox_ambtempfiltdt,  # type: ignore
            self.spinbox_ambtempparam1,  # type: ignore
            self.spinbox_ambtempparam2,  # type: ignore
            self.spinbox_ambtempparam3,  # type: ignore
            self.spinbox_ambtempparam4,  # type: ignore
            self.spinbox_ambtempparam5,  # type: ignore
            self.spinbox_ambtempparam6,  # type: ignore
        ]
        self._update_temp_correction_inputs_text = False
        # Bands group widgets
        self.button_band1: QtWidgets.QPushButton
        self.button_band1.clicked.connect(
            lambda: self.move2band_button_clicked("Band_1")
        )
        self.button_band2: QtWidgets.QPushButton
        self.button_band2.clicked.connect(
            lambda: self.move2band_button_clicked("Band_2")
        )
        self.button_band3: QtWidgets.QPushButton
        self.button_band3.clicked.connect(
            lambda: self.move2band_button_clicked("Band_3")
        )
        self.button_band4: QtWidgets.QPushButton
        self.button_band4.clicked.connect(
            lambda: self.move2band_button_clicked("Band_4")
        )
        self.button_band5a: QtWidgets.QPushButton
        self.button_band5a.clicked.connect(
            lambda: self.move2band_button_clicked("Band_5a")
        )
        self.button_band5b: QtWidgets.QPushButton
        self.button_band5b.clicked.connect(
            lambda: self.move2band_button_clicked("Band_5b")
        )
        self.button_band6: QtWidgets.QPushButton
        self.button_band6.clicked.connect(
            lambda: self.move2band_button_clicked("Band_6")
        )
        self.button_band_optical: QtWidgets.QPushButton
        self.button_band_optical.clicked.connect(
            lambda: self.move2band_button_clicked("Optical")
        )
        self._disable_opcua_widgets()
        # Recording group widgets
        self.button_select_recording_file: QtWidgets.QPushButton
        self.button_select_recording_file.clicked.connect(
            self.recording_file_button_clicked
        )
        self.line_edit_recording_file: QtWidgets.QLineEdit
        self.button_recording_overwrite_no: QtWidgets.QRadioButton
        self.button_recording_overwrite_no.setChecked(True)
        self.button_recording_config: QtWidgets.QPushButton
        self.button_recording_config.clicked.connect(
            self.recording_config_button_clicked
        )
        self.button_recording_start: QtWidgets.QPushButton
        self.button_recording_start.clicked.connect(self.recording_start_clicked)
        self.button_recording_stop: QtWidgets.QPushButton
        self.button_recording_stop.clicked.connect(self.controller.recording_stop)
        self.button_recording_stop.setEnabled(False)
        self.line_edit_recording_status: QtWidgets.QLineEdit
        self.controller.recording_status.connect(self.recording_status_update)
        self.recording_start_success = False

        # Track tab load widgets
        self.button_select_track_table_file: QtWidgets.QPushButton
        self.button_select_track_table_file.clicked.connect(
            self.track_table_file_button_clicked
        )
        self.line_edit_track_table_file: QtWidgets.QLineEdit
        self.line_edit_track_table_file.textChanged.connect(
            self.track_table_file_changed
        )
        self.button_file_track_absolute_times: QtWidgets.QRadioButton
        self.button_file_track_absolute_times.setChecked(False)
        self.button_file_track_relative_times: QtWidgets.QRadioButton
        self.button_file_track_relative_times.toggled.connect(
            self.button_file_track_relative_times_toggled
        )
        self.button_file_track_relative_times.setChecked(True)
        self.spinbox_file_track_additional_offset: QtWidgets.QDoubleSpinBox
        self.spinbox_file_track_additional_offset.setEnabled(False)
        self.combobox_file_track_mode: QtWidgets.QComboBox
        self.button_load_track_table: QtWidgets.QPushButton
        self.button_load_track_table.clicked.connect(self.load_track_table_clicked)

        # Track tab start widgets
        self.combobox_track_start_interpol_type: QtWidgets.QComboBox
        self.button_start_track_now: QtWidgets.QRadioButton
        self.button_start_track_now.setChecked(True)
        self.button_start_track_at: QtWidgets.QRadioButton
        self.button_start_track_at.toggled.connect(self.button_start_track_at_toggled)
        self.button_start_track_at.setChecked(False)
        self.line_edit_start_track_at: QtWidgets.QLineEdit
        self.line_edit_start_track_at.setEnabled(False)
        self.button_start_track_table: QtWidgets.QPushButton
        self.button_start_track_table.clicked.connect(self.start_tracking_clicked)

        # Track tab time widgets
        self.button_set_time_source: QtWidgets.QPushButton
        self.button_set_time_source.clicked.connect(self.set_time_source_clicked)
        self.combobox_time_source: QtWidgets.QComboBox
        self.line_edit_ntp_source_addr: QtWidgets.QLineEdit

        # Warning and Error tabs
        self.warning_tree_view: QtWidgets.QTreeWidget
        self.warning_status_show_only_warnings: QtWidgets.QCheckBox
        self.error_tree_view: QtWidgets.QTreeWidget
        self.error_status_show_only_errors: QtWidgets.QCheckBox
        self._status_widget_update_lut: dict[str, QtWidgets.QTreeWidgetItem] = {}
        self._status_group_update_lut: dict[
            tuple[StatusTreeCategory, str], QtWidgets.QTreeWidgetItem
        ] = {}
        self.model.status_attribute_update.connect(self._status_attribute_event_handler)
        self.model.status_group_update.connect(self._status_group_event_handler)
        self.model.status_global_update.connect(self._status_global_event_handler)
        self.warning_error_filter: bool = False
        self.warning_status_show_only_warnings.stateChanged.connect(
            self.warning_status_show_only_warnings_clicked
        )
        self.error_status_show_only_errors.stateChanged.connect(
            self.warning_status_show_only_warnings_clicked
        )

    @cached_property
    def opcua_widgets(
        self,
    ) -> dict[str, tuple[list[QtWidgets.QWidget], Callable]]:
        """
        A dict of of all 'opcua' widgets and their update method.

        A widget on the UI is defined as an 'opcua' widget if it has a dynamic property
        named 'opcua'. Only widgets of types `QLineEdit`, `QLabel` and `QRadioButton`
        are supported. The value of this property is the dot-notated OPC-UA parameter.

        This is a cached property, meaning the function will only run once, scanning
        the UI for 'opcua widgets' and subsequent calls will return the cached result.

        :return: {name: (list of widgets, update function)}
        """
        all_widgets = (
            self.findChildren(QtWidgets.QLineEdit)
            + self.findChildren(QtWidgets.QLabel)
            + self.findChildren(ToggleSwitch)
            + self.findChildren(QtWidgets.QDoubleSpinBox)
        )
        opcua_widget_updates: dict[str, tuple[list[QtWidgets.QWidget], Callable]] = {}
        for wgt in all_widgets:
            if "opcua" not in wgt.dynamicPropertyNames():
                # Skip all the non-opcua widgets
                continue
            if "opcua_array" in wgt.dynamicPropertyNames():
                continue

            opcua_parameter_name: str = wgt.property("opcua")
            # the default update callback
            opcua_widget_update_func: Callable = self._update_opcua_text_widget
            logger.debug("OPCUA widget: %s", opcua_parameter_name)

            if "opcua_type" in wgt.dynamicPropertyNames():
                opcua_type = wgt.property("opcua_type")
                if opcua_type == "Boolean":
                    if isinstance(wgt, ToggleSwitch):
                        opcua_widget_update_func = (
                            self._update_opcua_boolean_toggle_switch_widget
                        )
                    else:
                        opcua_widget_update_func = (
                            self._update_opcua_boolean_text_widget
                        )
                else:
                    opcua_widget_update_func = self._update_opcua_enum_widget
                logger.debug("OPCUA widget type: %s", opcua_type)

            # Return the list from the tuple or an empty list as default. This is for
            # updating multiple widgets with the same opcua attribute's value
            widgets: list = opcua_widget_updates.get(opcua_parameter_name, [[]])[0]
            widgets.append(wgt)
            opcua_widget_updates.update(
                {opcua_parameter_name: (widgets, opcua_widget_update_func)}
            )
        # dict with (key, value) where the key is the name of the "opcua" widget
        # property (dot-notated OPC-UA parameter name) and the value is a tuple with
        # a list of widgets (mostly single) and callback method to update the widget(s)
        return opcua_widget_updates

    @cached_property
    def all_opcua_widgets(self) -> list[QtWidgets.QWidget]:
        """
        Return a list of all OPC UA widgets.

        This function finds all interactive widgets that have a dynamic property that
        starts with 'opcua'.

        This is a cached property, meaning the function will only run once and
        subsequent calls will return the cached result.

        :return: List of OPC UA widgets.
        """
        all_widgets = self.findChildren(
            (
                QtWidgets.QLineEdit,
                QtWidgets.QPushButton,
                QtWidgets.QRadioButton,
                QtWidgets.QComboBox,
                QtWidgets.QDoubleSpinBox,
                QtWidgets.QLabel,
            )
        )
        all_opcua_widgets: list[QtWidgets.QWidget] = []
        for wgt in all_widgets:
            property_names: list[QtCore.QByteArray] = wgt.dynamicPropertyNames()
            for property_name in property_names:
                if property_name.startsWith(QtCore.QByteArray("opcua".encode())):
                    all_opcua_widgets.append(wgt)  # type: ignore
                    break
        return all_opcua_widgets

    def _enable_opcua_widgets(self):
        """
        Enable all the OPC-UA widgets.

        By default the widgets should always start up in the disabled state.
        """
        for widget in self.all_opcua_widgets:
            widget.setEnabled(True)

    def _disable_opcua_widgets(self):
        """Disable all the OPC-UA widgets."""
        for widget in self.all_opcua_widgets:
            widget.setEnabled(False)
            if isinstance(widget, QtWidgets.QLineEdit):
                widget.setStyleSheet("QLineEdit { border-color: white;} ")

    def _enable_data_logger_widgets(self, enable: bool = True) -> None:
        """
        Enable or disable data logger widgets.

        :param enable: Whether to enable or disable the widgets. Default is True.
        """
        self.button_recording_start.setEnabled(enable)
        self.line_edit_recording_file.setEnabled(enable)
        self.line_edit_recording_status.setEnabled(enable)
        self.button_recording_config.setEnabled(enable)

    def recording_status_update(self, status: bool) -> None:
        """Update the recording status."""
        if status:
            self.line_edit_recording_status.setText("Recording")
            self.line_edit_recording_status.setStyleSheet(
                "background-color: rgb(10, 250, 0);"
            )
            self.button_recording_start.setEnabled(False)
            self.button_recording_stop.setEnabled(True)
            self.button_recording_config.setEnabled(False)
        else:
            self.line_edit_recording_status.setText("Stopped")
            self.line_edit_recording_status.setStyleSheet(
                "background-color: rgb(10, 80, 0);"
            )
            self.button_recording_start.setEnabled(True)
            self.button_recording_stop.setEnabled(False)
            self.button_recording_config.setEnabled(True)

    def event_update(self, event: dict) -> None:
        """
        Update the view with event data.

        :param event: A dictionary containing event data.
        """
        logger.debug("View: data update: %s value=%s", event["name"], event["value"])
        # Get the widget update method from the dict of opcua widgets
        widgets = self.opcua_widgets[event["name"]][0]
        self._update_opcua_widget_tooltip(widgets, event)
        widget_update_func = self.opcua_widgets[event["name"]][1]
        widget_update_func(widgets, event)

    def _update_opcua_widget_tooltip(
        self, widgets: list[QtWidgets.QWidget], opcua_event: dict
    ) -> None:
        """Update the tooltip of the OPCUA widget."""
        str_val = str(opcua_event["value"])
        if "opcua_type" in widgets[0].dynamicPropertyNames():
            opcua_type = widgets[0].property("opcua_type")
            if opcua_type in self.model.opcua_enum_types and str_val != "None":
                opcua_enum: type = self.model.opcua_enum_types[opcua_type]
                enum_val: Enum = opcua_enum(int(str_val))
                str_val = enum_val.name
        tooltip = (
            f"<b>OPCUA param:</b> {opcua_event['name']}<br>" f"<b>Value:</b> {str_val}"
        )
        for widget in widgets:
            if isinstance(widget, QtWidgets.QDoubleSpinBox):
                widget.setToolTip(
                    tooltip + f"<br><b>Maximum:</b> {widget.maximum()}"
                    f"<br><b>Minimum:</b> {widget.minimum()}"
                )
            else:
                widget.setToolTip(tooltip)

    def _init_opcua_combo_widgets(self) -> None:
        """Initialise all the OPC-UA combo widgets."""
        for widget in self.findChildren(QtWidgets.QComboBox):
            if "opcua_type" not in widget.dynamicPropertyNames():
                # Skip all the non-opcua widgets
                continue
            opcua_type = str(widget.property("opcua_type"))
            if opcua_type in self.model.opcua_enum_types:
                opcua_enum = self.model.opcua_enum_types[opcua_type]
                enum_strings = [str(e.name) for e in opcua_enum]
                # Explicitly cast to QComboBox
                wgt: QtWidgets.QComboBox = widget  # type: ignore
                wgt.clear()
                wgt.addItems(enum_strings)

    def _update_opcua_text_widget(
        self,
        widgets: list[
            QtWidgets.QLineEdit | QtWidgets.QDoubleSpinBox | QtWidgets.QLabel
        ],
        event: dict,
    ) -> None:
        """
        Update the text of the widget with the event value.

        The event update dict contains:
        { 'name': name, 'node': node, 'value': value,
        'source_timestamp': source_timestamp, 'server_timestamp': server_timestamp,
        'data': data }
        """
        val = event["value"]
        if isinstance(val, float):
            str_val = QtCore.QLocale().toString(val, "f", DISPLAY_DECIMAL_PLACES)
        else:
            str_val = str(val)
        for widget in widgets:
            if isinstance(widget, (QtWidgets.QLineEdit, QtWidgets.QLabel)):
                widget.setText(str_val)
            elif isinstance(widget, QtWidgets.QDoubleSpinBox) and val is not None:
                widget.setValue(val)

    def _update_opcua_enum_widget(
        self, widgets: list[QtWidgets.QLineEdit], event: dict
    ) -> None:
        """
        Update the text of the widget with the event data.

        The Event data is an OPC-UA Enum type. The value arrives as an integer and
        it is converted to a string here before updating the text of the widget.

        If the OPC UA type name is found in the `_LED_COLOURS` dict, then the background
        colour of the widget is set accordingly.

        The event update dict contains:
        - name: name
        - node: node
        - value: value
        - source_timestamp: source_timestamp
        - server_timestamp: server_timestamp
        - data: data
        """
        if event["value"] is None:
            for widget in widgets:
                widget.setEnabled(False)
                widget.setStyleSheet("QLineEdit { border-color: white;} ")

            return

        opcua_type: str = widgets[0].property("opcua_type")
        int_val = int(event["value"])
        try:
            opcua_enum: type = self.model.opcua_enum_types[opcua_type]
        except KeyError:
            logger.warning(
                "OPC-UA Enum type '%s' not found. Using integer value instead.",
                opcua_type,
            )
            str_val: str = str(int_val)
        else:
            val: Enum = opcua_enum(int_val)
            str_val = val.name
        finally:
            for widget in widgets:
                widget.setText(str_val)

        if opcua_type in self._LED_COLOURS:
            try:
                led_colour = self._LED_COLOURS[opcua_type][str_val.lower()]
                for widget in widgets:
                    widget.setStyleSheet(
                        "QLineEdit {"
                        f"background-color: {led_colour};"
                        "border-color: black;} "
                    )
            except KeyError:
                logger.warning(
                    "Enum value '%s' for opcua type '%s' not found in LED colours dict",
                    str_val.lower(),
                    opcua_type,
                )

        # Populate input boxes with current read values after connecting to server
        if event["name"] == BAND_FOR_CORR:
            if self._update_static_pointing_inputs_text:
                self._update_static_pointing_inputs_text = False
                self._set_static_pointing_inputs_text()

    def _update_opcua_boolean_toggle_switch_widget(
        self, buttons: list[QtWidgets.QPushButton], event: dict
    ) -> None:
        """Set toggle switch based on its boolean OPC-UA parameter."""
        # There should only be one toggle button connected to an OPC-UA parameter.
        button = buttons[0]
        logger.debug(
            "Widget: %s. Boolean OPCUA update: %s value=%s",
            button.objectName(),
            event["name"],
            event["value"],
        )
        if event["value"] is None:
            return

        # Block or unblock tilt meter selection signal whether function is active and
        # populate input boxes with current read values after connecting to server
        if event["name"] == TILT_METER_TWO_ON:
            # The tilt meter button is only toggled when tilt correction is active
            if self.model.opcua_attributes[TILT_CORR_ACTIVE].value:
                button.setChecked(event["value"])
            self.update_tilt_meter_calibration_parameters_values()
            return
        if event["name"] == TILT_CORR_ACTIVE:
            if event["value"]:
                self.button_tilt_correction_meter_toggle.clicked.connect(
                    self.pointing_correction_setup_button_clicked
                )
            else:
                try:
                    self.button_tilt_correction_meter_toggle.clicked.disconnect(
                        self.pointing_correction_setup_button_clicked
                    )
                except TypeError:
                    pass
        elif event["name"] == TEMP_CORR_ACTIVE:
            if self._update_temp_correction_inputs_text:
                self._update_temp_correction_inputs_text = False
                self._set_temp_correction_inputs_text()
        button.setChecked(event["value"])

    def _update_opcua_boolean_text_widget(
        self, widgets: list[QtWidgets.QLineEdit], event: dict
    ) -> None:
        """
        Update background colour of widget to reflect boolean state of OPC-UA parameter.

        The event update 'value' field can take 3 states:
         - None: the OPC-UA parameter is not initialised yet. Colour background grey.
         - True: the OPC-UA parameter is True. Colour background light green (LED on).
         - False: the OPC-UA parameter is False. Colour background dark green (LED off).
        """
        logger.debug("Boolean OPCUA update: %s value=%s", event["name"], event["value"])
        for widget in widgets:
            if event["value"] is None:
                widget.setEnabled(False)
                widget.setStyleSheet("QLineEdit { border-color: white;} ")
            else:
                led_base_colour = "green"  # default colour
                if "led_colour" in widget.dynamicPropertyNames():
                    led_base_colour = widget.property("led_colour")
                try:
                    background_colour_rbg: str = self._LED_COLOURS[led_base_colour][
                        event["value"]
                    ]
                    text_color = "black" if event["value"] else "white"
                except KeyError:
                    logger.warning(
                        "LED colour for base colour '%s' and value '%s' not found",
                        led_base_colour,
                        event["value"],
                    )
                    return
                widget.setEnabled(True)
                widget.setStyleSheet(
                    "QLineEdit { "
                    f"background-color: {background_colour_rbg}; color: {text_color}; "
                    "border-color: black;} "
                )

    def _track_table_file_exist(self) -> bool:
        """Check if the track table file exists."""
        tt_filename = Path(self.line_edit_track_table_file.text())
        return tt_filename.exists()

    def server_connected_event(self):
        """
        Handle the server connected event.

        This function is called when the server is successfully connected.
        """
        logger.debug("server connected event")
        self._update_static_pointing_inputs_text = True
        self._update_temp_correction_inputs_text = True
        self.label_conn_status.setText("Status: Subscribing to OPC-UA updates...")
        self.controller.subscribe_opcua_updates(list(self.opcua_widgets.keys()))
        self.label_conn_status.setText(
            f"Connected to {self.model.get_server_uri()} - "
            f"Version {self.model.server_version}"
        )
        self.label_cache_status.setText(
            f"{self.model.opcua_nodes_status.value} - "
            f"Nodes generated {self.model.plc_prg_nodes_timestamp}"
        )
        self.action_connect_opcua_server.setEnabled(False)
        self.action_disconnect_opcua_server.setEnabled(True)
        self._enable_opcua_widgets()
        self._enable_data_logger_widgets(True)
        self._init_opcua_combo_widgets()
        if self._track_table_file_exist():
            self.button_load_track_table.setEnabled(True)
        self._initialise_error_warning_widgets()
        self.warning_status_show_only_warnings.setEnabled(True)
        self.error_status_show_only_errors.setEnabled(True)
        self.spinbox_file_track_additional_offset.setEnabled(
            not self.button_file_track_absolute_times.isChecked()
        )
        self.update_tilt_meter_calibration_parameters_values()

    def server_disconnected_event(self):
        """Handle the server disconnected event."""
        logger.debug("server disconnected event")
        self._disable_opcua_widgets()
        self._enable_data_logger_widgets(False)
        self.label_conn_status.setText("Disconnected")
        self.label_cache_status.setText("")
        self.action_connect_opcua_server.setEnabled(True)
        self.action_disconnect_opcua_server.setEnabled(False)
        self.button_load_track_table.setEnabled(False)
        self.line_edit_track_table_file.setEnabled(False)
        self.warning_status_show_only_warnings.setEnabled(False)
        self.warning_tree_view.setEnabled(False)
        self.error_status_show_only_errors.setEnabled(False)
        self.error_tree_view.setEnabled(False)

    def connect_button_clicked(self):
        """Open the Connect To Server configuration dialog."""
        if not self.controller.is_server_connected():
            dialog = ServerConnectDialog(self, self.controller)
            if dialog.exec():
                logger.debug("Connection configuration dialog accepted")
                logger.debug("Selected: %s", dialog.server_details)
                self.server_connect(
                    dialog.server_details, dialog.server_config_selected
                )
            else:
                logger.debug("Connection config dialog cancelled")
        else:
            logger.debug("disconnecting from server")
            self.controller.disconnect_server()

    def server_connect(
        self, connect_details: dict[str, Any], server_config_selected: str
    ) -> None:
        """Setup a connection to the server."""
        config_connection_details = self.controller.get_config_server_args(
            server_config_selected
        )
        if config_connection_details is not None:
            connect_details["username"] = config_connection_details.get(
                "username", None
            )
            connect_details["password"] = config_connection_details.get(
                "password", None
            )
        logger.debug("Connecting to server: %s", connect_details)
        self.label_conn_status.setText("Connecting... please wait")
        self.controller.connect_server(connect_details)

    def track_table_file_changed(self):
        """Update the track table file path in the model."""
        if self._track_table_file_exist() and self.controller.is_server_connected():
            self.button_load_track_table.setEnabled(True)
        else:
            self.button_load_track_table.setEnabled(False)

    def track_table_file_button_clicked(self) -> None:
        """Open a file dialog to select a track table file."""
        options = QFileDialog.Option(QFileDialog.Option.ReadOnly)
        filename, _ = QFileDialog.getOpenFileName(
            parent=self,
            caption="Open Track Table File",
            directory=user_documents_dir(),
            filter="Track Table Files (*.csv);;All Files (*)",
            options=options,
        )
        if filename:
            self.line_edit_track_table_file.setText(filename)

    def button_file_track_relative_times_toggled(self, checked: bool) -> None:
        """Only enable the additional offset box when file times are relative."""
        self.spinbox_file_track_additional_offset.setEnabled(checked)

    def load_track_table_clicked(self):
        """Call the TrackLoadTable command."""
        self.controller.load_track_table(
            self.line_edit_track_table_file.text(),
            self.combobox_file_track_mode.currentText(),
            self.button_file_track_absolute_times.isChecked(),
            self.spinbox_file_track_additional_offset.value(),
        )

    def button_start_track_at_toggled(self, checked: bool) -> None:
        """Only enable the line edit when the At radio is checked."""
        self.line_edit_start_track_at.setEnabled(checked)

    def start_tracking_clicked(self):
        """Start the track table on the PLC."""
        self.controller.start_track_table(
            self.combobox_track_start_interpol_type.currentText(),
            self.button_start_track_now.isChecked(),
            self.line_edit_start_track_at.text(),
        )

    def set_time_source_clicked(self):
        """Set the time axis source of the PLC."""
        self.controller.command_set_time_source(
            self.combobox_time_source.currentText(),
            self.line_edit_ntp_source_addr.text(),
        )

    def recording_config_button_clicked(self):
        """Open the recording configuration dialog."""
        if not self.controller.recording_config:
            for node in self.model.opcua_attributes:
                self.controller.recording_config[node] = {
                    "record": False,
                    "period": 100,
                }

        dialog = RecordingConfigDialog(self, self.controller.recording_config)
        if dialog.exec():
            logger.debug("Recording config dialog accepted")
            logger.debug("Selected: %s", dialog.config_parameters)
            self.controller.recording_config = dialog.config_parameters
        else:
            logger.debug("Recording config dialog cancelled")

    def recording_start_clicked(self) -> None:
        """Start the data recording."""
        output_filename = self.controller.recording_start(
            self.line_edit_recording_file.text(),
            not self.button_recording_overwrite_no.isChecked(),
        )

        if self.line_edit_recording_file.text() == "":
            self.line_edit_recording_file.setText(output_filename.rsplit(".")[0])

    def recording_file_button_clicked(self) -> None:
        """Open a dialog to select a file for the recording file box."""
        fname, _ = QtWidgets.QFileDialog.getSaveFileName(
            parent=self,
            caption="Select Recording File",
            directory=user_documents_dir(),
            filter="DataLogger File (*.hdf5 *.h5);;All Files (*)",
        )
        if fname:
            self.line_edit_recording_file.setText(fname)

    def slew2abs_button_clicked(self):
        """
        Slew to absolute position.

        QT slot that gets called when the slew2abs button is clicked.

        Convert slew simulation position and velocity values to absolute position and
        velocity and send the command to the controller.

        This function extracts the values from the line edit widgets for azimuth and
        elevation position and velocity, converts them to float, and then calls the
        controller's command_slew2abs_azim_elev method with the converted arguments.

        :raises ValueError: If the input arguments cannot be converted to float.
        """
        args = [
            self.spinbox_slew_simul_azim_position.value(),
            self.spinbox_slew_simul_elev_position.value(),
            self.spinbox_slew_simul_azim_velocity.value(),
            self.spinbox_slew_simul_elev_velocity.value(),
        ]
        logger.debug("slew2abs args: %s", args)
        self.controller.command_slew2abs_azim_elev(*args)

    def slew_button_clicked(self, axis: str) -> None:
        """
        Slot function to handle the click event of a slew button.

        Also called for the up/down clicks of an axis' position spinbox.

        :param axis: The axis for which the slew operation is being performed.
        """
        match axis:
            case "El":
                args = [
                    self.spinbox_slew_only_elevation_position.value(),
                    self.spinbox_slew_only_elevation_velocity.value(),
                ]
            case "Az":
                args = [
                    self.spinbox_slew_only_azimuth_position.value(),
                    self.spinbox_slew_only_azimuth_velocity.value(),
                ]
            case "Fi":
                args = [
                    self.spinbox_slew_only_indexer_position.value(),
                    self.spinbox_slew_only_indexer_velocity.value(),
                ]
            case _:
                return
        if args is not None:
            logger.debug("args: %s", args)
            self.controller.command_slew_single_axis(axis, *args)
        return

    def set_axis_inputs_step_size(self, step_size: float) -> None:
        """
        Set the input spinbox step size of the axis slew commands.

        :param step: Step size to use.
        """
        self.spinbox_slew_only_azimuth_position.setSingleStep(step_size)
        self.spinbox_slew_only_azimuth_velocity.setSingleStep(step_size)
        self.spinbox_slew_only_elevation_position.setSingleStep(step_size)
        self.spinbox_slew_only_elevation_velocity.setSingleStep(step_size)
        self.spinbox_slew_only_indexer_position.setSingleStep(step_size)
        self.spinbox_slew_only_indexer_velocity.setSingleStep(step_size)
        self.spinbox_slew_simul_azim_position.setSingleStep(step_size)
        self.spinbox_slew_simul_azim_velocity.setSingleStep(step_size)
        self.spinbox_slew_simul_elev_position.setSingleStep(step_size)
        self.spinbox_slew_simul_elev_velocity.setSingleStep(step_size)

    def limit_axis_inputs_toggled(self) -> None:
        """Limit the input ranges of the axis slew commands as specified in the ICD."""
        if self.button_enable_axis_limits.isChecked():
            self.spinbox_slew_only_azimuth_position.setRange(AZ_POS_MIN, AZ_POS_MAX)
            self.spinbox_slew_only_azimuth_velocity.setMaximum(AZ_VEL_MAX)
            self.spinbox_slew_only_elevation_position.setRange(EL_POS_MIN, EL_POS_MAX)
            self.spinbox_slew_only_elevation_velocity.setMaximum(EL_VEL_MAX)
            self.spinbox_slew_only_indexer_position.setRange(FI_POS_MIN, FI_POS_MAX)
            self.spinbox_slew_only_indexer_velocity.setMaximum(FI_VEL_MAX)
            self.spinbox_slew_simul_azim_position.setRange(AZ_POS_MIN, AZ_POS_MAX)
            self.spinbox_slew_simul_azim_velocity.setMaximum(AZ_VEL_MAX)
            self.spinbox_slew_simul_elev_position.setRange(EL_POS_MIN, EL_POS_MAX)
            self.spinbox_slew_simul_elev_velocity.setMaximum(EL_VEL_MAX)
        else:
            default_max = 1000.0
            default_min = -1000.0
            self.spinbox_slew_only_azimuth_position.setRange(default_min, default_max)
            self.spinbox_slew_only_azimuth_velocity.setMaximum(default_max)
            self.spinbox_slew_only_elevation_position.setRange(default_min, default_max)
            self.spinbox_slew_only_elevation_velocity.setMaximum(default_max)
            self.spinbox_slew_only_indexer_position.setRange(default_min, default_max)
            self.spinbox_slew_only_indexer_velocity.setMaximum(default_max)
            self.spinbox_slew_simul_azim_position.setRange(default_min, default_max)
            self.spinbox_slew_simul_azim_velocity.setMaximum(default_max)
            self.spinbox_slew_simul_elev_position.setRange(default_min, default_max)
            self.spinbox_slew_simul_elev_velocity.setMaximum(default_max)

    def stop_button_clicked(self, axis: str) -> None:
        """
        Handle the signal emitted when the stop button is clicked.

        :param axis: The axis on which to stop the movement.
        """
        self.controller.command_stop(axis)

    def stow_button_clicked(self):
        """Handle the click event of the stow button."""
        self.controller.command_stow()

    def unstow_button_clicked(self):
        """
        Unstow button clicked callback function.

        This function calls the controller's command_stow method with False as the
        argument.

        :param self: The object itself.
        """
        self.controller.command_stow(False)

    def activate_button_clicked(self, axis: str) -> None:
        """
        Activate the button clicked for a specific axis.

        :param axis: The axis for which the button was clicked.
        """
        self.controller.command_activate(axis)

    def deactivate_button_clicked(self, axis: str) -> None:
        """
        Deactivate button clicked slot function.

        :param axis: Axis identifier for deactivation.
        """
        self.controller.command_deactivate(axis)

    def reset_button_clicked(self, axis: str) -> None:
        """Clear latched errors for the axis/axes in the servo amplifiers."""
        logger.debug("reset_axis args: %s", axis)
        self.controller.command_reset_axis(axis)

    def take_authority_button_clicked(self):
        """Handle the click event of the take authority button."""
        username = self.combobox_authority.currentText()
        self.controller.command_take_authority(username)

    def release_authority_button_clicked(self):
        """Handle the click event of the release authority button."""
        self.controller.command_release_authority()

    def command_response_status_update(self, status: str) -> None:
        """Update the main window status bar with a status update."""
        self.status_bar_update(status)
        history_line: str = (
            f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} - {status}"
        )
        self.list_cmd_history.addItem(history_line)
        self.list_cmd_history.scrollToBottom()

    def move2band_button_clicked(self, band: str) -> None:
        """Move to the given band."""
        self.controller.command_move2band(band)

    def import_static_pointing_model(self) -> None:
        """Open a dialog to import a static pointing model JSON file."""
        options = QFileDialog.Option(QFileDialog.Option.ReadOnly)
        filename, _ = QFileDialog.getOpenFileName(
            parent=self,
            caption="Import Static Pointing Model from JSON",
            directory=user_documents_dir(),
            filter="JSON Files (*.json);;All Files (*)",
            options=options,
        )
        if filename:
            band = self.model.import_static_pointing_model(Path(filename))
            if band is not None:
                # pylint: disable=protected-access
                band_index = self.model._scu.convert_enum_to_int("BandType", band)
                self.combo_static_point_model_band_input.setCurrentIndex(band_index)
                for spinbox in self.static_pointing_spinboxes:
                    attr_name = (
                        spinbox.property("opcua_array").split(".")[-1]
                        if spinbox.property("opcua_array") is not None
                        else None
                    )
                    if attr_name is not None:
                        spinbox.setValue(
                            self.model.get_static_pointing_value(band, attr_name)
                        )
                self.controller.emit_ui_status_message(
                    "INFO",
                    f"Successfully imported static pointing model for '{band}' from "
                    f"'{filename}'",
                )

    def export_static_pointing_model(self) -> None:
        """Open a dialog to export a static pointing model JSON file."""
        band = self.combo_static_point_model_band_display.currentText()
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            parent=self,
            caption=f"Export '{band}' model to JSON",
            directory=f"{user_documents_dir()}/gpm-SKA000-{band}.json",
            filter="JSON Files (*.json);;All Files (*)",
        )
        if filename:
            try:
                self.model.read_static_pointing_model(band)
                self.model.export_static_pointing_model(
                    band, Path(filename), overwrite=True
                )
                self.controller.emit_ui_status_message(
                    "INFO",
                    f"Successfully exported static pointing model for '{band}' to "
                    f"'{filename}'",
                )
            except TypeError as e:
                self.controller.emit_ui_status_message(
                    "ERROR",
                    f"Export of static pointing model for '{band}' failed: {e}",
                )

    def apply_static_pointing_parameters(self):
        """Apply input static pointing model parameters slot function."""
        input_band = self.combo_static_point_model_band_input.currentText()
        params = []
        for spinbox in self.static_pointing_spinboxes:
            params.append(spinbox.value())
        if self.static_point_model_band.text() != input_band:
            self.pointing_correction_setup_button_clicked()
        self.controller.command_set_static_pointing_parameters(input_band, params)
        self.update_static_pointing_parameters_values()

    def apply_static_pointing_offsets(self):
        """Apply static pointing offsets slot function."""
        xelev = self.spinbox_offset_xelev.value()
        elev = self.spinbox_offset_elev.value()
        self.controller.command_set_static_pointing_offsets(xelev, elev)

    def apply_tilt_meter_calibration_parameters(self):
        """Apply tilt meter calibration parameters slot function."""
        params = []
        for var in self.tilt_meter_cal_inputs:
            if isinstance(var, str):
                attr_name = var.replace(
                    "[OneTwo]",
                    (
                        "One"
                        if not self.button_tilt_correction_meter_toggle.isChecked()
                        else "Two"
                    ),
                )
                if attr_name in self.model.opcua_attributes:
                    params.append(self.model.opcua_attributes[attr_name].value)
                else:
                    self.controller.emit_ui_status_message(
                        "ERROR",
                        f"Cannot set tilt meter x/y-filter constants, as '{attr_name}' "
                        "attribute not found on DSC!",
                    )
                    return
            else:
                params.append(var.value())
        tilt_meter = (
            "TiltmeterOne"
            if not self.button_tilt_correction_meter_toggle.isChecked()
            else "TiltmeterTwo"
        )
        self.controller.command_set_tilt_meter_calibration_parameters(
            tilt_meter, params
        )
        self.update_tilt_meter_calibration_parameters_values()

    def apply_ambtemp_correction_parameters(self):
        """Apply ambient temperature correction parameters slot function."""
        params = []
        for spinbox in self.ambtemp_correction_spinboxes:
            params.append(spinbox.value())
        self.controller.command_set_ambtemp_correction_parameters(params)

    def set_power_mode_clicked(self):
        """Set dish power mode."""
        args = [
            self.button_power_mode_low.isChecked(),
            self.spinbox_power_lim_kw.value(),
        ]
        logger.debug("set_power_mode args: %s", args)
        self.controller.command_set_power_mode(*args)

    def pointing_model_band_selected_for_input(self):
        """Static pointing model band selected for input of parameters slot function."""
        band = self.combo_static_point_model_band_input.currentIndex()
        for spinbox in self.static_pointing_spinboxes:
            attr_name = (
                spinbox.property("opcua_array").replace("[x]", f"[{band}]")
                if spinbox.property("opcua_array") is not None
                else None
            )
            if attr_name in self.model.opcua_attributes:
                attr_value = self.model.opcua_attributes[attr_name].value
                if attr_value is not None:
                    spinbox.setValue(attr_value)
                spinbox.setToolTip(
                    f"<b>OPCUA param:</b> {attr_name}<br>"
                    f"<b>Maximum:</b> {spinbox.maximum()}<br>"
                    f"<b>Minimum:</b> {spinbox.minimum()}"
                )

    def update_static_pointing_parameters_values(self) -> None:
        """Update displayed static pointing parameters values from server."""
        band = self.combo_static_point_model_band_display.currentIndex()
        for label in self.static_pointing_values:
            attr_name = (
                label.property("opcua_array").replace("[x]", f"[{band}]")
                if label.property("opcua_array") is not None
                else None
            )
            if attr_name in self.model.opcua_attributes:
                attr_value = self.model.opcua_attributes[attr_name].value
                label.setText(
                    QtCore.QLocale().toString(attr_value, "f", DISPLAY_DECIMAL_PLACES)
                    if isinstance(attr_value, float)
                    else str(attr_value)
                )
                tooltip = (
                    f"<b>OPCUA param:</b> {attr_name}<br>"
                    f"<b>Value:</b> {str(attr_value)}"
                )
                label.setToolTip(tooltip)

    def update_tilt_meter_calibration_parameters_values(self) -> None:
        """Update displayed tilt meter's calibration parameters values from server."""
        meter = "Two" if self.button_tilt_correction_meter_toggle.isChecked() else "One"
        for i, label in enumerate(self.tilt_meter_cal_values):
            attr_name = (
                label.property("opcua_array").replace("[x]", f"{meter}")
                if label.property("opcua_array") is not None
                else None
            )
            if attr_name in self.model.opcua_attributes:
                attr_value = self.model.opcua_attributes[attr_name].value
                label.setText(
                    QtCore.QLocale().toString(attr_value, "f", DISPLAY_DECIMAL_PLACES)
                    if isinstance(attr_value, float)
                    else str(attr_value)
                )
                tooltip = (
                    f"<b>OPCUA param:</b> {attr_name}<br>"
                    f"<b>Value:</b> {str(attr_value)}"
                )
                label.setToolTip(tooltip)
                spinbox = self.tilt_meter_cal_spinboxes[i]
                if attr_value is not None:
                    spinbox.setValue(attr_value)
                spinbox.setToolTip(
                    f"<b>OPCUA param:</b> {attr_name}<br>"
                    f"<b>Maximum:</b> {spinbox.maximum()}<br>"
                    f"<b>Minimum:</b> {spinbox.minimum()}"
                )

    def pointing_correction_setup_button_clicked(self):
        """Any pointing model toggle button clicked slot function."""
        tilt_correction = (
            "Off"
            if not self.button_tilt_correction_toggle.isChecked()
            else (
                "TiltmeterOne"
                if not self.button_tilt_correction_meter_toggle.isChecked()
                else "TiltmeterTwo"
            )
        )
        # Send command and check result
        result_code, _ = self.controller.command_config_pointing_model_corrections(
            self.button_static_point_model_toggle.isChecked(),
            tilt_correction,
            self.button_temp_correction_toggle.isChecked(),
            self.combo_static_point_model_band_input.currentText(),
        )
        # If command did not succeed, toggle triggering button back to prev state
        if result_code not in [ResultCode.COMMAND_ACTIVATED, ResultCode.COMMAND_DONE]:
            sender = self.sender()
            if isinstance(sender, ToggleSwitch):
                sender.toggle()

    def _set_static_pointing_inputs_text(self) -> None:
        """Set static pointing inputs' text to current read values."""
        # Static pointing band
        current_band = self.static_point_model_band.text()
        if current_band != "not read":
            # pylint: disable=protected-access
            band_index = self.model._scu.convert_enum_to_int("BandType", current_band)
            if band_index is not None:
                self.combo_static_point_model_band_input.setCurrentIndex(band_index)
                self.combo_static_point_model_band_display.setCurrentIndex(band_index)
        # Static pointing offsets
        try:
            self.spinbox_offset_xelev.setValue(float(self.opcua_offset_xelev.text()))
            self.spinbox_offset_elev.setValue(float(self.opcua_offset_elev.text()))
        except ValueError:
            self.spinbox_offset_xelev.setValue(0)
            self.spinbox_offset_elev.setValue(0)
        # Static pointing parameters

    def _set_temp_correction_inputs_text(self) -> None:
        """Set ambient temperature correction inputs' text to current read values."""
        for spinbox, value in zip(
            self.ambtemp_correction_spinboxes, self.ambtemp_correction_values
        ):
            try:
                spinbox.setValue(float(value.text()))
            except ValueError:
                spinbox.setValue(0)

    def _configure_status_tree_widget(
        self,
        category: StatusTreeCategory,
        tree_widget: QtWidgets.QTreeWidget,
        status_attributes: dict[str, list[tuple[str, str, str]]],
    ) -> None:
        """Configure the status tree widget."""
        tree_widget.clear()
        tree_widget.setEnabled(True)
        tree_widget.setColumnCount(3)
        tree_widget.setHeaderLabels(["Group", "Status", "Time"])
        tree_widget.setColumnWidth(0, 180)  # Group
        tree_widget.setColumnWidth(1, 50)  # Status
        tree_widget.setColumnWidth(2, 180)  # Time
        # tree_widget.setColumnWidth(3, 400)  # Description - TODO: add description

        for group, status_list in status_attributes.items():
            parent = QtWidgets.QTreeWidgetItem([group])
            tree_widget.addTopLevelItem(parent)
            self._status_group_update_lut[(category, group)] = parent
            for attr_short_name, attr_value, attr_full_name in status_list:
                status_widget = QtWidgets.QTreeWidgetItem(
                    parent, [attr_short_name, attr_value, "", ""]
                )
                self._status_widget_update_lut[attr_full_name] = status_widget

    def _initialise_error_warning_widgets(self) -> None:
        """Initialise the error and warning widgets."""
        self._configure_status_tree_widget(
            StatusTreeCategory.WARNING,
            self.warning_tree_view,
            self.controller.get_warning_attributes(),
        )
        self._configure_status_tree_widget(
            StatusTreeCategory.ERROR,
            self.error_tree_view,
            self.controller.get_error_attributes(),
        )

    def _status_attribute_event_handler(
        self,
        attribute_full_name: str,
        attribute_value: str,
        attribute_update_time: datetime,
    ) -> None:
        tree_widget_item = self._status_widget_update_lut[attribute_full_name]
        tree_widget_item.setText(1, attribute_value)
        tree_widget_item.setText(2, str(attribute_update_time))
        if "true" in attribute_value.lower():
            tree_widget_item.setBackground(1, QColor("red"))
            tree_widget_item.setHidden(False)
        if "false" in attribute_value.lower():
            tree_widget_item.setBackground(1, QColor("green"))
            tree_widget_item.setHidden(self.warning_error_filter)
        history_line: str = (
            f"{str(attribute_update_time)} - {attribute_full_name}: {attribute_value}"
        )
        self.list_cmd_history.addItem(history_line)
        self.list_cmd_history.scrollToBottom()

    def _status_group_event_handler(
        self,
        category: StatusTreeCategory,
        group_name: str,
        group_value: bool,
    ) -> None:
        tree_widget_item = self._status_group_update_lut[(category, group_name)]
        tree_widget_item.setText(1, str(group_value))
        if group_value:
            tree_widget_item.setBackground(1, QColor("red"))
        else:
            tree_widget_item.setBackground(1, QColor("green"))

    def _status_global_event_handler(
        self, category: StatusTreeCategory, global_value: bool
    ) -> None:
        # Only updates warning status indicator, as error uses
        # Management.ErrorStatus.errGeneral
        if category == StatusTreeCategory.WARNING:
            status_indicator = self.line_edit_warning_general
            self._update_opcua_boolean_text_widget(
                [status_indicator],
                {"name": "global warning", "value": global_value},
            )

    def warning_status_show_only_warnings_clicked(self, checked: int) -> None:
        """Show only warnings checkbox clicked slot function."""
        self.warning_error_filter = False
        if checked == 2:
            self.warning_error_filter = True

        self.warning_status_show_only_warnings.setChecked(self.warning_error_filter)
        self.error_status_show_only_errors.setChecked(self.warning_error_filter)

        for _, widget in self._status_widget_update_lut.items():
            if self.warning_error_filter and "false" in widget.text(1).lower():
                widget.setHidden(True)
            else:
                widget.setHidden(False)

    def about_button_clicked(self) -> None:
        """Open the About dialog."""
        dialog = QtWidgets.QMessageBox(self)
        # dialog.setIcon(QtWidgets.QMessageBox.Icon.Information)
        dialog.setTextFormat(QtCore.Qt.TextFormat.RichText)
        source_code_url = "https://gitlab.com/ska-telescope/ska-mid-disq"
        dialog.setText(
            "<center><h2>SKA-Mid Dish Structure Qualification GUI</h2></center>"
            f"<p>Version: {__version__}</p>"
            "<p>This application is intended for expert engineers for the purpose of "
            "controlling, monitoring and qualifying the SKA-Mid Dish Structures.</p>"
            "<p>Lovingly crafted by SKAO Wombats under the stern supervision of SARAO "
            "Dish Structure Engineers.</p>"
            "<center><img src=':/images/skao_logo.svg' width='380'></center>"
            "<center><img src=':/images/NRF25_SARAO.png' width='368'></center>"
            "<center><img src=':/images/wombat_logo.png' width='200'></center>"
            f"<center><p><a href='{source_code_url}'>DiSQ GUI source code</a></p>"
            "</center>"
        )
        dialog.setWindowTitle("About")
        dialog.setWindowIcon(QIcon(SKAO_ICON_PATH))
        dialog.exec()

    def open_documentation(self) -> None:
        """Open the RTD website."""
        QDesktopServices.openUrl(
            QtCore.QUrl("https://developer.skao.int/projects/ska-mid-disq/en/latest/")
        )


class LimitedDisplaySpinBox(QtWidgets.QDoubleSpinBox):
    """Custom double (float) spin box that only limits the displayed decimal points."""

    def __init__(self, *args, decimals_to_display=DISPLAY_DECIMAL_PLACES, **kwargs):
        """Init LimitedDisplaySpinBox."""
        super().__init__(*args, **kwargs)
        self.decimals_to_display = decimals_to_display
        self.setSingleStep(10**-decimals_to_display)  # Set step to displayed precision

    # pylint: disable=invalid-name,
    def textFromValue(self, value):  # noqa: N802
        """Display the value with limited decimal points."""
        return QtCore.QLocale().toString(value, "f", self.decimals_to_display)

    # pylint: disable=invalid-name,
    def stepBy(self, steps):  # noqa: N802
        """Override stepBy to round the step value to the displayed decimals."""
        new_value = self.value() + steps * self.singleStep()
        rounded_value = round(new_value, self.decimals_to_display)
        self.setValue(rounded_value)


class ToggleSwitch(QtWidgets.QPushButton):
    """Custom sliding style toggle push button."""

    def __init__(self, parent: Any = None) -> None:
        """Init ToggleSwitch."""
        super().__init__(parent)
        self.setCheckable(True)
        self.setMinimumWidth(70)
        self.setMinimumHeight(22)
        self.label_true = "ON"
        self.label_false = "OFF"
        self.change_color = True

    # pylint: disable=invalid-name,unused-argument
    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
        """Override mouseReleaseEvent to disable visual state change on click."""
        self.setChecked(not self.isChecked())  # Toggle state manually
        self.clicked.emit()  # Emit clicked signal for external logic

    # pylint: disable=invalid-name,unused-argument
    def paintEvent(self, event: Any) -> None:  # noqa: N802
        """Paint event."""
        label = self.label_true if self.isChecked() else self.label_false
        radius = 9
        width = 34
        center = self.rect().center()
        painter = QPainter(self)
        palette = super().palette()
        button_color = palette.color(QPalette.ColorRole.Window)
        if self.isEnabled() and self.change_color:
            background_color = QColor("green") if self.isChecked() else QColor("red")
        else:
            background_color = button_color
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.translate(center)
        painter.setBrush(background_color)
        painter.setPen(QPen(palette.color(QPalette.ColorRole.Shadow), 1))
        painter.drawRoundedRect(
            QtCore.QRect(-width, -radius, 2 * width, 2 * radius), radius, radius
        )
        painter.setBrush(QBrush(button_color))
        sw_rect = QtCore.QRect(-radius, -radius, width + radius, 2 * radius)
        if not self.isChecked():
            sw_rect.moveLeft(-width)
        painter.drawRoundedRect(sw_rect, radius, radius)
        painter.setPen(QPen(palette.color(QPalette.ColorRole.WindowText), 1))
        painter.drawText(sw_rect, QtCore.Qt.AlignmentFlag.AlignCenter, label)
