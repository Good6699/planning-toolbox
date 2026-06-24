#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""语义分析子进程 Worker — 独立进程执行分析任务"""
import sys
import os
import pickle

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
        sys.stderr.write(f"[worker] Failed to read args: {e}\n")
        sys.exit(1)

    source_url = args.get("source_url", "")
    revisions = args.get("revisions", [])
    guid_map = args.get("guid_map", {})
    auth = args.get("auth", {})
    rev_file_map = args.get("rev_file_map", {})
    target_path = args.get("target_path")
    svn_user = auth.get("svn_user")
    svn_pass = auth.get("svn_pass")

    from _merge_analyzer import _build_svn_auth_args, _analyze_revision_data

    auth_args = _build_svn_auth_args(svn_user, svn_pass)
    results = []
    total = len(revisions)

    for idx, rev in enumerate(sorted(revisions)):
        sys.stderr.write(f"r{rev} ({idx+1}/{total}): 分析中...\n")
        file_list = rev_file_map.get(str(rev))
        rd = _analyze_revision_data(rev, source_url, guid_map, auth_args, file_list=file_list, target_path=target_path)
        results.append(rd)
        has_semantic = any(f.get("parsed_lines") for f in rd.get("files", []))
        if has_semantic:
            sys.stderr.write(f"r{rev} ({idx+1}/{total}): 完成\n")
        else:
            sys.stderr.write(f"r{rev} ({idx+1}/{total}): 无语义文件\n")

    try:
        with open(res_path, "wb") as f:
            pickle.dump(results, f)
    except Exception as e:
        sys.stderr.write(f"[worker] Failed to write result: {e}\n")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
