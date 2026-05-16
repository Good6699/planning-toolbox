"""
graphify_quick.py — 策划工具箱知识图谱一键构建
用法:
  python graphify_quick.py              # 增量更新（默认，只处理变更文件）
  python graphify_quick.py --full      # 全量重建
  python graphify_quick.py --no-viz    # 跳过 HTML 生成
  python graphify_quick.py --full --no-viz
"""
import json, sys, time, argparse
from pathlib import Path
from graphify.detect import detect, detect_incremental, save_manifest
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

def main():
    ap = argparse.ArgumentParser(description='策划工具箱 知识图谱一键构建')
    ap.add_argument('--full', action='store_true', help='全量重建（默认增量）')
    ap.add_argument('--no-viz', action='store_true', help='跳过 HTML 生成')
    args = ap.parse_args()

    t0 = time.time()
    existing_graph = (OUT / 'graph.json').exists()

    # ─── Step 1: 检测文件 ───
    if not args.full and existing_graph:
        print('[1/5] detect (incremental)...', end=' ', flush=True)
        inc = detect_incremental(Path('.'))
        changed = [f for files in inc.get('new_files', {}).values() for f in files]
        print(f'{len(changed)} changed files in {time.time()-t0:.1f}s')
        if not changed:
            print('       No changes since last build. Skipping.')
            return
        # Full detect still needed for report accuracy
        detection = detect(Path('.'))
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

    report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, '.',
                      suggested_questions=questions)
    (OUT / 'GRAPH_REPORT.md').write_text(report, encoding='utf-8')
    to_json(G, communities, str(OUT / 'graph.json'))
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
