from queue import Queue

from PyQt6 import QtCore
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton, QStatusBar

from ska_mid_dish_qualification.sculib import scu


class Window(QMainWindow):
    def __init__(self, subscription):
        super().__init__()
        self._scu = None
        self._subscription_queue = subscription.queue
        subscription.worker.data_received.connect(self.handle_data)

        button1 = QPushButton(self)
        button1.setText("Button 1 (sync)")
        button1.setGeometry(25, 50, 200, 250)
        button1.clicked.connect(self.button1_clicked)

        button2 = QPushButton(self)
        button2.setText("Button 2\nInit sculib")
        button2.setGeometry(275, 50, 200, 250)
        button2.clicked.connect(self.button2_clicked)

        button3 = QPushButton(self)
        button3.setText("Button 3\nnothing")
        button3.setGeometry(525, 50, 200, 250)
        button3.clicked.connect(self.button3_clicked)

        # Add a label widget to the status bar for command/response status
        # The QT Designer doesn't allow us to add this label so we have to do it here
        self.cmd_status_label = QLabel("command status: ")
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.addWidget(self.cmd_status_label)

    @QtCore.pyqtSlot()
    def button1_clicked(self):
        print("btn1 clicked")
        self.cmd_status_label.setText("slot works")

    @QtCore.pyqtSlot()
    def button2_clicked(self):
        print("btn2 clicked")
        print("Instantiating sculib object")
        self._scu = scu(
            host="localhost",
            endpoint="/dish-structure/server/",
            namespace="http://skao.int/DS_ICD/",
        )
        print("Sculib initialised!")
        self.cmd_status_label.setText("sculib initialised")

    @QtCore.pyqtSlot()
    def button3_clicked(self):
        print("btn3 clicked")
        if self._scu is not None:
            self._scu.subscribe(
                ["Elevation.p_Set", "Azimuth.p_Set"],
                data_queue=self._subscription_queue,
            )

    @QtCore.pyqtSlot(dict)
    def handle_data(self, data: dict) -> None:
        print(f"Data keys: {data.keys()}")


class Worker(QtCore.QThread):
    data_received = QtCore.pyqtSignal(dict)

    def __init__(self, queue) -> None:
        super().__init__()
        self.queue: Queue = queue

    def run(self) -> None:
        while True:
            print("Waiting for data")
            data = self.queue.get()
            print(f"Got data: {data}")
            self.data_received.emit(data)


class SubscriptionHandler:
    def __init__(self) -> None:
        self.queue: Queue = Queue()
        self.worker: QtCore.QThread = Worker(self.queue)
        self.worker.start()


def main():
    app = QApplication([])
    subscription = SubscriptionHandler()
    window = Window(subscription=subscription)
    window.setGeometry(200, 150, 760, 350)
    window.setWindowTitle("Simple Threaded demo")
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
