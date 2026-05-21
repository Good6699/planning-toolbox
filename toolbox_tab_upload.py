#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""策划工具箱 - 上传SVN页签"""
from tkinter import filedialog, messagebox
import os
import subprocess
import threading
import shutil
import stat
from datetime import datetime
from toolbox_platform import _get_subprocess_kwargs, _get_svn_path
from toolbox_config import load_config, save_config


class UploadTabMixin:
    def _clear_upload_log(self):
        """清空上传日志"""
        self.upload_log_text.config(state="normal")
        self.upload_log_text.delete("1.0", "end")
        self.upload_log_text.config(state="disabled")

    def _clear_target_changelist(self):
        """清除目标目录的 '本次修改' changelist"""
        tgt = self.tgt_var.get().strip()
        if not tgt or not os.path.isdir(tgt):
            messagebox.showwarning("提示", "请先选择目标目录")
            return
        self._ulog("🧹 正在清除目标目录的 changelist...", "info")
        threading.Thread(target=self._do_clear_target_changelist, args=(tgt,), daemon=True).start()

    def _do_clear_target_changelist(self, tgt):
        try:
            svn_exe = _get_svn_path()
            r = subprocess.run(
                [svn_exe, "changelist", "--remove", "--changelist", "本次修改", tgt, "--depth", "infinity"],
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=60,
                **_get_subprocess_kwargs()
            )
            if r.returncode == 0:
                self._ulog("✅ 目标目录 changelist \"本次修改\" 已清除", "ok")
            else:
                err = r.stderr.strip()
                self._ulog(f"⚠️ 清除失败: {err}", "warn")
        except FileNotFoundError:
            self._ulog("⚠️ 未找到 svn 命令", "warn")
        except Exception as e:
            self._ulog(f"❌ 清除异常: {e}", "error")

    def _browse_source_dir(self):
        cur = self.src_var.get().strip()
        initial = cur if (cur and os.path.isdir(cur)) else (os.path.dirname(cur) if cur else None)
        path = filedialog.askdirectory(title="选择源目录", initialdir=initial)
        if path:
            self.src_var.set(path)
            self._save_src_history(path)
            self._refresh_file_list()

    def _browse_target_dir(self):
        cur = self.tgt_var.get().strip()
        initial = cur if (cur and os.path.isdir(cur)) else (os.path.dirname(cur) if cur else None)
        path = filedialog.askdirectory(title="选择目标目录", initialdir=initial)
        if path:
            self.tgt_var.set(path)
            self._save_tgt_history(path)

    def _on_src_drop(self, files):
        if files:
            path = files[0].strip('"').strip("'")
            if os.path.isdir(path):
                self.src_var.set(path)
                self._save_src_history(path)
                self._refresh_file_list()

    def _on_tgt_drop(self, files):
        if files:
            path = files[0].strip('"').strip("'")
            if os.path.isdir(path):
                self.tgt_var.set(path)
                self._save_tgt_history(path)

    def _on_src_selected(self):
        path = self.src_var.get().strip()
        if path:
            self._save_src_history(path)
            self._refresh_file_list()

    def _on_src_entered(self):
        path = self.src_var.get().strip()
        if path and os.path.isdir(path):
            self._save_src_history(path)
            self._refresh_file_list()

    def _on_tgt_selected(self):
        path = self.tgt_var.get().strip()
        if path:
            self._save_tgt_history(path)

    def _on_tgt_entered(self):
        path = self.tgt_var.get().strip()
        if path and os.path.isdir(path):
            self._save_tgt_history(path)

    def _save_src_history(self, path):
        if path in self.src_history:
            self.src_history.remove(path)
        self.src_history.insert(0, path)
        if len(self.src_history) > 20:
            self.src_history = self.src_history[:20]
        self.src_entry["values"] = self.src_history
        self.config["src_dir_history"] = self.src_history
        save_config(self.config)
        self.config = load_config()

    def _save_tgt_history(self, path):
        if path in self.tgt_history:
            self.tgt_history.remove(path)
        self.tgt_history.insert(0, path)
        if len(self.tgt_history) > 20:
            self.tgt_history = self.tgt_history[:20]
        self.tgt_entry["values"] = self.tgt_history
        self.config["tgt_dir_history"] = self.tgt_history
        save_config(self.config)
        self.config = load_config()

    @staticmethod
    def _build_file_info(full_path):
        try:
            st = os.stat(full_path)
            is_dir = os.path.isdir(full_path)
            ftype = "文件夹" if is_dir else "文件"
            if is_dir:
                total = 0
                for r, _, fs in os.walk(full_path):
                    for f in fs:
                        try:
                            total += os.path.getsize(os.path.join(r, f))
                        except Exception:
                            pass
                size = total
            else:
                size = st.st_size
            if size >= 1024 * 1024:
                size_str = f"{size / 1024 / 1024:.1f} MB"
            elif size >= 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size} B"
            mtime = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
        except Exception:
            ftype = "文件夹" if os.path.isdir(full_path) else "文件"
            size_str = "-"
            mtime = "-"
        return ftype, size_str, mtime

    def _refresh_file_list(self):
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        self._checked.clear()
        self._items_info.clear()

        src = self.src_var.get().strip()
        if not src or not os.path.isdir(src):
            return

        try:
            entries = sorted(os.listdir(src), key=lambda x: (not os.path.isdir(os.path.join(src, x)), x.lower()))
        except Exception as e:
            self._ulog(f"❌ 读取目录失败: {e}", "error")
            return

        for name in entries:
            full_path = os.path.join(src, name)
            ftype, size_str, mtime = self._build_file_info(full_path)
            item_id = self.file_tree.insert("", "end", values=(
                "☐", name, ftype, size_str, mtime
            ))
            self._checked[item_id] = False
            self._items_info[item_id] = {
                "path": full_path,
                "name": name,
                "is_dir": os.path.isdir(full_path)
            }

        if not hasattr(self, "_last_logged_src"):
            self._last_logged_src = ""
        if src != self._last_logged_src:
            self._ulog(f"📂 源目录: {src}  —  共 {len(entries)} 项", "info")
            self._last_logged_src = src

    def _on_tree_click(self, event):
        item = self.file_tree.identify_row(event.y)
        if item:
            checked = not self._checked.get(item, False)
            self._checked[item] = checked
            self.file_tree.set(item, "check", "☑" if checked else "☐")

    def _select_all_upload(self):
        for item in self.file_tree.get_children():
            self._checked[item] = True
            self.file_tree.set(item, "check", "☑")

    def _deselect_all_upload(self):
        for item in self.file_tree.get_children():
            self._checked[item] = False
            self.file_tree.set(item, "check", "☐")

    def _find_folder_in_target(self, target_root, folder_name):
        """在 target_root 下递归搜索同名文件夹"""
        direct = os.path.join(target_root, folder_name)
        if os.path.isdir(direct):
            return direct
        for root, dirs, _ in os.walk(target_root):
            for d in dirs:
                if d == folder_name:
                    return os.path.join(root, d)
        return None

    def _copy2_force(self, src, dst):
        """copy2 前确保目标文件可写，避免 .meta 等只读/锁定文件覆盖失败"""
        if os.path.exists(dst):
            try:
                os.chmod(dst, stat.S_IWRITE | stat.S_IREAD)
            except Exception:
                pass
        try:
            shutil.copy2(src, dst)
        except PermissionError:
            # 文件可能被其他进程锁定，删除后重新复制
            try:
                os.remove(dst)
            except Exception:
                pass
            shutil.copy2(src, dst)

    @staticmethod
    def _collect_copied(src_root, dest_root):
        out = []
        for r, _, fs in os.walk(src_root):
            rel = os.path.relpath(r, src_root)
            for f in fs:
                out.append(os.path.join(dest_root, rel, f))
        return out

    def _copy_checked_item(self, iid, info, tgt, copied_files):
        name = info["name"]
        src_path = info["path"]
        is_dir = info["is_dir"]
        if is_dir:
            matched = self._find_folder_in_target(tgt, name)
            if matched:
                self._ulog(f"📂 找到同名文件夹 [{name}] → {matched}", "info")
                for item in os.listdir(src_path):
                    s = os.path.join(src_path, item)
                    d = os.path.join(matched, item)
                    if os.path.isdir(s):
                        if os.path.exists(d):
                            shutil.copytree(s, d, dirs_exist_ok=True, copy_function=self._copy2_force)
                        else:
                            shutil.copytree(s, d, copy_function=self._copy2_force)
                        copied_files.extend(self._collect_copied(s, d))
                    else:
                        self._copy2_force(s, d)
                        copied_files.append(d)
                self._ulog(f"   ✅ 文件夹内容已合并到 [{matched}]", "ok")
            else:
                dest = os.path.join(tgt, name)
                if os.path.exists(dest):
                    shutil.copytree(src_path, dest, dirs_exist_ok=True, copy_function=self._copy2_force)
                else:
                    shutil.copytree(src_path, dest, copy_function=self._copy2_force)
                copied_files.extend(self._collect_copied(src_path, dest))
                self._ulog(f"   ✅ 文件夹 [{name}] 已复制到目标根目录", "ok")
        else:
            dest = os.path.join(tgt, name)
            self._copy2_force(src_path, dest)
            copied_files.append(dest)
            self._ulog(f"   ✅ 文件 [{name}] 已复制到目标根目录", "ok")

    def _upload_do_copy(self, checked_items, src, tgt):
        success = 0
        fail = 0
        copied_files = []
        for iid, info in checked_items:
            try:
                self._copy_checked_item(iid, info, tgt, copied_files)
                success += 1
            except Exception as e:
                self._ulog(f"   ❌ [{info['name']}] 复制失败: {e}", "error")
                fail += 1

        self._ulog("─" * 40, "head")
        if fail == 0:
            self._ulog(f"✅ 文件复制完成：成功 {success} 项", "ok")
        else:
            self._ulog(f"⚠️ 文件复制完成：成功 {success} 项，失败 {fail} 项", "warn")

        self.root.after(0, lambda: self._check_svn_and_confirm(tgt, copied_files))

    def _run_upload(self):
        src = self.src_var.get().strip()
        tgt = self.tgt_var.get().strip()

        if not src or not os.path.isdir(src):
            messagebox.showerror("错误", "请选择有效的源目录")
            return
        if not tgt or not os.path.isdir(tgt):
            messagebox.showerror("错误", "请选择有效的目标目录")
            return

        checked_items = [(iid, info) for iid, info in self._items_info.items()
                         if self._checked.get(iid, False)]
        if not checked_items:
            messagebox.showwarning("提示", "请先勾选要上传的文件或文件夹")
            return

        self.upload_run_btn.config(state="disabled", text="⏳ 上传中...")
        self._ulog("=" * 50, "head")
        self._ulog("开始上传", "head")
        self._ulog(f"源目录: {src}", "info")
        self._ulog(f"目标目录: {tgt}", "info")

        import threading as _th
        _th.Thread(target=self._upload_do_copy, args=(checked_items, src, tgt), daemon=True).start()

    def _svn_get_info(self, target_dir):
        svn_exe = _get_svn_path()
        result = subprocess.run(
            [svn_exe, "info", target_dir],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=15, **_get_subprocess_kwargs()
        )
        if result.returncode != 0:
            self._ulog(f"⚠️ 目标目录 [{target_dir}] 没有找到SVN链接，跳过SVN上传", "warn")
            self.root.after(0, lambda: self.upload_run_btn.config(state="normal", text="▶  上传SVN"))
            return None, None
        svn_url = ""
        for line in result.stdout.splitlines():
            if line.startswith("URL: "):
                svn_url = line[5:]
                break
        wc_r = subprocess.run(
            [svn_exe, "info", "--show-item", "wc-root", target_dir],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=15, **_get_subprocess_kwargs()
        )
        wc_root = wc_r.stdout.strip() if wc_r.returncode == 0 else ""
        return svn_url, wc_root

    def _svn_log_paths(self, copied_files, svn_url, wc_root):
        if not copied_files or not svn_url or not wc_root:
            return
        self._ulog("   📄 上传文件 SVN 路径:", "info")
        for f in copied_files:
            rel = os.path.relpath(f, wc_root).replace("\\", "/")
            self._ulog(f"       {svn_url}/{rel}", "info")

    def _svn_clean_stale_adds(self, wc_root, copied_files):
        svn_exe = _get_svn_path()
        try:
            r_status = subprocess.run(
                [svn_exe, "status", "--no-ignore", wc_root],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30, **_get_subprocess_kwargs()
            )
            if r_status.returncode != 0:
                return
            copied_abs = {os.path.abspath(f) for f in copied_files}
            revert_list = []
            for line in r_status.stdout.splitlines():
                if len(line) > 7 and line[0] == "A" and line[1] == " ":
                    status_path = line[7:].strip()
                    if not os.path.isabs(status_path):
                        status_path = os.path.join(wc_root, status_path)
                    status_path = os.path.abspath(status_path)
                    if status_path not in copied_abs:
                        revert_list.append(status_path)
            if not revert_list:
                return
            for rf in revert_list:
                subprocess.run(
                    [svn_exe, "revert", rf],
                    capture_output=True, text=True, timeout=10, **_get_subprocess_kwargs()
                )
            self._ulog(f"   🧹 已清理 {len(revert_list)} 个未提交的 add 记录", "info")
        except Exception:
            pass

    def _svn_add_files(self, copied_files):
        svn_exe = _get_svn_path()
        add_ok = 0
        for f in copied_files:
            try:
                r = subprocess.run(
                    [svn_exe, "add", "--parents", "--force", "--quiet", os.path.abspath(f)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=30, **_get_subprocess_kwargs()
                )
                if r.returncode == 0:
                    add_ok += 1
            except Exception:
                pass
        self._ulog(f"   ✅ {add_ok}/{len(copied_files)} 个文件已添加到SVN版本控制", "ok")
        return add_ok

    def _svn_build_modified_list(self, wc_root, copied_files):
        svn_exe = _get_svn_path()
        to_add = []
        to_commit = []
        changed_flags = {'M', 'A', 'R', '!', '?'}
        try:
            r_st = subprocess.run(
                [svn_exe, "status", wc_root],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30, **_get_subprocess_kwargs()
            )
            if r_st.returncode == 0:
                copied_abs = {os.path.abspath(f) for f in copied_files}
                for line in r_st.stdout.splitlines():
                    if not line or len(line) < 2:
                        continue
                    flag = line[0]
                    if flag not in changed_flags:
                        continue
                    status_path = line[7:].strip() if len(line) > 7 else ""
                    if not status_path:
                        continue
                    if not os.path.isabs(status_path):
                        status_path = os.path.join(wc_root, status_path)
                    status_path = os.path.abspath(status_path)
                    if status_path in copied_abs:
                        if flag in ('A', '?', '!'):
                            to_add.append(status_path)
                        else:
                            to_commit.append(status_path)
        except Exception:
            pass
        return to_add, to_commit

    def _svn_clean_stale_changelist(self, wc_root, modified_files):
        svn_exe = _get_svn_path()
        try:
            r_cl = subprocess.run(
                [svn_exe, "status", "--changelist", "本次修改", wc_root],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30, **_get_subprocess_kwargs()
            )
            if r_cl.returncode != 0:
                return
            modified_now = set(modified_files)
            cl_clean = []
            changed_flags = {'M', 'A', 'R', '!', '?'}
            for line in r_cl.stdout.splitlines():
                if not line or len(line) < 2:
                    continue
                flag = line[0]
                status_path = line[7:].strip() if len(line) > 7 else ""
                if not status_path:
                    continue
                if not os.path.isabs(status_path):
                    status_path = os.path.join(wc_root, status_path)
                status_path = os.path.abspath(status_path)
                if flag not in changed_flags or status_path not in modified_now:
                    cl_clean.append(status_path)
            if not cl_clean:
                return
            for cf in cl_clean:
                subprocess.run(
                    [svn_exe, "changelist", "--remove", cf],
                    capture_output=True, text=True, timeout=10, **_get_subprocess_kwargs()
                )
            self._ulog(f"   🧹 已从changelist清理 {len(cl_clean)} 个文件", "info")
        except Exception:
            pass

    def _svn_set_changelist(self, modified_files):
        svn_exe = _get_svn_path()
        cl_ok = 0
        for f in modified_files:
            try:
                r = subprocess.run(
                    [svn_exe, "changelist", "本次修改", os.path.abspath(f)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=30, **_get_subprocess_kwargs()
                )
                if r.returncode == 0:
                    cl_ok += 1
            except Exception:
                pass
        self._ulog(f"   🏷️ {cl_ok}/{len(modified_files)} 个文件已标记 changelist", "ok")

    def _svn_do_update(self, wc_root):
        svn_exe = _get_svn_path()
        try:
            r = subprocess.run(
                [svn_exe, "update", "--accept", "theirs-full", wc_root],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=120, **_get_subprocess_kwargs()
            )
            if r.returncode == 0:
                for line in r.stdout.strip().splitlines():
                    line = line.strip()
                    if line:
                        self._ulog("  " + line, "info")
                self._ulog("SVN 更新完成", "ok")
            else:
                self._ulog("SVN 更新失败: " + r.stderr.strip(), "warn")
        except subprocess.TimeoutExpired:
            self._ulog("SVN 更新超时（超过2分钟）", "warn")
        except Exception as e:
            self._ulog("SVN 更新异常: " + str(e), "warn")

    def _svn_scan(self, target_dir, copied_files):
        try:
            svn_url, wc_root = self._svn_get_info(target_dir)
            if svn_url is None:
                return
            self._ulog(f"   ✅ SVN 链接验证通过，即将提交 {len(copied_files)} 个文件", "ok")
            self._svn_log_paths(copied_files, svn_url, wc_root)
            self._svn_clean_stale_adds(wc_root, copied_files)
            self._svn_add_files(copied_files)
            to_add, to_commit = self._svn_build_modified_list(wc_root, copied_files)
            modified_files = to_add + to_commit
            self._svn_clean_stale_changelist(wc_root, modified_files)
            if not modified_files:
                self._ulog("⚠️ 没有文件实际发生变化，跳过SVN上传", "warn")
                self.root.after(0, lambda: self.upload_run_btn.config(state="normal", text="▶  上传SVN"))
                return
            self._svn_set_changelist(modified_files)
            self._svn_do_update(wc_root)
            tortoise = self._get_tortoise_proc_path()
            if tortoise:
                self._ulog(f"🖥️ 正在打开 TortoiseSVN 提交对话框 ({len(modified_files)} 个文件)...", "info")
                self.root.after(0, lambda: self._launch_tortoise_commit(tortoise, wc_root, modified_files))
            else:
                self._ulog("⚠️ 未找到 TortoiseSVN，SVN 上传需要安装 TortoiseSVN", "warn")
                self.root.after(0, lambda: self.upload_run_btn.config(state="normal", text="▶  上传SVN"))
        except FileNotFoundError:
            self._ulog("⚠️ 未找到 svn 命令，请确认 SVN 已安装", "warn")
            self.root.after(0, lambda: self.upload_run_btn.config(state="normal", text="▶  上传SVN"))
        except Exception as e:
            self._ulog(f"❌ SVN检查异常: {e}", "error")
            self.root.after(0, lambda: self.upload_run_btn.config(state="normal", text="▶  上传SVN"))

    def _check_svn_and_confirm(self, target_dir, copied_files):
        if not copied_files:
            self._ulog("⚠️ 没有复制的文件，跳过SVN上传", "warn")
            self.upload_run_btn.config(state="normal", text="▶  上传SVN")
            return
        self._ulog(f"🔍 正在检查 {len(copied_files)} 个复制文件的SVN状态...", "info")
        import threading as _th
        _th.Thread(target=self._svn_scan, args=(target_dir, copied_files), daemon=True).start()

    def _launch_tortoise_commit(self, tortoise_path, wc_root, file_paths):
        """启动 TortoiseSVN 提交对话框，传 WC 根目录展示全部变更"""
        try:
            subprocess.Popen(
                [tortoise_path, "/command:commit", f"/path:{wc_root}"],
            )
            self._ulog(f"📄 TortoiseProc -> 已传 {len(file_paths)} 个文件（changelist 分组）", "info")
            self._ulog("✅ TortoiseSVN 提交对话框已打开", "ok")
            self.upload_run_btn.config(state="normal", text="▶  上传SVN")
        except Exception as e:
            self._ulog(f"❌ 启动 TortoiseSVN 失败: {e}", "error")
            self.upload_run_btn.config(state="normal", text="▶  上传SVN")

    def _wait_tortoise_and_cleanup(self, proc, wc_root):
        """等待 TortoiseProc 退出后清理本次修改 changelist"""
        try:
            proc.wait()
        except Exception:
            pass
        import time
        time.sleep(1)
        try:
            svn_exe = _get_svn_path()
            subprocess.run(
                [svn_exe, "changelist", "--remove", "--changelist", "本次修改", wc_root, "--depth", "infinity"],
                capture_output=True, text=True,
                timeout=60,
                **_get_subprocess_kwargs()
            )
        except Exception:
            pass

    def _on_tgt_list_click(self, event):
        lb = self.tr_tgt_listbox
        idx = lb.nearest(event.y)
        if idx < 0:
            return
        text = lb.get(idx)
        display_raw = text.strip("✓ ").strip()
        # 从显示文本反查出原始表头名
        h = self.tr_reverse_display.get(display_raw, display_raw)
        if text.startswith("✓"):
            lb.delete(idx)
            display = self.tr_tgt_display.get(h, h)
            lb.insert(idx, f"  {display}")
            self.tr_tgt_checked.pop(h, None)
        else:
            lb.delete(idx)
            display = self.tr_tgt_display.get(h, h)
            lb.insert(idx, f"✓ {display}")
            self.tr_tgt_checked[h] = True
        self._save_tr_lang_config()
        self._update_tgt_info()

    def _on_src_lang_selected(self, event=None):
        self._save_tr_lang_config()
