# SVN 对比工具 v8 性能优化方案

## 问题诊断

### 执行日志分析（2026-04-22 17:22）
```
下载 40 个版本：~24s（0.6s/版本）
解析 32 对版本：~96s（3s/对）
总耗时：121s
```

### 根本原因

#### 1. 假流水线（代码第 872-873 行）
```python
dl_thread.join()  # 等待下载完全结束
all_tasks = list(iter(pair_queue.get, None))  # 然后才取任务
```
注释说"并行下载 + 解析（重叠进行）"，但实现是串行的。解析必须等全部下载完成才开始。

#### 2. 缓存未启用
- `_load_parse_from_disk()` 和 `_save_parse_to_disk()` 函数定义了但从未调用
- `_process_pair_worker_v2` 直接调用 `_parse_excel`，无缓存检查
- 相同内容重复解析，每次 ~3s

---

## 优化方案

### 方案A：启用缓存（快速修复）

**改动量：** ~20 行代码
**预计提速：** 30-50%
**风险：** 低

**实施：**
1. 在 `_process_pair_worker_v2` 中：
   - 调用 `_content_hash(bytes)` 计算哈希
   - 先查 `_parsed_cache` 内存缓存
   - 再查 `_load_parse_from_disk()` 磁盘缓存
   - 未命中才调用 `_parse_excel`
   - 解析完成后写入缓存

**注意：** 多进程环境下，worker 无法直接访问主进程的 `_parsed_cache`，需要：
- 方案A1：每个 worker 进程内部缓存（进程内复用，跨进程不复用）
- 方案A2：只用磁盘 pickle 缓存（跨进程复用，但 I/O 开销）

---

### 方案B：真流水线（中等改动）

**改动量：** ~50 行代码重构
**预计提速：** 40-60%
**风险：** 中等

**实施：**
1. 移除 `dl_thread.join()` 阻塞
2. Pool 在下载线程启动后立即启动
3. 使用 `pair_queue` 作为生产者-消费者队列：
   - 下载线程：生产任务
   - Pool workers：消费任务
4. 同步机制：`download_done` Event + queue sentinel

**伪代码：**
```python
# 启动下载线程
dl_thread.start()

# 立即启动 Pool（不等下载结束）
with Pool(processes=parse_w) as pool:
    def worker_loop():
        while True:
            task = pair_queue.get()
            if task is None:  # sentinel
                break
            result = _process_pair_worker_v2(task)
            result_queue.put(result)
    
    # 启动 workers
    for _ in range(parse_w):
        pool.apply_async(worker_loop)
    
    # 等待下载完成 + 队列清空
    dl_thread.join()
    for _ in range(parse_w):
        pair_queue.put(None)  # 每个 worker 一个 sentinel
```

---

### 方案C：全部优化（大改动）

**改动量：** ~100+ 行代码
**预计提速：** 60-80%
**风险：** 中高

**包含：**
1. 方案A（缓存）
2. 方案B（真流水线）
3. 解析器优化：
   - 改用 `openpyxl.read_only` 模式
   - 或用 `pandas.read_excel(engine='openpyxl')`
   - 或预编译正则

---

## 推荐执行顺序

1. **先实施 A1**（进程内缓存，最小改动）
2. **观察效果**，如果不够快再实施 B
3. **如果还不够**，考虑 A2（磁盘缓存跨进程复用）

---

## 待确认

- [ ] 是否需要持久化缓存（磁盘 pickle）？会增加 I/O 但跨进程复用
- [ ] 是否接受流水线重构的风险？需要充分测试
- [ ] 是否需要优化解析器本身？
