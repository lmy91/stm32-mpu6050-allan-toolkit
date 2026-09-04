# 数据采集、解码与 Allan 分析工具

[项目主页](../README.md) | 中文 | [English](README_EN.md)

本目录只包含数据处理脚本。默认在仓库根目录运行命令，所有实验数据统一写入 data/，不写回 tools/。

## 文件说明

| 文件 | 用途 | 默认输出 |
| --- | --- | --- |
| capture_serial.py | 串口采集并在线转换物理量 | data/decoded/ |
| decode_imu_data.py | 将历史原始 CSV 转成物理量并绘制七通道图 | data/decoded/ |
| allan_noise_identification.py | 计算 Allan 偏差并辨识随机误差参数 | data/allan_results/ |

## 安装依赖

    D:\Anaconda3\python.exe -m pip install -r tools\requirements.txt

也可以使用其他 Python 3.10+ 解释器。查看任意脚本参数：

    D:\Anaconda3\python.exe tools\capture_serial.py --help
    D:\Anaconda3\python.exe tools\decode_imu_data.py --help
    D:\Anaconda3\python.exe tools\allan_noise_identification.py --help

## 数据目录

    data\raw\               可选的原始整数帧
    data\decoded\           物理量 CSV 和七通道解码图
    data\allan_results\     Allan 曲线、参数表和报告

这些目录中的实验文件默认不提交 Git，只有 .gitkeep 用于保留空目录。

## 1. 直接采集物理量 CSV

确认 USB-TTL 已连接，串口没有被 Qt 监视器或串口助手占用。采集 COM3 的 12 小时数据：

    D:\Anaconda3\python.exe tools\capture_serial.py COM3 --hours 12

默认波特率 115200，输出文件自动命名并保存至 data/decoded/。hours=0 表示持续运行，按 Ctrl+C 安全结束：

    D:\Anaconda3\python.exe tools\capture_serial.py COM3 --hours 0

指定物理量文件，并同时保存原始帧：

    D:\Anaconda3\python.exe tools\capture_serial.py COM3 --hours 12 --output data\decoded\static_12h.csv --raw-output data\raw\static_12h_raw.csv

主输出已经是 Allan 工具所需格式，不需要再次运行 decode_imu_data.py。

## 2. 解码已有原始数据

仅当手中已有 STM32 原始整数 CSV 时使用：

    D:\Anaconda3\python.exe tools\decode_imu_data.py data\raw\static_12h_raw.csv

默认生成：

    data\decoded\static_12h_raw_physical.csv
    data\decoded\static_12h_raw_7channel.png

自定义输出：

    D:\Anaconda3\python.exe tools\decode_imu_data.py data\raw\static_12h_raw.csv --output-csv data\decoded\static_12h.csv --plot data\decoded\static_12h.png --rate 100

脚本按块读取长数据，完整保留有效样本；绘图使用分块均值，避免 12 小时数据耗尽内存。

## 3. Allan 随机误差辨识

输入必须是物理量 CSV：

    D:\Anaconda3\python.exe tools\allan_noise_identification.py data\decoded\static_12h.csv --rate 100 --skip-minutes 30 --points 90

参数含义：

- --rate：名义采样率，当前固件通常使用 100 Hz。
- --skip-minutes：跳过开机预热阶段；不需要时设为 0。
- --points：对数分布的聚类时间点数量，必须至少为 30。
- --output：自定义结果目录；省略时使用 data/allan_results/输入文件名_noise/。

默认结果包括：

| 文件 | 内容 |
| --- | --- |
| allan_deviation.png | 加速度计和陀螺仪 Allan 曲线总览 |
| allan_identification.png | 带拟合区间及参数标注的辨识图 |
| stability_overview.png | 六轴和温度的时间稳定性 |
| allan_parameters.csv | 六轴随机误差参数 |
| allan_deviation.csv | 各聚类时间的 Allan 偏差 |
| 随机误差判读报告.md | 数据质量、丢帧、温度和参数说明 |

程序辨识白噪声（VRW/ARW）、零偏稳定性（BI）、随机游走（RRW）和速率斜坡，并报告样本序号断点与估计丢帧数。详细原理见 [Allan 方差知识总结](../docs/Allan方差知识总结.md)。

## 输入格式

STM32 原始格式：

    sample,time_ms,dt_ms,ax_raw,ay_raw,az_raw,temp_raw,gx_raw,gy_raw,gz_raw

物理量/Allan 格式：

    sample,time_s,dt_s,ax_m_s2,ay_m_s2,az_m_s2,temp_deg_c,gx_deg_h,gy_deg_h,gz_deg_h

角速度 CSV 使用 deg/h；Allan 程序内部会转换为 rad/s 后进行统一估计。

## 长时间采集建议

- 固定 IMU，避免桌面振动、线缆拉扯和人为触碰。
- 先预热约 30 分钟，再开始用于分析的稳定段。
- 尽量控制温度；明显温漂会抬高长聚类时间处的曲线。
- 少量孤立丢帧通常不破坏整次分析，但大量或连续丢帧会改变等间隔采样假设，应重新采集。
- 正在写入的文件可复制一份快照再分析，不要让两个程序同时写同一文件。

## 常见问题

- Access denied/串口占用：关闭 Qt 监视器或其他串口软件。
- CSV header not found：确认输入文件确实是上面列出的 10 列格式。
- Warm-up skip leaves too few samples：减小 --skip-minutes。
- 采样率不确定：查看报告中的 empirical rate，再用正确的 --rate 重算。
- 内存不足：降低 --points，关闭其他大型程序；解码器本身已采用分块读取。
