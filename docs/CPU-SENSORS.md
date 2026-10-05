# 可选 CPU 温度组件

CPU 占用、物理内存和 NVIDIA 温度/占用不需要此组件。CPU 温度通过独立的 CPU-only LibreHardwareMonitor 采集进程读取，不控制频率、电压或风扇。

源码仓库/核心 Release **不包含第三方 DLL、PawnIO 驱动安装程序或 FFmpeg**。请从官方来源准备这些组件，保留上游自带文件和许可证。

## 准备

1. 从 [LibreHardwareMonitor v0.9.6 官方 Release](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/tag/v0.9.6) 下载 Windows ZIP，并解压到临时目录。
2. 将该目录中的 DLL 复制到 `C:\VK03\sensors`。没有对应 DLL 时不能运行只含自有代码的 `VK03Sensors.exe`。
3. 从 [PawnIO 官方网站](https://pawnio.eu/) 或 [官方安装程序仓库](https://github.com/namazso/PawnIO.Setup/releases) 获取签名安装程序，放到 `C:\VK03\sensors\PawnIO_setup.exe`。项目脚本会检查签名，不会关闭 Windows 安全功能。
4. 编译自己的 CPU helper（如果 Release 已含 helper 可跳过）：

```powershell
cd C:\VK03
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\build_sensors.ps1 -OutputFile sensors\VK03Sensors.exe
```

此步骤只编译源代码，不运行 helper，不安装驱动。

## 启用

点击控制中心“启用 CPU 温度”，或运行 `SetupCpuSensors.cmd`。完成管理员授权和安装向导。已经具备管理员权限时，Windows 可能不再弹出 UAC。

脚本会创建当前 Windows 用户登录时执行、具有最高权限的 **VK03 CPU Sensors** 计划任务并启动采集器。面板和控制中心保持普通用户权限。安装脚本为 ASCII，兼容 Windows PowerShell 5.1。

CPU helper 优先读取 CPU Package 或 AMD Tctl/Tdie，回退到最高核心温度。温度型号支持情况取决于上游库及驱动。没有有效读数，或读数超过 5 秒时显示 `--`。

安装日志：`C:\VK03\vk03_cpu_setup.log`。采集状态：`C:\VK03\vk03_cpu_sensor.json`。这两个文件不含 HA Token，仍应在提交问题前检查内容。

## 停止与移除

停止/退出面板会请求 helper 退出，下次启动重新运行已建立的任务。无需给整个控制中心管理员权限。

如需移除，在任务计划程序删除 `VK03 CPU Sensors`，再通过 Windows 已安装应用卸载 PawnIO；先确认其他硬件监控软件没有使用同一驱动。

LibreHardwareMonitor 采用 MPL-2.0，许可副本在 `sensors/LHM-LICENSE.txt`；本项目未修改其库。你下载的其他上游组件继续适用各自许可证。
