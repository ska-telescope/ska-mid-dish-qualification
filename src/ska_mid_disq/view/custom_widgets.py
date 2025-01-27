"""Custom Qt widgets for DiSQ GUI."""

from typing import Any

from PySide6.QtCore import QLocale, QRect, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import QDoubleSpinBox, QPushButton

from ska_mid_disq.constants import DISPLAY_DECIMAL_PLACES


class LimitedDisplaySpinBox(QDoubleSpinBox):
    """Custom double (float) spin box that only limits the displayed decimal points."""

    def __init__(self, *args, decimals_to_display=DISPLAY_DECIMAL_PLACES, **kwargs):
        """Init LimitedDisplaySpinBox."""
        super().__init__(*args, **kwargs)
        self.decimals_to_display = decimals_to_display
        self.setSingleStep(10**-decimals_to_display)  # Set step to displayed precision

    # pylint: disable=invalid-name,
    def textFromValue(self, value):  # noqa: N802
        """Display the value with limited decimal points."""
        return QLocale().toString(value, "f", self.decimals_to_display)

    # pylint: disable=invalid-name,
    def stepBy(self, steps):  # noqa: N802
        """Override stepBy to round the step value to the displayed decimals."""
        new_value = self.value() + steps * self.singleStep()
        rounded_value = round(new_value, self.decimals_to_display)
        self.setValue(rounded_value)


class ToggleSwitch(QPushButton):
    """Custom sliding style toggle push button."""

    def __init__(self, parent: Any = None) -> None:
        """Init ToggleSwitch."""
        super().__init__(parent)
        self.setCheckable(True)
        self.setMinimumWidth(70)
        self.setMinimumHeight(22)
        self.label_true = "ON"
        self.label_false = "OFF"
        self.change_color = True

    # pylint: disable=invalid-name,unused-argument
    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
        """Override mouseReleaseEvent to disable visual state change on click."""
        self.setChecked(not self.isChecked())  # Toggle state manually
        self.clicked.emit()  # Emit clicked signal for external logic

    # pylint: disable=invalid-name,unused-argument
    def paintEvent(self, event: Any) -> None:  # noqa: N802
        """Paint event."""
        label = self.label_true if self.isChecked() else self.label_false
        radius = 9
        width = 34
        center = self.rect().center()
        painter = QPainter(self)
        palette = super().palette()
        button_color = palette.color(QPalette.ColorRole.Window)
        if self.isEnabled() and self.change_color:
            background_color = QColor("green") if self.isChecked() else QColor("red")
        else:
            background_color = button_color
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.translate(center)
        painter.setBrush(background_color)
        painter.setPen(QPen(palette.color(QPalette.ColorRole.Shadow), 1))
        painter.drawRoundedRect(
            QRect(-width, -radius, 2 * width, 2 * radius),
            radius,
            radius,
        )
        painter.setBrush(QBrush(button_color))
        sw_rect = QRect(-radius, -radius, width + radius, 2 * radius)
        if not self.isChecked():
            sw_rect.moveLeft(-width)
        painter.drawRoundedRect(sw_rect, radius, radius)
        painter.setPen(QPen(palette.color(QPalette.ColorRole.WindowText), 1))
        painter.drawText(sw_rect, Qt.AlignmentFlag.AlignCenter, label)
