"""Capture MPU6050 serial data and convert it to physical units online.

The primary output is written directly in the 10-column physical-unit format
accepted by ``allan_noise_identification.py``.  Raw integer rows can optionally
be retained with ``--raw-output``.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import pathlib
import time

import serial


TOOLS_DIR = pathlib.Path(__file__).resolve().parent
DATA_DIR = TOOLS_DIR.parent / "data"
G0 = 9.80665
ACCEL_SCALE = G0 / 16384.0       # m/s^2 per LSB at +/-2 g
GYRO_SCALE = 3600.0 / 131.0      # deg/h per LSB at +/-250 deg/s

RAW_HEADER = (
    "sample,time_ms,dt_ms,ax_raw,ay_raw,az_raw,temp_raw,"
    "gx_raw,gy_raw,gz_raw"
)
PHYSICAL_COLUMNS = [
    "sample", "time_s", "dt_s",
    "ax_m_s2", "ay_m_s2", "az_m_s2", "temp_deg_c",
    "gx_deg_h", "gy_deg_h", "gz_deg_h",
]


def parse_raw_row(line: str) -> tuple[int, ...] | None:
    """Return one validated 10-integer firmware row, or ``None``."""
    try:
        fields = next(csv.reader([line]))
        if len(fields) != 10:
            return None
        return tuple(int(field.strip()) for field in fields)
    except (ValueError, csv.Error):
        return None


def decode_raw_row(raw: tuple[int, ...]) -> tuple[int | float, ...]:
    """Convert one firmware row to the project's physical-unit CSV format."""
    sample, time_ms, dt_ms, ax, ay, az, temperature, gx, gy, gz = raw
    return (
        sample,
        time_ms / 1000.0,
        dt_ms / 1000.0,
        ax * ACCEL_SCALE,
        ay * ACCEL_SCALE,
        az * ACCEL_SCALE,
        temperature / 340.0 + 36.53,
        gx * GYRO_SCALE,
        gy * GYRO_SCALE,
        gz * GYRO_SCALE,
    )


def format_physical_row(values: tuple[int | float, ...]) -> list[str]:
    """Format floats consistently with the existing offline decoder."""
    return [str(values[0]), *(format(value, ".9g") for value in values[1:])]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", help="Serial port, for example COM3")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--hours", type=float, default=0.0,
                        help="Stop after this many hours; 0 means until Ctrl+C")
    parser.add_argument("--output", type=pathlib.Path,
                        help="Physical CSV path (default: timestamped file in data/decoded/)")
    parser.add_argument("--raw-output", type=pathlib.Path,
                        help="Optional path for retaining the original raw-count CSV")
    args = parser.parse_args()

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output = args.output or (
        DATA_DIR / "decoded" / f"mpu6050_static_{stamp}_physical.csv"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.raw_output:
        args.raw_output.parent.mkdir(parents=True, exist_ok=True)
        if args.raw_output.resolve() == output.resolve():
            raise SystemExit("--raw-output must be different from --output")

    deadline = time.monotonic() + args.hours * 3600.0 if args.hours > 0 else None
    rows = 0
    invalid_lines = 0
    lost_frames = 0
    previous_sample: int | None = None
    started = time.monotonic()

    print(f"Capturing {args.port} at {args.baud} baud")
    print(f"Physical CSV -> {output.resolve()}")
    if args.raw_output:
        print(f"Raw CSV      -> {args.raw_output.resolve()}")
    print("Keep the IMU completely still. Press Ctrl+C to stop safely.")

    raw_stream = None
    try:
        if args.raw_output:
            raw_stream = args.raw_output.open("w", encoding="ascii", newline="")

        with serial.Serial(args.port, args.baud, timeout=1) as port, output.open(
            "w", encoding="ascii", newline=""
        ) as stream:
            writer = csv.writer(stream, lineterminator="\n")
            raw_writer = csv.writer(raw_stream, lineterminator="\n") if raw_stream else None

            port.reset_input_buffer()
            writer.writerow(PHYSICAL_COLUMNS)
            stream.write("# captured_and_decoded_by=capture_serial.py\n")
            stream.write("# accel_range=+/-2g,gyro_range=+/-250deg/s\n")
            if raw_writer:
                raw_stream.write(RAW_HEADER + "\n")
                raw_stream.write("# captured_by=capture_serial.py\n")

            try:
                while deadline is None or time.monotonic() < deadline:
                    serial_bytes = port.readline()
                    if not serial_bytes:
                        continue
                    line = serial_bytes.decode("ascii", errors="replace").strip()
                    if not line or line == RAW_HEADER:
                        continue
                    if line.startswith("#"):
                        continue

                    raw = parse_raw_row(line)
                    if raw is None:
                        invalid_lines += 1
                        continue

                    sample = raw[0]
                    if previous_sample is not None and sample > previous_sample + 1:
                        lost_frames += sample - previous_sample - 1
                    previous_sample = sample

                    writer.writerow(format_physical_row(decode_raw_row(raw)))
                    if raw_writer:
                        raw_writer.writerow(raw)
                    rows += 1

                    if rows % 1000 == 0:
                        stream.flush()
                        if raw_stream:
                            raw_stream.flush()
                        elapsed = time.monotonic() - started
                        print(
                            f"{rows:,} samples, lost {lost_frames:,}, "
                            f"invalid {invalid_lines:,}, {elapsed / 60:.1f} min",
                            end="\r",
                        )
            except KeyboardInterrupt:
                pass
            finally:
                stream.flush()
                if raw_stream:
                    raw_stream.flush()
    finally:
        if raw_stream:
            raw_stream.close()

    elapsed = time.monotonic() - started
    print(f"\nSaved {rows:,} decoded samples ({elapsed / 3600:.3f} h)")
    print(f"Lost frames: {lost_frames:,}; invalid lines: {invalid_lines:,}")
    print(f"Physical CSV: {output.resolve()}")
    if args.raw_output:
        print(f"Raw CSV: {args.raw_output.resolve()}")


if __name__ == "__main__":
    main()
