# VK03 USB 驱动检查与排错

适用于本项目已实测的 VK03 硬件。本文提供现有驱动检查与故障定位，**不是已验证的全新系统驱动安装教程**。没有干净设备完成驱动从零安装测试，不保证不同批次硬件使用相同接口。

## 1. 三条通道分别负责什么

| 通道 | 当前程序使用的标识 | 用途 |
| --- | --- | --- |
| 显示 HID | VID `345F` / PID `9132`，已实测 interface 0 | 初始化与控制屏幕 |
| 显示 Bulk | 同一显示设备，interface 3，输出 endpoint `0x04` | 发送图像 |
| 触摸 HID | VID `374A` / PID `A401` | 读取触摸坐标 |

这些值来自程序和已实测设备，不是让用户随意重绑驱动的目标列表。识别时必须同时核对硬件 ID、接口号和设备关系。显示正常不代表触摸通道正常，HID 能打开也不代表 Bulk 能占用。

## 2. 先检查现有环境

如果厂商软件可正常显示，先记录当前驱动信息，不要马上更换驱动。

1. 在 Windows 设备管理器中选择“查看 → 按连接显示设备”。
2. 找到屏幕相关设备，打开“属性 → 详细信息 → 硬件 ID”，检查 VID/PID。复合设备子接口可能包含 `MI_00`、`MI_03`；是否显示这些字段取决于驱动枚举方式。
3. 在“驱动程序”页记录提供商、版本和日期；在“驱动程序详细信息”中记录文件名。
4. 确认触摸 HID 与显示 HID 没有被替换成其他接口的驱动。

也可以在 PowerShell 中列出已连接的匹配设备（只读）：

```powershell
Get-PnpDevice -PresentOnly |
    Where-Object { $_.InstanceId -match 'VID_345F&PID_9132|VID_374A&PID_A401' } |
    Format-Table Status, Class, FriendlyName, InstanceId -AutoSize
```

设备管理器中的名字可以随驱动变化，不能只凭“USB Screen”等名称判断。实例 ID 可能包含设备序列号，反馈截图时按需遮盖。

## 3. 当前程序要求的库与驱动

Python 屏幕进程显式加载 `C:\Windows\System32\libusb0.dll`，使用 PyUSB 的 `libusb0` 后端。Python 和用户态 DLL 必须匹配 x64；只安装 pip 包不会自动安装 Windows USB 驱动或这个 DLL。

```powershell
Test-Path -LiteralPath 'C:\Windows\System32\libusb0.dll'
C:\VK03\.venv\Scripts\python.exe -c "import struct; print('Python bits:', struct.calcsize('P') * 8)"
C:\VK03\.venv\Scripts\python.exe -c "import usb.backend.libusb0; b=usb.backend.libusb0.get_backend(find_library=lambda name: r'C:\Windows\System32\libusb0.dll'); print('Backend loaded:', b is not None)"
```

文件存在仅代表路径存在；Backend loaded 仅代表用户态后端加载成功，**两者都不能证明 interface 3 能正常传图**。

libusb、libusb-win32、libusbK 和 WinUSB 不是可随意互换的同一个方案。当前代码没有使用 libusb-1.0 后端，不能仅安装 WinUSB 或把别的 DLL 改名为 `libusb0.dll` 就认为兼容。区别及复合设备枚举要求见 [libusb Windows 官方说明](https://github.com/libusb/libusb/wiki/Windows)。

驱动包应来自厂商或你已经验证的来源。公开 Release 不分发驱动，也不提供一键重绑。未经实机验证，本文不指定通用 Zadig 配置，更不要求替换整个复合设备或 HID 接口。

## 4. 接口无法占用时

日志出现 `could not claim interface 3`，表明程序在占用 Bulk 接口时失败。可能原因包括其他程序持有接口、驱动不匹配、设备状态或权限；不能仅凭该错误确定“厂商软件正在运行”。

按顺序处理：

1. 通过托盘退出本项目并停止面板，避免同时运行两个面板进程。
2. 退出厂商软件、MythTool 和其他访问此屏幕的程序，检查后台进程。
3. 在设备管理器确认设备状态及驱动信息没有异常。
4. 仍失败时，保存其他工作后重启 Windows，再只启动一个面板程序。

本项目开发期间，同一设备在重启前占用失败，重启后可以占用；这个案例说明重启可能恢复状态，不证明所有同类报错都由同一原因造成。已实测在同一诊断进程中打开/关闭显示 HID 不阻止 Bulk 占用，不能把 HID 本身直接认定为冲突来源。

无需在通电状态下拔插主板 USB 插针。本文不提供禁用所有 USB 设备、卸载所有 USB 驱动或结束所有 Python 进程的命令。

## 5. 常见现象对照

| 现象或日志 | 意义与下一步 |
| --- | --- |
| 无法载入 `libusb0.dll` | 检查路径、架构及库依赖；不是 HA Token 问题 |
| 未找到显示设备 | 检查设备是否枚举、VID/PID 是否一致和驱动状态 |
| interface 3 占用失败 | 按上面的占用排查流程处理，尚未进入传图阶段 |
| 占用成功，但 USB 写入失败 | 检查后续传输错误、设备连接及是否有重复进程 |
| 屏幕停在最后一帧 | 停止程序后可能保留画面；用触摸是否响应判断进程状态 |
| 画面正常但触摸无响应 | 检查触摸 HID 标识、驱动与日志，不要改显示 Bulk 驱动来修触摸 |
| HA 状态未知或 401 | 属于 HA 地址、设备绑定或认证问题，参见设备匹配教程 |
| EXE 提示解压 `ucrtbase.dll` 失败 | 是单文件程序运行库解压问题，与 USB 无关；v1.0.1 使用文件夹版，保留 `_internal` |

## 6. 回退和反馈

如需要更换驱动，先保存原驱动信息及可用安装包，并准备厂商恢复方法。不要根据不明教程直接删除驱动包。Windows 的驱动枚举、导出和安装命令能力见 [Microsoft PnPUtil 文档](https://learn.microsoft.com/zh-cn/windows-hardware/drivers/devtest/pnputil-command-syntax)；本文不执行这些修改命令。

反馈时提供：Windows 版本、Python 位数、设备硬件 ID（序列号可遮盖）、驱动提供商/版本、程序版本以及脱敏的报错片段。说明报错出现在 HID 打开、Bulk 占用还是传图阶段。

不要上传 HA Token、个人 `vk03_config.json` 或未经脱敏的完整日志。真实设备 ID 匹配与驱动安装仍需在使用者自己的设备上验证。
