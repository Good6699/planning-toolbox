# 线程安全问题修复规范文档

## 1. 问题描述

### 1.1 问题背景

在 `svn_oneclick_compare.py` 的 `step3_download_and_compare` 函数中，使用 `ThreadPoolExecutor` 并行处理多个版本对的对比任务。当多个版本对共享同一个版本时（例如版本对 `(3,2)` 和 `(2,1)` 都包含版本2），会同时访问和修改三个全局缓存：

- `_structure_cache`: 内容哈希 → 结构信息
- `_row_fp_cache`: 内容哈希 → 行指纹
- `_ss_crc_cache`: 内容哈希 → SS CRC

### 1.2 竞态条件分析

```python
# 当前存在问题的代码模式
if cur_ch not in _structure_cache:  # 线程A和B可能同时通过检查
    cur_struct, cur_ss_crc = _regex_scan_structure(cur_b)  # 耗时解析
    _structure_cache[cur_ch] = cur_struct  # 可能重复写入
```

**竞态场景**：
1. 线程A检查 `version_2_hash not in _structure_cache` → True
2. 线程B检查 `version_2_hash not in _structure_cache` → True（尚未写入）
3. 线程A开始解析版本2（耗时操作）
4. 线程B也开始解析版本2（重复工作）
5. 线程A写入缓存
6. 线程B写入缓存（覆盖，虽然结果相同但浪费资源）

### 1.3 影响范围

| 缓存名称 | 问题类型 | 影响程度 |
|----------|----------|----------|
| `_structure_cache` | 重复解析、数据覆盖 | 高 |
| `_row_fp_cache` | 重复计算、数据覆盖 | 高 |
| `_ss_crc_cache` | 重复计算、数据覆盖 | 高 |

### 1.4 风险等级

**严重等级**: 中

虽然最终结果正确（解析结果相同），但会导致：
- CPU 资源浪费（重复解析）
- 内存峰值增加（多个线程同时持有解析结果）
- 缓存可能处于不一致状态（短暂）

---

## 2. 解决方案

### 2.1 方案概述

引入**全局缓存锁** `_structure_cache_lock`，保护三个全局缓存的读写操作，实现线程安全的缓存访问。

### 2.2 锁设计

```python
# 在文件顶部定义锁
_structure_cache_lock = threading.Lock()
```

### 2.3 缓存访问模式

采用**双重检查锁定模式**（Double-Checked Locking），平衡线程安全和性能：

```python
# 伪代码示例
def get_or_parse_structure(content_hash, content_bytes):
    # 第一次检查（无锁，快速路径）
    if content_hash in _structure_cache:
        return _structure_cache[content_hash]
    
    # 获取锁
    with _structure_cache_lock:
        # 第二次检查（有锁，确保只有一个线程进行解析）
        if content_hash in _structure_cache:
            return _structure_cache[content_hash]
        
        # 执行解析
        struct = _regex_scan_structure(content_bytes)
        _structure_cache[content_hash] = struct
        return struct
```

### 2.4 修复范围

需要修改的代码位置：

| 位置 | 行号范围 | 修改内容 |
|------|----------|----------|
| Phase A 结构扫描（cur） | 2246-2269 | 添加锁保护 |
| Phase A 结构扫描（prv） | 2271-2289 | 添加锁保护 |
| 行指纹更新（cur） | 2316-2325 | 添加锁保护 |
| 行指纹更新（prv） | 2326-2335 | 添加锁保护 |
| 缓存清理 | 2264-2268 | 添加锁保护 |

---

## 3. 实施计划

### 3.1 步骤分解

| 步骤 | 任务描述 | 责任人 | 依赖 |
|------|----------|--------|------|
| 1 | 在文件顶部添加 `_structure_cache_lock` 定义 | 开发 | 无 |
| 2 | 修改 `_process_one_pair` 函数中 cur 版本的缓存访问 | 开发 | 步骤1 |
| 3 | 修改 `_process_one_pair` 函数中 prv 版本的缓存访问 | 开发 | 步骤1 |
| 4 | 修改缓存清理逻辑 | 开发 | 步骤1 |
| 5 | 单元测试验证 | 测试 | 步骤2-4 |
| 6 | 集成测试验证 | 测试 | 步骤5 |

### 3.2 时间估算

| 任务 | 预估时间 |
|------|----------|
| 代码修改 | 2小时 |
| 测试验证 | 1小时 |
| 文档更新 | 0.5小时 |
| **总计** | **3.5小时** |

---

## 4. 代码修改规范

### 4.1 锁定义规范

```python
# 位置：文件顶部，与其他锁定义放在一起
# 行号：约153行附近，在 _ss_cache_lock 之后
_structure_cache_lock = threading.Lock()
```

### 4.2 缓存读取规范

```python
# 正确模式：双重检查锁定
def _get_structure(content_hash, content_bytes):
    # 快速路径：无锁检查
    if content_hash in _structure_cache:
        return _structure_cache[content_hash]
    
    # 慢速路径：有锁检查和写入
    with _structure_cache_lock:
        if content_hash in _structure_cache:
            return _structure_cache[content_hash]
        # 执行解析
        struct, ss_crc = _regex_scan_structure(content_bytes)
        _structure_cache[content_hash] = struct
        _ss_crc_cache[content_hash] = ss_crc
        # 计算指纹
        for sd in struct.values():
            sd["fp"] = _compute_sheet_content_fp(sd["raw"], ss_crc)
        # 计算行指纹
        row_fp = {}
        for sn, sd in struct.items():
            text = sd["raw"].decode("utf-8", errors="replace")
            sn_fp = {}
            for row_m in _re_scan_row.finditer(text):
                rn = int(row_m.group(1))
                sn_fp[rn] = _compute_row_fingerprint(row_m.group(2))
            row_fp[sn] = sn_fp
        _row_fp_cache[content_hash] = row_fp
        # 清理过期缓存
        if len(_structure_cache) > _MAX_STRUCTURE_CACHE:
            for k in list(_structure_cache)[:_MAX_STRUCTURE_CACHE // 2]:
                del _structure_cache[k]
                _row_fp_cache.pop(k, None)
                _ss_crc_cache.pop(k, None)
        return struct
```

### 4.3 缓存写入规范

所有对 `_structure_cache`、`_row_fp_cache`、`_ss_crc_cache` 的写入操作必须在锁保护下进行。

---

## 5. 验证标准

### 5.1 功能验证

| 测试用例 | 预期结果 |
|----------|----------|
| 单文件多版本对比 | 正确输出差异结果 |
| 多文件并行对比 | 正确输出差异结果 |
| 重复版本多次对比 | 缓存命中，不重复解析 |

### 5.2 性能验证

| 指标 | 预期结果 |
|------|----------|
| 缓存命中率 | >= 90%（重复版本） |
| 并行效率 | 接近线性扩展 |

### 5.3 线程安全验证

通过 `threading.Event` 和多线程测试框架验证：
- 多个线程同时访问同一版本时，只有一个线程进行解析
- 所有线程最终都能获得正确的缓存数据

---

## 6. 变更记录

| 版本 | 日期 | 变更说明 | 作者 |
|------|------|----------|------|
| v1.0 | 2026-05-14 | 初始版本 | 系统 |

---

## 7. 附录

### 7.1 相关代码位置

- `svn_oneclick_compare.py` 第144-147行：缓存定义
- `svn_oneclick_compare.py` 第2246-2289行：Phase A 结构扫描
- `svn_oneclick_compare.py` 第2316-2335行：行指纹更新
- `svn_oneclick_compare.py` 第2461-2476行：线程池执行

### 7.2 参考文档

- Python threading 模块文档
- 双重检查锁定模式（Double-Checked Locking）
- 线程安全的缓存设计模式