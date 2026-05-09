#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统测试脚本
验证Python环境、SVN命令和主要功能是否正常
"""

import subprocess
import sys
import os

print("==============================================")
print("系统测试脚本")
print("==============================================")

# 1. 检查Python环境
print("1. 检查Python环境...")
print("Python版本:", sys.version)
print("Python路径:", sys.executable)
print()

# 2. 检查依赖项
print("2. 检查依赖项...")
try:
    import lxml
    import openpyxl
    import pandas
    import requests
    import numpy
    print("所有必要的依赖项已安装")
except ImportError as e:
    print("缺少依赖项:", e)
print()

# 3. 检查SVN命令
print("3. 检查SVN命令...")
try:
    result = subprocess.run(["svn", "--version"], capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        print("SVN命令可用")
        print("SVN版本信息:", result.stdout[:200], "...")
    else:
        print("SVN命令执行失败:", result.stderr)
except Exception as e:
    print("SVN命令不可用:", e)
print()

# 4. 检查脚本文件
print("4. 检查脚本文件...")
script_files = [
    "svn_oneclick_compare.py",
    "svn_compare_gui.py",
    "SVN一键对比GUI.vbs",
    "SVN一键对比GUI修复版.vbs"
]

for file in script_files:
    if os.path.exists(file):
        print(file, "存在")
    else:
        print(file, "不存在")
print()

# 5. 检查缓存目录
print("5. 检查缓存目录...")
cache_dirs = ["__parse_cache__"]
for dir in cache_dirs:
    if os.path.exists(dir):
        print(dir, "目录存在")
    else:
        print(dir, "目录不存在")
print()

print("==============================================")
print("系统测试完成")
print("==============================================")
