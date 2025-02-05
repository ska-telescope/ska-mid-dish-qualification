"""Qt Dialog windows for DiSQ GUI view."""

import ipaddress
import json
import logging
from importlib import resources
from pathlib import Path
from typing import Final

from platformdirs import user_documents_dir
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from ska_mid_wms_interface import load_weather_station_configuration

from ska_mid_disq.constants import SKAO_ICON_PATH

from .controller import Controller

_WEATHER_STATION_YAML: Final = "../weather_station_resources/weather_station.yaml"

logger = logging.getLogger("gui.view")


# pylint: disable=too-many-instance-attributes,too-many-statements
class ServerConnectDialog(QDialog):
    """
    A dialog-window class for connecting to the OPC-UA server.

    :param parent: The parent widget of the dialog.
    """

    def __init__(self, parent: QWidget, mvc_controller: Controller):
        """
        Initialize the Server Connect dialog.

        :param parent: The parent widget for the dialog.
        """
        super().__init__(parent)
        self._controller = mvc_controller

        self.setWindowTitle("Server Connection")
        self.setWindowIcon(QIcon(SKAO_ICON_PATH))

        self.save_button = QPushButton("Save", self)
        self.save_button.clicked.connect(self.save_config)
        self.delete_button = QPushButton("Delete", self)
        self.delete_button.clicked.connect(self.confirm_delete_dialog)
        connect_buttons = (
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Close
        )
        self.connect_box = QDialogButtonBox(connect_buttons)
        self.connect_box.button(QDialogButtonBox.StandardButton.Ok).setText("Connect")
        self.connect_box.accepted.connect(self.confirm_connect)
        self.connect_box.rejected.connect(self.reject)

        self.vbox_layout = QVBoxLayout()
        message = QLabel("Enter or select the OPC-UA server details and click OK")
        self.vbox_layout.addWidget(message)

        # Populate the server config select (drop-down) box with entries from
        # configuration file
        server_list = self._controller.get_config_servers()
        self.dropdown_server_config_select = QComboBox()
        self.dropdown_server_config_select.setEditable(True)
        self.dropdown_server_config_select.addItems([""] + server_list)
        self.dropdown_server_config_select.currentTextChanged.connect(
            self.server_config_select_changed
        )
        self.vbox_layout.addWidget(QLabel("Select server from config file:"))
        self.vbox_layout.addWidget(self.dropdown_server_config_select)

        self.vbox_layout.addWidget(QLabel("Server Address:"))
        self.input_server_address = QLineEdit()
        self.input_server_address.setPlaceholderText("Server Address")
        self.vbox_layout.addWidget(self.input_server_address)

        self.vbox_layout.addWidget(QLabel("Server Port:"))
        self.input_server_port = QLineEdit()
        self.input_server_port.setPlaceholderText("Server Port")
        self.vbox_layout.addWidget(self.input_server_port)

        self.vbox_layout.addWidget(QLabel("Server Endpoint:"))
        self.input_server_endpoint = QLineEdit()
        self.input_server_endpoint.setPlaceholderText("Server Endpoint")
        self.vbox_layout.addWidget(self.input_server_endpoint)

        self.vbox_layout.addWidget(QLabel("Server Namespace:"))
        self.input_server_namespace = QLineEdit()
        self.input_server_namespace.setPlaceholderText("Server Namespace")
        self.vbox_layout.addWidget(self.input_server_namespace)

        self.cache_checkbox = QCheckBox()
        self.cache_checkbox.setText("Use nodes cache")
        self.cache_checkbox.setChecked(False)
        self.vbox_layout.addWidget(self.cache_checkbox)

        self.hbox_layout = QHBoxLayout()
        self.hbox_layout.addWidget(self.connect_box)
        self.hbox_layout.addWidget(self.save_button)
        self.hbox_layout.addWidget(self.delete_button)
        self.vbox_layout.addLayout(self.hbox_layout)
        self.setLayout(self.vbox_layout)
        self.server_details: dict[str, str | bool] = {}

        if self._controller.last_server_details is not None:
            server_config = self._controller.last_server_details
            self.input_server_address.setText(server_config["host"])
            self.input_server_port.setText(str(server_config["port"]))
            self.input_server_endpoint.setText(server_config["endpoint"])
            self.input_server_namespace.setText(server_config["namespace"])
            self.cache_checkbox.setChecked(bool(server_config["use_nodes_cache"]))
        self.dropdown_server_config_select.setFocus()

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
        # Get the server config args from configfile
        server_config = self._controller.get_config_server_args(server_name)
        # Populate the widgets with the server config args
        if server_config is None:
            self.input_server_address.clear()
            self.input_server_port.clear()
            self.input_server_endpoint.clear()
            self.input_server_namespace.clear()
            self.cache_checkbox.setChecked(False)
        else:
            self.input_server_address.setText(server_config["host"])
            self.input_server_port.setText(str(server_config["port"]))
            self.input_server_endpoint.setText(server_config.get("endpoint", ""))
            self.input_server_namespace.setText(server_config.get("namespace", ""))
            self.cache_checkbox.setChecked(
                bool(server_config.get("use_nodes_cache", False))
            )
            if "use_nodes_cache" in server_config:
                self.cache_checkbox.setChecked(
                    False
                    if server_config["use_nodes_cache"]
                    in ["False", "false", "No", "no"]
                    else bool(server_config["use_nodes_cache"])
                )
            else:
                self.cache_checkbox.setChecked(False)

    def confirm_connect(self) -> None:
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

    def save_config(self) -> None:
        """Save a server config."""
        # Input validation
        try:
            ipaddress.ip_address(self.input_server_address.text())
        except ValueError:
            QMessageBox.warning(  # type: ignore
                self,
                "Invalid input",
                f"'{self.input_server_address.text()}' is not a valid IP address!",
                QMessageBox.StandardButton.Ok,
            )
            return
        server_details = {"host": self.input_server_address.text()}
        port = self.input_server_port.text()
        if port:
            if not port.isdigit() or not 0 <= int(port) <= 65535:
                QMessageBox.warning(  # type: ignore
                    self,
                    "Invalid input",
                    f"'{port}' is not a valid port!\n"
                    "Please enter a port between 0 and 65535.",
                    QMessageBox.StandardButton.Ok,
                )
                return
            server_details["port"] = port
        if self.input_server_endpoint.text():
            server_details["endpoint"] = self.input_server_endpoint.text()
        if self.input_server_namespace.text():
            server_details["namespace"] = self.input_server_namespace.text()
        if self.cache_checkbox.isChecked():
            server_details["use_nodes_cache"] = "True"
        if self.server_config_selected in self._controller.get_config_servers():
            # Create a confirmation dialog
            reply = QMessageBox.warning(
                self,
                "Overwrite",
                "Are you sure you want to overwrite the existing config for "
                f"'{self.server_config_selected}'?",
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
            )
        else:
            reply = QMessageBox.StandardButton.Yes
            self.dropdown_server_config_select.addItem(self.server_config_selected)
        # Handle user response
        if reply == QMessageBox.StandardButton.Yes:
            if self._controller.save_server_config(
                self.server_config_selected, server_details
            ):
                logger.info("Saved '%s' server config", self.server_config_selected)
                QMessageBox.information(
                    self,
                    "Success",
                    f"Saved config for '{self.server_config_selected}'.",
                    QMessageBox.StandardButton.Ok,
                )

    def confirm_delete_dialog(self) -> None:
        """Confirm a user wants to delete a server config."""
        # Create a confirmation dialog
        reply = QMessageBox.warning(
            self,
            "Delete",
            "Are you sure you want to delete the config for "
            f"'{self.server_config_selected}'?",
            QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.No,
        )
        # Handle user response
        if reply == QMessageBox.StandardButton.Yes:
            if self._controller.delete_server_config(self.server_config_selected):
                logger.info("Deleted '%s' server config", self.server_config_selected)
                self.dropdown_server_config_select.removeItem(
                    self.dropdown_server_config_select.findText(
                        self.server_config_selected
                    )
                )
                self.dropdown_server_config_select.setCurrentIndex(0)


class StatusBarMixin:
    """A mixin class to provide a window with a status bar."""

    def create_status_bar_widget(
        self,
        label: str = "",
    ) -> QStatusBar:
        """Create the status bar widgets for the window."""
        # Add a label widget to the status bar for command/response status
        status_bar = QStatusBar()
        self.cmd_status_label = QLabel(label)
        status_bar.addWidget(self.cmd_status_label)
        return status_bar

    def status_bar_update(self, status: str) -> None:
        """Update the status bar with a status update."""
        self.cmd_status_label.setText(status[:200])


class WeatherStationConnectDialog(StatusBarMixin, QDialog):
    # pylint: disable=too-few-public-methods
    """A dialog-window class for connecting to a weather station."""

    def __init__(self, parent: QWidget, mvc_controller: Controller):
        """
        Initialize the weather station connect dialog.

        :param parent: The parent widget for the dialog.
        """
        super().__init__(parent)
        self._controller = mvc_controller
        weather_stations = list(self._controller.get_weather_station_configs())
        self.server_details: dict[str, str] = {}

        self.setWindowTitle("Weather Station Connection")
        self.setWindowIcon(QIcon(SKAO_ICON_PATH))

        button = (
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        self.btn_box = QDialogButtonBox(button)
        self.btn_box.accepted.connect(self.confirm_connect)
        self.btn_box.rejected.connect(self.reject)

        self.vbox_layout = QVBoxLayout()
        # Create widgets
        self.dropdown_weather_station_config_select = QComboBox()
        self.dropdown_weather_station_config_select.setEditable(True)
        self.dropdown_weather_station_config_select.addItems([""] + weather_stations)
        self.dropdown_weather_station_config_select.currentTextChanged.connect(
            self.weather_station_config_select_changed
        )
        self.select_weather_station_config_file = QPushButton("Select configuration...")
        self.select_weather_station_config_file.clicked.connect(
            self._select_weather_station_config_file_clicked
        )
        self.weather_station_config_file = QLineEdit()
        self.default_weather_station_config_file = QPushButton(
            "Use Default Configuration"
        )
        self.default_weather_station_config_file.clicked.connect(
            lambda: self.weather_station_config_file.setText("/DEFAULT/")
        )
        self.weather_station_address = QLineEdit()
        self.weather_station_port = QLineEdit()
        # Create layout
        self.vbox_layout.addWidget(
            QLabel("Enter or select the weather station details and click OK")
        )
        self.vbox_layout.addWidget(QLabel("Select built-in weather station:"))
        self.vbox_layout.addWidget(self.dropdown_weather_station_config_select)
        self.vbox_layout.addWidget(QLabel("Select configuration:"))
        self.vbox_layout.addWidget(self.select_weather_station_config_file)
        self.vbox_layout.addWidget(self.default_weather_station_config_file)
        self.vbox_layout.addWidget(self.weather_station_config_file)
        self.vbox_layout.addWidget(QLabel("Weather Station Address:"))
        self.vbox_layout.addWidget(self.weather_station_address)
        self.vbox_layout.addWidget(QLabel("Weather Station Port:"))
        self.vbox_layout.addWidget(self.weather_station_port)
        self.vbox_layout.addWidget(self.btn_box)
        status_bar = self.create_status_bar_widget()
        self.vbox_layout.addWidget(status_bar)
        self.setLayout(self.vbox_layout)
        self.weather_station_details: dict[str, str] = {}

    def weather_station_config_select_changed(self, weather_station: str) -> None:
        """
        User changed weather station selection in drop-down box.

        Fill or clear the form.
        """
        logger.debug("Selected weather station config changed to %s", weather_station)
        try:
            weather_station_details = self._controller.get_weather_station_configs()[
                weather_station
            ]
        except KeyError:
            # Unknown config, clear form.
            self.weather_station_config_file.clear()
            self.weather_station_address.clear()
            self.weather_station_port.clear()
            return

        self.weather_station_config_file.setText(weather_station_details["config_file"])
        self.weather_station_address.setText(weather_station_details["address"])
        self.weather_station_port.setText(weather_station_details["port"])

    def _select_weather_station_config_file_clicked(self):
        """Load a weather station config from a yaml file."""
        options = QFileDialog.Option(QFileDialog.Option.ReadOnly)
        filename, _ = QFileDialog.getOpenFileName(
            parent=self,
            caption="Select Weather Station Config",
            dir=user_documents_dir(),
            filter="Weather Station Config Files (*.yaml);;All Files (*)",
            options=options,
        )
        if filename:
            logger.info("Weather station config file name: %s", filename)
            self.weather_station_config_file.setText(filename)

    def confirm_connect(self):
        """Accepts the weather station details entered in the dialog."""
        logger.debug("Weather station dialog accepted")
        config = self.weather_station_config_file.text()
        if config == "/DEFAULT/":
            config = resources.files(__package__).joinpath(_WEATHER_STATION_YAML)
        address = self.weather_station_address.text()
        port = self.weather_station_port.text()
        if not config or not address or not port:
            self.status_bar_update("Please fill in all weather station details.")
            return

        try:
            load_weather_station_configuration(config)
        except ValueError:
            msg = f"{config} does not contain a valid weather station configuration"
            logger.error(msg)
            self.status_bar_update(msg)
            return

        self.server_details = {"config": config, "address": address, "port": port}
        self.accept()


# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-statements,too-few-public-methods
class SelectNodesDialog(QDialog):
    """
    A dialog-window class for displaying OPC-UA nodes.

    :param parent: The parent widget of the dialog.
    :param nodes: A list of OPC-UA nodes to be displayed and selected.
    """

    def __init__(
        self,
        parent: QWidget,
        node_type: str,
        nodes: dict[str, dict[str, bool | int]],
        max_select: int | None = None,
    ):
        """
        Initialize the Recording Configuration dialog.

        :param parent: The parent widget for the dialog.
        :param type: The type of nodes to use in the window title.
        :param nodes: A list of strings representing OPC-UA nodes to choose
            from.
        :param max_select: Maximum amount of nodes to be selected simultaneously,
            default to None (no limit).
        """
        super().__init__(parent)

        self.setWindowTitle(f"Choose {node_type}")
        self.setWindowIcon(QIcon(SKAO_ICON_PATH))
        self.resize(544, 512)

        self._max_select = max_select
        self._node_table_widgets: dict[str, QCheckBox] = {}

        button = (
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        self.btn_box = QDialogButtonBox(button)
        self.btn_box.accepted.connect(self.accept_selection)
        self.btn_box.rejected.connect(self.reject)

        self.grid_layout = QGridLayout()
        table_options_layout = QGridLayout()
        self.grid_layout.addLayout(table_options_layout, 0, 0)

        message = QLabel(
            f"Select the OPC-UA {node_type} to display from the list and click OK"
        )
        if self._max_select:
            message.setText(
                f"{message.text()}<br>NOTE: A maximum of {self._max_select} can be "
                "selected at a time!"
            )
        message.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter
        )
        self.grid_layout.addWidget(message)

        self.node_table = QTableWidget(len(nodes), 2, self)
        self._create_node_table(nodes, self.node_table)
        self.grid_layout.addWidget(self.node_table)

        self.grid_layout.addWidget(self.btn_box)
        self.setLayout(self.grid_layout)
        self.config_parameters: dict[str, dict[str, bool | int]] = {}

    def _create_node_table(
        self, nodes: dict[str, dict[str, bool | int]], node_table: QTableWidget
    ) -> None:
        """Create the node table."""
        node_table.setStyleSheet(
            "QCheckBox {margin-left: 28px;} "
            "QCheckBox::indicator {width: 24px; height: 24px}"
        )
        node_table.setHorizontalHeaderLabels(["Name", "Display"])
        horizontal_header = node_table.horizontalHeader()
        horizontal_header.setDefaultSectionSize(80)
        horizontal_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        vertical_header = QHeaderView(Qt.Orientation.Vertical)
        vertical_header.hide()
        node_table.setVerticalHeader(vertical_header)
        node_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for i, (node, value) in enumerate(nodes.items()):
            # Add node name in first column and turn off table interactions
            node_name = QTableWidgetItem(node)
            node_name.setFlags(Qt.ItemFlag.ItemIsEnabled)
            node_table.setItem(i, 0, node_name)
            # Ensure "Display" column is also not interactable
            display_background = QTableWidgetItem()
            display_background.setFlags(Qt.ItemFlag.ItemIsEnabled)
            node_table.setItem(i, 1, display_background)
            # Add "Display" checkbox
            display_node = QCheckBox()
            display_node.setChecked(value["display"])  # type: ignore
            if self._max_select:
                display_node.checkStateChanged.connect(self._checkbox_state_changed)
            node_table.setCellWidget(i, 1, display_node)
            self._node_table_widgets[node] = display_node

    def _checkbox_state_changed(self) -> None:
        number_selected = 0
        for checkbox in self._node_table_widgets.values():
            checkbox.setHidden(False)
            if checkbox.isChecked():
                number_selected += 1
            if number_selected >= self._max_select:
                for checkbox in self._node_table_widgets.values():
                    if not checkbox.isChecked():
                        checkbox.setHidden(True)
                return

    def _get_current_config(self) -> dict[str, dict[str, bool]]:
        """Get the current displayed nodes' values."""
        config_parameters = {}
        for node, checkbox in self._node_table_widgets.items():
            config_parameters[node] = {"display": checkbox.isChecked()}

        return config_parameters

    def accept_selection(self):
        """Accepts the selection made in the configuration dialog."""
        logger.debug("Choose nodes dialog accepted")
        self.config_parameters = self._get_current_config()
        self.accept()


# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-statements
class RecordingConfigDialog(StatusBarMixin, QDialog):
    """
    A dialog-window class for selecting OPC-UA parameters to be recorded.

    :param parent: The parent widget of the dialog.
    :param attributes: A list of OPC-UA attributes to be displayed and selected.
    """

    def __init__(
        self,
        parent: QWidget,
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

        self._node_table_widgets: dict[str, dict[str, QCheckBox | QLineEdit]] = {}

        button = (
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        self.btn_box = QDialogButtonBox(button)
        self.btn_box.accepted.connect(self.accept_selection)
        self.btn_box.rejected.connect(self.reject)

        self.grid_layout = QGridLayout()
        table_options_layout = QGridLayout()
        self.table_file_label = QLabel("Table config file:")
        self.table_file_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignCenter
        )
        self.table_file_load = QPushButton("Open File...")
        self.table_file_load.clicked.connect(self._load_node_table)
        self.table_file_save = QPushButton("Save As...")
        self.table_file_save.clicked.connect(self._save_node_table)
        self.record_column_label = QLabel("Record column:")
        self.record_column_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignCenter
        )
        self.record_column_tick = QPushButton("Record All")
        self.record_column_tick.clicked.connect(
            lambda: self._set_all_record_checkboxes(True)
        )
        self.record_column_clear = QPushButton("Clear All")
        self.record_column_clear.clicked.connect(
            lambda: self._set_all_record_checkboxes(False)
        )
        self.period_column_label = QLabel("Period column:")
        self.period_column_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignCenter
        )
        self.period_column_value = QSpinBox()
        # Remove step buttons and prevent mouse wheel interaction
        self.period_column_value.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        self.period_column_value.wheelEvent = lambda e: None  # type: ignore[assignment]
        self.period_column_value.setRange(50, 60000)
        self.period_column_value.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.period_column_set = QPushButton("Set All")
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

        message = QLabel(
            "Select all the OPC-UA attributes to record from the list and click OK"
        )
        message.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter
        )
        self.grid_layout.addWidget(message)

        self.node_table = QTableWidget(len(attributes), 3, self)
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
        horizontal_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        vertical_header = QHeaderView(Qt.Orientation.Vertical)
        vertical_header.hide()
        node_table.setVerticalHeader(vertical_header)
        node_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for i, (attr, value) in enumerate(attributes.items()):
            # Add node name in first column and turn off table interactions
            node_name = QTableWidgetItem(attr)
            node_name.setFlags(Qt.ItemFlag.ItemIsEnabled)
            node_table.setItem(i, 0, node_name)
            # Ensure "Record" and "Period" columns are also not interactable
            add_background = QTableWidgetItem()
            period_background = QTableWidgetItem()
            add_background.setFlags(Qt.ItemFlag.ItemIsEnabled)
            period_background.setFlags(Qt.ItemFlag.ItemIsEnabled)
            node_table.setItem(i, 1, add_background)
            node_table.setItem(i, 2, period_background)
            # Add "Record" checkbox
            record_node = QCheckBox()
            record_node.setChecked(value["record"])
            node_table.setCellWidget(i, 1, record_node)
            # Add "Period" line edit
            node_period = QSpinBox()
            # Remove step buttons and prevent mouse wheel interaction
            node_period.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            node_period.wheelEvent = node_table.wheelEvent
            node_period.setRange(50, 60000)
            node_period.setAlignment(Qt.AlignmentFlag.AlignHCenter)
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
            dir=user_documents_dir(),
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
        filename, _ = QFileDialog.getOpenFileName(
            parent=self,
            caption="Load Recording Config File",
            dir=user_documents_dir(),
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
                        "Could not load file %s: %s:%s",
                        filename,
                        type(e).__name__,
                        e,
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
