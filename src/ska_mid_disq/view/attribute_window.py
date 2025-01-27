"""DiSQ GUI View."""

import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

import pyqtgraph
from PySide6 import QtCore, QtWidgets
from PySide6.QtGui import QCloseEvent, QIcon, QKeySequence

from ska_mid_disq.constants import SKAO_ICON_PATH, SUBSCRIPTION_RATE_MS

logger = logging.getLogger("gui.view")


class LiveAttributeWindow(QtWidgets.QWidget):
    """A window for displaying individual attribute values only."""

    signal = QtCore.Signal(object)

    def __init__(
        self,
        attribute: str,
        close_signal: QtCore.SignalInstance,
    ):
        """
        Initialise the LiveAttributeWindow.

        :param attribute: The attribute to display.
        :param close_signal: The signal to send when this window closes.
        """
        super().__init__()
        self.attribute = attribute
        self._close_signal = close_signal
        self.signal.connect(self.data_event)
        self.setWindowTitle(self.attribute)
        self.setWindowIcon(QIcon(SKAO_ICON_PATH))
        self.resize(580, 50)

        # Value
        self.attribute_value = QtWidgets.QLineEdit(parent=self)
        self.attribute_value.setReadOnly(True)
        self.attribute_value.setPlaceholderText(self.attribute)
        self.attribute_value.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.attribute_value.resize(12, 290)
        self.attribute_time = QtWidgets.QLineEdit(parent=self)
        self.attribute_time.setReadOnly(True)
        self.attribute_time.setPlaceholderText(self.attribute)
        self.attribute_time.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.attribute_time.resize(12, 290)
        self.label_layout = QtWidgets.QHBoxLayout()
        self.label_layout.addWidget(QtWidgets.QLabel("Value"))
        self.label_layout.addWidget(QtWidgets.QLabel("Timestamp"))
        self.data_point_layout = QtWidgets.QHBoxLayout()
        self.data_point_layout.addWidget(self.attribute_value)
        self.data_point_layout.addWidget(self.attribute_time)
        self.window_layout = QtWidgets.QVBoxLayout()
        self.window_layout.addLayout(self.label_layout)
        self.window_layout.addLayout(self.data_point_layout)
        self.setLayout(self.window_layout)

    def data_event(self, data):
        """Receive the attribute data event."""
        self.attribute_value.setText(str(data["value"]))
        self.attribute_time.setText(str(data["time"]))

    # pylint: disable=invalid-name
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Override of PYQT method, called when window is closed."""
        self._close_signal.emit(self.attribute)
        super().closeEvent(event)


# pylint: disable=too-many-instance-attributes
class LiveGraphWindow(LiveAttributeWindow):
    """A LiveAttributeWindow subclass that also displays a graph."""

    AXES_LENGTH = 32

    def __init__(
        self,
        attribute: str,
        attribute_type: list[str],
        close_signal: QtCore.SignalInstance,
    ):
        """
        Initialise the LiveGraphWindow.

        :param attribute: The attribute to display.
        :param attribute_type: A list of strings, index 0 is the data type of the
            attribute, and any remaining list is enumeration strings in order.
        :param close_signal: The signal to send when this window closes.
        """
        super().__init__(attribute, close_signal)
        self._attribute_type = attribute_type.pop(0)
        self.resize(580, 400)

        # Graph
        self.graph = pyqtgraph.PlotWidget()

        self.window_layout.addWidget(self.graph)

        init_date = datetime.now(timezone.utc)
        self.time_axis_data = [init_date.timestamp()] * self.AXES_LENGTH
        logger.info("Attribute: %s, type: %s", self.attribute, self._attribute_type)
        if self._attribute_type == "Boolean":
            attribute_axis = self.graph.getAxis("left")
            major = [(0, "False"), (1, "True")]
            attribute_axis.setTicks([major])
        elif self._attribute_type == "Enumeration":
            attribute_axis = self.graph.getAxis("left")
            major = []
            for i, enum_string in enumerate(attribute_type):
                major.append((i, enum_string))

            attribute_axis.setTicks([major])

        self.attribute_axis_data = [0.0] * self.AXES_LENGTH
        self._latest_data_time = init_date
        self._data_lock = Lock()
        self.x_axis = pyqtgraph.DateAxisItem()
        self.graph.setAxisItems({"bottom": self.x_axis})
        self.line = self.graph.plot(self.time_axis_data, self.attribute_axis_data)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(SUBSCRIPTION_RATE_MS)
        self.timer.timeout.connect(self._update_plot)  # type: ignore[attr-defined]
        self.timer.start()

    def _new_data_point(self, data_time: float, value: Any) -> None:
        """Store a new data point, removing the oldest."""
        with self._data_lock:
            _ = self.time_axis_data.pop(0)
            self.time_axis_data.append(data_time)
            _ = self.attribute_axis_data.pop(0)
            self.attribute_axis_data.append(float(value))
            self._latest_data_time = datetime.now(timezone.utc)

    def _get_latest_data_time(self) -> datetime:
        """Get the local time of the last datapoint."""
        with self._data_lock:
            return self._latest_data_time

    def _get_latest_data_point(self) -> tuple[float, Any]:
        """Get the value and timestamp of the latest data point."""
        with self._data_lock:
            return (self.time_axis_data[-1], self.attribute_axis_data[-1])

    def _get_all_data(self) -> tuple[list[float], list[Any]]:
        with self._data_lock:
            return (self.time_axis_data, self.attribute_axis_data)

    def data_event(self, data: dict[str, Any]) -> None:
        """Receive the attribute data event."""
        super().data_event(data)
        self._new_data_point(data["time"].timestamp(), data["value"])

    def _update_plot(self):
        """Refresh the data in the graph."""
        # Keep the plot moving if there is no data.
        if self._get_latest_data_time() < datetime.now(timezone.utc) - timedelta(
            milliseconds=SUBSCRIPTION_RATE_MS
        ):
            data_time, data_value = self._get_latest_data_point()
            self._new_data_point(data_time + SUBSCRIPTION_RATE_MS / 1000, data_value)

        self.line.setData(*self._get_all_data())


class LiveHistoryWindow(LiveAttributeWindow):
    """A LiveAttributeWindow subclass that also displays a history log."""

    HISTORY_LENGTH = 32

    def __init__(
        self,
        attribute: str,
        close_signal: QtCore.SignalInstance,
    ):
        """
        Initialise the LiveHistoryWindow.

        :param attribute: The attribute to display.
        :param close_signal: The signal to send when this window closes.
        """
        super().__init__(attribute, close_signal)
        self.resize(580, 400)

        # History
        # pylint: disable=too-few-public-methods
        class CopyMultipleLines(QtWidgets.QListWidget):
            """Subclass QListWidget to be able to copy multiple lines."""

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.setSelectionMode(
                    QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
                )

            # pylint: disable=invalid-name
            def keyPressEvent(self, e):  # noqa: N802
                """Override keyPressEvent to copy multiple lines to clipboard."""
                if e.matches(QKeySequence.StandardKey.Copy):
                    text = ""
                    for item in self.selectedItems():
                        text += f"{item.text()}\n"

                    clipboard = QtWidgets.QApplication.clipboard()
                    clipboard.setText(text)
                    return None

                return super().keyPressEvent(e)

        self.historic_values = CopyMultipleLines()
        self.window_layout.addWidget(self.historic_values)

    def data_event(self, data):
        """Receive the attribute data event."""
        super().data_event(data)
        # Value, timestamp to match parent class window labels.
        self.historic_values.addItem(f"{data['value']},{data['time']}")
        if self.historic_values.count() > self.HISTORY_LENGTH:
            _ = self.historic_values.takeItem(0)
