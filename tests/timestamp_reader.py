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
    file = h5py.File(file_name, "r")
    nodes_list = list(file.keys())

    for node in nodes_list:
        print(f"Node: {node}")
        timestamps = file[node]["SourceTimestamp"][:]
        values = file[node]["Value"][:]
        convert_timestamps(timestamps, values)

    file.close()


if __name__ == "__main__":
    FILE_NAME = "tests/input_files/node_not_in_file.hdf5"
    print(f"File: {FILE_NAME}")
    list_all(FILE_NAME)
