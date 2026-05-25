#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Squash 子进程 Worker — 按版本分片并行，返回 {path, parsed_lines}"""
import sys
import os
import pickle
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) != 3:
        sys.stderr.write(f"Usage: {sys.argv[0]} <arg_pickle> <res_pickle>\n")
        sys.exit(1)

    arg_path, res_path = sys.argv[1], sys.argv[2]

    try:
        with open(arg_path, "rb") as f:
            args = pickle.load(f)
    except Exception as e:
        sys.stderr.write(f"[squash_worker] Failed to read args: {e}\n")
        sys.exit(1)

    source_url = args.get("source_url", "")
    rev_file_map = args.get("rev_file_map", {})
    auth = args.get("auth", {})
    target_path = args.get("target_path")
    revisions = args.get("revisions", [])
    svn_user = auth.get("svn_user")
    svn_pass = auth.get("svn_pass")

    from _merge_analyzer import (
        _build_svn_auth_args, _strip_repo_prefix,
        _compare_prefab_texts_fast, _run_svn,
        _extract_guids_from_diff, _find_meta_for_guids,
    )

    auth_args = _build_svn_auth_args(svn_user, svn_pass)
    entries = []
    total = len(revisions)
    svn_timeout = 120

    for idx, rev in enumerate(sorted(revisions)):
        file_list = rev_file_map.get(str(rev), [])
        prefab_files = [cf for cf in file_list if os.path.splitext(cf["path"])[1].lower() in (".prefab", ".unity")]

        if not prefab_files:
            sys.stderr.write(f"  r{rev} ({idx+1}/{total}): no semantic files\n")
            continue

        sys.stderr.write(f"  r{rev} ({idx+1}/{total}): {len(prefab_files)} file(s)...\n")
        prv_rev = max(1, rev - 1)

        for cf in prefab_files:
            rel_path = _strip_repo_prefix(source_url, cf["path"])
            file_url = source_url.rstrip("/") + "/" + rel_path
            fname = os.path.basename(cf["path"])

            _t0 = time.time()
            try:
                old_text = _run_svn(["cat", "-r", str(prv_rev), file_url] + auth_args, timeout=svn_timeout)
            except RuntimeError:
                old_text = ""
            sys.stderr.write(f"    r{rev} {fname}: 旧版 svn cat 耗时 {time.time()-_t0:.1f}s ({'成功' if old_text else '失败'})\n")

            _t0 = time.time()
            try:
                new_text = _run_svn(["cat", "-r", str(rev), file_url] + auth_args, timeout=svn_timeout)
            except RuntimeError:
                new_text = ""
            sys.stderr.write(f"    r{rev} {fname}: 新版 svn cat 耗时 {time.time()-_t0:.1f}s ({'成功' if new_text else '失败'})\n")

            _t0 = time.time()
            all_guids = _extract_guids_from_diff(old_text + new_text)
            lazy_map = {}
            if all_guids and target_path and os.path.isdir(os.path.join(target_path, "Assets")):
                lazy_map = _find_meta_for_guids(all_guids, target_path)
            sys.stderr.write(f"    r{rev} {fname}: GUID 映射耗时 {time.time()-_t0:.1f}s (guid={len(all_guids)}, found={len(lazy_map)})\n")

            _t0 = time.time()
            parsed_lines = _compare_prefab_texts_fast(old_text, new_text, lazy_map, _log=None)
            sys.stderr.write(f"    r{rev} {fname}: YAML 对比耗时 {time.time()-_t0:.1f}s ({len(parsed_lines)} 条变更)\n")
            if parsed_lines:
                entries.append({"path": cf["path"], "action": "M", "parsed_lines": parsed_lines})

        sys.stderr.write(f"  r{rev} ({idx+1}/{total}): done\n")

    try:
        with open(res_path, "wb") as f:
            pickle.dump(entries, f)
    except Exception as e:
        sys.stderr.write(f"[squash_worker] Failed to write result: {e}\n")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
