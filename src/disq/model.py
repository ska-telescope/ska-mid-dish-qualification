import os
from queue import Queue

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from disq.sculib import scu

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


class QueuePollThread(QThread):
    def __init__(self, queue, signal) -> None:
        super().__init__()
        self.queue: Queue = queue
        self.signal = signal

    def run(self) -> None:
        print(
            f"QueuePollThread: Starting queue poll thread {QThread.currentThread()}({int(QThread.currentThreadId())})"
        )
        while True:
            print("QueuePollThread: Waiting for data")
            data = self.queue.get()
            print(f"QueuePollThread: Got data: {data}")
            self.signal.emit(data)


class Model(QObject):
    # define signals here
    command_response = pyqtSignal(str)
    data_received = pyqtSignal(dict)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._scu: scu | None = None
        self._namespace = str(
            os.getenv("DISQ_OPCUA_SERVER_NAMESPACE", "http://skao.int/DS_ICD/")
        )
        self._namespace_index: int | None = None
        self._subscriptions: list = []
        self.subscription_rate_ms = int(
            os.getenv("DISQ_OPCUA_SUBSCRIPTION_PERIOD_MS", "100")
        )
        self._event_registrations: dict = {}
        self._event_queue: Queue = Queue()
        self._poll_thread = QueuePollThread(self._event_queue, self.data_received)

    def connect(
        self,
        server_uri: str,
    ):
        print(f"Connecting to server: {server_uri}")
        self._scu = scu(host=server_uri, namespace=self._namespace)
        print(f"Connected to server on URI: {self._scu.connection.server_url.geturl()}")
        print("Getting node list")
        self._scu.get_node_list()
        self._poll_thread.start()

    def disconnect(self):
        if self._scu is not None:
            self._scu.unsubscribe_all()
            self._scu.disconnect()
            del self._scu
            self._scu = None
            self._poll_thread.exit()

    def is_connected(self) -> bool:
        return (
            self._scu is not None
        )  # TODO: MAJOR assumption here: OPC-UA is connected if scu is instantiated...

    def register_event_updates(self, registrations: dict) -> None:
        _ = self._scu.subscribe(
            list(registrations.keys()),
            period=self.subscription_rate_ms,
            data_queue=self._event_queue,
        )
        self._event_registrations = registrations
