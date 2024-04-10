from datetime import datetime

import h5py
import matplotlib.axes as axes  # Entire import just for typehints
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


def make_format(current: axes.Axes, other: axes.Axes, current_lab: str, other_lab: str):
    """
    Used for replacing the format_coord method of an matplotlib.axes object.
    """

    def format_coord(x, y):
        # x, y are data coordinates
        # convert to display coords
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


def categorical_ydata(labels: list[str]):
    """
    Convert y-value into string.
    """

    def format_ydata(y):
        ry = round(y)
        if ry >= len(labels):
            ry = len(labels) - 1
        if ry < 0:
            ry = 0
        return labels[ry]

    return format_ydata


class Grapher:
    _axis_colour = ("red", "blue")
    _axis_marker = ("x", "*")
    _axis_legend_location = ("lower left", "lower right")
    _grid_lines = True
    _dash_sequence = (3, 5)

    def hdf5_info(self, file: str):
        """Print the start and stop times and available nodes for the input
        hdf5 file."""
        with h5py.File(file, "r") as f:
            print(f"File: {file}")
            print(f"{f.attrs['Start time']} file starts.")
            print(f"{f.attrs['Stop time']} file stops.")
            print("The following nodes are available:")
            for node in f.keys():
                print(node)

    def _get_hdf5_data(self, fo: h5py.File, node: str, start: datetime, stop: datetime):
        dts = []
        data = []
        for i in range(fo[node]["SourceTimestamp"].len()):
            dt = datetime.fromtimestamp(fo[node]["SourceTimestamp"][i])
            if dt > start:
                if dt < stop:
                    dts.append(dt)
                    data.append(fo[node]["Value"][i])
                else:
                    # Datapointes are store chronologically; stop here.
                    break

        node_type = fo[node]["Value"].attrs["Type"]
        categories = []
        if node_type == "bool":
            categories = ["False", "True"]
        if node_type == "enum":
            categories = fo[node]["Value"].attrs["Enumerations"].split(",")

        return (dts, data, categories)

    def _build_axis(
        self,
        node: str,
        axis: axes.Axes,
        x: list[datetime],
        y: list,
        num: int,
        categories: list[str],
    ):
        axis.plot(
            x,
            y,
            color=self._axis_colour[num],
            label=node,
            marker=self._axis_marker[num],
        )
        if len(categories) > 0:
            axis.set_yticks(ticks=range(len(categories)), labels=categories)
            axis.format_ydata = categorical_ydata(categories)

        axis.legend(
            bbox_to_anchor=(0, 1.02, 1, 0.2),
            loc=self._axis_legend_location[num],
            borderaxespad=0,
        )

    def graph(
        self,
        file: str,
        node1: str,
        node2: str = None,
        start: str = None,
        stop: str = None,
    ):
        """Generate a graph with one or two y axis (nodes) with the same x
        axis (time). Start and stop are datetime strings in ISO format (e.g.
        YYYY-MM-DDThh:mm:ss). If the start or stop times are not given, the
        graph will default to the full time range of the input file."""
        # Get data from HDF5 file
        with h5py.File(file, "r") as f:
            if start is None:
                start = f.attrs["Start time"]
            if stop is None:
                stop = f.attrs["Stop time"]

            start_dt = datetime.fromisoformat(start)
            stop_dt = datetime.fromisoformat(stop)

            y1_dts, y1_data, y1_categories = self._get_hdf5_data(
                f, node1, start_dt, stop_dt
            )

            if node2 is not None:
                y2_dts, y2_data, y2_categories = self._get_hdf5_data(
                    f, node2, start_dt, stop_dt
                )

        # Build graph
        fig, y1 = plt.subplots(figsize=(12, 4.8))
        y1.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m-%d %H:%M:%S.%f"))
        self._build_axis(node1, y1, y1_dts, y1_data, 0, y1_categories)

        if node2 is not None:
            y2 = y1.twinx()
            self._build_axis(node2, y2, y2_dts, y2_data, 1, y2_categories)

            y2.format_coord = make_format(y2, y1, node2, node1)

        fig.autofmt_xdate(rotation=20)
        plt.grid(
            visible=self._grid_lines,
            which="major",
            c="dimgrey",
            dashes=self._dash_sequence,
        )
        plt.tight_layout()
        plt.show()
