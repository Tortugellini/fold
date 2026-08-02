from PyQt6 import QtWidgets


class StatusLED(QtWidgets.QFrame):
    """Small circular LED indicator with color control."""

    def __init__(self, size: int = 14, parent=None):
        super().__init__(parent)
        self._size = size
        self.setObjectName("StatusLED")
        self.setFixedSize(size, size)

        self.set_color("default")

    def set_color(self, state: str):
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
