# python
# file: `serialCon.py`
import threading
import serial
import time
import queue
from typing import Optional, Union
import csv

class ArduinoConnection:
    def __init__(self, port: str, baud: int = 115200, timeout: float = 0.5, debug: bool = False):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.debug = debug

        self.arduino: Optional[serial.Serial] = None
        self.reader_queue: "queue.Queue[str]" = queue.Queue()
        self.writer_queue: "queue.Queue[Union[bytes, str]]" = queue.Queue()

        self.reader_thread: Optional[threading.Thread] = None
        self.writer_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        self.last_log_time = time.time()
        self.csv_file = open("ServoData.csv", "a", newline="")
        self.csv_writer = csv.writer(self.csv_file)

    def connect(self):
        if self.arduino and getattr(self.arduino, "is_open", False):
            return
        try:
            self.arduino = serial.Serial(self.port, self.baud, timeout=self.timeout, write_timeout=0.1)
        except serial.SerialException as exc:
            raise RuntimeError(f"Failed to open {self.port}: {exc}") from exc

        self.stop_event.clear()
        # start threads with correct targets
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self.reader_thread.start()
        self.writer_thread.start()

    def disconnect(self):
        if not self.arduino:
            return
        # signal stop and join threads
        self.stop_event.set()
        if self.reader_thread:
            self.reader_thread.join(timeout=1)
        if self.writer_thread:
            self.writer_thread.join(timeout=1)
        try:
            self.arduino.close()
        except Exception:
            pass
        self.arduino = None

    def _reader_loop(self):
        while not self.stop_event.is_set():
            raw = self.arduino.readline()
            if not raw:
                continue

            line = raw.decode("utf-8", errors="ignore").strip()

            if line:

                self.reader_queue.put(line)

                # Throttle CSV writing ONLY
                now = time.time()
                if now - self.last_log_time >= 0.02:
                    self.last_log_time = now
                    self.csv_writer.writerow(line.split())
                    self.csv_file.flush()

    def _writer_loop(self):
        while not self.stop_event.is_set():
            try:
                data = self.writer_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            self.arduino.write(data.encode())

    def send(self, data: Union[bytes, str]):
        self.writer_queue.put(data)