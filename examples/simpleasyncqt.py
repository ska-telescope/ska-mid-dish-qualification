import asyncio
import sys

from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton, QStatusBar
from qasync import QEventLoop, asyncSlot

from disq.sculib import SCU


class Window(QMainWindow):
    def __init__(self, loop=None):
        super().__init__()
        self._scu = None
        self._loop = loop

        button1 = QPushButton(self)
        button1.setText("Button 1 (sync)")
        button1.setGeometry(25, 50, 200, 250)
        button1.clicked.connect(self.button1_clicked)

        button2 = QPushButton(self)
        button2.setText("Button 2 (async)\nStart Thread in sculib")
        button2.setGeometry(275, 50, 200, 250)
        button2.clicked.connect(self.button2_clicked)

        button3 = QPushButton(self)
        button3.setText("Button 3 (async)\nPass Event Loop to sculib (LOCKS!)")
        button3.setGeometry(525, 50, 200, 250)
        button3.clicked.connect(self.button3_clicked)

        # Add a label widget to the status bar for command/response status
        # The QT Designer doesn't allow us to add this label so we have to do it here
        self.cmd_status_label = QLabel("command status: ")
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.addWidget(self.cmd_status_label)

    @asyncSlot()
    async def button1_clicked(self):
        print("btn1 clicked")
        self.cmd_status_label.setText("async slot works")

    @asyncSlot()
    async def button2_clicked(self):
        print("btn2 clicked")
        print("Instantiating sculib object with no eventloop defined")
        self._scu = SCU(
            host="localhost",
            endpoint="/dish-structure/server/",
            namespace="http://skao.int/DS_ICD/",
        )
        print("Sculib initialised!")
        self.cmd_status_label.setText("sculib initialised with no event loop defined")

    @asyncSlot()
    async def button3_clicked(self):
        print("btn3 clicked")
        print(f"Instantiating sculib object with eventloop: {self._loop}")
        self._scu = SCU(
            host="localhost",
            endpoint="/dish-structure/server/",
            namespace="http://skao.int/DS_ICD/",
            eventloop=self._loop,
        )
        print("Sculib initialised!")
        self.cmd_status_label.setText(
            f"sculib initialised with eventloop: {self._loop}"
        )


async def main():
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    widget = Window(loop=loop)
    widget.setGeometry(200, 150, 760, 350)
    widget.setWindowTitle("Buttons connected to different funcs")
    widget.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    print("About to start")
    asyncio.run(main())
