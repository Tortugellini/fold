import sys
from PyQt6 import QtCore, QtWidgets
from ui import MainWindow

def main() -> None:
    # High-DPI and modern behavior
    app = QtWidgets.QApplication(sys.argv)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
