from __future__ import annotations

import ipaddress
import logging
import os
from pathlib import Path
import queue
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time

import av
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
DATA = Path(os.environ.get("LOCALAPPDATA", str(ROOT))) / "MirrorStage"
DATA.mkdir(parents=True, exist_ok=True)
LOG = logging.getLogger("mirror")
HIDDEN = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
PRESETS = {
    "清晰优先 · 原生 / 60 FPS": (1, 60, 12),
    "无线均衡 · 原生 / 30 FPS": (1, 30, 6),
    "低带宽 · 半分辨率 / 60 FPS": (2, 60, 4),
}


def find_tool(name: str) -> Path:
    override = os.environ.get("MIRROR_" + name.upper())
    candidates = [Path(override)] if override else []
    if name == "hdc":
        candidates.append(ROOT / "vendor/hdc/hdc.exe")
    else:
        candidates.append(ROOT / "runtime/bin/java.exe")
        if os.environ.get("JAVA_HOME"):
            candidates.append(Path(os.environ["JAVA_HOME"]) / "bin/java.exe")
    suffix = "sdk/default/openharmony/toolchains/hdc.exe" if name == "hdc" else "jbr/bin/java.exe"
    for base in (Path("D:/tools/DevEco Studio"), Path("C:/Program Files/Huawei/DevEco Studio")):
        candidates.append(base / suffix)
    found = shutil.which(name)
    if found:
        candidates.append(Path(found))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError(f"未找到 {name}，请安装 DevEco Studio 或设置 MIRROR_{name.upper()} 路径。")


def hdc(*args: str, timeout: float = 8) -> str:
    result = subprocess.run(
        [str(find_tool("hdc")), *args], capture_output=True,
        encoding="utf-8", errors="replace", timeout=timeout, creationflags=HIDDEN,
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode:
        raise RuntimeError(output or f"HDC 返回 {result.returncode}")
    return output


def devices() -> list[dict]:
    rows = hdc("list", "targets", "-v")
    found = []
    for line in rows.splitlines():
        fields = line.split()
        if len(fields) < 3 or fields[2].lower() != "connected":
            continue
        serial, transport = fields[:2]
        name = hdc("-t", serial, "shell", "param", "get", "const.product.name").strip()
        found.append({"serial": serial, "name": name or serial, "wireless": transport.upper() == "TCP"})
    return found


def validate_endpoint(value: str) -> str:
    host, separator, port = value.strip().rpartition(":")
    if not separator or not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ValueError("请输入手机无线调试页中的 IP:端口，例如 192.168.1.8:5555。")
    ipaddress.IPv4Address(host)
    return f"{host}:{int(port)}"


def connect_wifi(endpoint: str) -> str:
    endpoint = validate_endpoint(endpoint)
    try:
        output = hdc("tconn", endpoint, timeout=15)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("无线连接超时。请打开手机无线调试，确认同一 Wi-Fi，并使用手机显示的端口。") from error
    if "Connect OK" not in output and "already" not in output.lower():
        raise RuntimeError(output or "无线连接失败，请核对手机上的地址和端口。")
    return endpoint


def prepare_wifi(serial: str) -> str:
    info = hdc("-t", serial, "shell", "ifconfig", "wlan0")
    match = re.search(r"inet (?:addr:)?(\d+\.\d+\.\d+\.\d+)", info)
    if not match:
        raise RuntimeError("未获取到手机 Wi-Fi 地址。请连接 Wi-Fi，或填写无线调试页面显示的地址。")
    output = hdc("-t", serial, "tmode", "port", "5555")
    if "successful" not in output.lower():
        raise RuntimeError(output or "请在手机开发者选项中手动打开无线调试。")
    return f"{match.group(1)}:5555"


class Task(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, function, parent=None):
        super().__init__(parent)
        self.function = function

    def run(self):
        try:
            self.completed.emit(self.function())
        except Exception as error:
            LOG.exception("Background task failed")
            self.failed.emit(str(error))


class CastWorker(QThread):
    status = Signal(str)
    failed = Signal(str)

    def __init__(self, serial: str, preset: str, parent=None):
        super().__init__(parent)
        self.serial = serial
        self.preset = preset
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.latest: tuple[QImage, int, float] | None = None
        self.frames = 0
        self.bytes_received = 0
        self.decode_ms = 0.0
        self.socket: socket.socket | None = None
        self.process: subprocess.Popen | None = None
        self.started_at = 0.0
        self.first_frame_at = 0.0
        self.last_device_check = 0.0

    def take_frame(self):
        with self.lock:
            frame, self.latest = self.latest, None
            return frame

    def request_stop(self):
        self.stop_event.set()
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def _read(self, length: int) -> bytes:
        data = bytearray()
        while len(data) < length:
            if self.stop_event.is_set():
                raise InterruptedError()
            try:
                chunk = self.socket.recv(length - len(data))
            except socket.timeout:
                if not self.first_frame_at and time.monotonic() - self.started_at > 45:
                    raise RuntimeError("手机尚未返回画面，请解锁手机后重新连接。")
                if self.process.poll() is not None:
                    raise RuntimeError("投屏服务已退出，请重新连接。")
                if time.monotonic() - self.last_device_check > 4:
                    self.last_device_check = time.monotonic()
                    online = hdc("list", "targets", "-v", timeout=4)
                    pattern = rf"^{re.escape(self.serial)}\s+(?:USB|TCP)\s+Connected\b"
                    if not re.search(pattern, online, re.MULTILINE):
                        raise ConnectionError("手机连接已断开，请重新接好数据线或恢复无线网络。")
                continue
            if not chunk:
                raise ConnectionError("视频连接已断开，请检查 USB 线或无线网络。")
            data.extend(chunk)
        return bytes(data)

    def _heartbeat(self):
        while not self.stop_event.wait(3):
            try:
                self.socket.sendall(b"ping\n")
            except OSError:
                return

    def _logs(self, ready: queue.Queue):
        for line in self.process.stdout:
            line = line.decode("utf-8", errors="replace").strip()
            LOG.info("bridge %s", line)
            if line.startswith("CAST_READY "):
                ready.put(int(line.split()[-1]))
        ready.put(None)

    def _forward_rules(self) -> set[tuple[str, str]]:
        rules = set()
        try:
            for line in hdc("fport", "ls", timeout=3).splitlines():
                fields = line.split()
                if len(fields) >= 3 and fields[0] == self.serial and fields[2] in {
                    "localabstract:scrcpy_grpc_socket", "localabstract:uitest_socket",
                }:
                    rules.add((fields[1], fields[2]))
        except Exception:
            LOG.warning("Could not inspect HDC forwards", exc_info=True)
        return rules

    def run(self):
        before = self._forward_rules()
        try:
            self.status.emit("正在建立视频连接…")
            scale, fps, bitrate = PRESETS[self.preset]
            token = secrets.token_hex(24)
            command = [
                str(find_tool("java")), "-Xmx192m", "-Dfile.encoding=UTF-8", "-cp",
                str(ROOT / "vendor/hosScrcpy-1.0.18-beta.jar") + os.pathsep + str(ROOT / "bridge/out"),
                "CastBridge", self.serial, str(find_tool("hdc")), str(scale), str(fps), str(bitrate), token,
            ]
            self.started_at = time.monotonic()
            self.process = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=HIDDEN, cwd=DATA,
            )
            ready = queue.Queue()
            log_thread = threading.Thread(target=self._logs, args=(ready,), daemon=True)
            log_thread.start()
            port = None
            while not self.stop_event.is_set() and time.monotonic() - self.started_at < 30:
                try:
                    port = ready.get(timeout=0.3)
                    break
                except queue.Empty:
                    continue
            if self.stop_event.is_set():
                return
            if port is None:
                raise RuntimeError("投屏服务启动失败。请确认手机已允许 USB 调试授权，日志中有详细原因。")
            self.socket = socket.create_connection(("127.0.0.1", port), timeout=8)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.settimeout(0.5)
            self.socket.sendall((token + "\n").encode())
            threading.Thread(target=self._heartbeat, daemon=True).start()
            decoder = av.CodecContext.create("h264", "r")
            decoder.thread_count = 2
            decoder.thread_type = "SLICE"
            # SDK callback boundaries are complete access units. Save SPS/PPS until
            # the first picture so FFmpeg never receives a config-only packet.
            config = bytearray()
            stats_at = time.monotonic()
            stats_frames = 0
            while not self.stop_event.is_set():
                length = struct.unpack(">I", self._read(4))[0]
                if not 0 < length <= 16 * 1024 * 1024:
                    raise RuntimeError("视频帧数据异常，请重新连接。")
                data = self._read(length)
                self.bytes_received += length
                nal_types = [part[0] & 31 for part in re.split(b"\x00\x00\x00?\x01", data) if part]
                if not any(kind in (1, 5) for kind in nal_types):
                    config.extend(data)
                    if len(config) > 1024 * 1024:
                        raise RuntimeError("视频编码参数异常。")
                    continue
                if config:
                    data = bytes(config) + data
                    config.clear()
                started = time.monotonic()
                for frame in decoder.decode(av.Packet(data)):
                    rgba = frame.reformat(format="bgra")
                    plane = rgba.planes[0]
                    image = QImage(plane, rgba.width, rgba.height, plane.line_size, QImage.Format.Format_ARGB32).copy()
                    self.frames += 1
                    now = time.monotonic()
                    self.decode_ms = (now - started) * 1000
                    if now - stats_at >= 2:
                        LOG.info("Video %.1f fps, decode %.2f ms, %sx%s, total %s frames", (self.frames - stats_frames) / (now - stats_at), self.decode_ms, frame.width, frame.height, self.frames)
                        stats_at, stats_frames = now, self.frames
                    if not self.first_frame_at:
                        self.first_frame_at = now
                        self.status.emit("正在投屏")
                    with self.lock:
                        # Keep one decoded frame. A busy UI never builds a video queue.
                        self.latest = (image, self.frames, now)
        except Exception as error:
            if not self.stop_event.is_set():
                LOG.exception("Capture failed")
                self.failed.emit(str(error))
        finally:
            self.stop_event.set()
            if self.socket:
                self.socket.close()
            if self.process:
                self.process.stdin.close()
                try:
                    self.process.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=3)
                self.process.stdout.close()
            # Remove only this session's newly created capture forwarding entries.
            for local, remote in self._forward_rules() - before:
                try:
                    hdc("-t", self.serial, "fport", "rm", local, remote, timeout=3)
                except Exception:
                    LOG.warning("Forward cleanup failed", exc_info=True)
            LOG.info("Capture ended frames=%s bytes=%s", self.frames, self.bytes_received)
