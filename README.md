# STM32 MPU6050 采集与 Allan 方差工具箱

[English](README_EN.md) | 中文

本项目提供一套完整的 MPU6050 数据链路：STM32F103 实时采集、Qt 串口监视与保存、CSV 解码，以及 Allan 方差随机误差辨识。

## 项目结构

    firmware/                 STM32F103 下位机固件
    host/                     Qt 串口实时监视器及 EXE 打包配置
    tools/                    串口采集、历史数据解码、Allan 分析工具
    data/raw/                 原始整数 CSV（本地数据，不提交）
    data/decoded/             物理量 CSV（本地数据，不提交）
    data/allan_results/       Allan 分析结果（本地结果，不提交）
    docs/                     知识说明和文档图片

各模块的详细说明：

- [下位机固件](firmware/README.md)
- [Qt 实时监视器](host/README.md)
- [数据工具与 Allan 分析](tools/README.md)
- [Allan 方差知识总结](docs/Allan方差知识总结.md)

## 硬件连接

当前项目经过验证的连接如下。GY-521 使用 3.3 V 供电。

| 设备引脚 | STM32F103C8T6 | 用途 |
| --- | --- | --- |
| GY-521 VCC | 3.3V | IMU 供电 |
| GY-521 GND | GND | 共地 |
| GY-521 SCL | PB6 | I2C1_SCL |
| GY-521 SDA | PB7 | I2C1_SDA |
| GY-521 INT | PB0 | 数据就绪中断 |
| USB-TTL RX | PA9 | 接收 STM32 USART1_TX |
| USB-TTL GND | GND | 共地 |

ST-LINK 只负责下载和调试固件；USB-TTL 负责把采集数据送到电脑。两者可以同时连接。

<p align="center">
  <img src="docs/images/hardware_wiring.jpg" alt="STM32、MPU6050、ST-LINK 与 USB-TTL 实物连接" width="700">
</p>

## 从零开始运行

### 1. 安装软件

- STM32CubeIDE for Visual Studio Code，或 CMake、Ninja 与 GNU Arm Embedded Toolchain
- STM32CubeProgrammer 和 ST-LINK 驱动
- Python 3.10 或更高版本

在仓库根目录安装 Python 依赖：

    D:\Anaconda3\python.exe -m pip install -r host\requirements.txt
    D:\Anaconda3\python.exe -m pip install -r tools\requirements.txt

如果 Python 不在该位置，请替换为自己的解释器路径。

### 2. 编译 STM32 固件

在 PowerShell 中执行：

    $ninjaDir = "$env:LOCALAPPDATA\stm32cube\bundles\ninja\1.13.2+st.1\bin"
    $gccDir = "$env:LOCALAPPDATA\stm32cube\bundles\gnu-tools-for-stm32\14.3.1+st.2\bin"
    $env:Path = "$ninjaDir;$gccDir;$env:Path"
    Push-Location firmware
    cmake --preset Release
    cmake --build --preset Release
    Pop-Location

生成文件位于 firmware/build/Release/。工具版本目录可能不同，请按本机实际安装版本修改路径。

### 3. 烧录固件

连接 ST-LINK 的 SWDIO、SWCLK、GND 和 3.3V，然后用 STM32CubeProgrammer 选择生成的 ELF 文件烧录。命令行示例：

    & "$env:LOCALAPPDATA\stm32cube\bundles\programmer\2.23.0\bin\STM32_Programmer_CLI.exe" -c port=SWD mode=UR reset=HWrst -w "firmware\build\Release\stm32_imu_test.elf" -v -rst

复位或重新上电后，固件自动开始采集并通过 PA9 输出，不需要电脑再发送启动命令。

### 4. 运行 Qt 实时监视器

    D:\Anaconda3\python.exe host\imu_serial_qt.py

也可以双击 host/run_imu_serial_qt.bat。选择 USB-TTL 对应串口和 115200 波特率后点击“连接”。勾选“同时保存物理量 CSV”时，默认保存到 data/decoded/。

### 5. 命令行采集

下面命令采集 COM3 的 12 小时数据，并实时转换成与 Allan 工具一致的物理量格式：

    D:\Anaconda3\python.exe tools\capture_serial.py COM3 --hours 12

文件默认保存在 data/decoded/。如需同时保留原始整数帧：

    D:\Anaconda3\python.exe tools\capture_serial.py COM3 --hours 12 --raw-output data\raw\mpu6050_static_raw.csv

### 6. 分析 Allan 方差

    D:\Anaconda3\python.exe tools\allan_noise_identification.py data\decoded\你的数据.csv --rate 100 --skip-minutes 30 --points 90

结果默认写入 data/allan_results/数据文件名_noise/。建议静置采集至少数小时，采集期间避免振动，并尽量保持温度稳定。

## 数据格式

STM32 串口原始帧共 10 列：

    sample,time_ms,dt_ms,ax_raw,ay_raw,az_raw,temp_raw,gx_raw,gy_raw,gz_raw

解码后和 Allan 工具使用的物理量 CSV：

    sample,time_s,dt_s,ax_m_s2,ay_m_s2,az_m_s2,temp_deg_c,gx_deg_h,gy_deg_h,gz_deg_h

## 程序演示

![Qt 串口实时监视器](docs/images/imu_serial_monitor_demo.png)

![Allan 方差辨识结果](docs/images/allan_identification.png)

## 构建文件与实验数据

固件 build、PyInstaller 的 build/dist、Python 缓存以及 data/ 下的实验数据均已由 .gitignore 排除。空数据目录通过 .gitkeep 保留。删除这些生成文件不会丢失源代码，可按本文命令重新构建。

## 许可证

本项目采用 [MIT License](LICENSE)。
