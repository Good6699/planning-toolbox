#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""策划工具箱 - SVN记录页签"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json, os, subprocess, sys as _sys, threading, re, shutil, stat, copy
from datetime import datetime
from toolbox_platform import _DropTarget, _check_office_lock, _get_subprocess_kwargs, _get_svn_path
from toolbox_config import CONFIG_FILE, SCRIPT_DIR, MAIN_SCRIPT, DEFAULT_OUTPUT_DIR, load_config, save_config, int_or, args

class SvnTabMixin:
    def _on_wf_tree_select(self, event=None):
        sel = self.wf_tree.selection()
        if not sel:
            return
        iid = sel[0]
        parts = iid.split("_")
        if len(parts) == 2 and parts[0] == "wf":
            wf_idx = int(parts[1])
            self._selected_wf = wf_idx
            self._selected_step = None
            self._wf_show_workflow_detail(wf_idx)
        elif len(parts) == 4 and parts[0] == "wf" and parts[2] == "step":
            wf_idx = int(parts[1])
            step_idx = int(parts[3])
            self._wf_show_step_detail(wf_idx, step_idx)

    def _parse_step_range(self, range_str, total_steps):
        """解析步骤范围字符串如 '1-3,5'，返回 0-based 索引列表。空字符串返回所有步骤。"""
        if not range_str or not range_str.strip():
            return list(range(total_steps))
        indices = set()
        parts = range_str.split(",")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                try:
                    a, b = part.split("-", 1)
                    start = int(a.strip())
                    end = int(b.strip())
                    if start > end:
                        start, end = end, start
                    for i in range(start, end + 1):
                        if 1 <= i <= total_steps:
                            indices.add(i - 1)
                except ValueError:
                    return None
            else:
                try:
                    i = int(part)
                    if 1 <= i <= total_steps:
                        indices.add(i - 1)
                except ValueError:
                    return None
        return sorted(indices)

    def _build_url_section(self, parent):
        """SVN URL 输入区"""
        frame = tk.Frame(parent)
        frame.pack(fill="x")
        
        # 标签行
        tk.Label(frame, text="SVN 仓库 URL", 
                 font=("微软雅黑", 9, "bold"), anchor="w").pack(anchor="w")
        
        # 拖拽提示
        tk.Label(frame, text="💡 可将文件/文件夹拖拽到下方输入框自动识别 SVN 地址",
                 font=("微软雅黑", 8), fg="#7f8c8d", anchor="w").pack(anchor="w", pady=(0,4))
        
        # 输入框行
        url_frame = tk.Frame(frame)
        url_frame.pack(fill="x")
        url_frame.columnconfigure(0, weight=1)
        
        self.url_var = tk.StringVar()
        self._url_list = list(self.config.get("svn_urls", []))
        
        self.url_entry = tk.Entry(url_frame, textvariable=self.url_var,
                                  font=("Consolas", 9), relief="groove")
        self.url_entry.grid(row=0, column=0, sticky="nsew", padx=(0,0), pady=0)
        
        self._dropdown_btn = tk.Button(url_frame, text="▼", width=3,
                                        font=("Consolas", 9), relief="groove",
                                        takefocus=0, pady=0,
                                        command=self._toggle_url_dropdown)
        self._dropdown_btn.grid(row=0, column=1, sticky="nsew")
        
        if self._url_list:
            self.url_var.set(self._url_list[0])
        
        # URL 变化时滚动到末尾
        self.url_var.trace_add("write", self._scroll_url_to_end)
        self.url_entry.after(50, lambda: self.url_entry.xview_moveto(1.0))
        
        # 键盘导航
        self.url_entry.bind("<Up>", self._dropdown_key_up)
        self.url_entry.bind("<Down>", self._dropdown_key_down)
        self.url_entry.bind("<Return>", self._handle_url_return)
        self.url_entry.bind("<Escape>", self._dropdown_key_esc)
        
        # 拖拽绑定（通过 ctypes WndProc 子类化，在主线程消息泵中处理 WM_DROPFILES）
        self._drop_target = _DropTarget(self.url_entry, self._on_file_drop)
        self._drop_target.hook()

    def _build_mode_section(self, parent):
        """功能模式选择"""
        frame = tk.Frame(parent)
        frame.pack(fill="x")
        
        tk.Label(frame, text="功能选择",
                 font=("微软雅黑", 9, "bold"), anchor="w").pack(anchor="w")
        
        mode_frame = tk.Frame(frame)
        mode_frame.pack(anchor="w", padx=(20, 0), pady=(4, 0))
        
        self.mode_var = tk.StringVar(value="compare")
        
        tk.Radiobutton(mode_frame, text="对比 Excel 修改记录",
                       variable=self.mode_var, value="compare",
                       font=("微软雅黑", 9), anchor="w",
                       command=self._on_mode_changed).pack(side="left", padx=(0, 16))
        
        tk.Radiobutton(mode_frame, text="导出 SVN 修改文件",
                       variable=self.mode_var, value="export",
                       font=("微软雅黑", 9), anchor="w",
                       command=self._on_mode_changed).pack(side="left", padx=(0, 16))

        tk.Radiobutton(mode_frame, text="总结SVN修改记录",
                       variable=self.mode_var, value="summary",
                       font=("微软雅黑", 9), anchor="w",
                       command=self._on_mode_changed).pack(side="left")

    def _build_date_section(self, parent):
        """日期范围选择"""
        frame = tk.Frame(parent)
        frame.pack(fill="x")
        
        tk.Label(frame, text="日期范围",
                 font=("微软雅黑", 9, "bold"), anchor="w").pack(anchor="w", pady=(0,4))
        
        date_frame = tk.Frame(frame)
        date_frame.pack(anchor="w")
        
        # 开始日期
        tk.Label(date_frame, text="开始：", font=("微软雅黑", 9)).grid(row=0, column=0, sticky="w")
        self.start_year = self._make_year_combo(date_frame, self.cur_year, col=1)
        tk.Label(date_frame, text="年").grid(row=0, column=2)
        self.start_month = self._make_month_combo(date_frame, 1, col=3)
        tk.Label(date_frame, text="月").grid(row=0, column=4)
        self.start_day = self._make_day_combo(date_frame, 1, col=5)
        tk.Label(date_frame, text="日").grid(row=0, column=6, padx=(0, 20))
        
        # 结束日期
        tk.Label(date_frame, text="结束：", font=("微软雅黑", 9)).grid(row=0, column=7, sticky="w")
        self.end_year = self._make_year_combo(date_frame, self.cur_year, col=8)
        tk.Label(date_frame, text="年").grid(row=0, column=9)
        self.end_month = self._make_month_combo(date_frame, self.cur_month, col=10)
        tk.Label(date_frame, text="月").grid(row=0, column=11)
        self.end_day = self._make_day_combo(date_frame, self.cur_day, col=12)
        tk.Label(date_frame, text="日").grid(row=0, column=13)
        tk.Button(date_frame, text="今日", font=("微软雅黑", 8),
                  bg="#3498db", fg="white", relief="flat", padx=8, cursor="hand2",
                  command=self._set_today_date).grid(row=0, column=14, padx=(10, 0))

    def _set_today_date(self):
        now = datetime.now()
        self.start_year.set(now.year)
        self.start_month.set(now.month)
        self.start_day.set(now.day)
        self.end_year.set(now.year)
        self.end_month.set(now.month)
        self.end_day.set(now.day)

    def _build_filter_section(self, parent):
        """过滤条件"""
        frame = tk.Frame(parent)
        frame.pack(fill="x")
        
        tk.Label(frame, text="过滤条件",
                 font=("微软雅黑", 9, "bold"), anchor="w").pack(anchor="w", pady=(0,4))
        
        # 关键词
        kw_frame = tk.Frame(frame)
        kw_frame.pack(fill="x", pady=(0, 4))
        kw_frame.columnconfigure(1, weight=1)
        
        tk.Label(kw_frame, text="关键词", font=("微软雅黑", 9),
                 width=8, anchor="w").grid(row=0, column=0, sticky="w")
        
        self.keywords_var = tk.StringVar()
        ttk.Entry(kw_frame, textvariable=self.keywords_var,
                  font=("微软雅黑", 9)).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        
        tk.Label(kw_frame, text="（多个空格分隔，留空不过滤）",
                 font=("微软雅黑", 8), fg="#888").grid(row=0, column=2, padx=(6, 0))
        
        # 提交者
        auth_frame = tk.Frame(frame)
        auth_frame.pack(fill="x")
        auth_frame.columnconfigure(1, weight=1)
        
        tk.Label(auth_frame, text="提交者", font=("微软雅黑", 9),
                 width=8, anchor="w").grid(row=0, column=0, sticky="w")
        
        self.author_var = tk.StringVar()
        ttk.Entry(auth_frame, textvariable=self.author_var,
                  font=("微软雅黑", 9)).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        
        tk.Label(auth_frame, text="（留空不限制）",
                 font=("微软雅黑", 8), fg="#888").grid(row=0, column=2, padx=(6, 0))

    def _build_output_section(self, parent):
        """输出设置"""
        frame = tk.Frame(parent)
        frame.pack(fill="x")
        
        tk.Label(frame, text="输出设置",
                 font=("微软雅黑", 9, "bold"), anchor="w").pack(anchor="w", pady=(0, 4))
        
        out_frame = tk.Frame(frame)
        out_frame.pack(fill="x")
        out_frame.columnconfigure(1, weight=1)
        
        self.output_label = tk.Label(out_frame, text="输出目录",
                                     font=("微软雅黑", 9), width=8, anchor="w")
        self.output_label.grid(row=0, column=0, sticky="w")
        
        # 默认输出路径
        self.default_output_path = os.path.join(DEFAULT_OUTPUT_DIR, "Excel")  # 对比模式默认输出到 输出\Excel 目录
        self.default_export_dir = os.path.join(DEFAULT_OUTPUT_DIR, "导出")
        
        self.output_var = tk.StringVar()
        self.output_entry = ttk.Entry(out_frame, textvariable=self.output_var,
                                       font=("微软雅黑", 9))
        self.output_entry.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        
        # 加载上次保存的路径（分模式保存各自的最后路径）
        # 兼容旧配置：首次迁移单一路径 key
        if "output_dir" in self.config and "output_dir_compare" not in self.config:
            self.config["output_dir_compare"] = self.config["output_dir"]
            self.config["output_dir_export"] = self.config["output_dir"]
            del self.config["output_dir"]
        saved_compare = self.config.get("output_dir_compare", "")
        saved_export = self.config.get("output_dir_export", "")
        init_mode = self.mode_var.get()
        init_default = self.default_output_path if init_mode == "compare" else self.default_export_dir
        init_saved = saved_compare if init_mode == "compare" else saved_export
        display_path = init_saved if init_saved and init_saved != init_default else init_default
        self.output_entry.insert(0, display_path)

        def _on_output_focus_out(event):
            """FocusOut 时自动保存当前模式的路径"""
            path = self.output_entry.get().strip()
            mode = self.mode_var.get()
            if mode == "compare":
                self.config["output_dir_compare"] = path
            else:
                self.config["output_dir_export"] = path
            save_config(self.config)

        self.output_entry.bind("<FocusOut>", _on_output_focus_out)

        ttk.Button(out_frame, text="浏览…",
                   command=self._browse_output, width=6).grid(row=0, column=2, padx=(6, 0))
        
        # 高级选项按钮
        ttk.Button(frame, text="⚙ 高级选项",
                   command=self._show_advanced_window, width=12).pack(anchor="w", pady=(10, 0))

    def _build_exec_section(self, parent):
        """执行按钮区"""
        frame = tk.Frame(parent)
        frame.pack(fill="x", pady=(5, 0))

        # 上排：执行按钮（居中）
        self.run_btn = tk.Button(frame, text="▶  执行",
                                 font=("微软雅黑", 11, "bold"),
                                 bg="#27ae60", fg="white",
                                 activebackground="#2ecc71",
                                 relief="flat", padx=24, pady=8,
                                 cursor="hand2",
                                 command=self._run)
        self.run_btn.pack()

    def _build_log_section(self, parent):
        """日志区"""
        frame = tk.Frame(parent)
        frame.pack(fill="both", expand=True, pady=(10, 0))
        
        # 标题行：日志 + 操作按钮
        header_frame = tk.Frame(frame)
        header_frame.pack(fill="x")
        
        tk.Label(header_frame, text="执行日志",
                 font=("微软雅黑", 9, "bold")).pack(side="left")
        
        ttk.Button(header_frame, text="清空",
                   command=self._clear_log, width=5).pack(side="right", padx=(0, 4))
        ttk.Button(header_frame, text="清除缓存",
                   command=self._clear_cache, width=10).pack(side="right")
        
        # 日志文本框
        log_frame = tk.Frame(frame)
        log_frame.pack(fill="both", expand=True, pady=(4, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = tk.Text(log_frame, height=10, width=80,
                                 font=("Consolas", 9),
                                 bg="#1e1e1e", fg="#d4d4d4",
                                 insertbackground="white",
                                 state="disabled", wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")

        # 跟踪用户滚动位置：到底部时恢复自动滚动，离开底部时暂停
        def _on_yscroll(*args):
            scrollbar.set(*args)
            # args = (first, last)，last=1.0 表示滚动条在底部
            if len(args) >= 2 and args[1] == "1.0":
                self._auto_scroll = True
            else:
                self._auto_scroll = False
        self.log_text["yscrollcommand"] = _on_yscroll
        
        # 颜色标签
        self.log_text.tag_config("info",  foreground="#d4d4d4")
        self.log_text.tag_config("ok",    foreground="#4ec9b0")
        self.log_text.tag_config("warn",  foreground="#dcdcaa")
        self.log_text.tag_config("error", foreground="#f44747")
        self.log_text.tag_config("head",  foreground="#569cd6", font=("Consolas", 9, "bold"))

    def _on_mode_changed(self):
        """功能模式切换时，更新输出控件，保留各模式各自的保存路径"""
        mode = self.mode_var.get()
        self.output_label.config(text="输出目录")

        # 总结模式与导出模式使用相同输出路径
        is_export_like = mode in ("export", "summary")
        config_key = "output_dir_export" if is_export_like else "output_dir_compare"
        new_default = self.default_export_dir if is_export_like else self.default_output_path
        saved = self.config.get(config_key, "")
        self.output_entry.delete(0, "end")
        self.output_entry.insert(0, saved if saved else new_default)

    def _make_year_combo(self, parent, default_val, col):
        years = [str(y) for y in range(2020, self.cur_year + 1)]
        var = tk.StringVar(value=str(default_val))
        cb = ttk.Combobox(parent, textvariable=var, values=years,
                           width=6, state="readonly")
        cb.grid(row=0, column=col, padx=(4, 0))
        return var

    def _make_month_combo(self, parent, default_val, col):
        months = [f"{m:02d}" for m in range(1, 13)]
        var = tk.StringVar(value=f"{default_val:02d}")
        cb = ttk.Combobox(parent, textvariable=var, values=months,
                           width=4, state="readonly")
        cb.grid(row=0, column=col, padx=(4, 0))
        return var

    def _make_day_combo(self, parent, default_val, col):
        days = [f"{d:02d}" for d in range(1, 32)]
        var = tk.StringVar(value=f"{default_val:02d}")
        cb = ttk.Combobox(parent, textvariable=var, values=days,
                           width=4, state="readonly")
        cb.grid(row=0, column=col, padx=(4, 0))
        return var

    def _on_file_drop(self, files):
        """拖拽文件/文件夹后，自动识别 SVN URL"""
        if not files:
            return
        path = files[0]
        if isinstance(path, bytes):
            path = path.decode("gbk", errors="replace")
        path = path.strip('"').strip("'")
        # 已通过 ctypes WndProc 子类化在主线程中执行，安全跳转
        self.root.after(0, self._do_detect, path)

    def _do_detect(self, path):
        """在主线程中执行拖拽文件识别"""
        if not os.path.exists(path):
            self._log(f"❌ 路径不存在：{path}", "error")
            return
        
        self._log(f"📂 拖拽识别中：{path}", "info")
        self.root.config(cursor="watch")
        
        def _detect():
            try:
                svn_exe = _get_svn_path()
                check = os.path.abspath(path)
                svn_url = None
                while True:
                    result = subprocess.run(
                        [svn_exe, "info", "--show-item", "url", check],
                        capture_output=True, text=True,
                        encoding="utf-8", errors="replace",
                        timeout=15,
                        **_get_subprocess_kwargs()
                    )
                    url = result.stdout.strip()
                    if url and result.returncode == 0:
                        svn_url = url
                        break
                    parent = os.path.dirname(check)
                    if parent == check:
                        break
                    check = parent
                if not svn_url and os.path.isdir(path):
                    for entry in os.listdir(path):
                        sub = os.path.join(path, entry)
                        if os.path.isdir(os.path.join(sub, ".svn")):
                            result = subprocess.run(
                                [svn_exe, "info", "--show-item", "url", sub],
                                capture_output=True, text=True,
                                encoding="utf-8", errors="replace",
                                timeout=15,
                                **_get_subprocess_kwargs()
                            )
                            url = result.stdout.strip()
                            if url and result.returncode == 0:
                                svn_url = url
                                break
                if not svn_url:
                    self.root.after(0, lambda: messagebox.showwarning(
                        "识别失败", "该文件不是 SVN 版本库中的文件"))
                    return
                from urllib.parse import unquote
                svn_url = unquote(svn_url)
                self.root.after(0, self._set_svn_url, svn_url)
            except FileNotFoundError:
                self.root.after(0, lambda: messagebox.showwarning(
                    "SVN 未安装", "未找到 svn 命令，请确认 SVN 已安装"))
            except subprocess.TimeoutExpired:
                self.root.after(0, self._log,
                    "❌ svn info 超时", "error")
            except Exception as e:
                self.root.after(0, self._log,
                    f"❌ 识别失败：{e}", "error")
            finally:
                self.root.after(0, lambda: self.root.config(cursor=""))
        
        threading.Thread(target=_detect, daemon=True).start()

    def _set_svn_url(self, url):
        """设置 SVN URL 到输入框"""
        self.url_var.set(url)
        self._log(f"✅ 已识别 SVN 地址：{url}", "ok")
        self._save_url_to_history(url)

    def _on_url_selected(self, url):
        """下拉选择后，设置 URL 并置顶"""
        self.url_var.set(url)
        self._close_url_dropdown()
        self._save_url_to_history(url)

    def _scroll_url_to_end(self, *args):
        """URL 变化时滚动到末尾"""
        self.url_entry.after(10, lambda: self.url_entry.xview_moveto(1.0))

    def _save_url_to_history(self, url):
        """将 URL 保存到历史记录（最新置顶，最多20个）"""
        if url in self._url_list:
            self._url_list.remove(url)
        self._url_list.insert(0, url)
        if len(self._url_list) > 20:
            self._url_list = self._url_list[:20]
        self.config["svn_urls"] = self._url_list
        save_config(self.config)
        self.config = load_config()

    def _toggle_url_dropdown(self):
        """切换 URL 下拉弹窗"""
        if hasattr(self, "_dropdown_win") and self._dropdown_win.winfo_exists():
            self._close_url_dropdown()
        else:
            self._show_url_dropdown()

    def _show_url_dropdown(self):
        """显示 URL 下拉弹窗"""
        if not self._url_list:
            return
        
        self._dropdown_win = tk.Toplevel(self.root)
        self._dropdown_win.overrideredirect(True)
        self._dropdown_win.attributes("-topmost", True)
        
        # 计算位置 - 对齐到url_frame右边界
        x = self.url_entry.winfo_rootx()
        y = self.url_entry.winfo_rooty() + self.url_entry.winfo_height()
        # 宽度=输入框宽度 + 按钮宽度
        w = self.url_entry.winfo_width() + self._dropdown_btn.winfo_width()
        self._dropdown_win.geometry(f"{w}x200+{x}+{y}")
        
        # 列表框
        frame = tk.Frame(self._dropdown_win, bd=1, relief="solid")
        frame.pack(fill="both", expand=True)
        
        self._url_listbox = tk.Listbox(frame, font=("Consolas", 9),
                                        selectbackground="#3498db",
                                        activestyle="none",
                                        highlightthickness=0)
        self._url_listbox.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(frame, command=self._url_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self._url_listbox["yscrollcommand"] = scrollbar.set
        
        # 填充 URL
        for url in self._url_list:
            self._url_listbox.insert("end", url)
        
        # 事件绑定
        self._url_listbox.bind("<Button-1>", self._on_listbox_click)
        self._url_listbox.bind("<Return>", self._on_listbox_return)
        self._url_listbox.bind("<Escape>", lambda e: self._close_url_dropdown())
        self._dropdown_win.bind("<FocusOut>", lambda e: self._close_url_dropdown())
        
        self._dropdown_win.focus_set()
        self._url_listbox.selection_set(0)

    def _close_url_dropdown(self):
        """关闭 URL 下拉弹窗"""
        if hasattr(self, "_dropdown_win") and self._dropdown_win.winfo_exists():
            self._dropdown_win.destroy()

    def _on_listbox_click(self, event):
        """点击列表项选择"""
        try:
            idx = self._url_listbox.nearest(event.y)
            if 0 <= idx < len(self._url_list):
                self._on_url_selected(self._url_list[idx])
        except tk.TclError:
            pass

    def _on_listbox_return(self, event):
        """回车选择列表项"""
        try:
            sel = self._url_listbox.curselection()
            if sel:
                self._on_url_selected(self._url_list[sel[0]])
        except tk.TclError:
            pass

    def _dropdown_key_up(self, event):
        """上箭头导航"""
        try:
            if hasattr(self, "_url_listbox") and self._url_listbox.winfo_exists():
                sel = self._url_listbox.curselection()
                if sel and sel[0] > 0:
                    self._url_listbox.selection_clear(sel[0])
                    self._url_listbox.selection_set(sel[0] - 1)
                    self._url_listbox.see(sel[0] - 1)
        except tk.TclError:
            pass

    def _dropdown_key_down(self, event):
        """下箭头导航"""
        try:
            if hasattr(self, "_url_listbox") and self._url_listbox.winfo_exists():
                sel = self._url_listbox.curselection()
                if not sel:
                    self._url_listbox.selection_set(0)
                elif sel[0] < len(self._url_list) - 1:
                    self._url_listbox.selection_clear(sel[0])
                    self._url_listbox.selection_set(sel[0] + 1)
                    self._url_listbox.see(sel[0] + 1)
        except tk.TclError:
            pass

    def _handle_url_return(self, event):
        """URL输入框回车：下拉打开时导航选择，否则只移出焦点（不执行）"""
        if (hasattr(self, "_dropdown_win") and
                self._dropdown_win and
                self._dropdown_win.winfo_exists()):
            self._dropdown_key_enter(event)
        else:
            # 回车只移出焦点，不触发任何执行
            self.url_entry.tk_focusNext().focus()

    def _dropdown_key_enter(self, event):
        """回车确认（下拉打开时导航选择）"""
        try:
            if (hasattr(self, "_url_listbox") and
                self._url_listbox.winfo_exists()):
                sel = self._url_listbox.curselection()
                if sel:
                    self._on_url_selected(self._url_list[sel[0]])
        except tk.TclError:
            pass

    def _dropdown_key_esc(self, event):
        """ESC 关闭"""
        self._close_url_dropdown()

    def _show_advanced_window(self):
        """显示高级选项弹窗"""
        self._modal_win = tk.Toplevel(self.root)
        win = self._modal_win
        win.title("高级选项")
        win.resizable(False, False)
        win.transient(self.root)
        win.withdraw()

        main_frame = tk.Frame(win, padx=20, pady=15)
        main_frame.pack()

        # ── 导出设置 ────────────────────────────────────
        export_frame = tk.LabelFrame(main_frame, text="  导出设置  ",
                                     font=("微软雅黑", 9), padx=12, pady=8)
        export_frame.pack(fill="x", pady=(0, 10))

        tk.Label(export_frame, text="过滤目录：",
                 font=("微软雅黑", 9)).grid(row=0, column=0, sticky="w", pady=3)
        DEFAULT_EXCLUDE = "BinData, GenerateData, Language, gameData"
        saved = self.config.get("exclude_dirs", "").strip()
        display = saved if saved else DEFAULT_EXCLUDE
        exclude_var = tk.StringVar(value=display)
        ttk.Entry(export_frame, textvariable=exclude_var, width=40
                 ).grid(row=0, column=1, sticky="w", padx=(8, 0), pady=3)
        tk.Label(export_frame, text="（逗号分隔，仅导出模式有效）",
                 font=("微软雅黑", 8), fg="#888").grid(
                     row=1, column=1, sticky="w", padx=(8, 0), pady=(0, 2))

        # ── 对比模式 per-file 配置 ──────────────────────
        cmp_frame = tk.LabelFrame(main_frame, text="  对比模式  ",
                                  font=("微软雅黑", 9), padx=12, pady=8)
        cmp_frame.pack(fill="x", pady=(0, 10))
        cmp_frame.columnconfigure(1, weight=1)

        # 文件名行
        tk.Label(cmp_frame, text="文件名：",
                 font=("微软雅黑", 9)).grid(row=0, column=0, sticky="w", pady=3)
        cmp_file_var = tk.StringVar()
        presets = [""] + self.config.get("cmp_file_presets", [])
        cmp_file_cmb = ttk.Combobox(cmp_frame, textvariable=cmp_file_var,
                                    values=presets, width=40, state="normal")
        cmp_file_cmb.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=3)

        # 标题行数
        tk.Label(cmp_frame, text="标题行数：",
                 font=("微软雅黑", 9)).grid(row=1, column=0, sticky="w", pady=3)
        cmp_title_var = tk.StringVar(value=str(self.config.get("cmp_title_rows", "1")))
        ttk.Entry(cmp_frame, textvariable=cmp_title_var, width=40
                 ).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=3)

        # 对比ID列
        tk.Label(cmp_frame, text="对比ID列：",
                 font=("微软雅黑", 9)).grid(row=2, column=0, sticky="w", pady=3)
        cmp_id_var = tk.StringVar(value=self.config.get("cmp_id_col", "::ID::"))
        ttk.Entry(cmp_frame, textvariable=cmp_id_var, width=40
                 ).grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=3)

        # 全局对比ID
        tk.Label(cmp_frame, text="全局对比ID：",
                 font=("微软雅黑", 9)).grid(row=3, column=0, sticky="w", pady=3)
        global_id_var = tk.StringVar(value=self.config.get("cmp_global_id_col", ""))
        ttk.Entry(cmp_frame, textvariable=global_id_var, width=40
                 ).grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=3)
        tk.Label(cmp_frame, text="（留空=自动查找）",
                 font=("微软雅黑", 8), fg="#888").grid(
                     row=4, column=1, sticky="w", padx=(8, 0), pady=(0, 2))

        # 输出列
        tk.Label(cmp_frame, text="输出列：",
                 font=("微软雅黑", 9)).grid(row=5, column=0, sticky="w", pady=3)
        cmp_cols_var = tk.StringVar(value=self.config.get("cmp_output_cols", ""))
        ttk.Entry(cmp_frame, textvariable=cmp_cols_var, width=40
                 ).grid(row=5, column=1, sticky="ew", padx=(8, 0), pady=3)
        tk.Label(cmp_frame, text="（逗号分隔，留空=全部）",
                 font=("微软雅黑", 8), fg="#888").grid(
                     row=6, column=1, sticky="w", padx=(8, 0), pady=(0, 2))

        # ── 切换文件名 → 加载配对字段 ────────────────────
        def _on_cmp_file_changed(*_):
            name = cmp_file_var.get().strip()
            sett = self.config.get("cmp_file_settings", {})
            if name and name in sett:
                vals = sett[name]
            else:
                vals = {
                    "cmp_title_rows": self.config.get("cmp_title_rows", "1"),
                    "cmp_id_col": self.config.get("cmp_id_col", "::ID::"),
                    "cmp_global_id_col": self.config.get("cmp_global_id_col", ""),
                    "cmp_output_cols": self.config.get("cmp_output_cols", "")
                }
            cmp_title_var.set(vals["cmp_title_rows"])
            cmp_id_var.set(vals["cmp_id_col"])
            global_id_var.set(vals.get("cmp_global_id_col", ""))
            cmp_cols_var.set(vals["cmp_output_cols"])
            _update_del_btn_state()

        # ── 预设管理函数 ─────────────────────────────────
        def _save_preset():
            name = cmp_file_var.get().strip()
            title_rows = cmp_title_var.get().strip() or "1"
            id_col = cmp_id_var.get().strip() or "::ID::"
            global_id = global_id_var.get().strip()
            output_cols = cmp_cols_var.get().strip()
            # 写全局
            self.config["cmp_title_rows"] = title_rows
            self.config["cmp_id_col"] = id_col
            self.config["cmp_output_cols"] = output_cols
            # 只有在选择了文件名时，才保存全局对比ID到该文件名的预设
            if name:
                pres = self.config.get("cmp_file_presets", [])
                sett = dict(self.config.get("cmp_file_settings", {}))
                sett[name] = {"cmp_title_rows": title_rows, "cmp_id_col": id_col, "cmp_global_id_col": global_id, "cmp_output_cols": output_cols}
                if name not in pres:
                    pres.insert(0, name)
                self.config["cmp_file_presets"] = pres[:50]
                self.config["cmp_file_settings"] = {k: sett[k] for k in list(sett)[:50]}
                cmp_file_cmb["values"] = [""] + self.config["cmp_file_presets"]
            else:
                # 没有选择文件名时，保存全局对比ID为全局默认值
                self.config["cmp_global_id_col"] = global_id
            save_config(self.config)
            self.config = load_config()
            self._log(f"✅ 已保存预设 [{name}]" if name else "✅ 全局默认值已保存", "ok")
            _update_del_btn_state()

        def _del_preset():
            name = cmp_file_var.get().strip()
            if not name:
                return
            pres = list(self.config.get("cmp_file_presets", []))
            sett = dict(self.config.get("cmp_file_settings", {}))
            if name in pres:
                pres.remove(name)
            if name in sett:
                del sett[name]
            self.config["cmp_file_presets"] = pres
            self.config["cmp_file_settings"] = sett
            cmp_file_cmb["values"] = [""] + pres
            cmp_file_var.set("")
            cmp_title_var.set("1")
            cmp_id_var.set("::ID::")
            global_id_var.set("")
            cmp_cols_var.set("")
            save_config(self.config)
            self.config = load_config()
            self._log(f"🗑 已删除 [{name}]", "warn")
            _update_del_btn_state()

        # 文件名行：按钮装在 column=2 的 sub-frame 里（必须在 _save_preset/_del_preset 定义之后）
        def _update_del_btn_state():
            del_btn.config(state="normal" if cmp_file_var.get().strip() else "disabled")

        btn_cell = tk.Frame(cmp_frame)
        btn_cell.grid(row=0, column=2, sticky="w", padx=(6, 0), pady=3)
        save_btn = ttk.Button(btn_cell, text="√", width=3, command=_save_preset)
        save_btn.pack(side="left", padx=2)
        del_btn = ttk.Button(btn_cell, text="×", width=3, command=_del_preset, state="disabled")
        del_btn.pack(side="left", padx=2)

        cmp_file_cmb.bind("<<ComboboxSelected>>", _on_cmp_file_changed)
        _update_del_btn_state()

        # ── 保存/取消/清理（需要 cmp_frame 内的变量）─────
        def _flash():
            if win.winfo_exists():
                orig = main_frame.cget("bg")
                for _ in range(3):
                    main_frame.config(bg="#fffae6")
                    win.update(); win.after(80)
                    main_frame.config(bg=orig)
                    win.update(); win.after(80)

        def _cleanup():
            self._modal_active = False
            try:
                self.root.unbind("<Button-1>")
            except:
                pass

        def _save():
            exclude_val = exclude_var.get().strip()
            if exclude_val:
                self.config["exclude_dirs"] = exclude_val
            elif "exclude_dirs" in self.config:
                del self.config["exclude_dirs"]
            
            cmp_file = cmp_file_var.get().strip()
            if cmp_file:
                self.config["cmp_file"] = cmp_file
                sett = dict(self.config.get("cmp_file_settings", {}))
                sett[cmp_file] = {
                    "cmp_title_rows": cmp_title_var.get().strip() or "1",
                    "cmp_id_col": cmp_id_var.get().strip() or "::ID::",
                    "cmp_global_id_col": global_id_var.get().strip(),
                    "cmp_output_cols": cmp_cols_var.get().strip()
                }
                self.config["cmp_file_settings"] = sett
            else:
                if "cmp_file" in self.config:
                    del self.config["cmp_file"]
                self.config["cmp_title_rows"] = cmp_title_var.get().strip() or "1"
                self.config["cmp_id_col"] = cmp_id_var.get().strip() or "::ID::"
                self.config["cmp_global_id_col"] = global_id_var.get().strip()
                self.config["cmp_output_cols"] = cmp_cols_var.get().strip()
            save_config(self.config)
            self.config = load_config()
            _cleanup()
            win.destroy()
            self._log("✅ 高级选项已保存", "ok")

        def _cancel():
            _cleanup()
            win.destroy()

        # ── 底部按钮 ─────────────────────────────────────
        btn_frame = tk.Frame(main_frame)
        btn_frame.pack(pady=(5, 0))
        ttk.Button(btn_frame, text="保存", command=_save, width=10).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="取消", command=_cancel, width=10).pack(side="left", padx=8)

        # ── 显示窗口 ─────────────────────────────────────
        win.update()
        w = win.winfo_width()
        h = win.winfo_height()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - h) // 2
        win.geometry(f"+{x}+{y}")
        win.deiconify()
        self._modal_active = True
        self.root.bind("<Button-1>", lambda e: _flash() if self._modal_active else None)
        win.focus_set()
        win.protocol("WM_DELETE_WINDOW", _cancel)
        win.attributes("-topmost", True)
        win.after(100, lambda: win.attributes("-topmost", False))

    def _browse_output(self):
        """浏览输出路径"""
        mode = self.mode_var.get()
        if mode == "compare":
            # 选择目录（输出到指定目录）
            path = filedialog.askdirectory(
                initialdir=self.default_output_path if os.path.exists(self.default_output_path) else DEFAULT_OUTPUT_DIR
            )
        else:
            # 选择目录
            path = filedialog.askdirectory(
                initialdir=DEFAULT_OUTPUT_DIR
            )
        if path:
            self.output_var.set(path)
            self.output_entry.config(foreground="black")

    def _run(self):
        """执行对比/导出"""
        # 获取参数
        svn_url = self.url_var.get().strip()
        if not svn_url:
            messagebox.showerror("错误", "请输入 SVN URL")
            return

        
        mode = self.mode_var.get()

        # 不论是修改现有地址还是全新输入，都作为新记录保存（最新置顶）
        self._save_url_to_history(svn_url)

        start_date = f"{self.start_year.get()}-{int(self.start_month.get()):02d}-{int(self.start_day.get()):02d}"
        end_date = f"{self.end_year.get()}-{int(self.end_month.get()):02d}-{int(self.end_day.get()):02d}"
        keyword = self.keywords_var.get().strip()
        author = self.author_var.get().strip()
        output = self.output_var.get()

        # 使用默认值
        is_export_like = mode in ("export", "summary")
        if output in (self.default_output_path, self.default_export_dir):
            output = self.default_export_dir if is_export_like else self.default_output_path

        # export/summary 模式下自动创建输出目录
        import os
        if is_export_like and output and not os.path.exists(output):
            try:
                os.makedirs(output, exist_ok=True)
                self._log(f"📁 创建输出目录: {output}", "info")
            except Exception as e:
                self._log(f"❌ 创建输出目录失败: {e}", "error")
                messagebox.showerror("错误", f"创建输出目录失败: {e}")
                return

        # 清空输出目录下所有旧文件
        if output and os.path.exists(output):
            try:
                for fname in os.listdir(output):
                    fpath = os.path.join(output, fname)
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                    elif os.path.isdir(fpath):
                        import shutil
                        shutil.rmtree(fpath)
                self._log(f"🗑 已清空输出目录", "info")
            except Exception as e:
                self._log(f"⚠️ 清空输出目录失败: {e}", "warn")

        mode_label = {
            "compare": "对比 Excel 修改记录",
            "export": "导出 SVN 修改文件",
            "summary": "总结SVN修改记录",
        }.get(mode, mode)
        self._log(f"{'='*50}", "head")
        self._log("开始执行", "head")
        self._log(f"模式: {mode_label}", "info")
        self._log(f"SVN URL: {svn_url}", "info")
        self._log(f"日期范围: {start_date} ~ {end_date}", "info")
        if keyword:
            self._log(f"关键词: {keyword}", "info")
        if author:
            self._log(f"提交者: {author}", "info")
        self._log(f"输出目录: {output}", "info")
        
        self.run_btn.config(state="disabled", text="⏳ 执行中...")
        self.root.update()
        
        def _execute():
            try:
                import subprocess
                # 构建命令
                cmd = [
                    _sys.executable, MAIN_SCRIPT,
                    "--url", svn_url,
                    "--start", start_date,
                    "--end", end_date,
                    "--output", output,
                ]
                if mode == "export":
                    cmd.append("--export")
                    cmd.extend(["--export-dir", output])
                    exclude_dirs = self.config.get("exclude_dirs", "").strip()
                    if exclude_dirs:
                        cmd.extend(["--exclude-dirs", exclude_dirs])
                elif mode == "summary":
                    cmd.append("--summary")
                    cmd.extend(["--export-dir", output])
                    exclude_dirs = self.config.get("exclude_dirs", "").strip()
                    if exclude_dirs:
                        cmd.extend(["--exclude-dirs", exclude_dirs])
                if keyword:
                    cmd.extend(["--keyword", keyword])
                if author:
                    cmd.extend(["--author", author])
                
                # 添加全局对比ID参数
                global_id = self.config.get("cmp_global_id_col", "").strip()
                if global_id:
                    cmd.extend(["--global-cmp-id", global_id])
                
                # 添加SVN认证参数
                svn_user = self.config.get("svn_user", "").strip()
                svn_pass = self.config.get("svn_pass", "").strip()
                if svn_user:
                    cmd.extend(["--svn-user", svn_user])
                if svn_pass:
                    cmd.extend(["--svn-pass", svn_pass])
                
                self.root.after(0, lambda: self._log(f"执行命令: {' '.join(cmd)}", "info"))
                
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1,          # 行缓冲，每条 print 立即可读
                    **_get_subprocess_kwargs()
                )

                # 逐行读取并实时输出到日志（非阻塞方式）
                import threading
                def read_output():
                    for raw_line in iter(proc.stdout.readline, ""):
                        if raw_line:
                            line = raw_line.rstrip()
                            # 增强日志分类
                            if "[ERROR]" in line or "[错误]" in line:
                                self.root.after(0, lambda l=line: self._log(l, "error"))
                            elif "[WARNING]" in line or "[警告]" in line:
                                self.root.after(0, lambda l=line: self._log(l, "warn"))
                            elif "条差异 ->" in line:
                                self.root.after(0, lambda l=line: self._log(l, "ok"))
                            else:
                                self.root.after(0, lambda l=line: self._log(l, "info"))
                
                # 启动一个线程读取输出
                output_thread = threading.Thread(target=read_output, daemon=True)
                output_thread.start()
                
                # 等待子进程结束，超时时间设置为600秒（10分钟），以适应大型项目
                try:
                    proc.wait(timeout=600)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                    self.root.after(0, lambda: self._log("❌ 执行超时，已终止（超过10分钟）", "error"))
                    return
                
                # 等待输出线程完成
                output_thread.join(timeout=5)
                
                if proc.returncode == 0:
                    self.root.after(0, lambda: self._log("✅ 执行完成", "ok"))
                    self.root.after(0, lambda: self._ask_open_file(output))
                else:
                    self.root.after(0, lambda: self._log(f"❌ 执行失败，返回码: {proc.returncode}", "error"))
                    self.root.after(0, lambda: messagebox.showerror("执行失败", f"执行失败，返回码: {proc.returncode}\n请查看日志获取详细信息"))
                
            except Exception as e:
                import traceback
                error_msg = f"❌ 执行出错: {e}\n{traceback.format_exc()}"
                self.root.after(0, lambda msg=error_msg: self._log(msg, "error"))
                self.root.after(0, lambda: messagebox.showerror("执行出错", f"执行过程中发生错误: {e}"))
            finally:
                self.root.after(0, lambda: self.run_btn.config(state="normal", text="▶  执行"))
        
        threading.Thread(target=_execute, daemon=True).start()

    def _ask_open_file(self, filepath):
        """自动打开文件所在的目录（无需询问）"""
        if not filepath:
            return
        
        # 直接使用传入的路径作为目标目录，不做任何检测
        target = filepath
        
        # 打开目录（异步执行，避免阻塞主界面）
        def _open_dir():
            try:
                # 直接打开目录，不做任何检查，提高速度
                import os
                os.startfile(target)
                self._log(f"📂 已打开输出目录: {target}", "info")
            except Exception as e:
                self._log(f"⚠️ 打开目录失败: {e}", "error")
        
        # 在新线程中执行，避免阻塞主界面
        import threading
        threading.Thread(target=_open_dir, daemon=True).start()

    def _clear_cache(self):
        """清除 __parse_cache__、__byte_cache__ 和 __ss_cache__ 目录，立即生效"""
        total = 0
        for sub in ("__parse_cache", "__byte_cache", "__ss_cache"):
            cache_dir = os.path.join(SCRIPT_DIR, sub)
            if not os.path.exists(cache_dir):
                continue
            try:
                for fname in os.listdir(cache_dir):
                    fpath = os.path.join(cache_dir, fname)
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                        total += 1
            except Exception as e:
                self._log(f"⚠️ 清理 {sub} 失败: {e}", "error")
                return
        if total == 0:
            self._log("🗑 缓存目录不存在，无需清理", "info")
        else:
            self._log(f"🗑 缓存已清除，删除 {total} 个缓存文件", "ok")

    def _clear_log(self):
        """清空日志"""
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _merge_sheet_changes(self, inp_ws, tgt_ws, data_start_row, data_end_row, title_rows, id_col_num):
        """分析单 sheet 的数据变化，返回变更操作列表（不实际修改目标表）。

        返回 (added_count, updated_count, ops)
        ops = {"updates": [(row, col, value), ...],
               "inserts": [{"after_row": int, "col_data": {col: val, ...}, "has_end": bool}, ...]}
        """
        header_row = title_rows
        tgt_id_col = id_col_num

        if tgt_id_col > tgt_ws.max_column:
            return (0, 0, {"updates": [], "inserts": []})

        tgt_id_header = str(tgt_ws.cell(row=header_row, column=tgt_id_col).value or "").strip()
        if not tgt_id_header:
            return (0, 0, {"updates": [], "inserts": []})

        inp_id_col = None
        for col in range(1, inp_ws.max_column + 1):
            h = inp_ws.cell(row=header_row, column=col).value
            if h and str(h).strip() == tgt_id_header:
                inp_id_col = col
                break
        if inp_id_col is None:
            return (0, 0, {"updates": [], "inserts": []})

        tgt_id_map = {}
        for row in range(title_rows + 1, tgt_ws.max_row + 1):
            val = tgt_ws.cell(row=row, column=tgt_id_col).value
            if val is not None:
                key = str(val).strip()
                if key:
                    tgt_id_map[key] = row

        last_continuous_id_row = title_rows
        for row in range(title_rows + 1, tgt_ws.max_row + 1):
            val = tgt_ws.cell(row=row, column=tgt_id_col).value
            if val is not None and str(val).strip():
                last_continuous_id_row = row
            else:
                break

        updates = []
        inserts = []
        added = 0
        updated = 0

        has_end = False
        end_row_at = None
        if last_continuous_id_row >= title_rows + 1:
            for row in range(last_continuous_id_row, tgt_ws.max_row + 1):
                val = tgt_ws.cell(row=row, column=1).value
                if val is not None and str(val).strip().lower() == "end":
                    has_end = True
                    end_row_at = row
                    break

        for row in range(data_start_row, data_end_row + 1):
            inp_id_val = inp_ws.cell(row=row, column=inp_id_col).value
            if inp_id_val is None:
                continue
            inp_id_key = str(inp_id_val).strip()
            if not inp_id_key:
                continue

            row_data = {}
            inp_hdr_count = {}
            for col in range(2, inp_ws.max_column + 1):
                h = inp_ws.cell(row=header_row, column=col).value
                if h is not None:
                    h_str = str(h).strip()
                    occ = inp_hdr_count.get(h_str, 0)
                    inp_hdr_count[h_str] = occ + 1
                    val = inp_ws.cell(row=row, column=col).value
                    row_data[(h_str, occ)] = val

            if inp_id_key in tgt_id_map:
                tgt_row = tgt_id_map[inp_id_key]
                tgt_hdr_count = {}
                for col in range(1, tgt_ws.max_column + 1):
                    h = tgt_ws.cell(row=header_row, column=col).value
                    if h is not None:
                        h_str = str(h).strip()
                        occ = tgt_hdr_count.get(h_str, 0)
                        tgt_hdr_count[h_str] = occ + 1
                        if h_str != tgt_id_header:
                            if col == 1:
                                continue
                            key = (h_str, occ)
                            if key in row_data:
                                updates.append((tgt_row, col, row_data[key]))
                updated += 1
            else:
                col_data = {}
                ins_hdr_count = {}
                for col in range(1, tgt_ws.max_column + 1):
                    h = tgt_ws.cell(row=header_row, column=col).value
                    if h is not None:
                        h_str = str(h).strip()
                        occ = ins_hdr_count.get(h_str, 0)
                        ins_hdr_count[h_str] = occ + 1
                        if col == 1:
                            continue
                        key = (h_str, occ)
                        if key in row_data:
                            col_data[col] = row_data[key]

                if not has_end:
                    col_data[1] = inp_id_key

                if has_end:
                    after_row = end_row_at
                else:
                    after_row = last_continuous_id_row

                inserts.append({
                    "after_row": after_row,
                    "col_data": col_data,
                })

                new_row = after_row + 1
                last_continuous_id_row = new_row
                tgt_id_map[inp_id_key] = new_row
                added += 1

        if has_end and inserts:
            updates.append((end_row_at, 1, "0"))
            for ins in inserts:
                ins["col_data"][1] = "0"
            inserts[-1]["col_data"][1] = "END"

        return (added, updated, {"updates": updates, "inserts": inserts})
