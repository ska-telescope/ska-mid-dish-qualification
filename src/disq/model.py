"""DiSQ GUI model."""

import logging
import os
from datetime import datetime
from functools import cached_property
from pathlib import Path
from queue import Empty, Queue
from typing import Final

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

# Constant definitions of attribute names on the OPC-UA server
AZIMUTH_WARNING_STATUS_PREFIX: Final[str] = "Azimuth.WarningStatus.wa"
ELEVATION_WARNING_STATUS_PREFIX: Final[str] = "Elevation.WarningStatus.wa"
FEEDINDEXER_WARNING_STATUS_PREFIX: Final[str] = "FeedIndexer.WarningStatus.wa"
MANAGEMENT_WARNING_STATUS_PREFIX: Final[str] = "Management.WarningStatus.wa"
AZIMUTH_ERROR_STATUS_PREFIX: Final[str] = "Azimuth.ErrorStatus.err"
ELEVATION_ERROR_STATUS_PREFIX: Final[str] = "Elevation.ErrorStatus.err"
FEEDINDEXER_ERROR_STATUS_PREFIX: Final[str] = "FeedIndexer.ErrorStatus.err"
MANAGEMENT_ERROR_STATUS_PREFIX: Final[str] = "Management.ErrorStatus.err"


class QueuePollThread(QThread):
    """
    A class representing a queue poll thread using QThread.

    :param signal: The signal used to communicate data from the thread.
    :type signal: pyqtSignal
    """

    def __init__(self, signal) -> None:
        """
        Initialize the SignalProcessor object.

        :param signal: The signal to be emitted on event updates.
        :type signal: pyqtSignal
        """
        super().__init__()
        self.queue: Queue = Queue()
        self.signal: pyqtSignal = signal
        self._running: bool = False

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
            self._handle_event(data)

    def _handle_event(self, data: dict) -> None:
        """
        Handle an event.

        This method emits a signal with the data received. This may be overridden in
        subclasses to handle the data differently.

        :param data: The data to be handled.
        :type data: dict
        """
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


class StatusTreeHierarchy(QueuePollThread):
    """A class to represent a hierarchy of status attributes."""

    def __init__(self, status_signal, group_signal, status_attributes: list[str]):
        """A class to represent a hierarchy of status attributes.

        :param status_attributes: A list of status attributes with the full dot-notated
                                  attribute name
        :type status_attributes: list[str]
        """
        super().__init__(status_signal)
        self._group_signal: pyqtSignal = group_signal
        self._status_attribute_full_names: list[str] = status_attributes
        self._status: dict[str, dict[str, str]] = {}
        self._group_summary_status: dict[str, bool] = {}

        for attr_full_name in status_attributes:
            group, attr_name = self._attr_group_name(attr_full_name)
            if group not in self._status:
                self._status[group] = {}
            self._status[group].update({attr_name: None})
        for group, _ in self._status.items():
            self._group_summary_status[group] = None

    @property
    def attribute_names(self) -> list[str]:
        """A list of all status attribute names.

        Names are returned in the list as full dot-notated attribute names
        """
        return self._status_attribute_full_names

    @property
    def groups(self) -> list[str]:
        """A list of all group names."""
        return list(self._status.keys())

    def get_group(self, group: str) -> dict[str, str]:
        """Return a dictionary of attribute names and their values for a group."""
        return self._status.get(group, {})

    def get_attr_full_name(self, group: str, attr_name: str) -> str | None:
        """Return the full dot-notated attribute name."""
        for attr_full_name in self._status_attribute_full_names:
            if attr_full_name.startswith(group) and attr_full_name.endswith(attr_name):
                return attr_full_name
        raise KeyError(f"Attribute {attr_name} not found in group {group}")

    def _handle_event(self, data: dict) -> None:
        """Override the QueuePollThread base class event handler."""
        attribute_name = str(data["name"])
        # convert the value boolean or None to a string
        attribute_value = str(data["value"]) if data["value"] is not None else ""
        event_server_time = data["source_timestamp"]
        logger.debug(
            "DATA: name=%s val=%s, time=%s",
            attribute_name,
            attribute_value,
            str(event_server_time),
        )
        self._update_attribute_status(
            attribute_name, attribute_value, event_server_time
        )

    def _update_attribute_status(
        self, attr_full_name: str, value: str, event_server_time: datetime
    ):
        group, attr_name = self._attr_group_name(attr_full_name)
        self._status[group][attr_name] = value
        # signal an update on the attribute
        logger.warning("Signal update on %s", attr_full_name)
        self.signal.emit(attr_full_name, value, event_server_time)
        self._set_group_error_status(group)

    def _group_has_error(self, group: str) -> bool:
        return "true" in self._status[group].values()

    def _set_group_error_status(self, group):
        group_error_status = self._group_has_error(group)
        # Detect when the group error status changes
        if group_error_status != self._group_summary_status[group]:
            self._group_summary_status[group] = group_error_status
            # signal a group error status change
            self._group_signal.emit(group, group_error_status)
            logger.debug("signal a group error status change on %s", group)

    def _attr_group_name(self, attr_full_name: str) -> tuple[str, str]:
        """Split a full dot-notated attribute name into group and attribute name.

        :param attr_full_name: a dot-notated attribute name
        :type attr_full_name: str
        :return: a tuple of group and attribute name
        :rtype: tuple[str, str]
        """
        group = attr_full_name.split(".")[0]
        attr_name = attr_full_name.split(".")[-1]
        return group, attr_name


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
    status_attribute_update = pyqtSignal(str, str, datetime)
    status_group_update = pyqtSignal(str, bool)

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

        self._status_warning_tree: StatusTreeHierarchy | None = None
        self._status_error_tree: StatusTreeHierarchy | None = None

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
            self._scu = SCU(**connect_details, gui_app=True)
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
        self._register_status_event_updates()

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
        if self._scu is not None:
            return self._scu.is_connected()
        return False

    def register_event_updates(self, registrations: list[str]) -> None:
        """
        Register event updates for specific event registrations.

        A new event poller thread will be started if one is not already running.

        :param registrations: A list of attribute names to register for event updates.
        :type registrations: list[str]
        """
        if self._event_q_poller is None:
            self._event_q_poller = QueuePollThread(self.data_received)
            self._event_q_poller.start()

        if self._scu is not None:
            _ = self._scu.subscribe(
                registrations,
                period=self.subscription_rate_ms,
                data_queue=self._event_q_poller.queue,
            )
        else:
            logger.warning("Model: register_event_updates: scu is None!?!?!")

    def _register_status_event_updates(self) -> None:
        """Register status event updates."""
        # Create each of the status hiearchy objects
        self._status_warning_tree = StatusTreeHierarchy(
            self.status_attribute_update,
            self.status_group_update,
            self.status_warning_attributes,
        )
        self._status_error_tree = StatusTreeHierarchy(
            self.status_attribute_update,
            self.status_group_update,
            self.status_error_attributes,
        )

        # Create and start each queue poller thread for error/warning status trees
        self._status_warning_tree.start()
        self._status_error_tree.start()
        # subscribe to events with the scu
        if self._scu is not None:
            _ = self._scu.subscribe(
                self.status_warning_attributes,
                period=self.subscription_rate_ms,
                data_queue=self._status_error_tree.queue,
            )
            _ = self._scu.subscribe(
                self.status_error_attributes,
                period=self.subscription_rate_ms,
                data_queue=self._status_error_tree.queue,
            )
        else:
            logger.warning("Model: _register_status_event_updates: scu is None!?!?!")

    def convert_band_to_type(self, band: str) -> int:
        """
        Convert string to BandType enum (integer value).

        :param band: the band to convert to enum
        :type band: str
        :return: BandType enum integer value
        :rtype: int
        """
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

    def run_opcua_command(
        self, command: str, *args
    ) -> tuple[int, str, list[int | None] | None]:
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

        def _log_and_call(command, *args) -> tuple[int, str, list[int | None] | None]:
            logger.debug("Model: run_opcua_command: %s, args: %s", command, args)
            return self._scu.commands[command](*args)

        if self._scu is None:
            raise RuntimeError("server not connected")
        if command in [
            "Management.Commands.Stop",
            "Management.Commands.Activate",
            "Management.Commands.DeActivate",
            "Management.Commands.Reset",
            "Management.Commands.Slew2AbsSingleAx",
        ]:
            # Commands that take a single AxisSelectType parameter input
            try:
                axis = ua.AxisSelectType[args[0]]
            except AttributeError:
                logger.warning(
                    "OPC-UA server has no 'AxisSelectType' enum. Attempting a guess."
                )
                axis = {"Az": 0, "El": 1, "Fi": 2, "AzEl": 3}[args[0]]
            result = _log_and_call(command, axis, *args[1:])
        elif command == "Management.Commands.Move2Band":
            band = self.convert_band_to_type(args[0])
            result = _log_and_call(command, band)
        elif command == "Pointing.Commands.StaticPmSetup":
            band = self.convert_band_to_type(args[0])
            result = _log_and_call(command, band, *args[1:])
        elif command == "Pointing.Commands.PmCorrOnOff":
            band = self.convert_band_to_type(args[3])
            static = args[0]
            try:
                tilt = ua.TiltOnType[args[1]]
            except AttributeError:
                logger.warning(
                    "OPC-UA server has no 'TiltOnType' enum. Attempting a guess."
                )
                tilt = {"Off": 0, "TiltmeterOne": 1, "TiltmeterTwo": 2}[args[1]]
            temperature = args[2]
            result = _log_and_call(command, static, tilt, temperature, band)
        elif command == "CommandArbiter.Commands.TakeAuth":
            logger.debug("Model: run_opcua_command: %s, args: %s", command, args)
            code, msg = self._scu.take_authority(args[0])
            result = code, msg, None
        elif command == "CommandArbiter.Commands.ReleaseAuth":
            logger.debug("Model: run_opcua_command: %s, args: %s", command, args)
            code, msg = self._scu.release_authority()
            result = code, msg, None
        else:
            # Commands that take none or more parameters of base types: float,bool,etc.
            result = _log_and_call(command, *args)
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
            "DscTimeSyncSourceType",
            "InterpolType",
            "LoadEnumType",
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

    def _get_attributes_startswith(self, prefix: str) -> list[str]:
        """
        Get a list of OPC-UA nodes that start with the given prefix.

        :param prefix: The prefix to search for.
        :type prefix: str
        :return: A list of OPC-UA node names.
        :rtype: list[str]
        """
        return [attr for attr in self._scu.attributes if attr.startswith(prefix)]

    @cached_property
    def status_warning_attributes(self) -> list[str]:
        """
        A list of status warning attributes.

        :return: A list of status warning attributes.
        :rtype: list[str]
        """
        warning_attributes = (
            self._get_attributes_startswith(AZIMUTH_WARNING_STATUS_PREFIX)
            + self._get_attributes_startswith(ELEVATION_WARNING_STATUS_PREFIX)
            + self._get_attributes_startswith(FEEDINDEXER_WARNING_STATUS_PREFIX)
            + self._get_attributes_startswith(MANAGEMENT_WARNING_STATUS_PREFIX)
        )
        return warning_attributes

    @cached_property
    def status_error_attributes(self) -> list[str]:
        """
        A list of status error attributes.

        :return: A list of status warning attributes.
        :rtype: list[str]
        """
        warning_attributes = (
            self._get_attributes_startswith(AZIMUTH_ERROR_STATUS_PREFIX)
            + self._get_attributes_startswith(ELEVATION_ERROR_STATUS_PREFIX)
            + self._get_attributes_startswith(FEEDINDEXER_ERROR_STATUS_PREFIX)
            + self._get_attributes_startswith(MANAGEMENT_ERROR_STATUS_PREFIX)
        )
        return warning_attributes
