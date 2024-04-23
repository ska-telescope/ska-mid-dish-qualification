"""DiSQ GUI controller."""

import logging
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from disq import configuration, model

logger = logging.getLogger("gui.controller")

_LOCAL_DIR_CONFIGFILE = "disq.ini"


# pylint: disable=too-many-public-methods
class Controller(QObject):
    """
    Controller for managing server connections and issuing commands.

    :param mvc_model: The model object that the controller interacts with.
    :type mvc_model: model.Model
    :param parent: The parent object, if any.
    :type parent: QObject | None
    """

    ui_status_message = pyqtSignal(str)
    server_connected = pyqtSignal()
    server_disconnected = pyqtSignal()
    recording_status = pyqtSignal(bool)

    def __init__(self, mvc_model: model.Model, parent: QObject | None = None) -> None:
        """
        Initialize a new instance of the `Controller` class.

        :param mvc_model: A `model.Model` object.
        :type mvc_model: model.Model
        :param parent: An optional `QObject` object or None.
        :type parent: QObject | None
        """
        super().__init__(parent)
        self._model = mvc_model

    def _command_response_str(
        self, command: str, result_code: int, result_msg: str
    ) -> str:
        """
        Generate a response message based on the result of issuing a command.

        :param command: The command that was executed.
        :type command: str
        :param result_code: The result code of the command execution.
        :type result_code: int
        :param result_msg: The message associated with the result code.
        :type result_msg: str
        :return: The response message containing the command, result code, and result
            message.
        :rtype: str
        """
        r = f"Command: {command}; Response: {result_msg} [{result_code}]"
        self.emit_ui_status_message("INFO", r)
        return r

    def emit_ui_status_message(self, severity: str, message: str):
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
        :rtype: list[str]
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

    def get_config_server_args(self, server_name: str) -> dict[str, str]:
        """
        Get the server arguments from the configuration file.

        :param server_name: The name of the server to retrieve arguments for.
        :type server_name: str
        :return: A dictionary containing the server arguments.
        :rtype: dict[str, str | int]
        :raises FileNotFoundError: If the configuration file is not found.
        """
        server_args: dict[str, str] = {}
        try:
            server_args = configuration.get_config_sculib_args(
                config_filename=_LOCAL_DIR_CONFIGFILE, server_name=server_name
            )
        except FileNotFoundError:
            logger.warning("Unable to find config file")
        return server_args

    def is_server_connected(self) -> bool:
        """
        Check if the server is connected.

        :return: True if the server is connected, False otherwise.
        :rtype: bool
        """
        return self._model.is_connected()

    def connect_server(self, connection_details: dict):
        """
        Connect to a server using the provided connection details.

        :param connection_details: A dictionary containing server connection details,
            including as a minimum 'host' and 'port' keys.
        :type connection_details: dict
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

    def subscribe_opcua_updates(self, registrations: dict[str, Callable]) -> None:
        """
        Subscribe to the requested OPC UA variable data updates with the given callback.

        :param registrations: is a dictionary with key:UI name value:callback method.
        """
        self._model.register_event_updates(registrations=registrations)

    def command_slew2abs_azim_elev(
        self,
        azimuth_position: float,
        elevation_position: float,
        azimuth_velocity: float,
        elevation_velocity: float,
    ):
        """
        Issue command to slew to absolute azimuth and elevation positions.

        :param azimuth_position: The azimuth position to slew to (in degrees).
        :type azimuth_position: float
        :param elevation_position: The elevation position to slew to (in degrees).
        :type elevation_position: float
        :param azimuth_velocity: The azimuth velocity for slewing (in degrees per
            second).
        :type azimuth_velocity: float
        :param elevation_velocity: The elevation velocity for slewing (in degrees per
            second).
        :type elevation_velocity: float
        """
        cmd = "Management.Slew2AbsAzEl"
        self._issue_command(
            cmd,
            azimuth_position,
            elevation_position,
            azimuth_velocity,
            elevation_velocity,
        )

    def command_slew_single_axis(self, axis: str, position: float, velocity: float):
        """
        Issue command to slew a single axis to a specific position with given velocity.

        :param axis: The axis identifier.
        :type axis: str
        :param position: The target position to slew to.
        :type position: float
        :param velocity: The velocity at which to slew.
        :type velocity: float
        """
        cmd = "Management.Slew2AbsSingleAx"
        self._issue_command(cmd, axis, position, velocity)

    @pyqtSlot()
    def command_activate(self, axis: str = "AzEl"):
        """
        Issue command to activate a specific axis.

        :param axis: The axis to activate (default is 'AzEl').
        :type axis: str
        """
        cmd = "Management.Activate"
        self._issue_command(cmd, axis)

    @pyqtSlot()
    def command_deactivate(self, axis: str = "AzEl"):
        """
        Issue command to deactivate a specific axis.

        :param axis: The axis to deactivate (default is 'AzEl').
        :type axis: str
        """
        cmd = "Management.DeActivate"
        self._issue_command(cmd, axis)

    @pyqtSlot()
    def command_stop(self, axis: str = "AzEl"):
        """
        Issue command to stop a specific axis movement.

        :param axis: The axis for which the movement should be stopped. Default is
            'AzEl'.
        :type axis: str
        """
        cmd = "Management.Stop"
        self._issue_command(cmd, axis)

    @pyqtSlot(bool)
    def command_stow(self, stow: bool = True):
        """
        Issue command to stow or unstow the device.

        :param stow: A flag indicating whether to stow or unstow the device. Default is
            True (stow).
        :type stow: bool
        """
        cmd = "Management.Stow"
        self._issue_command(cmd, stow)  # argument to stow or not...

    @pyqtSlot()
    def command_interlock_ack(self):
        """
        Send a command to acknowledge the safety interlock.

        This function sends a command to acknowledge the safety interlock in the system.
        """
        cmd = "Safety.InterlockAck"
        self._issue_command(cmd)

    def command_move2band(self, band: str):
        """
        Issue command to move the device to a specified band.

        :param band: The band to move the device to.
        :type band: str
        """
        cmd = "Management.Move2Band"
        self._issue_command(cmd, band)

    def command_take_authority(self, take_command: bool, username: str):
        """
        Issue a command to take or release authority.

        :param take_command: A boolean indicating whether to take or release authority.
        :type take_command: bool
        :param username: The username of the user performing the command.
        :type username: str
        """
        cmd = "CommandArbiter.TakeReleaseAuth"
        # Arguments are: (bool TakeCommand, string Username)
        self._issue_command(cmd, take_command, username)

    def command_config_pointing_model_corrections(
        self, static: bool, tilt: str, temperature: bool, band: str
    ) -> tuple[int, str]:
        """
        Issue command to configure the pointing model corrections.

        The command has four input arguments:
        - StaticOn
        - TiltOn
        - AmbTOn
        - Band

        :param static: Enable static pointing.
        :type static: bool
        :param tilt: Enable tilt correction meter one or two.
        :type tilt: str
        :param temperature: Enable ambient temperature correction.
        :type temperature: bool
        :param band: The band to apply the model to.
        :type band: str
        :return: A tuple containing the result code and result message.
        :rtype: tuple
        """
        cmd = "Pointing.PmCorrOnOff"
        return self._issue_command(cmd, static, tilt, temperature, band)

    def command_set_static_pointing_parameters(
        self, band: str, params: list[float]
    ) -> tuple[int, str]:
        """
        Issue command to set the static pointing model parameters.

        :param band: The band to apply the model to.
        :type band: str
        :param params: list of parameter values to apply (20 values)
        :type params: list[float]
        :return: A tuple containing the result code and result message
        :rtype: tuple[int, str]
        """
        cmd = "Pointing.StaticPmSetup"
        return self._issue_command(cmd, band, *params)

    def command_set_static_pointing_offsets(
        self, azim: float, elev: float
    ) -> tuple[int, str]:
        """
        Issue command to set the static pointing tracking offsets.

        :param azim: Azimuth offset
        :type params: float
        :param elev: Elevation offset
        :type params: float
        :return: A tuple containing the result code and result message
        :rtype: tuple[int, str]
        """
        cmd = "Tracking.TrackLoadStaticOff"
        return self._issue_command(cmd, azim, elev)

    def command_set_ambtemp_correction_parameters(
        self, params: list[float]
    ) -> tuple[int, str]:
        """
        Issue command to set the ambient temperature correction parameters.

        :param params: list of parameter values to apply
        :type params: list[float]
        :return: A tuple containing the result code and result message
        :rtype: tuple[int, str]
        """
        cmd = "Pointing.AmbCorrSetup"
        return self._issue_command(cmd, *params)

    def _issue_command(self, cmd: str, *args) -> tuple[int, str]:
        """
        Issue a command to the OPCUA server.

        :param cmd: The command to be issued.
        :type cmd: str
        :param args: Optional arguments to be passed along with the command.
        :type args: tuple
        :return: A tuple containing the result code and result message.
        :rtype: tuple
        """
        logger.debug("Command: %s, args: %s", cmd, args)
        result_code, result_msg = self._model.run_opcua_command(cmd, *args)
        self._command_response_str(f"{cmd}{args}", result_code, result_msg)
        return (result_code, result_msg)

    @pyqtSlot(str)
    def load_track_table(self, filename: str):
        """
        Load a track table from a file.

        Will only attempt to load the track table if the file exist.
        Emits UI status messages.

        :param filename: The name of the file containing the track table.
        :type filename: str
        """
        fname = Path(filename)
        logger.debug("Loading track table from file: %s", fname.absolute())
        if not fname.exists():
            msg = f"Not loading track table. File does not exist: {fname.absolute()}"
            self.emit_ui_status_message("WARNING", msg)
            return
        try:
            self._model.load_track_table(fname)
        except Exception as exc:  # pylint: disable=broad-except
            exc_msg = f"Unable to load track table from file: {fname.absolute()}"
            logger.exception("%s - %s", exc_msg, exc)
            msg = f"Unable to load track table: {exc}"
            self.emit_ui_status_message("ERROR", msg)
            return
        self.emit_ui_status_message(
            "INFO", f"Track table loaded from file: {fname.absolute()}"
        )

    @pyqtSlot(str)
    def recording_start(self, filename: str):
        """
        Start recording OPC-UA parameter updates to `filename`.

        Emits UI status messages as feedback to user.

        To avoid accidental overwrite of existing data, this function first checks for
        existence of `filename` and only starts recording if a file does not already
        exist.

        :param filename: Name of HDF5 file to write to.
        :type filename: str
        """
        fname = Path(filename)
        logger.debug("Recording to file: %s", fname.absolute())
        if fname.exists():
            msg = f"⛔️ Not recording. Data file already exists: {fname.absolute()}"
            self.emit_ui_status_message("WARNING", msg)
            return
        try:
            self._model.start_recording(fname)
        except RuntimeError as e:
            msg = f"Unable to start recording: {e}"
            self.emit_ui_status_message("WARNING", msg)
            return
        self.emit_ui_status_message(
            "INFO", f"▶️ Recording started to file: {fname.absolute()}"
        )
        self.recording_status.emit(True)

    @pyqtSlot()
    def recording_stop(self):
        """
        Stop recording.

        Emits UI status update.
        """
        self._model.stop_recording()
        self.emit_ui_status_message("INFO", "Recording stopped")
        self.recording_status.emit(False)

    @property
    def recording_config(self) -> list[str]:
        """
        Get the recording configuration of the model.

        :return: A list of strings representing the recording configuration.
        :rtype: list[str]
        """
        return self._model.recording_config

    @recording_config.setter
    def recording_config(self, config: list[str]) -> None:
        """
        Set the recording configuration for the model.

        :param config: A list of strings representing the recording configuration.
        :type config: list[str]
        """
        self._model.recording_config = config
