import h5py
import threading
import queue
from datetime import datetime, timedelta
import warnings


class Logger:
    """Logger for DiSQ software."""

    # Constants
    _FLUSH_DOUBLE = 1024
    _FLUSH_PERIOD_MSECS = 200000
    _QUEUE_GET_TIMEOUT_SECS = 0.01  # TODO improve artificial timeout

    _nodes = None
    _stop_logging = threading.Event()
    _start_invoked = False
    _cache = {}
    _subscription_ids = []

    def __init__(self, file_name: str = None):
        if file_name is not None:
            self.file = file_name
        else:
            self.file = "delme/" + datetime.now().strftime(
                "%Y-%m-%d_%H-%M-%S"
            )  # TODO remove/change "delme/"

        self.file = self.file + ".hdf5"
        self._thread = threading.Thread(
            group=None, target=self._log, name="Logger internal thread"
        )
        self.queue = queue.Queue(maxsize=0)
        print("File name:", self.file)
        self.file_object = h5py.File(self.file, "w", libver="latest")

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
            # TODO check whether node exists on server through HLL (e.g. spelling mistake)? probably should be done before logger
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

    def start(self):
        if self._start_invoked:
            warnings.warn("WARNING: start() can only be invoked once per object.")
            return

        self._start_invoked = True
        self._stop_logging.clear()
        for node in self._nodes:
            # Datasets simply created at root group and named after node
            # TODO double check chunk sizes. Also adjust per type? Adjust type per node type?
            dataset = self.file_object.create_dataset(
                node, shape=(0, 2), dtype="f8", chunks=True, maxshape=(None, 2)
            )
            # First column of dataset is source timestamp, second column is value
            dataset.attrs.create("Column 0", "Source Timestamp; time since Unix epoch")
            dataset.attrs.create("Column 1", "Node Value")

            # While here create cache structure per node.
            # Node name : [data point count, [timestamp 1, timestamp 2, ...], [value 1, value 2, ...]]
            #                                 ^ list indices match for data points ^
            self._cache[node] = [0, [], []]

        # HDF5 structure created, can now enter SWMR mode
        self.file_object.swmr_mode = True

        # Sort added nodes into lists per period
        period_dict = {}
        for node, period in self._nodes.items():
            if period in period_dict.keys():
                period_dict[period].append(node)
            else:
                period_dict[period] = list(node)

        # TODO subscribe to nodes:
        # for period in period_dict:
        #     self._subscription_ids.append(hll.subscribe(self.queue, period, period_dict[period]))

        self._thread.start()

    def stop(self):
        # TODO stop subscriptions
        # for id in self.subscription_ids:
        #    hll.stop_subscriptions(id)
        self._stop_logging.set()

    def _write_cache_to_dataset(self, dataset, cache):
        curr_len = dataset.len()
        dataset.resize(curr_len + cache[0], axis=0)
        dataset[-cache[0] :, 0] = cache[1]
        dataset[-cache[0] :, 1] = cache[2]
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
                self._cache[datapoint["name"]][1].append(datapoint["source_timestamp"])
                self._cache[datapoint["name"]][2].append(datapoint["value"])
                self._cache[datapoint["name"]][0] += 1

                # Write to file when cache reaches predefined number of data points
                # TODO figure out cache sizes for different data types. Might need to get type from HLL?
                if self._cache[datapoint["name"]][0] >= self._FLUSH_DOUBLE:
                    self._write_cache_to_dataset(
                        self.file_object[datapoint["name"]],
                        self._cache[datapoint["name"]],
                    )
                    # Elegant reset has to be done here due to python "pass by assignment"/"call by object"
                    self._cache[datapoint["name"]] = [0, [], []]

            if next_flush_interval < datetime.now():
                for node, cache in self._cache.items():
                    if cache[0] > 0:
                        self._write_cache_to_dataset(self.file_object[node], cache)
                        self._cache[node] = [0, [], []]

                next_flush_interval += timedelta(milliseconds=self._FLUSH_PERIOD_MSECS)

        # Subscriptions have been stopped so clear remaining queue, do a final flush, and close file.
        while not self.queue.empty():
            datapoint = self.queue.get(block=True, timeout=self._QUEUE_GET_TIMEOUT_SECS)
            self._cache[datapoint["name"]][1].append(datapoint["source_timestamp"])
            self._cache[datapoint["name"]][2].append(datapoint["value"])
            self._cache[datapoint["name"]][0] += 1

        for node, cache in self._cache.items():
            if cache[0] > 0:
                self._write_cache_to_dataset(self.file_object[node], cache)
                self._cache[node] = [0, [], []]

        self.file_object.close()
