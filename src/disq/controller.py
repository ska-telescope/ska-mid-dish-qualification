from PyQt6.QtCore import QObject, pyqtSignal
from qasync import asyncSlot
from disq import model


class Controller(QObject):
    command_response_status = pyqtSignal(str)
    server_connected = pyqtSignal()
    server_disconnected = pyqtSignal()

    def __init__(self, model: model.Model, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.model = model

    def command_response_str(
        self, command: str, return_code: int, return_msg: str
    ) -> str:
        result = f'Command "{command}" response: {return_msg} ({return_code})'
        self.command_response_status.emit(result)
        return result

    async def is_server_connected(self) -> bool:
        return await self.model.is_connected()

    async def connect_server(self, server_uri):
        self.command_response_status.emit(f"Connecting to server...")
        try:
            await self.model.connect(server_uri)
        except OSError as e:
            self.command_response_status.emit(
                f"Unable to connect to server. Error: {e}"
            )
            return
        self.command_response_status.emit(f"Connected to server: {server_uri}")
        self.server_connected.emit()

    async def disconnect_server(self):
        await self.model.disconnect()
        self.command_response_status.emit(f"Disconnected from server")
        self.server_disconnected.emit()

    @asyncSlot(str)
    async def on_input_server_uri(self, server_uri):
        print(f"Server: {server_uri}")
        self._server_uri = server_uri

    # @asyncSlot()
    # async def connect_model(self):
    #     await self.model.connect(self._server_uri)
    #     # TODO: emit connected event - the view then requests subscriptions

    async def subscribe_opcua_updates(self, registrations: list):
        """Subscribe to the requested OPC UA variable data updates with the given callbacks

        registrations is a list of tuples with (UI name, callback method)"""
        # TODO: asynchronous call register_monitor and gather all futures..
        for name, callback in registrations:
            await self.model.register_monitor(name, callback)

    async def command_slew2abs(
        self,
        azimuth_position: float,
        elevation_position: float,
        azimuth_velocity: float,
        elevation_velocity: float,
    ):
        print("Command: slew2abs")
        cmd = "Slew2AbsAzEl"
        self.command_response_status.emit(f'Command: "{cmd}"...')
        retcode, retmsg = await self.model.call_method(
            "Management",
            cmd,
            azimuth_position,
            elevation_position,
            azimuth_velocity,
            elevation_velocity,
        )
        self.command_response_str(cmd, retcode, retmsg)

    asyncSlot()

    async def command_activate(self):
        cmd = "Activate"
        axis_select_arg = "AzEl"
        await self.issue_command(cmd, axis_select_arg)

    asyncSlot()

    async def command_deactivate(self):
        cmd = "DeActivate"
        axis_select_arg = "AzEl"
        await self.issue_command(cmd, axis_select_arg)

    asyncSlot()

    async def command_stop(self):
        cmd = "Stow"
        axis_select_arg = "AzEl"
        await self.issue_command(cmd, axis_select_arg)

    asyncSlot()

    async def command_stow(self):
        cmd = "Stow"
        await self.issue_command(cmd, True)  # argument to stow or not...

    async def issue_command(self, cmd: str, *args):
        print(f"Command: {cmd}  args: {[*args]}")
        self.command_response_status.emit(f"Issuing command: '{cmd} ...")
        retcode, retmsg = await self.model.call_method("Management", cmd, *args)
        self.command_response_str(cmd, retcode, retmsg)
