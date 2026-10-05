# 第三方组件

本项目自有代码使用 MIT。该许可不重新许可任何第三方软件。

| 组件 | 用途 | 来源 / 许可 |
| --- | --- | --- |
| Pillow | 绘制与图片/GIF | https://github.com/python-pillow/Pillow · 当前构建版本 12.3.0 声明 MIT-CMU（以所用发行版 LICENSE 为准） |
| pystray | Windows 托盘 | https://github.com/moses-palmer/pystray · LGPL-3.0 |
| PyUSB | USB 通讯 | https://github.com/pyusb/pyusb · BSD-3-Clause |
| hidapi Python 包 / HIDAPI | HID 通讯 | https://github.com/trezor/cython-hidapi / https://github.com/libusb/hidapi · 按所用版本许可，Python 包与原生库分别保留声明 |
| PyInstaller | EXE 构建 | https://github.com/pyinstaller/pyinstaller · GPL 及其打包例外；不是程序运行时自有代码许可 |
| LibreHardwareMonitor | 可选 CPU 温度 | https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/tree/v0.9.6 · MPL-2.0，副本在 sensors/LHM-LICENSE.txt |
| PawnIO | 可选温度访问驱动 | https://pawnio.eu/ / https://github.com/namazso/PawnIO.Setup · 安装程序和驱动的许可按官方发行版 |
| FFmpeg | 可选视频/大 GIF 解码 | https://ffmpeg.org/ · 许可取决于构建配置，可能为 LGPL 或 GPL；不得仅凭文件名认定 |
| libusb0 / Windows USB 驱动 | 现有硬件后端 | https://sourceforge.net/projects/libusb-win32/ · 用户自行准备，按使用发行版许可 |

源码仓库不包含以上组件的二进制。核心 Release 的 Python 打包依赖由构建脚本收集许可文本；外部依赖仍由用户安装。

之前本机测试的视频解码构建为 FFmpeg 7.1 essentials（Gyan 构建），具有 GPLv3 许可，未纳入本次公开包。源码和构建来源为 https://github.com/FFmpeg/FFmpeg/tree/n7.1 及 https://www.gyan.dev/ffmpeg/builds/ 。若你再分发该二进制，需遵守该构建的许可和对应源码提供要求。

LibreHardwareMonitor helper 只启用 CPU 硬件，未修改上游 DLL。库中的其他依赖及传递组件继续适用各自许可。上游官方 ZIP 的完整依赖不能统一改为 MIT。

软件名称及商标属于各自权利人；不包含米家界面素材、商业背景视频或厂商 logo 图片。
