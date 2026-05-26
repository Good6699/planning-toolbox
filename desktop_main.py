#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""策划工具箱桌面壳 — pywebview + Flask + QQ式贴边 + 系统托盘"""
import sys
import os

_pm = os.path.join(os.path.dirname(os.path.abspath(__file__)), "py_modules")
if os.path.isdir(_pm) and _pm not in sys.path:
    sys.path.insert(0, _pm)

import json
import threading
import time
import socket
import signal
import urllib.request
import ctypes.wintypes
import webview
import win32gui
import win32con
import win32api
import pystray
from PIL import Image, ImageDraw
from toolbox_config import load_config, save_config

WINDOW_W = 1100
WINDOW_H = 700

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
.lb{width:84px;height:84px;border-radius:20px;background:linear-gradient(180deg,rgba(255,255,255,.08),rgba(255,255,255,.02));border:1px solid rgba(255,255,255,.08);display:flex;align-items:center;justify-content:center}
.lb svg{width:58px;height:58px}
.t{margin-top:20px;font-size:30px;font-weight:700;letter-spacing:1px;color:#fff}
.st{margin-top:8px;font-size:13px;color:#8b96ad;letter-spacing:3px}
.p{position:absolute;bottom:64px;width:800px;text-align:center}
.pt{font-size:11px;letter-spacing:2px;color:#8b96ad;margin-bottom:12px}
.pw{width:100%;height:9px;background:rgba(255,255,255,.06);overflow:hidden;border-radius:999px}
.pb{width:0%;height:100%;background:linear-gradient(90deg,#5ea2ff,#7cb8ff);box-shadow:0 0 20px rgba(94,162,255,.7);transition:width .35s ease}
.pn{font-size:11px;color:#5f6b80;margin-top:8px;letter-spacing:1px}
@keyframes r2{0%{opacity:0;transform:scale(.96)}100%{opacity:1;transform:scale(1)}}
@keyframes f{0%{transform:translateX(-40px)}100%{transform:translateX(40px)}}
</style>
</head>
<body>
<div class="f"></div>
<div class="r">
<div class="lw"><div class="lb"><svg viewBox="0 0 24 24"><path d="M22.5,3 L18,1.5 L12,4.5 L6,10.5 L3,16.5 L3,22.5 L12,22.5 L18,16.5 Z" fill="#5ea2ff"/><line x1="3" y1="22.5" x2="22.5" y2="3" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/><line x1="18" y1="16.5" x2="6" y2="16.5" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/></svg></div><div class="t">策划工具箱</div><div class="st">Game Pipeline Toolkit</div></div>
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
_tray_stop = threading.Event()
_window_visible = True
_docker = None
_is_dragging = False


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
        self._stop = threading.Event()
        self._thread = None
        self._prev_fg = 0
        self._taskbar_activate = False

    def _resolve_hwnd(self):
        if self.hwnd and win32gui.IsWindow(self.hwnd):
            return self.hwnd
        try:
            h = ctypes.windll.user32.FindWindowW(None, "策划工具箱")
            if h:
                self.hwnd = h
                return h
        except Exception:
            pass
        return None

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
                self._prev_fg = win32gui.GetForegroundWindow()
                try:
                    ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                    ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex | 0x8)
                    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
                    desktop = ctypes.windll.user32.FindWindowW("Progman", None)
                    if desktop:
                        ctypes.windll.user32.SwitchToThisWindow(desktop, True)
                        ctypes.windll.user32.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
                except Exception:
                    pass
        except Exception:
            self._busy_until = 0.0

    def _slide_out(self, hwnd):
        self._op_seq += 1
        seq = self._op_seq
        self._animating_seq = seq
        self._busy_until = time.perf_counter() + 0.6
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
                self.docked = None
                try:
                    ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                    ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex & ~0x8)
                    win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
                except Exception:
                    pass
        except Exception:
            pass


def _acquire_instance_lock():
    global _instance_socket
    _instance_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _instance_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        _instance_socket.bind(("127.0.0.1", 18124))
    except socket.error:
        print("[单实例锁] 端口 18124 已被占用，已有实例在运行", file=sys.stderr)
        sys.exit(0)


def _start_flask():
    global _flask_server
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    sys.path.insert(0, script_dir)
    pm = os.path.join(script_dir, "py_modules")
    if os.path.isdir(pm) and pm not in sys.path:
        sys.path.insert(0, pm)
    from web_app import app
    from werkzeug.serving import make_server
    _flask_server = make_server("127.0.0.1", 18123, app, threaded=True)
    _flask_server.serve_forever()


def _wait_for_flask(timeout=10):
    url = "http://127.0.0.1:18123"
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def _make_tray_image():
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, 31, 31], radius=6, outline="#3a5580", width=1)
    blue = "#5ea2ff"
    body = [
        (30, 4),
        (24, 2),
        (16, 6),
        (8, 14),
        (4, 22),
        (4, 30),
        (16, 30),
        (24, 22),
    ]
    draw.polygon(body, fill=blue)
    draw.line([(4, 30), (30, 4)], fill="#ffffff", width=2)
    draw.line([(24, 22), (8, 22)], fill="#ffffff", width=2)
    return img


def _show_window(icon, item=None):
    global _window_visible
    hwnd = ctypes.windll.user32.FindWindowW(None, "策划工具箱")
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 9)
    try:
        for w in webview.windows:
            w.restore()
            w.show()
            _window_visible = True
    except Exception:
        pass
    if hwnd:
        if _docker and _docker.docked:
            _undock_and_center(hwnd)
        else:
            win32gui.SetForegroundWindow(hwnd)


def _quit_app(icon, item=None):
    _save_window_rect()
    icon.stop()


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

    def set_window(self, window):
        self._window = window

    def set_window_rect(self):
        if not self._window:
            return
        try:
            hwnd = ctypes.windll.user32.FindWindowW(None, "策划工具箱")
            if not hwnd:
                return
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            self._win_x = rect.left
            self._win_y = rect.top
            self._win_w = rect.right - rect.left
            self._win_h = rect.bottom - rect.top
            self._cursor_x, self._cursor_y = win32api.GetCursorPos()
        except Exception:
            pass

    def start_resize(self, edge):
        global _is_dragging
        _is_dragging = True
        self.set_window_rect()
        self._edge = edge
        self._active = True

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
            ctypes.windll.user32.SetWindowPos(
                ctypes.windll.user32.FindWindowW(None, "策划工具箱"),
                0, x, y, w, h, 0x0004
            )
        except Exception:
            return False
        return True

    def stop_resize(self):
        global _is_dragging
        _is_dragging = False
        self._active = False

    def app_ready(self):
        pass

    def browseFile(self, directory=""):
        try:
            w = webview.windows[0]
            if w:
                result = w.create_file_dialog(
                    webview.OPEN_DIALOG,
                    directory=directory,
                    allow_multiple=False,
                    file_types=('Excel Files (*.xlsm;*.xlsx;*.xls)', 'All Files (*.*)'),
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
            subprocess.Popen(f'explorer "{path}"', shell=True)
            return True
        except Exception as e:
            print("[open_folder]", e)
            return False


def _tray_thread():
    global _tray_icon
    _tray_icon = pystray.Icon(
        "planning-toolbox",
        _make_tray_image(),
        "策划工具箱",
        menu=pystray.Menu(
            pystray.MenuItem("显示窗口", _show_window, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", _quit_app),
        )
    )
    _tray_icon.run()
    os._exit(0)


_wnd_proc_ref = None


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
        hwnd = ctypes.windll.user32.FindWindowW(None, "策划工具箱")
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
    if _docker:
        _docker.docked = None
        _docker._busy_until = time.perf_counter() + 0.6
    try:
        _center_on_cursor_screen(hwnd)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass


_wnd_proc_fallback_ref = None
_fallback_original = 0


def _fallback_subclass(hwnd):
    global _wnd_proc_fallback_ref
    GWLP_WNDPROC = -4

    WNDPROC = ctypes.WINFUNCTYPE(
        ctypes.c_longlong, ctypes.c_longlong, ctypes.c_uint, ctypes.c_longlong, ctypes.c_longlong
    )

    ctypes.windll.user32.DefWindowProcW.argtypes = (
        ctypes.c_longlong, ctypes.c_uint, ctypes.c_longlong, ctypes.c_longlong
    )
    ctypes.windll.user32.CallWindowProcW.argtypes = (
        ctypes.c_longlong, ctypes.c_longlong, ctypes.c_uint, ctypes.c_longlong, ctypes.c_longlong
    )

    def _wnd_proc(hwnd_inner, msg, wparam, lparam):
        global _window_visible
        if msg == 0x0010:
            _save_window_rect()
            try:
                for w in webview.windows:
                    w.hide()
            except Exception:
                pass
            ctypes.windll.user32.ShowWindow(hwnd_inner, 0)
            _window_visible = False
            return 0
        if msg == 0x0006 and wparam == 1:
            if _docker and _docker.docked:
                _docker._taskbar_activate = True
        if _fallback_original:
            return ctypes.windll.user32.CallWindowProcW(
                _fallback_original, hwnd_inner, msg, wparam, lparam
            )
        return ctypes.windll.user32.DefWindowProcW(
            hwnd_inner, msg, wparam, lparam
        )

    _wnd_proc_fallback_ref = WNDPROC(_wnd_proc)
    ctypes.windll.user32.SetWindowLongPtrW.restype = ctypes.c_longlong
    new_ptr = ctypes.cast(_wnd_proc_fallback_ref, ctypes.c_void_p).value
    global _fallback_original
    _fallback_original = ctypes.windll.user32.SetWindowLongPtrW(
        hwnd, GWLP_WNDPROC, new_ptr
    )
    print(f"[子类化] fallback 完成, 原 WNDPROC={_fallback_original:#x}", file=sys.stderr)


def _subclass_window(hwnd):
    global _wnd_proc_ref
    _SUBCLASS_ID = 1001

    SUBCLASSPROC = ctypes.WINFUNCTYPE(
        ctypes.c_longlong,
        ctypes.c_longlong, ctypes.c_uint, ctypes.c_longlong, ctypes.c_longlong,
        ctypes.c_ulonglong, ctypes.c_ulonglong,
    )

    def _subclass_proc(hwnd_inner, msg, wparam, lparam, uId, dwRef):
        global _window_visible
        if msg == 0x0010:
            _save_window_rect()
            try:
                for w in webview.windows:
                    w.hide()
            except Exception:
                pass
            ctypes.windll.user32.ShowWindow(hwnd_inner, 0)
            _window_visible = False
            return 0
        if msg == 0x0006 and wparam == 1:
            if _docker and _docker.docked:
                _docker._taskbar_activate = True
        return ctypes.windll.comctl32.DefSubclassProc(
            hwnd_inner, msg, wparam, lparam
        )

    _wnd_proc_ref = SUBCLASSPROC(_subclass_proc)
    ctypes.windll.comctl32.DefSubclassProc.restype = ctypes.c_longlong
    ctypes.windll.comctl32.SetWindowSubclass.argtypes = (
        ctypes.c_longlong, ctypes.c_ulonglong, ctypes.c_ulonglong, ctypes.c_ulonglong,
    )
    ctypes.windll.comctl32.InitCommonControls()
    result = ctypes.windll.comctl32.SetWindowSubclass(
        hwnd, ctypes.cast(_wnd_proc_ref, ctypes.c_void_p).value,
        _SUBCLASS_ID, 0
    )
    if not result:
        print("[子类化] SetWindowSubclass 失败, 尝试 fallback", file=sys.stderr)
        _fallback_subclass(hwnd)


def _find_window_hwnd(timeout=5):
    start = time.time()
    while time.time() - start < timeout:
        try:
            h = ctypes.windll.user32.FindWindowW(None, "策划工具箱")
            if h:
                return h
        except Exception:
            pass
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
    try:
        from webview.platforms.winforms import BrowserView
        form = BrowserView.instances.get(window.uid)
        if not form or not hasattr(form, 'browser'):
            return
        edge = form.browser
        wv = getattr(edge, 'webview', None)
        if wv is None:
            return
        try:
            from System import Action
            form.Invoke(Action(lambda: setattr(wv, 'AllowDrop', False)))
        except Exception:
            pass
    except Exception:
        pass


def _init_dnd(window):
    window.events.loaded += lambda: _dnd_on_loaded(window)
    window.events.shown += _dnd_on_shown


def _set_progress(window, pct, text):
    try:
        window.evaluate_js(
            f"var e=document.getElementById('sbar');if(e)e.style.width='{pct}%';"
            f"var t=document.getElementById('stxt');if(t)t.innerText='{text}';"
            f"var p=document.getElementById('spct');if(p)p.innerText='{pct}%'"
        )
    except Exception:
        pass


def main():
    _acquire_instance_lock()

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

    resize_api = ResizeApi()

    window = webview.create_window(
        "策划工具箱",
        html=SPLASH_HTML,
        width=win_w,
        height=win_h,
        x=init_cx,
        y=init_cy,
        frameless=True,
        easy_drag=False,
        shadow=True,
        background_color="#0f1115",
        min_size=(400, 300),
        text_select=True,
        zoomable=False,
        resizable=True,
        js_api=resize_api,
    )
    resize_api.set_window(window)

    _init_dnd(window)
    window.events.resized += _save_window_rect

    if has_saved:
        def _restore_window_size():
            try:
                cx, cy = _get_cursor_screen_center(saved_w, saved_h)
                window.move(cx, cy)
                window.resize(saved_w, saved_h)
            except Exception:
                pass
        window.events.shown += _restore_window_size

    def _init_window(hwnd=None):
        if hwnd is None:
            hwnd = _find_window_hwnd(timeout=10)
        if not hwnd:
            return
        try:
            _subclass_window(hwnd)
        except Exception as e:
            print(f"[子类化异常] {e}", file=sys.stderr)

    hwnd = _find_window_hwnd(timeout=0.3)
    if hwnd:
        _init_window(hwnd)
    else:
        threading.Thread(target=_init_window, daemon=True).start()

    def _sigint_handler(signum, frame):
        os._exit(0)

    signal.signal(signal.SIGINT, _sigint_handler)

    def _boot_app(window):
        window.events.loaded.wait(timeout=30)
        _set_progress(window, 15, "界面就绪")

        global _docker
        docker = EdgeDocker(window)
        _docker = docker
        docker.start()
        _set_progress(window, 30, "初始化服务中")

        if not _wait_for_flask(timeout=15):
            print("[错误] Flask 未能在 15 秒内就绪", file=sys.stderr)
            return
        _set_progress(window, 55, "后端就绪")

        for i in range(6):
            time.sleep(0.4)
            _set_progress(window, 55 + i * 5, "加载模块中")

        _set_progress(window, 90, "准备就绪")
        time.sleep(0.4)
        _set_progress(window, 100, "启动中")
        time.sleep(0.2)

        try:
            window.load_url("http://127.0.0.1:18123")
        except Exception as e:
            print(f"[load_url] {e}", file=sys.stderr)

    try:
        webview.start(_boot_app, window, debug=False)
    finally:
        if not _tray_stop.is_set():
            _tray_stop.set()
            if _tray_icon:
                _tray_icon.stop()
    sys.exit(0)


if __name__ == "__main__":
    main()
