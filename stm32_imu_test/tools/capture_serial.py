"""Capture MPU6050 Allan logger output without losing long-duration data."""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import time

import serial


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", help="Serial port, for example COM3")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--hours", type=float, default=0.0,
                        help="Stop after this many hours; 0 means until Ctrl+C")
    parser.add_argument("--output", type=pathlib.Path,
                        help="Output CSV path (default: timestamped file in data/)")
    args = parser.parse_args()

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output = args.output or pathlib.Path("data") / f"mpu6050_static_{stamp}.csv"
    output.parent.mkdir(parents=True, exist_ok=True)

    deadline = time.monotonic() + args.hours * 3600.0 if args.hours > 0 else None
    rows = 0
    started = time.monotonic()

    print(f"Capturing {args.port} at {args.baud} baud -> {output.resolve()}")
    print("Keep the IMU completely still. Press Ctrl+C to stop safely.")

    with serial.Serial(args.port, args.baud, timeout=1) as port, output.open(
        "w", encoding="ascii", newline=""
    ) as stream:
        port.reset_input_buffer()
        # Always emit exactly one CSV header. This makes a capture valid even
        # when it starts while the MCU is already streaming and its boot header
        # has long since passed.
        csv_header = (
            "sample,time_ms,dt_ms,ax_raw,ay_raw,az_raw,temp_raw,"
            "gx_raw,gy_raw,gz_raw"
        )
        stream.write(csv_header + "\n")
        stream.write("# captured_by=capture_serial.py\n")
        try:
            while deadline is None or time.monotonic() < deadline:
                raw = port.readline()
                if not raw:
                    continue
                line = raw.decode("ascii", errors="replace").strip()
                if not line:
                    continue
                if line == csv_header:
                    continue
                if line.startswith("#"):
                    stream.write(line + "\n")
                    continue
                if line[0].isdigit() and len(line.split(",")) == 10:
                    stream.write(line + "\n")
                    rows += 1
                if rows and rows % 1000 == 0:
                    stream.flush()
                    elapsed = time.monotonic() - started
                    print(f"{rows} samples, {elapsed / 60:.1f} min", end="\r")
        except KeyboardInterrupt:
            pass
        finally:
            stream.flush()

    elapsed = time.monotonic() - started
    print(f"\nSaved {rows} samples ({elapsed / 3600:.3f} h) to {output.resolve()}")


if __name__ == "__main__":
    main()
