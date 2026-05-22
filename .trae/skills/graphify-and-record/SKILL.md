---
name: "graphify-and-record"
description: "一键完成知识图谱增量更新 + 记录经验到 MEMORY.md + 本地 Git 提交。改完代码后调用此 skill，依次执行：检测变更→AST提取→图谱合并→经验记录→Git提交。"
---

# graphify-and-record — 图谱更新 + 经验记录 + Git 提交

合并 `graphify-update` 和 `record-and-commit` 两个技能，一次调用完成：
1. 检测代码变更，增量更新知识图谱
2. 将经验教训写入 MEMORY.md
3. 提交本地 Git

## 触发时机

- 改完代码后需要刷新知识图谱时
- 解决复杂问题后需要记录经验并提交时
- 用户说 `记下来` / `提交` / `保存` / `commit` / `save` 时
- 修改了 `.py` / `.html` / `.js` / `.ts` / `.md` 等正式文件后

## 执行步骤

### Step 1: 检测变更文件

```powershell
$MANIFEST = "graphify-out/manifest.json"
$changed = @()
if (Test-Path $MANIFEST) {
    $m = Get-Content $MANIFEST | ConvertFrom-Json
    Get-ChildItem -Recurse -Filter *.py -Path . | ForEach-Object {
        $rel = $_.FullName
        $current = ($_ | Get-FileHash -Algorithm MD5).Hash
        if ($m.PSObject.Properties.Name -contains $rel) {
            $cached = $m.$rel.hash
            if ($current -ne $cached) { $changed += $rel }
        } else {
            $changed += $rel
        }
    }
} else {
    $changed = Get-ChildItem -Recurse -Filter *.py -Path . | ForEach-Object { $_.FullName }
}
if ($changed.Count -eq 0) { Write-Host "无变更文件，跳过图谱更新" } else {
    Write-Host "变更文件: $($changed.Count) 个"
    $changed | ForEach-Object { Write-Host "  $_" }
    $changed | Out-File -FilePath "graphify-out/_changed.txt" -Encoding utf8
}
```

### Step 2: 提取 AST（只对变更文件）

仅在 Step 1 检测到变更时执行：

```powershell
$PY = Get-Content graphify-out/.graphify_python -ErrorAction SilentlyContinue
if (-not $PY) { $PY = "python" }
$changedFiles = Get-Content graphify-out/_changed.txt -Encoding utf8 | Where-Object { $_ -ne "" }
$changedList = ($changedFiles -join " ")
& $PY -c "
import sys, json, hashlib
from pathlib import Path
from graphify.extract import collect_files, extract

changed = [Path(f.strip()) for f in open('graphify-out/_changed.txt').read().strip().splitlines() if f.strip()]
code_files = []
for f in changed:
    if f.suffix in ('.py','.ts','.js','.go','.rs','.java','.cpp','.c','.rb','.swift','.kt','.cs'):
        code_files.append(f)

if code_files:
    result = extract(code_files, parallel=False)
    Path('.graphify_ast_new.json').write_text(json.dumps(result, indent=2))
    print(f'AST: {len(result[\"nodes\"])} nodes, {len(result[\"edges\"])} edges from {len(code_files)} files')
else:
    Path('.graphify_ast_new.json').write_text(json.dumps({'nodes':[],'edges':[],'input_tokens':0,'output_tokens':0}))
    print('No code files changed')
"
```

### Step 3: 合并到现有图谱

仅在 Step 1 检测到变更时执行：

```powershell
& $PY -c "
import json, networkx as nx
from networkx.readwrite import json_graph
from pathlib import Path

old_path = Path('graphify-out/graph.json')
new_ast = json.loads(Path('.graphify_ast_new.json').read_text())

if old_path.exists() and new_ast['nodes']:
    old_data = json.loads(old_path.read_text())
    G = json_graph.node_link_graph(old_data, edges='links')

    from graphify.build import build_from_json
    G_new = build_from_json(new_ast)
    G.add_nodes_from(G_new.nodes(data=True))
    G.add_edges_from(G_new.edges(data=True))

    from graphify.cluster import cluster, score_all
    from graphify.analyze import god_nodes, surprising_connections, suggest_questions
    from graphify.report import generate
    from graphify.export import to_json
    from graphify.detect import detect
    from graphify.detect import save_manifest

    communities = cluster(G)
    cohesion = score_all(G, communities)
    detection = detect(Path('.'))
    tokens = {'input': 0, 'output': 0}
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    labels = {cid: f'Community {cid}' for cid in communities}
    questions = suggest_questions(G, communities, labels)

    report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, '.', suggested_questions=questions)
    Path('graphify-out/GRAPH_REPORT.md').write_text(report)
    to_json(G, communities, 'graphify-out/graph.json')

    save_manifest(detection['files'])

    from graphify.export import to_html
    if G.number_of_nodes() <= 5000:
        to_html(G, communities, 'graphify-out/graph.html', community_labels=labels or None)

    print(f'Updated: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(communities)} communities')
elif new_ast['nodes']:
    from graphify.build import build_from_json
    from graphify.cluster import cluster, score_all
    from graphify.analyze import god_nodes, surprising_connections, suggest_questions
    from graphify.report import generate
    from graphify.export import to_json, to_html
    from graphify.detect import detect, save_manifest

    G = build_from_json(new_ast)
    communities = cluster(G)
    cohesion = score_all(G, communities)
    detection = detect(Path('.'))
    tokens = {'input': 0, 'output': 0}
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    labels = {cid: f'Community {cid}' for cid in communities}
    questions = suggest_questions(G, communities, labels)

    report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, '.', suggested_questions=questions)
    Path('graphify-out/GRAPH_REPORT.md').write_text(report)
    to_json(G, communities, 'graphify-out/graph.json')
    save_manifest(detection['files'])
    if G.number_of_nodes() <= 5000:
        to_html(G, communities, 'graphify-out/graph.html', community_labels=labels or None)

    print(f'New graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges')
else:
    print('No new nodes - graph unchanged')
"
```

### Step 4: 清理（图谱临时文件）

```powershell
Remove-Item -Path ".graphify_ast_new.json","graphify-out/_changed.txt" -ErrorAction SilentlyContinue
Write-Host "✅ 图谱增量更新完成"
```

### Step 5: 记录经验到 MEMORY.md（有经验需要记录时）

如果有值得记录的经验教训（问题根因、修复方案、架构决策等），追加到 `MEMORY.md` 的 `## 经验与决策` 节，格式为：

```
### 问题简短标题
- **场景**：一句话描述
- **根因**：……
- **解决方案**：改了什么、怎么改的
- **涉及文件**：[filename](file:///path)
```

总结根因和解决方案即可，不用问用户确认。

### Step 6: 提交本地 Git（有代码变更时）

```powershell
git status
git add <files>
git commit --no-verify -m "<type>: <中文描述>"
```

- type 用 `fix` / `feat` / `refactor` / `style` / `docs` / `chore` 之一
- 描述用中文、祈使句
- 提交前先确认变更文件列表

### Step 7: 告知用户

一句话告知完成：图谱更新结果 + 记录/提交情况。

## 注意事项

- Step 1-4（图谱更新）仅在检测到文件变更时执行，无变更则跳过
- Step 5-6（记录+提交）可根据情况选择性执行，不是每次都必须
- 不要记琐碎操作，只记有价值的经验和教训
- Git 提交使用 `--no-verify`
- 当前分支 `web-optimal`，纯本地版本管理
