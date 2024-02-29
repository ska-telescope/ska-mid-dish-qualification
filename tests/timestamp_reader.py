"""Test timestamp reader."""

from datetime import datetime

import h5py


def convert_timestamps(timestamps, values):
    """convert_timestamps."""
    idx = 0
    for i in range(len(timestamps)):
        time = datetime.fromtimestamp(timestamps[idx]).isoformat()
        value = values[idx]
        print(f"{idx} : {time} : {value}")
        idx += 1


def list_all(file_name):
    """list_all."""
    fo = h5py.File(file_name, "r")
    nodes_list = list(fo.keys())

    for node in nodes_list:
        print(f"Node: {node}")
        timestamps = fo[node]["SourceTimestamp"][:]
        values = fo[node]["Value"][:]
        convert_timestamps(timestamps, values)

    fo.close()


if __name__ == "__main__":
    FILE_NAME = "input_files/node_not_in_file.hdf5"
    print(f"File: {FILE_NAME}")
    list_all(FILE_NAME)
