import typing, os
from PyQt6.QtCore import QObject, pyqtSignal
from asyncua import Client, ua, Node
from enum import Enum

class SubscriptionHandler:
    def __init__(self, callback_method:callable, ui_name:str) -> None:
        self.callback_method = callback_method
        self.ui_name = ui_name
    
    async def datachange_notification(self, node: Node, val, data):
        if type(val) == float:
            str_val = "{:.3f}".format(val)
        elif type(val) == Enum:
            str_val = val.name
        else:
            str_val = str(val)
        self.callback_method(str_val)


class Model(QObject):
    # define signals here
    command_response = pyqtSignal(str)

    def __init__(self, 
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._client:Client|None = None
        self._namespace = str(os.getenv("DISQ_OPCUA_SERVER_NAMESPACE", "http://skao.int/DS_ICD/"))
        self._namespace_index: int|None = None
        self._subscriptions = []
        self.subscription_rate_ms = int(os.getenv("DISQ_OPCUA_SUBSCRIPTION_PERIOD_MS", 100))


    async def connect(self, server_uri:str,):
        self._client = Client(server_uri)
        await self._client.connect()
        await self._client.load_data_type_definitions() # Needed to load OPC UA datatypes in the ua module
        self._namespace_index = await self._client.get_namespace_index(self._namespace)
    
    async def disconnect(self):
        await self._client.disconnect()

    async def is_connected(self) -> bool:
        connected = True
        try:
            await self._client.check_connection()
        except:
            print("======NOT CONNECTED======")
            connected = False
        return connected
    
    @property
    def plc_prog_path(self):
        """Return a list of the PLC_PRG path elements (display names)"""
        return [f"{self._namespace_index}:{path}" for path in [
            "Logic", "Application", "PLC_PRG"
        ]]
        
    def get_node_browse_name(self, display_name:str|list):
        """Return a nodes browse name, including the namespace index number"""
        if type(display_name) == str:
            return f"{self._namespace_index}:{display_name}"
        elif type(display_name) == list:
            return [f"{self._namespace_index}:{dname}" for dname in display_name]

    async def register_monitor(self, ui_name:str, monitor_callback:callable):
        """Register a callback and start subscription to data changes on the named variable
        
        ui_name is the UI string name form
        monitor_callback is a callback method that the subscription must call with the update"""
        monitor_callback('registering...')
        # opcua_node_path:list = self.plc_prog_path + self.get_node_browse_name(self.ui_name_to_opcua_name(ui_name))
        opcua_node_path:list = self.plc_prog_path + self.get_node_browse_name(ui_name.split('/'))
        print("Registering OPC-UA node: ", opcua_node_path)

        try:
            opcua_node = await self._client.nodes.objects.get_child( opcua_node_path )
        except ua.UaError as e:
            print(f"WARNING: no OPCUA object named \"{ui_name}\" found on server. Skipping subscription. ERROR: {e}")
            return
        handler = SubscriptionHandler(monitor_callback, ui_name)
        subscription = await self._client.create_subscription(self.subscription_rate_ms, handler)
        await subscription.subscribe_data_change(opcua_node)
        self._subscriptions.append(subscription)

    async def call_method(self, object_name:str, method_name:str, *args: typing.Any) -> tuple:
        obj_browse_path = self.plc_prog_path + [self.get_node_browse_name(object_name)]
        method_browse_name = self.get_node_browse_name(method_name)
        print(f"Object: {obj_browse_path} method: {method_browse_name}")
        obj = await self._client.nodes.objects.get_child( obj_browse_path )
        return_code = await obj.call_method(method_browse_name, *args)
        return_msg = ua.CmdResponseType(return_code).name
        return return_code, return_msg