"""
Tests for the DataLogger.

Some tests in this file expect an OPCUA server to be running, even if data is not being
gathered from the server. Specifically the custom server available in the ska-mid-dish-
simulators repo on branch wom-133-custom-nodes-for-pretty-graphs
"""

import logging

# pylint: disable=protected-access
import os
import random
import subprocess
import time
from datetime import datetime, timedelta, timezone
from queue import Queue
from typing import Callable

import h5py
import pytest

from ska_mid_disq import DataLogger, SteeringControlUnit


@pytest.fixture(scope="module", autouse=True)
def ds_simulator_opcua_server_mock_fixture():
    """Start DSSimulatorOPCUAServer as separate process."""
    simulator_process = subprocess.Popen(  # pylint: disable=consider-using-with
        ["python", "tests/resources/ds_opcua_server_mock.py"]
    )
    # Wait for some time to ensure the simulator is fully started
    time.sleep(10)
    yield simulator_process
    simulator_process.terminate()
    simulator_process.wait()  # Wait for the process to terminate completely


class StubScu(SteeringControlUnit):
    """High level library stub class (no real subscriptions)."""

    subscriptions: dict = {}

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4841,
        endpoint: str = "/dish-structure/server/",
        namespace: str = "http://skao.int/DS_ICD/",
    ) -> None:
        """Init."""
        super().__init__(
            host=host,
            port=port,
            endpoint=endpoint,
            namespace=namespace,
            timeout=25,
        )
        super().connect_and_setup()

    def subscribe(
        self,
        attributes: str | list[str] | None = None,
        period: int | None = None,
        data_queue: Queue | None = None,
        bad_shutdown_callback: Callable[[str], None] | None = None,
    ) -> tuple[int, list, list]:
        """
        Subscribe to a data source.

        :param attributes: Optional. Attributes related to the subscription.
        :type attributes: dict
        :param period: Optional. Period of the subscription.
        :type period: int
        :param data_queue: Optional. Queue to store incoming data.
        :type data_queue: list
        :param bad_shutdown_callback: will be called if a BadShutdown subscription
            status notification is received, defaults to None.
        :return: unique identifier for the subscription and lists of missing/bad nodes.
        :rtype: tuple[int, list, list]
        """
        uid = time.monotonic_ns()
        self.subscriptions[uid] = {}
        return uid, [], []

    def unsubscribe(self, uid: int) -> None:
        """
        Unsubscribe a user from the subscription.

        :param uid: The unique identifier of the user to unsubscribe.
        :type uid: int
        :raises IndexError: If the user ID is invalid.
        """
        _ = self.subscriptions.pop(uid)


def put_hdf5_file_in_queue(
    nodes: list[str], input_f_o: h5py.File, logger: DataLogger
) -> None:
    """
    Add data from the nodes in the input_f_o to the logger queue.

    The next node from which data is read is randomised, but data is always read in
    index (chronological) order.
    """
    node_datasets = {}
    node_start_count = {}
    node_current_count = {}
    for node in nodes:
        node_datasets[node] = {
            "SourceTimestamp": input_f_o[node]["SourceTimestamp"],
            "Value": input_f_o[node]["Value"],
        }
        node_start_count[node] = input_f_o[node]["SourceTimestamp"].len()
        node_current_count[node] = 0

    num_datapoints = sum(node_start_count.values())
    total_count = 0
    interval = timedelta(milliseconds=5000)
    next_print_interval = datetime.now(timezone.utc)
    while total_count < num_datapoints:
        first_rand = random.randint(0, len(nodes) - 1)
        if node_current_count[nodes[first_rand]] < node_start_count[nodes[first_rand]]:
            timestamp = datetime.fromtimestamp(
                node_datasets[nodes[first_rand]]["SourceTimestamp"][
                    node_current_count[nodes[first_rand]]
                ]
            )
            value = node_datasets[nodes[first_rand]]["Value"][
                node_current_count[nodes[first_rand]]
            ]
            logger.queue.put(
                {
                    "name": nodes[first_rand],
                    "value": value,
                    "source_timestamp": timestamp,
                }
            )
            node_current_count[nodes[first_rand]] += 1
            total_count += 1

        if next_print_interval < datetime.now(timezone.utc):
            # print(f"Put {total_count} data points in queue so far")
            next_print_interval += interval

    # print(f"Number of datapoints in {input_file} is {num_datapoints}")
    # print(f"Test put {total_count} data points in queue")


@pytest.fixture(scope="module", name="high_level_library")
def high_level_library_fixture() -> StubScu:
    """SCU library with active connection fixture."""
    high_level_library = StubScu()
    return high_level_library


@pytest.mark.skipif(
    os.getenv("CI") is not None, reason="Skipping test in GitLab CI pipeline"
)
def test_build_hdf5_structure(high_level_library: StubScu) -> None:
    """
    Test the _build_hdf5_structure() method.

    Checks the correct hierarchical structure is created and the file object is set to
    SWMR mode.
    """
    output_file = "tests/resources/output_files/_build_hdf5_structure.hdf5"
    logger = DataLogger(file_name=output_file, high_level_library=high_level_library)
    nodes = ["MockData.bool", "MockData.enum", "MockData.increment"]
    logger.add_nodes(nodes, 100)
    logger.file_object = h5py.File(output_file, "w", libver="latest")
    logger._build_hdf5_structure()
    expected_node_list = nodes
    assert list(logger.file_object.keys()) == expected_node_list
    assert logger.file_object.swmr_mode is True
    logger.file_object.close()


# TODO: Fix test
@pytest.mark.skip(reason="Test currently fails!")
def test_add_nodes(
    caplog: pytest.LogCaptureFixture, high_level_library: StubScu
) -> None:
    """
    Test the add_nodes method.

    Nodes are added correctly, logging matches expected, and nothing happens if
    _start_invoked is set.
    """
    logger = DataLogger(file_name="n/a", high_level_library=high_level_library)
    nodes = [
        "MockData.increment",
        "MockData.sine_value",
        "MockData.cosine_value",
        "a",
    ]
    nodes1 = [
        "MockData.increment",
        "MockData.bool",
        "MockData.enum",
    ]
    logger.add_nodes(nodes, 100)
    logger.add_nodes(nodes1, 50)
    logger._start_invoked = True
    logger.add_nodes(nodes, 50)
    captured = caplog.messages
    expected_log = [
        "renamed Locked&Stowed to Locked_Stowed due to Python syntax",
        '"a" not available as an attribute on the server, skipping.',
        "Updating period for node MockData.increment from 100 to 50.",
        "WARNING: nodes cannot be added after start() has been invoked.",
    ]
    # Sometimes the first line above does not appear
    expected_log2 = [
        '"a" not available as an attribute on the server, skipping.',
        "Updating period for node MockData.increment from 100 to 50.",
        "WARNING: nodes cannot be added after start() has been invoked.",
    ]
    # pylint: disable=consider-using-in
    assert captured == expected_log or captured == expected_log2
    expected_object_nodes = {
        "MockData.increment": 50,
        "MockData.sine_value": 100,
        "MockData.cosine_value": 100,
        "MockData.bool": 50,
        "MockData.enum": 50,
    }
    assert logger._nodes == expected_object_nodes


# TODO: Fix test
# @pytest.mark.skip(reason="Test currently fails!")
def test_start(caplog: pytest.LogCaptureFixture, high_level_library: StubScu) -> None:
    """
    Test the start() method.

    Check that a file (and directory) is made with the input file name, and that it
    cannot be invoked twice, logging the correct messages.
    """
    caplog.set_level(logging.INFO)
    output_file = "tests/resources/output_files/start.hdf5"
    logger = DataLogger(file_name=output_file, high_level_library=high_level_library)
    nodes = ["MockData.bool", "MockData.enum", "MockData.increment"]
    logger.add_nodes(nodes, 100)
    logger.start()
    logger.start()
    expected_log = [
        "Writing data to file: tests/resources/output_files/start.hdf5",
        "WARNING: start() can only be invoked once per object.",
    ]
    # Check messages are those expected.
    for message in expected_log:
        assert message in caplog.messages

    # Check file was created.
    assert os.path.exists(output_file) is True
    logger.stop()


def test_stop(high_level_library: StubScu) -> None:
    """
    Test the stop() method.

    Check _stop_logging is being set.
    """
    output_file = "tests/resources/output_files/stop.hdf5"
    logger = DataLogger(file_name=output_file, high_level_library=high_level_library)
    nodes = ["MockData.bool", "MockData.enum", "MockData.increment"]
    logger.add_nodes(nodes, 100)
    logger.start()
    logger.stop()
    assert logger._stop_logging.is_set() is True


def test_write_cache_to_group(high_level_library: StubScu) -> None:
    """
    Test the _write_cache_to_group() method.

    Check that values are written to the output file.
    """
    output_file = "tests/resources/output_files/_write_cache_to_group.hdf5"
    logger = DataLogger(file_name=output_file, high_level_library=high_level_library)
    nodes = ["MockData.increment"]
    logger.add_nodes(nodes, 100)
    logger.file_object = h5py.File(output_file, "w", libver="latest")
    logger._build_hdf5_structure()
    # Add some data to the cache for a node.
    data: list = [
        3,
        "double",
        3,
        [1699521707.946635, 1699521710.208692, 1699521714.539091],
        [1, 2, 3],
    ]
    logger._cache[nodes[0]] = data
    logger._write_cache_to_group(nodes[0])
    expected_cache = [3, "double", 0, [], []]
    # Check the data in the cache has been cleared.
    assert logger._cache[nodes[0]] == expected_cache
    logger.file_object.close()

    f_o = h5py.File(output_file, "r", libver="latest")
    timestamps = f_o[nodes[0]]["SourceTimestamp"][:]
    values = f_o[nodes[0]]["Value"][:]
    # Check the data in the file matches.
    for i in range(data[2]):
        assert timestamps[i] == data[3][i]
        assert values[i] == data[4][i]

    f_o.close()


def test_log(high_level_library: StubScu) -> None:
    """
    Test the log() method.

    Add datapoints to the queue from a known input file, check the output file contains
    all expected values.
    """
    input_file = "tests/resources/input_files/_log.hdf5"
    output_file = "tests/resources/output_files/_log.hdf5"
    input_f_o = h5py.File(input_file, "r", libver="latest")
    nodes = list(input_f_o.keys())
    logger = DataLogger(file_name=output_file, high_level_library=high_level_library)
    logger.add_nodes(nodes, 50)

    logger.start()
    put_hdf5_file_in_queue(nodes, input_f_o, logger)
    logger.stop()
    output_f_o = h5py.File(output_file, "r", libver="latest")

    for node in nodes:
        in_timestamps = input_f_o[node]["SourceTimestamp"][:]
        in_values = input_f_o[node]["Value"][:]
        out_timestamps = output_f_o[node]["SourceTimestamp"][:]
        out_values = output_f_o[node]["Value"][:]
        # Check the data in the file matches.
        for i in range(len(in_timestamps)):  # pylint: disable=consider-using-enumerate
            assert out_timestamps[i] == in_timestamps[i]
            assert out_values[i] == in_values[i]

    input_f_o.close()
    output_f_o.close()


def test_enum_attribute(high_level_library: StubScu) -> None:
    """
    Enum attribute.

    Test that an attribute containing a comma separated string of available enum string
    states is added to enum type node value datasets.
    """
    output_file = "tests/resources/output_files/enum_attribute.hdf5"
    logger = DataLogger(file_name=output_file, high_level_library=high_level_library)
    nodes = ["MockData.bool", "MockData.enum", "MockData.increment"]
    logger.add_nodes(nodes, 100)
    logger.start()
    logger.stop()
    output_f_o = h5py.File(output_file, "r", libver="latest")
    expected_attribute = (
        "StartUp,Standby,Locked,Stowed,Locked_Stowed,Activating,Deactivating,"
        "Standstill,Stopping,Slew,Jog,Track"
    )
    assert (
        output_f_o["MockData.enum"]["Value"].attrs["Enumerations"] == expected_attribute
    )
    output_f_o.close()


def test_performance(high_level_library: StubScu) -> None:
    """
    Test the performance of the logger class.

    By quickly reading a HDF5 file into the shared queue. Ensure the logging was
    completed within a certain time and the contents of he input and output files match.
    """
    input_file = "tests/resources/input_files/60_minutes.hdf5"
    output_file = "tests/resources/output_files/performance.hdf5"
    input_f_o = h5py.File(input_file, "r", libver="latest")
    nodes = list(input_f_o.keys())
    start_time = datetime.now(timezone.utc)
    logger = DataLogger(file_name=output_file, high_level_library=high_level_library)
    logger.add_nodes(nodes, 50)

    logger.start()
    put_hdf5_file_in_queue(nodes, input_f_o, logger)
    logger.stop()
    stop_time = datetime.now(timezone.utc)
    input_f_o.close()

    test_duration = stop_time - start_time
    print(f"Performance test duration: {test_duration}")
    # Check test ran in a reasonable time (1/10th of input file duration).
    assert test_duration < timedelta(minutes=6)
    # pylint: disable=subprocess-run-check
    subprocess.run(["h5diff", "-v", input_file, output_file])
    # result = subprocess.run(["h5diff", "-v", input_file, output_file])
    # Check output file contents match input file contents
    # The h5diff linux tool is returning 2 (i.e. error code) for 0 differences
    # found on the MockData.bool dataset.
    # assert result.returncode == 0 # assert excluded because of tool bug


def test_nameplate_attributes(high_level_library: StubScu) -> None:
    """Test the nameplate nodes are added to the root hdf5 object."""
    output_file = "tests/resources/output_files/nameplate_attributes.hdf5"
    logger = DataLogger(file_name=output_file, high_level_library=high_level_library)
    nodes = ["MockData.bool", "MockData.enum", "MockData.increment"]
    logger.add_nodes(nodes, 100)
    logger.start()
    logger.stop()
    output_f_o = h5py.File(output_file, "r", libver="latest")
    assert output_f_o.attrs["Management.NamePlate.DishId"] == "Mock XML test server"
    assert (
        output_f_o.attrs["Management.NamePlate.DishStructureSerialNo"]
        == "Mock serial number"
    )
    assert (
        output_f_o.attrs["Management.NamePlate.DscSoftwareVersion"]
        == "ds_icd_0.0.11_mock.xml"
    )
    assert output_f_o.attrs["Management.NamePlate.IcdVersion"] == "2"
    assert output_f_o.attrs["Management.NamePlate.RunHours"] == 0.0
    assert output_f_o.attrs["Management.NamePlate.TotalDist_Az"] == 0.0
    assert output_f_o.attrs["Management.NamePlate.TotalDist_El_deg"] == 0.0
    assert output_f_o.attrs["Management.NamePlate.TotalDist_El_m"] == 0.0
    assert output_f_o.attrs["Management.NamePlate.TotalDist_Fi"] == 0.0
    output_f_o.close()
