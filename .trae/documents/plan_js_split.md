# JS 按需拆包 + Terser 压缩 实施计划

## 变更清单

### Task 1: 分析 app.js 函数归属
- 扫描 app.js 所有 `function` 定义
- 标记每个函数所属的页签或框架

### Task 2: 拆分为独立文件
- **core.js**: 框架代码 + SVN 页签（启动必需）
- **tab-merge.js**: 语义合并
- **tab-upload.js**: 复制合并
- **tab-workflow.js**: 工作流
- **tab-translate.js**: 翻译
- **tab-textcheck.js**: 文字检测
- **tab-prefab.js**: 修改预制

### Task 3: buildTab 改为动态加载
- `buildTab(key)` 中 `case X: buildXTab(panel)` 改为：检查页签函数是否存在，不存在则动态加载对应 `.js` 文件

### Task 4: 更新 HTML
- `<script defer src="/api/static/core.js">` 加载框架
- 移除 app.js 引用

### Task 5: Terser 压缩
- 安装 terser
- 构建步骤：对每个 .js 生成 .min.js，Flask 根据调试模式选择加载

### Task 6: 验证
- 启动后 SVN 页签正常
- 切换其他页签时动态加载对应 JS
- Terser 压缩后体积显著减少
