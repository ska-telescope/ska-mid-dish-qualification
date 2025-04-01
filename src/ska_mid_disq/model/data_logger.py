"""DiSQ data logger."""

import logging
import os
import queue
import threading
from datetime import datetime, timedelta, timezone
from typing import Final, Optional, TypedDict

import h5py

from ska_mid_disq import SteeringControlUnit
from ska_mid_disq.constants import CURRENT_POINTING_NODE, NamePlate

app_logger = logging.getLogger("datalog")


class NodeData(TypedDict, total=False):
    """A dictionary to hold the data for a node."""

    period: int
    on_change: bool
    node_type: str
    enum_strings: Optional[list[str]]


# pylint: disable=too-many-instance-attributes
class DataLogger:
    """Data logger class for DiSQ software."""

    # Constants
    _CHUNK_SIZE_BYTES: Final = 4096
    _CHUNK_BOOL: Final = _CHUNK_SIZE_BYTES / 1  # A bool is 1 byte
    _CHUNK_DOUBLE: Final = _CHUNK_SIZE_BYTES / 8  # 512
    _CHUNK_ENUM: Final = _CHUNK_SIZE_BYTES / 4  # 1024
    _CHUNK_CURRENT_POINTING: Final = int(_CHUNK_SIZE_BYTES / (7 * 8))  # 73
    _CHUNK_STRING: Final = int(_CHUNK_SIZE_BYTES / 20)  # 204
    _CHUNK_UINT16: Final = _CHUNK_SIZE_BYTES / 2  # 2048
    _CHUNK_UINT32: Final = _CHUNK_SIZE_BYTES / 4  # 1024
    _CHUNKS_PER_FLUSH: Final = 2
    _FLUSH_BOOL: Final = _CHUNK_BOOL * _CHUNKS_PER_FLUSH
    _FLUSH_DOUBLE: Final = _CHUNK_DOUBLE * _CHUNKS_PER_FLUSH
    _FLUSH_ENUM: Final = _CHUNK_ENUM * _CHUNKS_PER_FLUSH
    _FLUSH_CURRENT_POINTING: Final = _CHUNK_CURRENT_POINTING * _CHUNKS_PER_FLUSH
    _FLUSH_STRING: Final = _CHUNK_STRING * _CHUNKS_PER_FLUSH
    _FLUSH_UINT16: Final = _CHUNK_UINT16 * _CHUNKS_PER_FLUSH
    _FLUSH_UINT32: Final = _CHUNK_UINT32 * _CHUNKS_PER_FLUSH
    _FLUSH_PERIOD_MSECS: Final = 5000
    _QUEUE_GET_TIMEOUT_SECS: Final = 0.01
    _COMPLETION_LOOP_TIMEOUT_SECS: Final = 0.01
    _PUBLISHING_INTERVAL_MSECS: Final = 1000
    _HDF5_TYPE_FROM_VALUE_TYPE: Final = {
        "Boolean": "?",
        "Double": "f8",  # 64 bit double numpy type
        "Enumeration": "u4",  # 32 bit unsigned integer numpy type
        CURRENT_POINTING_NODE: "(7,)f8",
        "String": "S20",  # 19 character zero-terminated bytes (IPv4 address)
        "UInt16": "u2",
        "UInt32": "u4",
    }
    _CHUNKS_FROM_VALUE_TYPE: Final = {
        "Boolean": _CHUNK_BOOL,
        "Double": _CHUNK_DOUBLE,
        "Enumeration": _CHUNK_ENUM,
        CURRENT_POINTING_NODE: _CHUNK_CURRENT_POINTING,
        "String": _CHUNK_STRING,
        "UInt16": _CHUNK_UINT16,
        "UInt32": _CHUNK_UINT32,
    }
    _FLUSH_FROM_VALUE_TYPE: Final = {
        "Boolean": _FLUSH_BOOL,
        "Double": _FLUSH_DOUBLE,
        "Enumeration": _FLUSH_ENUM,
        CURRENT_POINTING_NODE: _FLUSH_CURRENT_POINTING,
        "String": _FLUSH_STRING,
        "UInt16": _FLUSH_UINT16,
        "UInt32": _FLUSH_UINT32,
    }
    _TOTAL_COUND_IDX: Final = 0
    _TYPE_IDX: Final = 1
    _COUNT_IDX: Final = 2
    _TIMESTAMP_IDX: Final = 3
    _VALUE_IDX: Final = 4

    _ROOT_ATTRIBUTES: Final = [e.value for e in NamePlate]

    def __init__(
        self,
        high_level_library: SteeringControlUnit,
        file_name: str = None,
    ):
        """
        Initialize the Logger object.

        :param file_name: The name of the file to log data to.
        :param high_level_library: An optional high level library object to use for data
            manipulation.
        """
        self.hll = high_level_library
        self.file = file_name
        self._thread = threading.Thread(
            group=None, target=self._log, name="Logger internal thread"
        )
        self.queue: queue.Queue = queue.Queue(maxsize=0)
        self._data_count = 0
        self._nodes: dict[str, NodeData] | None = None
        self._stop_logging = threading.Event()
        self._start_invoked = False
        self._cache: dict = {}
        self._available_attributes = self.hll.get_attribute_list()
        self._subscription_ids: list = []
        self.file_object: h5py.File
        self.subscription_start_time: datetime
        self.subscription_stop_time: datetime

    def add_nodes(self, nodes: list[str], period: int, on_change: bool = True) -> None:
        """
        Add a node or list of nodes with desired period in milliseconds to subscribe to.

        Subsequent calls with the same node will overwrite the period.
        """
        if self._start_invoked:
            app_logger.warning(
                "WARNING: nodes cannot be added after start() has been invoked."
            )
            return

        if self._nodes is None:
            self._nodes = {}

        for node in list(nodes):
            if node not in self._available_attributes:
                app_logger.info(
                    '"%s" not available as an attribute on the server, skipping.',
                    node,
                )
                continue

            if node in self._ROOT_ATTRIBUTES:
                app_logger.info(
                    "%s is automatically included as an attribute of the HDF5 root "
                    "group and will not be logged further.",
                    node,
                )
                continue

            node_strings = self.hll.get_attribute_data_type(node)
            node_type = node_strings.pop(0)
            if node_type == "Float":
                node_type = "Double"

            if node_type not in self._HDF5_TYPE_FROM_VALUE_TYPE:
                app_logger.info(
                    'Unsupported type for "%s": "%s"; skipping. '
                    'Nodes must be of type "Boolean"/"Double"/"Enumeration".',
                    node,
                    node_type,
                )
                continue

            if node in self._nodes:
                app_logger.info(
                    "Updating period for node %s from %d to %d.",
                    node,
                    self._nodes[node]["period"],
                    period,
                )

            node_data: NodeData = {
                "period": period,
                "node_type": node_type,
                "on_change": on_change,
            }
            if node_type == "Enumeration":
                node_data["enum_strings"] = node_strings

            self._nodes[node] = node_data

    def _build_hdf5_structure(self) -> None:
        """
        Build the HDF5 structure for storing data.

        This method creates the necessary groups and datasets within an HDF5 file for
        storing data.
        """
        for node in NamePlate:
            node_string = node.value
            try:
                value = self.hll.attributes[node_string].value  # type: ignore
            except KeyError:
                app_logger.warning(
                    "WARNING: node %s is not available on the server. "
                    "HDF5 file will not contain %s.",
                    node_string,
                    node_string,
                )
            else:
                try:
                    self.file_object.attrs.create(node_string, value)
                except TypeError as e:
                    app_logger.error(
                        "ERROR: Could not create attr for %s; %s",
                        node_string,
                        e,
                    )

        for node_name, data in self._nodes.items():
            # One group per node containing a single dataset for each of
            # SourceTimestamp, Value
            group = self.file_object.create_group(node_name)
            # Zeroeth dataset is always source timestamp which must be an 8 byte float
            # as HDF5 does not support Python datetime.
            time_dataset = group.create_dataset(
                "SourceTimestamp",
                dtype="f8",
                shape=(0,),
                chunks=(self._CHUNK_DOUBLE,),
                maxshape=(None,),
            )
            time_dataset.attrs.create(
                "Info", "Source Timestamp; time since Unix epoch."
            )

            value_type = data["node_type"]
            dtype = self._HDF5_TYPE_FROM_VALUE_TYPE[value_type]
            value_chunks = self._CHUNKS_FROM_VALUE_TYPE[value_type]
            value_dataset = group.create_dataset(
                "Value",
                dtype=dtype,
                shape=(0,),
                chunks=(value_chunks,),
                maxshape=(None,),
            )
            value_dataset.attrs.create(
                "Info", "Node Value, index matches SourceTimestamp dataset."
            )
            value_dataset.attrs.create("node_type", value_type)
            if value_type == "Enumeration":
                value_dataset.attrs.create(
                    "Enumerations", ",".join(data["enum_strings"])
                )

            # While here create cache structure per node.
            # Node name : [total data point count, type string, current data point count
            #                , [timestamp 1, timestamp 2, ...], [value 1, value 2, ...]]
            #                            ^ list indices match for data points ^
            self._cache[node_name] = [0, value_type, 0, [], []]

        # HDF5 structure created, can now enter SWMR mode
        self.file_object.swmr_mode = True

    def _subscribe_to_nodes(self):
        """
        Subscribe to nodes with specified attributes and periods.

        This method subscribes to nodes with specific attributes and periods provided
        in the `_nodes` dictionary attribute of the class instance.
        """
        # Sort added nodes into lists per period
        combinations: dict[tuple[int, bool], list[str]] = {}
        for node, data in self._nodes.items():
            tuple_key = (data["period"], data["on_change"])
            if tuple_key not in combinations:
                combinations[tuple_key] = []

            combinations[tuple_key].append(node)

        # Start to fill queue
        self.subscription_start_time = self.hll.attributes[
            "Server.ServerStatus.CurrentTime"
        ].value
        for combo, attributes in combinations.items():
            period, on_change = combo
            if period <= self._PUBLISHING_INTERVAL_MSECS:  # Default
                publishing_interval = self._PUBLISHING_INTERVAL_MSECS
                buffer_samples = True
            else:
                publishing_interval = period
                buffer_samples = False
            self._subscription_ids.append(
                self.hll.subscribe(
                    attributes=attributes,
                    publishing_interval=publishing_interval,
                    sampling_interval=period,
                    data_queue=self.queue,
                    buffer_samples=buffer_samples,
                    trigger_on_change=on_change,
                )[0]
            )

    def start(self):
        """
        Start logging the nodes added by add_nodes().

        Creates and uses a thread internally.
        """
        if not self._nodes:
            app_logger.warning("WARNING: No nodes to subscribe to. Exiting.")
            return

        if self._start_invoked:
            app_logger.warning("WARNING: start() can only be invoked once per object.")
            return

        self._start_invoked = True
        self._stop_logging.clear()

        if self.file is None:
            file = (
                "results/"
                + datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
                + ".hdf5"
            )
            self.file = os.path.abspath(file)

        basedir = os.path.dirname(self.file)
        if basedir != "" and not os.path.exists(basedir):
            os.makedirs(basedir)

        app_logger.info("Writing data to file: %s", self.file)
        self.file_object = h5py.File(self.file, "w", libver="latest")

        self._subscribe_to_nodes()

        self._thread.start()

    def stop(self):
        """
        Stop logging.

        Ends the addition of new server data to internal queue and waits for the logging
        thread to clear the remaining queued items.
        """
        for uid in self._subscription_ids:
            self.hll.unsubscribe(uid)

        self.subscription_stop_time = self.hll.attributes[
            "Server.ServerStatus.CurrentTime"
        ].value
        self._stop_logging.set()

        if self._thread.is_alive():
            self._thread.join()

    def _add_time_attributes(self):
        """Add subscription and data start/stop times to root file object."""
        with h5py.File(self.file, "a", libver="latest") as fo:
            fo.attrs.create(
                "Subscription start time",
                self.subscription_start_time.isoformat(timespec="microseconds"),
            )
            fo.attrs.create(
                "Subscription stop time",
                self.subscription_stop_time.isoformat(timespec="microseconds"),
            )
            first_last_timestamps = []
            for group in fo:
                try:
                    first_last_timestamps.append(fo[group]["SourceTimestamp"][0])
                    first_last_timestamps.append(fo[group]["SourceTimestamp"][-1])
                except IndexError:
                    app_logger.debug(
                        "Could not get timestamp for empty dataset %s", group
                    )

            if len(first_last_timestamps) > 0:
                data_start_time = datetime.fromtimestamp(
                    min(first_last_timestamps), tz=timezone.utc
                )
                data_stop_time = datetime.fromtimestamp(
                    max(first_last_timestamps), tz=timezone.utc
                )
            else:
                app_logger.warning(
                    "No timestamp data recorded, data time will match subscription "
                    "times."
                )
                data_start_time = self.subscription_start_time
                data_stop_time = self.subscription_stop_time

            fo.attrs.create(
                "Data start time",
                data_start_time.isoformat(timespec="microseconds"),
            )
            fo.attrs.create(
                "Data stop time",
                data_stop_time.isoformat(timespec="microseconds"),
            )
            fo.close()
            app_logger.debug(
                "File start time: %s, and stop time: %s",
                data_start_time,
                data_stop_time,
            )

    def _write_cache_to_group(self, node: str) -> None:
        """Write the cache to the matching group for the given node."""
        group = self.file_object[node]
        cache = self._cache[node]
        # Dataset lengths will always match as they are only written here
        curr_len = group["SourceTimestamp"].len()

        group["SourceTimestamp"].resize(curr_len + cache[self._COUNT_IDX], axis=0)
        group["SourceTimestamp"][-cache[self._COUNT_IDX] :] = cache[self._TIMESTAMP_IDX]
        group["SourceTimestamp"].flush()

        group["Value"].resize(curr_len + cache[self._COUNT_IDX], axis=0)
        group["Value"][-cache[self._COUNT_IDX] :] = cache[self._VALUE_IDX]
        group["Value"].flush()

        # Cache has been written to file so clear it
        self._cache[node] = [
            self._cache[node][self._TOTAL_COUND_IDX],
            self._cache[node][self._TYPE_IDX],
            0,
            [],
            [],
        ]

    def _log(self):
        """
        Log data points to a cache and write them to a file periodically.

        This method logs data points to a cache and periodically writes them to a file.
        It also provides debug and info logging messages.

        This method does not have any parameters or return values.

        """
        self._build_hdf5_structure()
        next_flush_interval = datetime.now(timezone.utc) + timedelta(
            milliseconds=self._FLUSH_PERIOD_MSECS
        )
        while not self._stop_logging.is_set():
            try:
                datapoint = self.queue.get(
                    block=True, timeout=self._QUEUE_GET_TIMEOUT_SECS
                )
            except queue.Empty:
                pass
            else:
                self._data_count += 1
                node = datapoint["name"]
                if datapoint["value"] is None:
                    app_logger.error(
                        "Error: Got None value from node subscription %s", node
                    )
                    continue

                self._cache[node][self._TIMESTAMP_IDX].append(
                    datapoint["source_timestamp"]
                    .replace(tzinfo=timezone.utc)
                    .timestamp()
                )
                self._cache[node][self._VALUE_IDX].append(datapoint["value"])
                self._cache[node][self._COUNT_IDX] += 1
                self._cache[node][self._TOTAL_COUND_IDX] += 1

                # Write to file when cache reaches multiple of chunk size for value type
                if (
                    self._cache[node][self._TOTAL_COUND_IDX]
                    % self._FLUSH_FROM_VALUE_TYPE[self._cache[node][self._TYPE_IDX]]
                    == 0
                ):
                    self._write_cache_to_group(node)
                    app_logger.debug(
                        "Number of items in queue (cache write): %d",
                        self.queue.qsize(),
                    )

            # Write to file at least every self._FLUSH_PERIOD_MSECS
            if next_flush_interval < datetime.now(timezone.utc):
                for cache_node, cache in self._cache.items():
                    if cache[self._COUNT_IDX] > 0:
                        self._write_cache_to_group(cache_node)
                app_logger.debug(
                    "Number of items in queue (flush write): %d",
                    self.queue.qsize(),
                )

                next_flush_interval += timedelta(milliseconds=self._FLUSH_PERIOD_MSECS)

        app_logger.debug(
            "Number of items in queue (final write): %d", self.queue.qsize()
        )
        # Subscriptions have been stopped: clear remaining queue, flush and close file.
        while not self.queue.empty():
            datapoint = self.queue.get(block=True, timeout=self._QUEUE_GET_TIMEOUT_SECS)
            self._data_count += 1
            node = datapoint["name"]
            if datapoint["value"] is None:
                app_logger.error(
                    "Error: Got None value from node subscription %s", node
                )
                continue

            self._cache[node][self._TIMESTAMP_IDX].append(
                datapoint["source_timestamp"].timestamp()
            )
            self._cache[node][self._VALUE_IDX].append(datapoint["value"])
            self._cache[node][self._COUNT_IDX] += 1
            self._cache[node][self._TOTAL_COUND_IDX] += 1

        for cache_node, cache in self._cache.items():
            if cache[self._COUNT_IDX] > 0:
                self._write_cache_to_group(cache_node)

        self.file_object.close()
        app_logger.info("Logger received %d data points.", self._data_count)

        self._add_time_attributes()
