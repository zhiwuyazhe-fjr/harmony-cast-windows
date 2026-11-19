from __future__ import annotations

from collections import Counter, deque
import time

from PySide6.QtCore import Qt, QRectF, QTimer, QSettings, QUrl, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QShortcut, QKeySequence, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QComboBox,
    QLineEdit, QVBoxLayout, QHBoxLayout, QSlider, QButtonGroup, QScrollArea,
)

from .backend import CastWorker, Task, PRESETS, ROOT, DATA, devices, prepare_wifi, validate_endpoint


BACKGROUNDS = {"雾蓝": "#e8eff4", "暖白": "#f4f2ed", "石墨": "#262e36"}

STYLE = """
QMainWindow, QWidget#root, QWidget#header, QWidget#footer, QWidget#panel { background: #fcfdfe; }
QWidget { font-family: 'Microsoft YaHei UI'; font-size: 13px; color: #213445; }
QLabel { background: transparent; }
QLabel#brand { font-size: 21px; font-weight: 700; }
QLabel#muted { color: #536878; font-size: 12px; }
QLabel#section { color: #364d5e; font-weight: 600; }
QLabel#title { font-size: 18px; font-weight: 600; }
QWidget#header { border-bottom: 1px solid #d7e1e7; }
QWidget#footer { border-top: 1px solid #d7e1e7; }
QPushButton { border: 1px solid #c8d5df; background: #fcfdfe; border-radius: 6px; padding: 8px 12px; }
QPushButton:hover { background: #edf4f7; border-color: #8aa6b6; }
QPushButton:pressed { background: #dce8ef; }
QPushButton:focus { border: 1px solid #186b87; }
QPushButton:disabled { color: #708391; background: #edf1f4; border-color: #d8e2e8; }
QPushButton#primary { background: #195f7b; color: #ffffff; border-color: #195f7b; font-weight: 600; }
QPushButton#primary:hover { background: #104d65; }
QPushButton#primary:disabled { background: #dde7ed; border-color: #dde7ed; color: #566b79; }
QPushButton#tab { border: 1px solid #cbd7de; background: #fcfdfe; }
QPushButton#tab:checked { background: #e0eef4; color: #144f69; border-color: #83acbf; font-weight: 600; }
QComboBox, QLineEdit { background: #fcfdfe; border: 1px solid #c8d5df; border-radius: 6px; padding: 7px; min-height: 18px; }
QComboBox:focus, QLineEdit:focus { border-color: #186b87; }
QComboBox:disabled { color: #708391; }
QComboBox::drop-down { border: 0; width: 20px; }
QComboBox QAbstractItemView { background: #fcfdfe; selection-background-color: #e0eef4; selection-color: #144f69; }
QSlider::groove:horizontal { height: 4px; background: #d9e2e7; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #528399; border-radius: 2px; }
QSlider::handle:horizontal { width: 14px; margin: -5px 0; border-radius: 7px; background: #195f7b; }
"""


def label(text, name=None, wrap=False):
    result = QLabel(text)
    if name:
        result.setObjectName(name)
    result.setWordWrap(wrap)
    return result


def button(text, callback, name=None):
    result = QPushButton(text)
    if name:
        result.setObjectName(name)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    result.clicked.connect(callback)
    return result


class Stage(QWidget):
    def __init__(self):
        super().__init__()
        self.image = None
        self.scale = 100
        self.background = QColor(BACKGROUNDS["雾蓝"])
        self.message = "等待手机连接"
        self.detail = "连接并授权手机后，即可在这里查看屏幕。"
        self.setMinimumSize(260, 200)
        self.setAccessibleName("手机屏幕预览")
        self.frame_bounds = self.rect()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(event.rect(), self.background)
        if self.image:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            area = QRectF(self.rect()).adjusted(12, 12, -12, -12)
            factor = min(area.width() / self.image.width(), area.height() / self.image.height()) * self.scale / 100
            target = QRectF(0, 0, self.image.width() * factor, self.image.height() * factor)
            target.moveCenter(area.center())
            self.frame_bounds = target.toAlignedRect()
            painter.drawImage(target, self.image)
            return

        dark = self.background.lightness() < 128
        ink = QColor("#ecf3f6" if dark else "#304d60")
        muted = QColor("#b9cbd5" if dark else "#536c7c")
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.save()
        painter.translate(self.width() / 2, self.height() / 2 - 38)
        painter.setPen(QPen(muted, 2.5))
        painter.drawRoundedRect(QRectF(-53, -29, 88, 54), 5, 5)
        painter.drawLine(-9, 25, -9, 34)
        painter.drawLine(-26, 34, 8, 34)
        painter.setBrush(self.background)
        painter.setPen(QPen(ink, 3))
        painter.drawRoundedRect(QRectF(17, -9, 32, 56), 5, 5)
        painter.drawLine(29, 39, 37, 39)
        painter.restore()
        painter.setPen(ink)
        painter.setFont(QFont("Microsoft YaHei UI", 15, QFont.Weight.DemiBold))
        painter.drawText(QRectF(12, self.height() / 2 + 20, self.width() - 24, 36), Qt.AlignmentFlag.AlignCenter, self.message)
        painter.setPen(muted)
        painter.setFont(QFont("Microsoft YaHei UI", 10))
        painter.drawText(QRectF(12, self.height() / 2 + 60, self.width() - 24, 52),
                         Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, self.detail)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("鸿蒙手机连接助手")
        self.setWindowIcon(QIcon(str(ROOT / "installer/harmony-cast.ico")))
        self.settings = QSettings("HarmonyCast", "HarmonyCast")
        self.worker = None
        self.tasks = set()
        self.wanted = False
        self.retry_count = 0
        self.closing = False
        self.presentation = False
        self.controls_visible = True
        self.controls_before_fullscreen = True
        self.frame_times = deque(maxlen=240)
        self.last_image_time = 0.0
        self.all_devices = []
        self.current_serial = None
        self.auto_start = True

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.header = QWidget()
        self.header.setObjectName("header")
        bar = QHBoxLayout(self.header)
        bar.setContentsMargins(24, 14, 20, 14)
        bar.setSpacing(12)
        mark = QLabel()
        mark.setPixmap(self.windowIcon().pixmap(36, 36))
        bar.addWidget(mark)
        bar.addWidget(label(self.windowTitle(), "brand"))
        bar.addStretch()
        self.controls_button = button("隐藏连接面板  C", self.toggle_controls)
        self.focus_button = button("全屏  F11", self.toggle_presentation)
        bar.addWidget(self.controls_button)
        bar.addWidget(self.focus_button)
        outer.addWidget(self.header)

        workspace = QHBoxLayout()
        workspace.setContentsMargins(0, 0, 0, 0)
        workspace.setSpacing(0)
        outer.addLayout(workspace, 1)
        self.panel = QWidget()
        self.panel.setObjectName("panel")
        controls = QVBoxLayout(self.panel)
        controls.setContentsMargins(20, 24, 20, 20)
        controls.setSpacing(8)
        controls.addWidget(label("连接方式", "title"))
        tabs = QHBoxLayout()
        tabs.setSpacing(6)
        self.usb_tab = button("USB 有线", lambda: self.set_mode(False), "tab")
        self.wifi_tab = button("Wi-Fi 无线", lambda: self.set_mode(True), "tab")
        group = QButtonGroup(self)
        for item in (self.usb_tab, self.wifi_tab):
            item.setCheckable(True)
            group.addButton(item)
            tabs.addWidget(item)
        self.usb_tab.setChecked(True)
        controls.addLayout(tabs)
        self.instructions = label("用数据线连接手机，开启 USB 调试并允许电脑连接。", "muted", True)
        controls.addWidget(self.instructions)

        self.wifi_box = QWidget()
        wifi_layout = QVBoxLayout(self.wifi_box)
        wifi_layout.setContentsMargins(0, 4, 0, 0)
        wifi_layout.setSpacing(8)
        self.address = QLineEdit(str(self.settings.value("wireless_address", "")))
        self.address.setPlaceholderText("手机 IPv4 地址:端口")
        self.address.setAccessibleName("无线调试 IP 地址和端口")
        wifi_layout.addWidget(self.address)
        self.wifi_connect = button("连接并投屏", self.join_wifi)
        wifi_layout.addWidget(self.wifi_connect)
        self.prepare_button = button("通过 USB 获取无线地址", self.prepare_wireless)
        wifi_layout.addWidget(self.prepare_button)
        controls.addWidget(self.wifi_box)
        self.wifi_box.hide()

        controls.addSpacing(12)
        controls.addWidget(label("投屏设备", "section"))
        device_row = QHBoxLayout()
        self.device_combo = QComboBox()
        self.device_combo.setAccessibleName("选择投屏设备")
        self.device_combo.setPlaceholderText("未发现设备")
        self.device_combo.setMinimumContentsLength(6)
        self.device_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        device_row.addWidget(self.device_combo, 1)
        self.refresh_button = button("刷新设备", self.refresh_devices)
        device_row.addWidget(self.refresh_button)
        controls.addLayout(device_row)
        controls.addSpacing(8)
        controls.addWidget(label("视频画质", "section"))
        self.quality = QComboBox()
        self.quality.addItems(PRESETS)
        self.quality.setAccessibleName("视频画质")
        controls.addWidget(self.quality)
        controls.addSpacing(12)
        self.start_button = button("开始投屏", self.toggle_capture, "primary")
        self.start_button.setEnabled(False)
        controls.addWidget(self.start_button)
        self.hint = label("", "muted", True)
        self.hint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        controls.addWidget(self.hint)
        controls.addStretch()
        self.log_button = button("打开日志目录", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA))))
        controls.addWidget(self.log_button)

        self.panel_scroll = QScrollArea()
        self.panel_scroll.setWidget(self.panel)
        self.panel_scroll.setWidgetResizable(True)
        self.panel_scroll.setFixedWidth(296)
        self.panel_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.panel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        workspace.addWidget(self.panel_scroll)
        self.stage = Stage()
        workspace.addWidget(self.stage, 1)

        self.footer = QWidget()
        self.footer.setObjectName("footer")
        footer = QHBoxLayout(self.footer)
        footer.setContentsMargins(20, 8, 20, 8)
        footer.setSpacing(12)
        self.status_label = label("尚未投屏")
        footer.addWidget(self.status_label)
        self.metrics = label("", "muted")
        footer.addWidget(self.metrics)
        footer.addStretch()
        footer.addWidget(label("画面大小", "muted"))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(60, 100)
        self.slider.setValue(100)
        self.slider.setFixedWidth(88)
        self.slider.setAccessibleName("画面大小，60% 到 100%")
        self.slider.valueChanged.connect(self.resize_picture)
        footer.addWidget(self.slider)
        footer.addWidget(label("背景", "muted"))
        self.theme = QComboBox()
        self.theme.addItems(BACKGROUNDS)
        self.theme.setAccessibleName("预览背景")
        self.theme.setCurrentText(str(self.settings.value("preview_background", "雾蓝")))
        self.stage.background = QColor(BACKGROUNDS[self.theme.currentText()])
        self.theme.currentTextChanged.connect(self.change_background)
        footer.addWidget(self.theme)
        outer.addWidget(self.footer)

        self.setStyleSheet(STYLE)
        self.setMinimumSize(720, 480)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1160, int(screen.width() * 0.94)), min(780, int(screen.height() * 0.92)))
        self.move(screen.center() - self.rect().center())
        QShortcut(QKeySequence("F11"), self, self.toggle_presentation)
        QShortcut(QKeySequence("Escape"), self, self.exit_presentation)
        QShortcut(QKeySequence("C"), self, self.toggle_controls)
        self.paint_timer = QTimer(self)
        self.paint_timer.timeout.connect(self.update_frame)
        self.paint_timer.start(8)
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self.update_metrics)
        self.stats_timer.start(1000)
        self.retry_timer = QTimer(self)
        self.retry_timer.setSingleShot(True)
        self.retry_timer.timeout.connect(self.start_capture)
        QTimer.singleShot(100, self.refresh_devices)

    def run_task(self, function, success, error=None):
        task = Task(function, self)
        self.tasks.add(task)
        task.completed.connect(success)
        task.failed.connect(error or self.show_error)
        task.finished.connect(lambda: self.tasks.discard(task))
        task.finished.connect(task.deleteLater)
        task.start()

    def set_mode(self, wireless):
        self.auto_start = False
        if self.wanted or self.worker:
            self.stop_capture()
        self.wifi_box.setVisible(wireless)
        self.instructions.setText(
            "手机和电脑连接同一 Wi-Fi，在手机开发者选项中打开无线调试。" if wireless
            else "用数据线连接手机，开启 USB 调试并允许电脑连接。"
        )
        self.quality.setCurrentIndex(1 if wireless else 0)
        self.populate_devices()
        if not self.worker:
            self.hint.setText("填写手机无线调试页上的地址，或通过 USB 获取地址。" if wireless
                              else "连接并授权手机后，点击刷新设备。")

    def refresh_devices(self):
        if not self.refresh_button.isEnabled():
            return
        self.refresh_button.setEnabled(False)
        self.hint.setText("正在查找已授权的手机…")
        self.run_task(devices, self.on_devices, self.discovery_error)

    def discovery_error(self, message):
        self.refresh_button.setEnabled(True)
        self.show_error(message)

    def on_devices(self, found):
        self.all_devices = found
        if self.wanted or self.worker or self.closing:
            return
        self.refresh_button.setEnabled(True)
        self.populate_devices()
        if self.device_combo.count():
            self.hint.setText("在手机上操作，电脑会同步显示。")
        else:
            self.hint.setText("尚未找到设备，请检查调试授权后刷新。")
        if self.auto_start:
            self.auto_start = False
            usb = [item for item in found if not item["wireless"]]
            if len(usb) == 1 and self.usb_tab.isChecked():
                self.start_capture()

    def populate_devices(self):
        selected = self.device_combo.currentData()
        self.device_combo.clear()
        visible = [item for item in self.all_devices if item["wireless"] == self.wifi_tab.isChecked()]
        name_counts = Counter(item["name"] for item in visible)
        for item in visible:
            name = item["name"]
            if name_counts[name] > 1:
                name = f"{name} · {item['serial']}"
            self.device_combo.addItem(name, item["serial"])
            self.device_combo.setItemData(self.device_combo.count() - 1, item["serial"], Qt.ItemDataRole.ToolTipRole)
        index = self.device_combo.findData(selected)
        if visible:
            self.device_combo.setCurrentIndex(max(index, 0))
        self.start_button.setEnabled(bool(self.device_combo.count()) or self.wanted)

    def join_wifi(self):
        try:
            endpoint = validate_endpoint(self.address.text())
        except ValueError as error:
            self.show_error(str(error))
            return
        self.retry_count = 0
        self.start_capture(endpoint)

    def prepare_wireless(self):
        usb = [item for item in self.all_devices if not item["wireless"]]
        if len(usb) != 1:
            self.show_error("请先连接一台 USB 手机并点击刷新设备，然后获取无线地址。")
            return
        self.prepare_button.setEnabled(False)
        def done(endpoint):
            self.prepare_button.setEnabled(True)
            self.address.setText(endpoint)
            self.hint.setText("已获取地址，请点击「连接并投屏」，并留意手机授权提示。")
        def failed(message):
            self.prepare_button.setEnabled(True)
            self.show_error(message)
        self.run_task(lambda: prepare_wifi(usb[0]["serial"]), done, failed)

    def toggle_capture(self):
        if self.wanted:
            self.stop_capture()
        else:
            self.retry_count = 0
            self.start_capture()

    def start_capture(self, serial=None):
        if self.closing or self.worker:
            return
        if serial is None:
            serial = self.current_serial if self.wanted else self.device_combo.currentData()
        if not serial:
            self.show_error("请先连接手机并刷新设备。")
            return
        self.current_serial = serial
        self.wanted = True
        self.frame_times.clear()
        self.stage.image = None
        self.stage.message = "正在连接手机"
        self.stage.detail = "首次启动需要几秒钟"
        self.stage.update()
        self.device_combo.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.wifi_box.setEnabled(False)
        self.quality.setEnabled(False)
        self.start_button.setText("停止投屏")
        self.start_button.setEnabled(True)
        self.worker = CastWorker(serial, self.quality.currentText(), self, wireless=self.wifi_tab.isChecked())
        self.worker.status.connect(self.on_status)
        self.worker.failed.connect(self.capture_error)
        self.worker.finished.connect(self.capture_finished)
        self.worker.start()

    def on_status(self, message):
        if not self.wanted:
            return
        self.status_label.setText(message)
        if message == "正在投屏":
            if self.worker and self.worker.wireless:
                self.settings.setValue("wireless_address", self.current_serial)
                self.address.setText(self.current_serial)
                if not any(item["serial"] == self.current_serial for item in self.all_devices):
                    self.all_devices.append({"serial": self.current_serial, "name": self.current_serial, "wireless": True})
                self.populate_devices()
                self.device_combo.setCurrentIndex(self.device_combo.findData(self.current_serial))
            self.hint.setText(f"已连接 {self.device_combo.currentText()}。在手机上操作即可同步画面。")

    def stop_capture(self):
        self.wanted = False
        self.retry_timer.stop()
        self.start_button.setEnabled(False)
        self.start_button.setText("正在停止…")
        self.status_label.setText("正在停止投屏…")
        if self.worker:
            self.worker.request_stop()
        else:
            self.capture_finished()

    def capture_error(self, message):
        self.stage.image = None
        self.stage.message = "连接已中断"
        self.stage.detail = "请检查数据线或无线网络"
        self.stage.update()
        self.show_error(message)

    def capture_finished(self):
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        self.metrics.setText("")
        self.stage.image = None
        if self.closing:
            return
        if self.wanted and self.retry_count < 3:
            self.retry_count += 1
            self.status_label.setText(f"正在重连（{self.retry_count}/3）…")
            self.start_button.setText("取消重连")
            self.retry_timer.start(2000)
        else:
            self.wanted = False
            self.device_combo.setEnabled(True)
            self.refresh_button.setEnabled(True)
            self.wifi_box.setEnabled(True)
            self.quality.setEnabled(True)
            self.start_button.setEnabled(bool(self.device_combo.count()))
            self.start_button.setText("开始投屏")
            self.status_label.setText("已停止投屏")
            if not self.retry_count:
                self.hint.setText("投屏已停止，可调整画质后重新连接。")
            self.stage.message = "等待手机连接"
            self.stage.detail = "点击开始投屏"
        self.stage.update()

    def show_error(self, message):
        self.hint.setText(message)
        self.status_label.setText("请检查连接")
        self.controls_visible = True
        self.update_controls()

    def update_frame(self):
        if not self.worker:
            return
        frame = self.worker.take_frame()
        if frame:
            previous_size = self.stage.image.size() if self.stage.image else QSize()
            self.stage.image, count, timestamp = frame
            self.last_image_time = timestamp
            self.frame_times.append((timestamp, count))
            if previous_size == self.stage.image.size():
                self.stage.update(self.stage.frame_bounds)
            else:
                self.stage.update()

    def update_metrics(self):
        if not self.worker or not self.worker.frames:
            return
        now = time.monotonic()
        while self.frame_times and self.frame_times[0][0] < now - 2:
            self.frame_times.popleft()
        fps = 0.0
        if len(self.frame_times) >= 2:
            elapsed = self.frame_times[-1][0] - self.frame_times[0][0]
            fps = (self.frame_times[-1][1] - self.frame_times[0][1]) / max(0.01, elapsed)
        image = self.stage.image
        size = f"{image.width()} × {image.height()}" if image else ""
        activity = f"{fps:.0f} FPS" if now - self.last_image_time < 2 else "画面静止"
        self.metrics.setText(f"{size}  ·  {activity}  ·  H.264")

    def resize_picture(self, value):
        self.stage.scale = value
        self.stage.update()

    def change_background(self, name):
        self.stage.background = QColor(BACKGROUNDS[name])
        self.settings.setValue("preview_background", name)
        self.stage.update()

    def update_controls(self):
        show_bars = self.controls_visible or not self.presentation
        self.panel_scroll.setVisible(self.controls_visible)
        self.header.setVisible(show_bars)
        self.footer.setVisible(show_bars)
        self.controls_button.setText("隐藏连接面板  C" if self.controls_visible else "显示连接面板  C")
        self.focus_button.setText("退出全屏  Esc" if self.presentation else "全屏  F11")

    def toggle_controls(self):
        self.controls_visible = not self.controls_visible
        self.update_controls()

    def toggle_presentation(self):
        self.presentation = not self.presentation
        if self.presentation:
            self.controls_before_fullscreen = self.controls_visible
            self.controls_visible = False
            self.showFullScreen()
        else:
            self.controls_visible = self.controls_before_fullscreen
            self.showNormal()
        self.update_controls()

    def exit_presentation(self):
        if self.presentation:
            self.toggle_presentation()

    def closeEvent(self, event):
        self.closing = True
        self.wanted = False
        self.retry_timer.stop()
        self.paint_timer.stop()
        if self.worker:
            self.worker.request_stop()
        if self.worker or self.tasks:
            event.ignore()
            self.hide()
            QTimer.singleShot(100, self.finish_close)
        else:
            event.accept()
            QApplication.instance().quit()

    def finish_close(self):
        if self.worker or self.tasks:
            QTimer.singleShot(100, self.finish_close)
        else:
            QApplication.instance().quit()
