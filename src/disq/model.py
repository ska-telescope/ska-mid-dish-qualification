"""DiSQ GUI model."""

import logging
import os
from functools import cached_property
from pathlib import Path
from queue import Empty, Queue
from typing import Callable

from asyncua import ua
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from disq.logger import Logger
from disq.sculib import SCU

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
    """
    A class representing a queue poll thread using QThread.

    :param signal: The signal used to communicate data from the thread.
    :type signal: pyqtSignal
    """

    def __init__(self, signal) -> None:
        """
        Initialize the SignalProcessor object.

        :param signal: The signal to be processed.
        :type signal: Any
        """
        super().__init__()
        self.queue: Queue = Queue()
        self.signal = signal
        self._running = False

    def run(self) -> None:
        """
        Run the queue poll thread.

        This method starts a thread that continuously polls a queue for data and emits a
        signal when data is received.
        """
        self._running = True
        logger.debug(
            "QueuePollThread: Starting queue poll thread %s(%d)",
            QThread.currentThread(),
            QThread.currentThreadId(),
        )
        while self._running:
            try:
                data = self.queue.get(timeout=0.2)
            except Empty:
                continue
            logger.debug(
                "QueuePollThread: Got data: %s = %s", data["name"], data["value"]
            )
            self.signal.emit(data)

    def stop(self) -> None:
        """
        Stop the thread.

        This method sets the `_running` flag to False and waits for 1 second.
        If the thread does not stop within that time, it is terminated.
        """
        self._running = False
        if not self.wait(1):
            self.terminate()


# pylint: disable=too-many-instance-attributes
class Model(QObject):
    # define signals here
    """
    A class representing a Model.

    :param parent: The parent object of the Model (default is None).
    :type parent: QObject
    :param _scu: An instance of the SCU class or None.
    :type _scu: SCU
    :param _data_logger: An instance of the Logger class or None.
    :type _data_logger: Logger
    :param _recording_config: A list of strings containing recording configurations.
    :type _recording_config: list[str]
    :param _namespace: The namespace for the OPCUA server.
    :type _namespace: str
    :param _endpoint: The endpoint for the OPCUA server.
    :type _endpoint: str
    :param _namespace_index: The index of the namespace or None.
    :type _namespace_index: int
    :param _subscriptions: A list of subscriptions.
    :type _subscriptions: list
    :param subscription_rate_ms: The subscription rate in milliseconds.
    :type subscription_rate_ms: int
    :param _event_q_poller: An instance of QueuePollThread or None.
    :type _event_q_poller: QueuePollThread
    """

    command_response = pyqtSignal(str)
    data_received = pyqtSignal(dict)

    def __init__(self, parent: QObject | None = None) -> None:
        """
        Initialize a new instance of the `Model` class.

        :param parent: The parent object, if any.
        :type parent: QObject or None
        """
        super().__init__(parent)
        self._scu: SCU | None = None
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
        Connect to the server using the provided connection details.

        :param connect_details: A dictionary containing the connection details.
            connect_details should contain the disq.sculib.SCU class initialization
            parameters as keys: 'host' and 'port' are required. 'namespace', 'endpoint',
            'auth_user', 'auth_password' are optional and can be None.
        :raises RuntimeError: If an error occurs while creating the sculib object.
            (after which the connection is cleaned up and the SCU object is set to None)
        """
        logger.debug("Connecting to server: %s", connect_details)
        try:
            self._scu = SCU(
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
        """
        Get the URI of the server that the client is connected to.

        :return: The URI of the server.
        :rtype: str
        """
        if self._scu is None:
            return ""
        return self._scu.connection.server_url.geturl()

    def disconnect(self):
        """
        Disconnect from the SCU and clean up resources.

        Disconnects from the SCU, unsubscribes from all events, and stops the event
        queue poller.
        """
        if self._scu is not None:
            self._scu.unsubscribe_all()
            self._scu.disconnect()
            del self._scu
            self._scu = None
            self._event_q_poller.stop()
            self._event_q_poller = None

    def is_connected(self) -> bool:
        """
        Check if the `Model` instance object has a connection to the OPC-UA server.

        :return: True if the object is connected, False otherwise.
        :rtype: bool
        """
        return (
            self._scu is not None
        )  # TODO: MAJOR assumption here: OPC-UA is connected if scu is instantiated...

    def register_event_updates(self, registrations: dict[str, Callable]) -> None:
        """
        Register event updates for specific event registrations.

        :param registrations: A dictionary containing event registrations where keys are
            the events to subscribe to.
        :type registrations: dict
        """
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

    def _convert_band_to_type(self, band: str) -> int:
        try:
            return ua.BandType[band]
        except AttributeError:
            logger.warning("OPC-UA server has no 'BandType' enum. Attempting a guess.")
            return {
                "Band_1": 0,
                "Band_2": 1,
                "Band_3": 2,
                "Band_4": 3,
                "Band_5a": 4,
                "Band_5b": 5,
                "Band_6": 6,
                "Optical": 7,
            }[band]

    def run_opcua_command(self, command: str, *args) -> tuple[int, str]:
        """
        Run an OPC-UA command on the server.

        :param command: The command to be executed on the OPC-UA server.
        :type command: str
        :param args: Additional arguments to be passed to the command.
        :type args: tuple
        :return: The result of the command execution.
        :rtype: tuple
        :raises RuntimeError: If the server is not connected.
        """
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
            logger.debug(
                "Model: run_opcua_command: %s, args: %d, %r", command, arg, args[1:]
            )
            result = self._scu.commands[command](arg, *args[1:])
        elif command == "Management.Move2Band":
            band = self._convert_band_to_type(args[0])
            logger.debug("Model: run_opcua_command:  %s(%d)", command, band)
            result = self._scu.commands[command](band)
        elif command == "Pointing.PmCorrOnOff":
            band = self._convert_band_to_type(args[3])
            logger.debug(
                "Model: run_opcua_command:  %s, args: %r %d", command, *args[:3], band
            )
            static = args[0]
            try:
                tilt = ua.TiltOnEnumType[args[1]]
            except AttributeError:
                logger.warning(
                    "OPC-UA server has no 'TiltOnEnumType' enum. Attempting a guess."
                )
                arg = {"Off": 0, "TiltmeterOne": 1, "TiltmeterTwo": 2}[args[1]]
            temperature = args[2]
            result = self._scu.commands[command](static, tilt, temperature, band)
        else:
            # Commands that take none or more parameters of base types: float,bool,etc.
            logger.debug("Model: run_opcua_command: %s, args: %r", command, args)
            result = self._scu.commands[command](*args)
        return result

    @cached_property
    def opcua_enum_types(self) -> dict:
        """
        Retrieve a dictionary of OPC-UA enum types.

        :return: A dictionary mapping OPC-UA enum type names to their corresponding
            value. The value being an enumerated type.
        :rtype: dict
        :raises AttributeError: If any of the required enum types are not found in the
            UA namespace.
        """
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
        """
        Return the OPC UA attributes associated with the object.

        This method retrieves the attributes from the OPC UA server if the connection
        has been established.

        :return: A list of OPC UA attribute names.
        :rtype: list[str]
        """
        if self._scu is None:
            return []
        result = self._scu.attributes.keys()
        return result

    def load_track_table(self, filename: Path) -> None:
        """
        Load the track table data from a file.

        :param filename: The path to the file containing the track table data.
        :type filename: Path
        :raises RuntimeError: If the server is not connected.
        """
        if self._scu is None:
            raise RuntimeError("Server not connected")
        logger.debug("Loading track table from file: %s", filename.absolute())
        self._scu.track_table_reset_and_upload_from_file(str(filename.absolute()))

    def start_recording(self, filename: Path) -> None:
        """
        Start recording data to a specified file.

        :param filename: The path to the file where the data will be recorded.
        :type filename: Path
        :raises RuntimeError: If the server is not connected or if the data logger
            already exists.
        """
        if self._scu is None:
            raise RuntimeError("Server not connected")
        if self._data_logger is not None:
            raise RuntimeError("Data logger already exist")
        logger.debug("Creating Logger and file: %s", filename.absolute())
        self._data_logger = Logger(str(filename.absolute()), self._scu)
        self._data_logger.add_nodes(
            self.recording_config,
            period=50,
        )
        self._data_logger.start()
        logger.debug("Logger recording started")

    def stop_recording(self) -> None:
        """
        Stop recording data.

        This method stops the data recording process if it is currently running.
        """
        if self._data_logger is not None:
            logger.debug("stopping recording")
            self._data_logger.stop()
            self._data_logger.wait_for_completion()
            self._data_logger = None

    @property
    def recording_config(self) -> list[str]:
        """
        Get the recording configuration.

        :return: The recording configuration as a list of OPC-UA parameter names.
        :rtype: list[str]
        """
        return self._recording_config

    @recording_config.setter
    def recording_config(self, config: list[str]) -> None:
        """
        Set the recording configuration.

        :param config: A list of strings specifying which OPC-UA parameters to record.
        :type config: list[str]
        """
        self._recording_config = config
