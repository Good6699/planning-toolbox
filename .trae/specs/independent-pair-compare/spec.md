# 独立对比 Spec

## Why
`smart-sheet-parsing` 改造后发现 Phase 2 仍然慢（10-12 分钟），根因是 `_parse_excel_with_cache` 的三级缓存机制在 32 个版本对的场景下几乎无法命中（3/64 = 4.7%），反而引入：
- 磁盘写入 100% 失败（58 个 sheet 编号拼接导致文件名超 Windows 260 字符限制），每次失败都有时间开销
- 8 线程竞争 `_parse_cache_lock (RLock)` 每秒 n 次
- 解析结果累积在内存不释放

用户方案：每对版本独立处理，对比完立即释放内存。不经过共享缓存，不存在锁竞争，不存在磁盘写入。

## What Changes
- `_cmp_task` 内部直接调用 `_parse_excel_lxml`，跳过 `_parse_excel_with_cache` 的三级缓存
- Phase 2 并行线程不再访问 `_parsed_cache` / `_cache_hits` / `_cache_misses` / `_parse_cache_lock`
- `_save_parse_to_disk` 不再被 Phase 2 路径调用，消灭 100% 磁盘写入错误
- `only_sheets` 逻辑保留（决定解析多少 sheet）
- `_parse_excel_with_cache` 代码不删不改（其他调用方如 `_process_pair_bytes_worker` 仍依赖它）
- `_parse_cache_lock` / `_parsed_cache` 全局变量保留不删（模块级缓存仍供 `warm_parse_cache` 等使用）
- 不改 `_compare_pair` / `_dedupe_by_id` / `write_excel` / Phase 1

## Impact
- Affected specs: `smart-sheet-parsing`, `zip-precheck-parallel-compare`
- Affected code: `svn_oneclick_compare.py` — `_cmp_task` 内部函数

## MODIFIED Requirements

### Requirement: Phase 2 每对独立解析
Phase 2 的 `_cmp_task` SHALL 直接调用 `_parse_excel_lxml`，不经过 `_parse_excel_with_cache` 的三级缓存。

#### Scenario: 独立解析不写磁盘
- **WHEN** `_cmp_task` 执行解析
- **THEN** 直接调用 `_parse_excel_lxml(raw_bytes, rev, ...)`
- **AND** 不调用 `_parse_excel_with_cache`
- **AND** 不调用 `_save_parse_to_disk`
- **AND** 不访问 `_parsed_cache` / `_parse_cache_lock` / `_cache_hits` / `_cache_misses`

#### Scenario: only_sheets 仍生效
- **WHEN** ZIP 预检返回 `changed_sheets={"sheet27"}`
- **THEN** `_parse_excel_lxml(only_sheets={"sheet27"})` 只解析 1 个 sheet
- **AND** 行为与改造前完全一致

#### Scenario: 对比完立即释放内存
- **WHEN** `_cmp_task` 返回 diff 结果
- **THEN** `cur_parsed` 和 `prv_parsed` 离开作用域，由 Python GC 自动回收
- **AND** 不走 `_trim_cache` 等累积逻辑

#### Scenario: 结果与改造前一致
- **WHEN** `_cmp_task` 完成对比
- **THEN** `diff_rows`、`hdr`、`so` 与改造前完全相同
- **AND** 合并到 `all_file_results` 的逻辑不变

## REMOVED Requirements

### Requirement: Phase 2 使用共享解析缓存
**Reason**: 32 对场景下缓存命中率 3/64（4.7%），收益微不足道。磁盘写入 100% 失败引入额外开销，锁竞争进一步拖慢。
**Migration**: `_parse_excel_with_cache` 代码保留，其他调用方（`_process_pair_bytes_worker` 等）不受影响。
