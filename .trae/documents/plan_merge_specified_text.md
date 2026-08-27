# 计划：工作流新增步骤「指定合并文字表」(merge_specified_text)

## 成功标准
1. 工作流步骤类型新增"指定合并文字表"，设置弹窗含 6 个参数：来源路径/目标路径/提交备注/提交作者/自然日/提交路径
2. 执行后：按 备注(包含)+作者(精确)+自然日 筛选 SVN 版本 → 版本对对比(worker) 提取修改 ID → 从来源表整行复制到目标表(缺失追加、列头对应、保持值类型) → 保存一次 → bat 导出 → TortoiseSVN 提交框
3. 语义合并现有功能零改动

## 变更定位

### 1. tab-workflow.js
- L3-4 `typeCn`/`typeIcon`：加 `merge_specified_text:"指定合并文字表"` / 图标 📑
- L461 附近 `_wfStepFields` 的 `m` map：加 `merge_specified_text` 字段表单
  - 来源路径 `_fb(... "src_path" ..., "file")`（必填）
  - 目标路径 `_fb(... "tgt_path" ..., "file")`（必填）
  - 提交备注 `<input data-key="commit_msg">`（选填）
  - 提交作者 `<input data-key="commit_author">`（选填）
  - 自然日 `<input type="number" data-key="days" min="1" value="3">`（选填，默认3）
  - 提交路径 `_fb(... "commit_dir" ..., "dir", true)`（必填，多值）
- L300 附近 `required`：`merge_specified_text:["src_path","tgt_path","commit_dir"]`
- L1030 附近 `_wfAutoName`：加 `merge_specified_text` 分支（取目标路径文件名/父目录）

### 2. web_app.py
- L1685 后：`elif stype == "merge_specified_text": ok = _exec_merge_specified_text(step, _put, task_id)`
- 新增 `_exec_merge_specified_text(step, put, task_id)`（放在 _exec_consolidate 附近）：
  1. 解析参数：src_path/tgt_path/commit_msg/commit_author/days(默认3,min1)/commit_dir(列表)
  2. svn update 目标路径 WC（_svn_update_with_cleanup，svn info 找 wc-root）
  3. svn update 来源表 WC
  4. svn info 来源表 URL → `svn_log(url, start, end, author, keyword)` 筛版本（start = 今天0点-(days-1)天）
  5. 无命中 → 提示跳过返回
  6. 版本对：每命中版本 + 其实际前一版本（复用 toolbox_texts_merge 的 rev_to_idx 逻辑）
  7. `step3_download_and_compare(source_url=来源表URL的目录, file_pairs={文件名: 版本对})` → 变化行（worker 机制）
  8. 提取修改 ID 集合（sheet + ID）
  9. openpyxl 打开来源表（已 update 的最新内容）与目标表：按 ID 整行复制（列头名对应；值类型保持 openpyxl 原生类型；目标无 ID 追加到 sheet 末尾；源多列跳过、目标独有列保留）
  10. `wb_tgt.save()` 一次
  11. 导出：跑目标表目录 `服务器/客户端文字表导出_替换文本引用.bat`（复用 _exec_export_text 的 bat 执行逻辑）
  12. TortoiseSVN 提交框（commit_dir 多路径，复用 _exec_consolidate 弹框逻辑）

### 3. 新增 helper
- `_copy_rows_by_id(wb_src, wb_tgt, id_set_by_sheet, title_rows, id_col, put)`：按 ID 整行复制核心逻辑（放 web_app.py 或独立模块）

## 复用清单（不改动）
- `toolbox_merge.svn_log`（author+keyword 筛选）
- `svn_oneclick_compare.step3_download_and_compare`（_cmp_worker 子进程池对比）
- `toolbox_texts_merge` 的版本对构建逻辑
- `_svn_update_with_cleanup` / bat 导出 / TortoiseSVN 弹框

## 实施顺序
1. web_app.py 后端 `_exec_merge_specified_text` + `_copy_rows_by_id` + 路由
2. tab-workflow.js 步骤 UI（typeCn/图标/字段/required/autoName）
3. 语法自检 + 逻辑验证（构造迷你两表测整行复制；svn_log 筛选用真实数据）

## 验证
- py_compile + JS 括号平衡
- 迷你表：整行复制/缺失追加/列头对应/值类型保持
- svn_log 按 作者+备注+自然日 命中真实版本
