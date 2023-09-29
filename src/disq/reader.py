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
        dataset = fo[node]

        self.data = [[], []]

        for i in range(0, dataset.len()):
            tup = dataset[i][0]
            tup_time = datetime.fromisoformat(tup[0].decode("utf-8"))
            if tup_time >= start and tup_time <= stop:
                self.data[0].append(tup_time)
                self.data[1].append(tup[1])

        fo.close()
        print("Data range start:", start)
        print("Data range stop:", stop)

    def plot(self):
        fig, ax = plt.subplots()
        plt.scatter(self.data[0], self.data[1], marker="x", c="k")
        ax.set_axisbelow(True)
        ax.xaxis.set_major_formatter(dates.DateFormatter("%Y-%m-%dT%H:%M:%S.%f"))
        ax.xaxis.set_minor_locator(ticker.AutoMinorLocator(10))
        ax.yaxis.set_minor_locator(ticker.AutoMinorLocator(10))
        plt.xticks(rotation=90)
        plt.grid(visible=True, which="major", c="dimgrey")
        plt.grid(visible=True, which="minor")
        plt.show()
