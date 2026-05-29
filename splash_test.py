#!/usr/bin/env python3
"""极简测试：逐一排除 splash 不显示的问题"""
import sys, os
_pm = os.path.join(os.path.dirname(os.path.abspath(__file__)), "py_modules")
if os.path.isdir(_pm) and _pm not in sys.path:
    sys.path.insert(0, _pm)
import webview
import time

HTML1 = """<!DOCTYPE html>
<html><body style="background:#0f1115;display:flex;align-items:center;justify-content:center;height:100%;margin:0">
<h1 style="color:#5ea2ff;font-family:sans-serif">splash test 1</h1>
</body></html>"""

HTML2 = """<!DOCTYPE html>
<html><body style="background:#0f1115;display:flex;align-items:center;justify-content:center;height:100%;margin:0">
<h1 style="color:#fff;font-family:sans-serif">splash test 2</h1>
</body></html>"""

RED_HTML = """<!DOCTYPE html>
<html><body style="background:#ff0000;display:flex;align-items:center;justify-content:center;height:100%;margin:0">
<h1 style="color:#fff;font-family:sans-serif">RED BG TEST</h1>
</body></html>"""

class Api:
    def app_ready(self):
        print("[API] app_ready called")


def _switch_after_3s(win):
    time.sleep(3)
    print("[后台] load_html(红色测试页)")
    try:
        win.load_html(RED_HTML)
        print("[后台] 成功")
    except Exception as e:
        print(f"[后台] 失败: {e}")


# ── 测试 1: html= 参数 ──
def test1_html():
    print("=== 测试 1: html= 参数 ===")
    w = webview.create_window("test1", html=HTML1, width=600, height=400,
                              background_color="#0f1115")
    webview.start(debug=True)


# ── 测试 2: html= + 后台切换 ──
def test2_html_then_load():
    print("=== 测试 2: html= + 后台load_html ===")
    w = webview.create_window("test2", html=HTML1, width=600, height=400,
                              js_api=Api(), background_color="#0f1115")
    webview.start(_switch_after_3s, w, debug=True)


# ── 测试 3: 本地文件路径 splash/splash.html ──
def test3_local_file():
    print("=== 测试 3: 本地文件 splash/splash.html ===")
    w = webview.create_window("test3", url="splash/splash.html", width=600, height=400,
                              js_api=Api(), background_color="#0f1115")
    webview.start(_switch_after_3s, w, debug=True)


# ── 测试 4: 本地文件路径 + html= 混合 ──
def test4_html_after_local():
    print("=== 测试 4: 本地文件 + _switch_to_html ===")
    w = webview.create_window("test4", url="splash/splash.html", width=600, height=400,
                              js_api=Api(), background_color="#0f1115")

    def _switch(win):
        time.sleep(2)
        print("[后台] load_html(HTML2)")
        win.load_html(HTML2)
    webview.start(_switch, w, debug=True)


if __name__ == "__main__":
    tests = {
        "1": ("html= 参数", test1_html),
        "2": ("html= + 后台load_html", test2_html_then_load),
        "3": ("本地文件 splash/splash.html", test3_local_file),
        "4": ("本地文件 + 后台load_html", test4_html_after_local),
    }
    for k, (n, f) in tests.items():
        print(f"  {k} → {n}")
    sel = input("\n选择测试 (1/2/3/4, 默认 3): ").strip() or "3"
    if sel in tests:
        tests[sel][1]()
