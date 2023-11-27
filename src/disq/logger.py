import h5py
import threading
import queue
import os
from datetime import datetime, timedelta
from time import sleep
import logging

from disq import sculib

app_logger = logging.getLogger("hdf5_logger")
app_logger.setLevel(logging.INFO)


class Logger:
    """Logger for DiSQ software."""

    # Constants
    _MAX_ENUM_STR_LEN_BYTES = 64
    _CHUNK_SIZE_BYTES = 4096
    _CHUNK_DOUBLE = 4096 / 8  # 512
    _CHUNK_BOOL = 4096 / 1
    _CHUNK_ENUM = 4096 / 4  # 1024
    _CHUNKS_PER_FLUSH = 2
    _FLUSH_DOUBLE = _CHUNK_DOUBLE * _CHUNKS_PER_FLUSH
    _FLUSH_BOOL = _CHUNK_BOOL * _CHUNKS_PER_FLUSH
    _FLUSH_ENUM = _CHUNK_ENUM * _CHUNKS_PER_FLUSH
    _FLUSH_PERIOD_MSECS = 5000
    _QUEUE_GET_TIMEOUT_SECS = 0.01
    _COMPLETION_LOOP_TIMEOUT_SECS = 0.01
    _hdf5_type_from_value_type = {
        "Double": "f8",  # 64 bit double numpy type
        "Boolean": "?",
        "Enumeration": "u4",  # 32 bit unsigned integer numpy type
    }
    _chunks_from_value_type = {
        "Double": _CHUNK_DOUBLE,
        "Boolean": _CHUNK_BOOL,
        "Enumeration": _CHUNK_ENUM,
    }
    _flush_from_value_type = {
        "Double": _FLUSH_DOUBLE,
        "Boolean": _FLUSH_BOOL,
        "Enumeration": _FLUSH_ENUM,
    }

    _nodes = None
    _stop_logging = threading.Event()
    _start_invoked = False
    _cache = {}

    logging_complete = threading.Event()

    def __init__(
        self,
        file_name: str = None,
        high_level_library: sculib.scu = None,
        server: str = None,
        port: str = None,
    ):
        self.file = file_name
        self._thread = threading.Thread(
            group=None, target=self._log, name="Logger internal thread"
        )
        self.queue = queue.Queue(maxsize=0)
        self._data_count = 0

        if high_level_library is None:
            if server is None:
                self.hll = sculib.scu()
            else:
                self.hll = sculib.scu(host=server, port=port)
        else:
            self.hll = high_level_library

        self._available_attributes = self.hll.get_attribute_list()
        self._subscription_ids = []

    def add_nodes(self, nodes: list[str], period: int):
        """Add a node or list of nodes with desired period in miliseconds to be subscribed to.
        Subsequent calls with the same node will overwrite the period."""
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
                    f'"{node}" not available as an attribute on the server, skipping.'
                )
                continue

            type = self.hll.get_attribute_data_type(node)
            if type not in self._hdf5_type_from_value_type.keys():
                app_logger.info(
                    f'Unsupported type for "{node}": "{type}"; skipping. Nodes must be'
                    f' of type "Boolean"/"Double"/"Enumeration".'
                )
                continue

            if node in self._nodes:
                app_logger.info(
                    f"Updating period for node {node} from {self._nodes[node]} to "
                    f"{period}."
                )

            self._nodes[node] = period

    def _build_hdf5_structure(self):
        for node in self._nodes:
            # One group per node containing a single dataset for each of SourceTimestamp, Value.
            group = self.file_object.create_group(node)
            # Zeroeth dataset is always source timestamp which must be an 8 byte float as HDF5 does not support Python datetime.
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
            dtype = self._hdf5_type_from_value_type[value_type]
            value_chunks = self._chunks_from_value_type[value_type]
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
            # Node name : [total data point count, type string,
            # current data point count, [timestamp 1, timestamp 2, ...], [value 1, value 2, ...]]
            #                            ^ list indices match for data points ^
            self._cache[node] = [0, value_type, 0, [], []]

        # No magic numbers
        self._total_count_idx = 0
        self._type_idx = 1
        self._count_idx = 2
        self._timestamp_idx = 3
        self._value_idx = 4

        # HDF5 structure created, can now enter SWMR mode
        self.file_object.swmr_mode = True

    def _subscribe_to_nodes(self):
        # Sort added nodes into lists per period
        period_dict = {}
        for node, period in self._nodes.items():
            if period in period_dict.keys():
                period_dict[period].append(node)
            else:
                period_dict[period] = []
                period_dict[period].append(node)

        # Start to fill queue
        self.start_time = datetime.utcnow()
        for period, attributes in period_dict.items():
            self._subscription_ids.append(
                self.hll.subscribe(
                    attributes=attributes, period=period, data_queue=self.queue
                )
            )

    def start(self):
        """Start logging the nodes added by add_nodes(). Creates and uses a thread internally."""
        if self._start_invoked:
            app_logger.warning("WARNING: start() can only be invoked once per object.")
            return

        self._start_invoked = True
        self._stop_logging.clear()
        self.logging_complete.clear()

        if self.file is None:
            self.file = (
                "results/" + datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S") + ".hdf5"
            )

        basedir = os.path.dirname(self.file)
        if basedir != "" and not os.path.exists(basedir):
            os.makedirs(basedir)

        app_logger.info(f"Writing data to file: {self.file}")
        self.file_object = h5py.File(self.file, "w", libver="latest")
        self._build_hdf5_structure()

        self._subscribe_to_nodes()

        self._thread.start()

    def stop(self):
        """Stop logging. Ends the addition of new server data to internal queue
        and signals the logging thread to clear the remaining queued items."""
        for id in self._subscription_ids:
            self.hll.unsubscribe(id)

        self.stop_time = datetime.utcnow()
        self._stop_logging.set()

    def _write_cache_to_group(self, node: str):
        """Write the cache to the matching group for the given node."""
        group = self.file_object[node]
        cache = self._cache[node]
        # Dataset lengths will always match as they are only written here
        curr_len = group["SourceTimestamp"].len()

        group["SourceTimestamp"].resize(curr_len + cache[self._count_idx], axis=0)
        group["SourceTimestamp"][-cache[self._count_idx] :] = cache[self._timestamp_idx]
        group["SourceTimestamp"].flush()

        group["Value"].resize(curr_len + cache[self._count_idx], axis=0)
        group["Value"][-cache[self._count_idx] :] = cache[self._value_idx]
        group["Value"].flush()

        # Cache has been written to file so clear it
        self._cache[node] = [
            self._cache[node][self._total_count_idx],
            self._cache[node][self._type_idx],
            0,
            [],
            [],
        ]

    def _log(self):
        next_flush_interval = datetime.now() + timedelta(
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
                self._cache[node][self._timestamp_idx].append(
                    datapoint["source_timestamp"].timestamp()
                )
                self._cache[node][self._value_idx].append(datapoint["value"])
                self._cache[node][self._count_idx] += 1
                self._cache[node][self._total_count_idx] += 1

                # Write to file when cache reaches multiple of chunk size for value type
                if (
                    self._cache[node][self._total_count_idx]
                    % self._flush_from_value_type[self._cache[node][self._type_idx]]
                    == 0
                ):
                    self._write_cache_to_group(node)
                    app_logger.debug(
                        f"Number of items in queue (cache write): {self.queue.qsize()}"
                    )

            # Write to file at least every self._FLUSH_PERIOD_MSECS
            if next_flush_interval < datetime.now():
                for cache_node, cache in self._cache.items():
                    if cache[self._count_idx] > 0:
                        self._write_cache_to_group(cache_node)
                app_logger.debug(
                    f"Number of items in queue (flush write): {self.queue.qsize()}"
                )

                next_flush_interval += timedelta(milliseconds=self._FLUSH_PERIOD_MSECS)

        app_logger.debug(
            f"Number of items in queue (final write): {self.queue.qsize()}"
        )
        # Subscriptions have been stopped so clear remaining queue, do a final flush, and close file.
        while not self.queue.empty():
            datapoint = self.queue.get(block=True, timeout=self._QUEUE_GET_TIMEOUT_SECS)
            self._data_count += 1
            node = datapoint["name"]
            self._cache[node][self._timestamp_idx].append(
                datapoint["source_timestamp"].timestamp()
            )
            self._cache[node][self._value_idx].append(datapoint["value"])
            self._cache[node][self._count_idx] += 1
            self._cache[node][self._total_count_idx] += 1

        for cache_node, cache in self._cache.items():
            if cache[self._count_idx] > 0:
                self._write_cache_to_group(cache_node)

        self.file_object.close()
        app_logger.info(f"Logger received {self._data_count} data points.")
        self.file_object = h5py.File(self.file, "a", libver="latest")
        self.file_object.attrs.create(
            "Start time", self.start_time.isoformat(timespec="microseconds")
        )
        self.file_object.attrs.create(
            "Stop time", self.stop_time.isoformat(timespec="microseconds")
        )
        self.file_object.close()
        app_logger.debug(
            f"File start time: {self.start_time} and stop time: {self.stop_time}"
        )

        self.logging_complete.set()

    def wait_for_completion(self):
        """Wait for logging thread to write all data from the internal queue to file."""
        if not self._start_invoked:
            app_logger.warning(
                "WARNING: cannot wait for logging to complete if start() has not been "
                "invoked."
            )
            return

        if not self._stop_logging.is_set():
            app_logger.warning(
                "WARNING: cannot wait for logging to complete if stop() has not been "
                "invoked."
            )
            return

        while not self.logging_complete.is_set():
            sleep(self._COMPLETION_LOOP_TIMEOUT_SECS)
