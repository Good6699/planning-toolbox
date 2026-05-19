# svn_oneclick_compare.py 开发规则

## AGENT 行为规则

### ⚠️ 分析/制定方案前必须执行

1. **每次分析问题或制定方案前，必须先上网查资料** — 使用 `WebSearch` 工具搜索相关技术资料、最佳实践、已知解决方案。
2. **同一对话中每次遇到新问题时也必须查** — 不是只在对话开始时查一次，而是每次碰到新的技术问题、需要做决策时都要重新查。
3. **即使自己知道答案也必须查** — 技术资料在持续更新，过去的知识可能已过时。不能凭记忆或经验下结论。
4. **不得跳过此步骤直接下结论** — 任何技术方案制定、bug 诊断、功能设计前都必须先查资料。

### ⚠️ 修改代码前必须执行

1. **每次修改代码前，必须先调用 `step-by-step` skill** — 使用 step-by-step 技能将实现任务分解为有序的 Phase（问题分析 → 变更定位 → 变更点详述 → 实施顺序 → 逐项实施），再开始修改代码。
2. **不得跳过此步骤直接修改代码** — 任何代码变更（修复 bug、新增功能、重构等）都必须先运行 step-by-step skill。

### ⚠️ 分析问题前必须执行

1. **每次分析问题（诊断 bug、异常行为、性能问题等）前，必须先调用 `problem-solver` skill** — 使用 problem-solver 技能进行结构化根因分析（鱼骨图 + 5 Whys），不得跳过此步骤直接下结论或开始修改代码。
2. **不得跳过此步骤直接诊断** — 任何问题分析都必须先运行 problem-solver skill。

## 架构红线

### ❌ 绝对禁止

1. **ProcessPoolExecutor** — Windows spawn 模式下 2+ 进程静默崩溃。实测：1 进程 OK，2 进程 worker1 消失（exit code 0，无异常）。根因是 spawn 重新 import 3000 行模块某处失败且未被捕获，不是 OOM。

2. **multiprocessing.shared_memory 跨进程共享** — 与 ProcessPool 同根因。任何跨进程共享内存在 Windows spawn 下不可靠。

3. **ThreadPool + Queue + 哨兵流水线** — 2025Q2 已验证死锁 + 竞态条件 + 假并行。

4. **在子进程中调 _log()** — 虽然 _log() 本身没问题，但 spawn 子进程的 stdout 管道状态不可靠，避免依赖。

5. **禁止从 GitHub 下载文件覆盖本地文件** — 任何时候都不得自行从 GitHub 或其他远程仓库下载文件来覆盖项目中的本地文件。任何文件恢复、回退、获取历史版本等操作，都必须先经过用户明确同意后才能执行。

### ✅ 当前正确架构（2026-05）

```
Phase 1+2 流水线: 下载与解析在同一个事件循环中并发

主循环 while done < total:
  ① ThreadPool(workers) 并行下载 → 每完成一个版本:
     _check_pairs() 检查该版本所属的版本对是否双方都已就绪
     就绪 → pending_pairs.append()
  ② pending_pairs 非空 + 有空闲 worker 位 → subprocess.Popen 启动独立子进程
  ③ poll() 子进程 → 收集结果 → 清理临时文件

子进程: _cmp_worker.py（独立 python.exe，通过 pickle 临时文件通信）
```

### 为什么 subprocess.Popen 可行而 ProcessPool 不行

| | ProcessPoolExecutor | subprocess.Popen |
|---|---|---|
| 启动方式 | spawn: 框架控制 re-import | 全新 python.exe，独立 import |
| 2+ 进程 | 静默崩溃 | 全部存活 |
| 错误诊断 | 不可诊断 | stderr=PIPE，可读 |
| 参数传递 | pickle 序列化（自动） | 手动 pickle 临时文件 |

### 性能数据（32 版本对 / 16 进程 / 16 核 / 12GB）

| 方案 | Phase 2 时间 | 总时间 | 状态 |
|------|:---:|:---:|:---:|
| 原始 ThreadPool（58 sheet 全量 lxml） | 690s | 720s | ❌ |
| ThreadPool + only_sheets + SS 指纹 | 260s | 290s | ❌ 慢 |
| subprocess 16 进程 + SS 指纹 | 80s | 110s | ✅ 已上线 |
| subprocess + 流水线 + 传路径 | **~55s** | **~75s** | ✅ 已上线 |

## 与 Excel 解析相关的正确知识

### sharedStrings（SS）机制

```
Excel 存文字两种方式：
  方式 A: <c r="A1"><v>123</v></c>             — 值直接写在单元格
  方式 B: <c r="A1" t="s"><v>0</v></c>         — 存索引，真文字在 sharedStrings.xml[0]

sharedStrings 变了 ≠ sheet 内容变了：
  例: SS[42] "裂隙秘境" → "裂隙秘境（已开启）"
      sheet27 引用索引 [1,2,3]（不包含 42）→ sheet27 实际内容未变
      sheet28 引用索引 [0,5,42]（包含 42）→ sheet28 实际内容变了
```

### SS 指纹预检（已上线）

`_zip_get_changed_sheets` 对每个 sheet 的判定优先级：

```
1. raw bytes (zf.read) 不同 → 加入 changed_sheets（直接）
2. raw bytes 相同 + ss_changed=True + 有 t="s" → 正则提取引用索引 → 解析为实际文字 → MD5 指纹
   - 指纹不同 → 加入 changed_sheets
   - 指纹相同 → 跳过（内容未变，即使 SS 表变了）
3. raw bytes 相同 + ss_changed=False → 跳过
4. raw bytes 相同 + ss_changed=True + 无 t="s" → 跳过
```

### SS 解析：纯正则 > lxml iterparse > lxml fromstring

| 方法 | 18MB SS 耗时 | 内存 |
|------|:---:|:---:|
| `etree.fromstring` | 1.1s | ~200MB |
| `etree.iterparse` | 2.5s | ~50MB |
| 纯正则 `_SS_TEXT_RE` | 1.8s | ~10MB |

当前用正则 `_SS_TEXT_RE`，在进程内 `_ss_values_cache` 缓存（双重检查锁）。跨子进程不共享。

### lxml 与 GIL

- lxml 通过 ctypes 调用 C 库 libxml2，**C 层持有 GIL 不释放**
- ThreadPool 多线程 lxml 解析 = 串行（只有 1 个线程在 C 层工作）
- 唯一绕过方式：独立进程（subprocess.Popen，各自有独立解释器和 GIL）

### 为什么不能跳过 SS 全量解析

见上面 sharedStrings 机制。两个版本 SS 变了，但 sheet XML raw bytes 可能完全一致（都引用 SS[42]）。不解析 SS 就发现不了差异。正确性要求必须解析 SS。

### 之前错误的诊断需要在项目中更正

| 错误诊断 | 实际情况 |
|------|------|
| "OOM：16 进程 × 1.5GB = 24GB > 12GB" | 实测单进程 lxml 全量解析 ~400MB，不是 1.5-3GB |
| "_log() 导致子进程崩溃" | _log() 没问题，根因是 ProcessPool spawn 机制 |
| "传 bytes 比传路径好" | 传 bytes 导致 pickle 序列化 13MB → 临时文件，传路径 pickle <1KB |
| "共享内存 SS 缓存可行" | Windows spawn 下不可靠，与 ProcessPool 同根因 |
| "预热进程池省 5s" | 理论上可行但投入产出比极低（150+ 行 vs 5s） |

## 测试/验证规则

- 语法：`python -m py_compile svn_oneclick_compare.py _cmp_worker.py`
- 图谱：`$env:PYTHONPATH="py_modules"; python -m graphify update .`
- 不要删除 `临时辅助文件/` 目录下的文件
- 不要删除 `__byte_cache/` 下的缓存文件
- 子进程并发测试：先用路径参数模拟（`_test_pipeline.py` 风格），确认 2/4 worker 全部存活再上线

---

## ⚠️ Git 提交规范 — 每次提交前必须执行

**所有代码提交都必须遵循 [git_workflow_rules.md](.trae/rules/git_workflow_rules.md) 中定义的规范。**

### 每次 git commit 前必须执行的三步检查

1. **语法检查：** `python -m py_compile <修改的文件>` — 确保无语法错误
2. **规范检查：** `flake8 <修改的文件>` — 确保符合 PEP8 规范
3. **写规范的 commit message：** `<type>(<scope>): <subject>` 格式

### pre-commit 钩子

项目已配置 `.git/hooks/pre-commit`，git commit 时会自动运行 flake8 检查暂存区文件。如果检查到 E/F 级别错误，提交将被阻止。

### 提交信息格式速查

```
feat(web): 新功能
fix(cmp): 修复 Bug
perf(worker): 性能优化
refactor(gui): 代码重构
docs(rules): 文档/规则
chore: 杂项/构建
```

### 里程碑版本标签

- 语义化版本：`v<major>.<minor>.<patch>`（如 `v1.0`、`v1.1`）
- 里程碑版本推送 tag 到 GitHub 后需创建 GitHub Release
- 常规提交（非里程碑）直接 `git push`，不创建 tag

**⚠️ 只改 Web 应用端（Flask 后端 + templates/index.html），不改其他版本。**

- 所有问题、需求、修改都默认只针对 **Web 应用端**（`web_app.py` + `templates/index.html`）
- **tkinter GUI 桌面版**（`svn_compare_gui.py`、`toolbox_tab_*.py`、`desktop_main.py` 等）不做任何修改
- **命令行版**（`svn_oneclick_compare.py`、`_cmp_worker.py` 等）不做任何修改
- **说明书/README** 不做任何修改
- **纯静态 HTML**（`_rebuild_html.py`、`desktop_shell_demo.py` 等）不做任何修改
- 所有功能测试只关注 Web 应用端行为
