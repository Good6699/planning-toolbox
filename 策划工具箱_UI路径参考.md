# 策划工具箱 UI 路径引用

与 AI 沟通 UI 位置时，使用 `页签 > 区域 > 卡片 > 控件` 格式。

---

## 用法速记

```
app > S > nav.svn       → 点击SVN记录页签
svn > L > 地址 > URL    → SVN页签左列地址卡的URL输入框
@run-svn                → SVN页签的「开始执行」按钮
tr > R > API > Key      → 翻译页签右侧API Key输入框
wf > F > 工作流.0       → 工作流页签第一个工作流
merge > F > 版本.1      → 语义合并第二个版本项
upload > L > 文件.3     → 复制合并左列第4个文件
```

---

## 一、全局 `app`

| 路径 | CSS/HTML | 含义 |
|------|----------|------|
| `app > T > 标题` | `#page_title` | 顶栏当前页标题 |
| `app > T > 副标题` | `#page_subtitle` | 顶栏副标题 |
| `app > T > 状态` | `#status_bar` | 状态指示 [● 系统空闲] |
| `app > T > 关闭` | `#close_btn` | ✕ 关闭到托盘按钮 |
| `app > T > 缩放警告` | `#zoom_warning` | 浏览器缩放异常提示 |
| `app > S > logo` | `.logo` | 左侧Logo区域 |
| `app > S > nav.svn` | `.nav-btn[data-key="svn"]` | 导航-SVN记录 |
| `app > S > nav.merge` | `.nav-btn[data-key="merge"]` | 导航-语义合并 |
| `app > S > nav.upload` | `.nav-btn[data-key="upload"]` | 导航-复制合并 |
| `app > S > nav.wf` | `.nav-btn[data-key="workflow"]` | 导航-工作流 |
| `app > S > nav.tr` | `.nav-btn[data-key="translate"]` | 导航-翻译 |

---

## 二、SVN 记录 `svn`

| 路径 | 控件 | 含义 |
|------|------|------|
| `svn > L > 地址 > URL` | `#svn_url` | SVN URL 输入框 |
| `svn > L > 地址 > 浏览` | `@browse-svn-url` | 浏览本地副本 |
| `svn > L > 地址 > 打开` | `@open-svn-url` | 打开文件夹 |
| `svn > L > 设置 > 模式.summary` | `#svn_mode_group` | 修改摘要模式 |
| `svn > L > 设置 > 模式.compare` | `#svn_mode_group` | 对比Excel模式 |
| `svn > L > 设置 > 模式.export` | `#svn_mode_group` | 导出文件模式 |
| `svn > L > 设置 > 起始日期` | `#svn_start` | 日期范围起始 |
| `svn > L > 设置 > 结束日期` | `#svn_end` | 日期范围结束 |
| `svn > L > 设置 > 今日` | `@svn-today` | 今日按钮 |
| `svn > R > 过滤 > 关键词` | `#svn_keyword` | 关键词过滤 |
| `svn > R > 过滤 > 作者` | `#svn_author` | 作者过滤 |
| `svn > R > 过滤 > 输出目录` | `#svn_output` | 输出目录路径 |
| `svn > R > 过滤 > 输出浏览` | `@browse-svn-output` | 输出浏览按钮 |
| `svn > R > 过滤 > 输出打开` | `@open-svn-output` | 输出打开按钮 |
| `svn > R > 过滤 > 高级` | `@svn-advanced` | ⚙ 高级设置 |
| `svn > F > 执行` | `@run-svn` | 🚀 开始执行 |
| `svn > F > 日志` | `#svn_log` | 执行日志区 |
| `svn > F > 清除缓存` | `@svn-clear-cache` | 清除缓存按钮 |

### SVN 高级设置弹窗（点击⚙弹出）

| 路径 | 控件 | 含义 |
|------|------|------|
| `svn > 高级 > 用户名` | `#adv_svn_user` | SVN 用户名 |
| `svn > 高级 > 密码` | `#adv_svn_pass` | SVN 密码 |
| `svn > 高级 > 排除目录` | `#adv_exclude_dirs` | 排除目录（逗号分隔） |
| `svn > 高级 > 文件名` | `#adv_cmp_file` | 文件名输入框 |
| `svn > 高级 > 保存预设` | `@adv-save-preset` | 保存按钮 |
| `svn > 高级 > 删除预设` | `@adv-del-preset` | 删除按钮 |
| `svn > 高级 > 关闭` | `@close-adv-settings` | ✕ 关闭按钮 |

---

## 三、语义合并 `merge`

| 路径 | 控件 | 含义 |
|------|------|------|
| `merge > F > 源SVN地址` | `#merge_source` | 源SVN URL |
| `merge > F > 目标路径` | `#merge_target` | 本地工作副本路径 |
| `merge > F > 起始日期` | `#merge_start` | 时间范围起始 |
| `merge > F > 结束日期` | `#merge_end` | 时间范围结束 |
| `merge > F > 作者` | `#merge_author` | 提交者过滤 |
| `merge > F > 关键词` | `#merge_keyword` | 备注关键词 |
| `merge > F > 筛选查询` | `@merge-query` | [筛选查询] |
| `merge > F > 开始合并` | `@merge-run` | [开始合并] |
| `merge > F > 版本总数` | `#merge_version_count` | 显示 "共N个版本" |
| `merge > F > 已选版本数` | `#merge_version_count_bottom` | 底部显示 "已选 N 个" |
| `merge > F > 版本列表` | `#merge_version_list` | 版本列表容器 |
| `merge > F > 版本.N` | `.merge-version-item:nth(N)` | 第N个版本项(0起) |
| `merge > F > 版本.N > 复选框` | `.merge-version-item input[checkbox]` | 版本复选框 |
| `merge > F > 版本.N > 版本号` | `.merge-version-item .rev` | 显示 r12345 |
| `merge > F > 版本.N > 日期` | `.merge-version-item .date` | 提交日期 |
| `merge > F > 版本.N > 作者` | `.merge-version-item .author` | 提交者 |
| `merge > F > 版本.N > 备注` | `.merge-version-item .msg` | 提交备注 |
| `merge > F > 版本.全选` | `@merge-ver-select-all` | 版本全选 |
| `merge > F > 版本.反选` | `@merge-ver-select-invert` | 版本反选 |
| `merge > F > 版本.清空` | `@merge-ver-select-clear` | 版本清空 |
| `merge > F > 文件提示` | `#merge_file_hint` | 提示文字（如"请先选择版本"） |
| `merge > F > 已选文件数` | `#merge_file_count_bottom` | 显示 "已选 N 个文件" |
| `merge > F > 文件列表` | `#merge_file_list` | 变更文件列表容器 |
| `merge > F > 文件.N` | `.merge-file-item:nth(N)` | 第N个文件项(0起) |
| `merge > F > 文件.N > 复选框` | `.merge-file-item input[checkbox]` | 文件复选框 |
| `merge > F > 文件.N > 操作` | `.merge-file-item .action-tag` | [A/M/D] 操作标记 |
| `merge > F > 文件.N > 文件名` | `.merge-file-item .file-name` | 文件名 |
| `merge > F > 文件.N > 路径` | `.merge-file-item .file-dir` | 文件目录路径 |
| `merge > F > 文件.全选` | `@merge-select-all` | 文件全选 |
| `merge > F > 文件.反选` | `@merge-select-invert` | 文件反选 |
| `merge > F > 文件.清空` | `@merge-select-clear` | 文件清空 |
| `merge > F > 排除设置` | `@merge-file-settings` | ⚙ 排除路径设置 |
| `merge > F > 筛选按钮` | `#merge_query_btn` | [筛选查询] 按钮 |
| `merge > F > 合并按钮` | `#merge_run_btn` | [开始合并] 按钮 |
| `merge > F > 日志` | `#merge_log` | 执行日志 |

---

## 四、复制合并 `upload`

| 路径 | 控件 | 含义 |
|------|------|------|
| `upload > L > 源目录 > 输入` | `#upload_src` | 源目录路径 |
| `upload > L > 源目录 > 浏览` | `@browse-upload-src` | 浏览按钮 |
| `upload > L > 源目录 > 刷新` | `@refresh-files` | 刷新文件列表 |
| `upload > L > 文件列表` | `#upload_files` | 文件列表容器 |
| `upload > L > 文件.全选` | `@select-all` | 全选按钮 |
| `upload > L > 文件.取消全选` | `@select-none` | 取消全选 |
| `upload > L > 文件.N` | `.file-item:nth(N)` | 第N个文件(0起) |
| `upload > L > 文件.N > 复选框` | `.file-item input[checkbox]` | 文件复选框 |
| `upload > L > 文件.N > 图标` | `.file-item` 内图标 | 📁目录 / 📄文件 |
| `upload > L > 文件.N > 名称` | `.file-item` 内文字 | 文件名 |
| `upload > L > 文件.N > 大小` | `.file-item` 内大小 | 文件大小 |
| `upload > L > 文件.N > 日期` | `.file-item` 内日期 | 修改日期 |
| `upload > R > 目标 > 输入` | `#upload_tgt` | SVN目标目录 |
| `upload > R > 目标 > 浏览` | `@browse-upload-tgt` | 浏览按钮 |
| `upload > F > 执行` | `@run-upload` | 🚀 上传到SVN |
| `upload > F > 日志` | `#upload_log` | 执行日志 |
| `upload > F > 清理changelist` | `@clear-changelist` | 清理changelist |

---

## 五、工作流 `wf`

### 列表项

| 路径 | 含义 |
|------|------|
| `wf > F > 列表` | 工作流列表容器 |
| `wf > F > 工作流.N` | 第N个工作流（从0开始） |
| `wf > F > 工作流.N > 名称` | 工作流名称（可点击改名） |
| `wf > F > 工作流.N > 复选框` | 全选/取消所有步骤 |
| `wf > F > 工作流.N > 展开` | ▶ 展开/折叠箭头 |
| `wf > F > 工作流.N > 播放` | ▶ 执行本工作流 |
| `wf > F > 工作流.N > 复制` | 📋 复制工作流 |
| `wf > F > 工作流.N > 删除` | ✕ 删除工作流 |
| `wf > F > 工作流.N > 步骤.M` | 第M个步骤（从0开始） |
| `wf > F > 工作流.N > 步骤.M > 复选框` | 步骤复选框 |
| `wf > F > 工作流.N > 步骤.M > 设置` | ⚙ 步骤设置 |
| `wf > F > 工作流.N > 步骤.M > 删除` | ✕ 删除步骤 |
| `wf > F > 工作流.N > 添加步骤` | + 添加步骤（固定在步骤列表末尾，点击弹出类型选择） |
| `wf > F > 步骤类型选择` | 动态弹出菜单，选择步骤类型 |

### 步骤类型（步骤旁边的彩色标签）

```
📄 export_text      导出文字表   蓝色
📤 upload_svn       上传SVN      绿色
🔗 merge_table      合并表格     橙色
🌐 merge_translation合并翻译     紫色
⚠  export_error_code导出错误码   红色
🔒 lock_svn         锁定SVN      深橙
🔓 unlock_svn       解锁SVN      绿色
📂 open_tables      打开表格     青色
```

### 工具栏与日志

| 路径 | 控件 | 含义 |
|------|------|------|
| `wf > F > 新建` | `@wf-create` | [+ 新建] |
| `wf > F > 执行选中` | `@run-workflow` | 🚀 执行选中步骤 |
| `wf > F > 日志` | `#wf_log` | 执行日志 |
| `wf > F > 弹窗` | `#wf_modal_overlay` | 步骤设置弹窗 |
| `wf > F > 弹窗 > 保存` | `#wf_modal_save` | 弹窗保存按钮 |
| `wf > F > 弹窗 > 取消` | `#wf_modal_cancel` | 弹窗取消 |

### 弹窗字段（点击⚙设置后弹出）

按步骤类型不同，弹窗内字段如下：

| 步骤类型 | 字段 | 说明 |
|----------|------|------|
| `export_text` | 主文件路径, 工具目录, 语言列表 | 逗号分隔 |
| `upload_svn` | 源目录 | 逗号分隔多个 |
| `merge_table` | 输入文件, 输出目录, 合并前缀, 标题行, ID列 | 逗号分隔 |
| `merge_translation` | 翻译文件, 原始文件, Sheet名称 | 文件+文本 |
| `export_error_code` | 根目录, 语言代码 | 目录+文本 |
| `lock_svn` | 目标文件路径, 更新目录, 锁定消息 | 逗号分隔 |
| `unlock_svn` | 目标文件路径, 更新目录, 解锁消息 | 逗号分隔 |
| `open_tables` | 文件路径 | 逗号分隔多个 |

---

## 六、翻译 `tr`

| 路径 | 控件 | 含义 |
|------|------|------|
| `tr > L > 文件 > 路径` | `#tr_src` | 翻译文件路径 |
| `tr > L > 文件 > 浏览` | `@browse-tr-src` | 浏览文件 |
| `tr > L > 文件 > 参考` | `#tr_ref` | 参考文件 |
| `tr > L > 文件 > 参考浏览` | `@browse-tr-ref` | 浏览参考 |
| `tr > L > 语言 > 源语言` | `#tr_src_lang` | 源语言列 |
| `tr > L > 语言 > 高级` | `@tr-lang-adv-settings` | ⚙ 语言ID高级设置 |
| `tr > L > 语言 > 目标.N` | `#tr_tgt_langs .checkbox` | 第N个目标语言 |
| `tr > L > 执行` | `@run-translate` | 🚀 开始翻译 |
| `tr > R > API > URL` | `#tr_api_url` | API URL |
| `tr > R > API > Key` | `#tr_api_key` | API Key |
| `tr > R > API > 模型` | `#tr_model` | 模型名 |
| `tr > R > 输出 > 目录` | `#tr_out` | 输出目录 |
| `tr > R > 输出 > 浏览` | `@browse-tr-out` | 浏览输出 |
| `tr > R > 输出 > Prompt` | `#tr_prompt` | 翻译Prompt |
| `tr > R > 输出 > 批处理量` | `#tr_batch` | 批处理量数字 |
| `tr > F > 日志` | `#tr_log` | 执行日志 |

### 翻译语言ID高级设置弹窗（点击⚙弹出）

| 路径 | 控件 | 含义 |
|------|------|------|
| `tr > 语言高级 > 语言.N > 名称` | `.tr-lang-name` 第N行 | 语言名称 |
| `tr > 语言高级 > 语言.N > 匹配ID` | `.tr-lang-ids` 第N行 | 匹配ID（逗号分隔） |
| `tr > 语言高级 > 语言.N > 删除` | `@tr-lang-del-row` | ✕ 删除该行 |
| `tr > 语言高级 > 新增` | `@tr-lang-add-row` | [+ 新增语言] |
| `tr > 语言高级 > 保存` | `@tr-lang-save-adv` | 保存按钮 |
| `tr > 语言高级 > 取消` | `@tr-lang-close-adv` | 取消/关闭 |

---

## 交流示例

```
你: wf > F > 工作流.0 > 步骤.2 > 设置 弹窗里加个字段
我: 收到，给第一个工作流的第三个步骤设置弹窗加字段

你: svn > L > 设置 > 模式.compare 点了没反应
我: 检查对比Excel模式切换逻辑

你: tr > R > API > Key 显示明文了
我: 改成 password 类型

你: merge > F > 版本.0 的复选框跟文件列表不同步
我: 修复版本0选中后文件列表的联动

你: upload > L > 文件.5 > 复选框 勾不上
我: 检查第6个文件复选框事件

你: @run-svn 按钮灰的
我: 检查开始执行按钮的disabled状态
```
