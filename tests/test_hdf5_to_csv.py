"""Test HDF5 to CSV."""

import filecmp
import os
from datetime import datetime, timedelta

import h5py

from ska_mid_dish_qualification import hdf5_to_csv as h2c


def test_node_not_in_file(capsys):
    """
    Node not in file.

    When one of the requested nodes is not in the input file print message but
    continue making CSV for remaining nodes.
    """
    input_files = "tests/input_files/node_not_in_file.hdf5"
    output_file = "tests/output_files/node_not_in_file.csv"
    nodes = ["not_a_node", "MockData.increment"]
    fin = h5py.File(input_files, "r")
    start = datetime.fromisoformat(fin.attrs["Start time"])
    stop = datetime.fromisoformat(fin.attrs["Stop time"])
    fin.close()
    step = 100
    converter = h2c.Converter()
    converter.make_csv(input_files, output_file, nodes, start, stop, step)
    captured = capsys.readouterr()
    expected_stdout = "Node not_a_node is not in the input file and will be ignored.\n"
    # Check that error message matches expected
    assert captured.out == expected_stdout
    # Check the output file matches the expected CSV
    assert filecmp.cmp(output_file, "tests/expected_files/node_not_in_file.csv") is True


def test_no_matching_nodes(capsys):
    """
    No matching nodes.

    When the input file does not contain any of the requested nodes print error
    message and exit.
    """
    input_file = "tests/input_files/no_matching_nodes.hdf5"
    output_file = "tests/output_files/no_matching_nodes.csv"
    nodes = "not_a_node"
    fin = h5py.File(input_file, "r")
    start = datetime.fromisoformat(fin.attrs["Start time"])
    stop = datetime.fromisoformat(fin.attrs["Stop time"])
    fin.close()
    step = 100
    converter = h2c.Converter()
    converter.make_csv(input_file, output_file, nodes, start, stop, step)
    captured = capsys.readouterr()
    expected_stdout = (
        "Node not_a_node is not in the input file and will be ignored.\n"
        "ERROR: No data for requested nodes, exiting\n"
    )
    # Check that error message matches expected
    assert captured.out == expected_stdout
    # Check the output file was not created
    assert os.path.exists(output_file) is False


def test_start_stop_past_file(capsys):
    """
    Start and stop past ends of file.

    When the requested start time is earlier than the input file start time and/or
    the requested stop time is later than the input file stop time print messages
    and shorten range to existing file times.
    """
    input_file = "tests/input_files/start_stop_past_file.hdf5"
    output_file = "tests/output_files/start_stop_past_files.csv"
    nodes = ["MockData.increment", "MockData.bool", "MockData.enum"]
    fin = h5py.File(input_file, "r")
    # Cause the requested start and end times to be past the file ranges
    start = datetime.fromisoformat(fin.attrs["Start time"]) - timedelta(seconds=4)
    stop = datetime.fromisoformat(fin.attrs["Stop time"]) + timedelta(seconds=4)
    fin.close()
    step = 100
    converter = h2c.Converter()
    converter.make_csv(input_file, output_file, nodes, start, stop, step)
    captured = capsys.readouterr()
    expected_stdout = (
        "Requested start time 2023-10-30 16:14:52.138859 is before earliest file start "
        "2023-10-30 16:14:56.138859. Output CSV will start from 2023-10-30 "
        "16:14:56.138859\nRequested stop time 2023-10-30 16:15:01.315888 is after "
        "latest file stop 2023-10-30 16:14:57.315888. Output CSV will stop at "
        "2023-10-30 16:14:57.315888\n"
    )
    # Check that error message matches expected
    assert captured.out == expected_stdout
    # Check the output file matches the expected (including CSV starts at earliest file
    # start and stops no later than latest file stop)
    assert (
        filecmp.cmp(output_file, "tests/expected_files/start_stop_past_files.csv")
        is True
    )


def test_simple_input_file(capsys):
    """
    Simple input file.

    A simple HDF5 input file will be correctly converted to the expected CSV file
    without error.
    """
    input_file = "tests/input_files/simple_input_file.hdf5"
    output_file = "tests/output_files/simple_input_file.csv"
    nodes = ["MockData.increment", "MockData.bool", "MockData.enum"]
    fin = h5py.File(input_file, "r")
    start = datetime.fromisoformat(fin.attrs["Start time"])
    stop = datetime.fromisoformat(fin.attrs["Stop time"])
    fin.close()
    step = 100
    converter = h2c.Converter()
    converter.make_csv(input_file, output_file, nodes, start, stop, step)
    captured = capsys.readouterr()
    expected_stdout = ""
    # Check that error message matches expected
    assert captured.out == expected_stdout
    # Check the output file matches the expected.
    assert (
        filecmp.cmp(output_file, "tests/expected_files/simple_input_file.csv") is True
    )


def test_simple_input_file_double_speed(capsys):
    """
    Simple input file double speed.

    A simple HDF5 input file sampled at double the rate it was created will output a
    CSV file with asterisks to indidicate values that are older than the line time
    minus the step_ms given.
    """
    input_file = "tests/input_files/simple_input_file_double_speed.hdf5"
    output_file = "tests/output_files/simple_input_file_double_speed.csv"
    nodes = ["MockData.increment", "MockData.bool", "MockData.enum"]
    fin = h5py.File(input_file, "r")
    start = datetime.fromisoformat(fin.attrs["Start time"])
    stop = datetime.fromisoformat(fin.attrs["Stop time"])
    fin.close()
    step = 50
    converter = h2c.Converter()
    converter.make_csv(input_file, output_file, nodes, start, stop, step)
    captured = capsys.readouterr()
    expected_stdout = ""
    # Check that error message matches expected
    assert captured.out == expected_stdout
    # Check the output file matches the expected.
    assert (
        filecmp.cmp(
            output_file, "tests/expected_files/simple_input_file_double_speed.csv"
        )
        is True
    )
