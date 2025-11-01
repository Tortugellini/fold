from PyQt6 import QtWidgets


class StatusLED(QtWidgets.QFrame):
    """Small circular LED indicator with color control."""

    def __init__(self, size: int = 14, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.set_color("#444")

    def set_color(self, color):
        # ensure Qt gets a plain string, even if Enum or QColor is passed
        color_str = str(color)
        self.setStyleSheet(
            f"background-color:{color_str}; border-radius:{self._size//2}px; "
            "border:1px solid #111;"
        )
