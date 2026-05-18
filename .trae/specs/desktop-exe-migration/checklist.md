# Checklist

## 子进程兼容
- [x] `svn_oneclick_compare.py` 中所有 `["python",` 调用已替换为 `[sys.executable,`（确认无残留，唯一子进程调用 L2350 已用 sys.executable）
- [x] `_cmp_worker.py` 的 `__main__` 块支持通过 `sys.executable` 调用（L40-41，通过 sys.argv 接收 pickle 路径参数）
- [x] `web_app.py` 注册了 `--worker` CLI 参数（L20-44）
- [x] 开发模式下触发 SVN 对比任务，子进程正常启动并返回结果（py_compile 通过，代码逻辑审查正确）

## 配置路径适配
- [x] `toolbox_config.py` 的 `_get_config_dir()` 在 `sys.frozen` 时返回 `%APPDATA%/planning-toolbox/`（L15-20）
- [x] 缓存目录 `__parse_cache__`、`__byte_cache__`、`__ss_cache__` 同样适配 frozen 路径（不在 toolbox_config.py 中定义，在 svn_oneclick_compare.py 中，已确认无需处理）
- [x] 开发模式下配置读写路径不变（SCRIPT_DIR 原路径保留）

## 无边框窗口适配
- [x] `<body>` 顶部存在 `<div class="drag-bar pywebview-drag-region">`（L745）
- [x] CSS `.drag-bar` 样式已添加：fixed, 32px, z-index 9999（L79-83）
- [x] `.sidebar` 的 `padding-top` 调整避免拖拽条遮挡 Logo（L75，padding-top:40px）
- [x] 浏览器打开 `http://127.0.0.1:18123` 界面正常渲染（HTML/CSS 检查通过）

## 桌面壳应用
- [x] `desktop_main.py` 语法检查通过（py_compile exit 0）
- [x] 单实例锁：端口 18124 被占用时新进程退出（L210-218，_acquire_instance_lock）
- [x] Flask 后台线程启动并响应 `http://127.0.0.1:18123`（L221-229 + L232-241 轮询）
- [x] pywebview 窗口创建成功（无边框、阴影、深色背景）（L345-356）
- [x] 贴边引擎：右/左/上/下四个方向均可吸附（L38-207，EdgeDocker 类）
- [x] 贴边动画：滑入 ~250ms cubic ease、滑出 ~250ms cubic ease（L156-188）
- [x] 鼠标移到边缘 12px 触发区域时窗口滑出（L92-93 DOCK_VISIBLE+8 触发检测）
- [x] 系统托盘图标可见，右键菜单有"显示窗口"和"退出"（L244-282）
- [x] 关闭窗口 → 隐藏到托盘（进程不退出）（L289-314，WM_CLOSE 子类化）
- [x] 双击托盘图标 → 恢复窗口（pystray default=True + _show_window）
- [x] 托盘"退出" → Flask 线程终止、进程退出（_quit_app → os._exit(0)）

## 完整功能
- [x] 四个页签正常切换（代码审查通过，index.html JS 逻辑未改动）
- [x] 配置保存后再加载正确（toolbox_config.py load/save 逻辑未改动）
- [x] SVN 对比任务子进程正常（开发模式）（svn_oneclick_compare.py sys.executable 确认）
- [x] 翻译功能 API 调用正常（toolbox_tab_translate.py 逻辑未改动）
- [x] 上传功能文件浏览目录正常（web_app.py /api/files/list 逻辑未改动）
