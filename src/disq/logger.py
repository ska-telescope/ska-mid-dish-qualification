import h5py
import threading
import queue
import os
from datetime import datetime, timedelta
import warnings
from time import sleep

import sculib


class Logger:
    """Logger for DiSQ software."""

    # Constants
    _FLUSH_DOUBLE = 1024
    _FLUSH_PERIOD_MSECS = 5000
    _QUEUE_GET_TIMEOUT_SECS = 0.01
    _COMPLETION_LOOP_TIMEOUT_SECS = 0.01

    _nodes = None
    _stop_logging = threading.Event()
    _start_invoked = False
    _cache = {}
    _subscription_ids = []

    logging_complete = threading.Event()

    def __init__(
        self, file_name: str = None, high_level_library=None, server=None, port=None
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

    def add_nodes(self, nodes, period):
        """Add a node or list of nodes with desired period to be subscribed to.
        Subsequent calls with the same node will overwrite the period."""
        if self._start_invoked:
            warnings.warn(
                "WARNING: nodes cannot be added after start() has been invoked."
            )
            return

        if self._nodes is None:
            self._nodes = {}

        for node in list(nodes):
            if node not in self._available_attributes:
                print(
                    '"' + node + '"',
                    "not available as an attribute on the server, skipping.",
                )
                continue

            if node in self._nodes:
                print(
                    "Updating period for node",
                    node,
                    "from",
                    self._nodes[node],
                    "to",
                    str(period) + ".",
                )

            self._nodes[node] = period

    def _get_type_from_node_name(self, node):
        # TODO delete this method and use HLL instead
        d = {
            "MockData.sine_value": "f8",
            "MockData.cosine_value": "f8",
            "MockData.increment": "f8",
            "MockData.decrement": "f8",
            "MockData.bool": "?",
        }
        return d[node]

    def start(self):
        if self._start_invoked:
            warnings.warn("WARNING: start() can only be invoked once per object.")
            return

        self._start_invoked = True
        self._stop_logging.clear()
        self.logging_complete.clear()

        if self.file is None:
            # TODO Timezones
            self.file = (
                "results/" + datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S") + ".hdf5"
            )

        basedir = os.path.dirname(self.file)
        if not os.path.exists(basedir):
            os.makedirs(basedir)

        print("Writing data to file:", self.file)
        self.file_object = h5py.File(self.file, "w", libver="latest")

        for node in self._nodes:
            # One group per node containing a single dataset for each of SourceTimestamp, Value.
            group = self.file_object.create_group(node)
            # TODO double check chunk sizes. Also adjust per type?
            # Zeroeth dataset is always source timestamp which must be an 8 byte float as HDF5 does not support Python datetime.
            time_dataset = group.create_dataset(
                "SourceTimestamp",
                dtype="f8",
                shape=(0,),
                chunks=True,
                maxshape=(None,),
            )
            time_dataset.attrs.create(
                "Info", "Source Timestamp; time since Unix epoch."
            )

            value_type = self._get_type_from_node_name(node)  # TODO use HLL instead
            value_dataset = group.create_dataset(
                "Value", dtype=value_type, shape=(0,), chunks=True, maxshape=(None,)
            )
            value_dataset.attrs.create(
                "Info", "Node Value, index matches SourceTimestamp dataset."
            )

            # While here create cache structure per node.
            # Node name : [data point count, [timestamp 1, timestamp 2, ...], [value 1, value 2, ...]]
            #                                 ^ list indices match for data points ^
            self._cache[node] = [0, [], []]

        # No magic numbers
        self._count_idx = 0
        self._timestamp_idx = 1
        self._value_idx = 2

        # HDF5 structure created, can now enter SWMR mode
        self.file_object.swmr_mode = True

        # Sort added nodes into lists per period
        period_dict = {}
        for node, period in self._nodes.items():
            if period in period_dict.keys():
                period_dict[period].append(node)
            else:
                period_dict[period] = []
                period_dict[period].append(node)

        self.start_time = datetime.utcnow()
        for period, attributes in period_dict.items():
            self._subscription_ids.append(
                self.hll.subscribe(
                    attributes=attributes, period=period, data_queue=self.queue
                )
            )

        self._thread.start()

    def stop(self):
        for id in self._subscription_ids:
            self.hll.unsubscribe(id)

        self.stop_time = datetime.utcnow()
        self._stop_logging.set()

    def _write_cache_to_group(self, node):
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
        self._cache[node] = [0, [], []]

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
                # TODO timezones
                self._cache[node][self._timestamp_idx].append(
                    datapoint["source_timestamp"].timestamp()
                )
                self._cache[node][self._value_idx].append(datapoint["value"])
                self._cache[node][self._count_idx] += 1

                # Write to file when cache reaches predefined number of data points
                # TODO figure out cache sizes for different data types. Might need to get type from HLL?
                if self._cache[node][self._count_idx] >= self._FLUSH_DOUBLE:
                    self._write_cache_to_group(node)

            if next_flush_interval < datetime.now():
                for cache_node, cache in self._cache.items():
                    if cache[self._count_idx] > 0:
                        self._write_cache_to_group(cache_node)

                next_flush_interval += timedelta(milliseconds=self._FLUSH_PERIOD_MSECS)

        # Subscriptions have been stopped so clear remaining queue, do a final flush, and close file.
        while not self.queue.empty():
            datapoint = self.queue.get(block=True, timeout=self._QUEUE_GET_TIMEOUT_SECS)
            self._data_count += 1
            node = datapoint["name"]
            # TODO timezones
            self._cache[node][self._timestamp_idx].append(
                datapoint["source_timestamp"].timestamp()
            )
            self._cache[node][self._value_idx].append(datapoint["value"])
            self._cache[node][self._count_idx] += 1

        for cache_node, cache in self._cache.items():
            if cache[self._count_idx] > 0:
                self._write_cache_to_group(cache_node)

        self.file_object.close()
        print("Logger received", self._data_count, "data points.")
        self.logging_complete.set()

    def wait_for_completion(self):
        """Wait for logging thread to complete."""
        if not self._start_invoked:
            warnings.warn(
                "WARNING: cannot wait for logging to complete if start() has not been invoked."
            )
            return

        if not self._stop_logging:
            warnings.warn(
                "WARNING: cannot wait for logging to complete if stop() has not been invoked."
            )
            return

        while not self.logging_complete.is_set():
            sleep(self._COMPLETION_LOOP_TIMEOUT_SECS)
