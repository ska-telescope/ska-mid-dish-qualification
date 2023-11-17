import os
from functools import cached_property
from importlib import resources

from PyQt6 import QtCore, QtWidgets, uic

from disq import controller, model


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

        pb_slew2abs: QtWidgets.QPushButton = self.findChild(
            QtWidgets.QPushButton, name="pushButton_slew2abs"
        )
        pb_slew2abs.clicked.connect(self.slew2abs_button_clicked)

    @cached_property
    def opcua_widgets(self) -> dict:
        """Return a dict of of all 'opcua_' widgets and their update method
        {name: callback}"""
        # re = QtCore.QRegularExpression("opcua_")
        # opcua_widgets = self.findChildren(QtWidgets.QLineEdit, re)
        all_widgets = self.findChildren(QtWidgets.QLineEdit)
        opcua_widget_updates: dict = {}
        for wgt in all_widgets:
            if "opcua" in wgt.dynamicPropertyNames():
                print(f"OPCUA widget: {wgt.property('opcua')}")
                opcua_widget_updates.update({wgt.property("opcua"): wgt.setText})
        # dict with (key, value) where the key is the name of the "opcua" widget
        # property (dot-notated OPC-UA parameter name) and value is the callback method
        # to update the widget
        return opcua_widget_updates

    @QtCore.pyqtSlot(dict)
    def event_update(self, event: dict) -> None:
        print(f"View: data update: {event['name']} value={event['value']}")
        # The event update dict contains:
        # { 'name': name, 'node': node, 'value': value,
        #   'source_timestamp': source_timestamp,
        #   'server_timestamp': server_timestamp,
        #   'data': data
        # }
        val = event["value"]
        if isinstance(val, float):
            str_val = "{:.3f}".format(val)
        else:
            str_val = str(val)
        # Get the widget update method from the dict of opcua widgets
        _widget_update_func = self.opcua_widgets[event["name"]]
        _widget_update_func(str_val)

    @QtCore.pyqtSlot()
    def server_connected_event(self):
        print("server connected event")
        le: QtWidgets.QLineEdit = self.input_server_uri
        pb: QtWidgets.QPushButton = self.btn_server_connect
        self.controller.subscribe_opcua_updates(self.opcua_widgets)
        pb.setText("Disconnect")
        le.setDisabled(True)

    @QtCore.pyqtSlot()
    def server_disconnected_event(self):
        print("server disconnected event")
        le: QtWidgets.QLineEdit = self.input_server_uri
        pb: QtWidgets.QPushButton = self.btn_server_connect
        pb.setText("Connect")
        le.setEnabled(True)

    @QtCore.pyqtSlot()
    def connect_button_clicked(self):
        """Setup a connection to the server"""
        print("BTN CLICKED")
        le: QtWidgets.QLineEdit = self.input_server_uri
        server_uri = le.text()
        if not self.controller.is_server_connected():
            self.controller.connect_server(server_uri)
        else:
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
        print(f"args: {args}")
        self.controller.command_slew2abs(*args)

    @QtCore.pyqtSlot(str)
    def command_response_status_update(self, status: str):
        """Update the main window status bar with a status update"""
        self.cmd_status_label.setText(status)
