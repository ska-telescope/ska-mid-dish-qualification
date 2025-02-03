"""Graphing data from HDF5 files."""

from datetime import datetime, timezone
from typing import Callable

import h5py
from matplotlib import axes, dates, pyplot

from ska_mid_disq.constants import CURRENT_POINTING_NODE


# pylint: disable=consider-using-f-string
def make_format(
    current: axes.Axes, other: axes.Axes, current_lab: str, other_lab: str
) -> Callable[[float, float], str]:
    """Used for replacing the format_coord method of an matplotlib.axes object."""

    def format_coord(x: float, y: float) -> str:
        """
        Format the coordinates of two axes.

        Covert x, y data coordinates to display coords.

        :param x: The x-coordinate value.
        :type x: float
        :param y: The y-coordinate value.
        :type y: float
        :return: Formatted coordinates for two axes.
        :rtype: str
        """
        display_coord = current.transData.transform((x, y))
        inv = other.transData.inverted()
        # convert back to data coords with respect to ax
        x1, y1 = inv.transform(display_coord)
        return "{}: {:<}    {}: {:<}".format(  # noqa: FS002
            other_lab,
            "(x={}, y={})".format(  # noqa: FS002
                "???" if x1 is None else other.format_xdata(x1),
                "???" if y1 is None else other.format_ydata(y1),
            ),
            current_lab,
            "(x={}, y={})".format(  # noqa: FS002
                "???" if x is None else current.format_xdata(x),
                "???" if y is None else current.format_ydata(y),
            ),
        )

    return format_coord


def categorical_ydata(labels: list[str]) -> Callable[[float], str]:
    """Convert y-value into string."""

    def format_ydata(y: float) -> str:
        """
        Format the y data value to match a corresponding label.

        :param y: A numeric value representing the y data.
        :type y: int or float
        :return: The formatted label corresponding to the y data value.
        :rtype: str
        """
        ry = round(y)
        if ry >= len(labels):
            ry = len(labels) - 1
        ry = max(ry, 0)
        return labels[ry]

    return format_ydata


class Grapher:
    """
    A class for graphing data from HDF5 files.

    :ivar _axis_colour: Tuple of colors for the plot axes.
    :ivar _axis_marker: Tuple of markers for the plot axes.
    :ivar _axis_legend_location: Tuple of legend locations for the plot axes.
    :ivar _grid_lines: Boolean indicating whether grid lines should be displayed.
    :ivar _dash_sequence: Tuple of dash sequences for grid lines.

    .. note:: Requires the h5py library for working with HDF5 files.

    Methods
    -------
    hdf5_info(file: str)
        Print information about the HDF5 file including start and stop times and
        available nodes.

    graph(file: str, node1: str, node2: str=None, start: str=None, stop: str=None)
        Generate a graph with one or two y-axes (nodes) using data from the HDF5 file.
        Start and stop times can be specified as ISO format strings.

    Attributes
    ----------
    _axis_colour : tuple
        Tuple of colors for the plot axes.
    _axis_marker : tuple
        Tuple of markers for the plot axes.
    _axis_legend_location : tuple
        Tuple of legend locations for the plot axes.
    _grid_lines : bool
        Boolean indicating whether grid lines should be displayed.
    _dash_sequence : tuple
        Tuple of dash sequences for grid lines.
    """

    _axis_colour = ("red", "blue")
    _axis_marker = ("x", "*")
    _axis_legend_location = ("lower left", "lower right")
    _grid_lines = True
    _dash_sequence = (3, 5)

    def hdf5_info(self, file: str) -> None:
        """Print start and stop times and available nodes for the input hdf5 file."""
        with h5py.File(file, "r") as f:
            print(f"File: {file}")
            print(f"{f.attrs['Subscription start time']} file starts.")
            print(f"{f.attrs['Data stop time']} file stops.")
            print("The following nodes are available:")
            for node in f.keys():
                print(node)

    def _allowed_type(self, fo: h5py.File, node: str) -> bool:
        node_type = fo[node]["Value"].attrs["Type"]
        if node_type in ["String", CURRENT_POINTING_NODE]:
            print(f"Cannot graph attribute {node}, type {node_type} is incompatible.")
            return False

        return True

    def _get_hdf5_data(
        self, fo: h5py.File, node: str, start: datetime, stop: datetime
    ) -> tuple:
        """
        Get data from an HDF5 file for a specific node within a given time range.

        :param fo: An open HDF5 file object.
        :type fo: h5py.File
        :param node: The name of the node within the HDF5 file.
        :type node: str
        :param start: The start datetime for the time range.
        :type start: datetime.datetime
        :param stop: The stop datetime for the time range.
        :type stop: datetime.datetime
        :return: A tuple containing lists of timestamps, data values, and categories (if
            applicable).
        :rtype: tuple
        :raises: KeyError if the specified node or attribute is not found in the HDF5
            file.
        """
        dts = []
        data = []
        for i in range(fo[node]["SourceTimestamp"].len()):
            dt = datetime.fromtimestamp(fo[node]["SourceTimestamp"][i], tz=timezone.utc)
            if dt > start:
                if dt < stop:
                    dts.append(dt)
                    data.append(fo[node]["Value"][i])
                else:
                    # Datapointes are stored chronologically; stop here.
                    break

        node_type = fo[node]["Value"].attrs["Type"]
        categories = []
        if node_type == "bool":
            categories = ["False", "True"]
        if node_type == "enum":
            categories = fo[node]["Value"].attrs["Enumerations"].split(",")

        return (dts, data, categories)

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def _build_axis(
        self,
        node: str,
        axis: axes.Axes,
        x: list,
        y: list,
        num: int,
        categories: list[str],
    ) -> None:
        """
        Build an axis plot with specified data.

        This function builds a plot on the specified axis with the given data and
        formatting options. If categories are provided, the y-axis will be formatted
        accordingly. The legend for the plot will be placed at the top of the plot area
        based on the specified location and styling options.

        :param node: Node identifier for the plot.
        :type node: str
        :param axis: Matplotlib axis object for plotting.
        :type axis: axes.Axes
        :param x: List of datetime values for the x-axis.
        :type x: list[datetime]
        :param y: List of numeric values for the y-axis.
        :type y: list
        :param num: Index for tracking plot data.
        :type num: int
        :param categories: List of categories for categorical y-axis (optional).
        :type categories: list[str]
        """
        axis.plot(
            x,
            y,
            color=self._axis_colour[num],
            label=node,
            marker=self._axis_marker[num],
        )
        if len(categories) > 0:
            axis.set_yticks(ticks=range(len(categories)), labels=categories)
            axis.format_ydata = categorical_ydata(categories)  # type: ignore

        axis.legend(
            bbox_to_anchor=(0, 1.02, 1, 0.2),
            loc=self._axis_legend_location[num],
            borderaxespad=0,
        )

    # pylint: disable=too-many-arguments, too-many-locals,too-many-positional-arguments
    def graph(
        self,
        file: str,
        node1: str,
        node2: str = None,
        start: str = None,
        stop: str = None,
    ) -> None:
        """
        Generate a graph with one or two y-axis (nodes) with the same x-axis (time).

        Start and stop are datetime strings in ISO format (e.g. YYYY-MM-DDThh:mm:ss). If
        the start or stop times are not given, the graph will default to the full time
        range of the input file.
        """
        # Get data from HDF5 file
        with h5py.File(file, "r") as f:
            if start is None:
                start = f.attrs["Start time"]
            if stop is None:
                stop = f.attrs["Stop time"]

            start_dt = datetime.fromisoformat(start)
            stop_dt = datetime.fromisoformat(stop)

            if not self._allowed_type(f, node1):
                return

            y1_dts, y1_data, y1_categories = self._get_hdf5_data(
                f, node1, start_dt, stop_dt
            )

            if not self._allowed_type(f, node2):
                node2 = None

            if node2 is not None:
                y2_dts, y2_data, y2_categories = self._get_hdf5_data(
                    f, node2, start_dt, stop_dt
                )

        # Build graph
        y1: axes.Axes
        fig, y1 = pyplot.subplots(figsize=(12, 4.8))
        y1.xaxis.set_major_formatter(dates.DateFormatter("%y-%m-%d %H:%M:%S.%f"))
        self._build_axis(node1, y1, y1_dts, y1_data, 0, y1_categories)

        if node2 is not None:
            y2 = y1.twinx()
            assert isinstance(y2, axes.Axes)  # so MyPy does not flag assignment above
            self._build_axis(node2, y2, y2_dts, y2_data, 1, y2_categories)
            y2.format_coord = make_format(y2, y1, node2, node1)  # type: ignore

        fig.autofmt_xdate(rotation=20)
        pyplot.grid(
            visible=self._grid_lines,
            which="major",
            c="dimgrey",
            dashes=self._dash_sequence,
        )
        pyplot.tight_layout()
        pyplot.show()
