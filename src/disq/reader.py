import h5py
from datetime import datetime
import matplotlib.pyplot as plt  # TODO add matplotlib to disq modules
import matplotlib.dates as dates
import matplotlib.ticker as ticker


class Reader:
    def __init__(self, file):
        self.file = file

    def fill(self, node, start, stop):
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
        fo.close()

        self._x = []
        self._y = []

        for i in range(0, len(self._srctimestamps)):
            time = datetime.fromtimestamp(self._srctimestamps[i])
            if time >= start and time <= stop:
                self._x.append(time)
                self._y.append(self._values[i])

        print("Data range start:", start)
        print("Data range stop:", stop)

    def plot(self):
        fig, ax = plt.subplots()
        plt.scatter(self._x, self._y, marker="x", c="k")
        ax.set_axisbelow(True)
        ax.xaxis.set_major_formatter(dates.DateFormatter("%Y-%m-%dT%H:%M:%S.%f"))
        ax.xaxis.set_minor_locator(ticker.AutoMinorLocator(10))
        ax.yaxis.set_minor_locator(ticker.AutoMinorLocator(10))
        plt.xticks(rotation=90)
        plt.grid(visible=True, which="major", c="dimgrey")
        plt.grid(visible=True, which="minor")
        plt.show()


if __name__ == "__main__":
    reader = Reader("src/disq/delme/2023-10-05_11-08-24.hdf5")
    start = datetime.fromtimestamp(1696495948.075715)
    stop = datetime.fromtimestamp(1696495954.026438)
    print(start, stop)
    reader.fill("MockData.sine_value", start, stop)
    reader.plot()
