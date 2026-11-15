"""Reset the ESP32-CAM via RTS and capture its serial log for a fixed time."""
import argparse
import time

import serial

parser = argparse.ArgumentParser()
parser.add_argument("--port", default="COM49")
parser.add_argument("--baud", type=int, default=115200)
parser.add_argument("--seconds", type=float, default=30)
parser.add_argument("--out", default="esphome/serial.log")
args = parser.parse_args()

ser = serial.Serial()
ser.port = args.port
ser.baudrate = args.baud
ser.timeout = 0.2
# Keep IO0 (DTR) high so the board boots the app, not the ROM bootloader.
ser.dtr = False
ser.rts = False
ser.open()

ser.rts = True
time.sleep(0.1)
ser.rts = False

end = time.time() + args.seconds
with open(args.out, "wb") as f:
    while time.time() < end:
        f.write(ser.read(4096))
ser.close()
