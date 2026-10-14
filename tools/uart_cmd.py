import serial, time, sys
port="/dev/ttyUSB0"; baud=115200
cmd = sys.argv[1] if len(sys.argv) > 1 else ""
wait = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
s = serial.Serial(port, baud, timeout=0.2)
s.reset_input_buffer()
s.write((cmd + "\r\n").encode()); s.flush()
end = time.time() + wait
buf = b""
while time.time() < end:
    buf += s.read(4096)
txt = buf.decode("utf-8", "replace")
# filtra o ruido pra achar prompt/resposta
import re
for line in txt.splitlines():
    if "sunxi-mmc sdc0" in line: continue
    if "Digbell_key_proc" in line: continue
    if "pwm value" in line: continue
    cl = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
    if cl:
        print("| " + cl)
print("--- (fim, %d bytes brutos)" % len(buf))
