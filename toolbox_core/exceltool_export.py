# -*- coding: utf-8 -*-
"""Drive the original ExcelTool2 UI for modified Data2 tables only."""
import ctypes
from ctypes import wintypes
import os
import subprocess
import time
import xml.etree.ElementTree as ET


WM_DROPFILES = 0x0233
WM_GETTEXT = 0x000D
WM_CLOSE = 0x0010
BM_CLICK = 0x00F5
SW_SHOWNOACTIVATE = 4
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040

LIST_ID = 1001
LOG_ID = 1000
EXPORT_ID = 1008


class DROPFILES(ctypes.Structure):
    _fields_ = [
        ("pFiles", wintypes.DWORD),
        ("pt_x", wintypes.LONG),
        ("pt_y", wintypes.LONG),
        ("fNC", wintypes.BOOL),
        ("fWide", wintypes.BOOL),
    ]


_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
_kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
_kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
_kernel32.GlobalLock.restype = ctypes.c_void_p
_kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
_kernel32.GlobalUnlock.restype = wintypes.BOOL
_kernel32.GlobalFree.argtypes = (wintypes.HGLOBAL,)
_kernel32.GlobalFree.restype = wintypes.HGLOBAL
_user32.GetDlgItem.argtypes = (wintypes.HWND, ctypes.c_int)
_user32.GetDlgItem.restype = wintypes.HWND
_user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_user32.PostMessageW.restype = wintypes.BOOL


def resolve_project(source_path):
    current = os.path.abspath(source_path)
    if os.path.isfile(current):
        current = os.path.dirname(current)
    while True:
        game_data = os.path.join(current, "gameData")
        tools = os.path.join(current, "tools")
        if os.path.isdir(game_data) and os.path.isdir(tools):
            data2 = os.path.join(game_data, "Data2")
            tool = os.path.join(game_data, "ExcelTool2.exe")
            missing = [path for path in (data2, tool) if not os.path.exists(path)]
            if missing:
                raise RuntimeError("项目目录不完整: " + "、".join(missing))
            return current, game_data, data2, tool
        parent = os.path.dirname(current)
        if parent == current:
            raise RuntimeError("未找到同级 gameData 与 tools 的项目根目录")
        current = parent


def modified_tables(svn_exe, data2_dir):
    result = subprocess.run(
        [svn_exe, "status", "--no-ignore", "--xml", data2_dir],
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0:
        text = (result.stderr or result.stdout or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError("SVN 状态查询失败: " + text)

    try:
        root = ET.fromstring(result.stdout)
    except ET.ParseError as e:
        raise RuntimeError("SVN 状态 XML 解析失败: " + str(e))

    files = []
    for entry in root.findall(".//entry"):
        status = entry.find("wc-status")
        if status is None or status.get("item") not in {"modified", "added", "unversioned"}:
            continue
        path = os.path.abspath(entry.get("path", ""))
        if (os.path.dirname(path).lower() == os.path.abspath(data2_dir).lower()
                and path.lower().endswith(".xlsm") and os.path.isfile(path)):
            files.append(path)
    return files


def _window_for_pid(pid):
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        window_pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if window_pid.value == pid and _user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    _user32.EnumWindows(callback, 0)
    return found[0] if found else None


def _wait_for_window(proc, timeout, cancelled):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cancelled():
            raise RuntimeError("任务已取消")
        if proc.poll() is not None:
            raise RuntimeError("ExcelTool2 启动后异常退出")
        hwnd = _window_for_pid(proc.pid)
        if hwnd:
            list_hwnd = _user32.GetDlgItem(hwnd, LIST_ID)
            log_hwnd = _user32.GetDlgItem(hwnd, LOG_ID)
            export_hwnd = _user32.GetDlgItem(hwnd, EXPORT_ID)
            if list_hwnd and log_hwnd and export_hwnd:
                return hwnd, list_hwnd, log_hwnd, export_hwnd
        time.sleep(0.1)
    raise RuntimeError("等待 ExcelTool2 窗口超时")


def _dialog_for_pid(pid):
    dialogs = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        window_pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if window_pid.value == pid and _user32.IsWindowVisible(hwnd):
            class_name = ctypes.create_unicode_buffer(256)
            _user32.GetClassNameW(hwnd, class_name, len(class_name))
            if class_name.value == "#32770":
                dialogs.append(hwnd)
        return True

    _user32.EnumWindows(callback, 0)
    return dialogs[0] if dialogs else None


def _dialog_text(hwnd):
    texts = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(child, _):
        text = _text(child)
        if text:
            texts.append(text)
        return True

    _user32.EnumChildWindows(hwnd, callback, 0)
    return "\n".join(texts)


def _confirm_dialog(hwnd):
    button = _user32.GetDlgItem(hwnd, 1) or _user32.GetDlgItem(hwnd, 2)
    if not button:
        raise RuntimeError("未找到 ExcelTool2 检查弹窗的确定按钮")
    _click(button)


def _wait_for_check_result(proc, timeout, cancelled, put):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cancelled():
            raise RuntimeError("任务已取消")
        if proc.poll() is not None:
            raise RuntimeError("ExcelTool2 在检查配置表时退出")
        dialog = _dialog_for_pid(proc.pid)
        if dialog:
            text = _dialog_text(dialog)
            if "检查文件成功" in text:
                put("ExcelTool2 检查文件成功，自动确认\n")
                _confirm_dialog(dialog)
                return
            if "检查文件失败" in text:
                _confirm_dialog(dialog)
                raise RuntimeError("ExcelTool2 检查配置表失败")
        time.sleep(0.1)
    raise RuntimeError("等待 ExcelTool2 检查结果超时")


def _send_drop(hwnd, paths):
    payload = ("\0".join(paths) + "\0\0").encode("utf-16-le")
    size = ctypes.sizeof(DROPFILES) + len(payload)
    handle = _kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, size)
    if not handle:
        raise RuntimeError("无法为 ExcelTool2 拖放文件分配内存")
    pointer = _kernel32.GlobalLock(handle)
    if not pointer:
        _kernel32.GlobalFree(handle)
        raise RuntimeError("无法锁定 ExcelTool2 拖放数据")
    try:
        drop = DROPFILES.from_address(pointer)
        drop.pFiles = ctypes.sizeof(DROPFILES)
        drop.pt_x = 0
        drop.pt_y = 0
        drop.fNC = False
        drop.fWide = True
        ctypes.memmove(pointer + ctypes.sizeof(DROPFILES), payload, len(payload))
    finally:
        _kernel32.GlobalUnlock(handle)
    if not _user32.PostMessageW(hwnd, WM_DROPFILES, handle, 0):
        _kernel32.GlobalFree(handle)
        raise RuntimeError("向 ExcelTool2 拖入文件失败")


def _text(hwnd):
    length = _user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    _user32.SendMessageW(hwnd, WM_GETTEXT, length + 1, ctypes.byref(buffer))
    return buffer.value


def _click(hwnd):
    if not _user32.PostMessageW(hwnd, BM_CLICK, 0, 0):
        raise RuntimeError("无法触发 ExcelTool2 按钮")


def _wait_for_result(proc, log_hwnd, timeout, cancelled, put):
    deadline = time.time() + timeout
    previous = ""
    success_seen_at = None
    while time.time() < deadline:
        if cancelled():
            raise RuntimeError("任务已取消")
        if proc.poll() is not None:
            raise RuntimeError("ExcelTool2 在导出完成前退出")
        dialog = _dialog_for_pid(proc.pid)
        if dialog:
            dialog_text = _dialog_text(dialog)
            if "左侧导出成功" in dialog_text:
                put("ExcelTool2 左侧导出成功，自动确认\n")
                _confirm_dialog(dialog)
                return
            if "左侧导出失败" in dialog_text:
                _confirm_dialog(dialog)
                raise RuntimeError("ExcelTool2 左侧导出失败")
        text = _text(log_hwnd)
        if text != previous:
            added = text[len(previous):] if text.startswith(previous) else text
            if added.strip():
                put("[ExcelTool2] " + added.strip().replace("\r", "").replace("\n", "\n[ExcelTool2] ") + "\n")
            previous = text
        if "单表导出失败" in text or "导出失败" in text:
            raise RuntimeError("ExcelTool2 导出失败")
        if "单表导出成功" in text or "导出成功" in text:
            if success_seen_at is None:
                success_seen_at = time.time()
            elif time.time() - success_seen_at >= 3:
                return
        time.sleep(0.2)
    raise RuntimeError("等待 ExcelTool2 导出完成超时")


def _close(proc, hwnd, timeout):
    _user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return
        time.sleep(0.1)
    raise RuntimeError("ExcelTool2 导出成功后未能关闭")


def run_export(source_path, svn_exe, put, cancelled, on_launch):
    root, game_data, data2, tool = resolve_project(source_path)
    put("项目根目录: " + root + "\n")
    put("Data2 目录: " + data2 + "\n")
    files = modified_tables(svn_exe, data2)
    if not files:
        put("Data2 中没有直接修改的 .xlsm，跳过导出与提交\n")
        return None
    put("发现 " + str(len(files)) + " 个待导出配置表:\n")
    for path in files:
        put("  " + os.path.basename(path) + "\n")

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = SW_SHOWNOACTIVATE
    proc = subprocess.Popen([tool], cwd=game_data, startupinfo=startupinfo)
    on_launch(proc)
    try:
        hwnd, list_hwnd, log_hwnd, export_hwnd = _wait_for_window(proc, 15, cancelled)
        _send_drop(hwnd, files)
        _wait_for_check_result(proc, 60, cancelled, put)
        deadline = time.time() + 30
        while time.time() < deadline:
            if cancelled():
                raise RuntimeError("任务已取消")
            if proc.poll() is not None:
                raise RuntimeError("ExcelTool2 在校验表格时退出")
            if _user32.SendMessageW(list_hwnd, 0x1004, 0, 0) >= len(files):
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("ExcelTool2 未接收全部配置表")
        _click(export_hwnd)
        _wait_for_result(proc, log_hwnd, 3600, cancelled, put)
        _close(proc, hwnd, 15)
        put("ExcelTool2 已完成并关闭\n")
        return True
    finally:
        if proc.poll() is None and cancelled():
            try:
                proc.kill()
            except Exception:
                pass
