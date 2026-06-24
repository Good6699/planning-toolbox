# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('G:\\DGameAI\\workspace\\toolbox_core\\templates', 'templates'), ('G:\\DGameAI\\workspace\\toolbox_core\\assets', 'assets'), ('G:\\DGameAI\\workspace\\toolbox_core\\splash', 'splash'), ('G:\\DGameAI\\workspace\\toolbox_core\\py_modules/_tcl_data', '_tcl_data'), ('G:\\DGameAI\\workspace\\toolbox_core\\py_modules/_tk_data', '_tk_data'), ('G:\\DGameAI\\workspace\\_cmp_worker.py', '.'), ('G:\\DGameAI\\workspace\\_merge_analyzer.py', '.'), ('G:\\DGameAI\\workspace\\_merge_analyze_worker.py', '.'), ('G:\\DGameAI\\workspace\\_export_error_code_erl.py', '.'), ('G:\\DGameAI\\workspace\\toolbox_core\\_updater.bat', '.')]
binaries = []
hiddenimports = ['win32timezone', 'cffi', 'pycparser', 'webview', 'webview.dom', 'webview.platforms', 'webview.platforms.winforms', 'webview.platforms.edgechromium', 'webview.js', 'proxy_tools', 'bottle', '_text_check', 'win11toast']
tmp_ret = collect_all('webview')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['G:\\DGameAI\\workspace\\main.py'],
    pathex=['G:\\DGameAI\\workspace\\toolbox_core'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['scipy', 'numpy', 'pandas', 'pyarrow', 'llvmlite', 'numba', 'matplotlib', 'networkx', 'scipy.libs', 'numpy.libs'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='策划工具箱',
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
    icon=['G:\\DGameAI\\workspace\\toolbox_core\\assets\\app_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='策划工具箱',
)
