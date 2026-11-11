from __future__ import annotations

from collections import deque
import logging
import time

from PySide6.QtCore import Qt, QRectF, QTimer, QSettings, QUrl, QSize
from PySide6.QtGui import QColor, QPainter, QPainterPath, QFont, QShortcut, QKeySequence, QDesktopServices, QPixmap, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QComboBox,
    QLineEdit, QVBoxLayout, QHBoxLayout, QSlider, QButtonGroup, QScrollArea,
)

from .backend import CastWorker, Task, PRESETS, ROOT, DATA, devices, connect_wifi, prepare_wifi


STYLE = """
QMainWindow { background: #faf9ed; color: #223d35; }
QWidget#root { background: transparent; }
QWidget { font-family: 'Microsoft YaHei UI'; font-size: 13px; color: #223d35; }
QLabel { background: transparent; }
QLabel#brand { font-size: 25px; font-weight: 700; letter-spacing: 3px; }
QLabel#muted { color: #697b72; font-size: 12px; }
QLabel#section { font-size: 11px; color: #697b72; font-weight: 600; }
QLabel#title { font-size: 20px; font-weight: 600; }
QFrame#panel { background: #fcfcf9; border: 1px solid #dce3db; border-radius: 16px; }
QFrame#divider { background: #dce3db; max-height: 1px; }
QPushButton { border: 1px solid #d6dfd7; background: #fcfcf9; border-radius: 8px; padding: 9px 13px; }
QPushButton:hover { background: #e9efe7; border-color: #9aafa0; }
QPushButton:pressed { background: #dce6dc; }
QPushButton:focus { border: 2px solid #718e7d; }
QPushButton:disabled { color: #849189; background: #eef1eb; border-color: #e1e6df; }
QPushButton#primary { background: #285844; color: #fafbf7; border: 1px solid #285844; font-weight: 600; }
QPushButton#primary:hover { background: #1c4735; }
QPushButton#primary:disabled { background: #9bb0a3; border-color: #9bb0a3; }
QPushButton#tab { border: 0; background: #edf1ea; color: #6c7d73; }
QPushButton#tab:checked { background: #d9e6d9; color: #244f3a; font-weight: 600; }
QComboBox, QLineEdit { background: #fffefa; border: 1px solid #d5dfd5; border-radius: 7px; padding: 9px; min-height: 18px; }
QComboBox:focus, QLineEdit:focus { border-color: #638773; }
QComboBox:disabled { color: #8b968d; }
QComboBox::drop-down { border: 0; width: 22px; }
QComboBox QAbstractItemView { background: #fffefa; selection-background-color: #d9e6d9; selection-color: #244f3a; }
QSlider::groove:horizontal { height: 4px; background: #d7e0d6; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #507962; border-radius: 2px; }
QSlider::handle:horizontal { width: 14px; margin: -5px 0; border-radius: 7px; background: #285844; }
QScrollBar:vertical { border: 0; background: #e6eadc; width: 8px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #abbc95; min-height: 28px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
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


class Backdrop(QWidget):
    def __init__(self):
        super().__init__()
        self.artwork = QPixmap(str(ROOT / "assets/background.png"))
        self.scaled_artwork = QPixmap()
        self.color = None
        self.fitness_theme = False
        self.copy_visible = True
        self.headline_first = QPixmap(str(ROOT / "assets/headline-first.png"))
        self.headline_second = QPixmap(str(ROOT / "assets/headline-second.png"))
        self.subtitle = QPixmap(str(ROOT / "assets/subtitle.png"))

    def set_background(self, filename, color):
        self.color = QColor(color) if color else None
        self.fitness_theme = filename == "fitness-light.png"
        if filename:
            self.artwork = QPixmap(str(ROOT / "assets" / filename))
            self.scale_artwork()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scale_artwork()

    def scale_artwork(self):
        if not self.artwork.isNull():
            physical_size = self.size() * self.devicePixelRatioF()
            self.scaled_artwork = self.artwork.scaled(physical_size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            self.scaled_artwork.setDevicePixelRatio(self.devicePixelRatioF())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.color or QColor("#faf9ed"))
        if self.color is None and not self.scaled_artwork.isNull():
            size = self.scaled_artwork.deviceIndependentSize()
            painter.drawPixmap(round((self.width() - size.width()) / 2), round((self.height() - size.height()) / 2), self.scaled_artwork)
        if self.fitness_theme and self.copy_visible and self.width() >= 1280:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            title_size = round(min(130, self.width() * 0.076))
            title_scale = title_size / 109
            left = self.width() * 0.06
            top = self.height() * 0.32
            line_height = title_size * 1.16
            padding = 8 * title_scale
            painter.drawPixmap(QRectF(left - padding, top - padding, 480 * title_scale, 180 * title_scale),
                               self.headline_first, QRectF(self.headline_first.rect()))
            painter.drawPixmap(QRectF(left + title_size * 0.18 - padding, top + line_height - padding,
                                     480 * title_scale, 180 * title_scale),
                               self.headline_second, QRectF(self.headline_second.rect()))
            subtitle_scale = round(min(32, self.width() * 0.020)) / 29
            painter.drawPixmap(QRectF(left - 8 * subtitle_scale, top + line_height * 2.15 - 8 * subtitle_scale,
                                     480 * subtitle_scale, 64 * subtitle_scale),
                               self.subtitle, QRectF(self.subtitle.rect()))


class BrandHeader(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(108)
        self.competition = QPixmap(str(ROOT / "assets/competition.png"))
        self.harmony = QPixmap(str(ROOT / "assets/harmonyos.png"))
        self.jixfit = QPixmap(str(ROOT / "assets/jixfit.png"))
        self.setAccessibleName("2026 中国高校计算机大赛 人工智能创意赛 · HarmonyOS · 肌智 JixFit")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        factor = min(1.0, self.width() / 1100)
        # Multiply composites the supplied white-backed marks onto the backdrop.
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        left = QRectF(24, 10, 292 * factor, 292 * factor / 3.006)
        painter.drawPixmap(left, self.competition, QRectF(self.competition.rect()))
        right = self.width() - 28
        icon_size = 54 * factor
        word_width = 108 * factor
        icon_x = right - word_width - icon_size - 12
        harmony_width = 180 * factor
        harmony_height = harmony_width * 58 / 241
        harmony_x = icon_x - 24 - harmony_width
        painter.drawPixmap(QRectF(harmony_x, 48 - harmony_height / 2, harmony_width, harmony_height), self.harmony, QRectF(self.harmony.rect()))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.drawPixmap(QRectF(icon_x, 48 - icon_size / 2, icon_size, icon_size), self.jixfit, QRectF(self.jixfit.rect()))
        painter.setPen(QColor("#15241e"))
        font = QFont("Microsoft YaHei UI")
        font.setPixelSize(round(25 * factor))
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        text_x = icon_x + icon_size + 12
        painter.drawText(QRectF(text_x, 20, word_width, 36), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "肌智")
        font.setPixelSize(round(17 * factor))
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor("#3f5e38"))
        painter.drawText(QRectF(text_x, 55, word_width, 25), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "JixFit")


class Stage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.scale = 100
        self.panel_visible = False
        self.message = "等待手机连接"
        self.detail = "连接 USB 数据线，并在手机上允许调试"
        self.setMinimumHeight(280)
        self.setAccessibleName("手机实时画面")
        self.frame_bounds = self.rect()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = (self.image.width(), self.image.height()) if self.image else (720, 1604)
        # Keep the phone centered on the entire window. Controls live to its left.
        available_width = self.width() * (0.40 if width < height else 0.72)
        if self.panel_visible:
            available_width = min(available_width, max(180, self.width() - 600))
        # Large windows leave the center of the logo row available to the phone.
        # Compact windows reserve that row to avoid covering the corner marks.
        top_inset = 108 if self.width() < 1280 else 0
        display_area = QRectF(0, top_inset, self.width(), self.height() - top_inset)
        factor = min(available_width / width, (display_area.height() - 40) / height) * self.scale / 100
        rect = QRectF(0, 0, width * factor, height * factor)
        rect.moveCenter(display_area.center())
        frame = rect.adjusted(-7, -7, 7, 7)
        shadow = frame.translated(0, 6).adjusted(-3, -3, 3, 3)
        corner_radius = min(48, min(rect.width(), rect.height()) * 0.10)
        self.frame_bounds = frame.united(shadow).adjusted(-2, -2, 2, 2).toAlignedRect()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(32, 60, 44, 18))
        painter.drawRoundedRect(shadow, corner_radius + 10, corner_radius + 10)
        painter.setBrush(QColor("#283a32"))
        painter.drawRoundedRect(frame, corner_radius + 7, corner_radius + 7)
        path = QPainterPath()
        path.addRoundedRect(rect, corner_radius, corner_radius)
        painter.setClipPath(path)
        if self.image:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(rect, self.image)
        else:
            painter.fillRect(rect, QColor("#f8faf5"))
            painter.setPen(QColor("#b9cbb9"))
            painter.setFont(QFont("Microsoft YaHei UI", 38))
            painter.drawText(rect.adjusted(0, -70, 0, -70), Qt.AlignmentFlag.AlignCenter, "JF")
            painter.setPen(QColor("#345b44"))
            painter.setFont(QFont("Microsoft YaHei UI", 12, QFont.Weight.DemiBold))
            painter.drawText(rect.adjusted(12, 0, -12, 0), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.message)
            painter.setPen(QColor("#718273"))
            painter.setFont(QFont("Microsoft YaHei UI", 9))
            painter.drawText(rect.adjusted(20, 75, -20, 75), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.detail)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("肌智 JixFit · 演示投屏")
        self.setWindowIcon(QIcon(str(ROOT / "assets/jixfit.png")))
        self.settings = QSettings("MirrorStage", "MirrorStage")
        self.worker = None
        self.tasks = set()
        self.wanted = False
        self.retry_count = 0
        self.closing = False
        self.presentation = False
        self.controls_visible = False
        self.frame_times = deque(maxlen=240)
        self.last_image_time = 0.0
        self.all_devices = []
        self.current_serial = None
        self.auto_start = True
        self.root = Backdrop()
        self.root.setObjectName("root")
        self.setCentralWidget(self.root)
        outer = QVBoxLayout(self.root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = BrandHeader()
        self.header.setParent(self.root)
        self.header.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.stage = Stage()
        outer.addWidget(self.stage, 1)

        self.panel = QFrame(self.stage)
        self.panel.setObjectName("panel")
        self.panel.setFixedWidth(258)
        controls = QVBoxLayout(self.panel)
        controls.setContentsMargins(20, 24, 20, 22)
        controls.setSpacing(14)
        controls.addWidget(label("投屏设置", "title"))
        self.connection_label = label("准备连接", "muted", True)
        controls.addWidget(self.connection_label)
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
        wifi_layout.setContentsMargins(0, 0, 0, 0)
        wifi_layout.setSpacing(8)
        self.address = QLineEdit(str(self.settings.value("wireless_address", "")))
        self.address.setPlaceholderText("手机 IP:端口")
        self.address.setAccessibleName("无线调试 IP 地址和端口")
        wifi_layout.addWidget(self.address)
        self.wifi_connect = button("连接无线设备", self.join_wifi)
        wifi_layout.addWidget(self.wifi_connect)
        self.prepare_button = button("通过 USB 获取无线地址", self.prepare_wireless)
        wifi_layout.addWidget(self.prepare_button)
        controls.addWidget(self.wifi_box)
        self.wifi_box.hide()

        controls.addWidget(label("投屏设备", "section"))
        self.device_combo = QComboBox()
        self.device_combo.setAccessibleName("选择投屏设备")
        self.device_combo.setMinimumContentsLength(10)
        self.device_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        controls.addWidget(self.device_combo)
        self.refresh_button = button("刷新设备", self.refresh_devices)
        controls.addWidget(self.refresh_button)
        controls.addWidget(label("视频画质", "section"))
        self.quality = QComboBox()
        self.quality.addItems(PRESETS)
        self.quality.setAccessibleName("视频画质")
        controls.addWidget(self.quality)
        self.start_button = button("开始投屏", self.toggle_capture, "primary")
        controls.addWidget(self.start_button)
        self.hint = label("优先使用有线连接", "muted", True)
        self.hint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        controls.addWidget(self.hint)
        self.panel.adjustSize()

        self.panel_scroll = QScrollArea(self.stage)
        self.panel_scroll.setWidget(self.panel)
        self.panel_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.panel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.panel_scroll.viewport().setObjectName("controlsViewport")
        self.panel_scroll.setStyleSheet("QScrollArea { background: transparent; border: 0; } QWidget#controlsViewport { background: transparent; }")
        self.panel_scroll.hide()

        self.footer = QWidget()
        footer = QHBoxLayout(self.footer)
        footer.setContentsMargins(30, 10, 28, 14)
        footer.setSpacing(14)
        self.status_label = label("尚未投屏")
        footer.addWidget(self.status_label)
        self.metrics = label("", "muted")
        footer.addWidget(self.metrics)
        footer.addStretch()
        footer.addWidget(label("画面大小", "muted"))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(60, 100)
        self.slider.setValue(100)
        self.slider.setFixedWidth(100)
        self.slider.setAccessibleName("画面大小，60% 到 100%")
        self.slider.valueChanged.connect(self.resize_picture)
        footer.addWidget(self.slider)
        self.theme = QComboBox()
        self.theme.addItems(["PPT 背景", "浅苔绿", "暖米白", "雾蓝灰", "智能健身"])
        self.theme.setAccessibleName("展示背景")
        self.theme.currentIndexChanged.connect(self.change_background)
        footer.addWidget(self.theme)
        self.controls_button = button("显示控制台  C", self.toggle_controls)
        footer.addWidget(self.controls_button)
        self.focus_button = button("全屏展示  F11", self.toggle_presentation)
        footer.addWidget(self.focus_button)
        self.log_button = button("日志", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA))))
        controls.addWidget(self.log_button)
        outer.addWidget(self.footer)
        self.setStyleSheet(STYLE)
        self.setMinimumSize(860, 600)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1440, int(screen.width() * 0.94)), int(screen.height() * 0.94))
        self.move(screen.center() - self.rect().center())
        self.theme.setCurrentIndex(int(self.settings.value("display_background", 4)))
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
        if self.wanted or self.worker:
            self.stop_capture()
        self.wifi_box.setVisible(wireless)
        self.instructions.setText(
            "手机和电脑连接同一 Wi-Fi，在手机开发者选项中打开无线调试。" if wireless
            else "用数据线连接手机，开启 USB 调试并允许电脑连接。"
        )
        self.quality.setCurrentIndex(1 if wireless else 0)
        self.populate_devices()
        self.position_panel()

    def position_panel(self):
        self.header.setGeometry(0, 0, self.root.width(), 108)
        self.header.raise_()
        self.panel.adjustSize()
        available_height = max(100, self.stage.height() - 140)
        height = min(self.panel.height(), available_height)
        panel_top = 108 + max(16, (self.stage.height() - 108 - height) // 2)
        self.panel_scroll.setGeometry(24, panel_top, 276, height)
        # Compact windows retain all controls and place the picture to their right.
        self.stage.panel_visible = self.panel_scroll.isVisible()
        portrait = self.stage.image is None or self.stage.image.width() < self.stage.image.height()
        self.root.copy_visible = not self.controls_visible and portrait
        self.root.update()
        self.stage.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.position_panel)

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
        self.refresh_button.setEnabled(True)
        self.populate_devices()
        if self.device_combo.count():
            self.hint.setText("在手机上操作，电脑会同步显示。")
        else:
            self.hint.setText("尚未找到设备，请检查调试授权后刷新。")
        if self.auto_start:
            self.auto_start = False
            usb = [item for item in found if not item["wireless"]]
            if len(usb) == 1:
                self.start_capture()

    def populate_devices(self):
        selected = self.device_combo.currentData()
        self.device_combo.clear()
        for item in self.all_devices:
            if item["wireless"] == self.wifi_tab.isChecked():
                self.device_combo.addItem(item["name"], item["serial"])
                self.device_combo.setItemData(self.device_combo.count() - 1, item["serial"], Qt.ItemDataRole.ToolTipRole)
        index = self.device_combo.findData(selected)
        if index >= 0:
            self.device_combo.setCurrentIndex(index)
        self.start_button.setEnabled(bool(self.device_combo.count()) or self.wanted)

    def join_wifi(self):
        value = self.address.text()
        self.wifi_connect.setEnabled(False)
        self.hint.setText("正在连接无线调试…")
        def done(endpoint):
            self.settings.setValue("wireless_address", endpoint)
            self.wifi_connect.setEnabled(True)
            self.refresh_devices()
        def failed(message):
            self.wifi_connect.setEnabled(True)
            self.show_error(message)
        self.run_task(lambda: connect_wifi(value), done, failed)

    def prepare_wireless(self):
        usb = [item for item in self.all_devices if not item["wireless"]]
        if len(usb) != 1:
            self.show_error("请先连接一台 USB 手机并点击刷新设备，然后获取无线地址。")
            return
        self.prepare_button.setEnabled(False)
        def done(endpoint):
            self.prepare_button.setEnabled(True)
            self.address.setText(endpoint)
            self.hint.setText("已获取地址，请点击连接无线设备，并留意手机授权提示。")
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

    def start_capture(self):
        if self.closing or self.worker:
            return
        serial = self.device_combo.currentData()
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
        self.quality.setEnabled(False)
        self.start_button.setText("停止投屏")
        self.start_button.setEnabled(True)
        self.worker = CastWorker(serial, self.quality.currentText(), self)
        self.worker.status.connect(self.on_status)
        self.worker.failed.connect(self.capture_error)
        self.worker.finished.connect(self.capture_finished)
        self.worker.start()

    def on_status(self, message):
        self.status_label.setText(message)
        if message == "正在投屏":
            self.connection_label.setText(("Wi-Fi 无线" if self.wifi_tab.isChecked() else "USB 有线") + "  ·  " + self.device_combo.currentText())
            self.hint.setText("已连接。按 F11 进入比赛展示，按 C 显示或隐藏控制台。")

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
        self.device_combo.setEnabled(True)
        self.quality.setEnabled(True)
        self.start_button.setEnabled(bool(self.device_combo.count()))
        self.start_button.setText("开始投屏")
        self.connection_label.setText("已断开")
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
        self.panel_scroll.show()
        self.footer.show()
        self.controls_button.setText("隐藏控制台  C")
        self.position_panel()

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
                self.position_panel()

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

    def change_background(self, index):
        backgrounds = [
            ("background.png", None),
            (None, "#edf2ec"),
            (None, "#f3efe5"),
            (None, "#eaf0f3"),
            ("fitness-light.png", None),
        ]
        self.root.set_background(*backgrounds[index])
        self.settings.setValue("display_background", index)

    def toggle_controls(self):
        self.controls_visible = not self.controls_visible
        self.panel_scroll.setVisible(self.controls_visible)
        self.footer.setVisible(self.controls_visible or not self.presentation)
        self.controls_button.setText("隐藏控制台  C" if self.controls_visible else "显示控制台  C")
        self.position_panel()

    def toggle_presentation(self):
        self.presentation = not self.presentation
        if self.presentation:
            self.controls_visible = False
        self.panel_scroll.setVisible(self.controls_visible)
        self.footer.setVisible(not self.presentation)
        self.controls_button.setText("隐藏控制台  C" if self.controls_visible else "显示控制台  C")
        self.focus_button.setText("退出全屏  Esc" if self.presentation else "全屏展示  F11")
        if self.presentation:
            self.showFullScreen()
        else:
            self.showNormal()
        self.position_panel()

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
