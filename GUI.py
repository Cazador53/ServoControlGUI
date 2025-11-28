from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QMainWindow, QLineEdit
from PyQt5.QtCore import QTimer, QDateTime
import pyqtgraph as pg
from typing import Optional, Union
import numpy as np

import queue
import time
from serialCon import ArduinoConnection



class MainWindow(QMainWindow):
    def __init__(self, connection):
        super().__init__()
        self.arduino = connection

        # Central widget + layouts
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)

        self.plot_graph = pg.PlotWidget()
        vbox.addWidget(self.plot_graph)
        self.plot_graph.setBackground("black")
        fuelServo = pg.mkPen(color=(255, 0, 0))
        oxServo = pg.mkPen(color=(0, 255, 0))

        self.plot_graph.setTitle("Servo Movement", color="w", size="20pt")
        styles = {"color": "white", "font-size": "18px"}
        self.plot_graph.setLabel("left", "Position (°)", **styles)
        self.plot_graph.setLabel("bottom", "Time (ms)", **styles)

        self.plot_graph.addLegend()
        self.plot_graph.showGrid(x=True, y=True)
        self.plot_graph.setYRange(0, 90)
        self.fuelCurve = self.plot_graph.plot([], [], pen=fuelServo, name="Fuel Valve")
        self.oxCurve = self.plot_graph.plot([], [], pen=oxServo, name="Ox Valve")



        self.start_ms: Optional[float] = None
        self.data_time = []
        self.fuel_pos = []
        self.ox_pos = []

        self.timer = QTimer()
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.update_graph)
        self.timer.start()

        self.cycle_ox = QPushButton("Cycle Ox")
        self.cycle_fuel = QPushButton("Cycle Fuel")
        self.ignseq = QPushButton("Ignition Sequence")
        self.increment = QPushButton("increment")

        self.ignseq.setEnabled(False)

        self.cycle_ox.clicked.connect(lambda: self.arduino.send("cycleoxvalve 2"))
        self.cycle_fuel.clicked.connect(lambda: self.arduino.send("cyclefuelvalve 2"))
        self.ignseq.clicked.connect(lambda: self.arduino.send("ignseq 15"))
        self.increment.clicked.connect(lambda: self.arduino.send("incrementopen"))


        # Create a horizontal layout for buttons
        button_layout = QHBoxLayout()
        vbox.addLayout(button_layout)

        button_layout.addWidget(self.cycle_ox)
        button_layout.addWidget(self.cycle_fuel)
        button_layout.addWidget(self.ignseq)
        button_layout.addWidget(self.increment)

        self.line_edit = QLineEdit(self)
        self.line_edit.setPlaceholderText("Enter text here...")
        button_layout.addWidget(self.line_edit)

        self.line_edit.returnPressed.connect(self.return_pressed)

    def return_pressed(self):
        command = self.line_edit.text().strip()

        if command == "6969": self.ignseq.setEnabled(True)

        if not command:
            return

        if not command.endswith("\n"):
            command += "\n"

        self.arduino.send(command)

        self.line_edit.clear()

    # python
    import numpy as np
    import queue

    def update_graph(self):
        """Drain queue (non-blocking), keep full history, but decimate for plotting."""
        updated = False
        while True:
            try:
                raw = self.arduino.reader_queue.get_nowait()
            except queue.Empty:
                break

            if not raw:
                continue

            try:
                ox_pos_str, fuel_pos_str = raw.strip().split()
                ox_pos = int(ox_pos_str)
                fuel_pos = int(fuel_pos_str)
            except Exception:
                continue

            # compute monotonic timestamp in milliseconds
            now_ms = time.perf_counter() * 1000.0
            if self.start_ms is None:
                self.start_ms = now_ms
            elapsed_ms = now_ms - self.start_ms

            # record every sample (never delete)
            self.data_time.append(elapsed_ms)
            self.fuel_pos.append(fuel_pos)
            self.ox_pos.append(ox_pos)
            updated = True

        if not updated:
            return

        # Limit how many points we actually draw to keep UI responsive
        TARGET_DRAW_POINTS = 2000  # tune this (lower = less CPU)
        n = len(self.data_time)
        if n <= TARGET_DRAW_POINTS:
            # small enough — draw everything
            x = np.array(self.data_time)
            y_fuel = np.array(self.fuel_pos)
            y_ox = np.array(self.ox_pos)
        else:
            step = max(1, n // TARGET_DRAW_POINTS)
            # simple decimation by slicing; for better fidelity use min/max downsampling per bin
            x = np.array(self.data_time[::step])
            y_fuel = np.array(self.fuel_pos[::step])
            y_ox = np.array(self.ox_pos[::step])

        # update plots with decimated arrays (pyqtgraph accepts numpy arrays)
        self.fuelCurve.setData(x, y_fuel)
        self.oxCurve.setData(x, y_ox)