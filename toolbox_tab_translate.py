#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""策划工具箱 - 翻译页签"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json, os, subprocess, sys as _sys, threading, re, shutil, stat, copy
from datetime import datetime
from toolbox_platform import _DropTarget, _check_office_lock
from toolbox_config import CONFIG_FILE, SCRIPT_DIR, MAIN_SCRIPT, DEFAULT_OUTPUT_DIR, load_config, save_config, int_or

class TranslateTabMixin:
    def _tlog(self, msg, level="info"):
        """翻译日志"""
        ts = datetime.now().strftime("%H:%M:%S")
        msg = f"[{ts}] {msg}"
        log_widget = self.tr_log_text
        def _update():
            try:
                if not log_widget.winfo_exists():
                    return
                log_widget.config(state="normal")
                log_widget.insert("end", msg + "\n", level)
                log_widget.see("end")
                log_widget.config(state="disabled")
            except Exception:
                pass
        self.root.after(0, _update)

    def _clear_translate_log(self):
        self.tr_log_text.config(state="normal")
        self.tr_log_text.delete("1.0", "end")
        self.tr_log_text.config(state="disabled")

    def _browse_translate_source(self):
        cur = self.tr_src_var.get().strip()
        initial = os.path.dirname(cur) if (cur and os.path.exists(cur)) else None
        path = filedialog.askopenfilename(
            title="选择需要翻译的表格",
            initialdir=initial,
            filetypes=[("Excel 文件", "*.xlsm *.xlsx"), ("所有文件", "*.*")])
        if path:
            self.tr_src_var.set(path)
            self._save_tr_src_history(path)
            self._on_translate_source_selected()

    def _browse_translate_ref(self):
        cur = self.tr_ref_var.get().strip()
        initial = os.path.dirname(cur) if (cur and os.path.exists(cur)) else None
        path = filedialog.askopenfilename(
            title="选择翻译参考文件",
            initialdir=initial,
            filetypes=[("Excel/文本文件", "*.xlsm *.xlsx *.txt *.csv"), ("所有文件", "*.*")])
        if path:
            self.tr_ref_var.set(path)
            self._save_tr_ref_history(path)

    def _browse_translate_output(self):
        cur = self.tr_out_var.get().strip()
        initial = cur if (cur and os.path.isdir(cur)) else None
        path = filedialog.askdirectory(title="选择输出目录", initialdir=initial)
        if path:
            self.tr_out_var.set(path)
            self.config["tr_out_dir"] = path
            save_config(self.config)

    def _on_tr_src_drop(self, files):
        if files:
            self.tr_src_var.set(files[0])
            self._save_tr_src_history(files[0])
            self._on_translate_source_selected()

    def _on_tr_ref_drop(self, files):
        if files:
            self.tr_ref_var.set(files[0])
            self._save_tr_ref_history(files[0])

    def _save_tr_src_history(self, path):
        history = list(self.config.get("tr_src_history", []))
        if path in history:
            history.remove(path)
        history.insert(0, path)
        self.config["tr_src_history"] = history[:20]
        save_config(self.config)
        self.tr_src_entry["values"] = history[:20]

    def _save_tr_ref_history(self, path):
        history = list(self.config.get("tr_ref_history", []))
        if path in history:
            history.remove(path)
        history.insert(0, path)
        self.config["tr_ref_history"] = history[:20]
        save_config(self.config)
        self.tr_ref_entry["values"] = history[:20]

    def _update_tgt_info(self):
        lang_map = self._load_lang_map()
        names = []
        for h in self.tr_tgt_checked:
            lang = lang_map.get(h.lower()) or lang_map.get(h.lower().strip(":")) or ""
            names.append(f"{lang}({h})" if lang else h)
        if names:
            self.tr_tgt_info_var.set("、".join(names))
        else:
            self.tr_tgt_info_var.set("未选择任何目标语言")

    def _save_tr_lang_config(self):
        self.config["tr_saved_src_lang"] = self.tr_src_lang_var.get()
        self.config["tr_saved_tgt_langs"] = list(self.tr_tgt_checked.keys())
        save_config(self.config)

    def _get_checked_targets(self):
        return [k for k in self.tr_tgt_checked]

    def _on_translate_source_selected(self):
        path = self.tr_src_var.get().strip()
        if path and os.path.isfile(path):
            self._save_tr_src_history(path)
            self._detect_translate_columns()

    def _load_lang_map(self):
        """加载 lang_map.txt，返回 {关键词小写: 语言名}"""
        map_path = os.path.join(SCRIPT_DIR, "lang_map.txt")
        mapping = {}
        if not os.path.isfile(map_path):
            return mapping
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip().lower()
                        val = val.strip()
                        if key and val:
                            mapping[key] = val
        except Exception:
            pass
        return mapping

    def _edit_lang_map(self):
        """用记事本打开映射表，关闭后自动刷新"""
        map_path = os.path.join(SCRIPT_DIR, "lang_map.txt")
        if not os.path.isfile(map_path):
            self._tlog("语言映射文件不存在，创建默认文件", "warn")
            return
        import subprocess
        p = subprocess.Popen(["notepad.exe", map_path])
        def _wait_and_refresh():
            p.wait()
            self.root.after(200, self._detect_translate_columns)
        import threading
        threading.Thread(target=_wait_and_refresh, daemon=True).start()
        self._tlog(f"已打开语言映射文件: {map_path}", "info")

    def _detect_translate_columns(self):
        """读取 Excel 第一行表头，用映射表自动识别语言，填充 UI"""
        path = self.tr_src_var.get().strip()
        if not path or not os.path.isfile(path):
            return
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            ws = wb.active
            headers = []
            for cell in ws[1]:
                if cell.value is not None:
                    h = str(cell.value).strip()
                    if h:
                        headers.append(h)
            wb.close()

            # 加载语言映射表
            lang_map = self._load_lang_map()

            if headers:
                self.tr_src_lang_combo["values"] = headers
                self.tr_tgt_listbox.delete(0, "end")
                self.tr_tgt_checked.clear()
                self.tr_tgt_display.clear()
                self.tr_reverse_display.clear()

                # 识别每个列头的语言
                lang_of_header = {}
                for h in headers:
                    h_lower = h.lower()
                    lang_name = lang_map.get(h_lower)
                    if not lang_name:
                        lang_name = lang_map.get(h_lower.strip(":"))
                    if not lang_name:
                        lang_name = h
                    lang_of_header[h] = lang_name

                # 恢复上次保存的勾选
                saved_src = self.config.get("tr_saved_src_lang", "")
                saved_tgts = self.config.get("tr_saved_tgt_langs", [])

                # 没有已保存设置时自动识别
                auto_src = not saved_src

                for h in headers:
                    lang_name = lang_of_header[h]

                    # 恢复已保存的源语言选择
                    if saved_src and h == saved_src:
                        self.tr_src_lang_var.set(h)

                    # 自动识别源语言（匹配中文类关键词）
                    is_chinese = lang_name == "简体中文" or lang_name == "中文"
                    if auto_src and is_chinese and not self.tr_src_lang_var.get():
                        self.tr_src_lang_var.set(h)

                    # 插入列表
                    if lang_name != h:
                        display = f"  {lang_name} ({h})"
                    else:
                        display = f"  {lang_name}"
                    self.tr_tgt_display[h] = display.strip()
                    self.tr_reverse_display[display.strip()] = h

                    # 恢复勾选
                    checked = h in saved_tgts or h.lower() in [t.lower() for t in saved_tgts]
                    if not checked and not saved_tgts and lang_name != h and not is_chinese:
                        checked = True

                    if checked:
                        self.tr_tgt_listbox.insert("end", f"✓ {display.strip()}")
                        self.tr_tgt_checked[h] = True
                    else:
                        self.tr_tgt_listbox.insert("end", display)

                self._tlog(f"已加载 {len(headers)} 列表头", "info")
                self._update_tgt_info()

        except Exception as e:
            self._tlog(f"读取表头失败: {e}", "error")

    def _run_translate(self):
        """执行翻译主逻辑"""
        src_path = self.tr_src_var.get().strip()
        ref_path = self.tr_ref_var.get().strip()
        api_url = self.tr_api_url_var.get().strip()
        api_key = self.tr_api_key_var.get().strip()
        model = self.tr_model_var.get().strip()
        src_lang = self.tr_src_lang_var.get().strip()
        tgt_langs = self._get_checked_targets()
        out_dir = self.tr_out_var.get().strip()
        prompt_template = self.tr_prompt_var.get().strip()
        try:
            batch_size = int(self.tr_batch_size_var.get().strip())
            if batch_size < 1:
                batch_size = 20
        except ValueError:
            batch_size = 20

        # ── 校验输入 ──
        if not src_path or not os.path.isfile(src_path):
            messagebox.showerror("错误", "请选择有效的翻译表格")
            return
        if not api_key:
            messagebox.showerror("错误", "请输入 API Key")
            return
        if not src_lang:
            messagebox.showerror("错误", "请选择源语言列")
            return
        if not tgt_langs:
            messagebox.showerror("错误", "请在目标语言列中勾选至少一个语言")
            return
        for tl in tgt_langs:
            if tl.lower() == src_lang.lower():
                messagebox.showerror("错误", f"目标语言列「{tl}」与源语言列相同，请取消勾选")
                return

        os.makedirs(out_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(src_path))[0]
        if len(tgt_langs) == 1:
            safe_tgt = tgt_langs[0].strip(":").replace(" ", "_")
            out_name = f"翻译_{base_name}_{safe_tgt}.xlsx"
        else:
            out_name = f"翻译_{base_name}_多语言.xlsx"
        out_path = os.path.join(out_dir, out_name)

        # ── 检查输出文件是否被 Excel 打开 ──
        if os.path.exists(out_path) and _check_office_lock(out_path):
            messagebox.showerror("文件被占用",
                f"输出文件当前被 Excel 打开：\n{out_path}\n\n请先关闭该文件再重新翻译。")
            return

        # ── 保存 API 配置 ──
        self.config["tr_api_url"] = api_url
        self.config["tr_api_key"] = api_key
        self.config["tr_model"] = model
        self.config["tr_out_dir"] = out_dir
        self.config["tr_prompt"] = prompt_template
        self.config["tr_batch_size"] = batch_size
        save_config(self.config)

        self.tr_run_btn.config(state="disabled", text="⏳ 翻译中...")
        self._tlog("=" * 50, "head")
        self._tlog("开始翻译", "head")
        self._tlog(f"源文件: {src_path}", "info")
        self._tlog(f"参考文件: {ref_path if ref_path else '(无)'}", "info")
        self._tlog(f"API: {api_url}", "info")
        self._tlog(f"模型: {model}", "info")
        self._tlog(f"源语言列: {src_lang}", "info")
        self._tlog(f"目标语言列: {', '.join(tgt_langs)}", "info")
        self._tlog(f"输出: {out_path}", "info")

        import openpyxl
        import requests

        def _load_ref_for_target(tgt_lang_name):
            refs = {}
            if not ref_path or not os.path.isfile(ref_path):
                return refs
            ext = os.path.splitext(ref_path)[1].lower()
            try:
                if ext in (".xlsx", ".xlsm"):
                    rwb = openpyxl.load_workbook(ref_path, read_only=True, data_only=True)
                    rws = rwb.active
                    rheaders = [str(c.value).strip() if c.value is not None else "" for c in rws[1]]
                    src_idx = None
                    tgt_idx = None
                    for i, h in enumerate(rheaders):
                        if h and h.lower() == src_lang.lower():
                            src_idx = i
                        if h and h.lower() == tgt_lang_name.lower():
                            tgt_idx = i
                    if src_idx is not None and tgt_idx is not None:
                        for row in rws.iter_rows(min_row=2, values_only=True):
                            if row[src_idx] and row[tgt_idx]:
                                refs[str(row[src_idx]).strip()] = str(row[tgt_idx]).strip()
                    rwb.close()
                    if refs:
                        self._tlog(f"参考 ({tgt_lang_name}): 加载 {len(refs)} 条", "info")
                else:
                    with open(ref_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    refs["__raw_text__"] = content
            except Exception as e:
                self._tlog(f"读取参考文件失败: {e}", "warn")
            return refs

        def _call_api_multitarget(texts, tgt_names, refs_by_target, retries=5):
            """批量翻译多条文本到多个目标语言，返回 [dict{tgt: trans}, ...] 列表"""
            # 清理语言名中的特殊符号（如 ::SC:: → SC），避免模型照搬
            def _clean(name):
                return name.strip(":")
            clean_src = _clean(src_lang)
            clean_tgts = [_clean(t) for t in tgt_names]
            lang_display = "、".join(clean_tgts)

            # system prompt：只放固定角色定义+任务描述（跨批次不变 → 高缓存命中）
            system_prompt = prompt_template.replace("{src_lang}", clean_src).replace("{tgt_lang}", lang_display)

            # 动态内容（参考+文本）全部放入 user message
            user_parts = []

            # 注入参考
            if any(r.get("__raw_text__") for r in refs_by_target.values() if r):
                for tgt in tgt_names:
                    r = refs_by_target.get(tgt, {})
                    if r.get("__raw_text__"):
                        user_parts.append(f"参考内容 ({_clean(tgt)}):\n{r['__raw_text__']}")
            else:
                ref_parts = []
                for tgt in tgt_names:
                    r = refs_by_target.get(tgt, {})
                    if r:
                        sample = list(r.items())[:30]
                        ref_parts.append(f"【{_clean(tgt)}】参考:\n" + "\n".join(f"{k} → {v}" for k, v in sample))
                if ref_parts:
                    user_parts.append("\n".join(ref_parts))

            numbered_lines = []
            for i, t in enumerate(texts, 1):
                clean_t = t.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
                numbered_lines.append(f"{i}|{clean_t}")
            user_parts.append(
                f"请将以下文本从 {clean_src} 一次性翻译为 {lang_display}。"
                f"\n严格按照编号和分隔符格式返回，每行一条："
                f"\n编号|翻译1|翻译2|翻译3..."
                f"\n不要包含任何额外说明、解释或空行。"
                f"\n\n待翻译文本：\n" + "\n".join(numbered_lines)
            )

            user_content = "\n\n".join(user_parts)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 4096 + len(texts) * len(tgt_names) * 200
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            import time as _time
            for attempt in range(retries + 1):
                try:
                    resp = requests.post(api_url, headers=headers,
                                         json=payload, timeout=300)
                    if resp.status_code == 200:
                        data = resp.json()
                        usage = data.get("usage", {})
                        hit = usage.get("prompt_cache_hit_tokens", 0)
                        miss = usage.get("prompt_cache_miss_tokens", 0)
                        total_p = usage.get("prompt_tokens", 0)
                        if total_p > 0:
                            rate = hit / total_p * 100
                            self._tlog(f"缓存命中 {hit}/{total_p} tokens ({rate:.1f}%)")
                        raw = data["choices"][0]["message"]["content"].strip()
                        results = [None] * len(texts)
                        for line in raw.split("\n"):
                            line = line.strip()
                            if not line:
                                continue
                            m = re.match(r"^\s*(\d+)\s*[|.:、]\s*(.*)", line)
                            if m:
                                idx = int(m.group(1)) - 1
                                if 0 <= idx < len(texts):
                                    parts = [p.strip() for p in m.group(2).split("|")]
                                    row_result = {}
                                    for ti, tgt in enumerate(tgt_names):
                                        if ti < len(parts) and parts[ti]:
                                            row_result[tgt] = parts[ti]
                                    results[idx] = row_result
                        return results
                    elif resp.status_code == 429:
                        wait = 5 * (3 ** attempt)
                        self._tlog(f"  触发限流(429)，等待 {wait}s 后重试 ({attempt+1}/{retries+1})", "warn")
                        _time.sleep(wait)
                        continue
                    else:
                        self._tlog(f"API 返回 {resp.status_code}: {resp.text[:200]}", "warn")
                        if attempt < retries:
                            _time.sleep(3)
                            continue
                        return None
                except Exception as e:
                    self._tlog(f"API 调用异常: {e}", "warn")
                    if attempt < retries:
                        _time.sleep(3)
                        continue
                    return None
            return None

        # ── 开始工作 ──
        import time as _thr_time
        def _do_translate():
            nonlocal out_path
            try:
                wb = openpyxl.load_workbook(src_path)
                ws = wb.active

                headers = []
                for cell in ws[1]:
                    h = str(cell.value).strip() if cell.value is not None else ""
                    headers.append(h)

                # 找到源语言列
                src_col = None
                for i, h in enumerate(headers, 1):
                    if h.lower() == src_lang.lower():
                        src_col = i
                        break
                if src_col is None:
                    self._tlog(f"未找到源语言列 '{src_lang}'", "error")
                    return

                # 找到所有已勾选的目标语言列
                tgt_col_map = {}
                for tl in tgt_langs:
                    for i, h in enumerate(headers, 1):
                        if h.lower() == tl.lower():
                            tgt_col_map[tl] = i
                            break
                    if tl not in tgt_col_map:
                        self._tlog(f"未找到目标语言列 '{tl}'，跳过", "warn")

                if not tgt_col_map:
                    self._tlog("未找到任何有效的目标语言列", "error")
                    return

                tgt_names = list(tgt_col_map.keys())
                self._tlog(f"源列: {src_col} | 目标列: {', '.join(f'{k}({v})' for k,v in tgt_col_map.items())}", "info")

                # 预加载所有目标语言的参考
                self._tlog("加载参考文件...", "info")
                all_refs = {}
                has_raw_text = False
                for tgt in tgt_names:
                    all_refs[tgt] = _load_ref_for_target(tgt)
                    if all_refs[tgt].get("__raw_text__"):
                        has_raw_text = True

                # 收集需要翻译的行（跳过已有内容 + 参考匹配）
                batch_items = []
                ref_matched = 0
                for row in ws.iter_rows(min_row=2, values_only=False):
                    src_val = row[src_col - 1].value
                    if src_val is None or not str(src_val).strip():
                        continue
                    src_text = str(src_val).strip()

                    # 检查每个目标列：已有→跳过，有参考→直接填入，否则加入待翻译
                    missing_targets = set()
                    for tgt_name, tgt_col in tgt_col_map.items():
                        tgt_val = row[tgt_col - 1].value
                        if tgt_val and str(tgt_val).strip():
                            continue
                        if not has_raw_text:
                            ref_val = all_refs.get(tgt_name, {}).get(src_text)
                            if ref_val:
                                ws.cell(row=row[0].row, column=tgt_col, value=ref_val)
                                ref_matched += 1
                                continue
                        missing_targets.add(tgt_name)

                    if missing_targets:
                        batch_items.append((row[0].row, src_text, missing_targets))

                self._tlog(f"参考匹配直接填入: {ref_matched} 条", "info")
                self._tlog(f"需要 API 翻译: {len(batch_items)} 条 → {len(tgt_names)} 个语言", "info")

                if not batch_items:
                    self._tlog("无需 API 翻译，全部已处理", "ok")
                    wb.save(out_path)
                    wb.close()
                    self._tlog(f"已保存: {out_path}", "info")
                    try:
                        os.startfile(out_dir)
                    except Exception:
                        pass
                    return

                # 按批次发送（所有目标语言一次完成）
                overall_fail = 0
                for batch_start in range(0, len(batch_items), batch_size):
                    batch = batch_items[batch_start:batch_start + batch_size]
                    texts = [item[1] for item in batch]
                    rows = [item[0] for item in batch]
                    missing_sets = [item[2] for item in batch]

                    batch_num = batch_start // batch_size + 1
                    total_batches = (len(batch_items) + batch_size - 1) // batch_size
                    self._tlog(f"批次 {batch_num}/{total_batches} ({len(texts)} 条 × {len(tgt_names)} 语言)", "info")

                    results = _call_api_multitarget(texts, tgt_names, all_refs)
                    if results is None:
                        self._tlog(f"  批次 {batch_num} 全部失败", "error")
                        for row_num, missing in zip(rows, missing_sets):
                            for tgt_name in missing:
                                ws.cell(row=row_num, column=tgt_col_map[tgt_name], value="【翻译失败】")
                        overall_fail += sum(len(m) for m in missing_sets)
                        _thr_time.sleep(1)
                        continue

                    batch_ok = 0
                    batch_fail = 0
                    for row_num, row_result, missing in zip(rows, results, missing_sets):
                        if row_result is None:
                            for tgt_name in missing:
                                ws.cell(row=row_num, column=tgt_col_map[tgt_name], value="【翻译失败】")
                            batch_fail += len(missing)
                            continue
                        for tgt_name in missing:
                            trans = row_result.get(tgt_name)
                            if trans:
                                ws.cell(row=row_num, column=tgt_col_map[tgt_name], value=trans)
                                batch_ok += 1
                            else:
                                ws.cell(row=row_num, column=tgt_col_map[tgt_name], value="【翻译失败】")
                                batch_fail += 1

                    overall_fail += batch_fail
                    self._tlog(f"  批次 {batch_num} 完成（成功 {batch_ok}/{batch_ok + batch_fail}）", "ok" if batch_fail == 0 else "warn")
                    _thr_time.sleep(0.5)

                # 保存
                wb.save(out_path)
                wb.close()
                self._tlog("=" * 50, "head")
                self._tlog(f"全部翻译完成! 输出文件: {out_path}", "head" if overall_fail == 0 else "warn")
                try:
                    os.startfile(out_dir)
                except Exception:
                    pass

            except Exception as e:
                self._tlog(f"翻译过程出错: {e}", "error")
                import traceback
                self._tlog(traceback.format_exc(), "error")
            finally:
                self.root.after(0, lambda: self.tr_run_btn.config(
                    state="normal", text="▶  开始翻译"))

        import threading as _th
        _th.Thread(target=_do_translate, daemon=True).start()
