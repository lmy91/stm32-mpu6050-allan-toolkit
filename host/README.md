# Qt 串口实时监视器

[项目主页](../README.md) | 中文 | [English](README_EN.md)

本目录是电脑端上位机。程序接收 STM32 发出的 MPU6050 原始帧，实时换算并绘制三轴加速度、三轴角速度和温度，支持中英文切换、单轴勾选、丢帧统计及物理量 CSV 保存。

## 安装依赖

在仓库根目录执行：

    D:\Anaconda3\python.exe -m pip install -r host\requirements.txt

也可以使用其他 Python 3.10+ 解释器。依赖包括 PyQt5、pyqtgraph、pyserial 和 NumPy。

## 启动

在仓库根目录执行：

    D:\Anaconda3\python.exe host\imu_serial_qt.py

或双击 host/run_imu_serial_qt.bat。

## 使用步骤

1. 确认 STM32 PA9→USB-TTL RX，二者 GND 共地。
2. 将 USB-TTL 插入电脑，关闭可能占用串口的串口助手。
3. 点击“刷新串口”，选择对应 COM 端口。
4. 波特率选择 115200，然后点击“连接”。
5. 使用 Ax/Ay/Az/Gx/Gy/Gz 复选框选择要显示的轴；只勾一个即可单轴查看。
6. 需要记录时勾选“同时保存物理量 CSV”。保存对话框默认打开 data/decoded/。
7. 采集结束先点击“断开”，再拔出 USB-TTL。

“暂停绘图”只停止界面刷新，不停止串口接收和已启用的文件保存。“清空曲线”清除当前显示缓存，不删除已经保存的 CSV。

## 输入与输出

输入为 STM32 的 10 列原始整数 CSV：

    sample,time_ms,dt_ms,ax_raw,ay_raw,az_raw,temp_raw,gx_raw,gy_raw,gz_raw

保存文件为 Allan 工具可直接读取的物理量 CSV：

    sample,time_s,dt_s,ax_m_s2,ay_m_s2,az_m_s2,temp_deg_c,gx_deg_h,gy_deg_h,gz_deg_h

## 打包 Windows EXE

建议使用 PyInstaller 的 onedir 模式。它启动时直接加载目录内文件，不会像 onefile 一样每次解压大型运行环境。

在仓库根目录新建独立打包环境：

    D:\Anaconda3\python.exe -m venv .venv-package
    .\.venv-package\Scripts\python.exe -m pip install --upgrade pip
    .\.venv-package\Scripts\python.exe -m pip install -r host\requirements.txt pyinstaller

执行打包：

    .\.venv-package\Scripts\python.exe -m PyInstaller --noconfirm --clean host\MPU6050_Serial_Monitor.spec

输出位于：

    dist\MPU6050_Serial_Monitor\MPU6050_Serial_Monitor.exe

发布时必须压缩并分发整个 MPU6050_Serial_Monitor 文件夹，不能只复制 EXE。build/、dist/ 和 .venv-package/ 都可删除并重新构建，默认不提交 Git。

## 常见问题

- 点击连接没有数据：检查 COM 口、115200 波特率、PA9→RX 和共地。
- 串口打开失败：关闭其他串口软件，重新插拔 USB-TTL 后刷新端口。
- 显示乱码或无效行增加：确认固件输出格式和波特率没有改变。
- 运行 .bat 后闪退：在 PowerShell 直接运行 Python 命令查看错误信息。
- EXE 启动慢：确认使用当前 onedir spec，并从完整输出目录启动。

后续命令行采集、解码和 Allan 分析见 [工具说明](../tools/README.md)。
