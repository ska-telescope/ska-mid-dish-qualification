import logging
import os
from functools import cached_property
from importlib import resources

from PyQt6 import QtCore, QtWidgets, uic

from disq import controller, model

logger = logging.getLogger("gui.view")


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
        self.controller.command_response_status.connect(
            self.command_response_status_update
        )
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
        logger.debug(f"Boolean OPCUA update: {event}")
        # TODO: modify background colour of widget (LED style on/off) to reflect the boolean state
        led_colours = {
            "red": {True: "rgb(255, 0, 0)", False: "rgb(128, 0, 0)"},
            "green": {True: "rgb(10, 250, 0)", False: "rgb(10, 80, 0)"},
            "yellow": {True: "rgb(250, 255, 0)", False: "rgb(180, 180, 45)"},
            "orange": {True: "rgb(255, 185, 35)", False: "rgb(180, 135, 35)"},
        }
        if event["value"] is None:
            widget.setEnabled(False)
            # widget.setStyleSheet("background-color: rgb(128, 128, 128);")
        else:
            led_colour = "green"  # default colour
            if "led_colour" in widget.dynamicPropertyNames():
                led_colour = widget.property("led_colour")
            widget.setEnabled(True)
            widget.setStyleSheet(
                f"background-color: {led_colours[led_colour][event['value']]};"
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

    @QtCore.pyqtSlot()
    def server_disconnected_event(self):
        logger.debug("server disconnected event")
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
            logging.debug(f"connecting to server: %s", server_uri)
            lbl: QtWidgets.QLabel = self.label_connection_status
            lbl.setText("connecting...")
            self.controller.connect_server(server_uri)
        else:
            logging.debug(f"disconnecting from server")
            self.controller.disconnect_server()

    @QtCore.pyqtSlot()
    def slew2abs_button_clicked(self):
        args = [
            float(str_input)
            for str_input in [
                self.lineEdit_azimuth_position_demand.text(),
                self.lineEdit_elevation_position_demand.text(),
                self.lineEdit_azimuth_velocity_demand.text(),
                self.lineEdit_elevation_velocity_demand.text(),
            ]
        ]
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
