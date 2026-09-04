# STM32F103 下位机固件

[项目主页](../README.md) | 中文 | [English](README_EN.md)

本目录只负责 STM32F103C8T6 固件。MPU6050 通过 I2C1 接入，PB0 接收 DATA_RDY 中断；STM32 读取六轴和温度原始值，再通过 USART1 以 115200 bit/s 输出 10 列 CSV。

## 当前配置

- 目标芯片：STM32F103C8T6
- I2C：PB6/SCL、PB7/SDA
- 数据就绪：PB0/EXTI0，上升沿触发
- 串口输出：PA9/USART1_TX，115200 bit/s
- 标称输出频率：约 100 Hz
- 程序启动方式：上电或复位后自动采集

## 接线

| 外设 | STM32 引脚 |
| --- | --- |
| GY-521 VCC | 3.3V |
| GY-521 GND | GND |
| GY-521 SCL | PB6 |
| GY-521 SDA | PB7 |
| GY-521 INT | PB0 |
| USB-TTL RX | PA9 |
| USB-TTL GND | GND |
| ST-LINK SWDIO | PA13/SWDIO |
| ST-LINK SWCLK | PA14/SWCLK |
| ST-LINK GND | GND |
| ST-LINK 3.3V | 3.3V |

保持 BOOT0=0。所有设备必须共地。USB-TTL 的 TX 不需要连接；不要让多个电源同时向开发板 VCC 反向供电。

## 编译

需要 CMake、Ninja 和 GNU Arm Embedded Toolchain。STM32Cube VS Code 扩展的工具可按下面方式加入当前 PowerShell：

    $ninjaDir = "$env:LOCALAPPDATA\stm32cube\bundles\ninja\1.13.2+st.1\bin"
    $gccDir = "$env:LOCALAPPDATA\stm32cube\bundles\gnu-tools-for-stm32\14.3.1+st.2\bin"
    $env:Path = "$ninjaDir;$gccDir;$env:Path"

在仓库根目录构建 Release：

    Push-Location firmware
    cmake --preset Release
    cmake --build --preset Release
    Pop-Location

调试版本将两个 Release 替换为 Debug。主要输出：

    firmware\build\Release\stm32_imu_test.elf

build/ 是可重建目录，不提交到 Git。

## 烧录

可以在 STM32CubeProgrammer 中选择 ELF 文件，也可以在仓库根目录运行：

    & "$env:LOCALAPPDATA\stm32cube\bundles\programmer\2.23.0\bin\STM32_Programmer_CLI.exe" -c port=SWD mode=UR reset=HWrst -w "firmware\build\Release\stm32_imu_test.elf" -v -rst

烧录后复位。PA9 会立即输出：

    sample,time_ms,dt_ms,ax_raw,ay_raw,az_raw,temp_raw,gx_raw,gy_raw,gz_raw

## 工作原理

MPU6050 产生 DATA_RDY 后拉起 INT，PB0 的中断服务只记录事件和时间戳，主循环再执行 I2C 读取和串口发送。这可避免在中断内进行耗时通信。串口程序只接收数据，不负责触发采集。

## 常见问题

- 没有串口数据：检查 INT→PB0、PA9→USB-TTL RX、共地、115200 波特率。
- 编译找不到 Ninja/GCC：确认上面的版本目录与本机一致。
- 烧录失败：检查 BOOT0=0、ST-LINK 接线和驱动，降低 SWD 频率后重试。
- 采样率异常：确认 INT 没有接到 PB10，并检查主循环是否被阻塞。

数据查看和分析请继续阅读 [Qt 上位机说明](../host/README.md) 与 [工具说明](../tools/README.md)。
