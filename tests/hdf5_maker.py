"""Make HDF5 files with easily verifiable output for testing purposes."""

import os
from datetime import datetime
from time import sleep

import h5py


class Maker:
    """Make HDF5 files with easily verifiable output for testing purposes."""

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
        "double": "f8",  # 64 bit double numpy type
        "bool": "?",
        "enum": "u4",  # 32 bit unsigned integer numpy type
    }
    _chunks_from_value_type = {
        "double": _CHUNK_DOUBLE,
        "bool": _CHUNK_BOOL,
        "enum": _CHUNK_ENUM,
    }
    _flush_from_value_type = {
        "double": _FLUSH_DOUBLE,
        "bool": _FLUSH_BOOL,
        "enum": _FLUSH_ENUM,
    }

    SLEEP_TIME = 0.09726  # Adjust to get easy to read timestamp steps

    def __init__(self, spoof_server):
        """Init Maker."""
        self.spoof_server = spoof_server

    def _get_value_type_from_node_name(self, node):
        # TODO delete this and use HLL instead
        data = {
            "MockData.sine_value": "double",
            "MockData.cosine_value": "double",
            "MockData.increment": "double",
            "MockData.decrement": "bad",
            "MockData.bool": "bool",
            "MockData.enum": "enum",
        }
        return data[node]

    def generate(self, filename, nodes):
        """generate."""
        if os.path.exists(filename):
            print(
                f"This function will not overwrite. Please delete file {filename} first"
            )
            return

        fout = h5py.File(filename, "w")

        data_d = {}

        # Make hierarchical format
        for node in nodes:
            group = fout.create_group(node)
            fout.attrs.create("Server", self.spoof_server)
            timestamp_ds = group.create_dataset(
                "SourceTimestamp",
                dtype="f8",
                shape=(0,),
                chunks=(self._CHUNK_DOUBLE,),
                maxshape=(None,),
            )
            timestamp_ds.attrs.create(
                "Info", "Source Timestamp; time since Unix epoch."
            )

            value_type = self._get_value_type_from_node_name(node)
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
            if value_type == "enum":
                value_dataset.attrs.create("Enumerations", "one,two,three,four")

            data_d[node] = {"SourceTimestamp": [], "Value": []}

        start_time = datetime.utcnow()
        fout.attrs.create("Start time", start_time.isoformat(timespec="microseconds"))
        # Make data
        data_rows = 10
        for idx in range(data_rows):
            timestamp = datetime.utcnow().timestamp()
            for node in nodes:
                data_d[node]["SourceTimestamp"].append(timestamp)
                if self._get_value_type_from_node_name(node) == "double":
                    data_d[node]["Value"].append(idx)
                if self._get_value_type_from_node_name(node) == "bool":
                    if idx % 2 == 0:
                        data_d[node]["Value"].append(True)
                    else:
                        data_d[node]["Value"].append(False)
                if self._get_value_type_from_node_name(node) == "enum":
                    data_d[node]["Value"].append(idx % 4)

            sleep(self.SLEEP_TIME)

        stop_time = datetime.utcnow()
        fout.attrs.create("Stop time", stop_time.isoformat(timespec="microseconds"))

        # Store data
        for node in nodes:
            group = fout[node]
            curr_len = group["SourceTimestamp"].len()

            group["SourceTimestamp"].resize(curr_len + data_rows, axis=0)
            group["SourceTimestamp"][-data_rows:] = data_d[node]["SourceTimestamp"]
            group["SourceTimestamp"].flush()

            group["Value"].resize(curr_len + data_rows, axis=0)
            group["Value"][-data_rows:] = data_d[node]["Value"]
            group["Value"].flush()

        fout.close()


if __name__ == "__main__":
    the_nodes = ["MockData.increment", "MockData.bool", "MockData.enum"]
    maker = Maker("simple input file")
    maker.generate("tests/input_files/start_stop_past_file.hdf5", the_nodes)
