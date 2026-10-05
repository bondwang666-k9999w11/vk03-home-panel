# 安装与排错

## 运行环境

默认安装目录固定为 `C:\VK03`。Windows 11 x64 是已实测环境；Python 3.12 x64 是构建环境，硬件正式版曾使用 Python 3.14 x64。Python 必须包含 Tkinter，安装时保留 Python Launcher。

源码版：

```powershell
cd C:\VK03
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\StartVK03.cmd
```

v1.0.1 使用文件夹版 EXE。必须将 `_internal` 文件夹与 EXE 放在同一目录，不可单独复制 EXE；程序无需在启动时解压运行库。**屏幕进程仍使用 Python**。仍需安装上述依赖，保留完整源码模块，不能只复制 EXE。首次启动自动打开 HA 设备匹配向导，未配置前不会打开 USB 或发送设备指令。

## VK03 USB 驱动

需要能让 PyUSB/libusb0 访问显示 Bulk interface 3 的驱动，并保留显示 HID interface 0 和触摸 HID。当前屏幕进程使用 Windows System32 下已有的 `libusb0.dll`。Python、DLL、驱动应为匹配的 x64 架构。

项目不分发驱动，不自动重绑 USB 接口。请使用厂商或自己已经验证的驱动方案；不要把整个 USB 复合设备或 HID 接口替换成 Bulk 驱动，也不要套用不明网上驱动。

如果已有原版 VK03/MythTool 等程序，运行本项目时关闭会访问同一屏幕的程序及其后台进程。接口占用错误并不一定代表有可见窗口；可以先退出相关进程再重启 Windows。**无需在通电状态下拔插主板 USB 插针。**

## 背景与温度

普通 PNG/JPG/WebP/BMP 与缓存可容纳的小 GIF 可直接使用。视频与大 GIF 需要把合适的官方来源 Windows x64 FFmpeg 构建中的 `ffmpeg.exe` 放在 `C:\VK03`。来源与许可见第三方说明；本项目公开包不含该二进制。

CPU 温度另见 [组件教程](CPU-SENSORS.md)。未准备组件时其余功能仍可用。

## 快捷方式与自动启动

Release 版放好后运行 `InstallShortcuts.cmd`，将桌面和当前用户登录启动项指向 `C:\VK03\VK03控制中心.exe`；登录时带 `--background`。这里只创建当前用户快捷方式，不修改其他用户的启动项。

关闭设置窗口保留托盘进程；托盘“退出程序并停止面板”才会停止显示进程。`StopVK03.cmd` 是独立停止入口。

## 排错

- 认证失败：设备匹配向导重新输入 HA 地址/Token。确保 HA 虚拟机启动，电脑能访问 HA 页面。
- 状态未知：检查绑定实体 ID、HA 中的状态以及设备联网；`unavailable` 不等于关闭。
- Token 解密失败：使用保存凭据的 Windows 用户，或重新输入 Token。DPAPI 文件不能直接跨机器迁移。
- 背景报错：检查素材路径、文件是否存在、视频是否需要 FFmpeg，以及 FFmpeg 是否可运行。
- CPU 温度 `--`：查看 CPU 组件教程；设置窗口和屏幕共享实时数据，不用示例温度替代。
- 触摸唤醒后的首次点击没有切换灯：这是预期行为，首次触摸只进入家居页。

提交问题前不要附上 `vk03_config.json`。日志可能包含第三方错误信息，请脱敏后只提供相关几行。
