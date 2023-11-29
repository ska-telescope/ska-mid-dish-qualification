import logging
import os
from functools import cached_property
from importlib import resources

from PyQt6 import QtCore, QtWidgets, uic

from disq import controller, model

logger = logging.getLogger("gui.view")


class RecordingConfigDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, attributes: list[str] = []):
        super().__init__(parent)

        self.setWindowTitle("Recording Configuration")

        QBtn = (
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )

        self.btn_box = QtWidgets.QDialogButtonBox(QBtn)
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
        logger.debug("Recording config dialog accepted")
        self.config_parameters = [
            item.text() for item in self.list_widget.selectedItems()
        ]
        self.accept()


class MainView(QtWidgets.QMainWindow):
    def __init__(
        self, model: model.Model, controller: controller.Controller, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        # Load the UI from the XML .ui file
        ui_xml_filename = resources.files(__package__) / "ui/dishstructure_mvc.ui"
        uic.loadUi(ui_xml_filename, self)
        self.setWindowTitle("DiSQ GUI")

        # Add a label widget to the status bar for command/response status
        # The QT Designer doesn't allow us to add this label so we have to do it here
        self.cmd_status_label = QtWidgets.QLabel("command status: ")
        self.status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.addWidget(self.cmd_status_label)

        # Set the server URI from environment variable if defined
        server_uri: str | None = os.environ.get("DISQ_OPCUA_SERVER_URI", None)
        self.input_server_uri: QtWidgets.QLineEdit
        self.input_server_uri.setText(server_uri)
        self.btn_server_connect: QtWidgets.QPushButton
        self.btn_server_connect.setFocus()

        # Keep a reference to model and controller
        self.model = model
        self.controller = controller

        # Connect widgets and slots to the Controller
        self.controller.ui_status_message.connect(self.command_response_status_update)
        self.controller.server_connected.connect(self.server_connected_event)
        self.controller.server_disconnected.connect(self.server_disconnected_event)

        pb: QtWidgets.QPushButton = self.btn_server_connect
        pb.clicked.connect(self.connect_button_clicked)

        # Listen for Model event signals
        self.model.data_received.connect(self.event_update)

        # pb_slew2abs: QtWidgets.QPushButton = self.findChild(
        #     QtWidgets.QPushButton, name="pushButton_slew2abs"
        # )
        # pb_slew2abs.clicked.connect(self.slew2abs_button_clicked)
        self.pushButton_slew2abs: QtWidgets.QPushButton
        self.pushButton_slew2abs.clicked.connect(self.slew2abs_button_clicked)
        self.pushButton_stop: QtWidgets.QPushButton
        self.pushButton_stop.clicked.connect(self.stop_button_clicked)
        self.pushButton_stow: QtWidgets.QPushButton
        self.pushButton_stow.clicked.connect(self.stow_button_clicked)
        self.pushButton_unstow: QtWidgets.QPushButton
        self.pushButton_unstow.clicked.connect(self.unstow_button_clicked)
        self.pushButton_activate: QtWidgets.QPushButton
        self.pushButton_activate.clicked.connect(self.activate_button_clicked)
        self.pushButton_deactivate: QtWidgets.QPushButton
        self.pushButton_deactivate.clicked.connect(self.deactivate_button_clicked)
        self.pushButton_Band1: QtWidgets.QPushButton
        self.pushButton_Band1.clicked.connect(
            lambda: self.move2band_button_clicked("Band_1")
        )
        self.pushButton_Band2: QtWidgets.QPushButton
        self.pushButton_Band2.clicked.connect(
            lambda: self.move2band_button_clicked("Band_2")
        )
        self.pushButton_Band3: QtWidgets.QPushButton
        self.pushButton_Band3.clicked.connect(
            lambda: self.move2band_button_clicked("Band_3")
        )
        self.pushButton_Band4: QtWidgets.QPushButton
        self.pushButton_Band4.clicked.connect(
            lambda: self.move2band_button_clicked("Band_4")
        )
        self.pushButton_Band5a: QtWidgets.QPushButton
        self.pushButton_Band5a.clicked.connect(
            lambda: self.move2band_button_clicked("Band_5a")
        )
        self.pushButton_Band5b: QtWidgets.QPushButton
        self.pushButton_Band5b.clicked.connect(
            lambda: self.move2band_button_clicked("Band_5b")
        )
        self.pushButton_Band6: QtWidgets.QPushButton
        self.pushButton_Band6.clicked.connect(
            lambda: self.move2band_button_clicked("Band_6")
        )
        self.pushButton_Band_optical: QtWidgets.QPushButton
        self.pushButton_Band_optical.clicked.connect(
            lambda: self.move2band_button_clicked("Optical")
        )
        self.disable_opcua_widgets()

        self.pushButton_recording_start: QtWidgets.QPushButton
        self.lineEdit_recording_file: QtWidgets.QLineEdit
        self.pushButton_recording_start.clicked.connect(
            lambda: self.controller.recording_start(self.lineEdit_recording_file.text())
        )
        self.pushButton_recording_stop: QtWidgets.QPushButton
        self.pushButton_recording_stop.clicked.connect(self.controller.recording_stop)
        self.controller.recording_status.connect(self.recording_status_update)

        self.pushButton_recording_config: QtWidgets.QPushButton
        self.pushButton_recording_config.clicked.connect(
            self.recording_config_button_clicked
        )

    @cached_property
    def opcua_widgets(self) -> dict:
        """Return a dict of of all 'opcua' widgets and their update method
        {name: (widget, func)}"""
        # re = QtCore.QRegularExpression("opcua_")
        # opcua_widgets = self.findChildren(QtWidgets.QLineEdit, re)
        all_widgets: list[QtWidgets.QLineEdit] = self.findChildren(QtWidgets.QLineEdit)
        opcua_widget_updates: dict = {}
        for wgt in all_widgets:
            if "opcua" not in wgt.dynamicPropertyNames():
                # Skip all the non-opcua widgets
                continue

            opcua_parameter_name: str = wgt.property("opcua")
            opcua_widget_update_func = (
                self._update_opcua_text_widget
            )  # the default update callback
            logger.debug("OPCUA widget: %s", opcua_parameter_name)

            if "opcua_type" in wgt.dynamicPropertyNames():
                opcua_type = wgt.property("opcua_type")
                if opcua_type == "Boolean":
                    opcua_widget_update_func = self._update_opcua_boolean_widget
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
        all_widgets: list[QtWidgets.QObject] = self.findChildren(
            (QtWidgets.QLineEdit, QtWidgets.QPushButton)
        )
        opcua_widgets: list[QtWidgets.QObject] = []
        for wgt in all_widgets:
            property_names: list[QtCore.QByteArray] = wgt.dynamicPropertyNames()
            for property_name in property_names:
                if property_name.startsWith(QtCore.QByteArray("opcua".encode())):
                    opcua_widgets.append(wgt)
                    break
        return opcua_widgets

    def enable_opcua_widgets(self):
        """Enable all the OPC-UA widgets"""
        for widget in self.all_opcua_widgets:
            widget.setEnabled(True)

    def disable_opcua_widgets(self):
        """Disable all the OPC-UA widgets"""
        for widget in self.all_opcua_widgets:
            widget.setEnabled(False)

    def enable_data_logger_widgets(self, enable: bool = True):
        self.pushButton_recording_start.setEnabled(enable)
        self.pushButton_recording_stop.setEnabled(enable)
        self.lineEdit_recording_file.setEnabled(enable)
        self.lineEdit_recording_status.setEnabled(enable)
        self.pushButton_recording_config.setEnabled(enable)

    @QtCore.pyqtSlot(bool)
    def recording_status_update(self, status: bool):
        """Update the recording status"""
        self.lineEdit_recording_status: QtWidgets.QLineEdit
        if status:
            self.lineEdit_recording_status.setText("Recording")
            self.lineEdit_recording_status.setStyleSheet(
                "background-color: rgb(10, 250, 0);"
            )
            self.pushButton_recording_start.setEnabled(False)
            self.pushButton_recording_stop.setEnabled(True)
            self.pushButton_recording_config.setEnabled(False)
        else:
            self.lineEdit_recording_status.setText("Stopped")
            self.lineEdit_recording_status.setStyleSheet(
                "background-color: rgb(10, 80, 0);"
            )
            self.pushButton_recording_start.setEnabled(True)
            self.pushButton_recording_stop.setEnabled(False)
            self.pushButton_recording_config.setEnabled(True)

    @QtCore.pyqtSlot(dict)
    def event_update(self, event: dict) -> None:
        logger.debug(f"View: data update: {event['name']} value={event['value']}")
        # Get the widget update method from the dict of opcua widgets
        _widget = self.opcua_widgets[event["name"]][0]
        _widget_update_func = self.opcua_widgets[event["name"]][1]
        _widget_update_func(_widget, event)

    def _update_opcua_text_widget(
        self, widget: QtWidgets.QLineEdit, event: dict
    ) -> None:
        """Update the text of the widget with the event value

        The event update dict contains:
        { 'name': name, 'node': node, 'value': value,
          'source_timestamp': source_timestamp,
          'server_timestamp': server_timestamp,
          'data': data }
        """
        val = event["value"]
        if isinstance(val, float):
            str_val = "{:.3f}".format(val)
        else:
            str_val = str(val)
        widget.setText(str_val)

    def _update_opcua_enum_widget(self, widget: QtWidgets.QLineEdit, event: dict):
        """Update the text of the widget with the event data

        The Event data is an OPC-UA Enum type. The value arrives as an integer and
        it is converted to a string here before updating the text of the widget.

        The event update dict contains:
        { 'name': name, 'node': node, 'value': value,
          'source_timestamp': source_timestamp,
          'server_timestamp': server_timestamp,
          'data': data }
        """
        opcua_type: str = widget.property("opcua_type")
        OpcuaEnum: type = self.model.opcua_enum_types[opcua_type]

        val = OpcuaEnum(event["value"])
        str_val = val.name
        widget.setText(str_val)

    def _update_opcua_boolean_widget(
        self, widget: QtWidgets.QLineEdit, event: dict
    ) -> None:
        """Update the background colour of the widget to reflect the boolean state of the OPC-UA parameter

        The event udpdate 'value' field can take 3 states:
         - None: the OPC-UA parameter is not defined. Colour background grey/disabled.
         - True: the OPC-UA parameter is True. Colour background light green (LED on).
         - False: the OPC-UA parameter is False. Colour background dark green (LED off).
        """
        logger.debug(f"Boolean OPCUA update: {event['name']} value={event['value']}")
        # TODO: modify background colour of widget (LED style on/off) to reflect the boolean state
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

    @QtCore.pyqtSlot()
    def server_connected_event(self):
        logger.debug("server connected event")
        le: QtWidgets.QLineEdit = self.input_server_uri
        pb: QtWidgets.QPushButton = self.btn_server_connect
        lbl: QtWidgets.QLabel = self.label_connection_status
        lbl.setText("Subscribing to OPC-UA updates...")
        self.controller.subscribe_opcua_updates(self.opcua_widgets)
        lbl.setText(f"Connected to: {self.model.get_server_uri()}")
        pb.setText("Disconnect")
        le.setDisabled(True)
        self.enable_opcua_widgets()
        self.enable_data_logger_widgets(True)

    @QtCore.pyqtSlot()
    def server_disconnected_event(self):
        logger.debug("server disconnected event")
        self.disable_opcua_widgets()
        self.enable_data_logger_widgets(False)
        le: QtWidgets.QLineEdit = self.input_server_uri
        pb: QtWidgets.QPushButton = self.btn_server_connect
        lbl: QtWidgets.QLabel = self.label_connection_status
        lbl.setText("Status: disconnected")
        pb.setText("Connect")
        le.setEnabled(True)

    @QtCore.pyqtSlot()
    def connect_button_clicked(self):
        """Setup a connection to the server"""
        le: QtWidgets.QLineEdit = self.input_server_uri
        server_uri = le.text()
        if not self.controller.is_server_connected():
            logger.debug("connecting to server: %s", server_uri)
            lbl: QtWidgets.QLabel = self.label_connection_status
            lbl.setText("connecting...")
            self.controller.connect_server(server_uri)
        else:
            logger.debug("disconnecting from server")
            self.controller.disconnect_server()

    @QtCore.pyqtSlot()
    def recording_config_button_clicked(self):
        """Open the recording configuration dialog"""
        dialog = RecordingConfigDialog(self, self.model.opcua_attributes)
        if dialog.exec():
            logger.debug("Recording config dialog accepted")
            logger.debug(f"Selected: {dialog.config_parameters}")
            self.controller.recording_config = dialog.config_parameters
        else:
            logger.debug("Recording config dialog cancelled")

    @QtCore.pyqtSlot()
    def slew2abs_button_clicked(self):
        text_widget_args = [
            self.lineEdit_azimuth_position_demand.text(),
            self.lineEdit_elevation_position_demand.text(),
            self.lineEdit_azimuth_velocity_demand.text(),
            self.lineEdit_elevation_velocity_demand.text(),
        ]
        try:
            args = [float(str_input) for str_input in text_widget_args]
        except ValueError as e:
            logger.error(f"Error converting slew2abs args to float: {e}")
            self.controller.emit_ui_status_message(
                "ERROR",
                f"Slew2Abs invalid arguments. Could not convert to number: {text_widget_args}",
            )
            return
        logger.debug(f"args: {args}")
        self.controller.command_slew2abs(*args)

    @QtCore.pyqtSlot()
    def stop_button_clicked(self):
        self.controller.command_stop()

    @QtCore.pyqtSlot()
    def stow_button_clicked(self):
        self.controller.command_stow()

    @QtCore.pyqtSlot()
    def unstow_button_clicked(self):
        self.controller.command_stow(False)

    @QtCore.pyqtSlot()
    def activate_button_clicked(self):
        self.controller.command_activate()

    @QtCore.pyqtSlot()
    def deactivate_button_clicked(self):
        self.controller.command_deactivate()

    @QtCore.pyqtSlot(str)
    def command_response_status_update(self, status: str):
        """Update the main window status bar with a status update"""
        self.cmd_status_label.setText(status)

    @QtCore.pyqtSlot(str)
    def move2band_button_clicked(self, band: str):
        """Move to the given band"""
        self.controller.command_move2band(band)
