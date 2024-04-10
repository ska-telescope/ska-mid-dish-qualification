import os
from datetime import datetime, timedelta, timezone

import h5py


class Converter:
    default_start_delta = timedelta(minutes=60)  # TODO configure good default start

    _NO_DATA_YET_STR = "-"
    _OLD_DATA_STR = "*"
    _DELIMITER = ","

    def _get_adjacent_data(
        self, time: datetime, node: str, look_from: tuple
    ) -> tuple[datetime, datetime]:
        """look_from timestamp must be less than time i.e. while must loop at least
        once. No do-while in Python at the time of writing."""
        before = None
        after = look_from

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
            if self._node_d[node]["type"] == "enum":
                value = self._node_d[node]["enums"][
                    self._file_object[node]["Value"][idx]
                ]
            else:
                value = str(self._file_object[node]["Value"][idx])

            after = (
                datetime.fromtimestamp(self._file_object[node]["SourceTimestamp"][idx]),
                value,
                False,
                idx,
            )

        return before, after

    def _make_node_d(self, input_nodes: list[str], file_nodes: list[str]) -> bool:
        known_nodes = []
        for node in input_nodes:
            (
                known_nodes.append(node)
                if node in file_nodes
                else print(f"Node {node} is not in the input file and will be ignored.")
            )

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
            if node_type == "enum":
                self._node_d[node]["enums"] = (
                    self._file_object[node]["Value"].attrs["Enumerations"].split(",")
                )

        return True

    def _check_start_stop(self, start: datetime | None, stop: datetime | None) -> bool:
        file_start = datetime.fromisoformat(self._file_object.attrs["Start time"])
        file_stop = datetime.fromisoformat(self._file_object.attrs["Stop time"])

        if stop is None:
            stop = datetime.now(timezone.utc)

        if start is None:
            start = stop - self.default_start_delta

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
        if file_start <= start and file_stop > start:
            if file_start < start:
                self._start_in_file = True

        if stop <= start:
            print("ERROR: Start must be before stop, exiting.")
            return False

        self.start = start
        self.stop = stop
        return True

    def _create_next_line(self, line_time, prev_time) -> str:
        line = [f"{line_time.isoformat()}Z"]
        # Add a column in the line for each node
        for node in self._node_d.keys():
            current = self._node_d[node]["current"]
            next_val = self._node_d[node]["next"]
            # We already have the most recent value, no need to look again
            # Or reached end of node data in file
            if (line_time > current[0] and line_time < next_val[0]) or current[2]:
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

    def make_csv(
        self,
        input_file: str,
        output_file: str,
        nodes: str | list[str],
        start: datetime = None,
        stop: datetime = None,
        step_ms: int = 100,
    ):
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
        for node in self._node_d.keys():
            self._node_d[node]["current"] = cache_init
            self._node_d[node]["next"] = cache_init

        # Create directories if they don't exist
        output_directory = os.path.dirname(output_file)
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)

        # Write the CSV
        with open(output_file, "w") as f:
            # Match example file (timestamps end with a 'Z')
            f.write(f"StartTime{self._DELIMITER}{self.start.isoformat()}Z\n")
            f.write(f"EndTime{self._DELIMITER}{self.stop.isoformat()}Z\n")

            header = (
                "Date/Time"
                + self._DELIMITER
                + self._DELIMITER.join(node for node in self._node_d.keys())
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
