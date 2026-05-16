# Excel对比功能优化计划

## 一、需求分析

### 1.1 用户需求概述

用户要求优化当前的Excel对比功能，核心目标是提升解析和对比性能：

| 需求点 | 描述 | 优先级 |
|--------|------|--------|
| 快速解析 | 用最快方式解析唯一版本，避免重复解析 | 高 |
| Sheet级别过滤 | 对比时先按sheet快速对比，相同则跳过 | 高 |
| 行级别对比 | 仅对变化sheet按ID对比，保留表头和差异行 | 高 |
| 多线程并行 | 版本对之间多线程运行 | 高 |
| 全局去重 | 所有版本对对比结束后按ID去重，保留最新版本值 | 高 |
| 配置输出 | 按输出格式配置输出结果 | 中 |

### 1.2 现状分析

当前代码已具备：
- Phase 1: 并行下载（已优化）
- 版本对寻找逻辑（已优化）
- Sheet级别指纹对比（已有但可优化）
- ThreadPoolExecutor多线程（已有）

需要改进：
- 唯一版本解析策略
- 全局去重合并逻辑
- 输出格式配置应用

---

## 二、代码库研究

### 2.1 核心文件分析

| 文件 | 角色 | 关键函数 |
|------|------|----------|
| `svn_oneclick_compare.py` | 主对比逻辑 | `step3_download_and_compare`, `_process_one_pair` |
| `temp_github_original.py` | 参考版本 | `_dedupe_by_id`, `_parse_excel_with_cache` |

### 2.2 当前流程分析

```
当前流程：
Step 1 → Phase 1 (下载) → Phase 2 (解析+对比) → 输出

问题：每个版本对独立解析，存在重复解析
```

### 2.3 参考版本优势

备份版本 `temp_github_original.py` 的 `_dedupe_by_id` 函数提供了更完善的去重逻辑：
- 考虑操作类型合并（删除/新增/修改）
- 按版本号排序取最新值

---

## 三、修改方案

### 3.1 整体架构

```
优化后流程：
┌─────────────────────────────────────────────────────────────┐
│ Step 1: 查询文件版本对（保持不变）                           │
├─────────────────────────────────────────────────────────────┤
│ Phase 1: 并行下载（保持不变）                               │
├─────────────────────────────────────────────────────────────┤
│ Phase 2: 快速解析唯一版本（新增优化）                        │
│   - 提取所有唯一版本                                        │
│   - 并行快速解析                                            │
├─────────────────────────────────────────────────────────────┤
│ Phase 3: 版本对并行对比（优化）                             │
│   - Sheet级别快速过滤                                      │
│   - 行级别ID对比                                           │
├─────────────────────────────────────────────────────────────┤
│ Phase 4: 全局去重合并（新增）                               │
│   - 按ID分组去重                                           │
│   - 合并操作类型                                           │
│   - 保留最新版本值                                         │
├─────────────────────────────────────────────────────────────┤
│ Phase 5: 按配置输出（保持不变）                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 修改文件清单

| 文件 | 修改类型 | 修改内容 |
|------|----------|----------|
| `svn_oneclick_compare.py` | 修改 | Phase 2 解析逻辑优化 |
| `svn_oneclick_compare.py` | 修改 | Phase 3 对比逻辑优化 |
| `svn_oneclick_compare.py` | 新增 | Phase 4 全局去重合并 |
| `svn_oneclick_compare.py` | 修改 | 输出配置应用 |

### 3.3 核心修改点

#### 3.3.1 Phase 2: 快速解析唯一版本

**位置**：`step3_download_and_compare` 函数（约第2216行后）

**修改内容**：
```python
# 提取所有唯一版本
unique_versions = set()
for fn, pl in file_pairs.items():
    for cur, prv in pl:
        unique_versions.add((cur, fn))
        unique_versions.add((prv, fn))

# 并行快速解析所有唯一版本
parsed_cache = {}
with ThreadPoolExecutor(max_workers=parse_w) as ex:
    futures = [ex.submit(_parse_excel_fast, dl_cache[(rev, fn)], rev, fn) 
               for rev, fn in unique_versions]
    for f in as_completed(futures):
        rev, fn, result = f.result()
        parsed_cache[(rev, fn)] = result
```

#### 3.3.2 Phase 3: 版本对并行对比优化

**位置**：`_process_one_pair` 函数（约第2237行）

**修改内容**：
```python
def _process_one_pair(task):
    fname, cur, prv, tr, ic, oc = task
    
    # 从缓存获取已解析的版本
    cur_parsed = parsed_cache.get((cur, fname))
    prv_parsed = parsed_cache.get((prv, fname))
    
    # Sheet级别快速对比
    changed_sheets = _compare_sheets_fast(cur_parsed, prv_parsed)
    
    # 仅解析变化sheet的行数据
    diff_rows = []
    for sheet in changed_sheets:
        rows = _compare_rows_by_id(cur_parsed, prv_parsed, sheet)
        diff_rows.extend(rows)
    
    return fname, diff_rows, cur, prv, hdr, so
```

#### 3.3.3 Phase 4: 全局去重合并

**位置**：`step3_download_and_compare` 函数末尾（约第2490行后）

**新增内容**：
```python
def _dedupe_by_id_global(all_results):
    """全局去重，参考备份版本逻辑"""
    # 按 (filename, ID) 分组
    groups = defaultdict(list)
    for fn, results in all_results.items():
        for row in results:
            row_id = row.get("ID", "")
            key = (fn, row_id)
            groups[key].append((fn, row))
    
    # 去重合并
    final_results = {}
    for (fn, row_id), items in groups.items():
        if not row_id:
            # 表头直接保留
            for f, row in items:
                if f not in final_results:
                    final_results[f] = []
                final_results[f].append(row)
            continue
        
        # 按版本号降序排序
        items.sort(key=lambda x: x[1].get("当前版本", 0), reverse=True)
        
        # 合并操作类型
        ops = [item[1].get("操作", "") for item in items]
        has_delete = "删除" in ops
        
        if has_delete:
            if items[0][1].get("操作") == "删除":
                final_op = "删除"
            else:
                final_op = "修改"
        else:
            if "新增" in ops:
                final_op = "新增"
            else:
                final_op = "修改"
        
        # 取最新版本的值
        latest_fn, latest_row = items[0]
        merged = dict(latest_row)
        merged["操作"] = final_op
        
        if latest_fn not in final_results:
            final_results[latest_fn] = []
        final_results[latest_fn].append(merged)
    
    return final_results
```

---

## 四、实施步骤

### 4.1 步骤分解

| 步骤 | 任务 | 依赖 | 时间估算 |
|------|------|------|----------|
| 1 | 提取唯一版本并批量解析 | Phase 1 下载完成 | 30分钟 |
| 2 | 修改对比逻辑，添加Sheet级别快速过滤 | 步骤1完成 | 45分钟 |
| 3 | 新增全局去重合并函数 | 步骤2完成 | 45分钟 |
| 4 | 修改输出阶段，应用配置 | 步骤3完成 | 30分钟 |
| 5 | 测试验证 | 步骤4完成 | 60分钟 |

### 4.2 测试验证计划

| 测试场景 | 预期结果 |
|----------|----------|
| 单文件多版本对比 | 正确输出差异结果 |
| 多文件并行对比 | 正确输出差异结果 |
| 重复版本多次对比 | 缓存命中，不重复解析 |
| 全局去重验证 | 同一ID只保留最新版本 |
| 操作类型合并 | 删除+新增→修改 |

---

## 五、风险评估

### 5.1 潜在风险

| 风险 | 描述 | 影响 | 缓解措施 |
|------|------|------|----------|
| 内存占用 | 批量解析可能增加内存使用 | 中等 | 限制并发数，及时释放内存 |
| 缓存一致性 | 多线程访问缓存可能不一致 | 高 | 使用锁保护缓存读写 |
| 兼容性 | 修改可能影响现有功能 | 高 | 充分测试，保留备份 |

### 5.2 回滚方案

```bash
# 回滚到备份版本
git checkout backup_20260514
```

---

## 六、输出格式

### 6.1 差异行格式

```python
{
    "ID": "xxx",
    "操作": "新增/修改/删除",
    "当前版本": 123,
    "前一版本": 122,
    "sheet": "Sheet1",
    "列1": ["旧值", "新值"],
    ...
}
```

### 6.2 去重合并规则

| 场景 | 合并结果 |
|------|----------|
| 多次修改同一ID | 保留最新版本值，操作类型为"修改" |
| 删除后新增 | 操作类型为"修改" |
| 最新操作为删除 | 操作类型为"删除" |
| 首次出现 | 操作类型为"新增" |

---

## 七、参考文档

- [备份版本去重逻辑](file:///c:/Users/admin/.qclaw/workspace/temp_github_original.py#L1619)
- [当前对比函数](file:///c:/Users/admin/.qclaw/workspace/svn_oneclick_compare.py#L2237)
- [线程安全修复规范](file:///c:/Users/admin/.qclaw/workspace/docs/thread_safety_spec.md)