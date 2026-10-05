import struct
import time

import os
import json
import urllib.request
import urllib.error
import urllib.parse
import threading
import queue
import socket
import math
import atexit

import hid
import usb.core
import usb.util
import usb.backend.libusb0

from PIL import Image, ImageDraw, ImageFont

# ============================================================
# HOME ASSISTANT
# ============================================================

from pathlib import Path
import base64
import ctypes
from ctypes import wintypes

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "vk03_config.json"


from vk03_config import decrypt_token, load_bindings, ROLE_NAMES, NoRedirect


if CONFIG_PATH.exists():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    HA_URL = str(config["ha_url"]).strip().rstrip("/")
    HA_TOKEN = decrypt_token(config["token_dpapi"])
else:
    HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123").strip().rstrip("/")
    HA_TOKEN = (os.environ.get("HA_TOKEN") or "").strip()
HA_POLL_SECONDS = 1.0
HA_TIMEOUT_SECONDS = 3.0

parsed_url = urllib.parse.urlsplit(HA_URL)
if parsed_url.scheme not in ("http", "https") or not parsed_url.hostname:
    raise RuntimeError("HA_URL 必须是有效的 http:// 或 https:// 地址。")
if parsed_url.query or parsed_url.fragment or parsed_url.username or parsed_url.password:
    raise RuntimeError("HA_URL 必须为基础地址，不包含凭据、查询参数或片段。")
try:
    parsed_url.port
except ValueError as exc:
    raise RuntimeError("HA_URL 端口无效。") from exc
if not HA_TOKEN or any(c.isspace() for c in HA_TOKEN):
    raise RuntimeError("未找到有效 Token。请先运行面板设置。")


_mutex_kernel = ctypes.WinDLL("kernel32", use_last_error=True)
_mutex_kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
_mutex_kernel.CreateMutexW.restype = wintypes.HANDLE
_mutex_kernel.CloseHandle.argtypes = [wintypes.HANDLE]
_mutex_kernel.CloseHandle.restype = wintypes.BOOL
_instance_mutex = _mutex_kernel.CreateMutexW(None, False, "Local\\VK03DailyPanel")
_mutex_error = ctypes.get_last_error()
if not _instance_mutex:
    raise ctypes.WinError(_mutex_error)
if _mutex_error == 183:
    _mutex_kernel.CloseHandle(_instance_mutex)
    print("[INFO] 日常面板已经运行，本次启动退出。")
    raise SystemExit(0)
atexit.register(_mutex_kernel.CloseHandle, _instance_mutex)

_ha_error_kind = None
_last_error_report = (None, 0.0)


def report_ha_error(kind, method, path):
    global _ha_error_kind, _last_error_report
    _ha_error_kind = kind
    key = (kind, method, path)
    now = time.monotonic()
    if key != _last_error_report[0] or now - _last_error_report[1] >= 30:
        print(f"[HA ERROR] {kind}: {method} {path}")
        _last_error_report = (key, now)


def cleanup_hardware():
    """Release handles even if setup or the very first frame raises an error."""
    global _cleanup_done
    if globals().get("_cleanup_done", False):
        return
    _cleanup_done = True
    background_object = globals().get("appearance")
    if background_object is not None:
        background_object.close()
    stop_event = globals().get("ha_stop")
    if stop_event is not None:
        stop_event.set()
    commands = globals().get("ha_commands")
    if commands is not None:
        try:
            commands.put_nowait("stop")
        except queue.Full:
            pass
    thread = globals().get("worker")
    if thread is not None and thread.is_alive():
        thread.join(timeout=0.1)
    for name in ("touch", "display_hid"):
        handle = globals().get(name)
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass
    device = globals().get("usb_dev")
    if device is not None:
        try:
            usb.util.dispose_resources(device)
        except Exception:
            pass
    print("[DONE] handles released")


# This also covers startup failures that occur before the main loop's finally.
atexit.register(cleanup_hardware)


# ============================================================
# VK03 DISPLAY
# ============================================================

DISPLAY_VID = 0x345F
DISPLAY_PID = 0x9132

EP_OUT = 0x04

# MS912C framebuffer orientation
FB_WIDTH = 360
FB_HEIGHT = 960

# Physical UI size
SCREEN_WIDTH = 960
SCREEN_HEIGHT = 360

COLOR_BGR888 = 0x11
VIC = 0xA0


# ============================================================
# VK03 TOUCH
# ============================================================

TOUCH_VID = 0x374A
TOUCH_PID = 0xA401

RAW_MAX = 4095


# ============================================================
# HID CONTROL INTERFACE
# ============================================================

display_hids = hid.enumerate(
    DISPLAY_VID,
    DISPLAY_PID
)

if not display_hids:
    raise RuntimeError(
        "找不到 VK03 Display HID 345F:9132"
    )


display_hid = hid.device()

display_hid.open_path(
    display_hids[0]["path"]
)

print(
    "[OK] Display HID opened"
)


def hid_set(payload):

    payload = bytes(
        payload[:8]
    ).ljust(
        8,
        b"\x00"
    )

    # Report ID = 0
    data = b"\x00" + payload

    n = display_hid.send_feature_report(
        data
    )

    if n <= 0:
        raise RuntimeError(
            "send_feature_report failed"
        )


def hid_get():

    data = bytes(
        display_hid.get_feature_report(
            0,
            9
        )
    )

    if len(data) < 9:
        raise RuntimeError(
            "short HID feature report"
        )

    return data


def xread(addr):

    hid_set([
        0xB5,
        (addr >> 8) & 0xFF,
        addr & 0xFF
    ])

    data = hid_get()

    return data[4]


def xread_n(
    addr,
    count
):

    result = bytearray()

    offset = 0

    while offset < count:

        current = (
            addr
            +
            offset
        )

        hid_set([
            0xB5,
            (current >> 8) & 0xFF,
            current & 0xFF
        ])

        data = hid_get()

        take = min(
            4,
            count - offset
        )

        result.extend(
            data[4:4 + take]
        )

        offset += 4

    return bytes(result)


def xwrite(
    addr,
    value
):

    hid_set([
        0xB6,
        (addr >> 8) & 0xFF,
        addr & 0xFF,
        value & 0xFF
    ])


def wait_zero(
    addr,
    name,
    timeout=2.0
):

    deadline = (
        time.time()
        +
        timeout
    )

    last = None

    while time.time() < deadline:

        last = xread(
            addr
        )

        if last == 0:
            return

        time.sleep(
            0.005
        )

    raise RuntimeError(
        f"{name} timeout "
        f"status=0x{last:02X}"
    )


def a6(
    payload,
    status_addr=None,
    name="",
    settle=0.02
):

    hid_set(
        payload
    )

    time.sleep(
        settle
    )

    if status_addr is not None:

        wait_zero(
            status_addr,
            name
        )


# ============================================================
# HARDWARE CHECK
# ============================================================

chip = xread_n(
    0xF000,
    3
)

sdram = xread(
    0x0030
)

port = xread(
    0x0031
)

hpd = xread(
    0x0032
)

print(
    f"[ID] chip={chip.hex(' ')} "
    f"sdram={sdram} "
    f"port={port} "
    f"hpd={hpd}"
)

if chip != bytes([
    0xB7,
    0x16,
    0x0A
]):

    raise RuntimeError(
        "不是预期的 MS912C"
    )


if port != 6:

    raise RuntimeError(
        f"video port={port}, expected 6"
    )


# ============================================================
# USB BULK INTERFACE
# ============================================================

backend = (
    usb.backend.libusb0.get_backend(
        find_library=lambda x:
        r"C:\Windows\System32\libusb0.dll"
    )
)

if backend is None:

    raise RuntimeError(
        "无法载入 libusb0.dll"
    )


usb_dev = usb.core.find(
    idVendor=DISPLAY_VID,
    idProduct=DISPLAY_PID,
    backend=backend
)

if usb_dev is None:

    raise RuntimeError(
        "找不到 VK03 USB Bulk interface"
    )


print(
    "[OK] USB display device found (interface not claimed yet)"
)


# ============================================================
# TOUCH INTERFACE
# ============================================================

touch_devices = hid.enumerate(
    TOUCH_VID,
    TOUCH_PID
)

if not touch_devices:

    raise RuntimeError(
        "找不到 VK03 Touch Screen 374A:A401"
    )


touch = hid.device()

touch.open_path(
    touch_devices[0]["path"]
)

print(
    "[OK] Touch HID opened"
)


# ============================================================
# STATUS REGISTERS
# ============================================================

STATUS_POWER = 0xC454

STATUS_TRANSFER_MODE = 0xC558

STATUS_VIDEO_IN = 0xC555

STATUS_VIDEO_OUT = 0xC557

STATUS_VIDEO_ON = 0xC555

STATUS_TRANS = 0xC555


# ============================================================
# DISPLAY INITIALIZATION
# ============================================================

def initialize_display():

    print(
        "[INIT] transfer mode"
    )

    a6(
        [
            0xA6,
            0x03,
            0x03
        ],
        STATUS_TRANSFER_MODE,
        "transfer mode",
        0.01
    )


    print(
        "[INIT] SDK flag"
    )

    xwrite(
        0xDEEE,
        1
    )


    print(
        "[INIT] power on"
    )

    a6(
        [
            0xA6,
            0x07,
            0x01
        ],
        STATUS_POWER,
        "power",
        0.10
    )


    print(
        "[INIT] video off"
    )

    a6(
        [
            0xA6,
            0x05,
            0x00
        ],
        STATUS_VIDEO_ON,
        "video off",
        0.01
    )


    # Screen gate OFF

    gate = xread(
        0xF005
    )

    xwrite(
        0xF005,
        gate & ~0x10
    )

    print(
        f"[INIT] gate OFF "
        f"{gate:#04x} -> "
        f"{gate & ~0x10:#04x}"
    )


    # Important:
    # clean previous transfer state

    print(
        "[INIT] stop stale transfer"
    )

    a6(
        [
            0xA6,
            0x04,
            0x00
        ],
        STATUS_TRANS,
        "stop transfer",
        0.02
    )

    time.sleep(
        0.05
    )


    # Video input

    print(
        "[INIT] video input"
    )

    a6(
        [
            0xA6,
            0x01,

            (FB_WIDTH >> 8) & 0xFF,
            FB_WIDTH & 0xFF,

            (FB_HEIGHT >> 8) & 0xFF,
            FB_HEIGHT & 0xFF,

            COLOR_BGR888,
            0x00
        ],
        STATUS_VIDEO_IN,
        "video input",
        0.02
    )


    # Video output

    print(
        "[INIT] video output VIC A0"
    )

    a6(
        [
            0xA6,
            0x02,

            VIC,
            0x00,

            (FB_WIDTH >> 8) & 0xFF,
            FB_WIDTH & 0xFF,

            (FB_HEIGHT >> 8) & 0xFF,
            FB_HEIGHT & 0xFF
        ],
        STATUS_VIDEO_OUT,
        "video output",
        0.02
    )


    # Start transfer

    print(
        "[INIT] start transfer"
    )

    a6(
        [
            0xA6,
            0x04,
            0x01
        ],
        STATUS_TRANS,
        "start transfer",
        0.02
    )


# ============================================================
# FONT
# ============================================================

def load_font(
    size,
    bold=False
):

    candidates = []

    if bold:

        candidates.extend([
            r"C:\Windows\Fonts\msyhbd.ttc",
            r"C:\Windows\Fonts\msyhbd.ttf"
        ])

    candidates.extend([
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\segoeui.ttf"
    ])

    for path in candidates:

        try:

            return ImageFont.truetype(
                path,
                size
            )

        except Exception:

            pass

    return ImageFont.load_default()


FONT_TITLE = load_font(
    28,
    True
)

FONT_BUTTON = load_font(
    30,
    True
)

FONT_STATUS = load_font(
    19,
    False
)

FONT_TEMP = load_font(40, True)

FONT_SMALL = load_font(
    16,
    False
)

# ============================================================
# HOME ASSISTANT API
# ============================================================

# Drawing/control helpers are also used by the no-hardware GUI preview.
def load_background_color(path):
    default = (214, 239, 225)  # Soft green keeps dark labels readable.
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        value = data.get("background_color")
        if not isinstance(value, str) or len(value) != 7 or value[0] != "#" or any(c not in "0123456789abcdefABCDEF" for c in value[1:]):
            return default
        return tuple(int(value[i:i+2], 16) for i in (1, 3, 5))
    except (OSError, ValueError, TypeError, AttributeError):
        return default


from vk03_theme import Appearance, card, TextDraw
appearance = Appearance(APP_DIR)
BACKGROUND_COLOR = load_background_color(APP_DIR / "vk03_theme.json")


device_bindings = globals().get("PREVIEW_BINDINGS") or load_bindings(APP_DIR)
LIGHT_ENTITIES = {role: device_bindings[role]["entity_id"] for role in ("light_1", "light_2", "light_3", "light_4")}
AC_ENTITY = device_bindings["climate"]["entity_id"]
PURIFIER_ENTITY = device_bindings["purifier"]["entity_id"]
ENV_ENTITIES = {role: device_bindings[role]["entity_id"] for role in ("temperature", "humidity", "pm25", "pm10")}


def display_name(action):
    role = {"空调": "climate", "净化器": "purifier"}.get(action, action)
    return device_bindings.get(role, {}).get("label", action)


PURIFIER_ATTRIBUTE_KEYS = ("preset_modes", "preset_mode", "percentage", "percentage_step", "supported_features")
SENSOR_ATTRIBUTE_KEYS = ("unit_of_measurement", "device_class")
ALL_ENTITIES = list(LIGHT_ENTITIES.values()) + [AC_ENTITY, PURIFIER_ENTITY] + list(ENV_ENTITIES.values())
HOME_NAMES = ["light_1", "空调", "light_2", "light_3", "净化器", "light_4"]
MODE_NAMES = {"off": "关闭", "cool": "制冷", "heat": "制热",
              "dry": "除湿", "fan_only": "送风", "auto": "自动", "heat_cool": "冷暖自动"}
AC_ATTRIBUTE_KEYS = ("hvac_modes", "min_temp", "max_temp", "target_temp_step",
                     "fan_modes", "swing_modes", "current_temperature", "temperature",
                     "fan_mode", "hvac_action", "swing_mode", "supported_features")


def ha_request(method, path, body=None):
    global _ha_error_kind
    _ha_error_kind = None
    try:
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            HA_URL + path, data=data, method=method,
            headers={"Authorization": f"Bearer {HA_TOKEN}",
                     "Content-Type": "application/json; charset=utf-8"},
        )
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=HA_TIMEOUT_SECONDS) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else []
    except urllib.error.HTTPError as exc:
        report_ha_error("auth" if exc.code in (401, 403) else f"HTTP {exc.code}", method, path)
        exc.close()
    except (urllib.error.URLError, OSError, ValueError, UnicodeError) as exc:
        report_ha_error(type(exc).__name__, method, path)
    return None


def fetch_snapshot():
    # One state-list request for all six devices; do not poll six sequential URLs.
    # Refresh units too, so changing HA to Celsius does not break conversion.
    config = ha_request("GET", "/api/config")
    units = config.get("unit_system", {}) if isinstance(config, dict) else {}
    unit = units.get("temperature") if isinstance(units, dict) else None
    if unit not in ("°C", "°F"):
        unit = None
    result = ha_request("GET", "/api/states")
    lookup = {item["entity_id"]: item for item in result
              if isinstance(item, dict) and isinstance(item.get("entity_id"), str)} if isinstance(result, list) else {}
    entities = {}
    for entity in ALL_ENTITIES:
        item = lookup.get(entity, {})
        state = item.get("state")
        attrs = item.get("attributes", {})
        if not isinstance(attrs, dict):
            attrs = {}
        keys = (AC_ATTRIBUTE_KEYS if entity == AC_ENTITY else
                PURIFIER_ATTRIBUTE_KEYS if entity == PURIFIER_ENTITY else
                SENSOR_ATTRIBUTE_KEYS if entity in ENV_ENTITIES.values() else ())
        # Exclude timestamps: unchanged device states must not cause extra renders.
        entities[entity] = {
            "state": state if isinstance(state, str) else None,
            "attributes": {key: attrs[key] for key in keys if key in attrs},
        }
    return {"unit": unit, "entities": entities,
            "connection": "online" if isinstance(result, list) else ("auth" if _ha_error_kind == "auth" else "offline")}


def as_number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def to_celsius(value, unit):
    value = as_number(value)
    if value is None or unit not in ("°C", "°F"):
        return None
    return (value - 32) * 5 / 9 if unit == "°F" else value


def temperature_text(value, unit):
    value = to_celsius(value, unit)
    return "-- °C" if value is None else f"{value:.1f} °C"


def valid_options(value):
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def cycle_option(options, current):
    if not options:
        raise ValueError("设备没有提供可选项")
    return options[(options.index(current) + 1) % len(options)] if current in options else options[0]


def feature_bits(attributes):
    value = attributes.get("supported_features", 0)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def build_command(action, snapshot, last_mode):
    """Build from a fresh server read, never from an optimistic local toggle."""
    entities = snapshot["entities"]
    if action in LIGHT_ENTITIES:
        entity = LIGHT_ENTITIES[action]
        if entities[entity]["state"] not in ("on", "off"):
            raise ValueError("灯的状态暂不可用，请稍后重试")
        return entity.partition(".")[0], "toggle", {"entity_id": entity}
    if action == "purifier_power" or action.startswith("purifier_preset:") or action in ("purifier_speed_down", "purifier_speed_up"):
        purifier = entities[PURIFIER_ENTITY]
        state, attrs = purifier["state"], purifier["attributes"]
        if state not in ("on", "off"):
            raise ValueError("净化器状态暂不可用，请稍后重试")
        body = {"entity_id": PURIFIER_ENTITY}
        features = feature_bits(attrs)
        if action == "purifier_power":
            required = 16 if state == "on" else 32
            if not features & required:
                raise ValueError("净化器没有提供对应开关功能")
            return "fan", "turn_off" if state == "on" else "turn_on", body
        if state != "on":
            raise ValueError("请先开启净化器，再选择模式")
        if action in ("purifier_speed_down", "purifier_speed_up"):
            if not features & 1:
                raise ValueError("净化器未提供百分比风速控制")
            current = as_number(attrs.get("percentage"))
            step = as_number(attrs.get("percentage_step"))
            if step is None:step = 1
            if current is None or not 0 <= current <= 100 or not 0 < step <= 100:
                raise ValueError("风速范围未读取成功")
            target = max(0, min(100, round(current + step * (1 if action.endswith("up") else -1))))
            if target == round(current):
                raise ValueError("已达到风速边界")
            body["percentage"] = target
            return "fan", "set_percentage", body
        preset = action.partition(":")[2]
        if not features & 8 or preset not in valid_options(attrs.get("preset_modes")):
            raise ValueError("净化器当前不支持此模式")
        body["preset_mode"] = preset
        return "fan", "set_preset_mode", body
    ac = entities[AC_ENTITY]
    state, attrs = ac["state"], ac["attributes"]
    modes = valid_options(attrs.get("hvac_modes"))
    if state not in modes:
        raise ValueError("空调状态暂不可用，请稍后重试")
    body = {"entity_id": AC_ENTITY}
    if action == "ac_power":
        if state != "off":
            target = "off"
        else:
            active_modes = [mode for mode in modes if mode != "off"]
            target = last_mode if last_mode in active_modes else (
                "cool" if "cool" in active_modes else next(iter(active_modes), None))
        if target not in modes:
            raise ValueError("空调没有提供开关模式")
        body["hvac_mode"] = target
        return "climate", "set_hvac_mode", body
    if state == "off":
        raise ValueError("请先开启空调，再调节温度、模式或风力")
    features = feature_bits(attrs)
    if action in ("temp_down", "temp_up"):
        if not features & 1:
            raise ValueError("当前设备不支持目标温度")
        if state in ("dry", "fan_only"):
            raise ValueError("请切换到制冷或制热后调节温度")
        unit = snapshot["unit"]
        current = as_number(attrs.get("temperature"))
        minimum, maximum = as_number(attrs.get("min_temp")), as_number(attrs.get("max_temp"))
        step = as_number(attrs.get("target_temp_step"))
        if unit not in ("°C", "°F") or None in (current, minimum, maximum, step) or step <= 0 or minimum > maximum:
            raise ValueError("温度单位或范围未读取成功，请稍后重试")
        # UI increment is 1 Celsius degree; snap to the HA-native temperature grid.
        target = current + (1 if action == "temp_up" else -1) * (1.8 if unit == "°F" else 1)
        target = minimum + round((target - minimum) / step) * step
        target = max(minimum, min(maximum, target))
        if abs(target - current) < 1e-8:
            raise ValueError("已达到设备温度范围边界")
        body["temperature"] = round(target, 6)
        return "climate", "set_temperature", body
    if action == "ac_fan":
        if not features & 8:
            raise ValueError("当前设备不支持风档调节")
        body["fan_mode"] = cycle_option(valid_options(attrs.get("fan_modes")), attrs.get("fan_mode"))
        return "climate", "set_fan_mode", body
    if action == "ac_mode":
        body["hvac_mode"] = cycle_option([mode for mode in modes if mode != "off"], state)
        return "climate", "set_hvac_mode", body
    if action == "ac_swing":
        if not features & 32:
            raise ValueError("当前设备不支持扫风")
        body["swing_mode"] = cycle_option(valid_options(attrs.get("swing_modes")), attrs.get("swing_mode"))
        return "climate", "set_swing_mode", body
    raise ValueError("未知控制按钮")


ha_commands = queue.Queue(maxsize=1)
ha_results = queue.Queue()
ha_stop = threading.Event()


def ha_worker():
    # All networking is isolated from the USB/HID display and touch loop.
    next_poll = 0.0
    failures = 0
    last_mode = "cool"  # First start while OFF explicitly defaults to cooling.
    while not ha_stop.is_set():
        try:
            action = ha_commands.get(timeout=max(0.0, next_poll - time.monotonic()))
        except queue.Empty:
            action = None
        if ha_stop.is_set() or action == "stop":
            break
        message = None
        fresh = None
        try:
            fresh = fetch_snapshot()
            state = fresh["entities"][AC_ENTITY]["state"]
            if state in valid_options(fresh["entities"][AC_ENTITY]["attributes"].get("hvac_modes")) and state != "off":
                last_mode = state
            if action is not None:
                domain, service, body = build_command(action, fresh, last_mode)
                print("[HA COMMAND]", domain, service)  # Do not write device identifiers to logs.
                ok = ha_request("POST", f"/api/services/{domain}/{service}", body) is not None
                message = "已发送，请以设备回报状态为准" if ok else "请求失败，请查看设备状态后再操作"
                # No retries: a failed response may follow a successful physical action.
                if ha_stop.wait(0.25 if ok else 0.0):
                    break
                fresh = fetch_snapshot()
        except Exception as exc:
            # Keep the worker alive without printing credentials or response bodies.
            message = str(exc) if isinstance(exc, ValueError) else "通信异常，请稍后重试"
            print("[HA WORKER]", type(exc).__name__)
        if not ha_stop.is_set():
            ha_results.put({"snapshot": fresh, "done": action is not None, "message": message})
        failures = 0 if fresh is not None and fresh.get("connection") == "online" else min(failures + 1, 4)
        delay = HA_POLL_SECONDS if not failures else min(2 ** failures, 15)
        next_poll = time.monotonic() + delay


snapshot = {"unit": None, "connection": "starting", "entities": {
    entity: {"state": None, "attributes": {}}
    for entity in ALL_ENTITIES}}
page = "monitor"
pending = False
notice = "正在读取设备状态…"
buttons = []


def accept_result(result):
    global snapshot, pending, notice
    previous = (snapshot, pending, notice)
    if result["snapshot"] is not None:
        snapshot = result["snapshot"]
        connection = snapshot.get("connection")
        if connection == "offline":
            notice = "HA 连接中断，正在自动重连…"
        elif connection == "auth":
            notice = "HA 认证失败，请重新运行面板设置更新 Token"
        elif previous[0].get("connection") in ("offline", "auth"):
            notice = "已重新连接，设备状态已刷新"
        if notice == "正在读取设备状态…":
            notice = "点击灯具开关；空调和净化器进入详情"
    if result["done"]:
        pending = False
    if result["message"]:
        notice = result["message"]
    return previous != (snapshot, pending, notice)


def handle_action(action):
    global page, pending, notice
    if action == "monitor_home":
        page = "monitor"
        return True
    if action == "空调":
        if not pending:
            notice = "温度加减；风力、模式和扫风点击切换"
        page = "ac"
        return True
    if action == "净化器":
        if not pending:
            notice = "开关净化器；选择自动、睡眠或风档模式"
        page = "purifier"
        return True
    if action == "back":
        if not pending:
            notice = "点击灯具开关；空调和净化器进入详情"
        page = "home"
        return True
    if snapshot.get("connection") != "online":
        notice = "连接暂不可用，正在自动重连；本次操作未发送"
        return True
    if pending:
        notice = "上一条指令正在处理，请稍候"
        return True
    pending = True
    notice = "正在处理…"
    try:
        ha_commands.put_nowait(action)
    except queue.Full:
        pending = False
        notice = "指令队列忙，请稍后重试"
    return True


def draw_centered(draw, xy, text, font, fill):
    draw.text(xy, text, font=font, fill=fill, anchor="mm")


def draw_device_icon(draw, x, y, kind, color):
    if kind == "空调":
        draw.rounded_rectangle((x-18,y-12,x+18,y+8), radius=5, outline=color, width=2)
        draw.line((x-12,y+2,x+12,y+2),fill=color,width=2)
        for dx in (-9,0,9):
            draw.line((x+dx,y+13,x+dx,y+19),fill=color,width=2)
    elif kind == "净化器":
        draw.rounded_rectangle((x-13,y-20,x+13,y+20),radius=6,outline=color,width=2)
        for dy in (-4,2,8):
            draw.line((x-7,y+dy,x+7,y+dy),fill=color,width=2)
        draw.ellipse((x-2,y-13,x+2,y-9),fill=color)
    else:
        draw.ellipse((x-13,y-18,x+13,y+8),outline=color,width=2)
        draw.line((x-8,y+7,x-6,y+15,x+6,y+15,x+8,y+7),fill=color,width=2)
        draw.line((x-5,y+20,x+5,y+20),fill=color,width=2)


def tile(draw, rect, title, subtitle, action, active=False, enabled=True):
    if action in ("temp_down", "temp_up", "ac_fan", "ac_swing"):
        attributes = snapshot["entities"][AC_ENTITY]["attributes"]
        required = {"temp_down": 1, "temp_up": 1, "ac_fan": 8, "ac_swing": 32}[action]
        if not feature_bits(attributes) & required:
            return
    if enabled:
        buttons.append({"name": action, "rect": rect})
    x1,y1,x2,y2=rect
    if action in HOME_NAMES:
        while len(title)>1 and FONT_BUTTON.getlength(title)>x2-x1-110:
            title=title[:-2]+"…" if title.endswith("…") else title[:-1]+"…"
    color=(232,247,239) if active else (255,255,255)
    if not enabled: color=(237,240,239)
    card(draw, rect, color, appearance.settings["button_opacity"])
    foreground=(27,133,88) if active else (42,52,48)
    secondary=(73,143,108) if active else (130,141,136)
    if not enabled: foreground,secondary=(155,164,159),(165,173,169)
    if action in HOME_NAMES:
        draw.ellipse((x1+16,y1+18,x1+70,y1+72),fill=((40,87,61) if active else (52,61,56)) if appearance.settings["button_mode"] == "dark" else ((211,239,223) if active else (241,245,243)))
        draw_device_icon(draw,x1+43,y1+45,action,((108,231,177) if active else (170,192,178)) if appearance.settings["button_mode"] == "dark" else (foreground if active else (127,146,136)))
        draw.text((x1+86,y1+12),title,font=FONT_BUTTON,fill=foreground)
        draw.text((x1+86,y1+53),subtitle,font=FONT_SMALL,fill=secondary)
        if action in ("空调","净化器"):
            draw.line((x2-20,y1+36,x2-13,y1+43,x2-20,y1+50),fill=secondary,width=2)
        else:
            draw.ellipse((x2-22,y1+19,x2-14,y1+27),fill=(51,179,115) if active else (195,204,199))
    else:
        cx,cy=(x1+x2)//2,(y1+y2)//2
        draw_centered(draw,(cx,cy-(13 if subtitle else 0)),title,FONT_BUTTON,foreground)
        if subtitle:draw_centered(draw,(cx,cy+27),subtitle,FONT_STATUS,secondary)


def sensor_text(key):
    item = snapshot["entities"][ENV_ENTITIES[key]]
    value = as_number(item["state"])
    unit = item["attributes"].get("unit_of_measurement")
    if key == "temperature":
        return temperature_text(value, unit)  # Sensor's own unit, not HA's default.
    if key == "humidity":
        return "-- %" if value is None or unit != "%" or not 0 <= value <= 100 else f"{value:g} %"
    if value is None or value < 0:
        return "--"
    return f"{value:g} {unit}" if isinstance(unit, str) and unit else f"{value:g} (单位未知)"


def draw_environment(draw):
    for index, (key, label) in enumerate((("temperature", "环境温度"), ("humidity", "湿度"),
                                         ("pm25", "PM2.5"), ("pm10", "PM10"))):
        x = 18 + index * 234
        card(draw, (x, 68, x + 222, 113), (255, 255, 255), appearance.settings["button_opacity"], radius=10)
        draw.text((x + 10, 71), label, font=FONT_SMALL, fill=(124, 140, 131))
        draw.text((x + 86, 81), sensor_text(key), font=FONT_SMALL, fill=(43, 58, 49))


from vk03_monitor import EMPTY, PCMonitor, draw_monitor
pc_stats = EMPTY.copy()

def render_overlay():
    global buttons
    buttons = []  # Rebuilt hit regions always match the currently visible page.
    img = Image.new("RGBA", (SCREEN_WIDTH, SCREEN_HEIGHT), (0, 0, 0, 0))
    if page == "monitor":
        return draw_monitor(img, pc_stats, load_font, appearance.settings)
    draw = TextDraw(ImageDraw.Draw(img), appearance.settings)
    draw.text((20, 15), "我的家" if page == "home" else ("净化器控制" if page == "purifier" else "空调控制"),
              font=FONT_TITLE, fill=(39, 50, 44))
    if page != "home":
        tile(draw, (780, 8, 942, 54), "返回首页", "", "back")
    else:
        tile(draw, (780, 8, 942, 54), "返回主页", "", "monitor_home")
    connection = snapshot.get("connection", "starting")
    label = {"online": "HA 已连接", "offline": "正在重连", "auth": "认证失败", "starting": "正在连接"}.get(connection, "正在连接")
    color = (35, 164, 101) if connection == "online" else (183, 121, 42)
    draw.ellipse((385, 26, 393, 34), fill=color)
    draw.text((405, 21), label, font=FONT_SMALL, fill=color)
    draw.line((18, 61, 942, 61), fill=(228, 234, 230), width=2)
    ac = snapshot["entities"][AC_ENTITY]
    attrs, state = ac["attributes"], ac["state"]
    modes = valid_options(attrs.get("hvac_modes"))
    available = state in modes
    active = available and state != "off"
    unit = snapshot["unit"]
    if page == "home":
        draw_environment(draw)
        for index, name in enumerate(HOME_NAMES):
            row, col = divmod(index, 3)
            rect = (18 + col * 312, 122 + row * 101, 318 + col * 312, 212 + row * 101)
            if name == "空调":
                subtitle = "状态未知" if not available else ("关闭 · 点击设置" if not active else
                            f"{MODE_NAMES.get(state, state)} · {temperature_text(attrs.get('temperature'), unit)}")
                tile(draw, rect, display_name(name), "未绑定" if not AC_ENTITY else subtitle, name, active, bool(AC_ENTITY))
            elif name == "净化器":
                purifier = snapshot["entities"][PURIFIER_ENTITY]
                purifier_state = purifier["state"]
                subtitle = ("关闭 · 点击设置" if purifier_state == "off" else
                            "运行 · " + str(purifier["attributes"].get("preset_mode") or "已开启")
                            if purifier_state == "on" else "状态未知 · 点击设置")
                tile(draw, rect, display_name(name), "未绑定" if not PURIFIER_ENTITY else subtitle, name, purifier_state == "on", bool(PURIFIER_ENTITY))
            else:
                light_state = snapshot["entities"][LIGHT_ENTITIES[name]]["state"]
                subtitle = {"on": "已开启", "off": "已关闭"}.get(light_state, "状态未知")
                tile(draw, rect, display_name(name), "未绑定" if not LIGHT_ENTITIES[name] else subtitle, name, light_state == "on", light_state in ("on", "off"))
    elif page == "purifier":
        purifier = snapshot["entities"][PURIFIER_ENTITY]
        purifier_state, purifier_attrs = purifier["state"], purifier["attributes"]
        purifier_available = purifier_state in ("on", "off")
        purifier_on = purifier_state == "on"
        features = feature_bits(purifier_attrs)
        tile(draw, (18, 74, 302, 183), "关闭净化器" if purifier_on else "开启净化器",
             "状态未知" if not purifier_available else ("运行中" if purifier_on else "已关闭"),
             "purifier_power", active=purifier_on,
             enabled=purifier_available and bool(features & (16 if purifier_on else 32)))
        card(draw, (18, 197, 302, 312), (255, 255, 255), appearance.settings["button_opacity"])
        draw_centered(draw, (160, 221), "环境颗粒物浓度", FONT_STATUS, (124, 140, 131))
        draw_centered(draw, (160, 258), "PM2.5  " + sensor_text("pm25"), FONT_STATUS, (43, 58, 49))
        draw_centered(draw, (160, 290), "PM10  " + sensor_text("pm10"), FONT_SMALL, (124, 140, 131))
        presets = valid_options(purifier_attrs.get("preset_modes"))
        for index, preset in enumerate(presets[:6]):
            row, col = divmod(index, 3)
            rect = (320 + col * 210, 74 + row * 123, 520 + col * 210, 183 + row * 123)
            selected = purifier_on and purifier_attrs.get("preset_mode") == preset
            tile(draw, rect, preset, "当前模式" if selected else "点击选择", "purifier_preset:" + preset,
                 active=selected, enabled=purifier_on and bool(features & 8))
        if not presets and features & 1:
            percentage = as_number(purifier_attrs.get("percentage"))
            subtitle = "--" if percentage is None else f"{percentage:g}%"
            tile(draw, (320, 74, 625, 183), "降低风速", subtitle, "purifier_speed_down", enabled=purifier_on)
            tile(draw, (640, 74, 942, 183), "增加风速", subtitle, "purifier_speed_up", enabled=purifier_on)
        elif not presets:
            draw.text((340, 140), "设备未提供模式或风速控制", font=FONT_STATUS, fill=(124, 140, 131))
    else:
        features = feature_bits(attrs)
        temp_ready = (active and state not in ("dry", "fan_only") and bool(features & 1)
                      and unit in ("°C", "°F") and as_number(attrs.get("temperature")) is not None)
        card(draw, (18, 74, 470, 228), (255, 255, 255), appearance.settings["button_opacity"])
        draw_centered(draw, (244, 98), "目标温度", FONT_STATUS, (124, 140, 131))
        draw_centered(draw, (244, 156), temperature_text(attrs.get("temperature"), unit),
                      FONT_TEMP, (35, 143, 91))
        tile(draw, (30, 120, 122, 210), "−", "", "temp_down", enabled=temp_ready)
        tile(draw, (366, 120, 458, 210), "+", "", "temp_up", enabled=temp_ready)
        draw.text((30, 244), "室温：" + temperature_text(attrs.get("current_temperature"), unit),
                  font=FONT_STATUS, fill=(97, 119, 106))
        draw.text((30, 281), "每次调节约 1°C", font=FONT_SMALL, fill=(139, 151, 143))
        tile(draw, (488, 74, 707, 182), "关闭空调" if active else "开启空调",
             "状态未知" if not available else MODE_NAMES.get(state, state), "ac_power", active, available)
        tile(draw, (723, 74, 942, 182), "切换模式", MODE_NAMES.get(state, "状态未知"),
             "ac_mode", enabled=active)
        tile(draw, (488, 196, 707, 312), "切换风力", attrs.get("fan_mode") or "--", "ac_fan",
             enabled=active and bool(features & 8) and bool(valid_options(attrs.get("fan_modes"))))
        tile(draw, (723, 196, 942, 312), "上下扫风",
             {"off": "已关闭", "vertical": "已开启"}.get(attrs.get("swing_mode"), "--"), "ac_swing",
             active=attrs.get("swing_mode") == "vertical",
             enabled=active and bool(features & 32) and bool(valid_options(attrs.get("swing_modes"))))
    draw.text((20, 333), notice, font=FONT_SMALL,
              fill=(183, 121, 42) if pending else (124, 140, 131))
    return img


_overlay_key = None
_overlay_image = None


def render_ui():
    global _overlay_key, _overlay_image
    key = json.dumps([pc_stats if page == "monitor" else snapshot, page,
                      int(time.time()) if page == "monitor" else pending,
                      "" if page == "monitor" else notice,
                      appearance.settings['button_opacity'],appearance.settings['font_color'],appearance.settings['button_mode']],
                     ensure_ascii=False, sort_keys=True)
    if key != _overlay_key:
        _overlay_image=render_overlay()
        _overlay_key=key
    image=appearance.background()
    image.paste(_overlay_image,(0,0),_overlay_image)
    return image


# ============================================================
# ENCODE IMAGE FOR MS912C
# ============================================================

def encode_frame(
    image
):

    if image.size != (
        SCREEN_WIDTH,
        SCREEN_HEIGHT
    ):

        raise ValueError(
            "UI image must be 960x360"
        )


    # VK03 framebuffer orientation

    image = image.transpose(
        Image.Transpose.ROTATE_270
    )


    if image.size != (
        FB_WIDTH,
        FB_HEIGHT
    ):

        raise RuntimeError(
            f"rotation error: "
            f"{image.size}"
        )


    rgb = image.tobytes()


    # RGB -> BGR

    body = bytearray(
        len(rgb)
    )

    body[0::3] = rgb[2::3]

    body[1::3] = rgb[1::3]

    body[2::3] = rgb[0::3]


    # 0xFF is reserved

    body = bytes(
        body
    ).replace(
        b"\xFF",
        b"\xFE"
    )


    # Header

    header = bytearray(
        8
    )

    struct.pack_into(
        "<I",
        header,
        0,
        0xFF
    )

    header[4] = 0

    header[5] = (
        FB_WIDTH >> 4
    ) & 0xFF

    header[6] = (
        ((FB_WIDTH & 0x0F) << 4)
        |
        ((FB_HEIGHT >> 8) & 0x0F)
    )

    header[7] = (
        FB_HEIGHT
        &
        0xFF
    )


    trailer = bytes([
        0xFF,
        0xC0,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00
    ])


    frame = (
        bytes(header)
        +
        body
        +
        trailer
    )


    expected = (
        FB_WIDTH
        *
        FB_HEIGHT
        *
        3
        +
        16
    )


    if len(frame) != expected:

        raise RuntimeError(
            "frame size mismatch"
        )


    return frame


# ============================================================
# SEND FRAME
# ============================================================

def send_frame(
    frame,
    fid
):

    CHUNK = 0x80000

    offset = 0


    while offset < len(frame):

        chunk = frame[
            offset:
            offset + CHUNK
        ]

        written = usb_dev.write(
            EP_OUT,
            chunk,
            timeout=12000
        )

        if written <= 0:

            raise RuntimeError(
                f"bulk write stalled "
                f"at {offset}"
            )

        offset += written


    # ZLP

    usb_dev.write(
        EP_OUT,
        b"",
        timeout=12000
    )


    # Frame trigger

    hid_set([
        0xA6,
        0x00,
        fid,
        100,
        0,
        0,
        0,
        0
    ])


# ============================================================
# TOUCH COORDINATE
# ============================================================

def decode_touch(
    data
):

    if len(data) < 7:
        return None


    contact = data[1]


    if contact == 0:
        return None


    raw_x = (
        data[3]
        |
        (
            data[4]
            <<
            8
        )
    )


    raw_y = (
        data[5]
        |
        (
            data[6]
            <<
            8
        )
    )


    # Sensor is rotated 90 degrees:
    #
    # raw Y -> screen X
    # inverted raw X -> screen Y

    x = int(
        raw_y
        *
        (
            SCREEN_WIDTH - 1
        )
        /
        RAW_MAX
    )


    y = int(
        (
            RAW_MAX
            -
            raw_x
        )
        *
        (
            SCREEN_HEIGHT - 1
        )
        /
        RAW_MAX
    )


    x = max(
        0,
        min(
            SCREEN_WIDTH - 1,
            x
        )
    )

    y = max(
        0,
        min(
            SCREEN_HEIGHT - 1,
            y
        )
    )


    return (
        x,
        y,
        raw_x,
        raw_y
    )


# ============================================================
# BUTTON HIT TEST
# ============================================================

def hit_test(
    x,
    y
):

    for button in buttons:

        x1, y1, x2, y2 = (
            button["rect"]
        )

        if (
            x1 <= x <= x2
            and
            y1 <= y <= y2
        ):

            return button["name"]

    return None


def claim_display_interface():
    """Claim the same endpoint interface PyUSB would use on the first write.

    Check ownership BEFORE initialize_display turns video/gate off. Do not
    reset the USB device or replace its configuration/drivers.
    """
    try:
        config = usb_dev.get_active_configuration()
        candidates = [interface for interface in config
                      if any(endpoint.bEndpointAddress == EP_OUT
                             and endpoint.bmAttributes & 3 == 2
                             for endpoint in interface)]
        if not candidates:
            raise RuntimeError("VK03 当前配置中找不到 Bulk OUT 0x04 接口。")
        interface = candidates[0]
        number = interface.bInterfaceNumber
        print(f"[USB] claiming display interface {number}, endpoint 0x{EP_OUT:02X}")
        usb.util.claim_interface(usb_dev, number)
        print(f"[OK] Display USB interface {number} claimed")
    except usb.core.USBError as exc:
        print("[USB ERROR] 无法占用显示接口。请退出其他 VK03 程序和原厂显示软件。")
        print("[USB ERROR] 请检查其他程序；若接口持续占用，可保存工作后重启 Windows。")
        raise RuntimeError("VK03 USB 显示接口占用检查失败；尚未执行屏幕初始化。") from exc


# ============================================================
# START DISPLAY
# ============================================================

claim_display_interface()

# Initial state synchronization runs in the background immediately after display startup.
current_image = render_ui()

current_frame = encode_frame(
    current_image
)


# Render/encode and claim succeeded; now run the original display setup.
initialize_display()

# First frame uses FID 1

fid = 1

print(
    "[DISPLAY] sending first UI frame"
)

send_frame(
    current_frame,
    fid
)


# Gate ON

gate = xread(
    0xF005
)

xwrite(
    0xF005,
    gate | 0x10
)


# Video ON

a6(
    [
        0xA6,
        0x05,
        0x01
    ],
    STATUS_VIDEO_ON,
    "video on",
    0.01
)


print(
    "[OK] UI displayed"
)


# Next frame will use 0

fid = 0


# ============================================================
# MAIN LOOP
# ============================================================

KEEPALIVE_SECONDS = 1.0
last_send = time.monotonic()
was_down = False
last_touch = time.monotonic()
last_pc_check = 0.0
pc_monitor = PCMonitor(APP_DIR)
last_theme_check = 0.0
next_animation_at = 0.0
perf_started = time.monotonic()
perf_frames = 0
perf_encode = 0.0
perf_send = 0.0
worker = threading.Thread(target=ha_worker, name="HA-worker", daemon=True)

print("VK03 监控与家居面板 — 触摸进入家居控制；闲置30秒返回PC监控。")
print("Ctrl+C 退出。")

try:
    worker.start()
    pc_monitor.start()
    while True:
        if (APP_DIR / "vk03_stop.flag").exists():
            print("[EXIT] Stop requested")
            break
        dirty = False
        if time.monotonic() - last_theme_check >= 1.0:
            dirty = appearance.refresh()
            last_theme_check = time.monotonic()
        # Preserve decoding and press edges; shorten the <=20ms wait near an animation deadline.
        touch_timeout = 20
        if appearance.animated:
            remaining_ms = int((next_animation_at - time.monotonic()) * 1000)
            touch_timeout = min(20, max(1, remaining_ms))
        data = touch.read(32, touch_timeout)
        if data:
            raw = bytes(data)
            if len(raw) >= 7:
                contact = raw[1]
                if contact == 0:
                    was_down = False
                else:
                    last_touch = time.monotonic()
                    if not was_down:
                        if page == "monitor":
                            # Wake consumes the entire press: never toggle a hidden control.
                            page = "home"
                            dirty = True
                        else:
                            result = decode_touch(raw)
                            if result is not None:
                                x, y, raw_x, raw_y = result
                                button = hit_test(x, y)
                                if button is not None:
                                    dirty = handle_action(button) or dirty
                        was_down = True

        if page != "monitor" and time.monotonic() - last_touch >= 30:
            page = "monitor"
            was_down = False
            dirty = True
        if time.monotonic() - last_pc_check >= 1:
            pc_stats = pc_monitor.snapshot()
            last_pc_check = time.monotonic()
            if page == "monitor":dirty = True

        # Results update authoritative device state on the UI thread only.
        while True:
            try:
                dirty = accept_result(ha_results.get_nowait()) or dirty
            except queue.Empty:
                break

        # One render/encode per changed UI, one send per loop at most.
        if appearance.content_changed():
            dirty = True
        if appearance.animated and time.monotonic() >= next_animation_at:
            dirty = True
        if dirty:
            frame_started = time.monotonic()
            next_animation_at = frame_started + 1.0 / appearance.settings["animation_fps"]
            current_image = render_ui()
            current_frame = encode_frame(current_image)
            perf_encode += time.monotonic() - frame_started
        now = time.monotonic()
        if dirty or now - last_send >= KEEPALIVE_SECONDS:
            send_started = time.monotonic()
            send_frame(current_frame, fid)
            perf_send += time.monotonic() - send_started
            perf_frames += 1
            fid ^= 1
            last_send = time.monotonic()
        if time.monotonic() - perf_started >= 10.0:
            elapsed = time.monotonic() - perf_started
            stats = {"fps":round(perf_frames/elapsed,1),
                     "encode_ms":round(perf_encode/max(perf_frames,1)*1000,1),
                     "send_ms":round(perf_send/max(perf_frames,1)*1000,1)}
            if appearance.media is not None:stats.update(appearance.media.diagnostics())
            try:
                temporary=APP_DIR/"vk03_performance.pending.json"
                temporary.write_text(json.dumps(stats,ensure_ascii=False),encoding="utf-8")
                os.replace(temporary,APP_DIR/"vk03_performance.json")
            except OSError:pass
            perf_started=time.monotonic()
            perf_frames=0;perf_encode=0.0;perf_send=0.0

except KeyboardInterrupt:
    print("\n[EXIT] Ctrl+C")
finally:
    pc_monitor.close()
    appearance.close()
    cleanup_hardware()
