"""Hidden launcher with single instance, rotating logs and crash-only restarts."""
import ctypes
from ctypes import wintypes
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel.CreateMutexW.restype = wintypes.HANDLE
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
kernel.CloseHandle.restype = wintypes.BOOL


def main():
    mutex = kernel.CreateMutexW(None, False, 'Local\\VK03DailyLauncher')
    error = ctypes.get_last_error()
    if not mutex:
        raise ctypes.WinError(error)
    if error == 183:
        kernel.CloseHandle(mutex)
        return
    child = None
    try:
        stop_file = ROOT / 'vk03_stop.flag'
        stop_file.unlink(missing_ok=True)
        logger = logging.getLogger('vk03')
        logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(ROOT / 'vk03_panel.log', maxBytes=1024*1024,
                                      backupCount=3, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        logger.addHandler(handler)
        executable = Path(sys.executable).with_name('python.exe')
        while not stop_file.exists():
            logger.info('Starting daily panel')
            try:
                child = subprocess.Popen(
                    [str(executable), '-u', str(ROOT / 'vk03_home_panel_daily.py')],
                    cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding='utf-8', errors='replace',
                    env={**__import__('os').environ, 'PYTHONIOENCODING':'utf-8'},
                    creationflags=subprocess.CREATE_NO_WINDOW)
                for line in child.stdout:
                    logger.info(line.rstrip())
                code = child.wait()
                child.stdout.close()
                child = None
                if code == 0:
                    logger.info('Panel exited normally; launcher stops')
                    break
                logger.warning('Panel exited with %s; retry in 30 seconds', code)
            except OSError as exc:
                logger.error('Unable to start Python: %s', type(exc).__name__)
            for _ in range(30):
                if stop_file.exists():
                    break
                time.sleep(1)
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=10)
        (ROOT / 'vk03_stop.flag').unlink(missing_ok=True)
        kernel.CloseHandle(mutex)


if __name__ == '__main__':
    main()
