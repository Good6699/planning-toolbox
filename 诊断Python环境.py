#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""诊断 Python 环境完整性"""
import sys
import os
import platform
import subprocess
import json

print("=" * 60)
print("          🔍 Python 环境诊断工具")
print("=" * 60)
print()

results = {}

# 1. 基础信息
print("📋 1. Python 基本信息")
print("-" * 40)
results['version'] = sys.version
print(f"Python 版本: {sys.version}")
print(f"可执行文件: {sys.executable}")
print(f"平台: {platform.platform()}")
print(f"架构: {platform.machine()}")
print()

# 2. 路径检查
print("📂 2. 路径信息")
print("-" * 40)
print("sys.path:")
for i, p in enumerate(sys.path):
    print(f"  [{i}] {p}")
print()

# 3. 导入检查
print("✅ 3. 核心库导入测试")
print("-" * 40)

modules_to_test = [
    'os', 'sys', 'platform', 'subprocess', 'json', 'math',
    'threading', 'multiprocessing', 'ctypes', 'array',
    'struct', 're', 'datetime', 'time', 'collections',
    'io', 'pathlib'
]

results['import_test'] = {}
for mod in modules_to_test:
    try:
        __import__(mod)
        print(f"  ✓ {mod}")
        results['import_test'][mod] = True
    except Exception as e:
        print(f"  ✗ {mod} - {e}")
        results['import_test'][mod] = False
print()

# 4. 尝试检查 site-packages
print("📦 4. site-packages 目录")
print("-" * 40)
import site
site_packages = site.getsitepackages()
results['site_packages'] = site_packages
for i, sp in enumerate(site_packages):
    exists = os.path.exists(sp)
    print(f"  [{i}] {sp} - {'存在' if exists else '不存在'}")
print()

# 5. 测试简单计算
print("🧮 5. 简单计算测试")
print("-" * 40)
try:
    a = 1 + 1
    b = 100 * 200
    c = sum(range(100))
    print(f"  ✓ 数学计算正常: {a}, {b}, {c}")
    results['math_test'] = True
except Exception as e:
    print(f"  ✗ 数学计算失败: {e}")
    results['math_test'] = False
print()

# 6. 测试文件操作
print("📄 6. 文件操作测试")
print("-" * 40)
test_file = "test_temp.txt"
try:
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("测试")
    print(f"  ✓ 写文件成功: {test_file}")
    
    with open(test_file, "r", encoding="utf-8") as f:
        content = f.read()
    print(f"  ✓ 读文件成功: {content}")
    
    os.remove(test_file)
    print(f"  ✓ 删除文件成功")
    results['file_test'] = True
except Exception as e:
    print(f"  ✗ 文件操作失败: {e}")
    results['file_test'] = False
print()

# 7. 测试子进程调用
print("🔧 7. 子进程测试")
print("-" * 40)
try:
    result = subprocess.run(
        [sys.executable, "-c", "print('test')"],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        print(f"  ✓ 子进程调用成功: {result.stdout.strip()}")
        results['subprocess_test'] = True
    else:
        print(f"  ✗ 子进程失败: code={result.returncode}, stderr={result.stderr}")
        results['subprocess_test'] = False
except Exception as e:
    print(f"  ✗ 子进程异常: {e}")
    results['subprocess_test'] = False
print()

# 8. 保存结果
print("💾 8. 保存诊断结果")
print("-" * 40)
diagnosis_file = "diagnosis_results.json"
try:
    with open(diagnosis_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 结果已保存到: {diagnosis_file}")
except Exception as e:
    print(f"  ✗ 保存失败: {e}")
print()

print("=" * 60)
print("          🏁 诊断完成")
print("=" * 60)
print()

# 简单总结
total_tests = sum(
    len([v for k, v in results.get('import_test', {}).items()]) +
    sum([1 for k in ['math_test', 'file_test', 'subprocess_test'] if k in results])
)
passed = sum(
    sum([1 for k, v in results.get('import_test', {}).items() if v]) +
    sum([1 for k in ['math_test', 'file_test', 'subprocess_test'] if results.get(k)])
)
print(f"📊 通过率: {passed}/{total_tests}")
