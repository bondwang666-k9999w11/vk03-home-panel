"""Windows actions, isolated from editor preview. No vendor runtime."""
from PySide6.QtCore import QObject, Signal
import subprocess, threading, queue, json, os, sys
from pathlib import Path

class SystemBridge(QObject):
    snapshot=Signal(dict)
    error=Signal(str)
    def __init__(self,root):
        super().__init__();self.root=Path(root);self.jobs=queue.Queue(32);self.closed=threading.Event();self.process=None;self.seq=0
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def post(self,action,payload=None):
        try:self.jobs.put_nowait((action,payload or {}))
        except queue.Full:pass
    def run(self):
        try:
            exe=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
            self.process=subprocess.Popen([str(exe),'-NoLogo','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(self.root/'bridge/windows-worker.ps1'),'-EnableActions'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            while not self.closed.is_set():
                try:action,payload=self.jobs.get(timeout=.3)
                except queue.Empty:continue
                self.seq+=1;self.process.stdin.write(json.dumps(dict(id=str(self.seq),action=action,payload=payload))+'\n');self.process.stdin.flush()
                response=json.loads(self.process.stdout.readline())
                if not response.get('ok'):self.error.emit(response.get('error','系统操作失败'))
                elif action=='state.get':self.snapshot.emit(response.get('value',{}))
                elif action in ('volume.set','volume.muteToggle'):self.snapshot.emit(response.get('value',{}))
        except Exception as e:
            if not self.closed.is_set():self.error.emit(str(e))
        finally:
            if self.process and self.process.poll() is None:self.process.kill()
    def close(self):
        self.closed.set()
        if self.process and self.process.poll() is None:self.process.kill()
