# Qt Real-Time Serial Monitor

[Project home](../README_EN.md) | [中文](README.md) | English

This directory contains the desktop application. It receives raw MPU6050 frames from the STM32, converts and plots three-axis acceleration, three-axis angular rate, and temperature. It supports Chinese/English UI text, per-axis selection, lost-frame statistics, and physical-unit CSV recording.

## Install dependencies

Run from the repository root:

    D:\Anaconda3\python.exe -m pip install -r host\requirements.txt

Any Python 3.10+ interpreter may be used. Dependencies include PyQt5, pyqtgraph, pyserial, and NumPy.

## Start

Run from the repository root:

    D:\Anaconda3\python.exe host\imu_serial_qt.py

Alternatively, double-click host/run_imu_serial_qt.bat.

## Operation

1. Verify STM32 PA9→USB-TTL RX and connect the grounds.
2. Plug USB-TTL into the computer and close any serial terminal using the port.
3. Click Refresh and select the corresponding COM port.
4. Select 115200 baud and click Connect.
5. Use the Ax/Ay/Az/Gx/Gy/Gz check boxes to choose plotted axes. Select only one for a single-axis view.
6. Enable Save physical-unit CSV when recording is required. The save dialog defaults to data/decoded/.
7. Click Disconnect before unplugging USB-TTL.

Pause plots stops UI refresh only; reception and enabled recording continue. Clear plots clears the display buffer without deleting saved CSV files.

## Input and output

The input is the STM32 10-column raw integer CSV:

    sample,time_ms,dt_ms,ax_raw,ay_raw,az_raw,temp_raw,gx_raw,gy_raw,gz_raw

Recorded files use the physical-unit format accepted directly by the Allan tool:

    sample,time_s,dt_s,ax_m_s2,ay_m_s2,az_m_s2,temp_deg_c,gx_deg_h,gy_deg_h,gz_deg_h

## Package a Windows EXE

The project uses PyInstaller onedir mode. It loads files directly from the output directory instead of extracting a large onefile archive at every launch.

Create an isolated packaging environment from the repository root:

    D:\Anaconda3\python.exe -m venv .venv-package
    .\.venv-package\Scripts\python.exe -m pip install --upgrade pip
    .\.venv-package\Scripts\python.exe -m pip install -r host\requirements.txt pyinstaller

Build:

    .\.venv-package\Scripts\python.exe -m PyInstaller --noconfirm --clean host\MPU6050_Serial_Monitor.spec

Output:

    dist\MPU6050_Serial_Monitor\MPU6050_Serial_Monitor.exe

Zip and distribute the complete MPU6050_Serial_Monitor directory, not the EXE alone. build/, dist/, and .venv-package/ are reproducible and excluded from Git.

## Troubleshooting

- Connected but no data: verify the COM port, 115200 baud, PA9→RX, and common ground.
- Port cannot be opened: close other serial programs, reconnect USB-TTL, and refresh the list.
- Garbled text or increasing invalid lines: confirm the firmware format and baud rate.
- Batch file closes immediately: run the Python command in PowerShell to see the error.
- Slow EXE startup: use the current onedir spec and launch from the complete output directory.

For command-line capture, decoding, and Allan analysis, see the [tools guide](../tools/README_EN.md).
