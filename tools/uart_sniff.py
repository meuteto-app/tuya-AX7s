#!/usr/bin/env python3
"""Listen to the indoor unit's debug UART (header J1) through the FT232.

Two modes:
  probe    try common baud rates for a few seconds each and rank them by how
           much of what arrives is readable text
  capture  log every line with a timestamp to the screen and to a file, so
           button presses can be matched to log lines

Only listens: the FT232 TX pin stays disconnected, nothing is sent.

Usage:
  uvx --with pyserial python source/tools/uart_sniff.py probe
  uvx --with pyserial python source/tools/uart_sniff.py capture --baud 115200
"""
import argparse
import datetime
import sys
import time

import serial

BAUDS = [115200, 921600, 1500000, 57600, 38400, 19200, 9600, 230400, 460800, 2000000]


def readable_ratio(data: bytes) -> float:
    if not data:
        return 0.0
    ok = sum(1 for b in data if 32 <= b < 127 or b in (9, 10, 13))
    return ok / len(data)


def probe(port: str, seconds: float) -> None:
    print(f"Probing {port}: power-cycle the indoor unit now, or press its buttons while this runs.")
    results = []
    for baud in BAUDS:
        with serial.Serial(port, baud, timeout=0.2) as s:
            s.reset_input_buffer()
            end = time.time() + seconds
            data = b""
            while time.time() < end:
                data += s.read(4096)
        ratio = readable_ratio(data)
        results.append((ratio, len(data), baud, data[:160]))
        print(f"{baud:>8} baud: {len(data):>6} bytes, {ratio:5.0%} readable")
    results.sort(reverse=True)
    best = results[0]
    print()
    if best[1] == 0:
        print("Nothing arrived at any speed. Check GND and that FT232 RX is on the board's TX pin.")
    else:
        print(f"Best guess: {best[2]} baud. Sample:\n{best[3]!r}")


def capture(port: str, baud: int, out: str) -> None:
    print(f"Capturing {port} @ {baud} into {out} (Ctrl+C to stop)")
    with serial.Serial(port, baud, timeout=0.5) as s, open(out, "a", encoding="utf-8") as f:
        buf = b""
        while True:
            buf += s.read(4096)
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.rstrip(b"\r").decode("utf-8", "replace")
                stamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"{stamp} {line}", flush=True)
                f.write(f"{stamp} {line}\n")
                f.flush()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["probe", "capture"])
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seconds", type=float, default=4.0)
    ap.add_argument("--out", default="uart-capture.log")
    args = ap.parse_args()
    try:
        if args.mode == "probe":
            probe(args.port, args.seconds)
        else:
            capture(args.port, args.baud, args.out)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
