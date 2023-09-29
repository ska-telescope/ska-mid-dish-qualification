import h5py
import threading
import queue
from datetime import datetime, timedelta
import warnings
from time import sleep

import sculib


class Logger:
    """Logger for DiSQ software."""

    # Constants
    _FLUSH_DOUBLE = 1024
    _FLUSH_PERIOD_MSECS = 200000
    _QUEUE_GET_TIMEOUT_SECS = 0.01  # TODO improve artificial timeout
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
        if file_name is not None:
            self.file = file_name
        else:
            self.file = "delme/" + datetime.utcnow().strftime(
                "%Y-%m-%d_%H-%M-%S"
            )  # TODO remove/change "delme/", update time to be when start() is called?

        self.file = self.file + ".hdf5"
        self._thread = threading.Thread(
            group=None, target=self._log, name="Logger internal thread"
        )
        self.queue = queue.Queue(maxsize=0)
        self._data_count = 0
        print("File name:", self.file)
        self.file_object = h5py.File(
            self.file, "w", libver="latest"
        )  # TODO this can't create a directory for some reason so create file with normal python file write

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
        for node in self._nodes:
            # Datasets simply created at root group and named after node.
            # TODO double check chunk sizes. Also adjust per type?
            # First tuple element is always source timestamp, a 26 character string in ISO 8601 format.
            value_type = self._get_type_from_node_name(node)  # TODO use HLL instead
            dataset = self.file_object.create_dataset(
                node,
                dtype=[
                    ("SourceTimestamp", h5py.string_dtype(encoding="utf-8", length=26)),
                    ("Value", value_type),
                ],
                shape=(0, 1),
                chunks=True,
                maxshape=(None, 1),
            )
            dataset.attrs.create("First tuple element", "Source Timestamp.")
            dataset.attrs.create("Second tuple element", "Node Value.")

            # While here create cache structure per node.
            # Node name : [data point count, [(timestamp 1, value 1), (timestamp 2, value 2), ...]]
            #                                 ^ SourceTimestamp-Value tuples
            self._cache[node] = [0, []]

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

    def _write_values_to_dataset(self, dataset, count, values):
        curr_len = dataset.len()
        dataset.resize(curr_len + count, axis=0)
        dataset[-count:, 0] = values
        dataset.flush()

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
                # TODO source timestamp is UTC, check this is okay
                self._cache[datapoint["name"]][1].append(
                    (
                        datapoint["source_timestamp"].isoformat(
                            timespec="microseconds"
                        ),
                        datapoint["value"],
                    )
                )
                self._cache[datapoint["name"]][0] += 1

                # Write to file when cache reaches predefined number of data points
                # TODO figure out cache sizes for different data types. Might need to get type from HLL?
                if self._cache[datapoint["name"]][0] >= self._FLUSH_DOUBLE:
                    self._write_values_to_dataset(
                        self.file_object[datapoint["name"]],
                        self._cache[datapoint["name"]][0],
                        self._cache[datapoint["name"]][1],
                    )
                    # Elegant reset has to be done here due to python "pass by assignment"/"call by object"
                    self._cache[datapoint["name"]] = [0, []]

            if next_flush_interval < datetime.now():
                for node, cache in self._cache.items():
                    if cache[0] > 0:
                        self._write_values_to_dataset(
                            self.file_object[node], cache[0], cache[1]
                        )
                        self._cache[node] = [0, []]

                next_flush_interval += timedelta(milliseconds=self._FLUSH_PERIOD_MSECS)

        # Subscriptions have been stopped so clear remaining queue, do a final flush, and close file.
        while not self.queue.empty():
            datapoint = self.queue.get(block=True, timeout=self._QUEUE_GET_TIMEOUT_SECS)
            # TODO source timestamp is UTC, check this is okay
            self._cache[datapoint["name"]][1].append(
                (datapoint["source_timestamp"], datapoint["value"])
            )
            self._cache[datapoint["name"]][0] += 1

        for node, cache in self._cache.items():
            if cache[0] > 0:
                self._write_values_to_dataset(
                    self.file_object[node], cache[0], cache[1]
                )
                self._cache[node] = [0, []]

        self.file_object.close()
        print("Logger received", self._data_count, "data points.")
        self.logging_complete.set()

    def wait_for_completion(self):
        """Wait for logging to complete."""
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
