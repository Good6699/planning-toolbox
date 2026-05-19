#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SVN 一键对比工具 - GUI 版
模块化版本：各页签拆分为独立 Mixin 类
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
import json, os, subprocess, sys as _sys, threading, re, urllib.parse
from datetime import datetime
import argparse, shutil, stat, copy

from toolbox_platform import _DropTarget, _check_office_lock, _get_svn_path, _get_subprocess_kwargs
from toolbox_config import (
    parser, args, SCRIPT_DIR, MAIN_SCRIPT, CONFIG_FILE, DEFAULT_OUTPUT_DIR,
    load_config, save_config, int_or
)
from toolbox_tab_svn import SvnTabMixin
from toolbox_tab_upload import UploadTabMixin
from toolbox_tab_workflow import WorkflowTabMixin
from toolbox_tab_translate import TranslateTabMixin
from xlsm_zipper import apply_via_excel

class SVNCompareGUI(SvnTabMixin, UploadTabMixin, WorkflowTabMixin, TranslateTabMixin):
    def __init__(self, root):
        self.root = root
        self.root.title("策划工具箱")
        self.root.resizable(True, True)
        self.root.minsize(720, 600)

        self.config = load_config()
        saved_geom = self.config.get("window_geometry", "")
        if saved_geom and self._validate_geometry(saved_geom):
            self.root.geometry(saved_geom)
        else:
            self.root.geometry("776x800+78+78")
        self._ensure_output_dir()

        now = datetime.now()
        self.cur_year = now.year
        self.cur_month = now.month
        self.cur_day = now.day

        self._auto_scroll = True

        self._build_ui()

        self._geom_timer = None
        self.root.bind("<Configure>", self._on_window_configure)

    def _validate_geometry(self, geom):
        """验证保存的窗口位置是否合理（无负尺寸、不过小）"""
        if not geom or "x" not in geom or "+" not in geom:
            return False
        try:
            size_part = geom.split("+")[0]
            w, h = size_part.split("x")
            w, h = int(w), int(h)
            if w < 300 or h < 200:
                return False
            return True
        except (ValueError, IndexError):
            return False

    def _on_window_configure(self, event):
        if event.widget != self.root:
            return
        if self._geom_timer:
            self.root.after_cancel(self._geom_timer)
        self._geom_timer = self.root.after(500, self._save_window_geometry)

    def _save_window_geometry(self):
        try:
            geom = self.root.geometry()
            if geom and self._validate_geometry(geom):
                self.config["window_geometry"] = geom
                save_config(self.config)
                self.config = load_config()
        except Exception:
            pass

    def _ensure_output_dir(self):
        os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)

    def _build_ui(self):
        # ════════════════════════════════════════════════════
        # 标题栏
        # ════════════════════════════════════════════════════
        title_frame = tk.Frame(self.root, bg="#2c3e50", pady=8)
        title_frame.pack(fill="x")
        
        tk.Label(title_frame, text="策划工具箱",
                 font=("微软雅黑", 14, "bold"),
                 fg="white", bg="#2c3e50").pack()
        tk.Label(title_frame, text="策划工具箱  |  修改总结  /  对比 Excel  /  导出文件  /  上传SVN  /  SVN工作流  /  翻译",
                 font=("微软雅黑", 9), fg="#bdc3c7", bg="#2c3e50").pack()

        # ════════════════════════════════════════════════════
        # Notebook 页签
        # ════════════════════════════════════════════════════
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        # ── 页签1: SVN记录 ──
        self.svn_tab = tk.Frame(self.notebook)
        self.notebook.add(self.svn_tab, text="  SVN记录  ")
        self._build_svn_tab()

        # ── 页签2: 上传SVN ──
        self.upload_tab = tk.Frame(self.notebook)
        self.notebook.add(self.upload_tab, text="  上传SVN  ")
        self._build_upload_tab()

        # ── 页签3: SVN工作流 ──
        self.workflow_tab = tk.Frame(self.notebook)
        self.notebook.add(self.workflow_tab, text="  SVN工作流  ")
        self._build_workflow_tab()

        # ── 页签4: 翻译 ──
        self.translate_tab = tk.Frame(self.notebook)
        self.notebook.add(self.translate_tab, text="  翻译  ")
        self._build_translate_tab()

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, event=None):
        tab = self.notebook.select()
        tab_text = self.notebook.tab(tab, "text").strip() if tab else ""
        if tab_text == "上传SVN":
            self._refresh_file_list()
        elif tab_text == "翻译":
            self._on_translate_source_selected()

    def _build_svn_tab(self):
        """构建 SVN记录 页签内容"""
        parent = self.svn_tab

        # ── SVN URL 区 ──
        self._build_url_section(parent)
        self._add_separator(parent)

        # ── 功能模式 ──
        self._build_mode_section(parent)
        self._add_separator(parent)

        # ── 日期范围 ──
        self._build_date_section(parent)
        self._add_separator(parent)

        # ── 过滤条件 ──
        self._build_filter_section(parent)
        self._add_separator(parent)

        # ── 输出设置 ──
        self._build_output_section(parent)
        self._add_separator(parent)

        # ── 执行按钮 ──
        self._build_exec_section(parent)

        # ── 日志区 ──
        self._build_log_section(parent)

        # 启动提示（让用户知道 GUI 已就绪）
        self._log("✅ GUI 已就绪，请输入参数后点击「执行」", "ok")
        self._log(f"📋 工作目录: {SCRIPT_DIR}", "info")
        self._log("─" * 40, "info")

    def _build_upload_tab(self):
        """构建 上传SVN 页签内容"""
        parent = self.upload_tab
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)

        # ── 源目录 ──
        src_frame = tk.Frame(parent)
        src_frame.pack(fill="x", pady=(5, 0))
        src_frame.columnconfigure(1, weight=1)

        tk.Label(src_frame, text="源目录：",
                 font=("微软雅黑", 9)).grid(row=0, column=0, sticky="w", padx=(5, 0))
        self.src_var = tk.StringVar()
        self.src_history = list(self.config.get("src_dir_history", []))
        if self.src_history:
            self.src_var.set(self.src_history[0])
        self.src_entry = ttk.Combobox(src_frame, textvariable=self.src_var,
                                       values=self.src_history,
                                       font=("微软雅黑", 9))
        self.src_entry.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        ttk.Button(src_frame, text="浏览…", command=self._browse_source_dir,
                   width=8).grid(row=0, column=2, padx=(5, 0))
        self.src_entry.bind("<<ComboboxSelected>>", lambda e: self._on_src_selected())
        self.src_entry.bind("<Return>", lambda e: self._on_src_entered())

        # ── 源目录拖拽 ──
        self._src_drop = _DropTarget(self.src_entry, self._on_src_drop)
        self._src_drop.hook()

        # ── 文件列表（Treeview） ──
        tree_frame = tk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, pady=(8, 0))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        columns = ("check", "name", "type", "size", "date")
        self.file_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                       height=10)
        self.file_tree.heading("check", text="✓")
        self.file_tree.heading("name", text="名称")
        self.file_tree.heading("type", text="类型")
        self.file_tree.heading("size", text="大小")
        self.file_tree.heading("date", text="修改日期")

        self.file_tree.column("check", width=35, anchor="center", minwidth=30)
        self.file_tree.column("name", width=250, minwidth=150)
        self.file_tree.column("type", width=70, anchor="center")
        self.file_tree.column("size", width=80, anchor="e")
        self.file_tree.column("date", width=150)

        self.file_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.file_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.file_tree.configure(yscrollcommand=tree_scroll.set)

        self.file_tree.bind("<Button-1>", self._on_tree_click)

        # ── 全选/反选 ──
        sel_frame = tk.Frame(parent)
        sel_frame.pack(fill="x", pady=(4, 0))
        ttk.Button(sel_frame, text="☑ 全选", command=self._select_all_upload,
                   width=10).pack(side="left", padx=(5, 5))
        ttk.Button(sel_frame, text="☐ 取消全选", command=self._deselect_all_upload,
                   width=10).pack(side="left", padx=(0, 5))

        self._checked = {}
        self._items_info = {}

        # ── 目标目录 ──
        tgt_frame = tk.Frame(parent)
        tgt_frame.pack(fill="x", pady=(6, 0))
        tgt_frame.columnconfigure(1, weight=1)

        tk.Label(tgt_frame, text="目标目录：",
                 font=("微软雅黑", 9)).grid(row=0, column=0, sticky="w", padx=(5, 0))
        self.tgt_var = tk.StringVar()
        self.tgt_history = list(self.config.get("tgt_dir_history", []))
        if self.tgt_history:
            self.tgt_var.set(self.tgt_history[0])
        self.tgt_entry = ttk.Combobox(tgt_frame, textvariable=self.tgt_var,
                                       values=self.tgt_history,
                                       font=("微软雅黑", 9))
        self.tgt_entry.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        ttk.Button(tgt_frame, text="浏览…", command=self._browse_target_dir,
                   width=8).grid(row=0, column=2, padx=(5, 0))
        self.tgt_entry.bind("<<ComboboxSelected>>", lambda e: self._on_tgt_selected())
        self.tgt_entry.bind("<Return>", lambda e: self._on_tgt_entered())

        # ── 目标目录拖拽 ──
        self._tgt_drop = _DropTarget(self.tgt_entry, self._on_tgt_drop)
        self._tgt_drop.hook()

        # ── 执行按钮 ──
        exec_frame = tk.Frame(parent)
        exec_frame.pack(fill="x", pady=(8, 0))
        self.upload_run_btn = tk.Button(exec_frame, text="▶  上传SVN",
                                        font=("微软雅黑", 11, "bold"),
                                        bg="#27ae60", fg="white",
                                        activebackground="#2ecc71",
                                        relief="flat", padx=24, pady=6,
                                        cursor="hand2",
                                        command=self._run_upload)
        self.upload_run_btn.pack()

        # ── 日志区 ──
        log_frame = tk.Frame(parent)
        log_frame.pack(fill="both", expand=True, pady=(8, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(1, weight=1)

        log_header = tk.Frame(log_frame)
        log_header.grid(row=0, column=0, sticky="ew")
        log_header.columnconfigure(0, weight=1)
        tk.Label(log_header, text="执行日志",
                 font=("微软雅黑", 9, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Button(log_header, text="清除changelist",
                   command=self._clear_target_changelist, width=14).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(log_header, text="清空",
                   command=self._clear_upload_log, width=5).grid(row=0, column=2, padx=(4, 0))

        self.upload_log_text = tk.Text(log_frame, height=8,
                                       font=("Consolas", 9),
                                       bg="#1e1e1e", fg="#d4d4d4",
                                       insertbackground="white",
                                       state="disabled", wrap="word")
        self.upload_log_text.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

        log_scroll = ttk.Scrollbar(log_frame, orient="vertical",
                                    command=self.upload_log_text.yview)
        log_scroll.grid(row=1, column=1, sticky="ns", pady=(4, 0))
        self.upload_log_text["yscrollcommand"] = log_scroll.set

        self.upload_log_text.tag_config("info",  foreground="#d4d4d4")
        self.upload_log_text.tag_config("ok",    foreground="#4ec9b0")
        self.upload_log_text.tag_config("warn",  foreground="#dcdcaa")
        self.upload_log_text.tag_config("error", foreground="#f44747")
        self.upload_log_text.tag_config("head",  foreground="#569cd6", font=("Consolas", 9, "bold"))

        # 恢复上次路径后自动加载文件列表
        if self.src_history:
            self.root.after(100, self._refresh_file_list)

    def _build_workflow_tab(self):
        parent = self.workflow_tab
        parent.columnconfigure(0, weight=0, minsize=290)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        left = tk.Frame(parent, width=290)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left.grid_propagate(False)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        tk.Label(left, text="工作流列表",
                 font=("微软雅黑", 9, "bold")).grid(row=0, column=0, sticky="w")

        self.wf_tree = ttk.Treeview(left, columns=("name",), show="tree",
                                     selectmode="browse", height=8)
        self.wf_tree.grid(row=1, column=0, sticky="nsew")
        self.wf_tree.column("#0", minwidth=180, stretch=False)

        wf_tree_hbar = ttk.Scrollbar(left, orient="horizontal", command=self.wf_tree.xview)
        wf_tree_hbar.grid(row=2, column=0, sticky="ew")
        self.wf_tree.configure(xscrollcommand=wf_tree_hbar.set)

        wf_btn_frame = tk.Frame(left)
        wf_btn_frame.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(wf_btn_frame, text="+ 新建工作流", command=self._wf_show_create_dialog,
                   width=12).pack(side="left", padx=(0, 4))
        ttk.Button(wf_btn_frame, text="📋 复制", command=self._wf_copy_workflow,
                   width=8).pack(side="left", padx=(0, 4))
        ttk.Button(wf_btn_frame, text="- 删除", command=self._wf_del_workflow,
                   width=6).pack(side="left")

        self.wf_tree.bind("<<TreeviewSelect>>", self._on_wf_tree_select)
        self.wf_tree.bind("<Button-1>", self._wf_tree_drag_start)
        self.wf_tree.bind("<B1-Motion>", self._wf_tree_drag_motion)
        self.wf_tree.bind("<ButtonRelease-1>", self._wf_tree_drag_end)
        self._wf_drag_item = None
        self._wf_drag_parent = None
        self._wf_drag_start_y = 0

        right = tk.Frame(parent)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        self.wf_right = right
        self.wf_detail_frame = tk.Frame(right)
        self.wf_detail_frame.grid(row=0, column=0, sticky="nsew")
        self.wf_detail_frame.columnconfigure(0, weight=1)

        tk.Label(self.wf_detail_frame, text="请从左侧选择一个工作流",
                 font=("微软雅黑", 9), fg="#888").pack(pady=20)

        self._wf_load_workflows()
        self._wf_build_log_area()

    def _get_tortoise_proc_path(self):
        """查找 TortoiseProc.exe"""
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\TortoiseSVN") as key:
                path, _ = winreg.QueryValueEx(key, "ProcPath")
                if path and os.path.exists(path):
                    return path
        except (OSError, FileNotFoundError):
            pass
        candidates = [
            r"C:\Program Files\TortoiseSVN\bin\TortoiseProc.exe",
            r"C:\Program Files (x86)\TortoiseSVN\bin\TortoiseProc.exe",
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return None

    def _add_separator(self, parent):
        """添加分隔线"""
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=8)

    def _log(self, msg, level="info"):
        """添加日志（优化版本，避免频繁的 UI 更新）"""
        ts = datetime.now().strftime("%H:%M:%S")
        msg = f"[{ts}] {msg}"
        def _update_log():
            try:
                if not self.log_text.winfo_exists():
                    return
                self.log_text.config(state="normal")
                self.log_text.insert("end", msg + "\n", level)
                if self._auto_scroll:
                    self.log_text.see("end")
                self.log_text.config(state="disabled")
            except Exception:
                pass
        
        # 使用 after 方法在主线程中异步更新，避免阻塞
        self.root.after(0, _update_log)

    def _build_translate_tab(self):
        """构建 翻译 页签内容"""
        parent = self.translate_tab
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(6, weight=1)

        # ── 输入1: 需要翻译的表格 ──
        src_frame = tk.Frame(parent)
        src_frame.pack(fill="x", pady=(5, 0))
        src_frame.columnconfigure(1, weight=1)

        tk.Label(src_frame, text="翻译表格：",
                 font=("微软雅黑", 9)).grid(row=0, column=0, sticky="w", padx=(5, 0))
        self.tr_src_var = tk.StringVar()
        self.tr_src_history = list(self.config.get("tr_src_history", []))
        if self.tr_src_history:
            self.tr_src_var.set(self.tr_src_history[0])
        self.tr_src_entry = ttk.Combobox(src_frame, textvariable=self.tr_src_var,
                                           values=self.tr_src_history,
                                           font=("微软雅黑", 9))
        self.tr_src_entry.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        ttk.Button(src_frame, text="浏览…", command=self._browse_translate_source,
                   width=8).grid(row=0, column=2, padx=(5, 0))
        self.tr_src_entry.bind("<<ComboboxSelected>>", lambda e: self._on_translate_source_selected())
        self.tr_src_entry.bind("<Return>", lambda e: self._on_translate_source_selected())
        self._tr_src_drop = _DropTarget(self.tr_src_entry, self._on_tr_src_drop)
        self._tr_src_drop.hook()

        # ── 输入2: 翻译参考 ──
        ref_frame = tk.Frame(parent)
        ref_frame.pack(fill="x", pady=(5, 0))
        ref_frame.columnconfigure(1, weight=1)

        tk.Label(ref_frame, text="翻译参考（可选）：",
                 font=("微软雅黑", 9)).grid(row=0, column=0, sticky="w", padx=(5, 0))
        self.tr_ref_var = tk.StringVar()
        self.tr_ref_history = list(self.config.get("tr_ref_history", []))
        if self.tr_ref_history:
            self.tr_ref_var.set(self.tr_ref_history[0])
        self.tr_ref_entry = ttk.Combobox(ref_frame, textvariable=self.tr_ref_var,
                                           values=self.tr_ref_history,
                                           font=("微软雅黑", 9))
        self.tr_ref_entry.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        ttk.Button(ref_frame, text="浏览…", command=self._browse_translate_ref,
                   width=8).grid(row=0, column=2, padx=(5, 0))
        self._tr_ref_drop = _DropTarget(self.tr_ref_entry, self._on_tr_ref_drop)
        self._tr_ref_drop.hook()

        # ── 输入3: API 配置 ──
        api_frame = tk.LabelFrame(parent, text="API 配置", font=("微软雅黑", 9))
        api_frame.pack(fill="x", pady=(8, 0))
        api_frame.columnconfigure(1, weight=1)

        row = 0
        tk.Label(api_frame, text="API 地址：",
                 font=("微软雅黑", 9)).grid(row=row, column=0, sticky="w", padx=(5, 0), pady=2)
        self.tr_api_url_var = tk.StringVar(
            value=self.config.get("tr_api_url", "https://api.openai.com/v1/chat/completions"))
        ttk.Entry(api_frame, textvariable=self.tr_api_url_var,
                  font=("微软雅黑", 9)).grid(row=row, column=1, sticky="ew", padx=(5, 5), pady=2)
        tk.Label(api_frame, text="例: DeepSeek → https://api.deepseek.com/v1/chat/completions",
                 font=("微软雅黑", 7), fg="#888").grid(row=row+1, column=1, sticky="w", padx=(5, 5))

        row += 2
        tk.Label(api_frame, text="API Key：",
                 font=("微软雅黑", 9)).grid(row=row, column=0, sticky="w", padx=(5, 0), pady=2)
        self.tr_api_key_var = tk.StringVar(value=self.config.get("tr_api_key", ""))
        key_entry = ttk.Entry(api_frame, textvariable=self.tr_api_key_var,
                               font=("微软雅黑", 9), show="*")
        key_entry.grid(row=row, column=1, sticky="ew", padx=(5, 5), pady=2)

        row += 1
        tk.Label(api_frame, text="模型：",
                 font=("微软雅黑", 9)).grid(row=row, column=0, sticky="w", padx=(5, 0), pady=2)
        self.tr_model_var = tk.StringVar(
            value=self.config.get("tr_model", "gpt-4o-mini"))
        ttk.Entry(api_frame, textvariable=self.tr_model_var,
                  font=("微软雅黑", 9)).grid(row=row, column=1, sticky="ew", padx=(5, 5), pady=2)

        # ── 语言列设置 ──
        lang_frame = tk.LabelFrame(parent, text="语言列设置", font=("微软雅黑", 9))
        lang_frame.pack(fill="x", pady=(8, 0))
        lang_frame.columnconfigure(1, weight=1)

        tk.Label(lang_frame, text="源语言列：",
                 font=("微软雅黑", 9)).grid(row=0, column=0, sticky="w", padx=(5, 0), pady=2)
        self.tr_src_lang_var = tk.StringVar()
        self.tr_src_lang_combo = ttk.Combobox(lang_frame, textvariable=self.tr_src_lang_var,
                                               font=("微软雅黑", 9), state="readonly")
        self.tr_src_lang_combo.grid(row=0, column=1, sticky="ew", padx=(5, 10), pady=2)
        self.tr_src_lang_combo.bind("<<ComboboxSelected>>", self._on_src_lang_selected)

        ttk.Button(lang_frame, text="刷新列头", command=self._detect_translate_columns,
                   width=8).grid(row=0, column=2, padx=(5, 0), pady=2)
        ttk.Button(lang_frame, text="编辑语言映射", command=self._edit_lang_map,
                   width=10).grid(row=0, column=3, padx=(2, 0), pady=2)
        ttk.Button(lang_frame, text="高级设置", command=self._open_lang_advanced_settings,
                   width=8).grid(row=0, column=4, padx=(2, 5), pady=2)

        ttk.Separator(lang_frame, orient="horizontal").grid(row=1, column=0, columnspan=5, sticky="ew", pady=4)

        tk.Label(lang_frame, text="目标语言列（点击勾选）：",
                 font=("微软雅黑", 9)).grid(row=2, column=0, sticky="nw", padx=(5, 0), pady=2)
        tgt_list_frame = tk.Frame(lang_frame)
        tgt_list_frame.grid(row=2, column=1, columnspan=4, sticky="ew", padx=(5, 5), pady=2)
        tgt_list_frame.columnconfigure(0, weight=1)
        tgt_list_frame.rowconfigure(0, weight=1)

        self.tr_tgt_listbox = tk.Listbox(tgt_list_frame, font=("微软雅黑", 9),
                                          height=5, selectmode="none",
                                          exportselection=False)
        self.tr_tgt_listbox.grid(row=0, column=0, sticky="nsew")
        tgt_scroll = ttk.Scrollbar(tgt_list_frame, orient="vertical",
                                    command=self.tr_tgt_listbox.yview)
        tgt_scroll.grid(row=0, column=1, sticky="ns")
        self.tr_tgt_listbox["yscrollcommand"] = tgt_scroll.set
        self.tr_tgt_listbox.bind("<Button-1>", self._on_tgt_list_click)
        self.tr_tgt_checked = {}
        self.tr_tgt_display = {}
        self.tr_reverse_display = {}

        # ── 已选语言展示 ──
        tk.Label(lang_frame, text="已选中语言：",
                 font=("微软雅黑", 9)).grid(row=3, column=0, sticky="w", padx=(5, 0))
        self.tr_tgt_info_var = tk.StringVar(value="未选择任何目标语言")
        tgt_info_entry = tk.Entry(lang_frame, textvariable=self.tr_tgt_info_var,
                                   font=("微软雅黑", 9), state="readonly",
                                   bg="#fff8dc", relief="solid", bd=1)
        tgt_info_entry.grid(row=3, column=1, columnspan=4, sticky="ew", padx=(5, 5), pady=(0, 2))

        # ── 输出设置 ──
        out_frame = tk.Frame(parent)
        out_frame.pack(fill="x", pady=(8, 0))
        out_frame.columnconfigure(1, weight=1)

        tk.Label(out_frame, text="输出路径：",
                 font=("微软雅黑", 9)).grid(row=0, column=0, sticky="w", padx=(5, 0))
        self.tr_out_var = tk.StringVar(value=self.config.get("tr_out_dir", DEFAULT_OUTPUT_DIR))
        ttk.Entry(out_frame, textvariable=self.tr_out_var,
                  font=("微软雅黑", 9)).grid(row=0, column=1, sticky="ew", padx=(5, 0))
        ttk.Button(out_frame, text="浏览…", command=self._browse_translate_output,
                   width=8).grid(row=0, column=2, padx=(5, 0))

        # ── 提示词（可自定义） ──
        prompt_frame = tk.Frame(parent)
        prompt_frame.pack(fill="x", pady=(5, 0))
        prompt_frame.columnconfigure(1, weight=1)
        tk.Label(prompt_frame, text="提示词：",
                 font=("微软雅黑", 9)).grid(row=0, column=0, sticky="w", padx=(5, 0))
        default_prompt = "你是一个游戏翻译专家。请将以下文本从{src_lang}翻译为{tgt_lang}。只返回翻译结果，不要有任何额外内容。\n如果参考文件中有对应条目，请优先使用参考翻译。\n保留所有特殊格式标记原样不变，例如 <...>、{...}、[...]、<color=...> 等标记保持原封不动，只翻译其中的文本内容。"
        self.tr_prompt_var = tk.StringVar(value=self.config.get("tr_prompt", default_prompt))
        ttk.Entry(prompt_frame, textvariable=self.tr_prompt_var,
                  font=("微软雅黑", 9)).grid(row=0, column=1, sticky="ew", padx=(5, 5))

        # ── 每批条数 ──
        batch_frame = tk.Frame(parent)
        batch_frame.pack(fill="x", pady=(5, 0))
        tk.Label(batch_frame, text="每批条数：",
                 font=("微软雅黑", 9)).pack(side="left", padx=(5, 0))
        self.tr_batch_size_var = tk.StringVar(value=self.config.get("tr_batch_size", "20"))
        ttk.Spinbox(batch_frame, from_=5, to=100, increment=5,
                    textvariable=self.tr_batch_size_var,
                    font=("微软雅黑", 9), width=6).pack(side="left", padx=(5, 5))
        tk.Label(batch_frame, text="（将多条文本一次发送给 API，大幅提升速度）",
                 font=("微软雅黑", 8), fg="#888").pack(side="left")

        # ── 执行按钮 ──
        exec_frame = tk.Frame(parent)
        exec_frame.pack(fill="x", pady=(8, 0))
        self.tr_run_btn = tk.Button(exec_frame, text="▶  开始翻译",
                                     font=("微软雅黑", 11, "bold"),
                                     bg="#27ae60", fg="white",
                                     activebackground="#2ecc71",
                                     relief="flat", padx=24, pady=6,
                                     cursor="hand2",
                                     command=self._run_translate)
        self.tr_run_btn.pack()

        # ── 日志区 ──
        log_frame = tk.Frame(parent)
        log_frame.pack(fill="both", expand=True, pady=(8, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(1, weight=1)

        log_header = tk.Frame(log_frame)
        log_header.grid(row=0, column=0, sticky="ew")
        log_header.columnconfigure(0, weight=1)
        tk.Label(log_header, text="执行日志",
                 font=("微软雅黑", 9, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Button(log_header, text="清空",
                   command=self._clear_translate_log, width=5).grid(row=0, column=1, padx=(8, 0))

        self.tr_log_text = tk.Text(log_frame, height=8,
                                    font=("Consolas", 9),
                                    bg="#1e1e1e", fg="#d4d4d4",
                                    insertbackground="white",
                                    state="disabled", wrap="word")
        self.tr_log_text.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

        log_scroll = ttk.Scrollbar(log_frame, orient="vertical",
                                    command=self.tr_log_text.yview)
        log_scroll.grid(row=1, column=1, sticky="ns", pady=(4, 0))
        self.tr_log_text["yscrollcommand"] = log_scroll.set

        self.tr_log_text.tag_config("info",  foreground="#d4d4d4")
        self.tr_log_text.tag_config("ok",    foreground="#4ec9b0")
        self.tr_log_text.tag_config("warn",  foreground="#dcdcaa")
        self.tr_log_text.tag_config("error", foreground="#f44747")
        self.tr_log_text.tag_config("head",  foreground="#569cd6", font=("Consolas", 9, "bold"))

        # 如果已有默认源文件历史，自动检测列头
        if self.tr_src_history and os.path.isfile(self.tr_src_history[0]):
            self.root.after(200, self._detect_translate_columns)

def main():
    root = tk.Tk()
    app = SVNCompareGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
