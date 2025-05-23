"""DiSQ GUI model."""

import logging
from asyncio import exceptions as asyncexc
from datetime import datetime
from enum import IntEnum
from functools import cached_property
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Final, Type

from asyncua.ua import UaStatusCodeError
from PySide6.QtCore import QObject, QThread, Signal, SignalInstance
from ska_mid_dish_steering_control.sculib import AttrDict, CmdDict

from ska_mid_disq import CmdReturn, Command, ResultCode, __version__
from ska_mid_disq.constants import (
    SUBSCRIPTION_RATE_MS,
    USER_CACHE_DIR,
    NodesStatus,
    PollerType,
    RecordOptions,
    StatusTreeCategory,
)

from .data_logger import DataLogger
from .scu_weather_station import SCUWeatherStation

logger = logging.getLogger("gui.model")

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
    """

    def __init__(self, signal: SignalInstance) -> None:
        """
        Initialize the SignalProcessor object.

        :param signal: The signal to be emitted on event updates.
        """
        super().__init__()
        self.queue: Queue = Queue()
        self.signal = signal
        self._running: bool = False

    def run(self) -> None:
        """
        Run the queue poll thread.

        This method starts a thread that continuously polls a queue for data and emits a
        signal when data is received.
        """
        self._running = True
        logger.debug(
            "QueuePollThread: Starting queue poll thread %s", QThread.currentThread()
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
            self._handle_event(data)

    def _handle_event(self, data: dict) -> None:
        """
        Handle an event.

        This method emits a signal with the data received. This may be overridden in
        subclasses to handle the data differently.

        :param data: The data to be handled.
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

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        category: StatusTreeCategory,
        status_signal: SignalInstance,
        group_signal: SignalInstance,
        global_signal: SignalInstance,
        status_attributes: list[str],
    ) -> None:
        """A class to represent a hierarchy of status attributes.

        :param status_attributes: A list of status attributes with the full dot-notated
            attribute name
        """
        self._category = category
        super().__init__(status_signal)
        self._group_signal: SignalInstance = group_signal
        self._global_signal: SignalInstance = global_signal
        self._status_attribute_full_names: list[str] = status_attributes
        self._status: dict[str, dict[str, str]] = {}
        self._group_summary_status: dict[str, bool] = {}
        self._global_summary_status: bool | None = None

        for attr_full_name in status_attributes:
            group, attr_name = self._attr_group_name(attr_full_name)
            if group not in self._status:
                self._status[group] = {}
            self._status[group].update({attr_name: ""})
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

    def get_all_attributes(self) -> dict[str, list[tuple[str, str, str]]]:
        """Return a dictionary of all attributes and their values.

        Each tuple in the list contains:
            (attribute full name, attribute short name, value)
        """
        retval = {
            group: [
                (attr, value, self.get_attr_full_name(group, attr))
                for attr, value in attrs.items()
            ]
            for group, attrs in self._status.items()
        }
        return retval

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
    ) -> None:
        group, attr_name = self._attr_group_name(attr_full_name)
        self._status[group][attr_name] = value
        # signal an update on the attribute
        logger.warning("Signal update on %s", attr_full_name)
        self.signal.emit(attr_full_name, value, event_server_time)
        self._set_group_error_status(group)

    def _group_has_error(self, group: str) -> bool:
        return "True" in self._status[group].values()

    def _set_group_error_status(self, group):
        group_error_status = self._group_has_error(group)
        # Detect when the group error status changes
        if group_error_status != self._group_summary_status[group]:
            self._group_summary_status[group] = group_error_status
            # signal a group error status change
            self._group_signal.emit(self._category, group, group_error_status)
            logger.debug("signal a group error status change on %s", group)
            self._set_global_error_status()

    def _global_has_error(self) -> bool:
        return True in self._group_summary_status.values()

    def _set_global_error_status(self):
        global_error_status = self._global_has_error()
        if global_error_status != self._global_summary_status:
            self._global_summary_status = global_error_status
            self._global_signal.emit(self._category, global_error_status)

    def _attr_group_name(self, attr_full_name: str) -> tuple[str, str]:
        """Split a full dot-notated attribute name into group and attribute name.

        :param attr_full_name: a dot-notated attribute name
        :return: a tuple of group and attribute name
        """
        group = attr_full_name.split(".")[0]
        attr_name = attr_full_name.split(".")[-1]
        return group, attr_name


# pylint: disable=too-many-instance-attributes,too-many-public-methods
class Model(QObject):
    """
    A class representing a Model.

    :param parent: The parent object of the Model (default is None).
    """

    # define signals here
    command_response = Signal(str)
    data_received = Signal(dict)
    status_attribute_update = Signal(str, str, datetime)
    status_group_update = Signal(int, str, bool)
    status_global_update = Signal(int, bool)
    weather_station_data_received = Signal(dict)
    attribute_graph_data_received = Signal(dict)

    def __init__(self, parent: QObject | None = None) -> None:
        """
        Initialize a new instance of the `Model` class.

        :param parent: The parent object, if any.
        """
        super().__init__(parent)
        self._scu: SCUWeatherStation | None = None
        self._data_logger: DataLogger | None = None
        self._recording = False
        self._recording_config: dict[str, RecordOptions] = {}
        self._graph_config: dict[str, dict[str, bool | int]] = {}
        self._event_q_pollers: dict[PollerType, QueuePollThread] = {}
        self._nodes_status = NodesStatus.NOT_CONNECTED
        self.status_warning_tree: StatusTreeHierarchy | None = None
        self.status_error_tree: StatusTreeHierarchy | None = None

    def connect_server(self, connect_details: dict) -> None:
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
        self._scu = SCUWeatherStation(
            **connect_details,
            nodes_cache_dir=USER_CACHE_DIR,
            app_name=f"DiSQ GUI v{__version__}",
        )
        try:
            self._scu.connect_and_setup()
        except asyncexc.TimeoutError as e:
            msg = "asyncio raised TimeoutError trying to connect to server"
            logger.exception("%s (cleaning up SCU object)", msg)
            self._scu = None
            raise TimeoutError(msg) from e  # OSError
        except UaStatusCodeError as e:
            msg = "OPC-UA server returned an error code during connection and setup"
            logger.exception("%s (cleaning up SCU object)", msg)
            self._scu.disconnect_and_cleanup()
            self._scu = None
            raise RuntimeError(msg) from e
        except RuntimeError:  # Catch any runtime errors
            logger.exception(
                "Caught exception during connect and setup (cleaning up SCU object)"
            )
            self._scu.disconnect_and_cleanup()
            self._scu = None
            raise
        logger.debug("Connected to server on URI: %s", self.get_server_uri())
        self._register_status_event_updates()

    def get_server_uri(self) -> str:
        """
        Get the URI of the server that the client is connected to.

        :return: The URI of the server.
        """
        if self._scu is None:
            return ""
        return self._scu._server_url  # pylint: disable=protected-access

    @property
    def server_version(self) -> str:
        """
        The software/firmware version of the server that the client is connected to.

        :return: the version of the server.
        """
        if self._scu is None:
            return "not connected to server"
        version = self._scu.server_version
        return version if version is not None else "not found on server"

    @property
    def nodes_timestamp(self) -> str:
        """
        Generation timestamp of the PLC_PRG Node tree.

        :return: timestamp in 'yyyy-mm-dd hh:mm:ss' string format.
        """
        if self._scu is None:
            return "not connected to server"
        return self._scu.nodes_timestamp

    def stop_event_q_poller(self, server_type: PollerType) -> None:
        """Stop a specific QueuePollThread."""
        if server_type in self._event_q_pollers:
            self._event_q_pollers[server_type].stop()
            del self._event_q_pollers[server_type]

    def _stop_polling_threads(self) -> None:
        """Stop any running queue polling threads."""
        for event_q_poller in list(self._event_q_pollers.keys()):
            self.stop_event_q_poller(event_q_poller)

        if self.status_warning_tree is not None:
            self.status_warning_tree.stop()
            self.status_warning_tree = None
        if self.status_error_tree is not None:
            self.status_error_tree.stop()
            self.status_error_tree = None

    def disconnect_server(self) -> None:
        """
        Disconnect from the SCU and clean up resources.

        Disconnects from the SCU, unsubscribes from all events, and stops the event
        queue poller.
        """
        self._stop_polling_threads()
        if self._recording:
            self.stop_recording()
        if self._scu is not None:
            self._scu.disconnect_and_cleanup()
            self._scu = None

    def handle_closed_connection(self) -> None:
        """Handle unexpected closed connection."""
        self._stop_polling_threads()
        if self._scu is not None:
            self._scu.cleanup_resources()
            self._scu = None

    def is_connected(self) -> bool:
        """
        Check if the `Model` instance object has a connection to the OPC-UA server.

        :return: True if the object is connected, False otherwise.
        """
        if self._scu is not None:
            return self._scu.is_connected()
        return False

    def register_event_updates(
        self,
        server_type: PollerType,
        registrations: list[str],
        bad_shutdown_callback: Callable[[str], None] | None = None,
    ) -> None:
        """
        Register event updates for specific event registrations.

        :param registrations: A list containing events to subscribe to.
        :param bad_shutdown_callback: will be called if a BadShutdown subscription
            status notification is received, defaults to None.
        """
        if self._scu is not None:
            if server_type is PollerType.OPCUA:
                event_q_poller = QueuePollThread(self.data_received)
            elif server_type is PollerType.WMS:
                event_q_poller = QueuePollThread(self.weather_station_data_received)
            elif server_type is PollerType.GRAPH:
                event_q_poller = self._event_q_pollers.get(
                    server_type, QueuePollThread(self.attribute_graph_data_received)
                )
            else:
                logger.warning("Model: register_event_updates: Unknown origin")
                return

            event_q_poller.start()
            self._event_q_pollers[server_type] = event_q_poller

            _, missing_nodes, bad_nodes = self._scu.subscribe(
                registrations,
                publishing_interval=SUBSCRIPTION_RATE_MS,
                sampling_interval=SUBSCRIPTION_RATE_MS,
                buffer_samples=False,
                data_queue=event_q_poller.queue,
                bad_shutdown_callback=bad_shutdown_callback,
            )
            if server_type is PollerType.OPCUA:
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

    def _register_status_event_updates(self) -> None:
        """Register status event updates."""
        # Create each of the status hiearchy objects
        self.status_warning_tree = StatusTreeHierarchy(
            StatusTreeCategory.WARNING,
            self.status_attribute_update,
            self.status_group_update,
            self.status_global_update,
            self.status_warning_attributes,
        )
        self.status_error_tree = StatusTreeHierarchy(
            StatusTreeCategory.ERROR,
            self.status_attribute_update,
            self.status_group_update,
            self.status_global_update,
            self.status_error_attributes,
        )

        # Create and start each queue poller thread for error/warning status trees
        self.status_warning_tree.start()
        self.status_error_tree.start()
        # subscribe to events with the scu
        if self._scu is not None:
            self._scu.subscribe(
                self.status_warning_attributes,
                publishing_interval=SUBSCRIPTION_RATE_MS,
                sampling_interval=SUBSCRIPTION_RATE_MS,
                buffer_samples=False,
                data_queue=self.status_warning_tree.queue,
            )
            self._scu.subscribe(
                self.status_error_attributes,
                publishing_interval=SUBSCRIPTION_RATE_MS,
                sampling_interval=SUBSCRIPTION_RATE_MS,
                buffer_samples=False,
                data_queue=self.status_error_tree.queue,
            )
        else:
            logger.warning("Model: _register_status_event_updates: scu is None!?!?!")

    def run_opcua_command(self, command: Command, *args: Any) -> CmdReturn:
        """
        Run an OPC-UA command on the server.

        :param command: The command to be executed on the OPC-UA server.
        :param args: Additional arguments to be passed to the command.
        :return: The result of the command execution.
        :raises RuntimeError: If the server is not connected.
        """

        def _log_and_call(command: Command, *args: Any) -> CmdReturn:
            logger.debug("Calling command: %s, args: %s", command.value, args)
            try:
                result = self._scu.commands[command.value](*args)
            except KeyError:
                msg = f"Exception: Key '{command.value}' not found!"
                logger.error(msg)
                result = ResultCode.NOT_EXECUTED, msg, None
            return result

        if self._scu is None:
            raise RuntimeError("server not connected")
        match command:
            # Commands that take a single AxisSelectType parameter input
            case (
                Command.STOP
                | Command.ACTIVATE
                | Command.DEACTIVATE
                | Command.RESET
                | Command.SLEW2ABS_SINGLE_AX
            ):
                axis = self._scu.convert_enum_to_int("AxisSelectType", args[0])
                result = _log_and_call(command, axis, *args[1:])
            case Command.MOVE2BAND | Command.STATIC_PM_SETUP:
                band = self._scu.convert_enum_to_int("BandType", args[0])
                result = _log_and_call(command, band, *args[1:])
            case Command.SET_TIME_SOURCE:
                source = self._scu.convert_enum_to_int("DscTimeSyncSourceType", args[0])
                result = _log_and_call(command, source, *args[1:])
            case Command.PM_CORR_ON_OFF:
                static = args[0]
                tilt = self._scu.convert_enum_to_int("TiltOnType", args[1])
                temperature = args[2]
                band = self._scu.convert_enum_to_int("BandType", args[3])
                result = _log_and_call(command, static, tilt, temperature, band)
            case Command.TILT_CAL_SETUP:
                tilt = self._scu.convert_enum_to_int("TiltOnType", args[0])
                result = _log_and_call(command, tilt, *args[1:])
            case Command.TAKE_AUTH:
                logger.debug("Calling command: %s, args: %s", command.value, args)
                code, msg = self._scu.take_authority(args[0])
                result = code, msg, None
            case Command.RELEASE_AUTH:
                logger.debug("Calling command: %s, args: %s", command.value, args)
                code, msg = self._scu.release_authority()
                result = code, msg, None
            case Command.TRACK_START:
                logger.debug("Calling command: %s, args: %s", command.value, args)
                code, msg = self._scu.start_tracking(*args)
                result = code, msg, None
            # Commands that take none or more parameters of base types: float, bool, etc
            case _:
                result = _log_and_call(command, *args)
        return result

    @property
    def opcua_enum_types(self) -> dict[str, Type[IntEnum]]:
        """
        Retrieve a dictionary of OPC-UA enum types.

        :return: A dictionary mapping OPC-UA enum type names to their corresponding
            value. The value being an enumerated type.
        :raises AttributeError: If any of the required enum types are not found in the
            UA namespace.
        """
        return self._scu.opcua_enum_types

    @property
    def opcua_commands(self) -> CmdDict:
        """
        Dictionary containing the commands in the 'Server' node tree.

        This method retrieves the available command methods from the OPC UA server if
        the connection has been established.

        :return: A dict of OPC UA commands and their methods.
        """
        if self._scu is None:
            return {}
        return self._scu.commands

    def get_command_arguments(self, command: str) -> list[tuple[str, str]] | None:
        """
        Get a list of arguments with their types for a given command name.

        :return: List of tuples with each argument's name and its type, or None if the
            command does not exist.
        """
        if self._scu is None:
            return None
        if command in self._scu.nodes:
            return self._scu.get_command_arguments(self._scu.nodes[command][0])
        return None

    @property
    def opcua_attributes(self) -> AttrDict:
        """
        Dictionary containing the attributes in the 'PLC_PRG' node tree.

        This method retrieves the attributes from the OPC UA server if the connection
        has been established.

        :return: A dict of OPC UA attributes.
        """
        if self._scu is None:
            return {}
        return self._scu.attributes

    def get_attribute_type(self, attribute: str) -> list[str]:
        """
        Get the attribute data type.

        If the type is "Enumeration", the list also contains the associated string
        values.
        """
        if self._scu is None:
            return ["Unknown"]
        return self._scu.get_attribute_data_type(attribute)

    @property
    def opcua_nodes_status(self) -> NodesStatus:
        """Return a status message (Enum) of the OPC UA client's nodes."""
        return self._nodes_status

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def load_track_table(
        self,
        filename: Path,
        mode: str,
        absolute_times: bool,
        additional_offset: float,
        result_callback: Callable[[ResultCode, str], None],
    ) -> tuple[ResultCode, str]:
        """
        Load the track table data from a file.

        :param filename: The path to the file containing the track table data.
        :param mode: 'Append', 'New' or 'Reset'.
        :param absolute_times: Whether the time column is a real time or a relative
            time. Default True.
        :param additional_offset: Add additional time to every point. Only has an
            effect when absolute_times is False. Default 10.1
        :param result_callback: Callback with result code and message when task finishes
        :raises RuntimeError: If the server is not connected.
        :return: The result of attempted track table loading.
        """
        if self._scu is None:
            raise RuntimeError("Server not connected")
        logger.debug("Loading track table from file: %s", filename.absolute())
        return self._scu.load_track_table(
            mode,
            file_name=str(filename.absolute()),
            absolute_times=absolute_times,
            additional_offset=additional_offset,
            result_callback=result_callback,
        )

    def start_recording(self, filename: Path | None) -> Path:
        """
        Start recording data to a specified file.

        :param filename: The path to the file where the data will be recorded.
        :raises RuntimeError: If the server is not connected or if the data logger
            already exists.
        :return: The output file name on successful start.
        """
        if self._scu is None:
            raise RuntimeError("Server not connected")
        if self._data_logger is not None:
            raise RuntimeError("Data logger already exist")
        if filename is not None:
            logger.debug("Creating Logger and file: %s", filename.absolute())
            self._data_logger = DataLogger(self._scu, str(filename.absolute()))
        else:
            self._data_logger = DataLogger(self._scu)

        node_to_record = False
        for node, values in self.recording_config.items():
            if values["record"]:
                self._data_logger.add_nodes(
                    [node], values["period"], values["on_change"]
                )
                node_to_record = True

        if not node_to_record:
            self._data_logger = None
            raise RuntimeError("No attributes selected")

        self._recording = True
        self._data_logger.start()
        logger.debug("Logger recording started")
        return Path(self._data_logger.file)

    def stop_recording(self) -> None:
        """
        Stop recording data.

        This method stops the data recording process if it is currently running.
        """
        if self._data_logger is not None:
            logger.debug("stopping recording")
            self._data_logger.stop()
            self._data_logger = None
            self._recording = False

    @property
    def recording(self) -> bool:
        """
        Whether their is currently a data recording in progress.

        :return: True if a recording has been started and not yet stopped. False
                otherwise.
        """
        return self._recording

    @property
    def recording_config(self) -> dict[str, RecordOptions]:
        """
        Get the recording configuration.

        :return: The recording configuration as a list of OPC-UA parameter names.
        """
        return self._recording_config

    @recording_config.setter
    def recording_config(self, config: dict[str, RecordOptions]) -> None:
        """
        Set the recording configuration.

        :param config: A list of strings specifying which OPC-UA parameters to record.
        """
        self._recording_config = config

    @property
    def graph_config(self) -> dict[str, dict[str, bool | int]]:
        """
        Get the graph configuration.

        :return: The stored graph configuration.
        """
        return self._graph_config

    @graph_config.setter
    def graph_config(self, config: dict[str, dict[str, bool | int]]) -> None:
        """
        Set the graph configuration.

        :param config: A graph configuration to store.
        """
        self._graph_config = config

    def _get_attributes_startswith(self, prefix: str) -> list[str]:
        """
        Get a list of OPC-UA nodes that start with the given prefix.

        :param prefix: The prefix to search for.
        :return: A list of OPC-UA node names.
        """
        return [attr for attr in self._scu.attributes if attr.startswith(prefix)]

    @cached_property
    def status_warning_attributes(self) -> list[str]:
        """
        A list of status warning attributes.

        :return: A list of status warning attributes.
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
        """
        warning_attributes = (
            self._get_attributes_startswith(AZIMUTH_ERROR_STATUS_PREFIX)
            + self._get_attributes_startswith(ELEVATION_ERROR_STATUS_PREFIX)
            + self._get_attributes_startswith(FEEDINDEXER_ERROR_STATUS_PREFIX)
            + self._get_attributes_startswith(MANAGEMENT_ERROR_STATUS_PREFIX)
        )
        return warning_attributes

    # ---------------------
    # Static pointing model
    # ---------------------
    def import_static_pointing_model(self, file_path: Path) -> str | None:
        """
        Import static pointing model parameters from a JSON file.

        The static pointing model is only imported to a variable of the SCU instance,
        and not written to a (possibly) connected DSC.

        :param file_path: Path to the JSON file to load.
        :return: The specified band the model is for, or `None` if the import failed.
        """
        return self._scu.import_static_pointing_model(file_path)

    def export_static_pointing_model(
        self,
        band: str,
        file_path: Path | None = None,
        antenna: str | None = None,
        overwrite: bool = False,
    ) -> None:
        """
        Export current static pointing model parameters of specified band to JSON file.

        :param band: Band name to export.
        :param file_path: Optional path and name of JSON file to write.
        :param antenna: Optional antenna name to store in static pointing model JSON.
        :param overwrite: Whether to overwrite an existing file. Default is False.
        """
        self._scu.export_static_pointing_model(band, file_path, antenna, overwrite)

    def get_static_pointing_value(self, band: str, name: str) -> float | None:
        """
        Get the named static pointing parameters value in the band's model.

        :param band: Band name.
        :param name: Name of the parameter to set.
        :returns:
            - Value of parameter if set.
            - Default 0.0 if not set.
            - NaN if invalid parameter name given.
            - None if band's model is not setup.
        """
        return self._scu.get_static_pointing_value(band, name)

    def read_static_pointing_model(
        self, band: str, antenna: str = "SKAxxx"
    ) -> dict[str, float]:
        """
        Read static pointing model parameters for a specified band from connected DSC.

        The read parameters is stored in SCU's static pointing model dict so changes can
        be made and setup and/or exported again.

        :param band: Band's parameters to read from DSC.
        :param antenna: Target antenna name to store in static pointing model JSON dict.
        :return: A dict of the read static pointing parameters.
        """
        return self._scu.read_static_pointing_model(band, antenna)

    # ---------------
    # Weather Station
    # ---------------
    def weather_station_connect(self, station_details: dict) -> None:
        """Connect a weather station."""
        self._scu.connect_weather_station(**station_details)

    def weather_station_disconnect(self) -> None:
        """Disconnect the weather station."""
        self.stop_event_q_poller(PollerType.WMS)
        self._scu.disconnect_weather_station()

    def weather_station_sensors_update(self, sensors: list[str]) -> None:
        """Update the polled sensors to the input list."""
        if self._scu is not None:
            self._scu.change_weather_station_sensors(sensors)

    def is_weather_station_connected(self) -> bool:
        """
        Check if the `Model` instance object has a connection to a weather station.

        :return: True if the object is connected, False otherwise.
        """
        if self._scu is not None:
            return self._scu.is_weather_station_connected()
        return False

    def weather_station_available_sensors(self) -> list[str]:
        """Return the list of available weather station sensors as attributes names."""
        if self._scu is not None:
            return [
                f"weather.station.{sensor}"
                for sensor in self._scu.list_weather_station_sensors()
            ]
        return []

    def weather_station_attributes(self) -> list[str]:
        """Return the list of configured weather station attributes."""
        if self._scu is not None:
            return self._scu.weather_station_attributes
        return []

    def weather_station_polling_update(self, sensors: list[str]) -> None:
        """
        Change which weather station sensors are polled.

        :param sensors: A list of sensors to poll.
        """
        if self.is_weather_station_connected():
            self._scu.change_weather_station_sensors(sensors)
