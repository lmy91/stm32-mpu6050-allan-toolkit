"""Decode MPU6050 raw logger CSV into physical units and plot seven channels.

The full-rate converted CSV keeps every valid input row. Plotting uses block
means so multi-hour recordings remain readable and do not exhaust memory.
"""

from __future__ import annotations

import argparse
import pathlib

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TOOLS_DIR = pathlib.Path(__file__).resolve().parent
DATA_DIR = TOOLS_DIR.parent / "data"
G0 = 9.80665
ACCEL_SCALE = G0 / 16384.0       # m/s^2 per LSB at +/-2 g
GYRO_SCALE = 3600.0 / 131.0      # deg/h per LSB at +/-250 deg/s

INPUT_COLUMNS = [
    "sample", "time_ms", "dt_ms",
    "ax_raw", "ay_raw", "az_raw", "temp_raw",
    "gx_raw", "gy_raw", "gz_raw",
]

OUTPUT_COLUMNS = [
    "sample", "time_s", "dt_s",
    "ax_m_s2", "ay_m_s2", "az_m_s2", "temp_deg_c",
    "gx_deg_h", "gy_deg_h", "gz_deg_h",
]

INPUT_DTYPES = {
    "sample": "int64",
    "time_ms": "int64",
    "dt_ms": "int32",
    "ax_raw": "int16",
    "ay_raw": "int16",
    "az_raw": "int16",
    "temp_raw": "int16",
    "gx_raw": "int16",
    "gy_raw": "int16",
    "gz_raw": "int16",
}


class BlockMeanCollector:
    """Collect fixed-row block means across arbitrary input chunk boundaries."""

    def __init__(self, block_rows: int) -> None:
        self.block_rows = block_rows
        self.leftover = np.empty((0, 8), dtype=np.float64)
        self.blocks: list[np.ndarray] = []

    def add(self, values: np.ndarray) -> None:
        if self.leftover.size:
            values = np.vstack((self.leftover, values))
        usable = values.shape[0] // self.block_rows * self.block_rows
        if usable:
            means = values[:usable].reshape(-1, self.block_rows, values.shape[1]).mean(axis=1)
            self.blocks.append(means)
        self.leftover = values[usable:].copy()

    def finish(self) -> np.ndarray:
        if self.leftover.size:
            self.blocks.append(np.mean(self.leftover, axis=0, keepdims=True))
            self.leftover = np.empty((0, 8), dtype=np.float64)
        if not self.blocks:
            return np.empty((0, 8), dtype=np.float64)
        return np.vstack(self.blocks)


def find_header_line(path: pathlib.Path) -> int:
    with path.open("r", encoding="ascii", errors="replace") as stream:
        for line_number, line in enumerate(stream):
            if line.startswith("sample,time_ms,dt_ms,"):
                return line_number
    raise ValueError("CSV header not found")


def decode_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    if chunk[INPUT_COLUMNS].isnull().any().any():
        raise ValueError("Input contains missing or non-numeric values")

    decoded = pd.DataFrame(index=chunk.index)
    decoded["sample"] = chunk["sample"].astype(np.int64)
    decoded["time_s"] = chunk["time_ms"].to_numpy(dtype=np.float64) / 1000.0
    decoded["dt_s"] = chunk["dt_ms"].to_numpy(dtype=np.float64) / 1000.0
    for axis in "xyz":
        decoded[f"a{axis}_m_s2"] = (
            chunk[f"a{axis}_raw"].to_numpy(dtype=np.float64) * ACCEL_SCALE
        )
    decoded["temp_deg_c"] = (
        chunk["temp_raw"].to_numpy(dtype=np.float64) / 340.0 + 36.53
    )
    for axis in "xyz":
        decoded[f"g{axis}_deg_h"] = (
            chunk[f"g{axis}_raw"].to_numpy(dtype=np.float64) * GYRO_SCALE
        )
    return decoded[OUTPUT_COLUMNS]


def plot_matrix(decoded: pd.DataFrame) -> np.ndarray:
    return decoded[
        [
            "time_s",
            "ax_m_s2", "ay_m_s2", "az_m_s2",
            "gx_deg_h", "gy_deg_h", "gz_deg_h",
            "temp_deg_c",
        ]
    ].to_numpy(dtype=np.float64, copy=False)


def plot_channels(path: pathlib.Path, block_means: np.ndarray, block_seconds: float) -> None:
    if block_means.size == 0:
        raise ValueError("No decoded samples available for plotting")

    time_hours = (block_means[:, 0] - block_means[0, 0]) / 3600.0
    channels = [
        (1, "Acceleration X", "m/s^2", "#1f77b4"),
        (2, "Acceleration Y", "m/s^2", "#ff7f0e"),
        (3, "Acceleration Z", "m/s^2", "#2ca02c"),
        (4, "Gyroscope X", "deg/h", "#d62728"),
        (5, "Gyroscope Y", "deg/h", "#9467bd"),
        (6, "Gyroscope Z", "deg/h", "#8c564b"),
        (7, "Temperature", "degC", "#e41a1c"),
    ]

    figure, axes = plt.subplots(7, 1, figsize=(15, 17), sharex=True, constrained_layout=True)
    for axis, (column, title, unit, color) in zip(axes, channels):
        axis.plot(time_hours, block_means[:, column], color=color, linewidth=0.9)
        axis.set_ylabel(unit)
        axis.set_title(title, loc="left", fontsize=10)
        axis.grid(True, alpha=0.30)
    axes[-1].set_xlabel("Time after recording start (h)")
    figure.suptitle(
        f"MPU6050 decoded channels ({block_seconds:g} s block means; full-rate data retained in CSV)",
        fontsize=15,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def print_summary(total_rows: int, first_sample: int, last_sample: int,
                  first_time: float, last_time: float, output_csv: pathlib.Path,
                  plot_path: pathlib.Path) -> None:
    duration = last_time - first_time
    expected_rows = last_sample - first_sample + 1
    print(f"Decoded rows: {total_rows:,}")
    print(f"Duration: {duration / 3600.0:.3f} h")
    print(f"Sample range: {first_sample} .. {last_sample}")
    print(f"Sequence row difference: {expected_rows - total_rows}")
    print(f"Converted CSV: {output_csv.resolve()}")
    print(f"Seven-channel plot: {plot_path.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=pathlib.Path, help="Raw MPU6050 logger CSV")
    parser.add_argument("--output-csv", type=pathlib.Path, default=None,
                        help="Full-rate decoded CSV path")
    parser.add_argument("--plot", type=pathlib.Path, default=None,
                        help="Seven-channel PNG path")
    parser.add_argument("--rate", type=float, default=100.0,
                        help="Nominal sample rate used to size plot blocks")
    parser.add_argument("--plot-block-seconds", type=float, default=1.0,
                        help="Seconds averaged into each plotted point")
    parser.add_argument("--chunk-rows", type=int, default=250000,
                        help="Rows decoded per memory chunk")
    args = parser.parse_args()

    if not args.csv.exists():
        raise SystemExit(f"Input CSV not found: {args.csv}")
    if args.rate <= 0.0 or args.plot_block_seconds <= 0.0:
        raise SystemExit("--rate and --plot-block-seconds must be positive")
    if args.chunk_rows < 1000:
        raise SystemExit("--chunk-rows must be at least 1000")

    output_dir = DATA_DIR / "decoded"
    output_csv = args.output_csv or output_dir / f"{args.csv.stem}_physical.csv"
    plot_path = args.plot or output_dir / f"{args.csv.stem}_7channel.png"
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    plot_path.parent.mkdir(parents=True, exist_ok=True)

    header_line = find_header_line(args.csv)
    block_rows = max(1, int(round(args.rate * args.plot_block_seconds)))
    collector = BlockMeanCollector(block_rows)
    total_rows = 0
    first_sample = last_sample = 0
    first_time = last_time = 0.0
    first_chunk = True

    reader = pd.read_csv(
        args.csv,
        delimiter=",",
        comment="#",
        skiprows=header_line,
        usecols=INPUT_COLUMNS,
        dtype=INPUT_DTYPES,
        chunksize=args.chunk_rows,
        on_bad_lines="error",
    )

    for chunk_number, chunk in enumerate(reader, start=1):
        decoded = decode_chunk(chunk)
        if first_chunk:
            first_sample = int(decoded["sample"].iloc[0])
            first_time = float(decoded["time_s"].iloc[0])
        last_sample = int(decoded["sample"].iloc[-1])
        last_time = float(decoded["time_s"].iloc[-1])

        decoded.to_csv(
            output_csv,
            mode="w" if first_chunk else "a",
            header=first_chunk,
            index=False,
            encoding="utf-8",
            float_format="%.9g",
        )
        collector.add(plot_matrix(decoded))
        total_rows += decoded.shape[0]
        first_chunk = False
        print(f"Chunk {chunk_number}: total {total_rows:,} rows", flush=True)

    if first_chunk:
        raise SystemExit("No valid data rows found")

    means = collector.finish()
    plot_channels(plot_path, means, args.plot_block_seconds)
    print_summary(
        total_rows, first_sample, last_sample, first_time, last_time,
        output_csv, plot_path,
    )


if __name__ == "__main__":
    main()
