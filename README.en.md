# VK03 Home Panel

[简体中文](README.md) · **English**

A Windows control panel for the Valkyrie VK03 touchscreen, featuring PC hardware monitoring, Home Assistant smart home control, video/GIF backgrounds, and customizable appearance.

**v1.0.1** · Windows · 960 × 360 · MIT (third-party components retain their own licenses)

[Download](https://github.com/bondwang666-k9999w11/vk03-home-panel/releases/latest) · [Report a problem](https://github.com/bondwang666-k9999w11/vk03-home-panel/issues/new/choose)

![PC monitoring home screen](docs/images/monitor.png)

The default screen shows your background with CPU/GPU temperatures and utilization, RAM usage, time, and date. Touch anywhere to open smart home controls; the first touch only wakes the page. After 30 seconds without touch input, the panel returns to monitoring. You can also use the return button on the smart home home page.

## Features

- Settings window and system tray operation, with optional Windows sign-in startup.
- Image, GIF, and video backgrounds; target animation rate of 5–30 FPS.
- Adjustable font color, bold monitoring text with subtle glow, and light/dark cards with a shared opacity slider.
- Separate hardware sampling and network work, bounded media buffering, and static-screen keepalive.
- Home Assistant mapping wizard for up to four lights/switches, one air conditioner, one purifier, and temperature, humidity, PM2.5, and PM10 sensors.
- Controls adapt to the entity's capabilities; unbound devices are disabled.
- Automatic HA reconnection. Control commands are not automatically retried, to avoid duplicate actions.
- HA tokens are stored locally using Windows DPAPI for the current user.

## Screenshots

These images use the application's real drawing code with demo device states, metrics, and time. The plain/gradient backgrounds are original demo assets, not personal media.

![Smart home controls in light mode](docs/images/home-light.png)

![Smart home controls in dark mode](docs/images/home-dark.png)

![Air conditioner controls](docs/images/climate.png)

![Air purifier controls](docs/images/purifier.png)

## Installation

1. Download `VK03-v1.0.1-core.zip` from [Releases](https://github.com/bondwang666-k9999w11/vk03-home-panel/releases/latest). The automatically generated **Source code** archives do not contain the control center EXE.
2. Extract the complete package directly into **`C:\VK03`**. Keep the `_internal` runtime folder next to `VK03控制中心.exe`, along with all Python modules. Do not copy the EXE alone.
3. Install 64-bit Python with Tkinter and Python Launcher. Python 3.12 is recommended for building and has been used for isolated installation tests.
4. Open PowerShell and install the display process dependencies:

```powershell
cd C:\VK03
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

5. Prepare a verified VK03 USB driver environment. The display process currently loads the x64 `C:\Windows\System32\libusb0.dll` through PyUSB's libusb0 backend. Preserve the display HID and touch HID interfaces. Python packages alone do not install this DLL or the Windows USB driver.
6. Exit other software accessing the same screen, including background processes, then run `VK03控制中心.exe`.

The EXE provides settings and tray operation; **the display process still requires external Python**. v1.0.1 uses a folder-based EXE to avoid temporary runtime extraction at startup.

USB driver installation on a completely clean system has not been validated. The package does not contain USB drivers or automatically replace them. See the [USB checks and troubleshooting guide (Chinese)](docs/USB-DRIVERS.md).

## Connect Home Assistant and map devices

Home Assistant can run on another always-on machine. First verify that this Windows PC can open your HA page and that your devices can be controlled in HA itself.

Integrate Mijia/Xiaomi devices in HA using an integration that supports your model. This application does not log into Mijia or request your Mijia account password. Other brands can work when they expose compatible HA entities; compatibility with every model is not guaranteed.

Create a long-lived access token in your HA profile security settings. On first launch, the device wizard opens automatically. Later, use **HA 设备匹配** (HA device mapping) in the control center.

1. Enter the HA base URL, such as `http://homeassistant.local:8123`, and your token. Do not include dashboard paths.
2. Click **连接并读取设备** (connect and read devices).
3. Select your own entities and optionally rename the control cards. Leave unused positions empty.
4. Click **保存并应用设备匹配** (save and apply device mapping).

| Panel item | Entity type |
| --- | --- |
| Lights/switches 1–4 | `light.*` or `switch.*` |
| Air conditioner | `climate.*` |
| Air purifier | `fan.*` |
| Temperature, humidity, PM2.5, PM10 | Corresponding `sensor.*` entities |

The wizard only reads states during discovery; it does not send device commands. Saving mapping requests a panel restart. Tokens encrypted for one Windows user cannot simply be transferred to another user or PC; re-enter the token there.

The application UI currently uses Chinese labels. This English README does not add an English UI. Detailed [device mapping documentation](docs/DEVICE-MAPPING.md) is currently in Chinese.

## Appearance, startup, and stopping

Choose a background, font color, light/dark cards, and transparency, then click **保存并应用** (save and apply). Small GIFs and ordinary images can work without FFmpeg; video and large GIFs require a separately obtained `ffmpeg.exe` in `C:\VK03`.

Run `InstallShortcuts.cmd` to create desktop and current-user sign-in shortcuts. Closing the settings window keeps the tray process running. To stop it, use **退出程序并停止面板** (exit and stop panel) in the tray menu, or run `StopVK03.cmd`. A stopped screen may retain its last frame.

## Supported hardware and limitations

- Tested hardware protocol: display `345F:9132`, touch `374A:A401`, display Bulk interface 3, output endpoint `0x04`. Other hardware revisions are unverified.
- The existing panel has been tested on Windows 11 with an NVIDIA RTX 5070 Ti. GPU sampling currently uses `nvidia-smi`; AMD/Intel GPUs show `--`.
- CPU temperature requires optional LibreHardwareMonitor and PawnIO components. Missing, unsupported, or stale data shows `--`, not a simulated temperature. RAM means physical memory usage.
- Actual animation FPS depends on USB throughput and host performance; 30 FPS is a target.
- Climate controls support a single target temperature. The purifier page displays at most six presets, or percentage speed controls when supported and no presets are provided.
- Smart home previews use demo entities; monitoring previews read locally published live data.
- Generic mapping and capability branches have simulated regression coverage and still need verification with each user's HA devices.
- The folder EXE passed independent-directory window/four-page preview checks. This does not validate clean-system USB driver installation or every tray environment.

## Troubleshooting

| Symptom | Check first |
| --- | --- |
| `py` not found | Install Python Launcher |
| Cannot connect to HA | HA running, correct base URL, browser access from Windows |
| HTTP 401 | Complete and valid token |
| Unknown device state | Mapping and actual HA entity availability |
| Cannot claim interface 3 | Competing screen processes and driver/device state; restart Windows if needed |
| EXE cannot start | Keep `_internal` beside the EXE and extract the complete package |
| Missing CPU temperature/video | Optional sensor components/FFmpeg |

Avoid hot-plugging motherboard USB headers. Do not replace all composite/HID drivers to resolve a Bulk interface problem.

## Documentation and development

The detailed guides below are currently in Chinese:

- [Quick start](docs/QUICKSTART.md)
- [Installation and startup](docs/INSTALL.md)
- [USB drivers and troubleshooting](docs/USB-DRIVERS.md)
- [HA device mapping](docs/DEVICE-MAPPING.md)
- [CPU sensor components](docs/CPU-SENSORS.md)
- [Configuration and credential scope](docs/CONFIGURATION.md)
- [Build and package](docs/BUILD.md)
- [Changelog](CHANGELOG.md)

Run these checks from a clean source checkout, not the extracted binary installation folder:

```powershell
py -3 -m pip install -r requirements.txt
py -3 -m unittest discover -s tests -v
py -3 tools/check_public_tree.py
```

Tests do not control real HA devices or install drivers. Before reporting a problem, remove tokens, credentials, serial numbers, and personal paths from logs/screenshots. Do not attach `vk03_config.json`.

This is an independent community project, unaffiliated with Valkyrie, Mijia, or Home Assistant. Project-owned code is licensed under [MIT](LICENSE); see [third-party notices](THIRD_PARTY_NOTICES.md) for dependency licenses. Do not submit copyrighted background media without permission.
