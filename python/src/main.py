import click

from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow


@click.command()
@click.option(
    "--dev",
    is_flag=True,
    help="Run in developer mode (enables test mode and extra debugging features).",
)
def main(dev):
    app = QApplication([])
    dev_mode = bool(dev)

    # Load QSS stylesheet
    with open("ui/styles.qss", "r") as f:
        app.setStyleSheet(f.read())

    win = MainWindow(dev_mode=dev_mode)
    win.show()
    app.exec()


if __name__ == "__main__":
    main()
