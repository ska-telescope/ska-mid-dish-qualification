"""DiSQ GUI model."""

import logging
import os
from enum import Enum
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Type

from PyQt6.QtCore import QObject, QThread, pyqtBoundSignal, pyqtSignal

from disq.logger import Logger
from disq.sculib import PACKAGE_VERSION, SCU, Command

logger = logging.getLogger("gui.model")


class QueuePollThread(QThread):
    """
    A class representing a queue poll thread using QThread.

    :param signal: The signal used to communicate data from the thread.
    :type signal: pyqtSignal
    """

    def __init__(self, signal: pyqtBoundSignal) -> None:
        """
        Initialize the SignalProcessor object.

        :param signal: The signal to be processed.
        :type signal: pyqtBoundSignal
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
                "QueuePollThread: Got data: %s = %s",
                data["name"],
                data["value"],
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


class NodesStatus(Enum):
    """Nodes status."""

    NOT_CONNECTED = "Not connected to server"
    VALID = "Nodes valid"
    ATTR_NOT_FOUND = "Client is missing attribute(s). Check log!"
    NODE_INVALID = "Client has invalid attribute(s). Check log!"
    NOT_FOUND_INVALID = "Client is missing and has invalid attribute(s). Check log!"


# pylint: disable=too-many-instance-attributes
class Model(QObject):
    """
    A class representing a Model.

    :param parent: The parent object of the Model (default is None).
    :type parent: QObject
    """

    # define signals here
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
        self.subscription_rate_ms = int(
            os.getenv("DISQ_OPCUA_SUBSCRIPTION_PERIOD_MS", "100")
        )
        self._event_q_poller: QueuePollThread | None = None
        self._nodes_status = NodesStatus.NOT_CONNECTED

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
                gui_app=True,
                app_name=f"DiSQ GUI v{PACKAGE_VERSION}",
            )
            self._scu.connect_and_setup()
        except RuntimeError as e:
            logger.exception(
                "Exception while creating sculib object server (cleaning up SCU object)"
            )
            self._scu.disconnect_and_cleanup()
            self._scu = None
            raise e
        logger.debug("Connected to server on URI: %s", self.get_server_uri())

    def get_server_uri(self) -> str:
        """
        Get the URI of the server that the client is connected to.

        :return: The URI of the server.
        :rtype: str
        """
        if self._scu is None:
            return ""
        return self._scu._server_url  # pylint: disable=protected-access

    @property
    def server_version(self) -> str:
        """
        The software/firmware version of the server that the client is connected to.

        :return: the version of the server.
        :rtype: str
        """
        if self._scu is None:
            return "not connected to server"
        version = self._scu.server_version
        return version if version is not None else "not found on server"

    @property
    def plc_prg_nodes_timestamp(self) -> str:
        """
        Generation timestamp of the PLC_PRG Node tree.

        :return: timestamp in 'yyyy-mm-dd hh:mm:ss' string format.
        :rtype: str
        """
        if self._scu is None:
            return "not connected to server"
        return self._scu.plc_prg_nodes_timestamp

    @property
    def subscribed_nodes_status(self) -> str:
        """
        Status of the expected nodes versus what SCU client has loaded.

        :return: status string.
        :rtype: str
        """
        if self._scu is None:
            return "not connected to server"
        return self._scu.plc_prg_nodes_timestamp

    def disconnect(self):
        """
        Disconnect from the SCU and clean up resources.

        Disconnects from the SCU, unsubscribes from all events, and stops the event
        queue poller.
        """
        if self._scu is not None:
            self._event_q_poller.stop()
            self._event_q_poller = None
            self._scu.disconnect_and_cleanup()
            self._scu = None

    def is_connected(self) -> bool:
        """
        Check if the `Model` instance object has a connection to the OPC-UA server.

        :return: True if the object is connected, False otherwise.
        :rtype: bool
        """
        if self._scu is not None:
            return self._scu.is_connected()
        return False

    def register_event_updates(self, registrations: list[str]) -> None:
        """
        Register event updates for specific event registrations.

        :param registrations: A list containing events to subscribe to.
        :type registrations: list[str]
        """
        self._event_q_poller = QueuePollThread(self.data_received)
        self._event_q_poller.start()

        if self._scu is not None:
            _, missing_nodes, bad_nodes = self._scu.subscribe(
                registrations,
                period=self.subscription_rate_ms,
                data_queue=self._event_q_poller.queue,
            )
            if missing_nodes and not bad_nodes:
                self._nodes_status = NodesStatus.ATTR_NOT_FOUND
            elif not missing_nodes and bad_nodes:
                self._nodes_status = NodesStatus.NODE_INVALID
            elif missing_nodes and bad_nodes:
                self._nodes_status = NodesStatus.NOT_FOUND_INVALID
            else:
                self._nodes_status = NodesStatus.VALID
        else:
            logger.warning("Model: register_event_updates: SCU not initialised yet!")

    def run_opcua_command(
        self, command: Command, *args: Any
    ) -> tuple[int, str, list[int | None] | None]:
        """
        Run an OPC-UA command on the server.

        :param command: The command to be executed on the OPC-UA server.
        :type command: str
        :param args: Additional arguments to be passed to the command.
        :type args: Any
        :return: The result of the command execution.
        :rtype: tuple
        :raises RuntimeError: If the server is not connected.
        """

        def _log_and_call(
            command: Command, *args: Any
        ) -> tuple[int, str, list[int | None] | None]:
            logger.debug("Calling command: %s, args: %s", command.value, args)
            try:
                result = self._scu.commands[command.value](*args)
            except KeyError:
                msg = f"Exception: Key '{command.value}' not found!"
                logger.error(msg)
                result = -1, msg, None
            return result

        if self._scu is None:
            raise RuntimeError("server not connected")
        # Commands that take a single AxisSelectType parameter input
        match command:
            case (
                Command.STOP
                | Command.ACTIVATE
                | Command.DEACTIVATE
                | Command.RESET
                | Command.SLEW2ABS_SINGLE_AX
            ):
                axis = self._scu.convert_enum_to_int("AxisSelectType", args[0])
                result = _log_and_call(command, axis, *args[1:])
            case Command.MOVE2BAND:
                band = self._scu.convert_enum_to_int("BandType", args[0])
                result = _log_and_call(command, band)
            case Command.STATIC_PM_SETUP:
                band = self._scu.convert_enum_to_int("BandType", args[0])
                result = _log_and_call(command, band, *args[1:])
            case Command.PM_CORR_ON_OFF:
                band = self._scu.convert_enum_to_int("BandType", args[3])
                static = args[0]
                tilt = self._scu.convert_enum_to_int("TiltOnType", args[1])
                temperature = args[2]
                result = _log_and_call(command, static, tilt, temperature, band)
            case Command.TAKE_AUTH:
                logger.debug("Calling command: %s, args: %s", command, args)
                code, msg = self._scu.take_authority(args[0])
                result = code, msg, None
            case Command.RELEASE_AUTH:
                logger.debug("Calling command: %s, args: %s", command, args)
                code, msg = self._scu.release_authority()
                result = code, msg, None
            # Commands that take none or more parameters of base types: float, bool, etc
            case _:
                result = _log_and_call(command, *args)
        return result

    @property
    def opcua_enum_types(self) -> dict[str, Type[Enum]]:
        """
        Retrieve a dictionary of OPC-UA enum types.

        :return: A dictionary mapping OPC-UA enum type names to their corresponding
            value. The value being an enumerated type.
        :rtype: dict
        :raises AttributeError: If any of the required enum types are not found in the
            UA namespace.
        """
        return self._scu.opcua_enum_types

    @property
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
        return list(self._scu.attributes.keys())

    @property
    def opcua_nodes_status(self) -> NodesStatus:
        """Return a status message (Enum) of the OPC UA client's nodes."""
        return self._nodes_status

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
        self._data_logger = Logger(self._scu, str(filename.absolute()))
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
