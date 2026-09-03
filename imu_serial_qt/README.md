# MPU6050 串口实时监视器

[中文](README.md) | [English](README_EN.md)

独立的 Qt 串口显示子项目，用于实时读取 STM32 输出的 MPU6050 数据，并绘制三轴加速度、三轴陀螺仪和温度曲线。

## 启动

双击 `run_imu_serial_qt.bat`，或者在本目录执行：

```powershell
D:\Anaconda3\python.exe imu_serial_qt.py
```

点击“刷新串口”，选择USB-TTL对应的实际COM端口，波特率使用
`115200 bit/s`。Windows重新插拔USB-TTL后端口号可能变化。串口不能同时被
串口助手或其他采集程序占用。

## 串口数据格式

程序接收以下 10 列整数 CSV：

```text
sample,time_ms,dt_ms,ax_raw,ay_raw,az_raw,temp_raw,gx_raw,gy_raw,gz_raw
```

界面可独立勾选 `Ax/Ay/Az/Gx/Gy/Gz`，支持仅显示任意单轴；也可以把转换后的物理量保存为 CSV。

右上角“语言”下拉框可在中文与English之间即时切换。所选语言会自动保存，
下次启动时继续使用。

## 安装依赖

当前电脑的 `D:\Anaconda3` 环境已经安装所需依赖。如需在其他 Python 环境运行：

```powershell
python -m pip install -r requirements.txt
```
