# pylint: disable=too-many-lines
"""DiSQ GUI View."""

import json
import logging
import os
from datetime import datetime, timezone
from enum import Enum
from functools import cached_property
from importlib import resources
from pathlib import Path
from typing import Any, Callable, Final

from PyQt6 import QtCore, QtWidgets, uic
from PyQt6.QtGui import QColor

from ska_mid_disq import __version__, controller, model
from ska_mid_disq.constants import NodesStatus, StatusTreeCategory

logger = logging.getLogger("gui.view")

# Constant definitions of attribute names on the OPC-UA server
TILT_CORR_ACTIVE: Final = "Pointing.Status.TiltCorrActive"
STATIC_CORR_ACTIVE: Final = "Pointing.Status.StaticCorrActive"
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
        self.table_file_label = QtWidgets.QLabel("Table file:")
        self.table_file_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignCenter
        )
        self.table_file_load = QtWidgets.QPushButton("Load")
        self.table_file_load.clicked.connect(self._load_node_table)
        self.table_file_save = QtWidgets.QPushButton("Save")
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
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Recording Config File",
            "",
            "Recording Config Files (*.json)",
        )
        if filename:
            logger.info("Recording save file name: %s", filename)
            if Path(filename).suffix != "json":
                filename += ".json"
            with open(filename, "w", encoding="UTF-8") as f:
                json.dump(self._get_current_config(), f, indent=4, sort_keys=True)

            self.status_bar_update(f"Recording config saved to file {filename}")

    def _load_node_table(self) -> None:
        """Load the node table from a json file."""
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Recording Config File",
            "",
            "Recording Config Files (*.json)",
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

    _DECIMAL_PLACES: Final = 5
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

        # Adding a default style for the tooltip with a white background and black text
        # This is a work-around for the issue that tooltips inherit style from the
        # parent widget - and this choice of colour-scheme is at least readable.
        self.setStyleSheet(
            # "QToolTip { color: #ffffff; background-color: #2a82da;"
            "QToolTip { color: black; background-color: white;"
            "border: 1px solid black; }"
        )

        self.list_cmd_history: QtWidgets.QListWidget  # Command history list widget
        self.setStatusBar(self.create_status_bar_widget("ℹ️ Status"))

        # Set the server URI from environment variable if defined
        server_address: str | None = os.environ.get("DISQ_OPCUA_SERVER_ADDRESS", None)
        if server_address is not None:
            self.input_server_address: QtWidgets.QLineEdit
            self.input_server_address.setText(server_address)
        server_port: str | None = os.environ.get("DISQ_OPCUA_SERVER_PORT", None)
        if server_port is not None:
            self.input_server_port: QtWidgets.QLineEdit
            self.input_server_port.setText(server_port)
        server_endpoint: str | None = os.environ.get("DISQ_OPCUA_SERVER_ENDPOINT", None)
        if server_endpoint is not None:
            self.input_server_endpoint: QtWidgets.QLineEdit
            self.input_server_endpoint.setText(server_endpoint)
        server_namespace: str | None = os.environ.get(
            "DISQ_OPCUA_SERVER_NAMESPACE", None
        )
        if server_namespace is not None:
            self.input_server_namespace: QtWidgets.QLineEdit
            self.input_server_namespace.setText(server_namespace)
        self.button_server_connect: QtWidgets.QPushButton
        self.button_server_connect.clicked.connect(self.connect_button_clicked)
        self.label_conn_status: QtWidgets.QLabel
        self.label_cache_status: QtWidgets.QLabel
        self.cache_checkbox: QtWidgets.QCheckBox

        # Keep a reference to model and controller
        self.model = disq_model
        self.controller = disq_controller

        # Populate the server config select (drop-down) box with entries from
        # configuration file
        server_list = self.controller.get_config_servers()
        self.dropdown_server_config_select: QtWidgets.QComboBox
        self.dropdown_server_config_select.addItems([""] + server_list)
        self.dropdown_server_config_select.setFocus()
        self.dropdown_server_config_select.currentTextChanged.connect(
            self.server_config_select_changed
        )

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
        self.line_edit_slew_simul_azim_position: QtWidgets.QLineEdit
        self.line_edit_slew_simul_elev_position: QtWidgets.QLineEdit
        self.line_edit_slew_simul_azim_velocity: QtWidgets.QLineEdit
        self.line_edit_slew_simul_elev_velocity: QtWidgets.QLineEdit
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
        self.spinbox_slew_only_elevation_position: AxisPosSpinBox
        self.spinbox_slew_only_elevation_position.set_callback(self.slew_button_clicked)
        self.spinbox_slew_only_elevation_velocity: QtWidgets.QDoubleSpinBox
        self.spinbox_slew_only_elevation_position.setDecimals(self._DECIMAL_PLACES)
        self.spinbox_slew_only_elevation_velocity.setDecimals(self._DECIMAL_PLACES)
        self.spinbox_slew_only_elevation_velocity.setToolTip(
            f"<b>Maximum:</b> {self.spinbox_slew_only_elevation_velocity.maximum()}"
        )
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
        self.spinbox_slew_only_azimuth_position: AxisPosSpinBox
        self.spinbox_slew_only_azimuth_position.set_callback(self.slew_button_clicked)
        self.spinbox_slew_only_azimuth_velocity: QtWidgets.QDoubleSpinBox
        self.spinbox_slew_only_azimuth_position.setDecimals(self._DECIMAL_PLACES)
        self.spinbox_slew_only_azimuth_velocity.setDecimals(self._DECIMAL_PLACES)
        self.spinbox_slew_only_azimuth_velocity.setToolTip(
            f"<b>Maximum:</b> {self.spinbox_slew_only_azimuth_velocity.maximum()}"
        )
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
        self.spinbox_slew_only_indexer_position: AxisPosSpinBox
        self.spinbox_slew_only_indexer_position.set_callback(self.slew_button_clicked)
        self.spinbox_slew_only_indexer_velocity: QtWidgets.QDoubleSpinBox
        self.spinbox_slew_only_indexer_position.setDecimals(self._DECIMAL_PLACES)
        self.spinbox_slew_only_indexer_velocity.setDecimals(self._DECIMAL_PLACES)
        self.spinbox_slew_only_indexer_velocity.setToolTip(
            f"<b>Maximum:</b> {self.spinbox_slew_only_indexer_velocity.maximum()}"
        )
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
        self.checkbox_limit_axis_inputs: QtWidgets.QCheckBox
        self.checkbox_limit_axis_inputs.toggled.connect(
            lambda: self.limit_axis_inputs(self.checkbox_limit_axis_inputs.isChecked())
        )

        # Point tab static pointing model widgets
        self.button_static_point_model_off: QtWidgets.QRadioButton
        self.button_static_point_model_off.setChecked(True)
        self.button_static_point_model_on: QtWidgets.QRadioButton
        self.button_group_static_point_model = QtWidgets.QButtonGroup()
        self.button_group_static_point_model.buttonClicked.connect(
            self.pointing_model_button_clicked
        )
        self.static_point_model_checked_prev: int = 0
        self.button_group_static_point_model.addButton(
            self.button_static_point_model_off, 0
        )
        self.button_group_static_point_model.addButton(
            self.button_static_point_model_on, 1
        )
        self.static_point_model_band: QtWidgets.QLabel
        self.combo_static_point_model_band: QtWidgets.QComboBox
        self.static_point_model_band_index_prev: int = 0
        self.combo_static_point_model_band.currentTextChanged.connect(
            self.pointing_model_band_selected
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
        self.static_pointing_spinboxes: list[QtWidgets.QDoubleSpinBox] = [
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
        for spinbox in self.static_pointing_spinboxes:
            spinbox.editingFinished.connect(self.static_pointing_parameter_changed)
            spinbox.blockSignals(True)
        self.opcua_offset_xelev: QtWidgets.QLabel
        self.opcua_offset_elev: QtWidgets.QLabel
        self.spinbox_offset_xelev: QtWidgets.QDoubleSpinBox
        self.spinbox_offset_elev: QtWidgets.QDoubleSpinBox
        self.spinbox_offset_xelev.editingFinished.connect(
            self.static_pointing_offset_changed
        )
        self.spinbox_offset_elev.editingFinished.connect(
            self.static_pointing_offset_changed
        )
        self.spinbox_offset_xelev.blockSignals(True)
        self.spinbox_offset_elev.blockSignals(True)
        self._update_static_pointing_inputs_text = False
        # Point tab tilt correction widgets
        self.button_tilt_correction_off: QtWidgets.QRadioButton
        self.button_tilt_correction_off.setChecked(True)
        self.button_tilt_correction_on: QtWidgets.QRadioButton
        self.button_tilt_correction_meter_1: QtWidgets.QRadioButton
        self.button_tilt_correction_meter_1.setChecked(True)
        self.button_tilt_correction_meter_2: QtWidgets.QRadioButton
        self.button_group_tilt_correction = QtWidgets.QButtonGroup()
        self.button_group_tilt_correction.buttonClicked.connect(
            self.pointing_model_button_clicked
        )
        self.tilt_correction_checked_prev: int = 0
        self.button_group_tilt_correction.addButton(self.button_tilt_correction_off, 0)
        self.button_group_tilt_correction.addButton(self.button_tilt_correction_on, 1)
        self.button_group_tilt_correction_meter = QtWidgets.QButtonGroup()
        self.button_group_tilt_correction_meter.buttonClicked.connect(
            self.pointing_model_button_clicked
        )
        self.tilt_correction_meter_checked_prev: int = 1
        self.button_group_tilt_correction_meter.blockSignals(True)
        self.button_group_tilt_correction_meter.addButton(
            self.button_tilt_correction_meter_1, 1
        )
        self.button_group_tilt_correction_meter.addButton(
            self.button_tilt_correction_meter_2, 2
        )
        # Point tab ambient temperature correction widgets
        self.button_temp_correction_off: QtWidgets.QRadioButton
        self.button_temp_correction_off.setChecked(True)
        self.button_temp_correction_on: QtWidgets.QRadioButton
        self.button_group_temp_correction = QtWidgets.QButtonGroup()
        self.button_group_temp_correction.buttonClicked.connect(
            self.pointing_model_button_clicked
        )
        self.temp_correction_checked_prev: int = 0
        self.button_group_temp_correction.addButton(self.button_temp_correction_off, 0)
        self.button_group_temp_correction.addButton(self.button_temp_correction_on, 1)
        self.ambtemp_correction_values: list[QtWidgets.QLabel] = [
            self.opcua_ambtempfiltdt,  # type: ignore
            self.opcua_ambtempparam1,  # type: ignore
            self.opcua_ambtempparam2,  # type: ignore
            self.opcua_ambtempparam3,  # type: ignore
            self.opcua_ambtempparam4,  # type: ignore
            self.opcua_ambtempparam5,  # type: ignore
            self.opcua_ambtempparam6,  # type: ignore
        ]
        self.ambtemp_correction_spinboxes: list[QtWidgets.QDoubleSpinBox] = [
            self.spinbox_ambtempfiltdt,  # type: ignore
            self.spinbox_ambtempparam1,  # type: ignore
            self.spinbox_ambtempparam2,  # type: ignore
            self.spinbox_ambtempparam3,  # type: ignore
            self.spinbox_ambtempparam4,  # type: ignore
            self.spinbox_ambtempparam5,  # type: ignore
            self.spinbox_ambtempparam6,  # type: ignore
        ]
        for spinbox in self.ambtemp_correction_spinboxes:
            spinbox.editingFinished.connect(self.ambtemp_correction_parameter_changed)
            spinbox.blockSignals(True)
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
            + self.findChildren(QtWidgets.QRadioButton)
            + self.findChildren(QtWidgets.QDoubleSpinBox)
        )
        opcua_widget_updates: dict[str, tuple[list[QtWidgets.QWidget], Callable]] = {}
        for wgt in all_widgets:
            if "opcua" not in wgt.dynamicPropertyNames():
                # Skip all the non-opcua widgets
                continue

            opcua_parameter_name: str = wgt.property("opcua")
            # the default update callback
            opcua_widget_update_func: Callable = self._update_opcua_text_widget
            logger.debug("OPCUA widget: %s", opcua_parameter_name)

            if "opcua_type" in wgt.dynamicPropertyNames():
                opcua_type = wgt.property("opcua_type")
                if opcua_type == "Boolean":
                    if isinstance(wgt, QtWidgets.QRadioButton):
                        opcua_widget_update_func = (
                            self._update_opcua_boolean_radio_button_widget
                        )
                    else:
                        opcua_widget_update_func = (
                            self._update_opcua_boolean_text_widget
                        )
                else:
                    opcua_widget_update_func = self._update_opcua_enum_widget
                logger.debug("OPCUA widget type: %s", opcua_type)
            # Return the list from the tuple or an empty list as default
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
    def all_opcua_widgets(self) -> list:
        """
        Return a list of all OPC UA widgets.

        This function finds all widgets that are subclasses of QtWidgets.QLineEdit,
        QtWidgets.QPushButton, or QtWidgets.QComboBox and have a dynamic property that
        starts with 'opcua'.

        This is a cached property, meaning the function will only run once and
        subsequent calls will return the cached result.

        :return: List of OPC UA widgets.
        """
        all_widgets: list[QtCore.QObject] = self.findChildren(
            (
                QtWidgets.QLineEdit,
                QtWidgets.QPushButton,
                QtWidgets.QRadioButton,
                QtWidgets.QComboBox,
                QtWidgets.QDoubleSpinBox,
                QtWidgets.QLabel,
            )
        )
        opcua_widgets: list[QtCore.QObject] = []
        for wgt in all_widgets:
            property_names: list[QtCore.QByteArray] = wgt.dynamicPropertyNames()
            for property_name in property_names:
                if property_name.startsWith(QtCore.QByteArray("opcua".encode())):
                    opcua_widgets.append(wgt)
                    break
        return opcua_widgets

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

    def _enable_data_logger_widgets(self, enable: bool = True) -> None:
        """
        Enable or disable data logger widgets.

        :param enable: Whether to enable or disable the widgets. Default is True.
        """
        self.button_recording_start.setEnabled(enable)
        self.line_edit_recording_file.setEnabled(enable)
        self.line_edit_recording_status.setEnabled(enable)
        self.button_recording_config.setEnabled(enable)
        # Only disable stop. Stop can only be enabled by clicking start.
        if not enable:
            self.button_recording_stop.setEnabled(enable)

    def _enable_server_widgets(
        self, enable: bool = True, connect_button: bool = False
    ) -> None:
        """
        Enable or disable server widgets and optionally update the connect button text.

        :param enable: Enable or disable server widgets (default True).
        :param connect_button: Update the connect button text (default False).
        """
        self.input_server_address.setEnabled(enable)
        self.input_server_port.setEnabled(enable)
        self.input_server_endpoint.setEnabled(enable)
        self.input_server_namespace.setEnabled(enable)
        if connect_button:
            self.button_server_connect.setText("Connect" if enable else "Disconnect")

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
        widgets: list[QtWidgets.QLineEdit | QtWidgets.QDoubleSpinBox],
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
            str_val = f"{val:.{self._DECIMAL_PLACES}f}"
        else:
            str_val = str(val)
        for widget in widgets:
            if isinstance(widget, QtWidgets.QLineEdit):
                widget.setText(str_val)
            elif isinstance(widget, QtWidgets.QDoubleSpinBox):
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
                widget.setText(str_val.replace("_", " "))  # For BandType

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

    def _update_opcua_boolean_radio_button_widget(
        self, buttons: list[QtWidgets.QRadioButton], event: dict
    ) -> None:
        """
        Set radio button in exclusive group based on its boolean OPC-UA parameter.

        :param button: Button that signal came from.
        :param event: A dictionary containing event data.
        """
        # There should only be one radio button connected to an OPC-UA parameter.
        button = buttons[0]
        logger.debug(
            "Widget: %s. Boolean OPCUA update: %s value=%s",
            button.objectName(),
            event["name"],
            event["value"],
        )

        if event["value"] is None:
            return

        # Update can come from either OFF or ON radio button, but need to explicitly
        # set one of the two in a group with setChecked(True)
        if event["value"]:
            button = getattr(self, button.objectName().replace("_off", "_on"))
        else:
            button = getattr(self, button.objectName().replace("_on", "_off"))
        button.setChecked(True)
        # Block or unblock tilt meter selection signal whether function is active
        if event["name"] == TILT_CORR_ACTIVE:
            self.button_group_tilt_correction_meter.blockSignals(not event["value"])
            self.tilt_correction_checked_prev = int(event["value"])
        # Populate input boxes with current read values after connecting to server
        elif event["name"] == STATIC_CORR_ACTIVE:
            if self._update_static_pointing_inputs_text:
                self._update_static_pointing_inputs_text = False
                self._set_static_pointing_inputs_text(not event["value"])
                self.static_point_model_checked_prev = int(event["value"])
        elif event["name"] == TEMP_CORR_ACTIVE:
            if self._update_temp_correction_inputs_text:
                self._update_temp_correction_inputs_text = False
                self._set_temp_correction_inputs_text(not event["value"])
                self.temp_correction_checked_prev = int(event["value"])

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
                    f"background-color: {background_colour_rbg}; "
                    "color: rgb(238, 238, 238);border-color: black;} "
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
        if self.model.opcua_nodes_status == NodesStatus.VALID:
            self.label_cache_status.setStyleSheet("color: black;")
        else:
            self.label_cache_status.setStyleSheet("color: red;")
        self.cache_checkbox.setEnabled(False)
        self._enable_server_widgets(False, connect_button=True)
        self._enable_opcua_widgets()
        self._enable_data_logger_widgets(True)
        self._init_opcua_combo_widgets()
        if self._track_table_file_exist():
            self.button_load_track_table.setEnabled(True)
        self._update_static_pointing_inputs_text = True
        self._update_temp_correction_inputs_text = True
        self._initialise_error_warning_widgets()
        self.warning_status_show_only_warnings.setEnabled(True)
        self.error_status_show_only_errors.setEnabled(True)
        self.spinbox_file_track_additional_offset.setEnabled(
            not self.button_file_track_absolute_times.isChecked()
        )
        self.combobox_axis_input_step.setEnabled(True)
        self.checkbox_limit_axis_inputs.setEnabled(True)

    def server_disconnected_event(self):
        """Handle the server disconnected event."""
        logger.debug("server disconnected event")
        self._disable_opcua_widgets()
        self._enable_data_logger_widgets(False)
        self.label_conn_status.setText("Disconnected")
        self.label_cache_status.setText("")
        self.cache_checkbox.setEnabled(True)
        self._enable_server_widgets(True, connect_button=True)
        self.button_load_track_table.setEnabled(False)
        self.line_edit_track_table_file.setEnabled(False)
        self.warning_status_show_only_warnings.setEnabled(False)
        self.warning_tree_view.setEnabled(False)
        self.error_status_show_only_errors.setEnabled(False)
        self.error_tree_view.setEnabled(False)
        self.combobox_axis_input_step.setEnabled(False)
        self.checkbox_limit_axis_inputs.setEnabled(False)

    def connect_button_clicked(self):
        """Setup a connection to the server."""
        if not self.controller.is_server_connected():
            connect_details = {
                "host": self.input_server_address.text(),
                "port": (
                    self.input_server_port.text()
                    if self.input_server_port.text() != ""
                    else self.input_server_port.placeholderText()
                ),
                "endpoint": self.input_server_endpoint.text(),
                "namespace": self.input_server_namespace.text(),
                "use_nodes_cache": self.cache_checkbox.isChecked(),
            }
            config_connection_details = self.controller.get_config_server_args(
                self.dropdown_server_config_select.currentText()
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
        else:
            logger.debug("disconnecting from server")
            self.controller.disconnect_server()

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
            server_config = self.controller.get_config_server_args(server_name)
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

    def track_table_file_changed(self):
        """Update the track table file path in the model."""
        if self._track_table_file_exist() and self.controller.is_server_connected():
            self.button_load_track_table.setEnabled(True)
        else:
            self.button_load_track_table.setEnabled(False)

    def track_table_file_button_clicked(self) -> None:
        """Open a file dialog to select a track table file."""
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Track Table File", "", "Track Table Files (*.csv)"
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
        """Open a dialog to select a file or folder for the recording file box."""
        dialog = QtWidgets.QFileDialog()
        dialog.setNameFilter("DataLogger File (*.hdf5)")
        if dialog.exec():
            filepaths = dialog.selectedUrls()
            if filepaths:
                self.line_edit_recording_file.setText(
                    str(Path(filepaths[0].toLocalFile()).with_suffix(""))
                )

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
        text_widget_args = [
            self.line_edit_slew_simul_azim_position.text(),
            self.line_edit_slew_simul_elev_position.text(),
            self.line_edit_slew_simul_azim_velocity.text(),
            self.line_edit_slew_simul_elev_velocity.text(),
        ]
        try:
            args = [float(str_input) for str_input in text_widget_args]
        except ValueError as e:
            logger.error("Error converting slew2abs args to float: %s", e)
            self.controller.emit_ui_status_message(
                "ERROR",
                f"Slew2Abs invalid arguments. Could not convert to number: "
                f"{text_widget_args}",
            )
            return
        logger.debug("args: %s", args)
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

    def limit_axis_inputs(self, limit: bool) -> None:
        """
        Limit the input ranges of the axis slew commands as specified in the ICD.

        :param limit: True to apply the limits, False to use -1000 to 1000.
        """
        if limit:
            self.spinbox_slew_only_azimuth_position.setMaximum(AZ_POS_MAX)
            self.spinbox_slew_only_azimuth_position.setMinimum(AZ_POS_MIN)
            self.spinbox_slew_only_azimuth_velocity.setMaximum(AZ_VEL_MAX)
            self.spinbox_slew_only_elevation_position.setMaximum(EL_POS_MAX)
            self.spinbox_slew_only_elevation_position.setMinimum(EL_POS_MIN)
            self.spinbox_slew_only_elevation_velocity.setMaximum(EL_VEL_MAX)
            self.spinbox_slew_only_indexer_position.setMaximum(FI_POS_MAX)
            self.spinbox_slew_only_indexer_position.setMinimum(FI_POS_MIN)
            self.spinbox_slew_only_indexer_velocity.setMaximum(FI_VEL_MAX)
        else:
            default_max = 1000.0
            default_min = -1000.0
            self.spinbox_slew_only_azimuth_position.setMaximum(default_max)
            self.spinbox_slew_only_azimuth_position.setMinimum(default_min)
            self.spinbox_slew_only_azimuth_velocity.setMaximum(default_max)
            self.spinbox_slew_only_elevation_position.setMaximum(default_max)
            self.spinbox_slew_only_elevation_position.setMinimum(default_min)
            self.spinbox_slew_only_elevation_velocity.setMaximum(default_max)
            self.spinbox_slew_only_indexer_position.setMaximum(default_max)
            self.spinbox_slew_only_indexer_position.setMinimum(default_min)
            self.spinbox_slew_only_indexer_velocity.setMaximum(default_max)

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

    def static_pointing_parameter_changed(self):
        """Static pointing model parameter changed slot function."""
        band = self.combo_static_point_model_band.currentText().replace(" ", "_")
        params = []
        for spinbox in self.static_pointing_spinboxes:
            params.append(round(spinbox.value(), self._DECIMAL_PLACES))
        self.controller.command_set_static_pointing_parameters(band, params)

    def static_pointing_offset_changed(self):
        """Static pointing offset changed slot function."""
        xelev = round(self.spinbox_offset_xelev.value(), self._DECIMAL_PLACES)
        elev = round(self.spinbox_offset_elev.value(), self._DECIMAL_PLACES)
        self.controller.command_set_static_pointing_offsets(xelev, elev)

    def ambtemp_correction_parameter_changed(self):
        """Ambient temperature correction parameter changed slot function."""
        params = []
        for spinbox in self.ambtemp_correction_spinboxes:
            params.append(round(spinbox.value(), self._DECIMAL_PLACES))
        self.controller.command_set_ambtemp_correction_parameters(params)

    def set_power_mode_clicked(self):
        """Set dish power mode."""
        args = [
            self.button_power_mode_low.isChecked(),
            self.spinbox_power_lim_kw.value(),
        ]
        logger.debug("set_power_mode args: %s", args)
        self.controller.command_set_power_mode(*args)

    def pointing_model_band_selected(self):
        """Static pointing model band changed slot function."""
        if self.button_group_static_point_model.checkedId() != 0:  # Not OFF
            self.pointing_model_button_clicked()

    def pointing_model_button_clicked(self):
        """Any pointing model toggle button clicked slot function."""
        static_point_model_checked_id = self.button_group_static_point_model.checkedId()
        temp_correction_checked_id = self.button_group_temp_correction.checkedId()
        tilt_correction_checked_id = self.button_group_tilt_correction.checkedId()
        tilt_corr_meter_checked_id = self.button_group_tilt_correction_meter.checkedId()
        tilt_correction = (
            tilt_corr_meter_checked_id
            if self.button_tilt_correction_on.isChecked()
            else 0
        )
        # Validate command parameters
        try:
            stat = {0: False, 1: True}[static_point_model_checked_id]
            tilt = {0: "Off", 1: "TiltmeterOne", 2: "TiltmeterTwo"}[tilt_correction]
            ambtemp = {0: False, 1: True}[temp_correction_checked_id]
        except KeyError:
            logger.exception("Invalid button ID.")
            return
        band = self.combo_static_point_model_band.currentText().replace(" ", "_")
        # Send command and check result
        _, result_msg = self.controller.command_config_pointing_model_corrections(
            stat, tilt, ambtemp, band
        )
        if result_msg == "CommandDone":
            if stat:
                self.static_pointing_parameter_changed()
                self.static_pointing_offset_changed()
                self.spinbox_offset_xelev.blockSignals(False)
                self.spinbox_offset_elev.blockSignals(False)
                for spinbox in self.static_pointing_spinboxes:
                    spinbox.blockSignals(False)
            else:
                self.spinbox_offset_xelev.blockSignals(True)
                self.spinbox_offset_elev.blockSignals(True)
                for spinbox in self.static_pointing_spinboxes:
                    spinbox.blockSignals(True)
            if ambtemp:
                self.ambtemp_correction_parameter_changed()
                for spinbox in self.ambtemp_correction_spinboxes:
                    spinbox.blockSignals(False)
            else:
                for spinbox in self.ambtemp_correction_spinboxes:
                    spinbox.blockSignals(True)
            # Keep track of radio buttons' previous states
            self.static_point_model_checked_prev = static_point_model_checked_id
            self.tilt_correction_checked_prev = tilt_correction_checked_id
            self.tilt_correction_meter_checked_prev = tilt_corr_meter_checked_id
            self.temp_correction_checked_prev = temp_correction_checked_id
        else:
            # If command did not execute for any reason, restore buttons to prev states
            self.button_group_static_point_model.button(
                self.static_point_model_checked_prev
            ).setChecked(True)
            self.button_group_tilt_correction.button(
                self.tilt_correction_checked_prev
            ).setChecked(True)
            self.button_group_tilt_correction_meter.button(
                self.tilt_correction_meter_checked_prev
            ).setChecked(True)
            self.button_group_temp_correction.button(
                self.temp_correction_checked_prev
            ).setChecked(True)

    def _set_static_pointing_inputs_text(self, block_signals: bool) -> None:
        """
        Set static pointing inputs' text to current read values.

        :param block_signals: Block or unblock the widgets' signals.
        """
        # Static pointing band
        self.combo_static_point_model_band.blockSignals(True)
        current_band = self.static_point_model_band.text()
        if current_band != "not read":
            self.combo_static_point_model_band.setCurrentIndex(
                self.model._scu.convert_enum_to_int(  # pylint: disable=protected-access
                    "BandType", current_band.replace(" ", "_")
                )
            )
        self.combo_static_point_model_band.blockSignals(block_signals)
        # Static pointing offsets
        self.spinbox_offset_xelev.blockSignals(True)
        self.spinbox_offset_elev.blockSignals(True)
        try:
            self.spinbox_offset_xelev.setValue(float(self.opcua_offset_xelev.text()))
            self.spinbox_offset_elev.setValue(float(self.opcua_offset_elev.text()))
        except ValueError:
            self.spinbox_offset_xelev.setValue(0)
            self.spinbox_offset_elev.setValue(0)
        self.spinbox_offset_xelev.blockSignals(block_signals)
        self.spinbox_offset_elev.blockSignals(block_signals)
        # Static pointing parameters
        for spinbox, value in zip(
            self.static_pointing_spinboxes, self.static_pointing_values
        ):
            spinbox.blockSignals(True)
            try:
                spinbox.setValue(float(value.text()))
            except ValueError:
                spinbox.setValue(0)
            spinbox.blockSignals(block_signals)

    def _set_temp_correction_inputs_text(self, block_signals: bool) -> None:
        """
        Set ambient temperature correction inputs' text to current read values.

        :param block_signals: Block or unblock the widgets' signals.
        """
        for spinbox, value in zip(
            self.ambtemp_correction_spinboxes, self.ambtemp_correction_values
        ):
            spinbox.blockSignals(True)
            try:
                spinbox.setValue(float(value.text()))
            except ValueError:
                spinbox.setValue(0)
            spinbox.blockSignals(block_signals)

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


class AxisPosSpinBox(QtWidgets.QDoubleSpinBox):
    """Custom axis position double/float spinbox."""

    def __init__(self, **kwargs: Any) -> None:
        """Init AxisSpinBox."""
        super().__init__(**kwargs)
        self._callback: Callable[[str], None] | None = None

    def set_callback(self, callback: Callable[[str], None]) -> None:
        """Set the callback function to be called in stepBy."""
        self._callback = callback

    # pylint: disable=invalid-name
    def stepBy(self, steps: int) -> None:  # noqa: N802
        """This method is triggered only by the up/down buttons."""
        super().stepBy(steps)  # Call the base class functionality
        if self._callback is not None:
            self._callback(self.property("axis"))
