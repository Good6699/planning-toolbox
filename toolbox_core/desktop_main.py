#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""策划工具箱桌面壳 — pywebview + Flask + QQ式贴边 + 系统托盘"""
import sys
import os

_pm = os.path.join(os.path.dirname(os.path.abspath(__file__)), "py_modules")
if os.path.isdir(_pm) and _pm not in sys.path:
    sys.path.insert(0, _pm)
    # 手动添加 pywin32 需要的子目录
    for subdir in ["win32", "win32\\lib", "pythonwin"]:
        full_path = os.path.join(_pm, subdir)
        if os.path.isdir(full_path) and full_path not in sys.path:
            sys.path.insert(0, full_path)

# 添加 pywin32_system32 到 DLL 搜索路径（Python 3.8+）
if os.path.isdir(_pm):
    pywin32_dll = os.path.join(_pm, "pywin32_system32")
    if os.path.isdir(pywin32_dll):
        os.add_dll_directory(pywin32_dll)
    # 添加整个 py_modules 到 DLL 搜索路径
    os.add_dll_directory(_pm)
    # 设置 Tcl/Tk 环境变量
    tcl_dir = os.path.join(_pm, "_tcl_data")
    tk_dir = os.path.join(_pm, "_tk_data")
    if os.path.isdir(tcl_dir):
        os.environ["TCL_LIBRARY"] = tcl_dir
    if os.path.isdir(tk_dir):
        os.environ["TK_LIBRARY"] = tk_dir
    # 把 py_modules 加到 PATH 环境变量
    os.environ["PATH"] = _pm + os.pathsep + os.environ.get("PATH", "")

import json
import threading
import time
import socket
import signal
import urllib.request, urllib.error
import ctypes.wintypes
import webview
import win32gui
import win32con
import win32api
from toolbox_config import load_config, save_config, _ensure_frozen_config

WINDOW_W = 1100
WINDOW_H = 700

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, 'frozen', False):
    ICON_PATH = os.path.join(sys._MEIPASS, "assets", "app_icon.ico")
else:
    ICON_PATH = os.path.join(SCRIPT_DIR, "assets", "app_icon.ico")

SPLASH_HTML = """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>策划工具箱</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden;background:#0f1115;font-family:"Segoe UI","Microsoft YaHei UI",sans-serif}
body{background:radial-gradient(circle at top,#1c2540 0%,#0f1115 45%)}
.f{position:absolute;inset:-10%;background:radial-gradient(circle at 30% 20%,rgba(94,162,255,.08),transparent 40%);filter:blur(80px);animation:f 14s ease-in-out infinite alternate}
.r{position:relative;width:100%;height:100%;display:flex;flex-direction:column;justify-content:center;align-items:center}
.lw{display:flex;flex-direction:column;align-items:center;animation:r2 .9s cubic-bezier(.2,.8,.2,1) forwards}
.lb{width:100px;height:100px;border-radius:22px;background:linear-gradient(180deg,rgba(255,255,255,.08),rgba(255,255,255,.02));border:1px solid rgba(255,255,255,.08);display:flex;align-items:center;justify-content:center}
.lb svg{width:84px;height:84px}
.t{margin-top:20px;font-size:30px;font-weight:700;letter-spacing:1px;color:#fff}
.st{margin-top:8px;font-size:13px;color:#8b96ad;letter-spacing:3px}
.p{position:absolute;bottom:64px;width:800px;text-align:center}
.pt{font-size:11px;letter-spacing:2px;color:#8b96ad;margin-bottom:12px}
.pw{width:100%;height:9px;background:transparent;overflow:hidden;border-radius:999px}
.pb{width:0%;height:100%;background:linear-gradient(90deg,#5ea2ff,#7cb8ff);box-shadow:0 0 20px rgba(94,162,255,.7);transition:width .35s ease}
.pn{font-size:11px;color:#5f6b80;margin-top:8px;letter-spacing:1px}
@keyframes r2{0%{opacity:0;transform:scale(.96)}100%{opacity:1;transform:scale(1)}}
@keyframes f{0%{transform:translateX(-40px)}100%{transform:translateX(40px)}}
</style>
</head>
<body>
<div class="f"></div>
<div class="r">
<div class="lw"><div class="lb"><svg viewBox="25 25 50 50" fill="none"><defs><linearGradient id="cg" x1="25" y1="25" x2="75" y2="75" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#8BE9FF"/><stop offset="50" stop-color="#4F8CFF"/><stop offset="100" stop-color="#6A4CFF"/></linearGradient></defs><path d="M30 28 H70 L70 40 H42 L42 60 H70 L70 72 H30 L30 50 H58" stroke="url(#cg)" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/><circle cx="58" cy="50" r="6" fill="url(#cg)"/></svg></div><div class="t">策划工具箱</div><div class="st">Game Pipeline Toolkit</div></div>
<div class="p"><div class="pt" id="stxt">初始化中...</div><div class="pw"><div class="pb" id="sbar"></div></div><div class="pn" id="spct">0%</div></div>
</div>
</body>
</html>"""

EDGE_THRESHOLD = 8
DOCK_VISIBLE = 4
ANIM_FRAMES = 16

_vx = win32api.GetSystemMetrics(76)
_vy = win32api.GetSystemMetrics(77)
_VSCREEN_L = _vx
_VSCREEN_T = _vy
_VSCREEN_R = _vx + win32api.GetSystemMetrics(78)
_VSCREEN_B = _vy + win32api.GetSystemMetrics(79)

_instance_socket = None
_tray_icon = None
_tray_nid = None
_flask_server = None
_main_window = None
_main_hwnd = None
_window_visible = True
_force_close = False
_docker = None
_is_dragging = False
_splash_hwnd = None
_splash_progress = 0
_splash_text = "初始化中..."
_splash_ready = threading.Event()
_splash_root = None
_splash_should_close = False

WS_EX_TOOLWINDOW = 0x80
WS_EX_APPWINDOW = 0x40000


def _native_splash_proc(hwnd, msg, wparam, lparam):
    global _splash_hwnd
    if msg == win32con.WM_PAINT:
        hdc, ps = win32gui.BeginPaint(hwnd)
        try:
            rect = win32gui.GetClientRect(hwnd)
            bg = win32gui.CreateSolidBrush(win32api.RGB(15, 17, 21))
            panel = win32gui.CreateSolidBrush(win32api.RGB(23, 27, 36))
            bar = win32gui.CreateSolidBrush(win32api.RGB(94, 162, 255))
            try:
                win32gui.FillRect(hdc, rect, bg)
                w = rect[2] - rect[0]
                h = rect[3] - rect[1]
                cx = w // 2
                win32gui.SetBkMode(hdc, win32con.TRANSPARENT)
                title_font = win32gui.CreateFont(30, 0, 0, 0, 700, 0, 0, 0, win32con.DEFAULT_CHARSET, 0, 0, 0, 0, "Microsoft YaHei UI")
                sub_font = win32gui.CreateFont(13, 0, 0, 0, 500, 0, 0, 0, win32con.DEFAULT_CHARSET, 0, 0, 0, 0, "Microsoft YaHei UI")
                small_font = win32gui.CreateFont(11, 0, 0, 0, 500, 0, 0, 0, win32con.DEFAULT_CHARSET, 0, 0, 0, 0, "Microsoft YaHei UI")
                try:
                    logo_rect = (cx - 50, h // 2 - 120, cx + 50, h // 2 - 20)
                    win32gui.FillRect(hdc, logo_rect, panel)
                    old = win32gui.SelectObject(hdc, title_font)
                    win32gui.SetTextColor(hdc, win32api.RGB(242, 245, 255))
                    win32gui.DrawText(hdc, "策划工具箱", -1, (0, h // 2, w, h // 2 + 42), win32con.DT_CENTER | win32con.DT_SINGLELINE)
                    win32gui.SelectObject(hdc, sub_font)
                    win32gui.SetTextColor(hdc, win32api.RGB(139, 150, 173))
                    win32gui.DrawText(hdc, "Game Pipeline Toolkit", -1, (0, h // 2 + 44, w, h // 2 + 70), win32con.DT_CENTER | win32con.DT_SINGLELINE)
                    win32gui.SelectObject(hdc, small_font)
                    win32gui.DrawText(hdc, _splash_text, -1, (0, h - 96, w, h - 70), win32con.DT_CENTER | win32con.DT_SINGLELINE)
                    bar_rect = (cx - 400, h - 64, cx + 400, h - 55)
                    win32gui.FillRect(hdc, bar_rect, bg)
                    fill_w = int(800 * max(0, min(100, _splash_progress)) / 100)
                    if fill_w > 0:
                        win32gui.FillRect(hdc, (bar_rect[0], bar_rect[1], bar_rect[0] + fill_w, bar_rect[3]), bar)
                    win32gui.SetTextColor(hdc, win32api.RGB(95, 107, 128))
                    win32gui.DrawText(hdc, f"{_splash_progress}%", -1, (0, h - 48, w, h - 24), win32con.DT_CENTER | win32con.DT_SINGLELINE)
                    win32gui.SelectObject(hdc, old)
                finally:
                    win32gui.DeleteObject(title_font)
                    win32gui.DeleteObject(sub_font)
                    win32gui.DeleteObject(small_font)
            finally:
                win32gui.DeleteObject(bg)
                win32gui.DeleteObject(panel)
                win32gui.DeleteObject(bar)
        finally:
            win32gui.EndPaint(hwnd, ps)
        return 0
    if msg == win32con.WM_CLOSE:
        win32gui.DestroyWindow(hwnd)
        return 0
    if msg == win32con.WM_DESTROY:
        _splash_hwnd = None
        win32gui.PostQuitMessage(0)
        return 0
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def _show_native_splash(x, y, w, h):
    def _run():
        global _splash_hwnd, _splash_root, _splash_should_close
        import tkinter as tk
        _splash_should_close = False
        root = tk.Tk()
        _splash_root = root
        root.withdraw()
        root.overrideredirect(True)
        root.configure(bg="#0f1115")
        root.geometry(f"{w}x{h}+{x}+{y}")
        root.attributes("-topmost", True)
        try:
            root.attributes("-toolwindow", True)
        except Exception:
            pass
        canvas = tk.Canvas(root, width=w, height=h, bg="#0f1115", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        cx = w // 2
        logo_top = h // 2 - 120
        canvas.create_rectangle(cx - 50, logo_top, cx + 50, logo_top + 100, fill="#171b24", outline="#2a3142", width=1)
        canvas.create_text(cx, logo_top + 50, text="◇", fill="#5ea2ff", font=("Microsoft YaHei UI", 46, "bold"))
        canvas.create_text(cx, h // 2 + 20, text="策划工具箱", fill="#f2f5ff", font=("Microsoft YaHei UI", 30, "bold"))
        canvas.create_text(cx, h // 2 + 62, text="Game Pipeline Toolkit", fill="#8b96ad", font=("Segoe UI", 13))
        text_id = canvas.create_text(cx, h - 86, text=_splash_text, fill="#8b96ad", font=("Microsoft YaHei UI", 11))
        bar_x = cx - 400
        bar_y = h - 64
        canvas.create_rectangle(bar_x, bar_y, bar_x + 800, bar_y + 9, fill="#151821", outline="")
        fill_id = canvas.create_rectangle(bar_x, bar_y, bar_x, bar_y + 9, fill="#5ea2ff", outline="")
        pct_id = canvas.create_text(cx, h - 38, text="0%", fill="#5f6b80", font=("Segoe UI", 11))

        def _tick():
            if _splash_should_close:
                root.destroy()
                return
            pct = max(0, min(100, int(_splash_progress)))
            canvas.itemconfigure(text_id, text=_splash_text)
            canvas.coords(fill_id, bar_x, bar_y, bar_x + int(800 * pct / 100), bar_y + 9)
            canvas.itemconfigure(pct_id, text=f"{pct}%")
            root.after(80, _tick)

        root.update_idletasks()
        _splash_hwnd = root.winfo_id()
        _splash_ready.set()
        root.deiconify()
        root.after(80, _tick)
        root.mainloop()
    _splash_ready.clear()
    threading.Thread(target=_run, daemon=True).start()
    _splash_ready.wait(timeout=2)


def _set_native_splash(pct, text):
    global _splash_progress, _splash_text
    _splash_progress = int(pct)
    _splash_text = text


def _close_native_splash():
    global _splash_should_close
    _splash_should_close = True


def _hwnd_belongs_to_current_process(hwnd):
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False
    process_id = ctypes.wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    return process_id.value == os.getpid()


def _resolve_main_window_hwnd(window=None):
    global _main_hwnd
    if _hwnd_belongs_to_current_process(_main_hwnd):
        return _main_hwnd
    _main_hwnd = None
    target = window or _main_window
    if not target:
        return None
    try:
        handle = target.native.Handle
        hwnd = int(handle.ToInt64() if hasattr(handle, "ToInt64") else handle.ToInt32())
        if _hwnd_belongs_to_current_process(hwnd):
            _main_hwnd = hwnd
            return hwnd
    except Exception:
        pass
    return None


def _hide_main_window():
    global _window_visible
    if not _main_window:
        return False
    try:
        _main_window.hide()
        _window_visible = False
        return True
    except Exception:
        return False


def _is_main_window_visible():
    hwnd = _resolve_main_window_hwnd()
    if not hwnd:
        return True
    return bool(ctypes.windll.user32.IsWindowVisible(hwnd)) and not bool(
        ctypes.windll.user32.IsIconic(hwnd)
    )


def _hide_from_taskbar(hwnd):
    try:
        ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        ex = ex | WS_EX_TOOLWINDOW
        ex = ex & ~WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex)
        win32gui.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE | win32con.SWP_FRAMECHANGED)
    except Exception:
        pass


def _set_window_icon():
    if not os.path.isfile(ICON_PATH):
        return
    try:
        hwnd = _find_window_hwnd(timeout=5)
        if not hwnd:
            return
        hicon = win32gui.LoadImage(0, ICON_PATH, win32con.IMAGE_ICON, 0, 0,
                                   win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE)
        if hicon:
            win32gui.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_SMALL, hicon)
            win32gui.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_BIG, hicon)
    except Exception:
        pass


def _ensure_app_id():
    APP_ID = "PlanningToolbox.PlanningToolbox"
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass
    shortcut_name = "策划工具箱.lnk"
    shortcut_dir = os.path.join(os.environ.get("APPDATA", ""),
                                "Microsoft", "Windows", "Start Menu", "Programs")
    shortcut_path = os.path.join(shortcut_dir, shortcut_name)
    if os.path.isfile(shortcut_path):
        return
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = sys.executable
        shortcut.Arguments = '"' + os.path.join(SCRIPT_DIR, "..", "main.py") + '"'
        shortcut.WorkingDirectory = SCRIPT_DIR
        if os.path.isfile(ICON_PATH):
            shortcut.IconLocation = ICON_PATH
        shortcut.Save()
    except Exception:
        pass


def _show_taskbar_icon(hwnd):
    try:
        ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        ex = ex & ~WS_EX_TOOLWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex)
        win32gui.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE | win32con.SWP_FRAMECHANGED)
    except Exception:
        pass


class EdgeDocker:
    def __init__(self, window):
        self.window = window
        self.hwnd = None
        self.docked = None
        self.dock_w = WINDOW_W
        self.dock_h = WINDOW_H
        self.animating = False
        self._docked_edge = 0
        self._docked_ml = 0
        self._docked_mr = 0
        self._docked_mt = 0
        self._docked_mb = 0
        self._busy_until = 0.0
        self._op_seq = 0
        self._animating_seq = 0
        self._last_docked_edge = None
        self._had_focus_while_expanded = False
        self._stop = threading.Event()
        self._thread = None
        self._prev_fg = 0
        self._taskbar_activate = False

    def _resolve_hwnd(self):
        if _hwnd_belongs_to_current_process(self.hwnd):
            return self.hwnd
        self.hwnd = _resolve_main_window_hwnd(self.window)
        return self.hwnd

    def _monitor_bounds(self, hwnd):
        try:
            m = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
            info = win32api.GetMonitorInfo(m)
            rc = info["Monitor"]
            return rc[0], rc[1], rc[2], rc[3]
        except Exception:
            return _VSCREEN_L, _VSCREEN_T, _VSCREEN_R, _VSCREEN_B

    def _monitor_v_edges(self, hwnd):
        mt, mb = self._monitor_bounds(hwnd)[1], self._monitor_bounds(hwnd)[3]
        return mt, mb

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def force_undock(self):
        if not self.docked:
            return
        self._op_seq += 1
        self._animating_seq = self._op_seq
        hwnd = self._resolve_hwnd()
        if not hwnd:
            self.docked = None
            self._last_docked_edge = None
            return
        try:
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            rect = win32gui.GetWindowRect(hwnd)
            x, y, r, b = rect
            w, h = r - x, b - y
            if self.docked in ("right", "left"):
                ml = self._docked_ml
                mr = self._docked_mr
                if ml == mr == 0:
                    ml, _, mr, _ = self._monitor_bounds(hwnd)
                tx = ml if self.docked == "left" else mr - w
                ty = y
            else:
                mt, mb = self._monitor_v_edges(hwnd)
                tx = x
                ty = mt if self.docked == "top" else mb - h
            win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, tx, ty, w, h,
                                  win32con.SWP_NOACTIVATE)
        except Exception:
            pass
        finally:
            self.docked = None
            self._last_docked_edge = None
            self._busy_until = time.perf_counter() + 0.6

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                pass
            time.sleep(0.05)

    def _tick_maybe_undock(self, hwnd):
        if self._taskbar_activate:
            self._taskbar_activate = False
            _undock_and_center(hwnd)
            return True
        fg = win32gui.GetForegroundWindow()
        if fg == hwnd and self._prev_fg != 0 and self._prev_fg != hwnd:
            _undock_and_center(hwnd)
            return True
        self._prev_fg = fg
        return False

    def _tick_check_released(self, x, r, b, y):
        released = False
        if self.docked == "right":
            if x < self._docked_edge - 80:
                released = True
        elif self.docked == "left":
            if r > self._docked_edge + 80:
                released = True
        elif self.docked == "top":
            if y > self._docked_edge + 80:
                released = True
        elif self.docked == "bottom":
            if b < self._docked_edge - 80:
                released = True
        return released

    def _tick_try_slide_out(self, hwnd, x, y, r, b, h, cx, cy):
        if self.docked in ("right", "left"):
            edge_x = r if self.docked == "left" else x
            if abs(cx - edge_x) <= DOCK_VISIBLE + 4 and y - 8 <= cy <= y + h + 8:
                self._slide_out(hwnd)
        elif self.docked in ("top", "bottom"):
            edge_y = self._docked_mt if self.docked == "top" else self._docked_mb
            if abs(cy - edge_y) <= DOCK_VISIBLE + 4 and x - 8 <= cx <= r + 8:
                self._slide_out(hwnd)

    def _tick_docked(self, hwnd, x, y, r, b, w, h, cx, cy):
        if self._tick_maybe_undock(hwnd):
            return
        if self._tick_check_released(x, r, b, y):
            self.docked = None
            self._last_docked_edge = None
        else:
            self._tick_try_slide_out(hwnd, x, y, r, b, h, cx, cy)

    def _tick_snap_check(self, hwnd, x, y, r, b, w, h, cx, cy, in_window):
        if in_window or _is_dragging:
            return
        ml, mt, mr, mb = self._monitor_bounds(hwnd)
        mw = mr - ml
        can_dock_h = (mw - w >= 80)
        snap = None
        if can_dock_h and x <= ml + EDGE_THRESHOLD:
            snap = "left"
        elif can_dock_h and r >= mr - EDGE_THRESHOLD:
            snap = "right"
        elif y <= mt + EDGE_THRESHOLD:
            snap = "top"
        elif b >= mb - EDGE_THRESHOLD:
            snap = "bottom"
        if snap:
            self._slide_in(hwnd, snap)

    def _tick(self):
        if time.perf_counter() < self._busy_until:
            return
        hwnd = self._resolve_hwnd()
        if not hwnd or not win32gui.IsWindow(hwnd):
            return

        try:
            rect = win32gui.GetWindowRect(hwnd)
            x, y, r, b = rect
            w, h = r - x, b - y
        except Exception:
            return

        cx, cy = win32api.GetCursorPos()
        in_window = (x <= cx <= r and y <= cy <= b)

        if self.docked:
            self._tick_docked(hwnd, x, y, r, b, w, h, cx, cy)
            if time.perf_counter() < self._busy_until:
                return

        if not self.docked:
            if self._last_docked_edge:
                try:
                    fg = win32gui.GetForegroundWindow()
                    if fg == hwnd:
                        self._had_focus_while_expanded = True
                    elif self._had_focus_while_expanded:
                        self._slide_in(hwnd, self._last_docked_edge)
                        self._last_docked_edge = None
                        self._had_focus_while_expanded = False
                        return
                except Exception:
                    pass
            self._tick_snap_check(hwnd, x, y, r, b, w, h, cx, cy, in_window)

    def _animate(self, hwnd, start_x, start_y, target_x, target_y, ease_in=True):
        self.animating = True
        seq = self._animating_seq
        final_x, final_y = target_x, target_y
        try:
            frame_interval = 0.008
            for i in range(1, ANIM_FRAMES + 1):
                if seq != self._animating_seq:
                    return
                t0 = time.perf_counter()
                t = i / ANIM_FRAMES
                eased = 1 - (1 - t) ** 3 if ease_in else t ** 3
                cur_x = int(start_x + (target_x - start_x) * eased)
                cur_y = int(start_y + (target_y - start_y) * eased)
                final_x, final_y = cur_x, cur_y
                try:
                    win32gui.SetWindowPos(hwnd, 0, cur_x, cur_y, 0, 0,
                                          win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
                except Exception:
                    pass
                elapsed = time.perf_counter() - t0
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)
        finally:
            self.animating = False
            if seq == self._animating_seq:
                try:
                    rect = win32gui.GetWindowRect(hwnd)
                    w, h = rect[2] - rect[0], rect[3] - rect[1]
                    win32gui.SetWindowPos(hwnd, 0, final_x, final_y, w, h,
                                          win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
                except Exception:
                    pass

    def _slide_in(self, hwnd, edge):
        self._op_seq += 1
        seq = self._op_seq
        self._animating_seq = seq
        self._busy_until = time.perf_counter() + 0.6
        try:
            rect = win32gui.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            self.dock_w = w
            self.dock_h = h

            if edge in ("right", "left"):
                ml, _, mr, _ = self._monitor_bounds(hwnd)
                self._docked_ml = ml
                self._docked_mr = mr
                target_x = mr - DOCK_VISIBLE if edge == "right" else ml + DOCK_VISIBLE - w
                target_y = rect[1]
                self._docked_edge = target_x if edge == "right" else target_x + w
            else:
                mt, mb = self._monitor_v_edges(hwnd)
                self._docked_mt = mt
                self._docked_mb = mb
                target_x = rect[0]
                target_y = mt + DOCK_VISIBLE - h if edge == "top" else mb - DOCK_VISIBLE
                self._docked_edge = target_y + h if edge == "top" else target_y

            self._animate(hwnd, rect[0], rect[1], target_x, target_y, ease_in=True)
            if seq == self._op_seq:
                self.docked = edge
                try:
                    ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                    ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex | 0x8)
                    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_FRAMECHANGED)
                    desktop = ctypes.windll.user32.FindWindowW("Progman", None)
                    if desktop:
                        ctypes.windll.user32.SwitchToThisWindow(desktop, True)
                        ctypes.windll.user32.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
                except Exception:
                    pass
                ctypes.windll.user32.ShowWindow(hwnd, 0)
                self._prev_fg = 0
                self._taskbar_activate = False
        except Exception:
            self._busy_until = 0.0

    def _slide_out(self, hwnd):
        ctypes.windll.user32.ShowWindow(hwnd, 9)
        _hide_from_taskbar(hwnd)
        self._op_seq += 1
        seq = self._op_seq
        self._animating_seq = seq
        self._busy_until = time.perf_counter() + 0.25
        try:
            rect = win32gui.GetWindowRect(hwnd)
            w, h = rect[2] - rect[0], rect[3] - rect[1]
            if self.docked in ("right", "left"):
                target_x = self._docked_ml if self.docked == "left" else self._docked_mr - w
                target_y = rect[1]
            else:
                target_x = rect[0]
                target_y = self._docked_mt if self.docked == "top" else self._docked_mb - h
            self._animate(hwnd, rect[0], rect[1], target_x, target_y, ease_in=False)
            if seq == self._op_seq:
                self._last_docked_edge = self.docked
                self._had_focus_while_expanded = False
                self.docked = None
                try:
                    ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                    ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex & ~0x8)
                    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
                    win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_FRAMECHANGED)
                    win32gui.BringWindowToTop(hwnd)
                except Exception:
                    pass
        except Exception:
            pass


def _get_hidden_sp_kwargs():
    """返回隐藏 CMD 窗口的 subprocess 参数"""
    import subprocess as _sp
    si = _sp.STARTUPINFO()
    si.dwFlags |= _sp.STARTF_USESHOWWINDOW
    si.wShowWindow = _sp.SW_HIDE
    return {"startupinfo": si, "creationflags": _sp.CREATE_NO_WINDOW}


def _force_kill_old_instance():
    """强制杀死其他运行中的策划工具箱实例，确保唯一实例"""
    import subprocess as _sp
    import time as _time
    import ctypes
    pids = set()
    _my_pid = str(os.getpid())
    _kw = _get_hidden_sp_kwargs()

    # 0. 先给旧实例的托盘窗口发 WM_QUIT，让消息循环自然退出触发 NIM_DELETE 清理图标
    try:
        old_hwnd = ctypes.windll.user32.FindWindowW("PlanningToolboxTrayWindow", None)
        if old_hwnd:
            ctypes.windll.user32.PostMessageW(old_hwnd, 0x12, 0, 0)  # WM_QUIT
            _time.sleep(0.3)
    except Exception:
        pass

    try:
        # 1. 扫端口 18124（实例锁）和 18123（Flask），收集旧 PID
        r = _sp.run(["netstat", "-ano"], capture_output=True, text=True, timeout=5, **_kw)
        for line in r.stdout.splitlines():
            if ("18124" in line or "18123" in line) and "LISTENING" in line:
                parts = line.strip().split()
                if parts:
                    pid = parts[-1]
                    if pid.isdigit() and pid != _my_pid:
                        pids.add(pid)
    except Exception:
        pass

    # 2. 按 exe 名搜同类进程（兜底，同名但端口可能不同的情况）
    try:
        r = _sp.run(["tasklist", "/fi", "IMAGENAME eq 策划工具箱.exe", "/fo", "csv", "/nh"],
                    capture_output=True, text=True, timeout=5, **_kw)
        for line in r.stdout.splitlines():
            parts = line.strip().strip('"').split('","')
            if len(parts) >= 2 and parts[1].isdigit() and parts[1] != _my_pid:
                pids.add(parts[1])
    except Exception:
        pass

    for pid in pids:
        try:
            _sp.run(["taskkill", "/f", "/pid", pid],
                    capture_output=True, timeout=5, **_kw)
        except Exception:
            pass
    # 强制杀死后主动删除旧托盘图标（HWND 可能已失效，但 NIM_DELETE 仍可能被 Explorer 处理）
    try:
        old_hwnd2 = ctypes.windll.user32.FindWindowW("PlanningToolboxTrayWindow", None)
        if old_hwnd2:
            from win32gui import Shell_NotifyIcon, NIM_DELETE
            Shell_NotifyIcon(NIM_DELETE, (old_hwnd2, 1, 0, 0, 0, ""))
    except Exception:
        pass
    _time.sleep(0.3)


def _acquire_instance_lock():
    global _instance_socket
    # 先强制杀死旧实例，再绑定端口确保自己是唯一实例
    _force_kill_old_instance()
    _instance_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _instance_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _instance_socket.bind(("127.0.0.1", 18124))


def _start_flask():
    global _flask_server
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        os.chdir(script_dir)
    except FileNotFoundError:
        if getattr(sys, 'frozen', False):
            os.chdir(sys._MEIPASS)
        else:
            raise
    sys.path.insert(0, script_dir)
    pm = os.path.join(script_dir, "py_modules")
    if not os.path.isdir(pm):
        pm = os.path.join(os.path.dirname(script_dir), "py_modules")
    if os.path.isdir(pm) and pm not in sys.path:
        sys.path.insert(0, pm)
    from web_app import app
    import web_app as _wa
    _wa._on_notification_click = lambda: _show_window(None, None)
    _wa._quit_app_callback = _quit_app
    _wa._hide_window_callback = _hide_main_window
    _wa._is_window_visible_callback = _is_main_window_visible
    from werkzeug.serving import make_server
    _flask_server = make_server("127.0.0.1", 18123, app, threaded=True)
    _flask_server.serve_forever()


def _wait_for_flask(timeout=10):
    urls = [
        "http://127.0.0.1:18123/api/config",
        "http://127.0.0.1:18123/api/static/core.js",
    ]
    start = time.time()
    while time.time() - start < timeout:
        try:
            for url in urls:
                urllib.request.urlopen(url, timeout=1).close()
            return True
        except Exception:
            time.sleep(0.2)
    return False



def _show_window(icon, item=None):
    global _window_visible
    if not _main_window:
        return
    try:
        _main_window.restore()
        _main_window.show()
        _window_visible = True
    except Exception:
        return
    try:
        _main_window.evaluate_js("triggerUpdateCheck()")
        _main_window.evaluate_js("scrollLogToBottom()")
    except Exception:
        pass
    hwnd = _resolve_main_window_hwnd(_main_window)
    if hwnd:
        if _docker and _docker.docked:
            _undock_and_center(hwnd)
        else:
            _show_taskbar_icon(hwnd)
            win32gui.SetForegroundWindow(hwnd)


def _quit_app():
    global _force_close
    _force_close = True
    _save_window_rect()
    _stop_flask()
    if _tray_icon:
        try:
            # 发 WM_QUIT 让托盘线程的消息循环退出
            # 消息循环退出后会自动执行 NIM_DELETE 清理图标，再 os._exit(0)
            win32gui.PostMessage(_tray_icon, win32con.WM_QUIT, 0, 0)
        except Exception:
            pass
    # 让消息循环自己处理清理和退出，不在这里调 os._exit


def _stop_flask():
    global _flask_server
    if _flask_server is not None:
        try:
            _flask_server.shutdown()
        except Exception:
            pass
        _flask_server = None


class ResizeApi:
    def __init__(self):
        self._window = None
        self._cursor_x = 0
        self._cursor_y = 0
        self._win_x = 0
        self._win_y = 0
        self._win_w = 0
        self._win_h = 0
        self._active = False
        self.ready_event = threading.Event()

    def set_window(self, window):
        self._window = window

    def set_window_rect(self):
        if not self._window:
            return False
        try:
            hwnd = _resolve_main_window_hwnd(self._window)
            if not hwnd:
                return False
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            self._win_x = rect.left
            self._win_y = rect.top
            self._win_w = rect.right - rect.left
            self._win_h = rect.bottom - rect.top
            self._cursor_x, self._cursor_y = win32api.GetCursorPos()
            return True
        except Exception:
            return False

    def start_resize(self, edge):
        global _is_dragging
        self._active = self.set_window_rect()
        _is_dragging = self._active
        self._edge = edge
        return self._active

    def move(self):
        if not self._active or not self._window:
            return False
        try:
            cx, cy = win32api.GetCursorPos()
            nx = cx - self._cursor_x + self._win_x
            ny = cy - self._cursor_y + self._win_y
            self._window.move(nx, ny)
        except Exception:
            return False
        return True

    def resize(self):
        if not self._active or not self._window:
            return False
        try:
            cx, cy = win32api.GetCursorPos()
            dx = cx - self._cursor_x
            dy = cy - self._cursor_y
            if dx == 0 and dy == 0:
                return True

            x, y, w, h = self._win_x, self._win_y, self._win_w, self._win_h
            if 'left' in self._edge:
                x = self._win_x + dx
                w = self._win_w - dx
            if 'right' in self._edge:
                w = self._win_w + dx
            if 'top' in self._edge:
                y = self._win_y + dy
                h = self._win_h - dy
            if 'bottom' in self._edge:
                h = self._win_h + dy
            if w < 200:
                w = 200
            if h < 200:
                h = 200
            hwnd = _resolve_main_window_hwnd(self._window)
            if not hwnd:
                return False
            ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, w, h, 0x0004)
        except Exception:
            return False
        return True

    def stop_resize(self):
        global _is_dragging
        _is_dragging = False
        self._active = False
        _save_window_rect()

    def app_ready(self):
        self.ready_event.set()
        return True

    def hide_window(self):
        return _hide_main_window()

    def focusWindow(self):
        hwnd = _find_window_hwnd(timeout=0.1)
        if hwnd:
            try:
                _undock_and_center(hwnd)
            except Exception:
                pass

    def browseFile(self, filter=""):
        try:
            w = webview.windows[0]
            if w:
                if filter and '*' in filter:
                    name = filter.replace('*.', '').upper() + ' Files'
                    file_types = (f'{name} ({filter})', 'All Files (*.*)')
                    directory = ""
                else:
                    file_types = ('All Files (*.*)',)
                    directory = filter
                result = w.create_file_dialog(
                    webview.OPEN_DIALOG,
                    directory=directory,
                    allow_multiple=False,
                    file_types=file_types,
                )
                if result:
                    return result[0]
        except Exception as e:
            print("[browseFile]", e)
        return ""

    def browseDir(self, directory=""):
        try:
            w = webview.windows[0]
            if w:
                result = w.create_file_dialog(
                    webview.FOLDER_DIALOG,
                    directory=directory,
                )
                if result:
                    return result[0]
        except Exception as e:
            print("[browseDir]", e)
        return ""

    def open_folder(self, path):
        try:
            import subprocess
            if os.path.isfile(path):
                subprocess.Popen(f'explorer /select,"{path}"', shell=True)
            else:
                subprocess.Popen(f'explorer "{path}"', shell=True)
            return True
        except Exception as e:
            print("[open_folder]", e)
            return False


# ── 托盘图标 GUID（Windows 用户设置永久绑定的唯一标识，永不改变）──
_NOTIFY_ICON_ID = 1
_WM_TRAYICON = win32con.WM_APP + 100
# 固定 GUID —— 所有版本一致，确保托盘图标显示偏好持久化
_TRAY_GUID = (0x5F8C4B9E, 0x3E7A, 0x4D2A,
              (0x9B, 0x1C, 0x0D, 0x8E, 0x6F, 0x4A, 0x2C, 0x3B))
# GUID 字符串：{5F8C4B9E-3E7A-4D2A-9B1C-0D8E6F4A2C3B}
_TRAY_GUID_STR = "{" + "-".join([
    "5F8C4B9E", "3E7A", "4D2A",
    "9B1C", "0D8E6F4A2C3B"
]) + "}"


def _ensure_tray_visible():
    """在注册托盘图标前，确保 Windows 对应 GUID 的 IsPromoted=1，强制始终显示"""
    try:
        import winreg
        key_path = r"Control Panel\NotifyIconSettings"
        sub_key = key_path + "\\" + _TRAY_GUID_STR
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key, 0,
                               winreg.KEY_READ | winreg.KEY_SET_VALUE)
            try:
                val, _ = winreg.QueryValueEx(k, "IsPromoted")
                if val != 1:
                    winreg.SetValueEx(k, "IsPromoted", 0, winreg.REG_DWORD, 1)
            except FileNotFoundError:
                winreg.SetValueEx(k, "IsPromoted", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(k)
        except FileNotFoundError:
            # 注册表项还不存在，创建它
            k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, sub_key)
            winreg.SetValueEx(k, "IsPromoted", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(k, "ExecutablePath", 0, winreg.REG_SZ, sys.executable)
            winreg.CloseKey(k)
    except Exception:
        pass


def _ensure_tray_visible_fallback():
    """扫描 NotifyIconSettings 中 exe 路径匹配的旧条目并设 IsPromoted=1。返回是否找到"""
    try:
        import winreg
        base_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                  r"Control Panel\NotifyIconSettings")
        i = 0
        found = False
        while True:
            try:
                sub_name = winreg.EnumKey(base_key, i)
                sub = winreg.OpenKey(base_key, sub_name, 0,
                                     winreg.KEY_READ | winreg.KEY_SET_VALUE)
                try:
                    val, _ = winreg.QueryValueEx(sub, "ExecutablePath")
                    if val and "策划工具箱" in val:
                        winreg.SetValueEx(sub, "IsPromoted", 0, winreg.REG_DWORD, 1)
                        found = True
                except FileNotFoundError:
                    pass
                winreg.CloseKey(sub)
                i += 1
            except OSError:
                break
        winreg.CloseKey(base_key)
        return found
    except Exception:
        return False


def _create_tray_hwnd():
    """创建隐藏窗口，接收托盘图标回调消息"""
    wc = win32gui.WNDCLASS()
    wc.hInstance = win32gui.GetModuleHandle(None)
    wc.lpszClassName = "PlanningToolboxTrayWindow"
    wc.lpfnWndProc = _tray_wndproc
    wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
    wc.hbrBackground = win32con.COLOR_WINDOW + 1
    try:
        class_atom = win32gui.RegisterClass(wc)
    except Exception:
        class_atom = wc.lpszClassName
    hwnd = win32gui.CreateWindow(class_atom, "TrayWindow", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)
    return hwnd

def _tray_wndproc(hwnd, msg, wparam, lparam):
    if msg == _WM_TRAYICON:
        if lparam == win32con.WM_LBUTTONUP:
            _show_window(None, None)
        elif lparam == win32con.WM_RBUTTONUP:
            _show_tray_menu(hwnd)
        return 0
    if msg == win32con.WM_DESTROY:
        win32gui.PostQuitMessage(0)
        return 0
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

def _show_tray_menu(hwnd):
    menu = win32gui.CreatePopupMenu()
    win32gui.AppendMenu(menu, win32con.MF_STRING, 1001, "显示窗口")
    win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
    win32gui.AppendMenu(menu, win32con.MF_STRING, 1002, "退出")
    pos = win32gui.GetCursorPos()
    win32gui.SetForegroundWindow(hwnd)
    cmd = win32gui.TrackPopupMenu(menu, win32con.TPM_RIGHTBUTTON | win32con.TPM_RETURNCMD, pos[0], pos[1], 0, hwnd, None)
    win32gui.PostMessage(hwnd, win32con.WM_NULL, 0, 0)
    win32gui.DestroyMenu(menu)
    if cmd == 1001:
        _show_window(None, None)
    elif cmd == 1002:
        _quit_app()


def _tray_thread():
    global _tray_icon
    hicon = None
    try:
        hicon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
        hicon = win32gui.LoadImage(0, ICON_PATH, win32con.IMAGE_ICON, 32, 32, hicon_flags)
    except Exception:
        pass
    if not hicon:
        hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

    # Create hidden window and register tray icon（用 win32gui tuple 格式，稳定可靠）
    hwnd = _create_tray_hwnd()

    # 注册前先写注册表 IsPromoted=1
    _ensure_tray_visible()

    tray_flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
    nid = (hwnd, _NOTIFY_ICON_ID, tray_flags, _WM_TRAYICON, hicon, "策划工具箱")
    win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
    _tray_icon = hwnd
    _tray_nid = nid

    # 等待 Explorer 创建 NotifyIconSettings 注册表条目，然后设 IsPromoted=1
    # Windows 创建条目时机不确定，用重试机制确保生效
    _ensure_tray_visible_fallback()
    _tray_retry_count = 0
    while _tray_retry_count < 6:
        time.sleep(1)
        _tray_retry_count += 1
        # 扫描注册表，如果找到匹配条目则设 IsPromoted=1 并重注册
        found = _ensure_tray_visible_fallback()
        if found:
            # 找到条目后重新注册图标，让 Explorer 即时读取 IsPromoted
            try:
                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
                win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
            except Exception:
                pass
            break

    # Message loop
    from ctypes import wintypes as _wt
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    msg = _wt.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0):
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

    # Cleanup
    win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
    if hicon:
        win32gui.DestroyIcon(hicon)
    os._exit(0)


def _get_cursor_screen_center(win_w=None, win_h=None):
    if win_w is None:
        win_w = WINDOW_W
    if win_h is None:
        win_h = WINDOW_H
    try:
        cursor = win32api.GetCursorPos()
        monitor = win32api.MonitorFromPoint(cursor, win32con.MONITOR_DEFAULTTONEAREST)
        info = win32api.GetMonitorInfo(monitor)
        ml, mt, mr, mb = info["Monitor"]
        cx = ml + (mr - ml - win_w) // 2
        cy = mt + (mb - mt - win_h) // 2
    except Exception:
        sw = win32api.GetSystemMetrics(0)
        sh = win32api.GetSystemMetrics(1)
        cx = (sw - win_w) // 2
        cy = (sh - win_h) // 2
    return cx, cy


def _center_on_cursor_screen(hwnd):
    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    win_w = max(rect.right - rect.left, 800)
    win_h = max(rect.bottom - rect.top, 400)
    cx, cy = _get_cursor_screen_center(win_w, win_h)
    ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
    ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex & ~0x8)
    win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, cx, cy, win_w, win_h,
                          win32con.SWP_NOACTIVATE)


def _save_window_rect():
    try:
        hwnd = _resolve_main_window_hwnd()
        if not hwnd:
            return
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h_ = rect.bottom - rect.top
        if w >= 400 and h_ >= 300:
            config = load_config()
            config["window_w"] = w
            config["window_h"] = h_
            save_config(config)
    except Exception:
        pass


def _undock_and_center(hwnd):
    ctypes.windll.user32.ShowWindow(hwnd, 9)
    _show_taskbar_icon(hwnd)
    if _docker:
        _docker.docked = None
        _docker._last_docked_edge = None
        _now = time.perf_counter()
        if _now >= _docker._busy_until:
            _docker._busy_until = _now + 0.3
    try:
        _center_on_cursor_screen(hwnd)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass


def _find_window_hwnd(timeout=5, window=None):
    start = time.time()
    while time.time() - start < timeout:
        hwnd = _resolve_main_window_hwnd(window)
        if hwnd:
            return hwnd
        time.sleep(0.1)
    return None


def _dnd_on_drop(window, e):
    target_id = ''
    target = e.get('target')
    if target:
        target_id = target.get('id', '')
    files = e.get('dataTransfer', {}).get('files', [])
    if not files:
        return
    path = files[0].get('pywebviewFullPath')
    if not path:
        return
    if not target_id:
        try:
            target_id = window.evaluate_js('_lastDropTargetId || ""')
        except Exception:
            pass
    if not target_id:
        return
    js_path = json.dumps(path)
    if target_id == 'svn_url':
        js = f"document.getElementById('{target_id}').value={js_path};onSvnUrlPicked();"
    else:
        js = f"document.getElementById('{target_id}').value={js_path};document.getElementById('{target_id}').dispatchEvent(new Event('change',{{bubbles:true}}));"

    def _inj():
        try:
            window.evaluate_js(js)
        except Exception:
            pass
    threading.Thread(target=_inj, daemon=True).start()


def _dnd_on_loaded(window):
    try:
        from webview.dom import DOMEventHandler
        window.dom.document.events.drop += DOMEventHandler(lambda e: _dnd_on_drop(window, e), True, True)
    except Exception:
        pass


def _dnd_on_shown(window):
    pass


def _init_dnd(window):
    window.events.loaded += lambda: _dnd_on_loaded(window)
    window.events.shown += lambda: _dnd_on_shown(window)


def _set_progress(window, pct, text):
    _set_native_splash(pct, text)
    try:
        window.evaluate_js(
            f"var e=document.getElementById('sbar');if(e)e.style.width='{pct}%';"
            f"var t=document.getElementById('stxt');if(t)t.innerText='{text}';"
            f"var p=document.getElementById('spct');if(p)p.innerText='{pct}%'"
        )
    except Exception:
        pass


def main():
    global _main_window, _main_hwnd
    _acquire_instance_lock()
    _ensure_app_id()
    _ensure_frozen_config()

    flask_thread = threading.Thread(target=_start_flask, daemon=True)
    flask_thread.start()

    tray_thread = threading.Thread(target=_tray_thread, daemon=True)
    tray_thread.start()

    config = load_config()
    saved_w = config.get("window_w", 0)
    saved_h = config.get("window_h", 0)
    has_saved = saved_w >= 800 and saved_h >= 400
    win_w = saved_w if has_saved else WINDOW_W
    win_h = saved_h if has_saved else WINDOW_H
    init_cx, init_cy = _get_cursor_screen_center(win_w, win_h)

    if not _wait_for_flask(timeout=15):
        print("[错误] Flask 未能在 15 秒内就绪", file=sys.stderr)

    resize_api = ResizeApi()

    window = webview.create_window(
        "策划工具箱",
        url="http://127.0.0.1:18123",
        width=win_w,
        height=win_h,
        x=init_cx,
        y=init_cy,
        frameless=True,
        easy_drag=False,
        shadow=False,
        hidden=False,
        background_color="#0f1115",
        min_size=(400, 300),
        text_select=True,
        zoomable=False,
        resizable=True,
        js_api=resize_api,
    )
    _main_window = window
    _main_hwnd = None
    resize_api.set_window(window)

    _init_dnd(window)
    window.events.resized += _save_window_rect

    def _on_closing():
        global _force_close
        if _force_close:
            _force_close = False
            return True
        _hide_main_window()
        return False

    window.events.closing += _on_closing

    if has_saved:
        def _restore_window_size():
            try:
                cx, cy = _get_cursor_screen_center(saved_w, saved_h)
                window.move(cx, cy)
                window.resize(saved_w, saved_h)
            except Exception:
                pass
        window.events.shown += _restore_window_size


    def _sigint_handler(signum, frame):
        os._exit(0)

    signal.signal(signal.SIGINT, _sigint_handler)

    def _boot_app(window):
        print("[DEBUG] _boot_app 开始", file=sys.stderr)
        window.events.loaded.wait(timeout=30)
        loading_started = time.time()
        _set_progress(window, 15, "界面资源已加载")
        print("[DEBUG] 窗口已加载", file=sys.stderr)
        _set_window_icon()
        _set_progress(window, 30, "应用图标已设置")
        print("[DEBUG] 图标已设置", file=sys.stderr)

        global _docker
        docker = EdgeDocker(window)
        _docker = docker
        docker.start()
        _set_progress(window, 45, "窗口行为已就绪")
        print("[DEBUG] EdgeDocker 已启动", file=sys.stderr)

        hwnd = _find_window_hwnd(timeout=0.5)
        if hwnd:
            _show_taskbar_icon(hwnd)
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass
        print("[DEBUG] Loading 已显示", file=sys.stderr)

        def _finish_loading_when_ready():
            ready = resize_api.ready_event.wait(timeout=0.5)
            if not ready:
                start = time.time()
                while time.time() - start < 8:
                    try:
                        ready = bool(window.evaluate_js(
                            "!!(document.querySelector('.nav-btn.active') && "
                            "document.getElementById('tab-svn') && "
                            "document.getElementById('svn_log'))"
                        ))
                    except Exception:
                        ready = False
                    if ready:
                        break
                    time.sleep(0.1)
            if ready:
                _set_progress(window, 85, "主界面已生成")
                print("[DEBUG] 前端已完成初始化", file=sys.stderr)
            else:
                _set_progress(window, 85, "启动检查超时")
                print("[警告] 前端初始化检查超时，显示窗口用于诊断", file=sys.stderr)

            min_loading_secs = 2.0
            remain = min_loading_secs - (time.time() - loading_started)
            if remain > 0:
                time.sleep(remain)
            _set_progress(window, 100, "启动完成")
            time.sleep(0.28)
            try:
                window.evaluate_js(
                    "requestAnimationFrame(() => requestAnimationFrame(() => "
                    "document.body.classList.add('app-ready')))"
                )
            except Exception:
                pass
            print("[DEBUG] _boot_app 完成", file=sys.stderr)

        threading.Thread(target=_finish_loading_when_ready, daemon=True).start()

    try:
        webview.start(_boot_app, window, debug=False)
    finally:
        _close_native_splash()
        _stop_flask()
        if _tray_icon:
            try:
                win32gui.PostMessage(_tray_icon, win32con.WM_CLOSE, 0, 0)
            except Exception:
                pass
    sys.exit(0)


if __name__ == "__main__":
    main()
