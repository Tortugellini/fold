from PyQt6 import QtWidgets
import pyqtgraph as pg
from constants import Color


class PlotView(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.plot = pg.PlotWidget()
        self.plot.setLabel("left", "Amplitude")
        self.plot.setLabel("bottom", "Samples")
        self.curve = self.plot.plot(pen=pg.mkPen(Color.RUNNING, width=2))
        self.plot.showGrid(x=True, y=True, alpha=0.3)

        vb = self.plot.getViewBox()
        vb.setMouseMode(pg.ViewBox.RectMode)

        self.plot.scene().sigMouseClicked.connect(self._on_plot_click)

        layout.addWidget(self.plot, stretch=1)

        metrics = QtWidgets.QHBoxLayout()
        mono = "font-family:'Courier New', monospace;"
        self.mean_lbl = QtWidgets.QLabel("Mean: ---")
        self.rms_lbl = QtWidgets.QLabel("RMS: ---")
        self.fps_lbl = QtWidgets.QLabel("Feed: --- Hz")
        for lbl in (self.mean_lbl, self.rms_lbl, self.fps_lbl):
            lbl.setStyleSheet(f"color:black;font-size:13px;{mono}")
            metrics.addWidget(lbl)
            metrics.addSpacing(20)
        metrics.addStretch(1)
        layout.addLayout(metrics)

    def _on_plot_click(self, event):
        if event.double():
            self.plot.getPlotItem().autoBtnClicked()
