# MPU6050 Real-time Serial Monitor

[中文](README.md) | [English](README_EN.md)

A standalone Qt application that reads MPU6050 data sent by an STM32 and plots
3-axis acceleration, 3-axis angular rate, and temperature in real time.

## Start the application

On Windows, double-click `run_imu_serial_qt.bat`, or run this command from the
project directory:

```powershell
python imu_serial_qt.py
```

Click **Refresh**, select the COM port assigned to the USB-to-TTL adapter, and
use `115200 bit/s`. The COM number may change after reconnecting the adapter.
Only one application can open a serial port at a time, so close other serial
monitors and logging scripts first.

## Language

Use the **Language** list in the upper-right corner to switch between Chinese
and English immediately. The application remembers the selection for the next
launch.

## Serial data format

The application accepts the following 10-column integer CSV stream:

```text
sample,time_ms,dt_ms,ax_raw,ay_raw,az_raw,temp_raw,gx_raw,gy_raw,gz_raw
```

`Ax/Ay/Az/Gx/Gy/Gz` can be enabled independently, including single-axis views.
The decoded values can also be saved as a physical-unit CSV containing `m/s²`,
`deg/h`, and `°C`.

## Dependencies

Install the required packages in your Python environment:

```powershell
python -m pip install -r requirements.txt
```
