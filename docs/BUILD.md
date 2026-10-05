# 构建与发布包

## 控制中心 EXE

推荐 Windows x64、Python 3.12。源码中的固定默认安装目录为 `C:\VK03`。

请在干净的源码 checkout 中构建，运行配置及背景放在安装目录。隐私扫描会拒绝源码目录里的实际个人配置或传感器依赖下载；构建输出 `dist`、`build` 和自行准备的 `vendor` 目录不参与源码上传。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\check_public_tree.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\build_app.ps1 -Python .\.venv\Scripts\python.exe
```

构建脚本把 EXE 和 `_internal` 运行库写入 `dist/VK03ControlCenter`，不会接触 USB、HA 或个人安装目录。设备匹配、配置和监控模块显式包含在 EXE 中，GUI 不产生 CMD 窗口。

面板进程使用外部 Python；EXE 不代表摆脱 Python 依赖。Release 必须保留源码模块和运行说明。

## CPU helper

按 [CPU 组件教程](CPU-SENSORS.md) 准备官方库，可放到源码 checkout 的 `vendor/LHM`，再运行 `tools/build_sensors.ps1 -LibraryDirectory vendor/LHM`。它使用 .NET Framework C# 编译器生成 `dist/sensors/VK03Sensors.exe`，不安装驱动。源码位于 `sensors/VK03Sensors.cs`，库版本为 v0.9.6。

## 制作核心 Release

```powershell
.\.venv\Scripts\python.exe tools\build_release.py --exe "dist\VK03ControlCenter\VK03控制中心.exe"
```

打包器只使用允许清单，输出 `dist/VK03-v1.0.1-core.zip`。不复制真实配置、主题、日志、个人素材、外部硬件 DLL、驱动安装程序或 FFmpeg；随包包含控制中心依赖的 Python/Tk/Pillow 等运行库。可选 helper 编译完成后可用 `--sensor-exe dist/sensors/VK03Sensors.exe` 加入自有 helper。

打包器附带源码、文档、MIT 许可、第三方说明和构建环境可取得的依赖许可文件。FFmpeg/LHM/PawnIO 不在核心包中，用户按教程自行准备。如果未来重新打包第三方二进制，需要另行核查该构建的全部许可及相应源码提供义务，不能因为本项目是 MIT 就删除其许可。

GitHub Actions 在 Windows 上运行无硬件测试和隐私检查。构建工作流只在手动触发时生成 EXE/ZIP artifact，不会自动创建公开 Release，也不会安装驱动或向设备发送指令。
