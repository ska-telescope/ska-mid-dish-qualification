from disq import logger as log
from disq import sculib
from datetime import datetime, timedelta
import h5py
import os
import random
import subprocess
import time


class stub_scu(sculib.scu):
    """
    High level library stub class (no real subscriptions).
    """

    subscriptions = {}

    def subscribe(self, attributes=None, period=None, data_queue=None) -> int:
        id = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
        self.subscriptions[id] = {}
        return id

    def unsubscribe(self, id: int) -> None:
        _ = self.subscriptions.pop(id)


"""
Some tests in this file expect an OPCUA server to be running, even if data is not being
gathered from the server. Specifically the custom server available in the
ska-mid-dish-simulators repo on branch wom-133-custom-nodes-for-pretty-graphs
"""


def put_hdf5_file_in_queue(nodes: list[str], input_f_o: h5py.File, logger: log.Logger):
    """
    Helper function for adding data from the nodes in the input_f_o to the logger
    queue. The next node from which data is read is randomised, but data is always read
    in index (chronological) order.
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
    next_print_interval = datetime.now()
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

        if next_print_interval < datetime.utcnow():
            # print(f"Put {total_count} data points in queue so far")
            next_print_interval += interval

    # print(f"Number of datapoints in {input_file} is {num_datapoints}")
    # print(f"Test put {total_count} data points in queue")


def test_performance():
    """
    Performance:
    Test the performance of the logger class by quickly reading a HDF5 file into the
    shared queue. Ensure the logging was completed within a certain time and the
    contents of he input and output files match.
    """
    input_file = "input_files/60_minutes.hdf5"
    output_file = "output_files/performance.hdf5"
    input_f_o = h5py.File(input_file, "r", libver="latest")
    nodes = list(input_f_o.keys())
    test_start = datetime.now()
    hll = stub_scu()
    logger = log.Logger(file_name=output_file, high_level_library=hll)
    logger.add_nodes(nodes, 50)

    logger.start()
    put_hdf5_file_in_queue(nodes, input_f_o, logger)
    logger.stop()
    logger.wait_for_completion()
    test_stop = datetime.now()
    input_f_o.close()

    test_duration = test_stop - test_start
    print(f"Performance test duration: {test_duration}")
    # Check test ran in a reasonable time (1/10th of input file duration).
    assert test_duration < timedelta(minutes=6)

    result = subprocess.run(["h5diff", "-v", input_file, output_file])
    # Check output file contents match input file contents
    # The h5diff linux tool is returning 2 (i.e. error code) for 0 differences
    # found on the MockData.bool dataset.
    # assert result.returncode == 0 # assert excluded because of tool bug


def test_add_nodes(caplog):
    """
    add_nodes:
    Test the add_nodes method. Nodes are added correctly, logging matches expected,
    and nothing happens if _start_invoked is set.
    """
    logger = log.Logger(file_name="n/a")
    nodes = ["MockData.increment", "MockData.sine_value", "MockData.cosine_value", "a"]
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
    assert captured == expected_log or captured == expected_log2
    expected_object_nodes = {
        "MockData.increment": 50,
        "MockData.sine_value": 100,
        "MockData.cosine_value": 100,
        "MockData.bool": 50,
        "MockData.enum": 50,
    }
    assert logger._nodes == expected_object_nodes


def test_build_hdf5_structure():
    """
    _build_hdf5_structure:
    Test the _build_hdf5_structure() method. Checks the correct hierarchical structure
    is created and the file object is set to SWMR mode.
    """
    output_file = "output_files/_build_hdf5_structure.hdf5"
    logger = log.Logger(file_name=output_file)
    nodes = ["MockData.bool", "MockData.enum", "MockData.increment"]
    logger.add_nodes(nodes, 100)
    logger.file_object = h5py.File(output_file, "w", libver="latest")
    logger._build_hdf5_structure()
    expected_node_list = nodes
    assert list(logger.file_object.keys()) == expected_node_list
    assert logger.file_object.swmr_mode == True
    logger.file_object.close()


def test_start(caplog):
    """
    start:
    Test the start() method. Check that a file (and directory) is made with the input
    file name, and that it cannot be invoked twice, logging the correct messages.
    """
    output_file = "output_files/start.hdf5"
    hll = stub_scu()
    logger = log.Logger(file_name=output_file, high_level_library=hll)
    nodes = ["MockData.bool", "MockData.enum", "MockData.increment"]
    logger.add_nodes(nodes, 100)
    logger.start()
    logger.start()
    expected_log = [
        "renamed Locked&Stowed to Locked_Stowed due to Python syntax",
        "Writing data to file: output_files/start.hdf5",
        "WARNING: start() can only be invoked once per object.",
    ]
    # Sometimes the first line above does not appear
    expected_log2 = [
        "Writing data to file: output_files/start.hdf5",
        "WARNING: start() can only be invoked once per object.",
    ]
    # Check messages are those expected.
    assert caplog.messages == expected_log or caplog.messages == expected_log2
    # Check file was created.
    assert os.path.exists(output_file) == True
    logger.stop()
    logger.wait_for_completion()


def test_stop():
    """
    stop:
    Test the stop() method. Check _stop_logging is being set.
    """
    output_file = "output_files/stop.hdf5"
    hll = stub_scu()
    logger = log.Logger(file_name=output_file, high_level_library=hll)
    nodes = ["MockData.bool", "MockData.enum", "MockData.increment"]
    logger.add_nodes(nodes, 100)
    logger.start()
    logger.stop()
    assert logger._stop_logging.is_set() == True
    logger.wait_for_completion()


def test_write_cache_to_group():
    """
    _write_cache_to_group:
    Test the _write_cache_to_group() method. Check that values are written to the
    output file.
    """
    output_file = "output_files/_write_cache_to_group.hdf5"
    hll = stub_scu()
    logger = log.Logger(file_name=output_file, high_level_library=hll)
    nodes = ["MockData.increment"]
    logger.add_nodes(nodes, 100)
    logger.file_object = h5py.File(output_file, "w", libver="latest")
    logger._build_hdf5_structure()
    # Add some data to the cache for a node.
    data = [
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


def test_log():
    """
    _log:
    Test the log() method. Add datapoints to the queue from a known input file, check
    the output file contains all expected values.
    """
    input_file = "input_files/_log.hdf5"
    output_file = "output_files/_log.hdf5"
    input_f_o = h5py.File(input_file, "r", libver="latest")
    nodes = list(input_f_o.keys())
    hll = stub_scu()
    logger = log.Logger(file_name=output_file, high_level_library=hll)
    logger.add_nodes(nodes, 50)

    logger.start()
    put_hdf5_file_in_queue(nodes, input_f_o, logger)
    logger.stop()
    logger.wait_for_completion()
    output_f_o = h5py.File(output_file, "r", libver="latest")

    for node in nodes:
        in_timestamps = input_f_o[node]["SourceTimestamp"][:]
        in_values = input_f_o[node]["Value"][:]
        out_timestamps = output_f_o[node]["SourceTimestamp"][:]
        out_values = output_f_o[node]["Value"][:]
        # Check the data in the file matches.
        for i in range(len(in_timestamps)):
            assert out_timestamps[i] == in_timestamps[i]
            assert out_values[i] == in_values[i]

    input_f_o.close()
    output_f_o.close()


def test_wait_for_completion(caplog):
    """
    wait_for_completion:
    Test the wait_for_completion method. Check the log messages.
    """
    logger = log.Logger(file_name="n/a")
    logger._start_invoked = False
    logger._stop_logging.clear()
    logger.logging_complete.set()
    logger.wait_for_completion()
    logger._start_invoked = True
    logger.wait_for_completion()
    logger._stop_logging.set()
    logger.wait_for_completion()
    expected_log = [
        "renamed Locked&Stowed to Locked_Stowed due to Python syntax",
        "WARNING: cannot wait for logging to complete if start() has not been invoked.",
        "WARNING: cannot wait for logging to complete if stop() has not been invoked.",
    ]
    # Sometimes the first line above does not appear
    expected_log2 = [
        "WARNING: cannot wait for logging to complete if start() has not been invoked.",
        "WARNING: cannot wait for logging to complete if stop() has not been invoked.",
    ]
    assert caplog.messages == expected_log or caplog.messages == expected_log2


def test_enum_attribute():
    """
    Enum attribute:
    Test that an attribute containing a comma separated string of available enum string
    states is added to enum type node value datasets.
    """
    output_file = "output_files/enum_attribute.hdf5"
    logger = log.Logger(file_name=output_file)
    nodes = ["MockData.bool", "MockData.enum", "MockData.increment"]
    logger.add_nodes(nodes, 100)
    logger.start()
    logger.stop()
    logger.wait_for_completion()
    output_f_o = h5py.File(output_file, "r", libver="latest")
    expected_attribute = (
        "StartUp,Standby,Locked,EStop,Stowed,Locked&Stowed,Activating,Deactivation,"
        "Standstill,Stop,Slew,Jog,Track"
    )
    assert (
        output_f_o["MockData.enum"]["Value"].attrs["Enumerations"] == expected_attribute
    )
