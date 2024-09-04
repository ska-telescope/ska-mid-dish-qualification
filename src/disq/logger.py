"""DiSQ logger."""

import logging
import os
import queue
import threading
from datetime import datetime, timedelta, timezone
from typing import Final

import h5py
from ska_dish_steering_control.constants import NamePlate

from disq import sculib

app_logger = logging.getLogger("datalog")


# pylint: disable=too-many-instance-attributes
class Logger:
    """Data logger class for DiSQ software."""

    # Constants
    _CHUNK_SIZE_BYTES: Final = 4096
    _CHUNK_DOUBLE: Final = 4096 / 8  # 512
    _CHUNK_BOOL: Final = 4096 / 1
    _CHUNK_ENUM: Final = 4096 / 4  # 1024
    _CHUNK_CURRENT_POINTING: Final = int(4096 / (7 * 8))  # 73
    _CHUNKS_PER_FLUSH: Final = 2
    _FLUSH_DOUBLE: Final = _CHUNK_DOUBLE * _CHUNKS_PER_FLUSH
    _FLUSH_BOOL: Final = _CHUNK_BOOL * _CHUNKS_PER_FLUSH
    _FLUSH_ENUM: Final = _CHUNK_ENUM * _CHUNKS_PER_FLUSH
    _FLUSH_CURRENT_POINTING: Final = _CHUNK_CURRENT_POINTING * _CHUNKS_PER_FLUSH
    _FLUSH_PERIOD_MSECS: Final = 5000
    _QUEUE_GET_TIMEOUT_SECS: Final = 0.01
    _COMPLETION_LOOP_TIMEOUT_SECS: Final = 0.01
    _HDF5_TYPE_FROM_VALUE_TYPE: Final = {
        "Double": "f8",  # 64 bit double numpy type
        "Boolean": "?",
        "Enumeration": "u4",  # 32 bit unsigned integer numpy type
        "Pointing.Status.CurrentPointing": "(7,)f8",
    }
    _CHUNKS_FROM_VALUE_TYPE: Final = {
        "Double": _CHUNK_DOUBLE,
        "Boolean": _CHUNK_BOOL,
        "Enumeration": _CHUNK_ENUM,
        "Pointing.Status.CurrentPointing": _CHUNK_CURRENT_POINTING,
    }
    _FLUSH_FROM_VALUE_TYPE: Final = {
        "Double": _FLUSH_DOUBLE,
        "Boolean": _FLUSH_BOOL,
        "Enumeration": _FLUSH_ENUM,
        "Pointing.Status.CurrentPointing": _FLUSH_CURRENT_POINTING,
    }
    _TOTAL_COUND_IDX: Final = 0
    _TYPE_IDX: Final = 1
    _COUNT_IDX: Final = 2
    _TIMESTAMP_IDX: Final = 3
    _VALUE_IDX: Final = 4

    def __init__(
        self,
        high_level_library: sculib.SteeringControlUnit,
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
        self._nodes: dict | None = None
        self._stop_logging = threading.Event()
        self._start_invoked = False
        self._cache: dict = {}
        self._available_attributes = self.hll.get_attribute_list()
        self._subscription_ids: list = []
        self.file_object: h5py.File
        self.start_time: datetime
        self.stop_time: datetime

    def add_nodes(self, nodes: list[str], period: int) -> None:
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

            node_type = self.hll.get_attribute_data_type(node)
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
                    self._nodes[node],
                    period,
                )

            self._nodes[node] = period

    def _build_hdf5_structure(self) -> None:
        """
        Build the HDF5 structure for storing data.

        This method creates the necessary groups and datasets within an HDF5 file for
        storing data.
        """
        for node in NamePlate:
            node_string = node.value
            node_short = node_string.rsplit(".", 1)[1]
            try:
                value = self.hll.attributes[node_string].value  # type: ignore
            except KeyError:
                app_logger.warning(
                    "WARNING: node %s is not available on the server. "
                    "HDF5 file will not contain %s.",
                    node_string,
                    node_short,
                )
            else:
                try:
                    self.file_object.attrs.create(node_short, value)
                except TypeError as e:
                    app_logger.error(
                        "ERROR: Could not create attr for %s; %s",
                        node_string,
                        e,
                    )

        for node in self._nodes:
            # One group per node containing a single dataset for each of
            # SourceTimestamp, Value
            group = self.file_object.create_group(node)
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

            value_type = self.hll.get_attribute_data_type(node)
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
            value_dataset.attrs.create("Type", value_type)
            if value_type == "Enumeration":
                value_dataset.attrs.create(
                    "Enumerations", ",".join(self.hll.get_enum_strings(node))
                )

            # While here create cache structure per node.
            # Node name : [total data point count, type string, current data point count
            #                , [timestamp 1, timestamp 2, ...], [value 1, value 2, ...]]
            #                            ^ list indices match for data points ^
            self._cache[node] = [0, value_type, 0, [], []]

        # HDF5 structure created, can now enter SWMR mode
        self.file_object.swmr_mode = True

    def _subscribe_to_nodes(self):
        """
        Subscribe to nodes with specified attributes and periods.

        This method subscribes to nodes with specific attributes and periods provided
        in the `_nodes` dictionary attribute of the class instance.
        """
        # Sort added nodes into lists per period
        period_dict = {}
        for node, period in self._nodes.items():
            if period in period_dict:
                period_dict[period].append(node)
            else:
                period_dict[period] = []
                period_dict[period].append(node)

        # Start to fill queue
        self.start_time = datetime.now(timezone.utc)
        for period, attributes in period_dict.items():
            self._subscription_ids.append(
                self.hll.subscribe(
                    attributes=attributes, period=period, data_queue=self.queue
                )[0]
            )

    def start(self):
        """
        Start logging the nodes added by add_nodes().

        Creates and uses a thread internally.
        """
        if self._start_invoked:
            app_logger.warning("WARNING: start() can only be invoked once per object.")
            return

        self._start_invoked = True
        self._stop_logging.clear()

        if self.file is None:
            self.file = (
                "results/"
                + datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
                + ".hdf5"
            )

        basedir = os.path.dirname(self.file)
        if basedir != "" and not os.path.exists(basedir):
            os.makedirs(basedir)

        app_logger.info("Writing data to file: %s", self.file)
        self.file_object = h5py.File(self.file, "w", libver="latest")
        self._build_hdf5_structure()

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

        self.stop_time = datetime.now(timezone.utc)
        self._stop_logging.set()

        if self._thread.is_alive():
            self._thread.join()

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
        self.file_object = h5py.File(self.file, "a", libver="latest")
        self.file_object.attrs.create(
            "Start time", self.start_time.isoformat(timespec="microseconds")
        )
        self.file_object.attrs.create(
            "Stop time", self.stop_time.isoformat(timespec="microseconds")
        )
        self.file_object.close()
        app_logger.debug(
            "File start time: %s, and stop time: %s",
            self.start_time,
            self.stop_time,
        )
