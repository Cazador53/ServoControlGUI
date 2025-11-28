from pathlib import Path
import sys
from serial.tools import list_ports
from serialCon import ArduinoConnection
from GUI import MainWindow
from PyQt5.QtWidgets import QApplication

def find_port(preferred: str | None = None) -> str | None:
    if preferred:
        return preferred
    ports = list_ports.comports()
    # prefer mac usb modem / usb serial / arduino descriptions
    for p in ports:
        dev = p.device or ""
        desc = (p.description or "").lower()
        if "usbmodem" in dev or "usbmodem" in desc or "usbserial" in dev or "usbserial" in desc or "arduino" in desc or "cu.usb" in dev:
            return dev
    # fallback to first available
    if ports:
        return ports[0].device
    return None

def main():
    # remove existing CSV so runs don't merge
    csv_path = Path("ServoData.csv")
    if csv_path.exists():
        try:
            csv_path.unlink()
            print(f"Removed existing `{csv_path}`")
        except Exception as exc:
            print(f"Failed to remove `{csv_path}`: {exc}")

    port_arg = sys.argv[1] if len(sys.argv) > 1 else None
    port = find_port(port_arg)
    if not port:
        print("No serial ports found. Plug in the Arduino or run: ls /dev/cu.*")
        return

    print("Using serial port:", port)
    connection = ArduinoConnection(port)

    try:
        connection.connect()
    except Exception as exc:
        print("Serial connect failed:", exc)

    app = QApplication(sys.argv)
    win = MainWindow(connection)
    win.show()


    try:
        exit_code = app.exec_()
    finally:
        try:
            if getattr(connection, "stop_event", None):
                connection.stop_event.set()
        except Exception:
            pass

        try:
            rt = getattr(connection, "reader_thread", None)
            wt = getattr(connection, "writer_thread", None)
            if rt and rt.is_alive():
                rt.join(timeout=1)
            if wt and wt.is_alive():
                wt.join(timeout=1)
            ser = getattr(connection, "arduino", None)
            if ser:
                ser.close()
        except Exception as exc:
            print("Cleanup error:", exc)

    sys.exit(exit_code)

if __name__ == "__main__":
    main()