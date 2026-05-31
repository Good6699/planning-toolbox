#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""策划工具箱 - 入口路由器（支持 frozen 模式子进程路由）"""
import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
core_dir = os.path.join(script_dir, "toolbox_core")
sys.path.insert(0, core_dir)

# frozen 模式下 sys.executable 指向 exe 本身，子进程调用时会附带脚本名作为第一参数
# 此处识别并路由到正确的模块，否则 exe 不认识子进程参数会报错
if getattr(sys, 'frozen', False) and len(sys.argv) > 1:
    first_arg = sys.argv[1].replace("\\", "/")

    if "svn_oneclick_compare.py" in first_arg:
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        os.chdir(core_dir)
        from svn_oneclick_compare import main as svn_main
        svn_main()
    elif "_cmp_worker.py" in first_arg:
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        os.chdir(core_dir)
        from _cmp_worker import main as cmp_main
        cmp_main()
    elif "_merge_analyze_worker.py" in first_arg:
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        os.chdir(core_dir)
        from _merge_analyze_worker import main as maw_main
        maw_main()
    elif "_export_error_code_erl.py" in first_arg:
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        os.chdir(core_dir)
        from _export_error_code_erl import main as erl_main
        erl_main()
    else:
        os.chdir(core_dir)
        from desktop_main import main
        main()
else:
    os.chdir(core_dir)
    from desktop_main import main
    main()
