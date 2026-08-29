# 图集引用清理规格

## 目标

在「修改预制」页签新增「图集引用清理」模式，将 prefab 引用的 Atlas Sprite 原图迁移到 `Client\Assets\GameAssets\UI` 下其他已有图集目录；用户手动刷新 Unity 并打图集后，解析 `Client\Assets\Resources\UI\Atlas` 的最终 GUID/fileID，预览并确认修正 prefab。

## 输入与扫描

- 仅接受 `Client\Assets\Resources\UI\Prefabs` 或其子目录中的文件夹。
- 递归扫描 `.prefab`，只处理字段名精确为 `m_Sprite` 的外部引用。
- `m_Texture` 和其他字段不展示、不统计、不迁移、不修改。
- 用 Atlas `.meta` 的 `internalIDToNameTable`、`fileIDToRecycleName`、`nameFileIdTable` 解析 GUID/fileID 与 Sprite 名。
- 缺失或歧义项只标记，不猜测。

## 界面

- 左栏：prefab 列表，按不同引用图集数降序。
- 右栏：列出 `GameAssets\UI` 下全部已有图集目录；当前 prefab 已引用组置顶展开；支持拖单图或选中源组到其他已有组。
- 下栏：仅显示当前 prefab 的迁移预览；可修改目标名或删除计划。
- 同一 prefab 同一原图只能有一个目标，重新拖拽覆盖；不同 prefab 互不影响。
- 相同原图和目标图集共享一次物理复制，名称跨关联 prefab 联动。

## 复制

- 复制 PNG 和对应 `.meta`，不修改 `.meta` 内容、不生成 GUID。
- 数字前缀替换为目标图集数字；`H<数字>_` 保留 H；无数字前缀不变。
- 自动冲突追加 `_renameN`；手动重名标红并禁止复制。
- 每项使用临时文件发布 PNG/meta 文件对；失败项可重试，成功项不重复复制；单项失败不阻断其他项。

## 最终解析与修改

- 复制后等待用户手动在 Unity 刷新并打图集。
- 点击「已打图集，解析最终引用」后重新扫描最终 Atlas `.meta`，按目标组和最终名称取得唯一 GUID/fileID。
- 展示解析预览后，点击「确认修改预制」。
- 每个 prefab 重新校验旧 GUID/fileID 命中次数；不一致则整份跳过，其他 prefab 继续。
- 仅原子替换计划内 `m_Sprite` 的 GUID/fileID，保留 BOM、换行、缩进和其余内容；不备份，依赖 SVN。

## 记录与恢复

- 每批在输入预制根目录生成一份 `图集引用迁移_YYYYMMDD_HHMMSS.txt`，UTF-8 BOM，按 prefab 分组。
- 草稿保存在 `%APPDATA%\planning-toolbox\atlas-migration-drafts\`。
- 重启可继续；放弃草稿不删除已复制文件；全部完成并成功生成 TXT 后自动删除草稿。
