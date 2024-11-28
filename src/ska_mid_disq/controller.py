"""DiSQ GUI controller."""

import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QCoreApplication, QObject, pyqtSignal

from ska_mid_disq import Command, ResultCode, configuration, model
from ska_mid_disq.constants import ServerType

logger = logging.getLogger("gui.controller")

_LOCAL_DIR_CONFIGFILE = "disq.ini"


# pylint: disable=too-many-public-methods
class Controller(QObject):
    """
    Controller for managing server connections and issuing commands.

    :param mvc_model: The model object that the controller interacts with.
    :param parent: The parent object, if any.
    """

    ui_status_message = pyqtSignal(str)
    server_connected = pyqtSignal()
    server_disconnected = pyqtSignal()
    recording_status = pyqtSignal(bool)
    weather_station_connected = pyqtSignal()
    weather_station_disconnected = pyqtSignal()

    def __init__(self, mvc_model: model.Model, parent: QObject | None = None) -> None:
        """
        Initialize a new instance of the `Controller` class.

        :param mvc_model: A `model.Model` object.
        :param parent: An optional `QObject` object or None.
        """
        super().__init__(parent)
        self._model = mvc_model

    def _command_response_str(
        self, command: str, result_code: int, result_msg: str
    ) -> str:
        """
        Generate a response message based on the result of issuing a command.

        :param command: The command that was executed.
        :param result_code: The result code of the command execution.
        :param result_msg: The message associated with the result code.
        :return: The response message containing the command, result code, and result
            message.
        """
        r = f"Command: {command}; Response: {result_msg} [{result_code}]"
        self.emit_ui_status_message("INFO", r)
        return r

    def emit_ui_status_message(self, severity: str, message: str) -> None:
        """
        Emit a status message to the UI.

        Severity is one of: INFO, WARNING, ERROR
        """
        sevr_symbol = ""
        if severity == "INFO":
            sevr_symbol = "ℹ️"
            logger.info("UI status msg: %s %s", sevr_symbol, message)
        elif severity == "WARNING":
            sevr_symbol = "⚠️"
            logger.warning("UI status msg: %s %s", sevr_symbol, message)
        elif severity == "ERROR":
            sevr_symbol = "⛔️"
            logger.error("UI status msg: %s %s", sevr_symbol, message)
        else:
            logger.debug(message)
        self.ui_status_message.emit(f"{sevr_symbol} {message}")

    def get_config_servers(self) -> list[str]:
        """
        Get the list of servers found in the configuration file.

        :return: A list of server names.
        :raises FileNotFoundError: If the configuration file is not found.
        """
        server_list: list[str] = []
        try:
            server_list = configuration.get_config_server_list(
                config_filename=_LOCAL_DIR_CONFIGFILE
            )
        except FileNotFoundError:
            logger.warning("Unable to find config file")
        return server_list

    def get_config_server_args(self, server_name: str) -> dict[str, str] | None:
        """
        Get the server arguments from the configuration file.

        :param server_name: The name of the server to retrieve arguments for.
        :return: A dictionary containing the server arguments.
        """
        try:
            return configuration.get_config_sculib_args(
                config_filename=_LOCAL_DIR_CONFIGFILE, server_name=server_name
            )
        except FileNotFoundError:
            logger.warning("Unable to find config file")
        except KeyError:
            logger.warning("Specified server not found in the configuration file")
        return None

    def is_server_connected(self) -> bool:
        """
        Check if the server is connected.

        :return: True if the server is connected, False otherwise.
        """
        return self._model.is_connected()

    def connect_server(self, connection_details: dict) -> None:
        """
        Connect to a server using the provided connection details.

        :param connection_details: A dictionary containing server connection details,
            including as a minimum 'host' and 'port' keys.
        :raises ValueError: If the port number provided is not a valid integer.
        :raises OSError: If an OS level error occurs during the connection.
        :raises RuntimeError: If a runtime error occurs during the connection.
        """
        self.emit_ui_status_message("INFO", "Connecting to server...")
        try:
            connection_details["port"] = int(connection_details["port"].strip())
        except ValueError:
            self.emit_ui_status_message(
                "ERROR",
                f"Invalid port number, should be integer: {connection_details['port']}",
            )
            return
        QCoreApplication.processEvents()
        try:
            self._model.connect(connection_details)
        except (OSError, RuntimeError) as e:
            self.emit_ui_status_message(
                "ERROR", f"Unable to connect to server. Error: {e}"
            )
            self.server_disconnected.emit()
            return
        self.emit_ui_status_message(
            "INFO", f"Connected to server: {self._model.get_server_uri()}"
        )
        self.server_connected.emit()

    def disconnect_server(self):
        """
        Disconnect from the server.

        This method disconnects from the server, emits a status message signal, and
        emits a server disconnected signal.
        """
        self._model.disconnect()
        self.emit_ui_status_message("INFO", "Disconnected from server")
        self.server_disconnected.emit()

    def subscribe_opcua_updates(self, registrations: list[str]) -> None:
        """
        Subscribe to the requested OPC UA variable data updates with the given callback.

        :param registrations: A list containing events to subscribe to.
        """
        self._model.register_event_updates(
            ServerType.OPCUA, registrations, self._handle_closed_connection
        )

    def command_slew2abs_azim_elev(
        self,
        azimuth_position: float,
        elevation_position: float,
        azimuth_velocity: float,
        elevation_velocity: float,
    ) -> None:
        """
        Issue command to slew to absolute azimuth and elevation positions.

        :param azimuth_position: The azimuth position to slew to (in degrees).
        :param elevation_position: The elevation position to slew to (in degrees).
        :param azimuth_velocity: The azimuth velocity for slewing (in degrees per
            second).
        :param elevation_velocity: The elevation velocity for slewing (in degrees per
            second).
        """
        self._issue_command(
            Command.SLEW2ABS_AZ_EL,
            azimuth_position,
            elevation_position,
            azimuth_velocity,
            elevation_velocity,
        )

    def command_slew_single_axis(
        self, axis: str, position: float, velocity: float
    ) -> None:
        """
        Issue command to slew a single axis to a specific position with given velocity.

        :param axis: The axis identifier.
        :param position: The target position to slew to.
        :param velocity: The velocity at which to slew.
        """
        self._issue_command(Command.SLEW2ABS_SINGLE_AX, axis, position, velocity)

    def command_activate(self, axis: str = "AzEl") -> None:
        """
        Issue command to activate a specific axis.

        :param axis: The axis to activate (default is 'AzEl').
        """
        self._issue_command(Command.ACTIVATE, axis)

    def command_deactivate(self, axis: str = "AzEl") -> None:
        """
        Issue command to deactivate a specific axis.

        :param axis: The axis to deactivate (default is 'AzEl').
        """
        self._issue_command(Command.DEACTIVATE, axis)

    def command_stop(self, axis: str = "AzEl") -> None:
        """
        Issue command to stop a specific axis movement.

        :param axis: The axis for which the movement should be stopped. Default is
            'AzEl'.
        """
        self._issue_command(Command.STOP, axis)

    def command_stow(self, stow: bool = True) -> None:
        """
        Issue command to stow or unstow the device.

        :param stow: A flag indicating whether to stow or unstow the device. Default is
            True (stow).
        """
        self._issue_command(Command.STOW, stow)  # argument to stow or not...

    def command_interlock_ack(self) -> None:
        """
        Send a command to acknowledge the safety interlock.

        This function sends a command to acknowledge the safety interlock in the system.
        """
        self._issue_command(Command.INTERLOCK_ACK)

    def command_move2band(self, band: str) -> None:
        """
        Issue command to move the device to a specified band.

        :param band: The band to move the device to.
        """
        self._issue_command(Command.MOVE2BAND, band)

    def command_take_authority(self, username: str) -> None:
        """
        Issue a command to take or release authority.

        :param username: The username of the user performing the command.
        """
        self._issue_command(Command.TAKE_AUTH, username)

    def command_release_authority(self) -> None:
        """Issue a command to take or release authority."""
        self._issue_command(Command.RELEASE_AUTH)

    def command_set_time_source(
        self, source: str, address: str
    ) -> tuple[ResultCode, str]:
        """Issue a command to set the time source."""
        return self._issue_command(Command.SET_TIME_SOURCE, source, address)

    def command_set_power_mode(
        self, low_power: bool, power_lim_kw: float
    ) -> tuple[ResultCode, str]:
        """Issue a command to set the dish power mode."""
        return self._issue_command(Command.SET_POWER_MODE, low_power, power_lim_kw)

    def command_reset_axis(self, axis: str) -> tuple[ResultCode, str]:
        """Issue a command to clear servo amplifier axis/axes latched errors."""
        return self._issue_command(Command.RESET, axis)

    def command_config_pointing_model_corrections(
        self, static: bool, tilt: str, temperature: bool, band: str
    ) -> tuple[ResultCode, str]:
        """
        Issue command to configure the pointing model corrections.

        The command has four input arguments:
        - StaticOn
        - TiltOn
        - AmbTOn
        - Band

        :param static: Enable static pointing.
        :param tilt: Enable tilt correction meter one or two.
        :param temperature: Enable ambient temperature correction.
        :param band: The band to apply the model to.
        :return: A tuple containing the result code and result message.
        """
        return self._issue_command(
            Command.PM_CORR_ON_OFF, static, tilt, temperature, band
        )

    def command_set_static_pointing_parameters(
        self, band: str, params: list[float]
    ) -> tuple[ResultCode, str]:
        """
        Issue command to set the static pointing model parameters.

        :param band: The band to apply the model to.
        :param params: list of parameter values to apply (20 values)
        :return: A tuple containing the result code and result message,
            or None if the command was not issued.
        """
        return self._issue_command(Command.STATIC_PM_SETUP, band, *params)

    def command_set_static_pointing_offsets(
        self, azim: float, elev: float
    ) -> tuple[ResultCode, str]:
        """
        Issue command to set the static pointing tracking offsets.

        :param azim: Azimuth offset
        :param elev: Elevation offset
        :return: A tuple containing the result code and result message
        """
        return self._issue_command(Command.TRACK_LOAD_STATIC_OFF, azim, elev)

    def command_set_tilt_meter_calibration_parameters(
        self, tilt_meter: str, params: list[float]
    ) -> tuple[ResultCode, str] | None:
        """
        Issue command to set the tilt meter calibration parameters.

        :param tilt_meter: Tilt meter to calibrate (TiltOnType)
        :param params: list of parameter values to apply
        :return: A tuple containing the result code and result message
        """
        return self._issue_command(Command.TILT_CAL_SETUP, tilt_meter, *params)

    def command_set_ambtemp_correction_parameters(
        self, params: list[float]
    ) -> tuple[ResultCode, str]:
        """
        Issue command to set the ambient temperature correction parameters.

        :param params: list of parameter values to apply
        :return: A tuple containing the result code and result message
        """
        return self._issue_command(Command.AMBTEMP_CORR_SETUP, *params)

    def _issue_command(self, command: Command, *args: Any) -> tuple[ResultCode, str]:
        """
        Issue a command to the OPCUA server.

        :param command: The command to be issued.
        :param args: Optional arguments to be passed along with the command.
        :return: A tuple containing the result code and result message.
        """
        logger.debug("Command: %s, args: %s", command.value, args)
        # TODO: Nothing is currently done with other possible return values
        result_code, result_msg, _ = self._model.run_opcua_command(command, *args)
        self._command_response_str(f"{command.value}{args}", result_code, result_msg)
        if result_code == ResultCode.CONNECTION_CLOSED:
            self._handle_closed_connection()
        return (result_code, result_msg)

    def _handle_closed_connection(self, status_message: str | None = None) -> None:
        """Handle unexpected closed connection."""
        self._model.handle_closed_connection()
        if status_message:
            self.emit_ui_status_message("ERROR", status_message)
        self.server_disconnected.emit()

    def load_track_table(
        self,
        filename: str,
        load_mode: str,
        absolute_times: bool,
        additional_offset: float,
    ) -> None:
        """
        Load a track table from a file.

        Will only attempt to load the track table if the file exist.
        Emits UI status messages.

        :param filename: The name of the file containing the track table.
        :param load_mode: 'Append', 'New' or 'Reset'.
        :param absolute_times: Whether the time column is a real time or a relative time
        :param additional_offset: Add additional time to every point. Only has an
            effect when absolute_times is False.
        """

        def emit_result_to_ui(result_code: ResultCode, result_msg: str) -> None:
            if result_code == ResultCode.NOT_EXECUTED:
                self.emit_ui_status_message(
                    "WARNING", f"Track table cannot be loaded: {result_msg}"
                )
            elif result_code not in (
                ResultCode.COMMAND_DONE,
                ResultCode.COMMAND_ACTIVATED,
                ResultCode.COMMAND_FAILED,
                ResultCode.ENTIRE_TRACK_TABLE_LOADED,
                ResultCode.EXECUTING,
            ):
                self.emit_ui_status_message("ERROR", f"{result_msg}")
            else:
                self.emit_ui_status_message("INFO", f"{result_msg}")

        fname = Path(filename)
        logger.debug("Loading track table from file: %s", fname.absolute())
        if not fname.exists():
            msg = f"Not loading track table. File does not exist: {fname.absolute()}"
            self.emit_ui_status_message("WARNING", msg)
            return
        try:
            result_code, result_msg = self._model.load_track_table(
                fname,
                load_mode,
                absolute_times,
                additional_offset,
                emit_result_to_ui,  # callback to emit async end result
            )
            emit_result_to_ui(result_code, result_msg)  # emit immediate result
        except Exception as exc:  # pylint: disable=broad-except
            exc_msg = f"Unable to load track table from file: {fname.absolute()}"
            logger.exception("%s - %s", exc_msg, exc)
            msg = f"Unable to load track table: {exc}"
            self.emit_ui_status_message("ERROR", msg)

    def start_track_table(self, interpol: str, now: bool, at: str) -> None:
        """
        Start the track table on the PLC.

        :param str interpol: The interpolation type.
        :param bool now: Whether to start the track table immediately or not.
        :param str at: The time since SKAO epoch to start the track table at if now is
            False.
        """
        params = [interpol, now]
        if not now:
            try:
                at_num = float(at)
            except ValueError:
                self.emit_ui_status_message(
                    "ERROR",
                    "Invalid start time for TrackStart command, should be a number: "
                    f"{at}",
                )
                return

            params.append(at_num)
        self._issue_command(Command.TRACK_START, *params)

    def recording_start(self, filename: str, allow_overwrite: bool) -> str | None:
        """
        Start recording OPC-UA parameter updates to `filename`.

        Emits UI status messages as feedback to user.

        To avoid accidental overwrite of existing data, this function first checks for
        existence of `filename` and only starts recording if a file does not already
        exist.

        :param filename: Name of HDF5 file to write to.
        :return: Output file name or None if failed to start recording.
        """
        fname = None
        if filename:
            if not filename.rsplit(".", 1)[-1] == "hdf5":
                filename += ".hdf5"

            fname = Path(filename)
            logger.debug("Recording to file: %s", fname.absolute())
            if not allow_overwrite and fname.exists():
                msg = f"⛔️ Not recording. Data file already exists: {fname.absolute()}"
                self.emit_ui_status_message("WARNING", msg)
                return None

        try:
            output_name = str(self._model.start_recording(fname).absolute())
        except RuntimeError as e:
            msg = f"Unable to start recording: {e}"
            self.emit_ui_status_message("WARNING", msg)
            return None
        self.emit_ui_status_message(
            "INFO",
            f"▶️ Recording started to file: {output_name}",
        )
        self.recording_status.emit(True)

        return output_name

    def recording_stop(self) -> None:
        """
        Stop recording.

        Emits UI status update.
        """
        if self._model.recording:
            self._model.stop_recording()
            self.emit_ui_status_message("INFO", "Recording stopped")
            self.recording_status.emit(False)

    @property
    def recording_config(self) -> dict[str, dict[str, bool | int]]:
        """
        Get the recording configuration of the model.

        :return: A list of strings representing the recording configuration.
        """
        return self._model.recording_config

    @recording_config.setter
    def recording_config(self, config: dict[str, dict[str, bool | int]]) -> None:
        """
        Set the recording configuration for the model.

        :param config: A list of strings representing the recording configuration.
        """
        self._model.recording_config = config

    def get_warning_attributes(self) -> dict[str, list[tuple[str, str, str]]]:
        """Get the warning attributes from the model."""
        return self._model.status_warning_tree.get_all_attributes()

    def get_error_attributes(self) -> dict[str, list[tuple[str, str, str]]]:
        """Get the error attributes from the model."""
        return self._model.status_error_tree.get_all_attributes()

    # ---------------
    # Weather Station
    # ---------------
    def connect_weather_station(self, station_details: dict) -> None:
        """
        Connect to a weather station using the provided connection details.

        :param station_details: A dictionary containing weather station details.
        :raises ValueError: If the port number provided is not a valid integer.
        """
        self.emit_ui_status_message("INFO", "Connecting to weather station...")
        try:
            station_details["port"] = int(station_details["port"].strip())
        except ValueError:
            self.emit_ui_status_message(
                "ERROR",
                f"Invalid port number, should be integer: {station_details['port']}",
            )
            return

        self._model.weather_station_connect(station_details)
        self.emit_ui_status_message(
            "INFO",
            f"Connected to weather station at {station_details['address']}",
        )
        self.weather_station_connected.emit()

    def disconnect_weather_station(self):
        """Disconnect from the weather station."""
        self._model.weather_station_disconnect()
        self.emit_ui_status_message("INFO", "Disconnected from weather station.")
        self.weather_station_disconnected.emit()

    def subscribe_weather_station_updates(self, sensors: list[str]) -> None:
        """
        Subscribe to the requested weather station sensors.

        :param sensors: A list of weather station attributes.
        """
        self._model.register_event_updates(ServerType.WMS, sensors)

    def is_weather_station_connected(self) -> bool:
        """
        Check if the SCU is connected to a weather station.

        :return: True if the SCU has a weather station, False otherwise.
        """
        return self._model.is_weather_station_connected()

    def weather_station_available_sensors(self) -> list[str]:
        """Return the list of available weather station sensors as attributes names."""
        return self._model.weather_station_available_sensors()

    def weather_station_attributes(self) -> list[str]:
        """Return the list of configured weather station attributes."""
        return self._model.weather_station_attributes()

    def update_polled_weather_station_sensors(self, scu_sensors: list[str]) -> None:
        """
        Update the weather station config based on the input.

        :param sensor_details: An exhaustive list of sensors to be polled.
        """
        self._model.stop_event_q_poller(ServerType.WMS)
        self._model.weather_station_polling_update(
            [sensor.rsplit(".", 1)[-1] for sensor in scu_sensors]
        )
        self.subscribe_weather_station_updates(scu_sensors)

        # As this changes the attributes available in sculib, the recording config needs
        # to be reset so that it is recreated with the new attributes.
        self.recording_config = {}
