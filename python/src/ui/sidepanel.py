from PyQt6 import QtWidgets
from constants import Mode


class Sidepanel(QtWidgets.QFrame):
    def __init__(self, dev_mode: bool, parent=None):
        super().__init__(parent)
        self.dev_mode = dev_mode
        self.setObjectName("sidepanel")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Mode buttons
        self.mode_group = QtWidgets.QButtonGroup(self)
        self.buttons = []
        if dev_mode:
            self.test_btn = QtWidgets.QPushButton(Mode.TEST)
            self.test_btn.setObjectName("modeButton")
            self.buttons.append(self.test_btn)

        self.serial_btn = QtWidgets.QPushButton(Mode.SERIAL)
        self.serial_btn.setObjectName("modeButton")
        self.tcp_btn = QtWidgets.QPushButton(Mode.TCP)
        self.tcp_btn.setObjectName("modeButton")
        self.buttons.extend([self.serial_btn, self.tcp_btn])

        for i, b in enumerate(self.buttons):
            b.setCheckable(True)
            b.setAutoExclusive(True)
            self.mode_group.addButton(b, i)
            layout.addWidget(b)
        self.buttons[0].setChecked(True)

        layout.addSpacing(8)
        conn_label = QtWidgets.QLabel("Connection")
        conn_label.setObjectName("sectionLabel")
        layout.addWidget(conn_label)

        self.port_edit = QtWidgets.QLineEdit(placeholderText="COM5 / ttyUSB0")
        self.baud_edit = QtWidgets.QLineEdit(placeholderText="115200")
        self.host_edit = QtWidgets.QLineEdit(placeholderText="192.168.4.1")
        self.tcpport_edit = QtWidgets.QLineEdit(placeholderText="1234")

        for w in (self.port_edit, self.baud_edit, self.host_edit, self.tcpport_edit):
            w.setObjectName("connField")
            layout.addWidget(w)

        layout.addSpacing(8)
        self.start_btn = QtWidgets.QPushButton("Start")
        self.start_btn.setObjectName("controlButton")
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.setObjectName("controlButton")

        for b in (self.start_btn, self.stop_btn):
            layout.addWidget(b)

        layout.addStretch(1)
        self.status_lbl = QtWidgets.QLabel("Idle")
        self.status_lbl.setObjectName("statusLabel")
        layout.addWidget(self.status_lbl)
