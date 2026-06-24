# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\admin\\.qclaw\\workspace\\main.py'],
    pathex=['C:\\Users\\admin\\.qclaw\\workspace\\toolbox_core'],
    binaries=[],
    datas=[('C:\\Users\\admin\\.qclaw\\workspace\\toolbox_core\\templates', 'templates'), ('C:\\Users\\admin\\.qclaw\\workspace\\toolbox_core\\assets', 'assets'), ('C:\\Users\\admin\\.qclaw\\workspace\\toolbox_core\\splash', 'splash'), ('C:\\Users\\admin\\.qclaw\\workspace\\_cmp_worker.py', '.'), ('C:\\Users\\admin\\.qclaw\\workspace\\_merge_analyzer.py', '.'), ('C:\\Users\\admin\\.qclaw\\workspace\\_merge_analyze_worker.py', '.'), ('C:\\Users\\admin\\.qclaw\\workspace\\_export_error_code_erl.py', '.'), ('C:\\Users\\admin\\.qclaw\\workspace\\toolbox_core\\_updater.bat', '.')],
    hiddenimports=['win32timezone', 'cffi', 'pycparser'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='策划工具箱_v1.0.1_20260531_0955',
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
    icon=['C:\\Users\\admin\\.qclaw\\workspace\\toolbox_core\\assets\\app_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='策划工具箱_v1.0.1_20260531_0955',
)
