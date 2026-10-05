"""Read-only HA discovery and local mapping wizard; no device commands."""
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import urllib.request
import urllib.error

from vk03_config import (ROLES, ROLE_NAMES, DOMAINS, read_config, load_bindings,
                         validate_url, decrypt_token, save_config, normalize_bindings, NoRedirect)


def discover(address, token):
    address = validate_url(address)
    if not token or any(c.isspace() for c in token):
        raise ValueError("请输入完整的长期访问 Token")
    request = urllib.request.Request(address + "/api/states",
                headers={"Authorization": "Bearer " + token, "Accept": "application/json"})
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=8) as response:
            states = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        if code in (401, 403):
            raise ValueError("认证失败，请检查 HA 地址和 Token") from None
        raise ValueError("HA 返回 HTTP " + str(code) + "；请使用正确基础地址，避免重定向") from None
    except (urllib.error.URLError, OSError, UnicodeError, ValueError):
        raise ValueError("无法读取 HA 设备列表，请检查网络、地址及 HTTPS 证书") from None
    if not isinstance(states, list):
        raise ValueError("HA 返回了异常设备列表")
    return {item["entity_id"]: item for item in states
            if isinstance(item, dict) and isinstance(item.get("entity_id"), str)}


def choices(states, role):
    result = {}
    for entity, item in sorted(states.items()):
        if entity.partition(".")[0] not in DOMAINS[role]:
            continue
        attrs = item.get("attributes")
        name = attrs.get("friendly_name", entity) if isinstance(attrs, dict) else entity
        result[str(name) + "  [" + entity + "]"] = entity
    return result


class DeviceWizard:
    def __init__(self, parent, root, on_saved):
        self.root, self.on_saved = root, on_saved
        self.window = tk.Toplevel(parent)
        self.window.title("Home Assistant 设备匹配")
        self.window.geometry("940x770")
        self.window.minsize(840, 710)
        self.window.transient(parent)
        self.results = queue.Queue()
        self.states = None
        self.verified = None
        self.loading = False
        self.generation = 0
        self.closed = False
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        try:
            self.existing = read_config(root)
            self.bindings = load_bindings(root)
        except (OSError, ValueError, TypeError):
            self.existing = {}
            self.bindings = normalize_bindings({})
        frame = ttk.Frame(self.window, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="连接 HA，再为面板选择设备", font=("Microsoft YaHei UI", 17, "bold")).pack(anchor="w")
        ttk.Label(frame, text="米家设备需先接入 HA。此向导只读取实体，不会操作设备。未使用的项目可以留空。").pack(anchor="w", pady=7)
        credentials = ttk.Frame(frame)
        credentials.pack(fill="x")
        credentials.columnconfigure(1, weight=1)
        self.address = tk.StringVar(value=self.existing.get("ha_url", "http://homeassistant.local:8123"))
        self.token = tk.StringVar()
        ttk.Label(credentials, text="HA 地址").grid(row=0, column=0, sticky="w")
        ttk.Entry(credentials, textvariable=self.address).grid(row=0, column=1, sticky="ew", padx=10, pady=4)
        ttk.Label(credentials, text="长期访问 Token").grid(row=1, column=0, sticky="w")
        ttk.Entry(credentials, textvariable=self.token, show="*").grid(row=1, column=1, sticky="ew", padx=10, pady=4)
        self.connect_button = ttk.Button(credentials, text="连接并读取设备", command=self.connect)
        self.connect_button.grid(row=0, column=2, rowspan=2)
        ttk.Label(frame, text="已有 Token 时可留空复用；凭据仅按当前 Windows 用户加密保存在本机。").pack(anchor="w", pady=5)
        table = ttk.Frame(frame)
        table.pack(fill="both", expand=True, pady=7)
        table.columnconfigure(1, weight=1)
        for column, text in enumerate(("面板位置", "HA 实体（可输入实体 ID 搜索）", "按钮显示名称")):
            ttk.Label(table, text=text).grid(row=0, column=column, sticky="w", pady=5)
        self.selected, self.labels, self.combos, self.lookup = {}, {}, {}, {}
        for row, role in enumerate(ROLES, 1):
            binding = self.bindings[role]
            self.selected[role] = tk.StringVar(value=binding["entity_id"])
            self.labels[role] = tk.StringVar(value=binding["label"])
            ttk.Label(table, text=ROLE_NAMES[role]).grid(row=row, column=0, sticky="w", pady=7)
            combo = ttk.Combobox(table, textvariable=self.selected[role], state="disabled")
            combo.grid(row=row, column=1, sticky="ew", padx=10)
            combo.bind("<KeyRelease>", lambda event, r=role: self.filter_choices(r))
            self.combos[role] = combo
            if role in ROLES[:6]:
                ttk.Entry(table, textvariable=self.labels[role], width=16).grid(row=row, column=2)
            else:
                ttk.Label(table, text="使用实体实际单位").grid(row=row, column=2, sticky="w")
        self.status = tk.StringVar(value="请先连接 HA。保存后会重启面板以加载新的设备映射。")
        ttk.Label(frame, textvariable=self.status, wraplength=870).pack(anchor="w", pady=6)
        self.save_button = ttk.Button(frame, text="保存并应用设备匹配", command=self.save, state="disabled")
        self.save_button.pack(side="right")
        ttk.Button(frame, text="关闭", command=self.close).pack(side="right", padx=8)
        self.poll_after=self.window.after(150, self.poll)

    def close(self):
        self.closed = True
        if self.poll_after is not None:
            try:self.window.after_cancel(self.poll_after)
            except tk.TclError:pass
            self.poll_after=None
        self.generation += 1
        self.token.set("")
        self.verified = None
        self.window.destroy()

    def connect(self):
        if self.loading:
            return
        try:
            address = validate_url(self.address.get())
            token = self.token.get().strip()
            if not token:
                token = decrypt_token(self.existing["token_dpapi"])
        except (ValueError, KeyError, RuntimeError, TypeError):
            messagebox.showerror("无法连接", "请填写有效 HA 地址和 Token；已有凭据无法复用时请重新输入。", parent=self.window)
            return
        self.loading = True
        self.save_button.configure(state="disabled")
        self.connect_button.configure(state="disabled")
        self.status.set("正在后台连接 HA…")
        self.generation += 1
        generation = self.generation
        def worker():
            try:
                states = discover(address, token)
                result = (generation, states, address, token, None)
            except Exception as exc:
                result = (generation, None, None, None, str(exc) if isinstance(exc, ValueError) else "连接失败")
            self.results.put(result)
        threading.Thread(target=worker, name="HA-discovery", daemon=True).start()

    def filter_choices(self, role):
        needle = self.selected[role].get().casefold()
        self.combos[role]["values"] = [""] + [value for value in self.lookup.get(role, {}) if needle in value.casefold()]

    def poll(self):
        if self.closed:
            return
        try:
            generation, states, address, token, error = self.results.get_nowait()
            if generation == self.generation:
                self.loading = False
                self.connect_button.configure(state="normal")
                if error:
                    self.verified = None
                    self.status.set(error)
                else:
                    self.states, self.verified = states, (address, token)
                    for role in ROLES:
                        self.lookup[role] = choices(states, role)
                        self.combos[role].configure(state="normal", values=[""] + list(self.lookup[role]))
                    self.save_button.configure(state="normal")
                    self.status.set("连接成功。选择设备，也可以直接填写完整实体 ID；留空的功能将停用。")
        except queue.Empty:
            pass
        self.poll_after=self.window.after(150, self.poll)

    def save(self):
        try:
            if self.verified is None:
                raise ValueError("请先连接 HA")
            address, token = self.verified
            if validate_url(self.address.get()) != address or (self.token.get().strip() and self.token.get().strip() != token):
                raise ValueError("地址或 Token 已变化，请重新连接后保存")
            bindings = {}
            for role in ROLES:
                selected = self.selected[role].get().strip()
                entity = self.lookup[role].get(selected, selected)
                if entity and entity not in self.states:
                    raise ValueError(ROLE_NAMES[role] + " 未出现在本次 HA 设备列表中")
                bindings[role] = dict(entity_id=entity, label=self.labels[role].get())
            save_config(self.root, address, token, bindings)
        except (OSError, ValueError, RuntimeError, TypeError) as exc:
            messagebox.showerror("保存失败", str(exc), parent=self.window)
            return
        self.close()
        self.on_saved()
