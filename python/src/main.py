import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dev_mode = "--dev" in sys.argv
    win = MainWindow(dev_mode=dev_mode)
    win.show()
    sys.exit(app.exec())
