# 新手入门：从下载到第一次触屏控制

本教程面向首次使用 VK03 Home Panel 的用户。面板程序运行在连接 VK03 的 Windows 电脑上；Home Assistant（简称 HA）可以运行在另一台持续开机的电脑、虚拟机或服务器上。

## 1. 下载正确的安装包

打开 [正式版下载页面](https://github.com/bondwang666-k9999w11/vk03-home-panel/releases/latest)，展开 Assets，下载 `VK03-v1.0.1-core.zip`。

`Source code (zip)` 是源码归档，不含控制中心 EXE。首次使用建议下载 core 包。

将 core 包完整解压到 **`C:\VK03`**。确认这个目录内直接有 `VK03控制中心.exe`、`vk03_home_panel_daily.py`、`requirements.txt` 和 `StartVK03.cmd`，不要额外套一层同名文件夹，也不要只复制 EXE。

## 2. 准备 Windows 运行环境

安装包含 Tkinter 和 Python Launcher 的 Python x64。推荐 Python 3.12。在 PowerShell 中依次执行：

```powershell
cd C:\VK03
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

看到安装成功且没有红色错误后继续。EXE 是设置和托盘入口，实际屏幕进程仍需要 Python 和完整源码。

VK03 显示接口还需要已验证的 x64 USB 驱动及 `libusb0.dll`；公开包不包含这些组件。按 [USB 安装说明](INSTALL.md#vk03-usb-驱动) 确认环境，保留显示 HID 和触摸接口。当前项目不提供一键替换驱动功能。

运行本项目时退出访问同一屏幕的厂商程序或 MythTool，包括它们的后台进程。

## 3. 先在 HA 网页测试设备

如果尚未部署 HA，从 [Home Assistant 官方安装入口](https://www.home-assistant.io/installation/) 选择适合自己主机的方案。

在连接 VK03 的 Windows 电脑上，用浏览器打开自己的 HA 基础地址，例如 `http://homeassistant.local:8123`。无法访问时先解决主机、虚拟机和网络连接问题，再配置面板。地址不要包含 `/home/overview` 等页面路径。

HA 可以放在 Mac mini 等另一台主机上，但 HA 服务必须保持运行。更换 HA 地址后，在设备匹配向导中更新地址并重新验证。

按 [米家接入与设备匹配教程](DEVICE-MAPPING.md) 将设备加入 HA。在 HA 网页中实际测试开关、空调和净化器；网页里无法控制的设备，应先排查 HA 集成。面板不要求输入米家账号密码。

## 4. 创建 Token 并绑定设备

在 HA 用户资料的安全设置中创建长期访问 Token，只将它输入本机程序。[官方 API 文档](https://developers.home-assistant.io/docs/api/rest/) 说明了该认证方式。不要将 Token 放进 GitHub、截图或问题反馈中。

双击 `C:\VK03\VK03控制中心.exe`。首次使用会打开设备匹配向导；以后从控制中心的“HA 设备匹配”入口进入。

1. 填入自己的 HA 基础地址和完整 Token。
2. 点击“连接并读取设备”，等待列表出现。
3. 选择各位置对应的实体，也可以搜索名称或实体 ID。
4. 根据需要修改控制卡片名称。没有对应设备的位置留空。
5. 点击“保存并应用设备匹配”。程序会保存凭据和映射，并重启面板进程。

| 想控制或显示的内容 | 应选择的实体 |
| --- | --- |
| 灯具或墙壁开关 | `light.*` 或 `switch.*` |
| 空调 | `climate.*` |
| 空气净化器 | `fan.*` |
| 环境温度、湿度、PM2.5、PM10 | 对应的 `sensor.*` |

这些是实体类型，不是可以直接粘贴的 ID。每个用户必须选择自己 HA 中的真实实体。净化器可同时提供多个传感器，开关绑定到 `fan`，环境读数分别绑定到对应 `sensor`。

## 5. 第一次使用和外观设置

默认主页显示 PC 监控。触摸任意位置进入智能家居页，第一次触摸只唤醒；进入后再次点击卡片才会控制设备。无触摸 30 秒自动返回监控页，也可以点击家居首页右上角返回按钮。

在控制中心选择背景、字体颜色、浅色/深色按钮及透明度，点击“保存并应用”。先用普通图片确认正常，再尝试 GIF 或视频。

视频和大 GIF 需要自行准备 FFmpeg，见 [背景说明](INSTALL.md#背景与温度)。实际帧率受 USB 和电脑性能影响。CPU 温度需要额外组件，按 [CPU 温度教程](CPU-SENSORS.md) 配置；未安装时显示 `--`。当前 GPU 数据支持 NVIDIA，其他 GPU 也会显示 `--`。

## 6. 设置开机启动和停止程序

确认运行正常后双击 `InstallShortcuts.cmd`，创建桌面快捷方式和当前用户登录启动项。以后登录 Windows 后控制中心会在后台启动。

关闭设置窗口会保留托盘进程。彻底停止时，右键系统托盘图标，选择“退出程序并停止面板”，或运行 `StopVK03.cmd`。停止后屏幕可能保留最后一帧，以按钮不再响应判断是否停止。

## 7. 遇到问题时先定位哪一层

| 现象 | 先检查 |
| --- | --- |
| `py` 命令找不到 | Python Launcher 是否安装 |
| HA 连接失败 | Windows 浏览器能否打开同一 HA 地址、HA 是否运行 |
| 认证失败 / 401 | Token 是否完整、有效，保存地址是否正确 |
| 按钮状态未知 | HA 网页里的实体状态及匹配是否正确 |
| USB 接口无法占用 | 是否有其他屏幕进程；退出相关程序后重启 Windows |
| 有背景但温度是 `--` | 对应采集组件是否准备好、硬件是否受支持 |
| 视频不能播放 | FFmpeg 是否放好、素材是否可读 |

更多排错见 [安装指南](INSTALL.md)。提交 Issue 时提供 Windows/Python 版本、出错步骤和已脱敏日志，不上传个人配置文件或 Token。

教程更新发布在仓库中；v1.0.0 ZIP 内文档保留该版本打包时的内容。
