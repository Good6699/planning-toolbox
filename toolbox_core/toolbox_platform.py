#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SVN 一键对比工具 - GUI 版 - 平台工具模块"""

import json
import os
import subprocess
import sys as _sys
import threading
import re
import urllib.parse
from datetime import datetime
import argparse
import shutil
import stat
import copy
from xlsm_zipper import apply_via_excel

def _check_office_lock(filepath):
    """检查目标文件是否被 WPS/Excel 打开（通过 ~$ 锁文件）。"""
    dirname = os.path.dirname(filepath)
    basename = os.path.basename(filepath)
    lock_name = "~$" + basename
    lock_path = os.path.join(dirname, lock_name)
    return os.path.exists(lock_path)

# ── Windows 拖拽支持（通过 ctypes 子类化 WndProc，回调中不调用任何 Python API）──
# 注释掉 tkinter 相关代码，因为现在用 pywebview 了
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, font as tkfont
    import ctypes
    from ctypes import wintypes

    # 设置 Windows API 函数的参数/返回值类型
    ctypes.windll.user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    ctypes.windll.user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    ctypes.windll.user32.CallWindowProcW.restype = ctypes.c_ssize_t
    ctypes.windll.user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    ctypes.windll.shell32.DragAcceptFiles.restype = wintypes.BOOL
    ctypes.windll.shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
    ctypes.windll.shell32.DragQueryFileW.restype = wintypes.UINT
    ctypes.windll.shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPCWSTR, wintypes.UINT]
    ctypes.windll.shell32.DragFinish.argtypes = [wintypes.HANDLE]

    class _DropTarget:
        """拖拽文件处理：WndProc 回调中用 PyGILState_Ensure 获取 GIL 后处理"""
        GWLP_WNDPROC = -4
        WM_DROPFILES = 0x0233

        def __init__(self, widget, on_files):
            self.widget = widget
            self.on_files = on_files
            self._cb = None
            self._old_proc = None
            self._pending_paths = None

        def hook(self):
            hwnd = self.widget.winfo_id()
            WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

            PyGILState_Ensure = ctypes.pythonapi.PyGILState_Ensure
            PyGILState_Ensure.restype = ctypes.c_int
            PyGILState_Release = ctypes.pythonapi.PyGILState_Release
            PyGILState_Release.argtypes = [ctypes.c_int]

            ensure = PyGILState_Ensure
            release = PyGILState_Release
            DragQueryFileW = ctypes.windll.shell32.DragQueryFileW
            DragQueryFileW.restype = wintypes.UINT
            DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPCWSTR, wintypes.UINT]
            DragFinish = ctypes.windll.shell32.DragFinish
            DragFinish.argtypes = [wintypes.HANDLE]
            create_unicode_buffer = ctypes.create_unicode_buffer

            def wndproc(hwnd, msg, wparam, lparam):
                if msg == self.WM_DROPFILES:
                    gstate = ensure()
                    try:
                        hdrop = wintypes.HANDLE(wparam)
                        count = DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
                        paths = []
                        for i in range(count):
                            buf = create_unicode_buffer(260)
                            DragQueryFileW(hdrop, i, buf, 260)
                            paths.append(buf.value)
                        DragFinish(hdrop)
                        self._pending_paths = paths
                    finally:
                        release(gstate)
                    return 0
                return ctypes.windll.user32.CallWindowProcW(self._old_proc, hwnd, msg, wparam, lparam)

            self._cb = WNDPROC(wndproc)
            self._old_proc = ctypes.windll.user32.SetWindowLongPtrW(hwnd, self.GWLP_WNDPROC, self._cb)
            ctypes.windll.shell32.DragAcceptFiles(hwnd, True)
            self.widget.after(100, self._poll)

        def _poll(self):
            if self._pending_paths is not None:
                paths = self._pending_paths
                self._pending_paths = None
                if paths:
                    self.on_files(paths)
            self.widget.after(100, self._poll)
except Exception:
    # 如果 tkinter 导入失败，就跳过拖拽支持
    _DropTarget = None

def _get_svn_path() -> str:
    """查找 svn.exe 的完整路径"""
    # 常见固定安装路径
    possible_paths = [
        r"C:\Program Files\SlikSvn\bin\svn.exe",
        r"C:\Program Files (x86)\SlikSvn\bin\svn.exe",
        r"C:\Program Files\TortoiseSVN\bin\svn.exe",
        r"C:\Program Files (x86)\TortoiseSVN\bin\svn.exe",
        r"C:\Program Files\Subversion\bin\svn.exe",
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return p
    # 从注册表查找 TortoiseSVN 安装目录
    try:
        import winreg
        for key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for subkey in (r"SOFTWARE\TortoiseSVN", r"SOFTWARE\WOW6432Node\TortoiseSVN"):
                try:
                    with winreg.OpenKey(key, subkey) as k:
                        proc_path, _ = winreg.QueryValueEx(k, "ProcPath")
                        if proc_path:
                            svn_dir = os.path.dirname(proc_path)
                            svn_exe = os.path.join(svn_dir, "svn.exe")
                            if os.path.isfile(svn_exe):
                                return svn_exe
                except (OSError, FileNotFoundError):
                    pass
    except Exception:
        pass
    # 从注册表查找 SlikSvn / VisualSVN
    try:
        import winreg
        for subkey in (r"SOFTWARE\SlikSvn\Client", r"SOFTWARE\WOW6432Node\SlikSvn\Client",
                       r"SOFTWARE\VisualSVN", r"SOFTWARE\WOW6432Node\VisualSVN"):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey) as k:
                    install_path, _ = winreg.QueryValueEx(k, "InstallPath")
                    svn_exe = os.path.join(install_path, "svn.exe")
                    if os.path.isfile(svn_exe):
                        return svn_exe
            except (OSError, FileNotFoundError):
                pass
    except Exception:
        pass
    # fallback: 从 PATH 环境变量找
    try:
        import subprocess
        r = subprocess.run(["where", "svn"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            path = r.stdout.strip().split("\n")[0].strip()
            if path and os.path.isfile(path):
                return path
    except Exception:
        pass
    return "svn"


def _diagnose_svn_missing() -> str:
    """诊断 svn 命令找不到的原因，返回具体修复提示"""
    try:
        import winreg
        for key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for subkey in (r"SOFTWARE\TortoiseSVN", r"SOFTWARE\WOW6432Node\TortoiseSVN"):
                try:
                    with winreg.OpenKey(key, subkey) as k:
                        proc_path, _ = winreg.QueryValueEx(k, "ProcPath")
                        svn_dir = os.path.dirname(proc_path)
                        svn_exe = os.path.join(svn_dir, "svn.exe")
                        if not os.path.isfile(svn_exe):
                            return ("检测到已安装 TortoiseSVN，但缺少命令行客户端。\n"
                                    "请重新运行 TortoiseSVN 安装程序 → Modify → 勾选 Command Line Client Tools。")
                        return ("TortoiseSVN 命令行工具已安装，但未添加到 PATH 环境变量。\n"
                                "请将以下路径添加到系统 PATH：\n" + svn_dir)
                except (OSError, FileNotFoundError):
                    pass
    except Exception:
        pass
    # 检查其他常见 SVN 客户端
    common_clients = [
        (r"C:\Program Files\SlikSvn\bin\svn.exe", "SlikSvn"),
        (r"C:\Program Files (x86)\SlikSvn\bin\svn.exe", "SlikSvn"),
        (r"C:\Program Files\Subversion\bin\svn.exe", "Subversion"),
        (r"C:\Program Files\VisualSVN\bin\svn.exe", "VisualSVN"),
    ]
    for exe_path, client_name in common_clients:
        if os.path.isfile(exe_path):
            return (f"已找到 {client_name} ({exe_path})，但未添加到 PATH。\n"
                    f"请将其所在目录添加到系统 PATH 环境变量。")
    # 什么都没装
    return "未检测到 SVN 客户端。请安装 TortoiseSVN（安装时勾选 Command Line Client Tools）或 SlikSvn。"


def _auto_install_svn_cli(put=None) -> tuple:
    """
    自动安装 SVN 命令行客户端。
    优先使用 winget（Windows 11 内置），回退到直接下载 SlikSvn MSI。
    返回 (success: bool, message: str)
    """
    cache_dir = os.path.join(os.environ.get('APPDATA', ''), 'planning-toolbox', 'cache')
    os.makedirs(cache_dir, exist_ok=True)

    # ── 尝试 winget ──
    try:
        if put:
            put("正在通过 winget 安装 SlikSvn（SVN 命令行工具）...\n")
        r = subprocess.run(
            ["winget", "install", "SlikSvn", "--silent", "--accept-package-agreements"],
            capture_output=True, text=True, timeout=120)
        if r.returncode in (0, 3010):
            import time
            time.sleep(2)
            svn_test = subprocess.run(["svn", "--version"], capture_output=True, timeout=10)
            if svn_test.returncode == 0:
                return True, "通过 winget 安装 SlikSvn 成功"
            # 可能 PATH 没刷新，找实际路径
            if _get_svn_path() != "svn":
                return True, "SlikSvn 已安装（svn.exe 已找到）"
        if put:
            put(f"winget 安装结果: {r.stdout.strip()[-200:]}\n")
    except FileNotFoundError:
        if put:
            put("winget 不可用，切换为直接下载...\n")
    except Exception as e:
        if put:
            put(f"winget 安装异常: {e}，切换为直接下载...\n")

    # ── 直接下载 SlikSvn MSI ──
    msi_url = "https://sliksvn.com/pub/SlikSvn/1.14.3/SlikSvn-1.14.3-x64.msi"
    msi_file = os.path.join(cache_dir, "SlikSvn-1.14.3-x64.msi")

    if not os.path.isfile(msi_file):
        if put:
            put("正在下载 SlikSvn (约 8MB)...\n")
        try:
            import urllib.request
            urllib.request.urlretrieve(msi_url, msi_file)
            if put:
                put("下载完成\n")
        except Exception as e:
            return False, f"下载 SlikSvn 失败: {e}"

    if put:
        put("正在静默安装 SlikSvn...\n")
    try:
        r = subprocess.run(
            ["msiexec", "/i", msi_file, "/passive", "/norestart"],
            capture_output=True, text=True, timeout=120)
        if r.returncode in (0, 3010):
            import time
            time.sleep(3)
            svn_test = subprocess.run(["svn", "--version"], capture_output=True, timeout=10)
            if svn_test.returncode == 0:
                return True, "SlikSvn 安装成功"
            if _get_svn_path() != "svn":
                return True, "SlikSvn 已安装（svn.exe 已找到）"
            return True, "SlikSvn 安装完成（可能需要重启应用或电脑才能生效）"
        return False, f"SlikSvn 安装失败 (msiexec 返回 {r.returncode})"
    except Exception as e:
        return False, f"SlikSvn 安装异常: {e}"


def _get_subprocess_kwargs():
    """获取 subprocess 参数，Windows 下隐藏 CMD 窗口"""
    kwargs = {}
    if _sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = si
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


def _get_bat_subprocess_kwargs():
    """获取 subprocess 参数，适用于调用 .bat 脚本。
    与 _get_subprocess_kwargs 不同，不加 CREATE_NO_WINDOW。
    某些 .bat 内部调用的旧版 Python/C 扩展（如 Python 2.7 的 pyexpat）
    在没有控制台时会加载失败，需要隐藏控制台而非完全无控制台。"""
    kwargs = {}
    if _sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = si
    return kwargs
