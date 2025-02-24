"""
SteeringControlUnit now with weather station connectivity.

Subclass of SteeringControlUnit that can connect to a weather station and include its
sensors as SCU attributes.
"""

import logging
import queue
import threading
from typing import Any, Callable

from asyncua import ua
from ska_mid_dish_steering_control.sculib import SubscriptionHandler
from ska_mid_wms_interface import SensorEnum, WeatherStation

from ska_mid_disq import SteeringControlUnit

logger = logging.getLogger("ska-mid-ds-scu")


class SCUWeatherStation(SteeringControlUnit):
    """
    SteeringControlUnit with weather station connectivity.

    Subclass of SteeringControlUnit that can connect to a weather station and include
    its sensors as SCU attributes.
    """

    def __init__(self, *args, **kwargs):
        """Initialise SCUWeatherStation."""
        super().__init__(*args, **kwargs)
        self._weather_station: WeatherStation | None = None
        self._weather_station_subscription = None
        self._weather_station_cache = None
        self._weather_station_cache_lock = None
        self.weather_station_attributes = []
        self._scu_weather_station_subscriptions = {}

    def disconnect_and_cleanup(self) -> None:
        """
        Disconnect from server and clean up SCU client resources.

        Release any command authority, unsubscribe from all subscriptions, disconnect
        from the server, and stop the event loop if it was started in a separate thread.
        """
        super().disconnect_and_cleanup()
        self.disconnect_weather_station()

    def get_attribute_data_type(self, attribute: str | ua.uatypes.NodeId) -> list[str]:
        """
        Get the data type for the given node.

        Returns a list of strings for the type or "Unknown" for a not yet known type.
        For most types the list is length one, for enumeration types the list is
        "Enumeration" followed by the strings of the enumeration, where the index of the
        string in the list is the enum value + 1.
        """
        if attribute in self.weather_station_attributes:
            # TODO Check whether a weather station sensor can be a different type.
            return ["Double"]

        return super().get_attribute_data_type(attribute)

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def subscribe(
        self,
        attributes: str | list[str],
        period: int = 100,
        data_queue: queue.Queue | None = None,
        bad_shutdown_callback: Callable[[str], None] | None = None,
        subscription_handler: SubscriptionHandler | None = None,
    ) -> tuple[int, list, list]:
        """
        Subscribe to SCU attributes for event updates.

        :param attributes: A single SCU attribute or a list of attributes to
            subscribe to.
        :param period: The period in milliseconds for checking attribute updates
            (ignored for weather station sensors).
        :param data_queue: A queue to store the subscribed attribute data. If None, uses
            the default subscription queue.
        :return: unique identifier for the subscription and lists of missing/bad nodes.
        :param bad_shutdown_callback: will be called if a BadShutdown subscription
            status notification is received, defaults to None.
        :param subscription_handler: Allows for a SubscriptionHandler instance to be
            reused, rather than creating a new instance every time.
            There is a limit on the number of handlers a server can have.
            Defaults to None.
        """
        if data_queue is None:
            data_queue = self._subscription_queue

        uid, missing_nodes, bad_nodes = super().subscribe(
            attributes,
            period=period,
            data_queue=data_queue,
            bad_shutdown_callback=bad_shutdown_callback,
        )
        sensors = []
        missing_nodes_copy = missing_nodes.copy()
        for node in missing_nodes_copy:
            if node in self.weather_station_attributes:
                sensors.append(node)
                missing_nodes.remove(node)

        if sensors:
            # Send one value on first subscription of weather station sensor
            for sensor in sensors:
                data_queue.put(
                    {
                        "name": sensor,
                        "value": self._attributes[sensor].value,
                        "source_timestamp": self._attributes[sensor].timestamp,
                    },
                    block=True,
                    timeout=0.1,
                )
            self._scu_weather_station_subscriptions[uid] = {
                "sensors": sensors,
                "data_queue": data_queue,
            }

        if missing_nodes:
            msg = "The following attributes could not be found on the OPCUA server"
            if self._weather_station:
                msg += " or weather station"

            msg += ": %s"
            logger.info(msg, missing_nodes)

        return uid, missing_nodes, bad_nodes

    def unsubscribe(self, uid: int) -> None:
        """
        Unsubscribe a user from a subscription.

        :param uid: The ID of the user to unsubscribe.
        """
        self._scu_weather_station_subscriptions.pop(uid, None)
        if uid in self._subscriptions:
            super().unsubscribe(uid)

    def unsubscribe_all(self) -> None:
        """Unsubscribe all subscriptions."""
        uids = list(self._subscriptions.keys()) + list(
            self._scu_weather_station_subscriptions.keys()
        )
        for uid in uids:
            self.unsubscribe(uid)

    # ---------------
    # Weather Station
    # ---------------
    def list_weather_station_sensors(self) -> list[str]:
        """
        List all the sensors available on the connected weather station.

        :return: A list of sensors names.
        """
        if self._weather_station is not None:
            return [sensor.name for sensor in self._weather_station.available_sensors]

        return []

    def _create_ro_ws_attribute(self, sensor):
        ws_cache_lock = self._weather_station_cache_lock
        ws_cache = self._weather_station_cache

        class WeatherStationAttribute:
            # pylint: disable=too-few-public-methods,missing-class-docstring
            # pylint: disable=missing-function-docstring,broad-exception-caught
            @property
            def value(self) -> Any:
                try:
                    with ws_cache_lock:
                        return ws_cache[sensor]["value"]
                except Exception as e:
                    logger.error(
                        "Failed to read value of sensor: weather.station.%s: %s",
                        sensor,
                        e,
                    )
                    return None

            @property
            def timestamp(self) -> Any:
                try:
                    with ws_cache_lock:
                        return ws_cache[sensor]["timestamp"]
                except Exception as e:
                    logger.error(
                        "Failed to read value of sensor: weather.station.%s: %s",
                        sensor,
                        e,
                    )
                    return None

        return WeatherStationAttribute()

    def _update_weather_station_sensors(self, sensors):
        if self._weather_station is None:
            return

        self._weather_station_cache = {}
        self._weather_station_cache_lock = threading.Lock()
        self.weather_station_attributes = []
        for sensor in sensors:
            self._weather_station_cache[sensor] = {
                "value": None,
                "timestamp": None,
            }
            # Add to attributes
            scu_name = f"weather.station.{sensor}"
            self._attributes[scu_name] = self._create_ro_ws_attribute(sensor)
            self.weather_station_attributes.append(scu_name)

        def weather_station_callback(datapoints):
            for sensor, datapoint in datapoints.items():
                new_value = datapoint["value"]
                old_value = self._weather_station_cache[sensor]["value"]
                if new_value != old_value:
                    with self._weather_station_cache_lock:
                        self._weather_station_cache[sensor] = {
                            "value": new_value,
                            "timestamp": datapoint["timestamp"],
                        }

                    scu_name = f"weather.station.{sensor}"
                    for (
                        subscription
                    ) in self._scu_weather_station_subscriptions.values():
                        if scu_name in subscription["sensors"]:
                            subscription["data_queue"].put(
                                {
                                    "name": scu_name,
                                    "value": new_value,
                                    "source_timestamp": datapoint["timestamp"],
                                },
                                block=True,
                                timeout=0.1,
                            )

        self._weather_station.configure_poll_sensors(
            [SensorEnum(sensor) for sensor in sensors]
        )
        self._weather_station_subscription = self._weather_station.subscribe_data(
            weather_station_callback
        )

    def _clear_weather_station_attributes(self):
        for sensor in self.weather_station_attributes:
            self._attributes.pop(sensor, None)

        self.weather_station_attributes = []

    def _clear_weather_station_subscriptions(self):
        uids = list(self._scu_weather_station_subscriptions.keys())
        for uid in uids:
            self.unsubscribe(uid)

    def change_weather_station_sensors(self, new_sensors: list[str]) -> None:
        """
        Change the weather station sensors available.

        Updates the weather station to poll only new_sensors. Also adds/removes to the
        attributes dictionary as necessary to match new_sensors.

        WARNING: This will stop all SCU subscriptions to weather data.

        :param new_sensors: A list of the sensors to be used.
        """
        if self._weather_station is None:
            logger.error("No weather station connected, cannot change sensors.")
            return

        available_sensors = self.list_weather_station_sensors()
        for sensor in new_sensors:
            if sensor not in available_sensors:
                logger.error(
                    "Sensor %s is not available in the connected weather station, "
                    "cannot change sensors.",
                    sensor,
                )
                return

        if self._weather_station_subscription is not None:
            self._weather_station.unsubscribe_data(self._weather_station_subscription)
            self._weather_station_subscription = None
        self._clear_weather_station_attributes()
        self._clear_weather_station_subscriptions()
        self._update_weather_station_sensors(new_sensors)

    def connect_weather_station(self, config: str, address: str, port: int) -> None:
        """
        Connect to a weather station and start polling.

        :param address: The IP addresss of the weather station.
        :param port: The port of the weather station.
        :param config: The weather station config file.
        """
        self._weather_station = WeatherStation(config, address, port, logger)
        self._weather_station.start_polling()

        # Default to all sensors in config file
        sensors = self.list_weather_station_sensors()
        self.change_weather_station_sensors(sensors)

    def disconnect_weather_station(self) -> None:
        """Disconnect from the weather station, if any."""
        if self._weather_station is None:
            return

        self._scu_weather_station_subscriptions = {}
        self._weather_station.unsubscribe_data(self._weather_station_subscription)
        self._weather_station_subscription = None
        self._clear_weather_station_attributes()
        self._clear_weather_station_subscriptions()
        self._weather_station.stop_polling()
        self._weather_station.disconnect()
        self._weather_station_cache = None
        self._weather_station_cache_lock = None
        self._weather_station = None

    def is_weather_station_connected(self) -> bool:
        """
        Check if the SCU is connected to a weather station.

        :return: True if the SCU has a weather station, False otherwise.
        """
        return self._weather_station is not None
