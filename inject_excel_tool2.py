#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExcelTool2 注入导出工具
启动 ExcelTool2.exe，模拟拖入 xlsm 文件，自动点击「左侧导出」，
等待导出完成后关闭窗口。

用法:
  python inject_excel_tool2.py --exe <ExcelTool2.exe路径> --xlsm <ErrorMessage.xlsm路径>

依赖:
  - Python 标准库 (ctypes, subprocess, time)
  - Windows 系统 (Win32 API)
  - comtypes (可选, 用于更可靠的按钮查找, pip install comtypes)
"""

import argparse
import ctypes
import ctypes.wintypes
import os
import subprocess
import sys
import time
import threading


# comtypes 可选导入，用于 UI Automation 更可靠地查找按钮
try:
    import comtypes
    from comtypes import IUnknown, GUID, POINTER, HRESULT
    import comtypes.client
    _HAS_COMTYPES = True
except ImportError:
    _HAS_COMTYPES = False


# ═══════════════════════════════════════════════════════════════════
#  Win32 API 常量与类型
# ═══════════════════════════════════════════════════════════════════

WM_CLOSE = 0x0010
WM_DROPFILES = 0x0233
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E

GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040
GHND = GMEM_MOVEABLE | GMEM_ZEROINIT

S_OK = 0
CHILDID_SELF = 0
SELFLAG_TAKEFOCUS = 0x1
SELFLAG_TAKESELECTION = 0x2

OBJID_CLIENT = 0xFFFFFFFC

# AccState constants
STATE_SYSTEM_INVISIBLE = 0x00008000
STATE_SYSTEM_UNAVAILABLE = 0x00000001

# IID for IAccessible
IID_IAccessible = "{618736E0-3C3D-11CF-810C-00AA00389B71}"

# CLSID for Accessibility
CLSID_ACC = "{1EA4DBF0-3C3D-11CF-810C-00AA00389B71}"


class DROPFILES(ctypes.Structure):
    _fields_ = [
        ("pFiles", ctypes.wintypes.DWORD),
        ("pt", ctypes.wintypes.POINT),
        ("fNC", ctypes.wintypes.BOOL),
        ("fWide", ctypes.wintypes.BOOL),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


# Win32 API 函数
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

user32.FindWindowW.restype = ctypes.wintypes.HWND
user32.FindWindowW.argtypes = [ctypes.wintypes.LPCWSTR, ctypes.wintypes.LPCWSTR]
user32.EnumWindows.restype = ctypes.wintypes.BOOL
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.LPWSTR, ctypes.c_int]
user32.EnumChildWindows.restype = ctypes.wintypes.BOOL
user32.GetClassNameW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.restype = ctypes.wintypes.BOOL
user32.GetWindowRect.restype = ctypes.wintypes.BOOL
user32.GetClientRect.restype = ctypes.wintypes.BOOL
user32.ClientToScreen.restype = ctypes.wintypes.BOOL
user32.SendMessageW.restype = ctypes.c_void_p
user32.SendMessageW.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.UINT, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]
user32.PostMessageW.restype = ctypes.wintypes.BOOL
user32.PostMessageW.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.UINT, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]
user32.SetForegroundWindow.restype = ctypes.wintypes.BOOL

kernel32.GlobalAlloc.restype = ctypes.wintypes.HGLOBAL
kernel32.GlobalAlloc.argtypes = [ctypes.wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = ctypes.wintypes.BOOL
kernel32.GlobalUnlock.argtypes = [ctypes.wintypes.HGLOBAL]
kernel32.GetLastError.restype = ctypes.wintypes.DWORD

shell32.DragAcceptFiles.restype = None  # void
shell32.DragAcceptFiles.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.BOOL]
shell32.ShellExecuteW.restype = ctypes.c_void_p
shell32.ShellExecuteW.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.LPCWSTR, ctypes.wintypes.LPCWSTR, ctypes.wintypes.LPCWSTR, ctypes.wintypes.LPCWSTR, ctypes.c_int]

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)


# ═══════════════════════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════════════════════

def _get_window_text(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def _get_class_name(hwnd):
    buf = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(hwnd, buf, 128)
    return buf.value


def _find_windows_by_title(title_substr, exact=False):
    """按窗口标题查找所有匹配的顶级窗口句柄"""
    results = []

    def _enum_proc(hwnd, _):
        text = _get_window_text(hwnd)
        if text:
            if exact:
                if text == title_substr:
                    results.append(hwnd)
            else:
                if title_substr in text:
                    results.append(hwnd)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    proc = WNDENUMPROC(_enum_proc)
    user32.EnumWindows(proc, 0)
    return results


def _find_child_windows(hwnd_parent):
    """枚举指定窗口的所有子窗口"""
    results = []

    def _enum_child(hwnd, _):
        text = _get_window_text(hwnd)
        cls = _get_class_name(hwnd)
        visible = bool(user32.IsWindowVisible(hwnd))
        results.append((hwnd, cls, text, visible))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    proc = WNDENUMPROC(_enum_child)
    user32.EnumChildWindows(hwnd_parent, proc, 0)
    return results


def _send_drop_all(hwnd_main, file_path):
    """向窗口及所有子窗口发送 WM_DROPFILES，尝试多次"""
    abs_path = os.path.abspath(file_path)

    def _build_drop_mem():
        path_encoded = abs_path.encode("utf-16-le") + b"\x00\x00"
        dfs = ctypes.sizeof(DROPFILES)
        total = dfs + len(path_encoded)
        h_mem = kernel32.GlobalAlloc(GHND, total)
        if not h_mem:
            return None
        p_mem = kernel32.GlobalLock(h_mem)
        if not p_mem:
            kernel32.GlobalFree(h_mem)
            return None
        df = DROPFILES()
        df.pFiles = dfs
        df.pt.x = 50
        df.pt.y = 50
        df.fNC = False
        df.fWide = True
        ctypes.memmove(p_mem, ctypes.byref(df), dfs)
        ctypes.memmove(p_mem + dfs, path_encoded, len(path_encoded))
        kernel32.GlobalUnlock(h_mem)
        return h_mem

    # 先确保窗口接受拖拽
    shell32.DragAcceptFiles(hwnd_main, True)

    targets = [hwnd_main]
    # 递归收集所有子窗口
    def _collect(hwnd):
        targets.append(hwnd)
        children = _find_child_windows(hwnd)
        for ch, _, _, _ in children:
            _collect(ch)
    _collect(hwnd_main)

    # 去重
    seen = set()
    unique_targets = []
    for h in targets:
        if h not in seen:
            seen.add(h)
            unique_targets.append(h)

    for hwnd in unique_targets:
        h_mem = _build_drop_mem()
        if h_mem is None:
            continue
        user32.SendMessageW(hwnd, WM_DROPFILES, h_mem, 0)

    return True, f"拖拽发送至 {len(unique_targets)} 个窗口"


def _click_window(hwnd):
    """通过发送鼠标消息来点击窗口/控件"""
    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False

    center_x = (rect.left + rect.right) // 2
    center_y = (rect.top + rect.bottom) // 2

    lparam = (center_y << 16) | (center_x & 0xFFFF)
    user32.PostMessageW(hwnd, 0x0201, 1, lparam)  # WM_LBUTTONDOWN
    time.sleep(0.05)
    user32.PostMessageW(hwnd, 0x0202, 0, lparam)  # WM_LBUTTONUP
    return True


# 策略 5: 如果 WM_DROPFILES 全部失败，用 CopyFile + 模拟拖拽路径覆盖
def _write_drop_via_browser_dialog(hwnd_main, file_path):
    """如果程序需要从文件选择框打开，尝试模拟 Ctrl+O"""
    user32.SetForegroundWindow(hwnd_main)
    time.sleep(0.3)
    # Ctrl+O
    VK_CONTROL = 0x11
    KEYEVENTF_KEYUP = 0x0002
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
    ctypes.windll.user32.keybd_event(0x4F, 0, 0, 0)  # 'O'
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(0x4F, 0, KEYEVENTF_KEYUP, 0)
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    return True


def _try_uiautomation_click(hwnd_parent, button_text):
    """使用 UI Automation 查找并点击按钮（通过 IAccessible）"""
    # 尝试用 comtypes/UIAutomation
    try:
        import comtypes
        import comtypes.client

        comtypes.CoInitialize()

        # 创建 IUIAutomation 对象
        clsid = "{FF48DBA4-60EF-4200-AA87-6AAAC0AFSDFC}"  # 需要正确的 CLSID
        # 实际上正确的 CLSID 是:
        # CLSID_CUIAutomation = "{FF48DBA4-60EF-4200-AA87-6AAAC0AFDDFC}"

        from comtypes.gen import UIAutomationClient as UIA

        ui_auto = comtypes.client.CreateObject(
            "{FF48DBA4-60EF-4200-AA87-6AAAC0AFDDFC}",
            interface=UIA.IUIAutomation
        )

        # 从 HWND 获取元素
        element = ui_auto.ElementFromHandle(hwnd_parent)
        condition = ui_auto.CreatePropertyCondition(
            UIA.UIA_NamePropertyId, button_text
        )
        button = element.FindFirst(UIA.TreeScope_Subtree, condition)
        if button:
            # 调起 Invoke 模式
            invoker = button.GetCurrentPattern(UIA.UIA_InvokePatternId)
            invoker.Invoke()
            return True

        # 也尝试找 Button 控件类型
        condition2 = ui_auto.CreatePropertyCondition(
            UIA.UIA_ControlTypePropertyId, UIA.UIA_ButtonControlTypeId
        )
        all_buttons = element.FindAll(UIA.TreeScope_Subtree, condition2)
        for btn in all_buttons:
            name = btn.CurrentName
            if button_text in name:
                invoker = btn.GetCurrentPattern(UIA.UIA_InvokePatternId)
                invoker.Invoke()
                return True

    except ImportError:
        pass  # 没有 comtypes，降级
    except Exception as e:
        pass  # UIA 失败，降级

    return False


def _try_accessible_click(hwnd, button_text):
    """使用 IAccessible 接口查找并点击按钮"""
    try:
        import comtypes
        from comtypes import IUnknown, GUID, POINTER, HRESULT
        import comtypes.client

        comtypes.CoInitialize()

        # 定义 IAccessible 接口（简化版）
        class IAccessible(IUnknown):
            _iid_ = GUID("{618736E0-3C3D-11CF-810C-00AA00389B71}")

        # 通过 OBJID_CLIENT 和 HWND 获取 IAccessible
        OBJID_CLIENT = 0xFFFFFFFC
        CHILDID_SELF = 0

        acc = ctypes.c_void_p()
        result = ole32.AccessibleObjectFromWindow(
            hwnd, OBJID_CLIENT,
            ctypes.byref(GUID("{618736E0-3C3D-11CF-810C-00AA00389B71}")),
            ctypes.byref(acc)
        )
    except:
        pass
    return False


def _find_button_by_text(hwnd_parent, text_substr):
    """递归查找子窗口，按文本匹配"""
    def _search(hwnd):
        win_text = _get_window_text(hwnd)
        if win_text and text_substr in win_text:
            return hwnd
        children = _find_child_windows(hwnd)
        for child_hwnd, _, _, _ in children:
            result = _search(child_hwnd)
            if result:
                return result
        return None

    return _search(hwnd_parent)


# ═══════════════════════════════════════════════════════════════════
#  ExcelTool2 管理器
# ═══════════════════════════════════════════════════════════════════

class ExcelTool2Manager:
    def __init__(self, exe_path, xlsm_path, output_dir):
        self.exe_path = os.path.abspath(exe_path)
        self.xlsm_path = os.path.abspath(xlsm_path)
        self.output_dir = os.path.abspath(output_dir)
        self.proc = None
        self.main_hwnd = None

    def log(self, msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    def launch(self, timeout=30):
        """启动 ExcelTool2.exe"""
        if not os.path.isfile(self.exe_path):
            raise FileNotFoundError(f"ExcelTool2.exe 不存在: {self.exe_path}")

        self.log(f"启动: {self.exe_path}")
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= 1  # STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 5  # SW_SHOW

        self.proc = subprocess.Popen(
            [self.exe_path],
            startupinfo=startupinfo,
        )

        self.log(f"进程 PID: {self.proc.pid}")

        self.log("等待窗口出现...")
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                self.log(f"进程已退出，退出码={self.proc.returncode}")
                raise RuntimeError(f"ExcelTool2.exe 提前退出 (退出码={self.proc.returncode})")

            all_hwnds = []
            def _enum_proc(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    all_hwnds.append(hwnd)
                return True
            user32.EnumWindows(WNDENUMPROC(_enum_proc), 0)

            for hwnd in all_hwnds:
                text = _get_window_text(hwnd)
                cls = _get_class_name(hwnd)
                if not text:
                    continue
                self.log(f"  窗口: HWND={hwnd} class={cls} title='{text[:60]}'")
                if text.strip():
                    self.main_hwnd = hwnd
                    self.log(f"选择主窗口: HWND={self.main_hwnd}, 标题='{text}'")
                    return True

            time.sleep(1)

        self.log(f"等待窗口超时 ({timeout}s)，列出所有可见窗口:")
        all_hwnds = []
        def _enum_all(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                all_hwnds.append(hwnd)
            return True
        user32.EnumWindows(WNDENUMPROC(_enum_all), 0)
        for hwnd in all_hwnds[:30]:
            text = _get_window_text(hwnd)
            if text:
                self.log(f"  {hwnd}: '{text[:80]}'")

        raise TimeoutError(f"等待窗口超时 ({timeout}s)")

    def inject_file(self):
        """模拟拖拽 xlsm 文件到窗口 — 策略1: ShellExecute, 策略2: 真实鼠标拖拽, 策略3: WM_DROPFILES"""
        self.log(f"注入文件: {self.xlsm_path}")

        records = {}
        for p in [os.path.join(self.output_dir, "ExportTxt", "ErrorMessage.txt"),
                  os.path.join(self.output_dir, ".ExcelTool2", "ErrorMessage")]:
            records[p] = os.path.getmtime(p) if os.path.isfile(p) else 0

        # 策略1: ShellExecute open xlsm - 如果 ExcelTool2 注册了文件关联
        self.log("  [策略1] ShellExecute(open) xlsm...")
        try:
            shell32.ShellExecuteW(None, "open", self.xlsm_path, None, None, 1)
            time.sleep(3)
            if self._check_file_refreshed(records):
                self.log("  [策略1] ShellExecute 成功加载文件")
                return
            self.log("  [策略1] ShellExecute 未加载文件")
        except Exception as e:
            self.log(f"  [策略1] 异常: {e}")

        # 策略2: 真实鼠标拖拽模拟
        self.log("  [策略2] 模拟鼠标拖拽...")
        self._simulate_mouse_drag(self.xlsm_path, self.main_hwnd)
        time.sleep(3)
        if self._check_file_refreshed(records):
            self.log("  [策略2] 鼠标拖拽成功")
            return
        self.log("  [策略2] 鼠标拖拽未生效")

        # 策略3: WM_DROPFILES 到所有窗口
        self.log("  [策略3] WM_DROPFILES 广播...")
        _send_drop_all(self.main_hwnd, self.xlsm_path)
        time.sleep(3)
        if self._check_file_refreshed(records):
            self.log("  [策略3] WM_DROPFILES 成功")
            return

        self.log("  ⚠️ 所有注入策略均未检测到文件刷新，继续执行（可能已有旧文件）")

    def _check_file_refreshed(self, records):
        """检查是否有任一输出文件的时间戳更新了"""
        for p, old_mtime in records.items():
            if os.path.isfile(p):
                new_mtime = os.path.getmtime(p)
                if new_mtime > old_mtime:
                    return True
        return False

    def _simulate_mouse_drag(self, file_path, hwnd_target):
        """真实鼠标拖拽：从桌面拖入窗口
        使用 SendInput API 模拟真实的鼠标移动+拖放
        """
        # 获取目标窗口在屏幕上的位置
        rect = RECT()
        if not user32.GetWindowRect(hwnd_target, ctypes.byref(rect)):
            self.log("  无法获取窗口位置")
            return

        target_x = (rect.left + rect.right) // 2
        target_y = (rect.top + rect.bottom) // 2
        outside_x = max(0, rect.left - 100)
        outside_y = rect.top + 100

        self.log(f"  拖拽起点=({outside_x},{outside_y}) 终点=({target_x},{target_y})")

        # 1. 把窗口前置
        user32.SetForegroundWindow(hwnd_target)
        time.sleep(0.5)

        # 2. 先拿到文件路径的实际文件列表格式 (CF_HDROP)
        # 其实直接构造 DROPFILES + 拖入效果更好
        # 改用 SendMessage + PostMessage 序列模拟完整拖拽

        # 使用 INPUT 结构模拟鼠标操作
        INPUT_MOUSE = 0
        MOUSEEVENTF_MOVE = 0x0001
        MOUSEEVENTF_LEFTDOWN = 0x0002
        MOUSEEVENTF_LEFTUP = 0x0004
        MOUSEEVENTF_ABSOLUTE = 0x8000

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.wintypes.DWORD),
                ("dwFlags", ctypes.wintypes.DWORD),
                ("time", ctypes.wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_void_p),
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", ctypes.wintypes.DWORD),
                ("mi", MOUSEINPUT),
            ]

        # 把屏幕坐标映射到 0-65535 范围 (MOUSEEVENTF_ABSOLUTE)
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)

        def _abs(x, y):
            return (x * 65535 // sw, y * 65535 // sh)

        def _send_input(dx, dy, flags):
            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.mi = MOUSEINPUT(dx, dy, 0, flags, 0, 0)
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

        # 移动鼠标到窗口外的位置
        ax, ay = _abs(outside_x, outside_y)
        _send_input(ax, ay, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE)
        time.sleep(0.2)

        # 按下左键
        _send_input(0, 0, MOUSEEVENTF_LEFTDOWN)
        time.sleep(0.1)

        # 拖拽到窗口中心（分步移动）
        steps = 5
        for s in range(1, steps + 1):
            cx = outside_x + (target_x - outside_x) * s // steps
            cy = outside_y + (target_y - outside_y) * s // steps
            ax, ay = _abs(cx, cy)
            _send_input(ax, ay, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE)
            time.sleep(0.1)

        # 松开左键
        time.sleep(0.2)
        _send_input(0, 0, MOUSEEVENTF_LEFTUP)
        time.sleep(0.3)

    def find_and_click_export(self, timeout=10):
        """查找并点击「左侧导出」按钮"""
        self.log("查找左侧导出按钮...")

        # 策略 1: UI Automation (需要 comtypes)
        self.log("  [策略1] 尝试 UI Automation...")
        if _try_uiautomation_click(self.main_hwnd, "左侧导出"):
            self.log("  UI Automation 点击成功")
            return True

        # 策略 2: 按键导航 (Tab 到按钮 + 回车)
        self.log("  [策略2] 尝试按键导航...")
        user32.SetForegroundWindow(self.main_hwnd)
        time.sleep(0.3)

        # 尝试 FindWindowEx 方式找到按钮
        btn_hwnd = _find_button_by_text(self.main_hwnd, "左侧导出")
        if btn_hwnd:
            self.log(f"  找到按钮窗口: HWND={btn_hwnd}")
            _click_window(btn_hwnd)
            self.log("  按钮点击成功")
            return True

        # 策略 3: 找所有可见子窗口，尝试文本匹配
        self.log("  [策略3] 搜索子窗口...")
        children = _find_child_windows(self.main_hwnd)
        self.log(f"  子窗口数量: {len(children)}")
        for hwnd, cls, text, visible in children[:20]:
            self.log(f"    HWND={hwnd}, class={cls}, text='{text[:20]}', visible={visible}")

        # 策略 4: 尝试 Tab 导航
        self.log("  [策略4] Tab 导航...")
        # 模拟 Tab 键 20 次，看看能不能到按钮
        for i in range(30):
            if self.proc and self.proc.poll() is not None:
                raise RuntimeError("ExcelTool2 已退出")
            VK_TAB = 0x09
            user32.keybd_event(VK_TAB, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(VK_TAB, 0, 2, 0)
            time.sleep(0.15)
            # 检查当前焦点控件
            focused = user32.GetFocus()
            if focused:
                text = _get_window_text(focused)
                if text:
                    self.log(f"    Tab {i+1}: HWND={focused}, text='{text[:30]}'")
                    if "导出" in text or "export" in text.lower():
                        # 按回车
                        VK_RETURN = 0x0D
                        user32.keybd_event(VK_RETURN, 0, 0, 0)
                        time.sleep(0.05)
                        user32.keybd_event(VK_RETURN, 0, 2, 0)
                        self.log("  回车点击成功")
                        return True

        self.log("  Tab 导航未找到导出按钮")
        return False

    def wait_for_export(self, timeout=120, file_records=None):
        """等待导出完成（监控输出文件的时间戳变更）"""
        export_txt = os.path.join(self.output_dir, "ExportTxt", "ErrorMessage.txt")
        export_bin = os.path.join(self.output_dir, ".ExcelTool2", "ErrorMessage")

        if file_records is None:
            file_records = {export_txt: 0, export_bin: 0}

        self.log("等待导出完成...")
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                self.log("ExcelTool2 已退出")
                break

            all_fresh = True
            for fp, old_mtime in file_records.items():
                if os.path.isfile(fp):
                    new_mtime = os.path.getmtime(fp)
                    self.log(f"  检查 {os.path.basename(fp)}: 旧={old_mtime} 新={new_mtime}")
                    if new_mtime <= old_mtime:
                        all_fresh = False
                else:
                    all_fresh = False

            if all_fresh:
                self.log("导出完成")
                return True

            time.sleep(1)

        txt_ok = os.path.isfile(export_txt) and os.path.getmtime(export_txt) > file_records[export_txt]
        bin_ok = os.path.isfile(export_bin) and os.path.getmtime(export_bin) > file_records[export_bin]
        if txt_ok or bin_ok:
            self.log("导出文件已刷新")
            return txt_ok and bin_ok

        raise TimeoutError(f"导出超时 ({timeout}s)，输出文件未更新")

    def close(self):
        """关闭 ExcelTool2 窗口"""
        if self.main_hwnd:
            self.log("关闭窗口...")
            user32.PostMessageW(self.main_hwnd, WM_CLOSE, 0, 0)
            time.sleep(2)
            if self.proc and self.proc.poll() is None:
                self.log("终止进程...")
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except:
                    self.proc.kill()

    def run(self, export_timeout=120):
        """完整执行流程"""
        # 记录文件初始时间戳
        export_txt = os.path.join(self.output_dir, "ExportTxt", "ErrorMessage.txt")
        export_bin = os.path.join(self.output_dir, ".ExcelTool2", "ErrorMessage")
        file_records = {
            export_txt: os.path.getmtime(export_txt) if os.path.isfile(export_txt) else 0,
            export_bin: os.path.getmtime(export_bin) if os.path.isfile(export_bin) else 0,
        }

        try:
            self.launch()
            time.sleep(1)
            self.inject_file()
            time.sleep(1)
            self.find_and_click_export()
            self.wait_for_export(timeout=export_timeout, file_records=file_records)
            return True
        except Exception:
            import traceback
            print(traceback.format_exc(), file=sys.stderr, flush=True)
            return False
        finally:
            self.close()


# ═══════════════════════════════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="ExcelTool2 注入导出工具")
    parser.add_argument("--exe", required=True,
                        help="ExcelTool2.exe 路径")
    parser.add_argument("--xlsm", required=True,
                        help="ErrorMessage.xlsm 路径")
    parser.add_argument("--output-dir", default=None,
                        help="语言目录路径（不指定则从 xlsm 位置推断）")
    parser.add_argument("--timeout", type=int, default=120,
                        help="导出超时秒数 (默认 120)")
    args = parser.parse_args()

    xlsm_path = os.path.abspath(args.xlsm)
    exe_path = os.path.abspath(args.exe)

    if args.output_dir:
        output_dir = os.path.abspath(args.output_dir)
    else:
        # 从 xlsm 路径推断: .../Language/ZH_CN/Data2/ErrorMessage.xlsm
        output_dir = os.path.dirname(os.path.dirname(xlsm_path))

    if not os.path.isfile(exe_path):
        print(f"错误: ExcelTool2.exe 不存在: {exe_path}", file=sys.stderr)
        return 1
    if not os.path.isfile(xlsm_path):
        print(f"错误: xlsm 不存在: {xlsm_path}", file=sys.stderr)
        return 1

    manager = ExcelTool2Manager(exe_path, xlsm_path, output_dir)
    ok = manager.run(export_timeout=args.timeout)

    if ok:
        print("导出成功")
        return 0
    else:
        print("导出失败", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
