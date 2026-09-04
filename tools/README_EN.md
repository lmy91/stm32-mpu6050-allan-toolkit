# Capture, Decode, and Allan Analysis Tools

[Project home](../README_EN.md) | [中文](README.md) | English

This directory contains data-processing scripts only. Run the commands from the repository root. All experiment files are written below data/, never back into tools/.

## Files

| File | Purpose | Default output |
| --- | --- | --- |
| capture_serial.py | Capture serial frames and convert online | data/decoded/ |
| decode_imu_data.py | Convert legacy raw CSV and plot seven channels | data/decoded/ |
| allan_noise_identification.py | Compute Allan deviation and identify noise terms | data/allan_results/ |

## Install dependencies

    D:\Anaconda3\python.exe -m pip install -r tools\requirements.txt

Any Python 3.10+ interpreter may be used. Display command-line options with:

    D:\Anaconda3\python.exe tools\capture_serial.py --help
    D:\Anaconda3\python.exe tools\decode_imu_data.py --help
    D:\Anaconda3\python.exe tools\allan_noise_identification.py --help

## Data directories

    data\raw\               Optional raw integer frames
    data\decoded\           Physical-unit CSV and seven-channel plots
    data\allan_results\     Allan curves, parameter tables, and reports

Experiment files in these directories are excluded from Git. Only .gitkeep retains the empty directories.

## 1. Capture a physical-unit CSV directly

Verify that USB-TTL is connected and that no Qt monitor or serial terminal owns the port. Capture 12 hours from COM3:

    D:\Anaconda3\python.exe tools\capture_serial.py COM3 --hours 12

The default baud rate is 115200. A timestamped file is created in data/decoded/. Use hours=0 to run until Ctrl+C:

    D:\Anaconda3\python.exe tools\capture_serial.py COM3 --hours 0

Specify the decoded output and optionally retain raw frames:

    D:\Anaconda3\python.exe tools\capture_serial.py COM3 --hours 12 --output data\decoded\static_12h.csv --raw-output data\raw\static_12h_raw.csv

The primary output is already accepted by the Allan tool; do not decode it again.

## 2. Decode an existing raw recording

Use this only for a legacy STM32 raw integer CSV:

    D:\Anaconda3\python.exe tools\decode_imu_data.py data\raw\static_12h_raw.csv

Default outputs:

    data\decoded\static_12h_raw_physical.csv
    data\decoded\static_12h_raw_7channel.png

Custom outputs:

    D:\Anaconda3\python.exe tools\decode_imu_data.py data\raw\static_12h_raw.csv --output-csv data\decoded\static_12h.csv --plot data\decoded\static_12h.png --rate 100

The decoder reads long files in chunks and preserves every valid sample. The plot uses block means so a 12-hour recording does not exhaust memory.

## 3. Identify Allan noise parameters

The input must be a physical-unit CSV:

    D:\Anaconda3\python.exe tools\allan_noise_identification.py data\decoded\static_12h.csv --rate 100 --skip-minutes 30 --points 90

Options:

- --rate: nominal sample rate; the current firmware normally uses 100 Hz.
- --skip-minutes: discard the power-on warm-up period; use 0 to keep it.
- --points: number of logarithmic cluster-time points; minimum 30.
- --output: custom result directory; otherwise data/allan_results/input_name_noise/.

Default result files:

| File | Contents |
| --- | --- |
| allan_deviation.png | Accelerometer and gyroscope Allan overview |
| allan_identification.png | Identified regions and parameter annotations |
| stability_overview.png | Six-axis and temperature time stability |
| allan_parameters.csv | Six-axis stochastic-noise parameters |
| allan_deviation.csv | Allan deviation at each cluster time |
| 随机误差判读报告.md | Data quality, missing frames, temperature, and interpretation |

The script estimates white noise (VRW/ARW), bias instability (BI), random walk (RRW), and rate ramp. It also reports sequence discontinuities and estimated missing frames.

## Input formats

STM32 raw format:

    sample,time_ms,dt_ms,ax_raw,ay_raw,az_raw,temp_raw,gx_raw,gy_raw,gz_raw

Physical-unit/Allan format:

    sample,time_s,dt_s,ax_m_s2,ay_m_s2,az_m_s2,temp_deg_c,gx_deg_h,gy_deg_h,gz_deg_h

Angular rates are stored in deg/h. The Allan script converts them internally to rad/s for estimation.

## Recommendations for long recordings

- Rigidly mount the IMU and avoid vibration, cable motion, and handling.
- Warm up for about 30 minutes before the stable interval used for analysis.
- Control temperature where possible; thermal drift raises the long-tau region.
- A few isolated missing frames are often tolerable, but frequent or consecutive loss violates the uniform-sampling assumption and warrants a new recording.
- To analyze a file still being recorded, analyze a copied snapshot rather than allowing two writers.

## Troubleshooting

- Access denied/port busy: close the Qt monitor and every other serial program.
- CSV header not found: verify that the input uses one of the 10-column formats above.
- Warm-up skip leaves too few samples: reduce --skip-minutes.
- Unknown rate: inspect empirical rate in the report, then rerun with the correct --rate.
- Out of memory: reduce --points and close large applications; decoding already uses chunked input.
