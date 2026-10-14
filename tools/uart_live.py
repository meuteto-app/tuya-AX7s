import serial, time, datetime, sys
port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
out = sys.argv[3] if len(sys.argv) > 3 else "uart-live.log"
s = serial.Serial(port, baud, timeout=0.5)
with open(out, "a") as f:
    f.write(f"--- open {port} @ {baud} {datetime.datetime.now()}\n"); f.flush()
    while True:
        d = s.read(4096)
        if d:
            line = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3] + " " + repr(d)
            print(line, flush=True)
            f.write(line + "\n"); f.flush()
