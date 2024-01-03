import h5py
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def format_coord(self, x, y):
    """Return a format string formatting the *x*, *y* coordinates."""
    return "x={} y={}".format(
        "???" if x is None else self.format_xdata(x),
        "???" if y is None else self.format_ydata(y),
    )


def make_format(current, other):
    # current and other are axes
    def format_coord(x, y):
        # x, y are data coordinates
        # convert to display coords
        display_coord = current.transData.transform((x, y))
        inv = other.transData.inverted()
        # convert back to data coords with respect to ax
        ax_coord = inv.transform(display_coord)
        coords = [ax_coord, (x, y)]
        # print(coords)
        return "Left: {:<40}    Right: {:<}".format(
            "(x={}, y={})".format(
                "???" if x is None else other.format_xdata(coords[0][0]),
                "???" if y is None else other.format_ydata(coords[0][1]),
            ),
            "(x={}, y={})".format(
                "???" if x is None else current.format_xdata(coords[1][0]),
                "???" if y is None else current.format_ydata(coords[1][1]),
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
    _y1_colour = "red"
    _y2_colour = "blue"
    _y1_marker = "x"
    _y2_marker = "*"
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
        start_dt = None
        stop_dt = None
        y1_dt = []
        y1_data = []
        y1_type = None
        y1_categories = []
        y2_dt = []
        y2_data = []
        y2_type = None
        y2_categories = []
        with h5py.File(file, "r") as f:
            if start is None:
                start = f.attrs["Start time"]
            if stop is None:
                stop = f.attrs["Stop time"]

            start_dt = datetime.fromisoformat(start)
            stop_dt = datetime.fromisoformat(stop)

            for i in range(f[node1]["SourceTimestamp"].len()):
                dt = datetime.fromtimestamp(f[node1]["SourceTimestamp"][i])
                if dt > start_dt:
                    if dt < stop_dt:
                        y1_dt.append(dt)
                        y1_data.append(f[node1]["Value"][i])
                    else:
                        # Datapoints are stored chronologically; stop here.
                        break

            y1_type = f[node1]["Value"].attrs["Type"]
            if y1_type == "bool":
                y1_categories = ["False", "True"]
            if y1_type == "enum":
                y1_categories = f[node1]["Value"].attrs["Enumerations"].split(",")

            if node2 is not None:
                for i in range(f[node2]["SourceTimestamp"].len()):
                    dt = datetime.fromtimestamp(f[node2]["SourceTimestamp"][i])
                    if dt > start_dt:
                        if dt < stop_dt:
                            y2_dt.append(dt)
                            y2_data.append(f[node2]["Value"][i])
                        else:
                            # Datapoints are stored chronologically; stop here.
                            break

                y2_type = f[node2]["Value"].attrs["Type"]
                if y2_type == "bool":
                    y2_categories = ["False", "True"]
                if y2_type == "enum":
                    y2_categories = f[node2]["Value"].attrs["Enumerations"].split(",")

        fig, y1 = plt.subplots()
        y1.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m-%d %H:%M:%S.%f"))
        y1.plot(
            y1_dt, y1_data, color=self._y1_colour, label=node1, marker=self._y1_marker
        )
        if len(y1_categories) > 0:
            y1.set_yticks(ticks=range(len(y1_categories)), labels=y1_categories)
            y1.format_ydata = categorical_ydata(y1_categories)

        y1.legend(
            bbox_to_anchor=(0, 1.02, 1, 0.2),
            loc="lower left",
            borderaxespad=0,
        )

        if node2 is not None:
            y2 = y1.twinx()
            y2.plot(
                y2_dt,
                y2_data,
                color=self._y2_colour,
                label=node2,
                marker=self._y2_marker,
            )
            if len(y2_categories) > 0:
                y2.set_yticks(ticks=range(len(y2_categories)), labels=y2_categories)
                y2.format_ydata = categorical_ydata(y2_categories)

            y2.legend(
                bbox_to_anchor=(0, 1.02, 1, 0.2),
                loc="lower right",
                borderaxespad=0,
            )

            y2.format_coord = make_format(y2, y1)

        fig.autofmt_xdate(rotation=90)
        plt.grid(
            visible=self._grid_lines,
            which="major",
            c="dimgrey",
            dashes=self._dash_sequence,
        )
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    my_grapher = Grapher()
    my_grapher.graph(
        "results/2023-10-13_16-48-37.hdf5",
        "MockData.sine_value",
        "MockData.enum",
    )
