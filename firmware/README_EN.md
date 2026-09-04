# STM32F103 Firmware

[Project home](../README_EN.md) | [中文](README.md) | English

This directory contains only the STM32F103C8T6 firmware. The MPU6050 uses I2C1, PB0 receives DATA_RDY, and USART1 transmits the six raw axes and temperature as a 10-column CSV stream at 115200 bit/s.

## Current configuration

- Target: STM32F103C8T6
- I2C: PB6/SCL and PB7/SDA
- Data ready: PB0/EXTI0, rising edge
- Output: PA9/USART1_TX, 115200 bit/s
- Nominal output rate: approximately 100 Hz
- Startup: acquisition begins automatically after power-up or reset

## Wiring

| Peripheral | STM32 pin |
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

Keep BOOT0 low and use a common ground. USB-TTL TX is not required. Avoid feeding the board VCC from multiple power sources.

## Build

CMake, Ninja, and the GNU Arm Embedded Toolchain are required. Add the tool bundles installed by the STM32Cube VS Code extension to the current PowerShell session:

    $ninjaDir = "$env:LOCALAPPDATA\stm32cube\bundles\ninja\1.13.2+st.1\bin"
    $gccDir = "$env:LOCALAPPDATA\stm32cube\bundles\gnu-tools-for-stm32\14.3.1+st.2\bin"
    $env:Path = "$ninjaDir;$gccDir;$env:Path"

Build Release from the repository root:

    Push-Location firmware
    cmake --preset Release
    cmake --build --preset Release
    Pop-Location

Replace Release with Debug for a debug build. Main output:

    firmware\build\Release\stm32_imu_test.elf

The build/ directory is reproducible and excluded from Git.

## Flash

Select the ELF in STM32CubeProgrammer, or run this from the repository root:

    & "$env:LOCALAPPDATA\stm32cube\bundles\programmer\2.23.0\bin\STM32_Programmer_CLI.exe" -c port=SWD mode=UR reset=HWrst -w "firmware\build\Release\stm32_imu_test.elf" -v -rst

After reset, PA9 immediately emits:

    sample,time_ms,dt_ms,ax_raw,ay_raw,az_raw,temp_raw,gx_raw,gy_raw,gz_raw

## How it works

When the MPU6050 asserts DATA_RDY, the PB0 interrupt handler records the event and timestamp. The main loop performs the slower I2C read and UART transmission. The PC application receives data; it does not trigger acquisition.

## Troubleshooting

- No serial data: check INT→PB0, PA9→USB-TTL RX, common ground, and 115200 baud.
- Ninja or GCC not found: update the versioned bundle paths above.
- Flash failure: verify BOOT0=0, ST-LINK wiring and driver, then retry at a lower SWD frequency.
- Wrong sample rate: make sure INT is connected to PB0 rather than PB10 and that the main loop is not blocked.

Continue with the [Qt monitor](../host/README_EN.md) and [tools guide](../tools/README_EN.md).
