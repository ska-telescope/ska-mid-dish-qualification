"""Timestamp reader."""

from datetime import datetime

import h5py


def convert_timestamps(timestamps, values):
    """
    Convert timestamps to ISO format and print along with corresponding values.

    :param timestamps: A list of UNIX timestamps.
    :type timestamps: list
    :param values: A list of corresponding values.
    :type values: list
    :raises IndexError: If the length of the timestamps and values lists do not match.
    """
    for idx in range(len(timestamps)):  # pylint: disable=consider-using-enumerate
        time = datetime.fromtimestamp(timestamps[idx]).isoformat()
        value = values[idx]
        print(f"{idx} : {time} : {value}")


def list_all(file_name):
    """
    List all nodes in an HDF5 file and print information for each node.

    :param file_name: The file name of the HDF5 file.
    :type file_name: str
    :raises OSError: If the file cannot be opened or does not exist.
    """
    fo = h5py.File(file_name, "r")
    nodes_list = list(fo.keys())

    for node in nodes_list:
        print(f"Node: {node}")
        timestamps = fo[node]["SourceTimestamp"][:]
        values = fo[node]["Value"][:]
        convert_timestamps(timestamps, values)

    fo.close()


if __name__ == "__main__":
    FILE_NAME = "tests/input_files/node_not_in_file.hdf5"
    print(f"File: {FILE_NAME}")
    list_all(FILE_NAME)
