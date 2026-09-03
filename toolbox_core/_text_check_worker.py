#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文字表检测子进程 worker
在独立进程运行 detect()，避免占用主进程 GIL 导致界面卡顿。
用法: _text_check_worker.py <args_json_path>
args JSON 文件: {"file_path": str, "target_langs": [..], "lang_id_map": {..}, "exclude_ids_path": str}
进度通过 stdout 输出（父进程逐行读取转发 SSE），读取后删除参数文件。
"""
import sys
import os
import json

_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _script_dir)
_pm = os.path.join(_script_dir, "py_modules")
if os.path.isdir(_pm) and _pm not in sys.path:
    sys.path.insert(0, _pm)

# Windows 控制台默认 GBK 编码无法输出 ❌✅⚠ 等字符，强制 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: _text_check_worker.py <args_json_path>\n")
        sys.exit(1)
    arg_path = sys.argv[1]
    try:
        with open(arg_path, "r", encoding="utf-8") as f:
            args = json.load(f)
    except Exception as e:
        sys.stderr.write(f"参数读取失败: {e}\n")
        sys.exit(1)
    finally:
        try:
            os.unlink(arg_path)
        except Exception:
            pass

    from _text_check import detect

    def progress(msg):
        sys.stdout.write(msg)
        sys.stdout.flush()

    try:
        out_path, issues = detect(
            args.get("file_path", ""),
            progress_callback=progress,
            target_langs=args.get("target_langs") or None,
            lang_id_map=args.get("lang_id_map") or None,
            exclude_ids_path=args.get("exclude_ids_path"),
        )
        if out_path:
            progress(f"\n✅ 检测完成！发现问题: {issues} 行\n")
            progress(f"[输出路径] {out_path}\n")
        else:
            progress(f"\n❌ {issues}\n")
    except Exception as e:
        import traceback
        progress(f"\n❌ 检测失败: {e}\n")
        progress(traceback.format_exc() + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
