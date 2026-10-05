"""Windowless appearance app with tray; panel runs in its verified Python runtime."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageDraw
import pystray
from vk03_appearance_editor import Editor, ROOT
from vk03_config import configured, VERSION
from vk03_device_setup import DeviceWizard

kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.CreateMutexW.argtypes = [ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
kernel.CreateMutexW.restype = wintypes.HANDLE
kernel.CreateEventW.argtypes = [ctypes.c_void_p,wintypes.BOOL,wintypes.BOOL,wintypes.LPCWSTR]
kernel.CreateEventW.restype = wintypes.HANDLE
for name in ('CloseHandle','SetEvent','ResetEvent'):
    getattr(kernel,name).argtypes = [wintypes.HANDLE]
kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE,wintypes.DWORD]


def find_python():
    candidates = [ROOT/'.venv'/'Scripts'/'pythonw.exe']
    if not getattr(sys,'frozen',False):candidates.append(Path(sys.executable).with_name('pythonw.exe'))
    for path in candidates:
        if path.is_file():return str(path)
    try:
        result = subprocess.run(['py','-c','import sys; print(sys.executable)'],capture_output=True,text=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode == 0:
            path=Path(result.stdout.strip()).with_name('pythonw.exe')
            if path.is_file():return str(path)
    except (OSError, subprocess.TimeoutExpired):pass
    for base in [Path(os.environ.get('LOCALAPPDATA',''))/'Python', Path(os.environ.get('LOCALAPPDATA',''))/'Programs'/'Python']:
        if base.exists():
            for path in sorted(base.glob('*/pythonw.exe'),reverse=True):
                if path.is_file():return str(path)
    raise RuntimeError('找不到 Python，请按照 docs/INSTALL.md 安装运行依赖。')


class App:
    def __init__(self, window, event):
        self.window,self.event=window,event
        self.messages=queue.Queue()
        self.child=None
        self.stopping=False
        self.device_dialog=None
        self.restart_after_stop=False
        self.editor=Editor(window)
        window.title('VK03 控制中心 v'+VERSION)
        window.protocol('WM_DELETE_WINDOW',self.hide)
        bar=ttk.Frame(window,padding=(20,0,20,12));bar.pack(fill='x')
        ttk.Button(bar,text='启动面板',command=self.start_panel).pack(side='left')
        ttk.Button(bar,text='停止面板',command=lambda:self.stop_panel(False)).pack(side='left',padx=10)
        ttk.Button(bar,text='HA 设备匹配',command=self.open_device_setup).pack(side='left',padx=5)
        ttk.Button(bar,text='启用 CPU 温度',command=self.enable_cpu).pack(side='left',padx=5)
        ttk.Label(bar,text='关闭窗口后驻留托盘；右键托盘图标可退出。').pack(side='left')
        window.geometry('1030x915')
        icon=Image.new('RGB',(64,64),'#E4F3E9');d=ImageDraw.Draw(icon)
        d.rounded_rectangle((10,10,54,54),radius=12,fill='#209F68')
        d.line((20,22,32,42,44,22),fill='white',width=5)
        self.tray=pystray.Icon('VK03',icon,'VK03 控制中心',menu=pystray.Menu(
            pystray.MenuItem('打开设置',lambda:self.messages.put('show'),default=True),
            pystray.MenuItem('启动面板',lambda:self.messages.put('start')),
            pystray.MenuItem('停止面板',lambda:self.messages.put('stop')),
            pystray.MenuItem('退出程序并停止面板',lambda:self.messages.put('exit'))))
        threading.Thread(target=self.run_tray,daemon=True).start()
        window.after(200,self.poll)
        if configured(ROOT):
            self.start_panel()
            if '--background' in sys.argv:self.hide()
        else:
            self.editor.status.set('首次使用：请连接 HA 并选择自己的设备。')
            window.after(300,self.open_device_setup)

    def run_tray(self):
        try:self.tray.run()
        except Exception as exc:self.messages.put(('tray_error',str(exc)))

    def open_device_setup(self):
        if self.device_dialog is not None and not self.device_dialog.closed:
            self.device_dialog.window.deiconify();self.device_dialog.window.lift();return
        self.show()
        self.device_dialog=DeviceWizard(self.window,ROOT,self.configuration_saved)

    def configuration_saved(self):
        self.restart_after_stop=True
        self.stop_panel(False)

    def enable_cpu(self):
        script=ROOT/'enable_cpu_sensors.ps1'
        required=[script,ROOT/'sensors'/'VK03Sensors.exe',ROOT/'sensors'/'PawnIO_setup.exe']
        missing=[str(p) for p in required if not p.is_file()]
        if missing:
            messagebox.showerror('CPU 温度组件不完整','CPU 温度为选装组件，请按照 docs/CPU-SENSORS.md 准备文件。缺少：\n'+'\n'.join(missing));return
        if not messagebox.askyesno('启用 CPU 温度','将启动你准备的官方 PawnIO 安装程序，安装驱动并创建管理员权限的采集任务。是否继续？'):return
        try:
            shell=ctypes.WinDLL('shell32',use_last_error=True)
            shell.ShellExecuteW.argtypes=[wintypes.HWND,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.LPCWSTR,ctypes.c_int]
            shell.ShellExecuteW.restype=ctypes.c_void_p
            args=subprocess.list2cmdline(['-NoProfile','-ExecutionPolicy','Bypass','-File',str(script)])
            result=shell.ShellExecuteW(None,'runas','powershell.exe',args,str(ROOT),1)
            if not result or result<=32:raise RuntimeError('Windows 未启动安装程序（授权取消或启动失败，代码 '+str(result)+'）。')
            self.cpu_setup_started=time.time()
            self.cpu_setup_message=None
            self.editor.status.set('已请求启动，等待安装脚本确认；请查看安装窗口。')
        except Exception as exc:messagebox.showerror('CPU 温度启用失败',str(exc))

    def start_panel(self):
        if self.stopping:return
        if not configured(ROOT):self.open_device_setup();return
        if self.child is not None and self.child.poll() is None:
            self.editor.status.set('面板已在后台运行。');return
        try:
            for name in ['vk03_launcher.py','vk03_home_panel_daily.py','vk03_theme.py','vk03_media.py','vk03_monitor.py','vk03_config.py','vk03_device_setup.py','vk03_config.json']:
                if not (ROOT/name).is_file():raise RuntimeError('安装目录缺少 '+name+'，请把程序放在 C:\\VK03。')
            subprocess.run(['schtasks.exe','/Run','/TN','VK03 CPU Sensors'],capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
            self.child=subprocess.Popen([find_python(),str(ROOT/'vk03_launcher.py')],cwd=str(ROOT),creationflags=subprocess.CREATE_NO_WINDOW)
            self.editor.status.set('已启动面板。关闭设置窗口后程序继续在托盘运行。')
        except Exception as exc:messagebox.showerror('启动失败',str(exc))

    def stop_panel(self, exiting):
        if self.stopping:return
        self.stopping=True
        self.editor.status.set('正在停止面板并释放 USB…')
        def task():
            try:
                (ROOT/'vk03_stop.flag').touch()
                (ROOT/'vk03_sensors_stop.flag').touch()
                # Wait for both the launcher and panel instance mutex to disappear.
                probe=ctypes.WinDLL('kernel32',use_last_error=True)
                probe.OpenMutexW.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.LPCWSTR]
                probe.OpenMutexW.restype=wintypes.HANDLE
                stopped=False
                for _ in range(150):
                    handles=[probe.OpenMutexW(0x100000,False,name) for name in ('Local\\VK03DailyPanel','Local\\VK03DailyLauncher')]
                    running=any(handles)
                    for handle in handles:
                        if handle:kernel.CloseHandle(handle)
                    if not running:stopped=True;break
                    time.sleep(.1)
                self.messages.put(('stopped',exiting,stopped))
            except Exception as exc:self.messages.put(('stop_error',str(exc)))
        threading.Thread(target=task,daemon=True).start()

    def poll(self):
        if getattr(self,'cpu_setup_started',None) is not None:
            try:
                import json
                data=json.loads((ROOT/'vk03_cpu_setup_status.json').read_text(encoding='utf-8-sig'))
                if data.get('timestamp',0)>=self.cpu_setup_started-1:
                    message=data.get('message','')
                    if message!=self.cpu_setup_message:
                        self.cpu_setup_message=message;self.editor.status.set(message)
                    if data.get('state') in ('success','error'):self.cpu_setup_started=None
            except (OSError,ValueError,TypeError):pass
            if self.cpu_setup_started is not None and time.time()-self.cpu_setup_started>30 and self.cpu_setup_message is None:
                self.cpu_setup_started=None
                messagebox.showerror('安装脚本未响应','请双击 C:\\VK03\\CPU温度安装诊断.cmd，查看窗口中的具体错误。')
        if kernel.WaitForSingleObject(self.event,0)==0:
            kernel.ResetEvent(self.event);self.show()
        try:
            while True:
                item=self.messages.get_nowait()
                if item=='show':self.show()
                elif item=='start':self.start_panel()
                elif item=='stop':self.stop_panel(False)
                elif item=='exit':self.stop_panel(True)
                elif item[0]=='stopped':
                    self.stopping=False
                    if item[2]:
                        self.editor.status.set('面板已停止。屏幕可能保留最后一帧。')
                        if item[1]:self.editor.theme.close();self.tray.stop();self.window.destroy();return
                        if self.restart_after_stop:
                            self.restart_after_stop=False
                            self.child=None
                            self.start_panel()
                    else:
                        self.restart_after_stop=False
                        self.show();messagebox.showwarning('尚未停止','面板仍在运行，请使用 C:\\VK03 中的新版停止工具后再退出。')
                elif item[0]=='tray_error':
                    self.window.protocol('WM_DELETE_WINDOW',lambda:self.stop_panel(True))
                    self.show();messagebox.showerror('托盘启动失败',item[1])
                elif item[0]=='stop_error':
                    self.stopping=False;self.show();messagebox.showerror('停止失败',item[1])
        except queue.Empty:pass
        self.window.after(200,self.poll)

    def hide(self):
        if self.editor.pending_preview is not None:
            self.window.after_cancel(self.editor.pending_preview)
            self.editor.pending_preview=None
        self.editor.theme.close()
        self.window.withdraw()

    def show(self):
        self.editor.theme.apply(self.editor.settings)
        self.window.deiconify();self.window.lift();self.window.focus_force()


def main():
    if '--self-test' in sys.argv:
        import json
        report = {}
        try:
            window = tk.Tk(); window.withdraw()
            editor = Editor(window)
            window.update_idletasks()
            for page in ('监控页', '首页', '空调', '净化器'):
                editor.page.set(page); editor.redraw()
            report['window_and_previews'] = True
            if '--ui-only' in sys.argv:
                report['tray'] = 'not tested: UI-only mode'
                editor.theme.close();window.destroy()
                (ROOT/'vk03_exe_test.json').write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
                return
            test_tray = pystray.Icon('VK03Test', Image.new('RGB', (32,32), '#209F68'), 'VK03 test')
            test_tray.run_detached()
            time.sleep(.5)
            test_tray.stop()
            report['tray'] = True
            editor.theme.close();window.destroy()
        except Exception as exc:
            report['error'] = str(exc)
        (ROOT/'vk03_exe_test.json').write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
        return
    mutex=kernel.CreateMutexW(None,False,'Local\\VK03ControlCenter')
    existing=ctypes.get_last_error()==183
    event=kernel.CreateEventW(None,True,False,'Local\\VK03ControlCenterShow')
    if not mutex or not event:raise ctypes.WinError(ctypes.get_last_error())
    try:
        if existing:
            if '--background' not in sys.argv:kernel.SetEvent(event)
            return
        window=tk.Tk()
        try:App(window,event)
        except Exception as exc:
            messagebox.showerror('VK03 启动失败',str(exc));window.destroy();return
        window.mainloop()
    finally:
        kernel.CloseHandle(event);kernel.CloseHandle(mutex)


if __name__=='__main__':main()
