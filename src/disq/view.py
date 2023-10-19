import os
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6 import uic
from qasync import asyncSlot, asyncClose

import model
import controller

class MainView(QtWidgets.QMainWindow):
    def __init__(self, model:model.Model, controller:controller.Controller, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Load the UI from the XML .ui file
        uic.loadUi("dishstructure_mvc.ui", self)
        self.setWindowTitle("Dish Structure")

        # Add a label widget to the status bar for command/response status
        # The QT Designer doesn't allow us to add this label so we have to do it here
        self.cmd_status_label = QtWidgets.QLabel("command status: ")
        self.status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.addWidget(self.cmd_status_label)

        # Set the server URI from environment variable if defined
        server_uri:str|None = os.environ.get("OPCUA_SERVER_URI", None)
        self.input_server_uri:QtWidgets.QLineEdit
        self.input_server_uri.setText(server_uri)
        self.btn_server_connect:QtWidgets.QPushButton
        self.btn_server_connect.setFocus()

        # Keep a reference to model and controller
        self.model = model
        self.controller = controller

        # Connect widgets and slots to the Controller
        self.controller.command_response_status.connect(self.command_response_status_update)
        self.controller.server_connected.connect(self.server_connected_event)
        self.controller.server_disconnected.connect(self.server_disconnected_event)

        pb: QtWidgets.QPushButton = self.btn_server_connect
        pb.clicked.connect(self.connect_button_clicked)

        # Listen for Model event signals

        self.findChild(QtWidgets.QPushButton, name="pushButton_slew2abs").clicked.connect(self.slew2abs_button_clicked)

    @property
    def opcua_widgets(self) -> list:
        """Return a list of of all 'opcua_' widgets and their update method in a tuple (name:str, update:callable)"""
        # re = QtCore.QRegularExpression("opcua_")
        # opcua_widgets = self.findChildren(QtWidgets.QLineEdit, re)
        all_widgets = self.findChildren(QtWidgets.QLineEdit)
        opcua_widget_updates = []
        for wgt in all_widgets:
            if 'opcua' in wgt.dynamicPropertyNames():
                print(f"OPCUA widget: {wgt.property('opcua')}")
                opcua_widget_updates.append((wgt.property('opcua'), wgt.setText))
        # list of tuples with (name, callback)
        # opcua_widget_updates = [(w, w.setText) for w in widgets_opcua_property]
        return opcua_widget_updates
        
    @asyncClose
    async def closeEvent(self, event):
        print("closing event")

    @asyncSlot()
    async def server_connected_event(self):
        print("server connected event")
        le: QtWidgets.QLineEdit = self.input_server_uri
        pb: QtWidgets.QPushButton = self.btn_server_connect
        await self.controller.subscribe_opcua_updates(self.opcua_widgets)
        pb.setText("Disconnect")
        le.setDisabled(True)

    @asyncSlot()
    async def server_disconnected_event(self):
        print("server disconnected event")
        le: QtWidgets.QLineEdit = self.input_server_uri
        pb: QtWidgets.QPushButton = self.btn_server_connect
        pb.setText("Connect")
        le.setEnabled(True)

    @asyncSlot()
    async def connect_button_clicked(self):
        """Setup a connection to the server"""
        print("BTN CLICKED")
        le: QtWidgets.QLineEdit = self.input_server_uri
        server_uri = le.text()
        if not await self.controller.is_server_connected():
            await self.controller.connect_server(server_uri)
        else:
            await self.controller.disconnect_server()

    @asyncSlot()
    async def slew2abs_button_clicked(self):
        args = [float(str_input) for str_input in [
            self.lineEdit_azimuth_position_demand.text(),
            self.lineEdit_elevation_position_demand.text(),
            self.lineEdit_azimuth_velocity_demand.text(),
            self.lineEdit_elevation_velocity_demand.text()
        ]]
        print(f"args: {args}")
        await self.controller.command_slew2abs(*args)


    @asyncSlot(str)
    async def command_response_status_update(self, status:str):
        """Update the main window status bar with a status update"""
        self.cmd_status_label.setText(status)

