#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""策划工具箱 EXE 界面原型 - pywebview 无边框窗口 + QQ式贴边"""
import sys
import os
import threading
from ctypes import windll
import webview
import win32gui
import win32con
import win32api

SCREEN_W = win32api.GetSystemMetrics(0)
SCREEN_H = win32api.GetSystemMetrics(1)
WINDOW_W = 1100
WINDOW_H = 700

EDGE_THRESHOLD = 40
DOCK_VISIBLE = 4
ANIM_FRAMES = 18
ANIM_INTERVAL = 14


class EdgeDocker:
    def __init__(self, window):
        self.window = window
        self.hwnd = None
        self.docked = None
        self.dock_pos = None
        self.dock_w = WINDOW_W
        self.dock_h = WINDOW_H
        self.animating = False
        self._timer = None
        self._last_cursor = (0, 0)
        self.threading = __import__("threading")

    def _resolve_hwnd(self):
        if self.hwnd:
            return self.hwnd
        try:
            h = windll.user32.FindWindowW(None, "策划工具箱")
            if h:
                self.hwnd = h
                return h
        except:
            pass
        try:
            def cb(h, _):
                if win32gui.IsWindowVisible(h):
                    t = win32gui.GetWindowText(h)
                    if "策划工具箱" in t:
                        self.hwnd = h
                        return False
                return True
            win32gui.EnumWindows(cb, None)
        except:
            pass
        return self.hwnd

    def start(self):
        self._resolve_hwnd()
        self._tick()

    def _tick(self):
        hwnd = self._resolve_hwnd()
        if not hwnd or not win32gui.IsWindow(hwnd):
            self._schedule_next()
            return

        try:
            rect = win32gui.GetWindowRect(hwnd)
            x, y, r, b = rect
            w = r - x
            h = b - y
        except:
            self._schedule_next()
            return

        cx, cy = win32api.GetCursorPos()

        in_window = (x <= cx <= r and y <= cy <= b)

        if self.animating:
            self._schedule_next()
            return

        if self.docked:
            if self.docked in ("right", "left"):
                trigger = (cx >= SCREEN_W - DOCK_VISIBLE - 8 if self.docked == "right"
                           else cx <= DOCK_VISIBLE + 8)
                trigger = trigger and (y <= cy <= y + h)
                if trigger:
                    self._slide_out(hwnd)
            elif self.docked == "top":
                trigger = (cy <= DOCK_VISIBLE + 8) and (x <= cx <= r)
                if trigger:
                    self._slide_out(hwnd)
            elif self.docked == "bottom":
                trigger = (cy >= SCREEN_H - DOCK_VISIBLE - 8) and (x <= cx <= r)
                if trigger:
                    self._slide_out(hwnd)
        else:
            if not in_window:
                snap = None
                if x <= EDGE_THRESHOLD - w:
                    snap = "left"
                elif r >= SCREEN_W - EDGE_THRESHOLD:
                    snap = "right"
                elif y <= EDGE_THRESHOLD - h:
                    snap = "top"
                elif b >= SCREEN_H - EDGE_THRESHOLD:
                    snap = "bottom"
                if snap:
                    self._slide_in(hwnd, snap)

        self._schedule_next()

    def _slide_in(self, hwnd, edge):
        self.animating = True
        rect = win32gui.GetWindowRect(hwnd)
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]
        self.dock_w = w
        self.dock_h = h

        if edge == "right":
            target_x = SCREEN_W - DOCK_VISIBLE
            target_y = rect[1]
        elif edge == "left":
            target_x = DOCK_VISIBLE - w
            target_y = rect[1]
        elif edge == "top":
            target_x = rect[0]
            target_y = DOCK_VISIBLE - h
        else:
            target_x = rect[0]
            target_y = SCREEN_H - DOCK_VISIBLE

        start_x, start_y = rect[0], rect[1]
        for i in range(1, ANIM_FRAMES + 1):
            t = i / ANIM_FRAMES
            eased = 1 - (1 - t) ** 3
            cur_x = int(start_x + (target_x - start_x) * eased)
            cur_y = int(start_y + (target_y - start_y) * eased)
            try:
                win32gui.SetWindowPos(hwnd, 0, cur_x, cur_y, 0, 0,
                                      win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
            except:
                pass
            win32api.Sleep(ANIM_INTERVAL)

        self.docked = edge
        self.animating = False

    def _slide_out(self, hwnd):
        self.animating = True
        rect = win32gui.GetWindowRect(hwnd)
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]

        if self.docked == "right":
            target_x = SCREEN_W - w
            target_y = rect[1]
        elif self.docked == "left":
            target_x = 0
            target_y = rect[1]
        elif self.docked == "top":
            target_x = rect[0]
            target_y = 0
        else:
            target_x = rect[0]
            target_y = SCREEN_H - h

        start_x, start_y = rect[0], rect[1]
        for i in range(1, ANIM_FRAMES + 1):
            t = i / ANIM_FRAMES
            eased = t ** 3
            cur_x = int(start_x + (target_x - start_x) * eased)
            cur_y = int(start_y + (target_y - start_y) * eased)
            try:
                win32gui.SetWindowPos(hwnd, 0, cur_x, cur_y, 0, 0,
                                      win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
            except:
                pass
            win32api.Sleep(ANIM_INTERVAL)

        self.docked = None
        self.animating = False

    def _schedule_next(self):
        t = self.threading.Timer(0.06, self._tick)
        t.daemon = True
        t.start()


def _get_html():
    return r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>策划工具箱</title>
<style>
:root{
  --bg:#0f1115;
  --bg2:#151821;
  --panel:#171b24;
  --panel2:#1d2330;
  --card:#1b2230cc;
  --line:#2a3142;
  --text:#f2f5ff;
  --sub:#aeb8cc;
  --dim:#7f8aa3;
  --accent:#5ea2ff;
  --accent2:#7cb8ff;
  --accent3:#3784ff;
  --success:#52d273;
  --danger:#ff637d;
  --radius:12px;
  --radius-sm:8px;
  --space-xs:4px;
  --space-sm:8px;
  --space-md:12px;
  --space-lg:16px;
  --space-xl:20px;
  --space-2xl:24px;
  --space-3xl:32px;
  --btn-h:36px;
  --btn-h-lg:42px;
  --sidebar-width:260px;
  --shadow:0 10px 30px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.03);
}
*{box-sizing:border-box;}
html{font-size:15px;}
html,body{
  width:100%;height:100%;overflow:hidden;margin:0;
  background:var(--bg);
  font-family:"Segoe UI","Microsoft YaHei UI","PingFang SC",sans-serif;
  font-weight:500;color:var(--text);
  -webkit-user-select:none;user-select:none;
  -webkit-font-smoothing:auto;
}
body{
  background:radial-gradient(circle at 50% 0%,#1c2540 0%,#0f1115 45%);
}
button,input,textarea,select{font:inherit;color:inherit;}

.drag-bar{
  position:fixed;top:0;left:0;right:0;height:32px;
  z-index:9999;
}
.drag-bar:hover{cursor:default;}

.app{
  width:100%;height:100%;
  display:grid;
  grid-template-columns:var(--sidebar-width) minmax(0,1fr);
}

.sidebar{
  background:linear-gradient(180deg,rgba(255,255,255,.025),rgba(255,255,255,.005));
  backdrop-filter:blur(24px);
  border-right:1px solid rgba(255,255,255,.04);
  padding:var(--space-lg) var(--space-md);
  display:flex;flex-direction:column;
  padding-top:40px;
}

.logo{
  display:flex;align-items:center;gap:10px;
  padding:0 6px 6px;
}
.logo-icon{
  width:36px;height:36px;border-radius:8px;
  background:linear-gradient(135deg,var(--accent),var(--accent3));
  display:flex;align-items:center;justify-content:center;
  font-size:16px;font-weight:700;
  box-shadow:0 8px 28px rgba(94,162,255,.3),inset 0 1px 0 rgba(255,255,255,.3);
  color:#fff;
}
.logo-icon svg{width:20px;height:20px;}
.logo h1{font-size:15px;margin:0;font-weight:600;}
.logo span{color:var(--dim);font-size:11px;}

.nav{
  display:flex;flex-direction:column;gap:4px;
  margin-top:20px;flex:1;
}
.nav-btn{
  height:36px;min-height:36px;font-size:12px;
  border:none;border-radius:8px;background:transparent;
  color:var(--sub);padding:0 12px;
  display:flex;align-items:center;gap:10px;
  cursor:pointer;transition:.18s;text-align:left;
}
.nav-btn:hover{background:rgba(255,255,255,.03);color:#fff;}
.nav-btn.active{
  color:#fff;
  background:linear-gradient(135deg,rgba(94,162,255,.22),rgba(94,162,255,.06));
  box-shadow:0 0 0 1px rgba(94,162,255,.18),0 8px 20px rgba(94,162,255,.1);
  font-weight:600;
}
.nav-btn svg{width:16px;height:16px;flex-shrink:0;fill:currentColor;opacity:.7;}

.main{
  min-width:0;display:flex;flex-direction:column;height:100%;
}

.topbar{
  height:68px;padding:0 24px;
  border-bottom:1px solid rgba(255,255,255,.04);
  display:flex;align-items:center;justify-content:space-between;
  gap:12px;flex-shrink:0;
}

.page-title h2{font-size:20px;font-weight:700;letter-spacing:.3px;margin:0;}
.page-title span{color:var(--dim);font-size:11px;}

.status{
  display:flex;align-items:center;gap:6px;
  color:var(--sub);font-size:11px;
}
.status-dot{
  width:8px;height:8px;border-radius:999px;
  background:var(--success);
  box-shadow:0 0 12px rgba(82,210,115,.7);
}

.content{
  flex:1;overflow:auto;padding:20px;
  width:100%;min-width:0;
}
.content-inner{
  width:100%;max-width:1800px;margin:0 auto;
}

.workbench{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(360px,1fr));
  gap:16px;
}

.card{
  background:linear-gradient(180deg,rgba(33,40,56,.9),rgba(20,24,34,.94));
  border:1px solid rgba(255,255,255,.05);
  border-radius:16px;padding:16px;
  box-shadow:0 12px 40px rgba(0,0,0,.3),inset 0 1px 0 rgba(255,255,255,.02);
  overflow:hidden;position:relative;
  transition:border-color .2s;
}
.card:hover{border-color:rgba(255,255,255,.07);}
.card-title{
  font-size:14px;font-weight:700;margin-bottom:10px;
  display:flex;align-items:center;gap:8px;
}
.card-title .icon{
  width:32px;height:32px;border-radius:8px;
  display:flex;align-items:center;justify-content:center;
  font-size:14px;flex-shrink:0;
}
.icon-blue{background:rgba(94,162,255,.15);color:var(--accent);}
.icon-green{background:rgba(82,210,115,.15);color:var(--success);}
.icon-purple{background:rgba(147,130,255,.15);color:#9382ff;}
.icon-orange{background:rgba(255,165,80,.15);color:#ffa550;}

.form-group{margin-bottom:12px;}
.form-group label{
  display:block;margin-bottom:4px;
  color:var(--sub);font-size:11px;
}

input,select{
  width:100%;border:none;outline:none;
  background:#0e1219;border:1px solid #2a3040;
  border-radius:8px;height:36px;min-height:36px;
  padding:0 10px;font-size:13px;color:#fff;
  transition:border-color .2s ease,box-shadow .2s ease;
}
input:focus,select:focus{
  border-color:var(--accent);
  box-shadow:0 0 0 3px rgba(94,162,255,.12);
}

.action-center{
  margin:20px 0 8px;
  display:flex;justify-content:center;gap:12px;
}

.btn{
  height:var(--btn-h);min-height:var(--btn-h);
  font-size:13px;border:none;border-radius:8px;
  padding:0 20px;cursor:pointer;transition:.18s;
  display:inline-flex;align-items:center;justify-content:center;
  gap:6px;font-weight:600;
}
.btn-primary{
  background:linear-gradient(135deg,var(--accent),var(--accent3));
  color:#fff;min-width:260px;
  height:var(--btn-h-lg);font-size:14px;
  border-radius:12px;
  box-shadow:0 12px 32px rgba(74,141,255,.32),inset 0 1px 0 rgba(255,255,255,.24);
}
.btn-primary:hover{
  box-shadow:0 16px 40px rgba(74,141,255,.45),inset 0 1px 0 rgba(255,255,255,.24);
  transform:translateY(-1px);
}
.btn-primary:active{transform:translateY(0);}

.empty-state{
  padding:48px 24px;color:var(--sub);text-align:center;
  font-size:13px;line-height:1.6;
}

.edge-indicator{
  position:fixed;right:0;top:50%;transform:translateY(-50%);
  width:4px;height:60px;border-radius:4px 0 0 4px;
  background:var(--accent);
  opacity:0;transition:opacity .3s;
  pointer-events:none;z-index:9998;
}
.edge-indicator.show{opacity:.6;}

.status-bar{
  height:32px;background:rgba(0,0,0,.25);
  border-top:1px solid rgba(255,255,255,.04);
  display:flex;align-items:center;
  padding:0 16px;font-size:10px;color:var(--dim);
  flex-shrink:0;
}
</style>
</head>
<body>

<div class="drag-bar pywebview-drag-region"></div>
<div class="edge-indicator" id="edge-ind"></div>

<div class="app">
  <aside class="sidebar">
    <div class="logo">
      <div class="logo-icon">
        <svg viewBox="0 0 24 24"><path d="M22.5,3 L18,1.5 L12,4.5 L6,10.5 L3,16.5 L3,22.5 L12,22.5 L18,16.5 Z" fill="#5ea2ff"/><line x1="3" y1="22.5" x2="22.5" y2="3" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/><line x1="18" y1="16.5" x2="6" y2="16.5" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/></svg>
      </div>
      <div>
        <h1>策划工具箱</h1>
        <span>v2.0 Desktop</span>
      </div>
    </div>
    <nav class="nav">
      <button class="nav-btn active">
        <svg viewBox="0 0 24 24"><path d="M17.65 6.35A7.96 7.96 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
        SVN 记录
      </button>
      <button class="nav-btn">
        <svg viewBox="0 0 24 24"><path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z"/></svg>
        上传 SVN
      </button>
      <button class="nav-btn">
        <svg viewBox="0 0 24 24"><path d="M22 9V7h-2V5a2 2 0 00-2-2H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-2h2v-2h-2v-2h2v-2h-2V9h2zm-4 10H4V5h14v14zM6 13h5v4H6v-4zm6-6h4v3h-4V7zM6 7h5v5H6V7zm6 4h4v6h-4v-6z"/></svg>
        工作流
      </button>
      <button class="nav-btn">
        <svg viewBox="0 0 24 24"><path d="M12.87 15.07l-2.54-2.51.03-.03A17.52 17.52 0 0014.07 6H17V4h-7V2H8v2H1v2h11.17C11.5 7.92 10.44 9.75 9 11.35 8.07 10.32 7.3 9.19 6.69 8h-2c.73 1.63 1.73 3.17 2.98 4.56l-5.09 5.02L4 19l5-5 3.11 3.11.76-2.04zM18.5 10h-2L12 22h2l1.12-3h4.75L21 22h2l-4.5-12zm-2.62 7l1.62-4.33L19.12 17h-3.24z"/></svg>
        翻译
      </button>
    </nav>
    <div style="margin-top:auto;padding:4px 0 0;">
      <div style="display:flex;align-items:center;gap:8px;color:var(--dim);font-size:10px;padding:4px 12px;">
        <span style="width:6px;height:6px;border-radius:50%;background:var(--success);"></span>
        就绪
      </div>
    </div>
  </aside>

  <div class="main">
    <header class="topbar">
      <div class="page-title">
        <h2>SVN 记录</h2>
        <span>一键对比 · 导出 · 摘要</span>
      </div>
      <div class="status">
        <span class="status-dot"></span>
        <span>空闲</span>
      </div>
    </header>
    <div class="content">
      <div class="content-inner">
        <div class="workbench">
          <div class="card">
            <div style="display:flex;align-items:flex-start;gap:12px;margin-bottom:16px;">
              <div class="icon-blue" style="width:40px;height:40px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;background:rgba(94,162,255,.12);">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="var(--accent)"><path d="M17.65 6.35A7.96 7.96 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
              </div>
              <div style="flex:1;">
                <div class="card-title" style="margin-bottom:4px;">SVN 版本对比</div>
                <div style="font-size:11px;color:var(--dim);">选择日期范围，自动抓取 SVN 日志并对比 Excel 差异</div>
              </div>
            </div>
            <div class="form-group">
              <label>SVN 地址</label>
              <input type="text" placeholder="https://svn.example.com/..." value="https://svn.game.com/trunk/Texts">
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
              <div class="form-group">
                <label>开始日期</label>
                <input type="date" value="2026-05-01">
              </div>
              <div class="form-group">
                <label>结束日期</label>
                <input type="date" value="2026-05-16">
              </div>
            </div>
            <div class="action-center" style="margin-bottom:0;">
              <button class="btn btn-primary">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                开始对比
              </button>
            </div>
          </div>

          <div class="card">
            <div style="display:flex;align-items:flex-start;gap:12px;margin-bottom:16px;">
              <div class="icon-green" style="width:40px;height:40px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;background:rgba(82,210,115,.12);">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="var(--success)"><path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z"/></svg>
              </div>
              <div style="flex:1;">
                <div class="card-title" style="margin-bottom:4px;">快捷导出</div>
                <div style="font-size:11px;color:var(--dim);">快速导出 SVN 仓库文件到本地目录</div>
              </div>
            </div>
            <div class="form-group">
              <label>输出目录</label>
              <input type="text" placeholder="选择输出目录..." value="D:\Output\svn_export">
            </div>
            <div class="action-center" style="margin-bottom:0;">
              <button class="btn btn-primary" style="background:linear-gradient(135deg,var(--success),#3ab060);box-shadow:0 12px 32px rgba(82,210,115,.25),inset 0 1px 0 rgba(255,255,255,.24);">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>
                开始导出
              </button>
            </div>
          </div>
        </div>

        <div class="card" style="margin-top:16px;">
          <div class="card-title">最近操作日志</div>
          <div style="background:#0e1219;border:1px solid var(--line);border-radius:8px;height:320px;overflow-y:auto;padding:12px;font-size:12px;font-family:'Cascadia Code','Consolas',monospace;line-height:1.8;">
            <div style="color:var(--dim);">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
            <div style="color:var(--accent);">[15:30:22]</div><span style="color:var(--sub);"> 就绪 — 等待操作</span>
            <div style="color:var(--dim);margin-top:8px;">策划工具箱 v2.0 Desktop 已就绪</div>
            <div style="color:var(--dim);">贴边功能：拖拽窗口到屏幕边缘自动吸附</div>
            <div style="color:var(--dim);">系统托盘图标：最小化到托盘，不占用任务栏</div>
            <div style="color:var(--dim);">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
          </div>
        </div>
      </div>
    </div>
    <div class="status-bar">
      <span>策划工具箱 Desktop · 端口 18123 · 本地运行</span>
    </div>
  </div>
</div>

</body>
</html>"""


def main():
    window = webview.create_window(
        "策划工具箱",
        html=_get_html(),
        width=WINDOW_W,
        height=WINDOW_H,
        x=(SCREEN_W - WINDOW_W) // 2,
        y=(SCREEN_H - WINDOW_H) // 2,
        frameless=True,
        easy_drag=False,
        shadow=True,
        text_select=True,
        background_color="#0f1115",
        zoomable=False,
    )

    docker = EdgeDocker(window)
    threading.Thread(target=docker.start, daemon=True).start()

    webview.start(debug=False)


if __name__ == "__main__":
    main()
