import os
from queue import Empty, Queue

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
    def __init__(self, signal) -> None:
        super().__init__()
        self.queue: Queue = Queue()
        self.signal = signal
        self._running = False

    def run(self) -> None:
        self._running = True
        print(
            "QueuePollThread: Starting queue poll thread"
            f"{QThread.currentThread()}({int(QThread.currentThreadId())})"
        )
        while self._running:
            try:
                data = self.queue.get(timeout=0.2)
            except Empty:
                continue
            print(f"QueuePollThread: Got data: {data}")
            self.signal.emit(data)

    def stop(self) -> None:
        self._running = False
        if not self.wait(1):
            self.terminate()


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
        self._event_q_poller: QueuePollThread | None = None

    def connect(
        self,
        server_uri: str,
    ):
        print(f"Connecting to server: {server_uri}")
        self._scu = scu(host=server_uri, namespace=self._namespace)
        print(f"Connected to server on URI: {self._scu.connection.server_url.geturl()}")
        print("Getting node list")
        self._scu.get_node_list()

    def disconnect(self):
        if self._scu is not None:
            self._scu.unsubscribe_all()
            self._scu.disconnect()
            del self._scu
            self._scu = None
            self._event_q_poller.stop()
            self._event_q_poller = None

    def is_connected(self) -> bool:
        return (
            self._scu is not None
        )  # TODO: MAJOR assumption here: OPC-UA is connected if scu is instantiated...

    def register_event_updates(self, registrations: dict) -> None:
        self._event_q_poller = QueuePollThread(self.data_received)
        self._event_q_poller.start()

        if self._scu is not None:
            _ = self._scu.subscribe(
                list(registrations.keys()),
                period=self.subscription_rate_ms,
                data_queue=self._event_q_poller.queue,
            )
        else:
            print("Model: WARNING register_event_updates: scu is None!?!?!")

    def run_opcua_command(self, command: str, *args) -> tuple:
        if self._scu is not None:
            result = self._scu.commands[command](*args)
        else:
            print("Model: WARNING run_opcua_command: scu is None!?!?!")
        return result
