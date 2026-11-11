# 第三方组件

应用使用以下组件。各组件的版权和许可归其原作者所有。

## HOScrcpy 1.0.18-beta

H.264 投屏内核来自华为开发者社区的 HOScrcpy，通过其 Java API 接入。

- 上游项目 https://gitcode.com/OpenHarmonyToolkitsPlaza/HOScrcpy
- 本次获取路径 https://github.com/ns-zzj/dsh-hos-scrcpy/tree/main/resources
- 版本文件 `vendor/hosScrcpy-1.0.18-beta.jar`
- 获取时分发仓库提交为 `0b327aeac7a3280d043825addbffb1d594807000`，JAR SHA-256 为 `2ce60b1893cc2be471a8cd7eab7e4127e41921f1f89a32a134c730ba15c8c0fd`。
- 该分发源附带的上游 MIT 许可全文与版权说明已原样保存在 `vendor/HOScrcpy-NOTICE.md`。
- Java 桥接和 Windows 展示界面为本项目实现。

## OpenHarmony HDC

来自本机 DevEco Studio SDK，包含 `hdc.exe` 和 `libusb_shared.dll`。SDK 随附许可声明保存在 `vendor/hdc/NOTICE.txt`。

- 项目 https://gitee.com/openharmony/developtools_hdc

## Qt for Python / PySide6 Essentials 6.12.0

采用动态库方式使用 Qt Widgets，按 LGPLv3 许可使用。Python 依赖可通过 `requirements.txt` 安装和替换。

- 项目与源码 https://code.qt.io/pyside/pyside-setup.git/
- 许可 https://doc.qt.io/qtforpython-6/licenses.html

## PyAV 19.0.2 和 FFmpeg

PyAV 以 BSD-3-Clause 发布，底层视频解码使用其发行包随附的 FFmpeg 动态库。随附许可位于 Python 包的 dist-info/licenses 目录，构建时一并复制到发行目录。

- PyAV https://github.com/PyAV-Org/PyAV
- FFmpeg https://ffmpeg.org/legal.html

## PyInstaller

用于 Windows 可执行程序打包，按 GPL 及其 Bootloader Exception 使用。

- 许可 https://pyinstaller.org/en/stable/license.html

## Eclipse Temurin 21 JRE

安装包内置 Temurin 21.0.13+9 Windows x64 JRE。完整版权及第三方许可声明随运行时保存在 `_internal/runtime/legal`，运行时发行来源和校验值记录在 `installer/toolchain.json`。

- 发行与对应源代码 https://github.com/adoptium/temurin21-binaries/releases/tag/jdk-21.0.13%2B9
- 项目 https://adoptium.net/

## 界面文案图形

确认后的“越练，越懂你”和副标题由 `scripts/render_brand_copy.py` 渲染为透明 PNG，作为固定界面图形随包提供。运行时直接显示这些图形。
