"""Tests of the HDF5 to CSV converter."""

import filecmp
import os
from datetime import datetime, timedelta
from pathlib import Path

import h5py
import pytest

from ska_mid_disq import hdf5_to_csv as h2c


@pytest.fixture(name="base_path")
def base_path_fixture():
    """Return the tests root path."""
    return Path(__file__).parent


def test_node_not_in_file(capsys, base_path):
    """
    Test node not in file.

    When one of the requested nodes is not in the input file, print a message but
    continue making CSV for the remaining nodes.
    """
    input_files = base_path / "resources/input_files/node_not_in_file.hdf5"
    output_file = base_path / "resources/output_files/node_not_in_file.csv"
    expected_file = base_path / "resources/expected_files/node_not_in_file.csv"
    nodes = ["not_a_node", "MockData.increment"]
    fo = h5py.File(input_files, "r")
    start = datetime.fromisoformat(fo.attrs["Start time"])
    stop = datetime.fromisoformat(fo.attrs["Stop time"])
    fo.close()
    step = 100
    converter = h2c.Converter()
    converter.make_csv(input_files, output_file, nodes, start, stop, step)
    captured = capsys.readouterr()
    expected_stdout = "Node not_a_node is not in the input file and will be ignored.\n"
    # Check that error message matches expected
    assert captured.out == expected_stdout
    # Check the output file matches the expected CSV
    assert filecmp.cmp(output_file, expected_file) is True


def test_no_matching_nodes(capsys, base_path):
    """
    Test no matching nodes.

    When the input file does not contain any of the requested nodes, print error message
    and exit.
    """
    input_file = base_path / "resources/input_files/no_matching_nodes.hdf5"
    output_file = base_path / "resources/output_files/no_matching_nodes.csv"
    nodes = "not_a_node"
    fo = h5py.File(input_file, "r")
    start = datetime.fromisoformat(fo.attrs["Start time"])
    stop = datetime.fromisoformat(fo.attrs["Stop time"])
    fo.close()
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


def test_start_stop_past_file(capsys, base_path):
    """
    Test start and stop past ends of file.

    When the requested start time is earlier than the input file start time and/or the
    requested stop time is later than the input file stop time print messages and
    shorten range to existing file times.
    """
    input_file = base_path / "resources/input_files/start_stop_past_file.hdf5"
    output_file = base_path / "resources/output_files/start_stop_past_files.csv"
    expected_file = base_path / "resources/expected_files/start_stop_past_files.csv"
    nodes = ["MockData.increment", "MockData.bool", "MockData.enum"]
    fo = h5py.File(input_file, "r")
    # Cause the requested start and end times to be past the file ranges
    start = datetime.fromisoformat(fo.attrs["Start time"]) - timedelta(seconds=4)
    stop = datetime.fromisoformat(fo.attrs["Stop time"]) + timedelta(seconds=4)
    fo.close()
    step = 100
    converter = h2c.Converter()
    converter.make_csv(input_file, output_file, nodes, start, stop, step)
    captured = capsys.readouterr()
    expected_stdout = (
        "Requested start time 2023-10-30 16:14:52.138859+00:00 is before earliest "
        "file start 2023-10-30 16:14:56.138859+00:00. Output CSV will start from "
        "2023-10-30 16:14:56.138859+00:00\nRequested stop time 2023-10-30 "
        "16:15:01.315888+00:00 is after latest file stop 2023-10-30 "
        "16:14:57.315888+00:00. Output CSV will stop at 2023-10-30 "
        "16:14:57.315888+00:00\n"
    )
    # Check that error message matches expected
    assert captured.out == expected_stdout
    # Check the output file matches the expected (including CSV starts at earliest file
    # start and stops no later than latest file stop)
    assert filecmp.cmp(output_file, expected_file) is True


def test_simple_input_file(capsys, base_path):
    """
    Test simple input file.

    A simple HDF5 input file will be correctly converted to the expected CSV file
    without error.
    """
    input_file = base_path / "resources/input_files/simple_input_file.hdf5"
    output_file = base_path / "resources/output_files/simple_input_file.csv"
    expected_file = base_path / "resources/expected_files/simple_input_file.csv"
    nodes = ["MockData.increment", "MockData.bool", "MockData.enum"]
    fo = h5py.File(input_file, "r")
    start = datetime.fromisoformat(fo.attrs["Start time"])
    stop = datetime.fromisoformat(fo.attrs["Stop time"])
    fo.close()
    step = 100
    converter = h2c.Converter()
    converter.make_csv(input_file, output_file, nodes, start, stop, step)
    captured = capsys.readouterr()
    expected_stdout = ""
    # Check that error message matches expected
    assert captured.out == expected_stdout
    # Check the output file matches the expected.
    assert filecmp.cmp(output_file, expected_file) is True


def test_simple_input_file_double_speed(capsys, base_path):
    """
    Test simple input file double speed.

    A simple HDF5 input file sampled at double the rate it was created will output a CSV
    file with asterisks to indicate values that are older than the line time minus the
    step_ms given.
    """
    input_file = base_path / "resources/input_files/simple_input_file_double_speed.hdf5"
    output_file = (
        base_path / "resources/output_files/simple_input_file_double_speed.csv"
    )
    expected_file = (
        base_path / "resources/expected_files/simple_input_file_double_speed.csv"
    )
    nodes = ["MockData.increment", "MockData.bool", "MockData.enum"]
    fo = h5py.File(input_file, "r")
    start = datetime.fromisoformat(fo.attrs["Start time"])
    stop = datetime.fromisoformat(fo.attrs["Stop time"])
    fo.close()
    step = 50
    converter = h2c.Converter()
    converter.make_csv(input_file, output_file, nodes, start, stop, step)
    captured = capsys.readouterr()
    expected_stdout = ""
    # Check that error message matches expected
    assert captured.out == expected_stdout
    # Check the output file matches the expected.
    assert filecmp.cmp(output_file, expected_file) is True
