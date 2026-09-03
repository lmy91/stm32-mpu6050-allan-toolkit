# MPU6050 静态采集与 Allan 随机误差分析使用说明

[中文](README_Allan.md) | [English](README_Allan_EN.md)

本文说明如何完成以下流程：

1. 连接 MPU6050、STM32、ST-LINK 和 USB-TTL；
2. 编译并烧录 STM32 采集固件；
3. 保存静态 IMU 数据；
4. 将原始数据解码为物理量（如果需要）；
5. 使用 `allan_noise_identification.py` 计算 Allan 偏差并判读随机误差参数。

后续只需要运行 `tools\allan_noise_identification.py`。旧的
`allan_analysis.py` 不再需要单独运行，其左右双图绘制功能已经合并到
`allan_noise_identification.py`。

## 1. 项目目录

主要文件如下：

```text
low_cost_gnss_ins\
├─ imu_serial_qt\
│  ├─ imu_serial_qt.py          # 实时显示并保存物理量CSV
│  └─ run_imu_serial_qt.bat     # Qt程序启动脚本
└─ stm32_imu_test\
   ├─ Src\main.c                # STM32采集程序
   ├─ data\                     # 原始串口采集数据
   ├─ decoded_data\             # 解码后的物理量数据
   ├─ allan_results\            # Allan分析结果
   ├─ tools\capture_serial.py   # 长时间原始串口采集
   ├─ tools\decode_imu_data.py  # 原始计数转物理量
   └─ tools\allan_noise_identification.py
```

以下命令默认在此目录运行：

```text
D:\Dr\algorithm\low_cost_gnss_ins\stm32_imu_test
```

在 PowerShell 中进入目录：

```powershell
cd D:\Dr\algorithm\low_cost_gnss_ins\stm32_imu_test
```

## 2. 硬件连接

| 信号 | STM32F103C8T6 | GY-521 / USB-TTL |
|---|---|---|
| MPU6050电源 | 3.3V | GY-521 VCC |
| 公共地 | GND | GY-521 GND、USB-TTL GND |
| I2C时钟 | PB6 | GY-521 SCL |
| I2C数据 | PB7 | GY-521 SDA |
| 数据就绪中断 | PB0 | GY-521 INT |
| 串口输出 | PA9 | USB-TTL RXD |

注意事项：

- STM32、MPU6050、USB-TTL、ST-LINK 必须共地；
- `BOOT0` 保持为0；
- USB-TTL 的 TX 不是采集必需连接；
- STM32已经由USB或ST-LINK供电时，不要再用USB-TTL的VCC重复供电；
- MPU6050的INT必须连接PB0，否则中断触发采集不会运行。

当前固件将 MPU6050 `DATA_RDY` 配置为高电平锁存中断。PB0使用EXTI0
上升沿触发；中断服务函数只保存事件和时间戳，I2C读取及串口输出在主循环完成。

## 3. 编译和烧录STM32程序

### 3.1 ST-LINK连接

```text
ST-LINK SWDIO → STM32 PA13
ST-LINK SWCLK → STM32 PA14
ST-LINK GND   → STM32 GND
```

### 3.2 编译

```powershell
cmake --build --preset Debug
```

生成的固件位于：

```text
build\Debug\stm32_imu_test.elf
```

### 3.3 烧录

```powershell
& "$env:LOCALAPPDATA\stm32cube\bundles\programmer\2.23.0\bin\STM32_Programmer_CLI.exe" `
  -c port=SWD mode=UR reset=HWrst `
  -w "build\Debug\stm32_imu_test.elf" -v -rst
```

出现以下信息表示烧录和校验成功：

```text
Download verified successfully
```

当前固件参数：

- 输出串口：115200 bit/s，8N1；
- 输出频率：约100 Hz；
- 加速度计量程：±2 g，16384 LSB/g；
- 陀螺仪量程：±250 °/s，131 LSB/(°/s)；
- DLPF带宽：约42/44 Hz；
- 触发方式：MPU6050 DATA_RDY → PB0外部中断。

## 4. 采集静态数据

Allan实验建议：

- IMU固定在刚性、稳定的平台上；
- 整个采集过程不要移动、触碰桌面或插拔导线；
- 远离风扇、振动设备和阳光直射；
- 记录温度，并尽量减小空调周期造成的温度变化；
- 采集前预热30分钟；
- 6小时可以初步分析，推荐12～24小时；
- 采集期间避免电脑休眠、自动重启和USB节能断开。

有两种采集方法，任选一种即可。

### 4.1 方法A：Qt直接保存物理量CSV（推荐）

双击：

```text
D:\Dr\algorithm\low_cost_gnss_ins\imu_serial_qt\run_imu_serial_qt.bat
```

或运行：

```powershell
D:\Anaconda3\python.exe ..\imu_serial_qt\imu_serial_qt.py
```

操作顺序：

1. 关闭所有串口助手和其他串口采集脚本；
2. 点击“刷新串口”；
3. 选择Windows设备管理器中CH340对应的COM端口；
4. 波特率选择115200；
5. **连接前**勾选“同时保存物理量CSV”；
6. 点击“连接”；
7. 选择文件名和保存位置；
8. 检查有效帧持续增长、采样率约100 Hz、无效行和丢帧没有异常增加；
9. 采集完成后点击“断开”，让程序刷新并关闭CSV文件。

Qt保存的文件已经是 Allan 程序要求的物理量格式，不需要再次解码。

### 4.2 方法B：保存原始计数后再解码

将 `COM3` 替换为电脑当前显示的实际端口：

```powershell
D:\Anaconda3\python.exe tools\capture_serial.py COM3 --hours 12
```

原始串口列为：

```text
sample,time_ms,dt_ms,ax_raw,ay_raw,az_raw,temp_raw,gx_raw,gy_raw,gz_raw
```

采集完成后解码：

```powershell
D:\Anaconda3\python.exe tools\decode_imu_data.py `
  data\mpu6050_static_YYYYMMDD_HHMMSS.csv
```

默认结果写入 `decoded_data`。解码换算关系为：

```text
acceleration_m_s2 = raw / 16384 × 9.80665
angular_rate_deg_h = raw / 131 × 3600
temperature_deg_c = temp_raw / 340 + 36.53
```

`decode_imu_data.py`还会生成六轴加温度的总览图。可以通过
`--plot-block-seconds 10`获得更平滑的长时间曲线，或设置为`0.1`查看更多细节。

## 5. Allan程序要求的输入格式

`allan_noise_identification.py`只读取解码后的物理量CSV，列名和顺序必须是：

```text
sample,time_s,dt_s,ax_m_s2,ay_m_s2,az_m_s2,temp_deg_c,gx_deg_h,gy_deg_h,gz_deg_h
```

各列含义：

| 列名 | 单位 | 含义 |
|---|---|---|
| sample | 无 | 连续递增的采样序号 |
| time_s | s | STM32累计采样时间 |
| dt_s | s | 相邻样本时间间隔 |
| ax/ay/az_m_s2 | m/s² | 三轴加速度 |
| temp_deg_c | ℃ | MPU6050内部温度 |
| gx/gy/gz_deg_h | °/h | 三轴角速度 |

要求：

- 文件至少包含1000个有效样本；
- 不要在数据中间重复插入表头；
- 不允许出现NaN或无穷值；
- `sample`应连续递增；
- 数据必须来自完全静止的IMU；
- 不要使用姿态角或积分角度代替角速度。

## 6. 运行Allan随机误差分析

### 6.1 推荐命令

```powershell
D:\Anaconda3\python.exe tools\allan_noise_identification.py `
  decoded_data\mpu6050_static_20260901_213613_physical.csv `
  --rate 99.815 `
  --skip-minutes 30 `
  --points 90 `
  --output allan_results\mpu6050_12h_result
```

程序依次显示：

```text
Loading ...
Frames: ...
Duration: ...
Sequence discontinuities: ...
Computing accel X ...
...
Computing gyro Z ...
```

全部完成后会打印报告、参数表和图片的绝对路径。

### 6.2 参数说明

#### `csv`

必须提供的第一个参数，即解码后的物理量CSV路径。

#### `--rate`

Allan计算采用的采样频率，默认100 Hz。推荐使用完整数据时间戳计算出的实测
采样率，而不是始终写死为100。例如程序显示：

```text
empirical rate: 99.815641 Hz
```

下次计算可以将`--rate`设置为`99.815641`。采样率只有约0.2%的差异时不会改变
曲线形状，但会影响横轴τ和最终参数的精确尺度。

#### `--skip-minutes`

跳过开头的预热数据，默认0。MPU6050长时间静态实验推荐设置为30分钟：

```text
--skip-minutes 30
```

如果采集前已经单独预热30分钟，可以设为0。

#### `--points`

Allan横轴对数采样点数，默认90，最小30：

- 50～70：速度较快，适合测试；
- 90：推荐正式计算；
- 点数更多只会让曲线更密，不会增加原始信息。

#### `--output`

结果输出目录。省略时默认写入：

```text
allan_results\输入文件名_noise
```

建议每次实验使用独立目录，避免覆盖之前结果。

## 7. 正在写入的CSV如何分析

不要直接分析仍在写入的文件，因为程序读取时可能遇到尚未写完的最后一行，
并且分析过程中源文件仍会增长。先复制一个快照：

```powershell
Copy-Item `
  ..\imu_serial_qt\imu_realtime_YYYYMMDD_HHMMSS.csv `
  decoded_data\imu_snapshot_YYYYMMDD_HHMMSS.csv
```

然后对快照运行Allan程序。复制是只读快照操作，不会中断Qt实时采集。

## 8. 输出文件说明

每次运行生成以下文件：

### `allan_deviation.png`

合并自旧`allan_analysis.py`的简洁双图：

- 左图：X/Y/Z三轴加速度计Allan偏差，单位m/s²；
- 右图：X/Y/Z三轴陀螺仪Allan偏差，单位rad/s；
- 适合观察六轴曲线总体形状和轴间差异。

### `allan_identification.png`

六轴独立识别图。彩色粗线表示自动找到的噪声区间：

- 绿色：ARW/VRW，理论斜率约-1/2；
- 橙色：BI，理论斜率约0；
- 红色：RRW，理论斜率约+1/2；
- 紫色：Rate Ramp，理论斜率约+1。

### `stability_overview.png`

显示60秒分块均值残差和温度，用于检查温度阶跃、空调周期、长期漂移、外界
振动或误触碰，以及长τ上升是否可能由温漂引起。

### `allan_parameters.csv`

机器可读参数表，包含ARW/VRW、BI、RRW、Rate Ramp、拟合斜率、拟合τ区间、
可信度、各轴均值、标准差和温度相关系数。

### `allan_deviation.csv`

所有τ点及六轴Allan偏差数值，可以用于重新画图或与其他IMU对比。

### `随机误差判读报告.md`

中文总结报告，包含数据质量、温度情况、参数结果、拟合区间、可信度和
GNSS/INS使用建议。

## 9. 如何使用识别出的参数

### ARW / VRW

来自Allan曲线斜率约-1/2的白噪声区，可用于设置IMU测量白噪声。写入滤波器前
必须确认滤波器要求的是噪声密度、单样本标准差还是离散测量方差。

### BI（零偏稳定性）

来自Allan最低点附近的近水平区域，可作为零偏初始不确定度或一阶
高斯-马尔可夫模型的稳态尺度候选。不要直接将`BI²`作为每一步过程噪声Q。

### RRW（速率随机游走）

来自斜率约+1/2的区域，可作为零偏随机游走过程噪声候选。但如果该轴与温度
高度相关，报告会标记“温漂污染”，此时不要直接将RRW写入滤波器。

### Rate Ramp

来自斜率约+1的区域，通常更应检查温度趋势、供电漂移和确定性变化，而不是
直接当作白噪声处理。“未检出”不能按零填写。

## 10. 结果判读注意事项

- Allan曲线能够识别幂律形状，但不能仅凭斜率区分器件随机误差与温漂；
- 温度变化超过1 ℃时，应重点检查`stability_overview.png`；
- ARW/VRW通常比RRW和Rate Ramp更容易可靠识别；
- 最右侧τ点可用的独立数据块很少，长期参数必须重复实验验证；
- 线性插值补丢帧会平滑白噪声，不建议用于正式ARW计算；
- 少量丢帧应按连续数据段处理，不要直接压缩时间轴；
- 至少进行两次独立12小时实验，才能判断参数是否可重复；
- 如果需要温补，应先建立温度确定项，再对温补残差重新计算Allan偏差。

## 11. 常见问题

### 提示 `Decoded CSV header not found`

输入了原始计数CSV，或者列名不一致。先运行`decode_imu_data.py`，并检查表头
是否与第5节完全一致。

### 提示 `Too few valid samples`

有效数据少于1000行，或者`--skip-minutes`跳过了过多数据。

### 提示某列包含NaN或无穷值

说明CSV存在损坏、空值或非数值内容。先定位异常行，不要直接用插值掩盖问题。

### 运行很慢或占用较多内存

重叠Allan偏差需要对数百万帧反复计算，12～24小时数据运行几十秒属于正常现象。
可以先用`--points 50`测试，正式结果再使用90。

### 输出的RRW很大

先查看温度图和温度相关系数。室内空调引起的周期温变很容易在长τ区域形成
+1/2斜率，自动识别出的RRW可能实际是温漂。

## 12. 已验证示例

以下文件已完成实际运行验证：

```text
decoded_data\mpu6050_static_20260901_213613_physical.csv
```

数据量为4,318,258帧、约12.017小时、缺帧0。验证命令：

```powershell
D:\Anaconda3\python.exe tools\allan_noise_identification.py `
  decoded_data\mpu6050_static_20260901_213613_physical.csv `
  --rate 99.844 `
  --skip-minutes 30 `
  --points 70 `
  --output allan_results\decoded_physical_verified
```

该命令已经成功生成双图、六轴识别图、稳定性图、参数CSV、Allan数据CSV和
中文判读报告。
