import logging
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from disq import model

logger = logging.getLogger("gui.controller")


class Controller(QObject):
    ui_status_message = pyqtSignal(str)
    server_connected = pyqtSignal()
    server_disconnected = pyqtSignal()
    recording_status = pyqtSignal(bool)

    def __init__(self, mvc_model: model.Model, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._model = mvc_model

    def command_response_str(
        self, command: str, result_code: int, result_msg: str
    ) -> str:
        r = f'Command "{command}" response: ({result_code}) "{result_msg}"'
        self.ui_status_message.emit(r)
        return r

    def emit_ui_status_message(self, severity: str, message: str):
        """Emit a status message to the UI. Severity is one of: INFO, WARNING, ERROR"""
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

    def is_server_connected(self) -> bool:
        return self._model.is_connected()

    def connect_server(self, server_uri):
        self.ui_status_message.emit("Connecting to server...")
        try:
            self._model.connect(server_uri)
        except OSError as e:
            self.ui_status_message.emit(f"Unable to connect to server. Error: {e}")
            return
        self.ui_status_message.emit(f"Connected to server: {server_uri}")
        self.server_connected.emit()

    def disconnect_server(self):
        self._model.disconnect()
        self.ui_status_message.emit("Disconnected from server")
        self.server_disconnected.emit()

    def subscribe_opcua_updates(self, registrations: dict):
        """Subscribe to the requested OPC UA variable data updates with the given
        callback. registrations is a dictionary with key:UI name value:callback method
        """
        self._model.register_event_updates(registrations=registrations)

    def command_slew2abs(
        self,
        azimuth_position: float,
        elevation_position: float,
        azimuth_velocity: float,
        elevation_velocity: float,
    ):
        cmd = "Management.Slew2AbsAzEl"
        desc = f"Command: {cmd}  args: {azimuth_position}, {elevation_position}, {azimuth_velocity}, {elevation_velocity}"
        logger.debug(desc)
        self.ui_status_message.emit(desc)
        result_code, result_msg = self._model.run_opcua_command(
            cmd,
            azimuth_position,
            elevation_position,
            azimuth_velocity,
            elevation_velocity,
        )
        self.command_response_str(cmd, result_code, result_msg)

    @pyqtSlot()
    def command_activate(self):
        cmd = "Management.Activate"
        axis_select_arg = "AzEl"
        self.issue_command(cmd, axis_select_arg)

    @pyqtSlot()
    def command_deactivate(self):
        cmd = "Management.DeActivate"
        axis_select_arg = "AzEl"
        self.issue_command(cmd, axis_select_arg)

    @pyqtSlot()
    def command_stop(self):
        cmd = "Management.Stop"
        axis_select_arg = "AzEl"
        self.issue_command(cmd, axis_select_arg)

    @pyqtSlot(bool)
    def command_stow(self, stow: bool = True):
        cmd = "Management.Stow"
        self.issue_command(cmd, stow)  # argument to stow or not...

    def command_move2band(self, band: str):
        cmd = "Management.Move2Band"
        self.issue_command(cmd, band)

    def issue_command(self, cmd: str, *args):
        logger.debug(f"Command: {cmd}  args: {args}")
        self.ui_status_message.emit(f"Issuing command: {cmd} {args}")
        result_code, result_msg = self._model.run_opcua_command(cmd, *args)
        self.command_response_str(f"{cmd}{args}", result_code, result_msg)

    @pyqtSlot(str)
    def recording_start(self, filename: str):
        """Start recording"""
        fname = Path(filename)
        logger.debug(f"Recording to file: {fname.absolute()}")
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
        """Stop recording"""
        self._model.stop_recording()
        self.emit_ui_status_message("INFO", "Recording stopped")
        self.recording_status.emit(False)
