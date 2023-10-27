import asyncio
import os

from janus import Queue
from PyQt6.QtCore import QObject, pyqtSignal

# from asyncua import Client, ua, Node
from disq.sculib import scu

# from enum import Enum


# class SubscriptionHandler:
#     def __init__(self, callback_method: callable, ui_name: str) -> None:
#         self.callback_method = callback_method
#         self.ui_name = ui_name

#     async def datachange_notification(self, node: Node, val, data):
#         if type(val) == float:
#             str_val = "{:.3f}".format(val)
#         elif type(val) == Enum:
#             str_val = val.name
#         else:
#             str_val = str(val)
#         self.callback_method(str_val)


class Model(QObject):
    # define signals here
    command_response = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._scu: scu | None = None
        self._namespace = str(
            os.getenv("DISQ_OPCUA_SERVER_NAMESPACE", "http://skao.int/DS_ICD/")
        )
        self._namespace_index: int | None = None
        self._subscriptions = []
        self.subscription_rate_ms = int(
            os.getenv("DISQ_OPCUA_SUBSCRIPTION_PERIOD_MS", "100")
        )
        self._event_handler_task: asyncio.Task | None = None
        self._event_registrations: dict = {}
        self._event_queue: Queue | None = None

    def connect(
        self,
        server_uri: str,
    ):
        print(f"Connecting to server: {server_uri}")
        self._scu = scu(host=server_uri, namespace=self._namespace)
        print("Getting node list")
        self._scu.get_node_list()

    def disconnect(self):
        if self._scu is not None:
            self._scu.unsubscribe_all()
            self._scu.disconnect()
            del self._scu
            self._scu = None
            self._event_queue.close()
            self._event_handler_task.cancel()

    def is_connected(self) -> bool:
        return (
            self._scu is not None
        )  # TODO: MAJOR assumption here: OPC-UA is connected if scu is instantiated...

    def register_event_updates(self, registrations: dict) -> None:
        _queue = Queue()
        self._event_queue = _queue
        _ = self._scu.subscribe(
            registrations.keys(),
            period=self.subscription_rate_ms,
            data_queue=_queue.sync_q,
        )
        self._event_handler_task = asyncio.create_task(
            self._handle_event_updates(_queue)
        )

    async def _handle_event_updates(self, queue: Queue) -> None:
        while not queue.closed:
            try:
                _event: dict = await queue.async_q.get()
            except RuntimeError as e:
                print(f"Queue presumably closed. RuntimeError: {e}")
                continue
            # The event update dict contains:
            # { 'name': name, 'node': node, 'value': value,
            #   'source_timestamp': source_timestamp,
            #   'server_timestamp': server_timestamp,
            #   'data': data
            # }
            _widget_update_func = self._event_registrations[_event["name"]]
            _widget_update_func(_event["value"])

    # def register_monitor(self, ui_name: str, monitor_callback: callable):
    #     """Register a callback and start subscription to data changes on the named variable

    #     ui_name is the UI string name form
    #     monitor_callback is a callback method that the subscription must call with the update
    #     """
    #     monitor_callback("registering...")
    #     # opcua_node_path:list = self.plc_prog_path + self.get_node_browse_name(self.ui_name_to_opcua_name(ui_name))
    #     opcua_node_path: list = self.plc_prog_path + self.get_node_browse_name(
    #         ui_name.split("/")
    #     )
    #     print("Registering OPC-UA node: ", opcua_node_path)

    #     try:
    #         opcua_node = await self._client.nodes.objects.get_child(opcua_node_path)
    #     except ua.UaError as e:
    #         print(
    #             f'WARNING: no OPCUA object named "{ui_name}" found on server. Skipping subscription. ERROR: {e}'
    #         )
    #         return
    #     handler = SubscriptionHandler(monitor_callback, ui_name)
    #     subscription = await self._client.create_subscription(
    #         self.subscription_rate_ms, handler
    #     )
    #     await subscription.subscribe_data_change(opcua_node)
    #     self._subscriptions.append(subscription)

    # async def call_method(
    #     self, object_name: str, method_name: str, *args: typing.Any
    # ) -> tuple:
    #     obj_browse_path = self.plc_prog_path + [self.get_node_browse_name(object_name)]
    #     method_browse_name = self.get_node_browse_name(method_name)
    #     print(f"Object: {obj_browse_path} method: {method_browse_name}")
    #     obj = await self._client.nodes.objects.get_child(obj_browse_path)
    #     return_code = await obj.call_method(method_browse_name, *args)
    #     return_msg = ua.CmdResponseType(return_code).name
    #     return return_code, return_msg
