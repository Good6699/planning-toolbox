#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""策划工具箱 - 桌面版启动入口"""
import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
core_dir = os.path.join(script_dir, "toolbox_core")
sys.path.insert(0, core_dir)

os.chdir(core_dir)

from desktop_main import main
main()
