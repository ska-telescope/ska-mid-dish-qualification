from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from disq import model


class Controller(QObject):
    command_response_status = pyqtSignal(str)
    server_connected = pyqtSignal()
    server_disconnected = pyqtSignal()

    def __init__(self, mvc_model: model.Model, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._model = mvc_model

    def command_response_str(
        self, command: str, result_code: int, result_msg: str
    ) -> str:
        r = f'Command "{command}" response: ({result_code}) "{result_msg}"'
        self.command_response_status.emit(r)
        return r

    def is_server_connected(self) -> bool:
        return self._model.is_connected()

    def connect_server(self, server_uri):
        self.command_response_status.emit("Connecting to server...")
        try:
            self._model.connect(server_uri)
        except OSError as e:
            self.command_response_status.emit(
                f"Unable to connect to server. Error: {e}"
            )
            return
        self.command_response_status.emit(f"Connected to server: {server_uri}")
        self.server_connected.emit()

    def disconnect_server(self):
        self._model.disconnect()
        self.command_response_status.emit("Disconnected from server")
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
        print(desc)
        self.command_response_status.emit(desc)
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

    def issue_command(self, cmd: str, *args):
        print(f"Command: {cmd}  args: {args}")
        self.command_response_status.emit(f"Issuing command: {cmd} {args}")
        result_code, result_msg = self._model.run_opcua_command(cmd, *args)
        self.command_response_str(cmd, result_code, result_msg)
