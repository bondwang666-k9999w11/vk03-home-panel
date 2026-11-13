# VK03 Studio 0.2.1 · 独立控制面板 / Standalone preview

这次更新从之前的 **原厂扩展版0.3.0** 发展为独立软件，使用自己的中文菜单、编辑器、渲染器与USB/HID通信；不需要启动MythTool，也不包含HA功能。HA面板继续保留在main分支。

Studio采用独立版本线，因此本次标签为 **studio-v0.2.1**。

## 相较0.3.0的主要改进

- 重新设计为“屏幕编辑 / 方案库 / 设备 / 设置与关于”，组件、图层、完整画面预览与属性分区。
- 组件支持自由位置/尺寸、复制、图层顺序、撤销重做和自动保存。
- 字体、字号、颜色、显隐与多种透明度；CPU/GPU四项支持光晕及同族文字样式复用。
- 新增条形、水球、指针仪表盘三款内存组件，显示已用/总物理内存；水球带三层错速、反向、不同透明度波浪。
- 音量喇叭按音量分为1–3道波纹，0/静音显示小号X；音量和亮度填充色可自定义。
- 快捷方式由固定六槽位改为可添加多个独立按钮；保留图片居中裁剪与透明度。
- 关机/重启使用小屏同一按钮2.5秒内连续两次点按确认。
- 独立图片/GIF/视频背景、15/30目标FPS、纯背景模式、软件画面亮度、含素材方案导入导出。
- 新增清单式uninstall.exe，保留个人方案素材、修改文件及额外文件。

本次0.2.1重点完善动态水球。卸载程序与0.2.0相同，但本版的文件清单已更新。

## 下载与运行

- **VK03Studio-0.2.1-preview-win64.zip**：完整Windows x64程序，完整解压后运行VK03Studio.exe，保留_internal。
- **VK03Studio-0.2.1-source.zip**：源码、文档和依赖许可证，供开发者构建。
- **SHA256SUMS.txt**：校验文件。

从托盘退出旧版及其他VK03控制程序后再连接屏幕。已有Studio方案使用同一用户数据目录；原厂私有布局不自动转换。

[完整教程](https://github.com/bondwang666-k9999w11/vk03-home-panel/blob/vk03-studio/docs/USAGE.md) · [详细对比](https://github.com/bondwang666-k9999w11/vk03-home-panel/blob/vk03-studio/docs/COMPARISON-0.3.0.md)

## 支持范围

需要匹配的既有USB驱动；已确认的MS912C 360×960 VK03。CPU温度需要已有LHM WMI服务，NVIDIA GPU需要已有nvidia-smi；AMD/Intel GPU当前未接入，缺失值显示—。亮度是软件调暗，帧率为目标值。原厂皮肤未迁入独立版，本版提供原创初始布局。

本版已做离线、打包、视频和卸载保留检查，并收到当前设备用户实屏通过反馈；其他主机/驱动/固件组合仍需验证。

## English

VK03 Studio is now an independent Windows editor, renderer and USB/HID controller, replacing the previous factory-extension workflow. It adds resizable widgets, reusable text styles and optional glow, three RAM visualizations, layered animated liquid, customizable slider colors, portable schemes and a manifest-based uninstaller that retains personal data.

Download the **preview-win64.zip** for the complete application, extract every file and keep _internal beside the EXE. Exit other controllers before connecting. Compatible USB drivers are still required; CPU temperature depends on an existing LHM WMI service and NVIDIA GPU metrics on nvidia-smi. AMD/Intel GPU collection and automatic vendor-skin conversion are not included. This separate Studio version line uses the tag studio-v0.2.1; the HA edition remains on main.
