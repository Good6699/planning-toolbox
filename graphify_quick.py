"""
graphify_quick.py — 策划工具箱知识图谱一键构建
用法:
  python graphify_quick.py              # 增量更新（默认，只处理变更文件）
  python graphify_quick.py --full      # 全量重建
  python graphify_quick.py --no-viz    # 跳过 HTML 生成
  python graphify_quick.py --full --no-viz
"""
import json, sys, time, argparse, hashlib, os
from pathlib import Path
from graphify.detect import detect, save_manifest, load_manifest, classify_file, FileType
from graphify.extract import collect_files, extract as ast_extract
from graphify.cache import check_semantic_cache, save_semantic_cache
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.analyze import god_nodes, surprising_connections, suggest_questions
from graphify.report import generate
from graphify.export import to_json, to_html
from networkx.readwrite import json_graph
import networkx as nx

OUT = Path('graphify-out')
OUT.mkdir(exist_ok=True)

QUICK_DIRS = [
    'templates',
    'toolbox_core',
    'skills',
    '.trae/skills',
    '.trae/rules',
    '.workbuddy/memory',
    '自动学习',
]
QUICK_ROOT_FILES = {'AGENT.md', 'MEMORY.md', 'TOOLS.md', 'USER.md', 'CLAUDE.md'}
QUICK_ROOT_EXTS = {'.py', '.js', '.html', '.css', '.bat', '.ps1'}
EXCLUDE_DIRS = {
    'graphify-out', '.git', '.svn', '__pycache__', '.pytest_cache', '.mypy_cache',
    '.ruff_cache', 'node_modules', '.venv', 'venv', 'dist', 'build', 'release',
}
EXCLUDE_SUFFIXES = {
    '.pyc', '.log', '.exe', '.zip', '.7z', '.png', '.jpg', '.jpeg', '.gif', '.webp',
    '.bmp', '.svg', '.mp4', '.mov', '.avi', '.xlsx', '.xlsm', '.xls', '.pdf',
}
EXCLUDE_PREFIXES = ('_test', '_debug', '_tmp')
EXCLUDE_CONTAINS = ('_out.', '_err.')

def is_quick_excluded(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True
    name = path.name
    lower = name.lower()
    stem = path.stem.lower()
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return True
    if stem.startswith(EXCLUDE_PREFIXES):
        return True
    if any(x in lower for x in EXCLUDE_CONTAINS):
        return True
    return False

def quick_scan_files(root: Path) -> dict[str, list[str]]:
    root = root.resolve()
    files = {ft.value: [] for ft in FileType}
    candidates: list[Path] = []

    for rel in QUICK_DIRS:
        base = root / rel
        if not base.exists():
            continue
        if base.is_file():
            candidates.append(base)
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dp = Path(dirpath)
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not is_quick_excluded(dp / d)]
            for fname in filenames:
                candidates.append(dp / fname)

    for p in root.iterdir():
        if p.is_file() and (p.name in QUICK_ROOT_FILES or p.suffix.lower() in QUICK_ROOT_EXTS):
            candidates.append(p)

    # MEMORY.md is the memory index. Historical memory files are intentionally not scanned by default.
    memory_index = root / 'MEMORY.md'
    if memory_index.exists():
        candidates.append(memory_index)

    seen: set[str] = set()
    for p in sorted(candidates, key=lambda x: str(x)):
        if is_quick_excluded(p):
            continue
        try:
            resolved = str(p.resolve())
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        ftype = classify_file(p)
        if ftype in (FileType.CODE, FileType.DOCUMENT):
            files[ftype.value].append(resolved)

    return files

def file_hash(path: Path) -> str:
    h = hashlib.md5()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def quick_detect_incremental(root: Path) -> dict:
    root = root.resolve()
    files = quick_scan_files(root)
    manifest = load_manifest(root=root)
    new_files = {k: [] for k in files}
    unchanged_files = {k: [] for k in files}

    for ftype, file_list in files.items():
        for f in file_list:
            p = Path(f)
            stored = manifest.get(f)
            changed = stored is None
            if isinstance(stored, (int, float)):
                try:
                    changed = p.stat().st_mtime != stored
                except OSError:
                    changed = True
            elif isinstance(stored, dict):
                try:
                    current_mtime = p.stat().st_mtime
                except OSError:
                    current_mtime = 0
                stored_mtime = stored.get('mtime')
                stored_hash = stored.get('semantic_hash') or stored.get('ast_hash') or stored.get('hash') or ''
                if not stored_hash or not isinstance(stored_mtime, (int, float)):
                    changed = True
                elif current_mtime == stored_mtime:
                    changed = False
                else:
                    try:
                        changed = file_hash(p) != stored_hash
                    except OSError:
                        changed = True
            if changed:
                new_files[ftype].append(f)
            else:
                unchanged_files[ftype].append(f)

    total_files = sum(len(v) for v in files.values())
    return {
        'files': files,
        'incremental': True,
        'new_files': new_files,
        'unchanged_files': unchanged_files,
        'new_total': sum(len(v) for v in new_files.values()),
        'total_files': total_files,
        'total_words': 0,
        'skipped_sensitive': [],
    }

def main():
    ap = argparse.ArgumentParser(description='策划工具箱 知识图谱一键构建')
    ap.add_argument('--full', action='store_true', help='全量重建（默认增量）')
    ap.add_argument('--no-viz', action='store_true', help='跳过 HTML 生成')
    ap.add_argument('--force', action='store_true', help='强制覆盖旧图谱（全量重建时自动启用）')
    args = ap.parse_args()

    t0 = time.time()
    existing_graph = (OUT / 'graph.json').exists()

    # 全量重建时自动启用 force
    if args.full:
        args.force = True

    # ─── Step 1: 检测文件 ───
    if not args.full and existing_graph:
        print('[1/5] detect (quick incremental)...', end=' ', flush=True)
        detection = quick_detect_incremental(Path('.'))
        changed = [f for files in detection.get('new_files', {}).values() for f in files]
        print(f'{len(changed)} changed files / {detection["total_files"]} scanned in {time.time()-t0:.1f}s')
        if not changed:
            print('       No changes since last build. Skipping.')
            return
    else:
        mode = 'full' if args.full else 'initial'
        print(f'[1/5] detect ({mode})...', end=' ', flush=True)
        detection = detect(Path('.'))
        changed = None
        print(f'{detection["total_files"]} files / {detection["total_words"]:,} words in {time.time()-t0:.1f}s')

    # ─── Step 2: AST 提取 ───
    t1 = time.time()
    print('[2/5] AST extract...', end=' ', flush=True)
    code_files = []
    for f in detection.get('files', {}).get('code', []):
        code_files.extend(collect_files(Path(f)) if Path(f).is_dir() else [Path(f)])

    if changed is not None:
        code_files = [f for f in code_files if str(f) in changed]

    if code_files:
        ast = ast_extract(code_files)
        print(f'{len(ast["nodes"])} nodes, {len(ast["edges"])} edges in {time.time()-t1:.1f}s')
    else:
        ast = {'nodes': [], 'edges': [], 'input_tokens': 0, 'output_tokens': 0}
        print('0 nodes (no code files)')

    # ─── Step 3: 语义提取（文档节点 + 缓存） ───
    t2 = time.time()
    print('[3/5] semantic extract...', end=' ', flush=True)
    doc_files = detection.get('files', {}).get('document', [])
    all_scan_files = [f for files in detection['files'].values() for f in files]

    # Check cache
    cached_nodes, cached_edges, cached_hyperedges, uncached = check_semantic_cache(all_scan_files)

    doc_nodes = list(cached_nodes)
    doc_edges = list(cached_edges)
    doc_hyperedges = list(cached_hyperedges)

    if uncached:
        for df in uncached:
            p = Path(df)
            stem = p.stem
            doc_nodes.append({
                'id': f'doc_{stem}',
                'label': p.name,
                'file_type': 'document',
                'source_file': p.name,
                'source_location': None, 'source_url': None,
                'captured_at': None, 'author': None, 'contributor': None
            })
        # Save to cache
        new_nodes = [n for n in doc_nodes if n['id'] not in {c['id'] for c in cached_nodes}]
        save_semantic_cache(new_nodes, [], [])

    semantic = {
        'nodes': doc_nodes, 'edges': doc_edges, 'hyperedges': doc_hyperedges,
        'input_tokens': 0, 'output_tokens': 0,
    }
    print(f'{len(doc_nodes)} doc nodes ({len(cached_nodes)} cached, {len(uncached)} new) in {time.time()-t2:.1f}s')

    # ─── Step 4: 合并 + 构建图 + 聚类 ───
    t3 = time.time()
    print('[4/5] build & cluster...', end=' ', flush=True)

    if not args.full and existing_graph:
        # Merge with existing graph (preserve old semantic data)
        old = json.loads((OUT / 'graph.json').read_text(encoding='utf-8'))
        G_old = json_graph.node_link_graph(old, edges='links')
        G_new = build_from_json({
            'nodes': ast['nodes'] + semantic['nodes'],
            'edges': ast['edges'] + semantic['edges'],
            'hyperedges': semantic.get('hyperedges', []),
        })
        G_old.update(G_new)
        G = G_old
    else:
        seen = {n['id'] for n in ast['nodes']}
        merged_nodes = list(ast['nodes'])
        for n in semantic['nodes']:
            if n['id'] not in seen:
                merged_nodes.append(n)
                seen.add(n['id'])
        merged = {
            'nodes': merged_nodes,
            'edges': ast['edges'] + semantic['edges'],
            'hyperedges': semantic.get('hyperedges', []),
        }
        G = build_from_json(merged)

    communities = cluster(G)
    cohesion = score_all(G, communities)
    print(f'{G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(communities)} communities in {time.time()-t3:.1f}s')

    # ─── Step 5: 分析 + 导出 ───
    t4 = time.time()
    print('[5/5] analyze & export...', end=' ', flush=True)

    tokens = {'input': ast.get('input_tokens', 0), 'output': ast.get('output_tokens', 0)}
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    labels = {cid: f'Community {cid}' for cid in communities}
    questions = suggest_questions(G, communities, labels)

    # ── 生成自定义可读报告 ──
    today = time.strftime('%Y-%m-%d %H:%M')
    report_lines = [
        f'# 策划工具箱知识图谱报告',
        f'生成时间：{today}',
        f'',
        f'## 概况',
        f'- 项目文件：{detection["total_files"]} 个',
        f'- 图谱节点：{G.number_of_nodes()} 个（代码 {len([n for n in G.nodes() if G.nodes[n].get("file_type")=="code"])}，文档 {len([n for n in G.nodes() if G.nodes[n].get("file_type")=="document"])}）',
        f'- 关系边数：{G.number_of_edges()} 条',
        f'- 社区数：{len(communities)} 个',
        f'',
        f'## 核心模块（高连接度节点）',
    ]
    for i, g in enumerate(gods[:15], 1):
        report_lines.append(f'{i}. **{g["label"]}** — {g["degree"]} 条连接')
    report_lines.append('')

    # 按模块/分组展示文件
    file_nodes = {}
    for n in G.nodes():
        nd = G.nodes[n]
        if nd.get('file_type') != 'code':
            continue
        src = nd.get('source_file', '')
        if not src:
            continue
        base = nd.get('label', n)
        file_nodes.setdefault(src, []).append(base)
    report_lines.append(f'## 代码文件结构（{len(file_nodes)} 个文件）')
    for fname in sorted(file_nodes.keys()):
        funcs = file_nodes[fname]
        report_lines.append(f'- **{fname}** — {len(funcs)} 节点')
    report_lines.append('')

    # Top 25 社区摘要
    sorted_comms = sorted(communities.items(), key=lambda x: cohesion.get(x[0], 0), reverse=True)
    report_lines.append(f'## 社区分组（Top 25 / {len(communities)} 个）')
    shown = 0
    for cid, nodes in sorted_comms:
        if shown >= 25:
            break
        real = [n for n in nodes if G.nodes[n].get('file_type') != 'document']
        if len(real) < 3:
            continue
        score = cohesion.get(cid, 0)
        samples = [G.nodes[n].get('label', n) for n in real[:5]]
        files_in = {}
        for n in real:
            sf = G.nodes[n].get('source_file', '')
            if sf:
                files_in[sf] = files_in.get(sf, 0) + 1
        top_files = sorted(files_in, key=files_in.get, reverse=True)[:3]
        shown += 1
        report_lines.extend([
            f'### {labels.get(cid, f"Community {cid}")}',
            f'- 凝聚度：{score}',
            f'- 节点：{", ".join(samples)}{"..." if len(real) > 5 else ""}',
            f'- 文件：{", ".join(top_files)}' if top_files else '',
            '',
        ])

    # 跨模块连接
    if surprises:
        report_lines.append('## 跨模块连接（你可能不知道的关联）')
        for s in surprises[:10]:
            conf = s.get('confidence', '')
            relation = s.get('relation', 'related_to')
            report_lines.append(f'- `{s["source"]}` → `{s["target"]}` [{conf}]')
        report_lines.append('')

    # 凌散节点（知识缺口）
    isolated = [n for n in G.nodes() if G.degree(n) <= 1 and G.nodes[n].get('file_type') == 'code']
    if isolated:
        report_lines.append(f'## 孤立节点（{len(isolated)} 个代码节点仅 0-1 条连接）')
        for n in sorted(isolated, key=lambda x: G.nodes[x].get('source_file', ''))[:20]:
            nd = G.nodes[n]
            report_lines.append(f'- {nd.get("label", n)} ({nd.get("source_file", "?")})')
        if len(isolated) > 20:
            report_lines.append(f'- ... 还有 {len(isolated)-20} 个')
        report_lines.append('')

    (OUT / 'GRAPH_REPORT.md').write_text('\n'.join(report_lines), encoding='utf-8')
    to_json(G, communities, str(OUT / 'graph.json'), force=args.force)
    save_manifest(detection['files'])

    if not args.no_viz and G.number_of_nodes() <= 5000:
        to_html(G, communities, str(OUT / 'graph.html'), community_labels=labels or None)

    print(f'done in {time.time()-t4:.1f}s')

    # ─── Summary ───
    total = time.time() - t0
    print(f'\n{"="*50}')
    print(f'  Graph complete in {total:.1f}s')
    print(f'  {G.number_of_nodes()} nodes | {G.number_of_edges()} edges | {len(communities)} communities')
    print(f'  Outputs: graphify-out/')
    print(f'    graph.html        - interactive graph')
    print(f'    graph.json        - raw data')
    print(f'    GRAPH_REPORT.md   - audit report')
    print(f'{"="*50}')

    # Top 3 god nodes
    if gods:
        print(f'\n  Top God Nodes:')
        for g in gods[:5]:
            print(f'    {g["label"]} ({g["degree"]} edges)')

    # Hyperedges
    hyps = semantic.get('hyperedges', [])
    if hyps:
        print(f'\n  Hyperedges ({len(hyps)}):')
        for h in hyps:
            print(f'    {h["label"]} [{h["confidence"]} {h.get("confidence_score",""):.2f}]')


if __name__ == '__main__':
    main()
