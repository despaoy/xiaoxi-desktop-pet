# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH).resolve()
datas = [
    (str(root / 'assets' / 'ui'), 'assets/ui'),
    (str(root / 'assets' / 'language'), 'assets/language'),
    (str(root / 'plugins'), 'plugins'),
    (str(root / 'review' / 'live2d' / 'pet.html'), 'review/live2d'),
    (str(root / 'review' / 'live2d' / 'pet.js'), 'review/live2d'),
    (str(root / 'review' / 'live2d' / 'idle-motion.js'), 'review/live2d'),
    (str(root / 'review' / 'live2d' / 'interaction-motion.js'), 'review/live2d'),
    (str(root / 'review' / 'live2d' / 'vendor'), 'review/live2d/vendor'),
    (str(root / 'review' / 'live2d' / 'silver-v26-diagnostic'),
     'review/live2d/silver-v26-diagnostic'),
]
hiddenimports = [
    'uuid',
    'pystray', 'pystray._win32',
    'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
    'PySide6.QtNetwork', 'PySide6.QtWebChannel',
    'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
]

a = Analysis(
    ['run.py'],
    pathex=[str(root), str(root / '.runtime-live2d')],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'cv2', 'numpy', 'matplotlib', 'desktop_pet.smooth_motion',
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets',
        'PySide6.QtQuick3D', 'PySide6.QtQuickControls2',
        'PySide6.QtPositioning', 'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='XiaoXi',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root / 'assets' / 'ui' / 'app-icon.ico'),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='XiaoXi',
)
