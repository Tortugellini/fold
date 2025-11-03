from PyQt6 import QtWidgets
from constants import Mode

class Sidebar(QtWidgets.QFrame):
    def __init__(self, dev_mode: bool, parent=None):
        super().__init__(parent)
        self.dev_mode = dev_mode
        self.setMinimumWidth(200)
        self.setStyleSheet(
            "QFrame{background-color:#1e1e1e;border-right:1px solid #333;}"
            "QLabel{color:#ddd;}"
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Mode buttons
        self.mode_group = QtWidgets.QButtonGroup(self)
        button_style = (
            "QPushButton{border:1px solid #555;border-radius:4px;"
            "padding:6px 0;background-color:#333;color:white;}"
            "QPushButton:checked{background-color:#00e676;color:black;}"
        )
        buttons = []
        if dev_mode:
            self.test_btn = QtWidgets.QPushButton(Mode.TEST)
            buttons.append(self.test_btn)
        self.serial_btn = QtWidgets.QPushButton(Mode.SERIAL)
        self.tcp_btn = QtWidgets.QPushButton(Mode.TCP)
        buttons.extend([self.serial_btn, self.tcp_btn])
        for i, b in enumerate(buttons):
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setStyleSheet(button_style)
            self.mode_group.addButton(b, i)
            layout.addWidget(b)
        buttons[0].setChecked(True)

        layout.addSpacing(8)
        layout.addWidget(QtWidgets.QLabel("Connection"))
        self.port_edit = QtWidgets.QLineEdit(placeholderText="COM5 / ttyUSB0")
        self.baud_edit = QtWidgets.QLineEdit(placeholderText="115200")
        self.host_edit = QtWidgets.QLineEdit(placeholderText="192.168.4.1")
        self.tcpport_edit = QtWidgets.QLineEdit(placeholderText="1234")
        for w in (self.port_edit, self.baud_edit, self.host_edit, self.tcpport_edit):
            w.setStyleSheet("background:#222;color:#eee;border:1px solid #444;padding:4px;")
            layout.addWidget(w)

        layout.addSpacing(8)
        self.start_btn = QtWidgets.QPushButton("Start")
        self.stop_btn = QtWidgets.QPushButton("Stop")
        for b in (self.start_btn, self.stop_btn):
            b.setStyleSheet("padding:6px;background-color:#555;color:white;")
            layout.addWidget(b)
        layout.addStretch(1)
        self.status_lbl = QtWidgets.QLabel("Idle")
        self.status_lbl.setStyleSheet("color:#aaa;")
        layout.addWidget(self.status_lbl)
