"""PyQt5 real-time MPU6050 serial monitor for the STM32 Allan logger.

Expected firmware CSV columns:
sample,time_ms,dt_ms,ax_raw,ay_raw,az_raw,temp_raw,gx_raw,gy_raw,gz_raw
"""

from __future__ import annotations

import csv
import pathlib
import sys
import time
from collections import deque

import numpy as np
import pyqtgraph as pg
import serial
from serial.tools import list_ports
from PyQt5 import QtCore, QtGui, QtWidgets


G0 = 9.80665
ACCEL_SCALE = G0 / 16384.0
GYRO_DEG_H_SCALE = 3600.0 / 131.0
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "decoded"


TRANSLATIONS = {
    "zh_CN": {
        "window_title": "MPU6050 串口实时监视器",
        "serial": "串口", "refresh_ports": "刷新串口", "baud_rate": "波特率",
        "connect": "连接", "disconnect": "断开", "pause_plot": "暂停绘图",
        "resume_plot": "继续绘图", "clear_plot": "清空曲线", "display_window": "显示窗口",
        "save_csv": "同时保存物理量CSV", "language": "语言",
        "window_tip": "曲线保留的最近时间长度",
        "save_tip": "保存m/s²、deg/h和°C；勾选后连接时选择文件",
        "not_connected": "● 未连接", "connected": "● 已连接 {device}",
        "sample_rate": "采样率: {value}", "valid_frames": "有效帧: {value}",
        "lost_frames": "丢帧: {value}", "invalid_lines": "无效行: {value}",
        "temperature_stat": "温度: {value}", "accel_title": "三轴加速度",
        "gyro_title": "三轴陀螺仪", "temperature_title": "温度",
        "acceleration": "加速度", "angular_rate": "角速度", "temperature": "温度",
        "relative_time": "相对最新样本的时间", "accel_visible": "加速度计显示",
        "gyro_visible": "陀螺仪显示", "unknown_device": "未知设备",
        "startup_status": "未连接。串口不能与串口助手或采集脚本同时使用。",
        "user_disconnected": "用户断开。", "no_serial_title": "没有串口",
        "no_serial_message": "未发现可用串口，请检查USB-TTL连接。",
        "save_dialog": "保存实时物理量数据", "serial_error_title": "串口连接失败",
        "serial_error_message": "无法打开 {device}：\n{error}\n\n请关闭串口助手和其他采集程序。",
        "file_error_title": "文件错误", "file_error_message": "无法创建保存文件：\n{error}",
        "receiving": "正在接收 {device}，期望格式为10列STM32 CSV。",
        "serial_disconnected": "串口异常断开：{error}",
        "plot_paused": "绘图已暂停，串口仍在接收。", "plot_resumed": "绘图已继续。",
        "app_closed": "应用已关闭。",
    },
    "en_US": {
        "window_title": "MPU6050 Real-time Serial Monitor",
        "serial": "Port", "refresh_ports": "Refresh", "baud_rate": "Baud rate",
        "connect": "Connect", "disconnect": "Disconnect", "pause_plot": "Pause plots",
        "resume_plot": "Resume plots", "clear_plot": "Clear plots", "display_window": "Time window",
        "save_csv": "Save physical-unit CSV", "language": "Language",
        "window_tip": "Length of recent data retained in the plots",
        "save_tip": "Save m/s², deg/h, and °C; select the file when connecting",
        "not_connected": "● Disconnected", "connected": "● Connected: {device}",
        "sample_rate": "Sample rate: {value}", "valid_frames": "Valid frames: {value}",
        "lost_frames": "Lost frames: {value}", "invalid_lines": "Invalid lines: {value}",
        "temperature_stat": "Temperature: {value}", "accel_title": "3-axis acceleration",
        "gyro_title": "3-axis gyroscope", "temperature_title": "Temperature",
        "acceleration": "Acceleration", "angular_rate": "Angular rate", "temperature": "Temperature",
        "relative_time": "Time relative to newest sample", "accel_visible": "Accelerometer axes",
        "gyro_visible": "Gyroscope axes", "unknown_device": "Unknown device",
        "startup_status": "Disconnected. The serial port cannot be shared with another monitor or logger.",
        "user_disconnected": "Disconnected by user.", "no_serial_title": "No serial port",
        "no_serial_message": "No serial port was found. Check the USB-to-TTL connection.",
        "save_dialog": "Save real-time physical-unit data", "serial_error_title": "Serial connection failed",
        "serial_error_message": "Could not open {device}:\n{error}\n\nClose other serial monitors and loggers.",
        "file_error_title": "File error", "file_error_message": "Could not create the output file:\n{error}",
        "receiving": "Receiving {device}; expecting the 10-column STM32 CSV format.",
        "serial_disconnected": "Serial port disconnected unexpectedly: {error}",
        "plot_paused": "Plots paused; serial reception continues.", "plot_resumed": "Plots resumed.",
        "app_closed": "Application closed.",
    },
}


class ImuSerialMonitor(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QtCore.QSettings("lmy91", "MPU6050SerialMonitor")
        self.language = str(self.settings.value("language", "zh_CN"))
        if self.language not in TRANSLATIONS:
            self.language = "zh_CN"
        self.resize(1450, 930)

        self.serial_port: serial.Serial | None = None
        self.rx_buffer = bytearray()
        self.log_stream = None
        self.log_writer: csv.writer | None = None
        self.log_rows_since_flush = 0
        self.plot_paused = False

        self.channels: dict[str, deque[float]] = {
            name: deque() for name in
            ("time", "ax", "ay", "az", "gx", "gy", "gz", "temp")
        }
        self.last_mcu_time_ms: int | None = None
        self.elapsed_seconds = 0.0
        self.last_sample_number: int | None = None
        self.total_samples = 0
        self.lost_samples = 0
        self.invalid_lines = 0
        self.last_dt_ms = 0
        self.recent_arrivals: deque[float] = deque()

        self._build_ui()
        self._build_timers()
        self.refresh_ports()
        self.statusBar().showMessage(self.tr_text("startup_status"))

    def tr_text(self, key: str, **values: object) -> str:
        """Return one translated UI string for the active language."""
        return TRANSLATIONS[self.language][key].format(**values)

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        controls = QtWidgets.QHBoxLayout()
        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setMinimumWidth(180)
        self.refresh_button = QtWidgets.QPushButton()
        self.refresh_button.clicked.connect(self.refresh_ports)

        self.baud_combo = QtWidgets.QComboBox()
        self.baud_combo.addItems(["115200", "230400", "460800", "921600"])
        self.connect_button = QtWidgets.QPushButton()
        self.connect_button.setMinimumWidth(90)
        self.connect_button.clicked.connect(self.toggle_connection)

        self.pause_button = QtWidgets.QPushButton()
        self.pause_button.clicked.connect(self.toggle_plot_pause)
        self.pause_button.setEnabled(False)

        self.clear_button = QtWidgets.QPushButton()
        self.clear_button.clicked.connect(self.clear_data)

        self.window_spin = QtWidgets.QSpinBox()
        self.window_spin.setRange(5, 3600)
        self.window_spin.setValue(60)
        self.window_spin.setSuffix(" s")
        self.window_spin.valueChanged.connect(self.trim_buffers)

        self.save_checkbox = QtWidgets.QCheckBox()

        self.port_label = QtWidgets.QLabel()
        self.baud_label = QtWidgets.QLabel()
        self.window_label = QtWidgets.QLabel()
        self.language_label = QtWidgets.QLabel()
        self.language_combo = QtWidgets.QComboBox()
        self.language_combo.addItem("中文", "zh_CN")
        self.language_combo.addItem("English", "en_US")
        language_index = self.language_combo.findData(self.language)
        self.language_combo.setCurrentIndex(max(language_index, 0))
        self.language_combo.currentIndexChanged.connect(self.change_language)

        controls.addWidget(self.port_label)
        controls.addWidget(self.port_combo)
        controls.addWidget(self.refresh_button)
        controls.addSpacing(8)
        controls.addWidget(self.baud_label)
        controls.addWidget(self.baud_combo)
        controls.addWidget(self.connect_button)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.clear_button)
        controls.addSpacing(8)
        controls.addWidget(self.window_label)
        controls.addWidget(self.window_spin)
        controls.addWidget(self.save_checkbox)
        controls.addStretch(1)

        controls.addWidget(self.language_label)
        controls.addWidget(self.language_combo)

        self.connection_label = QtWidgets.QLabel()
        self.connection_label.setStyleSheet("color:#d9534f;font-weight:bold")
        controls.addWidget(self.connection_label)
        layout.addLayout(controls)

        stats = QtWidgets.QHBoxLayout()
        self.rate_label = QtWidgets.QLabel()
        self.samples_label = QtWidgets.QLabel()
        self.loss_label = QtWidgets.QLabel()
        self.invalid_label = QtWidgets.QLabel()
        self.dt_label = QtWidgets.QLabel("dt: -- ms")
        self.temp_label = QtWidgets.QLabel()
        for label in (
            self.rate_label, self.samples_label, self.loss_label,
            self.invalid_label, self.dt_label, self.temp_label,
        ):
            label.setMinimumWidth(130)
            stats.addWidget(label)
        stats.addStretch(1)
        layout.addLayout(stats)

        pg.setConfigOptions(antialias=False, background="#101418", foreground="#d8dee9")
        self.graphics = pg.GraphicsLayoutWidget()
        layout.addWidget(self.graphics, stretch=1)

        self.accel_plot = self.graphics.addPlot(row=0, col=0)
        self.gyro_plot = self.graphics.addPlot(row=1, col=0)
        self.temp_plot = self.graphics.addPlot(row=2, col=0)
        self.gyro_plot.setXLink(self.accel_plot)
        self.temp_plot.setXLink(self.accel_plot)

        for plot in (self.accel_plot, self.gyro_plot, self.temp_plot):
            plot.showGrid(x=True, y=True, alpha=0.25)
            plot.setClipToView(True)
            plot.setDownsampling(auto=True, mode="peak")

        accel_legend = self.accel_plot.addLegend(offset=(8, 8))
        gyro_legend = self.gyro_plot.addLegend(offset=(8, 8))
        self.accel_curves = {
            "ax": self.accel_plot.plot(pen=pg.mkPen("#4ea1ff", width=1.4), name="Ax"),
            "ay": self.accel_plot.plot(pen=pg.mkPen("#ff9f43", width=1.4), name="Ay"),
            "az": self.accel_plot.plot(pen=pg.mkPen("#2ecc71", width=1.4), name="Az"),
        }
        self.gyro_curves = {
            "gx": self.gyro_plot.plot(pen=pg.mkPen("#ff5c5c", width=1.4), name="Gx"),
            "gy": self.gyro_plot.plot(pen=pg.mkPen("#b084f5", width=1.4), name="Gy"),
            "gz": self.gyro_plot.plot(pen=pg.mkPen("#d4a373", width=1.4), name="Gz"),
        }
        self.temp_curve = self.temp_plot.plot(pen=pg.mkPen("#ff3b30", width=1.6), name="Temperature")
        _ = accel_legend, gyro_legend

        axis_controls = QtWidgets.QHBoxLayout()
        self.accel_axes_label = QtWidgets.QLabel()
        self.gyro_axes_label = QtWidgets.QLabel()
        axis_controls.addWidget(self.accel_axes_label)
        self.axis_checkboxes: dict[str, QtWidgets.QCheckBox] = {}
        axis_labels = {
            "ax": "Ax", "ay": "Ay", "az": "Az",
            "gx": "Gx", "gy": "Gy", "gz": "Gz",
        }
        for name in ("ax", "ay", "az"):
            checkbox = QtWidgets.QCheckBox(axis_labels[name])
            checkbox.setChecked(True)
            checkbox.toggled.connect(
                lambda visible, channel=name: self.set_axis_visible(channel, visible)
            )
            self.axis_checkboxes[name] = checkbox
            axis_controls.addWidget(checkbox)

        axis_controls.addSpacing(24)
        axis_controls.addWidget(self.gyro_axes_label)
        for name in ("gx", "gy", "gz"):
            checkbox = QtWidgets.QCheckBox(axis_labels[name])
            checkbox.setChecked(True)
            checkbox.toggled.connect(
                lambda visible, channel=name: self.set_axis_visible(channel, visible)
            )
            self.axis_checkboxes[name] = checkbox
            axis_controls.addWidget(checkbox)
        axis_controls.addStretch(1)
        layout.insertLayout(2, axis_controls)

        self.setCentralWidget(central)
        self.retranslate_ui()

    @QtCore.pyqtSlot(int)
    def change_language(self, _index: int) -> None:
        language = self.language_combo.currentData()
        if language not in TRANSLATIONS or language == self.language:
            return
        self.language = language
        self.settings.setValue("language", language)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """Apply the selected language immediately without restarting."""
        self.setWindowTitle(self.tr_text("window_title"))
        self.port_label.setText(self.tr_text("serial"))
        self.refresh_button.setText(self.tr_text("refresh_ports"))
        self.baud_label.setText(self.tr_text("baud_rate"))
        self.connect_button.setText(
            self.tr_text("disconnect") if self.serial_port is not None else self.tr_text("connect")
        )
        self.pause_button.setText(
            self.tr_text("resume_plot") if self.plot_paused else self.tr_text("pause_plot")
        )
        self.clear_button.setText(self.tr_text("clear_plot"))
        self.window_label.setText(self.tr_text("display_window"))
        self.window_spin.setToolTip(self.tr_text("window_tip"))
        self.save_checkbox.setText(self.tr_text("save_csv"))
        self.save_checkbox.setToolTip(self.tr_text("save_tip"))
        self.language_label.setText(self.tr_text("language"))
        self.accel_axes_label.setText(self.tr_text("accel_visible"))
        self.gyro_axes_label.setText(self.tr_text("gyro_visible"))

        self.accel_plot.setTitle(self.tr_text("accel_title"))
        self.gyro_plot.setTitle(self.tr_text("gyro_title"))
        self.temp_plot.setTitle(self.tr_text("temperature_title"))
        self.accel_plot.setLabel("left", self.tr_text("acceleration"), units="m/s²")
        self.gyro_plot.setLabel("left", self.tr_text("angular_rate"), units="deg/h")
        self.temp_plot.setLabel("left", self.tr_text("temperature"), units="°C")
        self.temp_plot.setLabel("bottom", self.tr_text("relative_time"), units="s")

        if self.serial_port is None:
            self.connection_label.setText(self.tr_text("not_connected"))
            self.statusBar().showMessage(self.tr_text("startup_status"))
        else:
            device = self.serial_port.port
            self.connection_label.setText(self.tr_text("connected", device=device))
            self.statusBar().showMessage(self.tr_text("receiving", device=device))
        self.update_stats()

    @QtCore.pyqtSlot(str, bool)
    def set_axis_visible(self, channel: str, visible: bool) -> None:
        """Show or hide one accelerometer/gyroscope curve independently."""
        curve = self.accel_curves.get(channel) or self.gyro_curves.get(channel)
        if curve is None:
            return
        curve.setVisible(visible)

        # Recalculate the vertical range from the remaining visible curves.
        plot = self.accel_plot if channel.startswith("a") else self.gyro_plot
        plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)

    def _build_timers(self) -> None:
        self.serial_timer = QtCore.QTimer(self)
        self.serial_timer.setInterval(10)
        self.serial_timer.timeout.connect(self.poll_serial)
        self.serial_timer.start()

        self.plot_timer = QtCore.QTimer(self)
        self.plot_timer.setInterval(100)
        self.plot_timer.timeout.connect(self.update_plots)
        self.plot_timer.start()

        self.stats_timer = QtCore.QTimer(self)
        self.stats_timer.setInterval(500)
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start()

    @QtCore.pyqtSlot()
    def refresh_ports(self) -> None:
        selected = self.port_combo.currentData()
        ports = sorted(list_ports.comports(), key=lambda item: item.device)
        self.port_combo.clear()
        preferred_index = -1
        restored_index = -1
        for index, port in enumerate(ports):
            description = port.description or self.tr_text("unknown_device")
            self.port_combo.addItem(f"{port.device} — {description}", port.device)
            if port.device.upper() == "COM4":
                preferred_index = index
            if selected and port.device == selected:
                restored_index = index
        if restored_index >= 0:
            self.port_combo.setCurrentIndex(restored_index)
        elif preferred_index >= 0:
            self.port_combo.setCurrentIndex(preferred_index)

    @QtCore.pyqtSlot()
    def toggle_connection(self) -> None:
        if self.serial_port is None:
            self.connect_serial()
        else:
            self.disconnect_serial(self.tr_text("user_disconnected"))

    def connect_serial(self) -> None:
        device = self.port_combo.currentData()
        if not device:
            QtWidgets.QMessageBox.warning(
                self, self.tr_text("no_serial_title"), self.tr_text("no_serial_message")
            )
            return

        log_path: pathlib.Path | None = None
        if self.save_checkbox.isChecked():
            default_name = f"imu_realtime_{time.strftime('%Y%m%d_%H%M%S')}.csv"
            DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
            default_path = DEFAULT_DATA_DIR / default_name
            selected, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, self.tr_text("save_dialog"), str(default_path), "CSV files (*.csv)"
            )
            if not selected:
                return
            log_path = pathlib.Path(selected)

        try:
            port = serial.Serial(
                device,
                int(self.baud_combo.currentText()),
                timeout=0,
                write_timeout=0,
            )
            port.dtr = False
            port.rts = False
            port.reset_input_buffer()
        except (serial.SerialException, OSError) as error:
            QtWidgets.QMessageBox.critical(
                self, self.tr_text("serial_error_title"),
                self.tr_text("serial_error_message", device=device, error=error),
            )
            return

        if log_path is not None:
            try:
                self.log_stream = log_path.open("w", newline="", encoding="utf-8")
                self.log_writer = csv.writer(self.log_stream)
                self.log_writer.writerow([
                    "sample", "time_s", "dt_s",
                    "ax_m_s2", "ay_m_s2", "az_m_s2", "temp_deg_c",
                    "gx_deg_h", "gy_deg_h", "gz_deg_h",
                ])
            except OSError as error:
                port.close()
                QtWidgets.QMessageBox.critical(
                    self, self.tr_text("file_error_title"),
                    self.tr_text("file_error_message", error=error),
                )
                return

        self.serial_port = port
        self.rx_buffer.clear()
        self.connect_button.setText(self.tr_text("disconnect"))
        self.pause_button.setEnabled(True)
        self.port_combo.setEnabled(False)
        self.baud_combo.setEnabled(False)
        self.save_checkbox.setEnabled(False)
        self.connection_label.setText(self.tr_text("connected", device=device))
        self.connection_label.setStyleSheet("color:#2ecc71;font-weight:bold")
        self.statusBar().showMessage(self.tr_text("receiving", device=device))

    def disconnect_serial(self, reason: str) -> None:
        if self.serial_port is not None:
            try:
                self.serial_port.close()
            except serial.SerialException:
                pass
        self.serial_port = None
        if self.log_stream is not None:
            self.log_stream.flush()
            self.log_stream.close()
        self.log_stream = None
        self.log_writer = None
        self.log_rows_since_flush = 0
        self.connect_button.setText(self.tr_text("connect"))
        self.pause_button.setEnabled(False)
        self.port_combo.setEnabled(True)
        self.baud_combo.setEnabled(True)
        self.save_checkbox.setEnabled(True)
        self.connection_label.setText(self.tr_text("not_connected"))
        self.connection_label.setStyleSheet("color:#d9534f;font-weight:bold")
        self.statusBar().showMessage(reason)

    @QtCore.pyqtSlot()
    def poll_serial(self) -> None:
        if self.serial_port is None:
            return
        try:
            waiting = self.serial_port.in_waiting
            if waiting <= 0:
                return
            self.rx_buffer.extend(self.serial_port.read(waiting))
        except (serial.SerialException, OSError) as error:
            self.disconnect_serial(self.tr_text("serial_disconnected", error=error))
            return

        while True:
            newline = self.rx_buffer.find(b"\n")
            if newline < 0:
                break
            raw_line = bytes(self.rx_buffer[:newline]).strip()
            del self.rx_buffer[:newline + 1]
            if raw_line:
                self.process_line(raw_line)

        if len(self.rx_buffer) > 1024 * 1024:
            self.rx_buffer.clear()
            self.invalid_lines += 1

    def process_line(self, raw_line: bytes) -> None:
        try:
            line = raw_line.decode("ascii")
        except UnicodeDecodeError:
            self.invalid_lines += 1
            return
        if line.startswith("#") or line.startswith("sample,"):
            return

        parts = line.split(",")
        if len(parts) != 10:
            self.invalid_lines += 1
            return
        try:
            numbers = [int(value) for value in parts]
        except ValueError:
            self.invalid_lines += 1
            return

        sample, time_ms, dt_ms, ax, ay, az, temp, gx, gy, gz = numbers
        if self.last_sample_number is not None:
            delta = sample - self.last_sample_number
            if delta > 1:
                self.lost_samples += delta - 1
            elif delta <= 0:
                self.invalid_lines += 1
        self.last_sample_number = sample

        if self.last_mcu_time_ms is None:
            self.elapsed_seconds = 0.0
        else:
            delta_ms = time_ms - self.last_mcu_time_ms
            if delta_ms < 0:
                delta_ms += 1 << 32
            self.elapsed_seconds += delta_ms / 1000.0
        self.last_mcu_time_ms = time_ms
        self.last_dt_ms = dt_ms

        values = {
            "time": self.elapsed_seconds,
            "ax": ax * ACCEL_SCALE,
            "ay": ay * ACCEL_SCALE,
            "az": az * ACCEL_SCALE,
            "temp": temp / 340.0 + 36.53,
            "gx": gx * GYRO_DEG_H_SCALE,
            "gy": gy * GYRO_DEG_H_SCALE,
            "gz": gz * GYRO_DEG_H_SCALE,
        }
        for name, value in values.items():
            self.channels[name].append(float(value))

        self.total_samples += 1
        arrival = time.monotonic()
        self.recent_arrivals.append(arrival)
        while self.recent_arrivals and arrival - self.recent_arrivals[0] > 2.0:
            self.recent_arrivals.popleft()

        if self.log_writer is not None:
            self.log_writer.writerow([
                sample, time_ms / 1000.0, dt_ms / 1000.0,
                values["ax"], values["ay"], values["az"], values["temp"],
                values["gx"], values["gy"], values["gz"],
            ])
            self.log_rows_since_flush += 1
            if self.log_rows_since_flush >= 1000:
                self.log_stream.flush()
                self.log_rows_since_flush = 0

        self.trim_buffers()

    @QtCore.pyqtSlot()
    def trim_buffers(self) -> None:
        maximum = int(self.window_spin.value() * 130)
        for channel in self.channels.values():
            while len(channel) > maximum:
                channel.popleft()

    @QtCore.pyqtSlot()
    def update_plots(self) -> None:
        if self.plot_paused or len(self.channels["time"]) < 2:
            return
        x = np.fromiter(self.channels["time"], dtype=np.float64)
        x -= x[-1]
        for name, curve in self.accel_curves.items():
            curve.setData(x, np.fromiter(self.channels[name], dtype=np.float64))
        for name, curve in self.gyro_curves.items():
            curve.setData(x, np.fromiter(self.channels[name], dtype=np.float64))
        self.temp_curve.setData(x, np.fromiter(self.channels["temp"], dtype=np.float64))
        self.accel_plot.setXRange(-float(self.window_spin.value()), 0.0, padding=0.0)

    @QtCore.pyqtSlot()
    def update_stats(self) -> None:
        if len(self.recent_arrivals) >= 2:
            span = self.recent_arrivals[-1] - self.recent_arrivals[0]
            rate = (len(self.recent_arrivals) - 1) / span if span > 0.0 else 0.0
            self.rate_label.setText(self.tr_text("sample_rate", value=f"{rate:.2f} Hz"))
        else:
            self.rate_label.setText(self.tr_text("sample_rate", value="-- Hz"))
        self.samples_label.setText(
            self.tr_text("valid_frames", value=f"{self.total_samples:,}")
        )
        self.loss_label.setText(self.tr_text("lost_frames", value=f"{self.lost_samples:,}"))
        self.invalid_label.setText(
            self.tr_text("invalid_lines", value=f"{self.invalid_lines:,}")
        )
        self.dt_label.setText(f"dt: {self.last_dt_ms} ms" if self.total_samples else "dt: -- ms")
        if self.channels["temp"]:
            temperature = f"{self.channels['temp'][-1]:.3f} °C"
        else:
            temperature = "-- °C"
        self.temp_label.setText(self.tr_text("temperature_stat", value=temperature))

    @QtCore.pyqtSlot()
    def toggle_plot_pause(self) -> None:
        self.plot_paused = not self.plot_paused
        self.pause_button.setText(
            self.tr_text("resume_plot") if self.plot_paused else self.tr_text("pause_plot")
        )
        self.statusBar().showMessage(
            self.tr_text("plot_paused") if self.plot_paused else self.tr_text("plot_resumed")
        )

    @QtCore.pyqtSlot()
    def clear_data(self) -> None:
        for channel in self.channels.values():
            channel.clear()
        self.last_mcu_time_ms = None
        self.elapsed_seconds = 0.0
        self.last_sample_number = None
        self.total_samples = 0
        self.lost_samples = 0
        self.invalid_lines = 0
        self.last_dt_ms = 0
        self.recent_arrivals.clear()
        for curve in (*self.accel_curves.values(), *self.gyro_curves.values(), self.temp_curve):
            curve.clear()
        self.update_stats()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802 (Qt API name)
        self.disconnect_serial(self.tr_text("app_closed"))
        event.accept()


def main() -> None:
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ImuSerialMonitor()
    window.show()
    raise SystemExit(app.exec_())


if __name__ == "__main__":
    main()
