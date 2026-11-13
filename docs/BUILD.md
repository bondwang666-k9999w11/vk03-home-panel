# 源码运行与构建

当前分支只维护VK03 Studio，main分支仍是HA面板。发布程序推荐使用Release里的完整win64 ZIP。

## 环境

Windows 10/11 x64、Python 3.12 x64。构建卸载程序使用Windows自带.NET Framework C#编译器。界面使用动态链接Qt，依赖版本见requirements.txt；许可证见licenses/与THIRD_PARTY_NOTICES.txt。

```powershell
git clone --branch vk03-studio https://github.com/bondwang666-k9999w11/vk03-home-panel.git
cd vk03-home-panel
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe app.py --data-dir ./dev-data
```

只有用户明确点击连接屏幕后才打开USB。开发时先退出其他控制程序。隔离测试不连接USB，不执行真实媒体/电源动作。

## 测试

```powershell
.venv/Scripts/python.exe tests/test_model.py
.venv/Scripts/python.exe tests/test_ui.py
.venv/Scripts/python.exe tests/test_video.py
.venv/Scripts/python.exe tools/check_public_tree.py
```

Qt测试使用offscreen平台与模拟系统桥接，截图写入artifacts/，不应提交个人画面。tests/probe_system.py为Windows真实只读状态探测，单独运行；不属于无系统依赖的模拟测试。

卸载隔离测试需要先通过构建脚本生成uninstall.exe，再运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/test_uninstall.ps1
```

它只删除tests目录中自行创建的夹具文件，验证修改文件与额外文件保留、清单越界拒绝和保护目录拒绝；不对实际安装执行卸载。

## 打包

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File build_release.ps1
```

输出：`dist-0.2.1/VK03Studio/` 与 `releases/standalone-0.2.1/`。完整运行目录必须保留_internal；包内包含uninstall.exe、应用标记、文件哈希清单和第三方许可证。

卸载源码改变或EXE缺失时编译；否则可以复用现有uninstall.exe。每次发布仍会重新生成文件清单、版本标记与SHA256SUMS.txt。

构建规范排除了开发工具的ICU库和系统libusb0.dll，避免误收开发环境文件。运行时使用Windows自带ICU，连接设备时显式加载系统已有的64位libusb0库。Qt自带的FFmpeg解码DLL明确进入运行目录。

## 代码结构

| 文件 | 用途 |
| --- | --- |
| app.py | 菜单、属性、编辑操作、设备控制、方案保存 |
| canvas.py | 场景绘制、监控光晕、内存图形和分层水波 |
| model.py | 方案结构、校验与样式复用 |
| device.py | MS912C帧格式、USB/HID连接与触摸解析 |
| system_bridge.py / bridge/ | Windows媒体、音量与系统动作 |
| projects.py | 带素材的方案导入导出 |
| Uninstall.cs | 清单式卸载与文件保留 |

测试与发布只使用自建数据。不要提交运行配置、快捷目标、日志、个人媒体、原厂程序、JSC、.node、驱动安装器、开发环境或完整dist目录。程序ZIP作为Release附件提供。
