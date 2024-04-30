# pylint: disable=C0114,C0115,C0116
# pylint: disable=attribute-defined-outside-init,no-member,unused-argument
# pylint: disable=too-many-instance-attributes,too-many-public-methods,too-many-locals
# pylint: disable=too-many-branches,too-many-statements,missing-docstring
# pylint: disable=W0719,R0913,W0012,R0902


import asyncio
import enum
import logging
import random
import threading

from asyncua import Server, ua, uamethod

# TODO: Confirm below constants
# units for drive rate of axis in degrees per second
AZIM_DRIVE_MAX_RATE = 3.0
ELEV_DRIVE_MAX_RATE = 1.0

# Rate for updates:
# 10Hz
# 10 updates per 1000ms
# 1 per 100ms
# i.e. update every .1 seconds
UPDATE_RATE = 0.1

# Mechanical limits for the axis in degrees
ELEV_MECHANICAL_LIMIT_MAX = 85.0
ELEV_MECHANICAL_LIMIT_MIN = 15.0

AZIM_MECHANICAL_LIMIT_MAX = 360.0
AZIM_MECHANICAL_LIMIT_MIN = 0.0


class DSSimulatorOPCUAServer:
    def __init__(self):
        # Starts an OPC UA server on port 4840
        self.server = Server()
        self.server.set_endpoint("opc.tcp://0.0.0.0:4840/dish-structure/server/")
        self.server.set_server_name("DS OPC-UA server")
        self.namespace_to_use = "http://skao.int/DS_ICD/"

        self.track_table = None
        self.tracking_thread = None
        self.tracking_stop_event = None

        self.movement_thread = None
        self.movement_stop_event = None

    async def init(self):
        await self.server.init()

        # Import server definition at start so it doesn't overwrite anything added on
        await self.server.import_xml("resources/ds_icd_0.0.4_mock.xml")

        self.idx = await self.server.get_namespace_index(uri=self.namespace_to_use)
        logging.info("Namespace index: %s", self.idx)

        self.plc_prg = await self.server.nodes.root.get_child(
            [
                "0:Objects",
                f"{self.idx}:Logic",
                f"{self.idx}:Application",
                f"{self.idx}:PLC_PRG",
            ]
        )

        self.management = await self.plc_prg.get_child(
            [
                f"{self.idx}:Management",
            ]
        )

        self.management_status = await self.management.get_child(
            [
                f"{self.idx}:ManagementStatus",
            ]
        )

        # Link methods to functionality
        set_power_mode_node = await self.management.get_child(
            [f"{self.idx}:SetPowerMode"]
        )
        self.server.link_method(set_power_mode_node, self.set_power_mode)

        activate_node = await self.management.get_child([f"{self.idx}:Activate"])
        self.server.link_method(activate_node, self.activate)

        deactivate_node = await self.management.get_child([f"{self.idx}:DeActivate"])
        self.server.link_method(deactivate_node, self.deactivate)

        stow_node = await self.management.get_child([f"{self.idx}:Stow"])
        self.server.link_method(stow_node, self.stow)

        move_2_band_node = await self.management.get_child([f"{self.idx}:Move2Band"])
        self.server.link_method(move_2_band_node, self.move_2_band)

        stop_node = await self.management.get_child([f"{self.idx}:Stop"])
        self.server.link_method(stop_node, self.stop)

        track_start_dm_node = await self.management.get_child(
            [f"{self.idx}:TrackStartDM"]
        )
        self.server.link_method(track_start_dm_node, self.track_start_dm)

        slew_abs_node = await self.management.get_child([f"{self.idx}:Slew2AbsAzEl"])
        self.server.link_method(slew_abs_node, self.slew_abs)

        track_load_table_node = await self.plc_prg.get_child(
            [f"{self.idx}:Tracking", f"{self.idx}:TrackLoadTable"]
        )
        self.server.link_method(track_load_table_node, self.track_load_table)

        logging.info("PLC_PRG node: %s", self.plc_prg)
        logging.info("Management node: %s", self.management)

        # ================
        #  Default values
        # ================
        await self.reset_attributes()

    async def __aenter__(self):
        await self.init()
        await self.server.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.server.stop()

    # ================
    #  Helper methods
    # ================
    async def reset_attributes(self):
        az_axis_state = await self.get_az_axis_state()
        az_axis_moving = await self.get_az_axis_moving()
        az_axis_p_set = await self.get_az_p_set()

        el_axis_state = await self.get_el_axis_state()
        el_axis_moving = await self.get_el_axis_moving()
        el_axis_p_set = await self.get_el_p_set()

        fi_axis_state = await self.get_fi_axis_state()
        fi_axis_moving = await self.get_fi_axis_moving()

        dsc_state = await self.get_dsc_state()
        low_power_active = await self.get_low_power_active()
        stow_pin_status = await self.get_stow_pin_status()
        fi_pos = await self.get_fi_pos()

        await az_axis_state.write_value(ua.AxisStateType.Standby)
        await el_axis_state.write_value(ua.AxisStateType.Standby)
        await fi_axis_state.write_value(ua.AxisStateType.Standby)

        await az_axis_moving.write_value(False)
        await el_axis_moving.write_value(False)
        await fi_axis_moving.write_value(False)

        await az_axis_p_set.write_value(AZIM_MECHANICAL_LIMIT_MIN)
        await el_axis_p_set.write_value(ELEV_MECHANICAL_LIMIT_MAX)

        await dsc_state.write_value(ua.DscStateType.Standby)
        await low_power_active.write_value(True)
        await stow_pin_status.write_value(ua.StowPinStatusType.Retracted)
        await fi_pos.write_value(ua.BandType.Band_1)

        self.track_table = [
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
        ]

    async def start_moving_dish_parts(self):
        # Set the axis states to slew
        axis_state = await self.get_el_axis_state()
        await axis_state.write_value(ua.AxisStateType.Slew)
        axis_state = await self.get_az_axis_state()
        await axis_state.write_value(ua.AxisStateType.Slew)

        # Set the axis moving to true
        axis_moving = await self.get_el_axis_moving()
        await axis_moving.write_value(True)
        axis_moving = await self.get_az_axis_moving()
        await axis_moving.write_value(True)

        dsc_state = await self.get_dsc_state()
        await dsc_state.write_value(ua.DscStateType.Slew)

    async def are_axis_activated(self) -> bool:
        azimuth_state = await self.get_az_axis_state()
        azimuth_state = await azimuth_state.get_value()

        elevation_state = await self.get_el_axis_state()
        elevation_state = await elevation_state.get_value()

        fi_state = await self.plc_prg.get_child(
            [
                f"{self.idx}:FeedIndexer",
                f"{self.idx}:AxisState",
            ]
        )
        fi_state = await fi_state.get_value()

        az_activated = azimuth_state == ua.AxisStateType.Standstill
        el_activated = elevation_state == ua.AxisStateType.Standstill
        fi_activated = fi_state == ua.AxisStateType.Standstill

        return az_activated and el_activated and fi_activated

    async def is_dish_stowed(self) -> bool:
        # Set DscState to stowed
        dsc_state = await self.get_dsc_state()
        dsc_state = await dsc_state.get_value()

        return dsc_state == ua.DscStateType.Stowed

    async def get_az_axis_state(self) -> any:
        val = await self.plc_prg.get_child(
            [
                f"{self.idx}:Azimuth",
                f"{self.idx}:AxisState",
            ]
        )

        return val

    async def get_az_axis_moving(self) -> any:
        val = await self.plc_prg.get_child(
            [
                f"{self.idx}:Azimuth",
                f"{self.idx}:AxisMoving",
            ]
        )

        return val

    async def get_az_p_set(self) -> any:
        val = await self.plc_prg.get_child(
            [
                f"{self.idx}:Azimuth",
                f"{self.idx}:p_Set",
            ]
        )

        return val

    async def get_el_axis_state(self) -> any:
        val = await self.plc_prg.get_child(
            [
                f"{self.idx}:Elevation",
                f"{self.idx}:AxisState",
            ]
        )

        return val

    async def get_el_axis_moving(self) -> any:
        val = await self.plc_prg.get_child(
            [
                f"{self.idx}:Elevation",
                f"{self.idx}:AxisMoving",
            ]
        )

        return val

    async def get_el_p_set(self) -> any:
        val = await self.plc_prg.get_child(
            [
                f"{self.idx}:Elevation",
                f"{self.idx}:p_Set",
            ]
        )

        return val

    async def get_fi_axis_state(self) -> any:
        val = await self.plc_prg.get_child(
            [
                f"{self.idx}:FeedIndexer",
                f"{self.idx}:AxisState",
            ]
        )

        return val

    async def get_fi_axis_moving(self) -> any:
        val = await self.plc_prg.get_child(
            [
                f"{self.idx}:FeedIndexer",
                f"{self.idx}:AxisMoving",
            ]
        )

        return val

    async def get_fi_pos(self) -> any:
        val = await self.management_status.get_child(
            [
                f"{self.idx}:FiPos",
            ]
        )

        return val

    async def get_low_power_active(self) -> any:
        val = await self.management_status.get_child(
            [
                f"{self.idx}:PowerStatus",
                f"{self.idx}:LowPowerActive",
            ]
        )

        return val

    async def get_dsc_state(self) -> any:
        val = await self.management_status.get_child(
            [
                f"{self.idx}:DscState",
            ]
        )

        return val

    async def get_stow_pin_status(self) -> any:
        val = await self.plc_prg.get_child(
            [
                f"{self.idx}:Safety",
                f"{self.idx}:StowPinStatus",
            ]
        )

        return val

    async def move_dish_to_position_task(
        self,
        pos_az: float,
        pos_el: float,
        speed_az: float,
        speed_el: float,
        stop_event: threading.Event,
        stowing: bool,
    ):
        logging.info(
            "Moving dish to positions az: %s, el: %s, speed_az: %s, speed_el: %s",
            pos_az,
            pos_el,
            speed_az,
            speed_el,
        )

        el_p_set = await self.get_el_p_set()
        az_p_set = await self.get_az_p_set()

        current_pos_el = await el_p_set.get_value()
        current_pos_az = await az_p_set.get_value()

        logging.info("Current az: %s, el: %s", current_pos_az, current_pos_el)

        az_movement_direction = 1 if pos_az > current_pos_az else -1
        el_movement_direction = 1 if pos_el > current_pos_el else -1

        az_movement_per_update = speed_az * UPDATE_RATE * az_movement_direction
        el_movement_per_update = speed_el * UPDATE_RATE * el_movement_direction

        # Set the axis states to Slew
        az_axis_state = await self.get_el_axis_state()
        el_axis_state = await self.get_az_axis_state()

        # Set the axis moving to True
        az_axis_moving = await self.get_az_axis_moving()
        el_axis_moving = await self.get_el_axis_moving()

        if current_pos_az != pos_az:
            await az_axis_moving.write_value(True)
            await az_axis_state.write_value(ua.AxisStateType.Slew)
        if current_pos_el != pos_el:
            await el_axis_moving.write_value(True)
            await el_axis_state.write_value(ua.AxisStateType.Slew)

        # Set the dscState to Slew
        dsc_state = await self.get_dsc_state()
        await dsc_state.write_value(ua.DscStateType.Slew)

        while not stop_event.is_set() and (
            current_pos_az != pos_az or current_pos_el != pos_el
        ):
            # Update the axis positions
            if current_pos_az != pos_az:
                new_pos_az = current_pos_az + az_movement_per_update

                if az_movement_direction == 1 and new_pos_az > pos_az:
                    new_pos_az = pos_az
                elif az_movement_direction == -1 and new_pos_az < pos_az:
                    new_pos_az = pos_az

                await az_p_set.write_value(new_pos_az)
                current_pos_az = new_pos_az

                # If the axis has reached it's position, set the axis moving to False
                if new_pos_az == pos_az:
                    await az_axis_moving.write_value(False)

            if current_pos_el != pos_el:
                new_pos_el = current_pos_el + el_movement_per_update

                if el_movement_direction == 1 and new_pos_el > pos_el:
                    new_pos_el = pos_el
                elif el_movement_direction == -1 and new_pos_el < pos_el:
                    new_pos_el = pos_el

                await el_p_set.write_value(new_pos_el)
                current_pos_el = new_pos_el

                if new_pos_el == pos_el:
                    await el_axis_moving.write_value(False)

            stop_event.wait(timeout=UPDATE_RATE)

        logging.info(
            "Done moving dish. Current positions az: %s, el: %s",
            current_pos_az,
            current_pos_el,
        )

        if stowing:
            # Set the axis states to stow
            axis_state = await self.get_el_axis_state()
            await axis_state.write_value(ua.AxisStateType.Stowed)
            axis_state = await self.get_az_axis_state()
            await axis_state.write_value(ua.AxisStateType.Stowed)

            # Stow pin is engaged
            stow_pin_status = await self.get_stow_pin_status()
            await stow_pin_status.write_value(ua.StowPinStatusType.Deployed)

            # Set DscState to stowed
            dsc_state = await self.get_dsc_state()
            await dsc_state.write_value(ua.DscStateType.Stowed)
        else:
            # Set the axis states to Standstill
            axis_moving = await self.get_el_axis_state()
            await axis_moving.write_value(ua.AxisStateType.Standstill)
            axis_moving = await self.get_az_axis_state()
            await axis_moving.write_value(ua.AxisStateType.Standstill)

            # Set DscState to Standstill
            dsc_state = await self.get_dsc_state()
            await dsc_state.write_value(ua.DscStateType.Standstill)

            # Set the axis moving to false
            axis_moving = await self.get_el_axis_moving()
            await axis_moving.write_value(False)
            axis_moving = await self.get_az_axis_moving()
            await axis_moving.write_value(False)

    async def dish_tracking_task(
        self, interpol: enum.Enum, stop_event: threading.Event
    ):
        logging.info("Starting dish tracking task with %s interpol!", interpol)

        az_p_set = await self.get_az_p_set()
        el_p_set = await self.get_el_p_set()

        az_movement_per_update = AZIM_DRIVE_MAX_RATE * UPDATE_RATE
        el_movement_per_update = ELEV_DRIVE_MAX_RATE * UPDATE_RATE

        az_movement_direction = 1
        el_movement_direction = 1

        # Loop to move the az and el axis between their min/max values
        while not stop_event.is_set():
            az_p_set_value = await az_p_set.get_value()
            el_p_set_value = await el_p_set.get_value()

            # Update the azimuth value and change the direction if it reaches the limits
            az_p_set_value = (
                az_p_set_value + az_movement_per_update * az_movement_direction
            )
            if (
                az_movement_direction == 1
                and az_p_set_value >= AZIM_MECHANICAL_LIMIT_MAX
            ):
                az_p_set_value = AZIM_MECHANICAL_LIMIT_MAX
                az_movement_direction = -1
            elif az_p_set_value <= AZIM_MECHANICAL_LIMIT_MIN:
                az_p_set_value = AZIM_MECHANICAL_LIMIT_MIN
                az_movement_direction = 1

            # Update the elevation value and change the direction if it reaches the limits
            el_p_set_value = (
                el_p_set_value + el_movement_per_update * el_movement_direction
            )
            if (
                el_movement_direction == 1
                and el_p_set_value >= ELEV_MECHANICAL_LIMIT_MAX
            ):
                el_p_set_value = ELEV_MECHANICAL_LIMIT_MAX
                el_movement_direction = -1
            elif el_p_set_value <= ELEV_MECHANICAL_LIMIT_MIN:
                el_p_set_value = ELEV_MECHANICAL_LIMIT_MIN
                el_movement_direction = 1

            await az_p_set.write_value(az_p_set_value)
            await el_p_set.write_value(el_p_set_value)

            stop_event.wait(timeout=UPDATE_RATE)

        logging.info("Dish tracking stopped")

    def run_dish_movement_task(
        self, pos_az, pos_el, speed_az, speel_el, stop_event, stowing=False
    ):
        """Start a new asyncio event loop which will run the dish movement coroutine"""
        logging.info("Creating new event loop for dish movement task")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self.move_dish_to_position_task(
                    pos_az, pos_el, speed_az, speel_el, stop_event, stowing
                )
            )
        finally:
            loop.close()

    def run_dish_tracking_task(self, interpol, stop_event):
        """Start a new asyncio event loop which will run the dish tracking coroutine"""
        logging.info("Creating new event loop for dish tracking task")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.dish_tracking_task(interpol, stop_event))
        finally:
            loop.close()

    # ================
    #  UA methods
    # ================

    @uamethod
    async def set_power_mode(
        self, parent, low_power_on_off: bool, maximum_power_allowed: float
    ) -> enum.Enum:
        logging.info(
            "Called SetPowerMode with parameters: %s, %s",
            low_power_on_off,
            maximum_power_allowed,
        )
        low_power_active = await self.get_low_power_active()
        await low_power_active.write_value(low_power_on_off)

        dsc_state = await self.get_dsc_state()

        if low_power_on_off:
            # Transition to STANDBY
            await dsc_state.write_value(ua.DscStateType.Standby)
        else:
            # Transition to STANDSTILL
            await dsc_state.write_value(ua.DscStateType.Standstill)

        return ua.CmdResponseType.CommandDone

    @uamethod
    async def activate(self, parent, axis: enum.Enum) -> enum.Enum:
        logging.info("Called Activate for axis %s", ua.AxisSelectType(axis))

        # AxisSelectType enum
        # <Field Name="Az" Value="0"/>
        # <Field Name="El" Value="1"/>
        # <Field Name="Fi" Value="2"/>
        # <Field Name="AzEl" Value="3"/>
        if axis in [ua.AxisSelectType.Az, ua.AxisSelectType.AzEl]:
            # Set Az axisstate to standstill
            axis_state = await self.get_az_axis_state()
            await axis_state.write_value(ua.AxisStateType.Standstill)

        if axis in [ua.AxisSelectType.El, ua.AxisSelectType.AzEl]:
            # Set El axisstate to standstill
            axis_state = await self.get_el_axis_state()
            await axis_state.write_value(ua.AxisStateType.Standstill)

        if axis == ua.AxisSelectType.Fi:
            # Set Fi axisstate to standstill
            axis_state = await self.get_fi_axis_state()
            await axis_state.write_value(ua.AxisStateType.Standstill)

        return ua.CmdResponseType.CommandDone

    @uamethod
    async def deactivate(self, parent, axis: enum.Enum) -> enum.Enum:
        logging.info("Called DeActivate for axis %s", ua.AxisSelectType(axis))

        # AxisSelectType enum
        # <Field Name="Az" Value="0"/>
        # <Field Name="El" Value="1"/>
        # <Field Name="Fi" Value="2"/>
        # <Field Name="AzEl" Value="3"/>
        if axis in [ua.AxisSelectType.Az, ua.AxisSelectType.AzEl]:
            # Set Az axisstate to Standby
            axis_state = await self.get_az_axis_state()
            await axis_state.write_value(ua.AxisStateType.Standby)

        if axis in [ua.AxisSelectType.El, ua.AxisSelectType.AzEl]:
            # Set El axisstate to Standby
            axis_state = await self.get_el_axis_state()
            await axis_state.write_value(ua.AxisStateType.Standby)

        if axis == ua.AxisSelectType.Fi:
            # Set Fi axisstate to Standby
            axis_state = await self.get_fi_axis_state()
            await axis_state.write_value(ua.AxisStateType.Standby)

        return ua.CmdResponseType.CommandDone

    @uamethod
    async def stow(self, parent, stow_action: bool) -> enum.Enum:
        logging.info("Called Stow with stow action %s", stow_action)

        if stow_action:
            az_p_set = await self.get_az_p_set()

            # TODO: Confirm stow position for azimuth with Henk
            # Dish Stop at elevation of 85 degrees as 90 degrees is the mechanical limit
            current_pos_az = await az_p_set.get_value()
            pos_el = 85.0

            self.movement_stop_event = threading.Event()
            self.movement_thread = threading.Thread(
                target=self.run_dish_movement_task,
                args=(
                    current_pos_az,
                    pos_el,
                    AZIM_DRIVE_MAX_RATE,
                    ELEV_DRIVE_MAX_RATE,
                    self.movement_stop_event,
                    True,
                ),
            )
            self.movement_thread.start()
        else:
            # Set the axis states to Standby
            axis_moving = await self.get_el_axis_state()
            await axis_moving.write_value(ua.AxisStateType.Standby)
            axis_moving = await self.get_az_axis_state()
            await axis_moving.write_value(ua.AxisStateType.Standby)

            # Stow pin is engaged
            stow_pin_status = await self.get_stow_pin_status()
            await stow_pin_status.write_value(ua.StowPinStatusType.Retracted)

            # Set DscState to standby
            dsc_state = await self.get_dsc_state()
            await dsc_state.write_value(ua.DscStateType.Standby)

        return ua.CmdResponseType.CommandDone

    @uamethod
    async def move_2_band(self, parent, band: enum.Enum) -> enum.Enum:
        logging.info("Move2Band method called with parameter %s", ua.BandType(band))

        # 1. Feed indexer starts moving
        # FeedIndexer:AxisMoving = True
        logging.info("Updating AxisMoving")
        axis_moving = await self.get_fi_axis_moving()
        await axis_moving.write_value(True)

        # 2. Low power active is set to False
        # Management: PowerStatus: Low_power = False
        logging.info("Updating PowerStatus")
        low_power_active = await self.get_low_power_active()
        await low_power_active.write_value(False)

        # Sleep for a random amount of time
        await asyncio.sleep(random.uniform(0.1, 1))

        # 3. Feed indexer stops moving
        # FeedIndexer:AxisMoving = False
        logging.info("Updating AxisMoving")
        await axis_moving.write_value(False)

        # 4. Feed indexer position changes to <band>
        logging.info("Updating FiPos")
        feed_indexer_position = await self.get_fi_pos()
        await feed_indexer_position.write_value(ua.BandType(band))

        return ua.CmdResponseType.CommandDone

    @uamethod
    async def stop(self, parent, axis: enum.Enum) -> enum.Enum:
        logging.info("Stop method called for axis %s!", ua.AxisSelectType(axis))

        # If the dish was tracking or slewing when stop is called on Azimuth or Elevation, then:
        # Transition to standstill
        # Stop tracking if tracking
        # Stop slewing if slewing
        if axis in [ua.AxisSelectType.Az, ua.AxisSelectType.El, ua.AxisSelectType.AzEl]:
            dsc_state_node = await self.get_dsc_state()
            dsc_state = await dsc_state_node.get_value()

            if self.tracking_stop_event is not None:
                self.tracking_stop_event.set()

                if self.tracking_thread is not None:
                    self.tracking_thread.join()

                self.tracking_stop_event = None
                self.tracking_thread = None

            if self.movement_stop_event is not None:
                self.movement_stop_event.set()

                if self.movement_thread is not None:
                    self.movement_thread.join()

                self.movement_stop_event = None
                self.movement_thread = None

            if dsc_state in [ua.DscStateType.Track, ua.DscStateType.Slew]:
                await dsc_state_node.write_value(ua.DscStateType.Standstill)

        if axis in [ua.AxisSelectType.Az, ua.AxisSelectType.AzEl]:
            # Set Az axisstate to Stop
            axis_moving = await self.get_az_axis_state()
            await axis_moving.write_value(ua.AxisStateType.Stop)

        if axis in [ua.AxisSelectType.El, ua.AxisSelectType.AzEl]:
            # Set El axisstate to Stop
            axis_moving = await self.get_el_axis_state()
            await axis_moving.write_value(ua.AxisStateType.Stop)

        if axis == ua.AxisSelectType.Fi:
            # Set Fi axisstate to Stop
            axis_moving = await self.get_fi_axis_state()
            await axis_moving.write_value(ua.AxisStateType.Stop)

        return ua.CmdResponseType.CommandDone

    @uamethod
    async def track_start_dm(
        self, parent, interpol: enum.Enum, start_time: float, start_stop: bool
    ) -> enum.Enum:
        logging.info(
            "TrackStartDM method called with %s, %s, %s!",
            ua.InterpolType(interpol),
            str(start_time),
            start_stop,
        )

        # Check if the track table has been loaded
        if self.track_table is not None:
            # Check if all the axis are activated
            axis_activated = await self.are_axis_activated()

            if not axis_activated:
                await self.management.call_method(
                    f"{self.idx}:Activate", ua.AxisSelectType.AzEl
                )
                await self.management.call_method(
                    f"{self.idx}:Activate", ua.AxisSelectType.Fi
                )

            # Start tracking
            logging.info("Moving")
            await self.start_moving_dish_parts()

            # Sleep for a random amount of time while "moving"
            await asyncio.sleep(start_time)

            # Set the axis to track
            axis_state = await self.get_el_axis_state()
            await axis_state.write_value(ua.AxisStateType.Track)
            axis_state = await self.get_az_axis_state()
            await axis_state.write_value(ua.AxisStateType.Track)

            # Set DscState to track
            dsc_state = await self.get_dsc_state()
            await dsc_state.write_value(ua.DscStateType.Track)

            # Start a new thread which will create its own asyncio
            # event loop to run the dish tracking task on it
            logging.info("Creating thread for tracking task")

            self.tracking_stop_event = threading.Event()
            self.tracking_thread = threading.Thread(
                target=self.run_dish_tracking_task,
                args=(interpol, self.tracking_stop_event),
            )
            self.tracking_thread.start()
        else:
            logging.error("TrackStart: No track table loaded")
            raise Exception("No track table loaded")

        return ua.CmdResponseType.CommandDone

    @uamethod
    async def slew_abs(
        self, parent, pos_az: float, pos_el: float, speed_az: float, speed_el: float
    ) -> enum.Enum:
        logging.info(
            "Slew2AbsAzEl method called with %s, %s, %s, %s!",
            str(pos_az),
            str(pos_el),
            str(speed_az),
            str(speed_el),
        )

        # If stowed, unstow
        is_stowed = await self.is_dish_stowed()

        if is_stowed:
            await self.management.call_method(f"{self.idx}:Stow", False)

        # If not activated, activate
        axis_activated = await self.are_axis_activated()

        if not axis_activated:
            await self.management.call_method(
                f"{self.idx}:Activate", ua.AxisSelectType.AzEl
            )

        # Slew
        self.movement_stop_event = threading.Event()
        self.movement_thread = threading.Thread(
            target=self.run_dish_movement_task,
            args=(pos_az, pos_el, speed_az, speed_el, self.movement_stop_event, False),
        )
        self.movement_thread.start()

        return ua.CmdResponseType.CommandDone

    @uamethod
    async def track_load_table(
        self, parent, load_mode: enum.Enum, sequence_length: int, track_table: any
    ) -> enum.Enum:
        logging.info(
            "TrackLoadTable method called with %s, %s, %s!",
            ua.LoadModeType(load_mode),
            str(sequence_length),
            track_table,
        )

        self.track_table = track_table

        return ua.CmdResponseType.CommandDone

    @uamethod
    async def new_mock_data_values(self, values_list):
        sine_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:sine_value",
            ]
        )
        await sine_value_node.write_value(values_list[0])

        cosine_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:cosine_value",
            ]
        )
        await cosine_value_node.write_value(values_list[1])

        i_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:increment",
            ]
        )
        await i_value_node.write_value(values_list[2])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:decrement",
            ]
        )
        await d_value_node.write_value(values_list[3])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:bool",
            ]
        )
        await d_value_node.write_value(values_list[4])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum",
            ]
        )
        await d_value_node.write_value(values_list[5])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress6",
            ]
        )
        await d_value_node.write_value(values_list[6])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress7",
            ]
        )
        await d_value_node.write_value(values_list[7])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress8",
            ]
        )
        await d_value_node.write_value(values_list[8])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress9",
            ]
        )
        await d_value_node.write_value(values_list[9])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress10",
            ]
        )
        await d_value_node.write_value(values_list[10])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress11",
            ]
        )
        await d_value_node.write_value(values_list[11])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress12",
            ]
        )
        await d_value_node.write_value(values_list[12])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress13",
            ]
        )
        await d_value_node.write_value(values_list[13])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress14",
            ]
        )
        await d_value_node.write_value(values_list[14])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress15",
            ]
        )
        await d_value_node.write_value(values_list[15])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress16",
            ]
        )
        await d_value_node.write_value(values_list[16])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress17",
            ]
        )
        await d_value_node.write_value(values_list[17])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress18",
            ]
        )
        await d_value_node.write_value(values_list[18])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress19",
            ]
        )
        await d_value_node.write_value(values_list[19])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress20",
            ]
        )
        await d_value_node.write_value(values_list[20])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress21",
            ]
        )
        await d_value_node.write_value(values_list[21])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress22",
            ]
        )
        await d_value_node.write_value(values_list[22])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress23",
            ]
        )
        await d_value_node.write_value(values_list[23])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress24",
            ]
        )
        await d_value_node.write_value(values_list[24])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress25",
            ]
        )
        await d_value_node.write_value(values_list[25])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress26",
            ]
        )
        await d_value_node.write_value(values_list[26])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress27",
            ]
        )
        await d_value_node.write_value(values_list[27])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress28",
            ]
        )
        await d_value_node.write_value(values_list[28])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress29",
            ]
        )
        await d_value_node.write_value(values_list[29])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress30",
            ]
        )
        await d_value_node.write_value(values_list[30])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress31",
            ]
        )
        await d_value_node.write_value(values_list[31])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress32",
            ]
        )
        await d_value_node.write_value(values_list[32])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress33",
            ]
        )
        await d_value_node.write_value(values_list[33])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress34",
            ]
        )
        await d_value_node.write_value(values_list[34])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress35",
            ]
        )
        await d_value_node.write_value(values_list[35])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress36",
            ]
        )
        await d_value_node.write_value(values_list[36])

        d_value_node = await self.plc_prg.get_child(
            [
                f"{self.idx}:MockData",
                f"{self.idx}:enum_stress37",
            ]
        )
        await d_value_node.write_value(values_list[37])


async def main():
    import numpy as np

    # list workaround for weird multiple parameter problem with File
    # "/home/oskiv/ska-mid-dish-simulators/.venv/lib/python3.10/site-packages/asyncua/
    # common/methods.py", line 96, in <listcomp>
    values = [
        0.0,
        0.0,
        0.0,
        9223372036854775.0,
        True,
        0,  # original
        0,  # stress test
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    ]
    async with DSSimulatorOPCUAServer() as server:
        await server.new_mock_data_values(values)
        count = 0
        while True:
            count += 1
            await asyncio.sleep(0.05)
            values[2] += 0.1
            values[3] += -1
            values[0] = np.sin(values[2])
            values[1] = np.cos(values[2])
            if values[4]:
                values[4] = False
            else:
                values[4] = True
            values[5] = count % 13

            for i in range(6, 38):
                values[i] = (count + i) % 13

            await server.new_mock_data_values(values)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
