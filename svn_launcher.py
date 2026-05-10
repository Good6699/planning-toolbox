#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""策划工具箱 - 启动器"""
import sys
import os


def ensure_pythonpath():
    """注入 py_modules 到 sys.path"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pm_path = os.path.join(script_dir, "py_modules")
    if os.path.isdir(pm_path) and pm_path not in sys.path:
        sys.path.insert(0, pm_path)
        os.environ.setdefault("PYTHONPATH", pm_path)


def main():
    ensure_pythonpath()
    import svn_compare_gui
    svn_compare_gui.main()


if __name__ == "__main__":
    main()
