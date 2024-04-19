"""DiSQ GUI View."""

import logging
import os
from enum import Enum
from functools import cached_property
from importlib import resources
from pathlib import Path
from typing import Callable

from PyQt6 import QtCore, QtWidgets, uic

from disq import controller, model

logger = logging.getLogger("gui.view")


# pylint: disable=too-few-public-methods,too-many-lines
class RecordingConfigDialog(QtWidgets.QDialog):
    """
    A dialog-window class for selecting OPC-UA parameters to be recorded.

    :param parent: The parent widget of the dialog.
    :type parent: QtWidgets.QWidget
    :param attributes: A list of OPC-UA attributes to be displayed and selected.
    :type attributes: list[str]
    """

    def __init__(self, parent: QtWidgets.QWidget, attributes: list[str]):
        """
        Initialize the Recording Configuration dialog.

        :param parent: The parent widget for the dialog.
        :type parent: QtWidgets.QWidget
        :param attributes: A list of strings representing OPC-UA attributes to choose
            from.
        :type attributes: list[str]
        """
        super().__init__(parent)

        self.setWindowTitle("Recording Configuration")

        button = (
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )

        self.btn_box = QtWidgets.QDialogButtonBox(button)
        self.btn_box.accepted.connect(self.accept_selection)
        self.btn_box.rejected.connect(self.reject)

        self.vbox_layout = QtWidgets.QVBoxLayout()
        message = QtWidgets.QLabel(
            "Select all the OPC-UA attributes to record from the list and click OK"
        )
        self.vbox_layout.addWidget(message)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.list_widget.resize(300, 120)
        for attr in attributes:
            self.list_widget.addItem(attr)
        self.vbox_layout.addWidget(self.list_widget)

        self.vbox_layout.addWidget(self.btn_box)
        self.setLayout(self.vbox_layout)
        self.config_parameters: list[str] = []

    @QtCore.pyqtSlot()
    def accept_selection(self):
        """Accepts the selection made in the configuration dialog."""
        logger.debug("Recording config dialog accepted")
        self.config_parameters = [
            item.text() for item in self.list_widget.selectedItems()
        ]
        self.accept()


# pylint: disable=too-many-statements, too-many-public-methods,
# pylint: disable=too-many-instance-attributes
class MainView(QtWidgets.QMainWindow):
    """
    A class representing the main Window of the DiSQ GUI application.

    :param disq_model: The model instance for the MainView.
    :type disq_model: model.Model
    :param disq_controller: The controller instance for the MainView.
    :type disq_controller: controller.Controller
    """

    def __init__(
        self,
        disq_model: model.Model,
        disq_controller: controller.Controller,
        *args,
        **kwargs,
    ):
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
        :type disq_model: model.Model
        :param disq_controller: The controller object for DiSQ.
        :type disq_controller: controller.Controller
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        """
        super().__init__(*args, **kwargs)
        logger.setLevel(logging.DEBUG)
        # Load the UI from the XML .ui file
        ui_xml_filename = resources.files(__package__) / "ui/dishstructure_mvc.ui"
        uic.loadUi(ui_xml_filename, self)
        self.setWindowTitle("DiSQ GUI")

        # Add a label widget to the status bar for command/response status
        # The QT Designer doesn't allow us to add this label so we have to do it here
        self.cmd_status_label = QtWidgets.QLabel("ℹ️ Status")
        self.status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.addWidget(self.cmd_status_label)

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
        self.button_server_connect.setFocus()
        self.label_conn_status: QtWidgets.QLabel

        # Keep a reference to model and controller
        self.model = disq_model
        self.controller = disq_controller

        # Populate the server config select (drop-down) box with entries from
        # configuration file
        server_list = self.controller.get_config_servers()
        self.dropdown_server_config_select: QtWidgets.QComboBox
        self.dropdown_server_config_select.addItems([""] + server_list)
        self.dropdown_server_config_select.currentTextChanged.connect(
            self.server_config_select_changed
        )

        # Connect widgets and slots to the Controller
        self.controller.ui_status_message.connect(self.command_response_status_update)
        self.controller.server_connected.connect(self.server_connected_event)
        self.controller.server_disconnected.connect(self.server_disconnected_event)

        pb: QtWidgets.QPushButton = self.button_server_connect
        pb.clicked.connect(self.connect_button_clicked)

        # Listen for Model event signals
        self.model.data_received.connect(self.event_update)

        # Authority status group widgets
        self.combobox_authority: QtWidgets.QComboBox
        self.button_take_auth: QtWidgets.QPushButton
        self.button_take_auth.clicked.connect(
            lambda: self.authority_button_clicked(True)
        )
        self.button_release_auth: QtWidgets.QPushButton
        self.button_release_auth.clicked.connect(
            lambda: self.authority_button_clicked(False)
        )
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
        self.line_edit_slew_only_elevation_position: QtWidgets.QLineEdit
        self.line_edit_slew_only_elevation_velocity: QtWidgets.QLineEdit
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
        self.line_edit_slew_only_azimuth_position: QtWidgets.QLineEdit
        self.line_edit_slew_only_azimuth_velocity: QtWidgets.QLineEdit
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
        self.line_edit_slew_only_indexer_position: QtWidgets.QLineEdit
        self.line_edit_slew_only_indexer_velocity: QtWidgets.QLineEdit
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
            self.opcua_ia,
            self.opcua_ca,
            self.opcua_npae,
            self.opcua_an,
            self.opcua_an0,
            self.opcua_aw,
            self.opcua_aw0,
            self.opcua_acec,
            self.opcua_aces,
            self.opcua_aba,
            self.opcua_abphi,
            self.opcua_caobs,
            self.opcua_ie,
            self.opcua_ecec,
            self.opcua_eces,
            self.opcua_hece4,
            self.opcua_hese4,
            self.opcua_hece8,
            self.opcua_hese8,
            self.opcua_eobs,
        ]
        self.static_pointing_spinboxes: list[QtWidgets.QDoubleSpinBox] = [
            self.spinbox_ia,
            self.spinbox_ca,
            self.spinbox_npae,
            self.spinbox_an,
            self.spinbox_an0,
            self.spinbox_aw,
            self.spinbox_aw0,
            self.spinbox_acec,
            self.spinbox_aces,
            self.spinbox_aba,
            self.spinbox_abphi,
            self.spinbox_caobs,
            self.spinbox_ie,
            self.spinbox_ecec,
            self.spinbox_eces,
            self.spinbox_hece4,
            self.spinbox_hese4,
            self.spinbox_hece8,
            self.spinbox_hese8,
            self.spinbox_eobs,
        ]
        for spinbox in self.static_pointing_spinboxes:
            spinbox.valueChanged.connect(self.static_pointing_parameter_changed)
            spinbox.blockSignals(True)
        self.opcua_offset_xelev: QtWidgets.QLabel
        self.opcua_offset_elev: QtWidgets.QLabel
        self.spinbox_offset_xelev: QtWidgets.QDoubleSpinBox
        self.spinbox_offset_elev: QtWidgets.QDoubleSpinBox
        self.spinbox_offset_xelev.valueChanged.connect(
            self.static_pointing_offset_changed
        )
        self.spinbox_offset_elev.valueChanged.connect(
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
            self.opcua_ambtempfiltdt,
            self.opcua_ambtempparam1,
            self.opcua_ambtempparam2,
            self.opcua_ambtempparam3,
            self.opcua_ambtempparam4,
            self.opcua_ambtempparam5,
            self.opcua_ambtempparam6,
        ]
        self.ambtemp_correction_spinboxes: list[QtWidgets.QDoubleSpinBox] = [
            self.spinbox_ambtempfiltdt,
            self.spinbox_ambtempparam1,
            self.spinbox_ambtempparam2,
            self.spinbox_ambtempparam3,
            self.spinbox_ambtempparam4,
            self.spinbox_ambtempparam5,
            self.spinbox_ambtempparam6,
        ]
        for spinbox in self.ambtemp_correction_spinboxes:
            spinbox.valueChanged.connect(self.ambtemp_correction_parameter_changed)
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
        self.disable_opcua_widgets()
        # Recording group widgets
        self.button_recording_start: QtWidgets.QPushButton
        self.line_edit_recording_file: QtWidgets.QLineEdit
        self.line_edit_recording_status: QtWidgets.QLineEdit
        self.button_recording_start.clicked.connect(
            lambda: self.controller.recording_start(
                self.line_edit_recording_file.text()
            )
        )
        self.button_recording_stop: QtWidgets.QPushButton
        self.button_recording_stop.clicked.connect(self.controller.recording_stop)
        self.controller.recording_status.connect(self.recording_status_update)

        self.button_recording_config: QtWidgets.QPushButton
        self.button_recording_config.clicked.connect(
            self.recording_config_button_clicked
        )

        self.button_load_track_table: QtWidgets.QPushButton
        self.button_load_track_table.clicked.connect(
            lambda: self.controller.load_track_table(
                self.line_edit_track_table_file.text()
            )
        )
        self.line_edit_track_table_file: QtWidgets.QLineEdit
        self.line_edit_track_table_file.textChanged.connect(
            self.track_table_file_changed
        )
        self.button_select_track_table_file: QtWidgets.QPushButton
        self.button_select_track_table_file.clicked.connect(
            self.track_table_file_button_clicked
        )

    @cached_property
    def opcua_widgets(self) -> dict:
        """
        Return a dict of of all 'opcua' widgets and their update method.

        This is a cached property, meaning the function will only run once and
        subsequent calls will return the cached result.

        :return: {name: (widget, func)}
        """
        all_widgets: list[QtCore.QObject] = (
            self.findChildren(QtWidgets.QLineEdit)
            + self.findChildren(QtWidgets.QLabel)
            + self.findChildren(QtWidgets.QRadioButton)
        )
        opcua_widget_updates: dict = {}
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
            opcua_widget_updates.update(
                {opcua_parameter_name: (wgt, opcua_widget_update_func)}
            )
        # dict with (key, value) where the key is the name of the "opcua" widget
        # property (dot-notated OPC-UA parameter name) and value is a tuple with
        # the widget and a callback method to update the widget
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
        :rtype: list[QtCore.QObject]
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

    def enable_opcua_widgets(self):
        """
        Enable all the OPC-UA widgets.

        By default the widgets should always start up in the disabled state.
        """
        for widget in self.all_opcua_widgets:
            widget.setEnabled(True)

    def disable_opcua_widgets(self):
        """Disable all the OPC-UA widgets."""
        for widget in self.all_opcua_widgets:
            widget.setEnabled(False)

    def enable_data_logger_widgets(self, enable: bool = True):
        """
        Enable or disable data logger widgets.

        :param enable: Whether to enable or disable the widgets. Default is True.
        :type enable: bool
        """
        self.button_recording_start.setEnabled(enable)
        self.button_recording_stop.setEnabled(enable)
        self.line_edit_recording_file.setEnabled(enable)
        self.line_edit_recording_status.setEnabled(enable)
        self.button_recording_config.setEnabled(enable)

    def enable_server_widgets(self, enable: bool = True, connect_button: bool = False):
        """
        Enable or disable server widgets and optionally update the connect button text.

        :param enable: Enable or disable server widgets (default True).
        :type enable: bool
        :param connect_button: Update the connect button text (default False).
        :type connect_button: bool
        """
        self.input_server_address.setEnabled(enable)
        self.input_server_port.setEnabled(enable)
        self.input_server_endpoint.setEnabled(enable)
        self.input_server_namespace.setEnabled(enable)
        if connect_button:
            self.button_server_connect.setText("Connect" if enable else "Disconnect")

    @QtCore.pyqtSlot(bool)
    def recording_status_update(self, status: bool):
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

    @QtCore.pyqtSlot(dict)
    def event_update(self, event: dict) -> None:
        """
        Update the view with event data.

        :param event: A dictionary containing event data.
        :type event: dict
        """
        logger.debug("View: data update: %s value=%s", event["name"], event["value"])
        # Get the widget update method from the dict of opcua widgets
        _widget = self.opcua_widgets[event["name"]][0]
        _widget_update_func = self.opcua_widgets[event["name"]][1]
        _widget_update_func(_widget, event)

    def _init_opcua_combo_widgets(self) -> None:
        """Initialise all the OPC-UA combo widgets."""
        for widget in self.findChildren(QtWidgets.QComboBox):
            if "opcua_type" not in widget.dynamicPropertyNames():
                # Skip all the non-opcua widgets
                continue
            opcua_type = str(widget.property("opcua_type"))
            if opcua_type in self.model.opcua_enum_types:
                opcua_enum: Enum = self.model.opcua_enum_types[opcua_type]
                enum_strings = [str(e.name) for e in opcua_enum]
                # Explicitly cast to QComboBox
                wgt: QtWidgets.QComboBox = widget  # type: ignore
                wgt.clear()
                wgt.addItems(enum_strings)

    def _update_opcua_text_widget(
        self, widget: QtWidgets.QLineEdit, event: dict
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
            str_val = f"{val:.3f}"
        else:
            str_val = str(val)
        widget.setText(str_val)

    def _update_opcua_enum_widget(self, widget: QtWidgets.QLineEdit, event: dict):
        """
        Update the text of the widget with the event data.

        The Event data is an OPC-UA Enum type. The value arrives as an integer and
        it is converted to a string here before updating the text of the widget.

        The event update dict contains:
        - name: name
        - node: node
        - value: value
        - source_timestamp: source_timestamp
        - server_timestamp: server_timestamp
        - data: data
        """
        opcua_type: str = widget.property("opcua_type")
        int_val = int(event["value"])
        try:
            opcua_enum: type = self.model.opcua_enum_types[opcua_type]
        except KeyError:
            logger.warning(
                "OPC-UA Enum type '%s' not found. Using integer value instead.",
                opcua_type,
            )
            str_val = str(int_val)
        else:
            val = opcua_enum(int_val)
            str_val = val.name
        finally:
            widget.setText(str_val)

    def _update_opcua_boolean_radio_button_widget(
        self, button: QtWidgets.QRadioButton, event: dict
    ) -> None:
        """
        Set radio button in exclusive group based on its boolean OPC-UA parameter.

        :param button: Button that signal came from.
        :type button: QtWidgets.QRadioButton
        :param event: A dictionary containing event data.
        :type event: dict
        """
        logger.debug(
            "Widget: %s. Boolean OPCUA update: %s value=%s",
            button.objectName(),
            event["name"],
            event["value"],
        )
        # Update can come from either OFF or ON radio button, but need to explicitly
        # set one of the two in a group with setChecked(True)
        if event["value"]:
            button = getattr(self, button.objectName().replace("_off", "_on"))
        else:
            button = getattr(self, button.objectName().replace("_on", "_off"))
        button.setChecked(True)
        # Block or unblock tilt meter selection signal whether function is active
        if event["name"] == "Pointing.TiltCorrActive":
            self.button_group_tilt_correction_meter.blockSignals(not event["value"])
        # Populate input boxes with current read values after connecting to server
        elif event["name"] == "Pointing.StaticCorrActive":
            if self._update_static_pointing_inputs_text:
                self._update_static_pointing_inputs_text = False
                self._set_static_pointing_inputs_text(not event["value"])
        elif event["name"] == "Pointing.TempCorrActive":
            if self._update_temp_correction_inputs_text:
                self._update_temp_correction_inputs_text = False
                self._set_temp_correction_inputs_text(not event["value"])

    def _update_opcua_boolean_text_widget(
        self, widget: QtWidgets.QLineEdit, event: dict
    ) -> None:
        """
        Update background colour of widget to reflect boolean state of OPC-UA parameter.

        The event update 'value' field can take 3 states:
         - None: the OPC-UA parameter is not defined. Colour background grey/disabled.
         - True: the OPC-UA parameter is True. Colour background light green (LED on).
         - False: the OPC-UA parameter is False. Colour background dark green (LED off).
        """
        logger.debug("Boolean OPCUA update: %s value=%s", event["name"], event["value"])
        # TODO: modify background colour of widget (LED style on/off) to reflect the
        # boolean state
        led_colours = {
            "red": {True: "rgb(255, 0, 0)", False: "rgb(128, 0, 0)"},
            "green": {True: "rgb(10, 250, 0)", False: "rgb(10, 80, 0)"},
            "yellow": {True: "rgb(250, 255, 0)", False: "rgb(180, 180, 45)"},
            "orange": {True: "rgb(255, 185, 35)", False: "rgb(180, 135, 35)"},
        }
        if event["value"] is None:
            widget.setEnabled(False)
            widget.setStyleSheet("border-color: white;")
        else:
            led_colour = "green"  # default colour
            if "led_colour" in widget.dynamicPropertyNames():
                led_colour = widget.property("led_colour")
            widget.setEnabled(True)
            widget.setStyleSheet(
                f"background-color: {led_colours[led_colour][event['value']]};"
                "border-color: black;"
            )

    def _track_table_file_exist(self) -> bool:
        """Check if the track table file exists."""
        tt_filename = Path(self.line_edit_track_table_file.text())
        return tt_filename.exists()

    @QtCore.pyqtSlot()
    def server_connected_event(self):
        """
        Handle the server connected event.

        This function is called when the server is successfully connected.
        """
        logger.debug("server connected event")
        self.label_conn_status.setText("Subscribing to OPC-UA updates...")
        self.controller.subscribe_opcua_updates(self.opcua_widgets)
        self.label_conn_status.setText(f"Connected to: {self.model.get_server_uri()}")
        self.enable_server_widgets(False, connect_button=True)
        self.enable_opcua_widgets()
        self.enable_data_logger_widgets(True)
        self._init_opcua_combo_widgets()
        if self._track_table_file_exist():
            self.button_load_track_table.setEnabled(True)
        self._update_static_pointing_inputs_text = True
        self._update_temp_correction_inputs_text = True

    @QtCore.pyqtSlot()
    def server_disconnected_event(self):
        """Handle the server disconnected event."""
        logger.debug("server disconnected event")
        self.disable_opcua_widgets()
        self.enable_data_logger_widgets(False)
        self.label_conn_status.setText("Status: disconnected")
        self.enable_server_widgets(True, connect_button=True)
        self.button_load_track_table.setEnabled(False)
        self.line_edit_track_table_file.setEnabled(False)

    @QtCore.pyqtSlot()
    def connect_button_clicked(self):
        """Setup a connection to the server."""
        if not self.controller.is_server_connected():
            connect_details = {
                "host": self.input_server_address.text(),
                "port": self.input_server_port.text(),
                "endpoint": self.input_server_endpoint.text(),
                "namespace": self.input_server_namespace.text(),
            }
            config_connection_details = self.controller.get_config_server_args(
                self.dropdown_server_config_select.currentText()
            )
            connect_details["username"] = config_connection_details.get(
                "username", None
            )
            connect_details["password"] = config_connection_details.get(
                "password", None
            )
            logger.debug("connecting to server: %s", connect_details)
            self.label_conn_status.setText("connecting...")
            self.controller.connect_server(connect_details)
        else:
            logger.debug("disconnecting from server")
            self.controller.disconnect_server()

    @QtCore.pyqtSlot(str)
    def server_config_select_changed(self, server_name: str):
        """
        User changed server selection in drop-down box.

        Enable/disable relevant widgets.
        """
        logger.debug("server config select changed: %s", server_name)
        if server_name is None or server_name == "":
            self.enable_server_widgets(True)
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
            self.enable_server_widgets(False)

    @QtCore.pyqtSlot(str)
    def track_table_file_changed(self):
        """Update the track table file path in the model."""
        if self._track_table_file_exist() and self.controller.is_server_connected():
            self.button_load_track_table.setEnabled(True)
        else:
            self.button_load_track_table.setEnabled(False)

    @QtCore.pyqtSlot()
    def track_table_file_button_clicked(self) -> None:
        """Open a file dialog to select a track table file."""
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Track Table File", "", "Track Table Files (*.csv)"
        )
        if filename:
            self.line_edit_track_table_file.setText(filename)

    @QtCore.pyqtSlot()
    def recording_config_button_clicked(self):
        """Open the recording configuration dialog."""
        dialog = RecordingConfigDialog(self, self.model.opcua_attributes)
        if dialog.exec():
            logger.debug("Recording config dialog accepted")
            logger.debug("Selected: %s", dialog.config_parameters)
            self.controller.recording_config = dialog.config_parameters
        else:
            logger.debug("Recording config dialog cancelled")

    @QtCore.pyqtSlot()
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

    @QtCore.pyqtSlot(str)
    def slew_button_clicked(self, axis: str):
        """
        Slot function to handle the click event of a slew button.

        :param axis: The axis for which the slew operation is being performed.
        :type axis: str
        """

        def validate_args(text_widget_args: list[str]) -> list[float] | None:
            """
            Validate and convert a list of string arguments to a list of float values.

            :param text_widget_args: A list of string arguments to be converted to float
                  values.
            :type text_widget_args: list[str]
            :return: A list of float values converted from the input string arguments.
            :rtype: list[float] or None if conversion fails.
            :raises ValueError: If any of the string arguments cannot be converted to a
                  float.
            """
            try:
                args = [float(str_input) for str_input in text_widget_args]
                return args
            except ValueError as e:
                logger.error("Error converting slew args to float: %s", e)
                self.controller.emit_ui_status_message(
                    "ERROR",
                    f"Slew invalid arguments. Could not convert to number: "
                    f"{text_widget_args}",
                )
                return None

        match axis:
            case "El":
                text_widget_args = [
                    self.line_edit_slew_only_elevation_position.text(),
                    self.line_edit_slew_only_elevation_velocity.text(),
                ]
            case "Az":
                text_widget_args = [
                    self.line_edit_slew_only_azimuth_position.text(),
                    self.line_edit_slew_only_azimuth_velocity.text(),
                ]
            case "Fi":
                text_widget_args = [
                    self.line_edit_slew_only_indexer_position.text(),
                    self.line_edit_slew_only_indexer_velocity.text(),
                ]
            case _:
                return
        args = validate_args(text_widget_args)
        if args is not None:
            logger.debug("args: %s", args)
            self.controller.command_slew_single_axis(axis, *args)
        return

    @QtCore.pyqtSlot(str)
    def stop_button_clicked(self, axis: str):
        """
        Handle the signal emitted when the stop button is clicked.

        :param axis: The axis on which to stop the movement.
        :type axis: str
        """
        self.controller.command_stop(axis)

    @QtCore.pyqtSlot()
    def stow_button_clicked(self):
        """Handle the click event of the stow button."""
        self.controller.command_stow()

    @QtCore.pyqtSlot()
    def unstow_button_clicked(self):
        """
        Unstow button clicked callback function.

        This function calls the controller's command_stow method with False as the
        argument.

        :param self: The object itself.
        :type self: object
        """
        self.controller.command_stow(False)

    @QtCore.pyqtSlot(str)
    def activate_button_clicked(self, axis: str):
        """
        Activate the button clicked for a specific axis.

        :param axis: The axis for which the button was clicked.
        :type axis: str
        """
        self.controller.command_activate(axis)

    @QtCore.pyqtSlot(str)
    def deactivate_button_clicked(self, axis: str):
        """
        Deactivate button clicked slot function.

        :param axis: Axis identifier for deactivation.
        :type axis: str
        """
        self.controller.command_deactivate(axis)

    @QtCore.pyqtSlot(bool)
    def authority_button_clicked(self, take_command: bool):
        """
        Handle the click event of an authority button.

        :param take_command: A boolean value indicating whether to take or release
            authority.
        :type take_command: bool
        """
        username = self.combobox_authority.currentText()
        self.controller.command_take_authority(
            take_command=take_command, username=username
        )

    @QtCore.pyqtSlot(str)
    def command_response_status_update(self, status: str):
        """Update the main window status bar with a status update."""
        self.cmd_status_label.setText(status)

    @QtCore.pyqtSlot(str)
    def move2band_button_clicked(self, band: str):
        """Move to the given band."""
        self.controller.command_move2band(band)

    @QtCore.pyqtSlot()
    def static_pointing_parameter_changed(self):
        """Static pointing model parameter changed slot function."""
        band = self.combo_static_point_model_band.currentText().replace(" ", "_")
        params = []
        for spinbox in self.static_pointing_spinboxes:
            params.append(spinbox.value())
        self.controller.command_set_static_pointing_parameters(band, params)

    @QtCore.pyqtSlot()
    def static_pointing_offset_changed(self):
        """Static pointing offset changed slot function."""
        xelev = self.spinbox_offset_xelev.value()
        elev = self.spinbox_offset_elev.value()
        self.controller.command_set_static_pointing_offsets(xelev, elev)

    @QtCore.pyqtSlot()
    def ambtemp_correction_parameter_changed(self):
        """Ambient temperature correction parameter changed slot function."""
        params = []
        for spinbox in self.ambtemp_correction_spinboxes:
            params.append(spinbox.value())
        self.controller.command_set_ambtemp_correction_parameters(params)

    @QtCore.pyqtSlot()
    def pointing_model_band_selected(self):
        """Static pointing model band changed slot function."""
        if self.button_group_static_point_model.checkedId() != 0:  # Not OFF
            self.pointing_model_button_clicked()

    @QtCore.pyqtSlot()
    def pointing_model_button_clicked(self):
        """Any pointing model toggle button clicked slot function."""
        tilt_correction = (
            self.button_group_tilt_correction_meter.checkedId()
            if self.button_tilt_correction_on.isChecked()
            else 0
        )
        # Validate command parameters
        try:
            stat = {0: False, 1: True}[self.button_group_static_point_model.checkedId()]
            tilt = {0: "Off", 1: "TiltmeterOne", 2: "TiltmeterTwo"}[tilt_correction]
            ambtemp = {0: False, 1: True}[self.button_group_temp_correction.checkedId()]
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

    def _set_static_pointing_inputs_text(self, block_signals: bool):
        """
        Set static pointing inputs' text to current read values.

        :param block_signals: Block or unblock the widgets' signals.
        :type block_signals: bool
        """
        # Static pointing band
        self.combo_static_point_model_band.blockSignals(True)
        self.combo_static_point_model_band.setCurrentIndex(
            self.model.convert_band_to_type(self.static_point_model_band.text())
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

    def _set_temp_correction_inputs_text(self, block_signals: bool):
        """
        Set ambient temperature correction inputs' text to current read values.

        :param block_signals: Block or unblock the widgets' signals.
        :type block_signals: bool
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
