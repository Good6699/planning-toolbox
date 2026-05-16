# Checklist: SVN 输入框 UX 增强

- [x] `/api/svn/detect` 后端路由实现且可正确处理 SVN 目录、非 SVN 目录、不存在的路径
- [x] `svn_url` 拖入 SVN 文件夹后输入框填入远程 URL
- [x] `svn_url` 拖入非 SVN 文件夹后显示错误提示
- [x] `svn_url` 旁边 "打开" 按钮可见，本地路径点按打开资源管理器，URL 则静默忽略
- [x] `svn_url` 失焦后内容自动保存到 `svn_urls`，去重置顶
- [x] `svn_output` 失焦后内容自动保存到 `output_dir_history`，去重置顶
- [x] 失焦自动保存与已有 Enter 键保存不产生重复条目
- [x] 日期选择器日历图标在深色背景下清晰可见
- [x] `python -m py_compile web_app.py` 语法检查通过
- [x] `graphify update` 执行通过
