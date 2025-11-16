from PyQt6 import QtWidgets
from constants import Mode


class Sidepanel(QtWidgets.QFrame):
    def __init__(self, dev_mode: bool, parent=None):
        super().__init__(parent)
        self.dev_mode = dev_mode
        self.setObjectName("sidepanel")

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(10)

        # Mode buttons
        self.mode_group = QtWidgets.QButtonGroup(self)
        self.buttons = []
        if dev_mode:
            self.test_btn = QtWidgets.QPushButton(Mode.TEST)
            self.test_btn.setObjectName("modeButton")
            self.buttons.append(self.test_btn)

        self.udp_btn = QtWidgets.QPushButton(Mode.UDP)
        self.udp_btn.setObjectName("modeButton")
        self.buttons.append(self.udp_btn)

        for i, b in enumerate(self.buttons):
            b.setCheckable(True)
            b.setAutoExclusive(True)
            self.mode_group.addButton(b, i)
            self.layout.addWidget(b)

        self.layout.addSpacing(8)

        self.host_edit = QtWidgets.QLineEdit(placeholderText="192.168.4.1")
        self.udpport_edit = QtWidgets.QLineEdit(placeholderText="1234")

        for w in (self.host_edit, self.udpport_edit):
            w.setObjectName("connField")
            self.layout.addWidget(w)

        self.layout.addSpacing(8)
        self.listen_btn = QtWidgets.QPushButton("Listen")
        self.listen_btn.setObjectName("controlButton")
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.setObjectName("controlButton")

        for b in (self.listen_btn, self.stop_btn):
            self.layout.addWidget(b)

        self.layout.addStretch(1)
        self.status_lbl = QtWidgets.QLabel("Idle")
        self.status_lbl.setObjectName("statusLabel")
        self.layout.addWidget(self.status_lbl)
