import random
import time
import serial  # PySerial


class DataSource:
    def __init__(self, mode="MOCK", port="COM3"):
        self.mode = mode
        self.port = port
        self.bluetooth = None

        if self.mode == "LIVE":
            try:
                self.bluetooth = serial.Serial(self.port, 9600, timeout=1)
            except:
                print(f"[ERROR] Could not open {self.port}. Switching to MOCK.")
                self.mode = "MOCK"

    def get_reading(self):
        """Returns tuple: (FlowRate, LeakFlag, TankLevel)"""
        if self.mode == "MOCK":
            # Simulate slight fluctuations
            flow = round(random.uniform(2.0, 2.5), 2)
            leak = 0

            # Logic for mock tank depletion
            if not hasattr(self, 'mock_tank'): self.mock_tank = 100
            self.mock_tank -= 0.2
            if self.mock_tank <= 0: self.mock_tank = 100

            if random.random() > 0.95:
                flow = 8.0
                leak = 1
            return flow, leak, int(self.mock_tank)

        elif self.mode == "LIVE":
            if self.bluetooth and self.bluetooth.in_waiting:
                try:
                    line = self.bluetooth.readline().decode().strip()
                    parts = line.split(',')
                    # Expecting: "Flow,LeakFlag,Level"
                    return float(parts[0]), int(parts[1]), int(parts[2])
                except Exception as e:
                    print(f"Data Parse Error: {e}")
                    return 0.0, 0, 0
            return None

    def send_command(self, command):
        """Sends a command string to the ESP32 (e.g., 'STOP', 'ECO')"""
        if self.mode == "LIVE" and self.bluetooth:
            try:
                # Send command with newline \n so ESP32 knows it's finished
                self.bluetooth.write(f"{command}\n".encode())
                print(f"[TX] Sent: {command}")
                return True
            except Exception as e:
                print(f"[TX FAILED] {e}")
                return False
        else:
            print(f"[MOCK TX] Simulated sending: {command}")
            return True