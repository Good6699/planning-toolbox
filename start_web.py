#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只启动 Flask 服务，用浏览器访问"""
import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
toolbox_core_dir = os.path.join(script_dir, "toolbox_core")
if os.path.isdir(toolbox_core_dir) and toolbox_core_dir not in sys.path:
    sys.path.insert(0, toolbox_core_dir)

pm = os.path.join(toolbox_core_dir, "py_modules")
if not os.path.isdir(pm):
    pm = os.path.join(os.path.dirname(toolbox_core_dir), "py_modules")
if os.path.isdir(pm) and pm not in sys.path:
    sys.path.insert(0, pm)
    # 手动添加 pywin32 需要的子目录
    for subdir in ["win32", "win32\\lib", "pythonwin"]:
        full_path = os.path.join(pm, subdir)
        if os.path.isdir(full_path) and full_path not in sys.path:
            sys.path.insert(0, full_path)

# 添加 DLL 搜索路径
if os.path.isdir(pm):
    pywin32_dll = os.path.join(pm, "pywin32_system32")
    if os.path.isdir(pywin32_dll):
        os.add_dll_directory(pywin32_dll)
    os.add_dll_directory(pm)
    # 设置 Tcl/Tk
    tcl_dir = os.path.join(pm, "_tcl_data")
    tk_dir = os.path.join(pm, "_tk_data")
    if os.path.isdir(tcl_dir):
        os.environ["TCL_LIBRARY"] = tcl_dir
    if os.path.isdir(tk_dir):
        os.environ["TK_LIBRARY"] = tk_dir
    os.environ["PATH"] = pm + os.pathsep + os.environ.get("PATH", "")

os.chdir(toolbox_core_dir)

from web_app import app
from werkzeug.serving import make_server

print("启动策划工具箱 Web 服务...")
print("请在浏览器中打开: http://127.0.0.1:18123")
print("按 Ctrl+C 停止服务")

server = make_server("127.0.0.1", 18123, app, threaded=True)
try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\n正在停止服务...")
    server.shutdown()
