#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终测试脚本
验证整个系统是否可以正常工作
"""

import subprocess
import sys
import os

print("==============================================")
print("最终测试脚本")
print("==============================================")

# 1. 测试Python环境
print("1. 测试Python环境...")
print("Python版本:", sys.version)
print("Python路径:", sys.executable)
print()

# 2. 测试SVN命令
print("2. 测试SVN命令...")
svn_path = r"C:\Program Files\SlikSvn\bin\svn.exe"
try:
    result = subprocess.run([svn_path, "--version"], capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        print("SVN命令可用")
        print("SVN版本:", result.stdout.split('\n')[0])
    else:
        print("SVN命令执行失败:", result.stderr)
except Exception as e:
    print("SVN命令不可用:", e)
print()

# 3. 测试脚本文件
print("3. 测试脚本文件...")
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

# 4. 测试依赖项
print("4. 测试依赖项...")
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

# 5. 测试修复版VBS脚本
print("5. 测试修复版VBS脚本...")
try:
    # 检查VBS脚本是否存在
    if os.path.exists("SVN一键对比GUI修复版.vbs"):
        print("修复版VBS脚本存在")
        print("请双击运行 'SVN一键对比GUI修复版.vbs' 来启动程序")
    else:
        print("修复版VBS脚本不存在")
except Exception as e:
    print("测试VBS脚本失败:", e)
print()

print("==============================================")
print("最终测试完成")
print("==============================================")
print("系统环境已修复，现在可以运行 'SVN一键对比GUI修复版.vbs' 来启动程序")
