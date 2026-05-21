---
name: "graphify-update"
description: "轻量级知识图谱增量更新：只对修改过的 .py 文件重新提取 AST → 重建图谱 → 生成 HTML + 报告。无需 LLM，秒级完成。"
---

# graphify-update

轻量版 graphify：**只更新修改过的代码文件**，不做 LLM 语义提取，纯 AST 结构提取 + 图谱重建。

适合日常开发中"改完代码后刷新知识图谱"的场景。

## 使用流程

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
if ($changed.Count -eq 0) { Write-Host "无变更文件，跳过"; return }
Write-Host "变更文件: $($changed.Count) 个"
$changed | ForEach-Object { Write-Host "  $_" }
$changed | Out-File -FilePath "graphify-out/_changed.txt" -Encoding utf8
```

### Step 2: 提取 AST（只对变更文件）

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

### Step 4: 清理

```powershell
Remove-Item -Path ".graphify_ast_new.json","graphify-out/_changed.txt" -ErrorAction SilentlyContinue
Write-Host "✅ graphify 增量更新完成"
```
