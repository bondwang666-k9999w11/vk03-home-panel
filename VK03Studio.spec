# -*- mode: python ; coding: utf-8 -*-


from pathlib import Path
root = Path(SPECPATH)
qt = root / '.venv/Lib/site-packages/PySide6'
media_bins = [(str(p), 'PySide6') for pattern in ('avcodec-*.dll','avformat-*.dll','avutil-*.dll','swresample-*.dll','swscale-*.dll') for p in qt.glob(pattern)]
a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=media_bins,
    datas=[(str(root/'bridge'), 'bridge')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml'],
    noarchive=False,
    optimize=0,
)
# Use Windows-native ICU; never collect the developer's Poppler ICU or USB driver.
a.binaries = [v for v in a.binaries if Path(v[0]).name.lower() not in ('icuuc.dll','icuin.dll','icudt.dll','libusb0.dll')]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VK03Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VK03Studio',
)
