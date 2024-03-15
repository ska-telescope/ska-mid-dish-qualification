from datetime import datetime

import h5py
import matplotlib.dates as dates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import plotly.graph_objects as graph_obj


class Reader:
    _type = None

    def __init__(self, file: str):
        self.file = file

    def fill(self, node: str, start: datetime, stop: datetime):
        """Retreive datapoints from file for given node between start and stop times"""
        fo = h5py.File(self.file, "r", libver="latest")
        group = fo[node]

        """
        # List comprehensions are faster than append-for because they have a different method than .append() with less overhead than calling an entire function.
        # This introduces way more overhead, no way comprehensions are faster for this use case.
        self._x = [
            data
            for data in group["SourceTimestamp"]
            if datetime.fromtimestamp(data) >= start
            and datetime.fromtimestamp(data) <= stop
        ]
        """
        self._srctimestamps = group["SourceTimestamp"][:]
        self._values = group["Value"][:]
        self._type = group["Value"].attrs["Type"]
        enums = []
        if self._type == "enum":
            enums = group["Value"].attrs["Enumerations"].split(",")

        fo.close()
        print("Data range start:", start)
        print("Data range stop:", stop)

        self._x = []
        self._y = []

        for i in range(0, len(self._srctimestamps)):
            time = datetime.fromtimestamp(self._srctimestamps[i])
            if time >= start and time <= stop:
                self._x.append(time)
                if self._type == "enum":
                    self._y.append(enums[self._values[i]])
                else:
                    self._y.append(self._values[i])

    def plot(self):
        """Plot the fetched data. Creates a graph for type "double" or a table for types
        "bool" and "enum"."""
        match self._type:
            case "double":
                fig, ax = plt.subplots()
                plt.scatter(self._x, self._y, marker="x", c="k")
                ax.set_axisbelow(True)
                ax.xaxis.set_major_formatter(
                    dates.DateFormatter("%Y-%m-%dT%H:%M:%S.%f")
                )
                ax.xaxis.set_minor_locator(ticker.AutoMinorLocator(10))
                ax.yaxis.set_minor_locator(ticker.AutoMinorLocator(10))
                plt.xticks(rotation=90)
                plt.grid(visible=True, which="major", c="dimgrey")
                plt.grid(visible=True, which="minor")
                plt.show()

            case "bool" | "enum":
                data = graph_obj.Table(
                    header={"values": ["SourceTimestamp", "Values"]},
                    cells={"values": [self._x, self._y]},
                )
                fig = graph_obj.Figure(data=data)
                fig.show(renderer="plotly_mimetype")  # TODO requires nbformat installed
            case _:
                print("Unknown type")
