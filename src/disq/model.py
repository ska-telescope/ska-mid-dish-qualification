import logging
import os
from functools import cached_property
from pathlib import Path
from queue import Empty, Queue

from asyncua import ua
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from disq.logger import Logger
from disq.sculib import scu

logger = logging.getLogger("gui.model")
# class SubscriptionHandler:
#     def __init__(self, callback_method: callable, ui_name: str) -> None:
#         self.callback_method = callback_method
#         self.ui_name = ui_name

#     async def datachange_notification(self, node: Node, val, data):
#         if type(val) == float:
#             str_val = f"{val:.3f}"
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
        logger.debug(
            "QueuePollThread: Starting queue poll thread"
            f"{QThread.currentThread()}({int(QThread.currentThreadId())})"
        )
        while self._running:
            try:
                data = self.queue.get(timeout=0.2)
            except Empty:
                continue
            logger.debug(f"QueuePollThread: Got data: {data['name']} = {data['value']}")
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
        self._data_logger: Logger | None = None
        self._recording_config: list[str] = []
        self._namespace = str(
            os.getenv("DISQ_OPCUA_SERVER_NAMESPACE", "http://skao.int/DS_ICD/")
        )
        self._endpoint = str(
            os.getenv("DISQ_OPCUA_SERVER_ENDPOINT", "/dish-structure/server")
        )
        self._namespace_index: int | None = None
        self._subscriptions: list = []
        self.subscription_rate_ms = int(
            os.getenv("DISQ_OPCUA_SUBSCRIPTION_PERIOD_MS", "100")
        )
        self._event_q_poller: QueuePollThread | None = None

    def connect(self, connect_details: dict) -> None:
        """
        Connects to the server using the provided connection details.

        Args:
            connect_details (dict): A dictionary containing the connection details.
                connect_details should contain the disq.sculib.scu class initialization parameters as keys: 'host' and 'port' are required.
                'namespace', 'endpoint', 'auth_user', 'auth_password' are optional and can be None.

        Raises:
            RuntimeError: If an error occurs while creating the sculib object (after which the connection is cleaned up and the scu object is set to None)

        Returns:
            None
        """
        logger.debug("Connecting to server: %s", connect_details)
        try:
            self._scu = scu(
                **connect_details,
            )
        except RuntimeError as e:
            logger.debug(
                "Exception while creating sculib object server "
                "(cleaning up scu object): %s",
                e,
            )
            del self._scu
            self._scu = None
            raise e
        logger.debug("Connected to server on URI: %s", self.get_server_uri())
        logger.debug("Getting node list")
        self._scu.get_node_list()

    def get_server_uri(self) -> str:
        if self._scu is None:
            return ""
        return self._scu.connection.server_url.geturl()

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
            logger.warning("Model: register_event_updates: scu is None!?!?!")

    def run_opcua_command(self, command: str, *args) -> tuple:
        if self._scu is None:
            raise RuntimeError("server not connected")
        if command in [
            "Management.Stop",
            "Management.Activate",
            "Management.DeActivate",
            "Management.Reset",
            "Management.Slew2AbsSingleAx",
        ]:
            # Commands that take a single AxisSelectType parameter input
            try:
                arg = ua.AxisSelectType[args[0]]
            except AttributeError:
                logger.warning(
                    "OPC-UA server has no 'AxisSelectType' enum. Attempting a guess."
                )
                arg = {"Az": 0, "El": 1, "Fi": 2, "AzEl": 3}[args[0]]
            logger.debug(f"Model: run_opcua_command: {command}({arg}) type:{type(arg)}")
            result = self._scu.commands[command](arg, *args[1:])
        elif command == "Management.Move2Band":
            try:
                arg = ua.BandType[args[0]]
            except AttributeError:
                logger.warning(
                    "OPC-UA server has no 'BandType' enum. Attempting a guess."
                )
                arg = {
                    "Band_1": 0,
                    "Band_2": 1,
                    "Band_3": 2,
                    "Band_4": 3,
                    "Band_5a": 4,
                    "Band_5b": 5,
                    "Optical": 6,
                }[args[0]]
            logger.debug(f"Model: run_opcua_command: {command}({arg}) type:{type(arg)}")
            result = self._scu.commands[command](arg)
        else:
            # Commands that take none or more parameters of base types: float,bool,etc.
            result = self._scu.commands[command](*args)
        return result

    @cached_property
    def opcua_enum_types(self) -> dict:
        result = {}
        missing_types = []
        for opcua_type in [
            "AxisStateType",
            "DscStateType",
            "StowPinStatusType",
            "AxisSelectType",
            "DscCmdAuthorityType",
            "BandType",
            "DscTimeSourceType",
            "InterpolType",
            "LoadModeType",
            "SafetyStateType",
            "TiltOnType",
        ]:
            try:
                result.update({opcua_type: getattr(ua, opcua_type)})
            except AttributeError:
                missing_types.append(opcua_type)
        if missing_types:
            logger.warning(
                "OPC-UA server does not implement the following Enumerated types "
                "as expected: %s",
                str(missing_types),
            )
        return result

    @cached_property
    def opcua_attributes(self) -> list[str]:
        if self._scu is None:
            return []
        result = self._scu.attributes.keys()
        return result

    def load_track_table(self, filename: Path) -> None:
        if self._scu is None:
            raise RuntimeError("Server not connected")
        logger.debug("Loading track table from file: %s", filename.absolute())
        self._scu.track_table_reset_and_upload_from_file(str(filename.absolute()))

    def start_recording(self, filename: Path) -> None:
        if self._scu is None:
            raise RuntimeError("Server not connected")
        if self._data_logger is not None:
            raise RuntimeError("Data logger already exist")
        logger.debug(f"Creating Logger and file: {filename.absolute()}")
        self._data_logger = Logger(str(filename.absolute()), self._scu)
        self._data_logger.add_nodes(
            self.recording_config,
            period=50,
        )
        self._data_logger.start()
        logger.debug("Logger recording started")

    def stop_recording(self) -> None:
        if self._data_logger is not None:
            logger.debug("stopping recording")
            self._data_logger.stop()
            self._data_logger.wait_for_completion()
            self._data_logger = None

    @property
    def recording_config(self) -> list[str]:
        return self._recording_config

    @recording_config.setter
    def recording_config(self, config: list[str]) -> None:
        self._recording_config = config
