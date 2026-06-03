---
name: "test-logic"
description: "用 Python 快速验证策划工具箱前端/后端的核心逻辑。Invoke when: (1) 修改路径/正则/数据转换逻辑前需要验证正确性, (2) 排查边界情况时, (3) 需要确认 refactor 前后行为一致时"
---

# 策划工具箱逻辑自测 Skill

## 用途

本项目是 Flask + 单页 HTML/JS 应用，没有正式的测试框架。此 Skill 用来**在执行代码变更前，快速用 Python 验证逻辑的正确性**，确保 AI 的理解与真实行为一致。

## 核心原则

1. **先写 test script 验证，再改代码** — 不要靠"读代码来推理"、不要靠"人肉走读"
2. **用 Python 模拟 JS 逻辑** — 正则、字符串操作、路径处理等可以直接翻译为 Python
3. **用真实数据测试** — 从 `svn_gui_config.json`（实际用户配置）、日志文件、用户提供的路径中提取真实样本
4. **测边界** — 路径结尾 `\`、空字符串、undefined、数组、嵌套对象、多个前缀、中文路径、特殊字符
5. **测试脚本放在 `临时辅助文件/` 下，用完不必删除**

## 项目常见 Bug 模式（基于 MEMORY.md 历史记录）

| 模式 | 说明 | 测试时关注点 |
|------|------|------------|
| `_esMap` 键冲突 | 并行步骤共用 `url` 作为 SSE 的 key，后一步 close 前一步的 EventSource，`_done()` 永不执行 | `_stateKey` 是否传递；`esKey` 是否互斥 |
| `_tabCount` 硬重置 | 并行时 `_tabCount[key]=0` 让第一个完成的步骤关掉黄点，忽略其他步骤仍在运行 | 改用 `_decTabRunning()` 引用计数 |
| `saveConfig` 竞态 | 先发请求再更新本地 config → 前端状态与后端不一致 | 先 `Object.assign(config, updates)` 再 `fetch` |
| `_wfSaving` 防重复 | `_wfModalDoSave()` 用布尔锁防 Enter 键 / 多次点击导致保存逻辑执行两次 | `_wfSaving=true` 时直接 return |
| svn lock 不传 --force | 强行抢夺他人锁，导致对方丢失锁 | 命令参数中不能含有 `--force` |
| openpyxl 公式缓存 | openpyxl 只写 `<f>` 不写 `<v>`，对比工具读不到计算值 | 用 win32com 后台静默打开+Save |
| 路径替换漏嵌套 | 只替换浅层字段，漏掉数组内对象、嵌套 dict 中的路径 | 递归遍历所有层级 |
| SortableJS 含非步骤元素 | 拖拽后 `container.children` 包含 `wf-add-step-item` | 必须 `.filter(Boolean)` 过滤 |
| `tr_api_key` 被误清 | `saveConfig` 改了其他字段但没带 `api_key` → 后端 `cfg[k]=v` 没覆盖 → 正常；但若前端 `Object.assign` 未包含加密 key → 丢失 | `api_key` 单独处理、后端 `else: cfg[k]=v` 不丢 |

## 适合的场景

### 1. 正则匹配验证（最常用）

当修改 `index.html` 中的 JavaScript 正则表达式（路径提取、字符串匹配等）时：

```python
# 临时辅助文件/test_regex.py
import re
tests = [
    r"H:\D3_EA\gameData\Text\Texts.xlsm",
    r"F:\D3_KR2_DEV\gameData\Text",
    r"H:\D3_EA\Client\Assets",
    r"E:\NoMatch\else.txt",
]
pat = r"^(.+?)\\(?:gameData|Client)(?:\\|$)"  # 从 JS 翻译过来的正则
for t in tests:
    m = re.match(pat, t, re.IGNORECASE)
    print(f"{'OK' if m else '--'}: {t}")
    if m: print(f"  prefix = {m.group(1)!r}")
```

### 2. 路径前缀替换验证

当修改 `_wfReplacePrefixes` 的逻辑时：

```python
# 模拟 JS 的 _wfReplacePrefixes 递归替换
def replace_prefixes(obj, old_p, new_p):
    if isinstance(obj, str):
        if obj == old_p or obj.startswith(old_p + "\\"):
            return new_p + obj[len(old_p):]
        return obj
    if isinstance(obj, list):
        return [replace_prefixes(v, old_p, new_p) for v in obj]
    if isinstance(obj, dict):
        return {k: replace_prefixes(v, old_p, new_p) for k, v in obj.items()}
    return obj

# 测试样本（从真实 config 提取）
sample = {
    "name": "KR2",
    "steps": [
        {"type": "export_text", "input_file": r"H:\D3_EA\gameData\Text\Texts.xlsm"},
        {"type": "upload_svn", "dirs": [r"H:\D3_EA\gameData", r"H:\D3_EA\Client\Assets"]},
        {"type": "lock_svn", "target_path": r"H:\D3_EA\gameData\Text\Texts.xlsm"}
    ]
}
result = replace_prefixes(sample, r"H:\D3_EA", r"F:\NEW_PATH")
import json
print(json.dumps(result, indent=2, ensure_ascii=False))
```

### 3. saveConfig 数据流验证

当涉及配置保存/读取逻辑时，检查后端 `api_save_config` 的行为：

```python
# 验证后端 saveConfig 只更新指定 key，不丢失其他配置
cfg = {
    "svn_urls": ["url1"],
    "workflows": [{"name": "A"}],
    "tr_api_key": "secret123",
}
updates = {"workflows": [{"name": "B"}]}
for k, v in updates.items():
    cfg[k] = v
# 预期: cfg["tr_api_key"] 仍然是 "secret123"
assert cfg["tr_api_key"] == "secret123"
```

### 4. _wfAutoName 行为验证

当分析步骤命名是否正确时：

```python
# 模拟 basename 提取逻辑
paths = [
    r"H:\D3_EA\gameData\Text\Texts.xlsm",
    r"F:\NEW_PATH\gameData\Text\Texts.xlsm",
]
for p in paths:
    i = max(p.rfind("\\"), p.rfind("/"))
    name = p[i+1:] if i >= 0 else p
    print(f"{p} → {name}")
# 两个路径都应该打印 "Texts.xlsm"，验证前缀替换不影响自动命名
```

### 5. 实际运行日志分析

当排查运行时问题时，从日志中提取关键时间戳和 exit code：

```python
# 从日志提取时间线
lines = """[KR2] 18:07:13 使用 2 个工具并行执行...
[KR2] 18:07:13 正在执行: 服务器文字表导出_替换文本引用.bat
[KR2] 18:08:02 服务器文字表导出_替换文本引用.bat 退出代码: 1
[KR2] 18:09:52 客户端文字表导出_替换文本引用.bat 退出代码: 1"""
import re
for line in lines.splitlines():
    m = re.match(r"\[(\w+)\] (\d+:\d+:\d+) (.+)", line)
    if m: print(f"{m.group(2)} [{m.group(1)}] {m.group(3)}")
```

## 不使用此 Skill 的场景

- 简单的变量改名、修改注释
- 纯 CSS 样式调整
- 已有的错误栈已直接指向问题代码（不需要再验证）

## 输出要求

测试脚本运行后，将所有结论（OK/FAIL、预期 vs 实际）输出到一条消息中，不要分段输出多条消息。如果有 FAIL，给出具体哪一项和预期的差异。
