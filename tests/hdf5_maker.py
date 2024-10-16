"""Make HDF5 files with easily verifiable output for testing purposes."""

import os
from datetime import datetime, timezone
from time import sleep

import h5py


# pylint: disable=too-few-public-methods
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
        """
        Initialize a new instance of the class.

        :param spoof_server: The server to spoof.
        :type spoof_server: str
        """
        self.spoof_server = spoof_server

    def _get_value_type_from_node_name(self, node):
        # TODO delete this and use HLL instead
        """
        Get the type of value based on the node name.

        :param node: The name of the node to get the value type from.
        :type node: str
        :return: The type of value associated with the input node name.
        :rtype: str
        """
        d = {
            "MockData.sine_value": "double",
            "MockData.cosine_value": "double",
            "MockData.increment": "double",
            "MockData.decrement": "bad",
            "MockData.bool": "bool",
            "MockData.enum": "enum",
        }
        return d[node]

    def generate(self, filename, nodes):
        """
        Generate HDF5 file with specified nodes and data.

        :param filename: The name of the HDF5 file to be generated.
        :type filename: str
        :param nodes: List of node names to create in the HDF5 file.
        :type nodes: list of str
        """
        if os.path.exists(filename):
            print(
                f"This function will not overwrite. "
                f"Please delete file {filename} first."
            )
            return

        fo = h5py.File(filename, "w")

        data_d = {}

        # Make hierarchical format
        for node in nodes:
            group = fo.create_group(node)
            fo.attrs.create("Server", self.spoof_server)
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
            value_dataset = group.create_dataset(
                "Value",
                shape=(0,),
                dtype=self._hdf5_type_from_value_type[value_type],
                chunks=(self._chunks_from_value_type[value_type],),
                maxshape=(None,),
            )
            value_dataset.attrs.create(
                "Info", "Node Value, index matches SourceTimestamp dataset."
            )
            value_dataset.attrs.create("Type", value_type)
            if value_type == "enum":
                value_dataset.attrs.create("Enumerations", "one,two,three,four")

            data_d[node] = {"SourceTimestamp": [], "Value": []}

        fo.attrs.create(
            "Data start time",
            datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        )
        # Make data
        data_rows = 10
        for idx in range(data_rows):
            for node in nodes:
                data_d[node]["SourceTimestamp"].append(
                    datetime.now(timezone.utc).timestamp()
                )
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

        fo.attrs.create(
            "Data stop time",
            datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        )

        # Store data
        for node in nodes:
            group = fo[node]
            curr_len = group["SourceTimestamp"].len()

            group["SourceTimestamp"].resize(curr_len + data_rows, axis=0)
            group["SourceTimestamp"][-data_rows:] = data_d[node]["SourceTimestamp"]
            group["SourceTimestamp"].flush()

            group["Value"].resize(curr_len + data_rows, axis=0)
            group["Value"][-data_rows:] = data_d[node]["Value"]
            group["Value"].flush()

        fo.close()


if __name__ == "__main__":
    mock_nodes = ["MockData.increment", "MockData.bool", "MockData.enum"]
    maker = Maker("simple input file")
    maker.generate("input_files/start_stop_past_file.hdf5", mock_nodes)
