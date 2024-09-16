"""HDF5 to CSV converter."""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Final

import h5py

# TODO: This class could use some refactoring. There is no __init__, so the only public
# method make_csv() can be decorated as a static method and the private methods as class
# methods.


# pylint: disable=too-few-public-methods,attribute-defined-outside-init
class Converter:
    """
    A class representing a Converter.

    - `default_start_delta`: The default time delta for the start.
    - `_NO_DATA_YET_STR`: A string indicating no data is available yet.
    - `_OLD_DATA_STR`: A string indicating old data.
    - `_DELIMITER`: The delimiter used in the CSV output.

    Methods:
    - `_get_adjacent_data`: Get the adjacent data for a given time and node.
    - `_make_node_d`: Make a dictionary of nodes with their properties.
    - `_check_start_stop`: Check start and stop times against file start and stop times.
    - `_create_next_line`: Create the next line of the CSV output.
    - `make_csv`: Generate a CSV output file based on input file and parameters.

    :param input_file: The input file to read data from.
    :type input_file: str
    :param output_file: The output file to write the CSV data.
    :type output_file: str
    :param nodes: The list of nodes to include in the CSV output.
    :type nodes: str or list[str]
    :param start: The start time for the CSV output.
    :type start: datetime, optional
    :param stop: The stop time for the CSV output.
    :type stop: datetime, optional
    :param step_ms: The time step in milliseconds for the CSV output.
    :type step_ms: int, default 100
    """

    # TODO: configure good default start
    _DEFAULT_START_DELTA: Final = timedelta(minutes=60)
    _NO_DATA_YET_STR: Final = "-"
    _OLD_DATA_STR: Final = "*"
    _DELIMITER: Final = ","

    def _get_adjacent_data(
        self, time: datetime, node: str, look_from: tuple[Any, ...]
    ) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
        """
        Get adjacent data.

        look_from timestamp must be less than time i.e. while must loop at least once.
        No do-while in Python at the time of writing.
        """
        before: tuple[Any, ...] = None
        after: tuple[Any, ...] = look_from

        while after[0] < time:
            idx = after[3] + 1
            if idx >= self._node_d[node]["length"]:
                # No more data for this node in this file (length of SourceTimestamp
                # and Value datasets always match for a given node).
                before = (after[0], after[1], True, after[3])
                break

            before = after
            # Get the value at the new idx as a string
            value = ""
            if self._node_d[node]["type"] == "Enumeration":
                value = self._node_d[node]["enums"][
                    self._file_object[node]["Value"][idx]
                ]
            elif self._node_d[node]["type"] == "String":
                value = self._file_object[node]["Value"].asstr()[idx]
            elif self._node_d[node]["type"] == "Pointing.Status.CurrentPointing":
                value = "|".join(
                    [str(x) for x in self._file_object[node]["Value"][idx]]
                )

            else:
                value = str(self._file_object[node]["Value"][idx])

            # The timestamp stored in the hdf5 file (read: returned from the OPCUA
            # server) must be UTC
            aware_datetime = datetime.fromtimestamp(
                self._file_object[node]["SourceTimestamp"][idx], tz=timezone.utc
            )
            after = (
                aware_datetime,
                value,
                False,
                idx,
            )

        return before, after

    def _make_node_d(self, input_nodes: list[str], file_nodes: list[str]) -> bool:
        """
        Make a node dictionary based on input nodes and file nodes.

        The function checks the input nodes against the file nodes and creates a
        dictionary for each known node with its type, length, current value, and next
        value. If the node type is 'enum', it also stores the possible enumerations. If
        no known nodes are found, an error message is printed and the function returns
        False.

        :param input_nodes: A list of node names from the input.
        :type input_nodes: list[str]
        :param file_nodes: A list of node names from the file.
        :type file_nodes: list[str]
        :return: True if the node dictionary was successfully created, otherwise False.
        :rtype: bool
        """
        known_nodes = []
        for node in input_nodes:
            if node in file_nodes:
                known_nodes.append(node)
            else:
                print(f"Node {node} is not in the input file and will be ignored.")

        if len(known_nodes) == 0:
            print("ERROR: No data for requested nodes, exiting")
            return False

        self._node_d = {}
        for node in known_nodes:
            node_type = self._file_object[node]["Value"].attrs["Type"]
            length = self._file_object[node]["Value"].len()
            self._node_d[node] = {
                "type": node_type,
                "length": length,
                "current": None,
                "next": None,
            }
            if node_type == "Enumeration":
                self._node_d[node]["enums"] = (
                    self._file_object[node]["Value"].attrs["Enumerations"].split(",")
                )

        return True

    def _check_start_stop(self, start: datetime | None, stop: datetime | None) -> bool:
        """
        Check and adjust the start and stop times based on file attributes.

        :param start: The start time to check and adjust.
        :type start: datetime or None
        :param stop: The stop time to check and adjust.
        :type stop: datetime or None
        :return: True if the start and stop times are valid and adjusted, False
            otherwise.
        :rtype: bool
        :raises ValueError: If the start time is before the earliest file start time or
            after the latest file stop time.
        :raises ValueError: If the stop time is before the start time.
        :raises ValueError: If the start time is before the start of the input file.
        :raises ValueError: If the stop time is after the end of the input file.
        :raises ValueError: If the start time is after the stop time.
        """
        file_start = datetime.fromisoformat(self._file_object.attrs["Start time"])
        file_stop = datetime.fromisoformat(self._file_object.attrs["Stop time"])

        if stop is None:
            stop = datetime.now(timezone.utc)

        if start is None:
            start = stop - self._DEFAULT_START_DELTA

        if start < file_start:
            print(
                f"Requested start time {start} is before earliest file start "
                f"{file_start}. Output CSV will start from {file_start}"
            )
            start = file_start

        if start >= file_stop:
            print(
                f"Error: Requested start time {start} is past the end of the "
                f"input_file ({file_stop}), exiting."
            )
            return False

        if stop > file_stop:
            print(
                f"Requested stop time {stop} is after latest file stop {file_stop}. "
                f"Output CSV will stop at {file_stop}"
            )
            stop = file_stop

        if stop <= file_start:
            print(
                f"Error: Requested stop time {stop} is before the start of the "
                f"input_file ({file_start}), exiting."
            )
            return False

        # Determine if start falls within a file
        self._start_in_file = False
        if file_start < start < file_stop:
            self._start_in_file = True

        if stop <= start:
            print("ERROR: Start must be before stop, exiting.")
            return False

        self.start = start
        self.stop = stop
        return True

    def _create_next_line(self, line_time: datetime, prev_time: datetime) -> str:
        """
        Create the next line in a data file based on the current time and previous time.

        :param line_time: The current time to generate the line for.
        :type line_time: datetime
        :param prev_time: The previous time for comparison.
        :type prev_time: datetime
        :return: The next line in the data file as a string.
        :rtype: str
        """
        line = [f"{line_time.isoformat()}Z"]
        # Add a column in the line for each node
        for node in self._node_d:  # TODO: pylint: disable=consider-using-dict-items
            current: tuple[Any, ...] = self._node_d[node]["current"]
            next_val: tuple[Any, ...] = self._node_d[node]["next"]
            # We already have the most recent value, no need to look again
            # Or reached end of node data in file
            if (current[0] < line_time < next_val[0]) or current[2]:
                if current[0] < prev_time:
                    line.append(f"{self._DELIMITER}{current[1]}{self._OLD_DATA_STR}")
                else:
                    line.append(f"{self._DELIMITER}{current[1]}")
                continue

            # Keep searching the current file.
            # We can't just assume it's at the next index as data may
            # have been produced in smaller intervals than requested
            # step_ms.
            # Minimises disk access as HDF5 should store recently read
            # chunks in memory.
            current, next_val = self._get_adjacent_data(line_time, node, current)

            if current[0] < prev_time:
                line.append(f"{self._DELIMITER}{current[1]}{self._OLD_DATA_STR}")
            else:
                line.append(f"{self._DELIMITER}{current[1]}")

            self._node_d[node]["current"] = current
            self._node_d[node]["next"] = next_val

        line.append("\n")
        return "".join(line)

    # pylint: disable=too-many-arguments,too-many-locals
    def make_csv(
        self,
        input_file: str,
        output_file: str,
        nodes: str | list[str],
        start: datetime = None,
        stop: datetime = None,
        step_ms: int = 100,
    ) -> None:
        """
        Generate a CSV file from an HDF5 input file.

        :param input_file: Path to the input HDF5 file.
        :type input_file: str
        :param output_file: Path to the output CSV file.
        :type output_file: str
        :param nodes: List of node names or a single node name to include in the CSV.
        :type nodes: str or list[str]
        :param start: Start datetime for data extraction. Defaults to None.
        :type start: datetime
        :param stop: Stop datetime for data extraction. Defaults to None.
        :type stop: datetime
        :param step_ms: Time step in milliseconds. Defaults to 100.
        :type step_ms: int
        :raises ValueError: If nodes are not found in the input file.
        :raises OSError: If an I/O operation fails.
        """
        if isinstance(nodes, str):
            nodes = [nodes]

        self._file_object = h5py.File(input_file, "r")
        file_nodes = list(self._file_object.keys())
        if not self._make_node_d(nodes, file_nodes):
            return

        if not self._check_start_stop(start, stop):
            return

        # Populate the node cache
        cache_init = (
            self.start - timedelta(milliseconds=step_ms),
            self._NO_DATA_YET_STR,
            False,
            -1,
        )
        for node in self._node_d:  # TODO: pylint: disable=consider-using-dict-items
            self._node_d[node]["current"] = cache_init
            self._node_d[node]["next"] = cache_init

        # Create directories if they don't exist
        output_directory = os.path.dirname(output_file)
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)

        # Write the CSV
        with open(output_file, "w", encoding="UTF-8") as f:
            # Match example file (timestamps end with a 'Z')
            f.write(f"StartTime{self._DELIMITER}{self.start.isoformat()}Z\n")
            f.write(f"EndTime{self._DELIMITER}{self.stop.isoformat()}Z\n")

            header = (
                "Date/Time"
                + self._DELIMITER
                + self._DELIMITER.join(node for node in self._node_d)
            )
            f.write(header + "\n")

            line_time = self.start
            # File start times are always before first value so skip first loop unless
            # we start in the middle of the file.
            if not self._start_in_file:
                line_time += timedelta(milliseconds=step_ms)

            prev_time = line_time - timedelta(milliseconds=step_ms)
            # Loop until we reach end of the input file
            while line_time <= self.stop:
                line = self._create_next_line(line_time, prev_time)
                f.write(line)

                prev_time = line_time
                line_time += timedelta(milliseconds=step_ms)

        # Close the HDF5 file
        self._file_object.close()
