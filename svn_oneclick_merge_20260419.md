# SVN 一键对比工具合并完成

**时间**: 2026-04-19 09:18

## 任务

合并三个 SVN 工具脚本为一个：

1. **脚本1**: `SVN查询工具.bat` + `svn_query.py` - 按日期/关键词查询 SVN 提交记录
2. **脚本2**: `SVN查找上一版本.bat` + `svn_find_prev.py` - 查找每个版本的上一版本
3. **脚本3**: `_safe_v8.bat` + `svn_compare_excel_v8.py` - 下载解析对比 Excel

## 输出

### Python 脚本
- **文件**: [svn_oneclick_compare.py](file:///C:/Users/admin/.qclaw/workspace/svn_oneclick_compare.py)
- **功能**: 合并了查询 → 查上一版本 → 对比三个步骤

### 批处理启动器
- **文件**: [SVN一键对比.bat](file:///C:/Users/admin/.qclaw/workspace/SVN一键对比.bat)
- **编码**: GBK（兼容 Windows cmd.exe）

## 使用方法

```batch
SVN一键对比.bat
```

按提示输入：
1. SVN URL（必填）
2. 开始日期（格式 YYYY-MM-DD）
3. 结束日期（格式 YYYY-MM-DD）
4. 关键词（可选，多个用空格分隔）
5. 提交者过滤（可选）
6. 输出文件路径（默认 workspace 目录）
7. 并发数（可选）

## 输出格式

与 v8 版本相同的 Excel 格式：
- 列：Sheet, ID, SC, SubstituteId, 当前版本, 上一版本, 操作类型
- 新增行：绿色背景
- 修改行：黄色背景
- 按 Sheet 分组，ID 按末尾数字降序排列

## 参数说明

```bash
python svn_oneclick_compare.py -u <SVN_URL> -s <开始日期> -e <结束日期> -o <输出xlsx>
  [-k 关键词] [--match-all] [--author 提交者]
  [-w 下载并发数] [-p 解析并发数]
```

## 技术细节

1. **SVN 查询**: 使用 `svn log --xml` 获取提交记录
2. **上一版本**: 通过 `svn log -r {cur}:1` 获取最近两条记录
3. **Excel 解析**: regex 直接解析 XML（比 openpyxl 快 3.7x）
4. **并行处理**: ThreadPoolExecutor 下载 + ProcessPoolExecutor 解析
5. **缓存**: LRU 缓存版本数据，避免重复下载
