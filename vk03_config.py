"""Public device schema and per-user Windows DPAPI credentials.

Importing this module does not contact HA, access USB, or decrypt credentials.
"""
import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

VERSION = "1.0.0"
ROLES = ("light_1", "light_2", "light_3", "light_4", "climate", "purifier",
         "temperature", "humidity", "pm25", "pm10")
ROLE_NAMES = dict(zip(ROLES, ("灯具 1", "灯具 2", "灯具 3", "灯具 4", "空调", "净化器",
                            "环境温度", "相对湿度", "PM2.5", "PM10")))
DOMAINS = {role: ("sensor",) for role in ROLES}
DOMAINS.update({role: ("switch", "light") for role in ROLES[:4]})
DOMAINS.update(climate=("climate",), purifier=("fan",))


def empty_bindings():
    return {role: {"entity_id": "", "label": ROLE_NAMES[role].replace("具 ", "")}
            for role in ROLES}


def normalize_bindings(data):
    if not isinstance(data, dict):
        raise ValueError("设备映射必须是 JSON 对象")
    result = empty_bindings()
    controls = set()
    for role in ROLES:
        item = data.get(role, {})
        if not isinstance(item, dict):
            raise ValueError(ROLE_NAMES[role] + " 配置格式错误")
        entity = item.get("entity_id", "")
        label = item.get("label", result[role]["label"])
        if not isinstance(entity, str) or not isinstance(label, str):
            raise ValueError(ROLE_NAMES[role] + " 配置必须是文字")
        entity, label = entity.strip(), label.strip()
        if entity and (not re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", entity)
                       or entity.partition(".")[0] not in DOMAINS[role]):
            raise ValueError(ROLE_NAMES[role] + " 实体类型不匹配")
        if role in ROLES[:6] and entity:
            if entity in controls:
                raise ValueError("同一控制实体不能分配给多个按钮")
            controls.add(entity)
        if not label or len(label) > 24 or any(ord(c) < 32 for c in label):
            raise ValueError(ROLE_NAMES[role] + " 显示名称须为 1–24 个字符")
        result[role] = dict(entity_id=entity, label=label)
    return result


def demo_bindings():
    """Clearly synthetic entities, only used by the no-hardware preview."""
    return {role: dict(entity_id=DOMAINS[role][-1] + ".example_" + role,
                       label=empty_bindings()[role]["label"]) for role in ROLES}


def read_config(root):
    path = Path(root) / "vk03_config.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("本机配置格式错误，请重新打开设备匹配向导")
    return data


def load_bindings(root):
    return normalize_bindings(read_config(root).get("bindings", {}))


def validate_url(address):
    address = address.strip().rstrip("/")
    try:
        url = urlsplit(address)
        if (url.scheme not in ("http", "https") or not url.hostname or url.username
                or url.password or url.query or url.fragment):
            raise ValueError
        url.port
    except (ValueError, TypeError):
        raise ValueError("填写 HA 基础地址，例如 http://homeassistant.local:8123") from None
    return address


def _dpapi(raw, protect):
    if os.name != "nt":
        raise RuntimeError("凭据加密功能只支持 Windows")
    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]
    buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    source, output = Blob(len(raw), buffer), Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if protect:
        fn = crypt.CryptProtectData
        fn.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    else:
        fn = crypt.CryptUnprotectData
        fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise RuntimeError("Token 加解密失败，请使用原 Windows 用户，或重新输入 Token")
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(output.data)


def encrypt_token(token):
    token = token.strip()
    if not token or any(c.isspace() for c in token):
        raise ValueError("Token 为空或含空白字符")
    return base64.b64encode(_dpapi(token.encode("utf-8"), True)).decode("ascii")


def decrypt_token(encoded):
    return _dpapi(base64.b64decode(encoded, validate=True), False).decode("utf-8")


def save_config(root, address, token, bindings):
    """One atomic file prevents credentials and device mapping diverging."""
    data = dict(schema_version=1, ha_url=validate_url(address),
                token_dpapi=encrypt_token(token), bindings=normalize_bindings(bindings))
    path = Path(root) / "vk03_config.json"
    temp = path.with_suffix(".pending.json")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def configured(root):
    try:
        data = read_config(root)
        validate_url(data.get("ha_url", ""))
        normalize_bindings(data["bindings"])
        return bool(data.get("token_dpapi"))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False
