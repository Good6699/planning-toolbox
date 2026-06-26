#!/usr/bin/env python3
"""JS 压缩脚本：对 core.js 和 tab-*.js 进行 Terser/minify 压缩"""
import os, sys
script_dir = os.path.dirname(os.path.abspath(__file__))

# Try import rjsmin
try:
    import rjsmin
    HAS_RJSMIN = True
except ImportError:
    HAS_RJSMIN = False

js_files = [
    'core.js',
    'tab-merge.js',
    'tab-upload.js',
    'tab-workflow.js',
    'tab-translate.js',
    'tab-textcheck.js',
    'tab-prefab.js',
]

total_original = 0
total_minified = 0

for filename in js_files:
    filepath = os.path.join(script_dir, filename)
    if not os.path.isfile(filepath):
        print(f"  [跳过] {filename} 不存在")
        continue

    with open(filepath, 'r', encoding='utf-8') as f:
        original = f.read()

    original_size = len(original)
    total_original += original_size

    if HAS_RJSMIN:
        minified = rjsmin.jsmin(original)
    else:
        import re
        minified = re.sub(r'//.*', '', original)  # remove single-line comments
        minified = re.sub(r'/\*.*?\*/', '', minified, flags=re.DOTALL)  # remove block comments
        minified = re.sub(r'\n+', '\n', minified)  # collapse blank lines

    minified_size = len(minified)
    total_minified += minified_size
    ratio = (1 - minified_size / original_size) * 100

    # Write .min.js version
    min_path = filepath.replace('.js', '.min.js')
    with open(min_path, 'w', encoding='utf-8') as f:
        f.write(minified)

    print(f"  {filename}: {original_size} -> {minified_size} bytes ({ratio:.0f}% reduction)")

print(f"\n总计: {total_original} -> {total_minified} bytes ({(1-total_minified/total_original)*100:.0f}% reduction)")
